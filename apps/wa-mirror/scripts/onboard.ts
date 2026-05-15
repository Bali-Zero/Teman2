// onboard.ts — single-shot QR scan helper for ONE team member.
//
// Usage:
//   tsx scripts/onboard.ts --email=adit@balizero.com --phone=+6281234567890
//
// The script starts the Baileys session for the given phone, prints the QR
// to stderr, waits for the `open` event, then exits cleanly. After exit,
// the auth state is persisted to apps/wa-mirror/sessions/<phone>/ and the
// long-running daemon (`npm start`) will pick it up on next restart.

import "dotenv/config";

import pino from "pino";

import { closePool } from "../bridge/pg.js";
import { normalizePhone } from "../bridge/phone.js";
import { startSession } from "../bridge/session.js";

const logger = pino({ level: "info", base: undefined });

function parseArgs(): { phone: string; name: string } {
  const phoneArg =
    process.argv.find((a) => a.startsWith("--phone=")) ??
    process.argv.find((a) => a.startsWith("--account="));
  if (!phoneArg) {
    process.stderr.write(
      "Usage: tsx scripts/onboard.ts --phone=<E.164> [--name=<name>]\n"
    );
    process.exit(2);
  }
  const phone = normalizePhone(phoneArg.slice(phoneArg.indexOf("=") + 1));
  if (!phone) {
    process.stderr.write(`Invalid phone: ${phoneArg}\n`);
    process.exit(2);
  }
  const nameArg = process.argv.find((a) => a.startsWith("--name="));
  const emailArg = process.argv.find((a) => a.startsWith("--email="));
  const name = nameArg
    ? nameArg.slice("--name=".length).trim()
    : emailArg
      ? emailArg.slice("--email=".length).trim().toLowerCase()
      : phone;
  return { phone, name };
}

async function main(): Promise<void> {
  const { phone, name } = parseArgs();
  logger.info({ phone, name }, "wa-mirror onboarding started; print QR & wait for open");
  try {
    // resolveOnFirstOpen=true: the reconnect loop inside startSession still
    // absorbs the post-pairing restartRequired (code 515) bounce, but the
    // promise resolves the first time the session reaches `connected` and the
    // socket is then closed. The persisted auth state in
    // apps/wa-mirror/sessions/<phone>/ is what the daemon picks up later.
    const sessionId = await startSession({
      accountPhone: phone,
      teamMemberName: name,
      sessionLabel: process.env.WA_MIRROR_SESSION_LABEL,
      sessionsRoot: process.env.WA_MIRROR_SESSIONS_ROOT,
      resolveOnFirstOpen: true,
    });
    logger.info(
      { phone, name, sessionId },
      "wa-mirror onboarding OK — auth state persisted; safe to ctrl-c"
    );
    await new Promise((r) => setTimeout(r, 1500));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.error({ phone, name, msg }, "wa-mirror onboarding failed");
    process.exitCode = 1;
  } finally {
    await closePool();
  }
}

main();
