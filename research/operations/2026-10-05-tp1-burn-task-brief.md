---
date: 2026-10-05
domain: operations
client_case: N/A — internal fleet governance (Alibaba Token Plan burn cycle)
sources: 4
discovered_by: session (worktree .worktrees/ops-tp1-burn-oct26, mandate Zero 2026-10-05)
adversarial_review: codex
---

# Task Brief — TP1 quota burn, cycle 2026-09-11 → 2026-10-12 (UTC+8)

> Owner mandate (Zero, 2026-10-05, interactive Qwen/TP1 session): consume the Token Plan Pro
> monthly pool before it resets. Lane GO granted the same day: lanes 1, 2, 3, 5 armed for the
> first night window; end-of-cycle buffer = **15% operational** (Zero's choice, overrides the
> burn-to-100% default).

## Quota state at arming (console read 2026-10-05 14:36 UTC+8, screenshot by Zero)

- Plan: Pro, ACTIVE, window 2026-09-11 16:36:33 → 2026-10-12 00:00:00 (UTC+8), auto-renewal ON.
- Monthly usage: **2.13%**. Resets 2026-10-12 00:00:00 (UTC+8). Unspent credits are lost at reset.
- Burn ceiling (Zero's buffer ruling): stop batch lanes at **85%**; the last 15% stays for
  operational seats (refuter/builder chains) until reset.
- Usable: 85 − 2.13 = **82.87 console points** over ~6.4 days ≈ **12.9 pts/day**, checkpointed
  every 12 h (08:00 / 22:00 WITA). Behind by >3 pts at a checkpoint → add workers; ahead →
  pull lane 5 (media-gen, heaviest per asset) forward.

## Meter and calibration

No programmatic credits endpoint exists (PROBE-1 residual: 20 candidate paths, all 404). The
console % is the only meter. Local per-job token logs reconcile against it within ~2.5%
(PROBE-1, research/operations/2026-08-14-probe1-tp1-burn-rate.md). Credit-per-token formula is
opaque → **calibrate empirically**: the first 12-h checkpoint yields pts-per-Mtok for the night
mix; worker counts for D1+ are sized from that number, not from a guess.

## Seats (console roster 2026-08-14, 14 models) and windows

- Night window 22:00–08:00 WITA (= UTC+8 night): `qwen3.8-max` carries **Night 50% Off** →
  60–70% of all 3.8-max volume scheduled here.
- Day: `deepseek-v4-flash-0731` (throughput), `glm-5.2` (counter-builds, `clear_thinking:
  false`), `qwen3.7-max`/`qwen3.7-plus` (second line), `deepseek-v4-pro` (reserve refuter,
  advisory only), `qwen3.6-flash` (non-exact grunt).
- Media (unwired capabilities, Zero GO 2026-10-05 via this brief): `wan2.7-image-pro`,
  `happyhorse-1.1-t2v/i2v/r2v`, `qwen-audio-3.0-tts-plus`. Drafts only (Legge 5).
- **EXCLUDED from burn** (attribution unresolved, MODEL_ROSTER 2026-08-21 probe): `qwen3-coder-*`,
  `kimi-k2/k2.7/k3`, `MiniMax-M2.7/M3` — live PONG under the TP1 key but unknown whether they
  draw the flat plan quota or silent metered billing. Metered spend needs a separate Zero GO;
  the 14-model roster is sufficient burn capacity without them.

## Lanes

| # | Lane | Seats | Repo assets | Gate |
|---|------|-------|-------------|------|
| 1 | KBLI 2025 mass corpus (risk sheet, jangka waktu, capital, licensing per code) | 3.8-max night / 3.7-plus day | `scripts/build_kbli_l1_from_oss.py`, `build_kbli_l2_oss_risk.py`, `enrich_kbli_jangka_waktu.py`, `enrich_kbli_company_concepts.py` | exact fields (code/title/risk class) → double convergent extraction; outputs land in draft/queue, curated datasets written only by canonical writers |
| 2 | Law library: structured summaries + synthetic Q&A per UU/PP/Permen for `nuzantara-knowledge` RAG | v4-flash day / 3.8-max night | backend-rag ingestion + eval set | article numbers/dates exact → double extraction + Anthropic/Google seat sample check |
| 3 | Mass docs/translation: balizero.com EN→ID (.id.mdx) catalog, docs refresh | 3.8-max night | Subhi pipeline, `scripts/docs_sync.py`, `docs_audit.py`, `doc_freshness_report.py` | non-PII; Subhi glossary |
| 4 | Test & refactor grind (day filler) | glm-5.2 + 3.7-max | scripts/tests conventions | modus Grinder: every lot sample-verified by an Anthropic seat; diffs to pack, no self-merge |
| 5 | Media-gen: OG/hero for article catalog, WR2 draft variants, WR3 B-roll, Morning News TTS | wan2.7-pro, happyhorse, audio-tts | WR2/WR3 draft pipelines | Zero GO recorded here; everything stops at `drafted` |
| 6 | Panels/second opinions: FOLLOWUPS, PENDING-ARMS pre-triage, cicatrix scar themes | v4-pro + 3.8-max | `scripts/archive_cicatrix_scars.py`, council journal | advisory only, never load-bearing |
| 7 | Agentic density: parallel Qwen Code sessions on TP1 (this door) | 3.8-max (night −50%) | `scripts/agent_start.py` worktrees | worktree discipline; prepare-only |

## Rate and concurrency envelope

2M tok/min · 15k req/min plan ceiling. Cap: ≤60 concurrent batch workers + ≤6 agentic sessions,
exponential backoff on 429. Heavy execution runs on Pro (`ssh pro`); M5 orchestrates only.

## Invariants at full burn (unchanged)

- Zero client PII in any lane; CRM corpus excluded a priori (Builder Contract 4 / SYMBIOSIS Law 2).
- Exact-format output never enters a product flow without independent verification (QWEN.md §1).
- generator≠grader: TP1 produces, an Anthropic/Google seat grades samples; this seat prepares and
  never merges/arms/deploys (Builder Contract 5).
- Legge 5: no outward publish on our initiative; drafts stop at `drafted`.
- Every job logs tokens locally (ledger contract per `scripts/check_llm_cost_tracking.py`) and
  declares its estimate here; real burn appends to this brief at each checkpoint.

## D0 findings (2026-10-05, this lane)

- **Breaker:** `cost_breaker.GUARDED_PROVIDERS` = claude_oauth/gemini/openrouter only — TP1
  (ledger provider `deepseek`) is UNGUARDED by fleet design (flat subscription, zero marginal
  cost, same posture as kimi/ollama; the retired metered door's $5 slot was not carried forward).
  The burn guard is therefore `tp1_burn_common.BurnGuard`: hard per-run caps (default 40M tokens /
  200k calls per process, env-overridable), fail-closed, on top of this checkpoint loop. Ledger
  visibility untouched: every chat call rides `deepseek_client.complete` → `log_cost_event`.
- **Media probe (one call each, M5):** `wan2.7-image-pro` → 200 PENDING on
  `/api/v1/services/aigc/image-generation/generation`; `happyhorse-1.1-t2v` → 200 PENDING on
  `/api/v1/services/aigc/video-generation/video-synthesis`; OpenAI-style `/images/generations`
  and `/audio/speech` → 404 on the TP1 base. Lane 5 runner (`tp1_burn_media_gen.py`) uses the
  native async submit→poll pattern; TTS native path probed once at runner start, verdict stored
  in the manifest, never guessed.
- **Runners shipped in this worktree:** `tp1_burn_common.py`, `tp1_burn_kbli_l3_full.py`
  (full 1,559-record schema → separate draft queue `_l3_generated_burn_oct26.json`, canonical
  queue and curated datasets untouched), `tp1_burn_translate_id.py` (canonical Subhi prompt
  imported verbatim, drafts under `data/burn_drafts/id_mdx/`), `tp1_burn_media_gen.py`
  (manifest under `data/burn_drafts/media/`), `tp1_burn_media_probe.py`.
- **Window-aware model choice inside runners:** night 22:00–08:00 WITA → `qwen3.8-max` +
  reasoning_effort high (Night 50% Off); day → `qwen3.7-plus` + effort low. One long-lived
  process per lane, no model-switch restarts, no output-file races.
- **Codex (Sol) adversarial review** on commit `21d6254b04`: REQUEST-CHANGES, 11 findings
  (1 blocker: caps did not reserve capacity atomically; majors: invisible retries,
  drain-discards-paid-work, locale-suffixed translations misread as EN originals, manifest
  race + partial JSON, shared deadline stranding late submissions, task-id lost on poll
  errors, media lane ledger-blind, `--images 0` meaning unlimited, resume freezing transient
  failures). ALL fixed in the successor commit; guilt+innocence tests in
  `scripts/tests/test_tp1_burn_guard.py`; evidence brief at
  `evidence/2026-10/agent-air-m5-ops-tp1-burn-oct26/brief.yml` (gear 2, gate_class opus, BLUE).

## Adversarial review

codex (Sol), on commit `21d6254b04`, 2026-10-05: **11 raised, 11 survived as fixes in the
successor commit, 0 waived.** The surviving objections and their cures:

1. (blocker) caps did not reserve capacity atomically and queued workers never re-checked the
   guard → `BurnGuard.reserve()` claims the slot at submit; workers re-check `ok()` before every
   paid attempt.
2. failed/retried HTTP attempts were invisible to the cap and ledger → `add_attempt()` counts
   them; media submits write `log_cost_event` rows.
3. mid-run cap break discarded already-paid queued work → pending futures are cancelled and the
   running few are drained into the output.
4. locale-suffixed translations (.it/.fr/.ru) misread as EN originals → discovery and media
   prompts accept only stems with no locale dot.
5. manifest checkpoint serialized without the lock, straight onto the final file → checkpoint()
   dumps under the lock via tmp + `os.replace`.
6. one shared deadline stranded late submissions as permanent TIMEOUT → per-job deadline
   computed at submit; POLL_TIMEOUT/POLL_ERROR stay retryable.
7. task id persisted only after polling → persisted the moment the provider accepts.
8. media lane ledger-blind (calibration blind spot) → ledger row per submit, per probe, per
   TTS probe.
9. `--images 0` meant unlimited → 0 disables, default 100.
10. fence regex stripped inner code fences → wrap-only stripping.
11. resume froze transient API failures forever → only PASS and real fact-gate REJECTs count as
    done.

Guilt+innocence tests for 1-4 and 10: `scripts/tests/test_tp1_burn_guard.py` (5 passed locally).

## Lane 7 outcomes (2026-10-05 evening, two agentic burn sessions)

~44.6M tokens consumed (test-gap 14.58M, docs 29.99M) — densest burn per wall-minute of the
cycle, as predicted. Both sessions prepare-only; both branches deliberately LEFT LOCAL
(unpushed): their `research/operations/*-queue.md` artifacts carry no R1 frontmatter and this
seat will not declare an adversarial review it did not perform. A shipping session picks them
up from the worktrees.

- **test-gap** — branch `agent/air-m5/infra/test-gap-oct26` (worktree
  `.worktrees/infra-test-gap-oct26`, 2 commits): 8 new pytest files over safety-critical
  modules (ledger export, outbox replay/prune, circuit breaker, worktree keep, WA janitor,
  PII-in-logs audit, canva lease watchdog), targeted run 270 passed / 0 failed, 366 with
  neighbours. Four real defects pinned, cures queued not applied: (1)
  `wa_mirror_session_janitor._phone_to_name()` AttributeError on a top-level LIST accounts
  file (dead janitor = the 2026-06-09 ghost-row crash-loop minus its safety net); (2)
  `audit_pii_in_logs` misses attribute-rooted loggers (`self.logger`, `app.logger`) so its PII
  count is a floor; (3) `wr2_canva_lease_watchdog.main()` propagates a Telegram failure AFTER
  leases were recovered; (4) `circuit_breaker` HALF_OPEN has no second timer. Structural:
  `scripts-tests-sweep.yml` is continue-on-error and not required (the new tests gate nothing
  until promoted), and 15 root-level `scripts/test_*.py` (incl. `test_redact_pii.py`) are named
  by no gate. Gap queue: `research/operations/2026-05-...-test-gap-queue.md` in that worktree.
- **docs** — branch `agent/air-m5/docs/refresh-queue-oct26` (worktree
  `.worktrees/docs-refresh-queue-oct26`, 3 commits): 10 stale reference docs corrected (+144
  net), 25 briefed, 691-line queue. Ship prerequisites for the shipping session: rebase over
  `origin/main` #7890 with the UNION resolution on the r3 spec (their `[CLIENT-NAME-REDACTED]`
  placeholders + this branch's de-linking), regenerate `docs/DOCS_INVENTORY.md` in the same PR
  (inventory-check gate), split PRs A (corrections+inventory) / B (report) / C (tooling
  D1-D3: `docs_audit.py:55` LINK_RE truncates at first `)` → false-positive STALE on
  `](<https://…(…)>)`; `docs_link_fixer.py:145` starves the fixer model of context;
  `docs_link_fixer.py:352` reads a file-count as a link-count).

### Escalations to Zero (owner decisions, not this seat's)

1. **Privacy:** `docs/superpowers/plans/2026-05-08-domain-mesh-phase0-foundations.md` still
   carries 3 cleartext client identifiers (#7890 cleaned 5 of the 6 files found; this one
   remains). Untouched by the burn lane on purpose — routing is a privacy-owner call.
2. The four pinned defects above need a cure lane (the janitor one is a resurrected scar).
3. Promoting `scripts-tests-sweep.yml` from report-only to a required check is a shipping
   session's decision (it changes what gates merges).

## Checkpoint #1 — 2026-10-05 20:07 WITA

- **kbli**: crashed at 1.767/2.422 (`l0_ground_truth.uraian_id` null on some schema records,
  unguarded subscript) → guard + permanent skip as `incomplete-schema-record` in `9872a9ca14`;
  resumed with 655 todo. Output so far: 1.531 PASS / 236 fact-gate REJECT.
- **translate**: 112/851 ok, 0 fail, 1.07M tokens; pace ~134/h → completes inside the night
  window on qwen3.8-max.
- **media**: run 1 = 6/6 happyhorse videos SUCCEEDED; 848 images FAILED provider-side with
  `InvalidParameter: Field required: input.messages` (submit accepted, task refused: the probe's
  200 PENDING measured acceptance, not validity) → multimodal `input.messages` shape in
  `9872a9ca14`, all 848 retryable and retrying at workers=2 with 429 backoff. TTS probe:
  http-403 on the multimodal path → TTS EXCLUDED from lane 5, measured, not guessed.
- **Ledger (day, chat lanes)**: qwen3.7-plus 6.21M tokens (kbli ~5.1M + translate ~1.1M).
  Lane 7 agentic sessions: ~44.6M tokens (own harness, not this JSONL). Media: credits per
  asset, ledger rows carry call counts only.
- **Caps**: 6.2M/40M tokens (15%), ~4k/200k calls — healthy, no resize needed.
- **Calibration PENDING**: needs the console read (baseline 2.13% @ 14:36 UTC+8). Requested
  from Zero at this checkpoint; pts-per-Mtok derives from his number, then D1 worker sizing.
- Night window opens 22:00 WITA: runners auto-switch to qwen3.8-max + effort high (−50%).

## Schedule

- **D0 (2026-10-05)**: brief + worktree `ops-tp1-burn-oct26`; lane-7 workers launched daytime;
  explorer maps corpus paths/clients; runners implemented; **22:00 WITA first night window opens
  with lanes 1+3+5(wiring)+7**.
- **D1–D4**: full regime; 12-h checkpoints; calibration-driven worker sizing.
- **D5 (2026-10-11)**: push toward 85%; taper batch lanes from 20:00 UTC+8.
- **D6 (2026-10-12 00:00)**: reset; ledger close; verification pack of samples handed to a Claude
  seat for the generator≠grader pass.
