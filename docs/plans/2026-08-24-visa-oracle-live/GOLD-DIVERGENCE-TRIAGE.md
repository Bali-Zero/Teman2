# Gold-persona divergence triage (owner switchboard #3)

Run 2026-08-24 on Pro: `gold_replay_driver.py --offline` against the signed pack
`rulepack-prod-013` (sequence 13, kid `prod-2026-07-1`, signature verified by the driver).

```
matches 4/20    personas_with_divergence 16    explained_divergences 0    unexplained 16
```

The 16 had never been opened. They are opened here. **They are not 16 engine defects — they are
one defect and fifteen explanations**, and the explanations matter more than the count.

## The headline

| Class                                                        | N     | What it means                                                                                                             |
| ------------------------------------------------------------ | ----- | ------------------------------------------------------------------------------------------------------------------------- |
| The corpus tests a smaller catalogue than the engine has     | 7     | Not a defect                                                                                                              |
| The engine is deliberately MORE conservative than the corpus | 6     | Not a defect — a later safety rule firing (was 5; persona #5 was missing, see below)                                      |
| The engine asks a different question first                   | 2     | Not a defect — reachable either way                                                                                       |
| **A real dead end**                                          | **1** | **#15 — V1 cured the E28/E33 shape of this disease, but not persona #15's own branch (2026-08-25: measured, still open)** |

## Class 1 — the corpus tests five products; the engine has thirty-eight (7 personas)

`_gold_fixtures.py` builds a SYNTHETIC pack containing exactly five product codes: **E28A, E31,
E23, E33G, C1**. Measured, not assumed: `grep -c 'D12' _gold_fixtures.py` returns **0**. So do
E31A/E31B/E31D and B1.

Personas **7, 8, 9, 10, 16, 17, 19** diverge because the engine answers with a product the corpus
has never heard of. Their `NO_SUPPORTED_PATH` expectations do not mean _"no visa in Indonesia fits
this person"_ — they mean _"none of these five fits"_. Read against the real catalogue they are
simply wrong questions.

The sharpest example, and the one most likely to be misread as a scandal: **persona 16, "investor
capital 1 IDR below minimum -> no supported path"**, where the engine offers **D12**. D12 is the
_pre-investment_ multiple-entry visit visa. Offering it to an investor who falls just under the
KITAS threshold is plausibly the **commercially correct** answer — come and look around first. The
corpus could not say that because D12 did not exist in its world.

D12 has carried six ELIGIBILITY rules since pack 009 — this is not recent drift; the corpus has
simply never been re-based.

## Class 2 — the engine is more conservative than the corpus, on purpose (5 personas)

Each of these is a safety rule that was added AFTER the corpus was written, now correctly firing:

| #   | Persona                                        | The engine adds                                                                      |
| --- | ---------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1   | ID citizen excluded outright                   | `CITIZENSHIP_LIST_DIVERGENCE` — escalates to a human instead of refusing outright    |
| 5   | minor without confirmed guardian               | `MINOR_GUARDIAN_PRIVACY_REVIEW` **added 2026-08-25** — see the arithmetic note below |
| 6   | minor child with confirmed family sponsor      | `MINOR_GUARDIAN_PRIVACY_REVIEW`                                                      |
| 11  | clean remote worker, no local footprint        | `E33G_INCOME_EVIDENCE_REVIEW`                                                        |
| 14  | tourism + remote-work purposes                 | `E33G_INCOME_EVIDENCE_REVIEW`                                                        |
| 20  | onshore conversion, status+overstay unprovided | `BRIDGING_FROM_VISIT_ITK_PROHIBITED`, `BRIDGING_TO_BRIDGING_PROHIBITED`              |

**Persona 20 is worth naming: that is Zero's bridging ruling of 2026-08-23 being enforced.** The
corpus expected the engine to ask for more facts; the engine instead recognises a prohibited
bridging transition and stops. That is the ruling working, showing up as a "failure".

A divergence in this direction costs a consultant's time. The opposite direction costs a wrong
visa. These five are the cheap side, and they should be re-based, not "fixed".

## Class 3 — a different question first (2 personas)

- **#2** conflicting nationality evidence: expected `CITIZENSHIP_EVIDENCE_CONFLICT`, got
  `CALLING_VISA_REVIEW` + `CITIZENSHIP_LIST_DIVERGENCE`. Same state, richer reasons.
- **#13** remote worker: expected to be asked `work.serves_indonesian_clients`, asked `sponsor.type`
  instead. Same state; both are real, askable facts, so the interview still terminates.

## Class 4 — the one real defect: persona 15

```
#15  tourism + employment purposes -> E23 only, never C1
     expected  SUPPORTED_CANDIDATES  candidates=[E23]
     actual    NEEDS_INPUT           missing_facts=['intent.requested_product_code']
```

The engine does not answer. It asks for **`intent.requested_product_code`** — the fact that
`fact-mapper.ts` hard-codes to `unknownFact(NOT_ASKED)`, which the interview can never populate.

**This is a dead end, not a question.** The visitor is told more information is needed, and no
answer they can give will ever supply it. Every other divergence in this report ends with the
visitor somewhere — a product, a consultant, an honest refusal. This one ends nowhere.

It is the same disease that makes E28B/C/D/F invisible, and it proves the disease is **wider than
those four products**: here it damages **E23**, a product that is otherwise healthy, priced, and
proposed T2. Lane V1 is curing it. This persona is its regression test — it must flip from
`NEEDS_INPUT` to `SUPPORTED_CANDIDATES [E23]` when the cure lands, and that flip is the
falsifiable acceptance.

### Update 2026-08-25 — re-measured after V1/E28 + V1/E33 shipped. Still a dead end for #15.

Re-ran the driver on this turn, same command, same active signed pack (`rulepack-prod-013.signed.
json`, verified sequence=13, kid=`prod-2026-07-1` — same pack this doc's header names):
**matches 4/20, unexplained 16 — byte-identical to the numbers above.** `intent.requested_product_code` is no longer unconditionally hard-coded to
`unknownFact(NOT_ASKED)` — V1 shipped and made it askable on two branches
(`fact-mapper.ts`/`tree.ts`/`flow.ts`, both merged since this doc's first pass): unconditionally
on the "invest" category (`investment_product_code`, every vehicle), and on the "work" category
only when `sponsor_category` is `GOVERNMENT` (`employment_product_code_govt`) or `NONE`
(`employment_product_code_none`). Persona #15's shape does not land on either gate.

**The correction to the paragraph above:** it is not that "the interview can never populate" this
fact anymore — it now can, for some applicants. Persona #15 is not one of them. Its raw engine
facts (`work.employer_is_indonesian_entity=true`, `work.indonesian_work_sponsor_confirmed=true`)
map back, on the real UI, to `category: "work"` with `sponsor_category: "EMPLOYER"` — an ordinary
private-employer-sponsored applicant, which is the common case E23 exists for, not an edge case.
Measured directly against the real reducer (`flow.ts`'s `getCategoryQuestionIds`, `category ===
"work"` branch — the ternary there has exactly two arms, `GOVERNMENT` and `NONE`; every other
`sponsor_category` value, including `EMPLOYER`, falls through to `[]`): the interview walks such
an applicant straight through `sponsor_category → work_payer → work_indonesia_compensation →
work_sponsor_confirmed → work_role → stay_days` to a verdict screen without ever presenting a
question that can set `intent.requested_product_code`. No UI navigation dead-end — the interview
completes normally — but the wire fact reaches `UNKNOWN NOT_ASKED`, and `review.e23{u,v}.
requested-product` (`on_unknown: NEEDS_INPUT`, both `required_facts` include this key) then
returns exactly the NEEDS_INPUT above. **The visitor still cannot supply the fact the engine is
asking for.**

This is now pinned by two independent, currently-passing tests (both go RED if this ever changes,
which is the signal to revisit this entry):

- `fact-mapper.test.ts`, describe `"V1/E33 (2026-08-25): sponsor-gated E33A/B/C -> intent.
requested_product_code"`, the TEAM-LEAD-MANDATED INNOCENCE TEST — already proves EMPLOYER (with
  INDIVIDUAL/EDUCATION/INVESTMENT) never reaches the product-code questions and the mapped fact
  stays `NOT_ASKED`, for a different original purpose (an `el.bridging.destination-stated`
  unreachability proof) that happens to cover this exact shape.
- `flow.test.ts`, new describe `"V1 dead end PERSISTS: persona #15 (GOLD-DIVERGENCE-TRIAGE.md
Class 4, switchboard-3 rehearsal 2026-08-25)"` — drives the real reducer end-to-end through
  persona #15's shape (the `CATEGORY_CASES` "work"/EMPLOYER branch), confirms no
  product-code-setting question is ever asked, and confirms the mapped wire fact.

**Persona #15 stays in Class 4, open, a live dead end.** Signature #3 ("zero-divergence
rehearsal... acknowledge, sign") is **not earnable yet**. The fix is a product decision, not an
engine or mapper bug: whether/what product-code question(s) an ordinary EMPLOYER-sponsored
applicant should be asked at all (E23 itself needs no code; only the two review carve-outs
`E23U`/`E23V` — diplomatic household staff, trade-office staff — do), and that decision was
explicitly out of scope for this turn (per the mandate: "do not redesign the interview tree
without a spec; that is a product decision").

## What this means for switchboard #3

The mandate asks for a "gold-persona rehearsal — zero-divergence report engine<->consultants" for
Zero to acknowledge and sign.

**"Zero divergences" is the wrong target, and reaching it by rewriting expectations to match the
engine would be reward-hacking with extra steps.** Fifteen of these sixteen are the corpus being
older and smaller than the engine; forcing them to zero teaches us nothing and destroys the record
of five safety rules working.

The target that means something:

> **Every divergence explained, and none of them a dead end.**

Today: 16 explained (this document), 1 dead end (#15). **Update 2026-08-25:** re-measured after
V1/E28 and V1/E33 shipped — #15 did not flip, and per the Class 4 update above it is not a cure
already "in flight" that will land on its own: the branch that would have to change (an
EMPLOYER-sponsored applicant on the "work" category) needs an explicit product decision that has
not been scoped yet. When #15 flips, the report is signable — with the divergences intact and
accounted for, not erased.

## What must happen to the corpus, and what must not

**Must:** re-base the corpus onto the real signed pack. Today `test_evaluator_gold.py` deliberately
drives the synthetic fixture — legitimate, it tests the ENGINE, not legal policy — while
`gold_replay_driver.py` drives the real pack. Both are honest; **reporting only the first as "the
gold tests pass" is not.** Any statement about gold coverage must say which of the two it means.

**Must:** fix the dead assertion. The corpus asserts on product code **`E31`**, which this pack
does not contain (it uses E31A..E31J). It never fails, because the fixture pack contains whatever
the fixture declares. A persona naming a code absent from the real pack is an assertion that can
never go red.

**Must:** grow. **34 of 38 products are never any persona's `expected_candidates`.** A product can
be tier-mapped, priced, and reachable and still have never been exercised end to end. Per the
frozen C4 contract, a product card without a passing persona stays T3.

**Must not:** silence a Class-2 divergence by relaxing the safety rule that caused it. Five of them
are the engine protecting someone.

## Method notes, recorded because both bit this session

1. **The first cut of this triage was wrong and looked right.** It filtered personas on
   `p.get('match')` — a key that does not exist in this report (the fields are `divergence` /
   `differences`). The filter never fired, so all 20 personas were processed and reported as
   divergent. It was caught only because 20 did not reconcile with the summary's 16. The rerun
   asserts `len(divergent) == summary['personas_with_divergence']` inside the script, so next time
   the script fails instead of a human noticing. A filter that silently matches nothing is green.
2. **`gold_replay_driver.py --offline` picks the highest signed PRODUCTION pack in
   `contracts/packs` and logs that it did not check which pack is ACTUALLY active in production.**
   That is the honest behaviour, but it means this report describes the pack on disk, not
   necessarily the one serving traffic. A `--live` run is a different claim.

### Correzione 2026-08-25 (seconda misura) — l'acceptance dichiarata qui sopra è IRRAGGIUNGIBILE

La sezione precedente fissa come acceptance falsificabile: _«`NEEDS_INPUT` → `SUPPORTED_CANDIDATES
[E23]` quando la cura atterra»_. **Misurato: quel flip non può avvenire.** Chi implementasse «poni
la domanda» spedirebbe il lavoro e troverebbe la divergenza ancora lì, in una forma diversa, dopo
essere stato indirizzato da questa riga ad aspettarsi una cura.

Guidando `PERSONAS[14]` contro lo stesso pack firmato e fornendo a mano i fatti che l'intervista non
sa porre, uno per volta:

```
1. NEEDS_INPUT        manca: intent.requested_product_code
2. NEEDS_INPUT        manca: sponsor.type
3. NO_SUPPORTED_PATH  nessun fatto mancante
```

`NO_SUPPORTED_PATH`, non `SUPPORTED_CANDIDATES [E23]` — e con tutti e sei i valori di `SponsorType`.
Motivo, letto sulla prova per prodotto: E23 esce `UNSUPPORTED` con `missing_purposes: ['TOURISM']`.
`evaluator.py:678` richiede che **ogni** scopo dichiarato sia coperto, ed entrambe le regole di
idoneità di E23 dichiarano `covered_purposes: ["EMPLOYMENT"]` e basta; la persona dichiara
`["TOURISM", "EMPLOYMENT"]`.

Quindi i difetti sono **due, indipendenti**, e curare il primo non chiude la divergenza:

1. l'intervista non sa scrivere `intent.requested_product_code` per quattro `sponsor_category` su
   sei (questo documento, sopra) — e i prodotti che lo pretendono, E23U/E23V, hanno **zero** regole
   di idoneità: non potrebbero vincere nemmeno rispondendo;
2. il pack non sa esprimere la policy «lavoro + turismo → visto di lavoro» che l'etichetta della
   persona enuncia.

**Acceptance corretta**: la divergenza #15 si chiude quando il verdetto per quella forma diventa
**una risposta onesta e non un muro** — che sia `SUPPORTED_CANDIDATES [E23]` (se Zero sceglie di
insegnare la policy al pack) oppure `HUMAN_REVIEW_REQUIRED` con la mano tesa al consulente. Il solo
passaggio a `NO_SUPPORTED_PATH` **non** è la cura: è lo stesso vicolo due schermate più avanti.

Catena completa, meccanismo e le due domande per Zero: `DEADEND-PURPOSE-COVERAGE.md`.

### Seguito, stesso turno — #15 NON è un vicolo cieco _del wizard_: il funnel non sa dichiarare due scopi

La correzione qui sopra resta valida ma è incompleta. Misurato subito dopo, sul mapper reale:
`fact-mapper.ts:344-350` (`mapPurposes`) è **l'unico** scrittore di `intent.purposes` in tutto
`apps/mouth/src` (verificato per grep, un solo assegnamento non di test, `:671`), e ritorna sempre
`known([purpose])` — **un array di un elemento** — perché `CATEGORY_TO_PURPOSE` (`:294-305`) è 1:1.

**Il wizard non può produrre `["TOURISM","EMPLOYMENT"]`.** La forma di #15 non è raggiungibile dal
funnel di produzione. Un richiedente `work` reale dichiara `["EMPLOYMENT"]` e basta, e su quella
forma esatta il motore risponde `SUPPORTED_CANDIDATES candidates=['E23']` — **anche senza**
`intent.requested_product_code`: E23U/E23V restano `BLOCKED_UNKNOWN`, ma un SUPPORTED batte un
bloccato. Il sequestro descritto sopra scatta **solo quando nessun prodotto è supportato**, ed è
per questo che morde #15 (due scopi → E23 cade) e non l'utente vero.

⚠️ Precisione, non assoluzione: irraggiungibile **dal mapper del wizard**, non in assoluto — l'API
del motore accetta due scopi, e qualunque altro consumatore (chat, integrazioni, un futuro
selettore multi-scelta) ci finisce dentro.

**Conseguenza sulla classificazione**: #15 va da «Class 4 — vicolo cieco vivo» a **divergenza
spiegata corpus↔pack su una forma che il funnel non produce**. Il criterio firmato da Zero il
2026-08-25 — _«ogni divergenza spiegata, e nessuna di esse un vicolo cieco»_ — risulta soddisfatto
su questa base. **La chiamata resta di Zero**, non della lane: la divergenza va tenuta agli atti
spiegata, mai cancellata.

Censimento completo (78 combinazioni di scopi, copertura per scopo, i 52 casi strutturalmente
impossibili) e le tre decisioni aperte: `DEADEND-PURPOSE-COVERAGE.md`.

---

## Terzo seguito, 2026-08-25 — NB-2 risponde, e la fixture aveva ragione: è il pack firmato a divergere

Le due correzioni qui sopra trattavano la fixture gold come l'artefatto e il pack come il metro:
la fixture dichiara `E23 covered_purposes=["EMPLOYMENT","TOURISM"]`, il pack firmato dichiara
`["EMPLOYMENT"]`, e la fixture stessa ammette nel proprio docstring di essere **«synthetic
engine-test policy, not production Indonesian legal assertions»**. Su quella base avevo raccomandato
di dichiarare il motore **mono-scopo per contratto**.

**Zero ha riaperto la porta NotebookLM e NB-2 ha risposto. La raccomandazione era sbagliata.**

Il Kepmen M.IP-08.GR.01.01/2025 (_Klasifikasi Visa_), Lampiran Bagian B.1, riga **E23**, colonna 5
(**Hak** / Diritti) elenca alla lettera:

> _«Melakukan kegiatan yang berhubungan dengan wisata, melakukan pembelian barang, serta mengunjungi
> keluarga dan teman.»_

Cioè: **il titolare di E23 ha un diritto esplicito, scritto nella classificazione, di fare turismo.**
La fixture non stava inventando una comodità di test — stava riproducendo, per ragionamento, una
norma vera. È il **pack firmato** che sotto-dichiara.

E la simmetria regge dall'altro lato: la stessa tabella, riga **C1**, colonna 7 (**Larangan** /
Divieti) vieta _«Menerima imbalan, upah, atau sejenisnya dari perorangan atau korporasi di
Indonesia»_. Quindi l'etichetta della persona #15 — «lavoro + turismo → E23, **mai C1**» — non è una
convenzione del corpus: è **la lettura corretta di due righe della stessa tabella**.

### La distinzione che avrei sbagliato a scrivere nel contratto

`Permenkumham 22/2023 Pasal 2 ayat (2)` dice _«Setiap Orang Asing hanya dapat memiliki 1 (satu)
Visa»_ — **un visto per persona**, e `Pasal 70` lega il visto al proprio indice e alla propria
`uraian kegiatan`. Questo è **mono-VISTO**, non **mono-SCOPO**: un solo prodotto vince, ma quel
prodotto può coprire più scopi dichiarati, perché è la colonna _Hak_ a dirlo. Scrivere «il motore è
mono-scopo» nel contratto avrebbe cristallizzato in invariante un **accidente del mapper** (un solo
scrittore, mappa 1:1) travestendolo da vincolo di legge — e avrebbe reso permanentemente
irraggiungibile un caso che la norma consente.

### Cosa vale questa prova, e cosa non vale — disciplina W90

- **Corroborata su due percorsi indipendenti**: NB-2 cita la riga E23 del Lampiran; il factbase su
  disco `research/visa/2026-08-11-w3-sponsor-rules-factbase.md` usa **lo stesso strumento** (Kepmen
  M.IP-08.GR.01.01/2025) nel frontmatter e ne cita la medesima struttura a colonne
  Hak/Kewajiban/Larangan per E23U/E23V. Due lettori, un documento.
- **Non l'ho riletta io.** Il PDF del Kepmen **non è su disco** (cercato: zero hit). Il factbase E23
  su disco (`2026-07-24-w2-factbase-e23-full.md`, 69 righe) **non contiene affatto** la colonna Hak —
  è sottile, e per di più porta ancora il nome sbagliato di E23V («Kantor Dagang dan Ekonomi»), che
  il factbase W3 del 2026-08-11 ha poi corretto. Quindi: la clausola è citata, non ri-verificata da
  me alla fonte.
- **Azione conseguente**: prima di cambiare il pack, scaricare il Kepmen e rileggere la riga E23.
  Il pack è firmato — correggerlo è **sostanza regolatoria**: nuovo `seq` + nuova firma, non un
  ritocco di sessione.

### Effetto sull'acceptance di #15

L'acceptance corretta più sopra («una risposta onesta e non un muro») **resta valida e ora ha un
vincitore indicato dalla norma**: la cura giusta è `SUPPORTED_CANDIDATES [E23]`, cioè insegnare al
pack ciò che il Kepmen già dice, non `HUMAN_REVIEW_REQUIRED` come ripiego. Il ripiego resta
accettabile solo finché la riga non è stata riletta alla fonte.

---

## Nota aritmetica, 2026-08-25 — la sedicesima divergenza mancava dalla tassonomia

Le classi qui sopra sommavano 7 + 5 + 2 + 1 = **15**, contro **16** divergenze misurate. Il totale
di `OWNER-RULINGS §7` («quindici non sono difetti», più la #15) era invece **giusto**: era la riga
della Classe 2 a essere corta di uno.

La mancante è la **persona #5** («minor without confirmed guardian»), e non cambia nessuna
conclusione: stesso stato (`HUMAN_REVIEW_REQUIRED`), stessi candidati (nessuno), il motore aggiunge
una ragione di review **in più** rispetto all'attesa — `MINOR_GUARDIAN_PRIVACY_REVIEW` accanto a
`MINOR_WITHOUT_CONFIRMED_GUARDIAN`. È esattamente la forma già assegnata alla persona #6 per la
stessa regola. Classificata qui, Classe 2, dalla sessione — non da un ruling.

## ⚠️ L'accettazione falsificabile della #15 NON è ancora soddisfatta (misurato 2026-08-25, su seq-15)

Questo documento fissa, per la persona #15, un test che si può far fallire:

> _«it must flip from `NEEDS_INPUT` to `SUPPORTED_CANDIDATES [E23]` when the cure lands, and that
> flip is the falsifiable acceptance.»_

Ri-eseguito il driver **dopo** la cura (`59cc092a0`) e **contro il pack seq-15 appena firmato**
(`payload_sha256 08ba8b09…`, `sequence 15` — il driver l'ha raccolto da solo, il che prova per
inciso che il bundle firmato è valido e consumabile):

```
persona #15  atteso  SUPPORTED_CANDIDATES ['E23']
             ADESSO  NEEDS_INPUT  missing_facts=['intent.requested_product_code']
             flippata: NO
summary      matches 4/20 · divergenze 16 · explained 0 · unexplained 16   (identico a seq-13)
```

**Perché la cura non la flippa, e non è un difetto della cura.** `59cc092a0` ha curato il **funnel**:
un visitatore vero sul ramo `work` può ora nominare E23U/E23V, e quel vicolo cieco è chiuso. La
persona #15 però non passa dal funnel — alimenta il motore direttamente, e la sua forma è un'altra:
**due scopi** (`TOURISM` + `EMPLOYMENT`) che vogliono E23. La sua radice non è la nominabilità del
prodotto: è la **copertura degli scopi** — nel pack firmato `E23.covered_purposes = ["EMPLOYMENT"]`,
e `evaluator.py:678` pretende che **ogni** scopo dichiarato sia coperto.

E quella radice ora ha una risposta normativa, che prima non c'era: NB-2 cita il **Kepmen
M.IP-08.GR.01.01/2025, Lampiran B.1, riga E23, colonna Hak** — _«Melakukan kegiatan yang berhubungan
dengan **wisata**…»_. Il titolare di E23 ha diritto esplicito al turismo: è il **pack firmato** a
sotto-dichiarare, non la fixture a sbagliare. La cura della #15 è quindi un **seq-16** che insegna
`E23.covered_purposes ⊇ {EMPLOYMENT, TOURISM}` — nuova firma, e prima va riletta la riga alla fonte
(il PDF del Kepmen non è su disco).

**Conseguenza sul registro d'accensione.** L'evidenza della firma #3 dice _«persona #15's dead end is
cured by 59cc092a0»_. Metà vera: il vicolo cieco **del funnel** è chiuso. Ma il test che questo
documento aveva designato come prova della cura **non è passato**, e continua a non passare. Non è
una ragione per ritirare la firma — il criterio firmato in §7 chiede «nessun vicolo cieco», e per un
visitatore reale non ce n'è più uno — ma è una ragione perché il registro non dica che una prova è
passata quando è misurabilmente rossa.

---

## ✅ seq-16 — la cura è costruita e l'accettazione falsificabile PASSA (misurato 2026-08-26)

La sezione precedente prescriveva la cura: un **seq-16** che insegni
`E23.covered_purposes ⊇ {EMPLOYMENT, TOURISM}`. È costruita. Non è ancora **firmata** — la firma è
di Zero (`operator[credential]`), e finché non c'è, il driver continua per costruzione a replayare
seq-15 (`select_highest_repository_pack` sceglie il pack **firmato** con sequenza massima), quindi il
report ufficiale legge ancora `unexplained_divergences: 1`. Quello che segue è misurato compilando
il payload sorgente seq-16 sullo stesso percorso del driver.

### La fonte, letta alla fonte

Il PDF del Kepmen non era su disco; ora lo è stato. Scaricato da `kemenimipas.go.id`,
**1.906.368 byte, 80 pagine**,
`sha256 b8e326667c892ab2dfb52be220c82a0716bab6a516fe925c5e45096e9ef81c33` — la provenienza è
ancorata all'**hash**, non a un percorso di scratch che sparisce — validato per **magic bytes**
(`od -c -N4` = `%PDF`) e non per stato HTTP, perché quel portale risponde `200` con una pagina
d'errore HTML. Riletto una terza volta sulla copia di Zero, confermata **byte-identica** (stesso
sha256), e una **quarta** da un lettore indipendente incaricato di refutare la lettura, non di
confermarla. Quel lettore ha stabilito i confini di colonna con un metodo migliore del mio: la
tabella interlaccia Hak / Kewajiban / Larangan sulle stesse righe fisiche, ma **ogni colonna ha la
propria numerazione indipendente** (Hak 1-5, Kewajiban 1-4, Larangan 1-4), quindi il marcatore sono
i reset di numerazione, non la posizione orizzontale. Riga E23, colonna **Hak**, voce **4**,
verbatim:

> «Melakukan kegiatan yang berhubungan dengan **wisata**, melakukan pembelian barang, serta
> mengunjungi keluarga dan teman»

**Correzione alla sezione precedente**: quella riga citava NB-2 con «Lampiran B.1». La collocazione
reale, riletta sul PDF, è **pagina 35**, Lampiran «Klasifikasi Visa Tinggal Terbatas» (una factbase
interna la stimava a pagina 37-38: anche quella era sbagliata). Il verdetto NB-2 era un **lead
corretto**, la sua coordinata no — che è esattamente la ragione per cui un verdetto NB si verifica
alla fonte prima di diventare una modifica normativa.

### Cosa cambia il fold, e cosa NON cambia

`backend/scripts/visa_engine/fold_pack_seq16.py` — 111 regole dentro, 111 fuori, zero aggiunte, zero
rimosse; 38 prodotti invariati come insieme. Superfici toccate: **una** (`E23`) e **due**
(`el.e23-employment-support`, `el.e23-operational-work-boundary`), e in tutte e tre l'unica chiave
che cambia è `covered_purposes: ["EMPLOYMENT"] → ["EMPLOYMENT","TOURISM"]`.

**La prima stesura del fold toccava solo le due regole, ed era sbagliata.** Ha superato la
validazione di schema (`RulePackPayload`) e si è schiantata sul compilatore:
`SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT` — una regola SUPPORT non può rivendicare uno scopo che il
**prodotto** non dichiara (`compiler.py:1085`); il `covered_purposes` del prodotto è il limite
esterno. Schema-valido non è semanticamente valido: il gate di compilazione ora sta **dentro** il
fold, non solo nel test, così un pack non compilabile non può raggiungere il disco.

Il pack aveva già la convenzione, e E23 era l'unico fuori: `E33A` dichiara
`['EMPLOYMENT','TOURISM','FAMILY']`, `E33B` cinque scopi, `E33G`
`['REMOTE_WORK','TOURISM','FAMILY']`. Prima di seq-16, `['EMPLOYMENT']` nudo compariva su **due
sole** regole in tutto il pack — le due di E23.

### La misura

```
persona #15   seq-15:  NEEDS_INPUT            missing_facts=['intent.requested_product_code']
              seq-16:  SUPPORTED_CANDIDATES   candidates=['E23']   missing_facts=[]
personas mosse da seq-16:  1 su 20  (esattamente la #15)
divergenze vs atteso:      seq-15 -> 16    seq-16 -> 15
                           l'unica rimossa e' la #15, cioe' l'unica NON spiegata
```

L'accettazione che questo documento aveva fissato — _«it must flip from `NEEDS_INPUT` to
`SUPPORTED_CANDIDATES [E23]`»_ — **passa**. E il collaterale è nullo: 19 personas su 20 non si
muovono di un byte. Alla firma, il driver leggerà `explained 15 · unexplained 0 · overall_pass True`.

Guardia: `backend/tests/services/visa_engine/test_seq16_pack.py`, 11 test, **nessuno skip
difensivo** — se l'artefatto manca il modulo va rosso, non verde. Mutation-check eseguito: rimesso
`["EMPLOYMENT"]` sul solo prodotto, **6 test su 11 vanno rossi**; ripristinato e ri-verificato verde.

### Due cose lasciate fuori, dette invece che taciute

1. **`FAMILY` — non aggiunto, e la lettura integrale dice che è giusto così.** ⚠️ Questa voce
   **corregge una versione precedente di sé stessa**: dicevo «forse dovrebbe», avendo letto solo la
   voce 2 e non l'intera cella. Le cinque voci della colonna Hak di E23 sono **di natura diversa**.
   La **4** — turismo, acquisti, visita a parenti e amici — è un'attività del titolare enunciata
   **senza alcuna condizione**, ed è ciò che seq-16 recepisce. La **2** è «Membawa keluarga untuk
   tinggal di wilayah Indonesia **sepanjang memenuhi ketentuan peraturan perundang-undangan di
   bidang keimigrasian**»: un diritto **derivato e condizionato** a portare _altri_, che rinvia
   esplicitamente ad altra normativa immigratoria — nel motore, i prodotti famiglia E31\*. Il
   lettore indipendente ha verificato proprio il punto critico, cioè che `sepanjang` appartenga al
   blocco di testo della voce 2 e non sbordi dalla colonna Kewajiban accanto (che lì recita una
   frase diversa, `…di bidang ketenagakerjaan`): regge. E ha trovato la stessa clausola verbatim su
   E23A ed E23U — quindi la condizionalità è un **template di regime**, non una particolarità di
   E23: l'asimmetria famiglia-condizionata / turismo-incondizionato è sistematica, il che rafforza
   la lettura invece di indebolirla. Poiché `covered_purposes` misura gli scopi **dichiarati dal
   richiedente**, chi dichiara `FAMILY` viene _per_ ragioni familiari — forma di E31, non di E23; e
   il «mengunjungi keluarga dan teman» della voce 4 è _visitare_ dentro un diritto di turismo, non
   risiedere per famiglia. L'analogia E33A/E33G su cui poggiava la versione precedente è più debole
   di come l'avevo presentata: sono **righe diverse con la loro colonna Hak**, che non ho aperto. →
   resta **decisione di Zero** (Legge 5); questa è la raccomandazione aggiornata: **non aggiungerlo**.
2. **E23U / E23V restano `['EMPLOYMENT']`.** Verificato prima di lasciarli fuori: ciascuno porta
   **una sola** regola, `REQUIRE_REVIEW` a stadio HUMAN_REVIEW, nessuna `SUPPORT` — quindi né il
   limite del compilatore né la copertura-scopi di `evaluator.py:678` (che legge le regole
   **ELIGIBILITY** vere) li ingaggiano mai. Allargarli asserirebbe un fatto normativo senza
   consumatore. Un test lo tiene fermo: se domani nascesse una regola SUPPORT su di loro, va rosso.

### Stato

`rulepack-prod-016.source.json` è su disco, compila, e la sua catena punta al `payload_sha256`
**dichiarato dal bundle firmato** di seq-15 (`08ba8b09…`) — non all'hash di un file sorgente
qualsiasi. Manca solo la cerimonia di firma, che è di Zero.

### La cerimonia, pronta (da eseguire su M5, `operator[credential]`)

La chiave privata non è mai presente in questa sessione né nel processo FastAPI. `--kid` e
`--environment` sono gli stessi di seq-15; `--sequence 16` deve combaciare con il campo `sequence`
del payload, e `sign_pack.py` rifiuta se diverge. Il flag di produzione è obbligatorio.

```bash
cd <repo>/apps/backend-rag
PYTHONPATH=. python -m backend.scripts.visa_engine.sign_pack \
  backend/services/visa_engine/contracts/packs/rulepack-prod-016.source.json \
  --kid prod-2026-07-1 \
  --key-file <percorso chiave privata Ed25519 PEM, chmod 0600> \
  --environment PRODUCTION \
  --sequence 16 \
  --i-know-this-is-production \
  --output backend/services/visa_engine/contracts/packs/rulepack-prod-016.signed.json
```

Verifica dopo la firma (la fa la sessione, non serve la chiave):

```bash
PYTHONPATH=. python -m backend.scripts.visa_engine.gold_replay_driver --offline \
  --accepted-explanations backend/services/visa_engine/contracts/gold-accepted-explanations.json
```

Atteso, e questo è il criterio: il driver deve **raccogliere da solo seq-16** (sceglie il pack
firmato con sequenza massima) e leggere `explained_divergences: 15 · unexplained_divergences: 0 ·
overall_pass: true`. Se raccoglie ancora seq-15, la firma non è atterrata dove il driver guarda.

### ⚠️ Il turismo NON è una specialità di E23 — e 23 prodotti su 38 non lo dichiarano

Il lettore indipendente ha trovato un fatto che rovescia l'inquadramento di questa sezione. La voce
4 della colonna Hak — «wisata, pembelian barang, mengunjungi keluarga dan teman» — **non è
distintiva di E23**: è **boilerplate** ripetuto su decine di codici. Verificata verbatim su **D14**,
**D17**, **E23A**, **E23U**; su tutto il documento di 80 pagine «pembelian barang» ricorre **114**
volte e «keluarga dan» **104**.

E23 è dunque l'anomalia **nel nostro pack**, non nella normativa — è semplicemente il prodotto su
cui una persona gold ha fatto emergere il buco. Misurato sullo stesso payload seq-16: **23 prodotti
su 38 non dichiarano `TOURISM`** — `E23U`, `E23V`, i cinque `E28*`, i cinque `E30*`, i nove `E31*`,
più `C2`, `C6`, `BRIDGING`.

**Non li ho allargati, ed è deliberato.** Dei codici nominati dal lettore, solo `E23U` e `E23V`
esistono nel nostro pack; `E23A`/`D14`/`D17`/`E23X`/`E23Y` no. Per tutti gli altri — E28, E30, E31 —
**nessuno ha letto la riga**: allargarli per analogia sarebbe esattamente il passo che ho rifiutato
di fare sul `FAMILY`. Ogni prodotto vuole la **sua** riga letta alla fonte prima che qualcuno tocchi
il suo `covered_purposes`. Aperto come lane nel ledger `modus`, non sanato di soppiatto qui.
