import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/logger", () => ({
  logger: {
    info: vi.fn(),
    error: vi.fn(),
  },
}));

const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;
const originalNextPublicApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalCookieDomain = process.env.COOKIE_DOMAIN;

function makeLoginRequest(
  url = "https://balizero.com/api/auth/login",
): NextRequest {
  return new NextRequest(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "ops@example.com", pin: "123456" }),
  });
}

describe("POST /api/auth/login", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          message: "Login successful",
          data: {
            token: " token-with-newline\n",
            csrfToken: " csrf-with-newline\n",
            expiresIn: 3600,
            user: { email: "ops@balizero.com" },
          },
        }),
      }),
    );
  });

  afterEach(() => {
    if (originalNuzantaraApiUrl === undefined) {
      delete process.env.NUZANTARA_API_URL;
    } else {
      process.env.NUZANTARA_API_URL = originalNuzantaraApiUrl;
    }

    if (originalNextPublicApiUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_URL;
    } else {
      process.env.NEXT_PUBLIC_API_URL = originalNextPublicApiUrl;
    }

    if (originalCookieDomain === undefined) {
      delete process.env.COOKIE_DOMAIN;
    } else {
      process.env.COOKIE_DOMAIN = originalCookieDomain;
    }

    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("trims whitespace from backend URL env values before proxying", async () => {
    process.env.NUZANTARA_API_URL = "https://backend.example.com/api\n";
    delete process.env.NEXT_PUBLIC_API_URL;

    const { POST } = await import("./route");
    const response = await POST(makeLoginRequest());

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.example.com/api/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("uses host-only non-Secure cookies on loopback production builds", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NUZANTARA_API_URL", "http://127.0.0.1:8000");
    vi.stubEnv("COOKIE_DOMAIN", "localhost");
    vi.stubEnv("MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE", "1");

    const { POST } = await import("./route");
    const response = await POST(
      makeLoginRequest("http://127.0.0.1:3101/api/auth/login"),
    );
    const cookies = response.headers.getSetCookie();

    expect(cookies).toHaveLength(2);
    for (const cookie of cookies) {
      expect(cookie).not.toContain("Domain=");
      expect(cookie).not.toContain("; Secure");
    }
  });

  it("keeps production cookie policy when the QA flag is absent", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NUZANTARA_API_URL", "http://127.0.0.1:8000");
    vi.stubEnv("COOKIE_DOMAIN", ".balizero.com");
    vi.stubEnv("MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE", "0");

    const { POST } = await import("./route");
    const response = await POST(
      makeLoginRequest("http://127.0.0.1:3101/api/auth/login"),
    );

    for (const cookie of response.headers.getSetCookie()) {
      expect(cookie).toContain("Domain=.balizero.com");
      expect(cookie).toContain("; Secure");
    }
  });

  it("does not expose upstream failure details to the public client", async () => {
    vi.mocked(global.fetch).mockRejectedValue(
      new Error(
        "connect ECONNREFUSED https://private-backend.example.internal:8000",
      ),
    );

    const { POST } = await import("./route");
    const response = await POST(makeLoginRequest());
    const payload = await response.json();

    expect(response.status).toBe(500);
    expect(payload).toEqual({
      success: false,
      message: "Internal server error",
    });
    expect(JSON.stringify(payload)).not.toContain("private-backend");
    expect(JSON.stringify(payload)).not.toContain("ECONNREFUSED");
  });
});
