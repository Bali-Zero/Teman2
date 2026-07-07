# Portal Readiness Audit - 2026-06-25

## Scope

This audit covers the client-facing portal experience for `my.balizero.com`, with emphasis on first-client readiness:

- Bureaucracy visibility: active practices, company status, tax status, documents, and process timeline.
- Smart advice: next actions, operational recap, deadlines, and matter-specific context.
- Deadlines: upcoming renewals and compliance checkpoints.
- Bali Zero information layer: approved editorial/news content in the portal context.
- Mobile usability: primary navigation remains reachable and pages do not create horizontal overflow.

No real client PII was used in the browser smoke tests. The Playwright fixture uses a synthetic `.test` client profile and mocked portal API responses.

## Current Verdict

The portal is now covered by a first-client smoke suite and the reproduced UX/runtime bugs were fixed. The local synthetic gate is green on desktop and mobile.

Before inviting the first real client, run one final production smoke on `my.balizero.com` using a sanctioned pilot account with non-sensitive sample data or an explicitly approved real record. The final gate must verify the deployed Vercel build, real auth cookie/session behavior, and backend data visibility.

## Fixed During This Pass

### P1 - Company status card opened the wrong section

The dashboard Company card routed clients to `/portal/vault`, which made the company-status surface feel broken and hid the dedicated company compliance view.

Fixed path:

- `apps/mouth/src/app/portal/(authenticated)/page.tsx`

New behavior:

- Company card opens `/portal/companies`.
- Smoke test verifies the card opens the Companies page and shows the primary company.

### P1 - Dispatch links used portal-relative article routes

The portal rendered Bali Zero Dispatch article links as same-origin routes. On `my.balizero.com`, those article routes belong to the public marketing site, not the client portal, and browser prefetch could trigger failed cross-origin noise.

Fixed path:

- `apps/mouth/src/components/portal/PortalNewsRail.tsx`

New behavior:

- Article links open `https://balizero.com/<category>/<slug>` in a new tab.
- The "More from Bali Zero" link opens `https://balizero.com/news`.

### P1 - Toast helpers changed identity on every render

The `useToast()` convenience helpers were recreated on every render. Pages that included a toast helper in an effect dependency could refetch repeatedly and log fetch failures during fast navigation.

Fixed path:

- `apps/mouth/src/components/ui/toast.tsx`

New behavior:

- Toast helper callbacks are memoized with `useCallback`.
- The all-sections Playwright loop no longer reports company-detail fetch errors during route changes.

## Browser Smoke Coverage Added

New Playwright file:

- `apps/mouth/e2e/portal-client-ready.spec.ts`

Covered flows:

- `/portal`: matter-first dashboard, next action, deadline, company card navigation.
- `/portal/dashboard`: client profile, operational recap, and Bali Zero Dispatch content.
- `/portal/matters` and `/portal/matters/[id]`: client-readable matter summary.
- `/portal/process`: active process, required documents, and explicit upload action.
- `/portal/vault`: document vault listing and search.
- `/portal/messages` and `/portal/chat`: client-safe messaging surface.
- `/portal/companies` and `/portal/company/[id]`: company/compliance surface.
- `/portal/visa`, `/portal/taxes`, `/portal/lkpm`, `/portal/billing`, `/portal/family`, `/portal/profile`, and `/portal/settings`: primary portal sections render without runtime errors.
- Mobile viewport: bottom navigation exposes Home, Vault, Chat, and Profile, with no horizontal overflow.

The suite also fails on:

- Browser page errors.
- Unexpected console errors, except missing favicon noise.
- Unhandled API calls in the test fixture.
- Horizontal document overflow.

## Verification Evidence

Backend portal targeted tests:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/routers/test_portal.py backend/tests/unit/routers/test_portal_dashboard.py backend/tests/unit/routers/test_portal_drive.py backend/tests/unit/routers/test_portal_process_timeline.py backend/tests/unit/routers/test_portal_notifications.py backend/tests/unit/services/portal/test_portal_service.py -q
```

Result:

```text
123 passed
```

Frontend targeted portal tests:

```bash
cd apps/mouth
npm test -- --run src/components/portal/PortalNewsRail.test.tsx src/components/portal/PortalBottomNav.test.tsx src/components/portal/PracticeBaton.test.tsx src/app/portal/'(authenticated)'/page.test.tsx src/app/portal/'(authenticated)'/layout.test.tsx src/app/portal/'(authenticated)'/vault/page.test.tsx src/app/portal/login/route.test.ts src/lib/api/portal/portal.api.test.ts
```

Result:

```text
8 test files passed
87 tests passed
```

Frontend typecheck:

```bash
cd apps/mouth
npm run typecheck
```

Result:

```text
tsc --noEmit passed
```

Targeted ESLint for the modified portal page:

```bash
cd apps/mouth
../../node_modules/.bin/eslint src/app/portal/'(authenticated)'/page.tsx
```

Result:

```text
passed
```

Full frontend Vitest suite was also triggered during the pass:

```text
207 test files passed
1836 tests passed
```

Browser smoke, desktop Chromium:

```bash
cd apps/mouth
PLAYWRIGHT_EXTERNAL_SERVER=1 npx playwright test e2e/portal-client-ready.spec.ts --project=chromium --reporter=list
```

Result:

```text
6 passed
```

Browser smoke, Mobile Chrome:

```bash
cd apps/mouth
PLAYWRIGHT_EXTERNAL_SERVER=1 npx playwright test e2e/portal-client-ready.spec.ts --project='Mobile Chrome' --reporter=list
```

Result:

```text
6 passed
```

## Local Worktree Dev Server Note

In this worktree, the default Turbopack dev server failed because `node_modules` is symlinked outside the worktree root:

```text
Symlink [project]/node_modules is invalid, it points out of the filesystem root
```

Use the webpack dev server when running Playwright from this worktree:

```bash
cd apps/mouth
npm run dev -- --webpack --hostname 127.0.0.1 --port 3000
PLAYWRIGHT_EXTERNAL_SERVER=1 npx playwright test e2e/portal-client-ready.spec.ts --project=chromium
```

## First-Client Acceptance Gate

The first real client should not receive access until these checks pass on the deployed `my.balizero.com` surface:

- Client can log in from the intended invitation path without admin privileges.
- Portal opens directly to the client dashboard after login.
- Dashboard shows at least one real matter or a clean empty state approved by Ops.
- Next action is visible without opening DevTools or searching through sections.
- Upcoming deadline is visible when one exists; no invented deadline appears when none exists.
- Process page shows active practices and required documents with correct status.
- Vault shows only client-visible documents and never internal team notes.
- Companies page shows only companies linked to the authenticated client.
- Messages and notifications do not leak internal CRM or OSINT phrasing.
- Bali Zero Dispatch content is approved editorial content, not raw research or private intelligence.
- Mobile navigation is visible on iPhone-sized viewport.
- Browser console has no runtime errors on dashboard, process, vault, companies, and profile.

## Residual Risks

- Synthetic Playwright smoke does not prove the deployed Vercel auth/session cookie path. Run the final smoke on `my.balizero.com` after deployment.
- Synthetic API fixtures do not prove production CRM data completeness. Use the onboarding runbook before issuing the invite.
- The worktree-specific Turbopack symlink issue is a local test-environment limitation, not a production blocker.
