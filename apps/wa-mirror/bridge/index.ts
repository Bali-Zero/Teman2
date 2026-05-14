// index.ts — wa-mirror orchestrator. Entry point for `npm start`.
//
// Reads the team roster from the env var WA_MIRROR_TEAM_MEMBERS
//   ("alice@balizero.com,bob@balizero.com,...") and starts one Baileys
// session per email. Each session runs `startSession` with
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

  // Each startSession promise is expected to stay pending forever (the
  // reconnect loop owns the lifecycle). We attach a .catch purely to observe
  // the terminal loggedOut rejection — we never let it bubble or tear down
  // the process. The daemon keeps running so the OTHER members stay mirrored
  // and so a re-onboarded member is picked up on the next daemon restart.
  for (const email of roster) {
    startSession({
      teamMemberEmail: email,
      sessionLabel: process.env.WA_MIRROR_SESSION_LABEL,
      sessionsRoot: process.env.WA_MIRROR_SESSIONS_ROOT,
      resolveOnFirstOpen: false,
    })
      .then(() => {
        // Should not happen with resolveOnFirstOpen=false, but log if it does.
        logger.warn(
          { email },
          "wa-mirror session promise resolved unexpectedly (daemon mode)"
        );
      })
      .catch((err) => {
        const msg = err instanceof Error ? err.message : String(err);
        logger.error(
          { email, msg },
          "wa-mirror session terminated (logged out — needs re-onboarding)"
        );
      });
  }

  logger.info(
    { count: roster.length },
    "wa-mirror all sessions launched; reconnect loops own their lifecycle"
  );

  // Keep the process up forever — Baileys event handlers and the reconnect
  // setTimeout callbacks fire async. SIGINT/SIGTERM handle shutdown.
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
