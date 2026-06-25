import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import LabVoiceConciergePage from "./page";

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

vi.mock(
  "@/app/(workspace)/intelligence/voice-concierge/VoiceConciergeClient",
  () => ({
    VoiceConciergeClient: () => <div data-testid="voice-concierge-client" />,
  }),
);

describe("lab voice concierge page", () => {
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
    const element = await LabVoiceConciergePage();

    render(element);

    expect(screen.getByTestId("voice-concierge-client")).toBeInTheDocument();
    expect(headersMock).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not expose the page in production without the lab flag", async () => {
    vi.stubEnv("NODE_ENV", "production");

    await expect(LabVoiceConciergePage()).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
    expect(headersMock).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not mount the client in production without an internal session", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    headersMock.mockResolvedValue(new Headers());

    await expect(LabVoiceConciergePage()).rejects.toThrow("NEXT_NOT_FOUND");

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
      new Response(JSON.stringify({ data: { role: "admin" } }), {
        status: 200,
      }),
    );

    const element = await LabVoiceConciergePage();

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

  it("renders in production for a normal team role session", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    headersMock.mockResolvedValue(
      new Headers({ cookie: "nz_access_token=team-token" }),
    );
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { email: "ops@balizero.com", role: "team" },
        }),
        { status: 200 },
      ),
    );

    const element = await LabVoiceConciergePage();

    render(element);

    expect(screen.getByTestId("voice-concierge-client")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        headers: { Authorization: "Bearer team-token" },
        method: "GET",
        redirect: "error",
      }),
    );
  });

  it("does not render in production for a client session", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    headersMock.mockResolvedValue(
      new Headers({ cookie: "nz_access_token=client-token" }),
    );
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { email: "client@example.com", role: "client" },
        }),
        { status: 200 },
      ),
    );

    await expect(LabVoiceConciergePage()).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
  });
});

function restoreEnv(name: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[name];
    return;
  }

  process.env[name] = value;
}
