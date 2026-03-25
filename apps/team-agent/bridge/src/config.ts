import "dotenv/config";

export const config = {
  whitelistNumber: process.env.WHITELIST_NUMBER || "",
  openclawUrl: process.env.OPENCLAW_URL || "http://localhost:18789",
  sessionDir: process.env.SESSION_DIR || "./sessions",
  healthPort: parseInt(process.env.HEALTH_PORT || "3100"),
  agentName: process.env.AGENT_NAME || "team-agent",
};
