---
date: 2026-06-14
domain: operations
client_case: none
session: opus-mythos-P2 (fleet launchd + FASE-0 governance)
machine: Pro (nuzantara@Nuzantara)
sources:
  - live launchctl list / launchctl print (174 project labels, this session)
  - ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist (on-disk)
  - ~/.claude/hooks/* + ~/.claude/settings.json (hook registration, E2E tested)
  - ~/.agent/decisions/state/{verify_the_verifiers,mcp_integrity,cost_breaker_deadman}.json
  - gh api repos/Balizero1987/Teman2/branches/main/protection/required_status_checks
  - research/operations/2026-06-11-guardian-of-guardians.md (queue E1-E13)
  - cicatrici W64 / W69 / W71 / W50-52 / W65 / W67
  - 4 diagnostic subagents (crash-loop, chronic, hooks, fase0) — ALL claims gated on disk
  - Gemini 3.5 Flash (High) second-order synthesis; Codex GPT-5.5 (xhigh) adversarial refuter
---

# Mythos P2 — Muscoli (parco LaunchAgent) + Governance FASE-0

> Organo: i ~174 LaunchAgent del Pro + il layer "guardiani dei guardiani" (FASE-0).
> Tesi-madre da cacciare: **`Esistere ≠ Armato`** (W64/W71). Esito: la tesi-madre regge in
> UNA istanza reale, ma il vero topic di 2° ordine è il suo **gemello** che genera la
> maggior parte dei suoi falsi-positivi — più una correzione del refuter che impedisce al
> gemello di overfittare.

---

## §0 — Executive

Il parco è **sostanzialmente sano**. La "diagnosi di partenza" del mandato (lista di
guardiani disarmati/rotti da W64/W69/W71 + guardian-of-guardians) si è rivelata, alla
ri-verifica su disco, **in larga parte FALSA**: **6 claim del LEAD falsificati** + 1
allucinato da un mio stesso subagent — tutti per **la stessa ragione unica** (§Meta-pattern).

- **Crash-loop (LEAD #1): inesistente.** I 4 daemon "loopanti" → `runs=1`, 3h uptime, redis
  LIVE `127.0.0.1` (UP), non Mini. Nessun looper nel parco. **Circuit-breaker non serve.**
- **guardrails-static disarmato (LEAD #3 / W71 gap #2): falso.** È il Tier-2 fallback del
  registrato `guardrails-client.sh`; catena E2E armata e testata.
- **required-checks mancanti (W69 BUCO #1): CHIUSO.** 18 contesti required su main.
- **UNICA rottura live impattante**: `wr2.html-apply` — Playwright chromium mancante nel
  venv → renderer HTML→PNG (sostituto Canva) **congelato**. **CURATO** (install + smoke-test
  live) e **reso durevole** (provisioning-guard nel plist, questa PR).
- **UNICO `Esistere≠Armato` reale**: `cost_breaker.py` cieco sul Pro (governa zero spesa) —
  e il suo deadman dà falso conforto (theater-per-procura, scoperto dal refuter).
- 2 confini operatore: **Mini-Pro2 offline** (fisico); **checkout locale 162 commit stale**
  (con lavoro non-committato → `git pull` non sicuro da me).

**Meta-pattern (il vero topic):** `Esistere≠Armato` ha un gemello dominante, **`Letto≠Vivo`**:
il piano-di-LETTURA (checkout locale 162 commit indietro + cicatrici che invecchiano) diverge
dal piano-di-ESECUZIONE (deploy worktree = origin/main). Quasi ogni allarme "disarmato!" è
questa divergenza. **MA** (correzione del refuter, accolta) `Letto≠Vivo` NON spiega tutto:
`cost_breaker` è un `Esistere≠Armato` puro del run-plane (gira dal checkout corrente ed è
semanticamente cieco). Le due malattie coesistono → la contromisura deve includere una
**sonda semantica live**, non solo un check di SHA-drift.

---

## §1 — Crash-loop daemons (LEAD #1 falsificato)

| label | runs | etime | redis (LIVE) | verdetto |
|---|---|---|---|---|
| intel-dedup-gateway | 1 | ~3h | 127.0.0.1 | idle-healthy |
| meta-dispatcher | 1 | ~3h | 127.0.0.1 | idle-healthy |
| observatory | 1 | ~3h | 127.0.0.1 | idle-healthy |
| research-sentinel | 1 | ~3h | 127.0.0.1 | idle-healthy |

- `launchctl print`: tutti `runs=1, state=running, never exited`. Log fermi a `02:13:28`
  con `PEL drained, switching to new-message mode` = connessione redis OK, bloccati su
  XREAD = **idle sano**, non loop.
- Redis: default sorgente = Mini (`publisher.py:21 BZ_REDIS_HOST default 100.93.236.6`); env
  LIVE (`ps eww`) lo sovrascrive a `127.0.0.1` (redis Pro UP, ping=PONG). Mini morto ma
  **non usato** → nessun rischio attuale.
- Scansione parco: ogni `runs>30` è un cron schedulato exit 0; conteggi coerenti con la
  cadenza. **"2750 run/giorno" del LEAD = non supportato** (max 60/h = 1440/giorno).
- **Fragilità latente (preventiva, NON rotta):** la protezione `127.0.0.1` vive solo
  nell'env login-shell; un riavvio che la perde farebbe ricadere i 4 daemon sul default
  Mini morto → pin esplicito `BZ_REDIS_HOST=127.0.0.1` nei plist (operatore, §Solo-operatore).

---

## §2 — Cronici minori

| label | stato live | causa (evidenza) | verdetto |
|---|---|---|---|
| **wr2.html-apply** | pre-fix exit → **FIXED + durevole** | Playwright chromium/headless-shell assente in `.venv-wr2-html` | **CURATO** (§Terapia) |
| wr2.plist-watchdog | exit 1 (cosmetico) | NON path-drift (script esiste, gira 15min); tenta di rianimare plist Canva ritirati | landscape Canva ambiguo → operatore |
| intel-radar-daily-digest | crash mascherato | `ModuleNotFoundError: structlog` (pyenv 3.11.11) | env runtime (organo intel) → operatore |
| wr2.sla-worker | exit 1 | manca `TELEGRAM_OWNER_CHAT_ID` nei secret | secrets → operatore |
| wr2.supervisor / -watchdog / wr3.supervisor | PID vivi 3h+, "74" | **stale-74**: 74 = boot pre-pg-proxy; ora `runs=2-3`, PG connesso | **sani** (no fix) |
| codex-spark-alarm / wr2.hardening / wr2.measurer | exit **0** | LEAD diceva erroring — falsi: idle/env-skip benigni | sani |
| domain-mesh.foundations.daily | exit 1 | 1/24 gov-API `RemoteProtocolError`; auto-guarisce | mata-garuda → operatore |
| federation-alert-dispatcher / cell.organism | PID vivi, exit 1 stale | crash transitorio gap pg-proxy 15432 a 02:13, ora `LISTEN`/pulsing | sani ora |

**Reperto §2:** gated 13 label → **1 sola** rottura live impattante (`html-apply`). 3 claim
del LEAD (codex-spark-alarm/hardening/measurer) erano exit 0 benigni. I tre exit-74 sono
falsi allarmi (semantica stale dell'exit + PID vivo).

---

## §3 — Hook (settings.json) — nessun guardiano disarmato sul Pro

- **Enforcing (bloccano), E2E testato:** `guardrails-client.sh` (PreToolUse `*`, 3 tier:
  daemon socket→`guardrails-static.py`→fail-closed) — `rm -rf ~`→BLOCK exit 2; `ls`→ALLOW
  exit 0; static fallback blocca `git push --force main`/`mcp__github__repo_delete`/`Write`
  su `.env`. Socket daemon vivo (02:14). Più `worktree_isolation.py`,
  `worktree_file_write_check.py`, `orchestrate_gate.py`, `stop_verify.py`.
- **`guardrails-static.py` = T2 fallback by-design**, NON un hook a sé. Il "W71 gap #2"
  ("esiste ma non registrato") è **mis-lettura della cicatrice**; registrarlo a parte sarebbe
  stato dannoso. Il meta-verifier lo conosce (gate `guardrails_static` con `invoked_via`,
  PR #1175). Gap M5-specifico/storico.
- **Advisory by-design (non teatro):** `seam_verify.py`, `stadio_zero_nudge.py`,
  `dispatch_nudge.py`, `sibling-claude-warn.sh`. **Nessuna terapia hook necessaria.**

---

## §4 — Guardiani FASE-0 (run-live, leggi l'OUTPUT non l'exit-code)

| guardiano | verdetto live | onesto? |
|---|---|---|
| verify_the_verifiers (deploy / run-plane) | `22/22 ARMED · GREEN` | sì (corrente) |
| verify_the_verifiers (repo locale stale / read-plane) | `20/21 + 1 WARN fantasma` | artefatto stale |
| verify_mcp_integrity.sh | `YELLOW connected=12 failed=5` | sì, ma vedi caveat ↓ |
| **cost_breaker.py** | ogni provider `UNKNOWN → DEGRADE` | **fail-safe ma CIECO (Esistere≠Armato)** |
| **cost_breaker_deadman.sh** | exit 0, "all fresh" | **teatro-per-procura: prova solo che il sensore cieco è vivo** |

- **Discrepanza 22/22-vs-20/21 = NON teatro ricorsivo.** Root-cause: il LaunchAgent gira la
  copia **deploy** (`nuzantara-deploy` = `3d5dd1da3`, 18162B, commit `bbeee75ca`, 22 gate →
  GREEN). La copia **repo locale** (17641B, `9b49048a7`, 162 commit indietro) emette un WARN
  `lint_asyncpg has no consumer` che è un **fantasma** — il consumer ORA esiste come
  required-check `asyncpg-lint`. **La mia run manuale dalla copia stale ha SOVRASCRITTO lo
  state-file alle 05:18** (read-plane che avvelena il record del run-plane — il pericolo del
  meta-pattern, osservato dal vivo).
- **cost_breaker.py — W71 ANCORA VERO (vero positivo, run-plane):** non raggiunge il ledger
  Fly PG `llm_cost_events`; il JSONL `/data` è vuoto → `UNKNOWN → DEGRADE`. Fail-safe ma
  **governa zero spesa reale.** NON spiegabile come stale-read: è un bug di authority/bridge.
- **cost_breaker_deadman — declassato (refuter):** "fresh blindness is still blindness". Il
  deadman osserva la *freschezza* dei 3 segnali, non se il breaker *vede* la spesa → dà falso
  conforto. Armato in senso stretto, cieco in senso utile.
- **mcp_integrity — caveat (refuter):** `failed=5 == baseline=5` è "debito normalizzato"
  senza owner/expiry. La regola "RED solo se failed AUMENTA vs baseline" non cattura il caso
  *identità-che-cambia* (un optional recupera + un reale fallisce → conteggio resta 5). Da
  irrobustire con set-di-id atteso, non solo conteggio.

---

## §5 — Required status checks su main (W69 BUCO #1 = CHIUSO)

`gh api .../branches/main/protection/required_status_checks` → **18 contesti**, verbatim:

```
E2E Tests (Playwright), MCP Server Tests, Detect Secrets, Backend Tests (Python),
Bandit Python Security, CodeQL Analysis (python), CodeQL Analysis (javascript),
root-guard, Frontend Tests (Next.js) (mouth, true), Canary self-test + incremental mutation,
verify-the-verifiers, Hot-zone enforcement, asyncpg-lint, P3 static validation (enforcing),
lesson-harvester-gate, brand-api-gate, cost-breaker-tests, P6 parallelize-hypothesis falsifiable gates
```

- `verify-the-verifiers` + `Canary self-test` + l'intera suite P1-P9 + hot-zone → **tutti
  required** (ciascuno dietro un sentinel skip→success per la trappola `paths:` di W69).
  W69 BUCO #1 superato: non 2 ma **18 contesti** bloccano i merge.
- GoG E1-E13 (report 11/06): **E1** (indexing-sweep loop) FIXED; **E2**
  (`AGENT_WORKTREE_ENFORCEMENT=true`) FIXED; **E4** (CODEOWNERS exit-1 enforcing nel deploy)
  FIXED; **E7** (state-bridge runs 10027→38) FIXED. **E11 NON regredito**: i supervisor
  exit-74 sono sani (il "runs=5943 looping" di un subagent era il **PID** confuso col
  run-count — falsificato dal mio re-grep, runs reale=3 in 3h13m, **W65**).

---

## §Meta-pattern — `Esistere ≠ Armato`, il gemello `Letto ≠ Vivo`, e il limite del gemello

> *Cosa si ripete attraverso TUTTI i finding? Quale convinzione difettosa li genera?*

**`Esistere≠Armato`** (un guardiano che esiste, gira, logga successo, e non fa nulla) esiste
in questo organo in **una sola istanza pura**: `cost_breaker.py` (+ il suo deadman che dà
falso conforto). Tutto il resto della tesi-madre erano **falsi-positivi** generati dal gemello.

### `Letto ≠ Vivo` (Divergenza Read-plane / Run-plane) — la malattia-delle-malattie

L'organismo ha due piani:
- **Run-plane** = ciò che gira: il deploy worktree `~/Desktop/nuzantara-deploy`
  (= origin/main = `3d5dd1da3`, corrente). Tutti i LaunchAgent puntano qui.
- **Read-plane** = ciò che gli auditor LEGGONO: il checkout locale `~/Desktop/nuzantara`
  (`e2b355f45`, **162 commit indietro**) + le cicatrici che invecchiano.

**Malattia:** trattare il read-plane come ground-truth dello stato operativo. Ogni allarme
"disarmato!" del mandato era un guardiano **armato nel run-plane** che **appariva disarmato
nel read-plane.**

**3 evidenze trasversali (gate-verificate):**
1. **Daemon redis** — diagnosi "loop contro Mini" dal *default sorgente* (read-plane); env
   *vivo* (run-plane) usa `127.0.0.1` UP → zero loop.
2. **verify_the_verifiers** — `22/22 GREEN` (deploy) vs `20/21 + WARN fantasma` (repo stale);
   il "consumer mancante" esiste ora come `asyncpg-lint`.
3. **Hot-zone / required-checks / E1-E2-E4-E7** — letti "disarmati/monitor-mode" nel checkout
   stale, ma `exit 1` enforcing + 18 required-checks nel run-plane.

**Pericolo concreto (osservato dal vivo):** eseguire un guardiano DAL read-plane emette un
verdetto falso che può **sovrascrivere lo state-file condiviso** — la mia run manuale ha
riscritto `verify_the_verifiers.json` da 22/22 a 21/20/1 alle 05:18. Il read-plane stale
**avvelena** il record del run-plane. È `Esistere≠Armato` puntato sul layer di audit stesso:
il catalogo delle malattie è scritto contro lo snapshot-cadavere di un corpo già guarito.

**Conferma indipendente (Gemini 3.5 High):** dato solo l'aggregato verificato, ha ri-derivato
lo stesso pattern ("Sindrome da Allucinazione Speculare"), stesse 3 evidenze, stessa famiglia
di contromisura → non è una proiezione di Opus.

### Il limite del gemello (refuter Codex GPT-5.5 — accolto)

`Letto≠Vivo` **può overfittare.** Alcune ferite sono **run-plane wounds**: un checkout deploy
fresco può comunque eseguire un guardiano *operativamente vivo ma semanticamente cieco* —
`cost_breaker.py` ne è il **controesempio** (gira dal run-plane corrente, eppure non vede
`llm_cost_events`). Quindi le due malattie **coesistono**:
- `Letto≠Vivo` → la maggioranza dei falsi-allarmi (codice stale letto come verità).
- `Esistere≠Armato` puro → cost_breaker (run-plane, cecità semantica), authority/bridge.

### Contromisura strutturale (proposta — NON shippata: richiede review 4-LLM, §6 CLAUDE.md)

Un **`ExecutionDriftGate` + sonda semantica** come primo step di ogni verificatore:
1. Ogni state-file porta `producing_commit_sha` + `checkout_path` + `data_source_authority`.
2. Meta-check FALLISCE se uno state-file è scritto da un checkout ≠ deploy (run-plane),
   **oppure** se il main locale drifta > N commit dietro origin/main, **oppure** (correzione
   refuter) se il guardiano non passa una **live semantic probe** = "vedi davvero la tua
   fonte dati?" (es. cost_breaker deve provare di leggere ≥1 riga reale di `llm_cost_events`,
   non solo che il file-segnale è fresco).
3. I guardiani-diagnostici rifiutano di scrivere lo state condiviso se `git rev-parse HEAD`
   ≠ HEAD del deploy worktree (anti-avvelenamento).

> **Coerenza-Mythos:** ho lasciato il worktree stale di `agent_start.py` (162 indietro) e ho
> ricreato un worktree **fresh da origin/main** (`EnterWorktree`) PRIMA di scrivere — editare
> file-repo dal piano stale *sarebbe* la malattia che diagnostico. Il gate strutturale tocca
> `verify_the_verifiers.py` (meta-verifier high-stakes) → richiede la spec-review 4-LLM, non
> uno ship autonomo: lo lascio come proposta.

---

## §Terapia eseguita

1. **`wr2.html-apply` — pipeline WR2 HTML→PNG sbloccata (cura immediata + antibody durevole).**
   - Diagnosi: `BrowserType.launch: Executable doesn't exist at
     .../chromium_headless_shell-1223/chrome-headless-shell` nel venv
     `~/Desktop/nuzantara-deploy/.venv-wr2-html` (playwright 1.60.0 come pacchetto, browser
     mai scaricato — "Looks like Playwright was just installed or updated").
   - **Cura immediata (runtime, additiva, reversibile):** `playwright install chromium` nel
     venv → chromium-1223 (169MB) + chromium-headless-shell-1223 (92MB).
   - **Verifica LIVE (gate green per la ragione giusta):** smoke-test diretto sul venv →
     `SMOKE_OK chromium_version=148.0.7778.96 screenshot_bytes=8807`. Il browser lancia
     headless e renderizza. (La run launchd post-kickstart mostrava il traceback STALE perché
     "no pending drafts" → non aveva lanciato il browser; lo smoke lo prova positivamente.)
   - **Antibody durevole (questa PR):** aggiunto al wrapper launchd di `html-apply`
     (`infra/launchagents/com.balizero.wr2.html-apply.plist`) un pre-flight idempotente
     `"$PY" -m playwright install chromium || (warn; proceed)` prima dell'`exec` — risponde al
     refuter ("manual install è un cerotto; il vero male è il venv non-provisioned"). Va live
     al prossimo install/sync del plist (plutil-lint: OK; non ho mut o a mano il launchd del
     daemon ora sano — rischio > beneficio per un future-proofing).

**Nessun'altra terapia shippata** — per disciplina: le restanti cure o non servono
(circuit-breaker, registrazione guardrails) o sono ambigue/confine-operatore o richiedono
review 4-LLM (ExecutionDriftGate) — vedi §Solo-operatore.

---

## §Solo-operatore (confini tracciati, fermato qui)

1. **Riaccendere Mini-Pro2** (fisico) — offline tailnet+LAN; consumer-group cross-machine giù
   (i daemon eventbus sopravvivono su redis locale, nessuna urgenza).
2. **`git pull` di `~/Desktop/nuzantara`** (162 commit dietro) — NON da me: ha lavoro
   non-committato → pull cieco rischia perdita (W50). È la RADICE del meta-pattern.
3. **Ship `ExecutionDriftGate` + sonda semantica** (contromisura strutturale) da sessione su
   checkout corrente, dopo review 4-LLM (tocca il meta-verifier).
4. **`cost_breaker.py` bridge al Fly PG `llm_cost_events`** — richiede DSN/secret (W71); è il
   vero `Esistere≠Armato` del run-plane (non risolvibile da read-plane).
5. **Attivare live il provisioning-guard di html-apply** — `infra/launchagents` install/sync
   del plist editato in questa PR (oppure lasciar propagare dal plist-watchdog).
6. **Decisione lifecycle plist Canva** (`canva-apply`/`canva-renderer` present-but-unloaded vs
   `canva-*-watchdog` loaded) — plist-watchdog logga exit 1 cosmetico tentando di rianimarli.
7. **`structlog` in pyenv 3.11.11** (intel-radar) + **`TELEGRAM_OWNER_CHAT_ID`** (sla-worker)
   — fix runtime/secret in organi confinanti.
8. **Pin `BZ_REDIS_HOST=127.0.0.1`** nei plist dei 4 daemon eventbus (fragilità latente §1).
9. **mcp_integrity**: dare ai 5 failures tollerati owner+expiry+set-di-id atteso (caveat §4).

---

## §Refuter (Mythos step 4-5) — verbatim sintesi

DeepSeek V4 Pro non disponibile (`402 Insufficient Balance`); cascade → **Codex GPT-5.5
(xhigh)**. I 5 colpi del refuter (tutti gated da me, validi):
1. **`cost_breaker_deadman` = theater candidate** ("fresh blindness is still blindness"). →
   accolto, declassato in §4.
2. **mcp_integrity** baseline = "normalized debt" senza owner/expiry/regression-boundary. →
   accolto, caveat §4 + §Solo-operatore #9.
3. **cost_breaker + html-apply = bug upstream reali, non read-plane drift.** → coerente con
   la mia classificazione (true-positive run-plane).
4. **html-apply manual install = symptom-patch; vera malattia = renderer deps non
   dichiarate/provisioned/CI-verificate** ("se `.venv-wr2-html` può esistere senza Chromium,
   non c'è invariante 'renderer is runnable'"). → accolto, **shippato** il provisioning-guard.
5. **Controesempio al meta-pattern:** `Letto≠Vivo` può overfittare; alcune ferite sono
   run-plane (vive ma semanticamente cieche). Il gate deve richiedere
   producer-SHA + checkout-path + **data-source-authority** + **live semantic probe**, non
   solo rifiutare i writer non-deploy. → accolto, raffina la contromisura §Meta-pattern.

**Verdetto refuter:** non distrugge il meta-pattern, lo **completa** — `Letto≠Vivo` resta la
malattia-delle-malattie per i falsi-allarmi, ma deve coesistere con `Esistere≠Armato` puro
del run-plane, e la cura ha bisogno di una sonda semantica oltre al SHA-drift.
