import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useBrowserSupport } from "../useBrowserSupport";

function setUA(ua: string) {
  Object.defineProperty(window.navigator, "userAgent", {
    value: ua,
    configurable: true,
  });
}

function stubWebGL(ok: boolean) {
  const spy = vi
    .spyOn(HTMLCanvasElement.prototype, "getContext")
    .mockImplementation((type: string) =>
      type === "webgl2" ? (ok ? ({} as WebGL2RenderingContext) : null) : null,
    );
  return spy;
}

describe("useBrowserSupport", () => {
  beforeEach(() => {
    Object.defineProperty(window.navigator, "userAgentData", {
      value: undefined,
      configurable: true,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("flags Chrome + WebGL2 as supported", async () => {
    setUA(
      "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    );
    stubWebGL(true);
    const { result } = renderHook(() => useBrowserSupport());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.supported).toBe(true);
    expect(result.current.chromium).toBe(true);
    expect(result.current.webgl2).toBe(true);
  });

  it("flags Firefox as unsupported", async () => {
    setUA("Mozilla/5.0 (Macintosh) Gecko/20100101 Firefox/125.0");
    stubWebGL(true);
    const { result } = renderHook(() => useBrowserSupport());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.supported).toBe(false);
    expect(result.current.chromium).toBe(false);
  });

  it("flags missing WebGL2 as unsupported even on Chrome", async () => {
    setUA("Chrome/126.0 Safari/537.36");
    stubWebGL(false);
    const { result } = renderHook(() => useBrowserSupport());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.supported).toBe(false);
    expect(result.current.webgl2).toBe(false);
  });
});
