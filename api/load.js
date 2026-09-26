// Vercel Serverless Function
// 网页 GET /api/load -> 从 GitHub 仓库实时读取 sites.json / history.json / last_run.json
// 解决"页面读 Vercel 部署快照导致数据滞后"的问题：页面永远显示仓库最新数据，
// 添加站点、Actions 写入延迟后，刷新页面立即可见，无需等待 Vercel 重新部署。
// Token 只存在于 Vercel 环境变量中，绝不进入前端代码或仓库源码。
const GH_REPO = "Cogen0/site-latency-monitor";
const BRANCH = "main";
const UA = "latency-monitor";

const EMPTY = {
  "sites.json": { sites: [] },
  "history.json": [],
  "last_run.json": { sites: {} },
};

function b64decode(s) {
  return Buffer.from(s, "base64").toString("utf8");
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ ok: false, error: "method not allowed" });
  }
  const token = process.env.GH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: "GH_TOKEN 未配置（请在 Vercel 环境变量中添加）" });
  }

  const result = {};
  for (const file of ["sites.json", "history.json", "last_run.json"]) {
    try {
      const r = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${file}?ref=${BRANCH}`, {
        headers: { Authorization: `Bearer ${token}`, "User-Agent": UA, Accept: "application/vnd.github+json" },
      });
      if (r.ok) {
        const j = await r.json();
        result[file] = JSON.parse(b64decode(j.content));
      } else if (r.status === 404) {
        result[file] = EMPTY[file];
      } else {
        result[file] = null;
      }
    } catch (e) {
      result[file] = null;
    }
  }

  res.setHeader("Cache-Control", "no-store");
  res.json(result);
}
