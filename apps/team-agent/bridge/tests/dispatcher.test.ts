import { describe, it, expect } from "vitest";
import { formatOpenClawMessage } from "../src/openclaw/dispatcher.js";

describe("dispatcher", () => {
  it("formats message for OpenClaw agent turn", () => {
    const result = formatOpenClawMessage("stato visa di Marco?", "damar-visa");
    expect(result).toHaveProperty("message");
    expect(result).toHaveProperty("agentName");
    expect(result.agentName).toBe("damar-visa");
    expect(result.message).toContain("stato visa");
  });

  it("handles empty message", () => {
    const result = formatOpenClawMessage("", "damar-visa");
    expect(result.message).toBe("");
    expect(result.agentName).toBe("damar-visa");
  });
});
