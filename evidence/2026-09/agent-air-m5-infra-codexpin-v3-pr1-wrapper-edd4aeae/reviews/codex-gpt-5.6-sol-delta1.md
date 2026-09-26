Delta re-review round 1, PR #7420 (D5 wrapper rework, C1-C4/N1-N7), same dispatch
mechanism as the gate's own council convening (env -i, codex-cli exec, --sandbox
read-only, model_reasoning_effort=high). HEAD at dispatch: the first rework commit
adding C1's 4 fixtures + C2/C3 code fixes. Condensed from the raw session transcript
(hook/tool-call noise and unrelated repo reads stripped); the full transcript is not
committed (see the gate's own precedent: scratchpad/gate7420/council/*.md are
condensed the same way, the raw transcripts stay in scratch).

La DELTA non chiude tutti i requisiti obbligatori.

| Voce | Esito                | Valutazione                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1   | Chiusa               | Le quattro fixture discriminanti richieste sono presenti. Il comportamento NUL è stato confermato direttamente su `/bin/sh` bash 3.2. La tabella di mutazione fornita dimostra che la rimozione integrale di ciascuna delle cinque guardie produce almeno un rosso.                                                                                                                                                                                                                                                                         |
| C2   | **Aperta**           | La guardia `[ -f ] && [ -x ]` è implementata correttamente nel wrapper, ma manca la fixture obbligatoria con `.../bin/codex` come directory 0755. Il caso `directory` esistente rende directory il pin file, non il binario. `_plant_pinned_codex()` crea sempre un file. Mutare soltanto il nuovo termine `-f` tornando alla vecchia verifica `-x` lascerebbe quindi la suite verde. La mutazione riportata elimina l'intero controllo ed è presa da `bin_missing`: non prova C2.                                                          |
| C3   | Parzialmente chiusa  | Il controllo pre-source su `RUNTIME_DIR` non ricercabile rifiuta con 78. Però la nuova fixture non riproduce il difetto dichiarato: il pin è `tmp_path/codex-pin.env`, mentre la directory resa 0644 è `tmp_path/runtime`, quindi sono fratelli, non contenitore e contenuto. Senza la nuova guardia, il test arriverebbe comunque a 78 perché il binario derivato dentro `runtime` non è statabile; diventa rosso solo per l'asserzione sul messaggio. Il pin deve stare dentro `world["runtime"]` per dimostrare il vero fallback legacy. |
| C4   | **Non verificabile** | Il prompt dichiara quattro condizioni C1-C4, ma riporta testualmente soltanto C1-C3. Anche ignorando questa omissione come refuso, C2 basta per il REWORK.                                                                                                                                                                                                                                                                                                                                                                                  |

N1-N7:

- N1, N2, N3, N4, N5, N6 e N7 risultano implementate.
- N1 e N4 non hanno però una regressione dedicata rispettivamente alle sei collisioni e al file mode-000.
- N5 soddisfa la richiesta, anche se la regex resta non ancorata.
- `actionlint`, `git diff --check`, `/bin/sh -n` e `bash -n` sono stati eseguiti da me con exit 0.
- La suite pytest e le mutazioni non sono state rieseguite: la sandbox read-only non dispone di una directory temporanea scrivibile. I risultati 23/23 e della mutation table sono quindi evidenza fornita, non esecuzione indipendente.
- Avviso non bloccante: l'Evidence Pack sul disco conserva ancora riferimenti a 17 test e la vecchia affermazione bash/dash; va riallineato, pur non essendo la causa del verdetto.

§Meta-pattern: le mutazioni eliminano blocchi composti, mentre i requisiti riguardano singoli termini e causalità della fixture. Questo spiega sia il falso senso di copertura C2 sia la fixture C3 che osserva il messaggio giusto senza ricreare il guasto giusto.

§Solo-operatore: nessuna azione necessaria; servono correzioni esclusivamente nel test corpus e il testo mancante di C4, se esiste davvero.

VERDICT: REWORK

## Disposition (this rework)

C2 fixture added (`bin_is_directory`), C3 fixture corrected (pin file moved inside
`world["runtime"]`), N1/N4 dedicated regressions added — see delta round 2 below,
which independently confirmed all three fixed via live shell mutation.
