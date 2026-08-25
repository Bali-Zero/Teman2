# Ruling #5 — raggio d'impatto misurato, e la premessa che tre file danno per struttura

> Misurato 2026-08-25 dall'orchestratore, eseguendo il motore di produzione contro il pack
> **firmato** `rulepack-prod-013.source.json` (non il pack-fixture del gold harness). Riproducibile:
> lo script è `scratchpad/blast3.py`, costruito sugli stessi helper del test
> `test_e28_investor_golden_visa_reachability.py` (stesso `AT`, stesso identity provider non-segreto,
> stessi `_PLAUSIBLE_INVESTOR_OVERRIDES`).

## Cosa cambia, in una tabella

Investitore plausibile (PT PMA impegnato, capitale sopra i minimi E28A), al variare del solo
`intent.requested_product_code`:

| requested   | stato                     | candidati     | quotes |
| ----------- | ------------------------- | ------------- | ------ |
| _(nessuno)_ | SUPPORTED_CANDIDATES      | D12, E28A     | 0      |
| **E28B**    | **HUMAN_REVIEW_REQUIRED** | **D12, E28A** | 0      |
| **E28C**    | **HUMAN_REVIEW_REQUIRED** | **D12, E28A** | 0      |
| **E28D**    | **HUMAN_REVIEW_REQUIRED** | **D12, E28A** | 0      |
| **E28F**    | **HUMAN_REVIEW_REQUIRED** | **D12, E28A** | 0      |
| E33A        | SUPPORTED_CANDIDATES      | D12, E28A     | 0      |

Prima del fix quelle quattro righe avevano `candidates = []` — non per una scelta del ramo review ma
perché il contratto congelato lo **vietava**. Il raggio è quindi: **4 codici prodotto**, sul segmento
investitori.

Due correzioni a quanto circolava:

1. I candidati che riemergono sono **due**, non uno: `D12` viaggia insieme a `E28A`.
   `REVIEW-EMPTIES-CANDIDATES.md` citava solo E28A perché misurava una persona gold diversa. Chi
   scrive copy per «eccolo, il prodotto per cui sei idoneo» deve gestire una **lista**, non un
   singolare.
2. `quotes` resta `0` su ogni riga, incluse quelle nuove. Il contratto C1 regge: nessun prezzo può
   accompagnare quei candidati.

## La cosa che conta: nessun test esistente poteva vederlo

Il corpus gold ha **23 persone**. Eseguite tutte contro il motore di produzione:

- 7 finiscono in `HUMAN_REVIEW_REQUIRED`;
- **0 di esse porta candidati**, anche dopo il fix;
- 0 violazioni di C1.

Non è un caso fortunato: il gold harness compila un **pack-fixture**, non il pack firmato, e quel
pack non contiene affatto le regole E28B/C/D/F. La co-occorrenza «un prodotto SUPPORTED accanto a uno
in REVIEW» **non è esercitata da nessuna persona del corpus**.

Conseguenza operativa, ed è il motivo per cui questo documento esiste: la premessa che il frontend ha
scritto — _«every gold-oracle persona predicts HUMAN_REVIEW_REQUIRED with zero candidates, so tier
never applies there»_ — **è vera del corpus gold e falsa della produzione**. La shadow-parity resta
verde, il gold resta verde, e il difetto passa. Una prova verde qui non dice che la cosa funziona:
dice che la sonda e l'oggetto concordano, su un pack che non contiene la regola in questione.

## I tre punti che dicono la stessa cosa non vera

La credenza «se lo stato non è SUPPORTED_CANDIDATES allora non ci sono candidati» è scritta in tre
posti, e in due dei tre è un **commento che dichiara la propria premessa come fatto strutturale** —
quindi nessun test la corregge, perché i commenti non falliscono mai:

1. `models.py::Decision._check_state_conditionals` — era il contratto. **Curato** dal ruling #5.
2. `engine-adapter.ts`, ramo dei prossimi passi — la riga tier-aware è costruita solo per
   `SUPPORTED_CANDIDATES`; ogni altro stato prende la costante tier-agnostica. Dopo il fix un
   candidato T2 reale può comparire su uno schermo che gli dice il generico.
3. `OracleShell.tsx` (~riga 782) — `consultantTier = outcome?.state === "SUPPORTED_CANDIDATES" ? "T2" : "T3"`,
   col commento «Every other state has no supported candidate at all, so T3». Questo alimenta il
   **routing del consulente**, non la copy: un idoneo T2 verrebbe instradato come «consulente
   obbligatorio», che è falso su quella persona.

Il punto 1 è chiuso. **2 e 3 sono aperti e appartengono alla lane frontend** — questo documento è il
loro handoff, non un mandato d'implementazione: la scelta di come rendere la lista (uno? tutti? il
primo per rank?) è copy client-facing e passa da chi la possiede.

## Cosa NON è misurato, dichiarato per non passare per coperto

- Il comportamento a livello **endpoint/proiezione** con questi candidati: è la superficie del
  difetto `_build_display` (vedi la riga di ledger e la lane R5c). Qui è misurato il `Decision` del
  motore, non la risposta HTTP.
- Se esistano altre coppie prodotto-in-review / prodotto-supported oltre alle quattro E28 sul pack
  firmato: sondati E33A come controllo negativo (resta SUPPORTED, protetto dal suo HARD_FILTER), non
  l'intero catalogo a 38.
