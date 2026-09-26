---
date: 2026-06-13
domain: operations
client_case: none — internal organism audit
sources:
  - 6 parallel subagent sweeps (nervous-system, arteries, launchd-fleet, immune-system, scars-taxonomy, brain-memory), all claims re-verified on disk by orchestrator per anti-hallucination discipline
  - live state: launchctl, ~/.agent/decisions/dlq.json, sentinel_status.json, ~/logs/*, fly status, deploy worktree git state
  - corpus: .claude/rules/cicatrix-scars.md + archive, MOS memory (6,424 entries)
author: Claude Fable 5 (autonomous background session, Pro)
---

# Il Connettoma di Nuzantara — TAC completa dell'organismo + Antibody Debt ledger

> Topic eseguito in autonomia su richiesta di Antonello ("un topic che solo tu puoi fare
> qualitativamente e profondamente"): tenere in un solo contesto l'intero organismo —
> sistema nervoso, arterie, fleet, sistema immunitario, cervello, corpus di cicatrici —
> e trasformare la diagnosi in terapia shippata. Snapshot: 2026-06-13 00:30-00:45 WITA.

## 0. Executive summary

L'organismo è **sostanzialmente sano** (89% job verdi, governance FASE-0 armata e fresca,
cascade LLM 4/4 verificata empiricamente per la prima volta, backend Fly senza split-brain,
parco NotebookLM eccellente). Le malattie reali sono **quattro**, tutte croniche e tutte già
"diagnosticate" in passato senza terapia:

1. **Il loop immunitario non chiude**: 31 job in DLQ TERMINAL, `healing_actions_24h=0`,
   sentinel cieco sullo stderr (W70 antibody #3 mai shippato). L'organismo cataloga le sue
   malattie ma non si cura — il **meta-pattern** è 8+ ANTIBODY proposti e mai shippati.
2. **Mini-Pro2 offline da ~1 giorno** → 4 daemon Pro in crash-loop (~2.750 run/giorno
   ciascuno) contro il Redis del Mini. Richiede azione fisica dell'operatore.
3. **Il repomap iniettava 188kB di chunk webpack minificati** in ogni sessione (aider sparito
   → ctags fallback silenzioso senza excludes `.next`). FIXATO in questa sessione (→40kB di
   firme sorgente reali, PR allegata).
4. **Recidiva W55**: il deploy worktree WR2 era dirty → deploy-pull bloccato → runtime 17
   commit stale, **con alert soppresso dal cooldown** (l'operatore non lo vede, di nuovo).
   RECUPERATO in questa sessione (procedura W50, hotfix verificato già in main).

**Meta-risultato sul metodo**: 2 dei 5 "malati" segnalati dai 6 subagent erano FALSI
(outbox-prune "mancante" ma vivo e funzionante; bridge HOME "in drift" ma byte-identico a
origin/main). La verifica su disco STADIO-0 li ha smascherati prima di costruirci sopra —
conferma sperimentale della cicatrice META-autopsy ("file:line dei report = lead, non fatti")
e della tesi verificatore-imperfetto del verdetto 9-spec.

## 1. Sistema nervoso — EventBus (PG LISTEN/NOTIFY + outbox)

- **27 canali** registrati in `PG_CHANNEL_MAP` (`apps/backend-rag/backend/services/events/event_bus.py`).
- Outbox **phase 1+2+3 sane**: trigger mig 146 scrivono `events_outbox` prima del NOTIFY,
  `_outbox_id` per idempotenza, replay on reconnect con TTL 60min, ack post-handler.
- **Prune VIVO** (falso-malato del subagent): `com.nuzantara.outbox-prune.daily` caricato,
  log `2026-06-11: deleted 2509 row(s)` — il subagent cercava in `infra/launchd/` invece di
  `infra/launchagents/`.
- **5 canali orfani** (producer senza consumer registrato — eventi scartati in silenzio):
  `war_room_event`, `cognitive_event`, `federation_alert`, `measurer_event` (consumer M14
  pianificato Sprint 2), `crm_welcome_completed`. Da decidere: consumer o de-registrazione.
- Redis streams: solo `llm:metrics` (producer attivo, consumer "future dashboard" mai nato).

## 2. Arterie — flussi dati end-to-end (stato empirico 00:30 WITA)

| Arteria | Stato | Evidenza / anello debole |
|---|---|---|
| WA intake → CRM | **VIVO** | 6 bridge stabili da 7h (W67 tiene); OCR gira SOLO sul fallback `qwen2.5vl` (primary `qwen3-vl` fallisce sempre, ~2min/pagina); damar `logged_out` attende QR (coerente standby 12/06) |
| Drive→CRM (#1364) | PENDING by design | watcher non armato, installazione prevista post-backfill ~14/06 |
| Dropbox→Drive | **VIVO** | rclone in copy ADESSO, batch 50% (10.082/20.094 file), ETA in corso |
| Intel → articles → mouth | **VIVO** | MDX 11/06, publish branch+PR funziona (fix #1202 tiene) |
| NLM feeders | **DEGRADATO** | `gap_scanner` MORTO da 9 giorni (age 218.9h); `nlm_feeder_stream` a digiuno (0/0/0); `matagaruda-bridge-err.log` 50MB in crescita |
| WR2 | VIVO/idle → **RECUPERATO** | renderer armato, coda vuota; deploy worktree era dirty+17 stale con alert soppresso (recidiva W55) — realineato alle 00:41 (sibling F03 + puller), verificato in §6 |
| Fly backend | **VIVO** | /health 200, api+rag entrambi started v3539, no split-brain |
| Telegram alerting | **DEGRADATO** | `wr2_supervisor_watchdog` → HTTP 400 ricorrente da 3 giorni (canale muto); transitori rete 12/06 risolti; token bot nei log = P0 noto audit 11/06, ancora da ruotare |

## 3. Fleet launchd (muscoli e cuore)

- 180 plist su disco, **173 caricati, 154 sani (89%)**, 7 disarmati intenzionali.
- **4 crash-loop vivi, UNA causa**: Mini-Pro2 offline dal tailnet (~1d) → `intel-dedup-gateway`,
  `meta-dispatcher`, `observatory`, `research-sentinel` muoiono ogni ~31s su
  `redis 100.93.236.6:6379` (824 run in 7h ciascuno). Fix = riaccendere il Mini, non toccare i daemon.
- Cronici minori: `codex-spark-alarm` (exit 1 ogni 2min), `wr2.plist-watchdog` (path drift
  `nuzantara-deploy/scripts/wr2_plist_watchdog.sh` assente — famiglia W50), `wr2.sla-worker` /
  `hardening` / `measurer` (env/secret mancanti), `intel-radar-daily-digest` (manca `structlog`).
- `daily-indexing-sweep` (il 10.7k run/day del guardian-of-guardians 11/06) oggi runs=0: non più in loop.
- Governance FASE-0: `verify_the_verifiers` 22/22 armed, `mcp_integrity` GREEN (12 reachable),
  `cost_breaker_deadman` ok — tutti freschi <10min.

## 4. Sistema immunitario

- **DLQ**: 33 job, 31 TERMINAL (28 degli ultimi 2-7 giorni: NON legacy), `healing_actions_24h=0`.
  vs W70 (39): −8, ma il loop di auto-heal resta MORTO.
- **Sentinel cieco** (la malattia load-bearing): `log_tail` distinct = `""`×17, `"exit 1"`×13 —
  zero stderr reale, classification UNKNOWN/0.0, autopilot retry alla cieca → TERMINAL.
  W70 antibody #3 (capture stderr in `sentinel_lib/repairer.py` / chiamanti) MAI shippato;
  `nuzantara-sentinel.py` fermo al 30 aprile.
- **CI: ottima** — W69 BUCO #1 CHIUSO: 18 required checks su main inclusi i P\*
  (verify-the-verifiers, mutation, hot-zone, asyncpg-lint, P3/P6, cost-breaker…), tutti verdi.
  Lint asyncpg exit 0 (regressione W64 sanata).
- **Bridge WhatsApp**: HOME ≡ origin/main (md5 `09ec1366…` identici) — NESSUN drift; il
  fix F11 LKPM è salvo in main (#1288). 10 `_guard_*` su entrambe le copie.
- Hooks: W71 gap #1 (seam_verify) CHIUSO; gap #2 ancora aperto (`guardrails-static.py` esiste
  ma non registrato in settings.json).

## 5. Cervello — memoria + arsenale LLM

- MOS: 482 file, MEMORY.md 19.9KB/109 righe (sotto soglia, margine 22%), FTS5 con 6.424 memorie.
- **Cascade 4/4 armata** (prima verifica empirica full-depth dall'audit 24/05 che la trovò 2-deep):
  claude v2.1.175 ✅ · agy v1.0.7 ✅ (CLAUDE.md dice 1.0.2, da aggiornare) · codex v0.135
  ping→pong exit 0 ✅ (no 401) · ollama 6 modelli con `qwen2.5vl:7b` presente ✅
  (assenti vs lista CLAUDE.md: deepseek-r1:32b, gemma4:26b, qwen3:8b, nomic-embed-text).
- NotebookLM: 86 NB / 3.769 src, 0 broken 0 stale. **2 scadenze**: feeder Immigration/
  Regulation/Tax PAUSED → stale-alarm il **22/06**; 24 proposal pending da 12 giorni.
- **Repomap: era l'organo marcio** — fixato in questa sessione (vedi commit nel PR):
  188kB di webpack chunks → 40kB di firme sorgente, degradazione aider ora loggata.

## 6. Interventi eseguiti in questa sessione (terapia, non solo diagnosi)

1. **fix(repomap)** `scripts/build_repomap.sh`: excludes `.next/.turbo/.vercel/coverage/
   *.min.js` + esclusione test + cap 100 file/15 simboli + log della degradazione aider.
   Verifica empirica: 0 hit rumore, 40kB/390 righe. (PR di questa branch.)
2. **Recovery deploy worktree WR2 — verificata (eseguita da sessione sibling F03)**: questa
   sessione ha diagnosticato il blocco (dirty `wr2_html_render_apply.py` + 17 commit stale +
   alert soppresso) e verificato che l'hotfix `_ensure_live` era già in origin/main (4 hit).
   Alle 00:41 una sessione parallela "F03" è arrivata alla stessa conclusione e ha eseguito
   stash (`wr2-ensure-live-already-on-main-f03-2026-06-13`) + il puller ha fatto ff
   `7f1de1588→02180cdab`. Verifica indipendente post-recovery: status clean, HEAD ==
   origin/main, puller `OK` ×2, `_ensure_live` presente. Criterio (b) soddisfatto.
3. Questo report (capture della TAC + ledger).

## 7. Antibody Debt ledger — proposti e mai shippati (il vero topic)

| # | Antibody dormiente | Cicatrice | Età | Costo stimato | Note |
|---|---|---|---|---|---|
| 1 | **Sentinel stderr capture** in DLQ `log_tail` | W70 #3 | 4g | S (1 file HOME `sentinel_lib/repairer.py` + chiamante) | Sblocca l'INTERO loop auto-heal: con stderr reale la classification smette di essere UNKNOWN/0.0 |
| 2 | Cleanup cron worktree broker (`agent_start.py --cleanup` schedulato) | W62 | 16g | S (1 plist + smart-skip WIP) | `com.nuzantara.agent-worktree-cleanup.daily` ESISTE ma exit 1 su WIP — da rendere non-fail |
| 3 | Leader-election / dedup 13 label active-active Pro+Mini | W67c / 2026-05-07 | 37g | M | Mini ora offline = momento ideale per decidere il default Pro-only |
| 4 | `lint_launchagents.sh` + plist validator in CI | P0-3 / 2026-04-29 | 45g | M | 19 job falliti odierni sarebbero stati visti prima |
| 5 | Test parity manifest-vs-registration + endpoints-reachable | PR #422 / 2026-05-02 | 42g | S | 2 file di test proposti, mai scritti |
| 6 | Rotation secrets (backend_rag_v2 + BRIDGE_SKILLS_API_KEY + token Telegram nei log WR2) | P0 06/03, W65, audit 11/06 | 10g+ | M | DECISIONE OPERATORE — non autonoma per design |
| 7 | Consumer (o de-registrazione) dei 5 canali EventBus orfani | questa TAC | 0g | M | `war_room_event`, `cognitive_event`, `federation_alert`, `measurer_event`, `crm_welcome_completed` |
| 8 | Weekly digest "alert soppressi dal cooldown" via Telegram | W55→W50→oggi (3ª recidiva) | 19g | S | Il cooldown ha nascosto di nuovo un ERROR per giorni: il pattern è provato recidivo |
| 9 | Fix `wr2_supervisor_watchdog` Telegram HTTP 400 | questa TAC | 3g | S | Canale d'allarme WR2 muto da 3 giorni |
| 10 | OCR primary `qwen3-vl` morto → o fix o promozione ufficiale del fallback | intake catalog v2 | 1g+ | M | Throughput intake dimezzato |

**Raccomandazione di sequenza** (rischio × leva): #1 sentinel stderr (sblocca tutto il
healing), #8 digest soppressioni (3ª recidiva dello stesso buco di visibilità), #9 watchdog
400, poi #2/#5 (piccoli), #3/#7 (decisioni di design), #6 (solo operatore).

## 8. Azioni SOLO-OPERATORE (non eseguibili in autonomia)

1. **Riaccendere/riconnettere Mini-Pro2** (offline tailnet ~1d) — spegne 4 crash-loop da soli.
2. **QR re-link** damar (se esce dallo standby) — sahira già gestita.
3. **Riavviare i feeder NB** Immigration/Regulation/Tax su Mini **entro il 22/06** (stale-alarm).
4. **Review delle 24 proposal NB** pending da 12 giorni (13 YouTube-dup, 13 garbage pages).
5. **Rotation secrets** (ledger #6) — già pending decisione da W38/P0.
6. **`git pull` del checkout Pro** (131 commit dietro origin/main) — sessione interattiva.
7. Decidere se **reinstallare aider** (pyenv 3.11.11) per riavere la strategia tree-sitter
   del repomap, o consacrare il ctags-fallback fixato come strategia primaria.
