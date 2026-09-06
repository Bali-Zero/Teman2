# Sintesi per Zero — il workflow che abbiamo davvero (7 settembre 2026)

Rapporto completo in inglese: `2026-09-07-workflow-reality-audit.md` (stessa cartella).
Solo analisi: nessun workflow lanciato, nessuna impostazione, hook, skill o codice toccato,
nessun merge o deploy. Ogni affermazione qui sotto è verificata su disco o su documentazione
ufficiale in questa sessione.

## Il verdetto in una riga

**Non serve un nuovo workflow. Serve riallineare e far rispettare quello che abbiamo.** Il ciclo
esiste, gira, è in gran parte imposto dalla macchina. Le regole sono più aggiornate dei controlli,
e i controlli sono più aggiornati dei default.

## Cosa siamo già

- **modus** è il ciclo vivo (9 stadi, Gear 1/2/3, budget come router, council solo se il gate
  scatta, generatore≠giudice, prova-live, registri PENDING-ARMS e AMENDMENTS).
- **Il Gear floor è imposto da CI** come check obbligatorio (`Harness floor recompute`), calcolato
  dal diff. Ceiling, corsie, quorum e appetite sono regole del lint sui pacchetti Gear-3: quasi
  tutte NOTICE, una sola FAIL (appetite), **tutte a posteriori**. Nessun limite di consumo agisce
  mentre il lavoro gira: gli unici limiti in volo sono quelli del runtime nativo.
- **I Dynamic Workflows sono già nostri**: skill `/workflow`, 4 template versionati, tool abilitato
  su questa macchina e **17 run registrati dal 28 agosto** (non 4).
- **La regola "modello esplicito su ogni agent()" esiste già due volte** (skill `/workflow` §1.1
  dal 21 agosto; hook `model_routing_gate.py` dal 14 luglio). Il controllo preventivo copre però
  solo il tool `Agent`: il tool `Workflow` non è mai guardato. Violazione osservata: run del
  5 settembre, 35 agenti tutti ereditati su Fable 5.1, 3,5M token nel record. Due template del
  repo (`verify-template.js`, `modus-bench.js`) violano la regola loro stessi.
- **Il pilot della gerarchia è già stato eseguito** nella notte 6→7 settembre: Dux Opus, generale
  Sol, checkpoint di Fable e Astra, validatore W1 verificato a livello fixture, W2 (indipendenza del
  revisore) costruito ma senza verificatore idoneo, collettore di consumo accettato a livello
  fixture. Tutto nei worktree `ops-army-*`; **nessuna PR aperta**. Il piano che dice "non
  iniziato" è vecchio di una notte.

## Le contraddizioni che pesano di più

1. **Una sessione fresca carica ancora "Opus 5 gate finale per tutti i gear, Fable fuori dal
   workflow"** in sei posti (RULINGS, modus, AGENTS §17.1, MODEL_ROSTER, FLEET_TOPOLOGY, hook).
   Le tue decisioni del 6 settembre vivono solo in file non tracciati e nella PR bozza #5821.
2. **Il modello di default su M5 è Fable 5.1** (`~/.claude/settings.json`), contro RULINGS e contro
   il reset a `opus[1m]` del 2 settembre. Ogni figlio senza pin eredita Fable.
3. **La regola due-consoli (PR #5821) dà a Fable e Astra "merge, deploy, ogni autorizzazione"**;
   la spec del 6 settembre dice che gli imperatori non implementano e intervengono poco; il Builder
   Contract dice che nessun seat esterno merga. Tre testi, tre risposte su chi spedisce.
4. **`max` contro `xhigh` per il gate** dentro lo stesso file RULINGS (riga 20 vs riga 32).
5. **Bites è una frase**: il 66% dei corpi PR la porta, nessun file la legge; il parser non è su main.
6. **Provenienza del verdetto Gear-3 non verificata**: chi ha un token `statuses:write` può postare PASS.

## Sul rapporto di Fable (da correggere)

- Il run da 113 agenti **non** girava su Fable: tutti i 226 record agente sono `claude-opus-5`
  perché lo script fissava `model:'opus'`. `defaultModel` è il modello della sessione, non quello
  effettivo. Il vero "fan-out ereditato su Fable" è un altro run (35 agenti, 5 settembre).
- Quella sessione (`7561e9d7`) era **una sessione Fable aperta da te con mandato di campo**
  ("tu in questa sessione e codex astra … completate /garuda_voa /secondhome /visaoracle"), non la
  finestra imperiale (`3901f1be`, che risulta a `xhigh`).
- "113 agenti" è un conteggio cumulativo; la concorrenza reale su M5 è al massimo 8.
- "Non durevole al crash" è per metà giusto: la stessa sessione o `claude --resume` rigiocano i
  risultati salvati; una sessione nuova riparte da zero; il replay è per ordine, non per contenuto.
- La proposta §7 è la riscrittura di una regola esistente; manca il consumatore, non la regola.

## Quanto costa davvero (contatori nativi, nessuna conversione)

| Superficie | Risposte | Cache write | Cache read | Output |
|---|---|---|---|---|
| Finestra Fable di campo (15 workflow lanciati) | 523 | 3,2M | 146,3M | 0,58M |
| Run 113 agenti (tutti Opus) | 4.911 | 12,0M | 345,7M | 0,28M |
| Run 35 agenti ereditati su Fable | 643 | 3,4M | 41,8M | 0,01M |
| Finestra imperiale Fable | 79 | 0,6M | 19,0M | 0,13M |

Il `totalTokens` del record di run (11,77M) **esclude le letture di cache** (345,7M): è un segnale
di dimensione, non un consumo. Il costo della struttura sta nelle riletture del prefisso a ogni
turno, non nell'output.

## Piano minimo (non eseguito)

1. **Tu, su HOME**: modello di default su M5 (Opus 5 come da dottrina, o Fable aperto con
   `--model` quando lo vuoi) e `workflowSizeGuideline` da `unrestricted` a `medium`/`small`.
2. **Una PR di dottrina**: sostituire "Opus gate permanente / Fable fuori" con la regola settled
   (la verifica indipendente è un incarico, non un titolo), risolvere `max`/`xhigh`, aggiornare il
   test che ancora l'ancora. Il testo dei consoli entra solo dopo la tua risposta al punto aperto.
3. **Estendere il consumatore che c'è**: l'hook guarda anche il tool `Workflow`; pin nei due
   template; un lint sui record agente senza chiave `model`.
4. **Portare su main gli artefatti del pilot al loro livello reale** (W1 e collettore a livello F;
   W2 dopo una verifica non-contributore, Sol è il candidato).
5. Chiudere provenienza del verdetto e parser `bites:`, che hanno già la spec.
6. Solo dopo, decidere se serve un servizio di ammissione/prenotazione. **Niente LangGraph adesso.**

## Pilot falsificabile

Un task Gear-2 congelato, non-PII, un generale, ≤4 seat, modelli fissati, prenotazioni su file.
Falsificato se: un record agente senza `model`, uno slot usato prima della riga di prenotazione,
chiusura dichiarata senza osservazione `bites:` a exit 0. Seconda ipotesi (nessun servizio di
capacità aggregata necessario): falsificata se due finestre sullo stesso account colpiscono un limite
nello stesso minuto. Fixture di interruzione e di orfani definite prima del run.

## Decisioni che restano a te

1. Default interattivo su M5 (e Pro/Mini): Opus 5 o Fable 5.1?
2. PR #5821: il gate Opus 5 resta obbligatorio sul lavoro spedito dai consoli, e "console" è lo
   stesso seat di "imperatore"?
3. L'allargamento della finestra Sol a `danger-full-access` del 6 settembre: selezione manuale tua?
4. Effort per le finestre imperiali: valore salvato `high`, richiesto `xhigh`.
5. Le sessioni Fable di campo del 5-6 settembre sono l'uso voluto del seat?
