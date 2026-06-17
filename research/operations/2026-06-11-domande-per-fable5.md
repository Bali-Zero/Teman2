---
date: 2026-06-11
domain: compliance
client_case: internal — domande dirette per Fable 5 (deep-reasoning) su sistema Nuzantara
sources:
  - "fan-out 5 esploratori read-only su disco, 2026-06-11 (Pro nuzantara@Nuzantara)"
  - "ogni tensione grounded su file letto/comando eseguito in sessione"
  - ".claude/rules/cicatrix-scars.md (famiglie W34-W73)"
  - "guardian-of-guardians audit 2026-06-11-guardian-of-guardians.md"
---

# 60 domande dirette per Fable 5 — sistema Nuzantara/Bali Zero

> **Come usare questo file**: ogni domanda è già grounded (con il `file:linea` o il comando dove serve), così Fable 5 può andarci diretto senza ri-esplorare. Sono domande per **risolvere, semplificare o illuminare** — non checklist di compliance. Ordinate per dominio; in fondo le 5 "se potessi farne solo 5" e il filo rosso trasversale.
>
> Metodo: nate da un fan-out di 5 esploratori read-only sul disco (2026-06-11). Ogni claim verificato in sessione — niente file:linea citato a memoria (trappola da cicatrice ℹ️META 2026-06-05).

---

## ⚙️ Aggiornamento post E1-E13 (2026-06-11 sera) — stato ri-verificato su disco

Il guardian-of-guardians audit (E1-E13 + PR #1287 merged) ha già toccato 7 di queste domande. Stato ri-letto in sessione:

| Q | Stato dopo i fix di oggi | Cosa resta |
|---|---|---|
| **#13/#57** (heal-loop cieco) | 🔴 **PEGGIORATO**: ora 29 terminal / `healing_24h=0` (era 16). Il prune F08 ha svuotato il DLQ e si è già ri-riempito a 29. | causa-radice (stderr-blind) **non toccata** — resta la #1 per leva |
| **#16** (2 W67 loop live) | 🟢 i 2 esempi live UCCISI/convertiti: `indexing-sweep.daily` rimosso (E1), `state-bridge` ora cron `runs=61` non-climbing (E7) | il lint daemon|cron XOR sui 52 plist ambigui resta |
| **#28** (leve env disarmabili) | 🟢 `AGENT_WORKTREE_ENFORCEMENT` ri-armato `true` (E2), `STOP_VERIFY_ALLOW_DIRTY` già rimosso | pattern 8-leve-senza-timebox resta |
| **#39** (cascade forkata 6×) | 🟢 il `set -e` trap di `regulatory-watcher-run.sh` fixato (E3, ora `set -uo`) | consolidazione 6→1 fork resta |
| **#50 / #52** (filo rosso: esiste-ma-non-armato) | 🟢 oggi armati: hot-zone CODEOWNERS (E4), `asyncpg-lint.yml` blocking (E8), 5 sentinel BUCO#1 p3/p6/p7/p8/p9 (E6) → **required checks 11→18** | i guardiani NON toccati (Law-5 lint #43, router-manifest #4, cascade health-ping #45) restano fail-silent |
| **#19** (worktree sprawl) | 🔴 **confermata/peggiorata**: ora 16 worktree / 17G (era 15/16G) | broker auto-cleanup ancora assente |
| **#5** (WR2 tre-render-path) | 🟢 **forma risolta**: cutover HTML fatto (PR #1236+F23), 1 path live (`html-apply`→`canva_renderer_v2`), Canva plist non-loaded | resta solo debito cancellazione (orchestrator dead + `canva_renderer` **v1** orfano + 2 plist) |
| **#1/#56** (W38 superuser) | ⚪ **invariata — P0 aperta** | i 2 ruoli app sono ancora `rolsuper=true` |

Le altre 53 domande restano com'erano. Annotazioni inline `[E#]` sotto dove un fix di oggi ha cambiato il fatto.

---

## 🔴 PRIORITÀ 0 — discrepanza security verificata oggi (non è una domanda: è un fatto da decidere)

**W38 NON è completa, contro quanto dice la memoria.** Lettura live di `pg_roles` in sessione: `backend_rag_v2`, `nuzantara_memory`, `zantara_rag_user` sono demoti ✓, ma **`nuzantara_rag` e `backend_ts_user` sono ancora `rolsuper=true`** — entrambi marcati "NO — app role" nello spec `research/operations/specs/W38-superuser-demotion-2026-06-03.md:15-18`. La memoria `audit_system_fable5` dice "W38 demotion FATTA": falso per 2 ruoli su 5. Lo Stage B (split `ADMIN_DATABASE_URL`/`DATABASE_URL`) è esplicitamente non implementato.

1. Si chiude W38 con `ALTER ROLE nuzantara_rag NOSUPERUSER` + `backend_ts_user NOSUPERUSER` (dopo grep-conferma che nessuno script runtime fa DDL come questi ruoli), e si shippa il split `ADMIN_DATABASE_URL` così l'app non si connette mai privilegiata?

---

## A — Architettura & organismo (legge-vs-codice, due-pipeline, organi)

2. La legge SYMBIOSIS dice 13 canali EventBus, il codice ne ha 17 (`event_bus.py:47`, 4 non documentati). Si genera l'inventario canali DA `PG_CHANNEL_MAP` nella legge (single-source) con una CI che fallisce quando `len(PG_CHANNEL_MAP)` ≠ il numero dichiarato — invece di mantenerlo a mano?

3. ~8 dei 17 canali PG sono LISTENed ma senza consumer in-process (`event_bus.py:84` dice letteralmente `# Consumers: TBD`). Per ciascuno: il consumer è (a) un daemon separato, (b) davvero TBD, (c) morto? Quali si possono togliere da `PG_CHANNEL_MAP` per smettere di pagare la durabilità a un vicolo cieco?

4. `VADEMECUM.md:106` dice "NON editare `router_registration.py` — legge il manifest automaticamente", ma `router_registration.py` ha 324 `include_router(...)` espliciti e **zero** iterazione del manifest. Il doc fabbrica esattamente il bug 404 che cita. Si rende la registrazione davvero manifest-driven (iterando `RouterEntry.process_groups`, cancellando ~953 righe di include a mano), o si corregge il doc in "edita ENTRAMBI"?

5. **[🟢 ri-verificato 2026-06-11 sera — la forma "scegliere fra path live" è RISOLTA dal cutover HTML (PR #1236 + F23): resta solo debito di cancellazione]** Il path render LIVE è ora **uno solo**: `com.balizero.wr2.html-apply` è loaded → `scripts/wr2_html_render_apply.py`, che **riusa `canva_renderer_v2`**. I plist Canva (`canva-apply`, `canva-renderer`) esistono su disco ma **non loaded**. `topic_ready` non è più in `PG_CHANNEL_MAP` (0 hit) → `wr2_carousel_orchestrator.py` è dead-code senza canale. Ma su disco restano **`canva_renderer` v1 E v2** (solo v2 ha importatori vivi), `wr2_carousel_orchestrator.py`, `wr2_canva_desktop_apply.py` e i 2 plist non-loaded. **Domanda riformulata**: il terminale (html-apply su canva_renderer_v2) è confermato — quale di {carousel_orchestrator, canva_renderer **v1**, canva_desktop_apply, 2 plist non-loaded} si cancella ORA, e perché esistono ancora DUE `canva_renderer` quando solo v2 è importato dal path live?

6. 107 dei 120 organi girano su un solo host (`pro_launchd`); se il Pro cade, l'89% dell'organismo si ferma. Quali dei 20 organi `critical` sono SPOF veri (consumer senza degradazione graceful)? Quali migrare su Mini/Fly per HA senza violare Law 2 (OSINT resta sul Pro)?

7. Due inventari organismo che non si parlano: `organs_registry.yaml` (120 organi, checksummato, CI-enforced) vs `automation_catalog.json` (17 entry), zero cross-link, e VADEMECUM §1.9 punta i contributor al più debole (17). Si deprecano/fondono in uno solo (o si auto-genera il catalog dal registry)?

8. La storia di durabilità dell'outbox si contraddice su 3 layer: la cicatrice dice "phase-3 pending", il docstring dice "as-shipped", e su disco esistono SIA `outbox-prune.daily` SIA `outbox-prune.weekly` (l'SLA di retention ri-deciso una volta e mai pulito). Il per-handler ack è ancora dovuto, o ci si è fermati deliberatamente a at-least-once + dedup (e allora si chiude la cicatrice)?

9. `cell-core` è il substrato genoma con 131 importatori, copiato in ogni worktree (`COPY` live dal repo root nel Dockerfile). Si rende un package versionato/pinnato (così i worktree referenziano una copia immutabile) invece di una `COPY` live? Qual è il gate di blast-radius per un cambio a cell-core che tocca 131 moduli?

10. Riferimenti all'Air (decommissionato 2026-05-05) vivono dentro le **leggi non-negoziabili** (`SYMBIOSIS.md:195` Law 6, `event_bus.py:11` docstring "Pro ↔ Air ↔ Fly"). Quali sono pura archeologia (da rimuovere) vs quali codificano un assunto 3-nodi ancora necessario (Redis cross-node) degradato silenziosamente a Pro↔Mini↔Fly?

---

## B — Flotta daemon & automazione (sprawl, HOME-fork, DLQ cieco, active-active)

11. **214 plist su disco, 179 nei 3 namespace, ma `organs_registry.yaml` ne copre 92: il 52% della flotta è invisibile al file che dovrebbe governarla.** Si può auto-derivare il registry DAI plist (reverse-index host/role/cadenza/runtime-home/intent) e renderlo una biiezione CI-enforced, così "on-disk ≠ registry" fa fallire la build?

12. Una sola feature (WR2) = **37 plist su 5 runtime-home diversi** (`.openclaw` 13, repo 11, `~/scripts` 7, deploy 5, skills 1). Qual è la consolidazione minima — tutti e 37 possono collassare in UN runtime root (deploy worktree) con un supervisor + sub-job? Quali dei 13 `.openclaw` hanno davvero bisogno del runtime OpenClaw?

12b. La copia HOME di `wr2-deploy-pull.sh` è driftata rispetto al gemello nel repo (lo script che GUARDA il deploy contro la drift è lui stesso driftato). **[⚠️ IMPRECISA — ri-verificata 2026-06-11 (Fable5/catB): NON "216 righe avanti".** `diff ~/scripts/wr2-deploy-pull.sh <repo copy>` → **171 righe differiscono**, ma la lunghezza differisce di sole **3 righe** (HOME=231, repo=228), md5 diversi. La HOME è in realtà la versione **più VECCHIA e verbosa** (header Sprint-C 2026-05-08, ~25 righe di commento-rationale + `git fetch origin main`), il repo è una riscrittura più snella con `SOURCE_REPO`/`EXPECTED_BRANCH` parametrici. Quindi la drift è **reale e sostanziale (171 righe di contenuto) ma la HOME non è "avanti": è la copia stale che il repo ha già superato.** Il rischio resta identico — il puller live gira la HOME stale.] `~/scripts/` diventa una symlink-farm nel repo (single source), o i plist puntano direttamente al path repo? Quali dei 74 script HOME-fork hanno divergiuto, e quali sono HOME-only (irrecuperabili)?

13. **[ri-verificato 2026-06-11 sera: 29 terminal, era 16 — PEGGIORATO]** L'autopilot di self-healing è strutturalmente **cieco e non ha guarito nulla**: `sentinel_status.json` = **29** terminal / `healing_actions_24h: 0`, e le 30 entry DLQ (`{"queue":[...]}`) hanno `log_tail == error_summary` (solo "exit 1") + classificazione `UNKNOWN/0.0` + `autopilot_attempts: 10`. Il prune F08 di oggi ha svuotato il backlog ma si è già ri-riempito → conferma che è un flusso, non un residuo. Dove nella catena del retry-wrapper si butta via lo stderr reale, e qual è il cambio minimo per infilare le ultime-N-righe vere in `log_tail`? Una volta che lo stderr vero scorre, un classificatore LLM può sostituire lo stub `UNKNOWN/0.0` e riarmare il loop?

14. **31 meta-monitor (17% della flotta), catena annidata 4-deep** (`sentinel`→`sentinel-meta-watchdog`→`sentinel-aggregate`→`supervisor-liveness-watchdog`), ma il top controlla solo la *freshness* del file-segnale, non il *lavoro* del bottom (riporta "ok/fresh" mentre sotto ci sono 16 morti + 0 heal). Quali dei 31 sono ridondanti, e la catena 4-deep può collassare in un sentinel il cui meta-check asserisce che `healing_actions_24h` si muove quando `circuit_terminal > 0`?

15. Il deploy worktree è uno SPOF di shared-state: 22 plist dipendono da esso, e un cron auto-evolvente (`agent-library-evolver`) ci fa `git checkout` sopra (la collisione che ruppe il puller per 32h). L'evolver prende il SUO worktree (l'Opzione A/B deferita), così non può mai fare checkout sotto i 22 dipendenti? Il pattern `deploy/main`-alias-locale-di-`origin/main` vale la pena di tenerlo?

16. **[🟢 E1/E7: i 2 loop live citati sono morti — `indexing-sweep.daily` rimosso, `state-bridge` ora cron 300s. Resta il lint sui 52]** **52 plist hanno SIA KeepAlive SIA uno schedule** — daemon-vs-cron è strutturalmente ambiguo, ed è la firma esatta del crash-loop W67 (`exec one-shot` sotto `KeepAlive=true` → SIGTERM ogni 22s). Si può lintare ogni plist a una classificazione stretta daemon|cron (KeepAlive XOR schedule) e flaggare i 52 ambigui, auto-rilevando `exec one-shot + KeepAlive=true` come errore hard?

17. Sub-flotta `codex-*` (9 job): accumula state-file per-giorno illimitati (17 file `codex_autofix_ci_count_<date>` mai prunati) e `zantara_vision_warmup` è in DLQ con exit 127 (binario mancante — classe Codex-OAuth-revoked / path-drift). I 9 sono ancora agganciati a un token Codex valido, e perché 127? Il pattern count-file giornaliero diventa un singolo file rolling?

18. Mini-Pro2 era irraggiungibile in sessione (Tailscale + mDNS giù), quindi l'active-active NON è confermabile — e quello È il rischio (W67c: Mini girava un wa-mirror orfano che spammava Telegram mentre il Pro sembrava pulito). Qual è un modo reachability-independent di rilevare la duplicazione Pro+Mini (es. tag `host_pro_or_mini` per-evento + dup-detector sulla PG condivisa), così l'audit non passa silenziosamente quando Mini è offline?

19. **[🔴 ri-verificato: ora 16 worktree / 17GB — cresce ancora]** **16 worktree / 17GB su disco** (W62 TTL-violation live e in crescita — era 6, poi 15, ora 16), `agent-worktree-cleanup.daily` esce 1 mentre si accumulano. Qual è la policy di auto-cleanup più piccola e sicura (la cicatrice nota che `--cleanup` non tocca i dirty, e molti sono pseudo-dirty da formatter) — pulire per mtime+branch-merged invece che per TTL?

---

## C — Orchestrazione agentica & auto-miglioramento (loop saturati, guardrail, broker)

20. **Il loop di self-improvement gira ma il suo eval è saturo**: il bug DeepSeek "" è fixato (`vendor/evoskill/src/cli/shared.py:206`), ma l'ultimo report mostra baseline accuracy = 100%, ogni iterazione +0.0%, 0 skill sopravvissute. Spende ~$0.055/settimana per scoprire che non può migliorare un dataset già al 100%. Il collo di bottiglia è la macchina o il **segnale obiettivo** a cui è puntata? Si ri-punta la curriculum EvoSkill su un segnale che fallisce (il ledger cicatrici / la famiglia `_guard_*` over-match) invece di un QA-set saturo?

21. Il LEARN harvester vede solo 12 scar su ~40 (`lesson_harvester.py:99` taglia a `\n## Archived`) e trova 0 ricorrenze ≥3× — ma le ricorrenze vere (HOME-fork W50/W51/W52, `_guard_*` W68/W72/W73, Air-path-drift) sono proprio nella parte che esclude. Si fa scansionare l'archivio + i cross-reference `Family:` (che già codificano la ricorrenza), e "≥3 occorrenze live" è la soglia sbagliata visto che le scar vengono archiviate *perché* sono ricorse?

22. Il layer guard WhatsApp è una catena hardcoded di 10 chiamate `_guard_*` (`openclaw_whatsapp_bridge.py:1413`), ognuna clobbera `response_text` in ordine fisso, ognuna tunata a mano — 4 sweep di cicatrici (W68/W72/W73×5) stessa classe. **I guard si spostano da "clobber la risposta" (sostituzione post-hoc) a "inietta ground-truth nel prompt" (grounding pre-hoc)**, così una risposta sbagliata è prevenuta non sovrascritta? O: le 10 funzioni ad-hoc diventano una tabella dichiarativa (trigger-intent / risk-intent / canonical) con un harness condiviso, così aggiungere un guard non può re-introdurre la trappola bare-substring?

23. Il broker forza worktree-per-sessione ma il momento dell'orfanizzazione (morte agente) non ha consumer sincrono — TTL è ancora advisory (`agent_start.py:638`, cleanup opt-in/cron). La dispatch dell'Agent-tool registra essa stessa un callback di teardown (l'ANTIBODY #4 W62 proposto-mai-costruito), così il release è accoppiato all'evento di spawn invece che a un cron giornaliero?

24. **La canary del meta-verifier è una tautologia**: `verify_the_verifiers.py:302` fa `if disarm in f"{disarm} python3 hook.py": return ARMED` — una stringa è sempre sottostringa di sé-stessa-più-suffisso. La canary passa per costruzione; non valida niente sul fatto che la leva di disarmo funzioni davvero. La canary dovrebbe settare l'env e ri-eseguire `check_claude_hook` con la disarm-substring iniettata, asserendo che flippa a DISARMED — una canary tautologica erode più fiducia (falso ARMED) che non averla?

25. WR2 (5 agenti) e WR3 (9 agenti) sono fan-out i cui prompt-orchestratore sono trattati ~400 righe che combattono l'istinto del modello a inlinare ("You produce decent carousels by writing the artifacts inline yourself. That is a bug" + self-audit che conta le chiamate Agent e aborta se <4). I contract (fan-out / NB-ground-truth / no-silent-reuse) possono essere enforcati da un harness deterministico (`_audit-checklist.sh`) che *gate-a la pipeline*, riducendo il prompt da 400 righe di coercizione a 40 di intento? Un fan-out 9-agenti è giustificato per un video da 60s, o è la complessità di WR2 copincollata prima che WR3 avesse evidenza di averne bisogno?

26. Il routing federation è 3-vie (keyword pre-filter + classificatore Qwen3.5:9b locale + merge dove **la keyword vince ogni disaccordo**, `federation_orchestrator.py:283`) e l'LLM può solo *aggiungere* dispatch, mai toglierne. Se le keyword vincono sempre e l'LLM può solo aggiungere, cosa compra la chiamata Qwen sopra la sola tabella keyword — e vale il timeout 120s + dipendenza Ollama sul path critico? Il classificatore dovrebbe poter *restringere* così il fan-out può davvero ridursi?

27. Il cost-breaker governa un **proxy USD**, non la quota flat che davvero vincola (la finestra rolling 5h di Claude MAX). Sul Pro non riesce nemmeno a leggere il ledger (è su Fly PG) → ogni provider UNKNOWN → fail-closed DEGRADE ogni tick. Il breaker dovrebbe osservare il segnale vincolante vero (esaurimento finestra-5h: grep `out of extra usage|429|exhausted`) invece di un proxy USD? Un breaker fail-closed che non legge il suo ledger sulla macchina dove gira aggiunge sicurezza o solo spam-DEGRADE?

28. **[🟢 E2: AGENT_WORKTREE_ENFORCEMENT ri-armato `true`, STOP_VERIFY_ALLOW_DIRTY già rimosso — 2 leve chiuse, pattern resta]** **Ogni leva di governance è disarmabile individualmente via env var** (≥8 `*_OFF=1`/`*_ENABLED=false`: STOP_VERIFY_ALLOW_DIRTY, AGENT_WORKTREE_ENFORCEMENT, ORCHESTRATE_GATE_OFF, GUARDRAILS_STATIC_OFF, …). Le leve di disarmo dovrebbero richiedere una ragione loggata e time-boxed (auto-riarmo dopo N ore) invece di un env-var appiccicoso? L'invariante giusto è "nessun gate disarmabile senza che il meta-verifier emetta RED entro un cron tick" — ed è garantito oggi su ogni macchina?

29. Tre subsistemi di self-improvement (EvoSkill, LEARN harvester, WR2 Reflexion — 7 mesi di `insufficient-data`, 0 graduation) **girano a schedule, costano quota, e producono zero cambiamento adottato**. Le macchine sono riparate; il gradiente che salgono è assente (eval saturo, slice sbagliato, no metriche IG). Il collo di bottiglia di TUTTO il layer di auto-miglioramento è la macchina o il segnale obiettivo? (ogni fix finora è stato alla macchina)

---

### 🔎 Re-grounding C (#20-#29) — Fable 5 audit, 2026-06-11 (disco ri-letto in sessione)

> Tutte le `file:linea` sotto sono ri-verificate **in questa sessione** su disco (non a memoria). Runtime reale dei loop di auto-miglioramento e del bridge = `~/Desktop/nuzantara-deploy/` (deploy worktree) e `~/.openclaw/bin/` (bridge HOME live), **non** il checkout repo — quindi i `file:linea` originali (presi sul checkout) erano stale di numero pur essendo veri di sostanza.

| Q | Verdetto | Evidenza (comando in sessione) | Correzione |
|---|---|---|---|
| **#20** | ANCORA-VALIDA | `Read .../agent-library/.evoskill/reports/run-2026-06-07-082825.md` | Ultimo report (07 giu): Baseline 100.0% / Final 100.0% / **+0.0%** / Iterazioni 8 / **0 skill** per iter / costo **$0.0552**. Il fix DeepSeek `''` È applicato (`vendor/evoskill/src/cli/shared.py:206-211`, `max_tokens=2000`+`reasoning_effort='low'`) → la **macchina è riparata**; il +0.0% prova che il collo è il **segnale obiettivo** (QA-set saturo al 100%), non la macchina. |
| **#21** | ANCORA-VALIDA | `Read .../agent-library/learn/lesson_harvester.py:99-120` | Taglio archivio confermato: `:103 archived_idx = text.find("\n## Archived")` → `:105 text = text[:archived_idx]`. Le ricorrenze vere (W50/W51/W52, W68/W72/W73, Air-path-drift) sono **sotto** quel taglio. Nota: esiste un `_recurrence_counts` (:123) che già conta i `Family:`, ma SOLO sugli scar non-archiviati → la soglia "≥3 live" non vede mai le famiglie archiviate. |
| **#22** | ANCORA-VALIDA (line-ref corretto) | `grep -n _guard_ ~/.openclaw/bin/openclaw_whatsapp_bridge.py` | **10** chiamate `_guard_*` in ordine fisso, ognuna clobbera `response_text`, **non** a `:1413` (stale) ma a **`:1814-1863`** nella copia HOME live (la copia repo `scripts/...` è 68 251 B vs HOME 81 608 B, mod. 11 giu → drift HOME-fork attivo). |
| **#23** | ANCORA-VALIDA | `grep -nE 'cleanup\|release\|callback\|teardown' scripts/agent_start.py` | `--cleanup` (opt-in/cron) + `--release` (manuale) esistono, ma **nessun teardown sincrono accoppiato allo spawn/morte agente**. ANTIBODY #4 W62 ancora proposto-non-costruito → conseguenza live = sprawl 16 worktree (#19). |
| **#24** | ANCORA-VALIDA (P-fix proposta) | `Read scripts/verify_the_verifiers.py:296-306` | Tautologia confermata verbatim: **`:302 if disarm in f"{disarm} python3 hook.py":`** → sempre True → sempre `ARMED`. Identico byte-per-byte fra worktree e deploy runtime (path live). Fix = 1 riga load-bearing → **proposta, non applicata** (vedi diff sotto). Lint di osservabilità aggiunto: `.github/workflows/catC-canary-tautology-lint.yml` (non-required). |
| **#25** | IMPRECISA (realtà corretta) | `wc -l ~/.claude/agents/wr{2,3}-design-architect.md`; `find -name _audit-checklist.sh` | (a) Le righe non sono "~400 entrambi": **WR2 = 416**, **WR3 = 251**. (b) `_audit-checklist.sh` **ESISTE GIÀ** (`~/.claude/skills/bali-zero-brand/_audit-checklist.sh`, 8 514 B) e conta Agent-calls/NB/imagegen (WR2 `:43,:45`). Il gap reale **non** è "manca l'harness" ma "**l'abort è onorato-dal-modello, non deterministico**": `:45/:59` sono self-check istruiti all'LLM (`if <4 Agent calls: abort`), non un gate hard fuori dal modello. La domanda riformulata: rendere l'exit-code di `_audit-checklist.sh` un gate ESTERNO che blocca la pipeline a prescindere dall'obbedienza del modello. |
| **#26** | ANCORA-VALIDA | `Read scripts/federation_orchestrator.py:283-285` | Merge confermato: `if keyword_suggestions.get(key) and not classification.get(key): classification[key] = True` → l'LLM può solo **aggiungere** un dispatch che le keyword mancano, **mai togliere**. Il classificatore Qwen (`:119 qwen3.5:9b`) non può mai restringere il fan-out. |
| **#27** | ANCORA-VALIDA | `grep -nE 'PROXY\|UNKNOWN\|DEGRADE\|/data\|llm_cost_events' scripts/cost_breaker.py` | Docstring verbatim: **`:42 HONEST LIMIT: ... budget è un PROXY threshold (USD)`**; G4 fail-closed UNKNOWN→DEGRADE (`:18-22`); legge `llm_cost_events` (Fly PG mig 117) o JSONL `${LLM_COST_JSONL_ROOT:-/data}` (`:5-6`) → sul Pro nessuno dei due esiste → DEGRADE ogni tick (= W71). Governa un proxy USD, non la finestra-5h vincolante. |
| **#28** | SUPERATA-PARZIALE (pattern resta) | `cat ~/.claude/settings.json` (`:14`); `grep -rhoE '_(OFF\|ENABLED\|ENFORCEMENT)' scripts .claude/hooks` | Le 2 leve citate sono chiuse: `settings.json:14 "AGENT_WORKTREE_ENFORCEMENT":"true"`, `STOP_VERIFY_ALLOW_DIRTY` assente. MA l'inventario leve è **~20+** (`COST_BREAKER_*_OFF`, `GUARDRAILS_STATIC_OFF`, `ORCHESTRATE_GATE_OFF`, `MCP_INTEGRITY_OFF`, `AGENT_LEASE_ENFORCEMENT`, …) tutte env-var appiccicose **senza ragione-loggata / time-box / auto-riarmo**. Pattern strutturale invariato. |
| **#29** | ANCORA-VALIDA | `ls ~/.claude/skills/bali-zero-brand/_proposed-amendments/` | Catena `*-ig-insights-insufficient-data.md` ricorrente (10/11/18 mag, 01 giu, **08 giu**, tutti 507 B = stesso stub) + WR3 `yt/.../2026-05-22-yt-insights-insufficient-data.md`. Mesi di `insufficient-data`, 0 graduation. EvoSkill saturo + LEARN archive-cieco + Reflexion no-metriche = stesso collo: **segnale obiettivo assente, non macchina**. |

#### Proposta-fix #24 (load-bearing — NON applicata, decisione operatore)

`scripts/verify_the_verifiers.py` `run_canary()` `:299-306`. La canary deve davvero settare l'env disarm e ri-eseguire `check_claude_hook` sul comando registrato, asserendo che il verdetto flippa a `DISARMED`:

```diff
-    # Synthetic: the disarm substring, if injected into the command, must be
-    # detected by the same check_claude_hook logic. We assert the substring would
-    # be caught (the lever is real and the detector sees it).
-    if disarm in f"{disarm} python3 hook.py":
-        return GateResult(gid, "claude_hook", ARMED,
-                          f"canary OK: disarm lever '{disarm}' is detectable")
-    return GateResult(gid, "claude_hook", DISARMED,
-                      f"canary FAIL: disarm lever '{disarm}' not detectable")
+    # Inject the disarm env onto a SYNTHETIC copy of the registered hook command
+    # and re-run the SAME check_claude_hook detector. The canary is only honest
+    # if the gate it would normally call ARMED flips to DISARMED under the lever.
+    canary_env = canary.get("env") if isinstance(canary, dict) else None
+    armed_now = check_claude_hook(gate)                      # baseline: expect ARMED
+    disarmed = check_claude_hook(gate, _env_override=canary_env or {disarm: "1"})
+    if armed_now.status == ARMED and disarmed.status == DISARMED:
+        return GateResult(gid, "claude_hook", ARMED,
+                          f"canary OK: lever '{disarm}' flips ARMED->DISARMED")
+    return GateResult(gid, "claude_hook", DISARMED,
+                      f"canary FAIL: lever '{disarm}' did not flip the gate "
+                      f"(armed={armed_now.status}, under-lever={disarmed.status})")
```

> Nota: il diff presume che `check_claude_hook` accetti (o riceva) un `_env_override` per la ri-esecuzione sintetica — la firma reale va verificata prima di applicare. È una modifica a logica TIER-1 meta-verifier (sha256-pinned + CODEOWNERS) → fuori dalla classe-safe-tocco; rimane all'operatore. La drift è resa **osservabile** dal lint non-required `catC-canary-tautology-lint.yml` (fallisce finché la tautologia è presente, verde dopo il fix → poi protegge da regressione).

---

## D — Backend dati & RAG (doppi-tracker, threshold bifurcato, router)

30. **Tre sistemi di migration-tracking coesistono**: il runner v2 legge solo `_schema_versions`, ma `migration_base` dual-scrive SU ENTRAMBI `schema_migrations` + `_schema_versions`, e 112 migration Python legacy (`backend/migrations/migration_NNN.py` fino a #124) non vengono mai scoperte. Una riga in una tabella e non l'altra è invisibile → re-apply o skip silenzioso. Si scrive finalmente `131_unify_migration_tracking` per collassare le due tabelle in una sola SSOT, e si promuovono/ritirano i 112 file orfani?

31. La invariante "soglia ABSTAIN singola 0.15" si è **biforcata in due sistemi paralleli che gate-ano diversamente in due path live**: `constants.py:96` hardcoda 0.15, ma `orchestrator_response.py` usa `get_abstain_threshold(query)` domain-aware (tax:0.10, kbli:0.20) mentre `reasoning.py` usa il global hardcoded a 12+ siti, zero riferimenti alla funzione domain. Stessa query, verdetto-abstain diverso. La soglia domain-aware diventa l'unica sorgente consumata da entrambi, e si riscrive l'invariante CLAUDE.md §9 sulla realtà per-dominio?

32. La dimensione embedding (1536) è una costante magica ripetuta in ≥6 file (`embeddings.py:256`, `qdrant_db.py:74`, 3 migration, `health.py:308`), non derivata dal modello frozen. Il count "93.283 vettori" non è in nessun file (grep: 0 hit) — è un numero solo-in-memoria, non verificabile dal repo. Si mette una sola assertion di startup `assert EMBEDDING_DIMS[model] == collection.vector_size` che fail-close, sostituendo i 6 literal sparsi con un registry model→dims?

33. L'invariante KBLI flat-payload è enforcata solo per convenzione negli script di index ad-hoc, e il nome canonico ha driftato (`kode_kbli` vs `kode_kbli_2025`): il read-path usa un fallback a 3 nomi (`_payload_value(p, "kode_kbli", "kode", "kode_kbli_2025")`) che maschera un data-contract mai centralizzato. Si validano i payload KBLI contro un solo modello Pydantic (i 7 campi flat) all'index time, normalizzando `kode_kbli_2025`→`kode_kbli` una volta, così il read-path può lasciar cadere il fallback?

34. La cache invalidation è **manuale al 91%**: 171 call-site `invalidate_cache` a mano con ~30 namespace stringly-typed, solo 16 usano il decoratore `@cache_invalidating` costruito per sostituirli. Una mutazione che dimentica la call, o typo-a `crm_clients_stat:*`, serve dati stale senza che nessun test lo catturi. Si migrano le mutazioni in massa al decoratore con un enum di namespace tipato, e un lint asserisce che ogni `@router.post/put/delete` su tabelle CRM invalida o è esplicitamente esente?

35. La worker queue intake (`services/intake/worker.py`) è un design SKIP-LOCKED SANO (lease + heartbeat + reclaim) ma shippa come **stub passthrough** (default `_stub_stage` "avanza silenziosamente le righe a 'done' SENZA OCR") e il docstring cita la migration sbagliata (dice 206, è 212). Girano DUE meccanismi intake (il vecchio lease-orphan-prone + questo nuovo sano): il vecchio è davvero decommissionato, e il worker dovrebbe rifiutarsi di partire in stub fuori dai test (fail-close) invece di passthrough silenzioso?

36. La registrazione router è **splittata su 3 entrypoint con 3 set di router diversi** (`main_api`→light, `main_rag`→heavy, `app_factory`→full), 326 `include_router` vs 157 `RouterEntry` nel manifest, e il manifest ha **zero consumer runtime** (è bookkeeping test-asserito, malgrado il test dica "il manifest guida la registrazione"). Questo È la radice live della famiglia 503 split-brain. Si rende la registrazione manifest-DRIVEN (iterando `RouterEntry.process_groups` per decidere light/heavy/full), collassando 326 include + 3 funzioni divergenti in un loop data-driven?

37. `PUBLIC_ENDPOINTS` è un allowlist a mano di 62 entry accoppiato alla catena 401/404, e l'app di test non monta il middleware che lo enforce. Un endpoint pubblico nuovo richiede 3 edit indipendenti per essere raggiungibile in prod, ognuno una superficie di silent-failure, e il test integrazione che lo catturerebbe (`test_endpoints_reachable.py`) è ancora "proposto, non implementato". Si fa UN test integrazione che boota lo STESSO app object di prod (light/heavy, con middleware) e asserisce che ogni route registrata ritorna ≠404 e ogni `/health` ≠401 — rendendo il gap mock-vs-prod un fail CI invece di un incidente a 3 PR?

38. `rollback_migration` cancella solo da `_schema_versions`, ma `migration_base` ha dual-scritto su ENTRAMBE → dopo un rollback, `schema_migrations` mostra ancora la migration applicata → il prossimo `is_applied()` (che legge `schema_migrations`) ritorna True → la migration rollback-ata non è MAI ri-applicata. Il rollback rompe silenziosamente il contratto dual-table. Si cancella da entrambe atomicamente, e le migration no-op di promozione si marcano `irreversible` per non droppare tabelle prod create a mano?

---

### 🔎 Re-grounding D (#30-#38) — Fable 5 audit, 2026-06-11 (disco ri-letto in sessione)

> Tutte le `file:linea` sotto sono ri-verificate **in questa sessione** su disco (worktree `.worktrees/ops-guardian-audit/`, `agent/nuzantara/ops/guardian-audit`), non a memoria. Annotazione APPEND-ONLY — il testo #30-#38 sopra è invariato.

| Q | Verdetto | Evidenza (comando in sessione) | Correzione / nota |
|---|---|---|---|
| **#30** | ANCORA-VALIDA (rafforzata) | `grep -n 'schema_migrations\|_schema_versions' db/migration_base.py`; `grep -n is_applied db/migration_manager.py`; `ls migrations_v2/ \| tail` | `migration_base._log_migration` dual-scrive ENTRAMBE (`:385` schema_migrations + `:399` _schema_versions). **Asimmetria di lettura confermata e load-bearing**: `migration_base._is_applied` (`:345`) + `_check_dependencies` (`:361`) leggono `schema_migrations`, ma il **runner v2** `migration_manager` legge SOLO `_schema_versions` (`:180/:212/:240`). Due lettori, due tabelle. Highest migration v2 = **223** (non 124). I 112 file legacy `migrations/migration_NNN.py` (fino a #124) sono ancora su disco, mai scoperti dal runner v2. |
| **#31** | ANCORA-VALIDA | `grep -c get_abstain_threshold reasoning.py` → **0**; `grep -c ABSTAIN_THRESHOLD reasoning.py` → **11**; `grep -n DOMAIN_ABSTAIN_THRESHOLDS reasoning_utils.py` | Biforcazione confermata: `constants.py:96 ABSTAIN_THRESHOLD=0.15` hardcoded; `reasoning_utils.py:556 DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT` (tax:0.10, kbli:0.20, default:0.15) + `:677 get_abstain_threshold`; `orchestrator_response.py:90` USA la domain-aware, `reasoning.py` la ignora (0 ref) e usa il global a 11 siti. Stessa query → verdetto-abstain diverso a seconda del path. CLAUDE.md §9 + `apps/backend-rag/CLAUDE.md` dicono ancora "0.15 flat" → invariante stale. |
| **#32** | PARZIALE (sostanza vera, path imprecisi + numero fantasma confermato) | `grep -rln 1536 backend/ --include='*.py'`; `grep -rn 93283 --include='*.py'` → **0** | Literal `1536` sparso e **non derivato dal modello**: `health.py:308 "dimensions": 1536` confermato, ma i path citati erano imprecisi — è `backend/core/embeddings.py` + `backend/core/qdrant_db.py` (NON `services/`). ~18 file `.py` non-test lo contengono (3 migration incluse). Il "93.283 vettori" è **0 hit** in qualsiasi `.py` (solo-in-memoria, non verificabile). Nessuna assertion di startup model→dims. |
| **#33** | ANCORA-VALIDA | `grep -rn '_payload_value.*kode_kbli' backend/ --include='*.py'` | Fallback 3-nomi presente in **DUE** read-site: `kbli_notebook_chat.py:970` + `kbli_notebook.py:257` → `_payload_value(p,"kode_kbli","kode","kode_kbli_2025")`. `_payload_value` definito in `kbli_notebook.py:104`. Esiste già `tests/unit/scripts/test_kbli_payload_contract.py` ma NON un Pydantic flat-model index-time che normalizzi `kode_kbli_2025`→`kode_kbli`. |
| **#34** | IMPRECISA→corretta (sostanza vera, numeri stale) | `grep -rn 'invalidate_cache(' backend/ --include='*.py' \| grep -v test`; `grep -rc '@cache_invalidating' \| grep -v test` | Numeri reali oggi: **131** call-site `invalidate_cache` manuali (non-test) — NON 171; **34** adozioni `@cache_invalidating` — NON 16 (l'adozione è CRESCIUTA). Decoratore in `services/common/cache.py`. Sostanza invariata: maggioranza ancora manuale (131 vs 34), stringly-typed namespace, nessun lint che forzi invalidazione su `@router.post/put/delete` CRM. |
| **#35** | PARZIALE — comment-bug FIXED, behavioral half SUPERATA | `grep -n 'migration 206' services/intake/worker.py`; `grep -rln intake_queue migrations_v2/`; `Read worker.py:475-497` | (a) **Docstring sbagliata CORRETTA in sessione**: diceva "migration 206" a `:5` e `:40`, ma `intake_queue`+`idx_iq_claimable` sono creati da **`212_intake_unified.sql:30/:62`** (206 = `wa_meta_inbox`, non correlato) → patchato a "212". (b) Il fail-open-to-stub è **già rimediato**: `main()` (`:481-497`) wira `build_real_stage_handler(pool)` di DEFAULT e fa stub SOLO con `INTAKE_WORKER_STUB=1` esplicito + `logger.warning`. Il `_stub_stage` default sulla CLASSE (`:161`) resta ma è "only for unit tests". |
| **#36** | PARZIALE — manifest-gap vero, test ESISTE ed È collected | `grep -c include_router router_registration.py` → **326**; `grep -c 'RouterEntry(' router_manifest.py` → **157**; `grep -rln router_manifest --include='*.py' \| grep -v test` → **vuoto** | 326 include espliciti vs 157 RouterEntry; il manifest ha **0 consumer runtime** (solo test-asserted) → confermato radice 503 split-brain. **MA `test_endpoints_reachable.py` ESISTE** (274 righe, 5 `def test_`, antibody del SCAR Sprint-1.B) ed è **collected** dal job REQUIRED "Backend Tests (Python)" (`tests.yml:182 pytest backend/tests/`, solo e2e ignorato) — con un `pytest.skip` fallback (`:116`) se `include_routers` fallisce in-env (può no-oppare in silenzio). Wired in **0 workflow NAMED**. Fix shippato: `catD-backend-data-invariants.yml` lo esegue come check NAMED non-required + asserisce che non sparisca. |
| **#37** | PARZIALE — count corretto, presupposto "non implementato" SUPERATO | `grep -oE '"/[^"]*"' auth/public_endpoints.py \| sort -u \| wc -l` → **62** | PUBLIC_ENDPOINTS ≈ **59-62** entry a mano (≈ "62" del testo, accurato). MA "il test integrazione che lo catturerebbe è ancora proposto-non-implementato" è **FALSO oggi**: `test_endpoints_reachable.py` ESISTE e fa esattamente quello (monta `include_routers()` + `HybridAuthMiddleware`, `test_public_paths_bypass_auth`/`test_private_paths_require_auth`/`test_health_like_routes_appear_in_registry`). Resta vero: 3-edit per un nuovo endpoint pubblico, e l'app di test resta più leggera di `create_app()`. |
| **#38** | ANCORA-VALIDA (load-bearing) | `Read migration_manager.py:220-257` | `rollback_migration` (`:220`) cancella SOLO `DELETE FROM _schema_versions` (`:257`), mai `schema_migrations`. Combinato con #30: `migration_base._is_applied` legge `schema_migrations` → dopo rollback la migration risulta ancora applicata lì → **mai ri-applicata**. Contratto dual-table rotto in silenzio. Nessun marker `irreversible` sui no-op di promozione. |

#### Azioni safe applicate in sessione (worktree only, no git ops, no commit)
- **#35 comment-fix**: `worker.py:5` + `:40` "migration 206" → "212 (`212_intake_unified.sql`)", dopo aver verificato che 212 crea `intake_queue`+`idx_iq_claimable` e 206 è `wa_meta_inbox` (non correlato).
- **#31 doc-sync**: `CLAUDE.md §9` invariante abstain riscritta sulla realtà per-dominio (vedi blocco DOCSYNC).
- **#32/#36/#37 nuovo lint non-required**: `.github/workflows/catD-backend-data-invariants.yml` — pin del literal embedding 1536 in `health.py` (Data Invariant #9) + run NAMED di `test_endpoints_reachable.py` + assert che l'antibody non venga cancellato. NON-required (osservazione 1 ciclo prima di gate, lezione W69 BUCO#1).

---

## E — Costo / sovranità / multi-LLM / ground-truth

39. **[🟢 E3: il `set -e` trap di `regulatory-watcher-run.sh` fixato (ora `set -uo`) — 1 fork sistemato, consolidazione resta]** **La cascade è forkata 6+ volte, non condivisa una**: `claude-cascade.sh` è la lib canonica ma solo 3 job la sorgono; `regulatory-watcher-run.sh`, `dlq_autopilot.py`, `cost_breaker.py`, `wr3_supervisor.py`, `ai-dispatch.sh` ri-codificano ognuno tier-order + quota-grep indipendentemente, e hanno già driftato (regex quota diverse per tier; cost_breaker lista DeepSeek+OpenRouter che la shell non ha). Ogni job autonomo passa per una sola `cascade.py`/`.sh`, e qual è la tier-list canonica (include DeepSeek/OpenRouter o no)?

40. **[⚠️ IMPRECISA→corretta + 🟢 lint armato 2026-06-11 sera]** Numeri ri-misurati su disco: gli `unset/pop ANTHROPIC_API_KEY` reali sono **9 file** (non 23; grep `(unset|.pop(|del) ...ANTHROPIC_API_KEY`), su **71 file** che lo nominano. Ma il fatto VERO e nuovo: il grep-lint ha scoperto **3 istanziazioni paid LIVE già su `main`** — `apps/bali-intel-scraper/backend/services/ai_engine.py:195` (`AsyncAnthropic(api_key=…)`, **importato da task_queue/classifier/sentiment** = path pagato vivo), `apps/backend-rag/process_batches_2_3.py:34`, `apps/backend-rag/scripts/claims_extractor.py:136`. Enforcement centrale resta **0**. **Fix shippato**: `.github/workflows/catE-sovereignty-lint.yml` (NON-required) — bana `Anthropic(api_key=…)` baseline-aware (fail su NUOVO paid path; le 3 note in `catE-paid-anthropic-baseline.txt`) + bana `export/setenv ANTHROPIC_API_KEY=<valore>`. Resta: il wrapper `claude_invoke()` unico e la **remediation delle 3 istanze a OAuth** (FUORI scope safe-fix — runtime).

   Il ban "no key Anthropic pagata" è ri-difeso in **23 file** (`unset/pop ANTHROPIC_API_KEY` copincollato), enforcato centralmente in 0 — nessun hook/CI che fa fallire il build se uno script istanzia `Anthropic(api_key=...)`. CLAUDE.md §7 dice "se una regola è violabile, scrivi un hook": questa non ce l'ha. Si fa un CI grep-lint che fallisce su ogni paid-path nuovo, e un solo `claude_invoke()` wrapper sostituisce i 23 `unset` inline?

41. **64 job dipendono da un solo prodotto Google gratis** (NotebookLM), interrogato via un solo OAuth personale (`antonellosiano@gmail.com`), senza export di backup. La NB "Indonesia Gov Data Sources" (313 sorgenti) è già **permanentemente cancellata**, e il curator ha auto-cancellato 242 sorgenti (`nb-dedup-deleted.jsonl`). C'è un export periodico del *contenuto* delle sorgenti (non solo la UUID-map) su Tigris/locale così una NB cancellata è ripristinabile? Si specchiano le 3.622 sorgenti nello stack Qdrant/Postgres posseduto, così NotebookLM degrada a "verifier nice-to-have" invece di "single point of truth"?

42. Law 2 (sovranità OSINT) è **un firewall-di-path stretto + fiducia**, non una boundary di egress: l'unico codice (`mata_garuda/security/path_firewall.py`) blocca la scrittura di file-agente fuori scope, ma non fa NULLA sul contenuto intel che esce — e i path reflection/digest chiamano `claude --print` (cloud), i 64 job NB spediscono query a Google. Dov'è esattamente la linea tra "dato OSINT" e "skill/aggregato" che può andare al cloud, ed è checkabile? Serve un egress-lint (read da tabelle intel-lake non devono confluire in un prompt cloud-LLM) analogo al path-firewall sulle scritture?

43. **[✅ ANCORA-VALIDA, parz. armata 2026-06-11 sera]** Ri-confermato su disco: `scripts/lint/wr3_lint_autonomous_publish.py` esiste (gira clean, exit 0, `sys.exit(1)` su ERROR), ma `grep` in `.github/workflows/` = **0 referenze**; `symbiosis-lint.yml` esegue solo `lint_symbiosis_promises.py SYMBIOSIS.md` (doc-check, come detto). **Fix parziale shippato**: la nuova `catE-sovereignty-lint.yml` ora esegue `wr3_lint_autonomous_publish.py` BLOCKING su ogni PR + push-main (non-required, in osservazione). Resta: il **gemello WR2** (un `wr2_lint_autonomous_publish.py` non esiste — solo `wr2_telegram_publish_gate.py` è il gate runtime) e la promozione a **required check** dopo un ciclo di review.

   Il gate publish Law 5 è codice vero (`wr2_telegram_publish_gate.py` HMAC + whitelist + `WR2_AUTO_PUBLISH_ENABLED=false`) ma il lint che lo protegge (`wr3_lint_autonomous_publish.py`, banna `ig.publish`/`tiktok.publish`/`yt.upload`) **non è in CI** — `symbiosis-lint.yml` gira solo il doc-check. La sicurezza di "mai auto-publish IG" oggi è "codice" o "il fatto che nessuno ha ancora cablato l'API"? Si rende `wr3_lint_autonomous_publish.py` (+ gemello WR2) un required CI check su ogni diff `scripts/wr*`?

44. **[⚠️ SUPERATA (il fatto-0644) + 🟢 lint antibody armato 2026-06-11 sera]** Ri-verificato live `stat -f '%Sp %N'` sui path PRO reali: **tutti e 5** gli `apps/*/.env` (wa-mirror, bali-intel-scraper, war-room, backend-rag, cell) sono **già `-rw-------` 0600** — `find apps -name '.env' -perm +044` (main checkout) = **ZERO**. Il fatto "ancora 0644 world-readable" è quindi SUPERATO (già rimediato prima/inizio sessione; nessun chmod necessario stavolta). MA la domanda strategica resta valida: **il loop antibody è ora armato** — `catE-sovereignty-lint.yml` fa fallire la build su ogni `apps/*/.env -perm /044` (più robusto del cron-alert proposto: gate al PR). Resta aperta la decisione **Keychain+wrapper `source` vs dotfile** (pattern `wa-media-pull-run.sh`).

   **Secrets-in-cleartext è firefighting per-incidente, non strategia**: live in sessione, `apps/wa-mirror/.env`, `apps/bali-intel-scraper/.env`, `apps/war-room/.env` sono ancora **0644 world-readable** (gli altri 2 chmod-ati a 0600 dopo le cicatrici). 5+ P0 della stessa classe in 5 settimane. Si fa un lint giornaliero (`find apps -name '.env' -perm +044` → alert) che chiude il loop che le cicatrici riaprono a mano? C'è ragione di tenere secrets in dotfile invece di Keychain + wrapper `source` (il pattern già usato per `wa-media-pull-run.sh`)?

45. Tier 3/4 della cascade si **auto-disarmano**: `claude-cascade.sh` salta Codex e Ollama se `--agent` è settato → ogni invocazione agent-flavored collassa la cascade 5-tier a 3, e l'audit 2026-05-24 trovò Tier 3+4 disarmati silenziosamente (cascade effettiva 2-deep). Non c'è heartbeat di liveness per-tier. La cascade dovrebbe health-pingare ogni tier (1 token) a schedule e Telegram-alertare un tier morto, così il disarmo è osservabile? Il grep-su-stdout è il segnale giusto di esaurimento vs i veri exit-code / header rate-limit?

46. Il "bipolar verifier" si fida del polo NB, ma il polo NB **muta silenziosamente sotto** (curator auto-cancella sorgenti, UUID-switch ha orfanizzato la famiglia NB-INTEL, la map è stale). Un verifier la cui "verità" perde sorgenti e cambia UUID ritorna meno/diversi fatti nel tempo senza che il consumer sappia che il terreno si è mosso. L'auto-delete del curator si gate-a (propose-not-execute) per le NB INTEL/regulatory, vista l'irreversibilità? Ogni query bipolar registra il source-count visto, così una regressione di coverage è rilevabile?

47. Il ledger costi è triple-write su Fly, ma il breaker legge uno store diverso da quello che il recorder scrive affidabilmente: il sink più affidabile (JSONL Fly-locale) è illeggibile da dove gira la governance (Pro, senza `/data` né DSN). Il ledger indistruttibile e il suo consumer sono in fault-domain diversi. La governance gira come cron Fly co-locato col ledger (legge PG/JSONL locale), col deadman Pro che guarda solo l'alive-signal? O si replica il ledger verso il Pro a schedule?

---

## F — WhatsApp / persona / bridge (HOME-fork + over-match)

48. Il bridge WhatsApp LIVE gira dalla copia **non-git-tracked** (`~/.openclaw/bin/openclaw_whatsapp_bridge.py`), mentre `scripts/openclaw_whatsapp_bridge.py` è la copia repo. Code-review, CI e ogni guardrail operano sulla copia repo; la prod gira la HOME. La superficie Bali Zero più editata (la famiglia `_guard_*`, 4 over-match in 5 giorni) vive dove la review non vede. **Perché il bridge live gira da HOME?** Può girare dal checkout repo (o da un path deploy-synced con un drift-check hook) così la disciplina byte-identical-double-file smette di essere load-bearing?

> **[Cat-F re-ground 2026-06-11 — ANCORA-VALIDA, anzi confermata PEGGIO del previsto]** Verificato in sessione: `launchctl print gui/501/com.nuzantara.openclaw-whatsapp-bridge` → `program = ~/.openclaw/bin/run_openclaw_whatsapp_bridge.sh` → quel wrapper fa `exec uvicorn --app-dir ~/.openclaw/bin openclaw_whatsapp_bridge:app` ⇒ la prod gira la HOME. La disciplina byte-identical NON regge ORA: `shasum` + `wc -l` mostrano HOME **1874 righe** vs repo **1471** (**+403**), 3 sha256 tutti diversi (HOME/repo/worktree), e la HOME ha **6 funzioni-helper guard live ASSENTI dalla copia repo** (`_is_incidental_villa_mention` @503, `_lkpm_window_is_current` @76/965, `_identity_rules` @1514, `_hak_milik_asserts_foreigner_can_own` @886, `_lkpm_window_clause`, `_normalize_whatsapp_format`) — cioè i *corpi* dei guard divergono, non solo i nomi. mtime HOME = Jun 11 20:11 (2 giorni DOPO l'ultimo commit repo Jun 9 23:51): la prod è avanti alla review. Il fix CI non chiude la drift cross-host (la HOME non è nel repo) — la lint `catF-wa-bridge-drift.yml` rende la cosa LOUD (notice ogni run + gate sull'invariante in-repo def==wired). Il vero drift-check resta da fare SUL Pro (PROPOSTA: hook byte-parity sulla HOME, o far girare la prod dal checkout repo/deploy-synced).

49. La persona Zantara ha un pattern di over-cautela documentato (W72: deflette fatti regulatory stabili a "verifica col team") E un pattern di over-match nei guard (W68/W72/W73). Sono due facce della stessa cosa — un layer post-LLM che non si fida del modello? Se i guard diventassero grounding pre-hoc (#22), l'over-cautela sparirebbe come effetto collaterale?

> **[Cat-F re-ground 2026-06-11 — ANCORA-VALIDA come domanda di design; il PRESUPPOSTO sui fix è SUPERATO]** I fix W72/W73 NON sono "non ancora live": `grep` in sessione li trova in ENTRAMBE le copie — `_contains_any_word` (word-boundary, @413 HOME), `_is_nominee_intent` (@1342), `_guard_legacy_b211_reply` (@769), `_VILLA_TERMS` che ora passa per `_contains_any_word`. Catena live = **10** `_guard_*` definiti e tutti **10 wired** (`response_text = _guard_*`, HOME @1814-1859), e le `reply_rules`/`knowledge_tool_contract` over-cautela W72 ci sono (@1465/@1490/@1499, con lo split DEFER vs STATE-DIRECTLY). Quindi la domanda resta valida ma va riletta così: i guard W72/W73 sono applicati, ma restano **post-hoc clobber in catena fissa** — la migrazione a grounding pre-hoc (#22) è il vero open. CAVEAT: la HOME è già avanti alla repo (vedi #48) — la HOME ha 6 helper-guard che la repo non ha, quindi "i guard live" ≠ "i guard in review".

---

## G — Il filo rosso (la vera preda per un deep model)

50. **Il layer documentazione (leggi, VADEMECUM, docstring, scar) drifta dietro la realtà-codice, e la drift è INVISIBILE perché ogni layer asserisce confidenza** ("verified 2026-05-12", "as-shipped", "NON editare"). Non c'è meccanismo che renda la divergenza doc-vs-codice *essa stessa* osservabile. Qual è il set minimo di CI-assertion (channel-count pin, manifest-auto-derivation, inventory-merge, Air-ref linter, threshold-doc-sync) che converte questi hand-audit ricorrenti in gate?

51. **Il pattern "due implementazioni parallele di un concetto"** ricorre ovunque: due migration-tracker, due sistemi abstain-threshold, tre router-registration, tre render-path WR2, 6 fork cascade — dove la VECCHIA è documentata canonica (invarianti CLAUDE.md) mentre la NUOVA è quella che gira in alcuni path. La mossa a più alta leva è collassare ogni coppia in una SSOT e riscrivere i doc-invarianti stale sulla realtà — invece di aggiungere un terzo meccanismo. Quale coppia, se collassata, elimina più superficie di drift a valle?

52. **[🟢 parz. E4/E6/E8: oggi armati hot-zone CODEOWNERS + asyncpg-lint blocking + 5 sentinel BUCO#1 → required 11→18; i guardiani non-toccati restano fail-silent]** **"Esiste ma non è armato" (W64) è la malattia ricorrente** a ogni layer: lint senza consumer, canary tautologica, cascade auto-disarmante, guardrail dietro un env-flag, breaker che non legge il ledger. Per un solo-dev che "non rivede codice", il rischio è "decadimento entropico inosservabile dei guardiani". Qual è il set minimo di required-CI-check + heartbeat-Pro che rende questi guardiani *fail-loud* invece di *fail-silent* — e quale singolo (cascade health-ping? .env-perm lint? Law-5 CI gate?) compra più osservabilità per riga?

53. **Tre subsistemi di auto-miglioramento girano, costano, e adottano zero cambiamenti** perché il gradiente che salgono è assente (eval saturo / slice sbagliato / no metriche). Vale la pena rifornire la macchina (riparata) o ri-puntarla su un segnale obiettivo che fallisce davvero (il ledger cicatrici è il candidato ovvio: è un corpus di fallimenti reali, ricorrenti, con famiglie taggate)?

54. **Lo stack assume una flotta 2-macchine ma la path-drift dimostra che sono N macchine con stato divergente** (Pro/Mini/M5/deploy-worktree, due utenti `nuzantara` vs `balizero`). Ogni domanda "è armato questo gate?" ha un implicito "...su quale macchina?" che il campo `scope` del registry risolve solo a metà. `verify_the_verifiers` dovrebbe girare su OGNI nodo e riconciliare (così "armato sul Pro ma disarmato su M5" è esso stesso RED), e il deploy-worktree-as-runtime-home è un debito strutturale che un solo checkout canonico eliminerebbe?

55. **31 meta-monitor + catena 4-deep girano verdi sopra: un registry che copre il 48%, un autopilot cieco, e una feature smearata su 5 home.** La self-knowledge della flotta è peggiore della sua self-monitoring. La singola mossa a più alta leva è il fix T4 (stderr vero nel DLQ → riarma il heal-loop) o il fix strutturale T1+T2 (registry-as-bijection + WR2 home-consolidation)? Da dove partire per la riduzione di entropia massima?

---

## H — Le 5 "se potessi farne solo 5"

56. (Sicurezza, ORA) Si chiude W38 sui 2 ruoli app ancora `rolsuper=true` (`nuzantara_rag`, `backend_ts_user`) + split `ADMIN_DATABASE_URL`? È l'unica P0 security-grade e current.

57. (Osservabilità, leva massima) Si infila lo stderr vero nel `log_tail` del DLQ (#13) per riarmare un heal-loop che oggi ha guarito 0/16 — il fix che converte 16 morti silenziosi in segnale azionabile?

58. (Drift, radice) Si collassano le coppie "due-implementazioni" (migration-tracker, abstain-threshold, router-registration) in SSOT (#51) e si rendono i doc-invarianti CI-enforced (#50) — invece di aggiungere il terzo meccanismo?

59. (Resilienza, single-point-of-truth) Si specchia il ground-truth NotebookLM (3.622 sorgenti) nello stack posseduto (#41), visto che 313 sorgenti sono già sparite irrecuperabilmente da un prodotto gratis su un OAuth personale?

60. (Auto-miglioramento, obiettivo) Si ri-punta il loop EvoSkill/LEARN dal QA saturo al ledger cicatrici come segnale-che-fallisce (#20/#21/#53) — o si spegne finché non ha una frontiera non-triviale, smettendo di pagare quota per +0.0%?

---

> **Nota di metodo finale**: queste 60 non sono uniformi per gravità. Le P0 reali sono **#1/#56** (security live) e **#13/#57** (heal-loop cieco). Le a-più-alta-leva strutturale sono **#11/#51/#55** (registry-bijection + collasso-coppie). Le più "illuminanti" (che cambiano come pensi al sistema) sono **#50/#52/#53** — il filo rosso che lega tutto: la documentazione e i guardiani driftano in silenzio, e nessun meccanismo rende la drift osservabile finché un umano non la nota. Esattamente la tesi del recursive-self-improvement (Anthropic, reference_anthropic_recursive_self_improvement_2026_06_06): il collo di bottiglia è la verifica, non la generazione.
