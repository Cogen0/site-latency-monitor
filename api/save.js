// Vercel Serverless Function
// 网页 POST {sites:[...]} -> 用环境变量 GH_TOKEN 写回 GitHub 仓库 sites.json
// Token 只存在于 Vercel 环境变量中，绝不进入前端代码或仓库源码。
const GH_REPO = "Cogen0/site-latency-monitor";
const BRANCH = "main";
const FILE = "sites.json";
const UA = "latency-monitor";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "method not allowed" });
  }
  const token = process.env.GH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: "GH_TOKEN 未配置（请在 Vercel 环境变量中添加）" });
  }

  let sites;
  try {
    let body = req.body;
    if (typeof body === "string") body = JSON.parse(body);
    sites = body && body.sites;
  } catch (e) {
    return res.status(400).json({ ok: false, error: "请求体不是合法 JSON" });
  }
  if (!Array.isArray(sites)) {
    return res.status(400).json({ ok: false, error: "sites 必须是数组" });
  }

  const content = Buffer.from(JSON.stringify({ sites }, null, 2), "utf8").toString("base64");

  // 1) 读取现有文件 sha（用于安全更新，避免覆盖别人的提交）
  let sha = null;
  try {
    const g = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${FILE}`, {
      headers: { Authorization: `Bearer ${token}`, "User-Agent": UA, Accept: "application/vnd.github+json" },
    });
    if (g.ok) {
      sha = (await g.json()).sha;
    } else if (g.status !== 404) {
      return res.status(502).json({ ok: false, error: `读取仓库文件失败 ${g.status}` });
    }
  } catch (e) {
    return res.status(502).json({ ok: false, error: "GitHub 连接失败" });
  }

  // 2) 写入 sites.json
  try {
    const p = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${FILE}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "User-Agent": UA,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: "update sites from panel [skip ci]",
        content,
        sha: sha || undefined,
        branch: BRANCH,
      }),
    });
    if (!p.ok) {
      return res.status(502).json({ ok: false, error: `写入仓库失败 ${p.status}` });
    }
  } catch (e) {
    return res.status(502).json({ ok: false, error: "GitHub 连接失败" });
  }

  res.json({ ok: true });
}
