#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
站点延迟监控脚本（由 GitHub Actions 定时调用）

功能：
1. 读取 sites.json 配置（运行模式 / 间隔 / 站点列表）
2. 判断本轮是否应该执行探测：
   - fixed 模式：距上次实际探测达到 interval_hours 小时则运行
   - random 模式：每次探测后，在 [random_min_hours, random_max_hours] 内
     随机决定下一次探测时间（"多久之内随机访问一次"）
   - 可选 window：仅允许在每日指定时间段 [start, end] 内运行（HH:MM 格式）
3. 对每个启用的站点发起 HTTP GET，记录延迟（毫秒）与状态码
4. 将结果追加到 history.json，每个站点只保留最近 5 次
5. 更新 last_run.json 供下次调度判断

仅使用 Python 标准库（urllib），GitHub Actions 的 ubuntu-latest 环境开箱即用。
"""
import json
import random
import time
import urllib.request
from datetime import datetime, timedelta

CONFIG_FILE = "sites.json"
HISTORY_FILE = "history.json"
LAST_RUN_FILE = "last_run.json"
KEEP_RECORDS = 5
TIMEOUT_SEC = 12


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[warn] 读取 {path} 失败({e})，使用默认值")
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_latency(url):
    """返回 (latency_ms, http_status)；失败时 latency_ms 为 None，status 为 -1"""
    start = time.time()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LatencyMonitor/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            latency_ms = round((time.time() - start) * 1000, 2)
            return latency_ms, resp.status
    except Exception as e:
        print(f"[warn] {url} 探测失败: {e}")
        return None, -1


def parse_hhmm(s):
    """将 'HH:MM' 解析为分钟数，非法时返回 None"""
    try:
        h, m = s.strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def in_window(window, now):
    """判断当前时间是否在每日运行窗口内（window: {"start":"09:00","end":"21:00"}）"""
    if not window:
        return True
    now_min = now.hour * 60 + now.minute
    start_min = parse_hhmm(window.get("start", ""))
    end_min = parse_hhmm(window.get("end", ""))
    if start_min is None or end_min is None:
        print("[warn] window 配置格式非法，期望 {'start':'HH:MM','end':'HH:MM'}，忽略窗口限制")
        return True
    if start_min <= end_min:
        return start_min <= now_min <= end_min
    else:  # 跨午夜窗口，例如 22:00 - 06:00
        return now_min >= start_min or now_min <= end_min


def should_run(config, last_run, now):
    """根据模式判断本轮是否执行探测"""
    mode = config.get("mode", "fixed")

    if mode == "fixed":
        interval_h = float(config.get("interval_hours", 24))
        last_ts = last_run.get("last_actual_run_ts", "2000-01-01 00:00:00")
        try:
            last_dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            last_dt = datetime(2000, 1, 1)
        due = (now - last_dt).total_seconds() >= interval_h * 3600
        reason = f"距上次探测 {(now-last_dt).total_seconds()/3600:.2f}h（阈值 {interval_h}h）"
    elif mode == "random":
        next_ts = last_run.get("next_run_ts")
        if not next_ts:
            due = True
            reason = "首次运行，立即探测"
        else:
            try:
                next_dt = datetime.strptime(next_ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                due, reason = True, "next_run_ts 解析失败，立即探测"
            else:
                due = now >= next_dt
                reason = f"当前 {now.strftime('%Y-%m-%d %H:%M:%S')} >= 计划时间 {next_ts}"
    else:
        due, reason = True, f"未知模式 {mode}，按立即执行处理"

    if due:
        print(f"[run] 本轮执行探测：{reason}")
    else:
        print(f"[skip] 本轮跳过：{reason}")
    return due


def main():
    config = load_json(CONFIG_FILE, {})
    sites = [s for s in config.get("sites", []) if s.get("enabled", True)]
    if not sites:
        print("[skip] 没有启用的站点，结束")
        return

    last_run = load_json(LAST_RUN_FILE, {})
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if not should_run(config, last_run, now):
        return

    window = config.get("window")
    if not in_window(window, now):
        print(f"[skip] 当前时间 {now.strftime('%H:%M')} 不在每日运行窗口内，跳过本轮")
        return

    # ---- 执行探测 ----
    results = []
    for site in sites:
        url = site.get("url", "").strip()
        if not url:
            continue
        latency_ms, status = fetch_latency(url)
        results.append({
            "url": url,
            "name": site.get("name", url),
            "latency_ms": latency_ms,
            "http_status": status,
            "ts": now_str,
        })
        print(f"[ok] {url} -> {latency_ms} ms, HTTP {status}")

    # ---- 更新历史（每站点保留最近 5 次）----
    history = load_json(HISTORY_FILE, [])
    history.extend(results)
    grouped = {}
    for item in history:
        grouped.setdefault(item["url"], []).append(item)
    new_history = []
    for u, arr in grouped.items():
        arr.sort(key=lambda x: x["ts"])
        new_history.extend(arr[-KEEP_RECORDS:])
    save_json(HISTORY_FILE, new_history)
    print(f"[ok] 已写入 history.json（共 {len(new_history)} 条记录）")

    # ---- 更新运行状态 ----
    last_run["last_actual_run_ts"] = now_str
    if config.get("mode") == "random":
        min_h = float(config.get("random_min_hours", 1))
        max_h = float(config.get("random_max_hours", 12))
        delta_sec = random.uniform(min_h, max_h) * 3600
        next_dt = now + timedelta(seconds=delta_sec)
        last_run["next_run_ts"] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[ok] 下次随机探测时间：{last_run['next_run_ts']}（{min_h}-{max_h}h 之间随机）")
    save_json(LAST_RUN_FILE, last_run)


if __name__ == "__main__":
    main()
