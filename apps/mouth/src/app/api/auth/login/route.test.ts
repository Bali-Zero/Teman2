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

function makeLoginRequest(): NextRequest {
  return new NextRequest("https://balizero.com/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "ops@balizero.com", pin: "123456" }),
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
});
