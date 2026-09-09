# R19 full-site review

> Active-work update — the owner changed direction to palette and typography before final closure. The local Journal technical proof is complete; the initial homepage CTA overlap has a CSS correction and passing focused browser proof. The narrow independent follow-up started before the redirect arrived and was then interrupted: exit 143, status `no_final_result`, no verdict. The original FAIL remains historical evidence; whole-site acceptance is still open. The owner has now authorized a distinct pre-design WIP checkpoint at `output/checkpoints/2026-09-07-pre-design`, preserving the current work without final acceptance; its archive and hashes must be verified by the checkpoint owner. No completion handoff or state acceptance update has been made. The evidence below does not approve subsequent design changes.

Date: 2026-09-07 (WITA). Machine: Pro. Status: **NOT ACCEPTED — independent Claude review found a blocking homepage CTA overlap. Correction and independent follow-up are pending.**

This review continues the existing R19 website in `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`, branch `codex/website-pro-continuation`, at base `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d` plus the preserved inherited overlay. It covers two concurrent tracks: a bounded local Journal read contract and review of the complete existing website. Production remains unarmed. No production credentials, data, publishing, access policy, merge, deployment, or production transport configuration was changed.

## Outcome by track

**Track A — local Magazine contract:** authenticated loopback authority, Website transport, snapshot/version checks, exact public-projection approval, and scoped media mediation are implemented and tested through real repository reads, canonical migration fixtures, actual local HTTP, and the existing Website v2 consumer. Independent boundary review passed. These are explicit local factories; the Website loader does not call them. The running UI retains its pre-existing `WEBSITE_EDITORIAL_FIXTURE=1` behavior.

**Track B — complete website review:** all eight routes were inspected on the replacement build at desktop, mobile, and tablet widths. The narrow fixes provide working skip-link focus, comfortable service navigation targets, a branded missing-page recovery surface, and distinct accessible service-link names. The approved R19 design, founder-only homepage imagery, 16-person Team roster, Ari/Surya destinations, and existing Journal fixture were preserved.

## Verified execution and evidence

All execution occurred in the exact worktree. Counts overlap: focused Track A and Track B tests are subsets of the integrated suites, not additional independent totals.

| Check | Result | Evidence |
| --- | --- | --- |
| Track A author tests | 46/46 passed | `journal-contract.md`, `journal-contract-receipt.json` |
| Independent boundary review | PASS; independently 46/46 in 1.83s; 15 selected source/config hashes stable | `boundary-review.md`, `boundary-evidence.json`, `boundary-tests.log` |
| Existing Magazine HMAC tests | Independent reviewer observed 14/14 passed | `boundary-review.md` |
| Integrated Website tests | 56/56 tests, 12 files, exit 0 | `integrated-website-tests.json` and `.log` |
| Integrated architecture tests | 93/93 tests, 4 files, exit 0 | `integrated-architecture-tests.json` and `.log` |
| Shared production build | Exit 0; 2026-09-06 19:09:38–19:10:12 UTC | `integrated-build.json` and `.log` |
| Post-build TypeScript check | Exit 0; finished 2026-09-06 19:10:57.791 UTC | `integrated-typecheck.json` and `.log` |
| Receipt/log verification | Independent reader checked all four receipt hashes and actual test summaries | `final-evidence-verification.json` |
| Replacement preview | Single listener PID 10597, parent 10525, exact website cwd, Next 16.3.1, loopback 3100, explicit fixture | `integrated-preview.json`, `fixture-preview-startup.log` |
| Source stability after initial integration | Capture worker verified 101 selected source files unchanged before the later visual correction | `integrated-source-before.json`, `integrated-source-after.json` |
| Pre-correction route matrix | 24 views: 8 routes × 1440/390/768; all HTTP 200 + noindex; zero document overflow, decode failures, page/console errors; not proof of the subsequent CSS correction | `output/playwright/website-r19-full-site/final/metrics.json` |
| Focused browser checks | PASS: 7 skip targets/next-Tab checks, 4 missing-route recovery cases, 4 unique service labels, selected 360px menu, service targets, 16 section captures | `output/playwright/website-r19-full-site/final/focused-metrics.json` |
| Screenshot inventory | 73 PNGs independently inventoried with dimensions/SHA256 | `output/playwright/website-r19-full-site/final/screenshot-manifest.json` |
| Independent Claude review | **FAIL: homepage service CTA occluded by lifted tool cards at 1440px and 768px** | `claude-visual-review.md`, `claude-review-receipt.json`, `claude-tool-trace.json`, `claude-auth-route.json` |
| Final documentation verification | **PENDING** | Complete after independent verdict and final disk/hash checks |

Post-build typecheck log SHA256: `6d32a87cb757acf1234ccd5182eb619acdbf1a699d686ca8fd6eb971de79e98e`. Focused metrics SHA256: `595ba30801c83a675b10aa552ca851e7271882e35b32961060b01004c50ec4ad`. The final verification worker checked these receipts; this documentation author did not rerun tests/builds after the orchestration gate blocked its next shell action. Sanctioned delegation completed remaining reads and preview startup. No gate was bypassed.

## Track A: the proven local boundary

The [technical contract](journal-contract.md) records exact interfaces, files, tests, and limitations. The [independent review](boundary-review.md) closes two findings: HTTP proof ingress rejects unexpected GET body framing, and Website transport has an explicit `server-only` import with an installed-Next guard test.

- One read-only SQL statement obtains current edition/story heads, quarantine/publication state, published evidence links, eligible assets, and dated published/superseded revisions from the real Magazine schema. The deterministic SQLite fixture uses canonical migrations. Duplicate placements are deduplicated; missing authoritative records and invalid shapes fail closed. Historical edition pins do not revive older story content.
- The existing v2 field allowlist distinguishes ready, empty, withdrawn, unpublished, unavailable, and malformed. It excludes raw notes, internal root IDs, jobs, rights/source metadata, and exception strings. Dates come from authoritative fixture records, without generated fallbacks.
- Approval binds the exact public projection, including prose, canonical URL, evidence labels/URLs, dates, and media description. An origin allowlist alone does not authorize arbitrary source prose. Fixture approvals are deterministic and synthetic; this is not a general semantic PII detector.
- Requests reuse actual Magazine HMAC behavior and a bounded nonce store. Signed responses bind request nonce/path, status, MIME type, and body digest. Tests cover missing/invalid credentials, wrong audience/path, replay, current signed-body tampering, bounds, truncation, timeouts, malformed data, and failures without stale/demo fallback.
- Media lookup is scoped to current approved story/version/snapshot and canonical object key. It reuses actual stored-byte verification of size, safe MIME, metadata, and actual SHA256 bytes. After asynchronous storage access, authority rereads publication/rights state. Website mediation serves approved bytes from its own origin with no-store, same-origin CORP, and nosniff.
- The actual local HTTP response passes through the Website v2 decoder and existing Journal renderer. This is not a helper-only proof. The transport remains unwired from the preview loader.

Limits are explicit. A single statement is a coherent SQL read under the exercised SQLite contract, not proof of deployed D1/replica parity. The media recheck bounds tested races without creating a database/object-store transaction or universal withdrawal recall after delivery. Nonce storage is local-process proof infrastructure. Approved PNG bytes receive hash, signature, and IHDR/dimension checks, not a complete raster decode. The existing resolver regression uses an unused Photon encoder stub because that dependency is absent; it does not prove a full image-ingress pipeline. The installed Next guard is exercised directly, not through a separate full negative Client Component build.

Canonical access is bounded too: local simulation executes the existing Magazine page metadata/not-found contract against actual current-story repository reads. It does not exercise the full Next dispatcher, middleware, all read-model dependencies, or production host admission. Production canonical access remains unverified/unarmed. The technical contract lists deployment prerequisites: real authority approval governance, deployment-specific database consistency, auth/key/nonce storage, canonical admission, and supported media validation/delivery.

## Track B: route, layout, and interaction coverage

The [coverage matrix](coverage-matrix.md) names all eight routes, homepage sections, keyboard interactions, external surfaces, and selected stress cases. The [source inventory](source-inventory.md) and [UI change record](ui-batch.md) describe scope and narrow fixes.

Final matrix: Chromium 152.0.7977.82 at 1440×1000, 390×900, and 768×900. All 24 valid views returned 200 with noindex, zero document overflow, image decode failure, or page/console error. Preview readiness on `/` and `/journal` also verified private/no-store cache headers. The matrix retained 31 `net::ERR_ABORTED` request events; these are reported rather than called zero network failures. Including deliberate missing-route probes there are 34 aborted requests in total and two expected 404 console messages.

Focused checks cover all seven newly focusable content routes: Skip reaches MAIN, then Tab reaches an anchor. Both missing-route probes were exercised at desktop/mobile with Home/Services recovery; tablet screenshots are included too. Service cards have four unique accessible names. Two service header links measure 44px; the coordinating reviewer measured the contact action at 48px. This is not whole-site WCAG certification.

On the replacement build, the coordinating reviewer independently exercised Portal Documents → ArrowRight Applications → End Messages → Tab into panel; Journal Next 01/02 → 02/02 → ArrowLeft 01/02; menu Escape with collapsed state/focus returned to Menu; Team navigation and the 16-person roster; Ari's Second Home and Surya's E-VOA anchors at top 105px below a 72px header; amended fixture disclosure with revisions dated September 1 and 2. Selected 360px checks found no document overflow on homepage, Team, and Journal; the capture worker also exercised homepage/company-setup stress. This is selected coverage, not an invented eight-route fourth-width sweep.

The coordinating reviewer opened actual final homepage mobile viewport, mobile branded 404, desktop immigration, and desktop Team PNGs, finding no visible overlap/clipping/broken layout in those four images. The independent Claude review nevertheless found a real blocking desktop/tablet homepage overlap: lifted tool cards obscure “Explore all services →”. This is outside the four-image parent sample and was not detected by the automated overflow metrics. One mobile homepage Journal element screenshot separately contains a sticky-header capture artifact; reviewer input substitutes the complete homepage mobile screenshot. That capture artifact is distinct from the actual CTA defect. Original captures and limitations remain.

The earlier [browser baseline](browser-baseline.md) is from the older build. Its geometry, decoded images, prefetch traces, contrast samples, and pre-fix findings do not verify replacement code. Current receipts/captures above provide that evidence. Sampled solid-color contrasts do not certify all image/text combinations or focus/hover states.

## External surfaces and research boundaries

The [destination audit](destination-audit.md) records 15 public destinations returning 200 after redirects, plus seven coordinating-reviewer public first-screen inspections. These establish reachability/relevant identity at the observed time. My stops at authentication. No login, form submission, purchase, payment, message, eligibility outcome, account workflow, or production Magazine access was exercised. Tax calendar freshness, legal accuracy, ratings, addresses, historical claims, and legacy Team parity were not independently certified. WhatsApp/email/phone links were destination intents only; nothing was sent. Telegram was not probed after access was blocked.

Completed earlier Gemini research is reused for local contract decisions and limits; it is not a fresh review of final changed bytes. Independent boundary review is separate from Track A authorship. Restricted Claude review returned actual initialized model `claude-opus-5`, with `claude-haiku-4-5-20251001` auxiliary usage; the auxiliary activity is not asserted as a second independent review. Its 39 Read invocations covered 27 unique hash-stable inputs: 19 PNGs, two metrics files, and six source files. It read focused metrics, but only part of the main metrics and no tablet PNG; it ran no live browser or tests and did not approve production. Exit 0 means the reviewer executed successfully, not that the website passed. The first FAIL evidence remains immutable.

## Remaining acceptance steps

1. Correct the homepage CTA overlap, record the narrow source change, and obtain fresh affected-build/browser evidence and independent follow-up review. See `review-resolution.md` for the open blocker and separate minor observations.
2. Finalize this report, coverage matrix, new completion handoff, and history-preserving website state entry only after the real follow-up outcome.
3. Independently verify final documents and checkpoint receipts on disk; do not substitute successful write-tool output for verification.

Until these steps are evidenced, local acceptance remains failed/open. The measured checks above passed their named properties on the reviewed build; they do not cancel the visual blocker or verify a subsequent correction. Production stays unarmed regardless of the local result.
