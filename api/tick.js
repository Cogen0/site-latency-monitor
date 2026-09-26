// Vercel Serverless Function
// 外部定时器（如 cron-job.org，免费）每 5 分钟调用本接口 -> 触发 GitHub Actions
// repository_dispatch（event_type=tick），monitor.py 将按各站点自己的调度判断是否访问。
// 这不受 GitHub 免费账号 schedule 节流限制，可真正实现"2 小时窗口内随机访问 10 次"。
//
// 访问：https://你的域名/api/tick?key=你的TICK_KEY
//   TICK_KEY 配置在 Vercel 环境变量中（与 GH_TOKEN 同一处添加），不进源码。
// 用法（cron-job.org 免费版）：
//   - URL: https://2dh.cc.cd/api/tick?key=你的TICK_KEY
//   - 频率：每 5 分钟（或按需）
const GH_REPO = "Cogen0/site-latency-monitor";
const UA = "latency-monitor";

export default async function handler(req, res) {
  // 1) 校验定时器密钥（防止他人随意触发你的 Actions）
  const expected = process.env.TICK_KEY;
  if (!expected) {
    return res.status(500).json({ ok: false, error: "TICK_KEY 未配置（请在 Vercel 环境变量中添加）" });
  }
  let got = null;
  if (req.method === "GET") {
    got = req.query && req.query.key;
  } else {
    try {
      let body = req.body;
      if (typeof body === "string") body = JSON.parse(body);
      got = (req.query && req.query.key) || (body && body.key);
    } catch (e) {
      got = (req.query && req.query.key) || null;
    }
  }
  if (got !== expected) {
    return res.status(403).json({ ok: false, error: "invalid tick key" });
  }

  // 2) 触发 GitHub Actions（repository_dispatch 需要 Actions: write 权限）
  const token = process.env.GH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: "GH_TOKEN 未配置（请在 Vercel 环境变量中添加）" });
  }
  try {
    const r = await fetch(`https://api.github.com/repos/${GH_REPO}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "User-Agent": UA,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ event_type: "tick" }),
    });
    if (r.status === 204 || r.ok) {
      return res.json({ ok: true, at: new Date().toISOString() });
    }
    return res.status(502).json({ ok: false, error: `触发 GitHub Actions 失败 ${r.status}` });
  } catch (e) {
    return res.status(502).json({ ok: false, error: "GitHub 连接失败" });
  }
}
