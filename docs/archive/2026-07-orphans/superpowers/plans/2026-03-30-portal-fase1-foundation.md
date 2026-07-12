# Portal Fase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the three P0 improvements from the portal strategy brainstorm: Process Tracker with timeline, Document Bridge to Google Drive, and shared component extraction — giving clients visibility into their process status and documents.

**Architecture:** Backend adds 3 new endpoints to the existing `portal.py` router (process timeline, Drive file list, Drive file download). Frontend extracts 3 shared components from duplicated portal code, then builds the Process Tracker stepper and integrates the Vault with Google Drive. All changes are additive — no existing endpoints or pages are broken.

**Tech Stack:** FastAPI (backend), Next.js App Router (frontend), asyncpg (DB), Google Drive API via `ServiceAccountDriveService`, Warm Depth design tokens, React Query for data fetching.

---

## File Structure

### Backend (new files)

| File                                                         | Responsibility                                                                                                                |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/routers/portal_process_timeline.py`             | `GET /api/portal/process/{id}/timeline` — returns practice status history + step metadata                                     |
| `backend/app/routers/portal_drive.py`                        | `GET /api/portal/drive/files` + `GET /api/portal/drive/files/{file_id}/download` — proxy to Drive API scoped to client folder |
| `backend/tests/unit/routers/test_portal_process_timeline.py` | Tests for process timeline endpoint                                                                                           |
| `backend/tests/unit/routers/test_portal_drive.py`            | Tests for Drive proxy endpoints                                                                                               |

### Backend (modified files)

| File                                       | Change                 |
| ------------------------------------------ | ---------------------- |
| `backend/app/setup/router_registration.py` | Register 2 new routers |

### Frontend (new files)

| File                                                  | Responsibility                                                                                   |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `apps/mouth/src/components/portal/StatusBadge.tsx`    | Shared status badge (active/pending/warning/expired/compliant/overdue) — extracted from 4+ pages |
| `apps/mouth/src/components/portal/CountdownChip.tsx`  | Shared `⏰ Xd left` / `Xd ago` chip — extracted from 6+ pages                                    |
| `apps/mouth/src/components/portal/ProcessStepper.tsx` | Visual stepper for practice timeline with completed/current/upcoming steps                       |
| `apps/mouth/src/hooks/usePortalProcessTimeline.ts`    | React Query hook for `GET /api/portal/process/{id}/timeline`                                     |
| `apps/mouth/src/hooks/usePortalDriveFiles.ts`         | React Query hook for `GET /api/portal/drive/files`                                               |

### Frontend (modified files)

| File                                                         | Change                                                                             |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `apps/mouth/src/components/portal/index.ts`                  | Export new shared components                                                       |
| `apps/mouth/src/app/portal/(authenticated)/process/page.tsx` | Add ProcessStepper to each ProcessCard                                             |
| `apps/mouth/src/app/portal/(authenticated)/vault/page.tsx`   | Add Drive files tab alongside existing uploaded documents                          |
| `apps/mouth/src/lib/api/portal/portal.api.ts`                | Add `getProcessTimeline()`, `getDriveFiles()`, `getDriveFileDownloadUrl()` methods |
| `apps/mouth/src/lib/api/portal/portal.types.ts`              | Add `ProcessTimelineStep`, `DriveFile` types                                       |

---

## Task 1: Extract Shared StatusBadge Component

**Files:**

- Create: `apps/mouth/src/components/portal/StatusBadge.tsx`
- Modify: `apps/mouth/src/components/portal/index.ts`
- Modify: `apps/mouth/src/app/portal/(authenticated)/visa/page.tsx`

- [ ] **Step 1: Create the StatusBadge component**

This component is duplicated in visa/page.tsx, companies/page.tsx, taxes/page.tsx with identical logic. Extract once.

```tsx
// apps/mouth/src/components/portal/StatusBadge.tsx
import React from "react";
import { CheckCircle, Clock, AlertTriangle } from "lucide-react";

type StatusType =
  | "active"
  | "compliant"
  | "verified"
  | "completed"
  | "approved"
  | "submitted"
  | "filed"
  | "pending"
  | "processing"
  | "attention"
  | "warning"
  | "expiring"
  | "received"
  | "uploaded"
  | "expired"
  | "overdue"
  | "rejected"
  | "cancelled"
  | "none"
  | "draft";

const STATUS_MAP: Record<
  string,
  { icon: React.ElementType; label: string; bg: string; color: string }
> = {
  // Green group
  active: {
    icon: CheckCircle,
    label: "Active",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  compliant: {
    icon: CheckCircle,
    label: "Compliant",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  verified: {
    icon: CheckCircle,
    label: "Verified",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  completed: {
    icon: CheckCircle,
    label: "Completed",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  approved: {
    icon: CheckCircle,
    label: "Approved",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  submitted: {
    icon: CheckCircle,
    label: "Submitted",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  filed: {
    icon: CheckCircle,
    label: "Filed",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  // Amber group
  pending: {
    icon: Clock,
    label: "Pending",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  processing: {
    icon: Clock,
    label: "Processing",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  attention: {
    icon: AlertTriangle,
    label: "Attention",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  warning: {
    icon: AlertTriangle,
    label: "Expiring",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  expiring: {
    icon: AlertTriangle,
    label: "Expiring",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  received: {
    icon: Clock,
    label: "Received",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  uploaded: {
    icon: Clock,
    label: "Uploaded",
    bg: "rgba(59,130,246,0.12)",
    color: "#60a5fa",
  },
  draft: {
    icon: Clock,
    label: "Draft",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  // Red group
  expired: {
    icon: AlertTriangle,
    label: "Expired",
    bg: "rgba(239,68,68,0.12)",
    color: "#f87171",
  },
  overdue: {
    icon: AlertTriangle,
    label: "Overdue",
    bg: "rgba(239,68,68,0.12)",
    color: "#f87171",
  },
  rejected: {
    icon: AlertTriangle,
    label: "Rejected",
    bg: "rgba(239,68,68,0.12)",
    color: "#f87171",
  },
  cancelled: {
    icon: AlertTriangle,
    label: "Cancelled",
    bg: "rgba(239,68,68,0.12)",
    color: "#f87171",
  },
  // Default
  none: {
    icon: Clock,
    label: "None",
    bg: "rgba(255,255,255,0.05)",
    color: "var(--bz-text-2)",
  },
};

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const config = STATUS_MAP[status.toLowerCase()] ?? STATUS_MAP.none;
  const Icon = config.icon;

  return (
    <div
      className={`px-2.5 py-1 rounded-full flex items-center gap-1.5 text-xs font-medium ${className ?? ""}`}
      style={{ background: config.bg, color: config.color }}
    >
      <Icon className="w-3.5 h-3.5" />
      {config.label}
    </div>
  );
}
```

- [ ] **Step 2: Export from portal index**

Add to `apps/mouth/src/components/portal/index.ts`:

```ts
export { StatusBadge } from "./StatusBadge";
```

- [ ] **Step 3: Replace one usage in visa/page.tsx to verify**

In `apps/mouth/src/app/portal/(authenticated)/visa/page.tsx`, replace the local `StatusBadge` function (lines 315-353) with the import:

```tsx
// At top of file, add:
import { StatusBadge } from "@/components/portal";

// Delete the local StatusBadge function (lines 315-353)
```

- [ ] **Step 4: Run dev server and verify visa page renders correctly**

Run: `cd apps/mouth && npm run dev`
Navigate to: `http://localhost:3000/portal/visa`
Expected: Status badges render identically to before.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/portal/StatusBadge.tsx apps/mouth/src/components/portal/index.ts apps/mouth/src/app/portal/\(authenticated\)/visa/page.tsx
git commit -m "refactor(portal): extract shared StatusBadge component from duplicated code"
```

---

## Task 2: Extract Shared CountdownChip Component

**Files:**

- Create: `apps/mouth/src/components/portal/CountdownChip.tsx`
- Modify: `apps/mouth/src/components/portal/index.ts`

- [ ] **Step 1: Create the CountdownChip component**

This pattern (`⏰ Xd left` / `Xd overdue` / `Xmo ago`) is duplicated across 6+ portal pages.

```tsx
// apps/mouth/src/components/portal/CountdownChip.tsx
import React from "react";

interface CountdownChipProps {
  /** ISO date string to count down to (future) or since (past) */
  date: string;
  /** 'countdown' = future deadline, 'age' = time since event */
  mode?: "countdown" | "age";
  className?: string;
}

export function CountdownChip({
  date,
  mode = "countdown",
  className,
}: CountdownChipProps) {
  const now = Date.now();
  const target = new Date(date).getTime();
  const diffDays = Math.round((target - now) / 86400000);

  if (mode === "age") {
    const ageDays = Math.abs(diffDays);
    if (ageDays < 7) return null;
    const label =
      ageDays >= 365
        ? `${Math.floor(ageDays / 365)}y ago`
        : ageDays >= 30
          ? `${Math.floor(ageDays / 30)}mo ago`
          : `${ageDays}d ago`;
    return (
      <span
        className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${className ?? ""}`}
        style={{
          background: "rgba(255,255,255,0.04)",
          color: "var(--bz-text-3)",
        }}
      >
        {label}
      </span>
    );
  }

  // Countdown mode
  const isOverdue = diffDays < 0;
  const absDays = Math.abs(diffDays);

  const chipColor = isOverdue
    ? "bg-red-500/15 text-red-400"
    : diffDays === 0
      ? "bg-red-500/10 text-red-400"
      : diffDays <= 7
        ? "bg-red-500/10 text-red-400"
        : diffDays <= 30
          ? "bg-amber-500/10 text-amber-400"
          : diffDays <= 90
            ? "bg-amber-500/10 text-amber-400"
            : "bg-emerald-500/10 text-emerald-400";

  const label = isOverdue
    ? `${absDays}d overdue`
    : diffDays === 0
      ? "today"
      : diffDays === 1
        ? "tomorrow"
        : diffDays <= 365
          ? `⏰ ${diffDays}d left`
          : `${Math.floor(diffDays / 30)}mo left`;

  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${chipColor} ${className ?? ""}`}
      title={new Date(date).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      })}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 2: Export from portal index**

Add to `apps/mouth/src/components/portal/index.ts`:

```ts
export { CountdownChip } from "./CountdownChip";
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/portal/CountdownChip.tsx apps/mouth/src/components/portal/index.ts
git commit -m "refactor(portal): extract shared CountdownChip component"
```

---

## Task 3: Backend — Process Timeline Endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/portal_process_timeline.py`
- Create: `apps/backend-rag/backend/tests/unit/routers/test_portal_process_timeline.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/backend-rag/backend/tests/unit/routers/test_portal_process_timeline.py
"""Tests for portal process timeline endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.routers.portal_process_timeline import get_process_timeline


@pytest.mark.asyncio
async def test_timeline_returns_steps_for_valid_practice():
    """Timeline endpoint returns ordered steps for a practice belonging to the client."""
    mock_conn = AsyncMock()

    # Practice row
    mock_conn.fetchrow.return_value = {
        "id": 10,
        "client_id": 1,
        "status": "in_progress",
        "start_date": "2026-01-15",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "KITAS B211A",
        "practice_category": "visa",
        "assigned_to": "asya@balizero.com",
    }

    # Status history rows
    mock_conn.fetch.return_value = [
        {"old_status": None, "new_status": "inquiry", "changed_at": "2026-01-15T10:00:00+00:00", "changed_by": "system"},
        {"old_status": "inquiry", "new_status": "quotation_sent", "changed_at": "2026-01-15T14:00:00+00:00", "changed_by": "asya@balizero.com"},
        {"old_status": "quotation_sent", "new_status": "payment_pending", "changed_at": "2026-01-16T09:00:00+00:00", "changed_by": "asya@balizero.com"},
        {"old_status": "payment_pending", "new_status": "in_progress", "changed_at": "2026-01-17T11:00:00+00:00", "changed_by": "system"},
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    client = {"client_id": 1, "user_id": "u1", "email": "client@test.com", "name": "Test"}

    from backend.app.routers.portal_process_timeline import _build_timeline
    result = await _build_timeline(mock_pool, practice_id=10, client_id=1)

    assert result["practice_id"] == 10
    assert result["practice_name"] == "KITAS B211A"
    assert result["current_status"] == "in_progress"
    assert len(result["steps"]) == 4
    assert result["steps"][0]["status"] == "inquiry"
    assert result["steps"][0]["completed"] is True
    assert result["steps"][-1]["status"] == "in_progress"
    assert result["steps"][-1]["is_current"] is True


@pytest.mark.asyncio
async def test_timeline_returns_404_for_wrong_client():
    """Timeline endpoint returns 404 if practice does not belong to the client."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None  # No practice found for this client

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    from backend.app.routers.portal_process_timeline import _build_timeline
    result = await _build_timeline(mock_pool, practice_id=999, client_id=1)

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_process_timeline.py -v`
Expected: FAIL with ImportError (module does not exist yet)

- [ ] **Step 3: Write the backend router**

```python
# apps/backend-rag/backend/app/routers/portal_process_timeline.py
"""
Portal Process Timeline Router.

Exposes practice status history as a visual timeline for the client portal.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/process", tags=["portal-process"])

# Canonical status ordering for visual stepper
STATUS_ORDER = [
    "inquiry",
    "quotation_sent",
    "sending_invoice",
    "payment_pending",
    "waiting_payment",
    "waiting_documents",
    "in_progress",
    "on_process",
    "submitted_to_gov",
    "approved",
    "completed",
]

STATUS_LABELS = {
    "inquiry": "Inquiry",
    "quotation_sent": "Quotation Sent",
    "sending_invoice": "Sending Invoice",
    "payment_pending": "Payment Pending",
    "waiting_payment": "Waiting for Payment",
    "waiting_documents": "Waiting for Documents",
    "in_progress": "In Progress",
    "on_process": "On Process",
    "submitted_to_gov": "Submitted to Government",
    "approved": "Approved",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


async def _build_timeline(
    pool: asyncpg.Pool,
    practice_id: int,
    client_id: int,
) -> dict[str, Any] | None:
    """Build timeline data for a practice. Returns None if not found."""
    async with pool.acquire() as conn:
        # Fetch practice with type info
        practice = await conn.fetchrow(
            """
            SELECT p.id, p.client_id, p.status, p.start_date, p.completion_date,
                   p.expiry_date, p.notes, pt.name as practice_name,
                   pt.category as practice_category,
                   c.assigned_to
            FROM practices p
            JOIN practice_types pt ON pt.id = p.practice_type_id
            LEFT JOIN clients c ON c.id = p.client_id
            WHERE p.id = $1
              AND p.client_id = $2
              AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
            """,
            practice_id,
            client_id,
        )

        if not practice:
            return None

        # Fetch status history from practice_status_log (if table exists)
        # Fallback: synthesize from current status only
        history_rows: list[dict] = []
        try:
            history_rows = [
                dict(r) for r in await conn.fetch(
                    """
                    SELECT old_status, new_status, changed_at, changed_by
                    FROM practice_status_log
                    WHERE practice_id = $1
                    ORDER BY changed_at ASC
                    """,
                    practice_id,
                )
            ]
        except Exception:
            # Table may not exist yet — fallback to single-step
            pass

        current_status = practice["status"]

        if history_rows:
            # Build steps from actual history
            steps = []
            for i, row in enumerate(history_rows):
                status = row["new_status"]
                is_current = (status == current_status and i == len(history_rows) - 1)
                steps.append({
                    "status": status,
                    "label": STATUS_LABELS.get(status, status.replace("_", " ").title()),
                    "completed": not is_current,
                    "is_current": is_current,
                    "changed_at": str(row["changed_at"]) if row["changed_at"] else None,
                    "changed_by": row.get("changed_by"),
                })
        else:
            # No history — single step from current status
            steps = [{
                "status": current_status,
                "label": STATUS_LABELS.get(current_status, current_status.replace("_", " ").title()),
                "completed": current_status in ("completed", "approved"),
                "is_current": current_status not in ("completed", "approved", "cancelled"),
                "changed_at": str(practice["start_date"]) if practice["start_date"] else None,
                "changed_by": None,
            }]

        return {
            "practice_id": practice["id"],
            "practice_name": practice["practice_name"],
            "practice_category": practice["practice_category"],
            "current_status": current_status,
            "assigned_to": practice["assigned_to"],
            "start_date": str(practice["start_date"]) if practice["start_date"] else None,
            "completion_date": str(practice["completion_date"]) if practice["completion_date"] else None,
            "expiry_date": str(practice["expiry_date"]) if practice["expiry_date"] else None,
            "steps": steps,
        }


@router.get("/{practice_id}/timeline")
async def get_process_timeline(
    practice_id: int,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get timeline of status changes for a specific practice."""
    result = await _build_timeline(db_pool, practice_id, client["client_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return {"success": True, "data": result}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_process_timeline.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Register the router**

In `apps/backend-rag/backend/app/setup/router_registration.py`, add to the lazy import section (follow existing pattern):

```python
# Portal process timeline
from backend.app.routers.portal_process_timeline import router as portal_process_timeline_router
app.include_router(portal_process_timeline_router)
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/portal_process_timeline.py apps/backend-rag/backend/tests/unit/routers/test_portal_process_timeline.py apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(portal): add process timeline endpoint with status history"
```

---

## Task 4: Backend — Drive Files Proxy Endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/portal_drive.py`
- Create: `apps/backend-rag/backend/tests/unit/routers/test_portal_drive.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/backend-rag/backend/tests/unit/routers/test_portal_drive.py
"""Tests for portal Drive proxy endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_list_files_returns_drive_files():
    """Drive list endpoint returns files from client's Drive folder."""
    from backend.app.routers.portal_drive import _list_client_drive_files

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = "folder_abc123"  # client's drive_folder_id

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_drive = MagicMock()
    mock_drive.get_folder_structure = AsyncMock(return_value={
        "root_id": "folder_abc123",
        "root_name": "Client_John",
        "folders": [{"id": "sub1", "name": "Documents"}, {"id": "sub2", "name": "Final"}],
        "total_files": 5,
        "total_size_bytes": 1024000,
    })

    result = await _list_client_drive_files(mock_pool, mock_drive, client_id=1)

    assert result is not None
    assert result["root_name"] == "Client_John"
    assert len(result["folders"]) == 2
    assert result["total_files"] == 5


@pytest.mark.asyncio
async def test_list_files_returns_none_when_no_folder():
    """Drive list endpoint returns None if client has no Drive folder."""
    from backend.app.routers.portal_drive import _list_client_drive_files

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None  # no drive_folder_id

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_drive = MagicMock()

    result = await _list_client_drive_files(mock_pool, mock_drive, client_id=1)

    assert result is None
    mock_drive.get_folder_structure.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_drive.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write the backend router**

```python
# apps/backend-rag/backend/app/routers/portal_drive.py
"""
Portal Drive Proxy Router.

Provides scoped access to a client's Google Drive folder.
Clients can only see files in their own drive_folder_id.
"""

import asyncio
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/drive", tags=["portal-drive"])


def _get_drive_service() -> ServiceAccountDriveService:
    return ServiceAccountDriveService()


async def _list_client_drive_files(
    pool: asyncpg.Pool,
    drive_service: ServiceAccountDriveService,
    client_id: int,
) -> dict[str, Any] | None:
    """List files from the client's Google Drive folder. Returns None if no folder linked."""
    async with pool.acquire() as conn:
        folder_id = await conn.fetchval(
            "SELECT drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )

    if not folder_id:
        return None

    return await drive_service.get_folder_structure(folder_id)


@router.get("/files")
async def list_drive_files(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    drive_service: ServiceAccountDriveService = Depends(_get_drive_service),
) -> dict[str, Any]:
    """List files in the client's Google Drive folder."""
    try:
        result = await _list_client_drive_files(db_pool, drive_service, client["client_id"])
        if result is None:
            return {
                "success": True,
                "data": {"files": [], "folders": [], "total_files": 0, "message": "No Drive folder linked"},
            }
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to list Drive files for client {client['client_id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load documents from Drive")


@router.get("/files/{folder_id}/list")
async def list_subfolder_files(
    folder_id: str,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    drive_service: ServiceAccountDriveService = Depends(_get_drive_service),
) -> dict[str, Any]:
    """List files in a subfolder of the client's Drive folder.

    Security: validates that folder_id is a child of the client's root folder.
    """
    async with db_pool.acquire() as conn:
        root_folder_id = await conn.fetchval(
            "SELECT drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client["client_id"],
        )

    if not root_folder_id:
        raise HTTPException(status_code=404, detail="No Drive folder linked")

    # Security: verify the requested folder is under the client's root
    # Get root structure and check folder_id is in the list
    root_structure = await drive_service.get_folder_structure(root_folder_id)
    allowed_ids = {root_folder_id} | {f["id"] for f in root_structure.get("folders", [])}

    if folder_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Access denied to this folder")

    result = await drive_service.get_folder_structure(folder_id)
    return {"success": True, "data": result}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_drive.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Register the router**

In `apps/backend-rag/backend/app/setup/router_registration.py`, add:

```python
# Portal Drive proxy
from backend.app.routers.portal_drive import router as portal_drive_router
app.include_router(portal_drive_router)
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/portal_drive.py apps/backend-rag/backend/tests/unit/routers/test_portal_drive.py apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(portal): add Drive files proxy endpoint scoped to client folder"
```

---

## Task 5: Frontend — API Types and Client Methods

**Files:**

- Modify: `apps/mouth/src/lib/api/portal/portal.types.ts`
- Modify: `apps/mouth/src/lib/api/portal/portal.api.ts`

- [ ] **Step 1: Add types to portal.types.ts**

Append to `apps/mouth/src/lib/api/portal/portal.types.ts`:

```ts
// ============================================================================
// Process Timeline Types
// ============================================================================

export interface ProcessTimelineStep {
  status: string;
  label: string;
  completed: boolean;
  is_current: boolean;
  changed_at: string | null;
  changed_by: string | null;
}

export interface ProcessTimeline {
  practice_id: number;
  practice_name: string;
  practice_category: string;
  current_status: string;
  assigned_to: string | null;
  start_date: string | null;
  completion_date: string | null;
  expiry_date: string | null;
  steps: ProcessTimelineStep[];
}

// ============================================================================
// Drive File Types
// ============================================================================

export interface DriveFolder {
  id: string;
  name: string;
}

export interface DriveFilesResponse {
  root_id?: string;
  root_name?: string;
  folders: DriveFolder[];
  total_files: number;
  total_size_bytes?: number;
  message?: string;
}
```

- [ ] **Step 2: Add API methods to portal.api.ts**

Append to the `PortalApi` class in `apps/mouth/src/lib/api/portal/portal.api.ts`, before the closing brace:

```ts
  // ============================================================================
  // Process Timeline
  // ============================================================================

  async getProcessTimeline(practiceId: number): Promise<ProcessTimeline> {
    const response = await this.client.request<PortalApiResponse<ProcessTimeline>>(
      `/api/portal/process/${practiceId}/timeline`,
      { method: "GET" },
    );
    return response.data!;
  }

  // ============================================================================
  // Drive Files
  // ============================================================================

  async getDriveFiles(): Promise<DriveFilesResponse> {
    const response = await this.client.request<PortalApiResponse<DriveFilesResponse>>(
      "/api/portal/drive/files",
      { method: "GET" },
    );
    return response.data!;
  }

  async getDriveSubfolderFiles(folderId: string): Promise<DriveFilesResponse> {
    const response = await this.client.request<PortalApiResponse<DriveFilesResponse>>(
      `/api/portal/drive/files/${folderId}/list`,
      { method: "GET" },
    );
    return response.data!;
  }
```

Also add the new type imports at the top of `portal.api.ts`:

```ts
import type {
  // ... existing imports ...
  ProcessTimeline,
  DriveFilesResponse,
} from "./portal.types";
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/api/portal/portal.types.ts apps/mouth/src/lib/api/portal/portal.api.ts
git commit -m "feat(portal): add API types and client methods for process timeline and Drive files"
```

---

## Task 6: Frontend — React Query Hooks

**Files:**

- Create: `apps/mouth/src/hooks/usePortalProcessTimeline.ts`
- Create: `apps/mouth/src/hooks/usePortalDriveFiles.ts`

- [ ] **Step 1: Create the process timeline hook**

```ts
// apps/mouth/src/hooks/usePortalProcessTimeline.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ProcessTimeline } from "@/lib/api/portal/portal.types";

export function usePortalProcessTimeline(practiceId: number | null) {
  return useQuery<ProcessTimeline>({
    queryKey: ["portal", "process-timeline", practiceId],
    queryFn: () => api.portal.getProcessTimeline(practiceId!),
    enabled: !!practiceId,
    staleTime: 60_000, // 1 minute
  });
}
```

- [ ] **Step 2: Create the Drive files hook**

```ts
// apps/mouth/src/hooks/usePortalDriveFiles.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DriveFilesResponse } from "@/lib/api/portal/portal.types";

export function usePortalDriveFiles() {
  return useQuery<DriveFilesResponse>({
    queryKey: ["portal", "drive-files"],
    queryFn: () => api.portal.getDriveFiles(),
    staleTime: 120_000, // 2 minutes
  });
}

export function usePortalDriveSubfolder(folderId: string | null) {
  return useQuery<DriveFilesResponse>({
    queryKey: ["portal", "drive-files", folderId],
    queryFn: () => api.portal.getDriveSubfolderFiles(folderId!),
    enabled: !!folderId,
    staleTime: 120_000,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/hooks/usePortalProcessTimeline.ts apps/mouth/src/hooks/usePortalDriveFiles.ts
git commit -m "feat(portal): add React Query hooks for process timeline and Drive files"
```

---

## Task 7: Frontend — ProcessStepper Component

**Files:**

- Create: `apps/mouth/src/components/portal/ProcessStepper.tsx`
- Modify: `apps/mouth/src/components/portal/index.ts`

- [ ] **Step 1: Create the ProcessStepper component**

```tsx
// apps/mouth/src/components/portal/ProcessStepper.tsx
"use client";

import React from "react";
import { CheckCircle, Circle, Loader, User } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcessTimelineStep } from "@/lib/api/portal/portal.types";

interface ProcessStepperProps {
  steps: ProcessTimelineStep[];
  className?: string;
}

export function ProcessStepper({ steps, className }: ProcessStepperProps) {
  if (steps.length === 0) return null;

  return (
    <div className={cn("relative", className)}>
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1;

        return (
          <div key={`${step.status}-${index}`} className="flex gap-3">
            {/* Vertical line + dot */}
            <div className="flex flex-col items-center">
              {step.completed ? (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(16,185,129,0.15)" }}
                >
                  <CheckCircle
                    className="w-4 h-4"
                    style={{ color: "#34d399" }}
                  />
                </div>
              ) : step.is_current ? (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 animate-pulse"
                  style={{ background: "rgba(59,130,246,0.15)" }}
                >
                  <Loader
                    className="w-4 h-4 animate-spin"
                    style={{ color: "#60a5fa" }}
                  />
                </div>
              ) : (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(255,255,255,0.05)" }}
                >
                  <Circle
                    className="w-3 h-3"
                    style={{ color: "var(--bz-text-3)" }}
                  />
                </div>
              )}
              {!isLast && (
                <div
                  className="w-0.5 flex-1 min-h-[24px]"
                  style={{
                    background: step.completed
                      ? "rgba(16,185,129,0.3)"
                      : "rgba(255,255,255,0.05)",
                  }}
                />
              )}
            </div>

            {/* Content */}
            <div className={cn("pb-4 flex-1 min-w-0", isLast && "pb-0")}>
              <p
                className={cn(
                  "text-sm font-medium",
                  step.is_current && "text-blue-400",
                  step.completed && "text-[var(--bz-text-1)]",
                  !step.completed &&
                    !step.is_current &&
                    "text-[var(--bz-text-3)]",
                )}
              >
                {step.label}
              </p>
              {step.changed_at && (
                <p
                  className="text-xs mt-0.5"
                  style={{ color: "var(--bz-text-3)" }}
                >
                  {new Date(step.changed_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                  {step.changed_by && step.changed_by !== "system" && (
                    <span className="ml-1.5">
                      <User
                        className="w-3 h-3 inline -mt-0.5"
                        style={{ color: "var(--bz-text-3)" }}
                      />{" "}
                      {step.changed_by.split("@")[0]}
                    </span>
                  )}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Export from portal index**

Add to `apps/mouth/src/components/portal/index.ts`:

```ts
export { ProcessStepper } from "./ProcessStepper";
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/portal/ProcessStepper.tsx apps/mouth/src/components/portal/index.ts
git commit -m "feat(portal): add ProcessStepper visual timeline component"
```

---

## Task 8: Frontend — Integrate ProcessStepper into Process Page

**Files:**

- Modify: `apps/mouth/src/app/portal/(authenticated)/process/page.tsx`

- [ ] **Step 1: Add timeline toggle to ProcessCard**

In `apps/mouth/src/app/portal/(authenticated)/process/page.tsx`, modify the `ProcessCard` component to include a "View Timeline" button that fetches and shows the stepper.

At the top of the file, add imports:

```tsx
import { ProcessStepper } from "@/components/portal";
import { usePortalProcessTimeline } from "@/hooks/usePortalProcessTimeline";
```

Inside the `ProcessCard` component, add state and the hook:

```tsx
function ProcessCard({
  process,
  onUploadClick,
}: {
  process: ProcessGroup;
  onUploadClick: (doc: ClientRequiredDocument) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showTimeline, setShowTimeline] = useState(false);
  const { data: timeline, isLoading: isLoadingTimeline } = usePortalProcessTimeline(
    showTimeline ? process.practiceId : null
  );
```

Add the timeline section inside the ProcessCard, after the header button and before the documents list:

```tsx
{
  /* Timeline Section */
}
{
  isExpanded && (
    <div className="px-4 pb-2">
      <button
        onClick={() => setShowTimeline(!showTimeline)}
        className="text-xs font-medium flex items-center gap-1 transition-opacity hover:opacity-80"
        style={{ color: "var(--bz-accent-warm)" }}
      >
        {showTimeline ? "Hide Timeline" : "View Timeline"}
      </button>
      {showTimeline && (
        <div className="mt-3">
          {isLoadingTimeline ? (
            <div className="flex items-center gap-2 py-2">
              <div
                className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                style={{
                  borderColor: "var(--bz-accent-warm)",
                  borderTopColor: "transparent",
                }}
              />
              <span className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                Loading timeline...
              </span>
            </div>
          ) : timeline?.steps ? (
            <ProcessStepper steps={timeline.steps} />
          ) : (
            <p className="text-xs py-2" style={{ color: "var(--bz-text-3)" }}>
              No timeline data available
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run dev server and verify Process page**

Run: `cd apps/mouth && npm run dev`
Navigate to: `http://localhost:3000/portal/process`
Expected: Each process card shows a "View Timeline" link. Clicking it shows the stepper (may show "No timeline data" if backend not deployed yet — that's OK).

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/app/portal/\(authenticated\)/process/page.tsx
git commit -m "feat(portal): integrate ProcessStepper into Process page with lazy loading"
```

---

## Task 9: Frontend — Integrate Drive Files into Vault Page

**Files:**

- Modify: `apps/mouth/src/app/portal/(authenticated)/vault/page.tsx`

- [ ] **Step 1: Add Drive files tab to Vault page**

At the top of `vault/page.tsx`, add imports:

```tsx
import { usePortalDriveFiles } from "@/hooks/usePortalDriveFiles";
import { FolderOpen } from "lucide-react";
```

Inside the `VaultPage` component, add Drive data fetching after existing state:

```tsx
const { data: driveData, isLoading: isLoadingDrive } = usePortalDriveFiles();
const [activeTab, setActiveTab] = useState<"uploaded" | "drive">("uploaded");
```

Replace the existing `{/* Header */}` section to include tab switcher:

```tsx
{
  /* Header */
}
<section>
  <h1 className="text-2xl font-bold tracking-tight">Document Vault</h1>
  <p style={{ color: "var(--bz-text-2)" }}>Manage your important documents</p>
</section>;

{
  /* Tab Switcher */
}
<section
  className="flex gap-1 p-1 rounded-lg"
  style={{ background: "rgba(255,255,255,0.03)" }}
>
  <button
    onClick={() => setActiveTab("uploaded")}
    className="flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors"
    style={
      activeTab === "uploaded"
        ? {
            background: "rgba(201,169,110,0.15)",
            color: "var(--bz-accent-warm)",
          }
        : {
            color: "var(--bz-text-2)",
          }
    }
  >
    Uploaded ({filteredDocs.length})
  </button>
  <button
    onClick={() => setActiveTab("drive")}
    className="flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors"
    style={
      activeTab === "drive"
        ? {
            background: "rgba(201,169,110,0.15)",
            color: "var(--bz-accent-warm)",
          }
        : {
            color: "var(--bz-text-2)",
          }
    }
  >
    Drive Files ({driveData?.total_files ?? 0})
  </button>
</section>;
```

Wrap the existing Upload Section + Filters + Documents List in a conditional:

```tsx
{
  activeTab === "uploaded" ? (
    <>{/* ...existing Upload Section, Filters, Documents List... */}</>
  ) : (
    /* Drive Files Tab */
    <section className="space-y-3">
      {isLoadingDrive ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-lg border p-4 h-16 animate-pulse"
              style={{
                background: "rgba(30,30,35,0.7)",
                borderColor: "rgba(255,255,255,0.05)",
              }}
            />
          ))}
        </div>
      ) : !driveData?.folders?.length && !driveData?.total_files ? (
        <div
          className="text-center py-12"
          style={{ color: "var(--bz-text-2)" }}
        >
          <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No Drive folder linked to your account</p>
          <p className="text-sm mt-1" style={{ color: "var(--bz-text-3)" }}>
            Contact your case manager to set up document sharing.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {driveData?.folders?.map((folder) => (
            <div
              key={folder.id}
              className="rounded-lg border p-4 flex items-center gap-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "rgba(30,30,35,0.7)",
                borderColor: "rgba(255,255,255,0.05)",
              }}
            >
              <div
                className="p-2 rounded-md"
                style={{ background: "rgba(201,169,110,0.12)" }}
              >
                <FolderOpen
                  className="w-5 h-5"
                  style={{ color: "var(--bz-accent-warm)" }}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{folder.name}</p>
              </div>
            </div>
          ))}
          <p
            className="text-xs text-center pt-2"
            style={{ color: "var(--bz-text-3)" }}
          >
            {driveData?.total_files ?? 0} files •{" "}
            {driveData?.root_name ?? "Drive"}
          </p>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Run dev server and verify Vault page**

Run: `cd apps/mouth && npm run dev`
Navigate to: `http://localhost:3000/portal/vault`
Expected: Two tabs (Uploaded / Drive Files). "Drive Files" tab shows folders or "No Drive folder linked" message.

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/app/portal/\(authenticated\)/vault/page.tsx
git commit -m "feat(portal): add Drive files tab to Document Vault with folder browsing"
```

---

## Task 10: Replace Remaining Duplicated StatusBadge Instances

**Files:**

- Modify: `apps/mouth/src/app/portal/(authenticated)/companies/page.tsx`
- Modify: `apps/mouth/src/app/portal/(authenticated)/taxes/page.tsx`

- [ ] **Step 1: Replace in companies/page.tsx**

In `apps/mouth/src/app/portal/(authenticated)/companies/page.tsx`:

Add import at top:

```tsx
import { StatusBadge } from "@/components/portal";
```

Delete the local `StatusBadge` function (lines 285-313). The shared component handles both `active` and `pending` statuses.

- [ ] **Step 2: Replace in taxes/page.tsx**

In `apps/mouth/src/app/portal/(authenticated)/taxes/page.tsx`:

Add import at top:

```tsx
import { StatusBadge } from "@/components/portal";
```

Delete the local `StatusBadge` function (lines 333-366). The shared component handles `compliant`, `attention`, and `overdue` statuses.

- [ ] **Step 3: Run dev server and verify both pages**

Run: `cd apps/mouth && npm run dev`
Navigate to: `http://localhost:3000/portal/companies` and `http://localhost:3000/portal/taxes`
Expected: Status badges render identically to before.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/portal/\(authenticated\)/companies/page.tsx apps/mouth/src/app/portal/\(authenticated\)/taxes/page.tsx
git commit -m "refactor(portal): replace remaining duplicated StatusBadge with shared component"
```

---

## Summary

| Task | Description                         | Backend | Frontend | Est.   |
| ---- | ----------------------------------- | ------- | -------- | ------ |
| 1    | Extract StatusBadge                 |         | ✅       | 5 min  |
| 2    | Extract CountdownChip               |         | ✅       | 5 min  |
| 3    | Process Timeline endpoint           | ✅      |          | 15 min |
| 4    | Drive Files proxy endpoint          | ✅      |          | 15 min |
| 5    | API types + client methods          |         | ✅       | 5 min  |
| 6    | React Query hooks                   |         | ✅       | 5 min  |
| 7    | ProcessStepper component            |         | ✅       | 10 min |
| 8    | Integrate stepper into Process page |         | ✅       | 10 min |
| 9    | Integrate Drive into Vault page     |         | ✅       | 15 min |
| 10   | Replace remaining StatusBadge dupes |         | ✅       | 5 min  |

**Total: 10 tasks, ~90 minutes, 10 commits**

**Not in this plan (deferred to Fase 1.5):**

- P0.3 Billing Page — requires investigation of `invoices` table existence and schema
- `practice_status_log` table migration — the timeline endpoint gracefully falls back if the table doesn't exist; migration is a separate task
