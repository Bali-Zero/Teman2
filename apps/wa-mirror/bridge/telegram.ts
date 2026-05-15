import type pino from "pino";

export async function sendTelegramAlert(
  text: string,
  logger?: pino.Logger
): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_OWNER_CHAT_ID;
  if (!token || !chatId) return;

  try {
    const response = await fetch(
      `https://api.telegram.org/bot${token}/sendMessage`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          disable_web_page_preview: true,
        }),
      }
    );
    if (!response.ok) {
      logger?.warn(
        { status: response.status },
        "wa-mirror Telegram alert failed"
      );
    }
  } catch {
    logger?.warn("wa-mirror Telegram alert threw");
  }
}
