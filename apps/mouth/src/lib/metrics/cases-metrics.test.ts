import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
  },
}));

import { logger } from "@/lib/logger";
import { casesMetrics } from "./cases-metrics";

const mockLogger = logger as unknown as {
  debug: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
  warn: ReturnType<typeof vi.fn>;
};

describe("casesMetrics", () => {
  beforeEach(() => {
    casesMetrics.clearMetrics();
    vi.clearAllMocks();
  });

  it("tracks page views and unique viewed cases in session stats", () => {
    casesMetrics.trackPageView("detail", 101, "user-1");
    casesMetrics.trackPageView("detail", 101, "user-1");
    casesMetrics.trackPageView("new", undefined, "user-1");

    expect(casesMetrics.getSessionStats()).toMatchObject({
      casesViewed: 1,
      casesCreated: 0,
      apiCalls: 0,
      errors: 0,
    });
    expect(casesMetrics.getMetrics()).toHaveLength(3);
    expect(mockLogger.info).toHaveBeenCalledWith(
      "Case page viewed",
      expect.objectContaining({
        component: "CasesMetrics",
        action: "trackPageView",
      }),
    );
  });

  it("aggregates button clicks and error types", () => {
    casesMetrics.trackButtonClick("open-client", "CasesListPage", 7);
    casesMetrics.trackButtonClick("open-client", "CasesListPage", 8);
    casesMetrics.trackButtonClick("new-case", "CasesListPage");
    casesMetrics.trackError("VALIDATION", "Missing field", "CasesNewPage");
    casesMetrics.trackError("VALIDATION", "Bad date", "CasesNewPage");
    casesMetrics.trackError("NETWORK", "Timeout", "CasesListPage");

    expect(casesMetrics.getButtonClickStats()).toEqual({
      "open-client": 2,
      "new-case": 1,
    });
    expect(casesMetrics.getErrorStats()).toEqual({
      VALIDATION: 2,
      NETWORK: 1,
    });
    expect(casesMetrics.getSessionStats().errors).toBe(3);
  });

  it("summarizes API success rate and case actions", () => {
    casesMetrics.trackApiCall("/api/cases", "GET", true, 120);
    casesMetrics.trackApiCall("/api/cases/7", "PATCH", false, 250, 7);
    casesMetrics.trackCaseCreation(7, "KITAS", 99, "user-2");
    casesMetrics.trackCaseUpdate(7, ["status"], "status", "user-2");

    expect(casesMetrics.getSessionStats()).toMatchObject({
      casesCreated: 1,
      casesEdited: 1,
      statusChanges: 1,
      apiCalls: 2,
    });
    expect(casesMetrics.getPerformanceSummary()).toMatchObject({
      apiCallCount: 2,
      apiSuccessRate: 50,
      errorCount: 0,
      caseActionCount: 2,
    });
    expect(mockLogger.warn).toHaveBeenCalledWith(
      "Cases API call failed",
      expect.objectContaining({
        component: "CasesMetrics",
        action: "trackApiCall",
      }),
    );
  });

  it("records performance marks and returns 0 for missing marks", () => {
    expect(casesMetrics.endPerformanceMark("missing_mark")).toBe(0);

    casesMetrics.startPerformanceMark("case_page_load");
    const duration = casesMetrics.endPerformanceMark("case_page_load", 42);

    expect(duration).toBeGreaterThanOrEqual(0);
    expect(casesMetrics.getPerformanceSummary().pageLoadTime).toBe(duration);
    expect(mockLogger.warn).toHaveBeenCalledWith(
      "Performance mark not found",
      expect.objectContaining({
        component: "CasesMetrics",
        action: "endPerformanceMark",
      }),
    );
  });

  it("exports metrics with session stats and derived summaries", () => {
    casesMetrics.trackQuickAction("whatsapp", 22, "CasesDetailPage", "user-3");
    casesMetrics.trackModal("status_change", "open", 22, "user-3");

    const exported = JSON.parse(casesMetrics.exportMetrics());

    expect(exported.metrics).toHaveLength(2);
    expect(exported.sessionStats).toMatchObject({
      casesViewed: 0,
      apiCalls: 0,
      errors: 0,
    });
    expect(exported.summary.performance.caseActionCount).toBe(2);
    expect(exported.exportedAt).toEqual(expect.any(String));
  });
});
