# scripts/usage/ — Consumi flotta (dashboard + collector seat)

> Creato 2026-08-09 da sessione Cowork (Fable 5). Contesto: FLEET_TOPOLOGY.json + AGENTS.md §17.

## Cosa c'è

| File | Cosa fa |
|---|---|
| `usage-dashboard.html` | Dashboard self-contained. Sezione API **già viva** (snapshot dal ledger PG `llm_cost_events`, mig 117). Sezione seat si accende quando il collector gira accanto (fetch di `seat_usage_snapshot.json`). |
| `seat_usage_collector.py` | Parsa i log locali delle CLI (Claude ×N profili, Codex ×2 CODEX_HOME, agy, kimi) → snapshot JSON. **NON testato sui log reali: PENDING-ARMS.** |
| `seat_map.json` | Generato al primo run: mappa profili locali → seat A1/A2/A3/AZ/O1/O2. Da editare dopo l'installazione di cswap. |
| `com.nuzantara.seat-usage.plist.template` | Template LaunchAgent (StartInterval 1800, no secrets). NON in `infra/launchagents/` finché non testato — spostarlo lì solo all'arming. |

## La verità sulle fonti (matrice onestà)

| Fonte | Metodo | Stato |
|---|---|---|
| API a consumo (gemini, claude_oauth, embeddings, openrouter) | ledger PG `llm_cost_events` → già esportato ogni 30' in `~/.agent/cost-ledger/` (`cost_ledger_export`) + cost-breaker armato | ✅ VIVO |
| Claude Max/Team (4 account) | nessuna API pubblica quota → parse transcript `~/.claude*/projects/**/*.jsonl` per profilo (pattern ccusage); finestre 5h/7d stimate dai timestamp | 🔧 collector da armare |
| Codex Pro (2 account) | parse `$CODEX_HOME/sessions/**/*.jsonl` per home | 🔧 collector da armare |
| Google AI Ultra (agy) | nessuna API quota → conteggio invocazioni dai log + quota % solo in settings UI | 🟡 parziale per natura |
| Kimi Allegro | conteggio invocazioni log CLI | 🟡 parziale |
| Alibaba Token Plan (crediti) | console Model Studio; endpoint crediti da individuare in PROBE-1; usage per-request nelle risposte API | ⏳ post PROBE-1 |
| Infra (Fly/Vercel/Upstash) | fatture console; fuori scope v1 | ⏳ |

## Arming (sessione Mac, in ordine)

1. `python3 scripts/usage/seat_usage_collector.py` → verifica parse sui log VERI (aspettarsi schema-drift: sistemare i campi, è scritto difensivo).
2. Editare `seat_map.json` con i profili cswap reali → seat.
3. Test 2-3 run; poi spostare il plist template in `infra/launchagents/` e armarlo col pattern degli installer esistenti (wrapper, no secrets, W64 graceful).
4. Servire la dashboard: opzione minima `python3 -m http.server` nella dir; opzione vera: aggiungerla a `apps/nuz-status-mac` (PENDING).
5. PROBE-1: aggiungere il poller crediti DashScope al collector.

## Estensioni future

- Pannello Grafana (lo stack monitoring/ esiste già) leggendo lo stesso snapshot.
- Quota % Anthropic via cswap (`cswap list` espone finestre 5h/7d) — parse dell'output come sorgente aggiuntiva.
- Refresh automatico dell'artifact Cowork via scheduled task.
