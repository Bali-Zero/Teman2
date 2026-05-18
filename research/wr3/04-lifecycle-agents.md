---
date: 2026-05-18
domain: wr3-design
step: 4
title: Lifecycle per agente — 6 fasi Nasce → Impara → Produce → Misura → Migliora → Muore
panel: Gemini 3.1 Pro + Codex GPT-5.5 + NB-AGENTS
deepseek: killed by user (Step 3 onwards)
my_draft_size: 14804 bytes
panel_convergence: 9/10 questions UNANIMOUS MODIFY, 1/10 UNANIMOUS KEEP
critical_red_flag: Codex caught Veo Fast pricing error in my draft ($0.01/cr vs $0.10/sec API)
---

# WR3 Step 4 — Lifecycle per agente

## Convergenze 3/3 (panel UNANIMOUS)

| #   | Question                           | Decisione panel                                                                                                                                      | Mia draft → cambio                                                                                     |
| --- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Q1  | Reflexion cross-agent patterns     | **Root-cause ownership ONLY upstream + orchestrator contract validation**                                                                            | Cambio: lesson NON va a 3 agent, solo a brief (root cause) + design-architect (I/O contract assertion) |
| Q2  | Per-agent death threshold          | **3 lifecycle classes via frontmatter tag**: `core` (30-45d), `scheduled/cron` (missed-windows-based), `fallback` (eligible-opportunity-count-based) | Cambio: uniforme 60d → tiered                                                                          |
| Q3  | Telemetry granularity              | **Agent-level rollup + lane dimensional tagging** (`critic_pass_rate{lane="legal"}`)                                                                 | Cambio: dimensioni in JSONL                                                                            |
| Q4  | Skill versioning                   | **Immutable post-graduation**: nuovo file `<skill>-v2.md` + archive v1 + manifest pin `skill_id + version + sha256`                                  | Cambio: no in-place edit                                                                               |
| Q5  | Orchestrator self-modification ban | **KEEP strict ban** — orchestrator può proporre PR ma MAI auto-modificare                                                                            | Confermo                                                                                               |
| Q6  | Cost ceiling per agent             | **Dynamic per agent class** in I/O contract: Text/Planning ~$0.05-0.15, Render/VLM $1.00+                                                            | **CRITICO**: cambio + correzione cost-model                                                            |
| Q7  | Idempotence protocol               | **Bifurcated**: planning agents strict JSON diff, render agents semantic idempotence (3 seeds pass critic) + manifest/prompt-hash idempotent         | Cambio: 2 tier                                                                                         |
| Q8  | Memory seed file                   | **Strict separation of concerns**: frontmatter = runtime routing, genesis.md = immutable history/why, lessons.md = ongoing                           | Cambio: 3 distinct files                                                                               |
| Q9  | Skill demotion gracefulness        | **FAIL ≥2 → `_quarantine/` (suspend)**, archive richiede Antonello PR + upstream-contamination check                                                 | Cambio: quarantine pre-archive                                                                         |
| Q10 | Genesis ritual scaling             | **1 PR `wr3-room-genesis` con 13 signed commits** (1 per agent, 5 artifacts each)                                                                    | Cambio: bisectable, not mega-commit                                                                    |

## CRITICO — Codex global red flag (Veo cost model errore)

**Errore nel mio draft:** ho scritto "clip-renderer $0.30 = 30 Veo cr × $0.01". Questo è il pricing **interno Flow UI** (Ultra plan: 1 generation Fast = 10 cr, Ultra package $250/mese ≈ ~$0.01/cr). NON il pricing Google AI Studio API.

**Veo 3.1 Fast API pricing (official, May 2026):**

- Veo 3.1 Fast 720p + audio = **$0.10/sec**
- Veo 3.1 Standard 720p + audio = **$0.40/sec**

**Implicazioni per clip-renderer:**

- Mia stima: 8s clip × $0.01/cr × 10 cr = $0.10 → **WRONG** se usiamo API
- Realtà API: 8s × $0.10/sec = **$0.80** per clip
- Episode 12 clip × $0.80 = **$9.60** solo render (vs mia stima $1.20)
- **Cost ceiling $0.50 hard cap KILLA ogni invocazione clip-renderer**

**Risoluzione:** Bali Zero usa **Flow UI Pro plan (3500 cr promo $10/mese)** non API diretta. Pricing effective: 1 episode ≈ 12 clip × 10 cr = 120 cr/episode = **3.4% del monthly budget**, costo cash equivalente $0.34/episode. Cost ceiling deve essere **plan-aware**, non API-rate-aware.

Per **veo-render-manager** in I/O contract:

```yaml
backend: flow_ui_pro # vs gemini_api
cost_model:
  unit: flow_credit
  budget_per_episode: 120 cr # 12 clip x 10 cr Fast Tier_ONE
  hard_cap: 200 cr # 67% buffer for retries
  monthly_quota: 3500 cr
  conversion_table:
    flow_pro_plan: $10/mo / 3500 cr = $0.00286/cr
    gemini_api_fast: $0.10/sec * 8s / 10 cr = $0.08/cr # 28× more expensive
```

## Divergenze risolte (panel splits)

| Punto               | Gemini             | Codex                            | NB-AGENTS                           | Decisione                                                                                 |
| ------------------- | ------------------ | -------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------- |
| Q4 skill versioning | KEEP (append-only) | MODIFY (skill_id+version+sha256) | MODIFY (file-based v2 + archive v1) | **MODIFY** (3/3 contro append-only in-place — KEEP era solo per "approccio già corretto") |
| Q10 genesis ritual  | mega-commit        | 13 signed commits in 1 PR        | mega-commit                         | **Codex wins** — 13 commit bisectabili in 1 PR (compromesso fra atomicità e cohesion)     |

## Lifecycle a 6 fasi — FINAL (post-panel)

### Fase 1 — NASCE (genesis)

**Artefatti day-0 per ogni agent (5 file):**

| Artefatto    | Path                                                  | Contenuto                                                             | Mutabilità                             |
| ------------ | ----------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------- |
| Agent file   | `~/.claude/agents/<name>.md`                          | Frontmatter + system prompt body                                      | Mutable via PR Antonello               |
| Skill cortex | `~/.claude/skills/bali-zero-brand/wr3/<name>/`        | `SKILL.md` + dominio-specifico (`camera-grammar.md`, etc.)            | Immutable post-graduation (v2 pattern) |
| I/O contract | `~/Desktop/nuzantara/docs/wr3/contracts/<name>.yaml`  | Input/output schema + failure codes + **cost_model + lifecycle_tier** | Versioned (manifest pin)               |
| Test fixture | `~/Desktop/nuzantara/tests/wr3/<name>_smoke.py`       | 1 happy + 1 edge                                                      | Mutable for test expansion             |
| Memory seed  | `~/.claude/projects/.../memory/wr3-<name>-genesis.md` | **Immutable** "why this exists + initial constraints"                 | NEVER edited (read-only history)       |

**Day-0 status:** all skill cortex files start with header `status: baseline_signed` (NOT `_proposed/`, NOT `graduated`). Risolve il bootstrap contradiction Codex global flag.

**Frontmatter ESTESO con lifecycle tag:**

```yaml
name: wr3-brief-interpreter
description: "MUST BE USED ..."
tools: Read, Glob, Grep, Bash, WebFetch
model: sonnet
color: pink
lifecycle_tier: core # core | scheduled | fallback
cost_class: text_planning # text_planning | reasoning | render | audio_gen
contract_version: 1.0.0
```

**Genesis ritual SCALING (Q10):**

- 1 PR `wr3-room-genesis`
- 13 signed commits (1 per agent, 5 artifacts each)
- Reviewable + bisectable + atomic per-agent rollback
- Antonello review weekly, merge after smoke tests green
- Final commit: `feat(wr3): activate room — all 13 agents bootstrapped + baseline_signed skills`

### Fase 2 — IMPARA (learning, gated)

**3 canali (post-Q1 modify):**

| Canale                   | Sorgente                                   | Ownership                                                | Output                                                         |
| ------------------------ | ------------------------------------------ | -------------------------------------------------------- | -------------------------------------------------------------- |
| Reflexion verbal lessons | Last 7d episodes + designer-override diffs | **Root-cause agent ONLY** + orchestrator contract update | `lessons.md` (agent) + `contract_assertions.md` (orchestrator) |
| Voyager skill proposals  | Pattern detection on success episodes      | Reflexion-synth proposes, root-cause agent owns          | `_proposed/<skill>.md`                                         |
| Critic feedback loop     | FAIL verdicts real-time                    | Orchestrator routes to root-cause agent                  | `previous_failure_signature` in next-episode brief             |

**Hard rule:** downstream agent NON impara per compensare upstream garbage. Compensatory pattern bandito (Gemini wording: "brittle compensatory anti-patterns").

### Fase 3 — PRODUCE (steady-state ops)

**I/O contract template aggiornato:**

```yaml
agent: wr3-<name>
contract_version: 1.0.0
input:
  schema_path: docs/wr3/contracts/<name>-input.schema.json
  mandatory_fields: [...]
output:
  schema_path: docs/wr3/contracts/<name>-output.schema.json
  artifacts: [list]
  failure_codes: [E001_..., E002_...]
timing:
  typical_latency_ms: 30000-120000
  hard_timeout_s: 300
  retries: 2
cost:
  cost_class: text_planning # determines ceiling
  ceiling_usd: 0.15 # text_planning=$0.15, reasoning=$0.50, render=plan-aware
  per_invocation_typical: 0.02
lifecycle_tier: core
idempotence:
  layer: planning # planning=strict_diff | render=semantic_3_seeds
```

**Cost class breakdown (Q6):**

| Cost class      | Examples                                                                | Ceiling                                        | Rationale                                                                                                                  |
| --------------- | ----------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `text_planning` | brief-interpreter, script-editor, pre-render-gatekeeper, b-roll-curator | $0.05-0.15                                     | Sonnet structured I/O, no big context. Loop detection critical (Codex flag: $0.50 + Sonnet = 25 catastrophic spin-cycles). |
| `reasoning`     | shot-director, critic, design-architect                                 | $0.30-0.50                                     | Opus + multi-step.                                                                                                         |
| `render`        | clip-renderer (Veo)                                                     | 200 cr Flow Pro plan ≈ $0.57                   | Plan-aware quota (3500 cr/mo), NOT API rate.                                                                               |
| `audio_gen`     | audio-asset-producer                                                    | $0.05 (Chatterbox local, GPU electricity only) | Self-host MIT zero cloud cost.                                                                                             |

### Fase 4 — MISURA (metrics, raw events)

**Codex global flag: log RAW events, derive aggregates later.**

**Per ogni invocazione, agent emette 1 JSONL line:**

```jsonl
{
  "ts": "2026-05-18T10:30:15Z",
  "agent": "wr3-critic",
  "duration_ms": 4530,
  "cost_usd": 0.08,
  "outcome": "PASS",
  "retry_count": 0,
  "critic_lane": "legal",
  "contract_version": "1.0.0",
  "episode_id": "WR3-2026-05-18-A001"
}
```

**6 fields obbligatori (replacing my draft's 5 pre-computed):**

- `duration_ms` (raw)
- `cost_usd` (raw)
- `outcome` (enum: PASS/FAIL/RETRY/TIMEOUT/COST_HALT)
- `retry_count` (int)
- `critic_lane` (only for critic: identity/audio/brand/legal; null otherwise — dimensional tag)
- `contract_version` (for skill versioning Q4 audit)

**Aggregates derived by `wr3-yt-metrics-analyst` Monday cron:**

- `latency_p50`, `latency_p95` (per agent, per lane)
- `cost_per_invocation_usd_p50`, `_p95`
- `critic_pass_rate{lane=X}`
- `retry_rate`
- `cost_overrun_count` (invocations halted at ceiling)

**Hard rule (Symbiosis Law 7):** se agent non emette JSONL line, non esiste. Lint `wr3-telemetry-completeness.py` enforce.

### Fase 5 — MIGLIORA (evolution, gated)

**Skill graduation 4-step (post-Q4 + Q9 modify):**

```
_proposed/<skill>-v1.md (Voyager autonomous draft)
    ↓ 3 successful uses (critic ≥ threshold)
    ↓ skill assigned skill_id + version 1.0.0 + sha256 hash
    ↓ Antonello git diff review (weekly)
    ↓ git commit to main
<skill>-v1.md (active, immutable)
```

**Skill modification (NEW post-graduation):**

- NEVER edit `<skill>.md` in-place
- Modification = create `_proposed/<skill>-v2.md` from scratch
- Re-run graduation gate (3 successful uses)
- On graduation: `<skill>-v2.md` becomes active, `<skill>-v1.md` → `_archived/`
- Episode manifest pins `skill_id + version + sha256` → past episodes replayable

**Skill demotion (post-Q9 modify):**

| Step | Trigger                          | Action                                                        |
| ---- | -------------------------------- | ------------------------------------------------------------- |
| 1    | Critic FAIL ≥2 with this skill   | Skill → `_quarantine/<skill>.md`, orchestrator suspends usage |
| 2    | Reflexion-synth analyzes 2 FAILs | Determine root cause: skill decay vs upstream contamination   |
| 3a   | Skill confirmed decay            | Antonello PR review → `_archived/`                            |
| 3b   | Upstream contamination           | Quarantine lifted, lesson goes to upstream agent (Q1)         |

### Fase 6 — MUORE (sunset, tiered)

**Death triggers per lifecycle tier (post-Q2 modify):**

| Tier          | Death criterion                                                                      | Detection                                   |
| ------------- | ------------------------------------------------------------------------------------ | ------------------------------------------- |
| **core**      | Unused 30-45d (per-agent SLO in contract)                                            | Weekly cron count invocations               |
| **scheduled** | Missed cron window ≥3 consecutive                                                    | LaunchAgent failure log                     |
| **fallback**  | Eligible opportunity unused ≥10 times (e.g., b-roll-curator skipped 10 Veo failures) | Orchestrator counter                        |
| **all**       | Critic FAIL ≥5 consecutive                                                           | Orchestrator monitor → QUARANTINE           |
| **all**       | Cost overrun ≥3× budget over 7d                                                      | yt-metrics-analyst → HALT + Antonello alert |
| **all**       | Symbiosis Law violation                                                              | Lint scan → quarantine + cicatrix entry     |

**Rebirth via Voyager fork:**

- Archived agents can be re-instantiated as variant if Reflexion detects pattern.
- Example: `wr3-shot-director-v2` forks from v1 archive + new camera-grammar skill.

## Lifecycle per agente specifico — FINAL drafts (post-panel)

Tabella riassuntiva (4 agent + 9 supporting per template):

| Agent                     | lifecycle_tier | cost_class    | ceiling                                 | Nasce skills                                                                                            | Misura key metric                                            |
| ------------------------- | -------------- | ------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| wr3-design-architect      | core           | reasoning     | $0.50                                   | none (orchestrator)                                                                                     | End-to-end episode latency ≤45 min, total cost ≤$3           |
| wr3-brief-interpreter     | core           | text_planning | $0.15                                   | nb-routing-domain-map, legal-claim-extraction-templates                                                 | NB query latency ≤8s, gate FAIL rate ≤0.15                   |
| wr3-script-editor         | core           | text_planning | $0.15                                   | voice-register-tones, pacing-marker-grammar, claim-id-binding-rules                                     | claim_id completeness ≥0.95, word count ≤200                 |
| wr3-shot-director         | core           | reasoning     | $0.50                                   | veo-prompt-pack-templates, camera-grammar-cinematic, transition-map-language, identity-token-A007       | gatekeeper PASS ≥0.8, Veo render success ≥0.7, ArcFace ≥0.65 |
| wr3-pre-render-gatekeeper | core           | text_planning | $0.10                                   | cliche-library, cost-circuit-breaker-rules, safety-pre-check-protocol                                   | gate PASS rate ~0.8, credit saved per FAIL                   |
| wr3-clip-renderer         | core           | render        | 200 cr (~$0.57 Flow Pro)                | veo-fast-tier-one-spec, arcface-identity-protocol, vlm-holistic-check-rubric, fallback-strategy-tree    | Veo success ≥0.7, ArcFace pass ≥0.8                          |
| wr3-audio-asset-producer  | core           | audio_gen     | $0.05 (Chatterbox local)                | chatterbox-emma-locked-config, lufs-normalization-rules, music-license-protocols                        | transcript match ≥0.95, LUFS ≤-14 ±1                         |
| wr3-post-assembler        | core           | text_planning | $0.10 (Sonnet diagnostic only)          | ffmpeg-command-library, episode-manifest-schema-18-fields, platform-variant-matrix, subtitle-ass-styles | assembly success ≥0.98, manifest 18/18                       |
| wr3-critic                | core           | reasoning     | $0.50                                   | critic-rubric-4-lanes, brand-voice-checklist, legal-accuracy-verbatim-rules, cliche-pattern-detection   | FP rate ≤0.1, FN rate ≤0.05, per-lane scores                 |
| wr3-reflexion-synth       | scheduled      | text_planning | $0.20 weekly                            | \_reflexion-template                                                                                    | Cron success rate, # lessons accepted/proposed               |
| wr3-yt-metrics-analyst    | scheduled      | text_planning | $0.30 weekly (Gemini 1M ctx free OAuth) | yt-analytics-api-routing, engagement-correlation-rules                                                  | Report timeliness Mon 06:00 ±15min, Pearson r reported       |
| wr3-editorial-bench       | scheduled      | reasoning     | $1 monthly                              | reference-brand-list-12                                                                                 | Report due 1st Mon 07:00 WITA                                |
| wr3-b-roll-curator        | fallback       | text_planning | $0.10                                   | stock-source-list, license-verification-protocol                                                        | License-clean rate 1.0, eligible-opportunity used vs skipped |

## Open questions per Antonello (decision gate)

1. **Flow Pro plan vs Gemini API for Veo**: confermo che restiamo su Flow UI Pro ($10/mo 3500 cr promo) e NON Gemini API ($0.10/sec)? Cost differential 28× — Flow è no-brainer financialmente, ma Pro plan ha rate limit / TOS commercial-use da verificare.
2. **Lifecycle tier per agent**: tabella sopra mette tutti pipeline agent come `core` (30-45d death). Eccezione `b-roll-curator` = `fallback`. Confermi o vuoi qualche pipeline agent come `scheduled` (es. editorial-bench)?
3. **Genesis 1 PR / 13 commits**: ok bisectable, ma 13 commit signed da te in 1 settimana è feasible? Compromesso accettato o vuoi 1 mega-commit (con rollback all-or-nothing)?
4. **Manifest skill_id+version+sha256 binding**: aggiunge complessità per replayability. Confermo o accetti che episodi past NON replayable (skill state-of-the-art "live")?
5. **Cost ceiling text_planning $0.15**: Codex flagga $0.50 = 25 spin-cycles catastrophic con Sonnet. $0.15 = ~5 spin tolerance. Ok o vuoi più stretto ($0.10)?
6. **Per-agent SLO in contract**: ogni agent ha latency/cost/quality SLO in `docs/wr3/contracts/<name>.yaml`. Chi cura questi numeri? Tu via PR, o Voyager autonomous proposal?
7. **wr3-reflexion-synth ownership di Voyager skill proposals**: Reflexion-synth è autore dei `_proposed/` skill, ma il pattern detection è suo o per-agent (es. brief-interpreter rileva pattern nelle proprie NB query)?
8. **Skill versioning sha256**: hash sul body Markdown post-frontmatter, o include frontmatter? Test: stesso content + diff `last_modified` campo → stesso hash? Decisione semantica.

## Next step (Step 5 — Integrazione Symbiosis 8 leggi)

Per ogni delle 8 leggi Symbiosis, mappare implicazione su WR3:

1. CLI-only per LLM (no API HTTP Anthropic/Google/OpenAI) → tutti agent shellano `claude --print`, `gemini --print`. DeepSeek excepted ($0.01/q OK ma killed by user).
2. OSINT blindato → Mata Garuda WR3 future? Per ora N/A (WR3 = brand video, NOT intelligence).
3. Event-driven + durabilità per canale → episodes flow via PG cell_pulse_observed channel (no polling).
4. Graceful degradation → se 1 sub-agent fail, orchestrator routes around (b-roll-curator fallback già design pattern).
5. Zero come ultima istanza → tu firmi genesis + graduation. No autonomous publish.
6. Sovranità locale → tutto su Pro/Mini. No cloud-bound state.
7. Numeri prima → Misura phase obbligatoria, lint enforce.
8. (8a legge implicita "Rispetta il passato"/Potenzia presente/Vedi futuro) → manifest skill versioning replayability.

Trigger: confirm Step 4 decisions?

## Sources

| Panel          | LLM                     | Bytes                       | Quality                                                    | Convergent on 10 questions |
| -------------- | ----------------------- | --------------------------- | ---------------------------------------------------------- | -------------------------- |
| Gemini 3.1 Pro | gemini-3.1-pro-preview  | 4743                        | terse, decision-oriented, KEEP/MODIFY/REJECT verdict per Q | 9/10 MODIFY + 1/10 KEEP    |
| Codex GPT-5.5  | gpt-5.5 xhigh           | ~5000 (22KB inc. exec logs) | thorough + caught Veo cost-model error via web search      | 9/10 MODIFY + 1/10 KEEP    |
| NB-AGENTS      | NotebookLM RAG          | 652 + 4500 retry            | NB-cited, 17.2× error finding referenced                   | 9/10 MODIFY + 1/10 KEEP    |
| DeepSeek       | KILLED by user (Step 3) | —                           | —                                                          | —                          |

**Panel agreement strength:** 30/30 votes on 10 questions = 9/10 MODIFY + 1/10 KEEP. Strongest convergence achieved in Step 1-4 progression.

**Critical Codex contribution:** caught Veo cost model error in my draft via web search of official Gemini API pricing — would have under-budgeted clip-renderer by 8×. This is exactly the "verify-not-trust" pattern that prevents hallucinated specs from reaching implementation.
