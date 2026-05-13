// session.ts — one Baileys connection per team member.
//
// We wrap @whiskeysockets/baileys with the privacy filter, the
// whatsapp_team_sessions lifecycle, and the EventBus emit. The exported
// `startSession` is invoked once per team member during daemon start.
//
// Architecture notes:
// - Auth state is persisted to disk via `useMultiFileAuthState` (Baileys
//   convention). Path: ~/.wa-mirror/sessions/<email>/.
// - The QR code is printed to stderr ONLY during the very first connect
//   (when no auth state exists yet). Subsequent restarts pick up the saved
//   credentials silently.
// - Read-only by design (v1): we never call sock.sendMessage. The bridge
//   subscribes to incoming `messages.upsert` events and mirrors them.
// - Outbound messages from the team member's phone ALSO arrive via
//   `messages.upsert` with `message.key.fromMe = true`. We mirror those as
//   direction="outbound" so the CRM sees both sides of the conversation.

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

import { emitMessageReceived } from "./events.js";
import { jidToPhone, shouldMirror } from "./filters.js";
import {
  incrementMessagesFiltered,
  incrementMessagesLogged,
  markConnected,
  markDisconnected,
  openSession,
  touch,
} from "./heartbeat.js";
import { query } from "./pg.js";

const logger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: undefined,
});

export type StartSessionOptions = {
  teamMemberEmail: string;
  /** Bali Zero-side number once the team member scans the QR. Falls back to
   *  the JID Baileys reports on `open`. Used only as fallback when the
   *  operator did not pre-populate the row. */
  expectedPhone?: string;
  sessionLabel?: string;
  sessionsRoot?: string;
};

const DEFAULT_SESSIONS_ROOT = path.join(
  process.env.HOME ?? "/Users/nuzantara",
  ".wa-mirror",
  "sessions"
);

const DEFAULT_LABEL = "Bali Zero WA-Mirror";

/**
 * Boot a Baileys session for one team member. Resolves after the first
 * `open` event (session is connected) OR after a permanent failure that
 * cannot be recovered without a fresh QR scan.
 *
 * Returns the session row id from whatsapp_team_sessions.
 */
export async function startSession(opts: StartSessionOptions): Promise<number> {
  const sessionsRoot = opts.sessionsRoot ?? DEFAULT_SESSIONS_ROOT;
  const authDir = path.join(sessionsRoot, opts.teamMemberEmail.toLowerCase());
  await mkdir(authDir, { recursive: true });

  const sessionRow = await openSession({
    teamMemberEmail: opts.teamMemberEmail,
    phoneNormalized: (opts.expectedPhone ?? "").replace(/[^\d]/g, ""),
    sessionLabel: opts.sessionLabel ?? DEFAULT_LABEL,
    authStatePath: authDir,
  });
  logger.info(
    { sessionId: sessionRow.id, email: opts.teamMemberEmail },
    "wa-mirror session row opened"
  );

  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const { version } = await fetchLatestBaileysVersion();

  const sock: WASocket = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    printQRInTerminal: false,
    browser: [opts.sessionLabel ?? DEFAULT_LABEL, "Chrome", "1.0.0"],
    logger: logger.child({ baileys: opts.teamMemberEmail }),
    markOnlineOnConnect: false,
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => false,
    generateHighQualityLinkPreview: false,
  });

  sock.ev.on("creds.update", saveCreds);

  let resolved = false;
  return new Promise<number>((resolve, reject) => {
    sock.ev.on("connection.update", async (update) => {
      const { connection, lastDisconnect, qr } = update;
      if (qr) {
        process.stderr.write(
          `\n[wa-mirror] Team member ${opts.teamMemberEmail}: scan this QR with WhatsApp → Settings → Linked Devices\n`
        );
        qrcodeTerminal.generate(qr, { small: true }, (qrAscii) => {
          process.stderr.write(qrAscii);
          process.stderr.write("\n");
        });
      }
      if (connection === "open") {
        const ownPhone = jidToPhone(sock.user?.id);
        await query(
          `UPDATE whatsapp_team_sessions
             SET phone_normalized = COALESCE(NULLIF($1, ''), phone_normalized)
           WHERE id = $2`,
          [ownPhone, sessionRow.id]
        );
        await markConnected(sessionRow.id);
        logger.info(
          { sessionId: sessionRow.id, ownPhone },
          "wa-mirror session connected"
        );
        if (!resolved) {
          resolved = true;
          resolve(sessionRow.id);
        }
      }
      if (connection === "close") {
        const code =
          (lastDisconnect?.error as Boom | undefined)?.output?.statusCode ?? 0;
        const reason = mapCloseReason(code);
        const final = code === DisconnectReason.loggedOut;
        if (final) {
          await markDisconnected(sessionRow.id, reason, "revoked");
        } else {
          await markDisconnected(sessionRow.id, reason, "disconnected");
        }
        logger.warn(
          { sessionId: sessionRow.id, code, reason, final },
          "wa-mirror session closed"
        );
        if (!resolved && final) {
          resolved = true;
          reject(
            new Error(`wa-mirror: session for ${opts.teamMemberEmail} revoked: ${reason}`)
          );
        }
      }
    });

    sock.ev.on("messages.upsert", async (event) => {
      if (event.type !== "notify" && event.type !== "append") return;
      for (const m of event.messages) {
        if (!m.message) continue;
        try {
          const direction = m.key.fromMe ? "outbound" : "inbound";
          const counterpartJid = m.key.remoteJid ?? "";
          const teamMemberPhone = jidToPhone(sock.user?.id);

          const decision = await shouldMirror({
            counterpartJid,
            teamMemberPhone,
          });
          if (!decision.mirror) {
            await incrementMessagesFiltered(sessionRow.id);
            continue;
          }

          const text = extractText(m.message);
          if (!text && !hasMedia(m.message)) {
            // Nothing useful (e.g. reaction-only or protocol message).
            await incrementMessagesFiltered(sessionRow.id);
            continue;
          }

          // Ensure a whatsapp_contacts row exists for the counterpart so the
          // FK on whatsapp_message_context is satisfied. UPSERT keyed on
          // unique `phone`. We don't have a display name from Baileys here
          // reliably, so we stamp the normalised phone.
          const counterpartName =
            m.pushName ?? `wa:${decision.counterpartNormalized}`;
          const contactRes = await query<{ id: number }>(
            `INSERT INTO whatsapp_contacts (phone, phone_normalized, name, contact_type, imported_from)
             VALUES ($1, $1, $2, 'client', 'wa_mirror')
             ON CONFLICT (phone) DO UPDATE
               SET last_message_at = NOW(),
                   total_messages = whatsapp_contacts.total_messages + 1,
                   updated_at = NOW()
             RETURNING id`,
            [decision.counterpartNormalized, counterpartName.slice(0, 255)]
          );
          const contactId = contactRes.rows[0].id;

          const messageDate = m.messageTimestamp
            ? new Date(Number(m.messageTimestamp) * 1000)
            : new Date();

          const insertRes = await query<{ id: number }>(
            `INSERT INTO whatsapp_message_context
               (contact_id, direction, message_text, message_date,
                team_member_email, source, bridge_session_id)
             VALUES ($1, $2, $3, $4, $5, 'wa_mirror', $6)
             RETURNING id`,
            [
              contactId,
              direction,
              text ?? "[media]",
              messageDate.toISOString(),
              opts.teamMemberEmail,
              sessionRow.id,
            ]
          );
          const messageContextId = insertRes.rows[0].id;

          await incrementMessagesLogged(sessionRow.id);

          await emitMessageReceived({
            message_context_id: messageContextId,
            bridge_session_id: sessionRow.id,
            team_member_email: opts.teamMemberEmail,
            client_id: decision.clientId!,
            direction,
            message_date: messageDate.toISOString(),
            preview: (text ?? "[media]").slice(0, 120),
          });
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          logger.warn(
            { sessionId: sessionRow.id, msg },
            "wa-mirror message persist failed"
          );
        }
      }
      await touch(sessionRow.id);
    });
  });
}

function mapCloseReason(code: number): string {
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

function extractText(message: Record<string, unknown>): string | null {
  const m = message as {
    conversation?: string;
    extendedTextMessage?: { text?: string };
    imageMessage?: { caption?: string };
    videoMessage?: { caption?: string };
    documentMessage?: { caption?: string; fileName?: string };
  };
  if (typeof m.conversation === "string" && m.conversation.length > 0) {
    return m.conversation;
  }
  if (m.extendedTextMessage?.text) return m.extendedTextMessage.text;
  if (m.imageMessage?.caption) return m.imageMessage.caption;
  if (m.videoMessage?.caption) return m.videoMessage.caption;
  if (m.documentMessage?.caption) return m.documentMessage.caption;
  if (m.documentMessage?.fileName) return `[doc] ${m.documentMessage.fileName}`;
  return null;
}

function hasMedia(message: Record<string, unknown>): boolean {
  const keys = Object.keys(message);
  return keys.some((k) =>
    ["imageMessage", "videoMessage", "documentMessage", "audioMessage"].includes(k)
  );
}
