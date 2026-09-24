# 站点延迟监控（GitHub Pages + GitHub Actions）

通过 GitHub Actions 定时访问你指定的网站，测量 HTTP 访问延迟并记录最近 5 次结果；通过 GitHub Pages（可绑定你自己的域名）提供一个带密码登录的监控面板，用于添加站点、设置访问间隔、查看延迟数据。

## 功能

- 密码登录后才可查看面板数据
- 网页上直接添加 / 删除 / 启停监控站点
- **自动同步**：填写一次 GitHub 仓库与 Token 后，网页上的所有修改（添加站点、调整间隔等）自动同步到仓库 `sites.json`，无需手动保存
- 两种调度模式（修改后自动生效，无需改代码）：
  - **固定间隔**：每隔 N 小时访问一次所有站点
  - **随机间隔**：每次探测后，在 N1~N2 小时之间随机决定下一次访问时间（"多久之内随机访问一次"）
  - 可选的每日运行窗口（如只在 09:00~21:00 之间运行）
  - 可选的最大运行次数 `max_runs`（达到后自动停止，0 = 不限）
- 每个站点显示最近 5 次访问的延迟（毫秒）、HTTP 状态码与趋势条
- 一键"立即运行一轮"：直接触发 GitHub Actions 立刻探测，无需等定时

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `index.html` | 监控面板页面（GitHub Pages 首页），含密码登录与全部前端逻辑 |
| `monitor.py` | Actions 中运行的探测脚本（Python 标准库，无第三方依赖） |
| `sites.json` | 监控配置：模式、间隔、站点列表（前端可读写） |
| `history.json` | 延迟历史记录，Actions 自动写入，每站点保留 5 条 |
| `last_run.json` | 调度状态记录（上次实际探测时间 / 下次随机探测时间） |
| `CNAME` | 自定义域名文件（内容改为你的域名，无 http/https 前缀） |
| `.github/workflows/monitor.yml` | GitHub Actions 定时工作流（每 10 分钟检查一次是否到期） |

## 部署步骤

### 1. 上传到 GitHub

1. 在 GitHub 新建一个仓库（公开或私有均可，建议公开，Pages 免费且 Actions 无限额）。
2. 把本目录**所有文件**（含隐藏的 `.github` 文件夹）上传到仓库 main 分支。

### 2. 修改访问密码

打开 `index.html`，把顶部 `const PASSWORD = "change-me-123";` 改成你自己的密码，重新提交。

### 3. 开启 Actions 写权限（关键步骤）

仓库 `Settings` → `Actions` → `General` → `Workflow permissions` → 勾选 **Read and write permissions** → 保存。
否则 Actions 无法把 `history.json` / `last_run.json` 提交回仓库。

### 4. 开启 GitHub Pages 并绑定域名

仓库 `Settings` → `Pages`：

1. **Branch**：选择 `Deploy from a branch` → 分支 `main`，目录 `/ (root)` → Save。
2. **Custom domain**：填入你的域名（例如 `monitor.example.com`），点击 Save。
   GitHub 会自动在仓库根目录生成/更新 `CNAME` 文件（内容即你的域名）。
3. 等待约 1 分钟，Pages 构建完成后即可通过 `https://<用户名>.github.io/<仓库名>/` 访问。

### 5. 域名解析（DNS）

到你的域名服务商（阿里云 / 腾讯云 / Cloudflare 等）添加一条解析记录，指向 GitHub Pages：

- 若用**主域名**（如 `example.com`）：添加 4 条 `A` 记录，指向
  `185.199.108.153`、`185.199.109.153`、`185.199.110.153`、`185.199.111.153`。
- 若用**子域名**（如 `monitor.example.com`）：添加一条 `CNAME` 记录，
  主机记录 `monitor`，记录值 `<你的GitHub用户名>.github.io`。

DNS 生效（几分钟~几小时）后，通过你的域名即可访问面板。

### 6. 测试 Actions

仓库 `Actions` 页 → 左侧 `Site Latency Monitor` → **Run workflow** → 手动触发一次。
观察运行日志，确认输出了 `[ok] ... -> xxx ms`。此时 `history.json` 会被更新并提交。

### 7. 在网页上配置监控站点（全自动）

1. 浏览器打开你的域名，输入密码登录。
2. 在「自动同步设置」卡片填写 GitHub 仓库（`用户名/仓库名`）与 Token，点**保存并立即同步**。
   - 创建 **Fine-grained Personal Access Token**：GitHub `Settings` → `Developer settings`
     → `Fine-grained tokens` → 仓库权限仅本仓库 → 勾选 `Contents: Read and write`
     （如想用「立即运行一轮」按钮，再勾选 `Actions: Read and write`）。
   - Token 只保存在你自己的浏览器 localStorage 中，不会写入代码或仓库。
3. 之后在页面上添加站点、修改间隔、切换启停……任何修改都会在约 1 秒内**自动同步**到仓库 `sites.json`，
   状态栏会显示"已自动同步到仓库（时间）"。
4. 想立刻验证：点**立即运行一轮**，GitHub Actions 马上执行探测，稍后刷新页面即可看到最近 5 次延迟。

> 若没有填写 Token，页面不会自动同步，但仍可通过「复制 JSON」手动到仓库替换 `sites.json`。

## 配置字段说明（sites.json）

```json
{
  "mode": "fixed | random",
  "interval_hours": 24,
  "random_min_hours": 1,
  "random_max_hours": 12,
  "max_runs": 0,
  "window": { "start": "09:00", "end": "21:00" },
  "sites": [{ "name": "站点名", "url": "https://...", "enabled": true }]
}
```

- `mode: "fixed"`：使用 `interval_hours`，每隔该小时数探测一次。
- `mode: "random"`：使用 `random_min_hours` / `random_max_hours`，每次探测后在此区间随机安排下次时间。
- `max_runs`：最大运行次数，达到后自动停止探测（`0` 或省略 = 不限次数）。
- `window`：可留空（全天运行）；也可限制每日运行时段。`end` 早于 `start` 表示跨午夜（如 22:00~06:00）。
- `window` 只限制探测开始时间，不代表"随机到某时刻"；随机性由 `mode: "random"` 提供。

## 注意事项

- **探测节点在海外**：GitHub Actions 运行在 GitHub 的海外服务器上，测出的延迟是海外节点到目标站点的延迟，
  并非你所在地区用户的访问速度。若要测量国内真实延迟，请改用国内云服务器 / 云函数方案。
- **调度粒度**：GitHub Actions 的 cron 最小为分钟级，本方案每 10 分钟检查一次是否到期，实际执行时间误差约 10 分钟以内。
- **密码为前端校验**：登录密码仅防止随意浏览，懂技术的人仍可通过查看仓库源码或直接访问数据文件读取内容。
  如需严格鉴权，需要后端服务（云服务器 / 云函数）。
- **历史数据是仓库的一部分**：`history.json` 每次更新会产生一次 commit，属于正常现象。

## 常见问题

- **页面空白 / 登录后提示无法读取 sites.json**：确认已部署到 Pages 且 `index.html`、`sites.json`、`history.json` 都在仓库根目录。
- **Actions 不更新数据**：检查 `Workflow permissions` 是否已设为 Read and write；检查 Actions 运行日志。
- **保存到仓库失败**：检查 Token 权限（Contents: Read and write）与仓库名格式（`用户名/仓库名`）。
- **域名访问 404**：检查 DNS 是否生效、`CNAME` 文件内容是否为你的域名、Pages 的 Custom domain 是否填写并保存。
