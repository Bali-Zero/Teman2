import pino from "pino";

export const logger = pino({
  name: "whatsapp-bridge",
  level: process.env.LOG_LEVEL || "info",
});
