import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import VoiceConciergePage from "./page";

const headersMock = vi.hoisted(() => vi.fn());
const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);

vi.mock("next/headers", () => ({
  headers: headersMock,
}));

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}));

vi.mock("./VoiceConciergeClient", () => ({
  VoiceConciergeClient: () => <div data-testid="voice-concierge-client" />,
}));

describe("workspace voice concierge page", () => {
  const originalFetch = global.fetch;
  const originalLabEnabled = process.env.VOICE_CONCIERGE_LAB_ENABLED;
  const originalVoiceBackendUrl = process.env.VOICE_CONCIERGE_BACKEND_URL;
  const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;

  beforeEach(() => {
    vi.restoreAllMocks();
    headersMock.mockReset();
    notFoundMock.mockClear();
    delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
    delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    delete process.env.NUZANTARA_API_URL;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = originalFetch;
    restoreEnv("VOICE_CONCIERGE_LAB_ENABLED", originalLabEnabled);
    restoreEnv("VOICE_CONCIERGE_BACKEND_URL", originalVoiceBackendUrl);
    restoreEnv("NUZANTARA_API_URL", originalNuzantaraApiUrl);
  });

  it("renders in development without a server auth probe", async () => {
    const element = await VoiceConciergePage();

    render(element);

    expect(screen.getByTestId("voice-concierge-client")).toBeInTheDocument();
    expect(headersMock).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not mount the client in production without an internal session", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    headersMock.mockResolvedValue(new Headers());

    await expect(VoiceConciergePage()).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("renders in production for an internal session cookie", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    headersMock.mockResolvedValue(
      new Headers({ cookie: "nz_access_token=staff-token" }),
    );
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { email: "founder@balizero.com", role: "founder" },
        }),
        {
          status: 200,
        },
      ),
    );

    const element = await VoiceConciergePage();

    render(element);

    expect(screen.getByTestId("voice-concierge-client")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        headers: { Authorization: "Bearer staff-token" },
        method: "GET",
        redirect: "error",
      }),
    );
  });

  it("renders in production for an internal email with legacy role_level only", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    headersMock.mockResolvedValue(
      new Headers({ cookie: "nz_access_token=member-token" }),
    );
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { email: "team@balizero.com", role_level: "member" },
        }),
        { status: 200 },
      ),
    );

    const element = await VoiceConciergePage();

    render(element);

    expect(screen.getByTestId("voice-concierge-client")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        headers: { Authorization: "Bearer member-token" },
        method: "GET",
        redirect: "error",
      }),
    );
  });
});

function restoreEnv(name: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[name];
    return;
  }

  process.env[name] = value;
}
