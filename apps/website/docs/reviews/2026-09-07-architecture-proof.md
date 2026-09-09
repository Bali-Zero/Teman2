# Website architecture proof — 7 September 2026

## Decision supported by the evidence

Keep the marketing presentation independent from application providers and put
an explicit publishing contract between it and editorial storage. Both an
integrated application and a separate marketing application can consume this
contract. This proof does not select a deployment topology.

Migration is also a correction opportunity: preserve useful destinations and
user journeys while replacing unsafe or ambiguous publishing behavior.

## What changed

The homepage Journal now accepts article records as props. The server page still
supplies the same checked six-record snapshot, so there is no live publishing
connection in this batch. The Journal handles empty feeds and feeds that shrink
after carousel navigation, and hides navigation controls for a single record.

A proposed, versioned feed decoder requires explicit publication approval and
indexability, validates categories, slugs, image origins and dates, and removes
duplicates while preserving source order. Missing dates remain missing. Failed
reads and malformed payloads return an unavailable state instead of sample news.
Publication approval remains distinct from an independently checked destination.

The contract currently accepts only same-origin `/static/` editorial assets.
Before adoption, inventory legitimate external assets and category conventions;
this policy has not been proven compatible with the complete article corpus.

## Reproducible comparison

The isolated suite executes the actual `mouth` MDX reader against the unchanged
repository article `tech/fintech-payments-indonesia.mdx`. Its raw `tech` category
is mapped by the real reader to `trends`. A proof adapter restores explicit
publication metadata from the raw article, because the legacy listing loses it.

The same small marketing page, containing the Journal and an E-VOA link, renders
with no `mouth` application providers. Passing the validated record directly or
through an actual ephemeral localhost HTTP server produces identical React
server-rendered HTML. Assertions preserve the canonical article path, editorial
asset origin, `/news` index destination and `/visa/voa` product destination.

| Question | Result | Limit |
| --- | --- | --- |
| Can Journal presentation avoid application providers? | Yes, in the isolated rendered page. | Full integrated Next.js layout not built. |
| Can direct and separate-service delivery share one consumer? | Yes, identical validated data and rendered HTML. | Loopback JSON service, not deployed infrastructure. |
| Can the legacy list be trusted as explicitly approved? | No; it drops publication state. | Proposed decoder refuses it until an adapter restores authoritative evidence. |
| Does a reader failure fabricate news? | New boundary returns unavailable and Journal keeps useful navigation. | Existing production API remains unchanged. |
| Are real destinations preserved? | Exact hrefs asserted in rendered output. | No login, destination availability or cross-zone transition test in this suite. |

## Historical behavior reproduced and identified

Synthetic fixtures passed through the real local reader reproduce a draft being
included in a listing and a missing publication date being replaced. A no-index
fixture is excluded. These are characterization tests: their passing records
the defects, not approval of them. No claim is made that a specific draft is
currently exposed in production.

Source inspection also identified demo-article fallback behavior in
`apps/mouth/src/app/api/blog/articles/route.ts`. That endpoint should not become
the new homepage's source unchanged. The proof deliberately does not call it.

## Architecture trade-offs

The existing marketing route group inherits the root application's query/theme
providers and global monitoring/error/UI behavior. The current R19 homepage
does not need the query or theme providers to render. Authentication/session
bridges, analytics and error reporting should have explicit ownership, rather
than being copied merely because they exist in the old root.

Integration into `mouth` may simplify ownership of existing routes and article
storage, but requires proving an isolated marketing layout within that app.
A separate website provides an independent build/runtime boundary, but needs
explicit route, asset, release and editorial-refresh ownership. Multi-zone
deployment additionally needs asset-prefix and cross-zone navigation checks.
An HTTP feed by itself does not solve those issues.

## Verification and limits

- Website suite: 55 tests passed in 12 files; TypeScript check passed.
- Architecture suite: 5 tests passed in one file, including actual loopback HTTP.
- Website optimized build passed, including homepage, Journal, services and Team.
- Browser checks at 1440px and 390px confirmed working carousel navigation,
  no horizontal overflow, a decoded feature image and retained preview noindex.
  Browser console reported no errors or warnings. Evidence is saved under
  `output/playwright/journal-boundary-desktop.png` and
  `output/playwright/journal-boundary-mobile.png` in the worktree.
- The architecture suite bypasses `next/cache`, forces the editorial backend
  unavailable, and uses one real MDX article plus three synthetic fixtures.
- No full-corpus validation, cache/ISR test, authenticated journey, multi-zone
  deployment, performance comparison or production publishing change is claimed.
- All implementation stays in `agent/air-m5/infra/website-r19`; no main merge or
  deployment is part of this work.

## Next bounded step

Define the authoritative publish-state and no-index mapping for both MDX and
backend records, then implement an isolated publisher adapter with empty/error
responses that stay distinguishable. Inventory route and asset ownership for
both deployment options before selecting topology. Keep editorial publication,
marketing presentation and authenticated products independently testable.

Reproduction details: `apps/website/proofs/architecture/README.md`.
