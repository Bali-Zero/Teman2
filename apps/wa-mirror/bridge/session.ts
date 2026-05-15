// session.ts — one Baileys connection per team member.
//
// We wrap @whiskeysockets/baileys with the privacy filter, the
// whatsapp_team_sessions lifecycle, and the EventBus emit.
//
// Architecture notes:
// - Auth state is persisted to disk via `useMultiFileAuthState` (Baileys
//   convention). Path: apps/wa-mirror/sessions/<e164_phone>/ by default.
// - The QR code is printed to stderr ONLY during the very first connect
//   (when no auth state exists yet). Subsequent restarts pick up the saved
//   credentials silently.
// - Read-only by design (v1): we never call sock.sendMessage. The bridge
//   subscribes to incoming `messages.upsert` events and mirrors them.
// - Outbound messages from the team member's phone ALSO arrive via
//   `messages.upsert` with `message.key.fromMe = true`. We mirror those as
//   direction="outbound" so the CRM sees both sides of the conversation.
//
// Reconnect contract (the reason this file was rewritten 2026-05-14):
// Baileys closes the socket on MANY non-terminal conditions — most notably
// `restartRequired` (code 515) which fires immediately after a fresh QR
// pairing, and `connectionLost` / `connectionClosed` / `timedOut` on any
// transient network blip. The ONLY terminal condition is `loggedOut`
// (the team member removed the linked device). For every non-terminal
// close we MUST recreate the socket — Baileys does not auto-reconnect.
// `connectWithRetry` owns that loop with exponential backoff.

import { Boom } from "@hapi/boom";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import type { WASocket } from "@whiskeysockets/baileys";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import pino from "pino";
import qrcodeTerminal from "qrcode-terminal";
import QRCode from "qrcode";

import { emitMessageReceived } from "./events.js";
import { jidToPhone } from "./filters.js";
import {
  findClientByPhone,
  findOpenPracticeForClient,
  touchWhatsAppContact,
} from "./pg.js";
import {
  incrementMessagesFiltered,
  incrementMessagesLogged,
  markConnected,
  markDisconnected,
  openSession,
  touch,
} from "./heartbeat.js";
import { query } from "./pg.js";
import {
  PgMessageContextStore,
  extractMessageRecord,
  persistCapturedMessage,
} from "./message_capture.js";
import type { MessageContextStore, WaMirrorAccount } from "./message_capture.js";
import { queueMediaDownload } from "./media.js";
import { normalizePhone, phoneDigits } from "./phone.js";
import { sendTelegramAlert } from "./telegram.js";

const logger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: undefined,
});

export type StartSessionOptions = {
  accountPhone: string;
  teamMemberName?: string;
  /** Bali Zero-side number once the team member scans the QR. Falls back to
   *  the JID Baileys reports on `open`. Used only as fallback when the
   *  operator did not pre-populate the row. */
  expectedPhone?: string;
  sessionLabel?: string;
  sessionsRoot?: string;
  /**
   * onboard.ts sets this `true`: resolve the returned promise as soon as the
   * session reaches `connected` once, then stop (single-shot QR helper). The
   * reconnect loop still handles `restartRequired` (code 515) which always
   * fires right after pairing — so even onboarding survives that one bounce.
   *
   * The daemon (index.ts) leaves this `false`/undefined: the promise stays
   * pending forever and the reconnect loop runs for the life of the process.
   */
  resolveOnFirstOpen?: boolean;
};

const DEFAULT_SESSIONS_ROOT = path.join(
  process.cwd(),
  "sessions"
);

const DEFAULT_LABEL = "Bali Zero WA-Mirror";

// Exponential backoff bounds for the reconnect loop.
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 60_000;

/**
 * Boot a Baileys session for one team member and keep it connected.
 *
 * Behaviour depends on `opts.resolveOnFirstOpen`:
 * - `true`  (onboard.ts): the returned promise resolves with the session-row
 *   id the first time the connection opens. The socket is then closed and the
 *   loop stops — the persisted auth state is what matters, the daemon will
 *   pick it up later.
 * - falsy   (daemon): the promise NEVER resolves under normal operation. The
 *   reconnect loop runs forever; it only rejects if the device is logged out
 *   (terminal — needs a fresh QR scan).
 *
 * Returns / rejects via the session-row id from whatsapp_team_sessions.
 */
export async function startSession(opts: StartSessionOptions): Promise<number> {
  const sessionsRoot = opts.sessionsRoot ?? DEFAULT_SESSIONS_ROOT;
  const accountPhone = normalizePhone(opts.accountPhone);
  if (!accountPhone) {
    throw new Error(`wa-mirror: invalid account phone ${opts.accountPhone}`);
  }
  const teamMemberName = opts.teamMemberName ?? accountPhone;
  const authDir = path.join(sessionsRoot, accountPhone);
  await mkdir(authDir, { recursive: true });

  const sessionLabel = opts.sessionLabel ?? DEFAULT_LABEL;

  const sessionRow = await openSession({
    teamMemberKey: accountPhone,
    teamMemberPhone: accountPhone,
    teamMemberName,
    phoneNormalized: phoneDigits(opts.expectedPhone ?? accountPhone),
    sessionLabel,
    authStatePath: authDir,
  });
  logger.info({ sessionId: sessionRow.id }, "wa-mirror session row opened");

  return connectWithRetry({
    sessionId: sessionRow.id,
    account: {
      phone: accountPhone,
      name: teamMemberName,
    },
    authDir,
    sessionLabel,
    resolveOnFirstOpen: opts.resolveOnFirstOpen ?? false,
    store: new PgMessageContextStore(),
  });
}

type ConnectContext = {
  sessionId: number;
  account: WaMirrorAccount;
  authDir: string;
  sessionLabel: string;
  resolveOnFirstOpen: boolean;
  store: MessageContextStore;
};

/**
 * The reconnect loop. Recreates the Baileys socket on every non-terminal
 * close with exponential backoff. Resolves/rejects the outer promise exactly
 * once, then keeps looping in the background (daemon mode) or stops
 * (onboard mode).
 */
function connectWithRetry(ctx: ConnectContext): Promise<number> {
  return new Promise<number>((resolve, reject) => {
    let settled = false;
    let attempt = 0;

    const settleResolve = (): void => {
      if (settled) return;
      settled = true;
      resolve(ctx.sessionId);
    };
    const settleReject = (err: Error): void => {
      if (settled) return;
      settled = true;
      reject(err);
    };

    const connectOnce = async (): Promise<void> => {
      attempt += 1;
      const { state, saveCreds } = await useMultiFileAuthState(ctx.authDir);
      const { version } = await fetchLatestBaileysVersion();

      const sock: WASocket = makeWASocket({
        version,
        auth: {
          creds: state.creds,
          keys: makeCacheableSignalKeyStore(state.keys, logger),
        },
        printQRInTerminal: false,
        browser: [ctx.sessionLabel, "Chrome", "1.0.0"],
        logger: logger.child({ baileys: ctx.account.name }),
        markOnlineOnConnect: false,
        syncFullHistory: false,
        shouldSyncHistoryMessage: () => false,
        generateHighQualityLinkPreview: false,
      });

      sock.ev.on("creds.update", saveCreds);
      registerMessageHandler(sock, ctx);

      sock.ev.on("connection.update", (update) => {
        // Fire-and-forget — connection.update handlers must not throw.
        void handleConnectionUpdate(update, sock, ctx, {
          attempt,
          settleResolve,
          settleReject,
          scheduleReconnect,
          stop: () => {
            // onboard mode: close the socket cleanly after first open.
            try {
              sock.end(undefined);
            } catch {
              // ignore — socket may already be torn down
            }
          },
        });
      });
    };

    const scheduleReconnect = (): void => {
      const delay = Math.min(
        RECONNECT_BASE_MS * 2 ** Math.min(attempt - 1, 5),
        RECONNECT_MAX_MS
      );
      logger.info(
        { sessionId: ctx.sessionId, attempt, delayMs: delay },
        "wa-mirror scheduling reconnect"
      );
      setTimeout(() => {
        connectOnce().catch((err) => {
          const msg = err instanceof Error ? err.message : String(err);
          logger.error(
            { sessionId: ctx.sessionId, msg },
            "wa-mirror connectOnce threw — retrying"
          );
          scheduleReconnect();
        });
      }, delay);
    };

    connectOnce().catch((err) => {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error(
        { sessionId: ctx.sessionId, msg },
        "wa-mirror initial connectOnce threw"
      );
      scheduleReconnect();
    });
  });
}

type ConnectionUpdateDeps = {
  attempt: number;
  settleResolve: () => void;
  settleReject: (err: Error) => void;
  scheduleReconnect: () => void;
  stop: () => void;
};

type ConnectionUpdate = {
  connection?: string;
  lastDisconnect?: { error?: unknown } | null;
  qr?: string;
};

async function handleConnectionUpdate(
  update: ConnectionUpdate,
  sock: WASocket,
  ctx: ConnectContext,
  deps: ConnectionUpdateDeps
): Promise<void> {
  const { connection, lastDisconnect, qr } = update;

  if (qr) {
    const qrPath = `/tmp/qr-${phoneDigits(ctx.account.phone)}.png`;
    await QRCode.toFile(qrPath, qr, { width: 400 });
    process.stderr.write(
      `\n[wa-mirror] QR saved to ${qrPath} — open it with: open ${qrPath}\n`
    );
    qrcodeTerminal.generate(qr, { small: true }, (qrAscii) => {
      process.stdout.write(qrAscii);
      process.stdout.write("\n");
    });
  }

  if (connection === "open") {
    const ownPhone = normalizePhone(jidToPhone(sock.user?.id)) || ctx.account.phone;
    try {
      await query(
        `UPDATE whatsapp_team_sessions
         SET phone_normalized = COALESCE(NULLIF($1, ''), phone_normalized),
               team_member_phone = COALESCE(NULLIF($2, ''), team_member_phone)
         WHERE id = $3`,
        [phoneDigits(ownPhone), ownPhone, ctx.sessionId]
      );
      await markConnected(ctx.sessionId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.warn(
        { sessionId: ctx.sessionId, msg },
        "wa-mirror markConnected failed (non-fatal)"
      );
    }
    logger.info(
      { sessionId: ctx.sessionId, teamMemberName: ctx.account.name },
      "wa-mirror session connected"
    );
    await sendTelegramAlert(
      `wa-mirror connected: ${ctx.account.name}`,
      logger
    );
    if (ctx.resolveOnFirstOpen) {
      // onboard.ts: auth state is persisted, our job is done.
      deps.settleResolve();
      deps.stop();
    }
    return;
  }

  if (connection === "close") {
    const code =
      (lastDisconnect as { error?: Boom } | undefined)?.error?.output
        ?.statusCode ?? 0;
    const reason = mapCloseReason(code);
    const terminal = isTerminalCloseCode(code);

    try {
      await markDisconnected(
        ctx.sessionId,
        reason,
        terminal ? "revoked" : "disconnected"
      );
    } catch (err) {
      // The pre-2026-05-14 UNIQUE(team_member_email, status) constraint made
      // this throw on a duplicate `disconnected` row. Migration 175 replaces
      // it with a partial unique index on active states only, but we still
      // swallow errors here so a bookkeeping failure never kills the loop.
      const msg = err instanceof Error ? err.message : String(err);
      logger.warn(
        { sessionId: ctx.sessionId, msg },
        "wa-mirror markDisconnected failed (non-fatal)"
      );
    }

    logger.warn(
      {
        sessionId: ctx.sessionId,
        accountName: ctx.account.name,
        code,
        reason,
        terminal,
        attempt: deps.attempt,
      },
      "wa-mirror session closed"
    );
    await sendTelegramAlert(
      `wa-mirror disconnected: ${ctx.account.name}; reason=${reason}; reconnect_attempt=${deps.attempt}`,
      logger
    );

    if (terminal) {
      // Device removed from the phone's Linked Devices — needs a fresh QR.
      deps.settleReject(
        new Error(
          `wa-mirror: session for ${ctx.account.name} logged out: ${reason}`
        )
      );
      return;
    }

    if (ctx.resolveOnFirstOpen && deps.attempt === 1 && code === 0) {
      // onboard mode, very first connect, closed with no status code before
      // ever opening — almost always means the QR window expired unscanned.
      // Keep retrying so a slow scanner still lands; the onboard.ts timeout
      // is the outer bound.
      deps.scheduleReconnect();
      return;
    }

    // Non-terminal: restartRequired (515), connectionLost (408),
    // connectionClosed, timedOut, badSession, etc. Recreate the socket.
    deps.scheduleReconnect();
  }
}

function registerMessageHandler(sock: WASocket, ctx: ConnectContext): void {
  let consecutiveDbErrors = 0;

  sock.ev.on("messages.upsert", async (event) => {
    if (event.type !== "notify" && event.type !== "append") return;
    for (const m of event.messages) {
      try {
        const record = extractMessageRecord(m, ctx.account);
        if (record === null) {
          await incrementMessagesFiltered(ctx.sessionId);
          continue;
        }

        try {
          await touchWhatsAppContact({
            phone: record.counterpartPhone,
            name: m.pushName ?? `wa:${record.counterpartPhone}`,
          });
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          logger.warn(
            { sessionId: ctx.sessionId, msg },
            "wa-mirror contact touch failed (message capture continues)"
          );
        }

        const persisted = await persistCapturedMessage(record, {
          store: ctx.store,
          resolveClientId: findClientByPhone,
          resolvePracticeId: findOpenPracticeForClient,
        });
        consecutiveDbErrors = 0;

        await incrementMessagesLogged(ctx.sessionId);

        await emitMessageReceived({
          message_context_id: persisted.id,
          bridge_session_id: ctx.sessionId,
          team_member_email: ctx.account.phone,
          client_id: persisted.row.clientId,
          direction: record.direction,
          message_date: record.timestamp.toISOString(),
          preview: (record.body || `[${record.mediaType}]`).slice(0, 120),
        });

        queueMediaDownload({
          sock,
          rawMessage: m,
          messageContextId: persisted.id,
          record,
          store: ctx.store,
          logger,
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        consecutiveDbErrors += 1;
        logger.warn(
          {
            sessionId: ctx.sessionId,
            msg,
            consecutiveDbErrors,
          },
          "wa-mirror message persist failed"
        );
        if (consecutiveDbErrors > 5) {
          await sendTelegramAlert(
            `wa-mirror DB write errors >5: ${ctx.account.name}; latest=${msg}`,
            logger
          );
        }
      }
    }
    await touch(ctx.sessionId);
  });
}

export function mapCloseReason(code: number): string {
  switch (code) {
    case DisconnectReason.badSession:
      return "bad_session";
    case DisconnectReason.connectionClosed:
      return "connection_closed";
    case DisconnectReason.connectionLost:
      return "connection_lost";
    case DisconnectReason.connectionReplaced:
      return "connection_replaced";
    case DisconnectReason.loggedOut:
      return "logged_out";
    case DisconnectReason.restartRequired:
      return "restart_required";
    case DisconnectReason.timedOut:
      return "timed_out";
    default:
      return `code_${code}`;
  }
}

/**
 * Is this close code TERMINAL — i.e. the session cannot recover without a
 * fresh QR scan — or merely a transient bounce the reconnect loop should
 * absorb?
 *
 * The ONLY terminal condition is `loggedOut` (HTTP 401): the team member
 * removed the linked device from their phone, or WhatsApp invalidated it.
 * Everything else — restartRequired (515, fires right after pairing),
 * connectionLost (408), connectionClosed (428), timedOut (408),
 * connectionReplaced (440, another device took over), badSession (500) —
 * is recoverable by recreating the socket. `connectionReplaced` is a grey
 * area but we treat it as non-terminal: if it keeps happening the backoff
 * caps at 60s and the operator sees the log churn.
 *
 * Exported as a pure function so the reconnect classification is unit-tested
 * without standing up a real Baileys socket.
 */
export function isTerminalCloseCode(code: number): boolean {
  return code === DisconnectReason.loggedOut;
}
