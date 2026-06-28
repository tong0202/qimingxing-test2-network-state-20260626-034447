const OWNER = "tong0202";
const REPO = "qimingxing-test2-network-state-20260626-034447";
const EVENT_TYPE = "qmx_e7_3_bridge_tick";

async function triggerGitHub(env, source, extraPayload = {}) {
  if (!env.GITHUB_TOKEN) {
    throw new Error("Missing Cloudflare secret: GITHUB_TOKEN");
  }

  const firedAt = new Date().toISOString();
  const response = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/dispatches`, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "qimingxing-e7-3-cloudflare-clock",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      event_type: EVENT_TYPE,
      client_payload: {
        clock: "cloudflare-worker-cron",
        stage: "E7.3b",
        intent: "wake_bridge_without_manual_operator",
        source,
        fired_at: firedAt,
        ...extraPayload,
      },
    }),
  });

  const text = await response.text();
  const result = {
    ok: response.status === 204,
    status: response.status,
    event_type: EVENT_TYPE,
    fired_at: firedAt,
    source,
    response_body: text.slice(0, 500),
  };

  if (!result.ok) {
    throw new Error(`GitHub repository_dispatch failed: ${JSON.stringify(result)}`);
  }

  return result;
}

export default {
  async scheduled(controller, env) {
    const result = await triggerGitHub(env, "cloudflare-cron", {
      cron: controller.cron,
      scheduled_time: controller.scheduledTime,
    });
    console.log(JSON.stringify(result));
  },

  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return Response.json({
        ok: true,
        worker: "qimingxing-e7-3-clock",
        event_type: EVENT_TYPE,
        target: `${OWNER}/${REPO}`,
      });
    }

    if (url.pathname === "/test-dispatch" && request.method === "POST") {
      const expected = env.QMX_WORKER_TEST_TOKEN;
      const observed = request.headers.get("X-QMX-Test-Token");
      if (!expected || observed !== expected) {
        return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
      }
      const result = await triggerGitHub(env, "cloudflare-http-test");
      return Response.json(result);
    }

    return Response.json({
      ok: true,
      message: "Qimingxing E7.3 Cloudflare clock worker is deployed. Cron calls GitHub repository_dispatch.",
    });
  },
};
