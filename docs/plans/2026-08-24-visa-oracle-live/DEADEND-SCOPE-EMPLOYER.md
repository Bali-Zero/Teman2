# Il dead end "EMPLOYER" — misura, non impressione

> **SINTESI PER ZERO, in una frase**: l'applicante ordinario sponsorizzato da un datore di lavoro
> privato **raggiunge oggi `SUPPORTED_CANDIDATES=[E23]` esattamente come dovrebbe** — il fatto
> mancante non lo blocca mai. Il dead end reale è più stretto e diverso nella FORMA da quanto la
> narrativa corrente (commit `32a85d002`, `GOLD-DIVERGENCE-TRIAGE.md`) suggerisce: colpisce solo
> **E23U** (assistente domestico diplomatico) ed **E23V** (ufficio commerciale), che **nessuna
> domanda dell'albero offre come opzione, per NESSUN `sponsor_category`** — non è una questione di
> "categorie fall-through". Questi due prodotti non restano bloccati: vengono **silenziosamente
> assorbiti nel verdetto E23 ordinario**, senza mai far scattare la review a cui sono destinati.
> Misurato eseguendo il motore vero contro il pack **firmato** `rulepack-prod-013.source.json`
> (mai la fixture del gold harness), non dedotto dal codice.

---

## Metodo (per riproducibilità)

Ogni numero qui sotto viene da uno script Python eseguito con:

```
cd apps/backend-rag && PYTHONPATH=. /Users/nuzantara/nuzantara/apps/backend-rag/.venv/bin/python <script>
```

contro `backend/services/visa_engine/contracts/packs/rulepack-prod-013.source.json`, caricato via
`backend.scripts.visa_engine.compile_pack.load_rule_pack_payload` +
`wrap_as_unsigned_pack` + `compiler.build_compiled_pack` — lo stesso pattern di
`test_e28_investor_golden_visa_reachability.py`. **Non è un envelope** (`json["payload"]` non
esiste a questo livello): le chiavi `products`/`rules`/`sequence`/... stanno alla radice del file —
verificato con un `json.load` diretto prima di scrivere qualunque script. Nessun file sorgente è
stato toccato; gli script scratch vivevano in `/tmp`, mai nel repo.

---

## 1 — I 13 rule che referenziano `intent.requested_product_code`

Cercato con una substring-match su `json.dumps(rule)` per ogni rule del pack firmato (111 rule
totali), poi risolto ogni `product_version_ids` al `product_code` via la lista `products` dello
stesso file.

| rule_id                                     | prodotto | stage        | effect         | on_unknown      |
| ------------------------------------------- | -------- | ------------ | -------------- | --------------- |
| `review.e28b.usd-threshold-manual`          | E28B     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e28c.usd-threshold-manual`          | E28C     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e28d.usd-threshold-turnover-manual` | E28D     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e28f.ikn-threshold-manual`          | E28F     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e33a.central-government-invitation` | E33A     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e33b.expertise-qualification`       | E33B     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e33c.central-government-invitation` | E33C     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e23u.requested-product`             | E23U     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `review.e23v.requested-product`             | E23V     | HUMAN_REVIEW | REQUIRE_REVIEW | **NEEDS_INPUT** |
| `el.bridging.destination-stated`            | BRIDGING | ELIGIBILITY  | SUPPORT        | **NEEDS_INPUT** |
| `el.bridging.t3-window-manual`              | BRIDGING | ELIGIBILITY  | SUPPORT        | NO_EFFECT       |
| `el.bridging.overstay-shield-payment`       | BRIDGING | ELIGIBILITY  | SUPPORT        | NO_EFFECT       |
| `el.bridging.source-status-verify`          | BRIDGING | ELIGIBILITY  | SUPPORT        | NO_EFFECT       |

Nessuna rule referenzia `intent.requested_product_code` con `on_unknown: HUMAN_REVIEW` (la terza
policy possibile, quella che escalerebbe automaticamente invece di bloccare). Le uniche due policy
in uso sono **NEEDS_INPUT** (10 rule) e **NO_EFFECT** (3 rule, tutte sul prodotto BRIDGING).

**Nota fuori-scope, per completezza dell'inventario (item 1 del mandato)**: le 4 rule BRIDGING sono
gated su `intent.purposes intersects OTHER` — la categoria interview `"other"`, non `"work"`. La sua
lista domande in `flow.ts` (`other: ["other_purpose","other_paid_activity","stay_days",
"entry_pattern"]`) non contiene NESSUNA domanda di product-code: `el.bridging.destination-stated`
(NEEDS_INPUT) è quindi una **quarta famiglia di dead end**, strutturalmente identica a E23U/E23V,
ma sotto la categoria `"other"` — non è parte del mandato di questo report (scope = `"work"` +
`EMPLOYER`) e non è stata misurata oltre l'identificazione della rule.

---

## 2 — Split NEEDS_INPUT vs inerte

**10 su 13** rule hanno `on_unknown: NEEDS_INPUT` — sono quelle che, quando il fatto è
UNKNOWN, fanno risolvere la **proof del LORO prodotto** a `BLOCKED_UNKNOWN`
(`evaluator.py:663-676`, per il meccanismo esatto vedi `_partition_unknowns_by_policy`).
Le altre 3 (`el.bridging.t3-window-manual`, `.overstay-shield-payment`, `.source-status-verify`)
sono `NO_EFFECT`: un `intent.requested_product_code` sconosciuto non le fa scattare né bloccare
nulla — sono innocue rispetto a questo fatto specifico (referenziano il fatto solo dentro un `neq`
per escludersi a vicenda dal caso BRIDGING vero, non per richiederlo).

**Punto load-bearing, verificato eseguendo il motore, non leggendo il codice**: una proof
`BLOCKED_UNKNOWN` per UN prodotto **non blocca l'intera Decision** se un ALTRO prodotto applicabile
è genuinamente `SUPPORTED`. `evaluate_with_trace` (`evaluator.py:1431-1441`) controlla
`supported = [proof SUPPORTED for proof in proofs]` **prima** di `blocked = [proof BLOCKED_UNKNOWN
for proof in proofs]` — se `supported` non è vuoto, la Decision è `SUPPORTED_CANDIDATES` e i
`blocked` non vengono mai nemmeno guardati. Questo è esattamente il meccanismo che il commit
`184e5f68f`/i test E28 descrivono per l'investitore E28A ("reaches SUPPORTED_CANDIDATES regardless"
di E28B/C/D/F bloccati) — e come misurato sotto, si applica **identico** a E23 rispetto a
E23U/E23V/E33A/E33B.

---

## 3 — Quali prodotti sono davvero irraggiungibili/bloccati per un applicante `work`+`EMPLOYER`

Misurato per-prodotto con `evaluator.evaluate_product` chiamato direttamente su OGNI prodotto del
pack firmato (38 prodotti), sui fatti reali che un applicante `category="work"`,
`sponsor_category="EMPLOYER"` produce (`intent.purposes=[EMPLOYMENT]`,
`work.employer_is_indonesian_entity=true`, `work.indonesian_work_sponsor_confirmed=true`,
`sponsor.type="EMPLOYER"` — quest'ultimo sempre KNOWN perché `sponsor_category` è la prima domanda
sia del ramo `"work"` che del ramo `"invest"`, non un fall-through).

Risultato — **E23 è l'UNICO prodotto la cui proof è SUPPORTED**:

```
E23      status=SUPPORTED       (el.e23-employment-support: TRUE)
E33A     status=EXCLUDED        hf.e33a.sponsor-not-government (sponsor.type=EMPLOYER != GOVERNMENT)
E33B     status=EXCLUDED        hf.e33b.sponsor-not-government-or-none (idem)
E33C     status=EXCLUDED        hf.e33c.sponsor-not-government-or-none (idem)
E23U     status=BLOCKED_UNKNOWN missing=['intent.requested_product_code']
E23V     status=BLOCKED_UNKNOWN missing=['intent.requested_product_code']
E28A     status=EXCLUDED        (capitale sotto minimo — irrilevante qui)
... (resto EXCLUDED per purpose/nazionalità/età, non correlato)
```

**Quindi, con `sponsor.type` KNOWN (cioè con `sponsor_category` risposto — sempre vero in
produzione), E33A/B/C non sono nemmeno `BLOCKED_UNKNOWN`: sono `EXCLUDED` a monte dal loro
proprio `HARD_FILTER` "sponsor-not-government[-or-none]", PRIMA che la loro rule di review su
`requested_product_code` venga mai raggiunta.** Il dead end reale, per un `EMPLOYER`, riguarda
**solo E23U ed E23V** — e la loro `BLOCKED_UNKNOWN` non impedisce mai il verdetto aggregato, perché
E23 stesso è `SUPPORTED` (vedi §5).

---

## 4 — LA MISURA CENTRALE: persona #15, letterale vs forma reale, con e senza il fatto

Il mandato chiedeva di riprodurre l'esatto fact-set della persona gold #15
(`test_evaluator_gold.py::PERSONAS[id=15]`, label _"tourism + employment purposes -> E23 only,
never C1"_) e mostrare il verdetto con/senza `intent.requested_product_code`. L'ho fatto — e il
risultato **si biforca in due misure diverse a seconda di QUALI fatti si passano**, ed è questa
biforcazione stessa il ritrovamento principale di questo report.

### 4a — I fatti LETTERALI della persona #15 (come autorati nel gold corpus)

```python
overrides = {
    "intent.purposes": known(["TOURISM", "EMPLOYMENT"]),   # <-- MULTI-purpose
    "work.employer_is_indonesian_entity": known(True),
    "work.indonesian_work_sponsor_confirmed": known(True),
}
```

```
SENZA intent.requested_product_code:
  state = NEEDS_INPUT
  missing_facts = ['intent.requested_product_code']

CON intent.requested_product_code = "E23":
  state = NEEDS_INPUT
  missing_facts = ['sponsor.type']          <-- NON PIÙ lo stesso fatto!
```

Questo **conferma byte-per-byte** la misura del commit `32a85d002` (_"gold_replay_driver.py
--offline ... persona #15 still NEEDS_INPUT missing_facts=['intent.requested_product_code']"_) —
ma il secondo run rivela che anche dando il fatto mancante, il verdetto **resta** `NEEDS_INPUT`,
solo con un motivo diverso. La causa, isolata chiamando `evaluate_product` prodotto-per-prodotto
(non l'aggregato): **E23 stesso non diventa mai `SUPPORTED` con questi fatti letterali** — la sua
proof risulta `UNSUPPORTED` con `missing_purposes={'TOURISM'}`. Il motivo è nel motore
(`evaluator.py:678`, `if purposes <= covered: ... SUPPORTED`): E23 nel pack **firmato** dichiara
`covered_purposes: ['EMPLOYMENT']` — SOLO employment — mentre `intent.purposes` della persona è
`{TOURISM, EMPLOYMENT}`; l'unione dei purpose coperti da regole vere per E23 non include mai
TOURISM, quindi E23 non copre l'intero set dichiarato e la sua proof cade a `UNSUPPORTED`, mai
`SUPPORTED`. Con E23 fuori gioco, l'unico blocco rimanente più piccolo (E33A/B/C via `sponsor.type`
ignoto — qui non impostato) vince come `missing_facts` minimo.

**Questo è un difetto SEPARATO, non lo stesso dead end.** Nel pack di FIXTURE che
`_gold_fixtures.py` costruisce per il gold harness (quello con SOLO 5 prodotti, mai usato qui come
motore ma citato per spiegare l'origine della persona), E23 è dichiarato con
`covered_purposes=["EMPLOYMENT", "TOURISM"]` — entrambi i purpose, quindi lì la copertura è
banale e la persona passa. Nel pack **firmato di produzione**, E23 copre solo EMPLOYMENT. La
persona letterale (multi-purpose) e il pack di produzione non sono mai stati fatti combaciare su
questo punto — è una divergenza fixture/produzione preesistente, non introdotta né chiusa da questo
mandato, e riguarda `intent.purposes` multi-valore, non `intent.requested_product_code`.

### 4b — La forma che la UI REALE produce per un `EMPLOYER` (single-purpose)

`fact-mapper.ts::mapPurposes` usa `CATEGORY_TO_PURPOSE`, una `Partial<Record<CategoryKey,
Purpose>>` — **un solo Purpose per categoria**, mai un array multi-valore
(`work: "EMPLOYMENT"`, verificato leggendo la costante, `fact-mapper.ts:294-305`). Nessun
percorso dell'interview reale produce mai `intent.purposes` contenente sia TOURISM che EMPLOYMENT
insieme per un applicante `"work"`. La forma reale per un `EMPLOYER` è quindi:

```python
overrides = {
    "intent.purposes": known(["EMPLOYMENT"]),     # <-- SINGLE-purpose, come produce la UI vera
    "work.employer_is_indonesian_entity": known(True),
    "work.indonesian_work_sponsor_confirmed": known(True),
    "sponsor.type": known("EMPLOYER"),
}
```

```
SENZA intent.requested_product_code:
  state = SUPPORTED_CANDIDATES
  candidates = ['E23']
  missing_facts = []

CON intent.requested_product_code = "E23":
  state = SUPPORTED_CANDIDATES
  candidates = ['E23']
  missing_facts = []        <-- IDENTICO. Il fatto mancante non cambia nulla per questo applicante.
```

**Non c'è dead end per questa forma.** Il fatto mancante è invisibile al verdetto finale, perché
`evaluate_with_trace` sceglie `SUPPORTED` prima ancora di guardare i prodotti `BLOCKED_UNKNOWN`
(§2). `gold_replay_driver.py --offline` importa `PERSONAS` **letteralmente** da
`test_evaluator_gold.py` (`from ...test_evaluator_gold import PERSONAS`) e le passa dirette al pack
firmato via `_gold_fixtures.applicant_facts()` — **non** passa mai per `flow.ts`/`fact-mapper.ts`.
È quindi una misura legittima di "cosa succede se questi fatti letterali colpiscono il pack vero",
ma non è una simulazione del percorso reale che un applicante `EMPLOYER` percorre nell'interview —
e il commit `32a85d002`, pur avendo verificato correttamente via `flow.test.ts` che la domanda non
viene mai posta, **non aveva eseguito il motore sulla forma single-purpose reale** per confermare
che quell'assenza si traduca in un verdetto peggiore. Rieseguita qui: non lo fa.

### 4c — Per completare il quadro: cosa succederebbe se la domanda ESISTESSE per E23U/E23V

```
forma reale + intent.requested_product_code = "E23U":
  state = HUMAN_REVIEW_REQUIRED
  candidates = ['E23']                                            <-- E23 non sparisce (ruling #5)
  review_reasons = [('E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW', ('review.e23u.requested-product',))]
```

Questo è il verdetto CORRETTO che un vero applicante E23U dovrebbe ricevere — e che oggi non può
mai ricevere, per NESSUN `sponsor_category`, perché nessuna domanda dell'albero offre mai "E23U" o
"E23V" come valore possibile di `intent.requested_product_code` (vedi §5). Al loro posto, ricevono
silenziosamente `SUPPORTED_CANDIDATES=['E23']` — il prodotto sbagliato per il loro caso, senza la
review a cui il pack li destina.

---

## 5 — E23U/E23V: non è un problema di `sponsor_category` fall-through

Il mandato chiedeva di verificare se il danno fosse confinato a E23U/E23V o si estendesse a E23
ordinario. La risposta empirica (§4b) è: **E23 non è mai in pericolo**. Ma verificando DOVE
`intent.requested_product_code` può essere impostato a "E23U"/"E23V", il quadro è più severo di
"le 4 categorie fall-through":

- `employment_product_code_govt` (posta solo se `sponsor_category="GOVERNMENT"`): opzioni
  `E33A`, `E33B`, `STANDARD` — **non E23U, non E23V** (`tree.ts:737,741,745`).
- `employment_product_code_none` (posta solo se `sponsor_category="NONE"`): opzioni `E33B`,
  `STANDARD` — **non E23U, non E23V** (`tree.ts:769,773`).
- Nessun'altra domanda del ramo `"work"` scrive `intent.requested_product_code`. `work_role`
  (executive/manager/specialist/performer/other) ha `decisionMapping: HUMAN_CONTEXT` — alimenta
  solo i review-flag narrativi, mai un product code (`tree.ts:548-564`).
- L'unica altra occorrenza di "E23U"/"E23V" nell'albero è `stay_permit_code`
  (`tree.ts:227-228`) — una domanda **completamente diversa**, gated da `holds_stay_permit==="yes"`,
  che alimenta `immigration.current_status_code` (il KITAS/ITAS **già posseduto**), non
  `intent.requested_product_code`. Verificato che i due FactPath sono distinti
  (`fact-mapper.ts::mapCurrentStatusCode` vs `mapRequestedProductCode`) — confonderli sarebbe
  un errore di lettura, non un percorso reale.

**Conclusione**: E23U ed E23V sono strutturalmente irraggiungibili per QUALSIASI valore di
`sponsor_category` — incluso GOVERNMENT e NONE, le due categorie già "curate" da V1/E33. Non è un
residuo del fall-through EMPLOYER/INDIVIDUAL/EDUCATION/INVESTMENT: è che nessuna opzione
esistente in nessuna domanda offre mai questi due codici. La cura di V1/E33 (aggiungere
`employment_product_code_govt`/`_none`) ha reso raggiungibili E33A/E33B, ma non includeva E23U/E23V
tra le opzioni — probabilmente perché non era nel loro scope dichiarato (V1/E28+V1/E33, non
E23U/E23V).

---

## 6 — Probe a una differenza sui 4 `sponsor_category` fall-through sotto `"work"`

Per completezza (item 5 del mandato): ripetuto lo stesso probe a una differenza — stessi fatti
`work.*`, `intent.purposes=[EMPLOYMENT]`, solo `sponsor.type` variato — per `EMPLOYER`,
`INDIVIDUAL`, `EDUCATION`, `INVESTMENT` (i 4 valori che non ricevono nessuna domanda di product
code sotto `"work"`; `sponsor_category` non gate nessun fatto rilevante per E23 oltre a
`sponsor.type`, che nessuna rule di E23 referenzia — vedi §3).

| `sponsor_category` | senza `requested_product_code` | con `requested_product_code="E23"`      |
| ------------------ | ------------------------------ | --------------------------------------- |
| EMPLOYER           | `SUPPORTED_CANDIDATES=[E23]`   | `SUPPORTED_CANDIDATES=[E23]` (identico) |
| INDIVIDUAL         | `SUPPORTED_CANDIDATES=[E23]`   | `SUPPORTED_CANDIDATES=[E23]` (identico) |
| EDUCATION          | `SUPPORTED_CANDIDATES=[E23]`   | `SUPPORTED_CANDIDATES=[E23]` (identico) |
| INVESTMENT         | `SUPPORTED_CANDIDATES=[E23]`   | `SUPPORTED_CANDIDATES=[E23]` (identico) |

**Le 4 righe sono byte-identiche.** Nessuna delle quattro categorie fall-through produce un
verdetto diverso da `EMPLOYER` — atteso, perché nessuna di esse cambia alcun fatto che una rule di
E23 legga. La biforcazione osservata (§4a vs §4b) dipende esclusivamente dal _numero di purpose_
dichiarati (`[TOURISM,EMPLOYMENT]` vs `[EMPLOYMENT]`), non dal valore di `sponsor_category`.

---

## 7 — Risposta diretta alla domanda dell'owner

**Quante forme di applicante distinte raggiungono oggi un dead end reale (verdetto peggiore di
quello dovuto), e l'estero-impiegato ordinario è tra queste?**

**No, l'applicante impiegato ordinario NON è tra queste.** Misurato, non dedotto: per
`category="work"` con QUALSIASI dei 6 valori di `sponsor_category` (GOVERNMENT/NONE inclusi), un
applicante che soddisfa la SUPPORT rule di E23 riceve `SUPPORTED_CANDIDATES=[E23]` — l'assenza
della domanda di product code non ha alcun effetto osservabile sul suo verdetto, perché la
precedenza del motore fa vincere `SUPPORTED` prima di guardare qualunque prodotto sorella
`BLOCKED_UNKNOWN`.

**Le forme che raggiungono davvero un esito peggiore di quello dovuto sono 2, e non sono un "dead
end" nel senso di un blocco visibile — sono un `SUPPORTED_CANDIDATES=[E23]` invece del
`HUMAN_REVIEW_REQUIRED` corretto**: un applicante il cui caso reale è **E23U** (assistente
domestico di un diplomatico straniero) o **E23V** (staff di un ufficio commerciale/economico),
per QUALSIASI `sponsor_category` scelga — non solo i 4 fall-through. Il pack li vuole sotto
verifica manuale (`REQUIRE_REVIEW`); oggi vengono invece serviti, silenziosamente, come E23
ordinario, perché nessuna domanda dell'interview permette mai di nominarli.

**Una terza forma esiste ma è fuori scope**: un applicante `category="other"` il cui vero prodotto
è BRIDGING riceve `NEEDS_INPUT` reale (non assorbito, perché BRIDGING non ha un rule ELIGIBILITY di
supporto indipendente dal fatto — `el.bridging.destination-stated` stessa è la sola via a
`SUPPORTED`), un vero blocco strutturalmente identico a quello che il briefing ipotizzava per
"work"+EMPLOYER — solo che accade sotto `"other"`, non `"work"`. Non misurato oltre
l'identificazione della rule (§1); lasciato a chi possiede quella lane.

**Sulla persona gold #15 stessa**: il suo fact-set letterale (multi-purpose TOURISM+EMPLOYMENT)
produce davvero `NEEDS_INPUT` contro il pack firmato — confermando la misura del commit
`32a85d002` — ma per una causa diversa da quella lì attribuita (E23 non copre TOURISM nel pack di
produzione, non "la domanda non è mai stata posta"): il fix del product-code non lo risolverebbe
(§4a, secondo run: il fatto mancante cambia da `intent.requested_product_code` a `sponsor.type`,
`NEEDS_INPUT` resta). Questo non contraddice che la domanda sia davvero assente per `EMPLOYER` —
lo è, verificato via `flow.test.ts` e via `tree.ts` (§5) — contraddice solo l'inferenza che
quell'assenza sia la causa del `NEEDS_INPUT` misurato su quella persona specifica, e che colmarla
curerebbe la persona #15 letterale.

---

## Cosa NON è stato fatto (per disciplina, non per omissione)

- Nessuna proposta di quale prodotto mostrare a un applicante EMPLOYER — decisione di prodotto,
  riservata a Zero, esplicitamente fuori mandato.
- Nessuna modifica a `flow.ts`, `tree.ts`, `fact-mapper.ts` o al pack — solo lettura + esecuzione
  del motore in `/tmp`, mai nel repo.
- Non misurato se BRIDGING (§1, §7) sia davvero un dead end vivo per un applicante `"other"` reale
  end-to-end (solo la rule è stata letta) — lasciato alla lane che possiede quella categoria.
- Non ri-verificata la correttezza di V1/E28 o V1/E33 per GOVERNMENT/NONE (già testata da
  `test_e28_investor_golden_visa_reachability.py` e dai nuovi blocchi in `flow.test.ts`) — presa
  per buona, solo la sua estensione (o mancata estensione) a E23U/E23V è stata verificata qui.
