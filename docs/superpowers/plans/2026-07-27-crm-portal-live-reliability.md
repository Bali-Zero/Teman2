# CRM and Client Portal Live Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live CRM-to-client-portal test journey deterministic, accessible, and clean from client creation through final synthetic-data cleanup.

**Architecture:** Reuse the existing portal matters endpoint as the practice source of truth and merge required documents in the frontend. Make writes converge through precise React Query cache transitions, reuse the shared outside-click hook, and correct UI state derivations and theme tokens without introducing new persistence or endpoints.

**Tech Stack:** Next.js 16, React 19, TypeScript, TanStack Query, Vitest/Testing Library, FastAPI, asyncpg, pytest, Vercel, Fly.io.

## Global Constraints

- Work only in `/Users/balizero/nuzantara/.worktrees/frontend-crm-portal-live-fixes`.
- Never send email, WhatsApp, invitation, notification, or other external communication.
- Never log client PII; automated and live QA data must be synthetic.
- Do not modify `fly.toml`, `.env*`, `alembic/env.py`, or curated datasets.
- No database migration is required.
- Do not merge the branch, push `main`, arm auto-merge, or deploy directly; use PR plus an independent verifier and normal CI deployment.
- Every behavior change follows RED, GREEN, REFACTOR with the failing output recorded before implementation.

---

## File Structure

- `apps/backend-rag/backend/app/routers/portal_matters.py` — add the raw status to the existing client-safe matter shape.
- `apps/backend-rag/backend/tests/unit/routers/test_portal_matters.py` — protect the additive matter contract.
- `apps/mouth/src/lib/api/portal/portal.types.ts` — type the additive matter status.
- `apps/mouth/src/app/portal/(authenticated)/process/page.tsx` — merge matters with document rows and render zero-document practices.
- `apps/mouth/src/app/portal/(authenticated)/process/page.test.tsx` — cover matter-only process rendering.
- `apps/mouth/src/hooks/useClientDetail.ts` — provide exact client query invalidation and authoritative cache patching.
- `apps/mouth/src/hooks/useClientDetail.test.tsx` — cover invalidation and immediate cache convergence.
- `apps/mouth/src/app/(workspace)/process/new/page.tsx` — invalidate the selected client before returning to its profile.
- `apps/mouth/src/app/(workspace)/process/new/page.test.tsx` — cover the post-create cache transition.
- `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` — fix status selection, immediate status paint, and visible process count.
- `apps/mouth/src/app/(workspace)/clients/[id]/page.test.tsx` — cover mouse selection, pending refetch behavior, and cancelled count.
- `apps/mouth/src/app/portal/(authenticated)/visa/page.tsx` — render a neutral superuser no-selection state.
- `apps/mouth/src/app/portal/(authenticated)/visa/page.test.tsx` — distinguish the expected no-selection condition from real failures.
- `apps/mouth/src/hooks/useTeamMembers.ts` — normalize, deduplicate, and disambiguate assignee options.
- `apps/mouth/src/hooks/useTeamMembers.test.tsx` — cover duplicate email and duplicate display-name cases.
- `apps/mouth/src/components/portal/PracticeBaton.tsx` — use theme foreground for the copper CTA.
- `apps/mouth/src/components/portal/PracticeBaton.test.tsx` — protect CTA token usage.
- `apps/mouth/src/app/globals.css` — map operative-dark/light muted and CTA foreground tokens to AA-safe values.
- `apps/mouth/src/app/(workspace)/process/[id]/page.tsx` — wrap long client email addresses.
- `apps/mouth/src/app/(workspace)/process/[id]/page.test.tsx` — protect the responsive email markup.

### Task 1: Portal matter contract and zero-document process

**Interfaces:**

- Consumes: `PortalApi.listMatters(): Promise<{ matters: PortalMatter[] }>` and `PortalApi.getMyRequiredDocuments(): Promise<unknown[]>`.
- Produces: `PortalMatter.status: string` and a merged process model whose `documents` defaults to `[]`.

- [ ] **Step 1: Write the failing backend contract test**

Add this assertion to `test_shape_matter_maps_category_and_progress`:

```python
assert matter["status"] == "in_progress"
```

- [ ] **Step 2: Run the backend test and verify RED**

Run:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_matters.py::test_shape_matter_maps_category_and_progress -q
```

Expected: fail because `_shape_matter` has no `status` key.

- [ ] **Step 3: Write the failing portal page test**

Extend the API mock with `listMatters` and render one matter while
`getMyRequiredDocuments` returns `[]`:

```tsx
mockListMatters.mockResolvedValue({
  matters: [
    {
      id: 603,
      title: "Synthetic Investor KITAS",
      status: "inquiry",
      type: "visa",
      progress: 10,
      pending_docs: [],
      next_deadline: null,
      next_step: "inquiry",
    },
  ],
});
mockGetMyRequiredDocuments.mockResolvedValue([]);
render(<PortalProcessPage />);
expect(await screen.findByText("Synthetic Investor KITAS")).toBeInTheDocument();
expect(screen.getByText("No documents required")).toBeInTheDocument();
```

- [ ] **Step 4: Run the frontend test and verify RED**

Run:

```bash
cd apps/mouth
npm test -- --run 'src/app/portal/(authenticated)/process/page.test.tsx'
```

Expected: fail because the page derives every process from document rows.

- [ ] **Step 5: Implement the minimal contract and merge**

Return `"status": status` from `_shape_matter`, add `status: string` to
`PortalMatter`, load profile/matters/documents together, and reduce documents
into their matching matter. Preserve the existing card and upload behavior.

- [ ] **Step 6: Run both tests and verify GREEN**

Run the two commands from Steps 2 and 4. Expected: both pass.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/app/routers/portal_matters.py \
  apps/backend-rag/backend/tests/unit/routers/test_portal_matters.py \
  apps/mouth/src/lib/api/portal/portal.types.ts \
  'apps/mouth/src/app/portal/(authenticated)/process/page.tsx' \
  'apps/mouth/src/app/portal/(authenticated)/process/page.test.tsx'
git commit -m "fix(portal): show practices without required documents"
```

### Task 2: Immediate CRM cache convergence

**Interfaces:**

- Consumes: TanStack `QueryClient`, `ClientProfile`, and the existing key `["client", String(clientId)]`.
- Produces: `useSetClientCache(clientId)` and the existing `useInvalidateClient(clientId)` used before navigation.

- [ ] **Step 1: Write failing hook tests**

Use a real `QueryClientProvider`. Seed an active `ClientProfile`, call the cache
setter with an inactive API client, and assert the cached profile becomes
inactive. Separately call the invalidator and assert the client query is marked
invalidated.

- [ ] **Step 2: Run hook tests and verify RED**

Run:

```bash
cd apps/mouth
npm test -- --run src/hooks/useClientDetail.test.tsx
```

Expected: fail because `useSetClientCache` is not exported.

- [ ] **Step 3: Implement the client cache helper**

Use one exported `clientDetailQueryKey(clientId)` in the query, invalidator, and
setter. The setter preserves family, document, practice, company, and stats
data while replacing `profile.client` with the authoritative returned client.

- [ ] **Step 4: Write failing client-page regression tests**

Render the real client-detail hooks under a real query client and mock only API
boundaries and large child tabs. Verify:

```tsx
await user.click(screen.getByRole("button", { name: "Change client status" }));
await user.click(screen.getByRole("button", { name: "inactive" }));
expect(await screen.findByText("inactive")).toBeInTheDocument();
```

Keep the refetch promise pending so the assertion proves the authoritative
response paints before the background refresh. With a cancelled-only practice,
assert the visible tab label is `Process (0)`.

- [ ] **Step 5: Run the client page test and verify RED**

Run:

```bash
cd apps/mouth
npm test -- --run 'src/app/(workspace)/clients/[id]/page.test.tsx'
```

Expected: the mouse selection does not invoke the update, and the process tab
shows the backend total including the cancelled practice.

- [ ] **Step 6: Implement status and count fixes**

Attach the existing `useClickOutside` hook to a status-menu ref, patch the
client cache from `api.crm.updateClient`, trigger a non-blocking invalidation,
and derive the process tab count from
`activePractices.length + completedPractices.length`.

- [ ] **Step 7: Write the failing process-create regression test**

Render `NewPracticePage` with a real query client and synthetic API fixtures,
select a category/service, submit, and assert that the seeded client-detail
query is invalidated before the route returns to `/clients/7?tab=process`.

- [ ] **Step 8: Run process-create test and verify RED**

Run:

```bash
cd apps/mouth
npm test -- --run 'src/app/(workspace)/process/new/page.test.tsx'
```

Expected: query state remains valid.

- [ ] **Step 9: Invalidate before navigation and verify GREEN**

Call `useInvalidateClient(preselectedClientId ?? 0)` and await it after the
practice succeeds, before `router.push`. Re-run all three Task 2 test files.

- [ ] **Step 10: Commit**

```bash
git add apps/mouth/src/hooks/useClientDetail.ts \
  apps/mouth/src/hooks/useClientDetail.test.tsx \
  'apps/mouth/src/app/(workspace)/clients/[id]/page.tsx' \
  'apps/mouth/src/app/(workspace)/clients/[id]/page.test.tsx' \
  'apps/mouth/src/app/(workspace)/process/new/page.tsx' \
  'apps/mouth/src/app/(workspace)/process/new/page.test.tsx'
git commit -m "fix(crm): converge client state after mutations"
```

### Task 3: Neutral visa state and unique assignee options

**Interfaces:**

- Consumes: the backend’s exact superuser selection message and the team member
  response keyed by email.
- Produces: a neutral no-client-selected view and unique
  `{ value, label, avatar }` options.

- [ ] **Step 1: Add failing visa test**

Reject `getVisaStatus` with
`Error("Superuser: select a client via ?as_client=<id>")`. Assert the page shows
`Select a client to view visa information` and does not call the error toast.

- [ ] **Step 2: Add failing team hook tests**

Return two rows with the same lowercased email and two different emails with
the same full name. Assert one option remains for the duplicate email and both
same-name users have labels that include their email.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
cd apps/mouth
npm test -- --run \
  'src/app/portal/(authenticated)/visa/page.test.tsx' \
  src/hooks/useTeamMembers.test.tsx
```

Expected: the visa path toasts an error and assignee options contain duplicates.

- [ ] **Step 4: Implement minimal neutral state and normalization**

Match only the exact superuser selection condition. For team options, trim and
lowercase email keys, exclude client roles, keep the first duplicate email, and
append ` (email)` only where two distinct users share a display label.

- [ ] **Step 5: Re-run tests and verify GREEN**

Run the Step 3 command. Expected: both files pass, while the existing genuine
error test still passes.

- [ ] **Step 6: Commit**

```bash
git add 'apps/mouth/src/app/portal/(authenticated)/visa/page.tsx' \
  'apps/mouth/src/app/portal/(authenticated)/visa/page.test.tsx' \
  apps/mouth/src/hooks/useTeamMembers.ts \
  apps/mouth/src/hooks/useTeamMembers.test.tsx
git commit -m "fix(portal): clarify neutral states and assignees"
```

### Task 4: Palette AA and responsive email

**Interfaces:**

- Consumes: operative-dark and operative-light CSS variables.
- Produces: `--accent-foreground`, AA-safe muted text mappings, and a wrapping
  email row.

- [ ] **Step 1: Add failing PracticeBaton token test**

Assert the CTA uses:

```tsx
expect(screen.getByRole("button")).toHaveStyle({
  background: "var(--accent)",
  color: "var(--accent-foreground)",
});
```

- [ ] **Step 2: Add failing responsive email test**

Render a practice with
`synthetic.long.client.address.for.layout.qa@example.test`. Assert the link has
`min-w-0`, the icon has `shrink-0`, and a child span has `break-all`.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
cd apps/mouth
npm test -- --run \
  src/components/portal/PracticeBaton.test.tsx \
  'src/app/(workspace)/process/[id]/page.test.tsx'
```

Expected: CTA still uses white on copper and the email is raw flex text.

- [ ] **Step 4: Implement theme and wrapping changes**

In dark mode set `--accent-foreground: #16213a` and
`--bz-text-2: var(--tx-secondary)`. In operative-light set
`--accent-foreground: var(--tx-pure)` and map
`--foreground-muted`, `--tx-tertiary`, and `--bz-text-3` to the existing
AA-safe soft-ink step. Use `var(--accent)`/`var(--accent-foreground)` for the
CTA. Wrap the email in a `break-all` span with `min-w-0`; keep the icon
`shrink-0`.

- [ ] **Step 5: Re-run tests and verify GREEN**

Run the Step 3 command. Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/app/globals.css \
  apps/mouth/src/components/portal/PracticeBaton.tsx \
  apps/mouth/src/components/portal/PracticeBaton.test.tsx \
  'apps/mouth/src/app/(workspace)/process/[id]/page.tsx' \
  'apps/mouth/src/app/(workspace)/process/[id]/page.test.tsx'
git commit -m "fix(ui): restore readable portal palette and reflow"
```

### Task 5: Verification, PR, independent gate, deploy, and live QA

**Interfaces:**

- Consumes: the complete feature branch and repository CI.
- Produces: reviewed PR, CI deployment, live evidence, and confirmed cleanup.

- [ ] **Step 1: Run the changed frontend regression suite**

```bash
cd apps/mouth
npm test -- --run \
  'src/app/portal/(authenticated)/process/page.test.tsx' \
  'src/app/portal/(authenticated)/visa/page.test.tsx' \
  'src/app/(workspace)/clients/[id]/page.test.tsx' \
  'src/app/(workspace)/process/new/page.test.tsx' \
  'src/app/(workspace)/process/[id]/page.test.tsx' \
  src/hooks/useClientDetail.test.tsx \
  src/hooks/useTeamMembers.test.tsx \
  src/components/portal/PracticeBaton.test.tsx
```

- [ ] **Step 2: Run frontend static gates**

```bash
npm run typecheck
npx eslint \
  'src/app/portal/(authenticated)/process/page.tsx' \
  'src/app/portal/(authenticated)/visa/page.tsx' \
  'src/app/(workspace)/clients/[id]/page.tsx' \
  'src/app/(workspace)/process/new/page.tsx' \
  'src/app/(workspace)/process/[id]/page.tsx' \
  src/hooks/useClientDetail.ts \
  src/hooks/useTeamMembers.ts \
  src/components/portal/PracticeBaton.tsx
npm run build
```

- [ ] **Step 3: Run backend and pre-deploy gates**

```bash
cd ../../apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_matters.py -q
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest \
  backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q
```

- [ ] **Step 4: Review diff and create PR**

Confirm only intended files changed, push
`agent/air-m5/frontend/crm-portal-live-fixes`, and create a PR against `main`
with the RED/GREEN evidence and live findings. Do not enable auto-merge.

- [ ] **Step 5: Independent verification and deployment**

Have an independent Claude verifier review the diff and test evidence. Only the
independent lane may approve/merge. The merge to `main` triggers Vercel
frontend deployment and the repository’s normal backend Fly workflow.

- [ ] **Step 6: Post-deploy health and browser QA**

Verify backend health returns 200 or 307. In the authenticated browser:

1. create one synthetic client;
2. update status by mouse and confirm immediate repaint;
3. create a synthetic process and confirm it appears immediately in the client profile;
4. sign in/impersonate the synthetic client and confirm the process appears with zero required documents;
5. verify the neutral superuser visa state;
6. inspect assignee uniqueness, palette, focus/interaction state, and long-email reflow;
7. capture and inspect screenshots for each accepted step;
8. cancel/delete the synthetic process;
9. soft-delete the synthetic client;
10. reload both team and client surfaces and verify cleanup.

- [ ] **Step 7: Report**

Report PR/deployment identifiers, exact test/build results, numbered live QA
steps with health, screenshot paths, remaining evidence limits, and cleanup
confirmation. Do not claim full WCAG compliance from screenshots alone.
