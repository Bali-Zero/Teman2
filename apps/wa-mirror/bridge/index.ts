// index.ts — wa-mirror orchestrator. Entry point for `npm start`.
//
// Reads the team roster from the env var WA_MIRROR_ACCOUNTS
//   ("+62812...,+62813...") and starts one Baileys session per phone.
// Each session runs `startSession` with
// resolveOnFirstOpen=false, so its promise NEVER resolves under normal
// operation — the reconnect loop inside session.ts keeps it alive across
// transient closes (restartRequired 515, connectionLost 408, etc.).
//
// A session promise only SETTLES (rejects) on a terminal `loggedOut`: the
// team member removed the linked device and must re-scan the QR via
// `npm run onboard -- --email=...`. When that happens we log it and let the
// other sessions keep running — we do NOT exit the process.
//
// On graceful shutdown (SIGINT/SIGTERM) we close the PG pool and exit.

import "dotenv/config";

import pino from "pino";

import { closePool } from "./pg.js";
import { normalizePhone } from "./phone.js";
import { SessionLoggedOutError, startSession } from "./session.js";
import { sendTelegramAlert } from "./telegram.js";

const logger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: undefined,
});

type AccountConfig = {
  phone: string;
  name: string;
  /**
   * FIX 4 (2026-05-26): optional team member email, sourced from
   * WA_MIRROR_ACCOUNT_EMAILS JSON map keyed by phone. Defaults to "" when
   * the manifest does not declare it — downstream CRM join handles "" as
   * "unmapped team member".
   */
  email: string;
};

function parseAccounts(): AccountConfig[] {
  const raw =
    process.env.WA_MIRROR_ACCOUNTS ?? process.env.WA_MIRROR_TEAM_MEMBERS ?? "";
  const names = parseAccountNames();
  const emails = parseAccountEmails();
  return raw
    .split(",")
    .map((s) => normalizePhone(s.trim()))
    .filter((phone) => phone.length > 0)
    .map((phone) => ({
      phone,
      name: names.get(phone) ?? phone,
      email: emails.get(phone) ?? "",
    }));
}

function parseAccountNames(): Map<string, string> {
  const names = new Map<string, string>();
  const raw = process.env.WA_MIRROR_ACCOUNT_NAMES;
  if (!raw) return names;
  try {
    const parsed = JSON.parse(raw) as Record<string, string>;
    for (const [phone, name] of Object.entries(parsed)) {
      const normalized = normalizePhone(phone);
      if (normalized && name.trim()) names.set(normalized, name.trim());
    }
  } catch {
    logger.warn("WA_MIRROR_ACCOUNT_NAMES is not valid JSON");
  }
  return names;
}

/**
 * FIX 4 (2026-05-26): parse WA_MIRROR_ACCOUNT_EMAILS as a JSON map
 *   {"<phone>": "<email>"}. Missing/invalid → empty map, accounts default
 *   to email="". Never crashes the daemon on malformed JSON.
 */
function parseAccountEmails(): Map<string, string> {
  const emails = new Map<string, string>();
  const raw = process.env.WA_MIRROR_ACCOUNT_EMAILS;
  if (!raw) return emails;
  try {
    const parsed = JSON.parse(raw) as Record<string, string>;
    for (const [phone, email] of Object.entries(parsed)) {
      const normalized = normalizePhone(phone);
      const trimmed = (email ?? "").trim().toLowerCase();
      if (normalized && trimmed) emails.set(normalized, trimmed);
    }
  } catch {
    logger.warn("WA_MIRROR_ACCOUNT_EMAILS is not valid JSON");
  }
  return emails;
}

async function main(): Promise<void> {
  const accounts = parseAccounts();
  if (accounts.length === 0) {
    logger.error(
      "WA_MIRROR_ACCOUNTS is empty. Set it to comma-separated E.164 phones " +
        "before starting the daemon.",
    );
    process.exit(2);
  }
  logger.info({ count: accounts.length }, "wa-mirror starting");

  // Each startSession promise is expected to stay pending forever (the
  // reconnect loop owns the lifecycle). We attach a .catch purely to observe
  // the terminal loggedOut rejection — we never let it bubble or tear down
  // the process. The daemon keeps running so the OTHER members stay mirrored
  // and so a re-onboarded member is picked up on the next daemon restart.
  for (const account of accounts) {
    void runAccountForever(account);
  }

  logger.info(
    { count: accounts.length },
    "wa-mirror all sessions launched; reconnect loops own their lifecycle",
  );

  // Keep the process up forever — Baileys event handlers and the reconnect
  // setTimeout callbacks fire async. SIGINT/SIGTERM handle shutdown.
  await new Promise<void>(() => undefined);
}

async function runAccountForever(account: AccountConfig): Promise<void> {
  let attempt = 0;
  for (;;) {
    attempt += 1;
    try {
      await startSession({
        accountPhone: account.phone,
        teamMemberName: account.name,
        teamMemberEmail: account.email,
        sessionLabel: process.env.WA_MIRROR_SESSION_LABEL,
        sessionsRoot: process.env.WA_MIRROR_SESSIONS_ROOT,
        resolveOnFirstOpen: false,
      });
      logger.warn(
        "wa-mirror session promise resolved unexpectedly (daemon mode)",
      );
      attempt = 0;
    } catch (err) {
      if (err instanceof SessionLoggedOutError) {
        // Terminal: the device was removed/invalidated on the WhatsApp side.
        // Retrying cannot recover it — it only spams Telegram every 60s and
        // hammers WhatsApp with dead credentials (raising the anti-automation
        // flag risk). Stop this account's loop and alert ONCE; a re-onboard
        // (start-one.sh <name> --qr) + daemon restart picks it back up. The
        // process stays alive (main() awaits forever) so other accounts in a
        // multi-account process keep mirroring.
        logger.error(
          { attempt },
          "wa-mirror session logged out (terminal) — stopping retries, needs QR re-link",
        );
        await sendTelegramAlert(
          `wa-mirror LOGGED OUT: ${account.name} — device unlinked on WhatsApp side. ` +
            `Needs QR re-link (start-one.sh <name> --qr). Retries stopped at attempt ${attempt}.`,
          logger,
        );
        return;
      }
      const delayMs = Math.min(2_000 * 2 ** Math.min(attempt - 1, 5), 60_000);
      logger.error(
        { attempt, delayMs },
        "wa-mirror session crashed; restarting with backoff",
      );
      await sendTelegramAlert(
        `wa-mirror disconnected: ${account.name}; reconnect_attempt=${attempt}`,
        logger,
      );
      await sleep(delayMs);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function shutdown(signal: string): Promise<void> {
  logger.warn({ signal }, "wa-mirror shutdown requested");
  try {
    await closePool();
  } catch {
    logger.error("pool close failed");
  }
  process.exit(0);
}

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));
// FIX 10 (2026-05-26): include err message + stack so diagnostics are
// possible. Pre-fix log line had no payload, so a post-mortem from launchd
// stderr was effectively impossible.
process.on("uncaughtException", (err: unknown) => {
  const e = err as { message?: string; stack?: string } | null;
  logger.error({ err: e?.message, stack: e?.stack }, "uncaughtException");
});
process.on("unhandledRejection", (reason: unknown) => {
  logger.error({ reason: String(reason) }, "unhandledRejection");
});

main().catch(() => {
  logger.error("wa-mirror main crashed");
  process.exit(1);
});
