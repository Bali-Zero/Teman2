import { describe, expect, it } from "vitest";

import nextConfig from "../../../../next.config";

describe("production content security policy", () => {
  it("keeps the shared security headers global without a global CSP", async () => {
    expect(nextConfig.headers).toBeDefined();

    const rules = await nextConfig.headers!();
    const catchAllRule = rules.find((rule) => rule.source === "/:path*");
    const enforcingHeader = catchAllRule?.headers.find(
      (header) => header.key === "Content-Security-Policy",
    );
    const reportOnlyHeader = catchAllRule?.headers.find(
      (header) => header.key === "Content-Security-Policy-Report-Only",
    );

    expect(catchAllRule?.headers).toContainEqual({
      key: "Strict-Transport-Security",
      value: "max-age=63072000; includeSubDomains; preload",
    });
    expect(enforcingHeader).toBeUndefined();
    expect(reportOnlyHeader).toBeUndefined();
  });

  it("enforces a client-safe CSP on every portal route", async () => {
    expect(nextConfig.headers).toBeDefined();

    const rules = await nextConfig.headers!();
    const portalRule = rules.find((rule) => rule.source === "/portal/:path*");
    const reportOnlyHeader = portalRule?.headers.find(
      (header) => header.key === "Content-Security-Policy-Report-Only",
    );
    const enforcingHeader = portalRule?.headers.find(
      (header) => header.key === "Content-Security-Policy",
    );

    expect(reportOnlyHeader).toBeUndefined();
    expect(enforcingHeader).toBeDefined();
    expect(enforcingHeader?.value).not.toContain("127.0.0.1");
    expect(enforcingHeader?.value).not.toContain("'unsafe-eval'");
    expect(enforcingHeader?.value).toContain("worker-src 'self' blob:");
    expect(enforcingHeader?.value).toContain("frame-ancestors 'none'");
    expect(enforcingHeader?.value).toContain("form-action 'self'");
  });

  it("does not apply the portal CSP globally to Prime", async () => {
    expect(nextConfig.headers).toBeDefined();

    const rules = await nextConfig.headers!();
    const cspRules = rules.filter((rule) =>
      rule.headers.some((header) => header.key === "Content-Security-Policy"),
    );

    expect(cspRules.map((rule) => rule.source)).toEqual(["/portal/:path*"]);
  });
});
