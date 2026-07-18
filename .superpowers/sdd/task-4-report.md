# Task 4 report: editorial front page and evidence reading

## Outcome

- Built a magazine-first authenticated front page with masthead, dated morning edition, hero dossier, conditional Breaking coverage, five editorial domains, curiosity module, and a restrained source-status footer.
- Added protected story and edition routes. Story pages expose sanitized evidence and revision history; edition pages preserve the selected archive revision while applying current source and asset overlays.
- Added responsive editorial styling with the approved anthracite, white, yellow, and red palette, sans-serif typography, asymmetric composition, and meaningful local visual placeholders.

## TDD evidence

- RED: the initial render suite reported six expected failures for missing editorial hierarchy, protected routes, evidence presentation, archive behavior, and the HTML response wrapper.
- RED: server rendering then exposed an unsupported direct `cloudflare:workers` import in Node. A request-scoped `AsyncLocalStorage` runtime adapter replaced that import without introducing shared mutable request state.
- GREEN: the complete package suite now passes 77 of 77 tests, including the new authenticated render and response-security coverage.

## Security and publication boundaries

- Authentication is checked before magazine reads and fails closed when no authenticated actor is available.
- Server read models expose sanitized publication DTOs and never pass raw claim, source, asset, snapshot, or internal record identifiers into rendered HTML.
- Evidence links accept HTTPS destinations only. Missing or degraded source data is represented as quiet, partial, or unavailable rather than inferred.
- The worker applies `private, no-store` and browser hardening headers only to HTML responses; JSON and media responses retain their existing cache behavior.

## Verification

- `npm test`: Vinext production build succeeded; 77 of 77 tests passed.
- `npm run lint`: passed.
- `git diff --check`: passed.
- Targeted scans confirmed approved sans-serif declarations and no raw identifier field references in the application or component rendering layer.

## Preserved workspace state

- Pre-existing changes in `INDEX.md`, `README.md`, and `.husky/_` were not edited and are excluded from this task's staging set.

## Review correction pass

- Rebased the magazine read model on the canonical Task 3 publication repository. The repository now returns complete published-edition metadata and embedded story projections; the front page derives its hero from the first valid ordered placement and uses only the contract domains (`immigration`, `company`, `tax`, `property`, `compliance`).
- Added a contract-valid integration fixture that passes through `parseEditionPacket`, the SQLite migration, and `createPublicationRepository`. It proves that a stale Breaking row cannot render after the story head advances, while historical edition revision 1 remains immutable and excludes live Breaking content.
- Expanded story pages with section, severity, lifecycle, coverage, event/first-seen/verified/published timestamps, visual provenance, and the append-only revision and visibility timeline.
- Corrected presentation requirements to the exact locked palette (`#2C2F38`, `#000000`, `#FFFFFF`, `#F4C430`, `#C8102E`), Montserrat/sans-only typography, exact `noindex, nofollow` robots metadata, exact external-link relation tokens, and WITA-labelled edition verification time.

## Review TDD and verification

- RED: five render assertions failed before implementation, covering the canonical Task 3 fixture, archive/Breaking separation, story metadata and provenance, locked design tokens, robots metadata, and WITA verification display.
- GREEN: `npm test` passed the production Vinext build and all 79 tests (79 passed, 0 failed).
- `npm run lint -- --max-warnings=0`: passed.
- `git diff --check`: passed.
- A standalone `npx tsc --noEmit` diagnostic remains outside the package gate because the existing Vinext/Cloudflare setup lacks ambient `cloudflare:workers`, `Fetcher`, and `D1Database` types and enables import-extension patterns that the standalone command rejects. The production package build passes.
