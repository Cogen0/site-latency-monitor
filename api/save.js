// Vercel Serverless Function
// 网页 POST {sites:[...], purgeUrls:[...]} -> 用环境变量 GH_TOKEN 写回 GitHub 仓库
//   - sites: 完整站点配置（写入 sites.json）
//   - purgeUrls: 已删除站点的 URL 列表（同时清除 history.json 中对应站点的全部记录）
// Token 只存在于 Vercel 环境变量中，绝不进入前端代码或仓库源码。
const GH_REPO = "Cogen0/site-latency-monitor";
const BRANCH = "main";
const UA = "latency-monitor";

const gh = (path, init) =>
  fetch(`https://api.github.com/repos/${GH_REPO}/contents/${path}`, {
    headers: {
      Authorization: `Bearer ${process.env.GH_TOKEN}`,
      "User-Agent": UA,
      Accept: "application/vnd.github+json",
      ...(init && init.headers),
    },
    ...init,
  });

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "method not allowed" });
  }
  const token = process.env.GH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: "GH_TOKEN 未配置（请在 Vercel 环境变量中添加）" });
  }

  let sites, purgeUrls;
  try {
    let body = req.body;
    if (typeof body === "string") body = JSON.parse(body);
    sites = body && body.sites;
    purgeUrls = body && body.purgeUrls;
  } catch (e) {
    return res.status(400).json({ ok: false, error: "请求体不是合法 JSON" });
  }
  if (!Array.isArray(sites)) {
    return res.status(400).json({ ok: false, error: "sites 必须是数组" });
  }
  if (purgeUrls !== undefined && !Array.isArray(purgeUrls)) {
    return res.status(400).json({ ok: false, error: "purgeUrls 必须是数组" });
  }

  // 1) 写入 sites.json
  try {
    let sha = null;
    try {
      const g = await gh("sites.json");
      if (g.ok) {
        sha = (await g.json()).sha;
      } else if (g.status !== 404) {
        return res.status(502).json({ ok: false, error: `读取仓库文件失败 ${g.status}` });
      }
    } catch (e) {
      return res.status(502).json({ ok: false, error: "GitHub 连接失败" });
    }
    const content = Buffer.from(JSON.stringify({ sites }, null, 2), "utf8").toString("base64");
    const p = await gh("sites.json", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        // 注意：不要带 [skip ci]，否则 Vercel 不会因本次提交而重新部署
        message: "update sites from panel",
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

  // 2) 若本次删除了站点，同步清除 history.json 中对应站点的全部记录
  if (Array.isArray(purgeUrls) && purgeUrls.length > 0) {
    try {
      const purgeSet = new Set(purgeUrls.filter(u => typeof u === "string" && u));
      if (purgeSet.size > 0) {
        let hsha = null, hjson = null;
        const hg = await gh("history.json");
        if (hg.ok) {
          const d = await hg.json();
          hsha = d.sha;
          try {
            hjson = JSON.parse(Buffer.from(d.content, "base64").toString("utf8"));
          } catch (e) {
            hjson = null;
          }
        } else if (hg.status !== 404) {
          return res.status(502).json({ ok: false, error: `读取 history.json 失败 ${hg.status}` });
        }
        if (Array.isArray(hjson)) {
          const filtered = hjson.filter(r => !(r && r.url && purgeSet.has(r.url)));
          if (filtered.length !== hjson.length) {
            const hcontent = Buffer.from(JSON.stringify(filtered, null, 2), "utf8").toString("base64");
            const hp = await gh("history.json", {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                message: "purge history of removed sites",
                content: hcontent,
                sha: hsha || undefined,
                branch: BRANCH,
              }),
            });
            if (!hp.ok) {
              return res.status(502).json({ ok: false, error: `清除历史失败 ${hp.status}` });
            }
          }
        }
      }
    } catch (e) {
      return res.status(502).json({ ok: false, error: "GitHub 连接失败（清理历史）" });
    }
  }

  res.json({ ok: true });
}
