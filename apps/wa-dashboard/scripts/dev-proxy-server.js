// Custom Next.js dev server that proxies /api/* to the production backend,
// injecting WA_DASHBOARD_AUTH_COOKIE so the EventSource SSE stream (which
// cannot set custom headers in the browser) authenticates via cookie JWT.
//
// Run via: WA_DASHBOARD_BACKEND_URL=https://nuzantara-rag.fly.dev \
//          WA_DASHBOARD_AUTH_COOKIE='nz_access_token=eyJ...' \
//          node server.js
//
// Dev-only. Production should use real cookie SSO via subdomain.

const { createServer } = require("http");
const { parse } = require("url");
const next = require("next");
const httpProxy = require("http-proxy");

const dev = process.env.NODE_ENV !== "production";
const port = parseInt(process.env.PORT || "3030", 10);
const backend = process.env.WA_DASHBOARD_BACKEND_URL || "http://localhost:8080";
const authCookie = process.env.WA_DASHBOARD_AUTH_COOKIE || "";
const debugKey = process.env.WA_DASHBOARD_DEBUG_KEY || "";

const app = next({ dev });
const handle = app.getRequestHandler();

const proxy = httpProxy.createProxyServer({
  changeOrigin: true,
  ws: false,
  selfHandleResponse: false,
  // SSE needs long-lived connections — never timeout
  proxyTimeout: 0,
  timeout: 0,
});

proxy.on("proxyReq", (proxyReq) => {
  if (authCookie) {
    const existing = proxyReq.getHeader("cookie") || "";
    proxyReq.setHeader(
      "cookie",
      existing ? `${existing}; ${authCookie}` : authCookie,
    );
  }
  if (debugKey) {
    proxyReq.setHeader("X-Debug-Key", debugKey);
  }
});

proxy.on("error", (err, req, res) => {
  console.error(`[proxy] ${req.method} ${req.url} →`, err.message);
  if (res && !res.headersSent) {
    res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "proxy_error", detail: err.message }));
  }
});

app.prepare().then(() => {
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url, true);
    if (parsedUrl.pathname && parsedUrl.pathname.startsWith("/api/")) {
      return proxy.web(req, res, { target: backend });
    }
    return handle(req, res, parsedUrl);
  });

  server.keepAliveTimeout = 0;
  server.headersTimeout = 0;

  server.listen(port, () => {
    console.log(`▲ wa-dashboard dev → http://localhost:${port}`);
    console.log(`  Backend: ${backend}`);
    console.log(
      `  Auth: ${authCookie ? "cookie inject ON" : "NO cookie"} | ${debugKey ? "debug-key ON" : "NO debug-key"}`,
    );
  });
});
