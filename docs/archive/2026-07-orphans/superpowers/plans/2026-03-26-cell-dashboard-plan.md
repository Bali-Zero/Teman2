# CELL Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CELL a face — a real-time dashboard at `/admin/cell` with a floating heartbeat widget on all admin pages.

**Architecture:** CELL (Mac Pro) writes pulse state to PostgreSQL every 60s. Backend serves `GET /api/cell/status`. Frontend polls every 10s and renders an organic, living visualization.

**Tech Stack:** PostgreSQL (table), FastAPI (endpoint), Next.js App Router, shadcn/ui, lucide-react, CSS animations, Tailwind

**Spec:** `docs/superpowers/specs/2026-03-26-cell-dashboard-design.md`

---

## File Structure

```
Backend (apps/backend-rag/):
  backend/app/routers/cell_status.py         # GET /api/cell/status
  backend/app/setup/router_registration.py   # Register new router (modify)

CELL (apps/cell/):
  cell/core/db.py                            # asyncpg pool for pulse logging
  cell/core/pulse.py                         # Add DB write after each pulse (modify)
  cell/main.py                               # Wire DB pool (modify)

Frontend (apps/mouth/):
  src/hooks/useCellStatus.ts                 # Polling hook
  src/components/cell/CellWidget.tsx         # Floating heartbeat widget
  src/components/cell/OrganismView.tsx       # Central pulsing organism
  src/components/cell/VitalSigns.tsx         # 4 metric cards
  src/components/cell/MetabolismBar.tsx      # Budget progress bar
  src/components/cell/PulseTimeline.tsx      # 50-block timeline
  src/components/cell/CellDashboard.tsx      # Full dashboard composition
  src/app/(workspace)/admin/cell/page.tsx    # Page route
  src/app/(workspace)/layout.tsx             # Add CellWidget (modify)
```

---

## Task 1: PostgreSQL Table + CELL DB Writer

**Files:**

- Create: `apps/cell/cell/core/db.py`
- Modify: `apps/cell/cell/core/pulse.py`
- Modify: `apps/cell/cell/main.py`

- [ ] **Step 1: Create the cell_pulse_log table via fly proxy**

```bash
# Open fly proxy in background (if not already open)
fly proxy 15432:5432 -a nuzantara-postgres &

# Create table
psql "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag" -c "
CREATE TABLE IF NOT EXISTS cell_pulse_log (
    id SERIAL PRIMARY KEY,
    pulse_number INT NOT NULL,
    health_status VARCHAR(10) NOT NULL,
    response_time_ms INT DEFAULT 0,
    dna_intact BOOLEAN DEFAULT true,
    budget_spent FLOAT DEFAULT 0.0,
    budget_limit FLOAT DEFAULT 10.0,
    memory_stm_count INT DEFAULT 0,
    memory_ltm_count INT DEFAULT 0,
    procedures_count INT DEFAULT 0,
    cells_active INT DEFAULT 1,
    cells_total INT DEFAULT 1,
    action_taken VARCHAR(255) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_pulse_log_created ON cell_pulse_log(created_at DESC);
"
```

- [ ] **Step 2: Create db.py — asyncpg pool manager**

```python
# apps/cell/cell/core/db.py
"""Database connection for CELL pulse logging."""
import asyncpg
import logging
from typing import Any

from cell.core.config import settings

logger = logging.getLogger("cell.db")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        logger.info("Creating database connection pool...")
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=2,
        )
        logger.info("Database pool created.")
    return _pool


async def close_pool() -> None:
    """Close the database pool on shutdown."""
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
        logger.info("Database pool closed.")
        _pool = None


async def log_pulse(
    pulse_number: int,
    health_status: str,
    response_time_ms: int,
    dna_intact: bool,
    budget_spent: float,
    budget_limit: float,
    memory_stm_count: int = 0,
    memory_ltm_count: int = 0,
    procedures_count: int = 0,
    cells_active: int = 1,
    cells_total: int = 1,
    action_taken: str | None = None,
    error_message: str | None = None,
) -> None:
    """Write a pulse record to PostgreSQL."""
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_pulse_log
               (pulse_number, health_status, response_time_ms, dna_intact,
                budget_spent, budget_limit, memory_stm_count, memory_ltm_count,
                procedures_count, cells_active, cells_total, action_taken, error_message)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            pulse_number, health_status, response_time_ms, dna_intact,
            budget_spent, budget_limit, memory_stm_count, memory_ltm_count,
            procedures_count, cells_active, cells_total, action_taken, error_message,
        )
    except Exception as e:
        logger.error(f"Failed to log pulse to DB: {e}")
```

- [ ] **Step 3: Modify pulse.py — add DB write after each pulse**

Add at the end of `single_pulse()`, before the return:

```python
# At top of file, add import:
from cell.core import db as cell_db

# At end of single_pulse(), before return PulseResult:
        # 6. PERSIST to PostgreSQL for dashboard
        try:
            await cell_db.log_pulse(
                pulse_number=0,  # Will be set by caller
                health_status=status.value,
                response_time_ms=int(reading.response_time_seconds * 1000) if reading.reachable else 0,
                dna_intact=True,
                budget_spent=self._metabolism.daily_spend,
                budget_limit=self._metabolism._daily_limit,
            )
        except Exception as e:
            logger.error(f"Pulse DB log failed: {e}")
```

Actually, the pulse_number needs to come from main.py. Better approach — add it as a parameter:

```python
    async def single_pulse(self, pulse_number: int = 0) -> PulseResult:
```

And log after evaluate:

```python
        # 6. PERSIST
        try:
            await cell_db.log_pulse(
                pulse_number=pulse_number,
                health_status=status.value,
                response_time_ms=int(reading.response_time_seconds * 1000) if reading.reachable else 0,
                dna_intact=True,
                budget_spent=self._metabolism.daily_spend,
                budget_limit=self._metabolism._daily_limit,
            )
        except Exception as e:
            logger.error(f"Pulse DB log failed: {e}")
```

- [ ] **Step 4: Modify main.py — pass pulse_number and close pool on shutdown**

In the main loop, change:

```python
result = await engine.single_pulse()
```

to:

```python
result = await engine.single_pulse(pulse_number=pulse_count)
```

Add pool cleanup before shutdown message:

```python
    from cell.core.db import close_pool
    await close_pool()
    logger.info("CELL organism shutdown complete.")
```

- [ ] **Step 5: Test by running CELL for 2 pulses, then check DB**

```bash
cd apps/cell && source .venv/bin/activate
pip install asyncpg  # if not already installed
PYTHONPATH=. timeout 130 python -m cell.main
```

Then verify:

```bash
psql "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag" -c "SELECT pulse_number, health_status, response_time_ms, budget_spent, created_at FROM cell_pulse_log ORDER BY created_at DESC LIMIT 5;"
```

Expected: 2 rows with health_status='green'

- [ ] **Step 6: Commit**

```bash
git add apps/cell/cell/core/db.py apps/cell/cell/core/pulse.py apps/cell/cell/main.py
git commit -m "feat(cell): persist pulse state to PostgreSQL for dashboard"
```

---

## Task 2: Backend API Endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/cell_status.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 1: Create cell_status.py router**

```python
# apps/backend-rag/backend/app/routers/cell_status.py
"""CELL organism status endpoint — serves dashboard data."""
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from backend.app.dependencies import get_db_pool, get_current_user

router = APIRouter(prefix="/api/cell", tags=["cell"])


@router.get("/status")
async def get_cell_status(
    db_pool=Depends(get_db_pool),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """Get CELL organism status for dashboard.

    Returns latest pulse, recent pulses, and 24h uptime stats.
    Admin only.
    """
    async with db_pool.acquire() as conn:
        # Latest pulse
        last = await conn.fetchrow(
            "SELECT * FROM cell_pulse_log ORDER BY created_at DESC LIMIT 1"
        )

        # Recent 50 pulses
        recent = await conn.fetch(
            """SELECT pulse_number, health_status, response_time_ms, created_at
               FROM cell_pulse_log ORDER BY created_at DESC LIMIT 50"""
        )

        # 24h uptime aggregation
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stats = await conn.fetchrow(
            """SELECT
                 COUNT(*) as total,
                 COUNT(*) FILTER (WHERE health_status = 'green') as green_count,
                 COUNT(*) FILTER (WHERE health_status = 'yellow') as yellow_count,
                 COUNT(*) FILTER (WHERE health_status = 'red') as red_count
               FROM cell_pulse_log
               WHERE created_at > $1""",
            cutoff,
        )

    # Determine if alive (last pulse within 120s)
    alive = False
    if last:
        age = (datetime.now(timezone.utc) - last["created_at"]).total_seconds()
        alive = age < 120

    total = stats["total"] if stats else 0

    return {
        "alive": alive,
        "last_pulse": dict(last) if last else None,
        "recent_pulses": [dict(r) for r in recent],
        "uptime_24h": {
            "green_percent": round(stats["green_count"] / total * 100, 1) if total > 0 else 0,
            "yellow_percent": round(stats["yellow_count"] / total * 100, 1) if total > 0 else 0,
            "red_percent": round(stats["red_count"] / total * 100, 1) if total > 0 else 0,
            "total_pulses": total,
        },
    }
```

- [ ] **Step 2: Register router in router_registration.py**

Add after the other admin router imports (around line 269):

```python
    from backend.app.routers import cell_status
    api.include_router(cell_status.router)
```

- [ ] **Step 3: Test locally**

```bash
cd apps/backend-rag && source .venv/bin/activate
# Start backend
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000 &
# Test endpoint (need auth token)
curl -s http://localhost:8000/api/cell/status -H "Authorization: Bearer YOUR_TOKEN" | python -m json.tool
```

Or test via Fly.io after deploy:

```bash
curl -s https://nuzantara-rag.fly.dev/api/cell/status -H "Authorization: Bearer YOUR_TOKEN" | python -m json.tool
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/routers/cell_status.py apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(api): add GET /api/cell/status endpoint for CELL dashboard"
```

- [ ] **Step 5: Deploy backend**

```bash
cd apps/backend-rag && fly deploy --strategy rolling
```

---

## Task 3: Frontend Hook — useCellStatus

**Files:**

- Create: `apps/mouth/src/hooks/useCellStatus.ts`

- [ ] **Step 1: Create the polling hook**

```typescript
// apps/mouth/src/hooks/useCellStatus.ts
"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

export interface CellPulse {
  pulse_number: number;
  health_status: "green" | "yellow" | "red";
  response_time_ms: number;
  dna_intact: boolean;
  budget_spent: number;
  budget_limit: number;
  memory_stm_count: number;
  memory_ltm_count: number;
  procedures_count: number;
  cells_active: number;
  cells_total: number;
  action_taken: string | null;
  created_at: string;
}

export interface CellStatus {
  alive: boolean;
  last_pulse: CellPulse | null;
  recent_pulses: Pick<
    CellPulse,
    "pulse_number" | "health_status" | "response_time_ms" | "created_at"
  >[];
  uptime_24h: {
    green_percent: number;
    yellow_percent: number;
    red_percent: number;
    total_pulses: number;
  };
}

export function useCellStatus(pollIntervalMs: number = 10000) {
  const [status, setStatus] = useState<CellStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev"}/api/cell/status`,
        {
          headers: {
            Authorization: `Bearer ${api.getToken()}`,
          },
        },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      logger.error("Failed to fetch CELL status:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!api.isAuthenticated() || !api.isAdmin()) return;
    fetchStatus();
    const interval = setInterval(fetchStatus, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchStatus, pollIntervalMs]);

  return { status, loading, error, refetch: fetchStatus };
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/mouth/src/hooks/useCellStatus.ts
git commit -m "feat(mouth): add useCellStatus polling hook for CELL dashboard"
```

---

## Task 4: Floating Widget — CellWidget

**Files:**

- Create: `apps/mouth/src/components/cell/CellWidget.tsx`
- Modify: `apps/mouth/src/app/(workspace)/layout.tsx`

- [ ] **Step 1: Create CellWidget.tsx**

```tsx
// apps/mouth/src/components/cell/CellWidget.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCellStatus } from "@/hooks/useCellStatus";
import { api } from "@/lib/api";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

export function CellWidget() {
  const [expanded, setExpanded] = useState(false);
  const router = useRouter();
  const { status, loading } = useCellStatus(10000);

  // Only show for admin users
  if (!api.isAdmin()) return null;

  const color = status?.alive
    ? HEALTH_COLORS[status.last_pulse?.health_status || "green"]
    : "#666";
  const emoji = loading ? "⏳" : status?.alive ? "🧬" : "💀";
  const pulse = status?.last_pulse;

  return (
    <>
      {/* Floating circle */}
      <button
        onClick={() => setExpanded(!expanded)}
        title={
          pulse
            ? `CELL — Pulse #${pulse.pulse_number} — ${pulse.health_status.toUpperCase()}`
            : "CELL — Loading..."
        }
        style={{
          position: "fixed",
          bottom: 16,
          right: 16,
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#111",
          border: `2px solid ${color}`,
          boxShadow: status?.alive
            ? `0 0 12px ${color}40, 0 0 24px ${color}20`
            : "none",
          cursor: "pointer",
          zIndex: 50,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 18,
          animation: status?.alive ? "cell-pulse 2s infinite" : "none",
          transition: "all 0.3s ease",
        }}
      >
        {emoji}
      </button>

      {/* Expanded panel */}
      {expanded && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setExpanded(false)}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 49,
            }}
          />
          {/* Panel */}
          <div
            style={{
              position: "fixed",
              bottom: 64,
              right: 16,
              width: 280,
              background: "#111",
              border: "1px solid #333",
              borderRadius: 12,
              padding: 16,
              zIndex: 51,
              fontFamily: "system-ui, sans-serif",
              color: "#e5e5e5",
              fontSize: 13,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 12,
              }}
            >
              <span style={{ fontSize: 20 }}>🧬</span>
              <span style={{ fontWeight: 600, fontSize: 15 }}>CELL</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 11,
                  color: "#666",
                }}
              >
                v0.1.0
              </span>
            </div>

            {!status || !pulse ? (
              <div style={{ color: "#666" }}>Loading...</div>
            ) : (
              <>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 8,
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: color,
                      display: "inline-block",
                    }}
                  />
                  <span>
                    {status.alive ? pulse.health_status.toUpperCase() : "DEAD"}
                  </span>
                  <span style={{ color: "#666", marginLeft: "auto" }}>
                    Pulse #{pulse.pulse_number}
                  </span>
                </div>

                <div style={{ color: "#888", marginBottom: 4 }}>
                  Response: {pulse.response_time_ms}ms
                </div>

                {/* Budget bar */}
                <div style={{ marginBottom: 8 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: "#666",
                      marginBottom: 2,
                    }}
                  >
                    <span>Budget</span>
                    <span>
                      ${pulse.budget_spent.toFixed(2)} / $
                      {pulse.budget_limit.toFixed(2)}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 4,
                      background: "#222",
                      borderRadius: 2,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${(pulse.budget_spent / pulse.budget_limit) * 100}%`,
                        background: color,
                        borderRadius: 2,
                        transition: "width 0.3s",
                      }}
                    />
                  </div>
                </div>

                <div style={{ color: "#888", fontSize: 12, marginBottom: 12 }}>
                  {pulse.action_taken || "Observing..."}
                </div>

                <button
                  onClick={() => {
                    setExpanded(false);
                    router.push("/admin/cell");
                  }}
                  style={{
                    width: "100%",
                    padding: "8px 0",
                    background: "#222",
                    border: "1px solid #333",
                    borderRadius: 6,
                    color: "#e5e5e5",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  Open CELL Dashboard →
                </button>
              </>
            )}
          </div>
        </>
      )}

      {/* Pulse animation */}
      <style jsx global>{`
        @keyframes cell-pulse {
          0%,
          100% {
            box-shadow:
              0 0 12px ${color}40,
              0 0 24px ${color}20;
          }
          50% {
            box-shadow:
              0 0 20px ${color}60,
              0 0 40px ${color}30;
          }
        }
      `}</style>
    </>
  );
}
```

- [ ] **Step 2: Add CellWidget to workspace layout**

In `apps/mouth/src/app/(workspace)/layout.tsx`, add inside the return, after `<ErrorBoundary>{children}</ErrorBoundary>`:

```tsx
import { CellWidget } from "@/components/cell/CellWidget";

// Inside the return, after children:
<CellWidget />;
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/cell/CellWidget.tsx apps/mouth/src/app/\(workspace\)/layout.tsx
git commit -m "feat(mouth): floating CELL heartbeat widget on all admin pages"
```

---

## Task 5: Dashboard Page — OrganismView + VitalSigns

**Files:**

- Create: `apps/mouth/src/components/cell/OrganismView.tsx`
- Create: `apps/mouth/src/components/cell/VitalSigns.tsx`

- [ ] **Step 1: Create OrganismView.tsx**

```tsx
// apps/mouth/src/components/cell/OrganismView.tsx
"use client";

import type { CellPulse } from "@/hooks/useCellStatus";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

const ORGANS = [
  { label: "SENSE", angle: 0, color: "#22c55e" },
  { label: "MEMORY", angle: 90, color: "#3b82f6" },
  { label: "HEAL", angle: 180, color: "#f59e0b" },
  { label: "THINK", angle: 270, color: "#8b5cf6" },
];

export function OrganismView({
  pulse,
  alive,
}: {
  pulse: CellPulse | null;
  alive: boolean;
}) {
  const color = alive ? HEALTH_COLORS[pulse?.health_status || "green"] : "#666";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        minHeight: 300,
        position: "relative",
      }}
    >
      {/* Orbit ring */}
      <div
        style={{
          position: "absolute",
          width: 220,
          height: 220,
          border: `1px solid ${color}33`,
          borderRadius: "50%",
          transition: "border-color 0.5s",
        }}
      />

      {/* Central pulse */}
      <div
        style={{
          width: 100,
          height: 100,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${color} 0%, #0a0a0a 70%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 36,
          animation: alive ? "organism-pulse 2s infinite" : "none",
          transition: "all 0.5s",
        }}
      >
        {alive ? "🧬" : "💀"}
      </div>

      {/* Orbiting organ labels */}
      {ORGANS.map((organ) => {
        const rad = (organ.angle * Math.PI) / 180;
        const x = Math.cos(rad) * 130;
        const y = Math.sin(rad) * 130;
        return (
          <div
            key={organ.label}
            style={{
              position: "absolute",
              left: `calc(50% + ${x}px)`,
              top: `calc(50% + ${y}px)`,
              transform: "translate(-50%, -50%)",
              fontSize: 11,
              fontWeight: 600,
              color: organ.color,
              letterSpacing: "0.05em",
              opacity: alive ? 0.9 : 0.3,
              transition: "opacity 0.5s",
            }}
          >
            {organ.label}
          </div>
        );
      })}

      {/* Pulse info below */}
      {pulse && (
        <div
          style={{
            position: "absolute",
            bottom: 10,
            display: "flex",
            gap: 20,
            fontSize: 11,
            color: "#666",
          }}
        >
          <span>Pulse #{pulse.pulse_number}</span>
          <span>Health: {pulse.health_status.toUpperCase()}</span>
          <span>${pulse.budget_spent.toFixed(2)} spent</span>
        </div>
      )}

      <style jsx global>{`
        @keyframes organism-pulse {
          0%,
          100% {
            box-shadow: 0 0 30px ${color}30;
          }
          50% {
            box-shadow: 0 0 60px ${color}50;
          }
        }
      `}</style>
    </div>
  );
}
```

- [ ] **Step 2: Create VitalSigns.tsx**

```tsx
// apps/mouth/src/components/cell/VitalSigns.tsx
"use client";

import type { CellPulse } from "@/hooks/useCellStatus";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

function VitalCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: string;
  subtitle?: string;
  color?: string;
}) {
  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #222",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: "#666",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 700,
          color: color || "#e5e5e5",
          fontFamily: "monospace",
        }}
      >
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

export function VitalSigns({
  pulse,
  alive,
}: {
  pulse: CellPulse | null;
  alive: boolean;
}) {
  if (!pulse) return null;

  const healthColor = alive ? HEALTH_COLORS[pulse.health_status] : "#666";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 12,
      }}
    >
      <VitalCard
        label="Heartbeat"
        value="60s"
        subtitle={`Pulse #${pulse.pulse_number}`}
      />
      <VitalCard
        label="DNA"
        value={pulse.dna_intact ? "INTACT" : "TAMPERED"}
        color={pulse.dna_intact ? "#22c55e" : "#ef4444"}
      />
      <VitalCard
        label="Health"
        value={pulse.health_status.toUpperCase()}
        color={healthColor}
      />
      <VitalCard
        label="Response"
        value={`${(pulse.response_time_ms / 1000).toFixed(2)}s`}
        subtitle={pulse.response_time_ms > 5000 ? "↑ slow" : "normal"}
      />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/cell/OrganismView.tsx apps/mouth/src/components/cell/VitalSigns.tsx
git commit -m "feat(mouth): CELL dashboard — organism view + vital signs"
```

---

## Task 6: Dashboard Page — MetabolismBar + PulseTimeline + Full Page

**Files:**

- Create: `apps/mouth/src/components/cell/MetabolismBar.tsx`
- Create: `apps/mouth/src/components/cell/PulseTimeline.tsx`
- Create: `apps/mouth/src/components/cell/CellDashboard.tsx`
- Create: `apps/mouth/src/app/(workspace)/admin/cell/page.tsx`

- [ ] **Step 1: Create MetabolismBar.tsx**

```tsx
// apps/mouth/src/components/cell/MetabolismBar.tsx
"use client";

import type { CellPulse } from "@/hooks/useCellStatus";

export function MetabolismBar({ pulse }: { pulse: CellPulse | null }) {
  if (!pulse) return null;

  const percent = (pulse.budget_spent / pulse.budget_limit) * 100;
  const barColor =
    percent > 90 ? "#ef4444" : percent > 60 ? "#f59e0b" : "#22c55e";

  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #222",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 8,
          fontSize: 10,
          color: "#666",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        <span>Metabolism</span>
        <span style={{ fontFamily: "monospace", color: "#e5e5e5" }}>
          ${pulse.budget_spent.toFixed(2)} / ${pulse.budget_limit.toFixed(2)} (
          {percent.toFixed(1)}%)
        </span>
      </div>
      <div
        style={{
          height: 8,
          background: "#222",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(percent, 100)}%`,
            background: barColor,
            borderRadius: 4,
            transition: "width 0.5s, background 0.5s",
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          gap: 16,
          marginTop: 8,
          fontSize: 11,
          color: "#666",
        }}
      >
        <span>Routine: ${Math.min(pulse.budget_spent, 3).toFixed(2)}/$3</span>
        <span>Incident: $0.00/$5</span>
        <span style={{ color: "#444" }}>Reserve: $2 (locked)</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create PulseTimeline.tsx**

```tsx
// apps/mouth/src/components/cell/PulseTimeline.tsx
"use client";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

interface PulsePoint {
  pulse_number: number;
  health_status: string;
  response_time_ms: number;
  created_at: string;
}

export function PulseTimeline({ pulses }: { pulses: PulsePoint[] }) {
  // Show newest on the right
  const sorted = [...pulses].reverse();

  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #222",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: "#666",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 8,
        }}
      >
        Pulse Timeline (last {pulses.length})
      </div>
      <div
        style={{
          display: "flex",
          gap: 2,
          flexWrap: "wrap",
        }}
      >
        {sorted.map((p, i) => (
          <div
            key={i}
            title={`#${p.pulse_number} — ${p.health_status.toUpperCase()} — ${p.response_time_ms}ms — ${new Date(p.created_at).toLocaleTimeString()}`}
            style={{
              width: 12,
              height: 20,
              borderRadius: 2,
              background: HEALTH_COLORS[p.health_status] || "#444",
              opacity: 0.8,
              cursor: "pointer",
              transition: "opacity 0.2s",
            }}
            onMouseEnter={(e) => {
              (e.target as HTMLElement).style.opacity = "1";
            }}
            onMouseLeave={(e) => {
              (e.target as HTMLElement).style.opacity = "0.8";
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create CellDashboard.tsx**

```tsx
// apps/mouth/src/components/cell/CellDashboard.tsx
"use client";

import { useCellStatus } from "@/hooks/useCellStatus";
import { OrganismView } from "./OrganismView";
import { VitalSigns } from "./VitalSigns";
import { MetabolismBar } from "./MetabolismBar";
import { PulseTimeline } from "./PulseTimeline";

export function CellDashboard() {
  const { status, loading, error } = useCellStatus(10000);

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          color: "#666",
        }}
      >
        Connecting to CELL...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          color: "#ef4444",
        }}
      >
        Cannot reach CELL: {error}
      </div>
    );
  }

  const pulse = status?.last_pulse || null;
  const alive = status?.alive || false;

  return (
    <div
      style={{
        background: "#0a0a0a",
        minHeight: "100vh",
        padding: 24,
        color: "#e5e5e5",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
          paddingBottom: 16,
          borderBottom: "1px solid #222",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 20,
              fontWeight: 700,
              margin: 0,
            }}
          >
            🧬 CELL — Essere Perfetto
          </h1>
          <p style={{ fontSize: 12, color: "#666", margin: "4px 0 0" }}>
            Autonomous Digital Organism
          </p>
        </div>
        <span style={{ fontSize: 12, color: "#444" }}>v0.1.0</span>
      </div>

      {/* Top: Organism + Vitals */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 8,
          }}
        >
          <OrganismView pulse={pulse} alive={alive} />
        </div>
        <VitalSigns pulse={pulse} alive={alive} />
      </div>

      {/* Metabolism */}
      <div style={{ marginBottom: 16 }}>
        <MetabolismBar pulse={pulse} />
      </div>

      {/* Timeline */}
      <div style={{ marginBottom: 16 }}>
        <PulseTimeline pulses={status?.recent_pulses || []} />
      </div>

      {/* Bottom: Memory + Cells */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
      >
        {/* Memory */}
        <div
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "#666",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 12,
            }}
          >
            Memory
          </div>
          <div style={{ fontSize: 13, lineHeight: 2, fontFamily: "monospace" }}>
            <div>STM: {pulse?.memory_stm_count || 0} observations (Redis)</div>
            <div>LTM: {pulse?.memory_ltm_count || 0} experiences (Qdrant)</div>
            <div>Procedures: {pulse?.procedures_count || 0} strategies</div>
          </div>
        </div>

        {/* Cells */}
        <div
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "#666",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 12,
            }}
          >
            Cells
          </div>
          <div style={{ fontSize: 13, fontFamily: "monospace" }}>
            <div style={{ marginBottom: 8 }}>
              {pulse?.cells_active || 1}/{pulse?.cells_total || 50} active
            </div>
            <div
              style={{
                fontSize: 12,
                color: "#888",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#22c55e",
                  display: "inline-block",
                }}
              />
              pulse_cell: ACTIVE
            </div>
          </div>
        </div>
      </div>

      {/* Uptime */}
      {status?.uptime_24h && status.uptime_24h.total_pulses > 0 && (
        <div
          style={{
            marginTop: 16,
            textAlign: "center",
            fontSize: 11,
            color: "#444",
          }}
        >
          24h uptime: {status.uptime_24h.green_percent}% green ·{" "}
          {status.uptime_24h.yellow_percent}% yellow ·{" "}
          {status.uptime_24h.red_percent}% red ·{" "}
          {status.uptime_24h.total_pulses} pulses
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create page.tsx**

```tsx
// apps/mouth/src/app/(workspace)/admin/cell/page.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CellDashboard } from "@/components/cell/CellDashboard";

export default function CellPage() {
  const router = useRouter();

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push("/login");
      return;
    }
    if (!api.isAdmin()) {
      router.push("/chat");
      return;
    }
  }, [router]);

  return <CellDashboard />;
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/cell/ apps/mouth/src/app/\(workspace\)/admin/cell/
git commit -m "feat(mouth): CELL dashboard — full organism visualization at /admin/cell"
```

---

## Summary

| Task | What It Builds                                      | Layer     |
| ---- | --------------------------------------------------- | --------- |
| 1    | PostgreSQL table + CELL DB writer                   | CELL + DB |
| 2    | Backend API endpoint GET /api/cell/status           | Backend   |
| 3    | useCellStatus polling hook                          | Frontend  |
| 4    | Floating heartbeat widget                           | Frontend  |
| 5    | OrganismView + VitalSigns components                | Frontend  |
| 6    | MetabolismBar + PulseTimeline + Full Dashboard Page | Frontend  |

After Task 6, push to main → Vercel auto-deploys → CELL has a face at `kita.balizero.com/admin/cell`.
