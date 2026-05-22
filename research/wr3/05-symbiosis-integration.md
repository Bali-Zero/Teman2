---
date: 2026-05-18
domain: wr3-design
step: 5
title: Integrazione Symbiosis 8 leggi → WR3 controls
panel: Gemini 3.1 Pro + Codex GPT-5.5 + NB-AGENTS
deepseek: killed by user (Step 3 onwards)
my_draft_size: ~26000 bytes
panel_convergence: 7/10 UNANIMOUS, 3/10 split 2-vs-1 (all resolved)
key_finding: Cartesia API fallback BANNED (3/3 reject) — Zantara voice degrades a no-VO+music+subtitles, not cloud TTS
---

# WR3 Step 5 — Symbiosis 8 leggi → WR3 controls

## Convergenze 3/3 (panel UNANIMOUS)

| #   | Q                         | Verdict    | Key rationale                                                                                                                                                                                                                                                                                                                       |
| --- | ------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | Q2 NB OSINT boundary      | **MODIFY** | Verbatim regulatory text è public domain (fair use) — MA da public/legal cache + domain NBs (NB-2..NB-7), NON da raw NB-INTEL OSINT family notes/source_ids/sintesi (NB-INTEL = OSINT cron feed, NEVER consumed by brief-interpreter for grounding). Codex sharpens: privato NB context, annotations, synthesis MAI escono dal Pro. |
| C2  | Q3 channel granularity    | **MODIFY** | Consolidare strictly linear states: `brief_ready` + `script_frozen` → `pre_render_ready` (purché `wr3-script-editor` salvi frozen script state durably). Retain granularity solo su fan-out paralleli e gate human-in-loop.                                                                                                         |
| C3  | Q4 hard-fail completeness | **MODIFY** | Variant ffmpeg fail = degrade (deliver master without variants). Master assembly fail = hard-fail. Veo 100% fail = degrade a still-image fallback.                                                                                                                                                                                  |
| C4  | Q5 Telegram P0/P1/P2      | **KEEP**   | Strict triage: P0=halt episode (immediate), P1=quarantine agent (daily batch), P2=weekly digest. Preserva attention bandwidth Antonello.                                                                                                                                                                                            |
| C5  | Q6 Cartesia fallback      | **REJECT** | **3/3 BAN cloud TTS for Zantara voice.** Degrade a no-VO + music + subtitles only. Cloud TTS = sovereignty breach Law 6 unless per-episode Antonello exception.                                                                                                                                                                     |
| C6  | Q8 cicatrix citation      | **KEEP**   | Forces structural memory. Cross-domain inheritance valid: wr3-shot-director cita WR2 pre-render gatekeeper scar as "visual prompt must be gated before paid render".                                                                                                                                                                |
| C7  | Q10 Law versioning        | **KEEP**   | 8 laws = immutable organism constitution. Law 9 propose path: collect repeated measured evidence (Law 7) → Antonello manual git-commit PR (Law 5).                                                                                                                                                                                  |

## Divergenze 2-vs-1 (resolved by majority + best argument)

| #   | Q                         | Gemini                         | Codex                                                       | NB-AGENTS                                   | Decision                                                                                                                                                                                                                        |
| --- | ------------------------- | ------------------------------ | ----------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Q1 cascade hot-path       | HARD-FAIL hot-path             | MODIFY (cascade non-gating only)                            | MODIFY (cascade per graceful degrade)       | **MODIFY + Codex clarification**: cascade SI per CRON + non-gating content agents; **NO** per `wr3-design-architect` (root-of-trust) e `wr3-pre-render-gatekeeper` (spend gate). Law 5/7 trumps Law 1 fallback per root + gate. |
| D2  | Q7 metric_delta exemption | REJECT (strict)                | MODIFY (proxy metrics OK)                                   | MODIFY (sustained pass-rate OK)             | **MODIFY**: no exemption, MA allow qualitative-to-proxy metrics per micro-skills. Es: "pronunciation correction reduces critic phonetics fails by N" è ammissibile under Law 7.                                                 |
| D3  | Q9 cross-legge precedence | Truth (Law 7) > Uptime (Law 4) | OSINT/privacy > Zero approval > metrics/legal > degradation | Law 4 wins with downgrade critic legal lane | **Codex wins** — explicit precedence chain: `Law 2 OSINT > Law 5 Zero > Law 7 numeri/legal-proof > Law 4 graceful degradation`. Orchestrator arbitrates. NB-down episode → routed to draft-only, NOT legal-passed.              |

## Synthesis: 8 leggi → WR3 controls FINAL

### Legge 1 — CLI-only per LLM

**Declinazione:** Tutti agent via `claude --print` / `gemini --print` / `nlm` subprocess. Cascade detection grep stdout per quota-exhaust strings.

**Cascade applicability rule (post-Q1):**

- **CRON agents** (reflexion-synth, yt-metrics-analyst, editorial-bench): full cascade chain `claude → gemini → codex → ollama`
- **Hot-path content agents** (brief-interpreter, script-editor, shot-director, clip-renderer, audio-asset-producer, post-assembler, critic, b-roll-curator): cascade `claude → gemini → codex` (no ollama for production quality)
- **Root-of-trust** (`wr3-design-architect`): **NO cascade.** Hard-fail + Telegram P0 if Claude OAuth MAX unavailable. (Law 5 trumps Law 1.)
- **Spend gate** (`wr3-pre-render-gatekeeper`): **NO cascade.** Hard-halt episode if Claude OAuth MAX unavailable. (Law 7 trumps Law 1 — better halt than uncontrolled cost.)

**Lint:** `scripts/lint_wr3_cli_only.py` — block ANTHROPIC_API_KEY usage + paid SDK imports in WR3 code.

### Legge 2 — OSINT blindato

**Declinazione:** WR3 = brand video, NOT OSINT/intelligence. Boundary clarification post-Q2:

| Allowed in WR3 output                                                                                                                                   | Forbidden in WR3 output                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Verbatim regulatory text (UU/PP/PMK pubblici) from **public/legal cache** + domain NBs NB-2..NB-7 (visa, company, tax, property, compliance, editorial) | Raw NB-INTEL OSINT family notes / annotations / synthesis (NB-INTEL is OSINT-only, never consumed for grounding)                                        |
| Public regulation references (PMK 12/2026, UU 6/2011)                                                                                                   | NB source UUIDs / NB conversation IDs                                                                                                                   |
| Insight derivato da competitor analysis (es. "competitor pattern X → noi Y meglio")                                                                     | Raw competitor IG screenshot + dossier_id                                                                                                               |
| Brand cortex skills (constitution.md, forbidden-phrases.md) committed in git                                                                            | Domain NB query results raw, and ANY NB-INTEL OSINT output (must be filtered through brief-interpreter cache; NB-INTEL never reaches brief-interpreter) |

**File/path:**

- Brief-interpreter MUST cache regulatory facts in local PG `regulatory_facts` table (sanitized) before passing to script-editor
- `nlm` CLI subprocess output filtered: pass facts + verbatim citations, strip source metadata

**Lint:** `scripts/lint_wr3_osint_boundary.py` — scan manifest JSON + captions + descriptions for forbidden fields (`nb_source_id`, `nb_conversation_id`, `competitor_dossier_id`).

### Legge 3 — Event-driven durabilità

**Channel consolidation post-Q3:** 9 channels → 6 (removing intermediate noise, keeping durable state changes):

```
1. wr3_episode_brief_requested → brief-interpreter
2. wr3_episode_pre_render_ready  (collapsed: brief_ready + script_frozen)
   → shot-director + audio-asset-producer (parallel)
3. wr3_episode_gate_passed → clip-renderer  (collapsed: prompts_ready + gate_passed)
4. wr3_episode_assembly_ready  (collapsed: clips_ready + audio_ready) → post-assembler
5. wr3_episode_critic_verdict (single channel with PASS/FAIL payload, was 2)
6. wr3_episode_staged → Drive + Telegram notify Antonello
```

**Durability:** PG NOTIFY + `events_outbox` (Phase 1 EventBus pattern, cicatrix-resolved).

**Test contract** (Law 3 hard requirement): `apps/backend-rag/backend/tests/services/events/test_wr3_outbox_replay.py` MUST cover all 6 channels + disconnect+reconnect replay scenario.

### Legge 4 — Graceful degradation

**Degrade-vs-hard-fail matrix (post-Q4):**

| Failure                                                        | Behavior                                                     | Reason                                                 |
| -------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------ |
| `wr3-design-architect` down                                    | HARD-FAIL                                                    | Root of trust, no proxy possible                       |
| `wr3-pre-render-gatekeeper` down                               | HARD-FAIL                                                    | Spend gate, no Veo without approval                    |
| `wr3-brief-interpreter` NB timeout 45s                         | DEGRADE (flag `nb_unavailable`) — episode → draft-only state | Brief without NB = incomplete claim_id binding (Law 7) |
| `wr3-clip-renderer` Veo safety reject single shot              | DEGRADE (b-roll-curator fallback)                            | Recoverable shot-level                                 |
| `wr3-clip-renderer` Veo 100% failure (all shots)               | DEGRADE (still-image fallback)                               | Episode delivers as motion-graphic                     |
| `wr3-audio-asset-producer` Chatterbox crash                    | DEGRADE (no VO + music + subtitles)                          | **NO cloud TTS** (Q6 reject)                           |
| `wr3-post-assembler` ffmpeg VARIANT fail (1+ platform variant) | DEGRADE (master + 3/4 variants, flag `variant_X_failed`)     | Master is coherent artifact                            |
| `wr3-post-assembler` ffmpeg MASTER fail                        | HARD-FAIL                                                    | No coherent artifact to review                         |
| `wr3-critic` Haiku VLM timeout                                 | DEGRADE (Opus full review slower but complete)               | Quality preserved                                      |
| `wr3-critic` FULL down (Haiku + Opus)                          | HARD-HALT staging                                            | No verdict = no publish                                |

**Lint:** Every agent contract MUST declare `failure_modes: {<code>: hard_fail | degrade_loud}` — silent degrade BANNED.

### Legge 5 — Zero ultima istanza

**Telegram P0/P1/P2 prioritization (post-Q5 KEEP):**

| Priority | Trigger                                                                                                                | Cadence                | Chat       |
| -------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------- | ---------- |
| **P0**   | Episode HALT (root-of-trust down, master assembly fail, cost ≥3× budget over 7d, Symbiosis Law violation)              | Immediate push         | 1125336968 |
| **P1**   | Agent quarantine (critic FAIL ≥5 consecutive, skill demoted to `_quarantine/`)                                         | Daily batch 09:00 WITA | 1125336968 |
| **P2**   | Weekly digest: # episodes produced, cost actuals vs budget, # skills graduated/quarantined, Reflexion lessons accepted | Sun 09:00 WITA         | 1125336968 |

**7 mandatory human-in-loop points (unchanged from draft):**

1. Genesis ritual: 13 signed commits in 1 PR `wr3-room-genesis`
2. Weekly graduation review (`_proposed/` → main)
3. Skill demotion archive (`_quarantine/` → `_archived/` via PR)
4. Cost overrun ≥3× budget 7d → P0 halt + decision
5. Critic FAIL ≥5 → P1 quarantine + decision
6. Publish to IG/TT/YT: Damar/Antonello manual click
7. New regulatory citation: brief-interpreter flag `regulatory_unverified` → Veronika/Antonello sign-off

### Legge 6 — Sovranità locale

**Cloud whitelist (post-Q6, Cartesia banned):**

| Cloud service           | Justification                                                                           | Fallback if down                                          |
| ----------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Flow UI Pro (Veo)       | Cloud-bound by design (Google service). Local alternative = none of comparable quality. | still-image + b-roll-curator stock pool                   |
| NotebookLM (NB queries) | Free OAuth, regulatory facts authority                                                  | local PG `regulatory_facts` cache (read-only)             |
| YouTube Analytics API   | Read-only consumer, async                                                               | skip weekly report (no production block)                  |
| ~~Cartesia API~~        | ~~Audio fallback~~                                                                      | **BANNED post-Q6** — degrade to no-VO + music + subtitles |

**Local stack confirmed:**

- Chatterbox Multilingual TTS (Pro M4, MIT license, mps fallback)
- ffmpeg evermeet static `/tmp/ffmpeg-full/ffmpeg`
- ArcFace identity check (insightface Python lib)
- Brand cortex `~/.claude/skills/bali-zero-brand/`
- Manifest + episode state `~/.cell-observatory/wr3/` + PG Pro/Mini

**Per-episode Antonello exception path** (Law 6 escape hatch):

- If Chatterbox crashes mid-episode AND episode has Veronika regulatory cite that NEEDS voice → Antonello can approve 1-off Cartesia call via Telegram P0 reply within 30 min window
- Manifest field `cloud_exception: {service: cartesia, approved_by: antonello, ticket: <telegram_msg_id>}`
- Quarterly audit: # exceptions / # episodes. Target ≤2%.

### Legge 7 — Numeri prima

**Already covered in Step 4 MISURA phase.** Q7 refinement:

**expected_metric_delta exemption (post-Q7):**

- NO blanket exemption
- Allow **proxy metrics for micro-skills**: e.g., new pronunciation rule "KITAS = kee-tahs" → `expected_metric_delta: -100% pronunciation_errors{phoneme=KITAS}` (qualitative-to-proxy)
- Allow **sustained pass-rate** as graduation criterion for additive skills: 3 successful uses with critic ≥ threshold = graduation (without explicit forward delta numerical claim)
- Hard requirement: ALL skills MUST have **some falsifiable metric** in frontmatter

### Legge 8 — Rispetto passato / Potenzia presente / Vedi futuro

**Cicatrix citation pre-PR (post-Q8 KEEP):**

- Every new agent MUST cite ≥1 cicatrix entry (cross-domain inheritance valid)
- Example: `wr3-shot-director` cites WR2 cicatrix "pre-render gatekeeper born from PR #565 master template failure" as inherited pattern "visual prompt must be gated before paid render"
- Skill graduation MUST include forward-looking quantification (Q7 modify)

**Voyager curriculum (already in draft):**

- Detect underrepresented topic types weekly
- Skill graduation log JSONL per agent
- Future-room template for WR4/WR5 forks

## Cross-legge precedence rule (post-Q9 MODIFY)

```
Law 2 (OSINT) > Law 5 (Zero) > Law 7 (numeri/legal-proof) > Law 4 (graceful degradation)
```

**Arbitration owner:** `wr3-design-architect`.

**Concrete examples:**

- NB down + brief-interpreter cannot validate claim_id → Law 7 trumps Law 4 → episode → draft-only state (NOT legal-passed)
- Cartesia exception requested but Antonello unreachable → Law 5 trumps Law 4 → degrade to no-VO + music + subs (NOT autonomous Cartesia call)
- Competitor screenshot accidentally in skill cortex → Law 2 trumps Law 8 (passato) → remove from git history immediately + cicatrix entry, do NOT preserve as "lesson learned"

## Summary table — 8 leggi → WR3 final controls

| Legge                      | WR3 control (FINAL)                                                                                                                                                                                                                 | Lint script                                    |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| 1 CLI-only LLM             | All agents `claude/gemini/nlm` CLI subprocess. **Cascade non-gating + cron; NO cascade orchestrator + gatekeeper.**                                                                                                                 | `lint_wr3_cli_only.py`                         |
| 2 OSINT blindato           | Brief-interpreter queries domain NBs only (NB-2..NB-7); NB-INTEL OSINT family stays local and is never consumed. Brief-interpreter caches regulatory facts in local PG before propagation. **NO source_ids in published manifest.** | `lint_wr3_osint_boundary.py`                   |
| 3 Event-driven             | **6 channels** (consolidated from 9): brief_requested → pre_render_ready → gate_passed → assembly_ready → critic_verdict → staged. PG NOTIFY + outbox.                                                                              | `test_wr3_outbox_replay.py`                    |
| 4 Graceful degradation     | **Matrix per failure mode** — hard-fail root/gate/master, degrade everything else loud. **NO silent placeholder.**                                                                                                                  | Contract validation pre-PR                     |
| 5 Zero ultima istanza      | **P0/P1/P2 Telegram triage** + 7 human-in-loop gates. Critical paths halt rather than improvise.                                                                                                                                    | `lint_wr3_autonomous_publish.py`               |
| 6 Sovranità locale         | Local Chatterbox + ffmpeg + ArcFace. Cloud whitelist: Veo + NLM + YT only. **Cartesia BANNED** (Antonello per-episode exception path only).                                                                                         | `lint_wr3_cloud_dependency.py`                 |
| 7 Numeri prima             | JSONL telemetry 6 mandatory fields. Proxy metrics OK for micro-skills. Sustained pass-rate as graduation for additive skills.                                                                                                       | `lint_wr3_telemetry_completeness.py`           |
| 8 Passato/Presente/Futuro  | Cicatrix citation pre-PR (cross-domain valid). Skill versioning manifest pin. Voyager curriculum.                                                                                                                                   | Pre-PR hook                                    |
| **Cross-legge precedence** | **`Law 2 > Law 5 > Law 7 > Law 4`** arbitrated by orchestrator.                                                                                                                                                                     | Doctrine in `docs/wr3/symbiosis-precedence.md` |

## Open questions per Antonello (decision gate)

1. **Cascade hot-path policy**: confermo NO cascade per orchestrator + gatekeeper (hard-fail invece)? Trade-off: resilienza ↓ vs disciplina spend ↑.
2. **Channel consolidation 9→6**: ok perdere `brief_ready` come canale separato (incorporato in `pre_render_ready`)? Implica brief-interpreter scrive script_frozen state durably PRIMA che fire l'event.
3. **Cartesia BAN definitivo**: panel REJECT 3/3. Confermi che Zantara voice MAI cloud (anche con exception per-episode), o vuoi mantenere Cartesia exception path attivo?
4. **P0/P1/P2 Telegram cadence**: P0 immediate, P1 daily 09:00, P2 Sun 09:00. Orari ok o vuoi shift?
5. **Cross-legge precedence**: `Law 2 > Law 5 > Law 7 > Law 4` come doctrine. Vuoi che la precedence chain finisca in `SYMBIOSIS.md` come addendum, o stay WR3-doctrine-only?
6. **Domain-NB source_id filtering** (brief-interpreter queries NB-2..NB-7; NB-INTEL OSINT family explicitly out of scope): brief-interpreter caches regulatory facts in local PG → quanto è OK manifest contenga `regulation_id: PMK_12_2026` ma non `nb_source_uuid: xxx-yyy-zzz`?
7. **Law 9 propose path**: se WR3 evidenza forte richiede "stochastic-idempotence law", processo è: collect 30 episode evidence → Antonello PR. Confermo o vuoi watchdog flag prima dei 30?

## Next step (Step 6 — Architettura LangGraph + skeleton code)

Mappare 9 pipeline agent in graph LangGraph con:

- 6 PG channels (post-Step 5 consolidation) = state transitions
- Conditional edges per critic verdict (PASS → staged, FAIL → re-route)
- Checkpoint per agent invocation (Reflexion replay)
- Cost ceiling check pre-spend (cost_class enforcement)
- Skeleton Python file structure: `apps/wr3-room/wr3/orchestrator.py`, `agents/`, `contracts/`, `tests/`

Trigger: confirm Step 5 decisions (A/B/C/D)?

## Sources

| Panel          | LLM                             | Bytes                      | Quality                                                  |
| -------------- | ------------------------------- | -------------------------- | -------------------------------------------------------- |
| Gemini 3.1 Pro | gemini-3.1-pro-preview          | 2438                       | terse KEEP/MODIFY/REJECT per Q                           |
| Codex GPT-5.5  | gpt-5.5 xhigh                   | 3094 (24KB inc. exec logs) | thorough + precedence chain insight (best Q9)            |
| NB-AGENTS      | NotebookLM RAG                  | 3500 retry                 | 17.2× error finding cited + sustained pass-rate proposal |
| DeepSeek       | KILLED by user (Step 3 onwards) | —                          | —                                                        |

**Strongest convergence in Step 1-5 progression.** Q6 Cartesia ban = unanimous reject — clearest signal that Law 6 sovereignty is non-negotiable for Zantara voice identity.

**Critical Codex contribution**: explicit precedence chain `Law 2 > Law 5 > Law 7 > Law 4` — directly resolves cross-legge tensions Q9 with operational arbitration rule for `wr3-design-architect`.
