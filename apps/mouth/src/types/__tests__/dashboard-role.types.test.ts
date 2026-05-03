import { describe, it, expectTypeOf } from "vitest";
import type {
  RoleWidgetData,
  ZeroMetrics,
  TeamMetrics,
  TaxMetrics,
  MarketingMetrics,
  AccountingMetrics,
  LiveActivityEvent,
  DashboardStatConfig,
  UseRoleMetricsResult,
} from "../dashboard-role.types";

describe("dashboard-role types", () => {
  it("ZeroMetrics has required fields", () => {
    expectTypeOf<ZeroMetrics>().toHaveProperty("revenue_mtd");
    expectTypeOf<ZeroMetrics>().toHaveProperty("visti_scadenza");
    expectTypeOf<ZeroMetrics>().toHaveProperty("fatture_overdue");
    expectTypeOf<ZeroMetrics>().toHaveProperty("agenti_count");
    expectTypeOf<ZeroMetrics>().toHaveProperty("fly_uptime");
  });

  it("RoleWidgetData is a discriminated union on role", () => {
    type ZeroVariant = Extract<RoleWidgetData, { role: "zero" }>;
    expectTypeOf<ZeroVariant>().toHaveProperty("metrics");
    expectTypeOf<ZeroVariant["metrics"]>().toEqualTypeOf<ZeroMetrics>();
  });

  it("LiveActivityEvent has userId for filtering", () => {
    expectTypeOf<LiveActivityEvent>().toHaveProperty("userId");
  });

  it("DashboardStatConfig colorVariant is constrained", () => {
    expectTypeOf<DashboardStatConfig["colorVariant"]>().toEqualTypeOf<
      "green" | "red" | "yellow" | "blue"
    >();
  });

  it("UseRoleMetricsResult has loading states", () => {
    expectTypeOf<UseRoleMetricsResult>().toHaveProperty("isLoading");
    expectTypeOf<UseRoleMetricsResult>().toHaveProperty("isError");
    expectTypeOf<UseRoleMetricsResult>().toHaveProperty("data");
  });
});
