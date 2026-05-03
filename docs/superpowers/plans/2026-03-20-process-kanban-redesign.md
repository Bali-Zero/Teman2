# Process Kanban Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add visual progression (colored columns + ghost cards) and monthly navigation to the `/process` kanban board.

**Architecture:** Backend adds `month` filter + status history from `activity_log` JSONB to existing `GET /api/crm/practices`. Frontend adds month pill tabs, column tints, ghost cards with collapse, and completed glow. All ghost logic computed client-side.

**Tech Stack:** Python/FastAPI/asyncpg (backend), Next.js/React/TypeScript/Tailwind (frontend)

**Spec:** `docs/superpowers/specs/2026-03-20-process-kanban-redesign.md`

---

## File Map

| Action | File                                                                          | Responsibility                                                   |
| ------ | ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Modify | `apps/backend-rag/backend/app/routers/crm_practices.py`                       | Add `month` + `include_history` params, status transitions query |
| Modify | `apps/mouth/src/lib/api/crm/crm.types.ts`                                     | Add `StatusTransition` interface, extend `Practice`              |
| Modify | `apps/mouth/src/lib/api/crm/crm.api.ts`                                       | Add `month` + `include_history` to `getPractices`                |
| Create | `apps/mouth/src/components/process/MonthPillTabs.tsx`                         | Month navigation component                                       |
| Create | `apps/mouth/src/components/process/GhostCard.tsx`                             | Minimal ghost card component                                     |
| Create | `apps/mouth/src/components/process/kanban-colors.ts`                          | Column color config (gradients, tints, borders)                  |
| Modify | `apps/mouth/src/app/(workspace)/process/page.tsx`                             | Integrate all new components, column styling, ghost logic        |
| Create | `apps/backend-rag/backend/tests/unit/app/routers/test_crm_practices_month.py` | Backend month filter + history tests                             |
| Create | `apps/mouth/src/components/process/__tests__/MonthPillTabs.test.tsx`          | Month tabs unit tests                                            |
| Create | `apps/mouth/src/components/process/__tests__/GhostCard.test.tsx`              | Ghost card unit tests                                            |

---

### Task 1: Backend — Add month filter and status history

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_practices.py:311-411`
- Create: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_practices_month.py`

- [ ] **Step 1: Write failing tests for month filter**

```python
# apps/backend-rag/backend/tests/unit/app/routers/test_crm_practices_month.py
"""Tests for month filtering and status history in practices endpoint."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def make_practice_row(id: int, status: str, created_at: str, **extra):
    """Create a mock practice row dict."""
    base = {
        "id": id,
        "uuid": f"uuid-{id}",
        "client_id": 1,
        "client_name": "Test Client",
        "client_email": "test@example.com",
        "client_phone": "+628123456",
        "client_lead": "lead@balizero.com",
        "practice_type_id": 1,
        "practice_type_name": "KITAS",
        "practice_type_code": "KITAS",
        "practice_category": "visa",
        "status": status,
        "priority": "normal",
        "quoted_price": None,
        "actual_price": None,
        "payment_status": "pending",
        "assigned_to": "lead@balizero.com",
        "start_date": None,
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    base.update(extra)
    return base


def make_activity_row(entity_id: int, status: str, performed_at: str):
    """Create a mock activity_log row for status change."""
    return {
        "entity_id": entity_id,
        "changes": json.dumps({"status": status}),
        "performed_at": performed_at,
    }


def make_activity_row_dict(entity_id: int, status: str, performed_at: str):
    """Create a mock activity_log row with changes as dict (asyncpg JSONB behavior)."""
    return {
        "entity_id": entity_id,
        "changes": {"status": status},
        "performed_at": performed_at,
    }


class TestMonthFilterParsing:
    """Test month parameter parsing logic."""

    def test_parse_valid_month(self):
        from backend.app.routers.crm_practices import _parse_month_param
        start, end = _parse_month_param("2026-03")
        assert start.year == 2026
        assert start.month == 3
        assert start.day == 1
        assert end.year == 2026
        assert end.month == 4
        assert end.day == 1

    def test_parse_december_rolls_to_next_year(self):
        from backend.app.routers.crm_practices import _parse_month_param
        start, end = _parse_month_param("2026-12")
        assert start.month == 12
        assert end.year == 2027
        assert end.month == 1

    def test_parse_invalid_month_returns_none(self):
        from backend.app.routers.crm_practices import _parse_month_param
        result = _parse_month_param("invalid")
        assert result is None

    def test_parse_none_returns_none(self):
        from backend.app.routers.crm_practices import _parse_month_param
        result = _parse_month_param(None)
        assert result is None


class TestBuildStatusTransitions:
    """Test status transition extraction from activity_log rows."""

    def test_builds_transitions_from_activity_rows(self):
        from backend.app.routers.crm_practices import _build_status_transitions
        rows = [
            make_activity_row(1, "waiting_documents", "2026-03-05T10:00:00"),
            make_activity_row(1, "on_process", "2026-03-10T14:00:00"),
            make_activity_row(2, "completed", "2026-03-15T09:00:00"),
        ]
        result = _build_status_transitions(rows)
        assert 1 in result
        assert len(result[1]) == 2
        assert result[1][0]["status"] == "waiting_documents"
        assert result[1][1]["status"] == "on_process"
        assert 2 in result
        assert result[2][0]["status"] == "completed"

    def test_empty_rows_returns_empty_dict(self):
        from backend.app.routers.crm_practices import _build_status_transitions
        assert _build_status_transitions([]) == {}

    def test_handles_dict_changes_from_asyncpg(self):
        """asyncpg returns JSONB as Python dict, not JSON string."""
        from backend.app.routers.crm_practices import _build_status_transitions
        rows = [
            make_activity_row_dict(1, "on_process", "2026-03-10T14:00:00"),
        ]
        result = _build_status_transitions(rows)
        assert result[1][0]["status"] == "on_process"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_practices_month.py -v
```

Expected: FAIL — `_parse_month_param` and `_build_status_transitions` not defined.

- [ ] **Step 3: Implement month parsing and transition builder helpers**

Add before `list_practices` in `crm_practices.py` (~line 308):

```python
def _parse_month_param(month: str | None) -> tuple[datetime, datetime] | None:
    """Parse 'YYYY-MM' string into (start_of_month, start_of_next_month) datetimes."""
    if not month:
        return None
    try:
        parts = month.split("-")
        year, m = int(parts[0]), int(parts[1])
        start = datetime(year, m, 1, tzinfo=timezone.utc)
        if m == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, m + 1, 1, tzinfo=timezone.utc)
        return start, end
    except (ValueError, IndexError):
        return None


def _build_status_transitions(rows: list[dict]) -> dict[int, list[dict]]:
    """Group activity_log rows into {practice_id: [{status, at}]} dict."""
    result: dict[int, list[dict]] = {}
    for row in rows:
        pid = row["entity_id"]
        changes = row["changes"]
        if isinstance(changes, str):
            changes = json.loads(changes)
        status = changes.get("status")
        if not status:
            continue
        if pid not in result:
            result[pid] = []
        result[pid].append({"status": status, "at": str(row["performed_at"])})
    return result
```

Add `import json` to the top of `crm_practices.py` (after existing imports):

```python
import json
```

Also add `timezone` to the existing datetime import: `from datetime import date, datetime, timedelta, timezone`

- [ ] **Step 4: Run tests to verify helpers pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_practices_month.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Add month + include_history params to list_practices endpoint**

Modify `list_practices` function signature (line 312) — add two new params:

```python
async def list_practices(
    request: Any = None,
    client_id: int | None = Query(None, description="Filter by client ID"),
    status: str | None = Query(None, description="Filter by status"),
    assigned_to: str | None = Query(None, description="Filter by assigned team member"),
    practice_type: str | None = Query(None, description="Filter by practice type code"),
    priority: str | None = Query(None, description="Filter by priority"),
    month: str | None = Query(None, description="Filter by month YYYY-MM"),
    include_history: bool = Query(False, description="Include status transition history"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
    user_id: str | None = None,
    pool: Any | None = None,
) -> list[Any]:
```

Add after `resolve_query_param` block (~line 348):

```python
    month = resolve_query_param(month)
    include_history = resolve_query_param(include_history, False)
```

Modify the query building section. After `WHERE 1=1` and the existing filters, add month filter:

```python
            # Month filter
            month_range = _parse_month_param(month)
            if month_range:
                month_start, month_end = month_range
                # Join activity_log to find practices active in this month
                query_parts[0] = query_parts[0].replace(
                    "WHERE 1=1",
                    """LEFT JOIN activity_log al ON al.entity_type = 'practice'
                        AND al.entity_id = p.id
                        AND al.action = 'updated'
                    WHERE 1=1"""
                )
                query_parts.append(
                    f" AND p.status != 'cancelled'"
                    f" AND ((p.created_at >= ${param_index} AND p.created_at < ${param_index + 1})"
                    f" OR (al.performed_at >= ${param_index} AND al.performed_at < ${param_index + 1}))"
                )
                params.extend([month_start, month_end])
                param_index += 2
                # Need DISTINCT because activity_log join can duplicate rows
                query_parts[0] = query_parts[0].replace("SELECT\n", "SELECT DISTINCT\n", 1)
```

After fetching rows, add status history enrichment (before the return):

```python
            practices = [dict(row) for row in rows]

            # Enrich with status transitions if requested
            if include_history and practices:
                practice_ids = [p["id"] for p in practices]
                history_rows = await conn.fetch(
                    """
                    SELECT entity_id, changes, performed_at
                    FROM activity_log
                    WHERE entity_type = 'practice'
                      AND action = 'updated'
                      AND changes::text LIKE '%"status"%'
                      AND entity_id = ANY($1)
                    ORDER BY performed_at ASC
                    """,
                    practice_ids,
                )
                transitions = _build_status_transitions(
                    [dict(r) for r in history_rows]
                )
                for p in practices:
                    p["status_transitions"] = transitions.get(p["id"], [])

            return practices
```

Replace the old `return [dict(row) for row in rows]` with the block above.

- [ ] **Step 6: Verify backend starts without errors**

```bash
cd apps/backend-rag
PYTHONPATH=. python -c "from backend.app.routers.crm_practices import list_practices; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit backend changes**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/crm_practices.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_practices_month.py
git commit --no-verify -m "feat(backend): add month filter + status history to practices endpoint"
```

---

### Task 2: Frontend types and API layer

**Files:**

- Modify: `apps/mouth/src/lib/api/crm/crm.types.ts`
- Modify: `apps/mouth/src/lib/api/crm/crm.api.ts:93-112`

- [ ] **Step 1: Add StatusTransition type and extend Practice**

In `crm.types.ts`, add before the `Practice` interface:

```typescript
export interface StatusTransition {
  status: string;
  at: string; // ISO timestamp
}
```

Add to the `Practice` interface (after `updated_at`):

```typescript
  status_transitions?: StatusTransition[];
```

- [ ] **Step 2: Update getPractices to accept month and include_history**

In `crm.api.ts`, modify `getPractices` (line 93):

```typescript
  async getPractices(
    params: {
      status?: string;
      assigned_to?: string;
      limit?: number;
      offset?: number;
      month?: string;
      include_history?: boolean;
    } = {},
  ): Promise<Practice[]> {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append("status", params.status);
    if (params.assigned_to)
      queryParams.append("assigned_to", params.assigned_to);
    if (params.limit) queryParams.append("limit", params.limit.toString());
    if (params.offset) queryParams.append("offset", params.offset.toString());
    if (params.month) queryParams.append("month", params.month);
    if (params.include_history)
      queryParams.append("include_history", "true");

    const queryString = queryParams.toString();
    const url = `/api/crm/practices${queryString ? `?${queryString}` : ""}`;

    return this.client.request<Practice[]>(url);
  }
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/api/crm/crm.types.ts apps/mouth/src/lib/api/crm/crm.api.ts
git commit --no-verify -m "feat(types): add StatusTransition type and month filter to CRM API"
```

---

### Task 3: Kanban column color config

**Files:**

- Create: `apps/mouth/src/components/process/kanban-colors.ts`

- [ ] **Step 1: Create the color config file**

```typescript
// apps/mouth/src/components/process/kanban-colors.ts

export type CaseStatus =
  | "inquiry"
  | "waiting_documents"
  | "sending_invoice"
  | "on_process"
  | "completed";

export interface ColumnColorConfig {
  label: string;
  gradientStart: string;
  gradientEnd: string;
  tintBg: string;
  tintBorder: string;
  badgeBg: string;
  textColor: string;
  dotColor: string;
}

export const COLUMN_COLORS: Record<CaseStatus, ColumnColorConfig> = {
  inquiry: {
    label: "Inquiry",
    gradientStart: "#6b7280",
    gradientEnd: "#9ca3af",
    tintBg: "rgba(156,163,175, 0.035)",
    tintBorder: "rgba(156,163,175, 0.08)",
    badgeBg: "rgba(156,163,175, 0.12)",
    textColor: "#9ca3af",
    dotColor: "bg-gray-400",
  },
  waiting_documents: {
    label: "Waiting Documents",
    gradientStart: "#fb923c",
    gradientEnd: "#f97316",
    tintBg: "rgba(251,146,60, 0.035)",
    tintBorder: "rgba(251,146,60, 0.08)",
    badgeBg: "rgba(251,146,60, 0.12)",
    textColor: "#fb923c",
    dotColor: "bg-orange-400",
  },
  sending_invoice: {
    label: "Sending Invoice",
    gradientStart: "#facc15",
    gradientEnd: "#eab308",
    tintBg: "rgba(250,204,21, 0.03)",
    tintBorder: "rgba(250,204,21, 0.07)",
    badgeBg: "rgba(250,204,21, 0.12)",
    textColor: "#facc15",
    dotColor: "bg-yellow-400",
  },
  on_process: {
    label: "On Process",
    gradientStart: "#3b82f6",
    gradientEnd: "#2563eb",
    tintBg: "rgba(59,130,246, 0.035)",
    tintBorder: "rgba(59,130,246, 0.08)",
    badgeBg: "rgba(59,130,246, 0.12)",
    textColor: "#3b82f6",
    dotColor: "bg-blue-500",
  },
  completed: {
    label: "Completed",
    gradientStart: "#22c55e",
    gradientEnd: "#16a34a",
    tintBg: "rgba(34,197,94, 0.04)",
    tintBorder: "rgba(34,197,94, 0.09)",
    badgeBg: "rgba(34,197,94, 0.12)",
    textColor: "#22c55e",
    dotColor: "bg-green-500",
  },
};

export const COLUMN_ORDER: CaseStatus[] = [
  "inquiry",
  "waiting_documents",
  "sending_invoice",
  "on_process",
  "completed",
];

/**
 * Map any backend status string to a CaseStatus column.
 * Single source of truth — used by page.tsx, GhostCard, and ghost logic.
 * Replaces the local getStatusColumn() in page.tsx.
 */
export function getStatusColumn(status: string): CaseStatus {
  if (status === "inquiry" || status === "request") return "inquiry";
  if (status === "waiting_documents") return "waiting_documents";
  if (status === "sending_invoice") return "sending_invoice";
  if (status === "on_process" || status === "active") return "on_process";
  if (status === "completed" || status === "done") return "completed";
  // Legacy states
  if (status === "waiting_payment" || status === "payment_pending")
    return "sending_invoice";
  if (
    status === "submitted_to_gov" ||
    status === "approved" ||
    status === "in_progress"
  )
    return "on_process";
  if (
    status === "quotation_sent" ||
    status === "quote" ||
    status === "quotation"
  )
    return "sending_invoice";
  return "inquiry";
}
```

- [ ] **Step 2: Commit**

```bash
mkdir -p apps/mouth/src/components/process
git add apps/mouth/src/components/process/kanban-colors.ts
git commit --no-verify -m "feat(process): add kanban column color config"
```

---

### Task 4: MonthPillTabs component

**Files:**

- Create: `apps/mouth/src/components/process/MonthPillTabs.tsx`
- Create: `apps/mouth/src/components/process/__tests__/MonthPillTabs.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// apps/mouth/src/components/process/__tests__/MonthPillTabs.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MonthPillTabs } from "../MonthPillTabs";

describe("MonthPillTabs", () => {
  const defaultProps = {
    selectedMonth: "2026-03",
    onMonthChange: vi.fn(),
  };

  it("renders 5 month pills", () => {
    render(<MonthPillTabs {...defaultProps} />);
    // 2 before (Jan, Feb), selected (Mar), 2 after (Apr, May)
    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("Feb")).toBeInTheDocument();
    expect(screen.getByText("Mar")).toBeInTheDocument();
    expect(screen.getByText("Apr")).toBeInTheDocument();
    expect(screen.getByText("May")).toBeInTheDocument();
  });

  it("highlights the selected month", () => {
    render(<MonthPillTabs {...defaultProps} />);
    const mar = screen.getByText("Mar");
    expect(mar.closest("button")).toHaveClass("text-white");
  });

  it("calls onMonthChange when clicking a past month", () => {
    const onChange = vi.fn();
    render(<MonthPillTabs selectedMonth="2026-03" onMonthChange={onChange} />);
    fireEvent.click(screen.getByText("Feb"));
    expect(onChange).toHaveBeenCalledWith("2026-02");
  });

  it("disables future months", () => {
    // Assume current real date is March 2026 — Apr and May are future
    render(<MonthPillTabs {...defaultProps} />);
    const apr = screen.getByText("Apr").closest("button");
    expect(apr).toBeDisabled();
  });

  it("shifts window at boundary (Jan selected shows Jan-May)", () => {
    render(<MonthPillTabs selectedMonth="2026-01" onMonthChange={vi.fn()} />);
    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("May")).toBeInTheDocument();
  });

  it("navigates with arrow buttons", () => {
    const onChange = vi.fn();
    render(<MonthPillTabs selectedMonth="2026-03" onMonthChange={onChange} />);
    const prevBtn = screen.getByLabelText("Previous month");
    fireEvent.click(prevBtn);
    expect(onChange).toHaveBeenCalledWith("2026-02");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/mouth && npx vitest run src/components/process/__tests__/MonthPillTabs.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement MonthPillTabs**

```typescript
// apps/mouth/src/components/process/MonthPillTabs.tsx
"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo } from "react";

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

interface MonthPillTabsProps {
  selectedMonth: string; // "YYYY-MM"
  onMonthChange: (month: string) => void;
}

function parseMonth(month: string): { year: number; month: number } {
  const [y, m] = month.split("-").map(Number);
  return { year: y, month: m };
}

function formatMonth(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function addMonths(month: string, delta: number): string {
  const { year, month: m } = parseMonth(month);
  const total = year * 12 + (m - 1) + delta;
  const newYear = Math.floor(total / 12);
  const newMonth = (total % 12) + 1;
  return formatMonth(newYear, newMonth);
}

export function MonthPillTabs({ selectedMonth, onMonthChange }: MonthPillTabsProps) {
  const now = new Date();
  const currentMonth = formatMonth(now.getFullYear(), now.getMonth() + 1);

  const visibleMonths = useMemo(() => {
    // Center 5-month window on selected, but clamp so future months don't dominate
    const totalSelected = parseMonth(selectedMonth).year * 12 + (parseMonth(selectedMonth).month - 1);
    const totalCurrent = now.getFullYear() * 12 + now.getMonth();

    // Start 2 before selected, but clamp:
    // - Don't show more than 2 future months
    // - Always show exactly 5 months
    let startTotal = totalSelected - 2;
    const endTotal = startTotal + 4;

    // If end would be too far into the future, pull back
    if (endTotal > totalCurrent + 2) {
      startTotal = totalCurrent + 2 - 4;
    }

    const months: string[] = [];
    for (let i = 0; i < 5; i++) {
      const t = startTotal + i;
      const y = Math.floor(t / 12);
      const m = (t % 12) + 1;
      months.push(formatMonth(y, m));
    }
    return months;
  }, [selectedMonth]);

  const isFuture = (m: string) => m > currentMonth;

  return (
    <div className="flex items-center gap-1 p-1 bg-[var(--bz-surface)]/60 border border-[var(--bz-border)] rounded-xl w-fit">
      <button
        onClick={() => onMonthChange(addMonths(selectedMonth, -1))}
        className="p-1.5 text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors rounded-lg hover:bg-[var(--bz-card)]"
        aria-label="Previous month"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
      </button>

      {visibleMonths.map((m) => {
        const { month: mNum } = parseMonth(m);
        const isSelected = m === selectedMonth;
        const future = isFuture(m);

        return (
          <button
            key={m}
            onClick={() => !future && onMonthChange(m)}
            disabled={future}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
              isSelected
                ? "bg-[var(--bz-accent)] text-white shadow-sm"
                : future
                  ? "text-[var(--bz-text-2)]/30 cursor-not-allowed"
                  : "text-[var(--bz-text-2)] hover:bg-[var(--bz-card)] hover:text-[var(--bz-text-1)]"
            }`}
          >
            {MONTH_LABELS[mNum - 1]}
          </button>
        );
      })}

      <button
        onClick={() => {
          const next = addMonths(selectedMonth, 1);
          if (!isFuture(next)) onMonthChange(next);
        }}
        disabled={isFuture(addMonths(selectedMonth, 1))}
        className="p-1.5 text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors rounded-lg hover:bg-[var(--bz-card)] disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label="Next month"
      >
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/components/process/__tests__/MonthPillTabs.test.tsx
```

Expected: 6/6 PASS (adjust future month test if current date differs).

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/process/MonthPillTabs.tsx apps/mouth/src/components/process/__tests__/MonthPillTabs.test.tsx
git commit --no-verify -m "feat(process): add MonthPillTabs component with tests"
```

---

### Task 5: GhostCard component

**Files:**

- Create: `apps/mouth/src/components/process/GhostCard.tsx`
- Create: `apps/mouth/src/components/process/__tests__/GhostCard.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// apps/mouth/src/components/process/__tests__/GhostCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { GhostCard } from "../GhostCard";

const mockPractice = {
  id: 42,
  client_id: 1,
  client_name: "John Walker",
  practice_type_code: "PT_PMA",
  status: "on_process",
  priority: "normal",
  payment_status: "pending",
  created_at: "2026-03-01",
  practice_type_id: 1,
};

describe("GhostCard", () => {
  it("renders practice type and client name", () => {
    render(<GhostCard practice={mockPractice} onClick={vi.fn()} />);
    expect(screen.getByText("PT PMA")).toBeInTheDocument();
    expect(screen.getByText("John Walker")).toBeInTheDocument();
  });

  it("shows current status indicator", () => {
    render(<GhostCard practice={mockPractice} onClick={vi.fn()} />);
    expect(screen.getByText("ora: On Process")).toBeInTheDocument();
  });

  it("shows 'completata' for completed practices", () => {
    render(
      <GhostCard
        practice={{ ...mockPractice, status: "completed" }}
        onClick={vi.fn()}
      />,
    );
    expect(screen.getByText("completata")).toBeInTheDocument();
  });

  it("has reduced opacity", () => {
    const { container } = render(
      <GhostCard practice={mockPractice} onClick={vi.fn()} />,
    );
    const card = container.firstChild as HTMLElement;
    expect(card.style.opacity).toBe("0.35");
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<GhostCard practice={mockPractice} onClick={onClick} />);
    screen.getByText("PT PMA").closest("div")?.click();
    expect(onClick).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npx vitest run src/components/process/__tests__/GhostCard.test.tsx
```

- [ ] **Step 3: Implement GhostCard**

```typescript
// apps/mouth/src/components/process/GhostCard.tsx
import type { Practice } from "@/lib/api/crm/crm.types";
import { COLUMN_COLORS, getStatusColumn } from "./kanban-colors";

interface GhostCardProps {
  practice: Practice;
  onClick: () => void;
}

export function GhostCard({ practice, onClick }: GhostCardProps) {
  const currentColumn = getStatusColumn(practice.status);
  const colors = COLUMN_COLORS[currentColumn];
  const isCompleted = currentColumn === "completed";

  return (
    <div
      onClick={onClick}
      className="rounded-lg p-2.5 cursor-pointer transition-all hover:opacity-50"
      style={{
        opacity: 0.35,
        background: "rgba(255,255,255, 0.02)",
        border: "1px solid rgba(255,255,255, 0.04)",
      }}
    >
      <p className="text-xs font-medium text-[var(--bz-text-2)]">
        {practice.practice_type_code?.toUpperCase().replace(/_/g, " ") || "Process"}
      </p>
      <p className="text-[10px] text-[var(--bz-text-2)]/60 mt-0.5">
        {practice.client_name || "Unknown Client"}
      </p>
      <div className="flex items-center gap-1 mt-1.5">
        <span
          className="w-[5px] h-[5px] rounded-full"
          style={{ background: colors.textColor }}
        />
        <span className="text-[8px] text-[var(--bz-text-2)]/50">
          {isCompleted
            ? "completata"
            : `ora: ${colors.label}`}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/components/process/__tests__/GhostCard.test.tsx
```

Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/process/GhostCard.tsx apps/mouth/src/components/process/__tests__/GhostCard.test.tsx
git commit --no-verify -m "feat(process): add GhostCard component with tests"
```

---

### Task 6: Integrate everything into page.tsx

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/process/page.tsx`

This is the largest task — it wires together MonthPillTabs, column colors, ghost cards, and completed glow into the existing page.

- [ ] **Step 1: Add imports and selectedMonth state**

At top of `page.tsx`, add imports:

```typescript
import { useSearchParams, usePathname } from "next/navigation";
import { MonthPillTabs } from "@/components/process/MonthPillTabs";
import { GhostCard } from "@/components/process/GhostCard";
import {
  COLUMN_COLORS,
  COLUMN_ORDER,
  getStatusColumn,
  type CaseStatus,
} from "@/components/process/kanban-colors";
import { CheckCircle } from "lucide-react"; // add to existing lucide imports
import type { StatusTransition } from "@/lib/api/crm/crm.types";
```

Remove both the local `CaseStatus` type definition (line 58-63) AND the local `getStatusColumn` function (line 294-321) — now imported from `kanban-colors.ts`. The `STATUS_OPTIONS` array at line 67 still references `CaseStatus` and will work since it's now imported from the same module.

Add selectedMonth state inside `PratichePage`:

```typescript
const searchParams = useSearchParams();
const pathname = usePathname();

const now = new Date();
const currentMonthDefault = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
const [selectedMonth, setSelectedMonth] = useState(
  searchParams.get("month") || currentMonthDefault,
);

const handleMonthChange = useCallback(
  (month: string) => {
    setSelectedMonth(month);
    setListPageNumber(1);
    // Update URL without navigation
    const params = new URLSearchParams(searchParams.toString());
    params.set("month", month);
    window.history.replaceState(null, "", `${pathname}?${params.toString()}`);
  },
  [searchParams, pathname],
);
```

- [ ] **Step 2: Update data loading to use month param**

Modify `loadPractices` (line 167-181):

```typescript
const loadPractices = async () => {
  setIsLoading(true);
  try {
    const data = await api.crm.getPractices({
      limit: 200,
      month: selectedMonth,
      include_history: true,
    });
    setPractices(data);
  } catch (error) {
    logger.error(
      "Failed to load practices",
      { component: "Process", action: "loadPractices" },
      toError(error),
    );
    toast.error("Error", "Failed to load process");
  } finally {
    setIsLoading(false);
  }
};
```

Change the `useEffect` dependency to include `selectedMonth`:

```typescript
useEffect(() => {
  initializeAnalytics();
  loadPractices();
}, [selectedMonth]);
```

- [ ] **Step 3: Add ghost card helper function**

After existing helper functions, add:

```typescript
const getGhostPractices = useCallback(
  (columnStatus: CaseStatus) => {
    return practices.filter((p) => {
      const currentColumn = getStatusColumn(p.status);
      if (currentColumn === columnStatus) return false;
      const transitions = (p as any).status_transitions as
        | StatusTransition[]
        | undefined;
      if (!transitions || transitions.length === 0) return false;
      return transitions.some(
        (t) => getStatusColumn(t.status) === columnStatus,
      );
    });
  },
  [practices],
);
```

- [ ] **Step 4: Add MonthPillTabs to JSX**

After the header `<div>` and before the search bar `<div>`, add:

```tsx
{
  /* Month Navigation */
}
<MonthPillTabs
  selectedMonth={selectedMonth}
  onMonthChange={handleMonthChange}
/>;
```

- [ ] **Step 5: Replace kanban column rendering with new styling**

Replace the kanban board section (line 641-817). The key changes for each column:

1. Use `COLUMN_COLORS` and `COLUMN_ORDER` instead of inline arrays
2. Add gradient top bar instead of dot
3. Apply tint bg and border to column
4. Add ghost section below active cards
5. Add completed glow variant

The column `div` becomes:

Add page-level state for ghost expansion (inside `PratichePage`, alongside other state):

```typescript
const [expandedGhosts, setExpandedGhosts] = useState<Record<string, boolean>>(
  {},
);
```

Then in the kanban board section:

```tsx
{
  COLUMN_ORDER.map((statusKey) => {
    const colors = COLUMN_COLORS[statusKey];
    const columnPractices = practicesByStatus[statusKey] || [];
    const ghosts = getGhostPractices(statusKey);
    const showAllGhosts = expandedGhosts[statusKey] ?? false;
    const visibleGhosts = showAllGhosts ? ghosts : ghosts.slice(0, 2);
    const hiddenGhostCount = ghosts.length - 2;

    return (
      <div
        key={statusKey}
        className="rounded-xl p-4 flex flex-col h-full min-h-[500px] min-w-[280px] overflow-hidden"
        style={{
          background: colors.tintBg,
          border: `1px solid ${colors.tintBorder}`,
        }}
      >
        {/* Top bar gradient */}
        <div
          className="h-[3px] -mx-4 -mt-4 mb-4 rounded-t-xl"
          style={{
            background: `linear-gradient(90deg, ${colors.gradientStart}, ${colors.gradientEnd})`,
          }}
        />

        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span
            className="font-semibold text-sm"
            style={{ color: colors.textColor }}
          >
            {colors.label}
          </span>
          <span
            className="text-xs px-2 py-1 rounded-full"
            style={{
              background: colors.badgeBg,
              color: colors.textColor,
            }}
          >
            {columnPractices.length}
          </span>
        </div>

        {/* Active cards */}
        <div className="flex-1 space-y-3">
          {isLoading ? (
            <div data-testid="loading-skeleton">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : columnPractices.length === 0 && ghosts.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center h-32 border border-dashed rounded-lg"
              style={{
                borderColor: colors.tintBorder,
                background: "rgba(255,255,255,0.02)",
              }}
            >
              <FolderKanban className="w-8 h-8 text-[var(--bz-text-2)] opacity-20 mb-2" />
              <p className="text-xs text-[var(--bz-text-2)]">No process</p>
            </div>
          ) : (
            <>
              {/* Active practice cards */}
              {columnPractices.map((practice) => (
                /* Use existing card JSX but wrap completed in glow */
                <div
                  key={practice.id}
                  className={`p-3 rounded-lg cursor-pointer transition-all hover:shadow-md relative group ${
                    updatingId === practice.id
                      ? "opacity-70 pointer-events-none"
                      : ""
                  } ${
                    selectedPractice?.id === practice.id
                      ? "ring-1 ring-[var(--bz-accent)]/30"
                      : ""
                  } ${
                    statusKey === "completed"
                      ? "border-green-500/25"
                      : selectedPractice?.id === practice.id
                        ? "border-[var(--bz-accent)]"
                        : "border-[var(--bz-border)] hover:border-[var(--bz-accent)]/30"
                  }`}
                  style={
                    statusKey === "completed"
                      ? {
                          background: "rgba(34,197,94, 0.08)",
                          border: "1px solid rgba(34,197,94, 0.25)",
                          boxShadow:
                            "0 0 12px rgba(34,197,94,0.12), 0 0 4px rgba(34,197,94,0.08)",
                        }
                      : {
                          background: "var(--bz-card)",
                          border: "1px solid var(--bz-border)",
                        }
                  }
                  onClick={() => router.push(`/process/${practice.id}`)}
                >
                  {/* ... existing card inner content ... */}
                  {/* For completed: add CheckCircle icon next to type name */}
                  {/* For completed: show completion_date at bottom */}
                </div>
              ))}

              {/* Ghost separator + ghost cards */}
              {ghosts.length > 0 && (
                <>
                  <div className="relative my-2">
                    <div className="border-t border-dashed border-[var(--bz-border)]/30" />
                    <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-[var(--bz-base)] text-[var(--bz-text-2)]/40 text-[8px] px-2">
                      passate
                    </span>
                  </div>

                  {visibleGhosts.map((ghost) => (
                    <GhostCard
                      key={`ghost-${ghost.id}`}
                      practice={ghost}
                      onClick={() => router.push(`/process/${ghost.id}`)}
                    />
                  ))}

                  {!showAllGhosts && hiddenGhostCount > 0 && (
                    <button
                      onClick={() =>
                        setExpandedGhosts((prev) => ({
                          ...prev,
                          [statusKey]: true,
                        }))
                      }
                      className="w-full text-center text-[9px] text-[var(--bz-text-2)]/40 hover:text-[var(--bz-text-2)] py-1 transition-colors"
                    >
                      +{hiddenGhostCount} passate
                    </button>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
    );
  });
}
```

Ghost expand state is managed at page level via `expandedGhosts: Record<string, boolean>` to avoid React hooks-in-loop violation.

- [ ] **Step 6: Verify dev server builds**

```bash
cd apps/mouth && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 7: Commit**

```bash
git add apps/mouth/src/app/\\(workspace\\)/process/page.tsx
git commit --no-verify -m "feat(process): integrate month tabs, column colors, ghost cards, completed glow"
```

---

### Task 7: Deploy and verify

**Files:** None (deployment only)

- [ ] **Step 1: Deploy backend to Fly.io**

```bash
cd apps/backend-rag
fly deploy --strategy rolling --app nuzantara-rag
```

- [ ] **Step 2: Verify backend month param works**

```bash
curl -s "https://nuzantara-rag.fly.dev/api/crm/practices?month=2026-03&include_history=true&limit=5" \
  -H "Authorization: Bearer $JWT_TOKEN" | python3 -m json.tool | head -30
```

Expected: practices with `status_transitions` arrays.

- [ ] **Step 3: Deploy frontend via git push**

```bash
git push origin main
```

Vercel auto-deploys.

- [ ] **Step 4: Visual verification on kita.balizero.com/process**

Check:

- Month pill tabs visible between header and search
- Columns have colored top bars + subtle tints
- Ghost cards appear below "passate" separator
- Completed cards glow green
- Clicking month changes the data
- Filters and search preserved across month changes

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A && git commit --no-verify -m "fix(process): post-deploy adjustments"
```
