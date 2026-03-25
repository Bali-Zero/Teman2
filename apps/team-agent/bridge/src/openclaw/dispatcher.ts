import axios from "axios";
import { config } from "../config.js";
import { logger } from "../logger.js";

export interface OpenClawMessage {
  message: string;
  agentName: string;
}

export function formatOpenClawMessage(
  text: string,
  agentName: string,
): OpenClawMessage {
  return {
    message: text,
    agentName,
  };
}

export async function dispatchToOpenClaw(text: string): Promise<string> {
  try {
    const payload = formatOpenClawMessage(text, config.agentName);

    const response = await axios.post(
      `${config.openclawUrl}/api/v1/agent/turn`,
      {
        message: payload.message,
        session: `whatsapp-${config.agentName}`,
      },
      {
        timeout: 120_000,
        headers: { "Content-Type": "application/json" },
      },
    );

    return (
      response.data?.reply || response.data?.text || "No response from agent."
    );
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : "Unknown error";
    logger.error(`[OpenClaw] Dispatch failed: ${msg}`);
    return "⚠️ Sistem sedang maintenance. Coba lagi nanti.";
  }
}
