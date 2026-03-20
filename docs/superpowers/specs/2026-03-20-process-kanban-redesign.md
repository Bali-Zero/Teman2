# Process Kanban Redesign — Visual Progression + Monthly Navigation

**Date:** 2026-03-20
**Status:** Approved
**Route:** `kita.balizero.com/process`

## Summary

Two enhancements to the `/process` kanban board:

1. **Visual progression** — colored top bars per column + ghost cards showing practice journey
2. **Monthly navigation** — pill tabs to browse practices by month with cross-month visibility

## Design Decisions

| Decision              | Choice                                                                 | Alternatives Considered                                                              |
| --------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Column coloring       | 3px top bar gradient + subliminal tint (3-4% opacity bg + 7-8% border) | Tinted bg at 8-10% (too heavy), neutral bg only (too flat), card left-border (noisy) |
| Month navigation      | Pill tabs with arrows (Jan \| Feb \| **Mar** \| Apr)                   | Underline tabs with counts, inline selector in title                                 |
| Cross-month practices | Ghost cards in traversed columns                                       | Show in creation month only, show in current month only                              |
| Completed cards       | Glow effect (green shadow + checkmark)                                 | Same as active, green tint only                                                      |
| Ghost overflow        | Collapse after 2, show "+N passate"                                    | Show all (clutters), hide all (loses context)                                        |
| Badge counter         | Current-status cards only (excludes ghosts)                            | Including ghosts (misleading)                                                        |
| Status history source | `activity_log` table (`changes` JSONB)                                 | `timeline_events` (lacks raw status values), new column (unnecessary migration)      |

## Architecture

### Data Flow

```
Browser                          Backend (Fly.io)
  |                                   |
  |-- GET /api/crm/practices          |
  |   ?month=2026-03                  |
  |   &include_history=true           |
  |                                   |
  |<-- practices[] with               |
  |    status_transitions[]           |
  |    per practice                   |
```

### Backend Changes

**File:** `apps/backend-rag/backend/app/routers/crm_practices.py`

#### API contract changes

Add two new query parameters to `list_practices`:

```python
month: str | None = Query(None, description="Filter by month YYYY-MM")
include_history: bool = Query(False, description="Include status transition history")
```

#### Data source: `activity_log` (not `timeline_events`)

The `timeline_events` table stores mapped event types (`milestone`, `payment_due`, `completion`) — NOT raw status values. The `activity_log` table stores `changes` as JSONB containing `{"status": "on_process"}` — this is the correct source for reconstructing transitions.

```sql
-- Practices active in a given month (created OR had activity in month)
-- Excludes cancelled practices
SELECT DISTINCT p.*, c.full_name as client_name, c.email as client_email,
       c.phone as client_phone, c.assigned_to as client_lead,
       pt.name as practice_type_name, pt.code as practice_type_code
FROM practices p
LEFT JOIN clients c ON p.client_id = c.id
LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
LEFT JOIN activity_log al ON al.entity_type = 'practice'
    AND al.entity_id = p.id
    AND al.action = 'updated'
WHERE p.status != 'cancelled'
  AND (
    (p.created_at >= '2026-03-01' AND p.created_at < '2026-04-01')
    OR (al.created_at >= '2026-03-01' AND al.created_at < '2026-04-01')
  )
ORDER BY p.created_at DESC;

-- Status transitions per practice (from activity_log changes JSONB)
SELECT entity_id as practice_id,
       jsonb_agg(
         jsonb_build_object(
           'status', changes->>'status',
           'at', al.created_at
         ) ORDER BY al.created_at
       ) as status_transitions
FROM activity_log al
WHERE al.entity_type = 'practice'
  AND al.action = 'updated'
  AND al.changes ? 'status'
  AND al.entity_id = ANY($1)  -- practice IDs from first query
GROUP BY al.entity_id;
```

When `include_history=false` (default, backward compatible), skip the second query.

#### Recommended index

```sql
CREATE INDEX IF NOT EXISTS idx_activity_log_practice_status
ON activity_log (entity_id, created_at)
WHERE entity_type = 'practice' AND action = 'updated';
```

#### Response shape change

Each practice dict gains an optional `status_transitions` field:

```python
# Only when include_history=true
practice_dict["status_transitions"] = [
    {"status": "inquiry", "at": "2026-02-15T10:30:00"},
    {"status": "waiting_documents", "at": "2026-02-18T14:00:00"},
    ...
]
```

### Frontend Changes

**File:** `apps/mouth/src/app/(workspace)/process/page.tsx`

#### 0. API layer changes

**File:** `apps/mouth/src/lib/api/crm/crm.api.ts`

Add `month?: string` and `include_history?: boolean` to `getPractices` params. Pass as query string.

**File:** `apps/mouth/src/lib/api/crm/crm.types.ts`

Add to `Practice` interface:

```typescript
interface StatusTransition {
  status: string;
  at: string; // ISO timestamp
}

// Extend Practice
status_transitions?: StatusTransition[];
```

#### 1. Month Pill Tabs Component

Position: between header and search bar.

```
State: selectedMonth (default: current month YYYY-MM)
URL: synced to ?month=YYYY-MM search param (survives refresh, shareable)
UI: ◀ Jan | Feb | [Mar] | Apr ▶
```

- Active month: `bg-[var(--bz-accent)] text-white` pill
- Past months: `text-[var(--bz-text-2)]` clickable
- Future months: `text-[var(--bz-text-2)]/30` not clickable
- Show 5 months window. At boundaries (e.g., Jan selected), shift to always show 5 (Jan-May). Years cross seamlessly.
- Arrows scroll the window by 1 month

When month changes:

- Re-fetch `getPractices({ month: selectedMonth, include_history: true })`
- Preserve current search query and filters (do NOT reset)
- Reset list view pagination to page 1

Both kanban and list views respect the month filter.

#### 2. Column Top Bar

Replace current `stepColors` dot system. Each column gets:

```tsx
<div
  className="h-[3px]"
  style={{ background: `linear-gradient(90deg, ${colorStart}, ${colorEnd})` }}
/>
```

Colors (same as current, just applied as gradient bar):

- Inquiry: `#6b7280 → #9ca3af`
- Waiting Docs: `#fb923c → #f97316`
- Invoice: `#facc15 → #eab308`
- On Process: `#3b82f6 → #2563eb`
- Completed: `#22c55e → #16a34a`

Column background: subliminal tint at 3-4% opacity of the column's color, with border tinted at 7-8%:

- Inquiry: `bg: rgba(156,163,175, 0.035)` / `border: rgba(156,163,175, 0.08)`
- Waiting Docs: `bg: rgba(251,146,60, 0.035)` / `border: rgba(251,146,60, 0.08)`
- Invoice: `bg: rgba(250,204,21, 0.03)` / `border: rgba(250,204,21, 0.07)`
- On Process: `bg: rgba(59,130,246, 0.035)` / `border: rgba(59,130,246, 0.08)`
- Completed: `bg: rgba(34,197,94, 0.04)` / `border: rgba(34,197,94, 0.09)`

Badge counter: colored background matching column (`rgba(color, 0.12)`), counts **current-status cards only** (excludes ghost cards).

#### 3. Ghost Cards

For each column, split cards into two groups:

**Active zone** (top): practices whose **current** status maps to this column.

- Full opacity, current card styling unchanged.

**Separator**: dashed line with centered "passate" label.

- Only render if ghost cards exist for this column.

**Ghost zone** (below separator): practices that **transitioned through** this column but are now elsewhere.

- `opacity: 0.35`
- `background: rgba(255,255,255, 0.02)`
- `border: 1px solid rgba(255,255,255, 0.04)`
- Text in `text-[var(--bz-text-2)]` tones
- Small status indicator: colored dot + "ora: {current_status}" or "completata"
- No quick actions (WhatsApp, email, docs buttons hidden)
- Still clickable (navigates to detail page)

**Collapse rule**: show max 2 ghost cards. If more, show "+N passate" button that expands all inline (no pagination).

**Important:** `status_transitions[].status` contains **raw practice status values** (e.g., `"on_process"`, `"sending_invoice"`) — NOT event types. The existing `getStatusColumn()` function at `page.tsx:294` is reused directly to map these to columns.

#### 4. Completed Card Glow

Cards in the Completed column with `status === "completed"` get a variant style:

```tsx
className="bg-green-500/8 border-green-500/25"
style={{ boxShadow: '0 0 12px rgba(34,197,94,0.12), 0 0 4px rgba(34,197,94,0.08)' }}
```

- Green checkmark icon next to practice type name
- Client name in `text-green-300`
- Completion date shown at bottom: "Completata 15 Mar 2026"
- Assigned-to badge in green tones

This is applied within the existing card rendering block (not a separate component), conditioned on `getStatusColumn(practice.status) === "completed"`.

### Component Structure

```
PratichePage
├── MonthPillTabs (new)
│   ├── ArrowButton (prev)
│   ├── MonthPill[] (5 visible)
│   └── ArrowButton (next)
├── SearchBar (existing)
├── FilterPanel (existing)
├── KanbanBoard
│   └── KanbanColumn[] (5)
│       ├── ColumnHeader (top bar gradient + colored badge)
│       ├── ActiveCards[]
│       │   └── PracticeCard (existing, with completed glow variant)
│       ├── GhostSeparator (conditional, only if ghosts exist)
│       ├── GhostCards[] (max 2 visible)
│       │   └── GhostCard (new, minimal)
│       └── GhostOverflow ("+N passate" expand button, conditional)
└── ContextMenu (existing)
```

### Ghost Card Logic (Frontend)

Reuses existing `getStatusColumn()` function at `page.tsx:294`.

```typescript
function getGhostPractices(
  allPractices: PracticeWithHistory[],
  columnStatus: CaseStatus,
): PracticeWithHistory[] {
  return allPractices.filter((p) => {
    // Current status is NOT this column
    const currentColumn = getStatusColumn(p.status);
    if (currentColumn === columnStatus) return false;

    // But practice passed through this column (has a transition with this column's status)
    const transitions = p.status_transitions || [];
    return transitions.some((t) => getStatusColumn(t.status) === columnStatus);
  });
}
```

## What Does NOT Change

- List view (table) — respects month filter, but no ghost cards or visual changes
- Context menu — unchanged
- Card quick actions (WhatsApp, email, docs) — unchanged for active cards
- Detail page (`/process/[id]`) — unchanged
- New practice page (`/process/new`) — unchanged
- Portal view — unchanged
- Backend status values — still 5 steps, no new statuses
- RBAC — unchanged

## Performance

- `activity_log` query adds ~20-30ms with recommended partial index
- Ghost cards computed client-side from `status_transitions` (no extra API call)
- Month change triggers a single re-fetch (no debounce needed, user clicks)
- Ghost collapse prevents DOM bloat (max 10 extra ghost cards across 5 columns)

## Edge Cases

| Case                                                   | Behavior                                                                                                                                            |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Practice created in Feb, still "on_process" in Mar     | Appears in both months. Active in On Process, ghost in columns it transitioned through                                                              |
| Practice completed in Feb, viewing Mar                 | Does NOT appear in Mar. Completed practices appear in all months they were active (creation through completion), but not in months after completion |
| Practice with no status changes (just created)         | No ghosts, no `status_transitions`, appears only in creation column                                                                                 |
| Brand new month (no practices yet)                     | Empty kanban with "No process" placeholders, month tabs still navigable                                                                             |
| Very old months (Jan 2025)                             | Arrows allow scrolling indefinitely, API handles any YYYY-MM                                                                                        |
| Cancelled practices                                    | Excluded from query (`p.status != 'cancelled'`), never shown                                                                                        |
| Practice created in Jan, completed in Mar, viewing Jan | Appears in Jan as ghost in Inquiry (or whatever its first status was), with indicator showing "completata"                                          |
| No `month` param (backward compat)                     | Returns current behavior — all non-cancelled practices, no history, `limit` applies                                                                 |
