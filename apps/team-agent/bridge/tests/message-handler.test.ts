import { describe, it, expect } from "vitest";
import {
  shouldProcessMessage,
  normalizeJid,
} from "../src/whatsapp/message-handler.js";

describe("message-handler", () => {
  describe("normalizeJid", () => {
    it("extracts number from WhatsApp JID", () => {
      expect(normalizeJid("6281234567890@s.whatsapp.net")).toBe(
        "6281234567890",
      );
    });
    it("handles group JID", () => {
      expect(normalizeJid("123456789@g.us")).toBe("123456789");
    });
  });

  describe("shouldProcessMessage", () => {
    it("allows whitelisted number", () => {
      expect(
        shouldProcessMessage("6281234567890@s.whatsapp.net", "6281234567890"),
      ).toBe(true);
    });
    it("blocks non-whitelisted number", () => {
      expect(
        shouldProcessMessage("6289999999999@s.whatsapp.net", "6281234567890"),
      ).toBe(false);
    });
    it("blocks group messages", () => {
      expect(shouldProcessMessage("123456789@g.us", "6281234567890")).toBe(
        false,
      );
    });
    it("blocks empty JID", () => {
      expect(shouldProcessMessage("", "6281234567890")).toBe(false);
    });
  });
});
