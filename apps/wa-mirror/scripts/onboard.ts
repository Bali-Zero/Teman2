// onboard.ts — single-shot QR scan helper for ONE team member.
//
// Usage:
//   tsx scripts/onboard.ts --email=adit@balizero.com
//
// The script starts the Baileys session for the given email, prints the QR
// to stderr, waits for the `open` event, then exits cleanly. After exit,
// the auth state is persisted to ~/.wa-mirror/sessions/<email>/ and the
// long-running daemon (`npm start`) will pick it up on next restart.

import "dotenv/config";

import pino from "pino";

import { closePool } from "../bridge/pg.js";
import { startSession } from "../bridge/session.js";

const logger = pino({ level: "info", base: undefined });

function parseArgs(): { email: string } {
  const arg = process.argv.find((a) => a.startsWith("--email="));
  if (!arg) {
    process.stderr.write("Usage: tsx scripts/onboard.ts --email=<addr>\n");
    process.exit(2);
  }
  const email = arg.slice("--email=".length).trim().toLowerCase();
  if (!email.includes("@")) {
    process.stderr.write(`Invalid email: ${email}\n`);
    process.exit(2);
  }
  return { email };
}

async function main(): Promise<void> {
  const { email } = parseArgs();
  logger.info({ email }, "wa-mirror onboarding started; print QR & wait for open");
  try {
    // resolveOnFirstOpen=true: the reconnect loop inside startSession still
    // absorbs the post-pairing restartRequired (code 515) bounce, but the
    // promise resolves the first time the session reaches `connected` and the
    // socket is then closed. The persisted auth state in
    // ~/.wa-mirror/sessions/<email>/ is what the daemon picks up later.
    const sessionId = await startSession({
      teamMemberEmail: email,
      sessionLabel: process.env.WA_MIRROR_SESSION_LABEL,
      sessionsRoot: process.env.WA_MIRROR_SESSIONS_ROOT,
      resolveOnFirstOpen: true,
    });
    logger.info(
      { email, sessionId },
      "wa-mirror onboarding OK — auth state persisted; safe to ctrl-c"
    );
    await new Promise((r) => setTimeout(r, 1500));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.error({ email, msg }, "wa-mirror onboarding failed");
    process.exitCode = 1;
  } finally {
    await closePool();
  }
}

main();
