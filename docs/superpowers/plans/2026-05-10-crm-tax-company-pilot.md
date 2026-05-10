# CRM Tax Company Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only `kita.balizero.com` pilot that maps Ocean and Bimala from tax member folders to companies, people, documents, gaps, and evidence links.

**Architecture:** Add a small static backend pilot dataset behind `GET /api/crm/pilot/tax-company-map`, expose it through the existing CRM frontend API client, and render a workspace page under `/clients/tax-pilot`. The pilot performs no Drive writes and uses confidence/RBAC labels for sensitive company evidence.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js App Router, React Query, Vitest, TypeScript.

---

### Task 1: Backend Read-Only Pilot Map

**Files:**

- Create: `apps/backend-rag/backend/services/crm/tax_company_pilot.py`
- Create: `apps/backend-rag/backend/app/routers/crm_tax_pilot.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`
- Test: `apps/backend-rag/backend/tests/unit/services/crm/test_tax_company_pilot.py`
- Test: `apps/backend-rag/backend/tests/unit/routers/test_crm_tax_pilot.py`

- [x] **Step 1: Write failing service tests**

Add tests asserting that `get_tax_company_pilot_map("ocean")` returns DEA, Ocean Drive links, three visible people, duplicate candidates, and `read_only=true`; assert `bimala` returns Dewa Ayu and family edges as unconfirmed.

- [x] **Step 2: Verify service tests fail**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/services/crm/test_tax_company_pilot.py -q`

Expected: import failure for missing `backend.services.crm.tax_company_pilot`.

- [x] **Step 3: Write failing router tests**

Add direct async tests for `get_tax_company_pilot(company="ocean")` and an unknown company raising 404.

- [x] **Step 4: Verify router tests fail**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_crm_tax_pilot.py -q`

Expected: import failure for missing `backend.app.routers.crm_tax_pilot`.

- [x] **Step 5: Implement static typed service and router**

Implement Pydantic models for `TaxCompanyPilotMap`, `TaxCompanyPilotPerson`, `TaxCompanyPilotDocument`, `TaxCompanyPilotGap`, and `TaxCompanyPilotEvidenceLink`. Keep all data static and read-only.

- [x] **Step 6: Register router in full and light router sets**

Add `crm_tax_pilot` to both lazy import lists and include it after the existing CRM routers.

- [x] **Step 7: Verify backend tests pass**

Run both pytest commands from steps 2 and 4.

### Task 2: Frontend API Contract

**Files:**

- Modify: `apps/mouth/src/lib/api/crm/crm.types.ts`
- Modify: `apps/mouth/src/lib/api/crm/crm.api.ts`
- Test: `apps/mouth/src/lib/api/crm/crm.api.test.ts`

- [x] **Step 1: Write failing API client test**

Add a test that `getTaxCompanyPilotMap("ocean")` calls `/api/crm/pilot/tax-company-map?company=ocean`.

- [x] **Step 2: Verify API client test fails**

Run: `cd apps/mouth && npm run test -- src/lib/api/crm/crm.api.test.ts --run`

Expected: method missing on `CrmApi`.

- [x] **Step 3: Add TypeScript contract and API method**

Add pilot map interfaces matching backend JSON and implement `getTaxCompanyPilotMap(company)`.

- [x] **Step 4: Verify API client test passes**

Run the same Vitest command.

### Task 3: Workspace Page

**Files:**

- Create: `apps/mouth/src/components/crm/TaxCompanyPilotWorkspace.tsx`
- Create: `apps/mouth/src/components/crm/TaxCompanyPilotWorkspace.test.tsx`
- Create: `apps/mouth/src/app/(workspace)/clients/tax-pilot/page.tsx`

- [x] **Step 1: Write failing component tests**

Render static Ocean/Bimala maps and assert the page shows tax members, linked people, missing-doc gaps, duplicate candidates, and Drive evidence links.

- [x] **Step 2: Verify component tests fail**

Run: `cd apps/mouth && npm run test -- src/components/crm/TaxCompanyPilotWorkspace.test.tsx --run`

Expected: missing component import.

- [x] **Step 3: Implement component**

Build a dense operational workspace: top summary, two company columns, person rows, document groups, gaps, duplicate candidates, and evidence links. No marketing hero.

- [x] **Step 4: Add page**

Fetch both maps with React Query and render the component. Keep error/loading states compact.

- [x] **Step 5: Verify component tests pass**

Run the component Vitest command again.

### Task 4: Final Verification

**Files:**

- All touched files.

- [x] **Step 1: Run backend tests**

Run:
`cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/services/crm/test_tax_company_pilot.py backend/tests/unit/routers/test_crm_tax_pilot.py -q`

- [x] **Step 2: Run frontend targeted tests**

Run:
`cd apps/mouth && npm run test -- src/lib/api/crm/crm.api.test.ts src/components/crm/TaxCompanyPilotWorkspace.test.tsx --run`

- [x] **Step 3: Run frontend typecheck if targeted tests pass**

Run:
`cd apps/mouth && npm run typecheck`

- [ ] **Step 4: Report exact status**

Report branch, changed files, commands run, failures if any, and the URL path `/clients/tax-pilot`.
