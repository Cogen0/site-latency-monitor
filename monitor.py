#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
站点延迟监控脚本（由 GitHub Actions 每 30 分钟调用一次）

核心设计：每个站点独立调度，互不影响。
每个站点在 sites.json 里自带调度参数：
  - mode: "fixed"  -> 每隔 interval_hours 小时访问一次
          "random" -> 每次访问后，在 random_min_hours~random_max_hours 之间随机安排下次访问
  - max_runs: 最多"自动"访问多少次（0 = 不限次数）
  - window（可选）: 仅允许在每日 [start, end] 时段内发起访问（HH:MM 格式，end 早于 start 视为跨午夜）

每轮只访问"当前已到期"的站点，未到期的站点不访问。
结果写入 history.json（每站点保留最近 5 次）；调度状态写入 last_run.json。

支持 --force 参数：强制访问所有启用的站点（忽略调度、每日窗口与自动次数限制），
供网页"立即运行一轮"按钮使用。
注意：--force 是手动临时检查，不消耗该站点的自动访问配额（auto_runs）、
不推迟自动调度时间（last_ts / next_ts 不更新），因此手动触发不影响自动计划。

所有记录时间统一为北京时间（UTC+8，GitHub Actions 系统时间为 UTC）。

仅使用 Python 标准库（urllib + argparse），GitHub Actions 的 ubuntu-latest 环境开箱即用。
"""
import argparse
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
BEIJING_OFFSET = timedelta(hours=8)   # 北京时间 = UTC + 8


def now_bj():
    """返回当前北京时间（naive datetime），用于所有记录与调度判断"""
    return datetime.utcnow() + BEIJING_OFFSET


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
        print("[warn] window 配置格式非法，忽略窗口限制")
        return True
    if start_min <= end_min:
        return start_min <= now_min <= end_min
    else:  # 跨午夜窗口，例如 22:00 - 06:00
        return now_min >= start_min or now_min <= end_min


def site_due(site, state, now):
    """判断某站点本轮是否需要访问；返回 (due, reason)
    max_runs 只统计"自动访问次数"（auto_runs），手动 --force 不消耗配额"""
    max_runs = int(site.get("max_runs", 0) or 0)
    auto_runs = int(state.get("auto_runs", 0))
    if max_runs > 0 and auto_runs >= max_runs:
        return False, f"自动访问次数已达上限 {max_runs}（如需继续请改大 max_runs）"

    mode = site.get("mode", "fixed")
    if mode == "random":
        next_ts = state.get("next_ts")
        if not next_ts:
            return True, "首次运行，立即访问"
        try:
            next_dt = datetime.strptime(next_ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return True, "next_ts 解析失败，立即访问"
        return now >= next_dt, f"计划访问时间 {next_ts}"
    else:
        interval_h = float(site.get("interval_hours", 24))
        last_ts = state.get("last_ts", "2000-01-01 00:00:00")
        try:
            last_dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            last_dt = datetime(2000, 1, 1)
        elapsed = (now - last_dt).total_seconds() / 3600
        return elapsed >= interval_h, f"距上次访问 {elapsed:.2f}h（阈值 {interval_h}h）"


def main():
    parser = argparse.ArgumentParser(description="站点延迟监控脚本")
    parser.add_argument("--force", action="store_true",
                        help="强制访问所有启用的站点，忽略调度、每日窗口与自动次数限制")
    args = parser.parse_args()
    force = args.force

    config = load_json(CONFIG_FILE, {})
    sites = [s for s in config.get("sites", []) if s.get("enabled", True)]
    if not sites:
        print("[skip] 没有启用的站点，结束")
        return

    last_run = load_json(LAST_RUN_FILE, {})
    states = last_run.get("sites", {})
    now = now_bj()   # 北京时间
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    results = []
    for site in sites:
        url = site.get("url", "").strip()
        if not url:
            continue
        state = states.setdefault(url, {})

        if force:
            print(f"[force] {url}：强制访问（忽略调度、窗口与次数限制）")
        else:
            due, reason = site_due(site, state, now)
            if not due:
                print(f"[skip] {url}：{reason}")
                continue
            if not in_window(site.get("window"), now):
                print(f"[skip] {url}：当前 {now.strftime('%H:%M')} 不在该站点运行窗口内")
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

        # 更新该站点状态：
        # - run_count  总访问次数（含手动 force），仅用于展示
        # - auto_runs  自动访问次数（--force 不累加，不消耗 max_runs 配额）
        # - 手动 force 不更新 last_ts / next_ts，不影响自动调度
        state["run_count"] = int(state.get("run_count", 0)) + 1
        if not force:
            state["auto_runs"] = int(state.get("auto_runs", 0)) + 1
            state["last_ts"] = now_str
            if site.get("mode") == "random":
                min_h = float(site.get("random_min_hours", 1))
                max_h = float(site.get("random_max_hours", 12))
                next_dt = now + timedelta(seconds=random.uniform(min_h, max_h) * 3600)
                state["next_ts"] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[ok] {url} 下次随机访问时间：{state['next_ts']}")

    if results:
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

    # 只写回调度状态（不写 last_check_ts：避免每轮无变化也提交，
    # 从而触发 Vercel 等托管平台无谓的重新部署）
    last_run["sites"] = states
    save_json(LAST_RUN_FILE, last_run)


if __name__ == "__main__":
    main()
