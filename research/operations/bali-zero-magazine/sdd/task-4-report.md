---
adversarial_review: codex
adversarial_review_date: 2026-07-21
---

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

## Second review correction pass

- Reassigned the locked palette to semantic surface roles: anthracite is the primary editorial canvas, black is the secondary surface, white is body ink, and yellow/red retain their exact accent values. Contrast-sensitive yellow treatments now use black text.
- Added an explicit `lead` placement field to the closed edition contract. Standard editions require exactly one lead; quiet editions require none. D1 persists `is_lead`, enforces at most one lead with a partial unique index, and compares the persisted flag with the packet during atomic finalization.
- Changed front-page composition to select the declared lead instead of inferring a hero from section-local order. A two-section integration fixture gives both stories order 1 and proves that the declared tax lead wins in the current edition while the archived edition keeps its own declared compliance lead.
- Added nullable `event_occurred_at` to the story contract, migration, repository, and reader DTO. The story page renders an explicit unavailable message when the source packet does not declare event time; it never substitutes `updated_at`.
- Removed the inferred correction event. The timeline now reports only persisted publication lifecycle rows with real `published_at` values and append-only visibility events with their recorded `created_at` values.

## Second review TDD and verification

- RED/GREEN: contract tests first failed on unknown `event_occurred_at` and `lead` fields, then passed after closed-schema validation and standard/quiet lead cardinality rules were implemented.
- RED/GREEN: the render fixture now exercises equal section-local ordering across tax and compliance and asserts the explicit lead in both current and archived revisions.
- GREEN: `npm test` passed the production Vinext build and all 82 tests (82 passed, 0 failed).
- `npm run lint -- --max-warnings=0`: passed.
- `npm run db:generate`: reported `No schema changes, nothing to migrate`.

## Adversarial review

Codex challenged whether the declared lead, archived revision, event time, and
correction timeline were inferred rather than persisted. The report's focused
fixtures and closed-schema checks answer those objections. The 82-test total is
point-in-time evidence for Task 4 and must not be read as the current package
total.
- `npx prettier --check` and `git diff --check`: passed for the scoped implementation.
