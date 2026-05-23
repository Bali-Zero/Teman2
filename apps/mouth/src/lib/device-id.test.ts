import { afterEach, describe, expect, it, vi } from "vitest";
import { getDeviceId } from "./device-id";

describe("getDeviceId", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it("returns an existing persisted device id", () => {
    window.localStorage.setItem("bz_device_id", "device-existing");

    expect(getDeviceId()).toBe("device-existing");
  });

  it("creates and persists a new crypto-backed device id when missing", () => {
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "device-fresh"),
    });

    expect(getDeviceId()).toBe("device-fresh");
    expect(window.localStorage.getItem("bz_device_id")).toBe("device-fresh");
  });

  it("returns an in-memory id when localStorage is unavailable", () => {
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "device-memory"),
    });
    vi.stubGlobal("window", {
      localStorage: {
        getItem: vi.fn(() => {
          throw new Error("storage unavailable");
        }),
        setItem: vi.fn(),
      },
    });

    expect(getDeviceId()).toBe("device-memory");
  });

  it("uses the timestamp fallback when crypto randomUUID is unavailable", () => {
    vi.stubGlobal("crypto", {});
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-24T00:00:00.000Z"));
    vi.spyOn(Math, "random").mockReturnValue(0.123456789);

    expect(getDeviceId()).toBe("dev-mpj0glc0-4fzzzxjy");
  });

  it("does not access browser storage during SSR", () => {
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "device-ssr"),
    });
    vi.stubGlobal("window", undefined);

    expect(getDeviceId()).toBe("device-ssr");
  });
});
