import { useMultiFileAuthState } from "@whiskeysockets/baileys";
import { config } from "../config.js";
import { mkdirSync } from "fs";

export async function getAuthState() {
  mkdirSync(config.sessionDir, { recursive: true });
  return useMultiFileAuthState(config.sessionDir);
}
