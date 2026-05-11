---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Step 4 REVOKE · Gap 2 Consiglio KILL decision OVERRULED by NB-1 review
sources: 6
status: revoke
loop_step: 4-revoke
loop_branch: feat/symbiosis-loop-2026-05-12
revokes: research/symbiosis/2026-05-12-consiglio-v2-or-kill.md
revoke_reason: NB-1 ground-truth review 2026-05-12 04:15 WITA caught a LIVE Consiglio v1 implementation at apps/backend-rag/backend/services/research/consiglio_orchestrator.py that the previous decision matrix had ignored. The KILL recommendation was based on incomplete analysis (only checked mata-garuda/.disabled-2026-05-06/council/ prototype, missed the backend RAG live implementation).
---

# Gap 2 Consiglio KILL — REVOKED

**Generated**: 2026-05-12 04:25 WITA · Revokes earlier Step 4 decision · branch `feat/symbiosis-loop-2026-05-12`.

## What went wrong

`2026-05-12-consiglio-v2-or-kill.md` (Step 4 of this loop, commit `fa0ddbef1`) recommended KILL based on:

- PR #468 quarantined `apps/mata-garuda/.disabled-2026-05-06/council/` with "never deliberated" rationale
- 5 existing multi-LLM patterns (wave-orchestrator, tri-LLM panel, bipolar verifier, ad-hoc brainstorm, MOS auto-save) all overlap Pilastro 4

This analysis MISSED the live implementation at `apps/backend-rag/backend/services/research/consiglio_orchestrator.py`.

## NB-1 ground-truth (verified 2026-05-12 04:15 WITA)

NotebookLM NB-1 (Nuzantara Codebase & Architecture, 75 sources) flagged:

> Il Consiglio vive in `apps/backend-rag/backend/services/research/consiglio_orchestrator.py`. È un modulo attivo che funge da "bias-breaker" eseguendo una delibera 4-LLM (Claude, Gemini, DeepSeek, NotebookLM) tollerante ai guasti per le decisioni strutturali.

> Consiglio v1 Ground Truth ASSOLUTA: Gemini esplicito — "Se Claude Opus dice X e NB-4 dice Y, il Consiglio deve forzare Claude ad allinearsi a Y o sollevare un'eccezione (Cicatrix)"

## Disk verification (2026-05-12 04:20 WITA)

`apps/backend-rag/backend/services/research/consiglio_orchestrator.py` exists and has `__pycache__/` entries — module is loaded at runtime. Preamble:

```python
"""Consiglio v1 orchestrator — 4-LLM deliberation for playbook synthesis.

Gate 6 invariant: every final claim has ≥3/4 LLMs agreeing (default).
Disputed claims (≤2 agreement) are kept in the playbook, flagged ⚠️.

Current members:
  claude     — Claude Opus 4.7 via OAuth CLI (primary analyst)
  gemini     — Gemini 3.1 Pro (1M ctx) via CLI — gracefully degrades
  deepseek   — DeepSeek Reasoner ($0.01/query, audited exception)
  notebooklm — NotebookLM MCP query — grounded authority validator
"""

DEFAULT_MIN_AGREEMENT = 3  # 3/4 threshold
CLAIM_QUERY_TIMEOUT_SEC = 600  # 10 min per LLM per deliberation round
```

Companion file: `apps/organism/organism/supervisor/consiglio_gate.py` — the supervisor's gate that integrates Consiglio deliberation outcomes.

## The two Consiglio v1's

| Location                                                               | Status              | Role                                                                                      | Decision                                          |
| ---------------------------------------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `apps/mata-garuda/.disabled-2026-05-06/council/`                       | Quarantined PR #468 | mata-garuda prototype, never deliberated, weekly LaunchAgent meant for decommissioned Air | Remains quarantined (correct per PR #468)         |
| `apps/backend-rag/backend/services/research/consiglio_orchestrator.py` | **LIVE**            | Backend RAG Gate-6 invariant, 4-LLM ≥3/4 agreement, playbook synthesis feeder             | **DO NOT KILL** — this is the canonical Consiglio |
| `apps/organism/organism/supervisor/consiglio_gate.py`                  | **LIVE**            | Supervisor integration gate                                                               | **DO NOT KILL**                                   |

## What the 5 patterns DO NOT cover

The KILL rationale was: "5 existing patterns cover Pilastro 4". NB-1 surfaces the gap they DO NOT cover:

**Multi-NB Ground-Truth enforcement at deterministic gate boundary**.

The 5 patterns are all session-scoped or query-scoped:

- Wave-orchestrator: parallel agents on tasks (ad-hoc)
- Tri-LLM panel: PR critical review (ad-hoc)
- Bipolar verifier: per-query NB check (per-query)
- Ad-hoc brainstorm: invocato quando serve (manual)
- MOS auto-save: persistence (passive)

NONE of them implements: **"At a deterministic gate (Gate-6 in `consiglio_orchestrator.py`), force 3-of-4 LLM agreement OR raise a Cicatrix exception"**. This is a deterministic FastAPI-context invariant, not an ad-hoc tool.

For playbook synthesis (Task 20 driver writing `08_playbook.md` + `09_wr2_weights.json`), the Consiglio gate is what prevents single-LLM bias from leaking into automated WR2 weights. Killing it would force human review of every playbook delta — operationally untenable.

## Corrected decision

**Keep `consiglio_orchestrator.py` and `consiglio_gate.py` as canonical Consiglio v1**.

**Archive the quarantined `.disabled-2026-05-06/council/` prototype** as a historical artifact (it's a different design that never ran — keep the directory for forensic reference, no further action needed).

**Document the divergence**:

- Quarantined prototype: weekly cron + 4-LLM moderator + SQLite council.db + escalation chain to Zero
- Live implementation: synchronous gate-6 invariant in FastAPI, 4-LLM voting on playbook claims, no persistent DB (read-only), no cron

They are NOT the same design. PR #468 quarantined the right thing (the cron-based prototype). My Step 4 incorrectly concluded "all Consiglio is quarantined → KILL".

## Pilastro 4 status after correction

| Promise                      | Coverage                     | Provider                                                                     |
| ---------------------------- | ---------------------------- | ---------------------------------------------------------------------------- |
| P4.1 Periodic deliberation   | ad-hoc only (no weekly cron) | wave-orchestrator + ad-hoc brainstorm                                        |
| P4.2 Moderator               | YES                          | `consiglio_orchestrator.py` 4-LLM ≥3/4 agreement                             |
| P4.3 Architectural diversity | YES                          | 4 different LLMs (Claude OAuth + Gemini CLI + DeepSeek API + NotebookLM MCP) |
| P4.4 Output channels         | YES                          | playbook + WR2 weights + Telegram via FAD                                    |
| P4.5 Groupthink detection    | YES                          | ≥3/4 threshold + ⚠️ flag on disputed                                         |
| P4.6 Devil's advocate        | YES                          | DeepSeek Reasoner is canonical role                                          |

5 of 6 promises COVERED by `consiglio_orchestrator.py`. P4.1 (weekly cadence) was the only thing the quarantined prototype attempted to add, and PR #468 correctly killed it because Air decommissioned and no production trigger existed.

## Action items revised

1. **Revoke Step 4 KILL recommendation** ✅ (this doc)
2. **Add cicatrix-scars-archive.md RESOLVED entry** for the quarantined mata-garuda prototype only (with clear note "live implementation continues at apps/backend-rag/backend/services/research/")
3. **NO new code needed** — Consiglio v1 live works as designed
4. **Optional Phase 2** (future PR): add cron schedule wrapper around `consiglio_orchestrator.py` if periodic deliberation is desired (Pilastro 4 P4.1 last unchecked promise)

## Sources

1. NotebookLM NB-1 `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` query response 2026-05-12 04:15 WITA (`/tmp/symbiosis-nlm-review-2026-05-12/04_gap2_consiglio.md`)
2. `apps/backend-rag/backend/services/research/consiglio_orchestrator.py:1-30` (preamble read 2026-05-12 04:20 WITA)
3. `apps/organism/organism/supervisor/consiglio_gate.py` (file existence verified)
4. PR #468 commit message `6c8f0284c` (quarantine of mata-garuda prototype — correct)
5. Step 4 KILL doc `research/symbiosis/2026-05-12-consiglio-v2-or-kill.md` (REVOKED)
6. NB-1 cited Decision 9 "Bias-breaker Consiglio v1: Claude (Sonnet 4.6) + Codex (GPT-5.5 xhigh) + DeepSeek + Gemini = 4-LLM voting con different training data per ogni decision strutturale" — the architecture intent matches the live impl
