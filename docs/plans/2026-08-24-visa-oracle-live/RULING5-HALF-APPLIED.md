# Il ruling #5 è applicato a un ramo su due — e quello scoperto è il ramo che scatta sempre

> Misurato 2026-08-25 eseguendo il mapper reale del frontend (`npx tsx`) e leggendo l'adattatore
> di backend su disco. **Corregge una mia affermazione di poche ore fa** e apre una decisione per
> Zero (Legge 5).

## Il fatto, in una riga

**Nessun richiedente `work` o `business` può ricevere un candidato.** Ogni singolo verdetto per
quelle due categorie è `HUMAN_REVIEW_REQUIRED` con `candidates=()` — una schermata a zero
risultati, che il ruling #5 del 2026-08-25 vieta esplicitamente.

## La misura

Eseguito il mapper vero su un richiedente ordinario — risponde a tutto, nessun «non sono sicuro»:

```
flags work     -> [ 'ACTIVITY_BOUNDARY' ]
flags business -> [ 'ACTIVITY_BOUNDARY' ]
flags tourism  -> [ ]
```

Perché: `mapDisclosedReviewFlags` (`fact-mapper.ts:454-471`) alza `ACTIVITY_BOUNDARY` se
`facts.work_role !== undefined` **oppure** `facts.business_activity !== undefined`. E quelle due
domande **sono sempre poste**: `work_role` è nella lista fissa del ramo `work` (`flow.ts:668`),
`business_activity` in quella del ramo `business` (`flow.ts:573`). Il reducer non lascia mai
assente la chiave di una domanda in-path al momento del verdetto — `SKIP` scrive il sentinella
`"unsure"`, mai `undefined` (documentato e verificato in `gold-oracle-baseline.ts:14-20`, e
`"unsure"` alza a sua volta `NOT_CERTAIN`). **Non c'è percorso che eviti il flag.**

E il flag cancella i candidati. `_apply_disclosed_review_flags`
(`evaluate_path.py:1262-1309`), letto su disco:

```python
payload.update({
    "state": "HUMAN_REVIEW_REQUIRED",
    "candidates": (),
    "missing_facts": (),
    ...
})
```

Il suo stesso docstring: _«This adapter cannot create or retain candidates.»_ Gira su **ogni**
valutazione pubblica, ultimo della catena `apply_public_policy_adapters`, dopo l'evaluator.

Prova di controllo (eseguita su contesto fresco, non ragionata): stessi fatti con
`intent.purposes = ["TOURISM"]`, che il motore risolve in `SUPPORTED_CANDIDATES ['B1','C1']` →
con il flag attivo il risultato finale è `HUMAN_REVIEW_REQUIRED`, `candidates=[]`,
`review_reasons=['DISCLOSED_ACTIVITY_BOUNDARY_REVIEW']`. **I candidati calcolati vengono buttati.**

## Perché è il ruling #5, e perché è mezzo applicato

Zero ha deciso il 2026-08-25 (`OWNER-RULINGS-2026-08-25.md` §5, `REVIEW-EMPTIES-CANDIDATES.md`):

> «Zero-risultati è vietato come schermata — ogni vicolo cieco diventa un candidato onesto + una
> mano tesa.» Lo stato resta `HUMAN_REVIEW_REQUIRED`, **i candidati già calcolati viaggiano con
> esso.**

Quella decisione è stata implementata su **un** ramo:

| superficie                                                                                               | stato ruling #5    |
| -------------------------------------------------------------------------------------------------------- | ------------------ |
| contratto congelato (`models.py`) — `candidates` ammessi su `HUMAN_REVIEW_REQUIRED`                      | ✅ fatto           |
| evaluator, ramo review **in-pack** (`evaluator.py`)                                                      | ✅ fatto           |
| frontend (`engine-adapter.ts`, ramo `HUMAN_REVIEW_REQUIRED`) — _«no longer structurally candidate-less»_ | ✅ pronto          |
| **`_apply_disclosed_review_flags` (`evaluate_path.py`)**                                                 | ❌ **non toccato** |

L'adattatore precede il ruling (il suo sha è pinnato dal 2026-08-16) e non è stato rivisitato.
Il risultato è la forma peggiore: **la cura è stata applicata al ramo raro e non a quello che
scatta sempre.** Il frontend è pronto a mostrare i candidati su una schermata di revisione; il
backend glieli toglie prima di spedirli.

## Correzione a quanto ho riferito prima

Poche ore fa ho scritto che un richiedente `work` reale «funziona, risponde `E23`». **Falso come
esperienza del cliente.** Il motore _calcola_ `SUPPORTED_CANDIDATES ['E23']` — quella misura è
corretta — ma io avevo misurato l'**evaluator**, non il **percorso consegnato**. L'adattatore a
valle sostituisce il verdetto prima che esca dal backend. È esattamente la trappola che questo
mandato ha già censito altrove: osservare il motore non è osservare ciò che il cliente riceve.

## Cosa NON so ancora, e non lo spaccio per saputo

- **Se sia voluto.** Il commento a `fact-mapper.ts:451-453` dichiara l'intento: una risposta di
  contesto umano che nessun `FactPath` firmato sa rappresentare _«may only lower the result to
  review»_. Come principio è onesto e coerente con _«Never an invented answer»_. Ciò che non torna
  è l'**azzeramento dei candidati**, che è precisamente ciò che il ruling #5 ha vietato.
- **Il volume.** Non ho misurato quanta parte del traffico reale sia `work`/`business`: la
  produzione non è raggiungibile da qui, e un conteggio locale spacciato per produzione sarebbe il
  proxy che questo mandato ha già censito.
- **Le altre categorie.** Ho misurato `work`, `business`, `tourism`. Restano da misurare `remote`,
  `family`, `invest`, `retirement`, `study`, `diaspora` (quest'ultima alza il flag di proposito, ed
  è corretto: è il suo instradamento a consulente).

## La decisione per Zero

Il principio «un dettaglio che il pack non sa leggere non può essere ignorato in silenzio» resta
giusto. La domanda è **cosa vede il cliente** quando scatta:

1. **L'adattatore conserva i candidati** (allinea il ruling #5 al ramo scoperto): stato
   `HUMAN_REVIEW_REQUIRED`, ragione della revisione, **e** i candidati che il motore aveva già
   calcolato, senza prezzo. Il cliente legge «sembri idoneo a E23, ma il tuo ruolo richiede una
   verifica: ti mettiamo in contatto». È la lettura letterale del ruling, ed è una riga
   nell'adattatore. **La raccomando.**
2. **Il flag smette di scattare su risposte ordinarie.** `work_role` e `business_activity` sono
   domande che l'intervista pone a tutti: alzano un'eccezione universale, che per definizione non è
   un'eccezione. Andrebbero ristrette ai valori che davvero eccedono il pack. Più giusto nel merito,
   più rischioso: serve decidere quali valori sono di confine, ed è sostanza normativa.
3. **Si lascia com'è e lo si dichiara**: `work` e `business` non sono self-service, per scelta.
   Difendibile — ma allora i tier T1/T2 del mandato non si applicano a quelle categorie, e va
   scritto in `TIER-MAP.md`, non lasciato accadere.

**Raccomando (1) subito** — è piccola, è letteralmente ciò che hai già deciso, e toglie la
schermata a zero risultati oggi — **e (2) come lavoro a sé**, con la sua spec, perché tocca il
merito.
