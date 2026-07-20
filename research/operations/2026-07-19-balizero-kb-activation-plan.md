---
date: 2026-07-19
domain: operations
project: Bali Zero KB activation (Lane A of the twin mandate)
status: ACTIVE — working ledger, update as levers land
adversarial_review: codex
client_case: none
sources:
  - 2026-07-19 full KB audit (4-reader sweep, session 932b2e53)
  - research/operations/2026-07-19-nuzantara-co-id-avvocato-totale-charter-v0.md (Lane B sibling)
---

# Bali Zero KB — Activation Plan (post-audit, 2026-07-19)

> Mandate (Zero, 2026-07-19): *"iniziamo l'attivazione e potenziamento di quello che
> manca a Bali Zero"* — twin of the NUZANTARA charter. This file is the operative
> ledger for Lane A: every disarmed/degraded lever found by the audit, with owner,
> gate, and verified state. **Rule of the lane: arm what exists before building
> anything new** (the audit's meta-pattern was Esiste≠Armato applied to knowledge).

## Levers, by leverage order

| # | Lever | Verified state (2026-07-19) | Action | Owner | Gate/risk |
|---|---|---|---|---|---|
| 1 | **Hybrid search ON in prod** | `enable_hybrid_search=False` default (`config.py:346-350`); collections carry BM25 sparse vectors since migration 031b; no fly.toml override | Flip via env on Fly + A/B smoke on golden queries (visa/kbli/tax) before+after; watch p95 latency. **Abstain-recalibration gate (adversarial F4): hybrid fusion changes the score distribution the 5 named abstain gates were calibrated on — before the flip goes live, run the golden abstain matrix (`test_abstain_policy_hardening.py`) PLUS a low-evidence query set that MUST remain abstained, before/after; any formerly-abstained answer that now passes = BLOCKER, re-derive thresholds with the panel rule** | session lane | Low risk on latency, NOT on abstain semantics (see gate). Verify per-collection sparse-vector presence FIRST — 031b covered tax_genius, pricing, training, visa_oracle, legal_unified; NOT necessarily kbli/news/curated_qa |
| 2 | **Reranker in prod** | Code-complete, `enable_reranker=False` ("Saves ~5GB Docker image"); `visa_oracle.py:918` says "cross-encoder not available on Fly"; nuzantara-rag = shared-2x/2GB RAM | NOT a blind flip. Spike doc comparing: (a) torch-free ONNX cross-encoder in rag process, (b) zerank2/ZeroEntropy external API, (c) stay off. Measure answer-quality delta on gold sets. Same abstain-recalibration gate as lever #1 (F4). **PDP egress gate (adversarial K4): option (b) sends raw query+chunk text to a third party — queries/chunks can carry client PII, so (b) is admissible ONLY behind an explicit redaction gate + DPA review; "already wired" is plumbing, not compliance. Default preference: (a) local ONNX or (c) stay off** | session lane (spike) | Image size + RAM ceiling on 2GB machine; external API = new cost → needs Zero if paid, AND PDP gate (K4) regardless of cost |
| 3 | **Migration 250 applied to prod** | Re-verified live this morning via `scripts/pg.sh`: tracker tops at `248_clients_npwp_strongid` (03:00 UTC). PR #2804 merged, file on main | Belongs to **lane S3 (visa-engine session)** — do not touch from other lanes (quad-session anti-collision). If still unapplied at next reconciliation, raise with Zero | lane S3 | Migration class = operator-adjacent gates; DB-state probe after apply per modus SHIP |
| 4 | **Visa rule-pack CONTENT + activation writer** | Substrate shipped (250), key ceremony done 2026-07-19 (session memory; visaoracle skill not yet updated), but zero production rule content, no writer (deferred "STEP 6") | Lane S3 roadmap: author first real rule-packs (114-code catalog → declarative rules), build activation writer | lane S3 | The engine stays ornamental until cargo loads (charter principle #1) |
| 5 | **`/api/drive/*` regression fix** | ~~ALL 3 endpoints broken~~ — corrected 2026-07-20: 2 distinct bugs, not 3 symptoms of 1. `FileItem` Pydantic model requires `type`, manager returned raw payloads (500 files / 500 search) — FIXED, PR #2816 merged 2026-07-19. `/api/drive/stats` (404) is unrelated: the route never existed at all — FIXED, PR #2898; follow-up wall-clock fix PR #2900 after a real-prod-data perf finding. **DONE — PROVE-LIVE confirmed 2026-07-20** (see narrative below) | DONE (#2816, #2898, #2900) | this session | Closed. 1 pre-existing out-of-scope finding flagged, not fixed (SYSTEM OAuth token dead → SA fallback, zero quota) |
| 6 | **Peraturan feeder (Sheet→PDF→NB-6)** | Dead 5+ weeks: every run fails on missing `GOOGLE_SERVICE_ACCOUNT_JSON` (log last entry 2026-06-16) | Operator provides/rotates the credential; then session re-arms + proves one green run end-to-end | operator[credential] → session | Without it NB-6 compliance ground truth stales |
| 7 | **Regulatory-watcher cadence** | ~~33 deltas over 64 days ≈ 52% day-coverage~~ — superseded 2026-07-20: live run found a NEW failure mode (false-clean, not a coverage gap) — ollama tier emitted a schema-valid `{partial:true}` stub the old check couldn't distinguish from a real scan | **DONE (#2877)**: `ensure_full_delta()` rejects+cascades partial stubs past tiers 1-3; tier 4 marks DEGRADED via heartbeat instead of logging as clean. Home-fork synced | this session | Closed. Day-coverage metric to proprioception NOT added — narrower fix shipped for the live-found bug, not the original coverage-gap framing (predates W81/W84 hardening, not reproduced live) |
| 8 | **KBLI schema drift vs CLAUDE.md §9** | Live table `kbli_documents`: `sektor_id`/`pma_status` NESTED in `metadata` jsonb on all 1,563 rows; `kategori_risiko` absent everywhere; `skala_usaha`→`per_skala`. CLAUDE.md §9 says flat/never-nested | Reconcile WITH the kbli-navigator lane: either the invariant doc is stale (likely — table carries newer keys like `kode_kbli_2025`, `pp28_sources`) or the table regressed. Update whichever is wrong; add tripwire test | kbli lane + session | CLAUDE.md §9 is marked NEVER VIOLATE — the contradiction itself is the bug |
| 9 | **NAGA claim ledger** | 3,119 claims / 6,980 evidence rows, stale since 2026-05-07 | Zero decides: revive as the claim-verification organ (charter L3 wants it alive) or archive formally. No zombie middle state | operator[business] | — |
| 10 | **NB hygiene** | 96 NBs / 5,643 sources; 24 empty shells, 11 never-populated "Research" shells, 6 self-marked deprecated (MERGED/ARCHIVED 2026-05-07) still live | Propose deletion/merge list to Zero (NB deletion = confirm-gated); populate-or-delete ruling for the 11 shells | session proposes, Zero confirms | notebook_delete is destructive → explicit confirm |
| 11 | **MCP observability lies** | ~~`get_collection_stats` + `get_qdrant_metrics` return the same zeroed op-counter... MCP caller has RBAC role `unknown` → all content tools 403~~ — corrected 2026-07-20 (re-grounded from scratch, not trusted from the audit): `get_collection_stats` repointed at `/health/collections` (real per-collection walk) — **FIXED, #2877**, PROVE-LIVE 2026-07-20 via direct `curl https://nuzantara-rag.fly.dev/health/collections` (no auth gate on `/health/*`): 15 collections, 121,252 total documents, real `live_points`/`status`/`vector_size`/`distance`/`segments_count` per collection. `get_qdrant_metrics`'s own docstring was NEVER mismatched with its behavior (promises op-counters, delivers op-counters) — not actually a bug, just less interesting data on a fresh process; left as-is. "All content tools 403" was FALSE — AST census found 41/131 tools RBAC-gated in `nuzantara-mcp` (2/6 content tools), ZERO in `nuzantara-mcp-advanced` (where `get_collection_stats` lives) | **DONE (#2877)** for the real half; RBAC `unknown`-role half correctly left as `operator[business]` — see `§Solo-operatore` note below, not a bug (deliberate fail-closed default, no scoped role exists to grant) | this session | Closed except the flagged operator decision. **Session-local note**: this session's own long-lived local `nuzantara-mcp-advanced` MCP process still returns the pre-fix op-counter shape (loaded the old code before #2877 merged, doesn't hot-reload) — verified via direct endpoint call instead; a session/MCP-connection restart would pick up the fix, not a code issue |
| 12 | **Orphan corpora** | `apps/kb/data/immigration/` 84 raw txt (unreferenced anywhere); `apps/kbli-navigator/data/` second KBLI dataset copy, sync unverified; `backend/kb/raw/top5_wave3/` empty stubs | Archive or re-wire the 84 txt; add sync check (or single-source) for kbli-navigator data; delete stub scaffold | session lane | Low; reduces fragmentation (audit found ≥6 uncoordinated KB locations) |
| 13 | **Tier1 legal PDFs → automated re-ingestion** | 517MB verified on disk (`data/kb_sources/`), wired to `ingest_tier1_gaps.py`/`ingest_2026_laws.py` but MANUAL invocation only; Qdrant freshness unconfirmed | Run a verified re-ingestion pass (dry-run → apply), then decide cadence (event-driven on new PDFs, not blind cron). **Embedding-invariant gate (adversarial F5): the pass MUST pin `text-embedding-3-small`/1536 dims explicitly, keep chunking config byte-identical to the collections' existing strategy, and use deterministic point IDs (idempotent re-runs, no silent duplicates). Proof = point-count delta AND per-vector spot-check (named-vector config + dims + a sampled cosine sanity on unchanged docs) — count alone cannot detect mixed embeddings (frozen-invariant breach)** | session lane | Needs Qdrant write path + before/after proof per the F5 gate (Legge 7) |

## Done this session

- Audit itself (4 readers + final-gate spot checks) — findings in memory
  `AUDIT KB COMPLETO 2026-07-19`, report delivered in session.
- Live re-verification of migration-250 non-application (pg.sh, tracker at 248).
- Prod health disambiguation: `zantara.balizero.com/health` = 200 healthy; the
  "critical/search unavailable" seen via MCP is the local MCP api-process path,
  not prod (fly-split-brain class, no P0).
- **Lever #5 (2026-07-20, re-grounded and closed out — the original "started by
  this session" note from 2026-07-19 went stale with no PR ever recorded):**
  re-verified from scratch rather than trusted from the ledger's own prior
  claim. Turned out to be 2 unrelated bugs conflated into one row: (a) 500s
  on `/files`/`/search` — already fixed and merged same-day via PR #2816
  (`FileItem` needed `type`, manager returned raw un-normalized payloads);
  (b) 404 on `/stats` — a route that had **never existed**, despite the
  `get_drive_storage_stats` MCP tool calling it since creation (silently
  swallowed by `error_monitoring.py`'s blanket `/api/drive/` 404 suppression
  — zero alerts, ever). Implemented the missing route in PR #2898 (auto-merge
  armed): exact total storage via `about.get`, files/folders/storage-by-type/
  largest-files via a capped, honestly-truncation-flagged `files.list` walk.
  Adversarial-reviewed by Kimi K3 (Codex CLI quota-dead until Aug 19th, GLM
  Keychain unreachable headless) — 2 findings, both checked against the real
  code rather than taken at face value: a "missing shared-drive scoping
  params" flag turned out to match every sibling method in the file (not a
  gap this diff introduced); a "Google-native-doc size crash" flag turned out
  to be already-handled by the existing normalizer (added a pinning test
  anyway since the path was genuinely untested). Not marked DONE above until
  PROVE-LIVE per standing rule #1. Confirmed-safe leftover branch
  `fix/team-drive-fileitem-type` (content-identical to #2816's squash-merge,
  W88-verified via blob diff) deleted as part of this cleanup.
  **PROVE-LIVE attempt on #2898 surfaced 2 real, distinct production findings**
  (via `fly ssh console` running the real service-layer code directly, once
  with `db_pool=None` — isolated a real perf bug but broke OAuth lookup as a
  side effect — then again with a correctly-wired `asyncpg` pool to rule that
  confound out): (1) the walk's only cap was `max_pages` (a page COUNT), which
  doesn't bound wall-clock latency — against the real Team Drive it took
  **45.5s for 20 pages, still truncated**, causing 2 real 30s MCP client
  timeouts; (2) the "system" OAuth token this endpoint depends on is
  genuinely dead in prod (fails to refresh even with a correctly-wired DB
  pool), forcing a Service-Account fallback whose own storage quota is
  genuinely ~0 — pre-existing, affects the whole `team_drive.py` router
  (shared `user_email="system"` auth path), NOT introduced by this diff.
  **Fix shipped in follow-up PR #2900** (auto-merged 2026-07-20T11:10:26Z,
  merge commit `ba7531cd4c`, verified on `origin/main` by content per W88):
  added a `max_seconds=10.0` wall-clock deadline alongside `max_pages` (walk
  truncates honestly on whichever hits first) — the actual root cause of the
  timeout, not just a smaller page-count guess; and a `quota_measured_as`
  field (from `about.get`'s `user.emailAddress`) so a `storage_used_bytes: 0`
  is never silently mistaken for the real account's usage. Cross-family
  adversarial review (Kimi K3 — Codex MCP/CLI and GLM all confirmed dead this
  session) caught a real bug in the diff's OWN test: the wall-clock
  "innocence" test used a single page with no `nextPageToken`, so the loop
  broke via `if not page_token` *before* the deadline check was ever reached
  — vacuous, would have passed even with the condition replaced by `or True`.
  Verified independently (re-read the real break-before-check ordering, then
  mutation-tested: forced the condition to `or True`, confirmed the original
  test passed silently and the fixed 2-page version correctly failed, then
  reverted the mutation cleanly). Fixed + full suite re-verified twice
  (19,270 passed both times) before/after the review fix.
  **PROVE-LIVE (2026-07-20, real `mcp__nuzantara-mcp__get_drive_storage_stats()`
  call post-deploy):** fast response, no timeout — `scanned_pages: 5,
  truncated: true` (deadline tripped well before the `max_pages=20` cap,
  exactly as designed), real `files_count`/`folders_count`/`storage_by_type`
  data returned. `quota_measured_as` confirmed the predicted Service-Account
  fallback identity, not a `@balizero.com` address — the SYSTEM OAuth finding
  is real and still live. **Deliberately NOT fixed here** (out of proportional
  scope for a "the route was 404" hotfix, pre-existing, affects a shared auth
  path other endpoints already silently depend on) — flagged instead: the
  SYSTEM OAuth token needs operator re-auth via
  `https://kita.balizero.com/settings/integrations` (documented flow, CLAUDE.md
  §Drive OAuth lifecycle) to restore the real 30TB account's quota reporting.
  `largest_files` in the live response contains real client document
  filenames (PII) — verified the fix works from the response shape/counts
  only, per the standing PII-output boundary (SYMBIOSIS Law 2); no filenames
  transcribed anywhere in this ledger, memory, or any commit.
- **Lever #12 re-grounded + partially DONE** (2026-07-20, fresh re-verification —
  the original row's claims were checked again on disk, not trusted from memory):
  - `apps/kb/data/immigration/`: **87** raw txt (audit said 84 — corrected), zero
    code/cron/CI references confirmed by repo-wide grep. NOT archived this
    session: two visaoracle-v2 research docs (`research/visa/2026-07-17-*`)
    still list it on their own "to examine" pile — moving it now would collide
    with that lane's pending work (scar family #5, standing rule #2). Deferred
    until that lane confirms done with it.
  - `backend/kb/raw/top5_wave3/`: confirmed genuinely dead (one-off 2026-04-22
    KG rerun, zero live references) — **DELETED**, see commit in this PR.
  - `apps/kbli-navigator/data/`: the row's own framing ("second copy, sync
    unverified") is **stale and wrong** — it's a live, CI-gated
    (`check-kbli-dataset-sync.yml`), prod-feeding
    (`scripts/sync_kbli_dataset.sh` → knowledge.balizero.com) consumer copy,
    NOT an orphan. **New finding, more urgent than the lever it was filed
    under**: `scripts/sync_kbli_dataset.sh --check` fails live on `origin/main`
    right now — 12,663-byte drift between the navigator copy and the canonical
    `source_documents/KBLI_2025_FINAL_CLEAN.json` — despite PR #2821 (merged
    2026-07-19, same day as the audit) claiming to cure exactly this class of
    drift. Tracked and handled as its own item, not as an "archive an orphan"
    task — see below.
  - **Update (2026-07-20, later same day):** the 12,663-byte drift above is
    fixed — root-caused by a dedicated forensics pass to PR #2821 committing a
    locally-generated navigator snapshot the same day canonical moved under
    it (one-time authoring gap, not a recurring compiler bug — all 5
    `kbli_filiera` cure compilers already call `sync_kbli_dataset.sh`
    unconditionally). Fix: `scripts/sync_kbli_dataset.sh` real-apply, scoped
    to exactly the 57 drifted codes (zero added/removed, record count
    unchanged), shipped as PR #2884 with auto-merge armed.
  - **Lever #12 DONE (2026-07-20, PR #2884 merged `3ef826be28`).** Evidence:
    (a) all 5 declared consumers confirmed byte-identical to canonical on
    `origin/main` via `scripts/sync_kbli_dataset.sh --check` (exit 0); (b)
    interesting content-provenance note — the squash-merge diff for #2884
    landed EMPTY (verified: `git diff 3ef826be28~1 3ef826be28` touches
    zero bytes) because PR #2878 (Batch A Lot 7 data-plane apply, merged
    in between) ran its own cure-compiler's unconditional `sync_kbli_dataset.sh`
    call and independently re-applied the identical fix first — a live,
    unplanned confirmation of this item's own root-cause claim that the
    self-healing property already holds going forward, caught by re-verifying
    content instead of trusting the "MERGED" label as a proxy (scar family #9,
    W88 discipline: verify state by content, never by SHA/label alone); (c)
    required CI on #2884 included a real `Frontend Tests (Next.js)` build of
    apps/kbli-navigator against the corrected data — passed; (d)
    reachability: `curl -I https://knowledge.balizero.com/kbli/19206` →
    `307` to `kita.balizero.com/login?redirect=.../kbli/19206` — per this
    project's own post-deploy QA convention (CLAUDE.md §11, "wait curl
    200/307") that is the documented-sufficient liveness signal for an
    SSO-gated surface, and the redirect correctly preserves the specific
    deep path, confirming the route resolves before hitting auth middleware.
    **NOT verified: actual rendered content behind the login wall** — this
    app has no public API and no headless-authenticated browser tool was
    available in this session; kita.balizero.com SSO login is a genuine
    operator-only credential (interactive login), not something bypassed.
    If a visual spot-check is wanted, it needs an interactive session with
    an authenticated browser (`mcp__claude-in-chrome__*` per CLAUDE.md §11).
- **Lever #7 DONE** (2026-07-20): root cause found by reading the actual log
  (not guessed) — a live run showed Claude+agy+Codex all missing in the same
  cascade, and ollama qwen3.5 (no web access) emitted a schema-valid
  `{new_today_count:0, partial:true}` stub instead of a real scan; the old
  `ensure_delta()` schema check (right KEYS present) could not distinguish
  that from a genuine clean day. Fixed: `ensure_full_delta()` rejects+cascades
  a partial stub past tiers 1-3; tier 4 (last resort) accepts it but marks the
  run DEGRADED via the existing `organism_hb_set` heartbeat channel instead of
  logging it identically to a clean run. Home-fork pair synced + verified via
  `scripts/lint_home_fork.py --check`. The audit's original "52% day-coverage"
  gaps (05-31→06-10, 06-18→06-28) predate this wrapper's W81/W84 hardening
  (dated 2026-07-05/06) and are not reproduced live — the NEW live failure mode
  found today (false-clean, not a visible gap) is the one this fix closes.
- **Lever #11 PARTIALLY DONE** (2026-07-20): `get_collection_stats` now calls
  `/health/collections` (extended with `status`/`vector_size`/`distance`/
  `segments_count`) instead of the op-counter endpoint `get_qdrant_metrics`
  also used — fixes the "returns the same zeroed op-counter" half. The RBAC
  `unknown`-role half is NOT a bug: `apps/nuzantara-mcp/nuzantara_mcp/auth.py`'s
  fail-closed default for direct/bypass callers (any interactive Claude Code
  session via the tracked `.mcp.json`, which sets no `AGENT_ROLE`) is deliberate
  per that module's own docstring, and `roles.yaml` has no non-admin role
  covering these tools today — inventing one or granting `admin` to interactive
  sessions is a privilege-boundary call, left open below for Zero rather than
  decided unilaterally under the K7 cure's own "identity resolution FIRST"
  principle (identifying the right principal/role is the missing step, not
  mine to skip by picking one).

## Standing rules for this ledger

1. A lever is DONE only at PROVE-LIVE (output observed, not exit code).
2. Levers owned by other live lanes (S3 visa) are tracked here but never executed
   from this lane — reconcile at boundaries, don't collide (scar family #5).
3. New levers discovered while working land HERE first, then get an owner.

## §Solo-operatore — open from lever #11 (2026-07-20)

`apps/nuzantara-mcp`'s per-tool RBAC (`auth.py`) fails closed to `unknown` for
any caller with no `AGENT_ROLE` env var — this is every interactive Claude Code
session on the tracked `.mcp.json` (which sets `PYTHONPATH`/`LANGSMITH_*` but
no `AGENT_ROLE`). `roles.yaml` today has 4 roles (`visa_specialist`,
`tax_consultant`, `company_setup`, `admin`); none cover `get_collection_stats`/
`get_qdrant_metrics`, and `admin` is a `*` wildcard — granting it to every
interactive session would be broad, not least-privilege. Zero's call: (a) add
a new scoped role (e.g. read-only observability) to `roles.yaml` + wire
`AGENT_ROLE` for interactive sessions in `.mcp.json`, or (b) leave `unknown`
fail-closed as designed and accept that self-inspection tools stay 403 from
direct sessions (route through the team-agent wrapper instead, which already
sets a role). Not decided here — it changes who can see what across an MCP
server multiple tools share.

## Adversarial review

**Seats (cross-family):** Codex `gpt-5.6-sol` (REJECT pre-cure) + Kimi `K3`
(SHIP-WITH-FIXES), run 2026-07-20 together with the sibling charter — full finding
table and dispositions live in the charter's `## Adversarial review` section
(single source, same PR). Findings that landed IN THIS FILE, cured in-place:

- **F4 [P0]** levers #1/#2 — hybrid/reranker flips change score distributions:
  added the abstain-recalibration gate (golden abstain matrix + must-stay-abstained
  low-evidence set, before/after; regression = BLOCKER).
- **K4 [P1]** lever #2(b) — external reranker API egresses query+chunk text:
  added the PDP/redaction gate; local ONNX preferred by default.
- **F5 [P0]** lever #13 — re-ingestion could breach the frozen-embedding invariant:
  added the embedding-invariant gate (pin model/dims, identical chunking,
  deterministic IDs, per-vector spot-check — count alone proves nothing).
- **K7 [P2]** lever #11 — never grant a role to an RBAC-`unknown` principal:
  identity resolution first, grant only to an identified principal.
