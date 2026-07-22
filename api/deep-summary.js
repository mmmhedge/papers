const OWNER = "mmmhedge";
const REPO = "papers";
const WORKFLOW_ID = "deep_summary.yml";
const ALLOWED_ORIGINS = new Set([
  "https://mmmhedge.github.io",
  "https://mmmhedge.github.io/papers",
]);

function json(res, status, body, origin = "") {
  const headers = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
  if (origin) headers["Access-Control-Allow-Origin"] = origin;
  res.writeHead(status, headers);
  res.end(JSON.stringify(body));
}

function getAllowedOrigin(req) {
  const origin = req.headers.origin || "";
  if (!origin) return "";
  if (ALLOWED_ORIGINS.has(origin)) return origin;
  if (/^https:\/\/papers(?:-[a-z0-9-]+)*\.vercel\.app$/.test(origin)) return origin;
  return "";
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

module.exports = async function handler(req, res) {
  const origin = getAllowedOrigin(req);

  if (req.method === "OPTIONS") {
    return json(res, 204, {}, origin);
  }
  if (req.method !== "POST") {
    return json(res, 405, { error: "Method not allowed" }, origin);
  }
  if (req.headers.origin && !origin) {
    return json(res, 403, { error: "Origin not allowed" });
  }

  const token = process.env.GITHUB_WORKFLOW_TOKEN || process.env.GITHUB_TOKEN;
  if (!token) {
    return json(res, 500, { error: "Missing GITHUB_WORKFLOW_TOKEN" }, origin);
  }

  let body;
  try {
    body = await readBody(req);
  } catch {
    return json(res, 400, { error: "Invalid JSON body" }, origin);
  }

  const source = String(body.source || "").trim();
  const title = String(body.title || "").trim();
  if (!source || !/^https?:\/\/|^\d{4}\.\d{4,5}/.test(source)) {
    return json(res, 400, { error: "A valid arXiv/PDF source is required" }, origin);
  }

  const response = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "papers-deep-summary-vercel",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: {
          source,
          title,
          math_depth: String(body.math_depth || "heavy"),
          include_tables: String(body.include_tables !== false),
        },
      }),
    },
  );

  if (!response.ok) {
    const message = await response.text();
    return json(res, response.status, { error: message || "GitHub workflow dispatch failed" }, origin);
  }

  return json(res, 202, { ok: true, message: "Deep summary started" }, origin);
};
