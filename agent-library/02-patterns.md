# Agent Library — Patterns (hand-written 2026-05-17, revised post 3-LLM panel)

<!-- DO NOT auto-regenerate — this file is curated by hand. -->
<!-- Companion to 01-inventory.md (auto-gen) and 03-lessons.md (hand-written). -->
<!-- Revised 2026-05-17 after 3-LLM panel review (Gemini + DeepSeek + Codex) -->
<!-- caught: pattern selection overfit to WR2/LLM-quality, missed infra primitives. -->

9 recurring patterns extracted from 16 Claude subagents + 35 agentic crons +
106 infra crons + cicatrix-scars. Each entry: nome, quando-usarlo,
anti-pattern, esempio concreto `file:line`, trade-off, scar correlato.

**Pattern = reusable design primitive** (trigger, invariant, implementation
shape). Lesson = incident evidence showing why the pattern exists.
Lessons live in `03-lessons.md`.

## Index

| #   | Pattern                                            | Category      |
| --- | -------------------------------------------------- | ------------- |
| 1   | Single-flight / lease / idempotency guard          | concurrency   |
| 2   | Durable queue / outbox / DLQ / replay contract     | reliability   |
| 3   | Heartbeat / liveness / watchdog contract           | observability |
| 4   | Provider cascade + circuit breaker + degraded-mode | resilience    |
| 5   | Empirical post-action verification                 | integrity     |
| 6   | Ground-truth verifier with freshness check (NB)    | ground-truth  |
| 7   | Bounded adversarial review gate                    | quality-gate  |
| 8   | Parallel wave orchestration with capacity caps     | orchestration |
| 9   | Artifact provenance / hash anchoring               | integrity     |

---

## Pattern 1: Single-flight / lease / idempotency guard

**Quando usarlo**: cron loop o orchestrator che pesca task da queue condivisa. Senza claim atomico, due worker possono processare la stessa unità.

**Anti-pattern**: `SELECT pending → process → UPDATE done` senza lock — race window 50ms-5s, basta perché 2 worker overlapping facciano doppio side-effect (doppio email, doppia Telegram alert, doppio invoice).

**Esempio concreto**: `apps/backend-rag/backend/services/canva_renderer_v2/_pg.py:48-68` (lease CAS pattern)

```python
async def acquire_lease_and_fetch(
    conn: asyncpg.Connection, *, draft_id: UUID | str, lease_owner: str,
):
    """CAS lease + return row payload, or None if another process won."""
    # UPDATE ... SET lease_owner = $1 WHERE id = $draft_id AND lease_owner IS NULL
    # RETURNING ...
    # If RETURNING is empty → another worker already won the lease
```

CAS atomico in SQL: UPDATE...WHERE lease_owner IS NULL RETURNING. Worker che perde la race riceve None e skippa. Watchdog separato (`scripts/wr2_canva_lease_watchdog.py:28`) resetta lease orfani >15min con `reset_stale_leases()`.

**Trade-off**: 1 extra round-trip DB per claim + complessità watchdog vs zero-duplicate guarantee. Costo accettabile su side-effect non-idempotenti (email, payment, mutation esterna). Skip su task puro read-only.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_orchestrator_issue_race.md` (orchestrator + sub-session 5-30s race window → duplicate GitHub issue).

---

## Pattern 2: Durable queue / outbox / DLQ / replay contract

**Quando usarlo**: ogni side-effect cross-process che deve sopravvivere a crash, restart, deploy. Producer scrive a outbox in stessa tx del side-effect; consumer separato drena outbox; failures vanno a DLQ con retry policy.

**Anti-pattern**: producer fires-and-forgets (HTTP POST, pg_notify, Redis publish) senza outbox — listener crash window = eventi persi for-ever. Cf. cicatrix `EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams`.

**Esempio concreto**: `~/Desktop/nuzantara/scripts/intel-lake-outbox-drain/intel-lake-outbox-drain.py` (outbox drain pattern)

```python
# Producer (in transaction):
INSERT INTO events_outbox (channel, payload) VALUES (...)
pg_notify('channel', payload || {_outbox_id})
# COMMIT atomico

# Consumer (separato, ogni 60s):
# SELECT pending FROM events_outbox WHERE consumed_at IS NULL
# → dispatch → mark consumed
```

Companion: `scripts/outbox_prune.py` (daily, retention 30d), `~/.claude/agents/.../dlq-autopilot` (`launch_dlq_autopilot.sh`, every 30min — autonomous DLQ replay). Inventory mostra anche `intel_dedup_gateway.py` (atomicamente check+claim per cross-stream dedup).

**Trade-off**: 1 extra INSERT per event + 1 cron drainer + 1 DLQ + 1 pruner vs eventi persi su listener-disconnect (max_age_minutes=60 per `PG_CHANNEL_MAP` per Symbiosis Law 4). Costo accettabile su event critical (regulatory deltas, intel signals, CRM mutations).

**Scar correlato**: `.claude/rules/cicatrix-scars.md` (EventBus PG LISTEN/NOTIFY entry — Phase 1 PR #342 shipped outbox.publish/acknowledge/replay).

---

## Pattern 3: Heartbeat / liveness / watchdog contract

**Quando usarlo**: ogni long-running daemon (supervisor, listener, sync). Distinguere 4 stati: alive (recent heartbeat), stuck (no heartbeat N min), stale (heartbeat ma metrics ferme), silently-degraded (heartbeat + metrics ma output wrong).

**Anti-pattern**: monitor solo `process running` (PID exist) — non distingue stuck-loop da working. Heartbeat senza watchdog = log nessuno guarda.

**Esempio concreto**: `~/Desktop/nuzantara/scripts/wr2_supervisor.py:455-482` (`_write_heartbeat` con dedicated conn)

```python
async def _write_heartbeat(conn_hb: asyncpg.Connection, note: str) -> None:
    """Insert one row into wr2_supervisor_heartbeat AND write Innervation
    Genoma file heartbeat for the sentinel-aggregator."""
    _write_organism_heartbeat("wr2.supervisor", "ok", note)
    try:
        await conn_hb.execute(
            "INSERT INTO wr2_supervisor_heartbeat (note) VALUES ($1)",
            (note or "")[:200],
        )
    except asyncpg.UndefinedTableError:
        # Migration not yet applied → degrade silently
```

Due canali ridondanti (DB row + file) — se uno fail, l'altro tiene. Watchdog separato: `pg-organism-bridge-watchdog.sh` (every 5min), `wr2_canva_lease_watchdog.py` (every 10min), `fly-restart-loop-detector.sh` (every 15min).

**Trade-off**: 1 INSERT/scrittura per intervallo HEARTBEAT_INTERVAL_SEC + 1 cron watchdog vs silent-stuck daemon discovered hours later. Cap pratico: heartbeat ogni 30-60s per daemon critical, ogni 5-15min per batch jobs.

**Scar correlato**: `.claude/rules/cicatrix-scars.md` (Backend prod down — drive_poll_service flood non-rilevato per 18min causa `Application startup complete` never logged — login healthcheck probe + `_lifespan_stuck_check` shipped post-incident).

---

## Pattern 4: Provider cascade + circuit breaker + degraded-mode boundary

**Quando usarlo**: cron job autonomo che dipende da provider esterno (LLM quota, API, external DB). Cascade fallback OK, ma serve breaker state + cooldown + semantic-validation per non mascherare bad output as success.

**Anti-pattern**: cascade puro stdout-grep senza breaker state — Tier-1 sempre tentato anche dopo 10 fail consecutivi (waste latency). Senza degraded-mode boundary, Tier-4 (Ollama local) output può finire in cliente come fosse Tier-1 quality.

**Esempio concreto**: `~/scripts/regulatory-watcher-run.sh:33` (4-tier cascade — incompleto: manca breaker state)

```bash
# Cascade tier 1 → 2 → 3 → 4
if [ $EXIT -eq 0 ] && ! grep -qE "out of extra usage|usage limit|quota exceeded|rate.limit" "$TMPOUT"; then
    SUCCESS=1
    USED_LLM="claude-sonnet-4-6"
fi
```

L'esempio attuale è cascade puro. Pattern completo richiederebbe: (a) state file con `{tier1: {failures: N, cooldown_until: ts}}` per skip-fast quando tier già exhausted; (b) `degraded_mode` flag che, se Tier-4 (Ollama) consegna, marca output `status=draft-only-not-client-safe`; (c) semantic gate (es. JSON valid + new_today_count > 0 plausibile). Cf. CLAUDE.md §"Multi-LLM cascade for autonomous agents".

**Trade-off**: state file + breaker logic (~50 LOC) + degraded boundary check vs masked-failure cost (Tier-4 output → cliente con tonalità sbagliata). Beneficio: zero-stall + zero-silent-quality-regression.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29 — 3 cloud LLM exhaust simultanei, solo Ollama consegnò; 1/4 OK come threshold ma serve degraded-mode marking).

---

## Pattern 5: Empirical post-action verification

**Quando usarlo**: dopo ogni side-effect non-locale (Write, Bash mutation, deploy, enqueue, publish, migration apply, PR create, source sync). Lo status code è il livello più alto di indirezione — sotto vivono i fail silenziosi.

**Anti-pattern**: trust del solo exit code 0 / HTTP 200 / "success" log line. Pattern di fail silenzioso: file scompaiono (sibling cleanup), processo "completa" con exit=0 (launchd masking), metric=0 con log success ("Applied: 26 migrations" stale count). Cf. memory `lessons_hallucinating_tool_output_is_diabolical.md` regola #3 ("dopo Write ri-verifica con ls -la SUBITO").

**Esempio concreto**: `~/scripts/regulatory-watcher-run.sh:87-89` (empirical disk-state check post-LLM)

```bash
# Empirical disk-state verification (lesson 2026-05-13 anti-hallucination):
# Claude/Gemini may narrate "JSON emitted" without actually writing the file.
if [ ! -f "$DELTA_JSON" ]; then
    echo "[$(date)] WARNING: $USED_LLM reported success but $DELTA_JSON does NOT exist on disk — possible hallucinated tool output, skipping eventbus publish" >> "$LOG"
fi
```

Pattern generalizzato: post-deploy `curl health endpoint`; post-migration `SELECT version FROM schema_migrations`; post-PR `gh pr view --json state`; post-Write `ls -la $file`. Verify-not-trust è la versione orchestration di questo pattern.

**Trade-off**: 1 extra Read/curl/SELECT per side-effect (~10-100ms) vs catastrophic decision su world-state fittizio. Hard rule: sempre verify side-effect critical.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_hallucinating_tool_output_is_diabolical.md` (5 regole anti-hallucination, hard rule globale CLAUDE.md).

---

## Pattern 6: Ground-truth verifier with freshness check (NotebookLM)

**Quando usarlo**: domain-critical query (regulatory, KBLI, visa, tax, property) dove single-LLM hallucination su normativa Indonesia = costo catastrofico. NB-INTEL specifico per il dominio funge da ground-truth.

**Anti-pattern**: NB query senza freshness check (sources NB possono essere stale — Permenkumham 22/2023 superato da emendamento 2026); NB sbagliato per dominio (visa→NB-1, tax→NB-4, property→NB-5 — querying wrong NB ritorna NOT_FOUND fingendo che la regulation non esista); council 4-LLM su ogni query (overhead 30s+).

**Esempio concreto**: `~/.claude/agents/wr2-brief-interpreter.md:33-44`

```yaml
### Step 2 — RAG against NotebookLM

NB routing:
- `visa` → NB-1 (Bali Zero legal/immigration)
- `tax` → NB-4 (Bali Zero tax)
- `property` → NB-5 (Bali Zero property)
- `regulatory` → NB-1 + cross-check against NB-INTEL family
```

Estrae citation verbatim (`PP 18/2021`, `KEP-71/PJ/2026`) + concrete numbers + freshness signal (data ultima ingest source NB). Freshness check NON è ancora implementato in wr2-brief-interpreter — è gap noto, da aggiungere.

**Trade-off**: NB query 3-8s vs single-LLM <1s + freshness re-verify. NB sources count vincolata (60 notebook, 2970 sources — memory `reference_notebooklm_arsenal_full.md`). Skip su low-stakes Q&A interno.

**Scar correlato**: preventivo (cf. CLAUDE.md §"Federation Orchestrator" "KBLI, visa, normativa → Gemini search; Grounding → NotebookLM oracolo").

---

## Pattern 7: Bounded adversarial review gate

**Quando usarlo**: pre-publish gate su output high-stakes (dossier, research, quote, strategy, spec critical-path). Fan-out parallel a 2-4 reviewer adversarial con cap iterazioni.

**Anti-pattern**: single-reviewer (mono-bias provider-correlato); loop infinito di refinement (devils-advocate caught empirically PPh21 Q3 2026: P4-P7 sono medium-only nitpicks editorial); review sequenziale (slow + biases later LLM by earlier output); skipping "il design sembra ovvio" — l'ovvio è dove i killer flaw si nascondono.

**Esempio concreto**: 2 invocations distinte ma stesso pattern.

Pre-spec-approval: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/feedback_always_review_spec_with_4_llm.md`

```
Fan out to 3 sibling LLMs in PARALLEL: Gemini + GPT-5.5 codex + DeepSeek V4 Pro
(+ NB-1 4° panelist se UUID known). Sintesi convergence/divergence:
3/3 converge → CRITICAL revise; 2/3 → SIGNIFICANT flag; 1/3 → trust majority.
```

Pre-publish artifact: `~/.claude/agents/devils-advocate.md` ("find the legal flaw, the tax miscalculation, the missing regulation, the hallucinated KBLI code"). Cap 3 iter da `lessons_devils_advocate_loop_pattern.md`.

**Trade-off**: $0.01-0.05/section + 2-5min wall vs ship-broken-design 2-3h debug + rollback + client-facing damage. Skip esplicito su user override "skip panel".

**Scar correlato**: preventivo (rule 2026-05-13 — FileTokenStorage v1 sarebbe stato shipped broken senza il panel; questo stesso PR catched 4 CRITICAL via 3-LLM panel pre-merge).

---

## Pattern 8: Parallel wave orchestration with capacity caps

**Quando usarlo**: ≥2 task indipendenti senza shared state né dipendenze sequenziali. Orchestrator dispatcha N agent paralleli (cf. `superpowers:dispatching-parallel-agents`). Topology centralized (orchestrator-led) preferita: error amplification 4.4× vs independent (no-coord) 17.2× (Kim et al. 2025 arxiv 2512.08296).

**Anti-pattern**: >4 sessioni parallele se ≥1 tocca prod esterna (LLM provider capacity exhaustion wave-level); brainstorm cap >3 scambi (gonfiamento scope FASE 2 wave 2026-05-07); scope esterno-irreversibile in wave parallela (prod deploy concorrente); independent topology (peer-to-peer no coordination → 17.2× error).

**Esempio concreto**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_wave_pacing_design_rigor.md`

```
wave 6-sessioni 2026-05-07: 5 chiuse fast, FASE 2 gonfiata. 3 cause
evitabili: brainstorm no-cap, design review missing, scope esterno-
irreversibile in wave parallela. Cap brainstorm 3 scambi, design review
Codex sandbox, smoke runtime deps al design time, max 4 sessioni parallele
se 1 tocca prod esterna.
```

**Trade-off**: wall-clock ~N× faster vs coordination overhead + capacity-exhaustion risk wave-level. Sweet spot 2-4 agent. Cap explicit always.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29 — Codex+Gemini+NLM simultaneous exhaust).

---

## Pattern 9: Artifact provenance / hash anchoring

**Quando usarlo**: pipeline che riusa asset (immagini, embedding, document fragment) da run precedenti. Ogni reuse decision deve essere loggata con source + hash, mai silenziosa.

**Anti-pattern**: trust del filename/metadata senza hash check (filename uguale, contenuto diverso); silent reuse (`cp ../prev/asset .` senza log); placeholder reuse mascherato come "fresh asset". Sprint S11 docet: 12 caroselli con stesso hero "paper on dark desk".

**Esempio concreto**: `~/.claude/agents/wr2-design-architect.md:77` (Contract C — sha256 anchor check)

```
Silent reuse of placeholders from a prior carousel directory (e.g.,
`cp ../test-1/placeholder-*.jpg .`) is forbidden. Each reuse decision must
be logged in `slides.json` as `image_source: "anchor:<file>"` or
`image_source: "imagegen:<codex_session>"`.
```

Verifica: `_audit-checklist.sh` mode `MODE=hero-sha` (line 41) — compute anchor sha + every hero sha, asserts per slide_spec.image_source declaration. Pattern generalizzabile oltre image: embedding checksum, document fragment hash, generated code hash.

**Trade-off**: 1 sha256 hash + log line per asset (~50ms × N) vs silent-reuse disaster (12 identical carousels, reputational damage). Costo accettabile sempre — check è cheap, fail è expensive.

**Scar correlato**: S11 hero monotone-template trap (preventivo dopo S11, documentato in agent description di `wr2-image-prompt-author`: "Avoids the monotone-template trap from S11").
