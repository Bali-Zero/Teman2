#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

function loadChromium() {
  const candidates = [
    "playwright",
    path.join(process.cwd(), "apps/mouth/node_modules/playwright"),
    path.join(
      os.homedir(),
      "nuzantara/apps/mouth/node_modules/playwright",
    ),
  ];
  let lastError = null;
  for (const candidate of candidates) {
    try {
      return require(candidate).chromium;
    } catch (error) {
      lastError = error;
    }
  }
  if (lastError) {
    throw lastError;
  }
  throw new Error("Playwright chromium could not be loaded");
}

const chromium = loadChromium();

const DEFAULT_BASE_URL = "https://kita.balizero.com";
const DEFAULT_SECRET_FILE =
  "~/.local/share/nuzantara/secrets/prod-smoke-login.env";
const DEFAULT_STORAGE_STATE =
  "~/.local/state/nuzantara/prod-smoke-storage-state.json";
const DEFAULT_CLIENT_ID = "11671";
const DEFAULT_SERVICE_CODE = "visa_bridging";
const STATUS_FLOW = [
  "waiting_documents",
  "sending_invoice",
  "on_process",
  "completed",
];
const PERMISSION_RE =
  /permission denied|insufficient privilege|not authorized|forbidden|denied for table|permission error/i;
const IGNORED_REQUEST_RE =
  /google-analytics|googletagmanager|vercel-insights|sentry|clarity/i;

function expandHome(value) {
  if (!value) return value;
  if (value === "~") return os.homedir();
  if (value.startsWith("~/")) return path.join(os.homedir(), value.slice(2));
  return value;
}

function parseArgs(argv) {
  const args = {
    baseUrl: process.env.NUZANTARA_SMOKE_BASE_URL || DEFAULT_BASE_URL,
    secretFile: process.env.NUZANTARA_SMOKE_SECRET_FILE || DEFAULT_SECRET_FILE,
    storageState:
      process.env.NUZANTARA_SMOKE_STORAGE_STATE || DEFAULT_STORAGE_STATE,
    clientId: process.env.NUZANTARA_SMOKE_CLIENT_ID || DEFAULT_CLIENT_ID,
    serviceCode:
      process.env.NUZANTARA_SMOKE_SERVICE_CODE || DEFAULT_SERVICE_CODE,
    assignedTo: process.env.NUZANTARA_SMOKE_ASSIGNED_TO || "",
    reportJson: process.env.NUZANTARA_SMOKE_REPORT_JSON || "",
    retries: Number(process.env.NUZANTARA_SMOKE_RETRIES || 6),
    retryDelayMs: Number(process.env.NUZANTARA_SMOKE_RETRY_DELAY_MS || 1000),
    headless: process.env.NUZANTARA_SMOKE_HEADLESS !== "false",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--base-url":
        args.baseUrl = argv[++i];
        break;
      case "--secret-file":
        args.secretFile = argv[++i];
        break;
      case "--storage-state":
        args.storageState = argv[++i];
        break;
      case "--client-id":
        args.clientId = argv[++i];
        break;
      case "--service-code":
        args.serviceCode = argv[++i];
        break;
      case "--assigned-to":
        args.assignedTo = argv[++i];
        break;
      case "--report-json":
        args.reportJson = argv[++i];
        break;
      case "--retries":
        args.retries = Number(argv[++i]);
        break;
      case "--retry-delay-ms":
        args.retryDelayMs = Number(argv[++i]);
        break;
      case "--headed":
        args.headless = false;
        break;
      case "-h":
      case "--help":
        printUsage();
        process.exit(0);
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  args.baseUrl = args.baseUrl.replace(/\/$/, "");
  args.secretFile = expandHome(args.secretFile);
  args.storageState = expandHome(args.storageState);
  args.account =
    process.env.NUZANTARA_SMOKE_LOGIN_ACCOUNT ||
    process.env.NUZANTARA_SMOKE_EMAIL ||
    "";
  args.password =
    process.env.NUZANTARA_SMOKE_LOGIN_PASSWORD ||
    process.env.NUZANTARA_SMOKE_PASSWORD ||
    "";
  args.assignedTo = args.assignedTo || args.account;

  if (!Number.isFinite(args.retries) || args.retries < 1) {
    throw new Error("--retries must be a positive number");
  }
  if (!Number.isFinite(args.retryDelayMs) || args.retryDelayMs < 0) {
    throw new Error("--retry-delay-ms must be a non-negative number");
  }

  return args;
}

function printUsage() {
  process.stdout.write(`Usage:
  node scripts/prod_crm_smoke.cjs --base-url https://kita.balizero.com --client-id 11671 --service-code visa_bridging --report-json /tmp/prod-crm-smoke.json

Credentials:
  source ~/.local/share/nuzantara/secrets/prod-smoke-login.env
  The script never prints password or tokens.
`);
}

function loadSecretFile(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return;
  const content = fs.readFileSync(filePath, "utf8");
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const key = match[1];
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) {
      process.env[key] = value;
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function safeText(value) {
  if (value == null) return "";
  return String(value).replace(
    /(nz_access_token|nz_csrf_token|auth_token|password|pin)=([^;\s]+)/gi,
    "$1=[redacted]",
  );
}

function extractPracticeId(body) {
  const candidates = [
    body && body.id,
    body && body.practice && body.practice.id,
    body && body.data && body.data.id,
    body && body.data && body.data.practice && body.data.practice.id,
  ];
  for (const candidate of candidates) {
    if (
      candidate !== undefined &&
      candidate !== null &&
      String(candidate).length > 0
    ) {
      return String(candidate);
    }
  }
  throw new Error(
    `Create practice response did not include an id: ${safeText(JSON.stringify(body))}`,
  );
}

function extractStatus(body) {
  const candidates = [
    body && body.status,
    body && body.practice && body.practice.status,
    body && body.data && body.data.status,
    body && body.data && body.data.practice && body.data.practice.status,
  ];
  return candidates.find((candidate) => typeof candidate === "string") || null;
}

async function ensureLoggedIn(page, args, report) {
  await page.goto(`${args.baseUrl}/login?redirect=/process`, {
    waitUntil: "domcontentloaded",
  });

  if (args.account && args.password) {
    const loginResponse = await authedFetch(
      page,
      `${args.baseUrl}/api/auth/login`,
      {
        method: "POST",
        body: JSON.stringify({ email: args.account, pin: args.password }),
      },
    );
    assertOkResponse("api login", loginResponse);
    const token = loginResponse.body?.data?.token;
    if (!token) {
      throw new Error("api login response did not include data.token");
    }
    const csrfToken = loginResponse.body?.data?.csrfToken || "";
    const user = loginResponse.body?.data?.user || null;
    await page.evaluate(
      ({ token: authToken, csrfToken: csrf, user: userProfile }) => {
        window.localStorage.setItem("auth_token", authToken);
        if (csrf) {
          window.localStorage.setItem("csrf_token", csrf);
        }
        if (userProfile) {
          window.localStorage.setItem(
            "user_profile",
            JSON.stringify(userProfile),
          );
        }
      },
      { token, csrfToken, user },
    );
    report.auth = { reused_session: false, api_login: true };
    return;
  }

  const existingToken = await page.evaluate(() =>
    window.localStorage.getItem("auth_token"),
  );
  if (existingToken) {
    report.auth = { reused_session: true, api_login: false };
    return;
  }

  if (!args.account || !args.password) {
    throw new Error(
      `Missing smoke credentials. Source ${args.secretFile} or set NUZANTARA_SMOKE_LOGIN_ACCOUNT and NUZANTARA_SMOKE_LOGIN_PASSWORD.`,
    );
  }
}

async function authedFetch(page, url, options = {}) {
  return page.evaluate(
    async ({ url: requestUrl, options: requestOptions }) => {
      const headers = { ...(requestOptions.headers || {}) };
      const token = window.localStorage.getItem("auth_token");
      if (token && !headers.Authorization) {
        headers.Authorization = `Bearer ${token}`;
      }
      const csrfMatch = document.cookie.match(
        /(?:^|;\s*)nz_csrf_token=([^;]+)/,
      );
      if (csrfMatch && !headers["X-CSRF-Token"]) {
        headers["X-CSRF-Token"] = decodeURIComponent(csrfMatch[1]);
      }
      if (requestOptions.body && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
      const response = await fetch(requestUrl, {
        ...requestOptions,
        headers,
        credentials: "include",
        cache: "no-store",
      });
      const text = await response.text();
      let body = null;
      try {
        body = text ? JSON.parse(text) : null;
      } catch (_error) {
        body = { raw: text };
      }
      return {
        ok: response.ok,
        status: response.status,
        url: response.url,
        text,
        body,
      };
    },
    { url, options },
  );
}

function assertOkResponse(label, response) {
  const text = safeText(response.text || "");
  if (!response.ok || PERMISSION_RE.test(text)) {
    throw new Error(
      `${label} failed status=${response.status} body=${text.slice(0, 800)}`,
    );
  }
}

async function checkAdminAndTeam(page, args, report) {
  const startDate = "2026-01-05";
  const endpoints = [
    `/api/admin/team-activity/overview?start_date=${startDate}`,
    `/api/admin/team-activity/team-stats?start_date=${startDate}`,
    `/api/team/my-status?user_id=${encodeURIComponent(args.account)}`,
  ];

  report.admin_team = [];
  for (const endpoint of endpoints) {
    const response = await authedFetch(page, `${args.baseUrl}${endpoint}`, {
      method: "GET",
    });
    assertOkResponse(endpoint, response);
    report.admin_team.push({ endpoint, status: response.status });
  }
}

async function createPractice(page, args, report) {
  const timestamp = new Date().toISOString();
  const payload = {
    client_id: Number(args.clientId),
    practice_type_code: args.serviceCode,
    status: "inquiry",
    priority: "normal",
    assigned_to: args.assignedTo || args.account,
    notes: `SMOKE TEST repeatable CRM flow ${timestamp}`,
    internal_notes:
      "Created by scripts/prod_crm_smoke.cjs; cleanup is mandatory.",
  };
  const response = await authedFetch(
    page,
    `${args.baseUrl}/api/crm/practices/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  assertOkResponse("create practice", response);
  const practiceId = extractPracticeId(response.body);
  report.practice = {
    id: practiceId,
    client_id: payload.client_id,
    service_code: payload.practice_type_code,
    created_status: extractStatus(response.body),
    transitions: [],
    cleanup: null,
  };
  return practiceId;
}

async function readPracticeStatus(page, args, practiceId) {
  const response = await authedFetch(
    page,
    `${args.baseUrl}/api/crm/practices/${practiceId}?_=${Date.now()}`,
    { method: "GET" },
  );
  assertOkResponse(`read practice ${practiceId}`, response);
  return extractStatus(response.body);
}

async function patchPracticeStatus(page, args, practiceId, status) {
  const response = await authedFetch(
    page,
    `${args.baseUrl}/api/crm/practices/${practiceId}/`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
  assertOkResponse(`patch practice ${practiceId} to ${status}`, response);
  return extractStatus(response.body);
}

async function openPracticeDetail(page, args, practiceId) {
  await page.goto(`${args.baseUrl}/process/${practiceId}?_=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  const bodyText = await page
    .locator("body")
    .innerText({ timeout: 15000 })
    .catch(() => "");
  if (PERMISSION_RE.test(bodyText)) {
    throw new Error(
      `detail page for practice ${practiceId} rendered a permission error`,
    );
  }
}

async function runStatusFlow(page, args, practiceId, report) {
  for (const targetStatus of STATUS_FLOW) {
    const patchedStatus = await patchPracticeStatus(
      page,
      args,
      practiceId,
      targetStatus,
    );
    const immediateStatus = await readPracticeStatus(page, args, practiceId);
    let finalStatus = immediateStatus;
    let attempts = 1;

    while (finalStatus !== targetStatus && attempts < args.retries) {
      await sleep(args.retryDelayMs);
      attempts += 1;
      finalStatus = await readPracticeStatus(page, args, practiceId);
    }

    await openPracticeDetail(page, args, practiceId);

    report.practice.transitions.push({
      target_status: targetStatus,
      patch_response_status: patchedStatus,
      immediate_get_status: immediateStatus,
      final_get_status: finalStatus,
      attempts,
      stale_read_observed: immediateStatus !== targetStatus,
      converged: finalStatus === targetStatus,
    });

    if (finalStatus !== targetStatus) {
      throw new Error(
        `practice ${practiceId} did not converge to ${targetStatus}; last status=${finalStatus}`,
      );
    }
  }
}

async function cleanupPractice(page, args, practiceId, report) {
  const response = await authedFetch(
    page,
    `${args.baseUrl}/api/crm/practices/${practiceId}?deleted_by=${encodeURIComponent(args.account)}`,
    { method: "DELETE" },
  );
  assertOkResponse(`delete practice ${practiceId}`, response);

  let finalStatus = await readPracticeStatus(page, args, practiceId);
  let attempts = 1;
  while (finalStatus !== "cancelled" && attempts < args.retries) {
    await sleep(args.retryDelayMs);
    attempts += 1;
    finalStatus = await readPracticeStatus(page, args, practiceId);
  }
  await openPracticeDetail(page, args, practiceId);
  report.practice.cleanup = {
    delete_status: response.status,
    final_get_status: finalStatus,
    attempts,
    converged: finalStatus === "cancelled",
  };
  if (finalStatus !== "cancelled") {
    throw new Error(
      `cleanup did not converge to cancelled; last status=${finalStatus}`,
    );
  }
}

async function main() {
  loadSecretFile(
    expandHome(process.env.NUZANTARA_SMOKE_SECRET_FILE || DEFAULT_SECRET_FILE),
  );
  const args = parseArgs(process.argv.slice(2));
  loadSecretFile(args.secretFile);
  args.account =
    process.env.NUZANTARA_SMOKE_LOGIN_ACCOUNT ||
    process.env.NUZANTARA_SMOKE_EMAIL ||
    args.account;
  args.password =
    process.env.NUZANTARA_SMOKE_LOGIN_PASSWORD ||
    process.env.NUZANTARA_SMOKE_PASSWORD ||
    args.password;
  args.assignedTo = args.assignedTo || args.account;

  const report = {
    started_at: new Date().toISOString(),
    base_url: args.baseUrl,
    account: args.account || null,
    secret_file: args.secretFile,
    storage_state: args.storageState,
    auth: null,
    admin_team: [],
    practice: null,
    browser_console: [],
    request_failures: [],
    warnings: [],
    ok: false,
  };

  const storageExists = args.storageState && fs.existsSync(args.storageState);
  const browser = await chromium.launch({ headless: args.headless });
  const context = await browser.newContext(
    storageExists ? { storageState: args.storageState } : {},
  );
  const page = await context.newPage();
  let practiceId = null;

  page.on("console", (message) => {
    if (!["error", "warning"].includes(message.type())) return;
    const text = safeText(message.text());
    if (IGNORED_REQUEST_RE.test(text)) return;
    report.browser_console.push({ type: message.type(), text });
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (IGNORED_REQUEST_RE.test(url)) return;
    const failure = request.failure();
    if (failure && failure.errorText === "net::ERR_ABORTED") return;
    report.request_failures.push({
      url,
      method: request.method(),
      error: failure ? failure.errorText : "unknown",
    });
  });

  try {
    await ensureLoggedIn(page, args, report);
    if (args.storageState) {
      fs.mkdirSync(path.dirname(args.storageState), { recursive: true });
      await context.storageState({ path: args.storageState });
      fs.chmodSync(args.storageState, 0o600);
    }
    await checkAdminAndTeam(page, args, report);
    await page.goto(`${args.baseUrl}/process`, {
      waitUntil: "domcontentloaded",
    });
    practiceId = await createPractice(page, args, report);
    await runStatusFlow(page, args, practiceId, report);
    await cleanupPractice(page, args, practiceId, report);

    const staleTransitions = report.practice.transitions.filter(
      (transition) => transition.stale_read_observed,
    );
    if (staleTransitions.length > 0) {
      report.warnings.push({
        code: "stale_read_observed",
        count: staleTransitions.length,
        note: "Immediate GET differed from PATCH target but retry converged.",
      });
    }

    const permissionConsole = report.browser_console.filter((entry) =>
      PERMISSION_RE.test(entry.text),
    );
    if (permissionConsole.length > 0) {
      throw new Error(
        `permission-like browser console output detected (${permissionConsole.length})`,
      );
    }
    if (report.request_failures.length > 0) {
      throw new Error(
        `request failures detected (${report.request_failures.length})`,
      );
    }

    report.ok = true;
  } catch (error) {
    report.ok = false;
    report.error = safeText(
      error && error.stack ? error.stack : error.message || String(error),
    );
    if (practiceId && report.practice && !report.practice.cleanup) {
      try {
        await cleanupPractice(page, args, practiceId, report);
      } catch (cleanupError) {
        report.cleanup_error = safeText(
          cleanupError && cleanupError.stack
            ? cleanupError.stack
            : cleanupError.message || String(cleanupError),
        );
      }
    }
  } finally {
    report.finished_at = new Date().toISOString();
    await browser.close();
  }

  const output = `${JSON.stringify(report, null, 2)}\n`;
  if (args.reportJson) {
    fs.mkdirSync(path.dirname(args.reportJson), { recursive: true });
    fs.writeFileSync(args.reportJson, output, { mode: 0o600 });
  }
  process.stdout.write(output);

  if (!report.ok) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  process.stderr.write(
    `${safeText(error && error.stack ? error.stack : String(error))}\n`,
  );
  process.exit(1);
});
