---
date: 2026-08-03
domain: operations
client_case: none (internal engineering — megatopics 1-5, continuation of megatopic 0)
status: SHIPPED — all 4 items merged and prove-live confirmed 2026-08-03/04 (#3558, #3559, #3560, #3561)
sources:
  - research/operations/2026-08-03-verified-claim-reconciliation.md (megatopic 0, the shared vocabulary/schema these fixes reuse)
  - 5 parallel read-only investigative agents dispatched this session (2026-08-03), each independently re-verifying one row of the VCR §1 table with commands run live, not from memory
  - research/marketing/2026-07-18-wr2-fact-check-degraded-root-cause.md (pre-existing, Codex-CADE'd, not yet implemented — reused here, not re-derived)
adversarial_review: codex
---

# Megatopics 1-5 — action plan (post-investigation, pre-build)

> Megatopic 0 (`2026-08-03-verified-claim-reconciliation.md`) built the shared
> vocabulary and picked ONE pilot (LLM seat-health). This plan applies the
> same discipline — verify with a live command, prefer Tier-1 deterministic,
> defer Tier-2 semantic judgment, one scoped fix per domain, never a bundled
> mega-PR — to the 5 other rows of that table's §1 disease-instance list.

## Priority order (risk-ranked, not row-number order)

| Priority | Domain | Risk | Why this order |
|---|---|---|---|
| 1 | PENDING-ARMS + E33 (merged into one build) | LOW | Pure signaler, no production data-path touched, reuses one mechanism for two findings |
| 2 | KBLI citation-propagation gap | LOW | Extends an existing conformance tool's output, already in active maintenance |
| 3 | WR2 fact-checker | MEDIUM | Gates content publishing, not customer-facing safety; fixes already designed+reviewed on 2026-07-18, just unshipped |
| 4 | Bot evidence score | MEDIUM-HIGH | Touches the live RAG abstain pipeline behind tax/visa/KBLI/pricing answers on WhatsApp/web — ships last, with the most test coverage |

---

## 1. PENDING-ARMS + E33 monitor — one reconciler, two probe classes

**Verified state** (via `megatopic-pending-arms` + `megatopic-e33-monitor` agents):
- Ledger sample (9 entries, live-checked): 6 CURRENT, 2 STALE (one is a PR merged days ago, ledger still says "open" — the ledger's own documented failure mode, caught live), 1 self-caveated/ambiguous.
- `e33_cases`: **0 rows**, confirmed via `scripts/pg.sh` SELECT; kill switch `e33_guarantee_scan_enabled` has **no row at all** (UNPROVISIONED); cron has posted HTTP 200 `{"status":"blocked",...}` daily for its whole life — green, doing nothing (scar family #2).

**Build**: one new script, `scripts/pending_arms_reconciler.py` — a **signaler, never a mutator** (per family #2's antidote: report, don't auto-fix):
- Probe class A ("PR-referenced"): regex-extract `#[0-9]{3,5}` from every ledger line, `gh pr view` each, flag (a) an *open* entry whose only blocker is "merge PR #N" where that PR is already MERGED, (b) a *closed* entry whose proof cited a seat/service that `arsenal_probe.py`'s current report now shows unhealthy.
- Probe class B ("zero-population monitor"): for any cron-gated organ backed by a `system_settings` kill switch, alert if switch is UNPROVISIONED >48h AND the target table has 0 rows / no write has ever happened (generalizes the E33 finding so the next instance of this shape doesn't need its own pilot).
- Exit codes: 0 clean, 1 stale-found, 4 cannot-verify (offline/no gh auth) — never touches the ledger file itself.

**Test plan**: guilt (a synthetic ledger line citing a real merged PR is flagged; a synthetic zero-row+unprovisioned monitor is flagged) + innocence (a genuinely-open entry citing an unmerged PR is NOT flagged; a populated table is NOT flagged).

**Prove-live**: run the reconciler against the REAL `PENDING-ARMS.md` and REAL `e33_cases` — it must reproduce the two live findings above (the stale PR-merged entry, the E33 zero-population case) without being told about them in advance.

---

## 2. KBLI citation-propagation gap

**Verified state** (via `megatopic-kbli-citations` agent): the 99%-uncited claim is real (97.8% today, down from 99.0% at the VCR doc's snapshot — active, ongoing improvement) and is the NAMED current focus of the already-active KBLI Navigator program (F2). `scripts/kbli_filiera/kbli_surface_conformance.py` already does the Tier-1 state-comparison this pattern calls for. The one genuinely new gap: the website page (`/kbli/<code>`) now renders a "Basis:" citation (#3532, PROVEN LIVE) that hasn't propagated back into canonical/`kbli_documents` — so DB-backed channels (chat_kbli, WhatsApp, webchat) stay blind while the website is fixed.

**Build**: extend `kbli_surface_conformance.py` with one new divergence check — website-rendered citation present AND canonical `pma_official_basis` absent → flag as `citation_not_propagated`. Small, additive, no new infrastructure.

**Test plan**: guilt (a code with a website citation but no canonical basis is flagged) + innocence (a code with both, or neither, is not flagged as this specific divergence).

**Prove-live**: run the extended conformance tool against production data, confirm it surfaces a non-zero, plausible count of `citation_not_propagated` codes (a zero result here would itself be suspicious per this org's own "esattamente 0 è sospetto" pattern — re-verify the check actually runs before trusting a clean report).

---

## 3. WR2 fact-checker — ship the already-designed, already-reviewed fixes

**Verified state** (via `megatopic-wr2-factcheck` agent): the VCR table's claim pointed at the wrong system (`ToneCouncil`, never instantiated in production — itself a scar-#2 instance, not "circular", just inert). The REAL production checker, `scripts/wr2_fact_checker.py`, already has a fail-closed cap (`degraded` when no external truth) — but `degraded` **silently proceeds to canva-apply exactly like `pass`**, so the cap is a label, not a block. A full root-cause report already exists (`research/marketing/2026-07-18-wr2-fact-check-degraded-root-cause.md`, Codex-CADE'd) with recommendations never shipped.

**Build** (from that report's own recommendations, not re-invented here):
1. Replace binary `verified`/`degraded` with 4 provenance labels: `independently_corroborated` / `supported_by_source_article` / `source_absent` / `claim_unparseable` — cheap, checker-side, no RAG changes.
2. Stop `degraded`'s silent pass-through at the canva-apply gate (`wr2_fact_checker.py:737-739`) — only `independently_corroborated` and `supported_by_source_article` may proceed; `source_absent`/`claim_unparseable` block, matching what the fail-closed design already intended.
3. Verify non-law claims against slide-excluded `external_text` in BOTH passes (currently only law citations get this; the live rubber-stamp hole).

**Explicitly deferred** (Tier-2, needs RAG data-plane work): re-querying the oracle per-claim at CHECK time using only the claim text, never the brief — this is the real "independently corroborated" fix and is a bigger, separate change; today's build only makes the LABEL honest about which of the two states a draft is actually in.

**Test plan**: guilt (a draft with zero external truth must land in `source_absent`, must NOT reach canva-apply) + innocence (a draft with genuine external corroboration still proceeds) + the 86-draft historical set from the 2026-07-18 report as a regression fixture (79 were `degraded` — after this change, none of those 79 should silently reach canva-apply).

**Prove-live**: run the updated checker against the current draft backlog (read-only dry-run mode first), confirm the count of "would-have-silently-published degraded drafts" matches expectations before flipping it live on the cron.

---

## 4. Bot evidence score — closes last, most test coverage

**Verified state** (via `megatopic-bot-evidence` agent): `_reasoning_evidence.py:30` hardcodes `0.85` whenever `trusted_tools_used=True`, computed by a purely mechanical check (tool name in an allowlist + no error string + `len(observation)>50`) with **zero correlation to `final_answer`**. Worse than the VCR table's original framing: `reasoning.py:731-732`/`:1435-1437` show this doesn't just inflate the score, it **skips the generation abstain-gate entirely** when `trusted_tools_used=True`. Two "flippers" can only turn this ON, never off.

**Build**: for tools returning quotable/structured data (`get_pricing`, `crm_query`, `timesheet`, `calculator`), extract key literal tokens (numbers, IDs, currency amounts) from the tool's observation and require at least one to appear (normalized) in `final_answer` before granting `0.85`; otherwise fall through to the existing `calculate_evidence_score` keyword path instead of hardcoding. **Does not touch the 5 named abstain-gate threshold VALUES** (CLAUDE.md §9 invariant, panel-ruled) — this fixes the INPUT signal those gates consume, not the gates themselves.

**Test plan**: guilt (tool returns price X, answer shows Y or no price → must NOT get 0.85, must fall through) + innocence (answer correctly quotes tool's figure → still gets 0.85) + regression run of `test_abstain_threshold_convergence.py` / `test_abstain_policy_hardening.py` (must stay green — this build must not touch those files).

**Prove-live**: this is the one domain where "prod" means the live WA/web bot — deploy behind existing test coverage, then run a small set of REAL known-answer queries (a price lookup with a deliberately-wrong-injected tool response, via a test harness, not real client traffic) against the deployed endpoint and confirm the evidence score now reflects actual relevance, not tool-call success alone.

---

## Outcome — shipped 2026-08-03/04

All 4 items merged and prove-live confirmed: #3558 (PENDING-ARMS+E33), #3559 (KBLI
citation-propagation, merged, live conformance run reproduced the expected
445/414 counts), #3560 (WR2 fact-checker hard gate + kill-switch), #3561 (bot
evidence-score relevance veto — deployed to `nuzantara-rag`, `/health` green,
live machine `GH_SHA` confirmed matching the merge commit).

Reviewed pre-build by a 4-LLM panel (Gemini/Codex/Kimi). Codex ran the
substantive independent post-merge re-verification (`panel-codex-plan`),
re-checking all 4 shipped fixes against the actual PRs and confirming no open
objections — all 7 of its original DO-NOT-SHIP conditions closed at the code
level.

---

## What this plan does NOT do

- Does not touch the abstain-gate threshold VALUES (§9 invariant).
- Does not build the WR2 Tier-2 re-query-at-check-time fix (separate, RAG-data-plane-touching effort).
- Does not open a new KBLI program — folds into the existing one.
- Does not attempt cron/plist or per-machine seat-health line-types in the PENDING-ARMS reconciler (VCR §4 already scoped that as its OWN harder pilot).
