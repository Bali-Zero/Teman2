// wa-tester.ts — standalone WhatsApp phone-test CLI.
//
// Runs end-to-end batteries against the Zantara WA bot (+62 821 3465 159)
// FROM Zero's own WhatsApp number (+62 822 3010 2328). This is a SEPARATE,
// single-purpose organ — it does NOT touch apps/wa-mirror's read-only-mirror
// invariant (bridge/session.ts: "we never call sock.sendMessage"), does NOT
// write to Postgres/CRM, does NOT enter the mirror's accounts roster, plist,
// or supervisor, and is on-demand only (no cron, no daemon). See
// docs/wa-tester.md for the full picture.
//
// Usage:
//   tsx scripts/wa-tester.ts --pair
//   tsx scripts/wa-tester.ts --send-battery battery.json [--out transcript.json]
//   tsx scripts/wa-tester.ts --status
//
// Auth state lives under WA_TESTER_STATE_DIR (default
// ~/.wa-tester/state/+6282230102328/) — NEVER under apps/wa-mirror/sessions/.

import "dotenv/config";

import { Boom } from "@hapi/boom";
import makeWASocket, {
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import type { BaileysEventMap, WASocket } from "@whiskeysockets/baileys";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import pino from "pino";
import qrcodeTerminal from "qrcode-terminal";
import QRCode from "qrcode";

import { isTerminalCloseCode, mapCloseReason } from "../bridge/session.js";
import {
  BOT_JID,
  BOT_PHONE_E164,
  QUIET_PERIOD_S,
  ReplyCollector,
  TESTER_PHONE_DIGITS,
  TESTER_PHONE_E164,
  buildQuestionResult,
  buildTranscript,
  extractMessageText,
  isPairedFromCreds,
  parseMessageTimestampMs,
  shouldReconnect,
  transcriptHasZeroReplyQuestion,
  validateBattery,
  type QuestionResult,
  type StoredCreds,
} from "./wa-tester-core.js";

const logger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: undefined,
});

const STATE_DIR =
  process.env.WA_TESTER_STATE_DIR ??
  path.join(homedir(), ".wa-tester", "state", TESTER_PHONE_E164);

const QR_PATH = `/tmp/qr-tester-${TESTER_PHONE_DIGITS}.png`;

const PAIR_MAX_ATTEMPTS = 2; // initial connect + ONE reconnect for the post-pairing 515 bounce
const PAIR_STABLE_WINDOW_MS = 12_000; // time to wait after `open` to see if a 515 bounce follows
const STATUS_CONNECT_TIMEOUT_MS = 20_000;

async function ensureStateDir(): Promise<void> {
  await mkdir(STATE_DIR, { recursive: true });
  // Scar #4 (secret-in-the-clear): Baileys auth state includes the Signal
  // identity/session keys — treat it exactly like any other credential dir.
  await chmod(STATE_DIR, 0o700);
}

async function isPaired(): Promise<boolean> {
  try {
    const raw = await readFile(path.join(STATE_DIR, "creds.json"), "utf8");
    const creds = JSON.parse(raw) as StoredCreds;
    // QR-companion pairing sets creds.me, not creds.registered (pairing-code flow only)
    return isPairedFromCreds(creds);
  } catch {
    return false;
  }
}

function makeSocket(
  version: [number, number, number],
  authState: Awaited<ReturnType<typeof useMultiFileAuthState>>["state"],
): WASocket {
  return makeWASocket({
    version,
    auth: {
      creds: authState.creds,
      keys: makeCacheableSignalKeyStore(authState.keys, logger),
    },
    printQRInTerminal: false,
    browser: ["Bali Zero WA-Tester", "Chrome", "1.0.0"],
    logger: logger.child({ component: "baileys" }),
    markOnlineOnConnect: true,
    // Mirror bridge/session.ts's proven-safe socket options (CICATRIX
    // 2026-05-25): full history sync avoids the LID-mapping instability bug
    // Baileys' own DANGER log warns about when sync is disabled.
    syncFullHistory: true,
    generateHighQualityLinkPreview: false,
    defaultQueryTimeoutMs: 60_000,
    keepAliveIntervalMs: 25_000,
  });
}

type CloseInfo = { code: number; terminal: boolean; reason: string };

function readCloseInfo(
  lastDisconnect: { error?: unknown } | null | undefined,
): CloseInfo {
  const code =
    (lastDisconnect as { error?: Boom } | undefined)?.error?.output
      ?.statusCode ?? 0;
  return {
    code,
    terminal: isTerminalCloseCode(code),
    reason: mapCloseReason(code),
  };
}

// ---------------------------------------------------------------------------
// --pair
// ---------------------------------------------------------------------------

async function runPair(): Promise<void> {
  await ensureStateDir();
  const { version } = await fetchLatestBaileysVersion();

  let attempt = 0;
  let openedOnce = false;

  while (true) {
    attempt += 1;
    const { state, saveCreds } = await useMultiFileAuthState(STATE_DIR);
    const sock = makeSocket(version, state);
    sock.ev.on("creds.update", saveCreds);

    const outcome = await new Promise<"open" | "close">((resolve, reject) => {
      sock.ev.on("connection.update", (update) => {
        void (async () => {
          if (update.qr) {
            await QRCode.toFile(QR_PATH, update.qr, { width: 400 });
            process.stderr.write(
              `\n[wa-tester] QR saved to ${QR_PATH} — open it with: open ${QR_PATH}\n`,
            );
            qrcodeTerminal.generate(update.qr, { small: true }, (ascii) => {
              process.stdout.write(ascii + "\n");
            });
          }
          if (update.connection === "open") {
            resolve("open");
          } else if (update.connection === "close") {
            const info = readCloseInfo(update.lastDisconnect);
            logger.warn(
              { attempt, ...info },
              "wa-tester pair: connection closed",
            );
            if (info.terminal) {
              reject(
                new Error(
                  `wa-tester: pairing failed — terminal close (${info.reason})`,
                ),
              );
              return;
            }
            resolve("close");
          }
        })();
      });
    });

    if (outcome === "open") {
      openedOnce = true;
      logger.info(
        { attempt, jid: sock.user?.id },
        "wa-tester pair: connection open",
      );
      // Wait a bit to see whether the expected post-pairing 515 bounce
      // follows. If the socket stays open for the stable window, we're done.
      const bounced = await waitForBounceOrStable(sock);
      if (!bounced) {
        sock.end(undefined);
        process.stdout.write(`PAIRED — auth state saved to ${STATE_DIR}\n`);
        return;
      }
      // A close fired during the stable window — fall through to the
      // reconnect-attempt gate below using the close info already logged.
    }

    const terminalSoFar = false; // non-terminal closes only reach here (terminal rejects above)
    if (
      !shouldReconnect({
        terminal: terminalSoFar,
        attempt,
        maxAttempts: PAIR_MAX_ATTEMPTS,
      })
    ) {
      throw new Error(
        `wa-tester: pairing did not stabilize after ${attempt} attempt(s) — ` +
          (openedOnce
            ? "connection opened but kept bouncing; try again"
            : "connection never opened; QR likely expired unscanned — try again"),
      );
    }
    logger.info(
      { attempt },
      "wa-tester pair: reconnecting once (515 bounce contract)",
    );
  }
}

/** Resolves `true` if the socket closes within PAIR_STABLE_WINDOW_MS
 * (the expected post-pairing 515 bounce), `false` if it stays open. */
function waitForBounceOrStable(sock: WASocket): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      sock.ev.off("connection.update", onUpdate);
      resolve(false);
    }, PAIR_STABLE_WINDOW_MS);
    const onUpdate = (update: BaileysEventMap["connection.update"]) => {
      if (settled) return;
      if (update.connection === "close") {
        settled = true;
        clearTimeout(timer);
        sock.ev.off("connection.update", onUpdate);
        resolve(true);
      }
    };
    sock.ev.on("connection.update", onUpdate);
  });
}

// ---------------------------------------------------------------------------
// --status
// ---------------------------------------------------------------------------

async function runStatus(): Promise<void> {
  if (!(await isPaired())) {
    process.stdout.write(`NOT_PAIRED — run: tsx scripts/wa-tester.ts --pair\n`);
    process.exitCode = 1;
    return;
  }

  const { version } = await fetchLatestBaileysVersion();
  const { state, saveCreds } = await useMultiFileAuthState(STATE_DIR);
  const sock = makeSocket(version, state);
  sock.ev.on("creds.update", saveCreds);

  const result = await new Promise<{ ok: boolean; detail: string }>(
    (resolve) => {
      const timer = setTimeout(() => {
        resolve({ ok: false, detail: "connect timed out" });
      }, STATUS_CONNECT_TIMEOUT_MS);
      sock.ev.on("connection.update", (update) => {
        if (update.connection === "open") {
          clearTimeout(timer);
          resolve({ ok: true, detail: sock.user?.id ?? "connected" });
        } else if (update.connection === "close") {
          const info = readCloseInfo(update.lastDisconnect);
          if (info.terminal) {
            clearTimeout(timer);
            resolve({
              ok: false,
              detail: `logged out (${info.reason}) — re-pair required`,
            });
          }
          // non-terminal: keep waiting until the timeout above fires
        }
      });
    },
  );

  try {
    sock.end(undefined);
  } catch {
    // socket already tearing down — non-fatal
  }

  if (result.ok) {
    process.stdout.write(`PAIRED_AND_CONNECTED — ${result.detail}\n`);
  } else {
    process.stdout.write(`PAIRED_BUT_CONNECT_FAILED — ${result.detail}\n`);
    process.exitCode = 2;
  }
}

// ---------------------------------------------------------------------------
// --send-battery
// ---------------------------------------------------------------------------

async function connectPairedSocket(): Promise<WASocket> {
  const { version } = await fetchLatestBaileysVersion();
  const { state, saveCreds } = await useMultiFileAuthState(STATE_DIR);
  const sock = makeSocket(version, state);
  sock.ev.on("creds.update", saveCreds);

  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(
        new Error(
          "wa-tester: connect timed out before questions could be sent",
        ),
      );
    }, STATUS_CONNECT_TIMEOUT_MS);
    sock.ev.on("connection.update", (update) => {
      if (update.connection === "open") {
        clearTimeout(timer);
        resolve();
      } else if (update.connection === "close") {
        const info = readCloseInfo(update.lastDisconnect);
        if (info.terminal) {
          clearTimeout(timer);
          reject(
            new Error(
              `wa-tester: logged out (${info.reason}) — re-pair required`,
            ),
          );
        }
        // non-terminal pre-open bounce: keep waiting for the retry inside
        // Baileys' own queueing, bounded by the timer above.
      }
    });
  });
  return sock;
}

/** Subscribes to messages.upsert scoped ONLY to the bot's JID conversation.
 * Privacy rail: every other chat/event is ignored and never logged. */
function collectReplies(
  sock: WASocket,
  sentAtMs: number,
  replyTimeoutS: number,
): Promise<{ text: string; timestampMs: number }[]> {
  const collector = new ReplyCollector({
    sentAtMs,
    replyTimeoutS,
    quietPeriodS: QUIET_PERIOD_S,
  });

  const onUpsert = (event: BaileysEventMap["messages.upsert"]) => {
    if (event.type !== "notify") return;
    for (const m of event.messages) {
      if (m.key?.remoteJid !== BOT_JID) continue; // ignore every other chat, no exceptions
      if (m.key?.fromMe) continue; // our own outbound echo, not a bot reply
      const text = extractMessageText(m.message);
      if (!text) continue;
      const ts = parseMessageTimestampMs(m.messageTimestamp as never);
      collector.addReply(text, ts);
    }
  };

  sock.ev.on("messages.upsert", onUpsert);
  return new Promise((resolve) => {
    const POLL_MS = 250;
    const timer = setInterval(() => {
      if (collector.verdict(Date.now()) !== "collecting") {
        clearInterval(timer);
        sock.ev.off("messages.upsert", onUpsert);
        resolve(collector.all);
      }
    }, POLL_MS);
  });
}

async function runSendBattery(
  batteryPath: string,
  outPath: string,
): Promise<void> {
  const raw = JSON.parse(await readFile(batteryPath, "utf8"));
  const validation = validateBattery(raw);
  if (!validation.ok) {
    // The allowlist guard (and every other validation) runs BEFORE any
    // socket connects and BEFORE any send — a bad battery never gets a
    // chance to touch the network.
    throw new Error(`wa-tester: invalid battery — ${validation.error}`);
  }
  const battery = validation.battery;

  if (!(await isPaired())) {
    throw new Error(
      "wa-tester: not paired — run: tsx scripts/wa-tester.ts --pair",
    );
  }

  const sock = await connectPairedSocket();
  logger.info(
    { jid: sock.user?.id, questions: battery.questions.length },
    "wa-tester: connected — starting battery",
  );

  const startedAtMs = Date.now();
  const results: QuestionResult[] = [];

  try {
    for (let i = 0; i < battery.questions.length; i++) {
      const question = battery.questions[i];
      const sentAtMs = Date.now();
      await sock.sendMessage(BOT_JID, { text: question.text });
      logger.info({ id: question.id }, "wa-tester: question sent");

      const replies = await collectReplies(
        sock,
        sentAtMs,
        battery.reply_timeout_s,
      );
      const result = buildQuestionResult(question, sentAtMs, replies);
      results.push(result);
      logger.info(
        { id: question.id, reply_count: result.reply_count },
        "wa-tester: question done",
      );

      const isLast = i === battery.questions.length - 1;
      if (!isLast) {
        await new Promise((r) =>
          setTimeout(r, battery.inter_question_delay_s * 1000),
        );
      }
    }
  } finally {
    try {
      sock.end(undefined);
    } catch {
      // socket already tearing down — non-fatal
    }
  }

  const finishedAtMs = Date.now();
  const transcript = buildTranscript({
    batteryFile: path.resolve(batteryPath),
    botJid: BOT_JID,
    startedAtMs,
    finishedAtMs,
    results,
  });

  await writeFile(outPath, JSON.stringify(transcript, null, 2) + "\n", "utf8");
  process.stdout.write(
    `wa-tester: ${transcript.summary.total_questions - transcript.summary.questions_with_zero_replies}/` +
      `${transcript.summary.total_questions} questions replied — transcript written to ${outPath}\n`,
  );

  if (transcriptHasZeroReplyQuestion(transcript)) {
    process.exitCode = 1;
  }
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]): {
  mode: "pair" | "status" | "send-battery" | null;
  batteryPath?: string;
  outPath?: string;
} {
  if (argv.includes("--pair")) return { mode: "pair" };
  if (argv.includes("--status")) return { mode: "status" };
  const batteryIdx = argv.indexOf("--send-battery");
  if (batteryIdx !== -1) {
    const batteryPath = argv[batteryIdx + 1];
    const outIdx = argv.indexOf("--out");
    const outPath =
      outIdx !== -1
        ? argv[outIdx + 1]
        : `/tmp/wa-tester-transcript-${Date.now()}.json`;
    return { mode: "send-battery", batteryPath, outPath };
  }
  return { mode: null };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.mode === "pair") {
    await runPair();
    return;
  }
  if (args.mode === "status") {
    await runStatus();
    return;
  }
  if (args.mode === "send-battery") {
    if (!args.batteryPath) {
      process.stderr.write(
        "Usage: tsx scripts/wa-tester.ts --send-battery <file.json> [--out <path>]\n",
      );
      process.exitCode = 2;
      return;
    }
    await runSendBattery(args.batteryPath, args.outPath!);
    return;
  }

  process.stderr.write(
    "Usage:\n" +
      "  tsx scripts/wa-tester.ts --pair\n" +
      "  tsx scripts/wa-tester.ts --send-battery <file.json> [--out <path>]\n" +
      "  tsx scripts/wa-tester.ts --status\n" +
      `\nSole allowed recipient: Zantara bot ${BOT_PHONE_E164}. No flag/env/config can change it.\n`,
  );
  process.exitCode = 2;
}

main().catch((err) => {
  const msg = err instanceof Error ? err.message : String(err);
  logger.error({ msg }, "wa-tester failed");
  process.stderr.write(`wa-tester: ${msg}\n`);
  process.exitCode = 1;
});
