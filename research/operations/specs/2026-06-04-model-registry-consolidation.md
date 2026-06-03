---
date: 2026-06-04
domain: operations
client_case: none
status: DRAFT — pending 4-LLM panel review + Antonello approval
author: Claude Opus 4.8 (Air-M5 session)
sources:
  - census subagent 2026-06-04 (empirical grep Pro/Mini, ~90 hardcode sites)
  - MODEL_TOPOLOGY.json + scripts/model_topology.py (existing registry)
  - drift fix PR #1091 (translation role)
---

# Spec: Model Registry Consolidation — single source of truth for Ollama models

## 1. Problem (empirically verified 2026-06-04)

A registry **already exists** (`MODEL_TOPOLOGY.json` + loader `scripts/model_topology.py::get_role`),
but only **4 files** import it while **~90 files + 2 LaunchAgent plist hardcode** the model
string inline. Result: silent drift and ghost models.

Concrete failures found:
- `translation` role named `gemma4:e4b` (NOT installed); script default `gemma4:26b` (NOT
  installed); plist forced `gemma3:27b` (the only gemma on disk). Cron worked only by luck.
  → fixed in PR #1091 for the `translation` role ONLY.
- `cron_fallback` = `gemma4:e4b` and `kg_json`/`cell_tier1` = `gemma4:26b` STILL name a
  non-installed model. Any consumer that actually pins/pulls these would fail.
- Backend has TWO independent copies of the same 4 roles: `llm/config.py:33-37` and
  `llm/ollama_client.py:29-32`.

Root cause class: same family as cicatrix "deploy-path desync" — N sources believe a
different world-state, drift is silent until a visible thing breaks.

## 2. Goal

The model used by any automation is decided in ONE place (`MODEL_TOPOLOGY.json`), every
consumer reads it via `get_role(...)`, and a pre-flight check refuses to run (or alerts)
when the named model is not actually installed — instead of failing mute.

Non-goals: touch the FROZEN OpenAI RAG embedding (`text-embedding-3-small`, §9 invariant) —
out of scope, not Ollama. No model quality changes (separate decisions).

## 3. The 5 canonical roles (consolidate ~90 sites into these)

| role | current value(s) | consumers (examples) |
|---|---|---|
| `ocr_vision` | qwen2.5vl:7b (→ qwen3-vl:8b pending) | crm_guardian/ocr:58, pdf_vision:45, vision_rag:210, image_handler:13, config VISION |
| `intake_extraction` | qwen3.5:9b + fallback qwen3:8b | wa_copilot/extraction:53-54, crm/enrichment:209, ner_worker:36 |
| `classification` | qwen3.5:9b / qwen3:8b | classifier_worker:36, scorer:125, federation:118, wa-mirror:52, organism:47 |
| `translation` | gemma3:27b (fixed #1091) | translate-articles.py:24, plist translate.hourly |
| `reasoning` + `kg_json` | deepseek-r1:32b / gemma4:26b(ghost!) | cell/reasoner:60-61, ollama_client HEAVY/KG |

(+ optional `embedding_ollama` = nomic-embed-text for mata-garuda intel, distinct from RAG.)

## 4. Design

### 4.1 Registry as single source (extend, don't replace)
Keep `MODEL_TOPOLOGY.json`. Reconcile every `gemma4:*` ghost to an installed model (verify
with `ollama list` on Pro AND Mini). Add a `min_ram_gb` + `installed_on` hint per role
(optional, for the pre-flight).

### 4.2 Python consumers
Replace each hardcoded constant with `from scripts.model_topology import get_role` →
`get_role("ocr_vision")`. For the backend, make `OllamaModel.VISION = get_role("ocr_vision")`
so `config.py` and `ollama_client.py` collapse to one source. Keep
`os.environ.get("OLLAMA_MODEL", get_role(...))` as a per-job override escape.

### 4.3 Plist / shell consumers
Remove inline `<key>OLLAMA_MODEL</key>`. In the wrapper script:
`export OLLAMA_MODEL=$(python3 -c "import scripts.model_topology as m; print(m.get_role('translation'))")`
(pattern already used correctly by `~/scripts/ollama-warm-pin.sh` — the template to replicate).

### 4.4 Pre-flight model-exists check (the "automatismo di sistema")
A small helper `get_role_checked(role)`:
1. read role from registry,
2. query `ollama list` (cache 5 min),
3. if model present → return it,
4. if absent → try the role's declared fallback, else raise + Telegram alert
   "role X wants model Y, not installed on <host>".
This is what makes model-swap a system concern, not a manual plist edit.

### 4.5 CI guard (anti-regression)
`tests/integration/test_model_topology_consistency.py`:
- fail if any `.py`/`.sh`/`.plist` hardcodes an Ollama-model string not present as a registry
  value (allowlist exceptions inline);
- fail if a registry value is not in the union of `ollama list` from Pro+Mini snapshot
  (snapshot committed, refreshed by cron).

## 5. Rollout (incremental, reversible)

- **Phase 0** (done): PR #1091 — translation role reconciled.
- **Phase 1**: reconcile remaining ghosts (`cron_fallback`, `kg_json`) to installed models;
  add `get_role_checked`. No consumer rewrites yet. Low risk.
- **Phase 2**: migrate backend `config.py`+`ollama_client.py` to `get_role` (collapse the 2
  copies). Targeted pytest from CLAUDE.md §11.
- **Phase 3**: migrate the worker/script consumers role-by-role (vision, then classification,
  then intake). One PR per role, each independently revertible.
- **Phase 4**: plist wrappers read from registry; add CI guard; flip it to blocking.

## 6. Risks
- A consumer migration that changes the effective model (e.g. a worker that was silently on a
  different model than the registry says) could change behavior. Mitigation: per-role PR +
  diff the before/after model string, call out any change explicitly.
- `ollama list` query latency in hot path → cache + only at process start, never per-request.
- §9 invariant "vision = qwen2.5vl ONLY" is hardcoded in CLAUDE.md; updating vision role to
  qwen3-vl requires updating that invariant in the same PR (else hook/doc conflict).

## 7. Open questions for the panel
1. Should `get_role_checked` hard-fail or degrade-to-fallback by default? (SYMBIOSIS Law 4 =
   graceful degradation suggests fallback + alert, not hard-fail.)
2. Is committing an `ollama list` snapshot for CI acceptable, or should the guard only check
   "hardcode ∈ registry values" and leave install-existence to runtime?
3. Per-role PR (4 PRs) vs one big migration PR — preference?

---

## 8. Panel review (Codex GPT-5.5, 2026-06-04) — 8 findings recepiti

DeepSeek V4 Pro panelist returned empty (`finish_reason=length`, all budget in
`reasoning_content` — the SAME reasoning-model bug as the evoskill scorer; needs
high max_tokens). Gemini `agy` OAuth expired under ssh. Codex was the live panelist.

Findings ACCEPTED into the design:

1. **`import scripts.model_topology` is a fragile runtime dep** (CWD/PYTHONPATH/venv differ
   across plist/cron/container). → Resolution must NOT be `python3 -c "import scripts..."` in
   a plist. Options: (a) a tiny standalone resolver binary with no repo-path dependency, or
   (b) generate a flat `~/.nuzantara-models.env` from the registry via cron, sourced by
   wrappers. Decide before Phase 4.

2. **Per-HOST validation, not Pro∪Mini union.** A model on Pro but not Mini must FAIL the
   check for Mini consumers. Registry needs `installed_on: [pro, mini]` per role and CI/runtime
   checks per host.

3. **Fail-closed for structured roles.** ocr_vision / kg_json / intake_extraction produce
   schema'd output — a silent fallback to a different model can emit malformed JSON. These
   roles fail-closed + alert. Only "soft" roles (e.g. translation) degrade-to-fallback.
   → Answers Open Q1: NOT graceful-by-default; per-role policy field.

4. **`OLLAMA_MODEL` override is a new drift channel** → must be logged/audited; allowed only
   for explicitly allowlisted jobs, blocked elsewhere in CI.

5. **Hardcode scanner is noisy/incomplete** (YAML, .env, Docker, .service, JS/TS escape it;
   false positives → people bypass). → Scope scanner to .py/.sh/.plist only, accept it's a
   helper not a guarantee, pair with runtime trace (finding 8).

6. **`ollama list` proves only the tag exists**, not health/context/quant/memory-fit/loadable.
   → Pre-flight should do a 1-token load probe, not just list-membership.

7. **Registry values alone insufficient** → add role-contract fields: output_mode (text/json),
   vision (bool), json_reliability, fallback_policy (fail-closed|degrade), allowed_hosts,
   min_ram_gb.

8. **Missing rollout step (biggest)**: a before/after runtime trace proving every migrated
   consumer resolves the SAME effective model string. → New Phase 2.5: instrument
   `get_role` to log resolved model per consumer; diff before vs after each migration PR.

### Revised role schema (per finding 7)
```json
"translation": {
  "model": "gemma3:27b",
  "output_mode": "text",
  "vision": false,
  "fallback_policy": "degrade",
  "allowed_hosts": ["pro"],
  "installed_on": ["pro"]
}
```
(was a bare string; now a contract object — migration must keep `get_role` returning the
string for backward-compat, e.g. `get_role(r)` returns `.model`, `get_contract(r)` the object.)

### Verdict
Spec direction sound; rollout NOT ready as-was. Blockers before Phase 1: per-host validation,
fail-closed policy per role, resolver-without-repo-import. Phase 0 (PR #1091) stands.
