// Vercel Serverless Function
// 网页 POST -> 触发 GitHub Actions 强制访问全部站点（"立即运行一轮"）
// Token 只存在于 Vercel 环境变量中，绝不进入前端代码或仓库源码。
const GH_REPO = "Cogen0/site-latency-monitor";
const UA = "latency-monitor";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "method not allowed" });
  }
  const token = process.env.GH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: "GH_TOKEN 未配置（请在 Vercel 环境变量中添加）" });
  }

  try {
    const r = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/workflows/monitor.yml/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "User-Agent": UA,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs: { force_all: true } }),
    });
    if (r.ok || r.status === 204) {
      return res.json({ ok: true });
    }
    return res.status(502).json({ ok: false, error: `触发失败 ${r.status}` });
  } catch (e) {
    return res.status(502).json({ ok: false, error: "GitHub 连接失败" });
  }
}
