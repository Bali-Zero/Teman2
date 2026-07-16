---
name: sota-architecture-loop
description: Use BEFORE architecting code, designing a feature, or making a structural/architectural decision. Evidence-backed 8-step loop (frame → ground → reason → council → decision-gate → execute → verify → capture) that improves on a naive 'reason → council → research → brainstorm' loop. Decides WHEN to invoke the multi-LLM council vs single-orchestrator, and runs review as asymmetric-adversarial (never consensus). Orchestrator-agnostic: works whether Claude, Codex, or Gemini drives.
allowed-tools: Read, Write, Edit, Bash, Skill, Agent, WebFetch
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# SOTA Architecture Loop

Procedura per architettura codice + feature design con orchestrazione multi-LLM.
Evidence-backed (paper 2024-2026), non opinione. Fonti + verifica in
`research/operations/2026-05-30-sota-ai-architecture-methodology.md`.

**Tre regole da cui tutto deriva** (verificate, vedi research file):

> Eterogeneità batte numerosità · Adversarialità calibrata batte consenso · Verifica esterna batte autodichiarazione.

---

## Il loop (8 step)

```
0. FRAME      Orchestratore solo. Decomponi: deciso / da-decidere / vincoli. 1 spec scheletro.
1. GROUND     Verità ESTERNA ai priors, PRIMA di ragionare. La fonte dipende dal dominio:
              · normativo/fattuale → NotebookLM (NB) + deep research
              · INTERNO al repo (infra, codice, cron, debt) → disk-state: ls/Read/grep/git/launchctl/log
2. REASON     Orchestratore reasoning sui fatti del passo 1 (mai sul training).
3. COUNCIL    SOLO se il gate sotto dice sì. Eterogeneo + asimmetrico. Mai consenso, mai cloni.
4. DECISION   Kill gate: go / no-go / defer + 1 metrica falsificabile.
5. EXECUTE    TDD, worktree isolato (agent_start.py), commit atomici.
6. VERIFY     Adversariale + EMPIRICO esterno (Codex sandbox / pytest / verify skill).
7. CAPTURE    Scar/lesson (cicatrix-scars.md / mem save).
```

**Perché ground PRIMA di reason/council**: se ragioni sui priors di training, allucini (KBLI, normativa, API)
— o ragioni su una premessa STALE (una cicatrix che dice "non esiste X" quando X è stato shippato ieri).
Il ground non è solo RAG: è qualunque verità esterna ai tuoi priors. Per un dominio normativo = NB+web;
per un debt interno = lo STATO DEL DISCO (lo script esiste già? il cron passa davvero `--apply`? cosa dice
il log?). RAG è il grounding #1 per fatti esterni; `ls`/`Read`/`git`/`launchctl` lo è per fatti interni.
**Test empirico W62 (2026-05-30)**: questo step ha ucciso una feature fantasma in 3 tool call — la cicatrix
diceva "fix NOT shipped", il disco diceva "shippato ma disarmato da un flag mancante". Mai fidarsi del
ricordo (proprio o di una cicatrix): verifica lo stato reale prima di progettare.

---

## STEP 3 — Quando convocare il council (e quando NO)

Il council multi-LLM costa **~15× i token** di un singolo agente (dato Anthropic). Non è gratis e
spesso NON migliora. Convocalo **solo se TUTTE e tre vere**:

1. **Priors diversi possono cambiare la risposta.** La domanda dipende da conoscenza dove
   modelli con training diverso divergono (normativa, regolamenti, fatti recenti, API esterne).
   Se la decisione è meccanica/deducibile dai fatti groundati → 3 LLM convergono → paghi 15× per conferma.
2. **L'errore costa più di 15× token.** Pre-deploy critical path, migration, quote cliente,
   decisione architetturale irreversibile, spesa reale. Se rollback è gratis → non serve.
3. **Il lavoro è davvero parallelo / breadth.** Più angoli indipendenti da coprire insieme.
   (Anthropic: il multi-agente vince su _research_, MA "coding ha meno task parallelizzabili".)

### Tabella decisione

| Situazione                                                        | Council? | Cosa fare invece                                       |
| ----------------------------------------------------------------- | -------- | ------------------------------------------------------ |
| Decisione architetturale irreversibile (DB schema, auth, billing) | ✅ SÌ    | council eterogeneo asimmetrico                         |
| Quote cliente / spec con numeri normativi                         | ✅ SÌ    | + NB-1/4/5 come 4° panelist ground-truth               |
| Pre-deploy critical path                                          | ✅ SÌ    | red team obbligatorio (cf. federation triggers)        |
| Feature isolata, fatti già groundati, rollback facile             | ❌ NO    | orchestratore-solo + più budget reasoning + 1 red-team |
| Refactor lineare 1-2 file                                         | ❌ NO    | orchestratore-solo + 1 spalla (un LLM ≠) sul diff      |
| Bug fix con causa nota                                            | ❌ NO    | systematic-debugging skill, no council                 |
| Task meccanico (format, lint, rename)                             | ❌ NO    | esegui e basta                                         |

### Anti-pattern del council (evidence-backed)

- **N-cloni dello stesso modello** = groupthink. Su 7-8B il debate omogeneo collassa: sycophancy
  fino 85.5%, abbandona risposte corrette fino 70%, e un _singolo_ agente con 10× budget lo batte
  a 1/3 del costo. → Council **solo eterogeneo** (modelli con training diverso: Claude / Gemini / DeepSeek / Codex), mai N-cloni dello stesso modello (es. Claude×3 o Codex×3).
- **Panel grande + tanti round** = più conformity. Shrink maggioranza 6→3 dimezza il conformity;
  1→5 round lo alza. → 3 panelisti, round cappati (adaptive stop), non "discutete finché concordate".
- **Council prima dei fatti** = ragiona su allucinazioni. → sempre dopo STEP 1.

---

## STEP 3/6 — Review adversariale asimmetrica (cos'è davvero)

**Il consenso è la cosa SBAGLIATA.** Davanti a una maggioranza errata gli LLM non solo cedono —
**fabbricano reasoning** per giustificare il cambio (conformity → hallucination, verificato).
"Siete tutti d'accordo?" non nasconde solo l'errore: ne _genera di nuovi_. Mai chiudere per consenso.

"Asimmetrica" = due assi distinti (è qui che si sbaglia):

### Asse 1 — asimmetria di RUOLO (chi fa cosa)

Nessuno valuta sé stesso. Tre ruoli separati, **ognuno su un LLM DIVERSO** (è il _diverso_ che conta,
non quale — l'orchestratore può essere Claude o Codex a seconda di chi guida la sessione):

| Ruolo           | Compito                                                                                                                      | Vincolo                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| **Proponente**  | produce la tesi / il diff / la spec                                                                                          | è l'agente/LLM che sta lavorando — chiunque guidi |
| **Red-team**    | prova a DISTRUGGERE: buco legale, numero sbagliato, regolazione mancante, contraddizione frase-A vs frase-B, KBLI allucinato | LLM ≠ proponente                                  |
| **Costruttivo** | NON distrugge: prova a SALVARE migliorando — edge case, naming, semplificazione                                              | LLM ≠ proponente, idealmente ≠ red-team           |

**Regola vincolante: i tre ruoli su tre modelli diversi** (priors di training diversi = il valore).
Quali modelli è secondario e fungibile. Se Codex orchestra, allora proponente=Codex, e
red-team/costruttivo vanno su Claude + Gemini + DeepSeek (qualsiasi due ≠ Codex). Se Claude orchestra,
red-team/costruttivo su Gemini/DeepSeek/Codex. **Anti-pattern: proponente e critico sullo stesso modello**
(auto-approvazione mascherata).

Il giudizio finale è di **chi orchestra** (l'LLM lead, chiunque sia) o un gate empirico (STEP 6),
**mai** del proponente quando proponente = orchestratore: in quel caso il verdetto lo dà il gate empirico.

### Asse 2 — asimmetria di INCENTIVO (come sono premiati)

Il prompt deve invertire l'incentivo, altrimenti collassano sul "sì, ottimo":

- **Red-team premiato se TROVA un difetto**, non se conferma. Prompt: _"Default a 'difettoso' se
  hai dubbi. Il tuo lavoro è trovare il flaw, non approvare. Se non trovi nulla, cerca più a fondo."_
- **Costruttivo premiato se SALVA l'idea** migliorandola, non se la elogia. Prompt: _"Assumi che
  l'idea vada fatta; il tuo compito è renderla difendibile, non giudicarla."_
- **Mai** un prompt simmetrico "valuta questa proposta" → produce sycophancy.

### Calibrazione (non puro-adversariale, non puro-consenso)

Il debate batte la self-reflection perché evita la "Degeneration-of-Thought" (un modello sicuro
di sé non genera pensieri nuovi). MA troppa adversarialità degrada quanto il consenso. Mix ottimale =
**1 troublemaker forte (red-team) + 1 peacemaker (costruttivo)**, non 4 che si massacrano né 4 che annuiscono.

### Chiusura: gate empirico, non autodichiarazione

Il segnale "fatto/solved" dell'agente è inaffidabile (gli agent marcano risolte cose che non lo sono).
→ STEP 6 chiude con **prova esterna**: `pytest`, Codex sandbox, `verify` skill, curl 200.
Mai "è finito" detto dall'agente che l'ha fatto. (cf. cicatrix premature-completion.)

---

## Mapping rapido sullo stack

> "L'orchestratore" = l'LLM che guida la sessione (Claude **o** Codex **o** Gemini). I nomi qui sotto
> sono i candidati abituali per ruolo, non assegnazioni fisse. La sola regola dura: nel COUNCIL e nella
> review, i ruoli stanno su modelli **diversi tra loro**.

| Step       | Strumento / chi                                                                                                                                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0 FRAME    | orchestratore + `karpathy-discipline` skill                                                                                                                                                                                            |
| 1 GROUND   | normativo/fattuale: `notebook_query` (NB) + `deep-research` / `federation_orchestrator search`. INTERNO: `ls`/`Read`/`grep`/`git worktree list`/`launchctl print`/tail log — lo stato del disco È il ground                            |
| 2 REASON   | orchestratore                                                                                                                                                                                                                          |
| 3 COUNCIL  | fan-out su ≥3 modelli diversi (pool: Claude, Gemini/agy, DeepSeek, Codex). 1 red-team (`devils-advocate`) + 1 costruttivo (`spalla`/`codex-second-opinion`); NB-dominio come ground-truth panelist se UUID noto. Ruoli ≠ orchestratore |
| 4 DECISION | orchestratore — go/no-go/defer + metrica (Symbiosis L7)                                                                                                                                                                                |
| 5 EXECUTE  | `agent_start.py` worktree + `test-driven-development` skill                                                                                                                                                                            |
| 6 VERIFY   | gate empirico esterno: `pytest` / Codex sandbox / `verify` skill / curl 200 — indipendente da chi ha scritto                                                                                                                           |
| 7 CAPTURE  | `scar` skill / `mem save`                                                                                                                                                                                                              |

## Scorciatoie (NON è dogma)

- Task triviale → salta al solo STEP 5-6. Il loop completo è per decisioni che pesano.
- Già groundato in sessione → non rifare STEP 1.
- Dominio puramente creativo (non fattuale) → STEP 1 conta meno; lì reason-prima può andare.
- **Debt interno / "sistemiamo X"** → STEP 1 = disk-state, NON RAG. Prima domanda sempre: "X esiste già?
  funziona davvero?". NB/web qui sono rumore. (W62: la feature esisteva ma girava disarmata.)
