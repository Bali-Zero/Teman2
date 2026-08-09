---
date: 2026-08-10
domain: operations
topic: system-wide work-queue acceleration — round 3 of the pr-queue-acceleration series
adversarial_review: "cross-family, 2 seats — Codex gpt-5.6-terra (read-only sandbox, verified files live) + GLM claude-glm (agentic file reads); both verdicts folded in below; convergent first-move: L3 measurement-only"
sources:
  - research/operations/2026-07-19-pr-queue-acceleration-research.md (round 1)
  - research/operations/2026-07-19-pr-queue-acceleration-round2-zero-cost.md (round 2)
  - research/operations/2026-07-26-ci-pr-latency-the-excursus-is-cheap-the-slots-are-not.md
  - research/operations/2026-07-17-backend-suite-sharding-investigation.md (verdict only)
  - live probes 2026-08-09/10 (gh api, workflow files, spool/DLQ on Pro, Vercel API)
method: 8-agent workflow (prior-art reader, 4 measurement lanes, synthesis, 2 cross-family refuters), generator≠grader
---

# Queue acceleration — round 3 (system-wide, 2026-08-10)

**One sentence**: the backlog problem of July dissolved (12 open PRs, 47/day merged); the cost
moved into STRUCTURE — the two heavy workflows (~40 slot-min each) run ~3.6×/PR across
`pull_request` + `merge_group` + `push`, ≈ **97k slot-min/wk ≈ 48% of total CI capacity** — and
into three smaller queues (pre-push lock, P0 lane, Vercel) each with its own currency.

## 0. State changes that invalidate prior-art framing

1. **Round-3's "merge queue structurally unavailable (owner.type=User)" is MOOT** — the repo
   moved to org `Bali-Zero` and the queue is LIVE since 2026-07-27 (ruleset 19779175,
   `merge_group` events, `gh-readonly-queue/*` refs). The whole triplication class post-dates
   every prior rejection.
2. **Round-1's backlog-hygiene family lost its patient** (Steward, TTL auto-close, admission
   broker): open PRs 26-36 → 12; merges 28.6 → 47.3/day. Re-open only if open-PRs re-cross
   ~25 for a week.
3. **Backend Tests grew +39% in 3 weeks** (18 → 25.1 min median). The growth, not xdist, is
   the backend lever.
4. Already in flight elsewhere (do not duplicate): change-map shadow (#3919, another lane);
   Vercel should-build origin-fix + concurrency (this session, 2026-08-10); grouped
   Dependabot + Require-PR toggles (owner).

## 1. Execution order (refuter-corrected — this is the plan)

| step | lever | saving/wk (corrected) | days | notes after refute |
|---|---|---:|---:|---|
| 1 | **L3 backend-growth audit — measurement-only PR first** | up to ~8.3k slot-min + latency IF backend is the true tail | 0.5+1 | Both refuters' first pick. `--durations=50` covers only pytest — add **per-step timing** (pip-audit is network-bound on PyPI; uv-install resolves unpinned torch tree; migrations). Latency claim must first prove Backend > CodeQL wall-clock in the same window. |
| 2 | **L5 pre-push allowlist v7 — 5 entries, NOT 6** | ~28 avoided FULL/wk × 13 min local + lock-tail relief | 0.5 | DROP `apps/evaluator/nlm_deep_research/**.py`: its schema-coupling innocence is UNVERIFIED — adding it inverts the classifier's fail-safe principle (refuter: "the corpus of innocence cannot exist yet"). Keep: `scripts/**.sh` (excl. `scripts/ci/`), `scripts/**.md`, `apps/wa-mirror/package*.json`, `organs_registry.yaml`, `scripts/tests/**.sh`. Each with guilt+innocence in the classifier corpus. Also add `.husky/pre-commit` to `NEVER_INNOCENT_EXACT_PATHS`. `scripts/**.py` stays OUT (backend suite imports 9 files from there — measured). |
| 3 | **L2 detect-secrets diff-scoping — with baseline-reconciliation wrapper** | ~11k slot-min, tail 19.9→12.5 min | 3-4 (not 2) | Refuter: `detect-secrets-hook` ≠ `detect-secrets scan --baseline` — no whole-tree baseline mutation ⇒ stale entries accumulate and `detect_secrets_check_unaudited.py` reads the WHOLE baseline; renames escape without `--no-renames`. Cure: wrapper that (a) runs hook on merge-base-enumerated files (reuse `hotzone_changed_files.sh`, add `--no-renames`), (b) forces FULL scan when `.secrets.baseline`, triage rules, exclusions or CI scripts are touched, (c) weekly full-tree + push full-tree stay as backstop. Measure the "1.5 min" cold/warm, don't assume. |
| 4 | **L4 green-NA pilot — 3 tiny checks only** | PR-side real; queue-side collapses (0.87^depth) | 2 | 47.5% NA holds for `pull_request` only; in `merge_group` the cumulative diff kills NA exponentially with queue depth (0.87⁵≈50%, 0.87¹⁰≈25%). Pilot on `asyncpg-lint` / `npm lock honors manifest` / `lint-migration-*` with the full co-requisite kit (classifier from main, `.github/**`→full fan-out, `if: always()` aggregator, guilt+innocence per check). Backend-NA decision only after a week of pilot receipts, with queue-depth-corrected math. |
| 5 | **L1 push-run dedupe — SPLIT, tests.yml only** | ~13k slot-min (T&C share) | 1.5 | Refuter (both seats): security.yml's full backstop is **WEEKLY**, not 2h — skipping Snyk/Safety/CodeQL on push opens a ≤7-day window for newly-published CVEs (≈50× slower detection). So: dedupe `tests.yml` push-runs only (2h scheduled full run is the backstop, verified line 42); security.yml push-runs UNTOUCHED until a daily security schedule exists (then revisit). Fail-closed-to-run on API error/direct push; skip verdict prints the deferred-to run URL. Consumer-map in PR body (Codecov, uv-cache priming, main-push-failure-watch). |

Realistic combined effect after refute: **~35-45k slot-min/wk removed** (not 52k — L3/L4
overlap double-counted ~4.5k, L1 halved by the security split), utilization 48% → ~30%,
which is the difference between burst backlogs (54-min queue waits measured) and none.

## 2. Smaller queues (different currencies)

- **P0 Telegram lane**: raising `TG_P0_BUDGET` 12→24 does NOT zero latency (24-31 daily
  sources ⇒ 0-7 overflow remains; refuter caught the arithmetic). It also doubles owner ping
  volume — **product decision, operator[business], parked**. The technical lever stays
  `dlq-autopilot` grouping (in flight via #3902-class work).
- **DLQ TERMINAL corpses**: 26/26 entries are corpses masking any new entry. Extend the W81b
  corpse-sweep to the TERMINAL class — archive-not-delete, atomic, dedup/audit-path
  preserved. Session-runnable, 0.5 day. Signal hygiene, not minutes.
- **Vercel**: the big lever (should-build origin fallback) shipped this session; residual
  preview waste is a bounded decaying transitional (~5.6 CPU-h, 12 pre-fix branches). KBLI
  ISR/page-count reduction is a NON-lever (tried 2026-07-03, reverted on measured SEO/TTFB
  regression; page gen is 29s of a ~5-min build). L11 typecheck-extraction inapplicable as
  drafted (`ignoreBuildErrors` already false; `frontend-typecheck` is NOT among the 26
  required — making it required comes first, else the flip opens a type-error-to-prod window).
- **Pre-push ReDoS timing test**: flaked again tonight under load (PASAL_PATTERN 4.4× on
  ~5ms absolute timings, machine running suites+agents). The two-sided control band (#3908)
  reduced but did not eliminate load-noise. Candidate: median-of-3 timing or moving the sweep
  to CI-only (it still runs on every PR there) — needs its own guilt+innocence pass; NOT done
  in this round.

## 3. Non-levers (data says no — do not re-propose without new evidence)

1. **xdist/sharding in CI**: 1.16× measured at -n8 on a 14-core machine; CI has 4 vCPU.
2. **Larger/paid runners**: queue wait ≈ 0s; the binding resource is the 20-slot pool, not
   machine size; standing Zero NO (Legge 5).
3. **26→3 required-check bundling**: late-stage by constraint; the 20 trivial checks are never
   the tail (batch waits on Backend regardless).
4. **Merge-queue parameter tuning**: capacity ~11 merges/h vs arrival 2/h — 5× oversized.
5. **Same-content green-cache for required checks**: killed 3/3 in BOTH prior rounds; no
   I1-compatible form. (L1 is NOT this: same-SHA-already-validated, on a non-required surface,
   with a scheduled backstop.)
6. **Top-level `paths:` on required workflows**: zero-jobs-blocks-forever scar. Job-level NA
   with the co-requisite kit is the only legal form.
7. **Round-1 queue-hygiene suite**: no patient (12 open PRs).
8. **L6 fail-open triad**: STALE — current tests.yml already fixed (E2E fails loudly, Test
   Summary reads `needs.*.result`). Verified live by the refuter.

## 4. Method notes (for the next round)

- The refuter pass earned its cost: it killed one lever (L6 stale), split another (L1),
  re-costed two (L2 wrapper, L4 queue-depth), and dropped an unsafe allowlist entry (L5) —
  five material corrections on a synthesis that had itself already re-verified prior art live.
- Convergent cross-family first-pick (L3, measurement-only) is the strongest signal in the
  round: when the red-team and the refuter independently choose the same lowest-risk move,
  start there.
- The 2h scheduled full run on main (tests.yml line 42) was load-bearing for L1 and appeared
  in NO prior round document — reading the live workflow beats reading the archive.
