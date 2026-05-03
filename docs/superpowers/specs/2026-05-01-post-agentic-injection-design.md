# Era Post-Agentica — Iniezione Cell + Genoma via vertical-slice renewals

**Data**: 2026-05-01 (revisione 2026-05-02 §3.3.2 + §3.3.6 + §4 Sprint 1-2)
**Autore**: Claude Opus 4.7 (max effort, 1M context) in dialogo con Antonello (Zero)
**Branch propost**: `feature/post-agentic-injection-2026-05-01` (Sprint 0 done) → `feat/post-agentic-skill-registry-2026-05-02` + `feat/post-agentic-heartbeat-middleware-2026-05-02` (Sprint 1)

**Changelog 2026-05-02**:

- §3.3.2: rimosso `packages/nuzantara-skills/` (era ridondante — `cell_core.genome` già skill registry full-featured); Sprint 1.A diventa estensione SEED_SKILLS (1 giorno invece di 3-4)
- §3.3.5: riformulato heartbeat — la versione originale ("middleware FastAPI in backend chiama emit_organ_last_seen") era broken-by-design (filesystem ephemeral su Fly). Cell-side bridge approach: estendere `health_sensor.py` + `channel_sensor.py` esistenti per emettere sidecar file su Pro post-poll. Costo: 2 giorni invece di 4-5
- §3.3.6 NUOVO: coordinamento con Cell Pulse Observatory Fase 0 (PRs #406-415 in `main`)
- §4 Sprint 1: scope reframed in 2-strato Air-parallel (1.A + 1.B) + 1.C deferred per coordination Observatory
- §4 Sprint 2: scope ridotto perché 50% già fatto in Sprint 1.A

**Riferimenti autoritativi**:

- `SYMBIOSIS.md` (7 Leggi inviolabili)
- `VADEMECUM.md` §1, §2, §11
- `docs/innervation-2026-04-29/07_innervation_protocol.md` (Genoma + Heartbeat schema)
- `docs/innervation-2026-04-29/09_migration_plan.md` (Wave 0-5 sequencing)
- `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` (Organism design)
- `.claude/rules/cicatrix-scars.md` (8+ scar rilevanti)

---

## 1. Contesto e domanda

L'organismo Nuzantara ha 4 gap diagnosticati che impediscono la transizione all'**Era Post-Agentica** ("Cell come loop decisionale primario + organismo che sopravvive senza agenti in sessione", modalità _B con sfumature di C_ nel framework brainstorm):

1. **32 organi su 58 plist Pro non enrolled in `genome.yaml`**
2. **`backend.api` e 4 channel webhook NON emettono heartbeat** malgrado dichiarati nel Genoma con `expected_hb_seconds=60`
3. **Cell isolata dal Cortex del backend** (nessuna skill registry condivisa; `apps/evaluator` usa fork separato `packages/cell-core`)
4. **Consiglio L3 cablato solo a 2 actuator infrastrutturali** (`consolidate_redundancy`, `propose_yaml_rule`) — zero decisioni di business

La domanda di partenza: **quale sequenza di iniezione apre la transizione Post-Agentica con minor blast radius e massimo learning rate?**

---

## 2. Decisione architetturale (verdetto multi-LLM)

Quattro angoli LLM consultati in parallelo:

| LLM             | Angolo                  | Voto                                           | Argomento principale                                                                                       |
| --------------- | ----------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Gemini 3.1 Pro  | Engineering pragmatist  | **Approccio 1** (Lamarckian-pure shadow-first) | Dual-path = state fragmentation pericolosa                                                                 |
| Codex GPT-5.5   | Business operations     | **Approccio 3** (Doppio binario)               | Approccio 1 troppo lento per il team — opportunity cost                                                    |
| DeepSeek R1     | Reasoning + adversarial | **Approccio 3**                                | Shadow eternity ha "false confidence": clienti reali generano feedback che nessun sensor cattura in shadow |
| Claude Opus 4.7 | Symbiosis philosopher   | **Approccio 3**                                | Unica architettura dove "organismo che vive" e "organismo che non danneggia" coesistono empiricamente      |

**Verdetto: Approccio 3 (Doppio binario) — 3 voti su 4.**

La critica di Gemini (state fragmentation) è valida e indirizzata: il routing shadow-vs-sandbox **non vive in Cell**, vive in un **dispatcher esterno** (`apps/backend-rag/backend/services/skill/dispatcher.py`, NUOVO — sibling di `service.py` esistente). Cell ha un single output path (proposal); la complessità di branching sta in 30 righe di dispatcher testabile in isolation.

**Approccio scelto**: Approccio 3 con **mitigazione architetturale Gemini** (dispatcher esterno, Cell single-output).

---

## 3. Architettura

### 3.1 Strati paralleli

L'iniezione si compone di **2 strati che vivono insieme dal day 1**, non in fasi temporali separate:

| Strato                 | Cosa                                                                                              | Rispetto SYMBIOSIS                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **C base**             | Heartbeat tutti gli organi, Genoma auto-discovery, governatore omeostatico                        | Pilastri 4 (graceful degradation), 6 (sovranità locale), 7 (numeri prima) |
| **B-1 vertical slice** | Skill registry esistente (`cell_core.genome`) + 5 skill renewals seed + dispatcher + Consiglio v2 | Pilastri 1 (CLI-only), 3 (event-driven), 5 (Zero ultima istanza)          |

C base costruisce le fondamenta che reggono B-1. B-1 è il primo dominio dove l'organismo _vive_ e _decide_. Senza C base, B-1 decide su dati ciechi. Senza B-1, C base è solo un osservatorio passivo.

### 3.2 Flusso decisionale (vertical slice renewals)

```
[Sensors]                    [Cortex]                   [Dispatcher]                 [Outcome]
visa_expiry_team_notifier →  Cell skill_library    →    skill/dispatcher.py       →  renewal_alert_outcomes
renewal_alerts (m007+080b)   propose(skill_name,        dispatcher.dispatch()         (acted_by_team |
predictive_engine            payload, confidence)       │                              client_renewed |
                                                        ├── tier-3 + value<2K USD →    client_ignored |
                                                        │   sandbox path:              expired_no_action)
                                                        │   • Consiglio v2 mono-LLM
                                                        │     (Ollama Pro, no cloud)
                                                        │   • Telegram approve Zero
                                                        │   • execute via skill
                                                        │
                                                        └── tutti gli altri →
                                                            shadow path:
                                                            • decisions.jsonl
                                                            • daily digest Telegram
```

### 3.3 Componenti

#### 3.3.1 Dispatcher (`apps/backend-rag/backend/services/skill/dispatcher.py`, NUOVO)

```python
def dispatch(proposal: Proposal) -> DispatchResult:
    sandbox_eligible = (
        proposal.client.tier == 3
        and proposal.client.lifetime_value_usd < 2000
        and proposal.skill_name in SANDBOX_WHITELIST
        and sandbox_quota_today() < 1
    )
    if sandbox_eligible:
        return execute_sandbox(proposal)  # Consiglio v2 + Zero approve + execute
    else:
        return log_shadow(proposal)        # decisions.jsonl + daily digest
```

Single point of branching. Cell non sa cosa succede dopo la `propose()`.

#### 3.3.2 Skill registry — usa `cell_core.genome` esistente (NON nuovo package)

> **Discovery 2026-05-02 (durante Sprint 1 planning su Air)**: il "gap 3" originale del brief ("Cell isolata dal Cortex, no skill registry condivisa") **NON era un gap reale**. La realtà del codebase:
>
> - **`packages/cell-core/cell_core/genome.py`** è già un skill registry full-featured: SQLite + FTS5, tier1/tier2, 11 HGT domains canonici (`visa`/`tax`/`kbli`/`property`/`legal`/`crm`/`news`/`architecture`/`rag`/`graph`/`generic`), confidence/uses/last_used, valid_to per epigenetic silencing, inherited_from per HGT.
> - **`apps/backend-rag/backend/services/skill/service.py`** è già un wrapper Genome con graceful-degradation (no-op se cell_core non importable).
> - **`apps/backend-rag/backend/services/learner/`** è già un orchestrator nightly che chiama `record_skill` / `record_scar` su outcome osservati.
> - **`apps/backend-rag/backend/scripts/seed_initial_skills.py`** è già un seeder con ~32 skill curated (cell="experience"/"rag"/"crm"/etc., procedure/precondition/success_criterion/confidence iniziale).
>
> Il design originale aveva proposto un nuovo `packages/nuzantara-skills/` ridondante. Cancellato.

**Scope reale Sprint 1.A (semplificato)**: aggiungere ~5 skill renewals al SEED_SKILLS list di `seed_initial_skills.py`, run `--apply` su prod genome.

| Skill ID                         | Cell | Domain | Procedure (sintesi)                                               |
| -------------------------------- | ---- | ------ | ----------------------------------------------------------------- |
| `crm:detect_expiring_kitas`      | crm  | crm    | Query `clients.kitas_expiry_date` between [today, today+90d]      |
| `crm:propose_renewal_outreach`   | crm  | crm    | Generate Proposal(client_id, channel=WA, urgency by days_left)    |
| `crm:draft_wa_renewal_message`   | crm  | crm    | Template via Ollama deepseek-r1, locale=client.preferred_language |
| `crm:measure_renewal_conversion` | crm  | crm    | Cron 24h post-execute → join renewal_alert_outcomes               |
| `crm:update_renewal_confidence`  | crm  | crm    | Lamarckian: bump confidence on outcome=client_renewed             |

Cell consumer: `apps/cell/cell/cortex/skill_library.py` (esistente) o nuovo modulo crm-aware. Backend-rag consumer: `apps/backend-rag/backend/services/skill/service.py` (esistente).

**Costo build**: 1 giorno (era 3-4 nel design originale). Single source of truth confermato: `cell_core.genome` SQLite at `~/.nuzantara/experience.db`.

**Implication su Sprint 2**: anche Sprint 2 ("Skill renewals + Cell wire-up") è in larga parte già fatto. Le 5 skill proposte sopra coprono Sprint 2 §1; restano §3 (sensor `kitas_renewal_sensor`) e §4 (shadow path attivo + sandbox stubbed). Cell `cortex.skill_library` import da package condiviso §2 è già live.

#### 3.3.3 Consiglio v2 mono-LLM locale (`apps/organism/organism/supervisor/consiglio_v2.py`, NUOVO)

Per decisioni con PII (renewals KITAS specifico cliente, payload contiene NPWP/NIB/passport/nomi):

- **LLM**: Ollama on Pro (`deepseek-r1:32b` per reasoning, `qwen3.5:9b` per fast classification)
- **Zero cloud**: nessun dato cliente esce mai dalla macchina di Zero
- **Latenza**: 30-120s per `deepseek-r1:32b`, accettabile per workflow human-in-loop
- **Fallback**: se Ollama down, Cell **non propone** azioni con PII (graceful degradation, Pilastro 4)

Consiglio v1 (multi-LLM cloud) **rimane attivo** per decisioni meta senza PII:

- Calibrazione soglie globali
- Mutation strategiche (`propose_yaml_rule`, `consolidate_redundancy`)
- Decisioni di policy organism-level

#### 3.3.4 Genoma auto-discovery (`apps/organism/organism/tools/discover_organisms.py`, NUOVO)

Cron settimanale (Pro, Lunedì 09:00 WITA):

1. Legge `launchctl list | grep com.{nuzantara,balizero,cell}.`
2. Legge `apps/organism/organism/genome.yaml`
3. Diff: plist senza entry → propone PR di update
4. PR auto-aperto via `gh pr create` con etichetta `genoma-drift`
5. Telegram digest a Zero: "3 nuovi organi rilevati: X, Y, Z. PR #1234"
6. Zero approva → merge → checksum aggiornato (`validate_genome --update-checksum`)

L'organismo che non sa cosa contiene è cieco. L'auto-discovery rende il Genoma **sempre sincrono con la realtà** senza richiedere disciplina manuale.

#### 3.3.5 Heartbeat per backend.api e channel.\* — Cell-side bridge (riformulato 2026-05-02)

> **Discovery 2026-05-02**: la prima formulazione ("FastAPI middleware in `apps/backend-rag/backend/app/middleware/heartbeat.py` chiama `emit_organ_last_seen` ogni 60s") era **broken-by-design**. `emit_organ_last_seen` scrive `~/.organism/last_seen/<id>.json` su filesystem **locale**. Backend.api e tutti i channel webhook girano su Fly.io — filesystem ephemeral. Lo stato non sopravvive a un restart e non è raggiungibile dal `genome_aggregator_sensor` su Pro che legge `~/.organism/last_seen/`.

**Approach (A)**: Cell-side bridge — Cell sensors esistenti traducono i poll che fanno già in sidecar file su Pro filesystem.

| Organ               | Cell sensor (esistente)                                                               | Cosa cambia in Sprint 1.B                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `backend.api`       | `apps/cell/cell/sensors/health_sensor.py` (poll `/health` ogni 60s, già live)         | Aggiungere chiamata `emit_organ_last_seen('backend.api', status_from_reading)` post-poll                                                  |
| `channel.whatsapp`  | `apps/cell/cell/sensors/channel_sensor.py` (queue depth `inbound_webhooks`, già live) | Estendere a poll `/api/channels/whatsapp/health` (NUOVO endpoint `apps/backend-rag/backend/app/routers/channel_health.py`) + emit sidecar |
| `channel.telegram`  | (idem)                                                                                | Idem                                                                                                                                      |
| `channel.instagram` | (idem)                                                                                | Idem                                                                                                                                      |
| `channel.web`       | (idem)                                                                                | Idem                                                                                                                                      |

**Backend changes (minimal)**:

- `apps/backend-rag/backend/app/routers/channel_health.py` (NUOVO, ~30 LOC): endpoint per channel `GET /api/channels/{name}/health` ritorna `{"status": "ok|degraded|fail", "ts": ..., "last_event_seen_at": ..., "queue_depth": ...}` aggregando lo state dei `channels/{name}/` modules.
- Backend NON tocca filesystem heartbeat: solo HTTP exposure.

**Cell changes (minimal)**:

- `apps/cell/cell/sensors/health_sensor.py` (MOD): post-poll, chiama `emit_organ_last_seen('backend.api', mapped_status, metadata={'http_status': reading.status_code, 'latency_ms': ...})`.
- `apps/cell/cell/sensors/channel_sensor.py` (MOD): per ogni channel poll a `/api/channels/{name}/health`, chiama `emit_organ_last_seen('channel.{name}', mapped_status, metadata={'queue_depth': ...})`. Estende il sensor esistente (queue depth → multi-fonte aggregation).

**Costo build**: 2 giorni (Cell-side + 1 endpoint backend, no middleware lifecycle complexity). Sblocca `genome_aggregator_sensor` per classificare correttamente questi 5 organi (backend.api + 4 channel) entro 2× expected_hb_seconds = 120s/240s window.

**Coordination**: zero conflict con Observatory PR-5 Task 5.3 — i sensors `health_sensor.py` e `channel_sensor.py` non sono toccati da Observatory (che agisce su `cell_core.observatory` + `pulse.py` + plist env var, hot path ma diverso).

**Note SYMBIOSIS**: Pilastro 4 (graceful degradation): se Cell down, no sidecar → genome_aggregator classifica `dead`. È il signal corretto — backend potrebbe essere up ma se nessuno lo verifica, è "dead from observer's POV". Pilastro 6 (sovranità locale): tutti gli stati vivono su Pro filesystem, niente cloud dependency per heartbeat.

#### 3.3.6 Coordinamento con Cell Pulse Observatory (Fase 0 progetto parallelo)

> **Discovery 2026-05-02 (Air session)**: durante la pausa post-Sprint 0, è stato shippato in `main` un progetto parallelo "Cell Pulse Observatory Fase 0" (PRs #406-415) — observability-only baseline empirico di pulse events + classifier MiniMax M2. Stato corrente: PR-0..PR-4 merged; PR-5 partial (smoke test + rollback scripts shipped, **organism cell activation + 48h obs window NON ancora done**); PR-6/PR-7 pending.

Spec autoritativa: `docs/superpowers/specs/2026-05-01-cell-observatory-fase0-design.md`.

**Touchpoint condivisi con Sprint 1 Era Post-Agentica**:

| Componente                                    | Observatory                                    | Sprint 1 Era Post-Agentica            | Conflict?                                                 |
| --------------------------------------------- | ---------------------------------------------- | ------------------------------------- | --------------------------------------------------------- |
| `packages/cell-core/cell_core/genome.py`      | non tocca                                      | Sprint 1.A estende SEED_SKILLS        | Zero — read-only su Genome, append seed                   |
| `packages/cell-core/cell_core/observatory.py` | introdotto da Observatory PR-1                 | non tocca                             | Zero                                                      |
| `packages/cell-core/cell_core/pulse.py`       | hook `emit_pulse_observed` (Observatory PR-1)  | possibile heartbeat hook              | Manageable se entrambi fire-and-forget pattern            |
| `events_outbox` PG channel                    | `cell_pulse_observed` (Observatory PR-2)       | heartbeat usa state file (non outbox) | Zero — heartbeat sceglie state file approach (Pilastro 4) |
| `apps/cell/cell/main.py`                      | non tocca                                      | non tocca in Sprint 1.A/B             | Zero                                                      |
| `com.cell.organism.plist`                     | Observatory PR-5 Task 5.3 aggiunge env var     | Sprint 1.C aggiungerebbe heartbeat    | DEFER Sprint 1.C finché Observatory PR-5 done + 48h obs   |
| `apps/organism/organism/genome.yaml`          | Observatory **non** enrolling cells nel Genoma | Sprint 1.C enroll 32 organi mancanti  | Zero diretto                                              |

**Strategia coordinamento**: Strategia 2 — parallel scope-isolated.

- **Sprint 1.A (skill registry extension)** parte ora da Air, branch `feat/post-agentic-skill-registry-2026-05-02`. Touchpoint: solo `seed_initial_skills.py`. Zero conflict.
- **Sprint 1.B (heartbeat middleware)** parte ora da Air, branch `feat/post-agentic-heartbeat-middleware-2026-05-02`. Touchpoint: solo `apps/backend-rag/backend/app/middleware/`. Zero conflict.
- **Sprint 1.C (Genoma auto-discovery + heartbeat sweep su organism cell)** **DEFERRED** finché Observatory PR-5 Task 5.3 (organism cell activation) + 48h observation window passed + PR-6/PR-7 done. Stima ritardo: 3-7 giorni.

**Marker tracciato in MOS**: decision id 2041 (saved 2026-05-02), summary in `MEMORY.md` Coordination section.

### 3.4 Database schema additions

Tre migration nuove (Sprint 0 step 2+3 paralleli, Step 1 ricorrente vivo):

| Migration                        | Tabella                                        | Cosa traccia                                                                                                                                                        |
| -------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `149_client_segments.sql`        | `client_segments`                              | `(client_id, tier ∈ {1,2,3}, lifetime_value_usd, computed_at)`. Calcolo iniziale via batch SQL su `practices` JOIN `invoices`; aggiornamento ricorrente settimanale |
| `150_renewal_alert_outcomes.sql` | `renewal_alert_outcomes`                       | `(alert_id FK renewal_alerts, outcome ∈ {acted_by_team, client_renewed, client_ignored, expired_no_action}, outcome_at, observed_by ∈ {cell, team_member})`         |
| (no new table)                   | `renewal_baseline_2024_2026` view materialized | Computed retroactively + ri-aggiornata settimanale da Cell skill `measure_conversion`                                                                               |

**Squawk lint mandatorio** su tutte e 3 (cf. PR #306 + cicatrix `2026-04-26-atlas-paywalled`). `-- === ROLLBACK ===` marker su tutte (cf. cicatrix `2026-04-19-migration-runner`).

---

## 4. Piano di esecuzione (12 settimane)

### Sprint 0 — Fondazioni baseline (1 settimana, settimane -1 → 0)

**Modalità: Step 2+3 paralleli via worktree, Step 1 ricorrente vivo**

| Step | Cosa                                                                                                                                       | Worktree                     | Stima      |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------- | ---------- |
| 0.2  | Migration `149_client_segments.sql` + script computazione LTV iniziale                                                                     | `worktree-tier-segmentation` | 2-3 giorni |
| 0.3  | Migration `150_renewal_alert_outcomes.sql` + backfill su `renewal_alerts` esistenti (post-hoc inference da `practices.status` transitions) | `worktree-outcome-tracking`  | 1 giorno   |
| 0.1  | Skill `measure_conversion` con materialized view auto-refresh settimanale (NON un batch one-off)                                           | Sprint 1 (vive con Cell)     | n/a        |

**Critica del piano originale corretta in D**: il baseline retroattivo NON è un job batch one-off. Diventa un _organo vivo_ che ri-computa retroattivamente ogni settimana. Più Lamarckian, più SYMBIOSIS.

### Sprint 1 — C base + skill registry extension (riformulato 2026-05-02)

> **Reframe post-discovery**: scope ridotto da 3-strato a **2-strato Air-side parallel** + 1 strato Pro-side deferred. La discovery del 2026-05-02 (cf. §3.3.2 e §3.3.6) ha rivelato che il "skill registry" è già live in `cell_core.genome`; non serve nuovo package. Sprint 1.C deferred per coordinamento Observatory.

Lavoro in parallelo (cf. `superpowers:dispatching-parallel-agents`):

| Sub-sprint | Branch                                              | Cosa                                                                                              | Stima      | Status         |
| ---------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------- | -------------- |
| **1.A**    | `feat/post-agentic-skill-registry-2026-05-02`       | Estendi `SEED_SKILLS` in `seed_initial_skills.py` con 5 skill renewals (cell="crm", domain="crm") | 1 giorno   | Air, parte ora |
| **1.B**    | `feat/post-agentic-heartbeat-middleware-2026-05-02` | FastAPI middleware `backend.api` + 4 channel webhook handlers `emit_organ_last_seen`              | 4-5 giorni | Air, parte ora |
| **1.C**    | `feat/post-agentic-genoma-discovery-2026-05-XX`     | `discover_organisms.py` + cron LaunchAgent + heartbeat sweep su organism cell + plist edits       | 2-3 giorni | **DEFERRED**   |

**Sprint 1.C deferred condition**: Observatory PR-5 Task 5.3 done + 48h observation window passed + PR-6/PR-7 merged. Cf. §3.3.6.

Wave 0 di `09_migration_plan.md` (Genoma + Supervisor deploy + scheduled_tick) **NON è prerequisito Sprint 1.A/B** (era prerequisito Sprint 1.C). Defer wave 0 con Sprint 1.C.

### Sprint 2 — Skill renewals consumer + Cell wire-up (riformulato)

> **Reframe**: in larga parte già fatto in Sprint 1.A. Resta:

Sequenziale (no parallel, runtime impact):

1. ~~5 skill renewals concrete~~ — fatto in Sprint 1.A (seed in genome)
2. ~~Cell `cortex.skill_library` import da package condiviso~~ — già live (`cell_core.genome` accesso diretto via `apps/cell/cell/cortex/skill_library.py` esistente, no refactor needed)
3. **Sensor `kitas_renewal_sensor`** (estende `compliance/visa_expiry_team_notifier.py`) — gap reale, da implementare
4. **Shadow path attivo, sandbox path stubbed** (`execute_sandbox = NotImplementedError`) — gap reale, da implementare

Stima Sprint 2 effettiva: ~3-4 giorni invece di 2 settimane originali.

### Sprint 3 — Sandbox path + Consiglio v2 (settimane 5-6)

**Gate aperto: prima di Sprint 3, decisione esplicita di Zero richiesta (vedi §6.1)**

1. `consiglio_v2.py` (Ollama mono-LLM)
2. `dispatcher.execute_sandbox` con Telegram approve Zero (`approve/reject/defer` buttons)
3. Whitelist sandbox: `propose_outreach` + `draft_wa_message` solo per tier-3 + LTV<2K + max 1/giorno
4. Test gauntlet su staging Pro (5 scenari: Ollama down, Telegram down, approve, reject, defer)

### Sprint 4 — Misurazione + Lamarckian loop (settimane 7-8)

1. Skill `measure_conversion` schedulata 24h post-execute
2. `update_skill_confidence` aggiorna `skill_library` per (skill, segment) con conversion delta
3. Soglie statiche → adattive (2c del brainstorm): dopo 30gg di sandbox, soglie auto-aggiornate da Cell con human-in-loop ogni N override
4. Daily digest Telegram esteso: shadow proposal counts, sandbox executed, conversion rate vs baseline

### Sprint 5 — Allargamento sandbox + osservazione (settimane 9-10)

Solo se metriche Sprint 4 ok (conversion rate sandbox ≥ baseline manuale × 0.9):

1. Tier-2 abilitato in `SANDBOX_WHITELIST`, max 3/giorno
2. Soglie tightened su tier-1 (rimangono shadow-only)
3. Shadow path estendibile ad altri domini (KBLI, tax) — _vertical slice template_ riutilizzabile

### Sprint 6 — Documentazione + handoff (settimane 11-12)

1. Design doc retrospettivo: cosa ha funzionato, cosa no, cicatrici nuove
2. Vademecum entry su skill registry usage
3. Telegram playbook per Zero: come approvare/rejectare proposal
4. Decisione Sprint 7+: scalare a KBLI, oppure consolidare e iterare su renewals

---

## 5. Vincoli e contraints

### 5.1 Vincoli hard (non negoziabili)

- **No Anthropic paid API**: Claude solo via OAuth CLI (`backend/llm/claude_oauth_client.py`). Cf. CLAUDE.md global Golden Rule #13.
- **UU PDP compliance**: nessun PII cliente esce dalle macchine di Zero. Consiglio v2 mono-LLM Ollama è soluzione tecnica.
- **Embedding model frozen**: `text-embedding-3-small` (1536 dims). Le skill non devono toccare embedding.
- **2h/settimana di Zero per review/calibration**: target sostenibile, non superabile.

### 5.2 Vincoli soft (preferenze)

- DeepSeek $0.01/query OK per Consiglio v1 (decisioni meta, no PII).
- Ollama latency 30-120s accettabile per workflow human-in-loop (NON real-time).
- Worktree isolation per parallel work (cf. cicatrix `2026-04-29-untracked-files-lost`).

### 5.3 Cicatrici da rispettare

- **`2026-04-29-startup-failed-mask`**: heartbeat middleware deve segnalare `degraded` quando `app.state.startup_failed=True`, non `ok`.
- **`2026-04-29-drive-poll-attribute-error`**: skill che chiamano metodi su services devono verificare l'esistenza con AST contract test (cf. `test_drive_poll_service_methods.py`).
- **`2026-04-29-eventbus-redis-vs-pgnotify`**: nuove skill che producono eventi devono usare `EventBus.emit_pg` (delega a `outbox.publish`), non `pg_notify` raw.
- **`2026-04-29-untracked-files-lost`**: WIP commit ogni 10min su feature branch durante long sessions.

---

## 6. Gate aperti — Decisioni esplicite richieste a Zero

### 6.1 Policy PII per Consiglio v2 (BLOCCANTE per Sprint 3)

**Domanda a Zero**: sei d'accordo che Consiglio v2 (decisioni di business con PII cliente) usi _esclusivamente_ Ollama on Pro, accettando latency 30-120s e qualità single-model invece di multi-LLM voting?

**Alternativa**: Consiglio v1 multi-LLM con sanitize aggressive PII. **Rischio**: sanitize regex non è bulletproof. Bali Zero è UU PDP-regolata. La differenza tra "feature implementata da Claude" e "scelta aziendale di Zero" è importante qui.

**Stato**: in attesa di decisione. Il piano procede su base "B con nudge a D" — implementazione tecnica B, marker policy D.

### 6.2 Tier segmentation policy

**Domanda a Zero**: la segmentazione tier 1/2/3 calcolata da LTV (lifetime value USD) basata su sum invoice amounts è coerente con come Bali Zero pensa i clienti? Oppure servono ulteriori dimensioni (anzianità, settore, geografia)?

**Stato**: decisione da prendere durante Sprint 0.2. Se Zero conferma, procediamo. Se serve revisione, +2-3 giorni Sprint 0.

### 6.3 Whitelist skill sandbox iniziale

**Domanda a Zero**: la whitelist sandbox iniziale è `[propose_outreach, draft_wa_message]` (proposal + draft, NON send autonomo). L'invio resta umano (Sahira). È accettabile, oppure vuoi che anche l'invio sia autonomo entro Sprint 5?

**Stato**: scelta conservativa di default (no autonomous send). Sblocco invio autonomo solo dopo decisione esplicita Zero post-Sprint 4.

---

## 7. Metriche di successo

Per ogni sprint, metriche numeriche before/after (Pilastro 7 SYMBIOSIS).

**Conversion rate da solo è propaganda.** Senza onestà metrica, dopo 12 settimane il design retrospective dirà "Cell ha intercettato 47 rinnovi, +7pp vs baseline" mentre Adit ha ricevuto 3 chiamate furiose, 2 clienti hanno chiuso, Surya ha perso 8h su false positive. Il sistema misuratore deve essere onesto su sé stesso.

### 7.1 Per-Sprint output checks

#### Sprint 0

- **Output**: `client_segments` table popolata con 5000+ righe; `renewal_alert_outcomes` con backfill di 6+ mesi storia.
- **Verifica**: `SELECT tier, COUNT(*) FROM client_segments GROUP BY tier;` ritorna distribuzione coerente.

#### Sprint 1

- **Output**: `genome.yaml` enrolled da 26 → 58+ organi (auto-discovery sweep complete).
- **Verifica**: `genome_aggregator_sensor` classifica `green` per backend.api e 4 channel.

#### Sprint 2

- **Output**: 5 skill renewals invocabili da Cell shadow.
- **Verifica**: `decisions.jsonl` ha 100+ proposal/settimana di shadow path.

#### Sprint 3

- **Output**: prima sandbox execution end-to-end con Zero approve.
- **Verifica**: `renewal_alert_outcomes` ha prima riga con `observed_by='cell'`.

#### Sprint 6

- **Output**: design retrospective + Vademecum update.
- **Verifica**: cicatrici nuove documentate in `.claude/rules/cicatrix-scars.md`.

### 7.2 Dashboard 4-dimensioni (Sprint 4 onwards)

Una sola schermata Telegram (`/cell-stats` weekly), 4 sezioni — ogni dimensione copre un aspetto che conversion rate da solo non vede.

#### 7.2.1 Causale (counterfactual)

**Domanda**: Cell è la causa del rinnovo, o sarebbe successo comunque?

| Metrica                               | Definizione                                                                                                  | Target Sprint 5            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------- |
| `conversion_rate_sandbox`             | rinnovi / proposal sandbox executed in 30d window                                                            | ≥ baseline × 0.9           |
| `conversion_rate_baseline_historical` | rinnovi / KITAS expired stesso cluster (tier+nationality+sector), 24 mesi pre-Cell. Approccio 5.1.B          | aggiornato weekly          |
| `conversion_rate_synthetic_control`   | per ogni cliente Cell-outreach, twin matching su pool storico (no outreach), pair-wise diff. Approccio 5.1.C | aggiornato monthly         |
| `cell_impact_pp`                      | conversion_sandbox − conversion_synthetic_control                                                            | > +3pp con stat sig p<0.05 |

**Approccio scelto**: 5.1.B come metrica primaria (semplice, weekly), 5.1.C come validation periodica (monthly). 5.1.A (random control group) **NON adottato** — etica con clienti reali e opportunity cost real su tier-3.

#### 7.2.2 Valore (vs solo numerosità)

**Domanda**: i rinnovi intercettati hanno _valore_ per Bali Zero?

| Metrica                   | Definizione                                              | Target Sprint 5              |
| ------------------------- | -------------------------------------------------------- | ---------------------------- |
| `revenue_intercepted_usd` | sum revenue rinnovi sandbox in 30d window                | trend up                     |
| `quality_score_pct`       | rinnovi senza escalation/complaint nei 30gg post-execute | ≥ 90%                        |
| `sla_met_pct`             | rinnovi sandbox con practice completed entro SLA         | ≥ 85%                        |
| `lifetime_value_impact`   | retention 6+ mesi post-rinnovo via Cell vs baseline      | Sprint 12+ (richiede storia) |

#### 7.2.3 Costo (visibile e nascosto)

**Domanda**: quanto costa fare quello che Cell fa?

| Metrica                      | Source                                                      | Target    | Cosa fare se sfora                   |
| ---------------------------- | ----------------------------------------------------------- | --------- | ------------------------------------ |
| `zero_review_minutes_weekly` | Telegram approve/reject timestamps                          | < 120 min | Sandbox quota ridotta                |
| `team_load_minutes_daily`    | `practice_state_machine` time_in_state delta                | < 45 min  | Skill confidence threshold alzata    |
| `compute_cost_usd_monthly`   | Ollama inference + electricity Pro                          | < $20     | Hibernation aggressive (Modalità 5)  |
| `complaints_count_monthly`   | manual `complaint_log` table compilata da Adit ~5min/giorno | 0         | Sandbox sospeso, root cause analysis |

**5.3.D (complaints) richiede process change manuale Adit/Sahira/team**. ~5min/giorno per loggare cliente arrabbiato in `complaint_log` table. Sentiment analysis automatico su WA replies è **out of scope**, parcheggiato per Sprint 12+.

#### 7.2.4 Onestà sistemica (meta)

**Domanda**: Cell sta migliorando sé stessa o sta gaming la metrica?

| Metrica                       | Definizione                                                  | Range sano |
| ----------------------------- | ------------------------------------------------------------ | ---------- |
| `skill_confidence_volatility` | stddev(confidence_90d) / mean(confidence_90d) per ogni skill | 0.05-0.20  |
| `zero_reject_rate`            | rejected / total decided last 30d                            | 15-35%     |
| `sandbox_quota_utilization`   | sandbox executed / sandbox eligible last 30d                 | 60-95%     |

Volatility < 0.05 → over-fit on success (Cell mai sbaglia, sospetto). Volatility > 0.20 → instabile (skill non mature). Reject rate < 15% → Zero rubber-stamping. Reject rate > 35% → Cell scollegata da business reality. Quota utilization < 60% → Cell troppo conservativa (lascia sandbox quota inutilizzata). > 95% → Cell sempre al limite, alza il rischio di errore con pochi margini.

### 7.3 Decision Journal (datastore unico)

**File**: `apps/cell/data/decisions_journal.jsonl` (append-only, persistent volume Pro)

**Schema per riga**:

```jsonl
{
  "ts": "2026-08-04T09:32:00Z",
  "proposal_id": 4521,
  "skill": "propose_outreach",
  "client_id": 1234,
  "tier": 3,
  "ltv": 1420,
  "cell_confidence_at_proposal": 0.72,
  "cell_alternative_skills_considered": [
    "propose_renewal_quote",
    "flag_quality_issue"
  ],
  "decision": "approve",
  "who_approved": "zero",
  "decision_latency_s": 412,
  "executed_at": "2026-08-04T09:35:12Z",
  "outcome_30d": "client_renewed",
  "outcome_at": "2026-08-21T14:22:00Z",
  "revenue_usd": 200,
  "complaint": false,
  "cell_confidence_at_outcome": 0.74
}
```

**Doppio uso**:

1. **Datastore metriche**: dashboard 4D legge da qui (no JOIN su PG, jsonl streaming)
2. **Input Lamarckian loop**: Cell legge journal nelle modalità idle (Punto 4 — Modalità 4 self-modification) per ricalibrare skill confidence basandosi su pattern di reject + outcome

**`who_approved`** distingue Zero, auto-reject (48h timeout), team-delegation (vacation mode disabled per ora). **`cell_alternative_skills_considered`** è ciò che Cell ha valutato e scartato — utile per skill genesis Sprint 7+ (se Cell scarta sempre stessa alternativa per pattern simili, suggerisce nuova skill).

### 7.4 Goal-state Sprint 5 (sandbox allargabile a tier-2)

Tutti i seguenti devono essere veri:

- 7.2.1 `cell_impact_pp` > +3pp con p<0.05
- 7.2.2 `quality_score_pct` ≥ 90%
- 7.2.3 `zero_review_minutes_weekly` < 120 (margine vincolo human)
- 7.2.3 `complaints_count_monthly` = 0
- 7.2.4 `skill_confidence_volatility` ∈ [0.05, 0.20]
- 7.2.4 `zero_reject_rate` ∈ [15%, 35%]

Se anche **uno** sfora → Sprint 5 NON parte, Sprint 4 esteso di 2 settimane per calibrazione.

---

## 8. Rischi noti

| Rischio                                          | Impatto                                 | Mitigazione                                                                       |
| ------------------------------------------------ | --------------------------------------- | --------------------------------------------------------------------------------- |
| Sanitize PII ha buchi → leak a cloud             | Alto (UU PDP, brand reputation)         | Consiglio v2 mono-LLM Ollama, zero cloud per PII                                  |
| Ollama Pro down durante sandbox                  | Medio (sandbox blocca, shadow continua) | Graceful degradation: Cell non propone azioni con PII se Ollama down (Pilastro 4) |
| Conversion rate sandbox < baseline manuale       | Alto (segnala Cell sbaglia)             | Sprint 5 NON parte se Sprint 4 metriche flaky; rollback a shadow-only             |
| Zero satura su 21 approve/sett                   | Medio (workflow non sostenibile)        | Sandbox max 1/giorno tier-3 = 7/sett. Margine x3 vs limite Zero                   |
| State fragmentation (critica Gemini)             | Medio (debt tecnico)                    | Dispatcher esterno a Cell, 30 righe testabili in isolation                        |
| Auto-discovery PR-spam                           | Basso (UI noise)                        | Telegram digest aggregato settimanale, non PR-per-organ                           |
| Lamarckian loop diverge (skill confidence drift) | Medio (Cell impara cosa sbagliata)      | Soglie adattive solo dopo 30gg di shadow + sandbox; review umana ogni 4 settimane |

---

## 9. Out of scope (esplicitamente NON in questo design)

- KBLI vertical slice (Sprint 7+, dopo conferma renewals funziona)
- Tax vertical slice (Sprint 8+)
- Compliance autopilot full (esiste già `chain_compliance_autopilot`, non modificato)
- Frontend changes su `apps/mouth` o `apps/web` (no UI nuova in questo design)
- Channel additions (no nuovo channel oltre i 4 esistenti)
- Federation cross-machine Air↔Pro per skill (Sprint solo Pro per semplicità)
- LLM provider change (Anthropic OAuth resta primario, regola hard)

---

## 10. Riferimenti tecnici da costruire

- `apps/backend-rag/backend/services/skill/dispatcher.py` (NUOVO — sibling of existing `service.py`)
- 5 nuove righe nel `SEED_SKILLS` di `apps/backend-rag/backend/scripts/seed_initial_skills.py` (skill_id `crm:detect_expiring_kitas`, `crm:propose_renewal_outreach`, `crm:draft_wa_renewal_message`, `crm:measure_renewal_conversion`, `crm:update_renewal_confidence`)
- (Skill registry storage: `cell_core.genome` already provides — no new files)
- `apps/backend-rag/backend/app/middleware/heartbeat.py`
- `apps/backend-rag/backend/db/migrations_v2/149_client_segments.sql`
- `apps/backend-rag/backend/db/migrations_v2/150_renewal_alert_outcomes.sql`
- `apps/organism/organism/tools/discover_organisms.py`
- `apps/organism/organism/supervisor/consiglio_v2.py`
- `apps/organism/organism/launchd/com.nuzantara.genome-discovery.plist`

Refactor:

- `apps/cell/cell/cortex/skill_library.py` — already uses `cell_core.genome` (no refactor needed; verify import patterns are consistent with backend-rag's `services/skill/service.py`)
- `apps/organism/organism/genome.yaml` → +32 organi via auto-discovery PR
- `apps/organism/organism/supervisor/consiglio_gate.py` → estende `_CONSIGLIO_GATED_ACTIONS` con dominio business

---

## 11. UX Telegram (punto di contatto umano)

Dimensione critica: se l'UX Telegram è scomoda, tutto il resto fallisce. Zero è non-developer, mobile-first, ~2h/settimana sostenibili.

### 11.1 Timing notifiche

**Modalità A3 (threshold-based)** scelta:

- **Real-time** se urgenza ≥ critica: KITAS expiring 0-7d (~1-2 proposal/giorno)
- **Batch 09:00 WITA** per il resto (7-90d expiring)

Cutoff su `renewal_alerts.alert_type` esistente (`renewal_7d/30d/60d/90d`).

### 11.2 Format messaggio (variante B2)

```
🔔 Cell propose: rinnovo KITAS

Cliente: Marco R. (tier-3, LTV $1,420)
KITAS scade: 2026-05-14 (in 13 giorni)
Skill: propose_outreach + draft_wa_message
Confidence: 0.72 (calibrata su 47 cases tier-3 ultimi 90gg)

Razionale: cliente non ha rinnovato 1× in passato (2024) ma ha
risposto positivamente a 2 outreach precedenti. Sensor signals:
last interaction 31gg ago, no payment overdue.

Draft WA: [link mini-webapp]

[ Approve ]  [ Reject ]  [ Defer 24h ]  [ Show alternatives ]
```

3 informazioni dense + razionale 1 frase + 4 bottoni inline + link webapp draft (no testo lungo nel chat).

### 11.3 Defer + auto-reject (C2 + C5 hybrid)

- 3 bottoni granulari: `Defer 4h` / `Defer 24h` / `Defer to Mon`
- Auto-reject se nessuna risposta entro **48h** con warning serale prima dell'auto-reject ("Domani auto-rejection per X proposal pending")

### 11.4 Vacation mode (D4 + D2 fallback)

Zero settta `vacation_until=YYYY-MM-DD` via `/vacation` command. Durante quel periodo:

- Sandbox path completamente OFF (solo shadow continua)
- Zero notifications (no daily digest, no real-time)
- Recovery automatico al ritorno con summary settimana

Se Zero dimentica `vacation_until` → fallback D2 (auto-reject 48h) come ultima rete.

### 11.5 Implementazione

- **Bot Telegram**: estende `@Balizerobot` esistente (Pro OpenClaw listener), nuovo handler `/pending`, `/vacation`, `/cell-stats`
- **Storage**: `proposal_queue` table — `(proposal_id, payload, status, created_at, decided_at, deferred_until, who_approved)`
- **Mini-webapp draft**: subdomain `proposal.balizero.com` (Vercel), authenticated via Telegram WebApp init data (NO nuovo login system)

**Costo build**: 4-5 giorni in Sprint 3.

---

## 12. Cell idle behavior (cuore Era Post-Agentica)

Cell pulsa ogni 60s = **1440 pulse/giorno**. Proposal renewals KITAS = **~7-10/giorno**. Le **23h59min idle** sono il 99.3% del tempo di Cell — devono avere uno scopo. Senza idle attivo, l'organismo è solo un cron job.

### 12.1 Priority cascade (Sprint 3-5)

Cell decide cosa fare via priority deterministica:

```
1. Active proposal pending? → process (NOT idle)
2. Sensor signal degraded? → investigate (NOT idle)
3. Curiosity slot available? (max 3/giorno) → run curiosity engine
4. Self-modification opportunity? → optimize self
5. Dream slot available? (1/giorno, scheduled 02-06 WITA) → consolidate memory + journal
6. Hibernate (reduced pulse rate 300s)
```

### 12.2 Curiosity engine (modalità 3)

Cerca anomalie, pattern non spiegati, opportunità mancate. Esempi:

- "Cluster nationality=Italian, settore=tech rinnova al 100% senza outreach. Auto-renewing pattern?"
- "Sensor OAuth Drive degraded sempre venerdì pomeriggio. Pattern temporale?"
- "Cluster nationality=US ha 0 KITAS expiring nei prossimi 60gg, vs ~15/mese storico. Anomalia?"

**Output policy**: scrive in `apps/cell/data/curiosity_log.md` (NON Telegram real-time). **Digest settimanale Telegram con TOP 3 insight** (scelta utente). Zero approva → diventano proposal Sprint successivo.

### 12.3 Self-modification (modalità 4) — la vera Era Post-Agentica

Cell ottimizza sé stessa:

| Operazione                               | Trigger                             | Soglia auto vs Zero approve                                          |
| ---------------------------------------- | ----------------------------------- | -------------------------------------------------------------------- |
| Skill confidence calibration             | Outcome osservato                   | Auto se drift < 0.2 in 30gg, Zero approve se >0.2                    |
| Sensor timing optimization               | 95% letture sono no-op per N giorni | Auto se nuovo intervallo < 2× current, Zero approve se >2×           |
| Memory pruning (episodic)                | Memory size grows beyond budget     | Auto se < 100 episodi/giorno, Zero approve se >100                   |
| **Skill genesis** (proposta nuova skill) | Pattern ricorrente in journal       | **OUT of Sprint 5**, parcheggiato Sprint 7+ post-renewals validation |

### 12.4 Hibernation (modalità 5)

- 02:00-06:00 WITA: pulse 300s (5min), Ollama sleep
- Weekend: pulse 180s, no curiosity exploration
- Vacation mode: hibernation aggressive

Riduce CPU draw <5% laptop, rispetta Pilastro 6 (sovranità locale).

### 12.5 Da Sprint 7+ (out of current scope)

Cascade deterministica → **attention budget self-allocated** via `homeostatic_controller`. Stress alto → meno curiosity, più hibernation. Stress basso → più curiosity, più self-modification. Più organico, ma richiede 12 settimane di dati prima per calibrarlo.

---

## 13. Successor

Dopo Sprint 6, naturale evoluzione (NON in questo design):

- **Sprint 7+**: vertical slice KBLI con stesso template skill registry
- **Sprint 9+**: tax compliance autopilot integrato a skill registry
- **Sprint 12+**: Cell goal-driven mode (4b del brainstorm) — Cell ottimizza fitness function definita esplicitamente da Zero
- **Sprint 16+**: Federation skill registry Air↔Pro (Mata Garuda, OSINT)

Il design corrente ferma a renewals KITAS Sprint 6 perché: vertical slice deve **provare** prima di scalare. SYMBIOSIS Pilastro 7: "Numeri prima" significa che ogni nuovo dominio richiede metriche before/after del precedente.

---

**Stato**: design approvato in dialogo con Zero, in attesa di sign-off finale prima di passare a `superpowers:writing-plans` per implementation plan dettagliato.

**Gate aperti che richiedono Zero PRIMA di Sprint 3**:

1. §6.1 — Policy PII Consiglio v2 (BLOCCANTE)
2. §6.2 — Tier segmentation logic (NON bloccante, posticipabile a Sprint 0.2)
3. §6.3 — Whitelist sandbox iniziale (NON bloccante, default conservativo applicabile)
