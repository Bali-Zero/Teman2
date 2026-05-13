// index.ts — wa-mirror orchestrator. Entry point for `npm start`.
//
// Reads the team roster from the env var WA_MIRROR_TEAM_MEMBERS
//   ("alice@balizero.com,bob@balizero.com,...") and starts one Baileys
// session per email. On graceful shutdown (SIGINT/SIGTERM) closes the PG
// pool. Crashes in a single team-member session are isolated and logged;
// the orchestrator does NOT restart them automatically — the team member
// rescans the QR via `npm run onboard -- --email=...`.

import "dotenv/config";

import pino from "pino";

import { closePool } from "./pg.js";
import { startSession } from "./session.js";

const logger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: undefined,
});

function parseRoster(): string[] {
  const raw = process.env.WA_MIRROR_TEAM_MEMBERS ?? "";
  return raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s) => s.length > 0 && s.includes("@"));
}

async function main(): Promise<void> {
  const roster = parseRoster();
  if (roster.length === 0) {
    logger.error(
      "WA_MIRROR_TEAM_MEMBERS is empty. Set it to a comma-separated list of " +
        "team-member emails before starting the daemon."
    );
    process.exit(2);
  }
  logger.info({ count: roster.length, members: roster }, "wa-mirror starting");

  const tasks = roster.map((email) =>
    startSession({
      teamMemberEmail: email,
      sessionLabel: process.env.WA_MIRROR_SESSION_LABEL,
      sessionsRoot: process.env.WA_MIRROR_SESSIONS_ROOT,
    }).catch((err) => {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error({ email, msg }, "wa-mirror session crashed");
      // Returning null keeps Promise.all alive for the other members.
      return null;
    })
  );

  await Promise.all(tasks);
  logger.info("wa-mirror all sessions settled. Daemon staying alive for events.");

  // Keep the process up forever — Baileys event handlers fire async; closing
  // here would tear the bridge down. SIGINT/SIGTERM handle shutdown.
  await new Promise<void>(() => undefined);
}

async function shutdown(signal: string): Promise<void> {
  logger.warn({ signal }, "wa-mirror shutdown requested");
  try {
    await closePool();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.error({ msg }, "pool close failed");
  }
  process.exit(0);
}

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));
process.on("uncaughtException", (err) => {
  logger.error({ err: err.message, stack: err.stack }, "uncaughtException");
});
process.on("unhandledRejection", (reason) => {
  logger.error({ reason: String(reason) }, "unhandledRejection");
});

main().catch((err) => {
  const msg = err instanceof Error ? err.message : String(err);
  logger.error({ msg }, "wa-mirror main crashed");
  process.exit(1);
});
