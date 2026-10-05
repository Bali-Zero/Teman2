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

## Schedule

- **D0 (2026-10-05)**: brief + worktree `ops-tp1-burn-oct26`; lane-7 workers launched daytime;
  explorer maps corpus paths/clients; runners implemented; **22:00 WITA first night window opens
  with lanes 1+3+5(wiring)+7**.
- **D1–D4**: full regime; 12-h checkpoints; calibration-driven worker sizing.
- **D5 (2026-10-11)**: push toward 85%; taper batch lanes from 20:00 UTC+8.
- **D6 (2026-10-12 00:00)**: reset; ledger close; verification pack of samples handed to a Claude
  seat for the generator≠grader pass.
