---
date: 2026-07-18
domain: operations
client_case: none
adversarial_review: exempt-machine-report
sources:
  - evidence-baseline/ (proprioception last.md/json, launchd-liveness-full.json, launchagent-reconcile-baseline.md, launchctl prints ×19, log tails ×13, crontab-baseline.txt, escalations-baseline.jsonl)
  - scripts/launchd_liveness_detector.py · scripts/launchagent-state-bridge.py · scripts/arsenal_probe.py · scripts/proprioception.py
  - infra/healer/healer-run.sh · infra/launchagents/wrappers/pro-healer.sh
  - apps/mata-garuda/mata_garuda/workers/plist_watchdog.py
---

# TAC S1 "IL MEDICO" — immune/infra dell'organismo (2026-07-18)

> Sessione lunga autonoma su Pro, GEAR 3 modus, worktree `infra-medico-0718`.
> Baseline immutabile fotografata in `evidence-baseline/` PRIMA di ogni cura.
> Perimetro: launchd/organi/receptors/ledger/board/home-fork/docs. Escluso: S2 (KBLI), S3 (visa engine), S4 (intake/CRM).

## Baseline (14:07 WITA) → esito

| Receptor | Baseline | Post-cura (atteso al prossimo run) |
|---|---|---|
| launchd_liveness | 14 FAILING-HONESTLY + 5 NOT-LOADED, 4-5 alarm | **0 alarm** (provato live dal branch PR #2710); 13 FAILING-HONESTLY residui si auto-RECOVERANO ~20/07 (72h uptime gate) |
| organs_heartbeat | 7 organi malati | 2 curati subito (sentinel_cell orfano rm, wr3.supervisor revived), 2 in PR (post_publish_poller bridge, launchd_liveness via #2710), 1 fresco (arsenal_probe 7.9d→0), 1 recovery-by-design (consumer_lag), 1 natural-wait (cell.organism ← timeout cron curato) |
| regulatory_promotion | 3 delta stranded | committati (branch medico) |
| docs_sync | INDEX.md drift | regen committata (stesso branch, W86-by-squash) |
| launchagent_canon | 85 finding | lane dedicata (subagent W3) — vedi esito in coda |
| seat<->armed | UNWATCHED su Pro, report 193h stantio | probe esteso a Pro (proprioception + pro-healer Receptor D), report rigenerato live: 5 LIVE / 1 BALANCE_DEAD / 1 TIMEOUT |
| board escalations | 56 righe (13 pending nette) | 65 righe, **4 pending nette** (1 = S4, 3 root-caused e documentate) |

## Diagnosi — le 4 malattie del giorno

### 1. Boot-storm del 17/07 22:20 (exit stantii, processi vivi)
Il Pro è stato riavviato il 17/07 ~22:20. I daemon KeepAlive sono ripartiti PRIMA delle loro dipendenze (Redis "loading dataset", pg-proxy 15432) → primo run exit 1 → launchd conserva l'exit stantio mentre i processi ora girano sani. Colpiti: intel-dedup-gateway, meta-dispatcher, research-sentinel, federation-alert-dispatcher, openclaw-whatsapp-bridge, post-publish-poller — tutti verificati `state=running` con log operativi. Il detector li tiene FAILING-HONESTLY fino a 72h uptime **by-design** (anti-crash-loop-masking). Nessuna cura necessaria; cura strutturale opzionale (wait-for-dependency nei wrapper) NON eseguita — costo>beneficio, il rumore è auto-estinguente.

### 2. Guardiani che si auto-flaggano (exit-code-as-alarm)
audit-launchd.daily, launchd-liveness-detector.daily, verify-connectome, consumer-lag.check escono 1 **quando trovano problemi altrui** → il receptor liveness li mostra malati per sempre. Deliberatamente NON curato in questo ciclo (cambiare il contratto exit di 4 guardiani ha consumer sconosciuti — es. missed-runs alerter — e merita red-team dedicato). → PENDING-ARMS.

### 3. Falsi malati del layer di monitoring (5/7 heartbeat)
- `mata_garuda.sentinel_cell`: sidecar ORFANO post-rename (organo rinominato `sentinel_daily.mini` il 07-07, file vecchio mai cancellato; il detector globba la dir senza cross-check col registry). Curato: `rm` del sidecar.
- `pro.post_publish_poller`: bridge `daemon=False` → status derivato dall'exit stantio invece che dal pid. Curato: `daemon=True` + test guilt+innocence.
- `wr3.supervisor`: plist disabilitato il 17/07 (`-recon`, indagine pg-proxy) e mai formalmente ritirato dal bridge → falso failed perpetuo. pg-proxy oggi sano → **revived** (bootstrap, pid 85667, err log fermo = niente storm). Mandato esplicito "macchina contenuti".
- `pro.launchd_liveness` degraded: i suoi 4 alarm erano 2 falsi NOT-LOADED (Label≠filename) + 2 disarmi deliberati → curati da PR #2710.
- `pro.arsenal_probe`: NESSUN trigger esisteva su Pro (probe healer-armed solo su Mini). Curato: Receptor D nel pro-healer + primo run live.
I 2 allarmi VERI: `consumer_lag_check` (lag scorer 984→534 in discesa — recovery pianificata dal fix #2435, si spegne sotto 500 al prossimo run notturno) e `cell.organism` ← cron `nlm-deep-research` ucciso OGNI notte da `TIMEOUT after 300s` del cron-agent (pipeline con query NLM da 180s l'una) → curato con `CRON_AGENT_TIMEOUT=1800` inline nel crontab (prova naturale 01:10).

### 4. Detector/receptor che mentono per costruzione (3 bug + 1 fantasma)
- `_classify`: ramo exit_code PRIMA di prog_exists → kg-query-api (program INESISTENTE, exit 78) classificato FAILING-HONESTLY invece di ARMED-TO-NOTHING.
- Label dal FILENAME invece che dal Label key → kita-feed/wr2-bridge (vivi e sani) perpetuamente NOT-LOADED. Il pattern giusto esisteva GIÀ in plist_watchdog._label_of.
- Disarmi deliberati (launchctl disable) contati come alarm per sempre → nuovo verdetto DISABLED non-alarm.
- kg-query-api sul Pro: istanza FANTASMA di un servizio solo-Mini (wrapper `~/scripts/mini-infra/` esiste solo là; servizio vivo 100.93.236.6:8990 → 200). Era già stato disarmato (`.disabled-pre-split-brain-fix`) e il **plist_watchdog l'ha resuscitato** (reinstalla da repo-snapshot qualunque com.matagaruda.* che launchctl non conosce, senza machine-awareness) — il guaritore ricreava la malattia (famiglia #10). Curato: disable persistente+bootout sul Pro + host-pins dichiarativo nel watchdog (branch watchdog-hostpins).

## Cure shipped (stato al momento della scrittura)

1. **PR #2710** (detector 3-fix, 21 test nuovi, suite 17655 verde, auto-merge armato) — alarms 4→0 provato live.
2. **Branch watchdog-hostpins** — host-pins.json + skip machine-aware nel plist_watchdog (push in suite).
3. **Branch medico-0718** — 7 commit: unset FLY_API_TOKEN nel ramo newsletter (root-cause riprodotta: token stantio nel secrets file oscura l'auth valida di ~/.fly/config.yml — terza recidiva della classe, antidoto già in fly-pg-backup.sh:28) · bridge poller daemon=True · plist canon cost-advisor via wr2-cron-wrapper (cura InvalidPasswordError backend_rag_v2, classe W87) · 3 delta regulatory · INDEX.md regen · Receptor D arsenal su pro-healer + proprioception pro · pin deepseek-v4-flash in article_composer (alias legacy hard-fail il 24/07; il class-audit ha scoperto che il default da solo NON bastava — il call-site del router passava l'alias esplicitamente) · weekend-halt exit 0 (i pipeline nb 1-6 morivano in DLQ ogni sabato per uno skip intenzionale).
4. **Live**: l5-2-phase2b riarmato · kg-query-api disabled+bootout · wr3.supervisor revived · sidecar orfano rm · crontab timeout 1800s · board 13→4 pending nette (9 resolved con evidenza via writer canonico).

## §Meta-pattern (la malattia-delle-malattie)

**Il sistema di monitoring invecchia più in fretta del sistema che monitora, e nessuno monitora il monitor.** 5 heartbeat su 7 erano bug del LAYER DI OSSERVAZIONE (sidecar orfano, colonna exit stantia, disarmo mai formalizzato, label derivato dal nome file, report seat di 193h ri-servito come fresco), non degli organi. La firma ricorrente: **un segnale di stato letto da un PROXY che può marcire in silenzio** — l'exit-code sticky invece del pid, il filename invece del Label, lo snapshot repo invece dell'hostname, il sidecar-file invece del registry, l'età del report mai confrontata con la cadenza promessa. È la fusione operativa di #2 (Esiste≠Armato) e W88 (il proxy mente): ogni receptor nuovo dovrebbe nascere con la domanda "quale proxy sto leggendo, e chi mi dice quando marcisce?". Secondo pattern: **il guaritore che ricrea la malattia** (plist_watchdog resuscita l'istanza fantasma; l'exit-as-alarm dei guardiani genera il rumore che desensibilizza il receptor che dovrebbe leggerli — cry-wolf strutturale). Terzo: **le cure arrivano nel repo ma non nel runtime** (fix scorer merged il 14/07 e vivo solo perché il sentinel daily lo esegue dal checkout fresco; il fix mind-map era già live ma il triage lo credeva rotto — anche il verificatore va verificato, W65).

## §Solo-operatore (NON tentati, one-liner pronte)

1. **Secrets file — disarmo del FLY_API_TOKEN morto** (host_boundary blocca correttamente la scrittura agent):
   `sed -i '' '44s/^FLY_API_TOKEN=/#DISABLED-2026-07-18-stale FLY_API_TOKEN=/' ~/.nuzantara-secrets.env`
   Evidenza: con quel token `fly status -a nuzantara-rag` → "Could not find App"; senza → OK. Il wrapper newsletter è già immunizzato via unset; restano esposti organism-supervisor (FlyMachinesStart) e chiunque altro sourci il file. In alternativa: incollare il token valido corrente (rotazione = solo operatore).
2. **DeepSeek top-up** (BALANCE_DEAD provato dal probe): decisione business — nota che il burner residuo sospetto è `intake_refinery_pilot.py` (raw, non guardato, perimetro S4 — segnalato a quella lane).
3. **TCC re-grant** per i wrapper sotto ~/Desktop (audit-launchd trampoline W84) — System Settings, se si vuole eliminare il trampoline ssh-localhost.
4. **agy TIMEOUT sul Pro** (probe): se persiste al prossimo tick del pro-healer, serve login interattivo agy.

## Residui / natural-wait (righe PENDING-ARMS aggiornate nel ledger)

- Newsletter: prova naturale al prossimo run daily (token unset + fly config auth provata a mano).
- Cost-advisor: prova naturale al fire 08:00 di domani (plist live da aggiornare post-merge — ALIGN).
- Weekend-halt: prova naturale sabato prossimo (o stasera sui run 1-6 se oggi halta).
- mind-map --no-progress: fix GIÀ live (Desktop checkout fresco) — prova al run 22:00; l'escalation resta pending finché non passa.
- nightly_autofix_ci: 3/3 "Push failed" post-commit Codex oggi — lane separata.
- Exit-contract dei 4 guardiani (cry-wolf strutturale) — red-team dedicato prima di cambiare il segnale.
- **W96 in variante LETTURA (trovata live, fuori perimetro — lane S4/backend)**: `test_intake_review.py::test_reject_writes_no_crm_rows` conta le righe CRM sul DB dev CONDIVISO attorno a una finestra ~0.5s → col backfill S4 attivo (clients 11774→11975 in ~20min) il pre-push di QUALUNQUE branch backend sul Pro fallisce a caso. La suite intera diventa una roulette mentre un writer live gira. Cura di classe (non applicata qui, perimetro S4): il test deve contare su un DB effimero/di-test o filtrare per le PROPRIE righe seed, mai il count globale di un DB condiviso.
- run_nb5_t4_monitor: pausa deliberata documentata nel crontab (t4-cure-lane) — non è un malato.
- ALIGN-FLEET: pro-healer live copy, plist cost-advisor live, pull main checkout Pro/Mini/M5 post-merge.
