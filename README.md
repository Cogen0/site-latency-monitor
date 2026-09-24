# 站点延迟监控（GitHub Pages + GitHub Actions）

通过 GitHub Actions 定时访问你指定的网站，测量 HTTP 访问延迟并记录最近 5 次结果；通过 GitHub Pages（可绑定你自己的域名）提供一个带密码登录的监控面板。

**核心特性：每个网站独立调度、互不影响。** 添加网站时分别为它设定"多久访问一次、共访问多少次"（固定间隔或随机间隔），各网站按自己的时间表运行，互不干扰。

## 功能

- 密码登录，登录后 **2 小时内免重复登录**
- **每个站点独立配置**（添加时设定）：
  - 访问模式：**固定间隔**（每隔 N 小时访问一次）或**随机间隔**（每次访问后，在 N1~N2 小时之间随机安排下次）
  - 访问次数 `max_runs`：最多访问多少次（0 = 不限），达到后该站点自动停止
  - 可选每日运行窗口（如只在 09:00~21:00 之间访问）
- 网页上添加 / 编辑 / 删除 / 启停监控站点
- **自动同步（配置固化）**：同步配置直接固化在 `index.html` 顶部的 `GH_REPO` / `GH_TOKEN` 常量中，
  换任何浏览器 / 设备打开都一样，无需在页面上重复设置；网页上的所有修改自动同步到仓库 `sites.json`
- 一键"立即运行一轮"：触发 GitHub Actions **强制访问当前所有启用的站点**（忽略间隔、次数与窗口限制）
- 每个站点显示最近 5 次访问的延迟（毫秒）、HTTP 状态码与趋势条

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `index.html` | 监控面板页面（GitHub Pages 首页），含密码登录、站点独立配置、自动同步与历史展示 |
| `monitor.py` | Actions 中运行的探测脚本，逐站点独立调度（Python 标准库，无第三方依赖） |
| `sites.json` | 站点配置：每个站点自带模式/间隔/次数/窗口 |
| `history.json` | 延迟历史记录，Actions 自动写入，每站点保留 5 条 |
| `last_run.json` | 各站点调度状态（上次访问时间 / 下次随机时间 / 已访问次数） |
| `CNAME` | 自定义域名文件（内容为你的域名，无 http/https 前缀） |
| `.github/workflows/monitor.yml` | GitHub Actions 定时工作流（每 10 分钟检查一次各站点是否到期） |

## 部署步骤

### 1. 上传到 GitHub（覆盖更新）

1. 把本目录**所有文件**上传到仓库 main 分支，覆盖旧文件。
2. **务必包含 `.github` 文件夹**（它是隐藏文件夹，Windows 上传前请在资源管理器「查看」中勾选"隐藏的项目"，确认 `.github/workflows/monitor.yml` 一起上传）。
3. 上传方式二选一：
   - 网页：Add file → Upload files，把文件拖入；或逐个 Create new file 粘贴内容。
   - 命令行（推荐，可一次推送全部含隐藏文件）：
     ```
     git clone https://github.com/Cogen0/site-latency-monitor
     # 把本目录所有文件复制进去，然后：
     cd site-latency-monitor
     git add -A
     git commit -m "update monitor v2"
     git push
     ```

### 2. 修改访问密码（如需）

打开 `index.html`，修改顶部 `const PASSWORD = "aaa000eee";` 为你自己的密码，重新提交。

### 3. 开启 Actions 写权限（关键步骤）

仓库 `Settings` → `Actions` → `General` → `Workflow permissions` → 勾选 **Read and write permissions** → 保存。
否则 Actions 无法把 `history.json` / `last_run.json` 提交回仓库。

### 4. 开启 GitHub Pages 并绑定域名

仓库 `Settings` → `Pages`：

1. **Branch**：选择 `Deploy from a branch` → 分支 `main`，目录 `/ (root)` → Save。
2. **Custom domain**：填入你的域名（如 `2dh.cc.cd`），点 Save。确认仓库根目录 `CNAME` 文件内容是你的域名。
3. 等待约 1 分钟，Pages 构建完成后即可通过域名访问。

### 5. 域名解析（DNS）

到你的域名服务商添加记录，指向 GitHub Pages：

- 主域名：4 条 `A` 记录指向 `185.199.108.153`、`185.199.109.153`、`185.199.110.153`、`185.199.111.153`。
- `www` 子域名：一条 `CNAME` 记录，值为 `<你的GitHub用户名>.github.io`。

DNS 生效（几分钟~几小时）后通过域名访问面板。GitHub 的 DNS 检查与 TLS 证书申请有延迟，界面提示等待属正常。

### 6. 测试 Actions

仓库 `Actions` 页 → `Site Latency Monitor` → **Run workflow** 手动触发一次。
日志中会看到每个到期站点输出 `[ok] ... -> xxx ms`，未到期站点输出 `[skip]`。

### 7. 在网页上配置监控站点

1. **把 GitHub Token 填入源码（只需一次）**：用记事本打开 `index.html`，把顶部
   `const GH_TOKEN = "";` 改为你的 Token，保存并重新上传 `index.html`。
   - 创建 **Fine-grained Personal Access Token**：GitHub `Settings` → `Developer settings` →
     `Personal access tokens` → `Fine-grained tokens` → 仓库权限仅本仓库 →
     勾选 `Contents: Read and write`（想用「立即运行一轮」按钮再加 `Actions: Read and write`）。
   - 配置固化在源码后，换任何浏览器 / 设备打开页面都直接可用，无需重复设置。
2. 打开你的域名，输入密码登录（2 小时内免重复登录）。
3. 添加站点：填写名称、网址，选择访问模式、间隔、**访问次数**（0=不限）、可选每日窗口，点**添加站点**。
   每个站点独立调度，互不影响。
4. 所有修改约 1 秒后自动同步到仓库 `sites.json`，Actions 每 10 分钟检查一次，按各站点自己的时间表访问。
5. 想立刻验证：点**立即运行一轮**——会强制访问当前所有启用的站点（忽略调度与次数限制），
   日志输出 `[force] ...`，约 1~2 分钟后刷新页面即可看到最新延迟。

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

- **探测节点在海外**：GitHub Actions 运行在 GitHub 海外服务器，测出的延迟是海外节点到目标站的延迟，
  并非你所在地区用户的访问速度。若要测量国内真实延迟，请改用国内云服务器 / 云函数方案。
- **调度粒度**：GitHub Actions 的 cron 最小为分钟级，本方案每 10 分钟检查一次各站点是否到期，
  固定间隔的实际执行时间误差约 10 分钟以内。
- **登录密码为前端校验**：登录仅防止随意浏览，懂技术的人仍可通过查看仓库源码或直接访问数据文件读取内容。
  如需严格鉴权，需要后端服务。
- **Token 固化在源码（重要）**：`GH_TOKEN` 写进了 `index.html`，若仓库是 **Public**，Token 会对所有人可见，
  请使用**仅授权本仓库 + 低权限 + 短有效期**的 Token，泄露后及时到 GitHub 撤销重建。
  若担心暴露，可把仓库设为 **Private**，或把 `GH_REPO` / `GH_TOKEN` 从源码中移除、改用页面填写方式。
- **`history.json` / `last_run.json` 由 Actions 自动管理**，每次更新会产生一次 commit，属正常现象。

## 常见问题

- **Actions 页面没有 Site Latency Monitor**：说明 `.github/workflows/monitor.yml` 没有上传成功，
  请用网页 Add file → Create new file，文件名填 `.github/workflows/monitor.yml`，把 README 同目录的
  `monitor.yml` 内容粘贴进去提交。
- **页面空白 / 登录后提示无法读取 sites.json**：确认已部署到 Pages 且 `index.html`、`sites.json`、`history.json` 都在仓库根目录。
- **Actions 不更新数据**：检查 `Workflow permissions` 是否已设为 Read and write；检查 Actions 运行日志。
- **保存到仓库失败 / 页面提示未配置 Token**：打开 `index.html` 顶部，把 `GH_TOKEN` 常量填为你的 Token（需 Contents 读写权限），保存后重新上传；或检查 Token 是否过期。
- **域名访问 404**：检查 DNS 是否生效、`CNAME` 文件内容是否为你的域名、Pages 的 Custom domain 是否填写并保存。
