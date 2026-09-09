# Website state — 2026-09-07

This is a dated handoff, not a substitute for live verification.

## Pro continuation — owner decision, 2026-09-07

Continue on Pro, not Air-M5. See
`apps/website/docs/handoffs/2026-09-07-pro-resume.md` and its companion loop prompt.
Target worktree: `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`.
Target branch: `codex/website-pro-continuation`.
The original M5 tree is retained as a checkpoint. Never edit both copies in
parallel without explicit coordination. Machine-global skill aliases and the
localhost preview do not migrate automatically.

Reuse the Magazine editorial engine; create the public presentation within R19.
The legacy review is `apps/website/docs/reviews/2026-09-07-magazine-legacy-review.md`.
Its live visual inspection was restricted by workspace authentication; source
review is not proof of the deployed engine revision or operational health.

## Historical M5 checkpoint (inactive)

- Worktree: `/Users/balizero/nuzantara/.worktrees/infra-website-r19`
- Branch: `agent/air-m5/infra/website-r19`
- Application: `apps/website` — standalone Next.js public website candidate.
- Local preview: `http://127.0.0.1:3100/` when the built preview is running.
- Mandate: develop in parallel with the live site, without touching main or prod.
- Starting committed handoff: `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d`.

## Completed Pro slice — current state

- Active worktree: /Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro.
- Branch: codex/website-pro-continuation; base b740b2cc3e94b1a46c9e9811bb369289fc21ea3d.
- / and /journal now consume the Magazine v2 projection per request.
- Explicit local sample mode: WEBSITE_EDITORIAL_FIXTURE=1 npm --prefix apps/website start.
  Without that switch the unarmed publisher shows unavailable, with no snapshot fallback.
- Three synthetic published stories exercise current revisions, evidence, missing
  media and the existing authority's quarantine rules. Fixture destinations are inert.
- Publication boundary decision and final evidence: apps/website/docs/reviews/2026-09-07-pro-slice/.
- Next-session instructions: apps/website/docs/handoffs/2026-09-07-pro-slice-complete.md.
- Preserve the entire inherited dirty overlay. No commits, push, merge or deployment.
- Gemini research is complete with qualified findings and observed browsing;
  read gemini-research.md and gemini-research-receipt.json in the final review
  directory. Runtime-selected gemini-3.1-pro-high is not backend attestation;
  observed web-only reads are not proof of sandbox enforcement.
- The research adds no local-fixture blocker. Browser media delivery, versioned
  read consistency and withdrawal freshness remain future production contracts.
- Exact final checkpoint: output/checkpoints/2026-09-07-pro-slice/ inside this
  worktree, already ignored by /output/. CHECKPOINT.json and VERIFIED.json bind
  the archive, manifest and extraction checks. RELOCATION.json records removal
  of the former external finished-slice copy; the original external R19 transfer
  package remains untouched. HEAD alone omits the essential overlay.
- Documentation closeout preserved product files and the last 55 website / 47
  architecture passes; no full suite rerun was needed. One owned preview remains;
  current HTTP/process observations are in the checkpoint's PREVIEW.json.

## Approved direction and inherited changes

- R19 visual direction is the design baseline; earlier numbered HTML prototypes
  are historical evidence, not the current source of truth.
- Public homepage, service pages, and Journal entry exist in the candidate.
  Production functionality must not be inferred from this standalone preview.
- This batch moves the existing roster to `/team`, leaving only two founders'
  portraits in the homepage band. Navigation and footer link to `/team`.
- Six previous app tasks completed and were archived to reduce resource use.
  Reuse their checked-in handoffs rather than reopening them automatically.
- Shared skill is `.agents/skills/website/SKILL.md`; machine aliases resolve
  here. Adapter and installation details live in `apps/website/docs/website-corner.md`.

## Prior evidence (superseded where the Pro slice says otherwise)

- Prior baseline: `apps/website/docs/qa/acceptance-matrix.md`.
- Current production comparison: `apps/website/docs/reviews/2026-09-07-production-transplant.md`.
- Current model review: `apps/website/docs/reviews/2026-09-07-panel/`.
- Completed batch verification and synthesis: `apps/website/docs/reviews/2026-09-07-website-report.md`.
- Owner clarification: migration must improve historical mistakes. Preserve useful
  outcomes/contracts; choose keep/fix/replace/retire per surface. Existing-app
  integration and separate marketing deployment remain candidates to compare.
- Previous UI batch verification: 47 tests, type check and build passed; homepage and Team
  checked at 360/390/768/1440px without horizontal overflow. Desktop founder band
  is 152px tall; `/team` has 16 people with existing roles, not invented biographies.
- Missing detailed biographies remain a content task requiring verified source
  material. Existing roles and owner-provided project responsibilities are used.
- Portal capabilities, pricing sources, and integration contracts must be
  verified before a production-facing promise or connection is added.
- Architecture continuation: Journal now receives records from the server page;
  the checked snapshot is still the homepage source. A proposed strict publishing
  decoder is exercised only by an isolated proof, not a live connection.
- Current verification: 55 website tests, type check and optimized build passed;
  5 additional architecture tests passed. Real MDX reader + unchanged article
  produced identical provider-free marketing HTML through direct and localhost
  HTTP delivery. Cache, full-corpus compatibility and deployment are unproven.
- The real reader included a synthetic draft and substituted an undated fixture's
  date. These passing characterization tests record defects, not approved behavior
  or evidence that production currently exposes a draft.
- New report: `apps/website/docs/reviews/2026-09-07-architecture-proof.md`.
  Reproduce with `npm run test:architecture`; details in `proofs/architecture/README.md`.
- Journal browser continuation: desktop 1440px/mobile 390px, carousel navigation,
  no horizontal overflow, decoded feature image, preview noindex retained, no
  browser console errors. Review browser closed; one local preview retained.
- No deployment approval or live migration has been requested.

## Verification commands

From `apps/website`, run `npm test -- --maxWorkers=1 --no-file-parallelism`,
`npm run typecheck`, and `npm run build`. Use `npm start` for the built preview
on port 3100. Identify the existing process before stopping/replacing it.

Inspect `/`, `/services`, each service route, `/journal`, and `/team`. Verify
founder-only homepage imagery, complete Team roster, working mobile navigation,
decoded images, no horizontal overflow, and preserved preview noindex headers.

## Loop 3 checkpoint — 2026-09-08, Pro

- Prepared in `codex/website-pro-continuation` under
  `.worktrees/infra-website-r19-pro`; no commit, push, merge or deployment.
- Archive discovery now reads the complete advertised public catalog. The observed
  815-record catalog includes `property/leasehold-vs-freehold` at index 751;
  search, combined category filters, pagination and browser Back passed.
- Literal checklist and decision data feed allowlisted client controls. Progress,
  reset, all three property outcomes, previous question, keyboard activation and
  heading focus passed. Contextual help appears once and carries the article URL
  and selected question into unsent contact drafts; canonical link copy passed.
- The five configured Hero and five Latest entries matched the browser order.
  Public chat and newsletter remain unavailable in this preview. Unreviewed
  calculator formulas are not executed; source illustrations are not new advice.
- Frozen checkpoint: build `nCcYRJBteyXklPYn97TcY`, PID 25875 / parent 25806,
  `next start` on port 3100. All 177 build inputs matched before tests and after
  build; aggregate `56894236f51f522908703829e4edb454afffd8944c5dd56f6996640e1ae13a91`.
  Unit suite: 126 passed, one intentionally gated corpus test skipped;
  architecture suite: 93 passed; typecheck and production build passed.
- Browser evidence includes true 390×844 and 1280×900 PNGs, no horizontal
  overflow and decision option targets at least 48 px. Source projection audits
  covered 815 public and 3,373 local articles; these do not prove universal
  interactive parity or later retained-route changes.
- Closure and receipts:
  `output/design/astra-restoration-loops/results/03/FINAL-HANDOFF.md`.
  Phase 4 resumed source edits after this build; its later source/runtime must
  have a separate checkpoint and must not inherit this acceptance automatically.


## 2026-09-09 — Interaction presentation checkpoint (Astra)

Local interactive presentation implemented in infra-website-r19-pro/apps/website; surrounding Journal and Services remain sibling-owned. Decision guide question/result hierarchy, editable answers, staged checklist and undo, native Journal search/filter composition, mobile comparison pairs, contextual contact identity and compact share/newsletter feedback are in place. Algorithms, authored facts, global tokens and outbound integrations preserved. Necessary shared underscore-slug and collision-safe heading-ID fixes carry tests.

Checkpoint XB89Fe_9yjoEFiPE-Cdge: unit257 PASS +1 optional corpus skip; architecture93 PASS; typecheck/build PASS. Full tests at preceding X6 checkpoint; XB89 adds only reader CSS with stable hash. Browser keyboard/back/reset/URL persistence and page-local checklist reload verified; clipboard pending/error used temporary local mocks, removed afterward. No sends, subscriptions, merge or deploy. Floating mobile launcher remains an existing movable overlap, with no unreachable controls observed.

Evidence: output/design/interaction-language/2026-09-09/visual-state-sheet.html (28 captures), functional-verification.md, implementation-notes.md and verification/checks-reader-final.json. Any subsequent Journal-only build has a separate receipt; interaction sources are frozen.


## 2026-09-09 — Services art direction checkpoint (Astra)

Local hub and four family pages now form an editorial dossier collection. Two rendered Immigration compositions were compared; the asymmetric opening/category index and wide reading layout was selected. Scoped styling distinguishes catalog, comparison, expanded scope, process, preparation and questions. Tax was the weakest first pass and was redesigned with accessible paper-on-slate copy and three actual category links.

All 103 service identities, 86 PricingTool identities and existing content remain; eight content/pricing files are byte-identical to the inherited baseline. Sixteen Services source files were frozen and verified without drift. Browser checkpoint XB89Fe_9yjoEFiPE-Cdge binds 24 matching desktop/mobile captures, complete expanded dossier, keyboard/focus/search/hash/comparison checks, and four stable pricing states (desktop314px/mobile405.578125px). One unmocked price request returned available; this does not validate all amounts.

Independent review PASS. Services tests23 PASS; shared website257 PASS +1 optional corpus skip and architecture93 PASS cover the frozen Services source; typecheck/build PASS. Later Journal-only rebuilds have separate receipts. No commit, push, merge or deployment.

Evidence: output/playwright/services-art-direction-2026-09-09/REVIEW.html, DESIGN-REVIEW.md, FINAL-REVIEW.md, browser-verification-final.json and build-verification.json. The longer mobile Immigration catalog is an explicit readability tradeoff, supported by category navigation and search.

## Journal art direction checkpoint — 2026-09-09, Pro

- Local Direction A Journal/reader presentation completed in codex/website-pro-continuation; no merge or deploy. Lead/secondary/archive hierarchy, aligned reader opening, 68ch body, grouped marginal contents and compact category continuation. Interaction slots and article content retained.
- Final preview build a29pTiZ_8M7i1uSnZkdX0, listener PID 2304 / npm 2171 on 3100. Final two-file presentation delta passed 26 focused tests, typecheck and optimized build; integrated logic checkpoint had 257 unit passes (one optional corpus audit skipped) and 93 architecture passes. Interaction/Services screenshots keep their own XB89 checkpoint; do not relabel older evidence.
- Actual desktop/mobile reader/Journal inspection and independent-role image review passed sampled acceptance. 14 before/after pairs have matching image dimensions; 24/8/64 sampled article headings and 3/0/3 tables retained. Search/category, pagination, native TOC and mobile table keyboard scroll passed.
- Remaining limits: inherited mobile floating launcher overlap, recovered excerpt truncation, unavailable preview integrations; no repeat of optional exhaustive corpus audit or production approval.
- Report: output/design/journal-art-direction-2026-09-09/REPORT.md. Handoff: apps/website/docs/handoffs/2026-09-09-journal-art-direction.md.


## Brand/company art direction checkpoint — 2026-09-09, Pro

- Local Home/company/trust presentation complete; approved sequence, recovered content, Direction A and authentic assets retained. Hero/Reviews/E-VOA/Studio/Portal now have distinct visual roles. About method, Team spacing, Contact office panel and slate footer refined. No invented product UI or testimonial.
- Build bNAoWKX0OXwoasgcUn0VU, listener 92846 / npm 92825 on 3100. 257 unit PASS + 1 optional corpus skip, 93 architecture PASS, typecheck/build PASS; 179 inputs stable through build/browser. Five Journal presentation hashes unchanged.
- Eight full-page desktop/mobile views and 20 details; 98 image instances decoded, no sampled document overflow/browser errors. 33 local route checks: 20 HTTP 200 and 13 expected retained-route 307 redirects. Keyboard navigation/contact context checked; no message sent.
- Evidence: output/design/brand-art-direction-2026-09-09/README.md and comparison.html. Handoff: apps/website/docs/handoffs/2026-09-09-brand-art-direction.md. Old baseline remains wEyYGnF8mUfl6kX22IXGB; sibling Journal recovery contributes to Home length changes.
- Limits: existing floating launcher overlap, external account/destination operation unverified, optional corpus audit skipped, two unrendered Portal studies set aside under explicit owner resumption. No commit, push, merge, arm or deploy.


## Native Visa Oracle decision atlas — 2026-09-09, Pro

- Local native `/visa-oracle` implemented with canonical current V2 branching, editable semantic route, typed controls, explanations, EN/ID, review, opt-in resume and all five outcome dossiers. Ancestor edits prune stale facts/results; admissible clarification appends separately and repeated unresolved requests stop for review. Two rendered compositions compared; outward desktop fork A selected, vertical mobile branches retained.
- Source pin `889935da4d8e7ce5a1537e55b9e5cc40c11dd590`; 85 source files verified, 14 canonical core modules identical, 54 exact imports / 31 adaptations. No stale worktree Mouth/backend transplant. Local relative aliases `/visa-v2` and bare `/visa`; separate legacy tools unchanged. Exact same-origin evaluate boundary, explicit backend origin, no production fallback.
- Final optimized build `SOB3JEOI_FViIKY0ypsfv`, preview PID 42991 on 127.0.0.1:3100, synthetic engine driver PID 84812 on 127.0.0.1:3191. 958 unit PASS + 1 optional corpus skip; 93 architecture PASS; final alias-only 27 focused PASS; final typecheck/build PASS. 399 post-build frozen inputs unchanged after browser checks, SHA256 `a49125d4f434a6d94b154d8aec63bf057eb38456a404aecf1f5f4484b822cf7b`.
- Independent registry 15/15 PASS, 14 actual sealed local evaluations, 201 questions: all 11 intents, original onshore conflict blocked without submission, explicitly declared coherent onshore runtime copy, two age-64 retirement probes. Desktop/mobile ancestor re-evaluation and fixture outcomes/follow-up/errors/resume pass. Route smoke 24/24; Home/Immigration coherence 4/4; AX/keyboard/source parity/restart spot PASS. Minimum main choice 98px, no sampled horizontal overflow, contrast minimum 4.883:1.
- Code and visual review PASS in their documented scopes. Preview uses canonical offline signed-clock evaluation/public adapters and a public local test seal, not production authentication/activation/pricing/persistence. WhatsApp remains honestly unconfigured; no browser consent check/revoke or outbound handoff claimed. Mobile dossier length and old mobile loading-only baseline remain explicit limits.
- Initial reviewer endpoint-test selection invoked local `nuzantara_test` reconstruction outside intended read-only scope; stopped, disclosed, excluded and not retried/repaired. Subsequent pure backend checks and local driver are DB-free; no production DB operation.
- Handoff: `apps/website/docs/handoffs/2026-09-09-visa-oracle.md`. Full receipts and gallery: `output/design/astra-restoration-loops/results/05/FINAL-HANDOFF.md` and `REVIEW.html`. Prior website checkpoints keep their original evidence identity. No commit, push, merge, arm, deploy, production configuration change, pack activation or external message.


## Visa Oracle themes follow-up — 2026-09-09, Pro

- Fixed mixed system-dark foreground/paper-background cascade; restored visible local Day/Night toggle with stored preference and current-state icons. Theme changes preserve answers; canonical engine/rulepack/transport unchanged. Native input/select/placeholder, dossier, focus, disabled, outer canvas and print palettes covered.
- Final build `g5aUEF3MkJrmNOwgvWX8d`, preview PID61000 on3100, existing synthetic driver PID84812 on3191. 399 frozen inputs unchanged after browser verification, aggregate SHA256 `65cfa7f59e89f893d8070222296b626a62d93d2bf6eb8bb0ea9ceddbd5cd02e9`; seven source/test files changed from original LOOP05.
- 961 unit PASS + 1 optional corpus skip; 43 focused theme/shell PASS; 93 architecture PASS; final typecheck/build PASS. 36 parent final screenshots and independent14/14 browser contexts PASS; native night text12.529:1, minimum placeholder6.081:1. Original acceptance was light-only; this follow-up covers the missing system-dark/native-control cases.
- Evidence: `output/design/astra-restoration-loops/results/05/theme-fix/README.md`, `REVIEW.html`, and `review/acceptance.md`. Handoff: `apps/website/docs/handoffs/2026-09-09-visa-oracle-themes.md`. Previous checkpoint evidence retained under its own build. Local only; no commit/push/merge/arm/deploy or external send.


## Visa Oracle D12 Business discovery — 2026-09-09, Pro

- D12 now appears in successful Business results as an additional pre-investment catalog option, without an extra question. EN/ID scope and unassessed eligibility wording; no rank, support badge or price. Engine candidates, counts, sharing, facts and canonical rules unchanged; deduplication and non-supported-state exclusions covered.
- Build `_v9jQKvOYRqymyBzWavtt`, preview PID4000 on3100; unchanged synthetic driver restored as PID95059 on3191 with ephemeral process-only test config. Three source/test hashes remain stable after browser verification.
- Focused46 PASS, website973 PASS +1 optional skip, final typecheck/build PASS. Full suite preceded two test-fixture typing fixes; final focused/typecheck/build validate those. Independent source review PASS. Actual synthetic Business evaluation returned D1/D2 and one D12 catalog card. Desktop Day/Night and mobile EN/ID sampled with no overflow/browser errors.
- Handoff: `apps/website/docs/handoffs/2026-09-09-visa-oracle-d12-business.md`. Receipt/logs: `output/design/astra-restoration-loops/results/05/d12-business/`. This is discovery visibility, not canonical eligibility widening. Local only; no commit/push/merge/arm/deploy, production change or external send.


## ASTRA Loop06 — final local Oracle verification, 2026-09-09

This dated addendum supersedes the earlier D12 discovery-only conclusion for the Loop06 proposal lane. Historical Loop05 runtime/test statements above retain their own build identities.

- Explicit Business pre-investment activity now reaches evaluated D12. Ordinary meetings remain under review for the canonical D1/D2 activity gap. The distinct unsigned proposal adds two compensation hard filters for D12/C2; unknown compensation remains input, and other investment alternatives may still require facts. No frontend candidate insertion or reranking.
- All 11 registered families / 53 questions examined. Fixed defects include retirement income/sponsor collection, work/remote distinctions, Family/Diaspora direction containment, permit collector metadata, admissible clarification, dossier evidence layers and false duration copy. See the matrix and exact changed paths in the final handoff.
- Final retained build: GlvUmjZjvy3JFaUtfb39_, .next-oracle06; 420-input source SHA256 826461092c8803fd8e77c43a8113fcd80a3f3617739eba0b1c2a79bca2ee14fb. Proposal UUID db0574ee-af99-5f82-90b2-cfa6098d44c2, payload 339f0f331c9361d422a86f6ac478dd67a85d9a3df710e48413711a066989d4f4, local unreserved seq21, unsigned/DB-free/test-sealed.
- Final website: 1,320 tests passed + 1 optional skip; adapter 55, architecture 93, isolated typecheck/build passed; 41/41 HTTP checks. Backend 79 DB-free tests / 15 witnesses. Census 84 paired profiles / 168 responses / 84 expected comparisons passed. Final browser 18 complete transactions with exact proposal identity, including all 11 coherent family completions. These denominators are separate and not exhaustive legal coverage.
- Three actual independent Claude Fable CLI reviews; final scoped correction has no blocker. Independent rendered review passed four final JPEGs. Eight accepted screen captures in gallery.html. Print-media DOM hides the open assistant/launcher, but a screen raster disagreed and printToPDF was unavailable: actual PDF/backdrop appearance remains unverified.
- Canonical dependencies remain: D1/D2 activity vocabulary, Family CHILD/PARENT normalization, broader Tourism compensation/activity rules and passport-validity facts. This addendum does not certify production readiness.
- Owned 3106/PID22012 and 3193/PID92447 were identity-checked and stopped. Protected 3100/PID4000, 3191/PID95059 and parent Home 3104/PID86559 were preserved at teardown. Parent later Home source changes are separate; 91 Oracle files matched the freeze. All temporary review tabs closed, viewport reset.

Final handoff: output/design/astra-restoration-loops/results/06/FINAL-HANDOFF.md. Evidence: VERIFICATION.md, CASES.json, gallery.html, final-artifact-manifest.json and runtime-teardown.json in that directory. Backend proposal is in /Users/nuzantara/nuzantara/.worktrees/backend-rag-astra-loop06-d12-proposal. For a local continuation, coordinate ownership and use the exact retained-build restart instructions linked by the handoff. No commit, push, PR, merge, arm, deploy, signing/activation, production configuration, database operation or external submission occurred.
