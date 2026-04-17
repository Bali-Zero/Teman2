import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { SessionInit } from "./SessionInit";

// The SessionInit component calls into @balizero/core/auth. Those are real
// implementations of getOrCreateSessionId + attachToServerSession. We don't
// mock them — we let them run against jsdom's document.cookie and mocked fetch
// so we exercise the full session-bridge contract.

describe("SessionInit", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    } as Response);
    // Reset cookie between tests
    document.cookie =
      "bz_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates bz_session cookie on mount", async () => {
    render(<SessionInit funnel="home" />);
    await waitFor(() => {
      expect(document.cookie).toMatch(/bz_session=[0-9a-f-]+/i);
    });
  });

  it("calls /api/funnel/session/touch with funnel + session_id", async () => {
    render(<SessionInit funnel="visa" />);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/funnel/session/touch",
        expect.objectContaining({
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.funnel).toBe("visa");
    expect(body.session_id).toMatch(/^[0-9a-f-]+$/i);
  });

  it("reuses existing bz_session cookie (no new UUID)", async () => {
    document.cookie = "bz_session=fixed-test-uuid-12345; path=/";
    render(<SessionInit funnel="tax" />);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.session_id).toBe("fixed-test-uuid-12345");
  });

  it("supports all 5 funnel slugs (visa/kbli/tax/property/home)", async () => {
    const funnels: Array<"visa" | "kbli" | "tax" | "property" | "home"> = [
      "visa",
      "kbli",
      "tax",
      "property",
      "home",
    ];
    for (const f of funnels) {
      (global.fetch as ReturnType<typeof vi.fn>).mockClear();
      // Also reset cookie so each funnel gets a fresh session to make the test isolated
      document.cookie =
        "bz_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
      const { unmount } = render(<SessionInit funnel={f} />);
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });
      const body = JSON.parse(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
      );
      expect(body.funnel).toBe(f);
      unmount();
    }
  });

  it("renders null (no DOM output)", () => {
    const { container } = render(<SessionInit funnel="home" />);
    expect(container.firstChild).toBeNull();
  });
});
