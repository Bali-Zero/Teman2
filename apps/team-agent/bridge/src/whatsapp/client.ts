import makeWASocket, {
  DisconnectReason,
  WASocket,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import pino from "pino";
import { getAuthState } from "./auth-store.js";
import { config } from "../config.js";

const baileysLogger = pino({ level: "warn" });
const log = pino({ level: "info", name: "whatsapp-bridge" });

let sock: WASocket | null = null;

export async function connectWhatsApp(
  onMessage: (jid: string, text: string, messageId: string) => Promise<void>,
): Promise<WASocket> {
  const { state, saveCreds } = await getAuthState();

  sock = makeWASocket({
    auth: state,
    printQRInTerminal: true,
    logger: baileysLogger,
    browser: ["Nuzantara Agent", "Chrome", "120.0.0"],
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect } = update;
    if (connection === "close") {
      const statusCode = (lastDisconnect?.error as Boom)?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      log.info({ shouldReconnect }, "Connection closed");
      if (shouldReconnect) {
        setTimeout(() => connectWhatsApp(onMessage), 3000);
      }
    } else if (connection === "open") {
      log.info({ agent: config.agentName }, "Connected");
    }
  });

  sock.ev.on("messages.upsert", async ({ messages }) => {
    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      const jid = msg.key.remoteJid;
      if (!jid) continue;

      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        "";

      if (text && msg.key.id) {
        await onMessage(jid, text, msg.key.id);
      }
    }
  });

  return sock;
}

export function getSocket(): WASocket | null {
  return sock;
}
