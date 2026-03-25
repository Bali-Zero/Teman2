import express from "express";
import { config } from "./config.js";
import { connectWhatsApp, getSocket } from "./whatsapp/client.js";
import { shouldProcessMessage } from "./whatsapp/message-handler.js";
import { dispatchToOpenClaw } from "./openclaw/dispatcher.js";
import { logger } from "./logger.js";

const app = express();
app.get("/health", (_req, res) => {
  const socket = getSocket();
  res.json({
    status: socket ? "connected" : "disconnected",
    agent: config.agentName,
    whitelist: config.whitelistNumber ? "configured" : "missing",
  });
});
app.listen(config.healthPort, () => {
  logger.info(`[Health] Listening on :${config.healthPort}`);
});

async function main() {
  logger.info(`[Agent] Starting ${config.agentName}`);
  logger.info(`[Agent] Whitelist: ${config.whitelistNumber}`);

  await connectWhatsApp(async (jid, text, _messageId) => {
    if (!shouldProcessMessage(jid, config.whitelistNumber)) {
      logger.info(`[WA] Blocked message from ${jid} (not whitelisted)`);
      return;
    }

    logger.info(`[WA] Message from ${jid}: ${text.slice(0, 100)}`);

    const socket = getSocket();
    if (socket) {
      await socket.sendPresenceUpdate("composing", jid);
    }

    const reply = await dispatchToOpenClaw(text);

    if (socket) {
      await socket.sendPresenceUpdate("paused", jid);
      await socket.sendMessage(jid, { text: reply });
      logger.info(`[WA] Replied to ${jid}: ${reply.slice(0, 100)}`);
    }
  });
}

main().catch((err) => logger.error(err, "Fatal error"));
