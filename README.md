# 站点延迟监控（GitHub Actions 探测 + Vercel 托管）

通过 GitHub Actions 定时访问你指定的网站，测量 HTTP 访问延迟并记录最近 5 次结果；页面由 **Vercel** 免费托管并绑定你自己的域名 `2dh.cc.cd`。

**为什么用 Vercel**：GitHub 免费账号的 Private 仓库不能启用 GitHub Pages，而 **Vercel 免费支持从 Private 仓库部署**。更关键的是——**Token 不再放在网页源码里**（Public/Private 仓库都会被 GitHub 强制失效，且网页源码任何人可见），而是只存在 **Vercel 的环境变量**中，通过 Vercel 服务端函数代理写回仓库。仓库源码、页面源码、Token 三者彻底分离，全部安全。

**核心特性：每个网站独立调度、互不影响。** 添加网站时分别为它设定"多久访问一次、共访问多少次"（固定间隔或随机间隔），各网站按自己的时间表运行。

## 功能

- 密码登录，登录后 **2 小时内免重复登录**
- **每个站点独立配置**（添加时设定）：
  - 访问模式：**固定间隔**（每隔 N 小时访问一次）或**随机间隔**（每次访问后，在 N1~N2 小时之间随机安排下次）
  - 访问次数 `max_runs`：最多访问多少次（0 = 不限），达到后该站点自动停止
  - 可选每日运行窗口（如只在 09:00~21:00 之间访问）
- 网页上添加 / 编辑 / 删除 / 启停监控站点
- **自动同步（无需任何客户端设置）**：换任何浏览器 / 设备打开都一样；网页上的所有修改自动写入仓库 `sites.json`
- 一键"立即运行一轮"：触发 GitHub Actions **强制访问当前所有启用的站点**（忽略间隔、次数与窗口限制）
- 每个站点显示最近 5 次访问的延迟（毫秒）、HTTP 状态码与趋势条

## 架构（安全设计）

```
你打开 2dh.cc.cd（Vercel 托管的页面 + 服务端函数）
   │  读取：fetch sites.json / history.json（Vercel 静态文件）
   │  写入：fetch /api/save  →  服务端函数用 GH_TOKEN（Vercel 环境变量）→ GitHub API 写 sites.json
   │  触发：fetch /api/run   →  服务端函数用 GH_TOKEN → 触发 GitHub Actions
GitHub 仓库（Private，源码中不含任何密钥）
   ├─ index.html / sites.json / history.json / last_run.json   ← 页面数据
   ├─ api/save.js / api/run.js  ← Vercel 服务端函数（Token 从环境变量读取）
   ├─ monitor.py          ← 探测脚本（每站点独立调度）
   └─ .github/workflows/monitor.yml  ← 每 30 分钟跑一次；有数据变化才提交
                                        → Vercel 检测到 push 自动重新部署
Token 只存在于：Vercel 项目设置 → Environment Variables → GH_TOKEN（加密存储）
```

**安全性说明**：`GH_TOKEN` 只配置在 Vercel 环境变量里，不出现在 index.html、api/*.js 或任何仓库文件中；即使网页源码公开、仓库转 Public，也没有 Token 可看，GitHub 的 Secret Scanning 也不会再检测或强制失效。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `index.html` | 监控面板（Vercel 托管的首页），含密码登录、站点独立配置、自动同步与历史展示；不含任何 Token |
| `api/save.js` | Vercel 服务端函数：网页修改站点后，用它写回 GitHub `sites.json` |
| `api/run.js` | Vercel 服务端函数：网页点"立即运行一轮"，用它触发 GitHub Actions |
| `monitor.py` | Actions 中运行的探测脚本，逐站点独立调度（Python 标准库，无第三方依赖） |
| `sites.json` | 站点配置：每个站点自带模式/间隔/次数/窗口 |
| `history.json` | 延迟历史记录，Actions 自动写入，每站点保留 5 条 |
| `last_run.json` | 各站点调度状态（上次访问时间 / 下次随机时间 / 已访问次数） |
| `CNAME` | 仅 GitHub Pages 需要；**Vercel 完全忽略**，可保留可删除 |
| `.github/workflows/monitor.yml` | GitHub Actions 定时工作流（每 30 分钟检查一次各站点是否到期） |

---

# 部署步骤（详细）

## 第一步：上传源码到 GitHub（仓库保持 Private）

1. 仓库保持 **Private**（Vercel 支持私有仓库部署）。
2. 把 `F:\Desktop\dingshifangwen` 里的**全部文件**上传覆盖到 main 分支（含新增的 `api/` 文件夹：`api/save.js`、`api/run.js`）。
3. **`.github/workflows/monitor.yml` 是隐藏文件夹，网页上传传不上去**，二选一：
   - 网页方式：仓库页 **Add file → Create new file**，文件名框输入 `.github/workflows/monitor.yml`，
     把本地该文件内容整体粘贴进去 → Commit changes（GitHub 自动创建目录）。
   - 命令行方式（一次推送全部含隐藏文件）：
     ```
     cd F:\Desktop\dingshifangwen
     git init
     git remote add origin https://github.com/Cogen0/site-latency-monitor.git
     git add -A
     git commit -m "v4 vercel secure"
     git push -u origin main
     ```
4. 开启 Actions 写权限：仓库 **Settings → Actions → General → Workflow permissions**
   → 勾选 **Read and write permissions** → Save。（否则 Actions 无法把数据写回仓库）

> 注意：**不需要**在 index.html 里填 Token——这一步已经彻底去掉了。Token 在第二步配置到 Vercel。

## 第二步：创建 Token 并配置到 Vercel

1. **创建 GitHub Token**（只在本步用到一次）：
   GitHub → 头像 → **Settings** → **Developer settings** → **Personal access tokens** →
   **Fine-grained tokens** → Generate new token →
   - Repository access 选 **Only select repositories** → 勾选 `site-latency-monitor`
   - Permissions 勾选 `Contents: Read and write` + `Actions: Read and write`
   - 有效期设短一些（如 30 天）→ 生成后复制（只显示一次）。
2. **把 Token 填到 Vercel 环境变量**（不要填到任何网页/仓库文件里）：
   - Vercel 项目页 → **Settings → Environment Variables**
   - Key 填 `GH_TOKEN`，Value 粘贴你的 Token
   - Environments 勾选 Production（+ Preview、Development 可选）
   - 点 **Save**。**保存后到项目 Deployments 重新 Deploy 一次**（环境变量对已有部署不生效，重新部署后生效）。

## 第三步：在 Vercel 部署（免费）

1. 打开 **vercel.com**，用 **GitHub 账号**登录（或注册后用 GitHub 授权）。
2. 点 **Add New… → Project**。
3. 列表里找到 **site-latency-monitor** → 点 **Import**。
   - 首次会要求授权：点 **Install** 安装 Vercel 的 GitHub App，授权范围选 **Only select repositories**（只勾选这一个仓库）。
4. 配置页（Configure Project）：
   - **Framework Preset**：选 **Other**（不要选 Next.js 等框架）
   - **Build Command**：留空
   - **Output Directory**：留空
   - 其余默认 → 点 **Deploy**
5. 等 1~2 分钟，部署完成会显示 **https://site-latency-monitor-xxxx.vercel.app**。
6. 打开该地址：应能看到登录页，输入密码（`aaa000eee`）进入。**先测一下自动同步**：
   添加一个站点 → 顶部状态应显示"已自动同步到仓库"（说明 /api/save + 环境变量工作正常）。
   若提示"GH_TOKEN 未配置"，回第二步补环境变量并重新部署。

> 之后每次 GitHub 仓库有新的 commit（Actions 写入数据、网页同步配置），Vercel 自动重新部署，页面数据自动更新。

## 第四步：绑定域名 2dh.cc.cd

1. Vercel 项目页 → **Settings** → **Domains** → 输入 `2dh.cc.cd` → **Add**。
2. 按 Vercel 页面提示配置 DNS（二选一）：
   - 主域名 `2dh.cc.cd`：**A 记录 → `76.76.21.21`**
   - 或 CNAME → `cname.vercel-dns.com`（视域名服务商是否支持裸域名 CNAME）
3. 到你的**域名服务商后台**修改记录：
   - **删除**之前指向 GitHub Pages 的记录（4 条 `185.199.108~111.153` 的 A 记录、
     `www` 指向 `Cogen0.github.io` 的 CNAME）
   - **添加** Vercel 要求的记录（主域名 A → `76.76.21.21`，`www` CNAME → `cname.vercel-dns.com`）
   - 想 www 也能访问，回 Vercel Domains 里再加 `www.2dh.cc.cd`
4. DNS 生效需几分钟到几小时。生效后打开 `https://2dh.cc.cd` 应显示登录页。Vercel 自动申请 HTTPS 证书。

## 第五步：验证全流程

1. 仓库 **Actions** 页：应能看到 **Site Latency Monitor** 工作流。
2. 点 **Run workflow**（可选勾选 **force_all**，强制访问全部站点）手动跑一次。
3. 打开 `https://2dh.cc.cd` → 登录 → **添加站点**：名称、网址、模式（固定/随机）、间隔、**访问次数**（0=不限）、可选每日窗口。
4. 添加后自动同步；等 Actions 按调度运行后，「最近 5 次访问延迟」出现数据。想立即看效果，点**立即运行一轮**，1~2 分钟后刷新。

---

## 配置字段说明（sites.json）

```json
{
  "sites": [
    {
      "name": "站点名",
      "url": "https://...",
      "enabled": true,
      "mode": "fixed | random",
      "interval_hours": 4,
      "random_min_hours": 1,
      "random_max_hours": 12,
      "max_runs": 0,
      "window": { "start": "09:00", "end": "21:00" }
    }
  ]
}
```

- `mode: "fixed"`：每隔 `interval_hours` 小时访问一次。
- `mode: "random"`：每次访问后，在 `random_min_hours` ~ `random_max_hours` 之间随机安排下次访问时间。
- `max_runs`：该站点最多访问次数，达到后自动停止（`0` = 不限）。
- `window`：可留空（全天）；`end` 早于 `start` 表示跨午夜（如 22:00~06:00）。

## 注意事项

- **部署频率**：monitor.py 只在有站点实际被访问时才写回数据，所以只有数据变化才触发 Vercel 重新部署，不会每 30 分钟无谓构建。
- **Vercel 免费计划限制**：Hobby 计划每月有一定构建与带宽额度（日常监控完全够用）。
  若收到构建次数告警，可把 `monitor.yml` 的 cron 改为 `0 * * * *`（每小时检查一次），误差相应变大。
- **探测节点在海外**：GitHub Actions 运行在 GitHub 海外服务器，测出的延迟是海外节点到目标站的延迟，并非你所在地区用户的访问速度。
- **登录密码为前端校验**：登录仅防止随意浏览，懂技术的人仍可通过查看仓库源码或直接访问数据文件读取内容。
- **Token 安全**：`GH_TOKEN` 只存在于 Vercel 环境变量，任何仓库文件、页面源码都不含 Token。
  Token 到期（30 天）后只需回 Vercel 环境变量更新新 Token 并重新部署，网页无需改动。
- **`history.json` / `last_run.json` 由 Actions 自动管理**，每次更新产生一次 commit，属正常现象。

## 常见问题

- **页面提示"GH_TOKEN 未配置"**：Vercel 项目 Settings → Environment Variables 添加 `GH_TOKEN` 后，
  Deployments 里重新 Deploy 一次。
- **Vercel 部署后是空白页 / 404**：确认 `index.html` 在仓库根目录；Framework Preset 是否选了 Other。
- **Actions 页面没有 Site Latency Monitor**：`.github/workflows/monitor.yml` 没传成功，
  用网页 Add file → Create new file 填路径 `.github/workflows/monitor.yml` 重建。
- **Actions 不更新数据**：检查 Settings → Actions → Workflow permissions 是否 Read and write；看运行日志。
- **网页同步失败 / 提示 HTTP 500**：Vercel 函数日志（Deployments → 查看运行日志）会写明原因；
  常见为环境变量未配置或 Token 无 Contents 权限。
- **域名打不开**：确认 DNS 记录已从 GitHub Pages 改为 Vercel（A → 76.76.21.21），等待生效；
  可先用 Vercel 分配的 `xxx.vercel.app` 地址确认站点本身正常。
- **网页修改配置没同步**：确认页面顶部状态显示"已自动同步到仓库"；若失败，按上面日志排查。
