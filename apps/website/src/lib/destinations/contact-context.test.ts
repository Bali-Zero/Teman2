import { describe, expect, it } from "vitest";
import {
  assistantContactContext,
  contactPageHref,
  resolveContactSource,
} from "./contact-context";
describe("assistant contact context", () => {
  it("preserves a service topic and source through the contact page", () => {
    const context = assistantContactContext(
      new URL("https://example.test/services/tax?ignore=untrusted"),
    );
    expect(context).toEqual({ topic: "tax", source: "/services/tax" });
    const next = new URL(
      contactPageHref(context.topic, context.source),
      "https://example.test",
    );
    expect(assistantContactContext(next)).toEqual(context);
  });
  it("retains an allowed team context but discards arbitrary query content", () => {
    expect(
      assistantContactContext(
        new URL(
          "https://example.test/contact?topic=portal&from=team&private=not-persisted",
        ),
      ),
    ).toEqual({ topic: "portal", source: "/team" });
    expect(
      assistantContactContext(
        new URL("https://example.test/contact?topic=unknown&from=unsafe"),
      ),
    ).toEqual({ topic: "general", source: "/contact" });
    expect(resolveContactSource(["team"])).toBe("/contact");
    expect(contactPageHref("tax", "/taxes/some-public-story")).toContain(
      "from=%2Fnews",
    );
  });
  it("carries a tool's subject without copying saved result references or URL context", () => {
    for (const [path, topic, source] of [
      ["/visa-oracle", "immigration", "/visa-oracle"],
      ["/kbli/56101", "company", "/kbli"],
      ["/kbli-explorer", "company", "/kbli-explorer"],
      ["/prime/proposal/SYNTHETIC_REFERENCE", "property", "/prime"],
      ["/visa/voa/SYNTHETIC_REFERENCE", "evoa", "/visa/voa"],
      ["/business/news_20260907_173053_1e7fa0d1", "company", "/news"],
    ]) {
      const context = assistantContactContext(
        new URL(`https://example.test${path}?token=SYNTHETIC_PRIVATE#private`),
      );
      expect(context).toEqual({ topic, source });
      expect(JSON.stringify(context)).not.toMatch(/SYNTHETIC|token|private/);
    }
  });
});
