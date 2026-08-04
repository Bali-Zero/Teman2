import { describe, it, expect } from "vitest";
import { buildWaDeeplink, WA_CANONICAL } from "./wa-deeplink";

describe("buildWaDeeplink", () => {
  it("uses canonical number +62 821 3454 721", () => {
    expect(WA_CANONICAL).toBe("628213454721");
  });
  it("url-encodes the context text", () => {
    const url = buildWaDeeplink({ text: "Ciao! sessione abc" });
    expect(url).toBe("https://wa.me/628213454721?text=Ciao!%20sessione%20abc");
  });
  it("composes from source + session + payload", () => {
    const url = buildWaDeeplink({
      source: "visa-oracle",
      sessionId: "abc-123",
      payload: { visa: "E23" },
    });
    expect(url).toMatch(/wa\.me\/628213454721\?text=/);
    expect(decodeURIComponent(url)).toContain("visa-oracle");
    expect(decodeURIComponent(url)).toContain("abc-123");
    expect(decodeURIComponent(url)).toContain("E23");
  });
});
