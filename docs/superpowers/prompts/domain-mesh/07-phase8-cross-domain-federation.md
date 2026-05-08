# Phase 8 — Cross-Domain Federation Layer

> **Prerequisiti**: TUTTE le 6 fasi domain (B1-B6) implementate. Senza, non c'è "cross" da fare.
>
> **Stima**: 8-12 giorni solo-dev.
>
> **Pre-azione richiesta a Antonello**: nessuna. Questa fase è puramente integrativa.
>
> **Differenza dalle fasi precedenti**: questa NON aggiunge un nuovo dominio, **collega quelli esistenti** in un grafo federato + skill graduation pipeline (la promessa Round 2 dal R1.5 NB lifecycle).

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 8 (finale): implementa il **Cross-Domain Federation Layer**.

Verifica precondizione:

```bash
ls apps/mata-garuda/mata_garuda/domains/
# Deve contenere: setup_team/ tax/ marketing/ antonello_lab/ bali_macro/ nexus_osint/
```

Se mancano domini → STOP e implementa quelli prima.

Poi leggi:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §8 (cross-domain federation completa)
2. Phase 0 mitochondrial value monitor (PR #493 reference) — è la base per Phase 8 auto-correct
3. NB lifecycle R1+R1.5 closure (memoria `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` cerca "NB Lifecycle R1+R1.5 closed")

`superpowers:brainstorming` → `writing-plans` → `subagent-driven-development`.

### Scope

**`apps/mata-garuda/mata_garuda/federation/`** modules:

1. **Cross-domain entity overlap layer**:
   - `entity_registry.py`: SQLite + Wikibase (se Phase 7 ha implementato) per shared entity store
   - 12 entity types (design §8.2 matrix): Person, Organization, KBLI, RegulatoryDoc, Property, ContentItem, Trend, Paper, PolicyEvent, Obligation, CoretaxIncident, CalendarBaliCeremony
   - Each entity has `owned_by` (B1-B6) + `referenced_by` (lista)
   - Cross-domain query: `lookup_entity(name) → list[(domain, ref_url)]`

2. **Cross-domain alert routing** (design §8.4):
   - `alert_router.py`: PolicyEvent → tax/setup, KEP-71 → tax+content brief candidate, etc.
   - Single Telegram bot @Balizerobot (NLM ground-truth W1: NO per-domain channels)
   - Routing rules in `alert_routing_rules.yaml` (declarative)
   - Test: feed PolicyEvent payload, assert routes correctly

3. **Multi-LLM fallback strategy** (design §8.5):
   - `llm_fallback.py`: priority Claude OAuth → DeepSeek → Gemini CLI → Codex CLI → Ollama local
   - Cost-aware: each call logs to Langfuse/Phoenix (Phase 0 OpenLLMetry SDK if activated)
   - Graceful degradation: max 30s wait per single LLM exhaust, then queue + Telegram alert

4. **Auto-correct layer** (design §1.4):
   - `drift_detector.py`: weekly cron — check superseded regulations (PMK abrogated by newer)
   - `conflict_detector.py`: nightly — cross-NB queries on overlapping entities (es. KITAS C312 validity NB-2 vs NB-INTEL-Immigration)
   - `self_coherence_probe.py`: per AUTHORITY NB, weekly LLM internal consistency check

5. **Telemetry & explainability** (design §1.5):
   - `mitochondrial_monitor_extended.py`: Phase 0 monitor extended a TUTTI i NB (non solo NB-INTEL)
   - `decision_log.py`: JSONL append-only di ogni autonomous action
   - Schema: `{ts, actor, action, target_nb, source_url, scorer_confidence, router_decision, reasoning, policy_applied}`
   - `explainability_api.py`: `GET /nb/{id}/why?source={source_id}` returns decision log entry
   - `weekly_self_report.py`: cron Sunday genera markdown report per dominio

6. **Skill graduation pipeline** (design §1.6 sink 5):
   - `skill_graduation.py`: detector di NB-WORKBENCH che hanno raggiunto maturity (3+ deep items, sustained query traffic, no internal conflicts)
   - Auto-spawn proposal in `~/.claude/plugins/proposed-skills/<name>/SKILL.md`
   - Antonello review + approve via `/skills/graduate <name>` slash command
   - Once approved: skill copied to `~/.claude/plugins/cache/.../skills/`

7. **ADR auto-generator** (design §1.6 sink 6):
   - `adr_generator.py`: critical autonomous decisions (NB-merge, NB-decommission, federation rule change) → ADR markdown in `docs/adr/`
   - Format: standard MADR template
   - Sign-off: system + Antonello approval timestamp

8. **Cross-domain cron orchestrator**:
   - `infra/scripts/federation-cron.sh`
   - Schedule: 11:00 WITA daily (after all domain crons 06:00-10:00)
   - Tasks: drift detection, conflict detection, mitochondrial scan, weekly self-report (Sunday only)
   - Kill switch: `FEDERATION_CRON_ENABLED=false`

### Integration con codebase esistente

- **EventBus** (PG LISTEN/NOTIFY + outbox): cross-domain alerts pubblicano su events_outbox
- **Innervation Genoma**: federation-cron è enrolled organism in `apps/organism/organism/genome.yaml`
- **Symbiosis Law 4** redundancy: ogni cross-domain alert handler is idempotent (replay-safe)
- **Mitochondrial Monitor** Phase 0 PR #493: estendi per supportare Phase 1-8 NB

### Deliverables

1. 6 nuovi moduli core in `mata_garuda/federation/`
2. `alert_routing_rules.yaml` declarative
3. SQLite migrations per `decision_log`, `entity_registry`
4. ADR template
5. Skill graduation slash command
6. Cron LaunchAgent
7. 80+ test (entity registry CRUD + routing rules + drift simulation + mitochondrial scoring)

### Sink (chiusura del lifecycle)

A questo punto, il sistema è **completo** secondo il design 5-fase:

- ① **Nascita**: genesis manifests per ogni dominio
- ② **Crescita**: 4 modalità (manual, cron, promotion, federation) attive
- ③ **Auto-correct**: drift + conflict + self-coherence
- ④ **Coscienza**: mitochondrial + decision log + explainability + weekly report
- ⑤ **Canalizzazione**: 6 sink (mouth, telegram, CRM, dispatch, skill graduation, ADR) tutti vivi

### Regole forti

- mata-garuda CLAUDE.md
- Lazy imports
- TDD strict (federation è critico, ogni regola routing test-coperta)
- Cron PATH
- Branch hijack push
- External review wave OBBLIGATORIO 5-LLM (3 wave) prima merge — federation tocca tutti i domini, blast radius alto

### Pre-condizioni per merge

- 80+ test green
- Smoke test: PolicyEvent fake → assert routes a 3+ domini correttamente
- Mitochondrial monitor smoke su 3+ NB: scoring corretto
- Decision log audit: 24h di esecuzione produce JSONL valido
- Antonello approva alert routing rules YAML

### Esito finale

Quando questa fase merga, hai il sistema autonomico completo end-to-end: 6 domini × 5 fasi lifecycle × federation graph × auto-correct × explainability × skill graduation pipeline.

A quel punto il sistema è in modalità **operational**: nuove feature solo via PR review umano + brainstorm session ad-hoc, non più phased rollout.

Procedi.
