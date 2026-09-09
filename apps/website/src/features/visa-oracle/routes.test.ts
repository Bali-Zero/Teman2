import { describe, expect, it } from "vitest";
import type { NextRequest } from "next/server";
import { GET, HEAD } from "../../app/visa-v2/route";
import { GET as visa } from "../../app/visa/[[...retainedPath]]/route";

describe("native Oracle entry ownership", () => {
  it.each([GET, HEAD, visa])(
    "permanently redirects an entry locally without carrying applicant query data",
    (handler) => {
      const path = handler === visa ? "/visa" : "/visa-v2";
      const result = handler(
        new Request(
          `http://localhost:3100${path}?birth_date=synthetic`,
        ) as NextRequest,
      );
      expect(result.status).toBe(308);
      expect(result.headers.get("location")).toBe("/visa-oracle");
      expect(
        new URL(result.headers.get("location")!, "http://127.0.0.1:3100")
          .origin,
      ).toBe("http://127.0.0.1:3100");
      expect(result.headers.get("cache-control")).toBe("no-store");
      expect(result.headers.get("referrer-policy")).toBe("no-referrer");
    },
  );
  it("preserves retained child contracts and their guarded origin", () => {
    for (const path of [
      "/visa/match/synthetic",
      "/visa/clock/synthetic",
      "/visa/voa/auth",
      "/visa/voa/upload/synthetic",
      "/visa/voa/checkout/synthetic",
      "/visa/second-home/studio",
    ]) {
      const allowed = visa(
        new Request(`http://localhost:3100${path}`) as NextRequest,
      );
      expect(allowed.status).toBe(307);
      expect(allowed.headers.get("location")).toBe(
        `https://balizero.com${path}`,
      );
      const blocked = visa(
        new Request(`https://unconfigured.example${path}`) as NextRequest,
      );
      expect(blocked.status).toBe(503);
    }
  });
});
