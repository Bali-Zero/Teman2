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

---

## ✅ Deciso da Zero 2026-08-25 — e cosa è stato costruito

**Ruling**: il ruling #5 **non** si estende agli altri tre adattatori; al loro posto si costruisce
il messaggio specifico. Verbatim: _«ok, non applicarlo — costruisci il messaggio specifico»_.

La ragione, già argomentata sopra e confermata dalla decisione: il ruling #5 restituisce un
candidato **che continuiamo a ritenere giusto**; questi tre scattano precisamente quando non lo
riteniamo più (fonte revocata/stantia/non affidabile) o non dobbiamo mostrarlo a quella persona
(un minore). Un candidato lì non sarebbe «onesto», che è la parola che il ruling usa.

### Il difetto che la decisione ha scoperchiato — e non era teorico

I sette codici di quei tre adattatori **non avevano copia** nella mappa del frontend, quindi
cadevano tutti su `GENERIC_REVIEW_REASON`:

> _«Some of your answers need a person's judgment before we can confirm a path.»_

Per i sei controlli-fonte quella frase è **falsa**: dà la colpa alle risposte del richiedente
quando il richiedente ha risposto bene ed è **la nostra fonte** a essere sotto ri-verifica. In un
funnel di consulenza regolamentata è un'attribuzione di colpa sbagliata, non una vaghezza.

E non è un caso di laboratorio. Contato sul report di replay **live**
`research/visa/2026-08-15-gold-replay-live-post-notice-report.json` (28 KB, letto su disco):

```
DECISIVE_SOURCE_STALE           12
SAFETY_CRITICAL_SOURCE_STALE     6
MINOR_GUARDIAN_PRIVACY_REVIEW    4
```

Questi controlli scattano davvero, e quella frase è stata mostrata.

### Cosa è stato costruito

Sette messaggi specifici EN+ID in `REVIEW_REASON_COPY` (`engine-adapter.ts`), una frase ciascuno,
18-24 parole — allineati alla voce delle voci preesistenti (14-19). I sei della famiglia-fonti
chiudono tutti su _«our source, not your answers»_ / _«ini soal sumber kami, bukan jawaban Anda»_.

Due correzioni di merito fatte in corsa, entrambe su segnalazione di un revisore cross-family e
poi **corrette oltre** la sua proposta:

1. **`*_NOT_APPLICABLE` non vuol dire «revocata».** Quel codice copre un'UNIONE di cause (autorità
   secondaria, revocata, superata, non disponibile, non applicabile, non corrente). La prima
   stesura diceva _«is not currently applicable»_ / _«sedang tidak berlaku»_, e quest'ultima in
   registro legale indonesiano legge «la norma è stata revocata» — falso quando la causa reale è
   «questa citazione è un'autorità secondaria». Entrambe le lingue ora dicono che **non possiamo
   farci affidamento**, vero per ogni membro dell'unione.
2. **`krusial untuk keselamatan`**, non `sangat penting bagi keselamatan`: la seconda è
   grammaticale ma è enfasi da brochure, mentre «safety-critical» qui è una classificazione di
   rischio.

**Nessuna promessa di tempi**: le «24 ore lavorative» sono la promessa commerciale del ruling #2,
agganciata alla superficie T2. Ripeterla qui la estenderebbe a un contesto nuovo — decisione di
Zero, non di una mappa di copy. Il contatto del consulente è già nei passi successivi.

### Il guardiano

Nuovo blocco in `engine-adapter.test.ts` che estrae i codici **da `evaluate_path.py`** invece di
specchiarli a mano: un rinominamento lato Python diventa ROSSO invece di far ricadere in silenzio
quel caso sul messaggio generico. Include una guardia anti-vacuità (≥7 codici trovati, altrimenti
è la regex a essere rotta) e un'asserzione di sostanza: ogni messaggio della famiglia-fonti deve
contenere «our source»/«sumber kami» e non deve incolpare le risposte.

Provato per mutazione, non assunto:

- tolta una copia → 3 test rossi, incluso `no copy for system review hold DECISIVE_SOURCE_STALE`;
- rimessa la frase che incolpa il cliente → `expected 'some of your answers need a person's…' to
contain 'our source'`.

I sette codici sono usciti da `KNOWN_UNMAPPED_REVIEW_REASON_CODES`, la lista che li dichiarava
scoperti di proposito.

Suite: **647 test frontend su 47 file, verdi**. Verificato inoltre che `ReasonList`
(`OutcomeSheet.tsx:143`) renda davvero `reason.message` — il testo arriva sullo schermo.
