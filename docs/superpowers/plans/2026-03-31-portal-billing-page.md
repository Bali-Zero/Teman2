# Portal Billing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/portal/billing` page where clients can see their invoices, payment status, and download invoice PDFs — exposing data already in the `invoices` table and `practices` table.

**Architecture:** Backend adds 2 endpoints to a new `portal_billing.py` router that reads from the existing `invoices` table (joined with `practices` and `practice_types` for context). Frontend adds a new billing page with invoice list, status badges, and PDF download links. Navigation updated to include Billing in the portal sidebar.

**Tech Stack:** FastAPI (backend), asyncpg, Next.js App Router (frontend), React Query, Warm Depth design tokens, shared `StatusBadge` and `CountdownChip` components from Fase 1.

---

## File Structure

### Backend (new files)

| File                                                | Responsibility                                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `backend/app/routers/portal_billing.py`             | `GET /api/portal/billing` (invoice list) + `GET /api/portal/billing/{invoice_id}/pdf-url` (Drive download redirect) |
| `backend/tests/unit/routers/test_portal_billing.py` | Tests for billing endpoints                                                                                         |

### Backend (modified files)

| File                                       | Change                           |
| ------------------------------------------ | -------------------------------- |
| `backend/app/setup/router_registration.py` | Register `portal_billing` router |

### Frontend (new files)

| File                                                            | Responsibility                    |
| --------------------------------------------------------------- | --------------------------------- |
| `apps/mouth/src/app/portal/(authenticated)/billing/page.tsx`    | Billing page with invoice list    |
| `apps/mouth/src/app/portal/(authenticated)/billing/loading.tsx` | Loading skeleton                  |
| `apps/mouth/src/app/portal/(authenticated)/billing/error.tsx`   | Error boundary                    |
| `apps/mouth/src/hooks/usePortalBilling.ts`                      | React Query hook for billing data |

### Frontend (modified files)

| File                                            | Change                                      |
| ----------------------------------------------- | ------------------------------------------- |
| `apps/mouth/src/lib/api/portal/portal.types.ts` | Add `PortalInvoice`, `BillingSummary` types |
| `apps/mouth/src/lib/api/portal/portal.api.ts`   | Add `getBilling()` method                   |
| `apps/mouth/src/types/navigation.ts`            | Add Billing to portal navigation            |

---

## Task 1: Backend — Billing Endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/portal_billing.py`
- Create: `apps/backend-rag/backend/tests/unit/routers/test_portal_billing.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/backend-rag/backend/tests/unit/routers/test_portal_billing.py
"""Tests for portal billing endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.routers.portal_billing import _get_client_billing


@pytest.mark.asyncio
async def test_billing_returns_invoices_for_client():
    """Billing endpoint returns invoices joined with practice data."""
    mock_conn = AsyncMock()

    mock_conn.fetch.return_value = [
        {
            "id": 1,
            "invoice_number": "INV-2026-001",
            "amount_idr": 20000000.0,
            "invoice_source": "local_pdf",
            "drive_file_id": "abc123",
            "drive_web_link": "https://drive.google.com/file/abc123",
            "email_sent_to_client": True,
            "generated_at": "2026-02-15T10:00:00+00:00",
            "created_at": "2026-02-15T10:00:00+00:00",
            "practice_id": 10,
            "practice_name": "KITAS B211A",
            "practice_category": "visa",
            "payment_status": "pending",
            "quoted_price": 20000000.0,
        },
        {
            "id": 2,
            "invoice_number": "INV-2026-002",
            "amount_idr": 35000000.0,
            "invoice_source": "local_pdf",
            "drive_file_id": "def456",
            "drive_web_link": "https://drive.google.com/file/def456",
            "email_sent_to_client": True,
            "generated_at": "2026-03-01T09:00:00+00:00",
            "created_at": "2026-03-01T09:00:00+00:00",
            "practice_id": 15,
            "practice_name": "PT PMA Setup",
            "practice_category": "company",
            "payment_status": "paid",
            "quoted_price": 35000000.0,
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _get_client_billing(mock_pool, client_id=1)

    assert result is not None
    assert len(result["invoices"]) == 2
    assert result["invoices"][0]["invoice_number"] == "INV-2026-001"
    assert result["invoices"][0]["payment_status"] == "pending"
    assert result["summary"]["total_invoiced"] == 55000000.0
    assert result["summary"]["total_paid"] == 35000000.0
    assert result["summary"]["total_pending"] == 20000000.0


@pytest.mark.asyncio
async def test_billing_returns_empty_for_client_with_no_invoices():
    """Billing endpoint returns empty list and zero summary when no invoices exist."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _get_client_billing(mock_pool, client_id=999)

    assert result is not None
    assert len(result["invoices"]) == 0
    assert result["summary"]["total_invoiced"] == 0
    assert result["summary"]["total_paid"] == 0
    assert result["summary"]["total_pending"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_billing.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write the backend router**

```python
# apps/backend-rag/backend/app/routers/portal_billing.py
"""
Portal Billing Router.

Exposes invoice data to client portal. Reads from `invoices` table
joined with `practices` for context (practice name, category, payment status).
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/billing", tags=["portal-billing"])


async def _get_client_billing(
    pool: asyncpg.Pool,
    client_id: int,
) -> dict[str, Any]:
    """Get all invoices for a client with summary stats."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                i.id,
                i.invoice_number,
                i.amount_idr,
                i.invoice_source,
                i.drive_file_id,
                i.drive_web_link,
                i.email_sent_to_client,
                i.generated_at,
                i.created_at,
                i.practice_id,
                pt.name AS practice_name,
                pt.category AS practice_category,
                p.payment_status,
                p.quoted_price
            FROM invoices i
            JOIN practices p ON p.id = i.practice_id
            JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE i.client_id = $1
            ORDER BY i.created_at DESC
            """,
            client_id,
        )

    invoices = []
    total_invoiced = 0.0
    total_paid = 0.0

    for row in rows:
        amount = float(row["amount_idr"] or 0)
        payment_status = row["payment_status"] or "pending"
        total_invoiced += amount
        if payment_status == "paid":
            total_paid += amount

        invoices.append({
            "id": row["id"],
            "invoice_number": row["invoice_number"],
            "amount_idr": amount,
            "invoice_source": row["invoice_source"],
            "has_pdf": bool(row["drive_file_id"]),
            "drive_web_link": row["drive_web_link"],
            "email_sent": bool(row["email_sent_to_client"]),
            "generated_at": str(row["generated_at"]) if row["generated_at"] else None,
            "created_at": str(row["created_at"]) if row["created_at"] else None,
            "practice_id": row["practice_id"],
            "practice_name": row["practice_name"],
            "practice_category": row["practice_category"],
            "payment_status": payment_status,
        })

    return {
        "invoices": invoices,
        "summary": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_pending": total_invoiced - total_paid,
            "count": len(invoices),
        },
    }


@router.get("")
async def get_billing(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get all invoices and billing summary for the authenticated client."""
    try:
        result = await _get_client_billing(db_pool, client["client_id"])
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to get billing for client {client['client_id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load billing data")


@router.get("/{invoice_id}/pdf-url")
async def get_invoice_pdf_url(
    invoice_id: int,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get the Drive download URL for an invoice PDF.

    Security: validates that the invoice belongs to the requesting client.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT drive_web_link, drive_file_id FROM invoices WHERE id = $1 AND client_id = $2",
            invoice_id,
            client["client_id"],
        )

    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not row["drive_web_link"] and not row["drive_file_id"]:
        raise HTTPException(status_code=404, detail="Invoice PDF not available")

    return {
        "success": True,
        "data": {
            "download_url": row["drive_web_link"],
            "drive_file_id": row["drive_file_id"],
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_billing.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Register the router**

In `apps/backend-rag/backend/app/setup/router_registration.py`, add in the portal section:

```python
from backend.app.routers.portal_billing import router as portal_billing_router
app.include_router(portal_billing_router)
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/portal_billing.py apps/backend-rag/backend/tests/unit/routers/test_portal_billing.py apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(portal): add billing endpoint exposing invoices to client portal"
```

---

## Task 2: Frontend — API Types, Client Method, Hook

**Files:**

- Modify: `apps/mouth/src/lib/api/portal/portal.types.ts`
- Modify: `apps/mouth/src/lib/api/portal/portal.api.ts`
- Create: `apps/mouth/src/hooks/usePortalBilling.ts`

- [ ] **Step 1: Add types to portal.types.ts**

Append to `apps/mouth/src/lib/api/portal/portal.types.ts`:

```ts
// ============================================================================
// Billing Types
// ============================================================================

export interface PortalInvoice {
  id: number;
  invoice_number: string;
  amount_idr: number;
  invoice_source: string;
  has_pdf: boolean;
  drive_web_link: string | null;
  email_sent: boolean;
  generated_at: string | null;
  created_at: string | null;
  practice_id: number;
  practice_name: string;
  practice_category: string;
  payment_status: string;
}

export interface BillingSummary {
  total_invoiced: number;
  total_paid: number;
  total_pending: number;
  count: number;
}

export interface BillingResponse {
  invoices: PortalInvoice[];
  summary: BillingSummary;
}
```

- [ ] **Step 2: Add API method to portal.api.ts**

Add import `BillingResponse` to the type import, then add method to `PortalApi` class:

```ts
  // ============================================================================
  // Billing
  // ============================================================================

  async getBilling(): Promise<BillingResponse> {
    const response = await this.client.request<PortalApiResponse<BillingResponse>>(
      "/api/portal/billing",
      { method: "GET" },
    );
    return response.data!;
  }

  async getInvoicePdfUrl(invoiceId: number): Promise<{ download_url: string; drive_file_id: string }> {
    const response = await this.client.request<PortalApiResponse<{ download_url: string; drive_file_id: string }>>(
      `/api/portal/billing/${invoiceId}/pdf-url`,
      { method: "GET" },
    );
    return response.data!;
  }
```

- [ ] **Step 3: Create the React Query hook**

```ts
// apps/mouth/src/hooks/usePortalBilling.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { BillingResponse } from "@/lib/api/portal/portal.types";

export function usePortalBilling() {
  return useQuery<BillingResponse>({
    queryKey: ["portal", "billing"],
    queryFn: () => api.portal.getBilling(),
    staleTime: 120_000,
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/lib/api/portal/portal.types.ts apps/mouth/src/lib/api/portal/portal.api.ts apps/mouth/src/hooks/usePortalBilling.ts
git commit -m "feat(portal): add billing API types, client method, and React Query hook"
```

---

## Task 3: Frontend — Billing Page

**Files:**

- Create: `apps/mouth/src/app/portal/(authenticated)/billing/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/billing/loading.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/billing/error.tsx`

- [ ] **Step 1: Create the loading skeleton**

```tsx
// apps/mouth/src/app/portal/(authenticated)/billing/loading.tsx
export default function BillingLoading() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <section>
        <div
          className="h-7 w-40 rounded animate-pulse"
          style={{ background: "var(--bz-border)" }}
        />
        <div
          className="h-4 w-64 rounded mt-2 animate-pulse"
          style={{ background: "var(--bz-border)", opacity: 0.5 }}
        />
      </section>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-xl border p-4 h-24 animate-pulse"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          />
        ))}
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border p-4 h-20 animate-pulse"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create the error boundary**

```tsx
// apps/mouth/src/app/portal/(authenticated)/billing/error.tsx
"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function BillingError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        <p style={{ color: "var(--bz-text-2)" }}>Your invoices and payments</p>
      </section>
      <section
        className="rounded-xl border p-8 text-center"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
        }}
      >
        <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-amber-400" />
        <p className="font-medium">Failed to load billing data</p>
        <p className="text-sm mt-1" style={{ color: "var(--bz-text-2)" }}>
          {error.message}
        </p>
        <Button onClick={reset} variant="outline" className="mt-4">
          Retry
        </Button>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Create the billing page**

```tsx
// apps/mouth/src/app/portal/(authenticated)/billing/page.tsx
"use client";

import React from "react";
import {
  DollarSign,
  Download,
  FileText,
  CheckCircle,
  Clock,
  AlertTriangle,
  Receipt,
} from "lucide-react";
import { usePortalBilling } from "@/hooks/usePortalBilling";
import { StatusBadge, CountdownChip } from "@/components/portal";
import { PortalCardSkeleton } from "@/components/portal";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type { PortalInvoice } from "@/lib/api/portal/portal.types";

const formatIDR = (amount: number) =>
  new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
  }).format(amount);

export default function BillingPage() {
  const { data, isLoading, isError, error } = usePortalBilling();
  const { error: toastError } = useToast();

  const handleDownloadPdf = async (invoice: PortalInvoice) => {
    try {
      const result = await api.portal.getInvoicePdfUrl(invoice.id);
      if (result.download_url) {
        window.open(result.download_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      toastError("Download failed", "Could not get invoice PDF");
      logger.error("Failed to get invoice PDF URL", {}, err as Error);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-40 rounded animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-4 w-64 rounded mt-2 animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
        </section>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <PortalCardSkeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        </section>
        <section
          className="rounded-xl border p-8 text-center"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        >
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-amber-400" />
          <p>
            {error instanceof Error
              ? error.message
              : "Failed to load billing data"}
          </p>
          <Button
            onClick={() => window.location.reload()}
            variant="outline"
            className="mt-3"
          >
            Retry
          </Button>
        </section>
      </div>
    );
  }

  const summary = data?.summary;
  const invoices = data?.invoices ?? [];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        <p style={{ color: "var(--bz-text-2)" }}>Your invoices and payments</p>
      </section>

      {/* Summary Cards */}
      {summary && summary.count > 0 && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            className="rounded-xl border p-5"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Total Invoiced
            </p>
            <p className="text-xl font-bold font-mono">
              {formatIDR(summary.total_invoiced)}
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--bz-text-3)" }}>
              {summary.count} invoice{summary.count !== 1 ? "s" : ""}
            </p>
          </div>
          <div
            className="rounded-xl border p-5"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Paid
            </p>
            <p
              className="text-xl font-bold font-mono"
              style={{ color: "#34d399" }}
            >
              {formatIDR(summary.total_paid)}
            </p>
          </div>
          <div
            className="rounded-xl border p-5"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Outstanding
            </p>
            <p
              className="text-xl font-bold font-mono"
              style={{
                color: summary.total_pending > 0 ? "#fbbf24" : "#34d399",
              }}
            >
              {formatIDR(summary.total_pending)}
            </p>
          </div>
        </section>
      )}

      {/* Invoice List */}
      <section className="space-y-3">
        {invoices.length === 0 ? (
          <div
            className="rounded-xl border border-dashed p-12 text-center"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <Receipt
              className="w-16 h-16 mx-auto mb-4 opacity-30"
              style={{ color: "var(--bz-text-2)" }}
            />
            <h2
              className="text-lg font-semibold"
              style={{ color: "var(--bz-text-2)" }}
            >
              No invoices yet
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--bz-text-3)" }}>
              Invoices will appear here when your services are billed.
            </p>
          </div>
        ) : (
          invoices.map((invoice) => (
            <div
              key={invoice.id}
              className="rounded-lg border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "rgba(30,30,35,0.7)",
                borderColor: "rgba(255,255,255,0.05)",
              }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="p-2 rounded-md"
                  style={{ background: "rgba(201,169,110,0.12)" }}
                >
                  <FileText
                    className="w-5 h-5"
                    style={{ color: "var(--bz-accent-warm)" }}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm font-mono">
                      {invoice.invoice_number}
                    </span>
                    <StatusBadge status={invoice.payment_status} />
                  </div>
                  <p
                    className="text-xs mt-1"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    {invoice.practice_name} ({invoice.practice_category})
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-lg font-bold font-mono">
                      {formatIDR(invoice.amount_idr)}
                    </span>
                    {invoice.generated_at && (
                      <CountdownChip date={invoice.generated_at} mode="age" />
                    )}
                  </div>
                  {invoice.generated_at && (
                    <p
                      className="text-xs mt-0.5"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      Issued:{" "}
                      {new Date(invoice.generated_at).toLocaleDateString(
                        "en-US",
                        { month: "short", day: "numeric", year: "numeric" },
                      )}
                    </p>
                  )}
                </div>
                {invoice.has_pdf && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDownloadPdf(invoice)}
                    aria-label={`Download invoice ${invoice.invoice_number}`}
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </section>

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "rgba(201,169,110,0.06)",
          borderColor: "rgba(201,169,110,0.3)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--bz-accent-warm)" }}>
          For payment inquiries or to request a receipt, please contact your
          account manager or send us a message through Chat.
        </p>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/portal/\(authenticated\)/billing/
git commit -m "feat(portal): add billing page with invoice list and PDF download"
```

---

## Task 4: Update Portal Navigation

**Files:**

- Modify: `apps/mouth/src/types/navigation.ts`

- [ ] **Step 1: Add Billing to portal navigation**

In `apps/mouth/src/types/navigation.ts`, find the `portalNavigation` constant. In the "Services" section (after LKPM), add:

```ts
      { title: "Billing", href: "/portal/billing", icon: "Receipt" },
```

So the Services block becomes:

```ts
  {
    title: "Services",
    items: [
      { title: "Companies", href: "/portal/companies", icon: "Building2" },
      { title: "Visa", href: "/portal/visa", icon: "Briefcase" },
      { title: "Taxes", href: "/portal/taxes", icon: "FileText" },
      { title: "LKPM", href: "/portal/lkpm", icon: "ClipboardCheck" },
      { title: "Billing", href: "/portal/billing", icon: "Receipt" },
    ],
  },
```

- [ ] **Step 2: Commit**

```bash
git add apps/mouth/src/types/navigation.ts
git commit -m "feat(portal): add Billing to portal navigation sidebar"
```

---

## Summary

| Task | Description                    | Backend | Frontend | Est.   |
| ---- | ------------------------------ | ------- | -------- | ------ |
| 1    | Billing endpoint + tests       | ✅      |          | 15 min |
| 2    | API types + hook               |         | ✅       | 5 min  |
| 3    | Billing page + loading + error |         | ✅       | 15 min |
| 4    | Navigation update              |         | ✅       | 2 min  |

**Total: 4 tasks, ~37 minutes, 4 commits**

**Dependencies:**

- Requires `invoices` table to exist in production DB (confirmed: `INSERT INTO invoices` in invoice_service.py with `ON CONFLICT (invoice_number)`)
- Uses shared `StatusBadge` and `CountdownChip` from Fase 1
- Uses `get_current_client` auth dependency from `portal.py`
