import { describe, it, expect } from "vitest";
import { GET } from "./route";

function makeRequest(search = ""): Parameters<typeof GET>[0] {
  const url = `http://localhost:3000/portal/login${search}`;
  // Minimal NextRequest shim — route uses only nextUrl.searchParams & origin
  return {
    nextUrl: new URL(url) as unknown as {
      searchParams: URLSearchParams;
      origin: string;
    },
  } as unknown as Parameters<typeof GET>[0];
}

describe("GET /portal/login", () => {
  it("308 to /portal/login-upgraded without redirect param", () => {
    const res = GET(makeRequest(""));
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/portal/login-upgraded",
    );
  });
  it("preserves safe /portal/ redirect", () => {
    const res = GET(makeRequest("?redirect=/portal/dashboard"));
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/portal/login-upgraded?redirect=%2Fportal%2Fdashboard",
    );
  });
  it("strips //evil.com", () => {
    const res = GET(makeRequest("?redirect=//evil.com"));
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/portal/login-upgraded",
    );
  });
  it("strips javascript: redirect", () => {
    const res = GET(makeRequest("?redirect=javascript:alert(1)"));
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/portal/login-upgraded",
    );
  });
  it("allows /workspace/ redirect", () => {
    const res = GET(makeRequest("?redirect=/workspace/kita"));
    expect(res.status).toBe(308);
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/portal/login-upgraded?redirect=%2Fworkspace%2Fkita",
    );
  });
});
