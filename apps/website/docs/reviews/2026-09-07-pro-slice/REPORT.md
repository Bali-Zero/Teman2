# Magazine to R19 Journal — completed local slice

Date: 2026-09-07 WITA. Machine: Pro (nuzantara@Nuzantara).

## Outcome and boundary

The homepage Journal and /journal now read the same versioned Magazine
publication projection at request time. The existing Magazine repository remains
the authority. The website supplies R19 presentation and a strict public-field
decoder. The transport is deliberately unarmed: an explicit local fixture switch
enables a deterministic demonstration; otherwise both routes show unavailable.

This is local preparation only. No production data, access changes, canonical
deployment verification, commit, push, PR, merge, auto-merge, deploy or publication
occurred. The inherited dirty overlay remains essential to the checkpoint.

**Bites:** src/app/page.tsx and src/app/journal/page.tsx consume the new server
loader. Built HTTP responses on both routes contain the same sample edition
when enabled, and the unavailable notice without sample stories when disabled.
See evidence/fixture-http.json and evidence/unarmed-http.json.

## Implementation

- SELECT-only adapter over the existing publication repository; current edition
  identities re-resolved through published/current/quarantine rules; repeated
  placements deduplicated; no raw-row serialization.
- Version 2 envelope and atomic decoder with explicit fields, canonical story
  route validation, publication timestamps, source-origin allowlist, current
  amendment labels and ordered publication revisions.
- Distinct empty, unavailable, malformed, withdrawn and unpublished states.
  These states suppress supplied stale cards. No historical snapshot fallback.
- Nullable media. Publisher images stay absent until delivery and rights are
  verified; one original SVG is explicitly fixture artwork. Eligibility follows
  the authority's latest status and rights events.
- Source/revision disclosure outside the story destination. Fixture story and
  source destinations are inert, accompanied by a sample-content notice.
- Request-time rendering via Next connection(), retaining private/no-store and
  preview noindex headers. The default loader cannot silently enable fixtures.

The fixture applies real Magazine migrations and repository stage/finalize calls
to fresh in-memory SQLite. It seeds synthetic rights/visibility rows, bypassing
machine ingress authorization, audit/promotion and canonical asset-byte checks.
This distinction is intentional and documented in DECISION.md. There are three
visible synthetic stories, including one amended second version; quarantined and
building candidates are suppressed. There are no real regulatory/news claims.

The v1 MDX characterization proof is retained in isolation. It records historical
reader defects and is not the current Journal source.

## Verification

| Check | Observed result | Evidence |
| --- | --- | --- |
| Transfer baseline | All 152 transferred manifest entries matched before work | Initial source manifest and baseline logs |
| Baseline | 55 website + 5 architecture tests; typecheck/build passed | evidence/baseline-* |
| Final website suite | 55 tests, 12 files passed | evidence/final-tests.log |
| Final architecture suite | 47 tests, 3 files passed | evidence/final-architecture.log |
| Final TypeScript | tsc --noEmit exit 0 after build | evidence/final-typecheck.log |
| Optimized build | exit 0; / and /journal dynamic | evidence/final-build.log |
| HTTP fixture/default | Both routes 200, no-store, noindex; opt-in only | evidence/*-http.json |
| Desktop/mobile | 1440px and 390px; no horizontal overflow; no broken Journal images | evidence/browser-*.txt |
| Keyboard | Enter toggles revision disclosure; Enter/ArrowLeft changes/restores carousel with focus retained | evidence/browser-journal.txt, browser-home-keyboard.txt |
| Browser console | 0 errors and warnings in checked fixture session | evidence/browser-console.txt |
| Inherited overlay | 152 entries still present; 134 byte-identical, 18 deliberately changed | evidence/inherited-overlay-comparison.json |

No package or lockfile change was made in this slice. Installed via the inherited
npm 11.19.0 lockfile; Node 26.5.0, Next 16.3.1, React 19.2.8. node:sqlite is needed
for the local architecture fixture; older Node versions were not exercised.

One integrated test failed because the old assertion expected the prior generic
unavailable copy. It was updated to the explicit feed state and rerun. Running
the final build and tsc simultaneously caused TS6053 while Next regenerated
.next/types; sequential typecheck after build passed. This was an environment
race, not a suppressed type error. Run those two commands sequentially.
The inherited Vite CommonJS warning and jsdom navigation warning were nonfatal.

Browser-use returned Transport closed. Playwright CLI then provided the actual
browser checks. No browser bridge/configuration was changed. Screenshots are in
output/playwright/website-r19-pro/: Journal desktop/mobile, amendment crops,
homepage Journal desktop/mobile, and unavailable Journal. Captures were made
from scroll origin to avoid sticky-header screenshot artifacts. A full assistive
technology audit and production browser/network parity were not performed.

## Independent review

The separate publication-boundary reviewer found an in-read withdrawal/rights
race affecting earlier candidates. The adapter now performs a final all-story
head/visibility and image-rights check, covered by two regression cases. The
reviewer rechecked the correction and reported no blocker for this local slice.
See boundary-review.md. Its served model was not independently observable.

Visual review result and exact served-model provenance are recorded separately
in claude-review.md and review-provenance.json. These are bounded reviews, not a
production approval or shipping gate.

The visual review actually served claude-opus-5 through the MAX OAuth CLI and
accepted the local proof. Its concrete accessibility, gutter, short-card and
fixture-affordance findings were corrected in one bounded batch; see
review-resolution.md. All final test/build logs were regenerated after those
edits. Fresh browser evidence verifies equal hero/story gutters, skip focus,
32px navigation targets and the text-only carousel at both viewport sizes.
The original six reviewed images remain under reviewed-before-fixes/; the final
screenshots were inspected by the builder, not independently re-reviewed.

The Gemini research stage is now complete; the earlier provenance statement
that it was not invoked is superseded. See gemini-research.md and
gemini-research-receipt.json for the qualified synthesis and execution evidence.
agy 1.1.27 completed one model turn with exit 0 / SUCCESS after a parser-only
first launch failed with exit 2. The requested and runtime-selected model was
gemini-3.1-pro-high; the provider's backend model and account/billing route were
not independently attested. Three search_web and two read_url_content calls
completed. Only web reads were observed; the plan-mode warning and
permission_mode always-proceed mean read-only sandbox enforcement is unproven.

Coordinator checks of Fetch, Next and RFC 9111, plus the audit agent's MDN,
Next and Cloudflare checks, qualify the model answer. The retained conclusions
are that CORP same-origin blocks ordinary cross-origin no-cors image use;
connection() and HTTP no-store do not establish atomic database reads or recall
already delivered content; and D1 session consistency alone is not a frozen
multi-query snapshot. See gemini-primary-sources.json for source-by-source
provenance. Current Next documentation is not an exact-version audit of local
16.3.1. Claims that all image attempts reach the origin, all App Router caching
is disabled, or every concurrent withdrawal necessarily defeats the final
recheck were rejected. A single SQL query and SSE/WebSockets are not mandated
as the only solutions by this evidence.

This research adds no blocker to the accepted local fixture and does not reopen
its tested final-recheck mitigation. It sharpens the future production contract:
prove the browser media path and read-consistency/freshness policy, with an
explicit refresh decision if already-open screens must update. No production
connection, publication, access change or new product edit follows from it.

## Remaining work and checkpoint

Separate D1 reads are not an atomic snapshot. Source-origin approval does not
sanitize arbitrary citation text. Canonical access, authenticated transport,
cache invalidation, approved public evidence and same-origin media remain
unproven. Current-edition selection also does not define breaking-news coverage.
Resolve these together in the next bounded contract task; do not attach a live
publisher by merely setting an environment variable.

Worktree: /Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro.
Branch: codex/website-pro-continuation.
Base HEAD: b740b2cc3e94b1a46c9e9811bb369289fc21ea3d.
Exact overlay checkpoint:
/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro/output/checkpoints/2026-09-07-pro-slice/.
Its CHECKPOINT.json identifies the base, archive hash, file manifest and
exclusions; VERIFIED.json records extraction and live-file verification. The
existing /output/ ignore rule covers this directory. RELOCATION.json records
the move of the eight finished-slice artifacts from the former external path;
that external copy was removed only after its directory was empty. The original
/Users/nuzantara/website-handoffs/2026-09-07-r19 transfer package is untouched.
The final overlay includes the original 152 paths, scoped current changes, full
review evidence including ignored test logs, and screenshots. It excludes its
own checkpoint directory and runtime caches; fixture-preview-startup.log is
retained while the active fixture-preview.log is excluded.
HEAD alone does not restore this result. Read the companion
apps/website/docs/handoffs/2026-09-07-pro-slice-complete.md before resuming.

One built preview remains at http://127.0.0.1:3100/ with
WEBSITE_EDITORIAL_FIXTURE=1. The port/process is transient: identify ownership
again before stopping or replacing it. The closeout recheck found exactly one
listener owned by this worktree; / and /journal returned 200 with preview
noindex and private/no-store. See the checkpoint's PREVIEW.json for the final
timestamp and process. This closeout changed documentation/checkpoint evidence
only; the recorded 55 website and 47 architecture tests, build and typecheck
remain the last product verification and were not rerun for these doc changes.
