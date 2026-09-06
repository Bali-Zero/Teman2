import { describe, expect, it } from "vitest";
import {
  destinations,
  getDestination,
  getReleasableDestination,
} from "../../content/destinations";
import { destinationEvidence20260906 } from "../../content/evidence/destinations-2026-09-06";
import { buildEmailIntent, buildWhatsAppIntent, toSafeExternalHref } from ".";

describe("destination contract", () => {
  it("contains only explicitly allowed external protocols", () => {
    for (const destination of Object.values(destinations)) {
      expect(() => toSafeExternalHref(destination.href)).not.toThrow();
    }
  });

  it.each([
    "javascript:alert(1)",
    "data:text/html,unsafe",
    "ftp://example.com/file",
    "http://example.com",
    "//example.com/path",
    "https://user:secret@example.com/path",
  ])("rejects the unsafe external destination %s", (href) => {
    expect(() => toSafeExternalHref(href)).toThrow(TypeError);
  });

  it("resolves a destination by its stable identifier", () => {
    expect(getDestination("visaOracle")).toMatchObject({
      label: "Visa Oracle",
      href: "https://visa.balizero.com/",
    });
  });

  it("fails closed for a blocked release destination", () => {
    expect(getReleasableDestination("telegram")).toBeNull();
    expect(getReleasableDestination("whatsapp")).toMatchObject({
      releaseStatus: "approved",
    });
  });

  it("keeps every dated evidence URL on an allowed protocol", () => {
    for (const evidence of destinationEvidence20260906) {
      expect(() => toSafeExternalHref(evidence.requestedHref)).not.toThrow();
      if (evidence.finalHref) {
        expect(() => toSafeExternalHref(evidence.finalHref)).not.toThrow();
      }
    }
  });
});

describe("contact intent builders", () => {
  it("encodes a contextual WhatsApp message without sending it", () => {
    const href = buildWhatsAppIntent({
      topic: "Tax & accounting",
      contactName: "Dewa Ayu",
    });
    const destination = new URL(href);

    expect(destination.protocol).toBe("https:");
    expect(destination.hostname).toBe("wa.me");
    expect(destination.pathname).toBe("/628213454721");
    expect(destination.searchParams.get("text")).toBe(
      "Hello Bali Zero, I would like to discuss Tax & accounting with Dewa Ayu.",
    );
    expect(href).toContain("Tax%20%26%20accounting");
  });

  it("normalizes and encodes email subject and body", () => {
    const href = buildEmailIntent({
      subject: "  Property   consultation ",
      body: "Leasehold & due diligence?",
    });
    const destination = new URL(href);

    expect(destination.protocol).toBe("mailto:");
    expect(destination.pathname).toBe("zantara@balizero.com");
    expect(destination.searchParams.get("subject")).toBe(
      "Property consultation",
    );
    expect(destination.searchParams.get("body")).toBe(
      "Leasehold & due diligence?",
    );
  });

  it("rejects an empty contact intent", () => {
    expect(() => buildWhatsAppIntent({ topic: "  " })).toThrow(TypeError);
    expect(() => buildEmailIntent({ subject: "\n\t" })).toThrow(TypeError);
  });
});
