#!/usr/bin/env node
// voa_journey_probe.mjs — anonymous VOA journey probe (GARUDA VOA public
// funnel). Drives the pre-payment leg of the eligibility journey against
// production and reports a TRI-STATE verdict via a heartbeat file. L07-PR2.
//
// Contract measured on balizero.com 2026-08-29 by the orchestrator (never
// re-derived here — see the L07-deploy spec + SQUAD-LEDGER.md GROUND section
// for the full evidence trail):
//
//   GET  /visa/voa                                        -> 200
//   POST /api/visa/voa/eligibility-checks                 -> 201 + Location +
//        Set-Cookie: garuda_result_session=... (HttpOnly)
//   GET  /api/visa/voa/eligibility-checks/{id}  (+jar)     -> 200 verdict JSON
//   GET  same, WITHOUT jar                                 -> 404 (trap, see below)
//   DELETE .../{id} via balizero.com (+jar)                -> 500 (Vercel proxy
//        mangles the bodyless 204 the backend actually returns — the row IS
//        deleted; see W122 note below)
//
// ---------------------------------------------------------------------------
// TRI-STATE VERDICT (why not a plain pass/fail — superscar #2 / scar W104)
// ---------------------------------------------------------------------------
// The frontend flag (apps/mouth/src/app/visa/voa/flag.ts) fails CLOSED on
// anything but the literal string "true": unset/false/typo all mean the
// funnel is deliberately dark, and Next then serves ITS OWN 404 template at
// HTTP 200, with the page's correct <title>. A probe that only checks status
// (200) or status+title would both falsely report "healthy" on a page that
// is actually the fallback template — the only reliable tell is the body
// literal `NEXT_HTTP_ERROR_FALLBACK`.
//
// A probe that reported that pre-launch "dark" state as `fail` would page on
// every single tick before go-live — and an alarm that always fires is an
// alarm nobody reads (scar W104: the log-anomaly detector's dedup silently
// failed and it fired 288 times a day; the fix there and the fix here are
// the same principle: an always-on alarm trains the reader to ignore it).
// So the probe distinguishes:
//
//   dark  — page body contains NEXT_HTTP_ERROR_FALLBACK => flag deliberately
//           off. NOT an incident.
//   pass  — page is public (no fallback marker, funnel content present) AND
//           the whole pre-payment API journey (create -> read -> cleanup)
//           worked.
//   fail  — page public but journey broken, OR the API journey is broken
//           EVEN WHILE the page is dark. Measured today: the frontend is
//           dark while the backend is fully armed (POST/GET/DELETE all work)
//           — darkness on ONE platform must never mask a real break on the
//           other, so `page dark + api broken` is still `fail`.
//
// ---------------------------------------------------------------------------
// THE COOKIE-JAR TRAP (verbatim, do not "fix" this into a bug)
// ---------------------------------------------------------------------------
// "The funnel's POST sets an HttpOnly cookie (`garuda_result_session`). A GET
//  without a cookie jar reads a perfectly healthy funnel as a 404. The
//  backend does this on purpose: `get_eligibility_result` takes
//  `garuda_result_session: Cookie() = None` and deliberately collapses
//  malformed-id, absent-cookie and real-but-unbound-id into one
//  non-enumerating answer. Do not 'fix' this into a bug — use a real cookie
//  jar."
//
// This module implements the jar manually: it captures Set-Cookie from the
// POST response via `response.headers.getSetCookie()` (NOT `.get("set-
// cookie")`, which folds multiple Set-Cookie headers into one comma-joined
// string per the Fetch spec and would silently corrupt a multi-cookie
// response), keeps only the `garuda_result_session` pair, and replays it as
// a `Cookie:` header on every subsequent request for that result. The cookie
// VALUE is never logged (Law 2 / secret hygiene) — only whether one was
// captured.
//
// ---------------------------------------------------------------------------
// CLEANUP-BY-CONSEQUENCE (W122: the red lies, the work was done)
// ---------------------------------------------------------------------------
// DELETE through balizero.com returns HTTP 500 {"error":"Proxy error",...}
// (Vercel's own proxy shape, not the backend's {"code",...} shape) — but the
// row is genuinely deleted; the same DELETE straight to nuzantara-rag.fly.dev
// returns 204. So this probe NEVER trusts the DELETE status code for
// cleanup verification. It always issues a follow-up GET (with the same
// cookie jar, so the trap above cannot mask the result): a 404 means the row
// is really gone (`verified_gone`), anything else — including a network
// failure on the verify call itself, since "cannot verify" must never read
// as "cannot be true positive" — is counted as `leaked` and forces the
// overall verdict to `fail`, loudly, rather than silently believing a status
// code that this exact endpoint is known to mangle in transit.
//
// ---------------------------------------------------------------------------
// CIVIL-CALENDAR DATES (avoiding the civil_clock.py class of bug)
// ---------------------------------------------------------------------------
// entry_date / passport_expiry_date are civil calendar days in Asia/Makassar
// (WITA, UTC+8), never a UTC instant — the contract's own comment documents
// `civil_clock.py::garuda_today` as the defect this exists to prevent: a
// client that derives "today" from a local Date in another timezone can
// shift the ACCEPT/DECLINE cutoff by a full day for the first eight hours of
// every Bali day. This probe derives "today" via Intl.DateTimeFormat with
// timeZone: "Asia/Makassar" and does all day/year arithmetic on the plain
// Y-M-D components (never on a timezone-bearing Date), so the WITA/UTC
// boundary can never leak in.
//
// ---------------------------------------------------------------------------
// HEARTBEAT CONTRACT (read by PR-3's dead-man — this is the interface)
// ---------------------------------------------------------------------------
// One JSON object per run, written ATOMICALLY (write to `<path>.tmp` then
// `rename` — a rename is atomic on the same filesystem, so a reader can
// never observe a half-written file, unlike a direct write that a crash
// mid-flush would leave truncated):
//
//   {
//     "schema": 1,
//     "probe": "voa_journey",
//     "ts": "<ISO 8601 UTC>",
//     "ts_epoch": <int seconds>,
//     "verdict": "pass" | "dark" | "fail",
//     "reason": "<short machine code>",
//     "latency_ms": { "page": n|null, "post": n|null, "get": n|null },
//     "legs": { "page": {...}, "api": {...} },
//     "cleanup": { "attempted": n, "verified_gone": n, "leaked": n },
//     "base_url": "<url probed>",
//     "probe_version": 1
//   }
//
// Written on EVERY path, including an unexpected crash (top-level try/catch
// in main()) — a MISSING heartbeat must mean "the probe did not run at all",
// never "the probe ran and failed" (superscar #2: silence and failure are
// different states a dead-man watcher must be able to tell apart).
//
// Exit code: 0 for `pass` AND `dark` (dark is a healthy, expected state,
// scar W104) — 1 for `fail`.

import { randomUUID } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FALLBACK_MARKER = "NEXT_HTTP_ERROR_FALLBACK";

// Literal from apps/mouth/src/app/visa/voa/page.tsx CASE_TYPES[0].label —
// rendered visibly as a card-button label on the live funnel page. Confirmed
// on disk before use (this file's header comment is not enough — the marker
// must actually be present in the JSX render path, not just in a data array
// that could in principle never be mapped over).
const FUNNEL_MARKER = "Get a new Visa on Arrival";

const REQUEST_TIMEOUT_MS = 20_000;

const DEFAULT_BASE_URL = "https://balizero.com";

function defaultHeartbeatPath() {
  const home = process.env.HOME || os.homedir();
  return path.join(home, "logs", "voa-probe-heartbeat.json");
}

// ---------------------------------------------------------------------------
// PURE classifiers — exported, network-free, driven by --self-test and by
// scripts/tests/test_voa_probe_wrapper.sh via a `node -e` import.
// ---------------------------------------------------------------------------

/**
 * classifyPage({status, body}) -> {state: "dark"|"live"|"broken", reason}
 *
 * Order matters and is deliberate:
 *   1. non-200            -> broken   (a redirect loop, a 500, etc.)
 *   2. fallback marker     -> dark     (checked before the funnel marker: a
 *                                       404 template dark page could in
 *                                       principle also lack the funnel
 *                                       marker, and "dark" is the correct,
 *                                       non-incident classification for it)
 *   3. missing funnel text -> broken   (200, no fallback marker, but the
 *                                       expected live-funnel content is not
 *                                       there either — a real content break)
 *   4. else                -> live
 */
export function classifyPage({ status, body }) {
  if (status !== 200) {
    return { state: "broken", reason: `page_http_${status}` };
  }
  const text = typeof body === "string" ? body : "";
  if (text.includes(FALLBACK_MARKER)) {
    return { state: "dark", reason: "flag_off_next_404_template" };
  }
  if (!text.includes(FUNNEL_MARKER)) {
    return { state: "broken", reason: "page_content_missing" };
  }
  return { state: "live", reason: "page_ok" };
}

/**
 * classifyJourney(legs) -> {state: "ok"|"broken", reason}
 *
 * `legs` is an object of named leg results, each shaped `{ok: boolean,
 * reason?: string}` at minimum (runJourney() attaches richer fields for the
 * heartbeat, but only `.ok` is load-bearing here). Evaluated in a fixed
 * order so the FIRST broken leg names the reason, not the last.
 */
export function classifyJourney(legs) {
  const order = ["post", "get"];
  for (const name of order) {
    const leg = legs ? legs[name] : undefined;
    if (!leg || leg.ok !== true) {
      const detail = leg && leg.reason ? leg.reason : "leg_missing";
      return { state: "broken", reason: `leg_${name}_failed:${detail}` };
    }
  }
  return { state: "ok", reason: "journey_complete" };
}

/**
 * combineVerdict({page, journey, cleanup, dryRun}) -> {verdict, reason}
 *
 * The tri-state rule, in priority order:
 *   1. page broken                       -> fail (its own reason)
 *   2. journey broken (skipped on --dry-run) -> fail — this fires REGARDLESS
 *      of page.state, so `page dark + journey broken` is fail, never dark.
 *   3. cleanup leaked a row               -> fail, reason "cleanup_leaked"
 *   4. page dark                          -> dark
 *   5. else                               -> pass
 */
export function combineVerdict({ page, journey, cleanup, dryRun }) {
  if (page.state === "broken") {
    return { verdict: "fail", reason: page.reason };
  }
  if (!dryRun) {
    if (journey.state === "broken") {
      return { verdict: "fail", reason: journey.reason };
    }
    if ((cleanup?.leaked ?? 0) > 0) {
      return { verdict: "fail", reason: "cleanup_leaked" };
    }
  }
  if (page.state === "dark") {
    return { verdict: "dark", reason: page.reason };
  }
  return { verdict: "pass", reason: "page_live_journey_ok" };
}

// ---------------------------------------------------------------------------
// Civil-calendar date helpers (Asia/Makassar), pure
// ---------------------------------------------------------------------------

function makassarTodayIso() {
  // en-CA formats as YYYY-MM-DD, which is exactly the ISO date-only form the
  // contract wants — no manual field reassembly needed.
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return fmt.format(new Date());
}

function shiftDateOnly(isoDate, { days = 0, years = 0 }) {
  // Arithmetic done on a UTC-midnight Date built from the plain Y-M-D
  // components — this is calendar-day math, not instant math, so it never
  // reintroduces a timezone-of-the-clock dependency.
  const [y, m, d] = isoDate.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  if (years) dt.setUTCFullYear(dt.getUTCFullYear() + years);
  if (days) dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Cookie jar (manual — see header comment)
// ---------------------------------------------------------------------------

const RESULT_SESSION_COOKIE_NAME = "garuda_result_session";

function extractResultSessionCookieHeader(headers) {
  const setCookies =
    typeof headers.getSetCookie === "function" ? headers.getSetCookie() : [];
  for (const raw of setCookies) {
    const pair = raw.split(";")[0] ?? "";
    const eq = pair.indexOf("=");
    if (eq <= 0) continue;
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1);
    if (name === RESULT_SESSION_COOKIE_NAME) {
      return `${name}=${value}`;
    }
  }
  return null;
}

function resultIdFromLocation(location) {
  // Contract pattern: ^/visa/voa/[A-Za-z0-9_-]{22,128}$ — the PUBLIC frontend
  // path, not the API path. The API result id is the same opaque token.
  const match = /^\/visa\/voa\/([A-Za-z0-9_-]{22,128})$/.exec(location ?? "");
  return match ? match[1] : null;
}

// ---------------------------------------------------------------------------
// Network legs
// ---------------------------------------------------------------------------

function apiEligibilityChecksUrl(baseUrl) {
  return `${baseUrl}/api/visa/voa/eligibility-checks`;
}

function apiEligibilityResultUrl(baseUrl, resultId) {
  return `${baseUrl}/api/visa/voa/eligibility-checks/${resultId}`;
}

function syntheticCheckBody() {
  const today = makassarTodayIso();
  return {
    case_type: "issuance",
    nationality: "USA",
    entry_date: shiftDateOnly(today, { days: 30 }),
    passport_expiry_date: shiftDateOnly(today, { years: 3 }),
    purpose: "tourism",
    travellers: 1,
    self_pay: true,
    extension_already_used: false,
    retention_notice_acknowledged: true,
  };
}

async function fetchPage(baseUrl, fetchImpl) {
  const started = Date.now();
  try {
    const resp = await fetchImpl(`${baseUrl}/visa/voa`, {
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    const body = await resp.text();
    return {
      result: classifyPage({ status: resp.status, body }),
      latencyMs: Date.now() - started,
    };
  } catch (err) {
    return {
      result: {
        state: "broken",
        reason: `page_request_error:${err?.name ?? "unknown"}`,
      },
      latencyMs: Date.now() - started,
    };
  }
}

/**
 * runJourney({baseUrl, fetchImpl}) -> {legs, cleanup, latency}
 *
 * POST -> read Location + Set-Cookie -> GET (+jar) -> [finally] DELETE (+jar)
 * -> verify-GET (+jar). Cleanup runs in a `finally` block so a mid-journey
 * throw (a malformed response, a thrown fetch error) still attempts deletion
 * — otherwise every broken run would also be a leaked-row run.
 */
export async function runJourney({ baseUrl, fetchImpl }) {
  const legs = { post: null, get: null };
  const cleanup = { attempted: 0, verified_gone: 0, leaked: 0 };
  const latency = { post: null, get: null };
  let resultId = null;
  let cookieHeader = null;

  try {
    const postStarted = Date.now();
    let postResp;
    try {
      postResp = await fetchImpl(apiEligibilityChecksUrl(baseUrl), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": randomUUID(),
        },
        body: JSON.stringify(syntheticCheckBody()),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch (err) {
      legs.post = { ok: false, reason: `post_request_error:${err?.name ?? "unknown"}` };
      return { legs, cleanup, latency };
    }
    latency.post = Date.now() - postStarted;

    resultId = resultIdFromLocation(postResp.headers.get("location"));
    cookieHeader = extractResultSessionCookieHeader(postResp.headers);
    let postBody = null;
    try {
      postBody = await postResp.json();
    } catch {
      // non-JSON body — postOk below will be false, which is the correct
      // signal; we do not need the parse error itself.
    }

    const postOk =
      postResp.status === 201 &&
      Boolean(resultId) &&
      Boolean(cookieHeader) &&
      postBody?.verdict === "ACCEPT";

    legs.post = {
      ok: postOk,
      status: postResp.status,
      hasLocation: Boolean(resultId),
      hasCookie: Boolean(cookieHeader),
      verdict: postBody?.verdict ?? postBody?.code ?? null,
      reason: postOk
        ? "post_ok"
        : `post_unexpected:status=${postResp.status},location=${Boolean(resultId)},cookie=${Boolean(cookieHeader)},verdict=${postBody?.verdict ?? postBody?.code ?? "unknown"}`,
    };
    if (!postOk) {
      return { legs, cleanup, latency };
    }

    const getStarted = Date.now();
    let getResp;
    try {
      getResp = await fetchImpl(apiEligibilityResultUrl(baseUrl, resultId), {
        headers: { Cookie: cookieHeader },
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch (err) {
      legs.get = { ok: false, reason: `get_request_error:${err?.name ?? "unknown"}` };
      return { legs, cleanup, latency };
    }
    latency.get = Date.now() - getStarted;

    let getBody = null;
    try {
      getBody = await getResp.json();
    } catch {
      // handled by getOk below
    }
    const getOk = getResp.status === 200 && getBody?.verdict === "ACCEPT";
    legs.get = {
      ok: getOk,
      status: getResp.status,
      verdict: getBody?.verdict ?? getBody?.code ?? null,
      reason: getOk ? "get_ok" : `get_unexpected:status=${getResp.status}`,
    };
    return { legs, cleanup, latency };
  } finally {
    // W122 class: cleanup by CONSEQUENCE, never by the DELETE status code —
    // the balizero.com proxy is known to return 500 on a request the backend
    // actually served as 204. This block mutates `cleanup` in place; since
    // the object above is returned by reference, its final state is visible
    // to the caller even though the mutation happens after the `return`
    // statements above have already been evaluated.
    if (resultId) {
      cleanup.attempted += 1;
      try {
        await fetchImpl(apiEligibilityResultUrl(baseUrl, resultId), {
          method: "DELETE",
          headers: {
            "Idempotency-Key": randomUUID(),
            ...(cookieHeader ? { Cookie: cookieHeader } : {}),
          },
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });
      } catch {
        // Deliberately ignored — DELETE's own status/error is not the
        // signal. The verify-GET below is.
      }
      try {
        const verifyResp = await fetchImpl(apiEligibilityResultUrl(baseUrl, resultId), {
          headers: cookieHeader ? { Cookie: cookieHeader } : {},
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });
        if (verifyResp.status === 404) {
          cleanup.verified_gone += 1;
        } else {
          cleanup.leaked += 1;
        }
      } catch {
        // Cannot verify the row is gone — treat as leaked (fail loud) rather
        // than silently assuming success (W104: an unreachable check is not
        // evidence of health).
        cleanup.leaked += 1;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Heartbeat
// ---------------------------------------------------------------------------

/**
 * writeHeartbeatAtomic(targetPath, obj) — write `<targetPath>.tmp` then
 * rename over `targetPath`. A rename on the same filesystem is atomic, so a
 * concurrent reader (PR-3's dead-man) can never observe a half-written file.
 */
export function writeHeartbeatAtomic(targetPath, obj) {
  const dir = path.dirname(targetPath);
  fs.mkdirSync(dir, { recursive: true });
  const tmpPath = `${targetPath}.tmp`;
  fs.writeFileSync(tmpPath, `${JSON.stringify(obj, null, 2)}\n`, { mode: 0o644 });
  fs.renameSync(tmpPath, targetPath);
}

// ---------------------------------------------------------------------------
// Self-test (pure classifiers only — zero network calls)
// ---------------------------------------------------------------------------

function assertEqual(actual, expected, label, failures) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    failures.push(`${label}: expected ${e}, got ${a}`);
  }
}

export function runSelfTest() {
  const failures = [];
  let count = 0;
  const check = (actual, expected, label) => {
    count += 1;
    assertEqual(actual, expected, label, failures);
  };

  // classifyPage
  check(
    classifyPage({ status: 200, body: `blah ${FALLBACK_MARKER} blah` }).state,
    "dark",
    "classifyPage: fallback marker -> dark",
  );
  check(
    classifyPage({ status: 200, body: `<html>...${FUNNEL_MARKER}...</html>` }).state,
    "live",
    "classifyPage: funnel marker -> live",
  );
  check(
    classifyPage({ status: 200, body: "<html>nothing relevant</html>" }).state,
    "broken",
    "classifyPage: 200 but no marker of either kind -> broken",
  );
  check(
    classifyPage({ status: 500, body: "" }).state,
    "broken",
    "classifyPage: non-200 -> broken",
  );
  check(
    classifyPage({ status: 404, body: `also has ${FALLBACK_MARKER} here` }).state,
    "broken",
    "classifyPage: non-200 wins over any body content",
  );

  // classifyJourney
  check(
    classifyJourney({ post: { ok: true }, get: { ok: true } }).state,
    "ok",
    "classifyJourney: both legs ok -> ok",
  );
  check(
    classifyJourney({ post: { ok: false, reason: "post_unexpected" }, get: { ok: true } }).state,
    "broken",
    "classifyJourney: post leg broken -> broken",
  );
  check(
    classifyJourney({ post: { ok: true }, get: { ok: false, reason: "get_unexpected" } }).state,
    "broken",
    "classifyJourney: get leg broken -> broken",
  );

  // combineVerdict — the crux of the tri-state design
  check(
    combineVerdict({
      page: { state: "dark", reason: "flag_off_next_404_template" },
      journey: { state: "ok" },
      cleanup: { leaked: 0 },
      dryRun: false,
    }).verdict,
    "dark",
    "combineVerdict: dark page + ok journey -> dark, NOT fail",
  );
  check(
    combineVerdict({
      page: { state: "dark", reason: "flag_off_next_404_template" },
      journey: { state: "broken", reason: "leg_get_failed:get_unexpected" },
      cleanup: { leaked: 0 },
      dryRun: false,
    }).verdict,
    "fail",
    "combineVerdict: dark page + BROKEN journey -> fail (darkness cannot mask a real backend break)",
  );
  check(
    combineVerdict({
      page: { state: "live" },
      journey: { state: "ok" },
      cleanup: { leaked: 0 },
      dryRun: false,
    }).verdict,
    "pass",
    "combineVerdict: live page + ok journey -> pass",
  );
  check(
    combineVerdict({
      page: { state: "broken", reason: "page_http_500" },
      journey: { state: "ok" },
      cleanup: { leaked: 0 },
      dryRun: false,
    }).verdict,
    "fail",
    "combineVerdict: broken page -> fail regardless of journey state",
  );
  check(
    combineVerdict({
      page: { state: "live" },
      journey: { state: "ok" },
      cleanup: { leaked: 1 },
      dryRun: false,
    }).verdict,
    "fail",
    "combineVerdict: leaked cleanup row forces fail even when journey is ok",
  );
  check(
    combineVerdict({
      page: { state: "dark", reason: "flag_off_next_404_template" },
      journey: { state: "ok" },
      cleanup: { leaked: 0 },
      dryRun: true,
    }).verdict,
    "dark",
    "combineVerdict: --dry-run with a dark page -> dark (journey never evaluated)",
  );

  if (failures.length > 0) {
    console.error(`SELF-TEST FAILED (${failures.length}/${count} assertions failed):`);
    for (const f of failures) console.error(`  - ${f}`);
    return false;
  }
  console.log(`SELF-TEST OK (${count} assertions, 0 network calls)`);
  return true;
}

// ---------------------------------------------------------------------------
// main()
// ---------------------------------------------------------------------------

async function main(argv) {
  const dryRun = argv.includes("--dry-run");
  const baseUrl = process.env.VOA_PROBE_BASE_URL || DEFAULT_BASE_URL;
  const heartbeatPath = process.env.VOA_PROBE_HEARTBEAT || defaultHeartbeatPath();

  let heartbeat;
  try {
    const { result: pageResult, latencyMs: pageLatency } = await fetchPage(baseUrl, fetch);

    let apiLegs = null;
    let cleanup = { attempted: 0, verified_gone: 0, leaked: 0 };
    let postLatency = null;
    let getLatency = null;

    if (!dryRun) {
      const journeyOutcome = await runJourney({ baseUrl, fetchImpl: fetch });
      apiLegs = journeyOutcome.legs;
      cleanup = journeyOutcome.cleanup;
      postLatency = journeyOutcome.latency.post;
      getLatency = journeyOutcome.latency.get;
    }

    const journeyResult = apiLegs
      ? classifyJourney(apiLegs)
      : { state: "ok", reason: "dry_run_skipped" };

    const overall = combineVerdict({
      page: pageResult,
      journey: journeyResult,
      cleanup,
      dryRun,
    });

    heartbeat = {
      schema: 1,
      probe: "voa_journey",
      ts: new Date().toISOString(),
      ts_epoch: Math.floor(Date.now() / 1000),
      verdict: overall.verdict,
      reason: overall.reason,
      latency_ms: { page: pageLatency, post: postLatency, get: getLatency },
      legs: { page: pageResult, api: apiLegs ?? { skipped: true, reason: "dry_run" } },
      cleanup,
      base_url: baseUrl,
      probe_version: 1,
    };
  } catch (err) {
    // Catch-all: a heartbeat MUST be written even on a totally unexpected
    // crash — a missing heartbeat means "did not run", never "ran and
    // failed" (superscar #2). This is the last line of defense; every
    // sub-step above already has its own try/catch for the expected failure
    // shapes, so reaching here means something genuinely unforeseen broke.
    heartbeat = {
      schema: 1,
      probe: "voa_journey",
      ts: new Date().toISOString(),
      ts_epoch: Math.floor(Date.now() / 1000),
      verdict: "fail",
      reason: `probe_crashed:${err?.name ?? "unknown"}:${String(err?.message ?? err).slice(0, 200)}`,
      latency_ms: { page: null, post: null, get: null },
      legs: {},
      cleanup: { attempted: 0, verified_gone: 0, leaked: 0 },
      base_url: baseUrl,
      probe_version: 1,
    };
  }

  writeHeartbeatAtomic(heartbeatPath, heartbeat);
  console.log(JSON.stringify(heartbeat));
  process.exit(heartbeat.verdict === "fail" ? 1 : 0);
}

function isMainModule() {
  try {
    const invoked = process.argv[1];
    if (!invoked) return false;
    return import.meta.url === pathToFileURL(invoked).href;
  } catch {
    return false;
  }
}

if (isMainModule()) {
  const argv = process.argv.slice(2);
  if (argv.includes("--self-test")) {
    process.exit(runSelfTest() ? 0 : 1);
  } else {
    main(argv);
  }
}
