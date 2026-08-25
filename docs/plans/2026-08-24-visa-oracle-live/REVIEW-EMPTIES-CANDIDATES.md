# Una regola di review su UN prodotto cancella i candidati di TUTTI

> ✅ **RISPOSTO da Zero 2026-08-25 — scelta l'opzione (2)**, come raccomandato: lo stato resta
> `HUMAN_REVIEW_REQUIRED`, i candidati già calcolati viaggiano con esso. «Zero-risultati è vietato come
> schermata — ogni vicolo cieco diventa un candidato onesto + una mano tesa.»
> ⚠️ **Non è la riga sola descritta qui sotto**: il contratto congelato vieta `candidates` E `quotes`
> su ogni stato ≠ SUPPORTED (3 livelli + 2 test verdi). Design adottato dopo confutazione
> cross-family: allentare `candidates` **solo** per `HUMAN_REVIEW_REQUIRED`, `quotes` vietato ovunque —
> perché il divieto su `quotes` **da solo** impedisce già il bottone «compra» (C1). Autorità:
> `OWNER-RULINGS-2026-08-25.md` §5.

> Misurato 2026-08-25 eseguendo il motore contro il pack **firmato** `rulepack-prod-013`
> (firma Ed25519 verificata davvero, `payload_sha256 = b9edb809…`, mai finta).
> Decisione richiesta a Zero: è il comportamento voluto?

## La misura

Persona gold `09_investor.json` — investitore singaporiano, PT PMA impegnato, capitale sopra i
minimi E28A. Un candidato legittimo.

```
BASELINE (senza intent.requested_product_code)
  decision.state = SUPPORTED_CANDIDATES
  candidates     = [E28A]
  review_reasons = []

CON intent.requested_product_code = "E28B"
  decision.state = HUMAN_REVIEW_REQUIRED
  candidates     = []                       <-- E28A SPARITO
  review_reasons = ['E28B_USD_THRESHOLD_MANUAL_CHECK']
```

Nominare un prodotto diverso non declassa il verdetto: **azzera la lista dei candidati.**
L'investitore non vede più il visto per cui è idoneo.

## Il meccanismo, e perché non è locale

`evaluator.py:1397-1400`:

```python
review = [proof for proof in proofs if proof.status is ProductProofStatus.REVIEW]
if review:
    review_reasons = _dedupe_reasons(...)
    return assemble(state=DecisionState.HUMAN_REVIEW_REQUIRED, review_reasons=review_reasons)
```

Due proprietà, entrambe deliberate, che insieme producono l'effetto:

1. Il filtro `review` gira su **tutti i 38 prodotti**, non su quello richiesto. Una sola prova di
   REVIEW ovunque nel catalogo vince.
2. Il ramo `assemble(...)` non passa i candidati. Non è che perdano la precedenza: **non vengono
   proprio inclusi**.

Quindi una regola `HUMAN_REVIEW` di scope `PRODUCTS` attaccata a **E28B** cancella la visibilità di
un SUPPORTED su **E28A** — prodotti diversi, nessuna relazione fra loro se non stare nello stesso
catalogo.

## Perché è E28 e non E33 — l'asimmetria che va detta

La lane V1 aveva provato che il rischio _non_ si materializza, e per E33 aveva ragione: E33A/B/C
portano un HARD_FILTER di scope `PRODUCTS` su `sponsor.type`, e un HARD_FILTER TRUE ritorna
`EXCLUDED` prima che il ramo review venga usato — gli `EXCLUDED` affondano in `NO_SUPPORTED_PATH`,
non promuovono nulla.

**E28B/C/D/F non hanno alcun HARD_FILTER di prodotto.** Hanno solo le due globali che ogni prodotto
del pack eredita (`hf.citizen`, `hf.overstay-exceeds-60-days`). La loro unica regola specifica è la
`HUMAN_REVIEW` su `{purposes intersects INVESTMENT} AND {requested_product_code == "E28x"}`.

Quindi la prova di sicurezza fatta su E33 **non si trasporta** su E28: sono due forme di regola
diverse, e la protezione che salva la prima non esiste sulla seconda. Chi legge il test di E33 come
garanzia generale sbaglia.

## Cosa c'entra il lavoro appena fatto

Prima del fix V1, `intent.requested_product_code` era cablato `NOT_ASKED`: la regola E28B era
`BLOCKED_UNKNOWN`, cioè inerte, e questo effetto non poteva accadere. Il fix è **giusto e ordinato
da Zero** (ruling 24/8: rendere il prodotto visibile _e_ rinviare a operatore). Ma rendendo il
fatto ottenibile ha reso raggiungibile anche questa conseguenza, che nessuno dei due aveva misurato.

E la superficie è appena cresciuta: oggi sono diventati raggiungibili **7 prodotti** (E28×4 +
E33×3). Le tre E33 sono protette dal loro HARD_FILTER; le quattro E28 no.

## La cosa che il ruling di Zero dice e la regola non fa

Il ruling del 24/8 parla di _«rinvio a operatore sopra soglia»_. La regola si chiama
`review.e28b.usd-threshold-manual`, ma **nella sua condizione non c'è nessuna soglia**: la soglia è
ciò che l'umano verifica, non ciò che la regola controlla. Quindi scatta per QUALUNQUE investitore
che nomini E28B, a qualunque cifra — inclusi quelli ben sotto, per cui la risposta giusta sarebbe
E28A e basta.

## La domanda per Zero

Il contratto a cinque esiti mette `HUMAN_REVIEW_REQUIRED` sopra `SUPPORTED_CANDIDATES`, e su questo
non si discute: se serve una persona, il verdetto lo dice. **La domanda è un'altra: quando serve una
persona, il cliente deve perdere anche l'informazione che aveva già?**

Tre risposte, e non sono equivalenti:

1. **Sì, com'è ora.** Difendibile: mostrare candidati accanto a «serve una persona» può leggersi
   come una risposta data. Costo: un investitore idoneo a E28A che chiede di E28B esce con niente,
   e verosimilmente riparte da capo o se ne va.
2. **No: stato `HUMAN_REVIEW_REQUIRED`, ma i candidati restano visibili** come «già idoneo a
   questo, e la tua domanda su E28B richiede una persona». È più informativo e più onesto, e non
   viola la precedenza — cambia solo cosa `assemble` porta con sé sul ramo review.
3. **Restringere il filtro `review` al prodotto richiesto** invece che a tutti i 38. È il cambiamento
   più profondo e il più rischioso: tocca il cuore della precedenza, che è stata sistemata da un fix
   P0 precedente. Non lo raccomando senza un mandato a sé.

**Raccomandazione**: (2). Non tocca la precedenza — che resta com'è — e restituisce al cliente
l'informazione che il motore ha già calcolato. (1) è lo stato attuale e va scelto esplicitamente, non
per inerzia.

## Provenienza

Concern sollevata dall'orchestratore su E28, confutata dalla lane V1 su E33 (correttamente, per
E33), poi misurata da un terzo su contesto fresco eseguendo il motore — non ragionandoci sopra. Il
terzo ha anche corretto la lane su un punto di precisione: le regole HUMAN_REVIEW **sono** valutate
prima del ramo HARD_FILTER (per la traccia di audit completa, `evaluator.py:577-585`), semplicemente
il loro esito non viene usato quando un HARD_FILTER è TRUE. «Non consultate affatto» era impreciso;
l'effetto no.
