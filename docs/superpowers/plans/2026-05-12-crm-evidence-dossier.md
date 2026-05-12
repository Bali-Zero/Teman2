# CRM Evidence Dossier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a team-only dynamic CRM dossier endpoint and wire kita's pilot workspace to use it with pilot fallback.

**Architecture:** Backend service reads CRM relational tables plus `crm_kg_*`, then returns `TaxCompanyPilotMap`-compatible dossiers. Router gates access with `require_team_member`. Frontend adds one API method and points the current tax pilot page at the live endpoint.

**Tech Stack:** FastAPI, asyncpg, Pydantic, Next.js, React Query, Vitest, pytest, Ruff.

---

### Task 1: Backend Service And Router

**Files:**
- Create: `apps/backend-rag/backend/services/crm/evidence_dossier.py`
- Create: `apps/backend-rag/backend/app/routers/crm_intelligence.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`
- Test: `apps/backend-rag/backend/tests/unit/services/crm/test_evidence_dossier.py`
- Test: `apps/backend-rag/backend/tests/unit/routers/test_crm_intelligence.py`

- [ ] Write failing tests for dynamic dossier rows, pilot fallback, and team-only router behavior.
- [ ] Implement `build_evidence_dossiers(pool, company=None, limit=10)`.
- [ ] Implement `/api/crm/intelligence/evidence-dossiers`.
- [ ] Register `crm_intelligence` router.
- [ ] Run targeted pytest and Ruff.

### Task 2: Frontend API And Workspace Wiring

**Files:**
- Modify: `apps/mouth/src/lib/api/crm/crm.types.ts`
- Modify: `apps/mouth/src/lib/api/crm/crm.api.ts`
- Modify: `apps/mouth/src/lib/api/crm/crm.api.test.ts`
- Modify: `apps/mouth/src/app/(workspace)/clients/tax-pilot/page.tsx`

- [ ] Add `getEvidenceDossiers({ company?, limit? })`.
- [ ] Update the tax pilot page to call the live endpoint for `ocean,bimala`.
- [ ] Keep existing component rendering and loading/error behavior.
- [ ] Run Vitest for CRM API and workspace component.
- [ ] Run `npm run typecheck -- --pretty false`.

### Task 3: Verification And Release

- [ ] Run backend targeted pytest.
- [ ] Run backend Ruff on touched files.
- [ ] Run frontend targeted Vitest.
- [ ] Run frontend typecheck.
- [ ] Run docs sync if service/test counts changed.
- [ ] Commit, push, and deploy if required.
- [ ] Verify Fly health and `kita.balizero.com/clients/tax-pilot`.
