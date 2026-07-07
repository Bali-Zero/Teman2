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
import { query, getPool } from "./pg.js";
import {
  hydrateAllGroupSubjects,
  attachGroupSubjectListeners,
} from "./group_subject.js";
import {
  PgMessageContextStore,
  extractMessageRecord,
  persistCapturedMessage,
} from "./message_capture.js";
import type {
  MessageContextStore,
  WaMirrorAccount,
} from "./message_capture.js";
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
  /**
   * FIX 4 (2026-05-26): explicit email override, distinct from phone.
   * Manifest loader passes the @balizero.com email when known; the CRM
   * downstream joins on this column. Default "" leaves the row attributable
   * by team_member_phone only (legacy behaviour).
   */
  teamMemberEmail?: string;
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

const DEFAULT_SESSIONS_ROOT = path.join(process.cwd(), "sessions");

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
      email: opts.teamMemberEmail ?? "",
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
    // FIX 5 (2026-05-26): attempt counter promoted to a shared context object
    // so connectOnce / scheduleReconnect / handleConnectionUpdate all read
    // the SAME value. Pre-fix the closure variable was fine, but the API
    // was ambiguous: callers could re-increment in scheduleReconnect by
    // accident. Context object enforces that connectOnce is the sole
    // incrementer.
    const retryCtx = { attempt: 0 };

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
      retryCtx.attempt += 1;
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
        logger: logger.child({ component: "baileys" }),
        // CICATRIX 2026-05-25: markOnlineOnConnect changed false→true.
        // Baileys issue #2491 (Jhey02 empirical) — markOnline=false combined
        // with the messageMutex hold in messages-recv.ts:1153 causes
        // executeInitQueries → fetchProps to hit Timed Out, then ACK never
        // fires and messages.upsert is permanently blocked while connection
        // stays "open" (sintomo: 9/9 bridges connected, 0 upserts in DB).
        markOnlineOnConnect: true,
        // CICATRIX 2026-05-25 (afternoon): re-enable history sync.
        // Baileys 7.0.0-rc13 emits literal DANGER warning:
        // "DISABLING ALL SYNC BY shouldSyncHistoryMsg PREVENTS BAILEYS FROM
        //  ACCESSING INITIAL LID MAPPINGS, LEADING TO INSTABILITY AND
        //  SESSION ERRORS". Without LID→PN mapping the socket cannot
        // resolve incoming direct messages (LID JIDs from non-WA-Business
        // contacts), so messages.upsert NEVER fires for direct chats while
        // groups (SenderKey, stateless) keep working. Empirical 9/9 bridges
        // dead on direct ingest from 10:17 WITA today — this was the cause.
        // Previous false-positives diagnosed: deaf-session #2491, registered:false,
        // version override, all were noise — the smoking gun was Baileys'
        // own DANGER log buried in the noise.
        syncFullHistory: true,
        // shouldSyncHistoryMessage removed — defaults to syncing initial,
        // then the bridge ignores subsequent history events (we don't store
        // history, only live messages.upsert anyway).
        generateHighQualityLinkPreview: false,
        // CICATRIX 2026-05-25: explicit timeouts per Baileys issue #2064/#2491.
        // Default defaultQueryTimeoutMs=undefined → promiseTimeout skips the
        // enforce path (generics.ts:154) → init queries hang forever instead
        // of failing fast and triggering reconnect. 60s gives WA time to ACK
        // on slow networks but still fails-fast vs infinite hang.
        defaultQueryTimeoutMs: 60_000,
        // Default keepAlive ~45s; WA terminates ~50s. 25s window avoids the
        // race where WA cuts the socket between two pings.
        keepAliveIntervalMs: 25_000,
      });

      // FIX 7 (2026-05-26): per-socket disposers Set. Every listener / timer
      // registered against THIS sock instance also goes here. On
      // connection=close we run them in `finally` so a stale socket cannot
      // leak callbacks (memory leak) or zombie intervals (deaf-watchdog
      // ticking against a torn-down sock after N reconnects).
      const disposers = new Set<() => void>();
      const onSock = <K extends Parameters<typeof sock.ev.on>[0]>(
        evt: K,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        fn: (...args: any[]) => void,
      ): void => {
        sock.ev.on(evt, fn);
        disposers.add(() => {
          try {
            sock.ev.off(evt, fn);
          } catch (err) {
            logger.warn(
              { err: (err as Error).message, evt },
              "wa-mirror dispose listener failed",
            );
          }
        });
      };

      onSock("creds.update", saveCreds);
      registerMessageHandler(sock, ctx);

      // CICATRIX 2026-05-25: Baileys issue #2491 "deaf session" mitigation.
      // Symptom: WebSocket alive, keepAlive pings OK, but messages.upsert
      // silently stops firing for incoming DIRECT messages after WA's
      // server-side flow control gives up (delayed ACKs from messageMutex
      // contention). Groups keep working because SenderKey is stateless.
      // Mitigation: track last messages.upsert/messages.update timestamp,
      // force ws.close() if silent for DEAF_SESSION_TIMEOUT_MS while
      // connection.update last reported "open". Triggers reconnect loop.
      const DEAF_SESSION_TIMEOUT_MS = 5 * 60 * 1000; // 5 min — issue #2491 recommended default
      const DEAF_SESSION_CHECK_MS = 60 * 1000; // poll every 60s
      // W77 (2026-06-14): the deaf-session watchdog had no OFF condition for
      // benign silence. At night WITA (Bali Zero hours are daytime) inbound
      // WhatsApp traffic is ~0, so 5min of silence is EXPECTED, not a deaf
      // socket — yet the watchdog forced ~50 empty reconnects/night (all
      // 02:24-03:24 WITA, attempt counter climbing). Issue #2491 is a
      // *daytime* flow-control bug; suppress the forced reconnect during the
      // quiet window so the antibody rests when the organism rests. Override
      // via WA_MIRROR_DEAF_QUIET_HOURS="" to disable, or "1-7" to retune.
      const DEAF_QUIET_WINDOW = process.env.WA_MIRROR_DEAF_QUIET_HOURS ?? "1-7";
      const isDeafQuietHourWITA = (): boolean => {
        if (!DEAF_QUIET_WINDOW) return false;
        const m = DEAF_QUIET_WINDOW.match(/^(\d{1,2})-(\d{1,2})$/);
        if (!m) return false;
        const [from, to] = [Number(m[1]), Number(m[2])];
        // WITA = UTC+8, no DST.
        const hourWITA = (new Date().getUTCHours() + 8) % 24;
        return from <= to
          ? hourWITA >= from && hourWITA < to
          : hourWITA >= from || hourWITA < to;
      };
      let lastUpsertAt = Date.now();
      let connectionOpen = false;
      const bumpUpsertTs = () => {
        lastUpsertAt = Date.now();
      };
      // FIX 6 (2026-05-26): only bump deaf-watchdog on real `notify` events
      // carrying at least one decrypted message. Pre-fix history-sync chunks
      // (type="append", or notify with empty `message`) bumped the timer
      // and masked the deaf-session state we are trying to detect. Also
      // removed messages.update bump — updates (read receipts, reactions)
      // are unrelated to "is the socket still receiving NEW direct chats?".
      onSock("messages.upsert", (event) => {
        if (
          event.type === "notify" &&
          Array.isArray(event.messages) &&
          event.messages.some((m: { message?: unknown }) => m.message != null)
        ) {
          bumpUpsertTs();
        }
      });
      let groupSubjectsHydrated = false;
      onSock("connection.update", (u) => {
        if (u.connection === "open") {
          connectionOpen = true;
          lastUpsertAt = Date.now(); // reset timer on fresh open
          // FIX (2026-06-30): hydrate group names once per session. Groups are
          // dashboard-blind without this — group_subject_snapshot is only ever
          // set from Baileys group metadata, never the message envelope.
          // Fire-and-forget + fully defensive (never throws into the ev loop).
          if (!groupSubjectsHydrated) {
            groupSubjectsHydrated = true;
            void hydrateAllGroupSubjects(sock, getPool(), logger);
            const detach = attachGroupSubjectListeners(sock, getPool(), logger);
            disposers.add(detach);
          }
        } else if (u.connection === "close") {
          connectionOpen = false;
        }
      });
      const deafTimer = setInterval(() => {
        if (!connectionOpen) return;
        const silentMs = Date.now() - lastUpsertAt;
        if (silentMs >= DEAF_SESSION_TIMEOUT_MS) {
          if (isDeafQuietHourWITA()) {
            // Benign nighttime silence — log at debug, do NOT force reconnect.
            logger.debug(
              {
                sessionId: ctx.sessionId,
                silentMs,
                quietWindow: DEAF_QUIET_WINDOW,
              },
              "wa-mirror deaf-session timer hit during quiet hours WITA — suppressing forced reconnect (W77)",
            );
            return;
          }
          logger.warn(
            { sessionId: ctx.sessionId, silentMs },
            "wa-mirror deaf-session detected — forcing reconnect (issue #2491)",
          );
          clearInterval(deafTimer);
          try {
            sock.end(new Error("deaf-session"));
          } catch (err) {
            // socket may already be tearing down
            logger.warn(
              { err: (err as Error).message },
              "wa-mirror sock.end during deaf-session forced reconnect failed",
            );
          }
        }
      }, DEAF_SESSION_CHECK_MS);
      // FIX 7 (2026-05-26): register the timer with disposers so it is also
      // cleared on any close path (not only the explicit deaf-session arm).
      disposers.add(() => clearInterval(deafTimer));

      onSock("connection.update", (update) => {
        // Fire-and-forget — connection.update handlers must not throw.
        void handleConnectionUpdate(update, sock, ctx, {
          // FIX 5 (2026-05-26): pass the live attempt counter, NOT a stale
          // capture from connectOnce's first tick.
          attempt: retryCtx.attempt,
          settleResolve,
          settleReject,
          scheduleReconnect,
          stop: () => {
            // onboard mode: close the socket cleanly after first open.
            try {
              sock.end(undefined);
            } catch (err) {
              logger.warn(
                { err: (err as Error).message },
                "wa-mirror sock.end during onboard stop failed",
              );
            }
          },
        });
      });

      // FIX 7 (2026-05-26): run all disposers on close (transient or
      // terminal). Sock.end() is still owned by handleConnectionUpdate /
      // the deaf-watchdog — we only release listeners + timers here.
      onSock("connection.update", (u) => {
        if (u.connection === "close") {
          try {
            for (const d of disposers) {
              d();
            }
          } finally {
            disposers.clear();
          }
        }
      });
    };

    const scheduleReconnect = (): void => {
      // FIX 5 (2026-05-26): read attempt from retryCtx — connectOnce is the
      // sole writer; scheduleReconnect only reads.
      const delay = Math.min(
        RECONNECT_BASE_MS * 2 ** Math.min(retryCtx.attempt - 1, 5),
        RECONNECT_MAX_MS,
      );
      logger.info(
        { sessionId: ctx.sessionId, attempt: retryCtx.attempt, delayMs: delay },
        "wa-mirror scheduling reconnect",
      );
      setTimeout(() => {
        connectOnce().catch(() => {
          logger.error(
            { sessionId: ctx.sessionId },
            "wa-mirror connectOnce threw — retrying",
          );
          scheduleReconnect();
        });
      }, delay);
    };

    connectOnce().catch(() => {
      logger.error(
        { sessionId: ctx.sessionId },
        "wa-mirror initial connectOnce threw",
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
  deps: ConnectionUpdateDeps,
): Promise<void> {
  const { connection, lastDisconnect, qr } = update;

  if (qr) {
    const qrPath = `/tmp/qr-${phoneDigits(ctx.account.phone)}.png`;
    await QRCode.toFile(qrPath, qr, { width: 400 });
    process.stderr.write(
      `\n[wa-mirror] QR saved to ${qrPath} — open it with: open ${qrPath}\n`,
    );
    qrcodeTerminal.generate(qr, { small: true }, (qrAscii) => {
      process.stdout.write(qrAscii);
      process.stdout.write("\n");
    });
  }

  if (connection === "open") {
    const ownPhone =
      normalizePhone(jidToPhone(sock.user?.id)) || ctx.account.phone;
    try {
      await query(
        `UPDATE whatsapp_team_sessions
         SET phone_normalized = COALESCE(NULLIF($1, ''), phone_normalized),
               team_member_phone = COALESCE(NULLIF($2, ''), team_member_phone)
         WHERE id = $3`,
        [phoneDigits(ownPhone), ownPhone, ctx.sessionId],
      );
      await markConnected(ctx.sessionId);
    } catch (err) {
      logger.warn(
        { sessionId: ctx.sessionId, err: (err as Error).message },
        "wa-mirror markConnected failed (non-fatal)",
      );
    }
    logger.info({ sessionId: ctx.sessionId }, "wa-mirror session connected");
    await sendTelegramAlert(`wa-mirror connected: ${ctx.account.name}`, logger);

    // CICATRIX 2026-05-25: refresh pre-keys on every connect.
    // Pre-fix: bridge initial pairing seeded ~30 prekeys, all consumed over time.
    // Peers then tried to negotiate using preKey IDs the bridge had discarded →
    // PreKeyError: Invalid PreKey ID on every direct-LID message (sintomo:
    // dashboard direct chats frozen 4+ days while groups kept flowing because
    // group cipher = SenderKey, no per-message prekey rotation needed).
    // Baileys auto-uploads on initial pairing only; refresh on each reconnect.
    try {
      const refresher = sock as unknown as {
        uploadPreKeysToServerIfRequired?: () => Promise<void>;
        uploadPreKeys?: () => Promise<void>;
      };
      if (typeof refresher.uploadPreKeysToServerIfRequired === "function") {
        await refresher.uploadPreKeysToServerIfRequired();
      } else if (typeof refresher.uploadPreKeys === "function") {
        await refresher.uploadPreKeys();
      }
      logger.info(
        { sessionId: ctx.sessionId },
        "wa-mirror prekey refresh attempted",
      );
    } catch (err) {
      logger.warn(
        { sessionId: ctx.sessionId, err: (err as Error).message },
        "wa-mirror prekey refresh failed (non-fatal)",
      );
    }

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
        terminal ? "revoked" : "disconnected",
      );
    } catch (err) {
      // The pre-2026-05-14 UNIQUE(team_member_email, status) constraint made
      // this throw on a duplicate `disconnected` row. Migration 175 replaces
      // it with a partial unique index on active states only, but we still
      // swallow errors here so a bookkeeping failure never kills the loop.
      logger.warn(
        { sessionId: ctx.sessionId, err: (err as Error).message },
        "wa-mirror markDisconnected failed (non-fatal)",
      );
    }

    logger.warn(
      {
        sessionId: ctx.sessionId,
        code,
        reason,
        terminal,
        attempt: deps.attempt,
      },
      "wa-mirror session closed",
    );
    await sendTelegramAlert(
      `wa-mirror disconnected: ${ctx.account.name}; reason=${reason}; reconnect_attempt=${deps.attempt}`,
      logger,
    );

    if (terminal) {
      // Device removed from the phone's Linked Devices — needs a fresh QR.
      // Reject with a TYPED error so the orchestrator (runAccountForever) can
      // tell a terminal logout apart from a transient crash and STOP retrying:
      // a logged-out session never recovers by reconnecting — only a QR does.
      deps.settleReject(
        new SessionLoggedOutError(`wa-mirror: session logged out: ${reason}`),
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

  // FIX 3 (2026-05-26): Baileys signalRepository.lidMapping.getPNForLID
  // resolver. Translates a raw LID (15-digit privacy-shielded identifier)
  // into the underlying phone via the per-session signal store, then
  // write-back caches the mapping to `wa_lid_phone_map` so downstream
  // consumers (CRM identity_resolver, analytics) can JOIN without
  // re-querying Baileys. Returns null on any failure path so callers can
  // fall back to the existing async-resolver behaviour.
  const resolveLidToPhone = async (lid: string): Promise<string | null> => {
    try {
      const sockAny = sock as unknown as {
        signalRepository?: {
          lidMapping?: {
            getPNForLID?: (lid: string) => Promise<string | null>;
          };
        };
      };
      const result = await sockAny.signalRepository?.lidMapping?.getPNForLID?.(
        lid.includes("@") ? lid : `${lid}@lid`,
      );
      if (!result) return null;
      const phoneDigits =
        result.split("@")[0]?.split(":")[0]?.replace(/\D/g, "") ?? "";
      const e164 = normalizePhone(`+${phoneDigits}`);
      if (!e164) return null;
      // Write-back to wa_lid_phone_map (fire-and-forget). Schema lives in
      // migration 201: lid PK, phone_e164, client_id (filled later by
      // identity_resolver), confidence, source enum.
      void query(
        `INSERT INTO wa_lid_phone_map (lid, phone_e164, source, confidence)
         VALUES ($1, $2, 'baileys_metadata', 0.95)
         ON CONFLICT (lid) DO UPDATE SET
           phone_e164 = EXCLUDED.phone_e164,
           last_confirmed_at = now()`,
        [lid, e164],
      ).catch((err) => {
        logger.warn(
          { err: (err as Error).message, lid },
          "wa-mirror wa_lid_phone_map upsert failed (non-fatal)",
        );
      });
      return e164;
    } catch (err) {
      logger.warn(
        { err: (err as Error).message, lid },
        "wa-mirror lid resolve failed (non-fatal)",
      );
      return null;
    }
  };

  sock.ev.on("messages.upsert", async (event) => {
    if (event.type !== "notify" && event.type !== "append") return;
    for (const m of event.messages) {
      try {
        const record = extractMessageRecord(m, ctx.account);
        if (record === null) {
          await incrementMessagesFiltered(ctx.sessionId);
          continue;
        }

        // FIX 9 (2026-05-26): only touch the contact table on INBOUND
        // direct messages. Pre-fix: outbound also fired touchWhatsAppContact
        // → contact name overwritten with the team member's own pushName
        // (e.g. "Adit" stomped the real counterpart name "Mr. Wijaya").
        if (
          record.chatType === "direct" &&
          record.counterpartPhone &&
          record.direction === "inbound"
        ) {
          try {
            await touchWhatsAppContact({
              phone: record.counterpartPhone,
              name: m.pushName ?? `wa:${record.counterpartPhone}`,
            });
          } catch (err) {
            logger.warn(
              { sessionId: ctx.sessionId, err: (err as Error).message },
              "wa-mirror contact touch failed (message capture continues)",
            );
          }
        }

        const persisted = await persistCapturedMessage(record, {
          store: ctx.store,
          resolveClientId: findClientByPhone,
          resolvePracticeId: findOpenPracticeForClient,
          // FIX 3 (2026-05-26): inline LID→phone resolver, see helper above.
          resolveLidToPhone,
        });
        consecutiveDbErrors = 0;

        await incrementMessagesLogged(ctx.sessionId);

        await emitMessageReceived({
          message_context_id: persisted.id,
          bridge_session_id: ctx.sessionId,
          // FIX 4 (2026-05-26): emit the real email (or "" when unknown).
          // Pre-fix forced phone here, which broke CRM joins downstream.
          team_member_email: ctx.account.email ?? "",
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
        consecutiveDbErrors += 1;
        logger.warn(
          {
            sessionId: ctx.sessionId,
            consecutiveDbErrors,
            err: (err as Error).message,
          },
          "wa-mirror message persist failed",
        );
        if (consecutiveDbErrors > 5) {
          await sendTelegramAlert(
            `wa-mirror DB write errors >5: ${ctx.account.name}; consecutive=${consecutiveDbErrors}`,
            logger,
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

/**
 * Thrown (via settleReject) when a session closes with a terminal `loggedOut`
 * (HTTP 401): the linked device was removed/invalidated on the WhatsApp side.
 * Reconnecting cannot fix this — only a fresh QR re-link can. The orchestrator
 * matches on `instanceof` to stop the per-account retry loop instead of
 * hammering WhatsApp every 60s with dead credentials (which also spams Telegram
 * and raises the anti-automation flag risk).
 */
export class SessionLoggedOutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SessionLoggedOutError";
    // Restore the prototype chain so `instanceof SessionLoggedOutError` holds
    // even when TS downlevels `extends Error` — the orchestrator relies on it.
    Object.setPrototypeOf(this, SessionLoggedOutError.prototype);
  }
}
