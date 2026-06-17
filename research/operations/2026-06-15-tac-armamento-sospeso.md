---
date: 2026-06-15
domain: operations
client_case: false
sources:
  - "6 sweep diagnostici paralleli (Explore) — immunità/nervi/contenuti/intake/scheletro/PR-memoria"
  - "Gate scettico Opus su disco (git/launchctl/gh) — ribaltati 3 falsi-loop dei subagent"
  - "Sintesi 2° ordine Gemini 3.5 Flash High (agy)"
  - "Refuter adversariale DeepSeek V4 Pro (reasoning_effort=high)"
  - "memory decision_armamento_sospeso_metapattern_2026_06_15.md"
method: skill opus-mythos (8 passi)
---

# TAC organismo — la Sindrome dell'Armamento Sospeso (2026-06-15)

## §0 — Executive

TAC Mythos su mandato "chiudere tutti i loop + trovare i mega-pattern". 6 sweep
paralleli per apparato → gate scettico su disco → sintesi 2° ordine (Gemini) →
refuter (DeepSeek) → cura interlacciata. **Il pattern di secondo ordine che
attraversa TUTTI gli organi è uno solo**: l'organismo COSTRUISCE benissimo
(PR verdi, fix, engine, cron, spec) ma lascia inerte il **last-mile di
ATTIVAZIONE** del runtime fisico. Battezzato (Gemini) **"Sindrome dell'Armamento
Sospeso"**. Manifestazione più grave trovata: **un intero deploy worktree
(`~/Desktop/nuzantara-deploy`) era sparito**, rompendo silenziosamente ~20 cron
critici (intake, WhatsApp, cost-control, guardian) — tutti "armati a vuoto" su un
host morto.

## §1 — Organi (post gate scettico)

I subagent hanno prodotto LEAD; il gate del padre (re-grep su disco) ha
**ribaltato 3 conclusioni**:
- "50 PR, zero mergeabili / CI apocalypse" → FALSO: Snyk non è required-check;
  ~14 PR avevano i 18 required verdi (di cui 13 erano spec-spam di un loop, 1 reale).
- "cost-breaker fresco e funzionante" → FALSO: era log storico; `launchctl` lo
  dava `last exit code 127` (path ghost).
- "dirty main da cron, benigno" → confermato cron-generated MA è il carburante di
  un loop runaway (vedi Meta-pattern).

| Apparato | Loop chiave verificato |
|---|---|
| Immunità | DLQ-autopilot/sentinel scritti ma `launchctl`-disabilitati; 30 job TERMINAL 9gg; antibody non armati |
| Nervi | ~20 plist → host ghost `nuzantara-deploy` (exit 127/78/2); split-brain wr2-telegram-gate; DNS Telegram down |
| Contenuti | engine WR2 mergeato (#1236) ma kill-switch mai flippato; renderer privo di `.venv-wr2-html` |
| Intake | deploy venv vuoto → intake-worker/wa-mirror down (asyncpg mancante); fire-test mai eseguito |
| Scheletro | fix W79 non propagato a Mini (offline); Pro `main` 175 commit dietro origin; 89 branch graveyard |
| PR/memoria | 13 PR-spam notturne auto-generate dal loop; MEMORY.md ok |

## §Meta-pattern — il vero topic (post panel asimmetrico)

**Sindrome dell'Armamento Sospeso (Last-Mile Activation Gap).** L'organismo ha una
barriera impermeabile tra il *piano logico* (produrre artefatti in sandbox) e il
*piano fisico* (mutare il runtime: `launchctl`, kill-switch, merge, propagate,
commit). Il "successo" per gli agenti è definito come "ho prodotto un artefatto",
non "ho attivato". Di fronte allo stato non-attivato, gli agenti producono
**altri** artefatti (13 PR notturne che *triageano* il dirty-main invece di
pulirlo) → il backlog si gonfia invece di chiudersi.

**Raffinamento dal refuter (DeepSeek), accolto** — distinguere due last-mile:
- **FIREBREAK (sano)**: publish IG (Legge 5), flip kill-switch di business, secret
  rotation → fermarsi all'umano è DESIGN CORRETTO, non malattia.
- **PATOLOGICO (la malattia)**: merge PR 100%-verdi, propagate fix mergeato,
  install watcher scopato, **ricreare un deploy worktree sparito**, arm daemon,
  commit dirty cron. Qui nessun firebreak giustifica l'inerzia e **la capacità
  esiste** (provato: in-sessione ho mergeato #1427 e ricreato il worktree).

Il refuter ha ragione anche sul fatto che **la contromisura non è "auto-attivare
tutto"** (suicidio operativo: auto-flip = falsi positivi spengono produzione).
La cura giusta:
1. **Fix radice del loop**: il cron NB-UUID-reconciler che riscrive `.py` tracked
   senza committare → main dirty perenne → spark-alarm runaway. (Fermato il loop, resta da fixare il cron.)
2. **Reconciliation REPORT** (segnalatore, non attuatore): allarme su
   "costruito-ma-non-attivato >48h", separando firebreak da debito-tecnico.
   Estende la superscar #2 "Esiste≠Armato": il guardiano deve leggere lo STATO DI
   ATTIVAZIONE, non solo l'exit code.
3. **Self-heal del deploy worktree armato** (oggi `wr2-deploy-pull` "self-heal
   failed" silenziosamente — Armamento Sospeso anche dell'auto-riparazione).

## §Terapia eseguita (autonoma, in-sessione)

1. ✅ **Loop runaway fermato**: `launchctl bootout`+`disable` flotta
   `codex-spark-alarm/spark-loop/spark-harvester/overnight-feeder/overnight-runner`.
2. ✅ **13 PR-spam chiuse** (`codex-overnight/spark-alarm-*`) con commento root-cause; branch conservati.
3. ✅ **#1427 merged** (a11y reale, unico lavoro vero tra le 14 "merge-ready").
4. ✅ **Deploy worktree RICREATO** (`git worktree add ~/Desktop/nuzantara-deploy deploy/main`)
   → ripara ~20 cron in un colpo senza toccare un plist. Verificati **exit 0**:
   cost-breaker, cost-breaker-deadman, mcp-integrity, verify-the-verifiers,
   merge-train, review-gate, lead-intent-matcher. (È in protect-list del GC.)
5. ✅ **Spark worktree orfano rimosso** (guard W80: 0 processi vivi).
6. ✅ Meta-pattern + provenance salvati in memory.

## §Solo-operatore (residui tracciati — NON eseguiti, con motivo)

- **Deploy venv vuoto** (7 vs 804 deps) → intake-worker/wa-mirror down.
  `cd ~/Desktop/nuzantara-deploy/apps/backend-rag && source .venv/bin/activate && pip install -r requirements.txt` (+ build cv2/playwright). **Production WA + build pesante → supervisionato.**
- **WR2 flip #1236**: BLOCCATO da `.venv-wr2-html` mancante. NON flippato (avrebbe
  spento Canva senza renderer → caroselli rotti). Campagna 18/06 già coperta
  dall'articolo LIVE. Path: runbook `docs/runbooks/wr2-html-cutover.md` → crea
  `.venv-wr2-html` → verifica `wr2.html-apply` exit 0 → flip `system_settings.wr2_html_renderer_enabled` → QA.
- **DNS Telegram down sul Pro**: `Could not resolve host: api.telegram.org`
  (rompe oss-monitor alert + wr2-deploy-puller). Verificare rete/NordVPN (cf. lessons_nordvpn_tailscale_block).
- **Pro `main` 175 commit dietro origin** + dirty cron-generated: ora benigno
  (spark fermo). Allineare: `git fetch && git reset/pull` quando sicuro (decidere su eventuale lavoro locale).
- **W79 → Mini**: Mini offline; propagare hook al ritorno.
- **DLQ 30 job TERMINAL** (no fix_pattern) + escalations stale: revisione manuale.
- **Perché il deploy worktree è sparito** (non dal GC, è protetto): causa ignota — sorvegliare ricomparsa.

## §Metodo
opus-mythos 8 passi. Panel asimmetrico (Gemini propone 2° ordine, DeepSeek
distrugge, Opus giudica su disco). Il refuter ha migliorato la tesi (firebreak vs
debito-tecnico) — il valore del MAI-consenso.
