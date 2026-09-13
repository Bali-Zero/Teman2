import { readFileSync } from "node:fs";
import { describe, it, expect } from "vitest";

import {
  REDACTED,
  SENSITIVE_QUERY_PARAMS,
  analyticsUrlRedactScript,
  redactSensitiveQueryParams,
} from "./analytics-url";

describe("redactSensitiveQueryParams", () => {
  it("redacts the invite token measured leaking to GA (portal audit L-GA)", () => {
    const out = redactSensitiveQueryParams(
      "https://my.balizero.com/portal/register?token=AUDITPROBE1234567890",
    );
    expect(out).not.toContain("AUDITPROBE1234567890");
    expect(out).toBe(
      `https://my.balizero.com/portal/register?token=${encodeURIComponent(REDACTED)}`,
    );
  });

  it("redacts the magic-link token", () => {
    const out = redactSensitiveQueryParams(
      "https://my.balizero.com/portal/magic?token=AUDITPROBE0987654321",
    );
    expect(out).not.toContain("AUDITPROBE0987654321");
  });

  it("redacts a token nested inside another parameter (the second leak)", () => {
    // The exact shape of the expired-magic-link redirect that leaked the token
    // a second time as dl=/dr=.
    const out = redactSensitiveQueryParams(
      "https://my.balizero.com/portal/login-upgraded?expired=true&reason=token_expired" +
        "&redirect=%2Fportal%2Fmagic%3Ftoken%3DAUDITPROBE0987654321",
    );
    expect(out).not.toContain("AUDITPROBE0987654321");
    expect(out).toContain("expired=true");
    expect(out).toContain("reason=token_expired");
  });

  it("redacts every declared parameter", () => {
    for (const param of SENSITIVE_QUERY_PARAMS) {
      const out = redactSensitiveQueryParams(
        `https://my.balizero.com/x?${param}=SUPERSECRETVALUE`,
      );
      expect(out, param).not.toContain("SUPERSECRETVALUE");
    }
  });

  it("leaves an ordinary URL byte-identical", () => {
    const clean = "https://balizero.com/kbli/56303?ref=newsletter&page=2";
    expect(redactSensitiveQueryParams(clean)).toBe(clean);
  });

  it("returns an unparseable value unchanged instead of throwing", () => {
    expect(redactSensitiveQueryParams("not a url")).toBe("not a url");
    expect(redactSensitiveQueryParams("")).toBe("");
  });
});

describe("analyticsUrlRedactScript", () => {
  it("is generated from the same parameter list (no drift between the two copies)", () => {
    for (const param of SENSITIVE_QUERY_PARAMS) {
      expect(analyticsUrlRedactScript).toContain(`"${param}"`);
    }
  });

  it("only overrides page_location when the URL actually carries a credential", () => {
    // Real jsdom window/document: the script sets the GLOBAL dataLayer and
    // reads the browser's own location, exactly as it does in the browser.
    const win = window as typeof window & { dataLayer?: unknown[] };

    const run = (path: string, referrer: string): unknown[] => {
      delete win.dataLayer;
      window.history.replaceState({}, "", path);
      Object.defineProperty(document, "referrer", {
        value: referrer,
        configurable: true,
      });
      new Function(analyticsUrlRedactScript)();
      return win.dataLayer ?? [];
    };

    expect(run("/kbli/56303?ref=newsletter", "")).toEqual([]);

    const pushed = run(
      "/portal/magic?token=LEAKME",
      "https://my.balizero.com/portal/register?token=LEAKMETOO",
    );
    expect(pushed).toHaveLength(1);
    const args = Array.from(pushed[0] as IArguments);
    expect(args[0]).toBe("set");
    const payload = args[1] as { page_location: string; page_referrer: string };
    expect(payload.page_location).not.toContain("LEAKME");
    expect(payload.page_referrer).not.toContain("LEAKMETOO");
  });
});

describe("root layout wiring", () => {
  // The scrub only works if it is queued in dataLayer BEFORE gtag.js loads.
  // @next/third-parties' <GoogleAnalytics> injects the gtag('config', …)
  // whose automatic page_view is the beacon that leaked, so ordering is the
  // whole mechanism — not a style preference.
  const layout = readFileSync("src/app/layout.tsx", "utf8");

  it("mounts the redact script in <head>, before <GoogleAnalytics>", () => {
    const scrubAt = layout.indexOf("__html: analyticsUrlRedactScript");
    const headEndsAt = layout.indexOf("</head>");
    const gaAt = layout.indexOf("<GoogleAnalytics");
    expect(scrubAt).toBeGreaterThan(-1);
    expect(gaAt).toBeGreaterThan(-1);
    expect(scrubAt).toBeLessThan(headEndsAt);
    expect(scrubAt).toBeLessThan(gaAt);
  });
});
