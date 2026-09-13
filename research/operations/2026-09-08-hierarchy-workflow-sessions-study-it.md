---
date: 2026-09-08
domain: operations
client_case: none — studio interno delle sessioni Zero↔Astra (2026-09-06) e Zero+Subhi↔Astra (2026-09-08) sul workflow gerarchico
adversarial_review: codex
sources: trascrizioni Codex locali su Air-M5 (rollout 2026-09-06T17-29 e 2026-09-08T11-17, lette in questa sessione) + docs/army-pilot/* sul branch agent/air-m5/ops/army-opus-general + research/operations/2026-09-07-astra-operative-workflow-audit.md + research/operations/2026-09-07-workflow-reality-audit.md (PR #5872) + research/operations/2026-09-08-nuzantara-operating-workflow-v1.md + PR #5821 + Codex GPT red-team sulla bozza (§ Adversarial review)
---

# Il workflow con i due imperatori — studio delle sessioni con Astra

Mandato di Zero (2026-09-08): *"implementa il workflow perfetto con i due imperatori e il resto della
gerarchia, e in più studia la sessione mia/Subhi con Astra."* Questo file è lo studio; la mappa
operativa è `docs/architecture/dual-consul/army-map.md`; la dottrina e i consumatori arrivano nelle
PR elencate in §7.

## 0. Verdetto in una riga

**La gerarchia è decisa da Zero; il contratto operativo del workshop è una sintesi da ratificare;
quello che manca è che la macchina faccia rispettare la parte decisa.** Zero l'ha disegnata il 6
settembre con Astra (parole sue, §2), il pilot l'ha eseguita la notte del 6→7, il workshop con
Subhi dell'8 settembre l'ha ridotta a un contratto operativo le cui righe "concordato" non citano
una conferma esplicita di Zero (§4). Il mandato di oggi, *"implementa il workflow perfetto con i due
imperatori e il resto della gerarchia"*, ratifica la gerarchia, non le nove decisioni del workshop.
Nessuno dei tre passaggi è arrivato su `main`: la gerarchia viveva in file non tracciati, e il
worktree che li conteneva è stato potato.

Provenienza delle prove: le trascrizioni Codex citate sono file locali di Air-M5
(`~/.codex/sessions/2026/09/06/rollout-2026-09-06T17-29-36-01a0760d-44eb-7a30-ac50-8137fff861d5.jsonl`
e `~/.codex/sessions/2026/09/08/rollout-2026-09-08T11-17-15-01a07f05-1a2e-7ec0-9934-ac37c032f1ea.jsonl`;
gli orari citati sono il campo `timestamp` di quei record, ora locale della macchina), i branch del
pilot (`agent/air-m5/ops/army-opus-general`, `agent/air-m5/ops/army-w1-assignment`, `agent/air-m5/ops/sol-usage-collector`) sono
locali e non su `origin`, i tempi della prova homepage vengono dalla ricevuta trapiantata in PR
#5941. Chi non è su questa macchina può verificare solo ciò che è nel repo: le citazioni di Zero in
§2 e §4 sono riprodotte qui perché altrove non esistono.

## 1. Le due sessioni

| Sessione | Quando (WITA) | Chi | Turni utente | Esito |
|---|---|---|---|---|
| Codex `01a0760d` | 2026-09-06 09:33 → 20:07 | Zero ↔ Astra | 34 | Disegno della gerarchia, W0 del pilot, due generali avviati, diagnosi del blocco, handoff |
| Codex `01a07f05` | 2026-09-08 03:17 → 10:56 | Zero + Subhi (voce) ↔ Astra | 7 | Nove decisioni, contratto v1, prova homepage fino alla PRE-review PASS |

## 2. Cosa ha deciso Zero il 6 settembre (parole sue)

1. **Due imperatori, non un orchestratore.** *"Fable 5.1 xhigh e Astra xhigh, ma con il consumo
   minimo di token. Sono puri architetti seduti al fresco."* (12:14)
2. **Il Dux lo scelgono loro.** *"All'inizio ci sono due finestre: Fable e Astra, i quali decidono
   anche l'arsenale da disporre per la battaglia e decidono tra di loro chi sarà il Dux."* (12:14)
   Precisato alle 12:43: Dux è il generale che conduce la missione sul campo, scelto tra Opus e Sol.
3. **Un esercito gerarchico, tutto l'arsenale.** *"Dai frontier model di reasoning potente, ai
   worker di qualità ma anche ai modelli più semplici che possono lavorare nel frattempo alla
   pulizia, ai test, alla raffinatura."* (12:25) E alle 13:24: *"hai l'arsenale con tutti gli LLM,
   paghiamo abbonamenti, sfruttiamo tutti per bene."*
4. **Comunicazione gerarchica.** *"Il supporto operativo parla solo con builder. I builder solo con
   specialisti o i Generali. Gli specialisti solo con i Generali e i Generali con gli imperatori."*
   (12:33)
5. **Contesto diverso per livello.** *"Luna, Haiku o Kimi 2.7 non devono avere lo stesso contesto
   che hanno Fable e Astra. Più focalizzato, più operaio."* (12:43)
6. **Niente Opus revisore permanente.** *"NO, SI TOGLIE OPUS REVISORE... OPUS E SOL SONO UGUALI."*
   (12:56)
7. **La mappa.** *"Disegna il grafico delle gerarchie, dei flussi, dei compiti, che potranno usare
   Fable e Astra come mappa quando dovranno scegliere le armate."* (12:59) — persa col worktree,
   rifatta in `army-map.md`.

Fable, dalla finestra parallela, ha aggiunto tre regole che Astra ha accolto (13:44): misurare il boot
con i contatori nativi; finestre imperiali corte per costruzione; **l'imperatore non fa mai fan-out**
(cinque lane Fable in parallelo esauriscono un seat MAX in 2–3 minuti).

## 3. Cosa ha fatto il pilot (notte 6→7 settembre)

Opus nominato Dux (pacchetto con hash, approvazione di entrambi gli imperatori), Sol generale sul
fronte nativo. Eseguito: piani di campo di entrambi, W1 (validatore del grafo di assegnazione) con
test negativi, W2 (indipendenza del revisore) costruito ma senza verificatore idoneo, collettore di
consumo corretto e accettato a livello fixture, fix dell'hook `orchestrate_gate` (la delega conta
come orchestrazione). Ventiquattro commit su `agent/air-m5/ops/army-opus-general`, sette su
`agent/air-m5/ops/army-w1-assignment`, cinque su `agent/air-m5/ops/sol-usage-collector`. **Zero PR aperte.**

Le lezioni, in ordine di costo:

- **Pubblicato ≠ consegnato.** *"Sol ha scritto l'accordo, ma Opus non è stato riattivato per
  leggerlo. La cartella condivisa conserva i messaggi, non sveglia le sessioni."* (Astra, 15:51)
  Entrambi i generali hanno consegnato il piano e chiuso il turno; nessuno assegnava il passo dopo.
- **Sol bloccato prima degli strumenti**: al Codex 0.153.4 pinnato mancava un componente; riparato da
  Astra (PR #5846), verificato da Opus sull'hash. Nel frattempo il profilo di permessi della sessione
  Sol si è allargato da solo a `danger-full-access` (causa non identificata: domanda 3 di §8).
- **Corsa sulle prenotazioni**: il Dux ha annunciato lo slot 4 per Sol e poi lo ha usato per un
  controllo proprio senza revocarlo. La "prenotazione atomica" della spec non esiste in nessun codice.
- **Troppa cerimonia.** Alle 16:52 Zero: *"solo Opus a lavoro ora ... altrimenti dovremo dichiarare
  fallito il progetto."* Alle 18:41 Astra: *"il multi-agente esiste davvero ed è usato in
  produzione. La nostra gerarchia completa, invece, è un'ipotesi da validare, non una pratica già
  dimostrata superiore. E sì: in questa sessione c'è stata troppa cerimonia."*
- **Mac a carico**: un worker Codex ausiliario a 2,5 GB e CPU alta, legato a una sessione vecchia;
  chiuderla ha riportato il carico a zero. *"Contesto corto anche per la salute del Mac."* (16:38)

Alle 19:34 Zero ha posto la domanda giusta: *"meglio usare una family Claude di base o la gerarchia
che vogliamo creare?"* Astra: base operativa Claude per il primo confronto, imperatori al livello
strategico, altre famiglie per incarichi mirati; nessuna prova che la gerarchia completa renda di più.

## 4. Il workshop con Subhi (8 settembre)

Il brief incollato da Zero fissa la regola d'oro: *"Mark Accepted only after Zero explicitly
confirms... silence, interruptions and an ambiguous spoken yes are not approval."* Le decisioni
raggiunte:

1. Review AI obbligatoria in due tempi: PRE-review del piano prima della decisione umana, POST-review
   indipendente dopo l'implementazione.
2. Indipendenza: chi ha contribuito non revisiona; cambiare skill nella stessa sessione non crea
   indipendenza.
3. Il Dux ha mandato scritto, alternative e rischi, prova ripetibile, ri-verifica a ogni modifica;
   fuori mandato interpella Subhi/Zero con domanda, opzioni, raccomandazione, parte bloccata.
4. Capacità pilota: una missione principale alla volta, **massimo quattro PR distinte lavorate al
   giorno**, parallelismo solo su parti indipendenti. Dichiarato: nessun dato prova che sia ottimale.
5. Chiusura con tre prove: esito utente verificato, test ripetibili, review indipendente completata
   con rilievi risolti.
6. Priorità: homepage → navigazione e KBLI Navigator → footer → altri contenuti.
7. Todoist è il registro unico; le transizioni sono commenti sullo stesso task.
8. **Gerarchia ripristinata dopo l'obiezione di Zero.** La prima stesura del contratto descriveva
   solo "coordinatore Codex + verificatore Claude". Zero (08:17): *"ma ci sono gli imperatori, i
   generali etc?"* Astra: *"il documento v1 ha perso un pezzo importante."* Revisione 1.1: imperatori
   Fable 5.1 e Astra pari; generali Opus e Sol pari; Dux temporaneo; verifica indipendente come
   incarico.
9. **Autorità di rilascio invariata**: *"Chi ha scritto l'implementazione non può approvarla."* Un
   Codex/Sol esterno prepara, una sessione Claude indipendente verifica, un responsabile Claude
   autorizzato rilascia. *"La parità non amplia i permessi di Astra/Sol."*

**Eseguito davvero**: un agente ha trovato il primo difetto (il "Get Started" mobile scorre in cima
invece di aprire WhatsApp come su desktop); poi la catena incarico → piano (Sol richiesto, modello
servito non esposto) → review Claude indipendente (CHANGES_REQUIRED, sei rilievi) → correzione →
seconda review **PASS**. Tempo totale 7 min 45 s; le due review 59 s e 19 s. Provato solo il tratto
piano/review; costruzione, rilascio, prova dal vivo e qualificazione ripetuta del Dux **non**
provati. La decisione di prodotto su "Get Started" è ancora aperta (Zero alle 10:45 e 10:55:
*"quindi?" / "dunque?"*).

Tensioni da registrare: la stessa sessione Codex ha impersonato imperatori, generali e Dux in una
simulazione dichiarata; le righe "concordato/disepakati" dell'assistente non citano una conferma
esplicita di Zero, contro la regola del brief; il connettore sbagliato (LONA) è stato installato e
rimosso; commenti Todoist vecchi portavano regole ("minimo di PR", review umana) che il pilota ha
dovuto scavalcare esplicitamente.

## 5. Le contraddizioni, e come si chiudono

| # | Testo A | Testo B | Chiusura |
|---|---|---|---|
| 1 | RULINGS/modus/AGENTS §17.1/MODEL_ROSTER/FLEET/hook: "Opus 5 gate finale per tutti i gear, Fable fuori dal workflow" (08-20) | Zero 09-06: due imperatori, Opus e Sol uguali, niente Opus revisore permanente | Vince il 09-06 sul **titolo**: la verifica indipendente è un incarico, non un grado. Resta il **gate empirico su disco** con le sue regole (mai cascata, finestra morta → SUSPEND, effort `xhigh`), e Opus 5 `xhigh` ne resta il seat obbligatorio (nessuna sostituzione senza ruling); il lavoro costruito da seat esterni è sempre verificato da una sessione Claude (Builder Contract 5). Fable rientra **solo** come finestra imperiale aperta da Zero; nessun auto-route. Il testo approvato dai due imperatori (`astra-w2-ruling-review/1`) è già scritto sul branch W1: si riusa byte-identico |
| 2 | PR #5821: consoli con "merge, deploy, every authorization" | Builder Contract 5 + workshop 09-08: nessun seat esterno merga; la parità non amplia i permessi di Astra | Vince il testo che coincide con il Builder Contract già su `main` (contract 5); la presenza di Zero al workshop non è ratifica, e la frase di #5821 non è mai stata su `main`. #5821 si chiude come superata; la parte viva (due imperatori pari) entra nella PR di dottrina |
| 3 | RULINGS riga 20: gate a effort `max` | RULINGS riga 32, modus, MODEL_ROSTER: `xhigh`, `max` solo su adjudication Gear-3 dichiarata | `xhigh`; FLEET `gear3_final_gate.chain[0].effort` passa da `max` a `xhigh` |
| 4 | Skill `/workflow` §1.1: `model:` su ogni `agent()` | Hook `model_routing_gate` guarda solo il tool `Agent`; due template del repo senza pin | L'hook ispeziona anche gli script `Workflow`; i template si pinnano |
| 5 | Contract 2: ogni PR porta `Bites:` | Il parser esiste (`scripts/ci/bites_parse.py`, testato in `immune-enforcement.yml`) ma nessun job legge i corpi delle PR; il chiamante è in PR #5734, bloccata | Fuori da questa ondata: #5734 resta il veicolo. Tre cose distinte: prosa nel corpo, parsing YAML, esecuzione dell'osservazione. Oggi esiste solo la seconda |
| 6 | Default M5 = Fable 5.1 (`~/.claude/settings.json`) | RULINGS: interattivo Opus 5; reset a `opus[1m]` del 09-02 | Decisione di Zero (§8). Il pin obbligatorio sui figli riduce l'ereditarietà (danno misurato: 35 agenti, 3,5M token, reality audit §5) ma non la elimina: `fork` e workflow salvati ereditano per disegno, e l'hook gira solo se il matcher HOME include `Workflow` |

## 6. Il meta-pattern (la malattia delle malattie)

**Nominare un ruolo non è farlo esistere.** Tutte e sei le contraddizioni hanno la stessa forma: la
decisione vive in prosa (trascrizione, file non tracciato, PR bozza), mentre il codice che gira
applica la regola precedente. Il pilot lo ha riprodotto in piccolo: piani scritti, nessuno che
assegna il passo dopo; file pubblicato, nessuno che lo legge. La cura non è un'altra spec, è dare a
ogni regola un consumatore osservabile (hook, validatore, lint, check CI) nella stessa PR che la
scrive. È esattamente la contract 2 del Builder Contract, applicata alla dottrina stessa.

## 7. Il workflow perfetto, come lo spedisce questa sessione

Regola settled (testo che entra in dottrina):

> Due imperatori pari, Fable 5.1 e Astra: direzione strategica, vincoli, nomina del Dux; parlano tra
> loro e con i generali; mai fan-out, mai implementazione. Due generali pari, Opus 5 e Sol: per
> missione uno è Dux temporaneo e possiede piano, assegnazioni, integrazione, evidenze, registro.
> Specialisti, builder e supporti solo per bisogno concreto, comunicazione lungo la catena. La
> verifica indipendente è un incarico fuori dalla catena contribuente, non un grado; valgono
> famiglia≠builder su Gear 2 e verificatore qualificato su Gear 3; effort di gate `xhigh`, `max` solo
> su adjudication dichiarata. Nessun seat esterno merga, arma o distribuisce; un responsabile Claude
> autorizzato rilascia. Ogni figlio `Agent`/`Workflow` pinna il modello. Fable 5.1 non è mai
> auto-instradato: entra solo come finestra imperiale aperta da Zero.

Di questa regola, la parte "chi comanda chi" è di Zero (§2) e la parte "chi verifica e chi
rilascia" è il Builder Contract già vigente; nessuna delle due nasce dal workshop. Le nove decisioni
del workshop (§4) restano una proposta finché Zero non le conferma per iscritto.

PR di questa ondata, serializzate, con lo stato onesto di ciò che ciascuna fa rispettare:

1. `#5941` — salvataggio dei tre documenti Astra. Consumatore: il gate R1 su quella PR (PASS).
2. questa PR — studio + `army-map.md`. Documento: il consumatore è chi apre le finestre (§Solo-operatore).
3. `feat(hooks)` — `model_routing_gate` ispeziona gli script `Workflow`; pin nei due template.
   Fa rispettare solo dopo che l'operatore allarga il matcher HOME a `Workflow` (riga PENDING-ARMS).
4. `#5940` — `orchestrate_gate`: la delega conta come orchestrazione. Vive nella copia HOME
   riallineata dal guaritore dopo il merge.
5. `#5942` / `#5943` — validatori W1 (`army_assignment`) e W2 (`review_eligibility`) con test.
   **Nessun consumatore li esegue ancora**: sono strumenti, non enforcement.
6. `feat(evidence)` — `evidence_pack_lint` consuma W2 sul rilascio (follow-up di #5943; sul branch
   del pilot è NOTICE-only fino al 2026-09-21).
7. `#5944` — collettore di consumo per seat. Consumatore: il job che già lo invoca.
8. `docs(doctrine)` — le sei superfici riallineate; #5821 chiusa come superata;
   `test_gate_seat_conformance.py` verde nello stesso diff.

Ogni PR porta la propria riga `Bites:`; dove il consumatore non esiste ancora la riga lo dice.
Detto senza attenuanti: le PR 5 (validatori senza chiamante) **non soddisfano** la contract 2 del
Builder Contract ("il job che li esegue spedisce nella stessa PR"); sono state aperte così perché il
codice esisteva già sul branch del pilot e perdeva valore ogni giorno fuori da `main`. La cura è la
PR 6 (il consumatore nel lint) e, per W1, un chiamante nel broker di assegnazione che oggi non c'è.
Finché non arrivano, W1 e W2 sono strumenti da invocare a mano, e questo studio non li conta come
enforcement.

## 8. Decisioni che restano a Zero

1. **Default interattivo su M5**: Opus 5 (dottrina) oppure Fable 5.1 aperto con `--model` quando
   serve la finestra imperiale. Il file è in HOME: tocca a te.
2. **Sessioni Astra in voce con Subhi**: sono la "porta strategica" (imperatore) o una finestra di
   campo? Il contratto v1 dice porta strategica; il workshop l'ha usata come Dux+builder simulati.
3. **Sol a `danger-full-access`** il 6 settembre: selezione manuale tua o deriva? Finché non è chiaro,
   il lavoro con effetti di Sol resta sul percorso figlio.
4. **Tetto di quattro PR al giorno** nel pilota: confermarlo, alzarlo o toglierlo dopo la prima
   settimana misurata.
5. **"Get Started" mobile**: destinazione e comportamento, per chiudere UX-01.

## Adversarial review

Red-team: **Codex** (`codex exec --sandbox read-only`, `model_reasoning_effort=high`, Air-M5,
2026-09-08), sulla prima bozza di questo studio e di `army-map.md`. Verdetto sulla bozza:
**REJECT**, 15 rilievi (8 SEVERE, 7 MODERATE). Disposizione di ciascuno nella versione attuale:

| # | Rilievo Codex (sintesi) | Disposizione |
|---|---|---|
| 1 | SEVERE — "settled" supera l'approvazione registrata: presenza al workshop ≠ ratifica | Accolto. §0 e §7 separano ciò che Zero ha deciso (06-09, citazioni) da ciò che il workshop ha sintetizzato (da ratificare) |
| 2 | SEVERE — la mappa aboliva l'"Opus revisore" confondendo review indipendente e gate su disco (RULINGS:32, fleet-order-spec:312) | Accolto. Mappa §1 e §5-tab. 1: il gate empirico resta con le sue regole, Opus 5 `xhigh` ne è il seat obbligatorio; abolito solo il titolo permanente di revisore |
| 3 | SEVERE — "qualsiasi verificatore qualificato" poteva saltare la verifica Claude del lavoro esterno (Builder Contract 5) | Accolto. Riga "Independent verifier": lavoro costruito da seat esterni → sempre verificato da una sessione Claude |
| 4 | MODERATE — "decisioni sostanziali" degli imperatori senza escludere business/credenziali/consensi | Accolto. Riga "Imperators": decisioni *tecniche*; business, credenziali, consensi, GUI restano umane |
| 5 | SEVERE — la mappa inventava un enforcement delle comunicazioni (`orchestrate_gate` controlla i dispatch, `army_assignment` i genitori, non gli archi dei messaggi) | Accolto. Mappa §2: "oggi nessun codice rifiuta un arco di messaggio"; §5 riscritta in LIVE / PR / PROMISE |
| 6 | MODERATE — copertura `Workflow` descritta come "enforces today"; `fork` esente | Accolto. §5 e §7 della mappa: stato PR, matcher HOME da allargare, `fork` e workflow salvati ereditano per disegno |
| 7 | SEVERE — omessa la limitazione decisiva: W2 non gradato e NOTICE-only fino al 21-09, W1 senza consumatore | Accolto. Mappa §5 e studio §7 lo dicono riga per riga |
| 8 | MODERATE — "family exclusion" sovrastimata: il lint conta i seat senza confrontare le famiglie | Accolto. Mappa §5, riga quorum/appetite |
| 9 | MODERATE — il parser Bites esiste (`scripts/ci/bites_parse.py`, `immune-enforcement.yml:523`); distinguere prosa, parsing, esecuzione | Accolto. Studio §5 riga 5 |
| 10 | SEVERE — validatori separati dal consumatore; lista PR come promessa, non osservazione | Accolto. Studio §7: stato onesto per PR, "strumenti, non enforcement" dove vale |
| 11 | MODERATE — conteggi, orari, citazioni, commit non verificabili nell'albero | Parzialmente accolto. §0 dichiara la provenienza locale (path delle trascrizioni, branch locali); le tre fonti Astra sono ora in PR #5941. Le citazioni restano verificabili solo su Air-M5 |
| 12 | MODERATE — misure senza riferimento (150k, 5,6k, 35 agenti/3,5M, "cerimonia") | Accolto. Mappa §4 e §7 citano la fonte di ogni numero e definiscono baseline e criterio di stop per la cerimonia |
| 13 | MODERATE — trasporto ≠ consegna senza proprietario del wake-up, scadenza, retry, recupero | Accolto. Mappa §2: procedura di consegna in cinque passi, legata all'envelope del pilot |
| 14 | SEVERE — il test del pilot non rileva la corsa sulle prenotazioni | Accolto. Mappa §8: acquisizione atomica create-if-absent, proprietario esclusivo, scadenza, generazione, revoca; falsificazione sul registro |
| 15 | MODERATE — R1 "live" ma controlla solo seat e intestazione | Accolto. Mappa §5 lo dichiara; questa sezione contiene rilievi reali e non un segnaposto |

**Seconda passata Codex** (stesso seat, sulla versione corretta): 9 FIXED, 6 PARTIAL (#1, #2, #10,
#11, #13, #14), due problemi nuovi SEVERE, verdetto **REJECT**. Disposizione:

| Rilievo | Disposizione |
|---|---|
| #1 PARTIAL — i prompt di avvio imponevano ancora PRE-review e decisione umana del workshop non ratificato | Accolto: nel prompt del Dux quei due passi sono etichettati "procedura pilota v1, in attesa di ratifica scritta di Zero" |
| #2 PARTIAL — Opus "default" per il gate permetteva una sostituzione non prevista (RULINGS:32) | Accolto: il gate su disco è una sessione Claude sul seat Opus 5 `xhigh`, obbligatorio, nessuna sostituzione senza ruling |
| NUOVO SEVERE — un solo incarico univa review cross-family Gear-2 e gate finale Claude: per lavoro costruito da Claude la regola di famiglia escludeva il seat obbligatorio | Accolto: due righe distinte nella mappa §1, "Independent reviewer" e "Final on-disk gate", con regole di idoneità separate |
| NUOVO SEVERE — la procedura di consegna era attribuita a un envelope marcato PROPOSED / not frozen / authority none | Accolto: la procedura è dichiarata regola di questa mappa; l'envelope è citato solo per i campi hash/generazione, con il suo stato |
| #10 PARTIAL — etichette oneste non sanano validatori senza consumatore (contract 2) | Accolto nel limite del possibile in un documento: §7 dice esplicitamente che le PR dei validatori non soddisfano la contract 2 e quale PR le cura |
| #11 PARTIAL — path abbreviati, prove locali | Accolto in parte: nomi file completi delle trascrizioni e dei branch in §0; le prove restano su Air-M5 e questo non è curabile da un documento |
| #13 PARTIAL — fonte della procedura di consegna | Come sopra (nuovo SEVERE 2) |
| #14 PARTIAL — "due proprietari nella stessa run" rifiutava la riassegnazione sequenziale legittima | Accolto: falsificazione solo su intervalli di validità sovrapposti |

**Terza passata Codex**: #13, #14 e l'attribuzione dell'envelope FIXED; #1, #2, #11 PARTIAL su frasi puntuali (corrette dopo la passata: "Zero presente" tolto da §5 riga 2, "default" → "obbligatorio" in §5 riga 1, branch per esteso in §0); #10 PARTIAL non curabile qui (contract 2); reviewer/gate PARTIAL perché W0 nominava un solo verificatore (corretto: mappa §3 passo 7 e la formula della missione piccola ora nominano reviewer e gate separatamente). Verdetto della terza passata sul testo *prima* di queste ultime correzioni: **REJECT**. Non è stata eseguita una quarta passata: chi legge ha davanti il testo corretto e il giudizio precedente, non un ACCEPT.
Le disposizioni sono dell'autore (Fable 5.1); il giudizio indipendente è quello riportato, non
quello che l'autore si attribuisce.

## Solo-operatore

- Modificare `~/.claude/settings.json` (modello di default, matcher hook su `Workflow`): file HOME.
- Rispondere alle cinque domande di §8.
- Aprire le finestre imperiali (Fable con `--model`, task Astra) e nominare il primo Dux reale.
