---
date: 2026-09-05
domain: operations
client_case: none — internal CI/PR-cycle-time study (session M5, mandato Zero: "studia come diminuire drasticamente il tempo delle PR")
adversarial_review: codex
sources: gh api / GraphQL live measurement of Bali-Zero/Teman2 (this session, 30 merged PRs + live merge-queue config introspection) + code reading of .github/workflows/security.yml, tests.yml, scripts/ci/change_map.py (this session) + GitHub Docs (merge queue, branch protection status checks, CodeQL workflow config, codeql-action dependency-caching) + community sources on Nx/Turborepo affected-testing and flaky-test quarantine (marked search-only) + Codex GPT-5 red-team on the draft (§ Adversarial review)
---

# Diminuire il tempo delle PR — dove va il tempo e cosa si può togliere

> Mandato Zero, 2026-09-04/05: «studia come diminuire drasticamente il tempo delle PR».
> Metodo: non ripartire dalle cifre della sera del 4/9 (110-114 CPU-min, 15-17 min wall, 12
> contesti richiesti) — rimisurarle sul repo vivo con `gh api`, poi confrontarle con ciò che
> fanno i migliori (merge queue, monorepo affected-testing, CodeQL, cache) e proporre un piano
> classificato per leva. Tabelle grezze: `2026-09-05-pr-cycle-time-diet-lane-measurements.md`.

## 0. Executive summary

- **Il campione misurato è caduto per intero nella finestra "classificatore CI morto".** 30 PR
  merged il 4/9 (08:21-15:35 UTC); il fix che lo rianima (#5692) è arrivato solo alle 16:25:30Z.
  Risultato: anche tre PR puramente-documentarie (solo `.md`) in questo campione hanno pagato
  Backend Shard×3, Frontend Tests, E2E Tests e Visa Oracle per intero (5-12 min ciascuno) — SOLO
  CodeQL (classificato in un workflow diverso, indipendente) si è fermato correttamente. Questo
  non è il regime "a riposo" del repo: è il caso peggiore, ed è quello che il numero mediano sotto
  descrive.
- **Anche così, mediana open→merge 35,2 min, media 50,0 min** (30 PR, min 28,3 · max 173,1).
  110,7 CPU-minuti/PR sul run della PR (conferma quasi esatta dei 110-114 osservati la sera
  prima su un'altra PR) più **136,3 CPU-minuti/PR nella coda di merge** — il re-run in coda
  costa PIÙ del check originale. CodeQL Analysis (python) è il check più lento su 19/30 PR (63%)
  e vale da solo una mediana del 34% del wall time totale della PR.
- **Un moltiplicatore reale, ma solo parzialmente spiegato, è la coda di merge.**
  `mergeQueue.configuration` (letta live via GraphQL): `mergingStrategy: ALLGREEN`, batch fino a
  5 PR, `minimumEntriesToMerge: 4` con fino a 15 minuti di attesa per raggiungerlo. 9 PR su 30
  (30%) hanno avuto un secondo tentativo di `merge_group`; di questi, 5 mostrano un `cancelled`
  PRIMA del tentativo che ha permesso il merge — un pattern coerente con un batch fallito che ha
  bloccato il PR — e questi cinque includono 4 dei 6 outlier oltre i 60 minuti. Gli altri 2
  outlier (incluso il peggiore, 173 min più uno da 116 min senza alcun secondo tentativo
  registrato) NON sono spiegati da questo pattern (dettaglio in §5 del file-lane). `HEADGREEN`
  è l'alternativa che GitHub stesso descrive (testo dell'enum letto live, non la pagina doc
  dedicata che ha risposto 404 in questa sessione) — il meccanismo esatto va verificato dalla UI
  prima di usarla.
- **Tre bersagli per un PR banale** (§5): da un caso peggiore osservato di 28,3-33,7 min, a
  ~9-26 / ~2-8 / ~2-6 minuti (certo / base / stretch, range non punti — n=3 misurazioni),
  aritmetica tracciata riga per riga in §5. Il pavimento condiviso da tutti e tre è un contesto
  RICHIESTO (`Immune enforcement`, "antidotes") che nessuna leva qui tocca. Le leve più grandi
  (batching della coda, dedup del merge_group, gating di VOA) sono decisioni di Zero; le più
  sicure (classificatore robusto, path-gating advisory, cache) sono spedibili dalla sessione via
  Gear 3.

## 1. Cosa dice la misura (30 PR, dettaglio in `-lane-measurements.md`)

| Metrica | Valore |
|---|---|
| Open→merge, mediana / media | 35,2 / 50,0 min |
| CPU-min/PR, run della PR | 110,7 (media) |
| CPU-min/PR, coda di merge | 136,3 (media) — **più** del run della PR |
| Check più lento più frequente | CodeQL Analysis (python), 19/30 PR (63%) |
| Quota mediana del wall time dal check più lento | 34% |
| PR ricacciati in coda ≥1 volta (batch ALLGREEN fallito) | 9/30 (30%) |
| Job che finiscono sotto i 90s | 53/72 nomi distinti — costo dominato dal cold-start del runner, non dal lavoro |
| Check per PR (conteggio a livello di run) | mediana 62 (range 57-67) |

Le tre PR di solo-`.md` nel campione (#5680, #5658, #5672 — nessun file Python/JS/backend/
frontend) hanno comunque pagato 28,3-33,7 minuti di wall time (28,3 · 29,5 · 33,7 — media 30,5)
perché tests.yml stava fallendo aperto (`run_all=True`, il default fail-safe quando l'estrazione
del classificatore fallisce — vedi §2). Solo il gate di CodeQL, che vive in un workflow
indipendente (`security.yml`, `RUN_THIS_LANGUAGE` per-step, non collegato allo stesso corpus
rotto), ha funzionato: CodeQL Analysis (python) ha finito in 18-27s su queste tre invece dei
consueti 11-15 min. Tutti gli altri job pesanti — Backend Shard×3, Frontend Tests (mouth), E2E
Tests, PIÙ Visa Oracle fullstack smoke, che NON fa parte del classificatore di `change_map.py`
(§4, L5/L7) — hanno girato per intero anche su queste tre PR puramente documentarie.

## 2. Diagnosi: il classificatore era morto per l'intero campione

`scripts/ci/change_map.py` classifica ogni path in uno di 11 domini; `docs_content_data` (che
include `docs/`, `research/`, `.claude/skills|rules|commands|agents/`, `evidence/`) non guadagna
NESSUNO dei sei `TEST_JOBS` del modulo (letti dal sorgente in questo turno, nome esatto della
costante): `backend-tests`, `mcp-tests`, `evaluator-critical-tests`, `frontend-tests`,
`packages-core-tests`, `e2e-tests` (`_suggested_jobs()`). **Visa Oracle fullstack smoke non è in
questo elenco** — non è gestito da `change_map.py` e ha girato per intero su tutte e 30 le PR del
campione, incluse le tre di sola documentazione (§1); lo stesso vale per gli scanner advisory
(Snyk×3, npm audit, SAST, Detect Secrets — §4 L5). Il meccanismo dei sei `TEST_JOBS` è corretto —
la sua ESECUZIONE non lo era:

- **#5676** (merged 15:32:20Z) ha corretto un corpus morto da 9 giorni: "ogni PR ha girato ogni
  job" (titolo della PR, letto in questo turno).
- **#5679** (merged 14:59:02Z, PRIMA di #5676 nonostante il numero più alto — l'ordine di merge
  non segue l'ordine dei numeri PR) ha esteso la classificazione di `scripts/**`.
- **#5692** (merged 16:25:30Z) ha corretto un secondo guasto introdotto dalla combinazione delle
  due: "every PR since #5679 ran all six heavy jobs" (titolo della PR, letto in questo turno).

Il campione di 30 PR di questo report (08:21-15:35Z) è quindi interamente compreso nella
finestra rotta. Cicatrice #2 (Esiste≠Armato): il meccanismo di path-gating esiste nel codice da
prima di oggi, ma non era ARMATO per nessuna delle 30 PR misurate. Alle 09:05 di oggi (2026-09-05,
quando questo report viene scritto) nessuna PR è stata ancora creata e fusa contro una base che
porta #5692 — il repo non ha ancora prodotto un esempio dal vivo di "PR di documentazione con
zero job pesanti". **Questa stessa PR (research-only, tocca solo `research/**` ed
`evidence/**`) è il primo caso reale**: l'osservazione dal vivo del suo proprio run è nella
sezione Bites del corpo della PR, non in questo file (il file è scritto prima che il run esista).

## 3. Cosa fanno i migliori (fonti fetchate; le non-fetchate sono marcate search-only)

**3.1 GitHub, status check "skipped" = passing.** Un check richiesto che viene skippato via
path-filter riporta `success`/`skipped`/`neutral` e NON blocca il merge — la doc lo conferma
(troubleshooting required status checks); una discussione della community lo chiama esplicitamente
un problema quando il path-filter è a livello di WORKFLOW (il job non parte affatto e il contesto
non riporta mai, restando "in attesa" per sempre). Il pattern corretto — quello che
`security.yml` già usa per CodeQL — è: il JOB parte sempre (soddisfa il contesto richiesto), solo
gli STEP costosi sono condizionati. `tests.yml` usa lo stesso pattern per i sei job pesanti.

**3.2 GitHub, merge queue.** Introspezione GraphQL live (non dalla doc, dal repo stesso, §1
lane-file): `checkResponseTimeout` 5400s (soffitto raramente toccato), `mergingStrategy` con due
soli valori enum (letti live): `ALLGREEN` ("Entries only allowed to merge if they are passing")
e `HEADGREEN` ("Failing Entries are allowed to merge if they are with a passing entry").
`minimumEntriesToMerge`/`minimumEntriesToMergeWaitTime` sono documentati altrove (ricerca
web, non verificati sulla pagina ufficiale — quella specifica pagina ha risposto 404 in questa
sessione) come il meccanismo che aspetta fino a N minuti un quorum di PR prima di aprire un
batch; la guida generica trovata suggerisce "1 e 0 a meno di 20+ PR/giorno" — soglia che questo
repo supera nel campione misurato (30 PR in 7 ore).

**3.3 Monorepo affected-only testing** [search-only, cifre di terzi]. Nx/Turborepo calcolano
l'insieme "affected" dal grafo delle dipendenze, non da un file di regole scritto a mano come
`change_map.py`; un caso citato riporta una CI da 45 a 4 minuti saltando l'80% dei task. Il
nostro `change_map.py` è lo stesso principio (path→dominio→job) ma manuale e quindi fragile al
tipo di rottura di §2 — un grafo derivato da import reali non avrebbe un "corpus" da tenere
sincronizzato a mano.

**3.4 CodeQL, cadenza e caching.** La doc ufficiale raccomanda `pull_request` come trigger
primario ("we recommend that you configure code scanning to analyse all pull requests"), NON
solo schedule — quindi spostare CodeQL fuori dal path della PR (come inizialmente ipotizzato nel
mandato) andrebbe contro la pratica raccomandata; il repo ha già la soluzione raccomandata
(path-gating per-step, non per-job). La leva restante è interna al job: `codeql-action/init@v4`
supporta `dependency-caching: true` (verificato sulla issue/changelog del repo `codeql-action`,
non sulla pagina docs ufficiale che non è stata fetchata) — introdotto per Java/dipendenze
pesanti; l'impatto su un linguaggio interpretato come Python (nessun passo di build) NON è
verificato in questa sessione e va misurato prima di contarlo come certo. C'è anche una cache
overlay-base per l'incremental analysis, citata dal changelog ma non approfondita qui.

**3.5 Flaky-test quarantine** [search-only]. Pratica convergente (Google, Meta): rilevamento
automatico via flip-rate su commit invariato, quarantena in una suite non-bloccante con
owner+SLA+ri-qualificazione. Non misurato se questo repo ha test flaky nel senso proprio (i 3
`failure` e 7 `cancelled` su 1862 record del run-PR in §1 lane-file non sono stati classificati
causa per causa in questa sessione — richiederebbe leggere i log di ciascuno).

## 4. Piano — leve ordinate per minuti-risparmiati-per-PR ÷ (rischio+cerimonia)

| # | Leva | Meccanismo | Risparmio atteso | Rischio se rotto | Gear | Decide |
|---|---|---|---|---|---|---|
| L1 | Blindare il classificatore | test unitario sul corpus estratto simulando l'estrazione flat (così non può morire in silenzio una terza volta); rimuovere la maschera `continue-on-error: true` sullo step di estrazione (deve essere un segnale rosso visibile, non silenzioso); correggere l'f-string con virgolette escapate in `tests.yml` righe 400-407 (verificato leggendo il file in questo turno: sintassi illegale su Python <3.12 dentro `{}` di un f-string) | protegge, non sottrae: impedisce la ricaduta a run_all=True su OGNI PR, cioè protegge tutto il risparmio delle leve sotto | ALTO se assente — è già successo due volte oggi | 3 (edita `.github/workflows/tests.yml`) | sessione |
| L2 | Verificare dal vivo che `docs_content_data` salti i sei `TEST_JOBS` | nessuna modifica: osservare il run di QUESTA PR (§2) — se conferma, chiudere l'incertezza; se no, è un bug nuovo da aprire subito. Non copre Visa Oracle né gli scanner advisory, che non sono nel classificatore (§2) | conferma (o smentisce) i sei `TEST_JOBS` su ogni PR di sola documentazione — non tocca VOA/advisory (L5) | — | 0 (osservazione) | sessione |
| L3 | Coda di merge: `ALLGREEN`→`HEADGREEN` | il testo dell'enum letto via GraphQL ("failing entries allowed to merge if with a passing entry") suggerisce che un fallimento non cancelli l'intero batch, ma il meccanismo esatto non è verificato oltre quel testo (§ lane-file §5) | 4 dei 6 outlier oltre i 60 min (5650, 5651, 5653, 5674) mostrano un `cancelled` prima del tentativo riuscito — plausibile bersaglio, non certo | cambia la semantica di "cosa può finire in coda con un vicino rosso" — la pagina doc dedicata ha risposto 404 in questa sessione, verificare dalla UI prima di girare l'interruttore | 0 (impostazione repo, non workflow) | **Zero** |
| L4 | Coda di merge: `minimumEntriesToMerge` 4→1, `minimumEntriesToMergeWaitTime` 900s→60-120s | riduce l'attesa fissa di un PR che arriva con meno di 3 altri già in coda, da fino 15 min a 1-2 min | nessuno strutturale — solo più batch piccoli, più runner-minuti totali se il traffico è denso | 0 (impostazione repo) | **Zero** |
| L5 | Path-gating esteso: security/lint advisory (Snyk×3, npm audit, SAST, Detect Secrets) + Visa Oracle seguono lo stesso classificatore dei sei `TEST_JOBS` | oggi girano SEMPRE indipendentemente dal diff (misurato: girano anche su #5680/#5658/#5672) — 6 job advisory: 414,1 CPU-min/30PR nel run-PR (npm audit 149,0 + Snyk Node 74,8 + Snyk Docker 68,2 + Snyk Python 15,2 + SAST 89,6 + Detect Secrets 17,2); VOA da sola 173,1 CPU-min/30PR | ~2-6 min/PR di wall time per un PR di sola-doc (il job advisory più lento residuo, non la somma — girano in parallelo) | i job sono advisory (non nei 12 contesti richiesti) tranne VOA che LO è — gating VOA su un PR non-app è una scelta di prodotto, non solo tecnica | 3 (edita `security.yml` + il workflow VOA) | sessione per gli advisory; **Zero** per VOA (è required) |
| L6 | `merge_group`: non ri-eseguire i job non sensibili all'integrazione (CodeQL×2, Immune enforcement, npm audit, Detect Secrets, Snyk×3 — leggono il diff, non lo stato del backend/frontend) | dei 4090,1 CPU-min/30PR nella coda, 1394,4 min (34,1%) sono questi otto job, che il PR-run ha già eseguito sullo stesso diff poco prima | 46,5 CPU-min/PR in coda; wall time solo se uno di questi era il collo di bottiglia del batch | decisione di sicurezza (accettare di non ri-scansionare contro un base branch aggiornato) — la scansione schedulata copre comunque le derive del base | 3 (edita più workflow) | **Zero** (trade-off di sicurezza) |
| L7 | Consolidare le ~40 sentinelle/guardie sotto i 90s in UN workflow "fast-gates" con job multipli | oggi ogni sentinella è un run/workflow separato = cold-start del runner ripetuto ~40 volte; un solo workflow con più job condivide meno overhead di checkout/setup ripetuto se raggruppati per stack (python vs node) | qualche decina di secondi/PR — piccolo per singola PR, ma ~40 avvii di runner in meno per PR moltiplicato su tutta la coda | ceremonia alta (tocca ~40 file .yml), va fatto a piccoli lotti | 3 × N PR | sessione, spezzato in più PR |
| L8 | `cancel-in-progress` sui workflow che non ce l'hanno ancora | oggi 46/118 workflow ce l'hanno; estendere agli altri | 0 min sul primo push di un PR banale; utile su iterazioni con push rapidi | nessuno — pattern già in uso altrove nel repo | 3 | sessione |
| L9 | Un solo "gate" aggregato al posto di 12 contesti richiesti | un job fan-in che dipende (`needs:`) da tutti i job path-gated e riporta un solo stato; riduce le occasioni di finire "Expected — Waiting for status" per sempre (bug GitHub documentato dalla community quando un contesto non riporta mai) | pochi minuti di latenza di propagazione GitHub + elimina gli incidenti rari-ma-costosi di contesto bloccato (quando capitano, 10-60+ min di intervento manuale) | riduce la granularità dei fallimenti visibili in `gh pr checks` — serve un buon riepilogo nel job fan-in | 3, grande refactor | sessione, ma da pianificare come PR dedicata |

## 5. Tre bersagli per una PR banale (solo `research/**`, `docs/**`, `.claude/skills|rules/**`)

Baseline: 28,3-33,7 min (§1, tre PR misurate) — il caso PEGGIORE già misurato (classificatore
morto). Sotto, l'aritmetica riga per riga di cosa resta dopo ogni leva, usando le durate REALI
osservate su quelle tre PR per i job che NON sono nei sei `TEST_JOBS` (n=3, quindi un range, non
un punto — Codex ha giustamente bocciato una prima versione di questa tabella che dava un solo
numero "certo" senza mostrare la somma).

Cosa resta dopo aver tolto i sei `TEST_JOBS` (L1), dalle tre PR misurate: Immune enforcement
(superscar antidotes) 1,7-6,7 min · Visa Oracle fullstack smoke 3,8-10,6 min · npm audit
0,9-5,6 min · Detect Secrets 0,5-0,7 min · Change map (i due step di decisione stessi, non
eliminabili, ~1-1,6 min cad.) · Snyk×3 già vicino a zero (gating proprio, indipendente,
funzionante anche nella finestra rotta) · ~40 sentinelle sotto i 90s (mai il collo di bottiglia).
Questi girano in PARALLELO: il pavimento è il più lento fra loro, non la somma.

| Bersaglio | Wall time (range) | Come | Certezza |
|---|---|---|---|
| **Certo** | ~9-26 min | L1 toglie i sei `TEST_JOBS`; resta il job non-gated più lento fra Immune enforcement (1,7-6,7 min, è uno dei 12 contesti richiesti — "antidotes" — non gate-abile senza una decisione di prodotto) e Visa Oracle (3,8-10,6 min, anch'esso richiesto); l'attesa di coda resta INVARIATA (1-15 min, dipende da quanti altri PR sono in coda) | meccanismo confermato leggendo `change_map.py`; magnitudine da confermare dal vivo (L2, questa stessa PR — vedi §2) |
| **Base** (+L4+L5) | ~2-8 min | L4 abbassa il tetto dell'attesa di coda da 15 a ~1,5 min; L5 estende il gating a VOA/npm-audit/Detect-Secrets/SAST (tutti advisory tranne VOA), lasciando Immune enforcement (1,7-6,7 min, required) come unico job non comprimibile senza una decisione di prodotto | L4 è un'impostazione (Zero); L5 è una PR Gear 3 (sessione) per la parte advisory, decisione di Zero per VOA |
| **Stretch** (+L3+L9) | ~2-6 min | stessa aritmetica di Base — L3 e L9 non toccano il pavimento di Immune enforcement, riducono la CODA della distribuzione (meno batch-cancellation da assorbire, meno propagazione multi-contesto): il range si stringe, non si sposta molto verso il basso | L3 è una decisione di sicurezza/processo di Zero; L9 è un refactor Gear 3 non banale |

Il pavimento pratico condiviso da tutti e tre i bersagli è `Immune enforcement (superscar
antidotes)`, un contesto RICHIESTO che non è nel classificatore di `change_map.py` — nessuna
delle leve L1-L9 lo tocca; comprimerlo sotto i 1,7-6,7 min osservati è fuori dallo scope di
questo report (richiederebbe guardare dentro `immune-enforcement.yml`, non fatto qui).

L'aritmetica di L6 (deduplicare `merge_group`) non tocca il wall-time di UNA PR isolata — riduce
il CPU totale della flotta (46,5 CPU-min/PR), rilevante quando la coda è densa (il caso di questo
campione: 30 PR in 7 ore), non nel caso "una PR alla volta" usato per i tre bersagli sopra.

## 6. Limiti

Il campione è un singolo giorno ad alta velocità (30 PR in 7h14m) — mediane qui non sono medie
annuali. I tre bersagli di §5 poggiano su n=3 PR di sola-documentazione: sono un range osservato,
non una distribuzione. Il meccanismo di `HEADGREEN` è descritto solo dal testo enum letto via
GraphQL in questa sessione; la pagina doc dedicata (`managing-a-merge-queue`) ha risposto HTTP 404
al fetch, due volte, da due URL diversi — Zero dovrebbe verificarla dalla UI prima di girare
l'interruttore. `dependency-caching` su CodeQL non è stato misurato per Python; il changelog lo
descrive esplicitamente per Java. La causa dei 3 `failure` e 7 `cancelled` PR-event non è stata
letta log-per-log (nessuna prova che siano flaky-in-senso-proprio vs fallimenti reali). Il
conteggio "62 check/PR" di questo report e il "72-75" della sera prima usano regole di conteggio
diverse (§8 lane-file) — non è una contraddizione ma non ho riconciliato le due fonti a livello di
singolo check. Il pattern di re-code in coda (§5 lane-file) spiega 4 dei 6 outlier oltre i 60
minuti: PR #5650 (123,5 min) ha bisogno di un terzo tentativo non catturato da questa query, e
#5657 (61,0) / #5676 (116,4) NON sono spiegati dal pattern di batch-cancellation — la causa dei
loro tempi resta non identificata in questa sessione.

## Adversarial review

Seat: Codex GPT-5 (`codex exec --sandbox read-only`, contesto fresco, prompt red-team "trova il
difetto, default a difettoso"), sulla bozza precedente a questa versione. Verdetto: **BLOCK**,
10 finding (tutti major/blocker, nessun minor). Disposizione:

| # | Sev | Finding (sintesi) | Esito |
|---|---|---|---|
| 1 | blocker | matching `merge_group`→PR solo dal numero nel `head_branch`, senza verificare che un batch da 5 non condivida quel numero fra più PR | **respinto con prova**: nessun `head_sha` è condiviso fra due `pr_number` diversi sui 487 run (§ lane-file, metodologia) — il matching è per-entry, non per-batch |
| 2 | major | tabella dei 9 re-code incompleta/sbagliata (una riga con placeholder, un caso con la sequenza invertita) | **fixed**: tabella completa con tutte e 9 le righe reali, e il pattern misto (5 cancelled→success, 4 success→cancelled) descritto senza generalizzare (§ lane-file §5) |
| 3 | major | "HEADGREEN evita che un guasto ne cancelli altri quattro" presentato come certo | **fixed**: declassato a "testo dell'enum letto, meccanismo non verificato oltre quello"; il nesso causale con gli outlier ridotto a "4 di 6, non tutti e sei" |
| 4 | major | "stessi commit" fra run PR e run merge_group, più un claim di flakiness non provato | **fixed**: rimossa l'affermazione "stessi commit" (sono commit diversi per costruzione), rimosso il claim di flakiness non supportato (§10 lo dichiarava già non misurato — contraddizione interna corretta) |
| 5 | major | off-by-one su "meno di 4 altri" per `minimumEntriesToMerge: 4` | **fixed**: corretto in "meno di 3 altri già in coda" (il PR stesso conta come una delle 4 entry) |
| 6 | major | range "28-37 min" non corrisponde ai tre valori reali (28,3/29,5/33,7) | **fixed**: sostituito con i tre valori esatti ovunque compaia |
| 7 | major | "5 job pesanti" enumerati come 6 voci, con Visa Oracle scambiato per uno dei sei `TEST_JOBS` | **fixed**: elencati i sei `TEST_JOBS` esatti dal sorgente (`backend-tests, mcp-tests, evaluator-critical-tests, frontend-tests, packages-core-tests, e2e-tests`), VOA esplicitamente segnalato come NON incluso; verificato anche che `backend-static` condivide il gating (era erroneamente nella lista "residua") |
| 8 | major | bersaglio "Certo" = 22 min presentato come certo mentre la riga stessa ammette che serve conferma dal vivo | **fixed**: tabella di §5 riscritta come range (9-26 / 2-8 / 2-6), con l'aritmetica dei job residui mostrata riga per riga dai dati reali delle tre PR, non un numero singolo |
| 9 | major | passo "Base" (22→12, cioè -10) non riconciliabile con "-13 min" dichiarato per L4 | **fixed**: stessa riscrittura del punto 8 — ogni passo ora mostra la somma dei componenti, non una sottrazione isolata |
| 10 | major | somma "149+75+68+90=~380" per 5-6 job nominati ma solo 4 numeri usati | **fixed**: ricalcolato con tutti e 6 i job nominati (npm audit, Snyk Node/Docker/Python, SAST, Detect Secrets) = 414,1 CPU-min/30PR nel run-PR, numero verificato via script (non a mano) |

Nessun finding scartato senza fix: tutti e 10 hanno prodotto una modifica al testo o ai dati. Non
richiesto un secondo giro — le correzioni sono verificabili contro i dati grezzi in
`-lane-measurements.md`, non contro un nuovo giudizio soggettivo.
