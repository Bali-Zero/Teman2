# Zantara Cockpit MVP — minimal read-only

**Date**: 2026-05-18
**Status**: SHIP THIS. Iterate from real design.
**Replaces**: v1 (PR #712 closed) + v2/v3 spec (too ambitious, panel divergent)

## Rationale

3 rounds of 4-LLM panel found 4 new structural issues each (12 total CRITICAL).
Pattern divergent, not convergent. 14h speculative spec, 0 LOC shipped.

**Pivot**: ship visible MVP with **read-only** scope. See real friction in design,
then iterate with actual user feedback, not speculative panel review.

## MVP scope (final, no panel review needed)

### 1. Home `/cockpit` (visible)

- Bali Zero brand topbar (logo asset already committed)
- 4 tiles READ-ONLY (no click action):
  - Global Pulse: `running/total` from launchctl (lib/cockpit-launchctl.ts already cherry-picked)
  - Pending Decisions: count of `gh pr list --draft --json` (no action, just count)
  - What It Learned: placeholder "coming v2"
  - Quick Commands: placeholder "coming v2"
- 2 door cards (CLICK → navigate, no destructive action):
  - WR2 → `/cockpit/wr2` (read-only view)
  - Intel-Lake → `/cockpit/intel-lake` (read-only view)

### 2. `/cockpit/wr2` (READ-ONLY)

- Page title + breadcrumb
- WR2 drafts table from `SELECT * FROM war_room_drafts ORDER BY updated_at DESC LIMIT 30`
- Columns: topic, status, register, updated_at, lease_owner
- Status filter dropdown
- **NO form, NO Approve/Reject, NO intent emission**
- **NO subprocess spawn**
- Refresh polling 30s (no SSE)

### 3. `/cockpit/intel-lake` (READ-ONLY)

- Page title + breadcrumb
- 4 KPI cards from existing queries: items_today, outbox_pending, stuck (routing_status='needs_review'), NB pushes 7d
- Recent items table: `SELECT * FROM intel_items ORDER BY first_seen_at DESC LIMIT 30`
- Click row → opens `canonical_url` in new tab (Antonello reads source directly)
- **NO action buttons, NO drawer, NO intent**
- Refresh polling 60s

### 4. Auth (already done in cherry-picked lib)

- PIN bcrypt + rate-limit (lib/cockpit-auth.ts ✓)
- Middleware origin localhost + cookie gate ✓
- HMAC audit on every page render (audit "/cockpit page viewed by antonello at $TIME")

### 5. Files (target — most cherry-picked already)

**Already in branch** (from v1 cherry-pick):

- `apps/admin-dashboard-local/lib/cockpit-{allowlist,auth,audit,launchctl,pg}.ts` ✓
- `apps/admin-dashboard-local/__tests__/cockpit/{allowlist,auth,audit}.test.ts` ✓
- `apps/backend-rag/backend/db/migrations_v2/{182_cockpit_audit_log,183_cockpit_intents}.sql` ✓
- `apps/admin-dashboard-local/public/balizero_logo_circle.png` ✓
- `apps/admin-dashboard-local/package.json` (bcryptjs added) ✓

**To create (MVP scope)**:

- `apps/admin-dashboard-local/app/cockpit/{layout,page}.tsx`
- `apps/admin-dashboard-local/app/cockpit/cockpit-shell.css` (warm palette v2 lighter)
- `apps/admin-dashboard-local/app/cockpit/wr2/page.tsx` (read-only)
- `apps/admin-dashboard-local/app/cockpit/intel-lake/page.tsx` (read-only)
- `apps/admin-dashboard-local/middleware.ts`
- `apps/admin-dashboard-local/app/api/cockpit/auth/route.ts`
- `apps/admin-dashboard-local/app/api/cockpit/cron/list/route.ts` (read-only — no /run endpoint)
- `apps/admin-dashboard-local/app/api/cockpit/decisions/route.ts`
- `apps/admin-dashboard-local/app/api/cockpit/wr2/drafts/route.ts` (read-only)
- `apps/admin-dashboard-local/app/api/cockpit/intel-lake/{kpi,items}/route.ts` (read-only)
- `apps/admin-dashboard-local/components/cockpit/{BrandTopbar,HomeTile,DoorCard,WidgetFrame,PinGate}.tsx`
- `apps/admin-dashboard-local/scripts/{setup-cockpit-pin,start-cockpit}.sh`

### 6. Out of scope MVP (explicit defer to v2 after MVP feedback)

- ❌ NewBriefForm (subprocess spawn, was CRITICAL)
- ❌ PipelineKanban with action buttons
- ❌ Intent table consumers (cockpit_intents tabella esiste ma resta vuota)
- ❌ SSE singleton multiplexed
- ❌ Trace card / live log
- ❌ Canva Status interactive
- ❌ Drawer slide-over
- ❌ Quick Commands actions
- ❌ Source Health detail
- ❌ NB Push interactive

### 7. Effort honest

- Foundation (layout + theme + middleware + auth API + 5 read-only API + 4 components): **12-15h**
- WR2 read-only page (drafts table + filter): **3-4h**
- Intel-Lake read-only page (4 KPI + items table): **3-4h**
- Smoke E2E (open cockpit, see data, click door cards): **2h**
- PR draft + push: **1h**

**Total: 21-26h**. Single PR, no parallel sessions needed.

### 8. Success criterion (the actual one)

Antonello opens `http://localhost:3100/cockpit`, sees Bali Zero brand topbar +
4 tiles + 2 door cards. Click WR2 door → see real war_room_drafts table.
Click Intel-Lake door → see real intel_items. No "lorem ipsum", real data
from PG. **That's MVP done.** Everything else iterate after feedback.

### 9. Migration path

When MVP shipped + Antonello uses it for 1 week:

- Identifies pain points ("vorrei poter approvare da qui")
- v2 spec adds **ONLY** those features, scoped narrow
- New panel reviews only what's added
- No speculative architecture
