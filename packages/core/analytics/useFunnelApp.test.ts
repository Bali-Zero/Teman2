import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFunnelAppTracker } from "./funnel-app";
import { useFunnelApp } from "./useFunnelApp";

const tracker = vi.hoisted(() => ({
  viewed: vi.fn().mockResolvedValue(undefined),
  branchSelected: vi.fn(),
  formStarted: vi.fn().mockResolvedValue(undefined),
  formSubmitted: vi.fn(),
  wizardStep: vi.fn(),
  wizardAbandoned: vi.fn(),
  resultViewed: vi.fn(),
  ctaClicked: vi.fn(),
  whatsappHandoff: vi.fn(),
  shareClicked: vi.fn(),
  pdfDownloaded: vi.fn(),
  emailSubscribed: vi.fn(),
}));

vi.mock("./funnel-app", () => ({
  createFunnelAppTracker: vi.fn(() => tracker),
}));

describe("useFunnelApp", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates the app tracker and records one view on mount", async () => {
    renderHook(() => useFunnelApp("visa_clock"));

    expect(createFunnelAppTracker).toHaveBeenCalledWith("visa_clock");
    await waitFor(() => expect(tracker.viewed).toHaveBeenCalledTimes(1));
  });

  it("allows automatic view tracking to be disabled", () => {
    renderHook(() => useFunnelApp("tax_gap", { trackView: false }));

    expect(tracker.viewed).not.toHaveBeenCalled();
  });

  it("emits form_started once per field while exposing the other helpers", () => {
    const { result } = renderHook(() => useFunnelApp("kbli_decoder"));

    act(() => {
      result.current.formStarted("sector");
      result.current.formStarted("sector");
      result.current.formStarted("location");
    });

    expect(tracker.formStarted).toHaveBeenNthCalledWith(1, "sector");
    expect(tracker.formStarted).toHaveBeenNthCalledWith(2, "location");
    expect(result.current.resultViewed).toBe(tracker.resultViewed);
  });
});
