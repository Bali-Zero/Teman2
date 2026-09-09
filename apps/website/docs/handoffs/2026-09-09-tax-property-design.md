# Tax and Property native migration — R19 review handoff

Status: implemented in the unpublished R19 worktree. Domain files frozen for parent integration. No build, preview restart, production evaluation, deployment, merge, push or client send performed by this worker.

## Native journeys

| Route | Native behavior |
| --- | --- |
| `/tax-calendar` | Six explicitly historical/unverified records; obligation and regency filters; national records retained in regional views; filtered all-day ICS export; archived notes; review contact context. |
| `/taxes/gap` | Tax record preparation, interactive reversible checklist, reconciliation steps, retained service scope and explanatory FAQs. The prior page was a consultation CTA, not a tax calculator. |
| `/tax/gap` | Local 307 alias to `/taxes/gap`, preserving query parameters. |
| `/property/eligibility` | Decimal, DMS and Google Maps coordinate input; optional KBLI/structure and paired area/price inputs; explicit analysis submission; zoning, building parameters, overlays, service score and factors, restrictions, activities, investment and property-tax estimates. |
| `/zoning` | Full preparation journey for title, land use, building documents and agreement review, with checklist, scope, stages and FAQs. |
| `/prime` | Native public polygon atlas; load/retry states; real geometry, zoom and color controls, zone selection, comparison of up to three recorded zone limits, shared coordinate analysis. |
| `/prime/proposal/[token]` | Explicit opening action, redacted saved property assessment, expiry/missing/unavailable states. Page render does not fetch the token. |

All pages consume the parent-owned `SiteShell` and create their own `main#main-content`. Scoped styling uses Fraunces/Manrope and the approved paper, ink, slate and copper colors. No new dependency is required.

## Data contract and retained boundaries

The property adapters require an explicit `WEBSITE_PROPERTY_API_ORIGIN`. An HTTPS origin or a localhost HTTP origin is accepted; userinfo, paths, queries and fragments are rejected. There is no production fallback. No configuration means HTTP 503 with honest UI messaging.

Only the following upstream operations are available:

| Native endpoint | Upstream |
| --- | --- |
| `POST /api/property/analyze` | `POST /api/prime/v2/analyze` |
| `POST /api/prime/v2/analyze` | Same fixed analysis endpoint (compatibility alias) |
| `GET /api/prime/zones-geojson` | `GET /api/prime/zones-geojson` |
| `POST /api/prime/v2/proposal/[token]` | `GET /api/prime/v2/proposal/[token]` |
| `GET /api/tax-calendar/deadlines` | Local archival records |
| `GET /api/tax-calendar/ical` | Local filtered archival export |

The existing proposal GET updates `viewed_at` and `status` on first access. The native adapter therefore accepts only a same-origin POST following the explicit Open proposal button. GET, HEAD, cross-site requests and malformed tokens do not invoke upstream. The upstream operation remains unchanged; its view side effect is disclosed before opening.

POST analysis also requires matching Origin and rejects cross-site Fetch Metadata. Request bodies are limited to 4 KiB. Upstream calls use fixed paths, a 15-second timeout, redirect rejection, no cookies/credentials forwarding and no-store responses. Analysis/proposal responses are limited to 2 MB and geometry to 20 MB. Browser requests have a 20-second timeout.

Only coordinates, KBLI, PMA boolean, land area and purchase price can be forwarded for analysis. Investor profiles, identities and geo/scoring overrides are stripped. Public projections exclude client names, emails, proposal IDs/tokens, intel articles and raw errors. Geometry strips extra coordinate dimensions and accepts only six-digit hex colors. Existing calculator and scoring outputs are retained without reimplementing formulas or inventing missing results. ROI errors remain unavailable; missing zone coverage never becomes an eligibility verdict.

The original Google 3D view still depends on its Google Maps JavaScript renderer/key contract. That view is not transplanted into this public atlas. Authenticated client overlays, portfolio records and proposal creation also remain in the existing Prime workspace. `/legacy/prime` is the parent-maintained explicit bridge. The public atlas states these boundaries; `/prime/[...retainedPath]` retains explicit handling for other original Prime paths.

No current tax deadlines were fabricated. The inherited six rows cover April–July 2026 and contain date/source claims that were not verified in this migration. Their original dates and notes are retained as an unverified archive, without recurrence, current-deadline claims, reminder subscriptions or silent date rollover. ICS titles and descriptions carry the same archival warning.

## Source fidelity

Read current Mouth and backend source in the main checkout; source HEAD observed during migration: `15751bd0705334dea3dfb06ba475e38b9320ec97`. Compared the worktree's older calendar and eligibility sources with the current versions. Sources used:

- `apps/mouth/src/components/funnel/PropertyEligibilityBody.tsx` and coordinate parsing utility.
- `apps/mouth/src/app/api/tax-calendar/deadlines.ts`, original calendar filter/export journey.
- `apps/mouth/src/app/taxes/gap/page.tsx` and `apps/mouth/src/app/zoning/page.tsx`.
- Prime map/layout, public API adapters and proposal page in `apps/mouth`.
- `apps/backend-rag/backend/services/prime/prime_nexus_service.py`, `property_service.py`, and `backend/app/routers/prime_v2.py` for the actual analysis/proposal contracts.
- Existing R19 `src/content/service-section-content.ts` for approved tax/property scope, preparation and FAQ depth.

No source application, backend, curated data or calculator logic was modified.

## Worker-owned file inventory

Feature directory `src/features/tax-property/`:

- `ToolFrame.tsx`, `tools.module.css`
- `TaxCalendar.tsx`, `tax-calendar.ts`, `tax-calendar.server.ts`
- `Preparation.tsx`
- `PropertyCheck.tsx`, `AnalysisResult.tsx`, `ZoneAtlas.tsx`, `Proposal.tsx`
- `coordinates.ts`, `property-contract.ts`, `property.server.ts`
- `contracts.test.ts`, `property.server.test.ts`, `journeys.test.tsx`

Route files:

- `src/app/tax-calendar/page.tsx`
- `src/app/taxes/gap/page.tsx`
- `src/app/tax/gap/route.ts`
- `src/app/property/eligibility/page.tsx`
- `src/app/zoning/page.tsx`
- `src/app/prime/page.tsx`
- `src/app/prime/proposal/[token]/page.tsx`
- `src/app/prime/[...retainedPath]/route.ts`
- `src/app/api/property/analyze/route.ts`
- `src/app/api/prime/v2/analyze/route.ts`
- `src/app/api/prime/zones-geojson/route.ts`
- `src/app/api/prime/v2/proposal/[token]/route.ts`
- `src/app/api/tax-calendar/deadlines/route.ts`
- `src/app/api/tax-calendar/ical/route.ts`

Replaced retained route handlers: `tax-calendar/route.ts`, `taxes/gap/route.ts`, `property/eligibility/route.ts`, `zoning/route.ts`, and `prime/[[...retainedPath]]/route.ts`. Those files were removed to avoid route/page conflicts. Shared shell, navigation, routing registry, server policy, globals, package/lockfile and Oracle are owned by the parent/other workers and were not edited here.

## Verification

Executed from `apps/website`:

```text
npm test -- src/features/tax-property --maxWorkers=1 --no-file-parallelism
3 test files passed; 37 tests passed; duration 1.55 seconds.
```

All network tests use synthetic mocked responses; no real coordinates were submitted to production and no real proposal tokens were opened. Tests cover coordinate parsing/ranges, native filters/ICS, public projection idempotence, PMA false values, missing coverage, failed calculations, unsafe geometry/colors, exact request paths, credential stripping, body/response bounds, explicit origin configuration, stale-result clearing, proposal method/origin/expiry protection, native map comparison and reversible checklists.

`tsc --noEmit --incremental false` reported only stale `.next/types` references to replaced retained route handlers (Tax/Property and the concurrent KBLI migration), with no `src` diagnostics. The worker did not clear or rebuild shared `.next`. The parent's serialized rebuild and browser verification remain the integrated acceptance step.

Scoped Prettier completed for the owned feature and route files. Final browser check should cover desktop/mobile typography and overflow, calendar PB1 + Badung → one record and filtered ICS, both preparation checklists, property unavailable state, Prime load/retry state, a synthetic polygon/analysis success fixture, and proposal absence of requests until an explicit same-origin POST.
