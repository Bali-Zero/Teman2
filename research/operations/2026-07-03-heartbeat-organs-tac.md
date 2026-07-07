---
date: 2026-07-03
domain: operations
client_case: none
captured: 2026-07-02 (flight session P1, operator airborne)
sources:
  - ~/.organism/last_seen/ (125 sidecar files, live reads this session)
  - launchctl print gui/501/* (live, read-only)
  - ~/Library/Logs/skills-bridge-consumer.log · ~/logs/alert-dispatcher/ · ~/logs/fly-restart-detector.log · ~/logs/l5-2-phase2b-trigger.log
  - git history (wip 74b8af953, PR #1805, connectome launchd-pro.yaml)
  - research/operations/2026-06-28-heartbeat-channel-dead-core-organs.md (prior TAC)
  - research/operations/2026-06-30-claude-code-perfect-session-doctrine.md §8
---

# TAC — I 9 organi heartbeat morti/malati (root-cause, 2026-07-02)

> Mandato Gear 3 (flight session P1): root-cause dei 9 organi flaggati dal receptor
> di boot (doctrine §8). Ipotesi di partenza: "il WRITER/bridge heartbeat è morto".
> **FALSIFICATA a livello di flotta**: i due bridge (pg_organism_bridge,
> launchagent-state-bridge) sono vivi e scrivono onestamente. La malattia è
> per-organo, e le malattie sono QUATTRO, non una. 5 PR di cura spedite e armate
> in auto-merge durante la diagnosi.

## Verdetto per organo

| Organo | Sintomo al boot | Root cause REALE | Cura | Stato |
|---|---|---|---|---|
| `pro.federation_alert_dispatcher` | stale 22.5d, status=ok | Daemon VIVO (launchd running); il codice heartbeat esiste solo nel wip M5 `74b8af953` (2026-06-07), **mai mergiato su main** → il processo su main non ha mai scritto il sidecar. W81 a livello di codice. | **PR #1918** porta l'hunk field-proven + fixa registry drift (`owner_module` puntava a uno .sh inesistente) | PR armata; arm = pull Pro + restart daemon (operatore) |
| `cell.observatory` | stale 29.5d, status=fail | Plist MAI presente in `~/Library/LaunchAgents` oggi (esiste solo nel repo) → organo spento dal ~2/6. L'ultimo battito è un `RuntimeError` da `config.py` (env mancante, verosimilmente `EVENTBUS_DATABASE_URL`). Log forensi DISTRUTTI dalla pulizia disco di stamattina (dir svuotata 08:47). | Operatore: env in secrets + `cp` plist + bootstrap (3 plist: collector/selfcheck/prune) | §Solo-operatore |
| `cell.skills_bridge_consumer_launchd` | failed, exit 1 | Redis locale Pro ha `requirepass` dal **29/6 06:38** (mtime redis.conf); il consumer si connette senza credenziali → `AuthenticationError` a ogni tick dal 29/6 ~08:50 | **PR #1921**: carica secrets env + inietta `REDIS_PASSWORD` nell'URL | PR armata; dipendenza operatore: `REDIS_PASSWORD` nel secrets env |
| `pro.fly_restart_loop_detector` | degraded (fresco) | Semantica: l'organo scriveva il suo FINDING nel campo salute. 1 machine `stopped` benigna su nuzantara-rag (autostop, 0 unhealthy checks dal 27/6, /health 200) → degraded ogni 15min. In più lo script viveva SOLO in `~/scripts/` (HOME-fork #1). | **PR #1924**: promozione nel repo + sidecar = salute del monitor; findings restano su Telegram | PR armata; arm = cp → ~/scripts |
| `pro.l5_2_phase2b_trigger` | failed, "label not loaded" | One-shot che ha sparato il 2/6 e si **auto-scarica by design**; connectome lo marca retired 20/6. Il bridge continuava a monitorarne la liveness launchd → falso-malato permanente. ⚠️ il one-shot uscì con **exit=1**: l'analyzer Phase 2b FALLÌ e si auto-marcò "fired". | **PR #1916** rimuove dal bridge. Il fallimento business (Phase 2b mai eseguita) → §Solo-operatore | PR armata |
| `pro.wa_viewer` | failed, "label not loaded" | Ritirato il 19/5 (plist rinominato `.retired` + label disabled). Stessa classe: il ritiro non si è propagato al monitor. | **PR #1916** rimuove dal bridge | PR armata |
| `wr2.canva_token_watchdog_launchd` | failed, exit 1 | `OrchestratorTokenStorage.load_sync()` fallisce su Pro (`TokenStorageError` → telegram + exit 1 SENZA log: entrambi i log 0 byte). Il token Canva non è leggibile su Pro (keychain creds solo su M5) E la dipendenza è superseded (renderer → HTML/CSS+Playwright dal 6/6, immagini → FlowKit). L'exit 1 è "onesto" ma perpetuo. | Decisione operatore: ritirare il watchdog vs re-bootstrap token | §Solo-operatore |
| `pro.eventbus_meta_dispatcher` / `pro.eventbus_observatory` | (usciti dall'alert, nel set del 30/6) | Recovered: daemon con pid vivi; il bridge registra `exit_code:1` storico ma status=ok | nessuna | ok |
| `cell.organism` | (nel set del 30/6) | Recovered: sidecar fresco, pulse_count vivo | nessuna | ok |

## Cure spedite (cure-while-diagnosing, tutte auto-merge armato)

| PR | Cosa | Probe eseguito |
|---|---|---|
| #1916 | Bridge: stop monitoraggio 2 organi ritirati | ast.parse + entries 90→88 + grep refs pulito |
| #1918 | Federation daemon: heartbeat thread (port dal wip) + registry fix + checksum refresh | sidecar JSON reale scritto in scratch dir; validate_organs_registry ✓ |
| #1921 | Skills consumer: auth Redis (secrets load + REDIS_PASSWORD inject) | 4 assertion su `_resolve_redis_url` PASS |
| #1923 | pg-organism-bridge: `REDISCLI_AUTH` su XADD + degrado VISIBILE (warning, prima debug+rc0) | guilt-probe riproduce verbatim il guasto live (`rc=0 reply=NOAUTH`) |
| #1924 | Fly detector: promozione repo (HOME-fork) + semantica sidecar onesta | sandbox HOME + fly stub: alert path attivo, sidecar `ok` con metadata |

## §Meta-pattern (la malattia-delle-malattie)

I 7 verdetti sembrano 7 malattie; sono 4 famiglie, e le 4 famiglie hanno UNA radice.

Le famiglie: (1) **cura-costruita-mai-armata** — il fix heartbeat del federation daemon
è rimasto 25 giorni in uno snapshot wip; il plist di cell.observatory è nel repo ma non
in launchd (W81, due incarnazioni). (2) **Il ritiro non si propaga** — wa_viewer e l5_2
sono morti LEGITTIMAMENTE, ma nessun protocollo di ritiro ha aggiornato i loro monitor:
il cimitero vive nel monitor. (3) **Hardening senza sweep dei consumer** — il
`requirepass` del 29/6 ha rotto in silenzio OGNI client Redis locale non autenticato
(famiglia #9: contratto condiviso cambiato da un lato solo). (4) **Finding conflato con
salute** — il fly detector scrive ciò che OSSERVA nel campo che dice come STA.

La radice unica: **il canale heartbeat non ha un contratto di ciclo-vita**. Quattro
superfici pretendono di descrivere lo stesso organismo — `organs_registry.yaml`, la
lista `BRIDGED_LABELS` del bridge, lo stato launchd reale, la directory dei sidecar —
e nessun processo le riconcilia. Ogni organo entra nel canale ad-hoc (codice
uncommitted, script in $HOME, entry manuale nel bridge) ed esce ad-hoc (retire,
self-unload, refactor). Ogni finding di questa TAC è una divergenza tra due di quelle
quattro superfici. La credenza difettosa che le genera tutte: *"la directory dei
sidecar riflette l'organismo"* — no: riflette la STORIA di chiunque abbia mai scritto
lì. L'antidoto strutturale è quello già indicato da W81: un **reconciliation-report**
(segnalatore, non attuatore) registry ↔ bridge ↔ launchd ↔ sidecar, che avrebbe
intercettato tutti e 7 i casi prima che diventassero rumore di boot.

Corollario dottrinale (estende il 2026-06-28): il receptor di boot oggi grida per
organi ritirati e per finding benigni — un receptor che cry-wolf addestra il cervello
a ignorarlo, che è esattamente la cecità che doveva curare.

## §Solo-operatore (boundary — serve Zero / fisico / strategico)

1. **Restart daemon federation** dopo merge #1918 + pull Pro: `launchctl kickstart -k gui/501/com.nuzantara.federation-alert-dispatcher` (il pull su Pro è bloccato dal file untracked del sibling wa-mirror — PENDING-ALIGN:Pro già a ledger). Il KeepAlive lo raccoglierebbe comunque al prossimo crash-cycle, ma il kickstart è deterministico.
2. **`REDIS_PASSWORD` nel secrets env**: verificare che `~/.nuzantara-secrets.env` contenga la password del requirepass del 29/6 (chi l'ha impostata l'ha salvata dove?). Senza, #1921/#1923 restano a vuoto. Poi restart `com.nuzantara.pg-organism-bridge`.
3. **cell.observatory**: decidere se l'organo serve ancora (severity_on_silence=critical nel registry dice sì). Se sì: `EVENTBUS_DATABASE_URL` nel secrets env + `cp infra/launchagents/com.nuzantara.cell-observatory*.plist ~/Library/LaunchAgents/` + bootstrap. Chi ha rimosso i plist e quando resta ignoto (forense distrutta dalla pulizia log di stamattina — le pulizie disco dovrebbero risparmiare i log degli organi rossi).
4. **Canva watchdog**: decisione retire-vs-fix. Il renderer è HTML/CSS (6/6) e le immagini FlowKit, ma la skill wr2-carousel-pipeline menziona ancora "Canva apply" — se Canva è morto davvero: rm plist + rimozione entry bridge (PR banale a valle della decisione).
5. **L5.2 Phase 2b mai eseguita**: il one-shot bruciò il colpo con exit=1 il 2/6 e si auto-marcò fired. Se l'enforcement hot-zone Phase 2b è ancora desiderato, va ri-armato manualmente (runbook `docs/runbooks/l5-2-phase2b-auto-trigger.md`). Mistero residuo: QUALCOSA esegue il wrapper ogni giorno alle 09:00 (firma cron nei log stderr, ma nessuna entry crontab trovata) — candidati: batch 9:00 (`job_health`, `cron-agent`); da identificare prima del decommission completo.
6. **pg.sh rotto su Pro** (recidiva W87): manca l'item Keychain account `nuzantara_readonly` (esiste il service ma non quell'account). Il probe DB del mandato è degradato con grazia (Law 4) e NON eseguito. `security add-generic-password -s nuzantara-postgres-readonly -a nuzantara_readonly -w '<pw>'`.
7. **Machine stopped su nuzantara-rag dal 27/6** (4 machine, 3 started, 0 unhealthy, /health 200): quasi certamente autostop/stop legittimo post-deploy, ma 5 giorni di alert Telegram in cooldown sono rumore — confermare che sia expected o distruggerla.
8. **P1 — 4 daemon eventbus in crash-loop dal 30/6** (`AuthenticationError`, vedi Findings collaterali): la pipeline eventbus Pro (meta-dispatch, observatory, dedup, research-sentinel) è FERMA da 2+ giorni. Cura = REDIS_PASSWORD nell'env dei loro plist (o secrets-load nei py in `~/scripts/eventbus/`) — HOME-fork con HOME avanti del repo, quindi mano operatore o sessione dedicata con riallineamento repo prima (W88).

## Findings collaterali

- **Blast-radius requirepass 29/6 — PIÙ AMPIO del previsto (scoperto a valle, P1)**: oltre ai 2 curati, i **4 daemon eventbus** (`meta_dispatcher`, `observatory`, `intel_dedup_gateway`, `research_sentinel` — tutti in `~/scripts/eventbus/`, HOME-fork) sono in **crash-loop `AuthenticationError` dal 30/6 07:52** (le connessioni long-lived li hanno protetti fino al primo restart post-hardening; 34MB di log storm = famiglia #7 KeepAlive). ⚠️ La memoria del sibling di oggi dice "meta_dispatcher HOME avanti del repo" → un sync repo→HOME REGREDIREBBE (W88): la cura va fatta sui file HOME o dopo riallineamento — operatore. Altri client non-auth censiti da sweepare: `system_doctor.py`, `seed_cell_skills_manual.py`, `sentinel_lib/zombie_hunter.py`, `apps/cell/cell/main.py`+`config.py`. Il flusso `organism:events` (XADD dal pg-bridge) è stato **muto dal 29/6** — il Supervisor ha visto il nulla senza saperlo.
- **Il verde che mente, un livello più giù**: il sidecar del pg-bridge diceva `ok tick` mentre il suo XADD falliva a ogni evento (`rc=0` + reply NOAUTH + log DEBUG). Curato il sintomo di visibilità in #1923; la lezione è che l'heartbeat misura il LOOP, non il LAVORO.
- **Incidente di probe (mio)**: il probe sandbox del fly detector ha ereditato `TELEGRAM_BOT_TOKEN` dall'env di shell → 1 falso alert Telegram reale inviato alle 15:42, corretto subito con messaggio di chiarimento sullo stesso canale. Registrato in AMENDMENTS: i probe con side-effect esterni girano sotto `env -i`.
- **Tool Agent morto in sessione headless** ("Could not determine current tmux pane/window") → fan-out impossibile; diagnosi eseguita inline. Registrato in AMENDMENTS.

## Riconciliazione ARMED (post-merge, prossima sessione Pro)

```
cp scripts/launchagent-state-bridge.py ~/scripts/ && cmp -s scripts/launchagent-state-bridge.py ~/scripts/launchagent-state-bridge.py
rm ~/.organism/last_seen/pro.wa_viewer.json ~/.organism/last_seen/pro.l5_2_phase2b_trigger.json
cp scripts/fly-restart-loop-detector.sh ~/scripts/ && cmp -s scripts/fly-restart-loop-detector.sh ~/scripts/fly-restart-loop-detector.sh
# proof-of-armed: boot successivo senza wa_viewer/l5_2/fly_detector nei findings;
# sidecar federation con ts < 3 min; log consumer "no new events"/"XADD'd" senza AuthenticationError.
```
