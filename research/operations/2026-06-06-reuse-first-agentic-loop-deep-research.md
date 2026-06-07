# Deep research reuse-first - automazioni open-loop e gerarchia agentica

Data: 2026-06-06

Report di partenza: `research/operations/2026-06-05-open-loop-automations-map.md`

Skill usate: `reuse-first`, `sota-architecture-loop`

## Verdetto

La gerarchia Nuzantara attuale e' corretta nella direzione. Non va rimpiazzata da LangGraph, AutoGen o OpenAI Agents SDK come runtime centrale dell'organismo. La forma piu' solida e':

`blackboard/events -> L0 regole deterministiche -> L1/L2 giudizio limitato -> L3 Consiglio solo per azioni irreversibili -> human/Zero per autorita' finale ad alto rischio`

I loop aperti del report 2026-06-05 non nascono soprattutto dalla mancanza di un framework agentico. Nascono da ricevute mancanti, `bridge_source` mancanti, canary post-azione mancanti, wrapper morti/stale e quarto verbo ancora incompleto: auto-revisione di regole, soglie, strumenti e target dismessi.

Decisione operativa: riusare/adattare prima i mattoni interni gia' funzionanti; studiare i framework esterni come pattern; non installare un nuovo runtime multi-agent nel core dell'organismo.

## Frame

Obiettivo: chiudere le automazioni secondo il contratto SYMBIOSIS/PulseLoop:

`sense -> judge -> act -> self-review`

Soglia empirica prima di aggiungere altri agenti:

1. Ogni automazione viva deve produrre una ricevuta durevole: heartbeat, state file, riga WAL, mirror JSONL, stream Redis o equivalente.
2. La ricevuta deve essere dichiarata in `organs_registry.yaml` via `bridge_source`, salvo automazioni batch-only o disabled esplicite.
3. Ogni attuatore autonomo deve produrre prova: canary, ledger row, transizione di stato target o ricevuta di escalation.
4. Ogni loop falso/stale ripetuto deve poter supersedere una regola, disarmare un watcher o proporre una correzione del genoma.

## Inventario reuse-first locale

| Mattone | Classificazione | Decisione |
| --- | --- | --- |
| `scripts/lib/heartbeat.sh` | `[FORK-ADAPT]` | Contratto canonico shell: id organo validato, whitelist status, state file atomico, non rompe mai il caller. Da usare come source of truth per i wrapper. |
| `scripts/lib/heartbeat.py` | `[FORK-ADAPT]` | Irrigidito in questo pass per allinearlo al contratto Bash. |
| `scripts/pg-to-organism-bridge.py` | `[FORK-ADAPT]` | Miglior bridge eventi gia' presente: PG LISTEN/NOTIFY, Redis stream, mirror JSONL durevole, heartbeat, reconnect/backoff, handling esplicito di `asyncpg.InterfaceError`. Da riusare come template per automazioni DB-backed. |
| `scripts/sentinel-aggregate.py` | `[FORK-ADAPT]` | Classificatore liveness esistente. Il suo comportamento su `bridge_source` state-file deve guidare la prossima wave di registry closure. |
| `apps/organism/organism/supervisor/dispatch.py` | `[COPY-DIRECT]` | Ha gia' i controlli giusti: allowlist attuatori safe, denylist human-only, blackout, circuit breaker, mutex, ledger. Va esteso attorno, non bypassato. |
| `apps/organism/organism/rules/base.yaml` | `[COPY-DIRECT]` | L0 deterministico corretto per fault operativi ricorrenti. Aggiungere regole solo dopo ricevute e canary. |
| `apps/organism/organism/supervisor/consiglio_gate.py` | `[COPY-DIRECT]` | Da tenere per azioni irreversibili; non usare council per restart o repair ordinario. |
| `research/operations/2026-06-03-organism-fourth-verb-spec.md` | `[STUDY-PATTERN-REWRITE]` | Roadmap giusta per il quarto verbo. Ordine di delivery confermato: C -> A -> D -> B. |

## Ricerca esterna

| Fonte | Cosa trasferire | Decisione reuse-first |
| --- | --- | --- |
| LangChain/LangGraph multi-agent docs: <https://docs.langchain.com/oss/python/langchain/multi-agent/index> | Tassonomia subagents, handoffs, skills, router, custom workflow; distinzione utile tra task paralleli, stateful e semplici. | `[STUDY-PATTERN-REWRITE]` soltanto. Nuzantara ha gia' custom workflow e dispatch gate; importare un framework aumenta il rischio d'integrazione. |
| AutoGen design patterns: <https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/intro.html> e concurrent agents: <https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/concurrent-agents.html> | Pattern topic/subscription e processor concorrenti compatibili con il nostro blackboard PG/Redis. | `[STUDY-PATTERN-REWRITE]`; niente install AutoGen nel core organismo. |
| OpenAI Agents SDK handoffs: <https://openai.github.io/openai-agents-python/handoffs/> | Handoff come delega esplicita a specialisti; utile per futuri contratti L1/L2. | `[STUDY-PATTERN-REWRITE]`; usare il concetto, non il runtime launchd. |
| OpenAI Agents SDK guardrails: <https://openai.github.io/openai-agents-python/guardrails/> | Tool guardrails prima/dopo custom tool call; mappa bene sui controlli pre/post attuatore. | `[STUDY-PATTERN-REWRITE]`; implementare con dispatch/canary locali. |
| OpenAI Agents SDK tracing: <https://openai.github.io/openai-agents-python/tracing/> | Span per agenti, tool, handoff e guardrail; rafforza la necessita' di ricevute end-to-end. | `[STUDY-PATTERN-REWRITE]`; usare prima ledger/JSONL/Redis locali. |
| Anthropic multi-agent research system: <https://www.anthropic.com/engineering/multi-agent-research-system> | Multi-agent forte per ricerca breadth-first con rami indipendenti e budget token adeguato; debole per task ops/coding fortemente accoppiati. | `[STUDY-PATTERN-REWRITE]`; fan-out per audit/ricerca, non per repair autonomo. |
| Cognition "Don't Build Multi-Agents": <https://cognition.ai/blog/dont-build-multi-agents> | Affidabilita' produttiva = contesto condiviso e decisioni implicite non disperse. | `[STUDY-PATTERN-REWRITE]`; supporta una singola spina dorsale decisionale. |
| MAST failure taxonomy: <https://arxiv.org/abs/2503.13657> | Failure class: system design, inter-agent misalignment, task verification. Il gap locale piu' rilevante e' verification. | `[STUDY-PATTERN-REWRITE]`; usarlo come rubrica review per L1/L2/L3 futuri. |

Nessun codice esterno e' stato copiato nel repo. Le fonti esterne sono usate come evidenza architetturale e pattern reference.

## Decisione sulla gerarchia agentica

Tenere la gerarchia, ma renderla piu' stretta:

1. `L0 deterministic`: regole YAML e classificatori statici gestiscono fault noti e ricorrenti. Default per restart, cleanup cache, heartbeat mancante e recovery safe.
2. `L1 local judgment`: solo per ambiguita' dopo che esiste una ricevuta. Deve produrre decisione proposta, confidenza ed evidenza; non mutare stato direttamente.
3. `L2 CLI brain`: proposta di repair, diff, investigazione e candidate rule. Deve scrivere azioni proposte nello stesso ledger/outbox.
4. `L3 Consiglio`: solo per irreversibili o cross-boundary: rollback, credenziali, supersession strutturale di regole, decommission.
5. `Human/Zero`: autorita' finale per mosse produzione/security irreversibili.

Questo e' migliore di uno swarm multi-agent piatto perche' le operations hanno bisogno di una sola spina dorsale decisionale accountable. Il fan-out resta utile in ricerca read-only, triage e review avversaria, dove piu' rami possono lavorare senza mutare stato condiviso.

## Innesto concreto applicato in questo pass

Implementato: hardening di `scripts/lib/heartbeat.py`.

Perche' questo innesto prima:

- Il report ha trovato 91 organi enabled senza `bridge_source`.
- Molti loop si chiudono aggiungendo heartbeat/state file normalizzati prima di aggiungere logica LLM.
- Il writer heartbeat Python era piu' debole del Bash: niente whitelist id e niente whitelist status.

Modifica:

- Validazione stretta dell'id organo: `^[a-zA-Z][a-zA-Z0-9_.]{0,80}$` e niente `..`.
- Whitelist status allineata a `heartbeat.sh`: `ok`, `error`, `warning`, `starting`, `degraded`, `fail`, `success`, `healthy`.
- Status sconosciuti normalizzati a `ok`.
- Test aggiunti in `scripts/tests/test_lib_heartbeat.py` per write, refusal path traversal, normalizzazione status e truncation note.

Verifica:

- `python3 -m py_compile scripts/lib/heartbeat.py scripts/tests/test_lib_heartbeat.py` passato.
- Esecuzione diretta delle quattro nuove test function passata.
- `python3 -m pytest ...` non eseguito: il Python di sistema non ha `pytest`.
- `.venv/bin/pytest ...` non eseguito: la venv locale punta a `/Users/nuzantara/Desktop/nuzantara/.venv/bin/python3.14`, che non esiste su questa macchina.

## Wave autonoma P0a - registry closure

Implementato un primo batch chiuso sui wrapper con codice locale reale e basso rischio:

| Organo | Owner reale | Bridge aggiunto | Stato |
| --- | --- | --- | --- |
| `wr2.supervisor_watchdog` | `scripts/wr2_supervisor_watchdog.py` | `~/.organism/last_seen/wr2.supervisor_watchdog.json` | chiuso |
| `wr2.deploy_puller` | `scripts/wr2-deploy-pull.sh` | `~/.organism/last_seen/wr2.deploy_puller.json` | chiuso |
| `wr2.image_generator` | `scripts/wr2_image_generator.py` | `~/.organism/last_seen/wr2.image_generator.json` | chiuso |
| `pro.codex_autofix_ci` | `scripts/codex/codex-nightly-autofix-ci.sh` | `~/.organism/last_seen/pro.codex_autofix_ci.json` | chiuso |
| `pro.automap_watchdog` | `/Users/balizero/scripts/automap/automap_watchdog.py` | `~/.organism/last_seen/pro.automap_watchdog.json` | chiuso |

Dettaglio innesti:

- `wr2.supervisor_watchdog`: heartbeat Python best-effort su start, tick, reconnect degraded, stop pulito e crash/error.
- `wr2.image_generator`: heartbeat Python best-effort su start, success, rc non zero, interrupt e crash.
- `wr2.deploy_puller`: heartbeat Bash su lock skip, repo mancante, branch errato, dirty tree, fetch failure, ahead/diverged, fast-forward fallito, up-to-date e advance riuscito.
- `pro.codex_autofix_ci`: heartbeat Bash su lock, daily cap, worktree mancante, dirty tree, no failures, no eligible jobs, run id invalido, checkout/reset/codex/commit/push/PR failure e success finale. Il lock cleanup ora e' protetto da flag per non rimuovere lock altrui nel ramo gia' locked.
- `pro.automap_watchdog`: heartbeat Python best-effort su start, `build_view` failure, run_done, interrupt e crash. Il codice operativo e' fuori repo in `/Users/balizero/scripts/automap/automap_watchdog.py`, quindi e' stato classificato come home-runtime invece che tombstone.

Registry:

- Copertura `bridge_source` salita da 25 a 30 organi.
- Enabled senza `bridge_source` scesi da 91 a 86.
- `backend.api`, `backend.surface_router`, `infra.postgres`, `infra.redis`, `infra.qdrant` restano aperti perche' sono superfici/servizi astratti o remoti, non wrapper locali patchabili nello stesso modo.

Regressione aggiunta:

- `scripts/tests/test_closed_loop_bridge_sources.py` verifica che i cinque organi chiusi abbiano `owner_module`, `bridge_source`, owner file esistente e marker heartbeat nel codice operativo; il file home-runtime di `pro.automap_watchdog` e' controllato quando presente sulla macchina locale.

Verifica P0a:

- `bash -n scripts/wr2-deploy-pull.sh scripts/codex/codex-nightly-autofix-ci.sh` passato.
- `python3 -m py_compile scripts/lib/heartbeat.py scripts/wr2_supervisor_watchdog.py scripts/wr2_image_generator.py scripts/tests/test_lib_heartbeat.py scripts/tests/test_closed_loop_bridge_sources.py /Users/balizero/scripts/automap/automap_watchdog.py` passato.
- Smoke `heartbeat.sh` sotto `bash -u` passato.
- Esecuzione diretta delle test function `test_lib_heartbeat.py` e `test_closed_loop_bridge_sources.py` passata.
- Parse YAML registry via Ruby passato: `total=120`, `enabled=116`, `bridge_source=30`, `no_bridge=86`.

## Prossima wave implementativa

P0 - ricevute e registry closure:

1. Patchare i wrapper no-bridge piu' rischiosi per chiamare `scripts/lib/heartbeat.sh` o `scripts/lib/heartbeat.py`.
2. Aggiungere `bridge_source: {type: state_file, path: ~/.organism/last_seen/<organ_id>.json}` in `organs_registry.yaml`.
3. Prossimo batch consigliato: filtrare i restanti 86 no-bridge per owner locali esistenti, escludendo prima servizi astratti/remoti e owner tombstone.

P0 - prova attuatori:

1. Per ogni safe actuator attivo in `dispatch.py`, richiedere proof callback o canary check.
2. Aggiungere ricevute post-azione: `action_id`, `target`, `before`, `after`, `proof_status`, `proof_note`.
3. Se la proof fallisce due volte, circuit-break sul target ed escalation.

P1 - event bridge:

1. Riusare `scripts/pg-to-organism-bridge.py` come template per automazioni DB-backed.
2. Preservare invarianti: JSONL mirror durevole first, Redis best-effort second, heartbeat always, reconnect/backoff, handling esplicito delle eccezioni sibling.

P1 - quarto verbo:

1. Usare `2026-06-03-organism-fourth-verb-spec.md` con delivery order C -> A -> D -> B.
2. Introdurre rule supersession solo dopo ricevute, failure e proof outcome sufficienti a giustificare la modifica.

## Bottom line

Nuzantara non ha bisogno prima di "piu' agenti". Ha bisogno di piu' ricevute chiuse, piu' copertura registry, piu' proof post-azione e un percorso piu' stretto di auto-revisione. Il supervisor gerarchico attuale e' lo scheletro giusto; il valore prossimo viene dal rendere ogni automazione leggibile a quello scheletro.

## Wave autonoma P0b/P0c - closure completa registry

Obiettivo: chiudere tutti gli organi abilitati ancora senza `bridge_source`, usando codice reale gia' presente prima di creare nuovi componenti.

Risultato:

- Enabled con `bridge_source`: 116.
- Enabled senza `bridge_source`: 0.
- Checksum registry aggiornato: `7d68bbfa838797c629a25a02484e4757881ad69f15bbc5c6bc3e557af170012c`.

Innesti principali:

- WR2 modulare: `scripts/wr2-cron-wrapper.sh` ora mappa i moduli CLI reali verso `wr2.connector`, `wr2.dossier_compiler`, `wr2.learner_nightly`, `wr2.measurer`, `wr2.sla_worker`, `wr2.strategos`, `wr2.trend_hunter`; `scripts/wr2-hardening-chain.sh` copre `wr2.hardening`.
- WR2 diretto: `scripts/wr2_draft_generator.py`, `scripts/wr2_topic_selector.py`, `scripts/wr2_fact_checker.py`, `scripts/wr2_fact_extractor.py` emettono heartbeat su start/ok/error.
- Mata Garuda: `run_sentinel.sh`, `matagaruda-bridge.sh` home-runtime e `mata_garuda_invalidation_sweep_wrapper.sh` sono registrati con owner reali e heartbeat.
- Infra/daemon esterni: Postgres, Redis e Qdrant passano da `/health/detailed`; `wr2.pg_proxy`, `mata_garuda.bridge_adaptive.pro` e `pro.prime_tunnel` sono osservati dal LaunchAgent state bridge.
- Pro/Codex: overnight runner, coverage improver, overnight feeder, research actor, spalla calibrate, sentinel meta-watchdog, federation alert dispatcher e secrets sync Mini hanno bridge standard.

Decisione architetturale:

- Non serve introdurre una nuova gerarchia agentica sopra l'attuale supervisor per questo problema. Il collo di bottiglia era osservabilita' e proof-of-run, non mancanza di agenti.
- La gerarchia ottimale resta: registry come contratto, heartbeat/HTTP bridge come proof layer, supervisor come recovery/decision layer, eventuale consiglio solo per attuatori irreversibili o cambi strutturali.
- Per daemon esterni senza codice applicativo proprio, il pattern corretto e' LaunchAgent bridge con owner esplicito nel registry, non wrapper fittizi.

Verifica:

- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_closed_loop_bridge_sources.py -q` passato.
- Conteggio YAML via Ruby passato: `{:bridge_source=>116}` per tutti gli organi abilitati.
- `python3 -m py_compile` passato sui Python toccati.
- `bash -n` passato sui wrapper bash toccati.
- `zsh -n` passato su `run_sentinel.sh` e `matagaruda-bridge.sh`.

## Wave autonoma P0d - audit consumer bridge

Obiettivo: verificare che i `bridge_source` non siano solo dichiarati nel genoma, ma letti davvero dai consumer operativi.

Gap trovati e corretti:

- `GenomeAggregatorSensor` costruiva `BridgeSource` senza propagare `json_path`, quindi gli HTTP bridge nested rischiavano di diventare status top-level errati.
- `GenomeAggregatorSensor` usava il timestamp del bridge ma ignorava lo status: un endpoint fresco con `down/fail` poteva risultare vivo.
- `BridgeStateReader` richiedeva `ts` anche per endpoint HTTP semplici come NLM/Automap che espongono solo status/ok.
- `scripts/sentinel-aggregate.py` trattava i `fly_machine` come `remote` prima di considerare l'HTTP bridge.

Innesti applicati:

- `BridgeStateReader`: HTTP senza timestamp usa il momento di lettura; mapping status esteso a `true/false`, `unavailable`, `unhealthy`, `operational`, ecc.
- `GenomeAggregatorSensor`: passa `json_path` e `http_timeout_s`; status bridge `fail/down/unavailable` forza `dead`, status `degraded/warning` forza `stale` se il timestamp sarebbe vivo.
- `scripts/sentinel-aggregate.py`: legge `bridge_source.type=http` con `json_path`, fallback timestamp di lettura, normalizzazione status, e classifica `fly_machine` dal bridge invece che sempre `remote`.
- `scripts/tests/test_closed_loop_bridge_sources.py`: aggiunto guardrail globale che in P0d copriva 116/116 enabled con `bridge_source` e soli tipi consumer-supported (`state_file`, `http`).

Verifica P0d:

- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_closed_loop_bridge_sources.py scripts/tests/test_sentinel_aggregate.py -q` passato: `12 passed`.
- `PYTHONPATH=apps/cell apps/backend-rag/.venv/bin/python -m pytest apps/cell/tests/test_bridge_state_reader.py apps/cell/tests/test_genome_aggregator_sensor.py -q` passato: `43 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/sentinel-aggregate.py apps/cell/cell/sensors/bridge_state_reader.py apps/cell/cell/sensors/genome_aggregator_sensor.py` passato.
- Conteggio registry P0d passato: `enabled=116 bridge_source=116 no_bridge=0`.

## Wave autonoma P0e/P1 - Law 1, W64 e residuo plist secret

Obiettivo: chiudere i P0/P1 localmente correggibili rimasti dal report del 2026-06-05 senza introdurre nuova architettura.

Triage:

- `scripts/wr2_canva_lease_watchdog.py` era gia' stato patchato: l'exception set include `asyncpg.InterfaceError`.
- Il lint `scripts/lint_asyncpg_except_completeness.py` era verde, ma il workflow dichiarato nel docstring non esisteva: il gate non era reale.
- `apps/evaluator/seo_auto_fixer.py` usava ancora `ANTHROPIC_API_KEY` e POST diretto a `https://api.anthropic.com/v1/messages`.
- I label `com.nuzantara.skills-bridge-consumer` e `com.balizero.wa-dashboard-m1` non risultano caricati in `~/Library/LaunchAgents` su questa macchina; il residuo operativo diretto non era riproducibile live.
- Il template repo `apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist` continuava pero' a indicare un possibile segreto inline nel plist e `chmod 0444`.

Innesti applicati:

- `seo_auto_fixer.py`: rimosso il percorso Anthropic diretto; `generate_meta_description()` ora usa generazione locale deterministica con normalizzazione whitespace e troncamento a parola entro 155 caratteri.
- `scripts/tests/test_seo_auto_fixer_cli_only.py`: guardrail sorgente contro `ANTHROPIC_API_KEY`, `api.anthropic.com`, `anthropic-version` e modelli Haiku diretti.
- `.github/workflows/asyncpg-lint.yml`: gate CI su PR/push per `scripts/lint_asyncpg_except_completeness.py`.
- `apps/cell/scripts/skills_bridge_consumer_launcher.sh`: launcher operativo che carica `~/.nuzantara-secrets.env` e poi esegue `skills_bridge_consumer.py`; fallisce esplicitamente se `BRIDGE_SKILLS_API_KEY` non e' presente.
- `apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist`: ProgramArguments passa dal Python diretto al launcher; il plist non deve contenere `BRIDGE_SKILLS_API_KEY`.
- `apps/cell/launchagent/README.md`: installazione aggiornata a launcher + `chmod 0400` per questo plist.
- `apps/cell/tests/scripts/test_skills_bridge_consumer.py`: test che il plist usi il launcher e non contenga la chiave inline in `EnvironmentVariables`.

Verifica P0e/P1:

- `apps/backend-rag/.venv/bin/python scripts/lint_asyncpg_except_completeness.py` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_lint_asyncpg_except_completeness.py scripts/tests/test_seo_auto_fixer_cli_only.py -q` passato: `13 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile apps/evaluator/seo_auto_fixer.py scripts/tests/test_seo_auto_fixer_cli_only.py` passato.
- `bash -n apps/cell/scripts/skills_bridge_consumer_launcher.sh` passato.
- `plutil -lint apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist` passato.
- `PYTHONPATH=apps/cell apps/backend-rag/.venv/bin/python -m pytest apps/cell/tests/scripts/test_skills_bridge_consumer.py -q` passato: `12 passed`.

Stato residuo:

- Non ho ruotato credenziali live: non c'e' un LaunchAgent corrente da aggiornare in questa sessione e la rotazione Fly/Pro richiede controllo operativo esterno. Il codice e il template non reintroducono piu' il pattern segreto-inline.
- A fine P0e restavano fuori `APERTO-1` live-vs-genoma e `APERTO-3/4` quarto verbo: il primo viene affrontato nella wave P0f sotto, il secondo resta un lavoro strutturale di supersession/proof post-azione.

## Wave autonoma P0f - APERTO-1 live runtime vs genome

Obiettivo: trasformare `APERTO-1` da stima documentale a diff operativo ripetibile.

Innesto applicato:

- `scripts/audit/live_runtime_vs_genome.py`: audit read-only che confronta `apps/organism/organism/organs_registry.yaml` con snapshot `launchctl list`, plist LaunchAgents e `crontab -l`.
- Il tool supporta snapshot remoti acquisiti via SSH (`--launchctl-file`, `--crontab-file`, `--plist-label-file`) e probe locale, non chiama mai `launchctl bootstrap/bootout/kickstart`.
- Classificazione automatica dei label fuori genoma:
  - `unmanaged_launchctl_running`: PID presente, import/quarantine prioritaria.
  - `unmanaged_launchctl_failed`: status non-zero senza PID, repair o tombstone.
  - `unmanaged_launchctl_scheduled_ok`: status 0 senza PID, batch da dichiarare o importare.
  - `unmanaged_plist_only`: plist presente ma non caricato.
  - `unmanaged_cron`: entry cron attive non coperte da owner module o label registry.
- `scripts/tests/test_live_runtime_vs_genome.py`: parser e classificazione coperti con test.

Snapshot Pro 2026-06-06:

| Metrica | Conteggio |
| --- | ---: |
| Registry launchd labels | 111 |
| Pro `launchctl` labels osservati | 190 |
| Pro plist osservati | 197 |
| Pro cron entry osservate | 88 |
| Launchctl fuori genoma | 90 |
| Fuori genoma running | 25 |
| Fuori genoma failed/non-zero | 12 |
| Fuori genoma scheduled-ok | 53 |
| Plist fuori genoma | 94 |
| Plist-only fuori genoma | 4 |
| Cron fuori genoma | 87 |
| Registry label non caricati nello snapshot Pro | 9 |

Classificazione operativa:

- Import/quarantine prioritaria: i 25 running fuori genoma. Esempi dal sample: `cron-log-sentinel`, `guardrails-daemon`, `intel-dedup-gateway`, `observatory`, `observatory-server`, `wa-dashboard-m1`, `wa-meta-inbox`, WA mirror, `wr3.supervisor`, `qdrant.daemon`.
- Repair/tombstone: i 12 non-zero fuori genoma. Esempi: `audit-launchd.daily`, `intel-lake.e2e-probe.6h`, `meta-dispatcher`, `nuzantara-drive-sync`, `wa-intelligence-incremental`, `wr2.e2e-probe.daily`, `wr2.plist-watchdog`, `consumer-lag.check`, `redis-split-brain.check`, `agent-worktree-cleanup.daily`.
- Batch dichiarabili: i 53 scheduled-ok fuori genoma, incluse famiglie agent-library, cicatrix, competitor, Intel Lake, WR2 metrics/GC/bench, openclaw/WA batch.
- Cron backlog: 87 entry Pro fuori registry. Sono il blocco maggiore: NLM pipeline, Fly backup/cost, OpenClaw cron, cron-agent Python, RAG/cell jobs, memoria Claude, quota/check e canary devono diventare `genome+bridge`, `genome+batch_declared` o `decommissioned`.
- Mismatch da risolvere: `com.matagaruda.sentinel.daily` e altri quattro label Mini sono attesi dal registry ma non verificati su Mini; Mini ha risposto con timeout SSH su `100.93.236.6:22`.

Decisione:

- Non importare in massa i 90/94/87 fuori genoma nel registry in questa wave: aggiungerli senza owner, heartbeat e decisione batch/decommission riaprirebbe `APERTO-2` e abbasserebbe la qualita' del genoma.
- Usare il tool come gate prima di ogni claim "tutti i loop sono chiusi": con `--fail-on-drift`, il comando fallisce finche' esistono runtime vivi fuori genoma.
- La gerarchia agentica resta confermata: il problema e' coverage/proof, non numero di agenti. Il prossimo innesto corretto e' una pipeline di import/decommission guidata dal diff, non un nuovo orchestratore.

Verifica P0f:

- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_live_runtime_vs_genome.py -q` passato: `5 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/audit/live_runtime_vs_genome.py scripts/tests/test_live_runtime_vs_genome.py` passato.
- Probe Air-M5 passato: solo `com.balizero.caffeinate` fuori genoma, coerente con ruolo thin client.
- Probe Pro read-only passato via SSH e snapshot file locali temporanei.

## Wave autonoma P0g - falsi-chiusi disabled e LaunchAgent bridge standard

Obiettivo: non permettere che un organo disabilitato nel registry venga contato come loop chiuso mentre gira ancora, e portare il bridge LaunchAgent legacy al formato letto da Cell.

Innesti applicati:

- `scripts/audit/live_runtime_vs_genome.py`: separa `disabled_registry_launchctl`, `disabled_registry_plists` e `disabled_registry_cron`; `--fail-on-drift` fallisce anche se il drift e' un organo disabled ancora live.
- `scripts/wr2_canva_desktop_apply.py`: emette heartbeat standard `wr2.canva_apply` per start, no-drafts, kill-switch, success, error e timeout.
- `apps/organism/organism/organs_registry.yaml`: `wr2.canva_apply` torna enabled con owner reale `scripts/wr2_canva_desktop_apply.py` e bridge `~/.organism/last_seen/wr2.canva_apply.json`.
- `scripts/ollama-warm-pin.sh`: portato nel repo dalla versione Pro e dotato di heartbeat standard `pro.ollama_warm_pin`.
- `apps/organism/organism/organs_registry.yaml`: `pro.ollama_warm_pin` torna enabled come cron coperto da owner module, senza label LaunchAgent dismesso; `expected_hb_seconds=691200` per coprire il ciclo weekly.
- `scripts/launchagent-state-bridge.py`: portato dal bridge legacy Pro, adattato a `~/.organism/last_seen`, con compatibilita' legacy `~/.agent/decisions/state` per `prime_tunnel`/`wr2_pg_proxy`.
- `scripts/tests/test_launchagent_state_bridge.py`: parser, status daemon e scrittura standard+legacy coperti.
- `scripts/tests/test_closed_loop_bridge_sources.py`: ora verifica `wr2.canva_apply`, `pro.ollama_warm_pin`, `pro.launchagent_state_bridge`, `pro.prime_tunnel` e `wr2.pg_proxy` contro file repo, non solo home-runtime opzionale.

Verifica live Pro:

- Installato con backup `/Users/nuzantara/scripts/launchagent-state-bridge.py.bak-*`.
- Esecuzione read-only: `python3 /Users/nuzantara/scripts/launchagent-state-bridge.py --json`.
- Receipt verificati in `~/.organism/last_seen`: `pro.launchagent_state_bridge=ok`, `pro.prime_tunnel=ok`, `wr2.pg_proxy=ok`.

Snapshot Pro post-P0g:

| Metrica | Conteggio |
| --- | ---: |
| Registry launchd labels | 110 |
| Pro `launchctl` labels osservati | 190 |
| Pro plist osservati | 197 |
| Pro cron entry osservate | 88 |
| Launchctl fuori genoma | 90 |
| Fuori genoma running | 23 |
| Fuori genoma failed/non-zero | 12 |
| Fuori genoma scheduled-ok | 55 |
| Plist fuori genoma | 94 |
| Plist-only fuori genoma | 4 |
| Cron fuori genoma | 87 |
| Disabled registry ancora live | 0 |
| Registry label non caricati nello snapshot Pro | 9 |

Verifica P0g:

- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_live_runtime_vs_genome.py scripts/tests/test_closed_loop_bridge_sources.py -q` passato: `12 passed`.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_launchagent_state_bridge.py scripts/tests/test_closed_loop_bridge_sources.py -q` passato: `8 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/wr2_canva_desktop_apply.py scripts/audit/live_runtime_vs_genome.py scripts/launchagent-state-bridge.py` passato.
- `bash -n scripts/ollama-warm-pin.sh` passato.

## Wave autonoma P0h - LaunchAgent running importati via bridge standard

Obiettivo: chiudere il sottoinsieme piu' rischioso di `APERTO-1`, cioe' i LaunchAgent Pro fuori genoma ma realmente attivi nello snapshot live.

Decisione reuse-first / SOTA loop:

- Riutilizzare `scripts/launchagent-state-bridge.py` come adapter unico invece di creare un nuovo demone.
- Non cambiare la gerarchia agentica: il difetto osservato era coverage/proof del genoma, non assenza di un orchestratore.
- Importare solo i label running con owner leggibile e receipt standard; lasciare failed/scheduled/cron-only nel backlog decisionale `repair`, `batch_declared` o `decommissioned`.

Innesti applicati:

- `scripts/launchagent-state-bridge.py`: aggiunti 21 mapping Pro running e guardrail contro falsi-ok quando un label atteso non e' caricato.
- `apps/organism/organism/organs_registry.yaml`: aggiunti 21 organi con runtime `pro_launchd` e `bridge_source` standard `~/.organism/last_seen/<organ_id>.json`.
- `scripts/tests/test_launchagent_state_bridge.py`: coperto il caso label mancante come failure, piu' coverage dei mapping P0h.
- `scripts/tests/test_closed_loop_bridge_sources.py`: aggiunto controllo registry+bridge per tutti i 21 organi importati.

Organismi importati in P0h:

- `pro.cron_log_sentinel`, `pro.guardrails_daemon`, `pro.nb_curator_daily`, `pro.observatory_server`, `pro.profile_monitor_wrapper`
- `infra.qdrant_pro`, `infra.local_postgres_pro`, `infra.syncthing_pro`
- `pro.wa_dashboard_m1`, `pro.wa_meta_inbox`, `pro.wa_mirror_auto_promote`, `pro.wa_mirror_launcher`, `pro.wa_viewer`
- `wr2.carousel_dispatcher`, `wr2.telegram_gate`, `wr3.supervisor`
- `mata_garuda.classifier_adaptive.pro`, `mata_garuda.ner_adaptive.pro`
- `codex.spark_loop`, `pro.openclaw_whatsapp_bridge`, `pro.openclaw_whatsapp_tunnel`

Verifica live Pro:

- Script copiato su Pro in `/Users/nuzantara/scripts/launchagent-state-bridge.py` con backup `.bak-p0h-*`.
- Esecuzione read-only: `python3 /Users/nuzantara/scripts/launchagent-state-bridge.py --json`.
- Receipt runtime: 24 `ok` / 0 failed.
- Receipt file verificati in `~/.organism/last_seen` per tutti i 21 nuovi organi: status `ok`, source `launchagent-state-bridge`, label corretto.

Snapshot Pro post-P0h:

| Metrica | Conteggio |
| --- | ---: |
| Organi registry totali | 141 |
| Organi enabled | 139 |
| Enabled con `bridge_source` | 139 |
| Enabled senza `bridge_source` | 0 |
| Registry launchd labels | 131 |
| Pro `launchctl` labels osservati | 190 |
| Pro plist osservati | 197 |
| Pro cron entry osservate | 88 |
| Launchctl fuori genoma | 69 |
| Fuori genoma running | 0 |
| Fuori genoma failed/non-zero | 15 |
| Fuori genoma scheduled-ok | 54 |
| Plist fuori genoma | 73 |
| Plist-only fuori genoma | 4 |
| Cron fuori genoma | 71 |
| Disabled registry ancora live | 0 |
| Registry label non caricati nello snapshot Pro | 9 |

Delta P0h:

| Metrica | Prima | Dopo |
| --- | ---: | ---: |
| Launchctl fuori genoma | 90 | 69 |
| Fuori genoma running | 21 | 0 |
| Plist fuori genoma | 94 | 73 |
| Cron fuori genoma | 87 | 71 |

Verifica P0h:

- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_live_runtime_vs_genome.py scripts/tests/test_launchagent_state_bridge.py scripts/tests/test_closed_loop_bridge_sources.py scripts/tests/test_sentinel_aggregate.py scripts/tests/test_lint_asyncpg_except_completeness.py scripts/tests/test_seo_auto_fixer_cli_only.py -q` passato: `38 passed`.
- `PYTHONPATH=apps/cell apps/backend-rag/.venv/bin/python -m pytest apps/cell/tests/test_bridge_state_reader.py apps/cell/tests/test_genome_aggregator_sensor.py apps/cell/tests/scripts/test_skills_bridge_consumer.py -q` passato: `55 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/audit/live_runtime_vs_genome.py scripts/launchagent-state-bridge.py scripts/wr2_canva_desktop_apply.py scripts/tests/test_live_runtime_vs_genome.py scripts/tests/test_launchagent_state_bridge.py scripts/tests/test_closed_loop_bridge_sources.py` passato.
- `git diff --check` passato.

## Wave autonoma P0i - plist-only morti e PG bridge watchdog

Obiettivo: chiudere il sottoinsieme piu' certo del backlog `APERTO-1` non-running: plist-only con target inesistente e un watchdog PG gia' presente ma non iscritto nel genoma.

Decisione reuse-first / SOTA loop:

- Non importare in massa i 54 scheduled-ok e i 15 failed: senza receipt reale diventerebbero falsi loop chiusi.
- Tombstonare solo plist non caricati con target script inesistente.
- Riparare/importare `com.nuzantara.pg-organism-bridge-watchdog` perche' il plist e lo script repo esistono, il target monitorato (`pro.pg_organism_bridge`) ha heartbeat live `ok`, e il watchdog puo' emettere ricevuta propria.
- Lasciare `com.balizero.wa-mirror` nel backlog: il target JS esiste e i log mostrano attivita'/QR, quindi non e' tombstone sicuro.

Innesti applicati:

- `infra/scripts/pg-organism-bridge-watchdog.sh`: aggiunto heartbeat standard `infra.pg_organism_bridge_watchdog`, state file locale, guardia contro `TELEGRAM_BOT_TOKEN` unset sotto `set -u`, e status `starting/ok/warning/error` su processo mancante, stream vuoto, stream stale o lag OK.
- `apps/organism/organism/organs_registry.yaml`: aggiunto organo `infra.pg_organism_bridge_watchdog` con dipendenze `pro.pg_organism_bridge` e `infra.redis`, recovery `launchctl_kickstart`, bridge `~/.organism/last_seen/infra.pg_organism_bridge_watchdog.json`.
- `scripts/tests/test_closed_loop_bridge_sources.py`: aggiunto guardrail owner+bridge+marker heartbeat per il watchdog PG.
- Pro live: copiati `infra/scripts/pg-organism-bridge-watchdog.sh` e `scripts/lib/heartbeat.sh`; spostati in quarantena i due plist non caricati e con target assente:
  - `/Users/nuzantara/Library/LaunchAgents/.disabled-2026-06-06-open-loop-p0i/com.balizero.wr2.canva-renderer.plist`
  - `/Users/nuzantara/Library/LaunchAgents/.disabled-2026-06-06-open-loop-p0i/com.nuzantara.workspace-event-bridge-sheets-import.plist`
- Pro live: bootstrap/kickstart del label `com.nuzantara.pg-organism-bridge-watchdog`.

Verifica live Pro:

- `com.nuzantara.pg-organism-bridge-watchdog`: `last exit code = 0`.
- Receipt: `~/.organism/last_seen/infra.pg_organism_bridge_watchdog.json` -> `{"status":"ok","note":"pid=1195 lag=0min"}` nello snapshot 2026-06-05T21:01:09Z.
- State file locale: `~/.agent/decisions/state/pg_organism_bridge_watchdog.state` -> `status=ok`, `note=pid=1195 lag=0min`.
- Snapshot plist corretto come `Label<TAB>path` per evitare falsi positivi filename-vs-Label (`.daily`, `.hourly`, `.10min`).

Snapshot Pro post-P0i:

| Metrica | Conteggio |
| --- | ---: |
| Organi registry totali | 142 |
| Organi enabled | 140 |
| Enabled con `bridge_source` | 140 |
| Enabled senza `bridge_source` | 0 |
| Registry launchd labels | 132 |
| Pro `launchctl` labels osservati | 191 |
| Pro plist osservati | 195 |
| Pro cron entry osservate | 88 |
| Launchctl fuori genoma | 69 |
| Fuori genoma running | 0 |
| Fuori genoma failed/non-zero | 16 |
| Fuori genoma scheduled-ok | 53 |
| Plist fuori genoma | 70 |
| Plist-only fuori genoma | 1 |
| Cron fuori genoma | 71 |
| Disabled registry ancora live | 0 |
| Registry label non caricati nello snapshot Pro | 9 |

Delta P0i:

| Metrica | Prima | Dopo |
| --- | ---: | ---: |
| Plist osservati | 197 | 195 |
| Registry launchd labels | 131 | 132 |
| Plist fuori genoma | 73 | 70 |
| Plist-only fuori genoma | 4 | 1 |

Verifica P0i:

- `bash -n infra/scripts/pg-organism-bridge-watchdog.sh` passato.
- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_closed_loop_bridge_sources.py -q` passato: `6 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/tests/test_closed_loop_bridge_sources.py scripts/audit/live_runtime_vs_genome.py` passato.

## Stato dopo P0i

- Chiuso: `APERTO-2` per i 140 organi enabled nel registry; consumer bridge aggiornati; Law 1 localmente chiusa; W64 gated; template skills bridge senza segreto inline; falsi-chiusi disabled eliminati; `launchagent-state-bridge` standardizzato e installato live su Pro; `APERTO-1 running unmanaged Pro` ridotto a 0 nello snapshot verificato; plist-only morti ridotti a 1 residuo non tombstonabile senza decisione WA.
- Non ancora chiuso: APERTO-1 come backlog operativo Pro non-running (69 launchctl, 70 plist, 71 cron fuori genoma: 16 failed/non-zero, 53 scheduled-ok, 1 plist-only), APERTO-3/4 quarto verbo pieno, rotazione esterna credenziali storiche se richiesta, Mini SSH ancora in timeout.
- Limite tecnico sul quarto verbo in questa sessione: gli attuatori basati su `ActuatorBase` gia' emettono evento `*_done`/`*_failed` e aggiornano `incident_ledger`; cio' che manca e' proof normalizzata per ogni runtime fuori genoma e per cron-only. Questo va risolto dopo import/decommission, altrimenti si aggiunge proof a job che potrebbero essere tombstone.

## Wave autonoma P0p - cron Pro fuori genoma

Obiettivo: chiudere il backlog cron-only Pro senza trasformare batch opachi in falsi organismi.

Decisione reuse-first:

- Riusare i wrapper shell esistenti e il contratto state-file gia' usato da `~/.agent/decisions/state/*.last.json`.
- Non introdurre un orchestratore nuovo: cron resta cron, ma ogni entry viene registrata nel genoma con `cron_match`, owner e recovery `human_only`.
- Separare due casi:
  - `scripts/cron-runner.sh` per script cron reali: esegue lo script originale e scrive receipt deterministica.
  - `scripts/cron-state.sh` per comandi nudi o compositi: wrapper minimale con state file, senza fingere retry o self-healing.

Innesti applicati:

- `scripts/audit/live_runtime_vs_genome.py`: copertura cron tramite `cron_match` esplicito oltre a owner module e label.
- `scripts/cron-runner.sh`: wrapper stateful per script cron; job key derivato da basename+argomenti.
- `scripts/cron-state.sh`: wrapper stateful per cron command arbitrari.
- `apps/organism/organism/organs_registry.yaml`: aggiunti 70 organi cron Pro:
  - 25 `pro.cron_runner.*`
  - 8 `pro.cron_wrapper.*`
  - 9 `pro.cron_agent.*`
  - 28 `pro.cron_state.*`
- `scripts/tests/test_cron_state_wrappers.py` e test audit aggiornati.

Deploy live Pro:

- Copiati `scripts/cron-runner.sh` e `scripts/cron-state.sh` in `/Users/nuzantara/scripts/`, `~/Desktop/nuzantara/scripts/`, `~/Desktop/nuzantara-deploy/scripts/`.
- Installato crontab candidato solo dopo confronto byte-for-byte con snapshot live pre-P0p.
- Backup crontab Pro: `/Users/nuzantara/.codex/runtime-audit/crontab-backup-before-p0p-20260605T214044Z.txt`.

Snapshot Pro post-P0p:

| Metrica | Conteggio |
| --- | ---: |
| Cron entry Pro osservate | 88 |
| Launchctl fuori genoma | 0 |
| Plist fuori genoma | 0 |
| Cron fuori genoma | 0 |
| Disabled registry ancora live | 0 |
| Registry label non caricati | 9 |

I 9 `missing_loaded_labels` erano 4 falsi positivi Mini in una snapshot Pro e 5 label Pro reali trattati in P0q.

Verifica P0p:

- `bash -n scripts/cron-runner.sh scripts/cron-state.sh` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_cron_state_wrappers.py scripts/tests/test_live_runtime_vs_genome.py -q` passato nel ciclo P0p.
- Smoke remoto Pro con temp state dir passato per entrambi i wrapper.

## Wave autonoma P0q - missing labels Pro e runtime scope

Obiettivo: portare il gate Pro a zero senza contare label Mini come mancanti e senza ricaricare automazioni ritirate.

Decisione SOTA loop:

- Aggiungere filtro runtime all'audit, non cambiare il parsing live: una snapshot Pro va confrontata contro organi `runtime=pro_launchd`.
- Ritirare `cell-observatory*` perche' il runbook 2026-06-03 li documenta come deprecated e sostituiti da `com.balizero.observatory` + `observatory-server`.
- Riparare i due label Pro reali mancanti:
  - `com.nuzantara.federation-alert-dispatcher`
  - `com.nuzantara.claude-max-usage-watcher`

Innesti applicati:

- `scripts/audit/live_runtime_vs_genome.py`: nuovo `--runtime`, ripetibile, che filtra il registry in `load_registry()`.
- `scripts/tests/test_live_runtime_vs_genome.py`: test contro falsi positivi `mini_launchd`.
- `infra/launchagents/com.nuzantara.federation-alert-dispatcher.plist`: usa `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python`, perche' la venv importa `orjson` e il modulo daemon.
- `apps/backend-rag/backend/scripts/federation_alert_daemon.py`: sincronizzato su Pro; ora scrive `~/.organism/last_seen/pro.federation_alert_dispatcher.json`.
- `scripts/claude-max-usage-watcher.sh`: wrapper repo nuovo; usa la venv backend con Playwright prima dei fallback pyenv/system.
- `apps/organism/organism/organs_registry.yaml`: `cell.observatory`, `cell.observatory_prune`, `cell.observatory_selfcheck` marcati `enabled: false`, `recovery_action: human_only`, con cicatrix di retirement.

Deploy live Pro:

- Quarantena non distruttiva: `/Users/nuzantara/Library/LaunchAgents/quarantine-open-loop-p0q-20260605T214647Z/`.
- Spostati in quarantena:
  - `com.nuzantara.cell-observatory.plist`
  - `com.nuzantara.cell-observatory-prune.plist`
  - `com.nuzantara.cell-observatory-selfcheck.plist`
  - `com.claude-max-api.plist`
- Bootstrap/kickstart:
  - `com.nuzantara.federation-alert-dispatcher`
  - `com.nuzantara.claude-max-usage-watcher`

Evidenza live:

- Federation dispatcher: log `LISTEN federation_alert active`; heartbeat fresco `~/.organism/last_seen/pro.federation_alert_dispatcher.json` con status `ok` e note `federation alert dispatcher running`.
- Claude watcher: import Playwright risolto; run completato e `~/.claude/usage-watcher/last_run.json` aggiornato a `status=degraded`, `accounts_ok=0`, `accounts_total=3`. Il loop e' chiuso come liveness/receipt; il parsing account resta degradato.

Snapshot Pro post-P0q (`--runtime pro_launchd`):

| Metrica | Conteggio |
| --- | ---: |
| Registry labels Pro | 192 |
| Launchctl labels Pro osservati | 188 |
| Plist labels Pro osservati | 188 |
| Cron entry Pro osservate | 88 |
| Launchctl fuori genoma | 0 |
| Plist fuori genoma | 0 |
| Cron fuori genoma | 0 |
| Disabled registry ancora live | 0 |
| Registry label Pro non caricati | 0 |

Snapshot non filtrato sulla stessa macchina:

- `missing_loaded_labels=4`, tutti `runtime=mini_launchd`.
- Label Mini non verificati live: `com.matagaruda.intel-bridge.daily`, `com.matagaruda.ner-worker.hourly`, `com.matagaruda.normalizer.hourly`, `com.matagaruda.sentinel.daily`.
- Mini resta non raggiungibile: `tailscale ping --timeout=10s 100.93.236.6`, `nc -vz -G 8 100.93.236.6 22` e `ssh -o ConnectTimeout=8 -o BatchMode=yes mini true` vanno in timeout; anche da `pro`, TCP/22 e SSH verso Mini vanno in timeout. Quindi non dichiaro chiusa la verifica live Mini.

Registry corrente post-P0q:

| Metrica | Conteggio |
| --- | ---: |
| Organi totali | 277 |
| Organi enabled | 272 |
| Organi disabled intenzionali | 5 |
| Enabled con `bridge_source` | 272 |
| Enabled senza `bridge_source` | 0 |
| Runtime `pro_launchd` enabled | 259 |
| Runtime `fly_machine` enabled | 8 |
| Runtime `mini_launchd` enabled | 5 |

Checksum registry: `99c395caa3a3e056653d8f3c03e5fe5bcb857f05aeeb430b7dfcb427a59e154a`.

Verifica P0q:

- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml` passato.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/audit/live_runtime_vs_genome.py apps/backend-rag/backend/scripts/federation_alert_daemon.py` passato.
- `bash -n scripts/claude-max-usage-watcher.sh scripts/cron-runner.sh scripts/cron-state.sh` passato.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_live_runtime_vs_genome.py scripts/tests/test_cron_state_wrappers.py scripts/tests/test_closed_loop_bridge_sources.py scripts/tests/test_launchagent_state_bridge.py -q`: `25 passed`.
- `git diff --check` passato.

## Stato dopo P0q

- Chiuso su Pro: `APERTO-1` runtime drift per launchctl, plist e cron; nessun unmanaged Pro e nessun missing loaded Pro nello snapshot finale.
- Chiuso nel genoma: 272/272 organi enabled hanno `bridge_source`; i retired sono disabled espliciti.
- Ancora non dichiarato chiuso: verifica live Mini, per timeout di Tailscale ping, TCP/22 e SSH anche passando da `pro`. Il filtro runtime impedisce che Mini falsi l'audit Pro, ma serve una snapshot Mini separata quando torna raggiungibile.
- Ancora strutturale: quarto verbo pieno (`supersede`, auto-dismissione watcher, proof post-azione) resta il prossimo livello dopo la chiusura runtime.

## Wave autonoma P0r - proof post-azione nel dispatcher

Obiettivo: chiudere un sotto-gap del quarto verbo nel punto piu' vicino agli attuatori reali: il ledger deve poter provare `dispatched -> done/failed`, non solo che il dispatcher ha invocato qualcosa.

Gap trovato:

- `incident_ledger` e la migration 195 promettono una riga per dispatch e un update terminale dall'attuatore.
- `ActuatorBase.run()` gia' chiama `incident_ledger.record_outcome(done|failed)`.
- Ma `Dispatcher.dispatch()` scriveva `record_dispatch()` dopo `await actuator.run(...)`; quindi l'update terminale poteva arrivare prima dell'insert e non trovare la riga da chiudere. Il risultato pratico era una proof post-azione fragile, soprattutto per il quarto verbo e le query sugli incidenti aperti.

Innesto applicato:

- `apps/organism/organism/supervisor/dispatch.py`: `record_dispatch()` viene scritto prima del side effect dell'attuatore, subito dopo il controllo registry e prima di `instance.run(...)`.
- La callback Telegram resta dopo l'esecuzione e non puo' rompere la catena di proof.
- Nessun nuovo schema: si riusa `incident_ledger` esistente.

Test aggiunti:

- `apps/organism/tests/test_incident_ledger.py`: nuovo test `test_dispatcher_records_dispatch_before_actuator_outcome()` con attuatore reale derivato da `ActuatorBase`; verifica ordine SQL `INSERT INTO incident_ledger` prima di `UPDATE incident_ledger ... outcome=done`.

Verifica P0r:

- `UV_PROJECT_ENVIRONMENT=/tmp/nuzantara-organism-test-venv uv run --project apps/organism --extra dev pytest apps/organism/tests/test_incident_ledger.py apps/organism/tests/supervisor/test_dispatch.py apps/organism/tests/actuators/test_base.py -q`: `26 passed`.
- `PYTHONPATH=apps/organism apps/backend-rag/.venv/bin/python -m py_compile apps/organism/organism/supervisor/dispatch.py apps/organism/tests/test_incident_ledger.py` passato.
- `git diff --check` passato.
- Suite ampia organism (`supervisor + actuators + incident_ledger`) ha dato `184 passed, 1 failed`: il fail e' `apps/organism/tests/supervisor/test_claude_brain.py::test_timeout_returns_defer`, dove il test patcha globalmente `asyncio.wait_for` e manda in timeout anche la connessione Redis fake con questa combinazione `redis/fakeredis`. Non e' causato dal patch P0r, ma va corretto in una wave separata se si vuole una suite organism ampia verde su `uv`.

Stato dopo P0r:

- Chiuso un pezzo del quarto verbo: proof post-azione per gli attuatori `ActuatorBase` ora ha la sequenza durevole corretta.
- Ancora non chiuso: Mini live verification; quarto verbo completo C/A/D/B della spec (`robust_parse`, `red_summary`, `suppression_digest`, `supersede`) e auto-dismissione watcher.

## Wave autonoma P0s - quarto verbo C/A e suite organism

Obiettivo: continuare l'ordine di delivery della spec quarto verbo senza cambiare gerarchia agentica: prima rendere robusto il giudizio strutturato (C), poi rendere leggibile il red per sensore/causa (A).

Correzione preliminare:

- Il failure non correlato della suite organism era nel test `test_timeout_returns_defer`: patchava globalmente `asyncio.wait_for` e mandava in timeout anche la connessione Redis fake.
- `apps/organism/tests/supervisor/test_claude_brain.py` ora forza il timeout abbassando `CLAUDE_TIMEOUT_SECONDS`, senza intercettare tutto `asyncio.wait_for`.
- Verifica ampia organism: `UV_PROJECT_ENVIRONMENT=/tmp/nuzantara-organism-test-venv uv run --project apps/organism --extra dev pytest apps/organism/tests/supervisor apps/organism/tests/actuators apps/organism/tests/test_incident_ledger.py -q`: `185 passed, 5 warnings`.

Innesto C - robust structured judgment:

- `apps/cell/cell/slow/robust_parse.py`: parser JSON object tollerante a markdown/preamboli, retry su risposte vuote/non parseabili, feedback strutturato al modello e fallback esplicito dopo esaurimento.
- `apps/cell/cell/slow/reasoner.py`: robust mode default-on con kill switch `CELL_REASONER_ROBUST=false`; un output vuoto/garbage su red produce `alert_silent` con confidenza `0.0` e `fallback=True`, non piu' `alert_human` spurio. I fallback non vengono salvati come pattern appresi.
- `apps/backend-rag/backend/llm/deepseek_client.py`: helper `complete_json_async()` con preflight del token `JSON`, `response_format={"type":"json_object"}`, retry su empty/non-JSON e `reasoning_effort="low"` di default.

Innesto A - red leggibile e persistito:

- `apps/cell/cell/fast/red_summary.py`: funzione pura `summarize_pulse()` che deriva `driver_sensors`, headline e details dalla mappa sensore->status piu' metadata.
- `apps/cell/cell/core/pulse.py`: il pulse mantiene `sensor_status_by_name`, scrive la headline come `error_message` quando il sistema e' non-green e il reasoner non ha prodotto una causa, espone `driver_sensors`/`health_headline` su `PulseResult` e li passa all'observatory.
- Esempio chiuso: backup rosso con `age_hours=113.3` diventa headline persistibile tipo `backup stale 113h (...)`, invece di un red generico senza causa.

Test aggiunti:

- `apps/cell/tests/test_robust_parse.py`
- `apps/cell/tests/test_red_summary.py`
- `apps/backend-rag/backend/tests/unit/llm/test_deepseek_json.py`
- Estensioni in `apps/cell/tests/test_slow_reasoner.py` e `apps/cell/tests/test_pulse.py`.

Verifica P0s:

- `PYTHONPATH=apps/cell apps/backend-rag/.venv/bin/python -m pytest apps/cell/tests/test_red_summary.py apps/cell/tests/test_pulse.py apps/cell/tests/test_robust_parse.py apps/cell/tests/test_slow_reasoner.py -q`: `36 passed, 1 warning`.
- `PYTHONPATH=apps/cell apps/backend-rag/.venv/bin/python -m py_compile apps/cell/cell/fast/red_summary.py apps/cell/cell/core/pulse.py apps/cell/cell/slow/robust_parse.py apps/cell/cell/slow/reasoner.py apps/cell/tests/test_red_summary.py apps/cell/tests/test_pulse.py apps/cell/tests/test_robust_parse.py apps/cell/tests/test_slow_reasoner.py` passato.
- `apps/backend-rag/.venv/bin/python -m pytest apps/backend-rag/backend/tests/unit/llm/test_deepseek_json.py -q`: `4 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile apps/backend-rag/backend/llm/deepseek_client.py apps/backend-rag/backend/tests/unit/llm/test_deepseek_json.py` passato.
- `UV_PROJECT_ENVIRONMENT=/tmp/nuzantara-organism-test-venv uv run --project apps/organism --extra dev pytest apps/organism/tests/supervisor apps/organism/tests/actuators apps/organism/tests/test_incident_ledger.py -q`: `185 passed, 5 warnings`.
- `git diff --check` passato.
- Ritest Mini 2026-06-06: `tailscale status` mostra `100.93.236.6 mini-pro2 ... offline, last seen 1d ago`; `nc -vz -G 8 100.93.236.6 22` e `ssh -o ConnectTimeout=8 -o BatchMode=yes mini 'hostname; date'` sono ancora in timeout.

Stato dopo P0s:

- Chiuso nel quarto verbo: C `robust_parse` e A `red_summary`.
- Gia' chiuso in P0r: proof post-azione dispatcher/attuatore.
- Ancora non chiuso: D `suppression_digest`, B `RulesEngine.supersede`, auto-dismissione watcher e verifica live Mini.

## Wave autonoma P0t - quarto verbo D/B e auto-dismissione watcher

Obiettivo: completare i tre sotto-gap rimasti dopo P0s senza cambiare la gerarchia agentica (`L0 deterministic -> L1/L2 bounded judgment -> L3 council solo quando giustificato -> Zero/human per autorita' finale`). La correzione resta reuse-first: usa tabelle, state file, cooldown e test gia' presenti.

Innesto D - suppression digest:

- `apps/cell/cell/slow/suppression_digest.py`: digest delle soppressioni ripetute nelle ultime 24h, solo se la headline corrente e' ancora attiva, con `min_age_hours`, cooldown 6h e kill switch `CELL_SUPPRESSION_DIGEST_ENABLED`.
- `apps/cell/cell/core/pulse.py`: quando `alert_human` viene bloccato da cooldown/limite, registra `cell_alerts.action='alert_suppressed'` con la headline leggibile; ogni 60 pulse avvia un task non bloccante che emette digest e registra `suppression_digest_emitted`.
- Test: `apps/cell/tests/test_suppression_digest.py` copre emissione, cooldown, headline vuota, filtro headline attiva e cadence/kill switch; `apps/cell/tests/test_pulse.py` copre la riga `alert_suppressed`.

Innesto B - RulesEngine supersede:

- `apps/backend-rag/backend/services/olympus/rules_engine.py`: `supersede(old_rule_name, new_rule_id, reason)` aggiorna `superseded_by`, scrive audit `olympus_actions` e rimuove la regola vecchia dalla cache runtime.
- Le regole `source=base`/`initial` sono protette; sono eleggibili solo `learned`, `reflexion`, `dream`, stessa categoria, nuova regola attiva e non gia' superseded.
- `propose_supersessions()` e' shadow di default: scrive insight in `olympus_insights`; con `OLYMPUS_RULE_SUPERSEDE_MODE=enforce` applica la sostituzione.
- Test: quattro casi nuovi in `apps/backend-rag/backend/tests/services/olympus/test_rules_engine.py` per supersede, protezione base, shadow insight ed enforce.

Innesto auto-dismissione WR2:

- `scripts/wr2_supervisor_watchdog.py`: il ramo renderer-specifico (`pipeline_frozen`, `success_rate_low`) ora si auto-silenzia con receipt persistente nello state file quando `system_settings.wr2_canva_renderer_enabled=false`.
- Aggiunto marker opzionale `system_settings.wr2_canva_renderer_superseded_by`: se valorizzato, il watchdog scrive `last_self_silence_canva_renderer_reason=superseded` e `last_self_silence_canva_renderer_detail=<replacement>`.
- I cooldown stale `last_alert_pipeline_frozen` e `last_alert_success_rate_low` vengono cancellati durante l'auto-silenzio, cosi' una riattivazione reale non resta bloccata da vecchi cooldown.
- Il controllo `supervisor_down` resta separato: protegge il daemon WR2 e non viene spento dal kill switch del renderer.
- Test: `scripts/tests/test_wr2_supervisor_watchdog.py` aggiorna la fixture al fetch reale del kill switch e aggiunge i casi kill-switch OFF e superseded.

Verifica P0t:

- `PYTHONPATH=apps/cell apps/backend-rag/.venv/bin/python -m pytest apps/cell/tests/test_suppression_digest.py apps/cell/tests/test_pulse.py apps/cell/tests/test_red_summary.py apps/cell/tests/test_robust_parse.py apps/cell/tests/test_slow_reasoner.py apps/backend-rag/backend/tests/services/olympus/test_rules_engine.py apps/backend-rag/backend/tests/unit/llm/test_deepseek_json.py -q`: `56 passed`.
- `apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_wr2_supervisor_watchdog.py -q`: `18 passed`.
- `apps/backend-rag/.venv/bin/python -m py_compile scripts/wr2_supervisor_watchdog.py scripts/tests/test_wr2_supervisor_watchdog.py` passato.
- `git diff --check -- scripts/wr2_supervisor_watchdog.py scripts/tests/test_wr2_supervisor_watchdog.py` passato.
- Mini ritest 2026-06-06: `tailscale status` mostra `100.93.236.6 mini-pro2 ... offline, last seen 1d ago`; `nc -vz -G 8 100.93.236.6 22` e `ssh -o ConnectTimeout=8 -o BatchMode=yes mini 'hostname; date'` restano in timeout.

Stato dopo P0t:

- Chiuso nel codice: proof post-azione, C `robust_parse`, A `red_summary`, D `suppression_digest`, B `RulesEngine.supersede`, auto-dismissione watcher WR2.
- Chiuso su Pro: runtime gate `launchctl/plist/cron` a zero drift con filtro `--runtime pro_launchd`.
- Non dichiarato chiuso: verifica live Mini e i quattro label `mini_launchd`, perche' il nodo `100.93.236.6` non e' raggiungibile.
