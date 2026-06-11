# PEZZO 5 — SPEC come artefatto-cardine (Spec-Driven Development onesto)

> **Spec studio (non implementazione).** Ciclo calibrato: reuse-first (disk-state + git history
> VERIFICATI) + council 2-LLM (Gemini red-team / DeepSeek logic-costruttivo). Pezzo 5 di 9. **Meta**:
> questa spec riguarda il processo che la sta producendo.
>
> **Riformulazione-chiave (DeepSeek)**: l'SDD NON è "la spec genera il codice" (irrealistico per un
> repo vivo con 50 spec già parzialmente stale). È **"ogni decisione architetturale è una spec
> tracciabile, falsificabile e storicamente immutabile"**. La spec è un **ADR rafforzato** (Architecture
> Decision Record) — preserva la *memoria decisionale*, non descrive il presente.

---

## 0. La correzione che precede tutto — il ruolo ONESTO della spec

Il design iniziale assumeva implicitamente l'SDD-forte (la spec è la fonte di verità da cui discende
il codice). Il council l'ha demolito da due lati:

- **Red-team #6 (CRITICA)**: 50 spec versionate **decadono** man mano che il codice evolve. Una spec
  non aggiornata che descrive un sistema cambiato è una **bugia autorevole** — lo stesso meccanismo
  delle cicatrici che allucinavano `file:line` (autorevoli e false). Il design aggiunge spec ma ignora
  il decadimento di quelle esistenti.
- **DeepSeek #3 (risoluzione)**: la tensione "spec-è-verità" vs "spec-che-decade" si scioglie
  **abbandonando la pretesa descrittivo-generativa**. La spec è un **artefatto di decisione
  immutabile**: cattura ragionamento + panel + gate + motivazioni *al momento della decisione*. Non
  promette di rappresentare il codice attuale. **Una spec così non decade**: smette di essere "mappa
  del presente" e diventa "mappa della decisione-di-allora", sempre vera per quel momento. Quando il
  codice cambia radicalmente, non si *modifica* la vecchia spec — si crea una nuova che la **supersede**
  (il campo `supersedes_partial`, che il frontmatter reale del repo già usa).

Questo è il cardine del pezzo. Tutto il resto discende da questa ridefinizione: **spec = ADR
rafforzato, immutabile, con verdetto-panel e gate-falsificabili dell'epoca, collegato ai test che
all'epoca verificavano quei gate**. La tracciabilità spec→codice→test diventa una *catena di
giustificazione storica*, non una *garanzia di corrispondenza sincrona*.

---

## 1. GROUND — reuse-first disk-state + git history (VERIFICATO questo turn)

Anti-hallucination: ogni claim qui sotto è stato verificato con `ls`/`grep`/`git log`/`find` in questo
turn. **L'Explore reuse-first aveva commesso 2 errori che la verifica ha corretto** (vedi §1.3) — prova
che il GROUND disk-state va sempre ri-eseguito, non fidato di un report.

### 1.1 Cosa ESISTE (l'SDD è ~40% reale, più di quanto sembri)

| Mattone | Stato | Evidenza verificata |
|---|---|---|
| Spec versionate | **GIÀ-PRONTO** | **50** file `.md` in `research/operations/specs/` (count `ls \| wc -l` verificato) |
| Frontmatter de-facto | **GIÀ-PRONTO** | `date / domain / client_case / status / sources / supersedes_partial / complements` (letto da `2026-05-23-chat-data-intelligence-nuzantara.md`) |
| Lint CI | **GIÀ-PRONTO** | **8** workflow in `.github/workflows/`: asyncpg, cross-import, golden-rule-10, i18n, migration×3, symbiosis |
| Symbiosis-promise lint | **GIÀ-PRONTO ma ristretto** | `scripts/lint_symbiosis_promises.py` (79 righe) — verifica che le promesse di durabilità abbiano un `Test:` citato, MA copre **solo `SYMBIOSIS.md`**, non le spec generiche |
| 4-LLM panel | **REALE ma MANUALE** | 4 JSON storici (DeepSeek+Gemini+GPT-5.5+Opus, 2026-05-21). Workflow cognitivo (l'agente lancia gli LLM a mano — come in QUESTO ciclo). Nessun CI gating. |
| VADEMECUM | **GIÀ-PRONTO (spec-lite)** | `VADEMECUM.md` checklist pre-build, "se al punto 3 non sai rispondere, fermati" — autodisciplina |
| Plan files | **GIÀ-PRONTO** | `docs/superpowers/plans/` (5 plan). Separati: spec=cosa/perché, plan=chi/come/timeline |

### 1.2 Il BUG GRAVE verificato — il Preflight SDD "mandatory" è un COMANDO MORTO

Verificato con `find` + `git log` in questo turn (documentato, NON fixato — siamo in fase studio):

- `CLAUDE.md` cita `./scripts/ai-dispatch.sh preflight-{l1,l2,l3}` come **Preflight SDD mandatory**.
- `scripts/ai-dispatch.sh:737` chiama `PYTHONPATH=. python3 apps/federation/workflows.py run "preflight-${LEVEL}"`.
- **`apps/federation/` NON ESISTE** come directory (`workflows.py` esiste solo in `apps/nuzantara-mcp/`, non-correlato).
- **Git history**: commit `b6f5777aa "feat(federation): implement Preflight SDD — mandatory pre-implementation workflow"` → poi `0c60050e8 "chore: massive repo cleanup — untrack 739 files, remove 2.4M lines of legacy"` → **il cleanup ha rimosso `apps/federation/workflows.py` lasciando il chiamante `ai-dispatch.sh:737`**.
- **Conseguenza**: `ai-dispatch.sh preflight-l3` **fallisce a runtime**. Il gate "mandatory" del CLAUDE.md è **non-eseguibile da [tempo]**, e nessuno l'ha notato.

Famiglia: orphan post-cleanup (W50/W59 deploy-desync). **Questo è la prova vivente del difetto #4 del
red-team** (un gate che muore in silenzio non era un gate) — non un'ipotesi, un fatto sul disco.

### 1.3 Meta-lezione — l'Explore ha sbagliato 2 volte, la verifica l'ha corretto

- L'Explore disse "preflight-l1/l2/l3 NOT FOUND" → **falso**: il comando esiste in `ai-dispatch.sh:727-737` (è il *file che chiama* a mancare, sfumatura che cambia tutto).
- L'Explore citò un frontmatter con campi `spec_id`/`panel_verdict` → **inventati**: il reale è `date/domain/client_case/...`.

Applicazione diretta della cicatrix W-meta: *mai costruire su un file:line di un report senza
ri-verificare*. Il GROUND disk-state ri-eseguito ha salvato la spec da 2 premesse false.

---

## 2. I 6 DIFETTI DEL RED-TEAM → risoluzione

| # | Difetto (Gemini) | Sev | Risoluzione |
|---|---|---|---|
| 1 | gate architetturale aggirabile (allowlist path) O teatro (se troppo largo) | ALTA | **residuo parziale §5**. Mitigazione: allowlist + il gate NON è l'unico layer (testmon di P4 cattura l'impatto reale anche fuori-allowlist). Onestà: nessun gate statico-su-path è completo. |
| 2 | template → fuffa-plausibile (gate falsificabile che SEMBRA tale) | **CRITICA** | **residuo onesto §5**. Il linter valida la forma, non la sostanza. Mitigazione: è il **panel umano-multi-LLM** a giudicare se un gate è davvero falsificabile, non il linter. Il template garantisce che la sezione esista; il panel garantisce che sia vera. Due layer distinti. |
| 3 | lint_spec_promises = stringa non semantica (test esiste ma testa altro) | ALTA | **residuo onesto §5** (identico a P4): il lint misura la citazione, non la verifica. Stesso limite strutturale. Mitigazione: il lint è il pavimento (test deve almeno esistere), il panel è il soffitto. |
| 4 | preflight-morto = sintomo di inutilità, riparare = ripristinare teatro | ALTA | **DeepSeek #2**: la proprietà mancante è l'**auto-testabilità riflessiva**. Vedi §3.2 — un gate reale ha un `preflight-self-test` che fa rumore quando muore. NON ripristinare il file orfano: ricostruirlo CON il self-test, o rimuoverlo e dichiarare il panel manuale onesto. |
| 5 | circolarità bootstrap (uso il processo rotto per ripararlo) | MEDIA | **DeepSeek #1**: bootstrap legittimo. Distinzione livello-oggetto / meta-livello. Vedi §0-bis. |
| 6 | decadimento spec → bugie autorevoli | **CRITICA** | **DeepSeek #3**: spec = artefatto immutabile di decisione, non descrizione del presente. Non decade perché non pretende di descrivere ora. Vedi §0. |

---

## 2-bis. La circolarità (risoluzione DeepSeek #1, difetto #5)

> Questa spec definisce l'SDD. Per approvare l'SDD si dovrebbe applicare l'SDD (gate+panel). Ma il
> gate è rotto e il panel è manuale. Uso il processo che dichiaro rotto per ripararlo.

**Non è un paradosso fatale — è bootstrap legittimo.** Ogni sistema normativo si auto-fonda con un atto
di decisione *extra*-normativo. La distinzione è livello-oggetto vs meta-livello:

- **Spec che SOGGIACE al processo** (le altre 48): passa il gate+panel istituiti.
- **Spec che DEFINISCE il processo** (questa, P5): è essa stessa una *decisione architetturale*,
  approvata dal panel-manuale-oggi-operativo (questo ciclo: Gemini+DeepSeek), e **istituisce** il gate
  per le decisioni successive. Non deve passare un gate che non esiste ancora — è la *base* che lo crea.

Il paradosso si scioglie: il meta-livello è *deciso* (atto fondativo), non *generato* dal meccanismo
che esso stesso definisce.

---

## 3. DESIGN (potenziare il 40% reale, riparare il morto CON la proprietà mancante)

### 3.1 La spec come ADR rafforzato — formalizzare ciò che queste 9 spec già fanno

Il template non è un'imposizione nuova: è la *codifica* del formato de-facto che le 50 spec usano e che
questo ciclo (P1-P9) sta seguendo. Sezioni di un ADR rafforzato:

- Frontmatter reale (`date/domain/status/sources/supersedes_partial/complements`).
- **§0 correzione/ground**: i fatti verificati su cui poggia (disk-state, non priors).
- **Difetti-council** + risoluzione (chi ha trovato cosa, su quale modello).
- **Gate falsificabili** numerati (Symbiosis Law 7).
- **Decisione** (go/no-go/defer + metrica).
- **Provenienza** (quali LLM, quali fonti, residui onesti).
- **Immutabilità**: una volta `status: approved`, non si modifica. Si supersede.

### 3.2 Riparare il gate CON auto-testabilità riflessiva (DeepSeek #2, difetto #4)

La causa-radice del preflight morto: **nessun test verificava che il comando restasse eseguibile**. Un
gate reale deve "fare rumore quando muore". Tre opzioni (studio — documentare, non scegliere):

- **Opzione A — ricostruire con self-test**: ripristinare `apps/federation/workflows.py` (o ri-puntare
  `ai-dispatch.sh` a un eseguibile esistente) E aggiungere `preflight-self-test` in CI: esegue il
  comando in dry-run, **fallisce se il file/comando è assente**. Se un cleanup futuro lo rimuove → CI
  rossa → "rumore". + renderlo *required status check* su PR hot-zone.
- **Opzione B — onestà**: rimuovere il comando morto da `ai-dispatch.sh` + da `CLAUDE.md`, e dichiarare
  il 4-LLM panel come processo *manuale* esplicito (non finto-automatico). Meno potente, ma non-teatro.
- **Opzione C — minimale**: un solo CI check `test_claudemd_commands_executable.py` che, per ogni
  comando citato come "mandatory" nel CLAUDE.md, verifica che l'eseguibile esista. Cattura QUESTA
  classe di orphan-post-cleanup in generale, non solo il preflight.

Raccomandazione (per leva): **C poi A**. C è il meta-gate generale (cattura ogni futuro comando-morto);
A ricostruisce il preflight specifico solo se si decide che serve davvero un gate automatico oltre al
panel manuale.

### 3.3 SDD gate per PR architetturali — con i limiti dichiarati

Un CI check: se una PR tocca hot-zone (auth/billing/migration/dependencies/router-manifest — la stessa
lista del lease-check esistente), richiede un link a una spec con `status: approved`. **Limiti
onesti** (red-team #1): l'allowlist è aggirabile spostando logica fuori-path; non è l'unico layer (il
testmon di P4 cattura l'impatto reale). Il gate è igiene, non garanzia.

### 3.4 Lint_spec_promises — il pavimento, non il soffitto (difetti #2/#3)

Estendere `lint_symbiosis_promises.py` a un `lint_spec_promises.py` che verifica: ogni spec
`status: approved` ha ≥1 `Gate:`/`Test:` citato e il file-test **esiste**. **Dichiarato esplicitamente**:
questo è il *pavimento* (il test deve almeno esistere) — NON verifica che il test *verifichi la
promessa* (limite semantico non-lintabile, identico a P4). Il *soffitto* è il panel umano-multi-LLM.

---

## 4. GATE FALSIFICABILI (Symbiosis Law 7)

- **G1 — gate fa rumore quando muore** (binario): rimuovere/rompere il comando preflight (o qualsiasi
  comando "mandatory" del CLAUDE.md) DEVE far fallire `preflight-self-test` / `test_claudemd_commands_
  executable` in CI. Falsificabile: CI rossa. *Questo è il gate che il preflight morto non aveva.*
- **G2 — spec immutabile + supersede** (binario): modificare una spec `status: approved` (invece di
  superseder-la con una nuova) DEVE essere flaggato. Falsificabile: un lint/hook rileva il diff su file
  approved-immutable.
- **G3 — PR architetturale ha spec** (binario, con caveat §3.3): PR che tocca hot-zone senza link a
  spec `approved` → CI warn/block. Falsificabile, ma aggirabile (dichiarato).
- **G4 — spec-promise floor** (binario): spec `approved` senza `Gate:`/`Test:` citato → lint fallisce.
  Pavimento, non semantica.
- **G5 — copertura** (numerico): # spec-architetturali-con-gate-eseguibili / # spec-architetturali.
  Metrica di igiene. Con il disclaimer: misura la forma (gate presente+test-esiste), non la sostanza
  (gate-vero+test-verifica) — quella la giudica il panel.

---

## 5. RESIDUI ONESTI

1. **Semantica non-lintabile (red-team #2/#3, CRITICA+ALTA)**: nessun linter distingue un gate
   *realmente* falsificabile da uno che ne ha la forma, né un test che *verifica la promessa* da uno
   che esiste-ma-testa-altro. **Il panel umano-multi-LLM è il soffitto; il lint è il pavimento.** Lo
   stesso limite strutturale di P4 (verificare la citazione ≠ verificare la verità). Non risolvibile
   con più automazione — è il confine tra sintassi e semantica.
2. **Gate aggirabile (red-team #1)**: l'allowlist-path per il gate architetturale è evitabile spostando
   logica fuori-path. Mitigato (non risolto) dal testmon di P4 e dal panel. Nessun gate statico è
   completo.
3. **Spec-teatro residuo**: imporre il template può generare spec con-le-sezioni-ma-vuote. Il panel le
   smaschera, ma un agente determinato può produrre fuffa-plausibile che passa il pavimento-lint. Costo
   accettato: il pavimento alza comunque la qualità mediana; il panel cattura le critiche.

---

## 6. DECISIONE (kill gate)

**GO sulla riformulazione** (spec = ADR rafforzato immutabile) come base concettuale dell'SDD. **GO su
G1 (self-test del gate)** come priorità — è il fix della causa-radice (gate che muore in silenzio) e
cattura una classe di bug (orphan-post-cleanup) oltre il preflight specifico.

**DOCUMENTATO non fixato** (fase studio): il Preflight SDD morto (`ai-dispatch.sh:737` → file
inesistente) resta un bug reale da riparare in una sessione dedicata (opzione C poi A di §3.2). Segnalato
come finding, non risolto qui.

**Metrica primaria falsificabile**: G1 — se rompi il comando-mandatory e la CI NON diventa rossa, il
gate è ancora teatro e il pezzo ha fallito il suo scopo centrale.

**Bootstrap dichiarato**: questa spec si auto-approva come atto fondativo (panel manuale di questo
ciclo: Gemini+DeepSeek), istituendo il gate per le spec successive. Non passa un gate che non esiste
ancora — lo crea.

---

## 7. Provenienza

- **Reuse-first**: Explore disk-state (con 2 errori corretti dalla ri-verifica, §1.3). 50 spec, 8 lint
  CI, panel-storico, VADEMECUM, plans.
- **Verifica diretta** (questo turn): `git log` su `apps/federation/workflows.py` → preflight morto da
  cleanup `0c60050e8`. `find` conferma `apps/federation/` inesistente. Memory importance-8.
- **Council 2-LLM asimmetrico** (calibrato — pezzo meta/disk-state, no full-council; SOTA SDD già
  groundato nei 15+ paper della ricerca-madre):
  - Red-team: **Gemini 3.1 Pro** — 6 difetti, 2 CRITICA (template→fuffa, decadimento→bugie-autorevoli).
  - Logic-costruttivo: **DeepSeek V4 Pro** (`reasoning_effort=high`) — scioglie circolarità (bootstrap),
    gate-morto (auto-testabilità riflessiva), decadimento (spec=ADR immutabile). La riformulazione
    centrale del ruolo-spec è sua.
- **Famiglia**: P4 (stesso residuo semantico: lint misura citazione non verità). Le 9 spec di questo
  ciclo (P1-P9) sono l'esemplificazione vivente del template ADR-rafforzato che §3.1 codifica.

> **Onestà finale**: l'SDD di Nuzantara non diventa "la spec genera il codice" (non lo è, non lo sarà).
> Diventa onesto: **la spec è la memoria decisionale immutabile del sistema** — cattura *perché* si è
> deciso così, col panel e i gate dell'epoca, e si supersede invece di decadere. Il gate smette di
> essere teatro quando "fa rumore mentre muore" (G1). Il salto è da "Preflight mandatory che nessuno
> esegue ed è morto da [tempo] senza un rumore" a "ogni decisione architetturale lascia un record
> falsificabile, e il gate che lo impone si auto-verifica".
