# CRM Phase 0 + Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 security/bug issues (Phase 0) and establish the foundation for CRM evolution: React Query migration, shared utilities, team API, N+1 fixes (Phase 1).

**Architecture:** Phase 0 is surgical fixes to existing files — no new files, no refactors. Phase 1 introduces shared packages in `packages/core/`, migrates the detail page to React Query, adds a team members API endpoint, and fixes N+1 queries in analytics.

**Tech Stack:** Next.js App Router, FastAPI, asyncpg, React Query (@tanstack/react-query), TypeScript, Python 3.11

**Spec:** `docs/superpowers/specs/brainstorm-crm-strategy.md`

---

## Phase 0 — Security & Bug Fix

### Task 1: Add auth to expiry-alerts/summary endpoint

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced_alerts.py:70-71`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_enhanced_alerts.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_crm_enhanced_alerts.py`:

```python
"""Tests for CRM enhanced alerts router — auth enforcement."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import asyncpg


@pytest.fixture
def mock_pool():
    pool = AsyncMock(spec=asyncpg.Pool)
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "total": 10, "expired": 2, "red": 3, "yellow": 3, "green": 2
    })
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.mark.asyncio
async def test_expiry_alerts_summary_requires_auth():
    """Endpoint must require current_user dependency."""
    from backend.app.routers.crm_enhanced_alerts import get_expiry_alerts_summary
    import inspect

    sig = inspect.signature(get_expiry_alerts_summary)
    param_names = list(sig.parameters.keys())
    assert "current_user" in param_names, (
        "get_expiry_alerts_summary must have a current_user parameter "
        f"but only has: {param_names}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_enhanced_alerts.py::test_expiry_alerts_summary_requires_auth -v`

Expected: FAIL — `current_user` not in parameters (only `pool`).

- [ ] **Step 3: Add auth dependency to endpoint**

In `apps/backend-rag/backend/app/routers/crm_enhanced_alerts.py`, change line 70-71 from:

```python
@router.get("/expiry-alerts/summary")
async def get_expiry_alerts_summary(pool: Any = Depends(get_database_pool)) -> dict[str, Any]:
```

to:

```python
@router.get("/expiry-alerts/summary")
async def get_expiry_alerts_summary(
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
```

Ensure `get_current_user` is already imported at the top of the file. If not, add:

```python
from backend.app.dependencies import get_current_user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_enhanced_alerts.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_enhanced_alerts.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_enhanced_alerts.py
git commit -m "$(cat <<'EOF'
fix(security): add auth to expiry-alerts/summary endpoint

Endpoint was exposed without authentication, leaking aggregate alert counts.
Added get_current_user dependency.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Fix soft delete to set deleted_at

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py:740-748`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients_delete.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients_delete.py`:

```python
"""Tests for CRM client soft delete — deleted_at must be set."""
import pytest


def test_delete_query_sets_deleted_at():
    """The DELETE endpoint SQL must SET deleted_at = NOW()."""
    import ast
    from pathlib import Path

    router_path = Path("backend/app/routers/crm_clients.py")
    source = router_path.read_text()

    # Find the SQL in the delete endpoint — look for the UPDATE that sets status='inactive'
    # It MUST also set deleted_at
    assert "deleted_at = NOW()" in source and "status = 'inactive'" in source, (
        "The soft delete UPDATE query must set both status='inactive' AND deleted_at=NOW(). "
        "Currently the query sets status but not deleted_at, causing deleted clients to "
        "reappear in lists filtered by WHERE deleted_at IS NULL."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients_delete.py -v`

Expected: FAIL — `deleted_at = NOW()` not in the UPDATE query.

- [ ] **Step 3: Fix the soft delete SQL**

In `apps/backend-rag/backend/app/routers/crm_clients.py`, change lines 741-746 from:

```python
            row = await conn.fetchrow(
                """
                UPDATE clients
                SET status = 'inactive', updated_at = NOW()
                WHERE id = $1
                RETURNING id
                """,
```

to:

```python
            row = await conn.fetchrow(
                """
                UPDATE clients
                SET status = 'inactive', deleted_at = NOW(), updated_at = NOW()
                WHERE id = $1 AND deleted_at IS NULL
                RETURNING id
                """,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients_delete.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients_delete.py
git commit -m "$(cat <<'EOF'
fix(crm): set deleted_at on soft delete so WHERE deleted_at IS NULL works

Previously only set status='inactive' without writing deleted_at,
causing deleted clients to reappear in list queries.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Fix portal navigation (vault + company back button)

**Files:**

- Modify: `apps/mouth/src/types/navigation.ts:98-121`
- Modify: `apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx:120-122`

- [ ] **Step 1: Add Vault to portal navigation**

In `apps/mouth/src/types/navigation.ts`, add the Vault entry to the portal navigation. Change the first section (lines 100-104) from:

```typescript
    items: [
      { title: "Dashboard", href: "/portal", icon: "Home" },
      { title: "Process", href: "/portal/process", icon: "FolderOpen" },
      { title: "Messages", href: "/portal/messages", icon: "MessageCircle" },
    ],
```

to:

```typescript
    items: [
      { title: "Dashboard", href: "/portal", icon: "Home" },
      { title: "Process", href: "/portal/process", icon: "FolderOpen" },
      { title: "Vault", href: "/portal/vault", icon: "Archive" },
      { title: "Messages", href: "/portal/messages", icon: "MessageCircle" },
    ],
```

- [ ] **Step 2: Fix company back button route**

In `apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx`, change line 120 from:

```typescript
        <Button variant="ghost" className="mt-4" onClick={() => router.push('/portal/vault')}>
```

to:

```typescript
        <Button variant="ghost" className="mt-4" onClick={() => router.push('/portal/companies')}>
```

And line 122 from:

```typescript
          Back to Vault
```

to:

```typescript
          Back to Companies
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/types/navigation.ts apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx
git commit -m "$(cat <<'EOF'
fix(portal): add Vault to sidebar nav + fix company back button route

Vault page existed but was missing from portalNavigation config.
Company not-found fallback incorrectly routed to /portal/vault.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Remove MagicMock import from production audit_logger

**Files:**

- Modify: `apps/backend-rag/backend/app/services/crm/audit_logger.py:10,311`

- [ ] **Step 1: Read the file to understand MagicMock usage**

Read `apps/backend-rag/backend/app/services/crm/audit_logger.py` around lines 10 and 309-312 to understand how MagicMock is used.

- [ ] **Step 2: Replace MagicMock with a proper null check**

Remove the import on line 10:

```python
from unittest.mock import MagicMock
```

And at line 311, change:

```python
                            elif row and not isinstance(row, MagicMock):
```

to:

```python
                            elif row and hasattr(row, "items"):
```

This eliminates the test-only import while preserving the guard. The `hasattr(row, "items")` check is already done in the line above, so this branch handles the case where `row` exists but is not a mapping — which is the actual concern.

If the `isinstance(row, MagicMock)` check was the only usage of MagicMock, this is sufficient. If there are other usages, keep the import.

- [ ] **Step 3: Verify import chain is clean**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.services.crm.audit_logger import CRMAuditLogger; print('OK')"`

Expected: `OK` with no warnings about MagicMock.

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/services/crm/audit_logger.py
git commit -m "$(cat <<'EOF'
fix(crm): remove unittest.mock.MagicMock import from production audit_logger

Test artifact leaked into production code. Replaced isinstance(row, MagicMock)
with a proper hasattr check.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Fix month arithmetic in revenue analytics

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_analytics.py:323-327,463-467`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_crm_analytics_months.py`:

```python
"""Tests for CRM analytics month boundary calculation."""
import pytest
from datetime import datetime, timezone


def test_month_boundaries_are_correct():
    """Month calculation must use replace(day=1) subtraction, not timedelta(days=30)."""
    from pathlib import Path

    source = Path("backend/app/routers/crm_analytics.py").read_text()

    # The old pattern: timedelta(days=i * 30) is imprecise
    assert "timedelta(days=i * 30)" not in source, (
        "Month boundaries must not use timedelta(days=i*30) — this produces "
        "wrong boundaries (30 vs 28/31 days). Use dateutil.relativedelta or "
        "manual month arithmetic."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_analytics_months.py -v`

Expected: FAIL

- [ ] **Step 3: Fix both occurrences of month arithmetic**

In `apps/backend-rag/backend/app/routers/crm_analytics.py`, add this helper function near the top of the file (after imports):

```python
def _months_ago(n: int) -> datetime:
    """Return first day of month N months ago (UTC). Avoids timedelta(days=30) imprecision."""
    now = datetime.now(tz=timezone.utc)
    month = now.month - n
    year = now.year
    while month <= 0:
        month += 12
        year -= 1
    return datetime(year, month, 1, tzinfo=timezone.utc)
```

Then at line 323-327 (revenue summary monthly breakdown), replace:

```python
            for i in range(5, -1, -1):
                month_start = (datetime.now(tz=timezone.utc).replace(day=1) - timedelta(days=i * 30)).replace(
                    day=1,
                )
                month_end = (month_start + timedelta(days=32)).replace(day=1)
```

with:

```python
            for i in range(5, -1, -1):
                month_start = _months_ago(i)
                month_end = _months_ago(i - 1) if i > 0 else datetime.now(tz=timezone.utc).replace(day=1) + timedelta(days=32)
                month_end = month_end.replace(day=1) if i > 0 else (month_start + timedelta(days=32)).replace(day=1)
```

Actually, simpler approach — replace both occurrences (lines ~323 and ~463) with:

```python
            for i in range(5, -1, -1):
                month_start = _months_ago(i)
                next_month = month_start.month + 1
                next_year = month_start.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                month_end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
```

Apply the same fix at line ~463 (client trend monthly breakdown) where the same `timedelta(days=i * 30)` pattern appears.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_analytics_months.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_analytics.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_analytics_months.py
git commit -m "$(cat <<'EOF'
fix(analytics): replace timedelta(days=30) with proper month arithmetic

timedelta(days=i*30) produces wrong month boundaries (Feb=28d, months with 31d).
Added _months_ago() helper for precise first-of-month calculation.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Tab URL sync on client detail page

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`

- [ ] **Step 1: Find the tab state setter**

In `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`, find where `setActiveTab` is defined and where it's called. It will be a `useState<TabType>` pattern with initial value from `searchParams.get('tab')`.

- [ ] **Step 2: Add router.replace on tab change**

Create a wrapper function that both sets state and updates the URL. Find the `setActiveTab` definition and add a handler:

```typescript
const handleTabChange = (tab: TabType) => {
  setActiveTab(tab);
  router.replace(`/clients/${params.id}?tab=${tab}`, { scroll: false });
};
```

Then replace all occurrences of `setActiveTab(someTab)` in the tab bar's onClick handlers with `handleTabChange(someTab)`.

Do NOT change the initial state from `searchParams` — that still works for first load.

- [ ] **Step 3: Verify locally**

Run: `cd apps/mouth && npm run dev`

Navigate to `/clients/123`, switch tabs, verify URL updates with `?tab=company` etc. Verify that browser back button returns to previous tab.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/(workspace)/clients/[id]/page.tsx
git commit -m "$(cat <<'EOF'
fix(crm): sync tab state to URL for shareable deep links

Tab switches now call router.replace with ?tab= param so links
to specific tabs work persistently, not just on first load.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1 — Foundation

### Task 7: Create shared utility package (expiry, date, currency)

**Files:**

- Create: `packages/core/utils/expiry.ts`
- Create: `packages/core/utils/date.ts`
- Create: `packages/core/utils/currency.ts`
- Create: `packages/core/utils/index.ts`

- [ ] **Step 1: Read existing utility implementations**

Read these files to extract the current implementations:

- `apps/mouth/src/app/(workspace)/clients/[id]/components/utils.ts` — `getPassportValidityColor`, `formatCurrency`, `formatDate`
- `apps/mouth/src/app/portal/(authenticated)/dashboard/page.tsx` — `getPassportValidityColor`, `isBirthdayToday`

Document the exact threshold values and logic used in each location.

- [ ] **Step 2: Create packages/core/utils/expiry.ts**

```typescript
export type ExpiryStatus = "expired" | "critical" | "warning" | "ok";

export interface ExpiryResult {
  status: ExpiryStatus;
  daysRemaining: number;
  label: string;
  color: string;
}

/**
 * Unified expiry status calculator.
 * Thresholds: expired (<=0), critical (<=30d), warning (<=90d), ok (>90d).
 */
export function getExpiryStatus(
  expiryDate: string | Date | null | undefined,
): ExpiryResult {
  if (!expiryDate) {
    return {
      status: "ok",
      daysRemaining: Infinity,
      label: "No expiry",
      color: "var(--bz-text-2)",
    };
  }

  const expiry =
    typeof expiryDate === "string" ? new Date(expiryDate) : expiryDate;
  const now = new Date();
  const diffMs = expiry.getTime() - now.getTime();
  const daysRemaining = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (daysRemaining <= 0) {
    return {
      status: "expired",
      daysRemaining,
      label: "Expired",
      color: "#ef4444",
    };
  }
  if (daysRemaining <= 30) {
    return {
      status: "critical",
      daysRemaining,
      label: `${daysRemaining}d left`,
      color: "#ef4444",
    };
  }
  if (daysRemaining <= 90) {
    return {
      status: "warning",
      daysRemaining,
      label: `${daysRemaining}d left`,
      color: "#f59e0b",
    };
  }
  return {
    status: "ok",
    daysRemaining,
    label: `${daysRemaining}d left`,
    color: "#22c55e",
  };
}

export function isBirthdayToday(
  dateOfBirth: string | null | undefined,
): boolean {
  if (!dateOfBirth) return false;
  const dob = new Date(dateOfBirth);
  const today = new Date();
  return (
    dob.getMonth() === today.getMonth() && dob.getDate() === today.getDate()
  );
}
```

- [ ] **Step 3: Create packages/core/utils/currency.ts**

```typescript
const IDR_FORMATTER = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const USD_FORMATTER = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatIDR(amount: number): string {
  return IDR_FORMATTER.format(amount);
}

export function formatUSD(amount: number): string {
  return USD_FORMATTER.format(amount);
}

export function formatCurrency(
  amount: number,
  currency: string = "IDR",
): string {
  if (currency === "USD") return formatUSD(amount);
  return formatIDR(amount);
}
```

- [ ] **Step 4: Create packages/core/utils/date.ts**

```typescript
const DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const TIME_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "—";
  return DATE_FORMATTER.format(d);
}

export function formatTime(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "—";
  return TIME_FORMATTER.format(d);
}

export function formatRelative(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(d);
}
```

- [ ] **Step 5: Create packages/core/utils/index.ts barrel export**

```typescript
export {
  getExpiryStatus,
  isBirthdayToday,
  type ExpiryStatus,
  type ExpiryResult,
} from "./expiry";
export { formatIDR, formatUSD, formatCurrency } from "./currency";
export { formatDate, formatTime, formatRelative } from "./date";
```

- [ ] **Step 6: Commit**

```bash
git add packages/core/utils/
git commit -m "$(cat <<'EOF'
feat(core): add shared utility package for expiry, date, and currency

Unified implementations to replace duplicated logic across CRM
(4 files) and Portal (2 files). Consistent thresholds for expiry
status: expired (<=0d), critical (<=30d), warning (<=90d), ok.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Fix N+1 in team performance analytics

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_analytics.py:214-270`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_analytics_n1.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_crm_analytics_n1.py`:

```python
"""Tests for CRM analytics — N+1 query prevention."""
import pytest
from pathlib import Path
import re


def test_team_performance_no_n_plus_1():
    """Team performance must use GROUP BY, not per-member loop queries."""
    source = Path("backend/app/routers/crm_analytics.py").read_text()

    # Find the team performance function
    func_match = re.search(
        r"async def get_team_performance.*?(?=\nasync def |\nclass |\Z)",
        source,
        re.DOTALL,
    )
    assert func_match, "get_team_performance function not found"
    func_body = func_match.group(0)

    # It must NOT iterate team members with individual queries
    assert "for member in" not in func_body and "for tm in" not in func_body, (
        "Team performance endpoint must not loop over team members "
        "with individual queries. Use a single GROUP BY assigned_to query."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_analytics_n1.py -v`

Expected: FAIL — the function currently has a `for member in` loop.

- [ ] **Step 3: Rewrite team performance to use GROUP BY**

In `apps/backend-rag/backend/app/routers/crm_analytics.py`, replace the team performance endpoint body (the section that loops over team members) with a single aggregate query:

```python
            # Team performance — single aggregate query (no N+1)
            team_rows = await conn.fetch(
                """
                SELECT
                    tm.email,
                    tm.full_name,
                    COUNT(DISTINCT c.id) FILTER (WHERE c.deleted_at IS NULL) as total_clients,
                    COUNT(DISTINCT p.id) FILTER (WHERE p.status NOT IN ('completed', 'cancelled')) as active_practices,
                    COUNT(DISTINCT p.id) FILTER (WHERE p.status = 'completed') as completed_practices,
                    COALESCE(SUM(p.actual_price) FILTER (WHERE p.status = 'completed'), 0) as total_revenue
                FROM team_members tm
                LEFT JOIN clients c ON c.assigned_to = tm.email AND c.deleted_at IS NULL
                LEFT JOIN practices p ON p.assigned_to = tm.email
                WHERE tm.active = true AND tm.role != 'client'
                GROUP BY tm.email, tm.full_name
                ORDER BY total_revenue DESC
                """
            )

            team_performance = []
            for row in team_rows:
                total = row["total_clients"]
                completed = row["completed_practices"]
                team_performance.append({
                    "email": row["email"],
                    "name": row["full_name"],
                    "total_clients": total,
                    "active_practices": row["active_practices"],
                    "completed_cases": completed,
                    "conversion_rate": round(completed / total * 100, 1) if total > 0 else 0,
                    "revenue": float(row["total_revenue"]),
                })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_analytics_n1.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_analytics.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_analytics_n1.py
git commit -m "$(cat <<'EOF'
perf(analytics): eliminate N+1 in team performance with GROUP BY

Was issuing 4 queries per team member in a Python loop.
Now uses a single aggregate query with FILTER clauses.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Fix N+1 in company list associates count

**Files:**

- Modify: `apps/backend-rag/backend/app/modules/crm/company_router.py:93-98`

- [ ] **Step 1: Read the current company list endpoint**

Read `apps/backend-rag/backend/app/modules/crm/company_router.py` around lines 80-110 to see the N+1 pattern for associates count.

- [ ] **Step 2: Inline the COUNT into the main query**

Replace the separate COUNT query per company with a LEFT JOIN COUNT in the main list query. The pattern:

Change from (pseudo):

```python
companies = await conn.fetch("SELECT * FROM companies ...")
for company in companies:
    count = await conn.fetchval("SELECT COUNT(*) FROM client_company_links WHERE company_id = $1", company["id"])
    company_dict["associates_count"] = count
```

To:

```python
companies = await conn.fetch("""
    SELECT c.*, COUNT(ccl.id) as associates_count
    FROM companies c
    LEFT JOIN client_company_links ccl ON ccl.company_id = c.id
    WHERE ...
    GROUP BY c.id
    ORDER BY ...
""")
```

The exact change depends on the current query structure — read the file first and adapt.

- [ ] **Step 3: Verify the endpoint still works**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.modules.crm.company_router import company_router; print('Import OK')"`

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/modules/crm/company_router.py
git commit -m "$(cat <<'EOF'
perf(crm): eliminate N+1 in company list with LEFT JOIN COUNT

Was issuing a separate COUNT(*) query per company for associates.
Now uses LEFT JOIN client_company_links with GROUP BY in the main query.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Add team members API endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/team_members.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_team_members.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_team_members.py`:

```python
"""Tests for team members list endpoint."""
import pytest
from unittest.mock import AsyncMock, patch

import asyncpg


@pytest.fixture
def mock_pool():
    pool = AsyncMock(spec=asyncpg.Pool)
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"email": "adit@balizero.com", "full_name": "Adit", "role": "agent", "avatar_url": None},
        {"email": "asya@balizero.com", "full_name": "Asya", "role": "admin", "avatar_url": None},
    ])
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.mark.asyncio
async def test_list_team_members(mock_pool):
    from backend.app.routers.team_members import list_team_members

    result = await list_team_members(
        pool=mock_pool,
        current_user={"email": "test@balizero.com", "role": "agent"},
    )
    assert len(result["members"]) == 2
    assert result["members"][0]["email"] == "adit@balizero.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_team_members.py -v`

Expected: FAIL — `ImportError: cannot import name 'list_team_members'`

- [ ] **Step 3: Create the team members router**

Create `apps/backend-rag/backend/app/routers/team_members.py`:

```python
"""Team members endpoint — returns active team members for dropdowns and assignments."""
from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter(prefix="/api/team", tags=["team"])


@router.get("/members")
async def list_team_members(
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """List active team members. Used by CRM dropdowns for assignment."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT email, full_name, role, avatar_url
            FROM team_members
            WHERE active = true AND role != 'client'
            ORDER BY full_name
            """
        )
        return {
            "members": [
                {
                    "email": r["email"],
                    "full_name": r["full_name"],
                    "role": r["role"],
                    "avatar_url": r.get("avatar_url"),
                }
                for r in rows
            ]
        }
```

- [ ] **Step 4: Register the router**

In `apps/backend-rag/backend/app/setup/router_registration.py`, add the lazy import for the team_members router following the existing pattern:

```python
def _team_members_router():
    from backend.app.routers.team_members import router
    return router
```

And add it to the router registration list.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_team_members.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/team_members.py apps/backend-rag/backend/app/setup/router_registration.py apps/backend-rag/backend/tests/unit/app/routers/test_team_members.py
git commit -m "$(cat <<'EOF'
feat(api): add GET /api/team/members endpoint for CRM dropdowns

Returns active team members (email, full_name, role, avatar_url).
Replaces hardcoded TEAM_MEMBERS arrays in 3 frontend files.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Replace hardcoded TEAM_MEMBERS with API call

**Files:**

- Create: `apps/mouth/src/hooks/useTeamMembers.ts`
- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/constants.ts:63-111`
- Modify: `apps/mouth/src/app/(workspace)/clients/new/page.tsx:45-90`

- [ ] **Step 1: Create the useTeamMembers hook**

Create `apps/mouth/src/hooks/useTeamMembers.ts`:

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface TeamMember {
  email: string;
  full_name: string;
  role: string;
  avatar_url: string | null;
}

async function fetchTeamMembers(): Promise<TeamMember[]> {
  const res = await api.client.request<{ members: TeamMember[] }>(
    "/api/team/members",
  );
  return res.members;
}

export function useTeamMembers() {
  return useQuery({
    queryKey: ["team-members"],
    queryFn: fetchTeamMembers,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000,
  });
}

export function useTeamMemberOptions() {
  const { data: members = [], ...rest } = useTeamMembers();
  const options = members.map((m) => ({
    value: m.email,
    label: m.full_name,
    avatar: m.avatar_url ?? undefined,
  }));
  return { options, ...rest };
}
```

- [ ] **Step 2: Update constants.ts to export a helper instead of hardcoded array**

In `apps/mouth/src/app/(workspace)/clients/[id]/components/constants.ts`, remove the `TEAM_MEMBERS` array (lines 64-111) and the `getTeamMemberAvatar` helper. Replace with a re-export:

```typescript
// Team members now loaded from API via useTeamMembers hook
// Removed hardcoded TEAM_MEMBERS array — use useTeamMemberOptions() instead
```

- [ ] **Step 3: Update new/page.tsx to use the hook**

In `apps/mouth/src/app/(workspace)/clients/new/page.tsx`, remove the hardcoded `TEAM_MEMBERS` array (lines 45-90) and replace the dropdown with the hook:

```typescript
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";

// Inside the component:
const { options: teamMembers, isLoading: teamLoading } = useTeamMemberOptions();
```

Then update the `<select>` that maps `TEAM_MEMBERS` to use `teamMembers` instead.

- [ ] **Step 4: Update any component that imports TEAM_MEMBERS from constants**

Search for `import { TEAM_MEMBERS` or `import { getTeamMemberAvatar` across the codebase and update each one to use `useTeamMemberOptions()` instead.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/hooks/useTeamMembers.ts apps/mouth/src/app/(workspace)/clients/[id]/components/constants.ts apps/mouth/src/app/(workspace)/clients/new/page.tsx
git commit -m "$(cat <<'EOF'
refactor(crm): replace hardcoded TEAM_MEMBERS with useTeamMembers hook

Removed hardcoded arrays from 3 files. Team members now fetched from
GET /api/team/members with 5min React Query cache. Adding/removing
team members no longer requires code changes.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Migrate client detail page to React Query

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`
- Create: `apps/mouth/src/hooks/useClientDetail.ts`

- [ ] **Step 1: Create the useClientDetail hook**

Create `apps/mouth/src/hooks/useClientDetail.ts`:

```typescript
"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ClientProfile } from "@/lib/api/crm/crm.types";

export function useClientDetail(clientId: string | number) {
  return useQuery({
    queryKey: ["client", String(clientId)],
    queryFn: () => api.crm.getClientProfile(Number(clientId)),
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchOnWindowFocus: true,
  });
}

export function useInvalidateClient(clientId: string | number) {
  const queryClient = useQueryClient();
  return () =>
    queryClient.invalidateQueries({ queryKey: ["client", String(clientId)] });
}
```

- [ ] **Step 2: Refactor page.tsx to use the hook**

In `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`:

1. Replace the `useState` for `client`, `familyMembers`, `documents`, `interactions`, `documentCategories` with the single `useClientDetail` query.
2. Replace the `useEffect` that does `Promise.all([...])` with the query hook.
3. Replace all `refreshProfile()` prop passing with `useInvalidateClient(id)`.
4. Each tab component that currently receives `onRefresh` should instead call `useInvalidateClient` directly (or receive the invalidation function as a prop — simpler migration).

The key change in the component:

```typescript
import { useClientDetail, useInvalidateClient } from "@/hooks/useClientDetail";

// Inside component:
const { data: profile, isLoading, error } = useClientDetail(params.id);
const invalidateClient = useInvalidateClient(params.id);

// Replace all onRefresh={refreshProfile} with onRefresh={invalidateClient}
```

This is a significant refactor of a 977-line file. Take care to:

- Keep the existing tab rendering logic
- Keep all modal state management
- Only change the data fetching and refresh patterns
- Test each tab still renders correctly

- [ ] **Step 3: Verify the migration works**

Run: `cd apps/mouth && npm run dev`

Navigate to `/clients/[some-id]`, verify:

- Data loads correctly
- All 8 tabs render
- Mutations (edit client, add document, etc.) trigger refresh
- Window refocus triggers background refresh

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/hooks/useClientDetail.ts apps/mouth/src/app/(workspace)/clients/[id]/page.tsx
git commit -m "$(cat <<'EOF'
refactor(crm): migrate client detail page from useState to React Query

Replaces manual Promise.all + refreshProfile() prop drilling with
useClientDetail hook. Enables: automatic refetch on window focus,
shared cache with list page, simpler tab components.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Migrate OCR tasks to shared pool

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced.py:222-235,361-372,451-462,537-548`
- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced_documents.py` (where OCR tasks are dispatched)

- [ ] **Step 1: Identify all OCR function signatures**

Read `apps/backend-rag/backend/app/routers/crm_enhanced.py` to find all 4 OCR functions:

- `_auto_ocr_passport(client_id, file_id)` — line 222
- `_auto_ocr_visa(client_id, file_id, doc_id)` — line 361
- `_auto_ocr_nib(client_id, file_id, doc_id)` — line 451
- `_auto_ocr_npwp(client_id, file_id, doc_id)` — line 537

Each creates its own `asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)`.

- [ ] **Step 2: Add db_pool parameter to each function**

Change each function signature to accept `db_pool` as first parameter. For example:

```python
async def _auto_ocr_passport(db_pool: asyncpg.Pool, client_id: int, file_id: str) -> dict:
```

Remove the `db_pool = await asyncpg.create_pool(...)` and `await db_pool.close()` from inside each function. Replace `db_pool = None` / `try: db_pool = await asyncpg.create_pool(...)` / `finally: if db_pool: await db_pool.close()` with just using the passed-in pool directly.

- [ ] **Step 3: Update all callers to pass the pool**

Find where these functions are called (in `_dispatch_ocr_by_folder` and direct callers). They're called via `asyncio.create_task()`. Update each call site to pass the pool:

```python
# Before:
asyncio.create_task(_auto_ocr_passport(client_id, file_id))

# After:
asyncio.create_task(_auto_ocr_passport(pool, client_id, file_id))
```

The `pool` variable is available in the router endpoint that dispatches the OCR task.

- [ ] **Step 4: Verify import chain**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.routers.crm_enhanced import router; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_enhanced.py apps/backend-rag/backend/app/routers/crm_enhanced_documents.py
git commit -m "$(cat <<'EOF'
fix(ocr): pass shared db_pool to background OCR tasks

Was creating transient asyncpg pools (min=1, max=2) per OCR invocation,
causing connection churn on Fly.io 2GB. Now reuses the app-level pool.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Verification Checkpoint

After completing all 13 tasks:

- [ ] **Run backend test suite**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_enhanced_alerts.py backend/tests/unit/app/routers/test_crm_clients_delete.py backend/tests/unit/app/routers/test_crm_analytics_months.py backend/tests/unit/app/routers/test_crm_analytics_n1.py backend/tests/unit/app/routers/test_team_members.py -v
```

Expected: All tests PASS.

- [ ] **Verify import chain**

```bash
cd apps/backend-rag && python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

- [ ] **Run frontend build**

```bash
cd apps/mouth && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Run core KG tests (regression)**

```bash
cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```

Expected: 82/82 pass.
