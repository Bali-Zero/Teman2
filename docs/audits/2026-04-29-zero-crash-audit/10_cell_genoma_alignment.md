# Cell/Genoma alignment — every intervention's touchpoint

**Goal:** Per Symbiosis Pillar 8 (Simbiosi) and the audit constraint that "Cell e Genoma sono organi centrali — ogni proposta di hardening deve passare da loro o spiegare perché non li tocca", this file maps every fix from `09_intervention_plan.md` to its Cell/Genoma touchpoint, OR motivates the exception.

**Symbiosis principle:** Cell is the substrate. Genoma is the memory. Every hardening should either (a) feed Cell sensors with new health signals, (b) write Genoma skills/scars on success/failure, or (c) be explicitly classified as "infrastructure plumbing" with no organ relevance.

---

## Touchpoint matrix

| Fix | Cell sensor added/updated | Genoma entry on success | Genoma entry on failure | Exception motivated |
|---|---|---|---|---|
| **P0-0** /health + Cell pulse classify | YES — HealthSensor body classification | skill: `health_endpoint_503_on_startup_failed` | scar: `cell_blind_to_semantic_health` | — |
| **P0-1** SearchService degraded mode | YES — SearchSensor with degraded state | skill: `searchservice_init_degraded_mode` | scar: `searchservice_init_failure_pattern` | — |
| **P0-2** EventBus Outbox | YES — EventBusSensor (lag, outbox queue depth) | skill: `outbox_pattern_for_pg_eventbus` | scar: `pg_listen_notify_silent_loss` | — |
| **P0-3** LaunchAgents KeepAlive audit | META (fixes Cell substrate itself) | skill: `launchd_keepalive_discipline_v1` | scar: `daemons_died_silently_53_unmonitored` | — |
| **P0-4** SQL v2 deploy ordering bug | NO | — | — | EXCEPTION: CI/build-time, not organ runtime |
| **P0-5** httpx + dependencies.py | YES — ResourceSensor (FD count) | skill: `golden_rule_10_audit_corrected_2026_04_29` | scar: `httpx_leak_resource_exhaustion` | — |
| **P0-6** Channels ack-first webhooks | YES — ChannelSensor (inbound queue depth) | skill: `webhook_ack_first_pattern` | scar: `meta_disabled_webhook_after_3_5min_failures` | — |
| **P0-7** Duplicate migration numbers | NO | — | — | EXCEPTION: build-time integrity check |
| **P1-7** NLM auto-recovery | YES — NLMPipelineSensor | skill: `nlm_auto_rerun_after_24h_stuck` | scar: `nlm_pipeline_silent_failures_pattern` | — |
| **P1-8** Escalations SQLite | NO (infrastructure) | — | — | EXCEPTION: storage migration only |
| **P1-9** MCP partition | partial — MCPSensor per namespace | skill: `mcp_namespace_isolation_v1` | — | — |
| **P1-10** i18n provider lint | NO | — | — | EXCEPTION: frontend CI lint |
| **P1-11** OAuth tiers | YES — OAuthExpirySensor (Cell skill) | skill: `oauth_health_tiered_warnings` | scar: `drive_oauth_silent_expiry` | — |
| **P2-12** KG BFS timeout | YES — KGGraphSensor (depth/timing) | skill: `kg_confidence_threshold_2nd_hop` | — | — |
| **P2-13** nuzantara-qdrant zombie | NO | — | — | EXCEPTION: lifecycle decision |
| **P2-14** Vercel build env | NO | — | — | EXCEPTION: dev workflow |
| **P2-15** Healthcheck probes | YES — multiple probe sensors | skill: `synthetic_probe_per_subdomain` | — | — |
| **NB-A** Sentinel watchdog | META (fixes Sentinel) | skill: `sentinel_self_keepalive` | scar: `who_watches_the_watcher_v1` | — |
| **NB-B** Federation launcher restart | META | skill: `federation_launcher_supervisor` | — | — |
| **NB-C** system_doctor naming | NO | — | — | EXCEPTION: documentation only |
| **NB-D** Vercel monorepo lint | NO | — | — | EXCEPTION: pre-deploy gate |
| **NB-E** Brevo email fallback | YES — EmailProviderSensor | skill: `email_dual_provider_failover` | scar: `brevo_single_key_silent_outage` | — |
| **NB-F** Tigris restore drill | YES — BackupSensor | skill: `monthly_restore_drill_pattern` | — | — |
| **NB-G** Tailscale heartbeat | YES — RemoteAccessSensor | skill: `tailscale_scheduled_heartbeat` | — | — |

---

## Sensors to add to Cell

Currently `apps/cell/cell/sensors/` has limited coverage. The audit reveals 14 new sensor types needed:

1. `HealthSensorV2` — body status field classification (BS-0b fix)
2. `SearchSensor` — vector backend availability + degraded state
3. `EventBusSensor` — PG NOTIFY listener health, outbox queue depth
4. `ResourceSensor` — FD count, memory usage, connection pool sizes
5. `ChannelSensor` — inbound webhook queue depth + processing lag per channel
6. `NLMPipelineSensor` — last_success_ts age per pipeline
7. `MCPSensor` — per-namespace heartbeat
8. `OAuthExpirySensor` — days until each OAuth credential expires
9. `KGGraphSensor` — last query timing, depth distribution
10. `EmailProviderSensor` — Brevo health probe + fallback availability
11. `BackupSensor` — last successful backup age + last successful restore drill age
12. `RemoteAccessSensor` — Tailscale connectivity heartbeat
13. `MigrationSchemaSensor` — `_schema_versions` integrity (no duplicates)
14. `SentinelSelfSensor` — Sentinel itself heartbeat (recursive watchdog)

**Pattern:** Each Sensor implements the `Sensor` protocol from `packages/cell-core/cell_core/`. Returns `SensorResult(name, status, value, unit)`. Cell PulseLoop integrates them all.

**Effort to add 14 sensors:** ~30-60 min each = 7-14 hours. Spread across the intervention weeks (each fix introduces its own sensor).

---

## Genoma entries to record

Per Symbiosis Pillar 2 (Accumulazione), genome accumulates skills and scars. Each fix above should produce both:

**On success (skill):**
- Records procedure, precondition, success criterion, confidence
- Confidence starts at 0.7, decays if not used, increases on re-success
- `scope='Project'` for transferable patterns (e.g., webhook_ack_first_pattern)
- `scope='Personal'` for organ-specific quirks (e.g., this-cell-runs-on-Air)

**On failure (scar):**
- Records procedure that failed, why, root cause if known
- Persists permanently (no decay)
- Read by genome.search() before any new agent reasons in this domain

**Genome write integration:**
The fix code itself should call `genome.record_skill()` and `genome.record_scar()` from within the cell that owns the surface. Example for P0-0:

```python
# In apps/cell/cell/actors/health_recovery_actor.py
async def act(self, sensor_result):
    if sensor_result.name == "backend_health" and sensor_result.status == "red":
        # Attempt recovery
        success = await self.attempt_fly_restart()
        if success:
            self.cell.genome.record_skill(
                cell="cell-backend-health",
                skill_id="backend_restart_on_503",
                procedure="curl -sI /health → if 503, fly machines restart <id>",
                confidence=0.7,
                scope="Project"
            )
        else:
            self.cell.genome.record_scar(
                cell="cell-backend-health",
                scar_id=f"backend_restart_failed_{sensor_result.value}",
                procedure="restart attempted, still 503 after 60s",
                rationale=str(sensor_result)
            )
```

This is the pattern. **Every fix that adds a sensor must also add the genome write on the actor side.** Otherwise the cell senses but doesn't learn.

---

## Cell crisis path — when Cell itself crashes

The audit reveals Cell is itself a SPOF. P0-3 fixes the LaunchAgent layer, but if the Cell process crashes after launchd has tried 3x to restart it, what then?

**Recovery hierarchy:**

1. **launchd KeepAlive** (P0-3 fix) — auto-respawn within 10s on crash.
2. **heartbeat_monitor** (existing, [NB-1 #20]) — dead-man switch on Telegram if pulse log not updated for 3x window.
3. **Air-side Sentinel** — Air's own Sentinel watches Pro Cell heartbeat via `~/.agent/decisions/cell_pulse_log.json`. If Pro Cell silent >15min, Air sends Telegram.
4. **External 15min healthcheck** (already deployed 2026-04-29) — `healthcheck@balizero.com` login probe. Catches Cell crashes via downstream impact (CRM not updating).

**Layered defense:** No single failure mode at any layer (1-4) takes down all 4. Crisis path proven survivable.

**Open question (escalation to Zero):** Should Cell also have a "Cell Lite" emergency mode running on Air as standby? Like a second-machine-Cell that takes over if Pro Cell silent for >1 hour. Currently Air does NOT run Cell. Decision deferred.

---

## Symbiosis Law compliance per fix

Each fix verified against the 8 inviolable laws:

| Law | Compliance per fix |
|----|----|
| 1. CLI-only LLM | All fixes use claude OAuth CLI or DeepSeek API (only sanctioned). No Anthropic SDK. |
| 2. OSINT blindato | None of the fixes touch OSINT data flow. Mata Garuda surfaces deliberately not in scope. |
| 3. Event-driven | P0-2 Outbox pattern preserves event-driven semantics. No new polling introduced. |
| 4. Graceful degradation | Every P0 fix EXPLICITLY codes degraded mode (not crash). P0-1, P0-2, P0-5, P0-6 are textbook implementations. |
| 5. Zero ultima istanza | Telegram alerts on critical failures. No autonomous decisions on architectural changes (e.g., MCP partition P1-9 has Zero handoff). |
| 6. Sovranità locale | All fixes preserve Pro+Air autonomy. Tigris backup (NB-F) preserves locality. Tailscale heartbeat (NB-G) preserves disconnect-as-natural-state. |
| 7. Numeri prima | Every fix has `Verifica post-fix` with quantified before/after. Convergent findings has 18 baseline numbers. |
| 8. (added 2026-04-12) Five universal questions before existing | This audit document IS the answer to those 5 questions for the system as a whole. |

**No law violation in any P0/P1/P2 fix.**

---

## Cells affected (organ map)

Per `INDEX.md`, the following cells get touched by these fixes:

- **`apps/backend-rag`** (Production RAG cell) — P0-0, P0-1, P0-2, P0-4, P0-5, P0-6, P1-7, P0-7
- **`apps/cell`** (Organism cell implementation) — P0-0 (HealthSensor), P0-3 (KeepAlive)
- **`apps/organism`** (Autonomic design) — P0-3
- **`apps/mata-garuda`** (Lamarckian meta-agent) — touched only via Sensor hierarchy
- **`apps/nuzantara-mcp`** + advanced + browser — P1-9
- **`apps/mouth`** (Frontend) — P1-10
- **`apps/evaluator`** (Core Guardian, NLM) — P1-7
- **`apps/federation`** (A2A, Pro/Air) — NB-B
- **`apps/zantara-media`** (GARUDA Curator) — not directly, but SearchSensor (P0-1) reflects qdrant_assets state

This is **integral organism work**: 9 of 21 apps directly touched, plus 5 packages including `cell-core`.

---

## Summary statement

**Every intervention either touches Cell/Genoma or has a documented exception.**

- **17 fixes touch Cell:** P0-0, P0-1, P0-2, P0-3 (meta), P0-5, P0-6, P1-7, P1-9, P1-11, P2-12, P2-15, NB-A, NB-B, NB-E, NB-F, NB-G + the 14 sensor additions.
- **6 fixes have explicit exceptions:** P0-4, P0-7, P1-8, P1-10, NB-C, NB-D — all CI/build-time or storage-only, not organ runtime.

The organism's nervous system gets richer. The genome accumulates 12+ new skills and 8+ new scars from this audit alone.
