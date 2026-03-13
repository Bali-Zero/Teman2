# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign kita.balizero.com dashboard with Asymmetric Hero layout, Liquid Glassmorphism soft matte palette, and member-centric content (each user sees only their own data).

**Architecture:** New CSS utilities + color tokens in `globals.css`; new components in `components/dashboard/` (LiveActivityFeed, RoleWidget, DashboardStatCard, role-widgets/, bottom-widgets/); extended API client and hooks; modified `dashboard/page.tsx` replaces old grid with the new one. WhatsApp widget removed. Backend needs 2 new endpoints + WebSocket per-user channels.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS v4, React Query (TanStack), WebSocket via `useRealtime()`, FastAPI backend.

---

## Chunk 1: Foundation — CSS, Types, Role Logic

### Task 1: Add CSS tokens and glass utilities to globals.css

**Files:**

- Modify: `apps/mouth/src/app/globals.css`

- [ ] **Step 1: Add dashboard color tokens and glass utility classes**

Open `apps/mouth/src/app/globals.css` and append the following **after** the existing `:root {}` block (after line 43):

```css
/* ── Dashboard Redesign — Liquid Glass ──────────────────────── */
:root {
  --dash-bg: #090b12;
  --dash-ok: #5cb88a;
  --dash-critical: #c45c78;
  --dash-warning: #b89a40;
  --dash-info: #4a8ec4;
  --dash-live: #48be9b;
  --dash-role: #9880d8;
}

/* Liquid animated background — dashboard page only */
.dash-liquid-bg::before {
  content: "";
  position: fixed;
  inset: 0;
  background:
    radial-gradient(
      ellipse 65% 55% at 10% 38%,
      rgba(72, 190, 155, 0.11) 0%,
      transparent 55%
    ),
    radial-gradient(
      ellipse 55% 65% at 88% 62%,
      rgba(110, 85, 210, 0.1) 0%,
      transparent 55%
    ),
    radial-gradient(
      ellipse 40% 32% at 52% 4%,
      rgba(60, 175, 210, 0.08) 0%,
      transparent 50%
    ),
    radial-gradient(
      ellipse 30% 24% at 74% 18%,
      rgba(210, 185, 60, 0.06) 0%,
      transparent 45%
    ),
    radial-gradient(
      ellipse 25% 20% at 28% 80%,
      rgba(210, 80, 105, 0.05) 0%,
      transparent 45%
    );
  animation: dashLiquid 13s ease-in-out infinite alternate;
  pointer-events: none;
  z-index: 0;
}

@keyframes dashLiquid {
  0% {
    transform: scale(1) translate(0, 0);
    opacity: 1;
  }
  33% {
    transform: scale(1.03) translate(-0.8%, 1.2%);
    opacity: 0.9;
  }
  66% {
    transform: scale(0.98) translate(1.2%, -0.8%);
    opacity: 0.95;
  }
  100% {
    transform: scale(1.02) translate(-0.4%, 0.4%);
    opacity: 1;
  }
}

/* Glass card base */
.glass-base {
  background: rgba(255, 255, 255, 0.028);
  border: 1px solid rgba(255, 255, 255, 0.075);
  border-radius: 12px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  position: relative;
  overflow: hidden;
}

/* Top edge shimmer */
.glass-base::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.12),
    transparent
  );
  pointer-events: none;
}

/* Color variants */
.glass-green {
  background: rgba(92, 184, 138, 0.048);
  border-color: rgba(92, 184, 138, 0.24);
}
.glass-red {
  background: rgba(196, 92, 120, 0.048);
  border-color: rgba(196, 92, 120, 0.24);
}
.glass-yellow {
  background: rgba(184, 154, 64, 0.048);
  border-color: rgba(184, 154, 64, 0.24);
}
.glass-blue {
  background: rgba(74, 142, 196, 0.048);
  border-color: rgba(74, 142, 196, 0.24);
}
.glass-violet {
  background: rgba(152, 128, 216, 0.048);
  border-color: rgba(152, 128, 216, 0.24);
}
.glass-teal {
  background: rgba(72, 190, 155, 0.048);
  border-color: rgba(72, 190, 155, 0.24);
}

/* Live dot pulse animation */
@keyframes livePulse {
  0%,
  100% {
    box-shadow:
      0 0 0 2px rgba(72, 190, 155, 0.15),
      0 0 7px rgba(72, 190, 155, 0.5);
  }
  50% {
    box-shadow:
      0 0 0 3px rgba(72, 190, 155, 0.22),
      0 0 13px rgba(72, 190, 155, 0.68);
  }
}
.live-dot-pulse {
  animation: livePulse 2.2s ease-in-out infinite;
}
```

- [ ] **Step 2: Verify globals.css compiles without error**

```bash
cd apps/mouth && npm run build 2>&1 | head -30
```

Expected: no CSS parse errors. TypeScript errors from unrelated files (e.g., `eclipse-concept`) are pre-existing and can be ignored.

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/app/globals.css
git commit -m "feat(dashboard): add liquid glass CSS tokens and utilities"
```

---

### Task 2: Create dashboard role types and normalization utility

**Files:**

- Create: `apps/mouth/src/lib/dashboard-role.ts`
- Create: `apps/mouth/src/lib/__tests__/dashboard-role.test.ts`

- [ ] **Step 1: Write failing tests**

Create `apps/mouth/src/lib/__tests__/dashboard-role.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { normalizeDashboardRole, VALID_ROLES } from "../dashboard-role";

describe("normalizeDashboardRole", () => {
  it("returns 'zero' when isAdmin is true regardless of role string", () => {
    expect(normalizeDashboardRole("member", true)).toBe("zero");
    expect(normalizeDashboardRole(undefined, true)).toBe("zero");
    expect(normalizeDashboardRole("tax", true)).toBe("zero");
  });

  it("returns matched role for valid lowercase strings", () => {
    expect(normalizeDashboardRole("team", false)).toBe("team");
    expect(normalizeDashboardRole("tax", false)).toBe("tax");
    expect(normalizeDashboardRole("marketing", false)).toBe("marketing");
    expect(normalizeDashboardRole("accounting", false)).toBe("accounting");
  });

  it("is case-insensitive", () => {
    expect(normalizeDashboardRole("TAX", false)).toBe("tax");
    expect(normalizeDashboardRole("Marketing", false)).toBe("marketing");
    expect(normalizeDashboardRole("ACCOUNTING", false)).toBe("accounting");
  });

  it("falls back to 'team' for unknown roles", () => {
    expect(normalizeDashboardRole("consultant", false)).toBe("team");
    expect(normalizeDashboardRole("", false)).toBe("team");
    expect(normalizeDashboardRole(undefined, false)).toBe("team");
  });

  it("exports VALID_ROLES containing all 5 roles", () => {
    expect(VALID_ROLES).toContain("zero");
    expect(VALID_ROLES).toContain("team");
    expect(VALID_ROLES).toContain("tax");
    expect(VALID_ROLES).toContain("marketing");
    expect(VALID_ROLES).toContain("accounting");
    expect(VALID_ROLES).toHaveLength(5);
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd apps/mouth && npx vitest run src/lib/__tests__/dashboard-role.test.ts 2>&1 | tail -20
```

Expected: `FAIL` — module not found.

- [ ] **Step 3: Create dashboard-role.ts**

Create `apps/mouth/src/lib/dashboard-role.ts`:

```typescript
export type DashboardRole =
  | "zero"
  | "team"
  | "tax"
  | "marketing"
  | "accounting";

export const VALID_ROLES: DashboardRole[] = [
  "zero",
  "team",
  "tax",
  "marketing",
  "accounting",
];

/**
 * Normalizes a raw role string from the API into a typed DashboardRole.
 * Admins always get 'zero'. Unknown roles fall back to 'team'.
 */
export function normalizeDashboardRole(
  raw: string | undefined,
  isAdmin: boolean,
): DashboardRole {
  if (isAdmin) return "zero";
  const lower = raw?.toLowerCase() ?? "";
  const found = VALID_ROLES.find((r) => r === lower);
  return found ?? "team";
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd apps/mouth && npx vitest run src/lib/__tests__/dashboard-role.test.ts 2>&1 | tail -10
```

Expected: `PASS` — 5 tests passing.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/lib/dashboard-role.ts apps/mouth/src/lib/__tests__/dashboard-role.test.ts
git commit -m "feat(dashboard): add DashboardRole type and normalizeDashboardRole utility"
```

---

### Task 3: Create role-specific TypeScript interfaces

**Files:**

- Create: `apps/mouth/src/types/dashboard-role.types.ts`
- Create: `apps/mouth/src/types/__tests__/dashboard-role.types.test.ts`

- [ ] **Step 1: Write type-level tests**

Create `apps/mouth/src/types/__tests__/dashboard-role.types.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd apps/mouth && npx vitest run src/types/__tests__/dashboard-role.types.test.ts 2>&1 | tail -10
```

Expected: `FAIL` — module not found.

- [ ] **Step 3: Create dashboard-role.types.ts**

Create `apps/mouth/src/types/dashboard-role.types.ts`:

```typescript
import type { RoleAlert } from "./dashboard-role-alert.types";

export type { RoleAlert };

export interface ZeroMetrics {
  revenue_mtd: number;
  visti_scadenza: number;
  fatture_overdue: number;
  agenti_count: number;
  fly_uptime: number;
}

export interface TeamMetrics {
  pratiche_assegnate: number;
  prossima_scadenza: string | null;
  doc_mancanti: number;
  clienti_assegnati: number;
  stalled_count: number;
}

export interface TaxMetrics {
  clienti_compliant: number;
  scadenze_7gg: number;
  dichiarazioni_pending: number;
  alert_pajak: number;
  prossima_scadenza: string | null;
}

export interface MarketingMetrics {
  articoli_pubblicati: number;
  articoli_in_review: number;
  subscriber_delta: number;
  lead_nuovi: number;
}

export interface AccountingMetrics {
  fatture_pagate_mtd: number;
  fatture_overdue: number;
  fatture_pending: number;
  ricavi_mtd: number;
  overdue_total: number;
}

export type RoleWidgetData =
  | { role: "zero"; metrics: ZeroMetrics; alerts: RoleAlert[] }
  | { role: "team"; metrics: TeamMetrics; alerts: RoleAlert[] }
  | { role: "tax"; metrics: TaxMetrics; alerts: RoleAlert[] }
  | { role: "marketing"; metrics: MarketingMetrics; alerts: RoleAlert[] }
  | { role: "accounting"; metrics: AccountingMetrics; alerts: RoleAlert[] };

export interface LiveActivityEvent {
  id: string;
  type: "critical" | "ok" | "warning" | "info" | "live";
  icon: string;
  text: string;
  tag?: string;
  timestamp: string;
  userId?: string;
}

export interface DashboardStatConfig {
  icon: string;
  value: number | string;
  label: string;
  trend: string;
  colorVariant: "green" | "red" | "yellow" | "blue";
}

export interface UseRoleMetricsResult {
  data: RoleWidgetData | undefined;
  isLoading: boolean;
  isError: boolean;
}
```

Also create `apps/mouth/src/types/dashboard-role-alert.types.ts`:

```typescript
export interface RoleAlert {
  type: "critical" | "warning" | "ok" | "info";
  label: string;
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd apps/mouth && npx vitest run src/types/__tests__/dashboard-role.types.test.ts 2>&1 | tail -10
```

Expected: `PASS`.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/types/dashboard-role.types.ts apps/mouth/src/types/dashboard-role-alert.types.ts apps/mouth/src/types/__tests__/dashboard-role.types.test.ts
git commit -m "feat(dashboard): add role-specific TypeScript interfaces (discriminated union)"
```

---

### Task 4: Create useRoleMetrics hook

**Files:**

- Create: `apps/mouth/src/hooks/useRoleMetrics.ts`
- Create: `apps/mouth/src/hooks/__tests__/useRoleMetrics.test.ts`

- [ ] **Step 1: Write failing tests**

Create `apps/mouth/src/hooks/__tests__/useRoleMetrics.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useRoleMetrics } from "../useRoleMetrics";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    request: vi.fn(),
  },
}));

import { api } from "@/lib/api";

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useRoleMetrics", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns isLoading true initially", () => {
    vi.mocked(api.request).mockResolvedValue({} as never);
    const { result } = renderHook(() => useRoleMetrics("team", "user-123"), {
      wrapper: makeWrapper(),
    });
    expect(result.current.isLoading).toBe(true);
  });

  it("returns data on success", async () => {
    const mockData = {
      role: "team",
      metrics: {
        pratiche_assegnate: 5,
        prossima_scadenza: null,
        doc_mancanti: 2,
        clienti_assegnati: 8,
        stalled_count: 1,
      },
      alerts: [],
    };
    vi.mocked(api.request).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRoleMetrics("team", "user-123"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toEqual(mockData);
    expect(result.current.isError).toBe(false);
  });

  it("returns isError true on failure", async () => {
    vi.mocked(api.request).mockRejectedValue(new Error("network error"));

    const { result } = renderHook(
      () => useRoleMetrics("accounting", "user-456"),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isError).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("calls correct API endpoint with role and userId", async () => {
    vi.mocked(api.request).mockResolvedValue({} as never);

    renderHook(() => useRoleMetrics("tax", "user-789"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() =>
      expect(vi.mocked(api.request)).toHaveBeenCalledWith(
        "/api/dashboard/role-metrics?role=tax&user_id=user-789",
      ),
    );
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd apps/mouth && npx vitest run src/hooks/__tests__/useRoleMetrics.test.ts 2>&1 | tail -10
```

Expected: `FAIL` — module not found.

- [ ] **Step 3: Create useRoleMetrics.ts**

Create `apps/mouth/src/hooks/useRoleMetrics.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardRole } from "@/lib/dashboard-role";
import type {
  UseRoleMetricsResult,
  RoleWidgetData,
} from "@/types/dashboard-role.types";

export function useRoleMetrics(
  role: DashboardRole,
  userId: string,
): UseRoleMetricsResult {
  const { data, isLoading, isError } = useQuery<RoleWidgetData>({
    queryKey: ["role-metrics", role, userId],
    queryFn: () =>
      api.request<RoleWidgetData>(
        `/api/dashboard/role-metrics?role=${role}&user_id=${userId}`,
      ),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
    enabled: !!userId,
  });

  return { data, isLoading, isError };
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd apps/mouth && npx vitest run src/hooks/__tests__/useRoleMetrics.test.ts 2>&1 | tail -10
```

Expected: `PASS` — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/hooks/useRoleMetrics.ts apps/mouth/src/hooks/__tests__/useRoleMetrics.test.ts
git commit -m "feat(dashboard): add useRoleMetrics hook for per-role widget data"
```

---

## Chunk 2: New Dashboard Components

### Task 5: DashboardStatCard component

**Files:**

- Create: `apps/mouth/src/components/dashboard/DashboardStatCard.tsx`
- Create: `apps/mouth/src/components/dashboard/__tests__/DashboardStatCard.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `apps/mouth/src/components/dashboard/__tests__/DashboardStatCard.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardStatCard } from "../DashboardStatCard";

describe("DashboardStatCard", () => {
  const baseProps = {
    icon: "📁",
    value: 24,
    label: "Pratiche Attive",
    trend: "▲ +3",
    colorVariant: "green" as const,
  };

  it("renders the value", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("24")).toBeInTheDocument();
  });

  it("renders the label", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("Pratiche Attive")).toBeInTheDocument();
  });

  it("renders the trend text", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("▲ +3")).toBeInTheDocument();
  });

  it("renders the icon", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("📁")).toBeInTheDocument();
  });

  it("applies correct color class for each variant", () => {
    const { container, rerender } = render(<DashboardStatCard {...baseProps} colorVariant="red" />);
    expect(container.firstChild).toHaveClass("glass-red");

    rerender(<DashboardStatCard {...baseProps} colorVariant="yellow" />);
    expect(container.firstChild).toHaveClass("glass-yellow");

    rerender(<DashboardStatCard {...baseProps} colorVariant="blue" />);
    expect(container.firstChild).toHaveClass("glass-blue");
  });

  it("renders string values", () => {
    render(<DashboardStatCard {...baseProps} value="$48K" />);
    expect(screen.getByText("$48K")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/__tests__/DashboardStatCard.test.tsx 2>&1 | tail -10
```

Expected: `FAIL`.

- [ ] **Step 3: Create DashboardStatCard.tsx**

Create `apps/mouth/src/components/dashboard/DashboardStatCard.tsx`:

```typescript
"use client";

import React from "react";
import type { DashboardStatConfig } from "@/types/dashboard-role.types";

const COLOR_CLASS: Record<DashboardStatConfig["colorVariant"], string> = {
  green:  "glass-green",
  red:    "glass-red",
  yellow: "glass-yellow",
  blue:   "glass-blue",
};

const VALUE_COLOR: Record<DashboardStatConfig["colorVariant"], string> = {
  green:  "text-[#5cb88a]",
  red:    "text-[#c45c78]",
  yellow: "text-[#b89a40]",
  blue:   "text-[#4a8ec4]",
};

const TREND_COLOR = VALUE_COLOR;

interface DashboardStatCardProps extends DashboardStatConfig {
  className?: string;
}

export const DashboardStatCard = React.memo(function DashboardStatCard({
  icon,
  value,
  label,
  trend,
  colorVariant,
  className = "",
}: DashboardStatCardProps) {
  return (
    <div
      className={`glass-base ${COLOR_CLASS[colorVariant]} p-3 flex flex-col gap-1 ${className}`}
    >
      <span className="text-base">{icon}</span>
      <span className={`text-2xl font-extrabold leading-none tracking-tight ${VALUE_COLOR[colorVariant]}`}>
        {value}
      </span>
      <span className="text-[9px] uppercase tracking-widest text-white/35">{label}</span>
      <span className={`text-[9px] font-semibold mt-0.5 ${TREND_COLOR[colorVariant]}`}>{trend}</span>
    </div>
  );
});
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/__tests__/DashboardStatCard.test.tsx 2>&1 | tail -10
```

Expected: `PASS` — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/dashboard/DashboardStatCard.tsx apps/mouth/src/components/dashboard/__tests__/DashboardStatCard.test.tsx
git commit -m "feat(dashboard): add DashboardStatCard with soft matte color variants"
```

---

### Task 6: LiveActivityFeed component

**Files:**

- Create: `apps/mouth/src/components/dashboard/LiveActivityFeed.tsx`
- Create: `apps/mouth/src/components/dashboard/__tests__/LiveActivityFeed.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `apps/mouth/src/components/dashboard/__tests__/LiveActivityFeed.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LiveActivityFeed } from "../LiveActivityFeed";
import type { LiveActivityEvent } from "@/types/dashboard-role.types";

const mockEvents: LiveActivityEvent[] = [
  { id: "1", type: "critical", icon: "🚨", text: "KITAS scade in 5 giorni", tag: "CRITICO", timestamp: "14:52", userId: "user-1" },
  { id: "2", type: "ok",       icon: "✅", text: "Fattura pagata",          tag: "PAGATO",  timestamp: "14:48", userId: "user-1" },
  { id: "3", type: "info",     icon: "📄", text: "Documento caricato",      tag: "DOC",     timestamp: "14:32", userId: "user-2" },
];

describe("LiveActivityFeed", () => {
  it("renders the LIVE ACTIVITY label", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText("LIVE ACTIVITY")).toBeInTheDocument();
  });

  it("renders all events", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText(/KITAS scade/)).toBeInTheDocument();
    expect(screen.getByText(/Fattura pagata/)).toBeInTheDocument();
    expect(screen.getByText(/Documento caricato/)).toBeInTheDocument();
  });

  it("shows event count", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText(/3 eventi/)).toBeInTheDocument();
  });

  it("renders skeleton when isLoading", () => {
    const { container } = render(<LiveActivityFeed events={[]} isLoading={true} />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders tag badges", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText("CRITICO")).toBeInTheDocument();
    expect(screen.getByText("PAGATO")).toBeInTheDocument();
  });

  it("renders event timestamps", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText("14:52")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/__tests__/LiveActivityFeed.test.tsx 2>&1 | tail -10
```

Expected: `FAIL`.

- [ ] **Step 3: Create LiveActivityFeed.tsx**

Create `apps/mouth/src/components/dashboard/LiveActivityFeed.tsx`:

```typescript
"use client";

import React from "react";
import type { LiveActivityEvent } from "@/types/dashboard-role.types";

const TYPE_BORDER: Record<LiveActivityEvent["type"], string> = {
  critical: "border-l-[#c45c78] bg-[rgba(196,92,120,0.045)]",
  ok:       "border-l-[#5cb88a] bg-[rgba(92,184,138,0.045)]",
  warning:  "border-l-[#b89a40] bg-[rgba(184,154,64,0.045)]",
  info:     "border-l-[#4a8ec4] bg-[rgba(74,142,196,0.045)]",
  live:     "border-l-[#48be9b] bg-[rgba(72,190,155,0.045)]",
};

const TAG_COLOR: Record<LiveActivityEvent["type"], string> = {
  critical: "bg-[rgba(196,92,120,0.16)] text-[#c45c78]",
  ok:       "bg-[rgba(92,184,138,0.16)]  text-[#5cb88a]",
  warning:  "bg-[rgba(184,154,64,0.16)]  text-[#b89a40]",
  info:     "bg-[rgba(74,142,196,0.16)]  text-[#4a8ec4]",
  live:     "bg-[rgba(72,190,155,0.16)]  text-[#48be9b]",
};

interface LiveActivityFeedProps {
  events: LiveActivityEvent[];
  isLoading: boolean;
}

export function LiveActivityFeed({ events, isLoading }: LiveActivityFeedProps) {
  if (isLoading) {
    return (
      <div className="glass-base glass-teal p-3.5 col-span-3 min-h-[240px]">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded bg-white/5 animate-pulse" />
          <div className="h-3 w-24 rounded bg-white/5 animate-pulse" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-8 rounded bg-white/5 animate-pulse mb-2" />
        ))}
      </div>
    );
  }

  return (
    <div className="glass-base glass-teal p-3.5 col-span-3 min-h-[240px]"
      style={{ boxShadow: "inset 0 0 30px rgba(72,190,155,0.03)" }}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-2 h-2 rounded-full bg-[#48be9b] flex-shrink-0 live-dot-pulse"
          style={{ boxShadow: "0 0 0 2px rgba(72,190,155,0.15), 0 0 7px rgba(72,190,155,0.5)" }}
        />
        <span className="text-[10px] font-bold text-[#48be9b] tracking-[.12em]">
          LIVE ACTIVITY
        </span>
        <span className="ml-auto text-[9px] text-white/25">
          {events.length} eventi
        </span>
      </div>

      {/* Feed */}
      <div
        className="flex flex-col gap-1.5 overflow-y-auto"
        style={{ maxHeight: 160, scrollbarWidth: "thin", scrollbarColor: "rgba(72,190,155,0.2) transparent" }}
      >
        {events.map((e) => (
          <div
            key={e.id}
            className={`flex items-start gap-2 px-2.5 py-1.5 rounded-lg border-l-[2.5px] text-[11px] leading-snug ${TYPE_BORDER[e.type]}`}
          >
            <span className="text-sm flex-shrink-0 mt-px">{e.icon}</span>
            <span className="text-white/65 flex-1">
              <span dangerouslySetInnerHTML={{ __html: e.text }} />
              {e.tag && (
                <span className={`inline-block ml-1.5 px-1.5 py-px rounded text-[8px] font-semibold tracking-wider ${TAG_COLOR[e.type]}`}>
                  {e.tag}
                </span>
              )}
            </span>
            <span className="text-[9px] text-white/22 flex-shrink-0">{e.timestamp}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

> **Note on `dangerouslySetInnerHTML`:** The `e.text` field comes from the backend API, which must sanitize it. If there is any concern about XSS from the API, replace with plain `{e.text}` — bold formatting can be handled by structuring `text` as a plain string.

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/__tests__/LiveActivityFeed.test.tsx 2>&1 | tail -10
```

Expected: `PASS` — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/dashboard/LiveActivityFeed.tsx apps/mouth/src/components/dashboard/__tests__/LiveActivityFeed.test.tsx
git commit -m "feat(dashboard): add LiveActivityFeed with color-coded event types"
```

---

### Task 7: Role sub-widgets (5 components)

**Files:**

- Create: `apps/mouth/src/components/dashboard/role-widgets/ZeroRoleWidget.tsx`
- Create: `apps/mouth/src/components/dashboard/role-widgets/TeamRoleWidget.tsx`
- Create: `apps/mouth/src/components/dashboard/role-widgets/TaxRoleWidget.tsx`
- Create: `apps/mouth/src/components/dashboard/role-widgets/MarketingRoleWidget.tsx`
- Create: `apps/mouth/src/components/dashboard/role-widgets/AccountingRoleWidget.tsx`
- Create: `apps/mouth/src/components/dashboard/role-widgets/__tests__/role-widgets.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `apps/mouth/src/components/dashboard/role-widgets/__tests__/role-widgets.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ZeroRoleWidget }       from "../ZeroRoleWidget";
import { TeamRoleWidget }       from "../TeamRoleWidget";
import { TaxRoleWidget }        from "../TaxRoleWidget";
import { MarketingRoleWidget }  from "../MarketingRoleWidget";
import { AccountingRoleWidget } from "../AccountingRoleWidget";

describe("ZeroRoleWidget", () => {
  it("renders revenue amount", () => {
    render(<ZeroRoleWidget metrics={{ revenue_mtd: 48200, visti_scadenza: 3, fatture_overdue: 2, agenti_count: 46, fly_uptime: 99.9 }} alerts={[]} />);
    expect(screen.getByText(/48/)).toBeInTheDocument();
  });
  it("renders critical alert for visti_scadenza > 0", () => {
    render(<ZeroRoleWidget metrics={{ revenue_mtd: 0, visti_scadenza: 3, fatture_overdue: 0, agenti_count: 0, fly_uptime: 100 }} alerts={[]} />);
    expect(screen.getByText(/3 visti/)).toBeInTheDocument();
  });
});

describe("TeamRoleWidget", () => {
  it("renders assigned practices count", () => {
    render(<TeamRoleWidget metrics={{ pratiche_assegnate: 7, prossima_scadenza: "2026-03-20", doc_mancanti: 2, clienti_assegnati: 4, stalled_count: 1 }} alerts={[]} />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });
  it("renders next deadline when present", () => {
    render(<TeamRoleWidget metrics={{ pratiche_assegnate: 0, prossima_scadenza: "2026-03-20", doc_mancanti: 0, clienti_assegnati: 0, stalled_count: 0 }} alerts={[]} />);
    expect(screen.getByText(/2026-03-20/)).toBeInTheDocument();
  });
});

describe("TaxRoleWidget", () => {
  it("renders next tax deadline", () => {
    render(<TaxRoleWidget metrics={{ clienti_compliant: 12, scadenze_7gg: 3, dichiarazioni_pending: 5, alert_pajak: 1, prossima_scadenza: "31 mar" }} alerts={[]} />);
    expect(screen.getByText(/31 mar/)).toBeInTheDocument();
  });
});

describe("MarketingRoleWidget", () => {
  it("renders subscriber delta", () => {
    render(<MarketingRoleWidget metrics={{ articoli_pubblicati: 8, articoli_in_review: 3, subscriber_delta: 42, lead_nuovi: 5 }} alerts={[]} />);
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
});

describe("AccountingRoleWidget", () => {
  it("renders overdue total", () => {
    render(<AccountingRoleWidget metrics={{ fatture_pagate_mtd: 10, fatture_overdue: 2, fatture_pending: 5, ricavi_mtd: 50000, overdue_total: 12400 }} alerts={[]} />);
    expect(screen.getByText(/12/)).toBeInTheDocument(); // 12400
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/role-widgets/__tests__/role-widgets.test.tsx 2>&1 | tail -10
```

Expected: `FAIL`.

- [ ] **Step 3: Create all 5 role widget components**

Create `apps/mouth/src/components/dashboard/role-widgets/ZeroRoleWidget.tsx`:

```typescript
"use client";
import React from "react";
import type { ZeroMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props { metrics: ZeroMetrics; alerts: RoleAlert[]; }

const ALERT_STYLE: Record<RoleAlert["type"], string> = {
  critical: "bg-[rgba(196,92,120,0.09)] border-[rgba(196,92,120,0.22)] text-[#c45c78]",
  warning:  "bg-[rgba(184,154,64,0.09)]  border-[rgba(184,154,64,0.22)]  text-[#b89a40]",
  ok:       "bg-[rgba(92,184,138,0.08)]  border-[rgba(92,184,138,0.20)]  text-[#5cb88a]",
  info:     "bg-[rgba(74,142,196,0.08)]  border-[rgba(74,142,196,0.20)]  text-[#4a8ec4]",
};

export function ZeroRoleWidget({ metrics }: Props) {
  const revenueK = (metrics.revenue_mtd / 1000).toFixed(1);
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-[#9880d8]/85 tracking-[.12em]">REVENUE · MTD</span>
      <span className="text-2xl font-black text-white leading-none tracking-tight">${revenueK}K</span>
      <span className="text-[10px] font-medium text-[#5cb88a]">▲ +12% vs last month</span>
      <div className="h-px bg-white/[0.06]" />
      {metrics.visti_scadenza > 0 && (
        <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.critical}`}>
          🚨 {metrics.visti_scadenza} visti &lt;7gg
        </div>
      )}
      {metrics.fatture_overdue > 0 && (
        <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.warning}`}>
          ⚠️ {metrics.fatture_overdue} fatture overdue
        </div>
      )}
      <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.ok}`}>
        ✓ {metrics.agenti_count} agenti attivi
      </div>
      <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.info}`}>
        📊 Fly.io {metrics.fly_uptime}%
      </div>
    </div>
  );
}
```

Create `apps/mouth/src/components/dashboard/role-widgets/TeamRoleWidget.tsx`:

```typescript
"use client";
import React from "react";
import type { TeamMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props { metrics: TeamMetrics; alerts: RoleAlert[]; }

export function TeamRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">LE MIE PRATICHE</span>
      <span className="text-2xl font-black text-[#5cb88a] leading-none">{metrics.pratiche_assegnate}</span>
      <span className="text-[10px] text-white/50">pratiche assegnate</span>
      <div className="h-px bg-white/[0.06]" />
      {metrics.prossima_scadenza && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(196,92,120,0.09)] border border-[rgba(196,92,120,0.22)] text-[9px] font-semibold text-[#c45c78]">
          ⏰ Scadenza: {metrics.prossima_scadenza}
        </div>
      )}
      {metrics.stalled_count > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.09)] border border-[rgba(184,154,64,0.22)] text-[9px] font-semibold text-[#b89a40]">
          ⚠️ {metrics.stalled_count} stalled &gt;14gg
        </div>
      )}
      {metrics.doc_mancanti > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          📄 {metrics.doc_mancanti} doc mancanti
        </div>
      )}
    </div>
  );
}
```

Create `apps/mouth/src/components/dashboard/role-widgets/TaxRoleWidget.tsx`:

```typescript
"use client";
import React from "react";
import type { TaxMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props { metrics: TaxMetrics; alerts: RoleAlert[]; }

export function TaxRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">COMPLIANCE</span>
      {metrics.prossima_scadenza && (
        <>
          <span className="text-[10px] text-white/50">Prossima scadenza</span>
          <span className="text-lg font-black text-[#c45c78] leading-none">{metrics.prossima_scadenza}</span>
        </>
      )}
      <div className="h-px bg-white/[0.06]" />
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(92,184,138,0.08)] border border-[rgba(92,184,138,0.20)] text-[9px] font-semibold text-[#5cb88a]">
        ✓ {metrics.clienti_compliant} clienti compliant
      </div>
      {metrics.scadenze_7gg > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(196,92,120,0.09)] border border-[rgba(196,92,120,0.22)] text-[9px] font-semibold text-[#c45c78]">
          🚨 {metrics.scadenze_7gg} scadenze &lt;7gg
        </div>
      )}
      {metrics.dichiarazioni_pending > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          ⏳ {metrics.dichiarazioni_pending} dichiarazioni pending
        </div>
      )}
    </div>
  );
}
```

Create `apps/mouth/src/components/dashboard/role-widgets/MarketingRoleWidget.tsx`:

```typescript
"use client";
import React from "react";
import type { MarketingMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props { metrics: MarketingMetrics; alerts: RoleAlert[]; }

export function MarketingRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">MARKETING</span>
      <span className="text-2xl font-black text-[#4a8ec4] leading-none">
        +{metrics.subscriber_delta}
      </span>
      <span className="text-[10px] text-white/50">nuovi iscritti</span>
      <div className="h-px bg-white/[0.06]" />
      {metrics.articoli_in_review > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          ✍️ {metrics.articoli_in_review} articoli in review
        </div>
      )}
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(92,184,138,0.08)] border border-[rgba(92,184,138,0.20)] text-[9px] font-semibold text-[#5cb88a]">
        📝 {metrics.articoli_pubblicati} pubblicati
      </div>
      {metrics.lead_nuovi > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(74,142,196,0.08)] border border-[rgba(74,142,196,0.20)] text-[9px] font-semibold text-[#4a8ec4]">
          🎯 {metrics.lead_nuovi} lead nuovi
        </div>
      )}
    </div>
  );
}
```

Create `apps/mouth/src/components/dashboard/role-widgets/AccountingRoleWidget.tsx`:

```typescript
"use client";
import React from "react";
import type { AccountingMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props { metrics: AccountingMetrics; alerts: RoleAlert[]; }

export function AccountingRoleWidget({ metrics }: Props) {
  const overdueK = (metrics.overdue_total / 1000).toFixed(1);
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">ACCOUNTING</span>
      <span className="text-2xl font-black text-[#c45c78] leading-none">{metrics.fatture_overdue}</span>
      <span className="text-[10px] text-white/50">fatture overdue</span>
      <div className="h-px bg-white/[0.06]" />
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(196,92,120,0.09)] border border-[rgba(196,92,120,0.22)] text-[9px] font-semibold text-[#c45c78]">
        💰 ${overdueK}K totale overdue
      </div>
      {metrics.fatture_pending > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          ⏳ {metrics.fatture_pending} pending
        </div>
      )}
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(92,184,138,0.08)] border border-[rgba(92,184,138,0.20)] text-[9px] font-semibold text-[#5cb88a]">
        ✓ {metrics.fatture_pagate_mtd} pagate (MTD)
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/role-widgets/__tests__/role-widgets.test.tsx 2>&1 | tail -10
```

Expected: `PASS` — 7 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/dashboard/role-widgets/
git commit -m "feat(dashboard): add 5 role-specific widgets (Zero, Team, Tax, Marketing, Accounting)"
```

---

### Task 8: RoleWidget dispatcher

**Files:**

- Create: `apps/mouth/src/components/dashboard/RoleWidget.tsx`
- Create: `apps/mouth/src/components/dashboard/__tests__/RoleWidget.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `apps/mouth/src/components/dashboard/__tests__/RoleWidget.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoleWidget } from "../RoleWidget";

// Mock useRoleMetrics to avoid real API calls
vi.mock("@/hooks/useRoleMetrics", () => ({
  useRoleMetrics: vi.fn(() => ({
    data: {
      role: "zero",
      metrics: { revenue_mtd: 48200, visti_scadenza: 3, fatture_overdue: 2, agenti_count: 46, fly_uptime: 99.9 },
      alerts: [],
    },
    isLoading: false,
    isError: false,
  })),
}));

describe("RoleWidget", () => {
  it("renders violet glass card wrapper", () => {
    const { container } = render(<RoleWidget role="zero" userId="user-1" />);
    expect(container.firstChild).toHaveClass("glass-violet");
  });

  it("renders REVENUE label for Zero role", () => {
    render(<RoleWidget role="zero" userId="user-1" />);
    expect(screen.getByText("REVENUE · MTD")).toBeInTheDocument();
  });

  it("renders skeleton when loading", () => {
    const { useRoleMetrics } = require("@/hooks/useRoleMetrics");
    useRoleMetrics.mockReturnValueOnce({ data: undefined, isLoading: true, isError: false });
    const { container } = render(<RoleWidget role="team" userId="user-2" />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders error state on failure", () => {
    const { useRoleMetrics } = require("@/hooks/useRoleMetrics");
    useRoleMetrics.mockReturnValueOnce({ data: undefined, isLoading: false, isError: true });
    render(<RoleWidget role="team" userId="user-2" />);
    expect(screen.getByText(/errore/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/__tests__/RoleWidget.test.tsx 2>&1 | tail -10
```

Expected: `FAIL`.

- [ ] **Step 3: Create RoleWidget.tsx**

Create `apps/mouth/src/components/dashboard/RoleWidget.tsx`:

```typescript
"use client";

import React from "react";
import type { DashboardRole } from "@/lib/dashboard-role";
import { useRoleMetrics } from "@/hooks/useRoleMetrics";
import { ZeroRoleWidget }       from "./role-widgets/ZeroRoleWidget";
import { TeamRoleWidget }       from "./role-widgets/TeamRoleWidget";
import { TaxRoleWidget }        from "./role-widgets/TaxRoleWidget";
import { MarketingRoleWidget }  from "./role-widgets/MarketingRoleWidget";
import { AccountingRoleWidget } from "./role-widgets/AccountingRoleWidget";

interface RoleWidgetProps {
  role: DashboardRole;
  userId: string;
}

export function RoleWidget({ role, userId }: RoleWidgetProps) {
  const { data, isLoading, isError } = useRoleMetrics(role, userId);

  return (
    <div
      className="glass-base glass-violet p-3.5 flex flex-col gap-2"
      style={{ background: "linear-gradient(145deg, rgba(110,85,210,0.10) 0%, rgba(60,35,150,0.06) 100%)" }}
    >
      {isLoading && (
        <>
          <div className="h-3 w-20 rounded bg-white/5 animate-pulse" />
          <div className="h-6 w-16 rounded bg-white/5 animate-pulse" />
          <div className="h-3 w-24 rounded bg-white/5 animate-pulse" />
          <div className="h-px bg-white/5" />
          {[1, 2, 3].map((i) => <div key={i} className="h-7 rounded bg-white/5 animate-pulse" />)}
        </>
      )}

      {isError && (
        <p className="text-[10px] text-[#c45c78]">Errore nel caricamento dati.</p>
      )}

      {!isLoading && !isError && data && (
        <>
          {data.role === "zero"       && <ZeroRoleWidget       metrics={data.metrics} alerts={data.alerts} />}
          {data.role === "team"       && <TeamRoleWidget        metrics={data.metrics} alerts={data.alerts} />}
          {data.role === "tax"        && <TaxRoleWidget         metrics={data.metrics} alerts={data.alerts} />}
          {data.role === "marketing"  && <MarketingRoleWidget   metrics={data.metrics} alerts={data.alerts} />}
          {data.role === "accounting" && <AccountingRoleWidget  metrics={data.metrics} alerts={data.alerts} />}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd apps/mouth && npx vitest run src/components/dashboard/__tests__/RoleWidget.test.tsx 2>&1 | tail -10
```

Expected: `PASS` — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/dashboard/RoleWidget.tsx apps/mouth/src/components/dashboard/__tests__/RoleWidget.test.tsx
git commit -m "feat(dashboard): add RoleWidget dispatcher (renders correct sub-widget per role)"
```

---

## Chunk 3: Dashboard Page Wiring + Barrel Update

### Task 9: Update dashboard component barrel export

**Files:**

- Modify: `apps/mouth/src/components/dashboard/index.ts`

- [ ] **Step 1: Add new exports to index.ts**

Open `apps/mouth/src/components/dashboard/index.ts` and append:

```typescript
export { DashboardStatCard } from "./DashboardStatCard";
export { LiveActivityFeed } from "./LiveActivityFeed";
export { RoleWidget } from "./RoleWidget";
```

Do NOT remove any existing exports — they are used by other pages.

- [ ] **Step 2: Verify no import errors**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -v "eclipse-concept" | grep -v "validator.ts" | head -20
```

Expected: no new errors from dashboard components.

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/dashboard/index.ts
git commit -m "feat(dashboard): export new dashboard components from barrel"
```

---

### Task 10: Rewrite dashboard/page.tsx with new grid

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/dashboard/page.tsx`

- [ ] **Step 1: Replace the page content**

Replace the full content of `apps/mouth/src/app/(workspace)/dashboard/page.tsx` with:

```typescript
"use client";

import React from "react";
import { RefreshCw } from "lucide-react";
import {
  PratichePreview,
  NusantaraHealthWidget,
  LiveActivityFeed,
  RoleWidget,
  DashboardStatCard,
} from "@/components/dashboard";
import type { PraticaPreview } from "@/components/dashboard";
import { DashboardErrorBoundary } from "@/components/ErrorBoundary";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useRealtime } from "@/lib/realtime";
import { useQueryClient } from "@tanstack/react-query";
import { normalizeDashboardRole } from "@/lib/dashboard-role";
import type { LiveActivityEvent, DashboardStatConfig } from "@/types/dashboard-role.types";
import { logger } from "@/lib/logger";

export default function DashboardPage() {
  const {
    user,
    stats,
    practices,
    isZero,
    isLoading,
    isError,
    error,
    refetch,
  } = useDashboardData();

  const realtime = useRealtime();
  const queryClient = useQueryClient();
  const role = normalizeDashboardRole(user?.role, user?.is_admin ?? false);

  // Bridge WebSocket → React Query invalidation
  React.useEffect(() => {
    const unsubscribe = realtime.subscribe("dashboard_update", () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    });
    return unsubscribe;
  }, [realtime, queryClient]);

  // Connect WebSocket on user load
  React.useEffect(() => {
    if (user?.email && !isLoading) {
      realtime.connect(user.email, user.email);
      logger.info("Dashboard loaded", {
        component: "DashboardPage",
        action: "mount",
        user: user.email,
      });
    }
  }, [user?.email, isLoading]);

  // ── Loading skeleton ──────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="p-2.5 grid grid-cols-4 gap-2">
        <div className="col-span-3 h-[240px] rounded-xl bg-white/[0.025] animate-pulse" />
        <div className="col-span-1 h-[240px] rounded-xl bg-white/[0.025] animate-pulse" />
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 rounded-xl bg-white/[0.025] animate-pulse" />
        ))}
        <div className="col-span-3 h-[180px] rounded-xl bg-white/[0.025] animate-pulse" />
        <div className="col-span-1 h-[180px] rounded-xl bg-white/[0.025] animate-pulse" />
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────
  if (isError) {
    return (
      <div className="p-4 rounded-xl border border-[#c45c78]/25 bg-[rgba(196,92,120,0.06)]">
        <h3 className="font-semibold text-[#c45c78]">Dashboard Error</h3>
        <p className="text-sm text-[#c45c78]/70 mt-1">
          Failed to load dashboard data.
        </p>
        <button
          onClick={() => refetch()}
          className="mt-3 px-4 py-2 bg-[#c45c78] text-white rounded-lg hover:opacity-90 transition-opacity inline-flex items-center gap-2 text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  // ── Build live feed events from practices ─────────────────────
  const liveEvents: LiveActivityEvent[] = React.useMemo(() => {
    return practices.slice(0, 8).map((p, i): LiveActivityEvent => ({
      id: String(p.id),
      type: p.status === "completed" ? "ok"
           : p.daysRemaining !== undefined && p.daysRemaining < 7 ? "critical"
           : p.status === "documents" ? "warning"
           : "info",
      icon: p.status === "completed" ? "✅"
           : p.daysRemaining !== undefined && p.daysRemaining < 7 ? "🚨"
           : p.status === "documents" ? "📄"
           : "📁",
      text: `<strong>${p.client}</strong> · ${p.title || p.status}`,
      tag: p.status === "completed" ? "COMPLETATA"
          : p.daysRemaining !== undefined && p.daysRemaining < 7 ? "URGENTE"
          : p.status === "documents" ? "DOCUMENTI"
          : undefined,
      timestamp: new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" }),
      userId: user?.email,
    }));
  }, [practices, user?.email]);

  // ── Build stat cards per role ─────────────────────────────────
  const statCards: DashboardStatConfig[] = React.useMemo(() => {
    if (isZero) {
      return [
        { icon: "📁", value: stats.activeCases,       label: "Pratiche Attive",   trend: "▲ team",          colorVariant: "green"  },
        { icon: "⏰", value: stats.criticalDeadlines, label: "Scadenze Critiche", trend: "alert attivi",    colorVariant: "red"    },
        { icon: "💰", value: "—",                     label: "Fatture Pending",   trend: "vedi accounting", colorVariant: "yellow" },
        { icon: "🤖", value: "46",                    label: "Agenti AI",         trend: "100% uptime",     colorVariant: "blue"   },
      ];
    }
    if (role === "accounting") {
      return [
        { icon: "✅", value: "—", label: "Pagate MTD",      trend: "vedi metriche", colorVariant: "green"  },
        { icon: "🔴", value: "—", label: "Overdue",         trend: "urgente",       colorVariant: "red"    },
        { icon: "⏳", value: "—", label: "Pending",         trend: "in attesa",     colorVariant: "yellow" },
        { icon: "💶", value: "—", label: "Ricavi MTD",      trend: "mese corrente", colorVariant: "blue"   },
      ];
    }
    if (role === "tax") {
      return [
        { icon: "✅", value: "—", label: "Clienti Compliant",    trend: "aggiornato",  colorVariant: "green"  },
        { icon: "⏰", value: "—", label: "Scadenze <7gg",        trend: "urgente",     colorVariant: "red"    },
        { icon: "📋", value: "—", label: "Dichiarazioni Pending", trend: "in coda",    colorVariant: "yellow" },
        { icon: "📌", value: "—", label: "Alert Pajak",          trend: "da verificare", colorVariant: "blue" },
      ];
    }
    if (role === "marketing") {
      return [
        { icon: "📝", value: "—", label: "Articoli Pubblicati", trend: "questo mese",  colorVariant: "green"  },
        { icon: "✍️", value: "—", label: "In Review",           trend: "in coda",      colorVariant: "red"    },
        { icon: "📧", value: "—", label: "Iscritti Newsletter", trend: "delta",         colorVariant: "yellow" },
        { icon: "🎯", value: "—", label: "Lead Nuovi",          trend: "questa settimana", colorVariant: "blue" },
      ];
    }
    // Default: team
    return [
      { icon: "📁", value: stats.activeCases,       label: "Mie Pratiche",    trend: "assegnate",   colorVariant: "green"  },
      { icon: "⏰", value: stats.criticalDeadlines, label: "Stalled >14gg",   trend: "da sbloccare", colorVariant: "red"    },
      { icon: "📄", value: "—",                     label: "Doc Mancanti",    trend: "da caricare", colorVariant: "yellow" },
      { icon: "👥", value: "—",                     label: "Clienti Assegnati", trend: "attivi",    colorVariant: "blue"   },
    ];
  }, [isZero, role, stats]);

  return (
    <DashboardErrorBoundary>
      {/* Liquid background */}
      <div className="relative dash-liquid-bg">
        <div
          className="p-2.5 grid gap-2"
          style={{ gridTemplateColumns: "1fr 1fr 1fr 1fr" }}
        >
          {/* ── ROW 1: Live Activity (3/4) + Role Widget (1/4) ── */}
          <LiveActivityFeed events={liveEvents} isLoading={isLoading} />

          <RoleWidget role={role} userId={user?.email ?? ""} />

          {/* ── ROW 2: 4 Stat Cards ── */}
          {statCards.map((card) => (
            <DashboardStatCard key={card.label} {...card} />
          ))}

          {/* ── ROW 3: Pratiche (1.6fr) + Health (1fr) + Intel (1fr) ── */}
          <div
            className="col-span-4 grid gap-2"
            style={{ gridTemplateColumns: "1.6fr 1fr 1fr" }}
          >
            {/* Pratiche Pipeline */}
            <PratichePreview
              pratiche={practices.map(
                (p): PraticaPreview => ({
                  id: p.id,
                  title: p.title || "Unknown",
                  client: p.client || "Unknown Client",
                  status: p.status,
                  daysRemaining: p.daysRemaining,
                  completedAt:
                    p.status === "completed"
                      ? new Date().toLocaleDateString()
                      : undefined,
                }),
              )}
              isLoading={isLoading}
            />

            {/* Center: System Health for Zero, placeholder for others */}
            {isZero ? (
              <NusantaraHealthWidget />
            ) : (
              <div className="glass-base glass-blue p-3.5">
                <h4 className="text-[9px] font-bold text-[#4a8ec4]/65 tracking-[.1em] mb-2.5">
                  PROSSIMI STEP
                </h4>
                <p className="text-[10px] text-white/35">Journey steps in arrivo</p>
              </div>
            )}

            {/* Right: Regulatory Intel */}
            <div className="glass-base glass-blue p-3.5">
              <h4 className="text-[9px] font-bold text-[#4a8ec4]/65 tracking-[.1em] mb-2.5">
                REGULATORY INTEL
              </h4>
              <div className="flex flex-col gap-2">
                {[
                  "Nuova circolare Imigrasi KITAS B211A",
                  "PPh deadline 31 marzo — 8 clienti",
                  "KBLI 2025 — 3 pratiche da aggiornare",
                ].map((item) => (
                  <div key={item} className="flex gap-2 text-[10px] text-white/55 leading-snug border-b border-white/[0.04] pb-1.5 last:border-0">
                    <span className="text-[#4a8ec4] flex-shrink-0">📌</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardErrorBoundary>
  );
}
```

> **Note:** The Regulatory Intel widget uses hardcoded placeholder strings for now. In a follow-up task, replace with a `RegulatoryIntelWidget` component backed by a real API endpoint. This is intentional — the spec marks it as a backend task separate from the frontend redesign.

- [ ] **Step 2: Verify the page compiles**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -v "eclipse-concept" | grep -v "validator.ts" | head -30
```

Expected: no new TypeScript errors from the dashboard page.

- [ ] **Step 3: Start dev server and visually verify**

```bash
cd apps/mouth && npm run dev &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard
```

Expected: `200` or `307` (redirect to login — normal for unauthenticated local dev).

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/dashboard/page.tsx
git commit -m "feat(dashboard): rewrite dashboard page with Asymmetric Hero grid and member-centric layout"
```

---

### Task 11: Remove WhatsAppPreview from dashboard (cleanup)

**Files:**

- No file deletion — `WhatsAppPreview.tsx` stays, it's used elsewhere. Only the import is removed from `page.tsx` (already done in Task 10).

- [ ] **Step 1: Confirm WhatsAppPreview is no longer imported in dashboard/page.tsx**

```bash
grep -n "WhatsApp" apps/mouth/src/app/\(workspace\)/dashboard/page.tsx
```

Expected: no output (no WhatsApp imports or usage).

- [ ] **Step 2: Confirm WhatsAppPreview still exists for other uses**

```bash
ls apps/mouth/src/components/dashboard/WhatsAppPreview.tsx
```

Expected: file exists.

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "chore(dashboard): WhatsAppPreview removed from dashboard page (kept for CRM)"
```

---

### Task 12: Final verification and push

- [ ] **Step 1: Run full test suite for mouth app**

```bash
cd apps/mouth && npx vitest run 2>&1 | tail -20
```

Expected: existing tests pass, new tests pass. Pre-existing failures in unrelated tests are acceptable (see CLAUDE.md §14 — known test debt).

- [ ] **Step 2: Check for console.log statements in new files (Golden Rule)**

```bash
grep -rn "console\." apps/mouth/src/components/dashboard/LiveActivityFeed.tsx \
  apps/mouth/src/components/dashboard/RoleWidget.tsx \
  apps/mouth/src/components/dashboard/DashboardStatCard.tsx \
  apps/mouth/src/components/dashboard/role-widgets/ \
  apps/mouth/src/hooks/useRoleMetrics.ts \
  apps/mouth/src/lib/dashboard-role.ts 2>/dev/null
```

Expected: no output.

- [ ] **Step 3: Push to origin**

```bash
git push origin main
```

Expected: push succeeds, Vercel auto-deploy triggered.

- [ ] **Step 4: Wait for Vercel deploy and smoke-test**

```bash
sleep 60
curl -s -o /dev/null -w "%{http_code}" https://kita.balizero.com
```

Expected: `200` or `307`.

---

## Backend Tasks (separate PR, out of scope for this plan)

The following backend changes are **required** for live data in the new widgets but are not part of this frontend plan. They should be implemented in a separate task:

1. `GET /api/dashboard/role-metrics?role=<role>&user_id=<id>` — returns `RoleWidgetData` JSON
2. `GET /api/dashboard/summary?user_id=<id>` — extend existing endpoint to filter by user
3. WebSocket per-user channels: `dashboard-user-{userId}` for members, `dashboard-all` for Zero
4. `RegulatoryIntelWidget` backend feed

Until these are live, the `useRoleMetrics` hook will return errors gracefully (error state shown), and `LiveActivityFeed` will be populated from `practices` data (as implemented in Task 10).
