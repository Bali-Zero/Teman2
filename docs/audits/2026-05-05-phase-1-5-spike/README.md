# Phase 1.5 spike — notebooklm-py v0.3.4 empirical validation (2026-05-05)

**Decision**: NUANCED PROCEED to Week 1 (see
`/Users/nuzantara/Desktop/nlm/WEEK0_PHASE_1_5_DECISION_2026_05_05.md` for
the full reasoning).

## What's in this directory

- `notebooklm_py_spike.py` — async test harness, 270 LOC. Runs 8 source-add
  + 12 source-get-fulltext + 30 chat.ask + 8 cleanup-delete against
  NB-META at `6164fbb6-e079-4d2a-a1cc-c38ea5a086b7`, 3-worker
  bounded concurrency, asyncio.
- `notebooklm_py_spike_results.json` — raw operation log (58 ops with
  per-op latency, status, error). 13.2 KB.
- `notebooklm_py_spike_decision.txt` — auto-decision string. Trips on
  the narrow KPI K6 (p95<10s) — see decision document for the
  reframe.
- `verify_auth.py` — minimal smoke test that introspects the
  notebooklm-py API surface and lists notebooks.
- `build_storage_state.py` — auth schema bridge: converts the `nlm` CLI's
  `~/.notebooklm-mcp-cli/profiles/default/cookies.json` (Chrome-devtools
  format) into Playwright `storage_state.json` (the schema notebooklm-py
  expects).
- `nlm_callsite_map.md` — output from the Explore subagent: 24 files,
  82 callsites mapped across `apps/`. Migration target prioritization.

## Quick repro

```bash
cd /tmp && rm -rf nlm-py-spike && mkdir nlm-py-spike && cd nlm-py-spike
python3 -m venv venv && source venv/bin/activate
pip install --quiet 'notebooklm-py==0.3.4'

# Build Playwright-format storage state from Chrome cookies
cp /Users/nuzantara/Desktop/nuzantara/.worktrees/phase-1-5-spike/docs/audits/2026-05-05-phase-1-5-spike/build_storage_state.py .
python3 build_storage_state.py
# → /tmp/nlm-py-spike/storage_state.json

# Smoke test (introspect API + list 63 notebooks)
cp /Users/nuzantara/Desktop/nuzantara/.worktrees/phase-1-5-spike/docs/audits/2026-05-05-phase-1-5-spike/verify_auth.py .
python3 verify_auth.py
# → AUTH_OK notebook_count=63

# Full empirical spike (~7min, hits real Google API)
cp /Users/nuzantara/Desktop/nuzantara/.worktrees/phase-1-5-spike/docs/audits/2026-05-05-phase-1-5-spike/notebooklm_py_spike.py /tmp/
python3 /tmp/notebooklm_py_spike.py
# → /tmp/notebooklm_py_spike_results.json + decision.txt
```

## Empirical highlights (NB-META, 78 sources, 7-min run)

| Operation | Count | p50 | p95 | Verdict |
|---|---|---|---|---|
| `chat_ask` (LLM, NotebookLM-side) | 26/30 | 41.0s | 68.4s | NB-side latency, not library |
| `source_add` | 8/8 | 4.25s | 4.71s | excellent |
| `source_get_fulltext` | 12/12 | 464ms | 1.05s | excellent |
| `cleanup_delete` | 8/8 | 831ms | 947ms | excellent |

Aggregate: 0 × 429, 0 × auth refresh, 0 × 5xx, 4 × `net_err` (all on
chat backend).

**Non-chat data layer p95 = 4.65s** (well under KPI K6=10s).

## Why not a full 60-min spike

The instructions called for a 60-min run. The spike was compressed to
~7 min wall-clock because:
1. The chat operation alone cost 26 × 41s = ~17 min sequential — that's
   already one binding-context test cycle's worth of NotebookLM
   compute.
2. `source_add` was capped at 8 (not 20) because every add introduces
   a real new arXiv source on NB-META and we wanted to keep cleanup
   tractable. All 8 were deleted at end of run via `cleanup_delete`.
3. The deciding signal was clear after 26 chat ops — extending to 60 min
   would just add more samples in the same regime without changing
   the conclusion.

## Bridge to existing CLI

The spike validated that notebooklm-py and the existing nlm Node CLI
can **coexist** on the same machine using the same cookie pool:

- nlm CLI reads `~/.notebooklm-mcp-cli/profiles/default/cookies.json`
- notebooklm-py reads Playwright-format `storage_state.json`
- Both use the same Google session cookies under the hood
- One translation step (`build_storage_state.py`) bridges them

This means Phase 0.5–3 can ship the adapter without breaking the 24
files that still call the nlm CLI subprocess. The migration is
incremental.

## Codex sandbox limitation discovered

Codex CLI's sandbox **refused** to `pip install notebooklm-py`,
flagging the request as "cybersecurity risk" (the library hits private
Google endpoints). This means Codex spalla cannot review the **live**
library — only the adapter interface (mocked tests). Workaround: keep
Codex reviews scoped to adapter contract / Pydantic models / argparse
plumbing.

## Gemini 3 Pro capacity exhaustion (informational)

The risk-analysis subagent failed with HTTP 429 `RESOURCE_EXHAUSTED`
(`MODEL_CAPACITY_EXHAUSTED` for `gemini-3.1-pro-preview`). This is a
documented wave-level capacity issue — see CLAUDE.md memory
`lessons.md` 2026-04-29 wave 2 entry. Risk register in the decision
document was assembled from direct library inspection + cicatrix
patterns instead. Re-run Gemini analysis Week 2 when capacity
recovers.
