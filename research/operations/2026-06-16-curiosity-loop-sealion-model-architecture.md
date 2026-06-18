---
date: 2026-06-16
domain: operations
client_case: none (internal infra — curiosity_loop knowledge-gap pipeline)
sources:
  - https://docs.sea-lion.ai/models/sea-lion-v4
  - https://huggingface.co/aisingapore/Apertus-SEA-LION-v4-8B-IT
  - https://ollama.com/aisingapore
  - https://aclanthology.org/2025.findings-acl.636.pdf (SEA-HELM, ACL 2025 Findings)
  - https://www.gotocompany.com/en/news/press/indosat-ooredoo-hutchison-and-goto-launch-sahabat-ai-indonesias-open-source-llm-for-empowering-digital-sovereignty
  - https://ollama.com/Supa-AI/llama3-8b-cpt-sahabatai-v1-instruct
  - https://ai-desk.tech/blog/mac-mini-m4-pro-ollama-benchmark
  - https://github.com/ollama/ollama/issues/11949 (KV cache quant throughput regression)
  - https://arxiv.org/pdf/2401.15884 (Corrective RAG / CRAG)
  - https://arxiv.org/pdf/2312.11462 (speculative cascades)
---

# curiosity_loop — SEA-LION model + architecture decision (2026-06-16)

## Problem (measured, not inferred)

curiosity_loop's Tier-1 `SimpleDispatcher` calls `aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m`
via local Ollama on the Pro (M4 Pro 48GB), `OLLAMA_TIMEOUT=240`. A real run measured SEA-LION
generating at **~4.2 tok/s under daytime contention** (load avg 15→29 from 7 interactive Opus
agents + Codex + next-server): `eval_duration=291.9s for 1242 tokens` with the model already
**warm** (`load_duration=0.1s`) — i.e. the single generation alone exceeds the 240s timeout.
An intermittent **+48s cold-reload** lands when another cron (gemma3:27b / qwen3.5:9b) evicts
SEA-LION (no keep-alive pin; eviction suspects = `deepseek-r1:32b` + `gemma4:26b` in the
backend-rag H24 daemon). The PR #1506 benchmark of 121s was almost certainly on an idle machine.

Crucially: the pipeline **degrades gracefully** — even with every SEA-LION call timing out, the
two observed runs finished `errors=0` and produced 7 and 5 real proposals (timeout → web/template
fallback, never a dead cycle).

## Axis 1 — Model choice (Indonesian accuracy × speed)

The load-bearing data point (SEA-HELM, ACL 2025 Findings): on the overall normalized SEA score,
the SEA-tuned **9B** (`gemma2-9b-cpt-sea-lionv3-instruct`) scores **63.2** vs the 27B's **65.4** —
a ~2.2-point gap, and the 9B "performed the best of all evaluated models" on SEA instruction-following.
The gap is concentrated in raw reasoning, **not** in the Indonesian regulatory terminology
(BKPM / UU-PP-Perpres lexicon) that SEA-LION was chosen for — and that terminology comes from the
SEA tokenizer + ID instruction data, which the 9B shares.

Smaller SEA-tuned options that keep ID strength:
- **`aisingapore/Gemma-SEA-LION-v3-9B-IT`** (Gemma2-9B lineage, documented ID strength) — recommended.
- **Sahabat-AI 9B** (`Supa-AI/gemma2-9b-cpt-sahabatai-v1-instruct`, GoTo/Indosat) — ~448k extra ID
  instruction pairs on the same base; maximum ID specialization. Worth a 5-10 query A/B vs the above.
- **Avoid** `Apertus-SEA-LION-v4-8B-IT` (newest, but weak Western base, unproven for ID regulatory text).

Speed on M4 Pro (uncontended, Ollama Q4_K_M): 32B ≈ **19 tok/s**; 9B ≈ **55-68 tok/s** — a ~3x
speedup that turns the 1242-token answer from ~291s into **~20-25s**.

## Axis 2 — Architecture under contention

- **Mini-routing** (`CURIOSITY_OLLAMA_URL` → Mini's Tailscale IP) is trivial to wire and already
  supported (`simple.py:62`). BUT a 32B-q4 (~19GB) will **not** co-fit on the 24GB Mini alongside
  its embed/vision models → forces eviction churn. A **9B (~6-8GB) co-fits** — so Mini-routing is
  worth it *only* paired with the smaller model. This independently pushes toward 9B.
- **Ollama knobs**: `keep_alive` pinning + `OLLAMA_NUM_PARALLEL=1` + `OLLAMA_MAX_LOADED_MODELS=1`
  reliably help a once-nightly batch (eliminate cold-load, give all bandwidth to one job).
  `num_predict` caps worst-case length. **Caveat**: `OLLAMA_KV_CACHE_TYPE=q8_0` is a *memory* knob
  that can *halve* Gemma throughput on Apple Silicon (ollama #11949) — leave at default for a 9B.
  None of these knobs give 3x; the model-size change does.
- **The pattern is recognized**: "small local draft → web-ground → cloud/large re-synthesis" is a
  hand-rolled **CRAG** (arxiv 2401.15884) / Speculative-RAG / speculative-cascade. The literature
  **endorses a small cheap drafter** — so shrinking the local model is architecturally correct, not a
  degradation, *precisely because* Exa-verify + resynth repair the reasoning gap downstream.

## Decision (conservative — gated on missing data)

The cron runs **04:30**; all observed timeouts were **daytime manual runs**. There is **zero 04:30
data** (cron armed 2026-06-16 08:14; first real run 17/06). Changing the model now would be premature
optimization on a system that already produces output (errors=0).

**Shipped 2026-06-16 (low-risk, reversible, no code):** `CURIOSITY_OLLAMA_TIMEOUT=240→600` in the
curiosity plist EnvironmentVariables (backup `.bak.pre-timeout`, reloaded). A no-SLA nightly job can
afford a slow SEA-LION far better than degrading to web/template.

## Checklist — decide AFTER the 17/06 04:30 run

- [ ] Read `~/logs/cron/curiosity-loop.log` for the `2026-06-17 04:30` entry; count `timed out` lines + tok/s.
- [ ] If 04:30 is quiet and SEA-LION finishes <600s → **stop, no model change** (timeout bump sufficient).
- [ ] If 04:30 ALSO starves (6 crons share the 04:30 slot, spawning claude/agy/codex CPU spikes) →
      swap to `Gemma-SEA-LION-v3-9B-IT` (or Sahabat-AI 9B after A/B) + route to Mini via
      `CURIOSITY_OLLAMA_URL` + `keep_alive` pin + `num_predict≈1500`.
- [ ] Reuse the existing infra: `MODEL_TOPOLOGY.json` warm-pin config + `scripts/ollama-warm-pin.sh`
      (currently INERT — the warm-pin LaunchAgent is archived/not loaded; re-arming is a separate op).

## Reuse-first findings (internal)

~70% of the fix infrastructure already exists in-repo: `CURIOSITY_OLLAMA_URL` env override
(simple.py:62), `MODEL_TOPOLOGY.json` host→model registry with `warm_models_extra` + roles,
`scripts/ollama-warm-pin.sh` (reads warm_models_extra, `keep_alive:-1`), `num_predict` as a standard
pattern in every OTHER Ollama consumer (ollama_client.py, wa_copilot, crm vision) but NOT in
curiosity. The model-swap + Mini-route is config, not new code.
