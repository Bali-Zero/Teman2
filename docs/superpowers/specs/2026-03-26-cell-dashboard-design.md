# CELL Dashboard — Design Spec

> Design Spec v1.0 — 2026-03-26
> Visual style: Organismo Vivente (dark, pulsating, organic)

---

## Overview

A real-time dashboard for CELL — the autonomous digital organism. Two components: a full dashboard at `/admin/cell` and a floating heartbeat widget on all admin pages.

Data flows from CELL (local Mac Pro) → PostgreSQL (Fly.io) → Backend API → Frontend (Vercel).

---

## 1. Data Pipeline

### 1.1 PostgreSQL Table

CELL writes its state every 60 seconds to `cell_pulse_log` on the production PostgreSQL (Fly.io).

```sql
CREATE TABLE cell_pulse_log (
    id SERIAL PRIMARY KEY,
    pulse_number INT NOT NULL,
    health_status VARCHAR(10) NOT NULL,  -- green, yellow, red
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

-- Index for fast latest-row queries
CREATE INDEX idx_cell_pulse_log_created ON cell_pulse_log(created_at DESC);

-- Auto-cleanup: keep only last 7 days (cron or trigger)
-- DELETE FROM cell_pulse_log WHERE created_at < NOW() - INTERVAL '7 days';
```

### 1.2 CELL Writer (Python — apps/cell)

After each pulse, CELL inserts one row into `cell_pulse_log` via the fly proxy tunnel (port 15432).

Added to `cell/core/pulse.py` post-pulse:

```python
await db_pool.execute(
    "INSERT INTO cell_pulse_log (pulse_number, health_status, response_time_ms, ...) VALUES ($1, $2, $3, ...)",
    pulse_count, status.value, int(reading.response_time_seconds * 1000), ...
)
```

### 1.3 Backend API Endpoint (FastAPI — apps/backend-rag)

New router: `backend/app/routers/cell_status.py`

```
GET /api/cell/status
```

Response:

```json
{
  "alive": true,
  "last_pulse": {
    "pulse_number": 847,
    "health_status": "green",
    "response_time_ms": 3522,
    "dna_intact": true,
    "budget_spent": 0.12,
    "budget_limit": 10.0,
    "memory_stm_count": 24,
    "memory_ltm_count": 0,
    "procedures_count": 0,
    "cells_active": 1,
    "cells_total": 1,
    "action_taken": null,
    "created_at": "2026-03-26T20:31:28Z"
  },
  "recent_pulses": [
    {
      "pulse_number": 847,
      "health_status": "green",
      "response_time_ms": 3522,
      "created_at": "..."
    },
    {
      "pulse_number": 846,
      "health_status": "green",
      "response_time_ms": 4322,
      "created_at": "..."
    }
  ],
  "uptime_24h": {
    "green_percent": 95.2,
    "yellow_percent": 4.1,
    "red_percent": 0.7,
    "total_pulses": 1440
  }
}
```

Logic:

- `alive`: true if last pulse was within 120 seconds (2 missed pulses = dead)
- `last_pulse`: most recent row from `cell_pulse_log`
- `recent_pulses`: last 50 rows, ordered by created_at DESC
- `uptime_24h`: aggregated counts from last 24h

Auth: admin only (same RBAC as other admin endpoints).

### 1.4 Frontend Polling

The Next.js frontend polls `GET /api/cell/status` every 10 seconds using `useEffect` + `setInterval`. No WebSocket, no SSE — simple polling through the existing API client.

---

## 2. Widget Flottante

A small floating indicator visible on all admin pages.

### Position

Bottom-right corner, 16px from edges. Above any existing floating elements. `z-index: 50`.

### States

| CELL State            | Widget Appearance                                     |
| --------------------- | ----------------------------------------------------- |
| Alive + GREEN         | 40px circle, pulsing green glow (animation), 🧬 emoji |
| Alive + YELLOW        | 40px circle, pulsing amber glow, 🧬 emoji             |
| Alive + RED           | 40px circle, pulsing red glow, 🧬 emoji               |
| Dead (no pulse >120s) | 40px circle, static gray, 💀 emoji                    |
| Loading               | 40px circle, static dim, ⏳ emoji                     |

### Interaction

- **Hover:** tooltip with "CELL — Pulse #847 — GREEN"
- **Click:** expands to a 280px wide panel showing:
  - Health status with colored dot
  - Pulse count
  - Response time
  - Budget: "$0.12 / $10.00" with mini progress bar
  - Last action (or "Observing..." if none)
  - Link: "Open CELL Dashboard →"
- **Click outside panel:** collapses back to circle
- **Pulse animation:** CSS `@keyframes` matching CELL's 60s cycle — one gentle pulse per minute

### Visibility

Only rendered when user role is `admin`. Check existing `useAuth()` or RBAC context.

### Component

`apps/mouth/src/components/cell/CellWidget.tsx` — self-contained, no props needed. Handles its own data fetching.

---

## 3. Dashboard `/admin/cell`

Full-page dashboard at `apps/mouth/app/(authenticated)/admin/cell/page.tsx`.

### Layout (dark theme, organic feel)

```
┌─────────────────────────────────────────────────────────┐
│  CELL — Essere Perfetto                    v0.1.0       │
├────────────────────────┬────────────────────────────────┤
│                        │                                │
│    [ORGANISM VIEW]     │     [VITAL SIGNS]              │
│                        │                                │
│    Central pulsing     │  ┌──────────┐ ┌──────────┐    │
│    🧬 with orbiting   │  │ Heartbeat│ │ DNA      │    │
│    organ labels        │  │ 60s      │ │ INTACT   │    │
│    (SENSE, MEMORY,     │  └──────────┘ └──────────┘    │
│     HEAL, THINK)       │  ┌──────────┐ ┌──────────┐    │
│                        │  │ Health   │ │ Response │    │
│    Color = health      │  │ GREEN    │ │ 3.52s    │    │
│                        │  └──────────┘ └──────────┘    │
├────────────────────────┴────────────────────────────────┤
│  [METABOLISM]                                           │
│  ████████░░░░░░░░░░░░░░░░░░░░  $0.12 / $10.00 (1.2%)  │
│  Routine: $0.10/$3  │  Incident: $0.02/$5  │  Reserve  │
├─────────────────────────────────────────────────────────┤
│  [PULSE TIMELINE]                                       │
│  ■■■■■■■■■■■■■■□■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■  │
│  Each block = 1 pulse. Green/Yellow/Red. Last 50.       │
│  Hover = timestamp + response time                      │
├──────────────────────────┬──────────────────────────────┤
│  [MEMORY]                │  [CELLS]                     │
│  STM: 24 obs (Redis)    │  1/50 active                 │
│  LTM: 0 exp (Qdrant)    │  pulse_cell: ACTIVE          │
│  Procedures: 0 strat     │    847 pulses, 0 actions     │
└──────────────────────────┴──────────────────────────────┘
```

### Organism View (center-left)

- 120px circle with 🧬 emoji, `radial-gradient` glow matching health color
- CSS `@keyframes pulse-glow` — 2s cycle, shadow expands/contracts
- 4 labels orbiting: SENSE, MEMORY, HEAL, THINK
- Orbit ring: thin circle (1px border, 20% opacity of health color)
- When health changes color, transition smoothly (CSS `transition: all 0.5s`)

### Vital Signs (4 cards, top-right)

- **Heartbeat:** "60s" large number, "Pulse #847" subtitle
- **DNA:** "INTACT" green or "TAMPERED" red with hash prefix
- **Health:** "GREEN" / "YELLOW" / "RED" with colored dot
- **Response:** "3.52s" with trend indicator (↑ slower / ↓ faster vs avg)

### Metabolism Bar (full width)

- Single progress bar: green fill up to 60%, yellow 60-90%, red >90%
- Three sub-bars below: routine, incident, reserve (reserve always gray/locked)
- Numbers: "$0.12 / $10.00 (1.2%)"

### Pulse Timeline (full width)

- 50 small squares in a row, each representing one pulse
- Color: green/yellow/red based on health_status
- Hover tooltip: "Pulse #844 — YELLOW — 8.21s — 20:28 UTC"
- Newest on the right
- Updates every 10s when new data arrives

### Memory Section (bottom-left)

- Three rows: STM count, LTM count, Procedures count
- Small labels with actual numbers
- When CELL grows, these numbers will increase visibly

### Cells Section (bottom-right)

- "1/50 active" header
- List of cells with name, status, pulse count, action count
- Embryo has only "pulse_cell"

### Styling

- Background: `#0a0a0a` (near-black)
- Cards: `#111111` with `border: 1px solid #222`
- Text: `#e5e5e5` primary, `#666` secondary
- Green: `#22c55e` (Tailwind green-500)
- Yellow: `#f59e0b` (Tailwind amber-500)
- Red: `#ef4444` (Tailwind red-500)
- Font: system monospace for numbers, system sans for labels
- All animations use `prefers-reduced-motion: reduce` media query as kill switch

---

## 4. Files to Create/Modify

### Backend (apps/backend-rag)

- Create: `backend/app/routers/cell_status.py` — GET /api/cell/status endpoint
- Modify: `backend/app/setup/router_registration.py` — register cell_status router
- Create: SQL migration for `cell_pulse_log` table

### Frontend (apps/mouth)

- Create: `src/components/cell/CellWidget.tsx` — floating widget
- Create: `src/components/cell/CellDashboard.tsx` — full dashboard
- Create: `src/components/cell/OrganismView.tsx` — central pulsing organism
- Create: `src/components/cell/VitalSigns.tsx` — 4 metric cards
- Create: `src/components/cell/MetabolismBar.tsx` — budget progress bar
- Create: `src/components/cell/PulseTimeline.tsx` — 50-block timeline
- Create: `src/components/cell/MemoryPanel.tsx` — memory counters
- Create: `src/components/cell/CellsPanel.tsx` — active cells list
- Create: `src/hooks/useCellStatus.ts` — polling hook (10s interval)
- Create: `app/(authenticated)/admin/cell/page.tsx` — dashboard page
- Modify: admin layout to include CellWidget

### CELL (apps/cell)

- Modify: `cell/core/pulse.py` — add DB write after each pulse
- Create: `cell/core/db.py` — asyncpg pool for pulse logging

---

## 5. What This Spec Does NOT Cover

- Real-time WebSocket/SSE (polling is sufficient for 60s pulse cycle)
- Historical analytics (7+ day trends, charts)
- CELL control panel (start/stop/maintenance from UI)
- Mobile responsive layout
- Public access (admin-only)

These are future enhancements.
