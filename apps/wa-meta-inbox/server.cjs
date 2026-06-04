#!/usr/bin/env node
"use strict";

// ===========================================================================
// WA Meta Inbox — local thin proxy (Section 5 of 2026-06-03-wa-meta-inbox-design)
// ---------------------------------------------------------------------------
// Desktop-local UI for the BALI ZERO WhatsApp Business (Meta API) number.
// This server is a THIN PROXY: it does NOT touch any database. It forwards
// authenticated requests to the FastAPI backend on Fly, attaching the
// X-API-Key (read from macOS Keychain) so the secret NEVER reaches the browser.
//
// Security posture (per spec sez. 5):
//   - Bind 127.0.0.1 ONLY (never 0.0.0.0). The Fly API key lives in memory.
//   - Fail LOUD on missing config (no half-broken UI).
//   - Ephemeral in-memory CSRF token (crypto.randomUUID at startup), injected
//     into viewer.html, validated on EVERY mutating route (fail-closed → 403).
//   - GET routes do not require CSRF (read-only).
//
// Known limit (documented, not masked): the CSRF token defends against
// browser-CSRF from other localhost pages. It does NOT defend against a
// malicious LOCAL process that curls + scrapes the page to lift the token.
// For a single operator on their own Mac this is an accepted risk.
//
// Dependencies: Node builtins only (http, crypto, child_process) + native
// fetch (Node 18+). No npm packages.
// ===========================================================================

const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

// --- Config -----------------------------------------------------------------
const HOST = "127.0.0.1"; // HARD: loopback only. Never configurable to 0.0.0.0.
const PORT = parseInt(process.env.WA_INBOX_PORT || "7791", 10);
const BACKEND_URL = (
  process.env.WA_INBOX_BACKEND_URL || "https://nuzantara-rag.fly.dev"
).replace(/\/+$/, "");
const KEYCHAIN_SERVICE = process.env.WA_INBOX_KEYCHAIN_SERVICE || "wa-inbox-api-key";
const VIEWER_HTML = path.join(__dirname, "viewer.html");

const LOG_PREFIX = "[wa-meta-inbox]";
const CSRF_PLACEHOLDER = "__WA_INBOX_CSRF_TOKEN__";

// fetch must exist (Node >= 18). Fail loud otherwise.
if (typeof fetch !== "function") {
  console.error(`${LOG_PREFIX} FATAL: global fetch unavailable — Node >= 18 required (have ${process.version})`);
  process.exit(1);
}

// --- API key resolution (Keychain → env fallback → fail loud) ---------------
function resolveApiKey() {
  // 1) macOS Keychain (preferred): security find-generic-password -s <service> -w
  try {
    const out = execFileSync(
      "/usr/bin/security",
      ["find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
    );
    const key = out.trim();
    if (key) {
      console.log(`${LOG_PREFIX} API key loaded from Keychain service '${KEYCHAIN_SERVICE}'`);
      return key;
    }
    console.error(`${LOG_PREFIX} Keychain item '${KEYCHAIN_SERVICE}' returned empty value`);
  } catch (err) {
    // Item missing, Keychain locked, or `security` unavailable → describe precisely.
    const msg = (err && err.stderr ? String(err.stderr) : err && err.message) || "unknown error";
    console.error(`${LOG_PREFIX} Keychain lookup for '${KEYCHAIN_SERVICE}' failed: ${msg.trim()}`);
  }

  // 2) Env fallback (e.g. dev / CI smoke). Explicitly allowed by spec.
  if (process.env.WA_INBOX_API_KEY && process.env.WA_INBOX_API_KEY.trim()) {
    console.log(`${LOG_PREFIX} API key loaded from env WA_INBOX_API_KEY (Keychain fallback)`);
    return process.env.WA_INBOX_API_KEY.trim();
  }

  // 3) Neither available → fail loud, do NOT serve a half-broken UI.
  console.error(
    `${LOG_PREFIX} FATAL: no API key. Add it to Keychain:\n` +
      `  security add-generic-password -s ${KEYCHAIN_SERVICE} -a "$USER" -w <key>\n` +
      `  (or export WA_INBOX_API_KEY for dev/smoke).`,
  );
  process.exit(1);
}

const API_KEY = resolveApiKey();

// --- Ephemeral CSRF token (in-memory, reset on restart, never on disk) ------
const CSRF_TOKEN = crypto.randomUUID();

// --- viewer.html (read once at startup; fail loud if absent) ----------------
let VIEWER_TEMPLATE;
try {
  VIEWER_TEMPLATE = fs.readFileSync(VIEWER_HTML, "utf8");
  if (!VIEWER_TEMPLATE.includes(CSRF_PLACEHOLDER)) {
    console.error(
      `${LOG_PREFIX} FATAL: viewer.html does not contain CSRF placeholder '${CSRF_PLACEHOLDER}'`,
    );
    process.exit(1);
  }
} catch (err) {
  console.error(`${LOG_PREFIX} FATAL: cannot read ${VIEWER_HTML}: ${err.message}`);
  process.exit(1);
}

// --- Helpers ----------------------------------------------------------------
function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function readBody(req, maxBytes = 256 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > maxBytes) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function checkCsrf(req, res) {
  const got = req.headers["x-local-csrf"];
  if (got !== CSRF_TOKEN) {
    sendJson(res, 403, { error: "csrf_token_missing_or_invalid" });
    return false;
  }
  return true;
}

// Proxy to the Fly backend, attaching X-API-Key. The key NEVER leaves this
// process: it is added here, not echoed back to the browser.
async function proxyToBackend(res, { method, backendPath, query, body }) {
  let url = `${BACKEND_URL}${backendPath}`;
  if (query) url += `?${query}`;
  const headers = { "X-API-Key": API_KEY, Accept: "application/json" };
  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = body;
  }
  let upstream;
  try {
    upstream = await fetch(url, init);
  } catch (err) {
    console.error(`${LOG_PREFIX} upstream ${method} ${backendPath} network error: ${err.message}`);
    sendJson(res, 502, { error: "backend_unreachable", detail: err.message });
    return;
  }
  const text = await upstream.text();
  // Pass through status + body; force JSON content-type for the browser.
  res.writeHead(upstream.status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(text);
}

// Validate a numeric thread id from the path (defense against path traversal /
// injection into the backend URL).
function parseThreadId(raw) {
  if (!/^\d+$/.test(raw)) return null;
  return raw;
}

// --- Startup auth-probe (log 200/401, do not block boot) --------------------
async function authProbe() {
  try {
    const r = await fetch(`${BACKEND_URL}/api/wa-inbox/threads?limit=1`, {
      method: "GET",
      headers: { "X-API-Key": API_KEY, Accept: "application/json" },
    });
    if (r.status === 200) {
      console.log(`${LOG_PREFIX} auth-probe OK (200) against ${BACKEND_URL}/api/wa-inbox/threads`);
    } else if (r.status === 401 || r.status === 403) {
      console.error(
        `${LOG_PREFIX} auth-probe REJECTED (${r.status}) — API key invalid or not scoped for /api/wa-inbox. ` +
          `UI will load but mutations/reads will fail until the key is fixed.`,
      );
    } else {
      console.warn(`${LOG_PREFIX} auth-probe returned ${r.status} (endpoint may not be deployed yet)`);
    }
  } catch (err) {
    console.warn(`${LOG_PREFIX} auth-probe could not reach backend: ${err.message} (continuing; backend may be cold)`);
  }
}

// --- Router -----------------------------------------------------------------
const server = http.createServer(async (req, res) => {
  try {
    const parsed = new URL(req.url, `http://${HOST}:${PORT}`);
    const pathname = parsed.pathname;
    const method = req.method || "GET";

    // GET / → serve viewer.html with CSRF token injected.
    if (method === "GET" && pathname === "/") {
      const html = VIEWER_TEMPLATE.split(CSRF_PLACEHOLDER).join(CSRF_TOKEN);
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
      res.end(html);
      return;
    }

    // Local health (no proxy) — handy for lsof/launchctl verification.
    if (method === "GET" && pathname === "/health.json") {
      sendJson(res, 200, { ok: true, backend: BACKEND_URL, port: PORT, csrf_present: true });
      return;
    }

    // GET /api/threads → proxy GET /api/wa-inbox/threads (forward query string)
    if (method === "GET" && pathname === "/api/threads") {
      await proxyToBackend(res, {
        method: "GET",
        backendPath: "/api/wa-inbox/threads",
        query: parsed.searchParams.toString() || undefined,
      });
      return;
    }

    // GET /api/threads/:id → proxy GET /api/wa-inbox/threads/:id/messages
    let m = pathname.match(/^\/api\/threads\/([^/]+)$/);
    if (method === "GET" && m) {
      const id = parseThreadId(m[1]);
      if (!id) return sendJson(res, 400, { error: "invalid_thread_id" });
      await proxyToBackend(res, {
        method: "GET",
        backendPath: `/api/wa-inbox/threads/${id}/messages`,
        query: parsed.searchParams.toString() || undefined,
      });
      return;
    }

    // POST /api/send → proxy POST /api/wa-inbox/threads/:id/send (CSRF required)
    // Body from browser: {thread_id, text, idempotency_key}
    if (method === "POST" && pathname === "/api/send") {
      if (!checkCsrf(req, res)) return;
      let payload;
      try {
        payload = JSON.parse(await readBody(req));
      } catch {
        return sendJson(res, 400, { error: "invalid_json" });
      }
      const id = parseThreadId(String(payload.thread_id ?? ""));
      if (!id) return sendJson(res, 400, { error: "invalid_thread_id" });
      const forward = { text: payload.text, idempotency_key: payload.idempotency_key };
      await proxyToBackend(res, {
        method: "POST",
        backendPath: `/api/wa-inbox/threads/${id}/send`,
        body: JSON.stringify(forward),
      });
      return;
    }

    // POST /api/takeover → proxy POST /api/wa-inbox/threads/:id/takeover (CSRF)
    if (method === "POST" && pathname === "/api/takeover") {
      if (!checkCsrf(req, res)) return;
      let payload;
      try {
        payload = JSON.parse(await readBody(req));
      } catch {
        return sendJson(res, 400, { error: "invalid_json" });
      }
      const id = parseThreadId(String(payload.thread_id ?? ""));
      if (!id) return sendJson(res, 400, { error: "invalid_thread_id" });
      await proxyToBackend(res, {
        method: "POST",
        backendPath: `/api/wa-inbox/threads/${id}/takeover`,
        body: "{}",
      });
      return;
    }

    // POST /api/release → proxy POST /api/wa-inbox/threads/:id/release (CSRF)
    if (method === "POST" && pathname === "/api/release") {
      if (!checkCsrf(req, res)) return;
      let payload;
      try {
        payload = JSON.parse(await readBody(req));
      } catch {
        return sendJson(res, 400, { error: "invalid_json" });
      }
      const id = parseThreadId(String(payload.thread_id ?? ""));
      if (!id) return sendJson(res, 400, { error: "invalid_thread_id" });
      await proxyToBackend(res, {
        method: "POST",
        backendPath: `/api/wa-inbox/threads/${id}/release`,
        body: "{}",
      });
      return;
    }

    sendJson(res, 404, { error: "not_found" });
  } catch (err) {
    console.error(`${LOG_PREFIX} unhandled request error: ${err.message}`);
    if (!res.headersSent) sendJson(res, 500, { error: "internal_error" });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`${LOG_PREFIX} listening on http://${HOST}:${PORT} (loopback only)`);
  console.log(`${LOG_PREFIX} backend: ${BACKEND_URL}`);
  console.log(`${LOG_PREFIX} CSRF token generated (in-memory, ${CSRF_TOKEN.length} chars)`);
  authProbe();
});

server.on("error", (err) => {
  console.error(`${LOG_PREFIX} FATAL: server error: ${err.message}`);
  process.exit(1);
});
