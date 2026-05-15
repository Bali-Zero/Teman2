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
import { startSession } from "./session.js";
import { sendTelegramAlert } from "./telegram.js";

const logger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: undefined,
});

type AccountConfig = {
  phone: string;
  name: string;
};

function parseAccounts(): AccountConfig[] {
  const raw =
    process.env.WA_MIRROR_ACCOUNTS ?? process.env.WA_MIRROR_TEAM_MEMBERS ?? "";
  const names = parseAccountNames();
  return raw
    .split(",")
    .map((s) => normalizePhone(s.trim()))
    .filter((phone) => phone.length > 0)
    .map((phone) => ({
      phone,
      name: names.get(phone) ?? phone,
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

async function main(): Promise<void> {
  const accounts = parseAccounts();
  if (accounts.length === 0) {
    logger.error(
      "WA_MIRROR_ACCOUNTS is empty. Set it to comma-separated E.164 phones " +
        "before starting the daemon."
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
    "wa-mirror all sessions launched; reconnect loops own their lifecycle"
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
        sessionLabel: process.env.WA_MIRROR_SESSION_LABEL,
        sessionsRoot: process.env.WA_MIRROR_SESSIONS_ROOT,
        resolveOnFirstOpen: false,
      });
      logger.warn(
        "wa-mirror session promise resolved unexpectedly (daemon mode)"
      );
      attempt = 0;
    } catch {
      const delayMs = Math.min(2_000 * 2 ** Math.min(attempt - 1, 5), 60_000);
      logger.error(
        { attempt, delayMs },
        "wa-mirror session crashed; restarting with backoff"
      );
      await sendTelegramAlert(
        `wa-mirror disconnected: ${account.name}; reconnect_attempt=${attempt}`,
        logger
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
process.on("uncaughtException", () => {
  logger.error("uncaughtException");
});
process.on("unhandledRejection", () => {
  logger.error("unhandledRejection");
});

main().catch(() => {
  logger.error("wa-mirror main crashed");
  process.exit(1);
});
