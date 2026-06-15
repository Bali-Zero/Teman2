---
date: 2026-06-14
domain: operations
client_case: none
sources:
  - ~/.agent/decisions/dlq.json (live, 44 entries)
  - ~/.agent/decisions/sentinel_status.json (live)
  - ~/.agent/decisions/state/*.last.json (per-job state)
  - ~/.agent/decisions/job_registry.json (staleness thresholds)
  - scripts/nuzantara-sentinel.py + scripts/dlq_autopilot.py + scripts/sentinel_lib/repairer.py
  - cron-state.sh / cron-runner.sh (wrapper last_error convention)
  - cicatrix W70 / W50-51-52 / W53 / W54 / W64 / W78
  - 3 parallel triage subagents (garuda/KG, NLM/NB, ops/env)
  - Gemini 3.x (meta-pattern synthesis) + Gemini adversary (refuter); DeepSeek V4 Pro refuter UNAVAILABLE (HTTP 402)
method: opus-mythos (P1 immune-system TAC)
---

# Mythos P1 — Sistema Immunitario: perché il loop auto-heal non chiude

## §0 — Executive

Il connectome del 13-giu segnalava "39 job DLQ-terminal, healing=0, core infra dying NOW".
La TAC su disco **ridimensiona drasticamente l'allarme e ne sposta la diagnosi**:

- Stato live di partenza: **33 TERMINAL + 11 skipped_preflight, healing_actions_24h=0**, tutti
  `classification=UNKNOWN c=0.0`.
- Dei 33 TERMINAL, **19 erano job GIÀ GUARITI** (state-file = `ok`) mai rimossi → corpi contabili,
  non malati. **11 skipped_preflight** hanno tutti state=ok → non-fallimenti. I job *davvero* malati
  erano **~10-12, non 39**.
- I lead W70 specifici sono **in parte falsi su disco**: i backup (`fly_pg_backup`,
  `fly_qdrant_backup`, `rag_canary`) **non sono in DLQ**; `qdrant_snapshot` è skipped, non TERMINAL;
  **nessuno** dei backup-script contiene path-drift `Projects/nuzantara`. Il gate scettico Mythos ha
  abbattuto questi malati-fantasma (≈ il 40% atteso).

**Terapia eseguita questa sessione** (verificata live):
- 10 corpi fresh-ok + 1 falso-positivo (`dropbox_intake`) `dlq clear`'d → **dlq_terminal 33 → 22**
  (i 10 fresh-ok **non sono ri-apparsi** dopo un giro reale del sentinel = durabile).
- `mkdir ~/.cron-agent/logs` → risolve il chicken-egg di `nb_agents_daily_dr`.
- **PR #1413** (auto-merge SQUASH): porta nel sentinel l'enrichment-fatto-bene (stderr reale) +
  l'**auto-resurrezione** dei TERMINAL guariti + il conteggio healing. 11 test verdi; resurrezione
  **provata su dati live** (10/10 corpi fresh-ok resuscitati in dry-run, 0 mutazioni).

**Confine operatore**: i ~10 malati reali sono quasi tutti **drift di environment/secret/config** che
richiedono mani umane (ripristinare `~/.openclaw-cron-env`, ri-auth NotebookLM, regenerare un service
account, applicare una migration, decidere su un gateway cancellato) — fuori dal mio perimetro
autonomo. Vedi §Solo-operatore.

## §1 — Coda DLQ (l'organo accumulatore)

44 entry: 33 TERMINAL + 11 skipped_preflight. La coda **accumula corpi** perché `TERMINAL` è un
dead-end senza auto-resurrezione (W53 aggiunse il gate di soppressione; nessuno aggiunse l'edge
inverso "guarito → rimuovi"). 19/33 erano già `ok`. `dlq clear <job>` è l'unico modo (manuale) di
rimuovere un corpo → la coda cresce monotona finché un umano non la pota.

Triage deterministico (join DLQ × state-file × cron-log):
- **ALREADY_HEALTHY (19)**: state=ok. 10 fresh (age < soglia staleness) = clear-safe; 9 old-ts
  (post_publish_*, zombie_hunter, fly_cost_alert, nlm_nb1_daily_refresh, run_gap_scanner_*,
  auto_judgement_day, run_nb5_t4_monitor) = stale-risk (cleararli può ri-escalarli come `stale` se si
  rimuove il gate W53) → lasciati all'auto-resurrezione/operatore.
- **REAL_FAIL (14)**: vedi §4.
- **SKIPPED (11)**: NB pipelines + ragas + qdrant_snapshot + login_healthcheck + sync_damar, tutti
  state=ok → saltati al preflight, non falliti.

## §2 — Classificatore stderr (il nervo cieco)

Causa-radice della cecità, confermata su disco: i wrapper `cron-state.sh:55` / `cron-runner.sh:78`
scrivono `last_error = f"exit {exit_code}"` — letteralmente `"exit 1"`. Lo stderr REALE va nel log
proprio del job (redirect `>> logfile 2>&1`), **mai** nello state-file. Quindi `classify()` vede
`"exit 1"`, ritorna `UNKNOWN c=0.0`, e l'autopilot ritenta cieco 10× → TERMINAL.

Due tentativi di cura PRECEDENTI, entrambi non-arrivati al paziente:
- **PR #1344** (11-giu, su origin/main): aggiunge `_check_blind_heal_loop()` — un **detector** che
  allerta su `dlq_terminal>0 AND healing=0`. NON cattura stderr (il titolo del commit sovra-promette).
- **F08 enrichment** (13-giu): `_enrich_last_error_from_cron_log` scritto **nella copia HOME orfana**
  (`~/scripts/nuzantara-sentinel.py`, che launchd NON esegue), con regex che pretende
  `"exit N after M attempts"` (il wrapper non lo emette mai) e legge `~/logs/cron` (vuota per questi
  job). Tripla rottura: orfano + regex + dir.

**Fix (PR #1413)**: enrichment con regex che matcha il `"exit N"`/vuoto reale, legge `~/logs/cron-tmp`
prima, tail bounded a 16 KiB (no OOM su log multi-MB — bug colto dal refuter).

## §3 — Actuator auto-heal (il muscolo) + il contatore

`dlq_autopilot.process_job`: tier1 retry → tier2 aider → tier3 alert → TERMINAL a 10 tentativi.
`healing_actions_24h = log_entry["retried"]` (solo ciclo corrente). È **0 perché tutti i 33 sono
TERMINAL** (D0.1 guard li salta) — quindi 0 non è "rotto", è "tutti hanno già rinunciato e niente li
resuscita". L'auto-resurrezione (PR #1413) aggiunge `resurrected` al conteggio healing → il detector
#1344 smette di falsare quando il loop si auto-pota.

## §4 — Job-sorgente per famiglia (i ~10 malati reali — fan-out 3 subagent, ri-verificato)

| Job | Causa-radice (verificata) | Categoria | Fix | In perimetro |
|---|---|---|---|---|
| garuda_indexer, garuda_gc, knowledge_graph_builder | `~/.openclaw-cron-env` **MANCANTE** (sparito ~31-mag) → API key / DB password unset; garuda cade su fallback hardcoded **già ruotato da W38** (valore redatto) | env-drift | ripristinare l'env file | **operatore** (secret) |
| zantara_vision_warmup | `~/.zantara-gateway/warmup-vision.sh` cancellato (dir assente) → exit 127 | file-drift | ripristinare o rimuovere il cron | operatore |
| curiosity_loop | tabella Postgres `kg_proposals` mai provisionata su questo host | schema-drift | applicare migration | operatore (hot-zone) |
| run_ops_briefing | NB-11 (ops) ID mancante post NB-UUID-switch 18-mag | config-drift | ripopolare gli ID NLM | P3/operatore |
| nextdns_weekly_digest | `NEXTDNS_API_KEY` non sourced dal cron | secret-drift | sourcing secret | operatore |
| run_peraturan_ingestion | `GOOGLE_SERVICE_ACCOUNT_JSON` unset + SA revocato | secret-drift | regenerare SA | operatore |
| nb_agents_daily_dr | `~/.cron-agent/logs/` inesistente → redirect fallisce prima del mkdir interno | path-drift | **`mkdir` — FATTO** | **mio (fatto)** |
| run_nb2_pipeline, run_persona_validate, run_gap_scanner_layer_a | `nlm` CLI rotto post-UUID-switch + bug: weekend-skip/partial ritorna exit 1 invece di 0 | NLM-drift + code-bug | ri-auth NLM + exit 0 sul skip | P3 |
| dropbox_intake | **falso-positivo**: quota Drive transitoria durante backfill 527GiB; job sta girando e ha successo | transient | clear (fatto; ri-emerso `needs_aider`, si risolverà a fine backfill) | mio |
| auto_test | venv senza pytest → fallback a Xcode python | dep-drift | puntare PYTEST_CMD a un venv con pytest | borderline |

## §Meta-pattern — il vero topic: l'organismo è OPEN-LOOP

Domanda Mythos: *cosa si ripete attraverso TUTTI i finding?* Non i singoli malati — la
**malattia-delle-malattie**.

**La cura è prodotta ma non propagata al paziente.** Ogni fallimento — sia dei job, sia dei fix del
sentinel STESSO — è un **anello di propagazione rotto** tra *dove un cambiamento è fatto* e *dove la
cosa gira davvero*:

1. **code → runtime**: PR #1344 mergiato su origin/main ma **mai eseguito** (il sentinel gira dal
   checkout dev `~/Desktop/nuzantara`, **162 commit dietro**, senza puller).
2. **env → runtime**: `~/.openclaw-cron-env` creato una volta, poi **sparito** (~31-mag, finestra
   reboot) e mai ripristinato → 3 job morti in simultanea.
3. **DB/coda → realtà**: 19 job guariti in realtà ma ancora `TERMINAL` nella coda — **nessun hook di
   riconciliazione** stato-vs-esecuzione.
4. Varianti: fix scritto nella copia ORFANA; secret ruotato ma fallback hardcoded lasciato stale;
   UUID NotebookLM cambiato ma ID downstream non aggiornati.

**Riformulazione affilata (Gemini)**: *State and Execution Drift Blindness* — il sistema opera
**open-loop**: manca un meccanismo unificato per verificare che path runtime + stato env + DB dello
scheduler **siano allineati alla source-of-truth versionata**. Famiglia diretta: W70 (Air-path-drift),
W64 (esistere≠armato), W50/51/52 (HOME-fork), W78 (no-unlearning / system-shapes-the-agent) — tutte
istanze di "cambiato QUI, gira LÀ, niente fa il ponte".

**Versione falsificabile (refuter agy, adottata)**: *"il loop fallisce per **lossy telemetry +
unmonitored sentinel loopback**, non per drift generico."* Condizione di falsificazione: *se arricchisci
lo stderr E fai girare il sentinel da origin/main, e la coda CONTINUA ad accumulare falsi-positivi
TERMINAL, allora l'ipotesi drift è falsa.* PR #1413 + il deploy del checkout sono esattamente
l'esperimento.

**Caveat onesto (gate round 2, controesempi confermati)**: il pattern NON copre il 100%. ~2-3 malati
sono **intrinseci, non drift**: `dropbox_intake` (quota esterna), `run_nb2`/`gap_scanner` weekend-skip
(bug logico di exit-code: il deploy combaciava con l'intento, l'intento era sbagliato). Non sovra-
estendere il pattern a "tutto è drift" (sarebbe infalsificabile).

**Contromisura strutturale (Gemini, converge sui fix del PR)**: un wrapper unico `nuzantara-executor`
che per ogni job fa (1) self-sync+validate (pull main + verifica env/dir/schema), (2) intercetta lo
stderr nello state-file (= il mio enrichment), (3) **riconciliazione bidirezionale** (su successo
pulisce il flag TERMINAL = la mia auto-resurrezione). I pezzi (2) e (3) sono in PR #1413; il pezzo (1)
— il closed-loop di propagazione — è il lavoro strutturale residuo (operatore).

## §Terapia-eseguita

1. **`dlq clear` × 11** (10 fresh-ok + dropbox falso-positivo) → dlq_terminal **33 → 22**, verificato
   durabile dopo un giro reale del sentinel (i 10 non ri-appaiono; dropbox ri-emerge come needs_aider,
   atteso).
2. **`mkdir ~/.cron-agent/logs`** → nb_agents_daily_dr guarirà al prossimo giro (07:30).
3. **PR #1413** (`agent/nuzantara/infra/mythos-p1-immune`, auto-merge SQUASH, basato su origin/main =
   include #1344): enrichment-corretto + auto-resurrezione + healing counter + tail bounded 16KiB.
   **11 test** (importlib + HOME-isolati), tutti verdi; resurrezione provata 10/10 su dati live.

## §Solo-operatore (confine — NON eseguito da me)

1. **PROPAGAZIONE (il fix più ad alto leverage)**: il sentinel gira dal checkout dev **162 commit
   dietro** senza puller → PR #1413 e #1344 **non gireranno** finché `~/Desktop/nuzantara` non fa
   `git pull`. Decisione operatore (pull 162 commit tocca tutto ciò che gira da quel checkout) o
   istituire un puller/`nuzantara-executor`.
2. **Ripristinare `~/.openclaw-cron-env`** (NUZANTARA_API_KEY + FLY_POSTGRES_PASSWORD correnti) →
   resuscita kg_builder + garuda×2. **Security debt**: i garuda-script hardcodano una password (ora
   invalida post-W38) — rimuovere il fallback hardcoded.
3. **NotebookLM re-auth / ID** (NB-11 ops + nlm CLI post-UUID-switch) → nb2, persona, gap_scanner,
   ops_briefing. (P3.)
4. Secret/SA: `NEXTDNS_API_KEY`, Google service-account per peraturan. Decidere su gateway cancellato
   (`~/.zantara-gateway/warmup-vision.sh`: ripristinare o rimuovere il cron). Migration `kg_proposals`.
5. **DeepSeek API HTTP 402 (Payment Required)** — credito esaurito: il refuter Tier-3 del panel è giù.
   Top-up o verifica cost-breaker. (Ho usato un secondo agy come adversario di rimpiego.)
6. **Follow-up codice (non bloccante)**: contatore resurrection-rate per smascherare i flapper
   (90%-fail/10%-ok) che l'auto-resurrezione altrimenti maschera.

## Verifica finale (anti-hallucination)

- dlq_terminal 33→22 letto due volte da `dlq.json` su disco (recount post-clear + post-sentinel-run).
- Resurrezione: 10/10 su dati live con `clear_dlq_entry` mockato (0 mutazioni), verificato.
- OOM-bounded tail: log 5MB → output 499 char, tail reale trovato.
- PR #1413 auto-merge SET (SQUASH), BLOCKED su CI (atteso).
- Controesempi del refuter ri-verificati su disco (dropbox running PID confermato; weekend-skip = bug
  logico non drift).
