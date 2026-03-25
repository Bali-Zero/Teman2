import { describe, it, expect } from "vitest";
import { shouldProcessMessage } from "../src/whatsapp/message-handler.js";
import { formatOpenClawMessage } from "../src/openclaw/dispatcher.js";

describe("full flow integration", () => {
  const DAMAR_NUMBER = "6281234567890";
  const DAMAR_JID = `${DAMAR_NUMBER}@s.whatsapp.net`;

  it("processes whitelisted message through full pipeline", () => {
    const allowed = shouldProcessMessage(DAMAR_JID, DAMAR_NUMBER);
    expect(allowed).toBe(true);

    const payload = formatOpenClawMessage(
      "stato visa di Marco Bianchi?",
      "damar-visa",
    );
    expect(payload.agentName).toBe("damar-visa");
    expect(payload.message).toContain("stato visa");
  });

  it("blocks message from unknown number", () => {
    const allowed = shouldProcessMessage(
      "6289999999@s.whatsapp.net",
      DAMAR_NUMBER,
    );
    expect(allowed).toBe(false);
  });

  it("blocks group message even from whitelisted number", () => {
    const allowed = shouldProcessMessage("123456@g.us", DAMAR_NUMBER);
    expect(allowed).toBe(false);
  });

  it("handles multiple sequential messages", () => {
    const messages = [
      "stato visa di Marco?",
      "check compliance per PT ABC",
      "invia email reminder scadenza",
    ];
    for (const msg of messages) {
      const allowed = shouldProcessMessage(DAMAR_JID, DAMAR_NUMBER);
      expect(allowed).toBe(true);
      const payload = formatOpenClawMessage(msg, "damar-visa");
      expect(payload.message).toBe(msg);
    }
  });
});
