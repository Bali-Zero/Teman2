---
title: "250 € di cloud: dove metterli (e dove no)"
date: 2026-10-12
domain: operations
client_case: none
adversarial_review: exempt-same-family-3-lens-refutation-no-cross-family-cli-in-cloud-session
sources:
  - CLAUDE.md
  - SYMBIOSIS.md
  - AUTONOMOUS_OPS.md
  - FLEET_TOPOLOGY.json
  - docs/rules/RULINGS.md
  - docs/rules/operations.md
  - docs/SLO.md
  - docs/runbooks/zero-cutover.md
  - docs/runbooks/qdrant-estate-reconciliation.md
  - docs/runbooks/telegram-token-rotation.md
  - docs/runbooks/fly-logs-accumulator.md
  - docs/ops/pse-registration-balizero.md
  - docs/audits/2026-08-20-visa-oracle-dpia-v2.md
  - docs/scars/cicatrix-scars.md
  - docs/specs/localci-sovereign-2026-10-07.md
  - docs/specs/localci-host-floor-2026-10-11.md
  - docs/superpowers/specs/2026-04-24-air-retirement-cloud-offload-design.md
  - docs/superpowers/specs/2026-05-10-mini-h24-server-migration-design.md
  - docs/AUTOMATIONS_REFERENCE.md
  - .claude/skills/modus/PENDING-ARMS.md
  - shared/escalations_pro.jsonl
  - research/operations/2026-09-10-fly-cost-review-personal-org.md
  - research/operations/2026-09-10-pr-time-queue-and-fly-vercel-cost-study.md
  - research/operations/2026-08-19-near-free-tools-token-cost-panel.md
  - research/operations/2026-08-28-beyond-sota-anatomy-16-lanes/X2-fleet-runtime-ops.md
  - research/operations/2026-08-28-beyond-sota-anatomy-16-lanes/B7-data-platform-reliability-security.md
  - scripts/fly_cost_guard.py
  - scripts/fly-pg-backup.sh
  - scripts/fly-qdrant-backup.sh
  - scripts/qdrant-snapshot.sh
  - scripts/pg-restore-drill.sh
  - scripts/ci/restore_drill_verify.py
  - scripts/fleet_watch.py
  - scripts/tg_notify.py
  - scripts/lib/heartbeat.sh
  - scripts/healer_receptor_registry.py
  - scripts/check_autonomous_ops_staleness.py
  - scripts/fly_logs_accumulator.sh
  - infra/scripts/fly-backup.sh
  - .github/workflows/cron-fly-cost-alert.yml
  - .github/workflows/restore-drill.yml
  - apps/backend-rag/fly.toml
  - apps/backend-rag/backend/core/collection_registry.py
  - apps/backend-rag/backend/app/metrics.py
  - apps/organism/organism/organs_registry.yaml
  - apps/cell/cell/sensors/backup_sensor.py
  - gh run list -R Bali-Zero/Teman2 --workflow restore-drill.yml (2026-10-12)
  - https://fly.io/pricing-update/
  - https://docs.fly.io/about/pricing
  - https://healthchecks.io/pricing/ e /docs/
  - https://api.vultr.com/v2/plans
  - https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
  - https://docs.cloud.google.com/free/docs/free-cloud-features
  - https://gcloud-compute.com/e2-micro.html
  - https://qdrant.tech/pricing/
  - https://www.tigrisdata.com/pricing.md
  - https://developers.cloudflare.com/r2/pricing
  - https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
---

# 250 € di cloud: dove metterli (e dove no)

## Risposta in 10 righe

1. **Nessuna attività cloud è sbloccata da questi 250 €.** Otto candidati, tre lenti avversarie ciascuno: 23 verdetti su 24 confutano il punto "il credito è il vincolo". I tre dolori misurati dell'organismo si curano a 0 €.
2. I dolori misurati sono: un **solo canale di allarme** (il bot Telegram è stato muto per 14 giorni a settembre–ottobre), un **drill di restore rosso** da due mesi per una causa nota che si risolve con due righe, e una **bolletta Fly mai letta** dopo il repricing del 1° ottobre.
3. **Azione immediata a 0 €, oggi:** disattivare il drill mensile su GitHub. Ogni mese scarica un dump con dati cliente su un runner di Microsoft e stampa la coda del log in un job pubblico — un'esposizione che esiste indipendentemente da qualunque scelta sul credito. Subito dopo, le cinque voci di igiene a 0 € elencate più sotto.
4. **Attività cloud-native consigliata (#1):** una sentinella fuori flotta più un secondo canale di allarme — ricevitore gratuito di "battiti" (20 controlli), un secondo bot Telegram, il healer che legge in uscita. Costo 0 €/mese; 20 $/mese solo se servono più di 20 controlli (14 mesi di credito). Zero sceglie prima tra la variante solo-in-flotta (nessun terzo) e quella con ricevitore esterno.
5. **Precondizione a 0 €:** riparare il restore drill e spostarlo su Mini, come Zero ha già deciso l'11 ottobre, e mettere la sua ricevuta tra i controlli della sentinella.
6. Cosa prova: si simula il guasto del 22 settembre (bot muto) e si verifica che l'allarme arrivi comunque, su un canale che non dipende dal token del bot di flotta.
7. **Il credito:** se è Fly, molto probabilmente si consuma da solo sulle prossime fatture (~2,5–3,4 mesi dell'estate) — quella finestra va usata per eseguire i tagli aperti dal 10 settembre; se è contante, resta riserva o paga il tier a pagamento del ricevitore; se è GCP o VPS, scade: non costruirci nulla di ricorrente.
8. Zero deve decidere: la forma della sentinella (in-flotta o con provider esterno gratuito), la creazione del secondo bot, la ri-certificazione di AUTONOMOUS_OPS (scaduto da 41 giorni), la lettura del Cost Explorer, e le tre decisioni Fly ferme da un mese (nodi, volumi, drive).
9. Nessun nuovo app Fly, nessun VPS, nessun nuovo cron su GitHub, nessun dump in chiaro verso un secondo provider: ogni forma che ne aveva bisogno è stata confutata.
10. Nessun dato cliente lascia Pro/Mini in nessuna forma raccomandata, una volta disattivato il drill su GitHub. Se il credito è a scadenza (trial), vale la scadenza, non l'aritmetica: spenderlo male per non perderlo sarebbe il primo errore.

## Glossario minimo

- **Bites:** la riga obbligatoria di ogni PR che nomina chi consuma la modifica e l'osservazione concreta che prova che è in vigore (CLAUDE.md, Builder Contract §2).
- **launchd:** lo scheduler di macOS; "job launchd su Mini" = un'attività schedulata sul Mac Mini, non nel cloud.
- **HOME-fork:** la copia di uno script in `~/scripts` sul Pro, che è quella che gira davvero e che può divergere dal repo (famiglia di cicatrici #1). Una PR unita non è "viva" finché quella copia non è riallineata.
- **Dedup / scala dedup:** il gateway Telegram tace i ripetuti dello stesso allarme per 6, 24, 72, 168 ore; dopo un guasto del token va azzerata, altrimenti un allarme vero resta muto fino a 7 giorni.
- **operator[gui] / [credential] / [business] / [secret]:** le categorie di azioni che restano nelle mani di Zero (clic in una console, creazione di una chiave, decisione di spesa, custodia di un segreto).
- **Livello 5 (Level-5):** la verifica del restore che controlla contenuti e invarianti delle tabelle, non solo che il comando sia finito.

## Ipotesi sul credito

Il provider non è scritto da nessuna parte nel repo (grep su `docs/rules`, `FLEET_TOPOLOGY.json`, `SYMBIOSIS.md`: zero riferimenti). Nessun provider emette un credito standard di 250 €.

| Se il credito è… | Cosa cambia | Uso sensato |
|---|---|---|
| **Fly.io** | Probabile che venga consumato sulla prossima fattura (la meccanica dei crediti prepagati Fly non è documentata nel repo: da confermare in console). Prepagherebbe ~2,49 mesi a listino Ott-2026 ($112,63/mese, sin ×1,269) o ~3,4 mesi al misurato $82 (`research/operations/2026-09-10-fly-cost-review-personal-org.md:26-35`) | Finestra per eseguire i tagli già proposti (−$9,4…−22,7/mese); nessuna attività nuova |
| **Google Cloud** ($300/90 gg è il trial standard, non 250 €) | Spesa per token = "needs GO" (`FLEET_TOPOLOGY.json`, invariante). Il progetto GCP esistente condivide probabilmente il billing prepay del bot WA (deplezioni 4× in 6 settimane) — da confermare in console prima di appoggiarci qualunque cosa | Niente: lasciarlo scadere. Un bucket mirror su GCP è sconsigliato (vedi runner-up) |
| **VPS** (Vultr sgp $5/mese; Hetzner solo EU, CX23 5,99 €) | D6 respinge l'host sempre acceso (`docs/superpowers/specs/2026-04-24-air-retirement-cloud-offload-design.md:69`) | **Nessuna attività.** Una sentinella self-hosted "per 30 giorni" smette di essere fuori flotta il giorno 31 e riproduce esattamente gli argomenti di D6: richiederebbe una ri-ruling datata, e non è raccomandata |
| **Contanti** | Unica forma trattenibile | Riserva incidenti (un incidente reale costa 2–25 €, non 250), oppure Healthchecks Business $20/mese se servono più di 20 controlli |

Cambio: 1 € = 1,1206 $ (BCE 2026-10-09) → 250 € = 280,15 $.

## Stato di fatto misurato

| Area | Numero | Fonte |
|---|---|---|
| App Fly vive | 2 (nuzantara-rag, nuzantara-postgres); 7 macchine / 6 avviate; 77 GB volumi | `scripts/fly_cost_guard.py:60-67` |
| Spesa Fly | ~$82/mese misurata (prezzi 2026-09-10); ~$112,6/mese a listino Ott-2026 sin; +11–14 % da repricing, il resto è il moltiplicatore regionale 1,269 (forse preesistente) | cost-review `:26-35`; fly.io/pricing-update |
| Soglie del cost guard | sedute AL footprint; "mai alzarle senza decisione di costo del proprietario" | `.github/workflows/cron-fly-cost-alert.yml:24-37` |
| Decisioni Fly aperte | 7, ferme dal 2026-09-10 (3→2 nodi, 25→10 GB, drive 512 MB…) | cost-review `:237-245` |
| Postgres | 3 nodi × 2 GB; DB 3,37 GB, +0,4 GB/mese; audit trail 979 MB senza retention verificata | cost-review `:51-53` |
| Qdrant | Cloud GCP us-east4; 14 collezioni / 113.818 punti; la più grande (81.411) è quella da cui prod SERVE le ricerche (`collection_registry.py:40-49`) ed è esclusa dallo snapshot settimanale per un commento errato ("mirror abbandonato") | `docs/runbooks/qdrant-estate-reconciliation.md:3-5`; `scripts/qdrant-snapshot.sh:116-120` |
| Pro | load 14,93 / RAM 47/48 GB (2026-05-10); disco 82→46→13 GiB liberi in 48 h a ottobre; floor 90 GB deciso l'11 ottobre | mini-h24 spec `:42`; `docs/specs/localci-sovereign-2026-10-07.md:62`; `docs/specs/localci-host-floor-2026-10-11.md:5-11` |
| Mini | 24 GB, load ~3,3 (2026-08-19); nessuna misura dopo l'arrivo del runner CI | `research/operations/2026-08-19-fleet-max-throughput-plan.md:29` |
| Organi su GitHub | 29 di 132 workflow schedulati; 9 solo-HTTP, 8 flyctl/Tigris, 12 muoiono col repo; destinazione decisa: Mini/Pro launchd o runner di zero | `docs/runbooks/zero-cutover.md:61` |
| Allarmi | token Telegram 401 dal 2026-09-22 al 10-06; 16/29 organi GHA e 12 plist Pro allertano solo lì; riga del board ancora `pending` (campo severità vuoto) | `docs/scars/cicatrix-scars.md:1831-1832`; `shared/escalations_pro.jsonl:81` |
| Sentinella incrociata | esiste già Mini↔Pro ogni 900 s, ma allerta solo via lo stesso bot e ha mancato un'interruzione Tailscale di 66 min (2026-08-26) | `scripts/fleet_watch.py`; PENDING-ARMS `:1489` |
| Restore drill | PASS 06-05, 07-01, 08-01 **solo a livello censimento con errori ignorati** (`ON_ERROR_STOP=0`, ~1.100 errori "ruolo inesistente" saltati, runner GitHub a 4 vCPU, l'ultimo PASS ha ripristinato un dump vecchio di ≥3 giorni senza accorgersene); ROSSO 09-01 e 10-01 da quando il drill è severo (#5261) per due ruoli DB mancanti nel target; alert del 10-01 perso nel 401. **RTO di livello 5 mai misurato, RPO mai provato** | `gh run list` 2026-10-12; `.github/workflows/restore-drill.yml` |
| Esposizione del drill GitHub, oggi | scarica il dump con dati cliente su un runner Microsoft (Azure) e stampa `tail -25` del log di restore nel job log del repo pubblico; sotto `ON_ERROR_STOP=1` la riga COPY che abortisce può contenere una riga cliente. I segreti Tigris risultano presenti (le run di agosto–ottobre hanno scaricato il dump), il commento "assenti" nel workflow è stale | `.github/workflows/restore-drill.yml:191-205`, `:110` |
| SLO backup | RTO "Untested" per Postgres e Qdrant (doc del 2026-04-06) | `docs/SLO.md:31-32` |
| 3-2-1 | Tigris nello stesso account Fly (gap "Medium"); nessuna cifratura client-side; raccomandazione P0 = copia su secondo provider | B7 `:152`, `:171` |
| Dump locali | 7 giorni di dump in chiaro sotto `~/backups/fly-postgres` sul Pro con permessi di default: nessun `umask`/`chmod` in nessuno dei tre script produttori | `scripts/fly-pg-backup.sh`, `scripts/fly-qdrant-backup.sh`, `infra/scripts/fly-backup.sh` (grep vuoto) |
| AUTONOMOUS_OPS | LAPSED: certificato 2026-09-01, 41 gg > 30 → modalità conservativa | `scripts/check_autonomous_ops_staleness.py` |

## Igiene a 0 € (prima di qualunque spesa)

Cinque azioni che le lenti hanno classificato sopra qualunque spesa; ognuna è una PR piccola con il suo consumatore.

| # | Azione | Dove | Consumatore e prova |
|---|---|---|---|
| 1 | **Disattivare il drill mensile su GitHub oggi** (`gh workflow disable 'Monthly PG Restore Drill'`); nella PR di riparazione, stderr di `psql` solo in un file 0600 sull'host che guida il restore, mai nel log del job | `.github/workflows/restore-drill.yml:191-205` | `gh workflow list` legge `disabled_manually`; il prossimo 1° del mese non esiste una run |
| 2 | **Togliere `legal_unified_hybrid_hybrid` dalla skip-list** dello snapshot settimanale e correggere il commento (è la collezione che serve prod, non un mirror abbandonato); aggiungere `--max-time` alle `curl` del backup notturno Qdrant (`:107`, `:126`, oggi senza timeout) | `scripts/qdrant-snapshot.sh:116-120`; `apps/backend-rag/backend/core/collection_registry.py:40-49`; `scripts/fly-qdrant-backup.sh` | `aws s3 ls s3://nuzantara-backups/qdrant/` elenca una copia datata della collezione da 81k punti |
| 3 | **`umask 077` / `chmod 600` sui dump locali** nei tre produttori; estendere `scripts/secrets_permissions_audit.py` a quel percorso | `scripts/fly-pg-backup.sh`, `scripts/fly-qdrant-backup.sh`, `infra/scripts/fly-backup.sh` | `ls -l ~/backups/fly-postgres` mostra 0600; l'audit permessi è verde |
| 4 | **Collegare `record_qdrant_search_latency`** (definita, zero chiamanti) nel percorso di ricerca, e prima di qualunque discorso sulla latenza leggere `/health/metrics/qdrant` sul processo `rag` (quello che fa le ricerche; sull'`api` leggerà 0) | `apps/backend-rag/backend/app/metrics.py:1528` | `search_calls > 0` letto dalla macchina `rag` via 6PN |
| 5 | **Riconciliare il board e l'inventario**: la riga `telegram_bot_token_dead` è ancora `pending` mentre W141 dice token tornato il 10-06; i cinque file che ancora dichiarano 3 app Fly o `nuzantara-qdrant` come macchina Fly con azione di recupero `fly_machines_start` (una trappola per il healer) | `shared/escalations_pro.jsonl:81`; `.claude/rules/infrastructure.md:14`; `VADEMECUM.md:288`; `README.md:95-97`; `scripts/cron-agent-python/fly_watcher.py:45`; `apps/organism/organism/organs_registry.yaml:27-36` | il hook di SessionStart non rialza la riga; il registro organi non ha più azioni di recupero su app ritirate |

## Classifica dei candidati

Valore residuo per lente su scala 0–5 (dai verdetti); **Voto = media delle tre lenti su 5**, un decimale, così la classifica è ricontrollabile.

| Candidato | €/mese · mesi coperti | Dolore misurato | Gov. | Fatt. | Val. | Voto | Rilievo decisivo |
|---|---|---|---|---|---|---|---|
| **Sentinella fuori flotta + secondo canale** | 0 € (free) · ∞; 20 $/mese · 14 mesi | Canale unico morto 14 gg; sentinelle che guardano se stesse | 4 | 4 | 3 | **3,7** | Falso che "nessun cron nuovo": il ricevitore gratuito non fa probe HTTP; lista controlli = 26 su 20; il canale e-mail proposto violava la regola fissa sull'invio e-mail (`docs/rules/operations.md:181`) e usava una credenziale di staff |
| **Restore drill con RTO misurato** | 0 € su Mini; 0,2 € one-shot su Fly | RTO di livello 5 mai misurato; drill rosso | 4 | 4 | 3 | **3,7** | Premessa imprecisa ("mai passato": 3 PASS a livello censimento con errori ignorati); causa del rosso nota; Zero ha già deciso Mini (`PENDING-ARMS.md:2662`); le forme Fly invertono la ruling |
| **Rightsize Fly post-repricing** | 0 € + ~4–8 $ one-shot; risparmio −10,56 $/mese | Bolletta non osservata | 4 | 4 | 2 | **3,3** | Il "launchd da tenere" non esiste (solo una copia legacy HOME-only che stampa "within budget" senza API di billing); il taglio volumi aspetta un drill che è rosso |
| **Replica Qdrant in sin + tooling restore** | 15,7–30 €/mese · 8–16 mesi | Nessuno misurato (zero incidenti Qdrant negli scar) | 3 | 4 | 3 | **3,3** | La latenza è già strumentata in prod (`/health/metrics/qdrant`); l'harness di qualità è uno stub offline; app nuovo sotto soglie al footprint |
| **Mirror backup su secondo provider** | ~1 $/mese · "20 anni" | 3-2-1 non rispettato (mai materializzato in un incidente) | 4 | 3 | 2 | **3,0** | Cifratura rompe i drill esistenti; account "write-only" non può listare; progetto GCP = probabilmente lo stesso billing prepay del bot; R2 gratuito già disponibile |
| **Riserva + misure gratuite** | 0 € | — | 3 (non confutato) | 3 | 2 | **2,7** | Riserva non trattenibile in 3 casi su 4; la misura del cold start è sul processo "light" (non la catena di import W60); prova finale tautologica |
| **App Fly `nuzantara-cron` per i 29 organi** | ~4,3 €/mese · 58 mesi | Pro saturo (dati di maggio) | 3 | 2 | 2 | **2,3** | Vuole impacchettare `scripts/cron-agent-python/` che è codice CLI-OAuth (D4 lo vieta in cloud); D3 era per altri job; sempre acceso = la forma che D6 ha respinto |
| **Staging Fly a digest esatto** | 12–31 €/mese · 8–19 mesi | Nessuno (commento stale in fly.toml) | 2 | 2 | 2 | **2,0** | Cold start già misurato (2 m 30 s, cost-review `:180`); il consumatore "Autonomous Lab" non legge URL; un path di deploy duplicato già morto |

## Raccomandazione #1: sentinella fuori flotta + secondo canale (forma corretta)

**Principio.** Il ricevitore misura solo il silenzio e non guarisce nulla; il secondo canale non tocca mai il token del bot di flotta; tutto il resto resta sui Mac.

**Decisione preliminare per Zero (due righe, X2 `:183`: "Law 6 permits either").**

| Forma | Cosa copre | Cosa non copre | Terzi | Costo |
|---|---|---|---|---|
| **A — solo in-flotta** | `fleet_watch` Mini↔Pro già attivo (900 s) + secondo bot + ping di esito dai produttori verso il healer | il caso "entrambi i Mac spenti o sede senza rete" — mai registrato negli scar (grep vuoto) | nessuno | 0 € |
| **B — A + ricevitore esterno gratuito** | anche il caso "entrambi spenti"; una vista indipendente da Fly e dai Mac | — | un terzo vede nomi dei controlli e orari dei ping, nessun dato | 0 €; 20 $/mese oltre 20 controlli |

Il valore marginale di B rispetto ad A è un'assicurazione su un guasto mai osservato; va detto così. In entrambe le forme la cura del dolore misurato (canale unico) è il **secondo bot**.

**Passo 0 — precondizione a 0 €, già decisa da Zero l'11 ottobre (`PENDING-ARMS.md:2662`: "restore-drill becomes a Mini launchd job (fixed first)"; la copia GitHub va disattivata PRIMA che parta il gemello).** Tre PR, una per concern (`docs/rules/operations.md:22`):

- **PR-A — riparare il drill esistente.** Preambolo che crea i due ruoli DB NOLOGIN mancanti prima di `psql -v ON_ERROR_STOP=1` (la causa dei rossi del 09-01 e 10-01); asserzione che il dump più recente abbia ≤26 ore (oggi non esiste: il PASS del 08-01 ha ripristinato un dump di tre giorni, quindi RPO mai provato — stesso criterio di `apps/cell/cell/sensors/backup_sensor.py`); stderr di `psql` in file 0600, mai `tail` nel log. Il workflow resta disattivato: l'unica run di prova su GitHub si fa solo se Zero la chiede esplicitamente e solo dopo che la stampa del log è sparita.
- **PR-B — porting su Mini.** Sequenza del workflow (immagine PostGIS 17-3.5, verifica di livello 5 con `scripts/ci/restore_drill_verify.py`) in un job launchd su Mini; `scripts/pg-restore-drill.sh` riallineato (oggi usa `postgres:17` senza PostGIS e `ON_ERROR_STOP=0`, la forma silenziosa); DB del drill legato a `127.0.0.1` con password non di default (`scripts/pg-restore-drill.sh:49-50,109` oggi pubblica `drill/drill` su tutte le interfacce, accanto al runner CI); dump e container rimossi a fine run.
- **PR-C — il numero.** Il RTO misurato sostituisce "Untested" in `docs/SLO.md:31`, con host, data e livello di verifica; Qdrant resta "Untested" finché non esiste un tooling di restore (oggi: zero).

Prerequisiti operatore per PR-B, da registrare come righe: raggiungibilità di Docker da un job launchd su Mini (il runner CI vive in una VM Colima "LAN/tailnet bloccati" su Mini, `docs/runbooks/zero-cutover.md:14`, ma `docs/AUTOMATIONS_REFERENCE.md:331` elenca Colima solo sotto Pro — potrebbe servire un secondo profilo); PostGIS su Mini se Docker non è disponibile; credenziali Tigris di sola lettura su Mini (`${AWS_ACCESS_KEY_ID:+SET}`, operator[credential]); una lettura di carico e disco di Mini (nessuna dopo il 2026-08-19); conferma che Mini è la corsia autorizzata per un dump con dati cliente (operator[business]).

**Passo 1 — secondo canale nel gateway (0 €).** `scripts/tg_notify.py` invia su un **secondo bot** (bot nuovo creato a BotFather, non un token riemesso dello stesso bot) quando una send risponde 401, un P0 finisce in `p0_unsent`, o una riga HIGH entra in `shared/escalations_pro.jsonl`. Custodia del token: variabile d'ambiente separata, in `~/.nuzantara-secrets.env` con permessi 0600 su ogni host, mai nel repo pubblico. E-mail: solo la consegna nativa del ricevitore verso la casella del proprietario (forma B) — nessun SMTP con credenziali di staff, nessuna eccezione alla regola fissa sull'invio e-mail senza riga datata di Zero. Dopo ogni test con token sovrascritto, azzeramento della scala dedup (`PENDING-ARMS.md:2421`).

**Passo 2 — ricevitore gratuito (solo forma B).** 20 controlli al massimo, lista pubblicata nella PR: fleet_watch ×2, ricevuta off-site pg, backup Qdrant, healer ×2, digest flush ×2 (così un 401 diventa silenzio), merger LocalCI, zero_sync, sentinel-meta-watchdog, cost-breaker-deadman, WAL probe, disk floor, visa-freshness, voa_deadman, reg-alert, drill su Mini. Helper `scripts/hc_ping.sh` che non blocca mai l'organo (timeout 3 s, nessun retry, lanciato in background, interruttore via variabile d'ambiente) — mai dentro `scripts/lib/heartbeat.sh` in modo bloccante (Legge 6: offline è lo stato naturale). Riga esplicita nei produttori (`scripts/fly-pg-backup.sh` dopo la ricevuta, `scripts/fly-qdrant-backup.sh`, `infra/healer/healer-run.sh`, wrapper del digest flush) **e** nelle copie `~/scripts` sul Pro (`scripts/lint_home_fork.py` verde fa parte della prova). Chiave di ping in `~/.nuzantara-secrets.env` 0600, mai negli argomenti di riga di comando. Stato `disabled` → pausa, non DOWN (`scripts/healer_receptor_registry.py:55` lo tratta già come esente). Nessun probe HTTP nella forma hosted (il ricevitore non ne fa); il controllo `getMe` del token vive nel wrapper del digest flush.

**Passo 3 — il healer legge in uscita.** Il tick del healer interroga l'API del ricevitore con una chiave di sola lettura (operator[credential]); nessun webhook in ingresso sui Mac.

**Consumatori.** I produttori che pingano, il ricettore del healer, la chat del secondo bot e la casella di Zero.

**Bites.** (1) Il ricevitore elenca i ≤20 controlli in stato up con ultimo ping sotto il periodo, letto il giorno in cui le righe atterrano in canone e in HOME; (2) prova negativa su un **organo canarino dedicato** (mai il merger, mai il backup notturno): stop → DOWN sul secondo bot e, in forma B, sull'e-mail nativa o Pushover del ricevitore (le integrazioni Telegram del tier gratuito non sono verificate: pagine 404 al fetch) entro periodo+grace, latenza scritta nel runbook, UP alla ripartenza; (3) una sola chiamata manuale a `tg_notify` sul canarino con il token sovrascritto via variabile d'ambiente (mai editando il file dei segreti) → il secondo canale consegna; subito dopo reset della scala dedup; (4) giorno 30: tabella silenzi colti / pagine false / pagine perse.

**Kill date.** 30 giorni, poi Zero sceglie: gratis, Business (20 $/mese, 100 controlli), kill.

**Autorizzazioni.** Pannello cross-family prima dell'approvazione (`docs/rules/operations.md:159`: obbligatorio per uno spec architetturale — nuovo provider, modifica del gateway, nuovo ricettore del healer); scelta tra forma A e B; nuovo provider esterno anche se gratuito (`AUTONOMOUS_OPS.md:65`, contratto scaduto → ogni passo è proposta); secondo bot (operator[gui]/[secret]); chiave API del ricevitore su Mini/Pro (operator[credential]); tier Business (operator[business]); nessun VPS senza ri-ruling di D6; nessuna variazione dell'inventario Fly, soglie intatte.

**Rischi.** Lo spool P0 sul Pro ha già perso allarmi per disco pieno su `~/.organism/tg` (riga del board del 2026-09-26, `shared/escalations_pro.jsonl:76`): il secondo canale non cura un disco pieno, il floor 90 GB sì. Un Mac deliberatamente offline legge DOWN: serve la pausa manutenzione a un comando, visibile anche al healer.

**Uscita a credito finito.** Nulla di ricorrente dipende dal credito; nel peggior caso 20 $/mese su carta o downgrade a gratuito.

## Runner-up e combinazioni

- **Credito Fly.** Non si divide: molto probabilmente viene consumato. La combinazione giusta è #1 (0 €) + igiene Fly a 0 €: un solo attore del cost guard su Mini (richiede `flyctl` e un token Fly di sola lettura collocato da Zero, 0600 — operator[credential]), con lo stimatore in dollari (listino Ott-2026) come **passo fratello** che legge l'output di `--dump-inventory` (il guard non può chiamare altri programmi, `scripts/fly_cost_guard.py:38-42`) e consegna Telegram giudicata; ritiro dei tre attori legacy — `~/scripts/fly-cost-alert.sh` via `com.balizero.fly-cost-alert.weekly` e via cron Pro `fly_cost_alert`, che stampano "Cost within budget" senza alcuna API di billing — e del cron GitHub solo dopo la prova viva; soglie **abbassate** solo dopo i tagli, con fixture ricatturata dal vivo e test ri-pinnati. Il taglio volumi 25→10 GB solo dopo il PASS del drill (ordine W106) e dopo la verifica che la retention dell'audit trail giri davvero in prod.
- **Contanti.** 0 € a #1; 0,2 € opzionali per un timing one-shot del restore in sin; il resto in riserva (incidenti reali costano 2–25 €, non 250).
- **Drill + sentinella** condividono per costruzione: la ricevuta del drill è un controllo; l'alert del 10-01 si perse proprio perché c'era un solo canale.
- **Mirror su secondo provider: nessun mirror finché i dump non sono cifrati.** Oggi i dump escono dal produttore in chiaro e contengono dati cliente: copiarli su un secondo provider, anche su un bucket gratuito dell'account Cloudflare già esistente, sarebbe l'esportazione in chiaro di uno snapshot prod verso un terzo che `SYMBIOSIS.md:181` e `:246` vietano anche in fase DEV, e che coincide con la voce 9 di "Cosa NON fare". Condizioni, nell'ordine: (1) cifratura `age` al produttore in `scripts/fly-pg-backup.sh`, con custodia della chiave come riga operator[secret] (X2 `:184`: custodia ancora APERTA, nessuna decisione da citare); (2) entrambi i drill riallineati a decifrare solo su Pro/Mini (oggi selezionano `\.sql\.gz$` e andrebbero a vuoto alla prima notte cifrata); (3) riga processore attestata da Zero nel DPIA (`docs/audits/2026-08-20-visa-oracle-dpia-v2.md:195`: base del trasferimento "OPEN — Zero"; la riga Tigris dice "Encrypted backups" senza che esista cifratura client-side) e nella tabella PSE (`docs/ops/pse-registration-balizero.md:92-97`, dove Tigris non compare e Cloudflare è processore solo per il Tunnel). Solo dopo: bucket R2 (10 GB gratis, blocco di retention), copia da Mini via `aws s3 sync`, solo prefisso Postgres, dopo il PASS del drill — non Cloud Run, non GCP.

## Cosa NON fare con 250 €

1. Nessun seggio per token verso endpoint Anthropic (SDK, chiave, Bedrock/Vertex): bannato come entità (`CLAUDE.md` §3, `RULINGS.md:145`).
2. Nessuna ricarica del seggio metered del bot WA da un credito GCP: "per-token-like, needs GO" (`FLEET_TOPOLOGY.json`), e la bolletta continua dopo il credito.
3. Nessun box GPU/inferenza in cloud per intake, OCR, documenti: "PII lanes = local models only. No cloud fallback ever".
4. Nessun VPS sempre acceso per i 29 organi: D6 in vigore; gate 7b nomina solo Mini/Pro launchd o il runner di zero.
5. Nessun nuovo app Fly "perché paga il credito": soglie al footprint, `fly.toml` off-limits (`RULINGS.md:193`), contratto scaduto.
6. Nessun 4° nodo Postgres o CPU performance: la CPU strozzata del primario si cura con la migrazione 308 già su disco (cost-review `:106-142`).
7. Nessuno spostamento di Qdrant senza modifica della policy pubblicata ("Qdrant Cloud, US", `docs/ops/pse-registration-balizero.md:95`).
8. Nessun workflow schedulato nuovo su GitHub: "locale decide, GitHub solo storage" (RULED 2026-10-07).
9. Nessun dump prod in chiaro su un secondo provider: `SYMBIOSIS.md:181` e `:246` vietano "il dato sta già lì" come giustificazione.
10. Nessuna dashboard (Grafana Cloud, Betterstack): il dolore è la consegna, non i grafici.

## Incertezze residue

- Provider ed eventuale scadenza del credito: non risulta nel repo.
- Meccanica dei crediti prepagati Fly (consumati sulla prossima fattura?): non documentata nel repo, da confermare in console.
- Fattura Fly reale: nessuna API di billing; se il moltiplicatore sin 1,269 fosse già in vigore prima del 1° ottobre, il salto vero è ~+13 %, non +37 %; ottobre leggibile solo a mese chiuso. L'URL del Cost Explorer nomina l'org `bali-zero`, la review dice `personal`.
- Progetto e billing account GCP: l'appartenenza del progetto esistente al billing prepay del bot WA è probabile ma non verificata dal vivo.
- Piano e prezzo di Qdrant Cloud: non registrati; 16,45 GB di snapshot server-side (2026-06-21) fanno pensare a un tier a pagamento.
- Esistenza di una copia off-site valida della collezione più grande: solo un listing Tigris lo dice.
- Integrazioni Telegram/ntfy sul tier gratuito del ricevitore: pagine non raggiungibili (404) al fetch; e-mail nativa e Pushover risultano dalla pagina notifiche.
- Se la copia HOME di `fly-pg-backup.sh` su Pro contenga già lo sweep automatico (#6045): non verificabile da qui.
- Raggiungibilità di Docker e presenza di PostGIS/credenziali Tigris su Mini: non documentate.
- Carico attuale di Pro e Mini: nessuna lettura dopo luglio/agosto.
- Se il token del bot sia stato ruotato anche sul segreto GitHub e sull'app Fly il 2026-10-06; la riga del board resta `pending`.
- Se la retention dell'audit trail giri in prod (un DELETE senza VACUUM non libera disco).
- Lo spool Telegram sul Pro può perdere P0 se il disco si riempie di nuovo (riga del 2026-09-26).
- Clone shallow (50 commit): la storia prima del 2026-10-11 non è ispezionabile.

**La domanda per Zero:** chi ha emesso questi 250 € e quando scadono? Se è Fly, la risposta è "lasciali consumare e usa la finestra per i tagli"; se è un trial a scadenza, la risposta è "non costruirci nulla"; se è contante, "riserva + sentinella gratuita". In ogni caso, oggi: drill GitHub disattivato e le cinque voci di igiene a 0 €.

## Adversarial review (generator ≠ grader)

- **Metodo.** 7 lettori paralleli (estate Fly, organi schedulati, data plane, pressione host locali, osservabilità, governance, prezzi di mercato) → 5 proponenti con lenti diverse (continuità, migrazione, capacità, efficienza, contrarian) → 15 proposte fuse in 8 candidati → **3 refutatori indipendenti per candidato** (governance, fattibilità/verità, valore), ciascuno con lettura del repo → sintesi → critico di completezza (12 lacune, 3 major, corrette in un giro di patch). 40 agenti, 0 errori, 2026-10-12.
- **Perché `exempt-`.** Tutti i seggi sono della stessa famiglia (Claude, via Workflow in una sessione cloud): nessuna CLI codex/kimi/gemini/qwen/glm nel container, quindi la review cross-family richiesta da R1 non era eseguibile. **Dovuta:** una passata codex o kimi sulla Raccomandazione #1 e sulle cinque voci di igiene prima di qualunque PR di implementazione.
- **Verifiche dal vivo del conduttore (2026-10-12), fuori dal workflow.** Storico run del drill su GitHub via API: success 06-05 (dispatch), 07-01, 08-01; failure 09-01, 10-01. `fly.io/pricing-update` dichiara "Effective October 1, 2026" e `fly.io/pricing.md` riporta il moltiplicatore sin 1,269. Healthchecks.io: tier gratuito a 20 controlli confermato solo da listini di terze parti (pagina ufficiale non letta). Righe del repo rilette: `.github/workflows/restore-drill.yml:192-205`, `research/operations/2026-09-10-fly-cost-review-personal-org.md:26-35`, `shared/escalations_pro.jsonl:81`, `docs/runbooks/telegram-token-rotation.md:3`, `.claude/skills/modus/PENDING-ARMS.md:2662`, `scripts/qdrant-snapshot.sh:116-120`, `apps/backend-rag/backend/app/metrics.py:1528` (zero chiamanti), `docs/rules/operations.md:181`, `AUTONOMOUS_OPS.md:37`. Nel documento nessun nome di staff, nessun dato cliente, nessun segreto.
- **Non verificato dal conduttore.** Cambio BCE, listini Vultr/Hetzner/Qdrant Cloud, appartenenza del progetto GCP al billing del bot.
