# Persona #15 non è un vicolo cieco vivo — ma due prodotti danno una risposta SBAGLIATA in silenzio

> Misurato 2026-08-25 contro il pack **firmato** `rulepack-prod-013` (`payload_sha256 = b9edb809…`),
> mai contro il pack fixture. Ogni numero prodotto da due sonde indipendenti che concordano.
> **Correzione a `GOLD-DIVERGENCE-TRIAGE.md`** (acceptance irraggiungibile) e **decisione per Zero**
> in fondo (Legge 5).

## La misura decisiva, in tre righe

`fact-mapper.ts:344-350` — l'unico scrittore di `intent.purposes` in tutto il frontend:

```ts
const purpose = CATEGORY_TO_PURPOSE[category];
return purpose === undefined ? unknownFact(NOT_APPLICABLE) : known([purpose]);
```

`CATEGORY_TO_PURPOSE` (`:294-305`) è **1:1**: una categoria → **uno** scopo. `known([purpose])`
è sempre un array di **un** elemento. Verificato che non esistano altri scrittori: `grep` su tutto
`apps/mouth/src` dà un solo assegnamento non di test (`fact-mapper.ts:671`).

**Conseguenza: il wizard non può produrre `["TOURISM", "EMPLOYMENT"]`.** La forma di persona #15
non è raggiungibile dal funnel di produzione. `GOLD-DIVERGENCE-TRIAGE.md` la classifica come
_«a live dead end»_: rispetto al **wizard** non lo è.

⚠️ **Precisione, non assoluzione**: è irraggiungibile _dal mapper del wizard_. L'endpoint del motore
accetta eccome due scopi — chiunque altro lo chiami (API, chat, un futuro selettore multi-scelta)
ci finisce dentro. «Il wizard non ce la porta» ≠ «non ci si arriva».

## Cosa succede davvero a un richiedente `work` reale

Il wizard dichiara `["EMPLOYMENT"]` e basta. Misurato su quella forma esatta:

```
intent.purposes = ["EMPLOYMENT"]  ->  SUPPORTED_CANDIDATES  candidates=['E23']
```

Funziona. E funziona **anche senza** `intent.requested_product_code`: E23U/E23V restano
`BLOCKED_UNKNOWN`, ma un `SUPPORTED` batte un bloccato, quindi non prendono nulla in ostaggio.

Il sequestro scatta **solo quando nessun prodotto è supportato**. È il caso di persona #15, che
dichiara due scopi: E23 cade (sotto), non resta nessun `SUPPORTED`, e i cinque bloccati
(E23U, E23V, E33A, E33B, E33C — **tutti a zero regole di idoneità**) diventano la decisione,
chiedendo un fatto che non li renderebbe comunque mai una risposta.

> Questo corregge una sfumatura di `TIER-MAP.md`, che scrive che un `BLOCKED_UNKNOWN` _«perde contro
> qualunque prodotto SUPPORTED»_. Vero — ma perde **solo se un SUPPORTED esiste**. Quando non esiste,
> vince, e detta la domanda. E lì `TIER-MAP.md` nomina solo gli E28: nel ramo `work` mordono E23U/E23V.

## Il difetto VIVO, e non è un vicolo cieco: è una risposta sbagliata detta con sicurezza

Cercando il vicolo se n'è trovato uno peggiore. **E23U** (assistente domestico di un diplomatico
straniero) ed **E23V** (lavoro presso una **camera di commercio estera**) hanno una regola di review
che si accende solo se il richiedente li **nomina** — e nessuno può nominarli.

> **Provenienza delle due caratterizzazioni, e una correzione (2026-08-25).** Non vengono dai nomi
> di prodotto del pack: quelli, per E23V, sono essi stessi sbagliati. La fonte è
> `research/visa/2026-08-11-w3-sponsor-rules-factbase.md`, che estrae il Lampiran del Kepmen
> M.IP-08.GR.01.01/2025 (pag. 37-38) e conferma E23U alla lettera — _«Melakukan pekerjaan sebagai
> asisten rumah tangga [diplomat asing]»_. Per E23V invece il testo primario dice _«…pejabat atau
> staf pada **kamar dagang asing**»_, cioè **camera di commercio estera**: il factbase corregge
> esplicitamente la lettura «Kantor Dagang dan Ekonomi»/KDEI, che il pack ha invece cristallizzato
> nel nome inglese «Trade and Economic Office». Una camera di commercio estera può benissimo essere
> un'associazione privata — il factbase lascia infatti `sponsor.type` **UNRESOLVED** per E23V, e
> segnala che la scelta `GOVERNMENT` nel pack è un giudizio non difeso da nessuna fonte. Nessuno dei
> due prodotti ha un Pasal dedicato in Permenkumham 22/2023 jo. 11/2024 (ricerca full-text nel
> factbase). Questo NON è stato chiesto a NB-2 — la porta NotebookLM è morta (auth scaduta); è
> invece una fonte primaria già su disco, con citazioni a livello di Pasal/Lampiran, che per questo
> vale più di un verdetto NB (cicatrice W90: un verdetto NB è una PISTA finché non ne confronti la
> data-fonte).

Misurato enumerando ogni domanda dell'albero la cui `decisionMapping.factPaths` contiene
`intent.requested_product_code`. Sono **quattro**, e queste sono tutte le loro opzioni:

| domanda                        | opzioni offerte                      |
| ------------------------------ | ------------------------------------ |
| `investment_product_code`      | E28B · E28C · E28D · E28F · STANDARD |
| `investment_product_code_govt` | E33C · STANDARD                      |
| `employment_product_code_govt` | E33A · E33B · STANDARD               |
| `employment_product_code_none` | E33B · STANDARD                      |

Unione di tutti i valori proponibili: `E28B, E28C, E28D, E28F, E33A, E33B, E33C, STANDARD`.
**`E23U` ed `E23V` non compaiono da nessuna parte** — sotto nessuna delle sei categorie di sponsor,
incluse `GOVERNMENT` e `NONE` che la lane V1 ha già cablato. Non è un residuo di fall-through:
**nessun visitatore può nominare quei due prodotti, mai.**

La conseguenza non è uno schermo vuoto. Un assistente domestico di un diplomatico dichiara
`work` → `["EMPLOYMENT"]` → E23 risulta `SUPPORTED` → **l'Oracolo gli risponde «E23»**, con
sicurezza, mentre il suo caso reale è E23U e avrebbe dovuto attivare `HUMAN_REVIEW_REQUIRED`.
Nessun blocco, nessun avviso: **una miscategorizzazione silenziosa.** Il mandato lo vieta a lettere
tonde — _«Never an invented answer»_ — e questo è esattamente il modo in cui un motore
deterministico può inventare: non allucinando un prodotto, ma tacendo su quello giusto.

> **Provenienza**: la scoperta è della lane R8 (`DEADEND-SCOPE-EMPLOYER.md`, commit `528a00658`).
> Non l'ho presa per buona: ho ri-enumerato io le domande e le loro opzioni dall'albero, e la
> tabella qui sopra è la mia misura, non la sua. Concorda.

## Perché E23 cade con due scopi

`evaluator.py:678` — candidato solo se **ogni** scopo dichiarato è coperto:

```python
if purposes <= covered:   # covered = unione dei covered_purposes delle regole di idoneità VERE
```

| rule_id                            | `on_unknown`  | `covered_purposes` | verità per #15 |
| ---------------------------------- | ------------- | ------------------ | -------------- |
| `el.e23-employment-support`        | `NEEDS_INPUT` | `["EMPLOYMENT"]`   | **TRUE**       |
| `el.e23-operational-work-boundary` | `NO_EFFECT`   | `["EMPLOYMENT"]`   | FALSE          |

`covered = {EMPLOYMENT}`, `purposes = {TOURISM, EMPLOYMENT}` → E23 `UNSUPPORTED` con
`missing_purposes: ['TOURISM']` → nessun altro prodotto copre la coppia → `NO_SUPPORTED_PATH`,
confermato con tutti e sei i valori di `SponsorType`.

**E il pack fixture dice il contrario — misurato su entrambi i lati:**

| pack                                          | `E23.covered_purposes`      |
| --------------------------------------------- | --------------------------- |
| **fixture** (`_gold_fixtures.py:537`)         | `["EMPLOYMENT", "TOURISM"]` |
| **firmato** (`rulepack-prod-013.source.json`) | `["EMPLOYMENT"]`            |

Il fixture lo fa di proposito — il suo stesso docstring (`:18`) scrive _«A product's own
`covered_purposes` deliberately includes TOURISM for…»_ — e infatti anche C1, E31, E33G, E28A
portano `TOURISM` accanto al loro scopo principale. **Quindi la divergenza #15 è precisamente
questa riga, e nient'altro**: il corpus gold attende un comportamento che solo il pack fixture
produce. Non è una prova che un richiedente reale sbatta contro un muro.

## Il censimento completo: 78 combinazioni di scopi

`VisaPurpose` ha **12** membri (contati importando l'enum, non a regex). 12 singoli + 66 coppie = 78.
Per ciascuna, due sonde: **strutturale** (esiste un prodotto le cui regole di idoneità coprono,
in unione, tutta la combinazione?) ed **empirica** (il motore, con un set di fatti generoso).

| esito                                   | n            | lettura                                         |
| --------------------------------------- | ------------ | ----------------------------------------------- |
| coperto da ≥1 prodotto (strutturale)    | **26** su 78 | 11 singoli (tutti tranne `MEDICAL`) + 15 coppie |
| **strutturalmente impossibile** (`N=0`) | **52** su 78 | 1 singolo (`MEDICAL`) + 51 coppie               |
| empirico `SUPPORTED_CANDIDATES`         | 11           | 8 singoli + 3 coppie                            |
| empirico `NEEDS_INPUT` (il sequestro)   | 19           | tutte con `EMPLOYMENT` o `INVESTMENT`           |
| empirico `HUMAN_REVIEW_REQUIRED`        | 1            | `EMPLOYMENT+SECOND_HOME`                        |
| empirico `NO_SUPPORTED_PATH`            | 47           | —                                               |

Copertura per scopo (quanti prodotti hanno ≥1 regola di idoneità che lo copre):

```
FAMILY 14 · TOURISM 8 · STUDY 5 · BUSINESS_MEETINGS 4 · INVESTMENT 3
RETIREMENT 2 · SECOND_HOME 2 · TRANSIT 2 · OTHER 2 · EMPLOYMENT 1 · REMOTE_WORK 1 · MEDICAL 0
```

Due letture che valgono la pena:

- **`MEDICAL` non è coperto da nessun prodotto.** È uno scopo legale dell'enum che il catalogo non
  serve. Il wizard oggi **non** lo offre (`CATEGORY_TO_PURPOSE` non ha una categoria che ci mappi),
  quindi non è raggiungibile — ma chi aggiungesse la tessera «cure mediche» spedirebbe un vicolo
  garantito.
- **La colonna empirica NON misura l'impossibilità.** 15 combinazioni divergono fra le due sonde
  (strutturalmente coperte, empiricamente `NO_SUPPORTED_PATH`): il set di fatti generoso non
  soddisfa le condizioni di quel prodotto. Solo la colonna **strutturale** dice «mai».

## Un possibile vicolo cieco vivo, misurato ma NON confermato

Cercando altro, ne è emerso uno che il wizard **sa** produrre. La tessera **`diaspora`** non mappa
ad alcuno scopo (`CATEGORY_TO_PURPOSE` la omette di proposito; `tree.ts:388` la dichiara
`unknownValues: ["diaspora"]`). Misurato sul motore:

```
intent.purposes UNKNOWN/NOT_APPLICABLE -> NEEDS_INPUT  missing=['FactPath.INTENT_PURPOSES']
```

E `engine-adapter.ts:796-806` (`questionForFact`) risolve `intent.purposes` alla **prima** domanda
che la dichiara — cioè `category`, quella appena risposta. La forma sospetta è quindi un **anello**:
scegli «diaspora» → il motore chiede lo scopo → l'interfaccia ti rimanda alla stessa tessera.

**Non l'ho confermato e non lo presento come difetto**: non ho ancora guidato il reducer reale
end-to-end su quel percorso, e un guard contro il ri-presentare una domanda già risposta potrebbe
esistere. La prova che lo deciderebbe: un test sul reducer che sceglie `diaspora` e osserva se
`missingInputs` porta un `questionId` già risposto. Sonda da scrivere, non conclusione raggiunta.

## Cosa NON ho fatto

- **Non ho toccato le attese del corpus** né i fixture: sono evidenza, non manopole.
- **Non ho toccato il pack firmato**: `covered_purposes` e `on_unknown` sono sostanza normativa,
  cambiarli è nuovo `seq` + nuova firma, e non è mia da decidere.
- **Non ho misurato la produzione**: tutto qui è pack firmato + codice su disco, riproducibile.

## Le decisioni per Zero

**(A) Persona #15 blocca ancora la firma #3?**
Il criterio che hai firmato è _«ogni divergenza spiegata, e nessuna di esse un vicolo cieco»_.
La divergenza ora **è spiegata**, con meccanismo e file:line, e rispetto al wizard **non è un vicolo
cieco** — la forma non è producibile dal funnel. Resta una divergenza corpus↔pack legittima da
tenere agli atti. **Raccomando: #3 diventa firmabile su questa base**, con la divergenza intatta e
spiegata, non cancellata. È una tua chiamata, non mia.

> ✅ **COSTRUITO 2026-08-25 — Zero ha scelto (1), commit `59cc092a0`.** La domanda è
> `employment_special_employer` (`tree.ts`/`flow.ts`/`i18n.ts`, EN+ID), non gated sullo sponsor, più
> le copie dei due `reason_code` e **seq-15** (`fold_pack_seq15.py`, 109 → 111) che ri-autorizza le
> due regole di review che **PR #4797 aveva ritirato**. #4797 era giusta sulla sua premessa — quelle
> regole erano appese a un fatto inottenibile — e la premessa smette di valere nello stesso commit
> che rende il fatto chiedibile. La sua obiezione alle regole SUPPORT (nessun predicato separa «casa
> di un diplomatico» da «un qualunque datore individuale») **resta in piedi e non è stata toccata**:
> seq-15 non autorizza nessuna SUPPORT, e un test lo tiene. Una riga di #4797 invece non regge —
> «E23U/E23V stay unreachable and **route to a human consultant**»: la raggiungibilità è misurata,
> l'instradamento no, e un prodotto irraggiungibile non instrada, tace. Un grader indipendente ha
> trovato un bloccante prima del merge (il filo diceva `NOT_ASKED` per una domanda posta e risposta);
> corretto e mutation-checked. Resta **non fatto**: seq-15 non è firmato, e che seq-13 sia il pack
> attivo è **documentato, non misurato** — il DB di produzione non è leggibile da questa sessione.

**(A-bis) E23U/E23V: la cosa che romperei per prima.**
È l'unico difetto qui dentro che tocca un visitatore vero **oggi**, e produce una risposta sbagliata
detta con sicurezza, non un errore visibile. Tre strade, in ordine di quanto mi convincono:

1. **Una domanda onesta nel ramo `work`**, per ogni categoria di sponsor: «il tuo datore di lavoro
   è **un diplomatico straniero** (lavoro domestico presso la sua residenza), oppure **una camera di
   commercio estera**?» → se sì, `E23U`/`E23V` e la review scatta. È piccola, tutta frontend,
   nessuna firma, e cura la miscategorizzazione alla radice.

   **Formulazione corretta il 2026-08-25, due volte, e la seconda volta conta più della prima.**
   Diceva «rappresentanza diplomatica o ufficio commerciale estero». Un seat indipendente ha
   verificato entrambe le metà contro il Lampiran e le ha bocciate **in direzioni opposte**:
   «rappresentanza diplomatica» _sovra-cattura_ — la fonte nomina solo `asisten rumah tangga
diplomat asing`, un rapporto personale con **un** diplomatico, non l'impiego presso la missione
   come istituzione (e il factbase lascia esplicitamente irrisolto quale dei due sia il Penjamin);
   «ufficio commerciale estero» _sostituisce_ al termine della fonte (`kamar dagang asing`, camera di
   commercio estera) la lettura KDEI che il factbase ha già corretto via, catturando un
   sottoinsieme reale e perdendo il resto della classe. È lo stesso errore che il pack ha nel nome
   inglese di E23V: l'avrei riprodotto un livello più a monte, dentro la cura.

   **Nota su cosa deve fare questa domanda.** Non deve classificare: deve **accendere una review
   umana**. L'asimmetria è quindi voluta e va detta — sovra-catturare manda in review qualcuno in
   più (costo: un consulente legge un caso ordinario), sotto-catturare lascia in piedi la risposta
   sbagliata detta con sicurezza, che è il difetto. Dove il testo primario è ambiguo, la
   formulazione deve sbagliare **verso la review**, mai verso il silenzio.

2. **Regola di review su un fatto che l'intervista già raccoglie** (chi paga, che ruolo) invece che
   sul nome del prodotto — non chiede al cliente di conoscere il codice del proprio visto, il che è
   comunque la forma giusta. Costo: pack firmato.
3. **Lasciare com'è e dichiararlo**, cioè accettare per iscritto che E23U/E23V non sono serviti
   dall'Oracolo e che quei casi arrivano per altra via. Difendibile solo se è vero.

**Raccomando (1) subito e (2) come forma definitiva.** (3) solo se mi dici che quei due casi non
passano mai dal funnel.

**(B) La policy «lavoro + turismo» deve esistere nel pack?**
Oggi non c'è. Se un domani il wizard offrisse scopi multipli — o se un altro consumatore del motore
li manda — chi dichiara lavoro _e_ turismo esce con niente. Due strade: insegnare la policy al pack
(E23 copre anche `TOURISM`, o una regola assorbe `TOURISM` quando c'è `EMPLOYMENT`), oppure
dichiarare per scritto che il motore è **mono-scopo** e vincolare ogni consumatore a mandarne uno.
~~**Raccomando la seconda**~~ — **RITIRATA il 2026-08-25.** Zero ha riaperto la porta NotebookLM e
NB-2 ha risposto: il Kepmen M.IP-08.GR.01.01/2025, Lampiran B.1, riga **E23**, colonna **Hak**,
concede alla lettera _«Melakukan kegiatan yang berhubungan dengan wisata, melakukan pembelian
barang, serta mengunjungi keluarga dan teman»_ — il titolare di E23 **ha diritto esplicito al
turismo**. Quindi la fixture gold (`["EMPLOYMENT","TOURISM"]`) è normativamente giusta e **il pack
firmato sotto-dichiara**; e l'etichetta della persona #15, «lavoro + turismo → E23, mai C1», è la
lettura corretta di due righe della stessa tabella (C1, colonna **Larangan**, vieta _«Menerima
imbalan, upah, atau sejenisnya…»_).

**Raccomando ora la prima**: insegnare la policy al pack, `E23.covered_purposes ⊇ {EMPLOYMENT,
TOURISM}`. Dichiarare il motore mono-scopo avrebbe scritto nel contratto un **accidente del mapper**
spacciandolo per vincolo di legge: `Permenkumham 22/2023 Pasal 2(2)` (_«hanya dapat memiliki 1
(satu) Visa»_) impone **un visto solo**, non **uno scopo solo** — un prodotto può coprirne più d'uno,
ed è la colonna _Hak_ a stabilirlo.

**Limite dichiarato, e vincola l'esecuzione (W90).** Il PDF del Kepmen non è su disco; io la riga
E23 non l'ho riletta. La clausola è corroborata da due lettori indipendenti dello stesso strumento
(NB-2, e il factbase `2026-08-11-w3-sponsor-rules-factbase.md` che lo cita in frontmatter), ma il
pack è **firmato**: cambiarlo è sostanza regolatoria — nuovo `seq`, nuova firma, e prima si scarica
il Kepmen e si rilegge la riga. Non è una modifica di sessione.

**(C) Un prodotto senza regole di idoneità deve poter chiedere qualcosa?**
Nove prodotti (i T3 di `TIER-MAP.md`) non possono mai essere una risposta, ma cinque di loro possono
prendere l'intervista in ostaggio quando nulla è supportato. La cura pulita è
`on_unknown: NO_EFFECT` su quelle regole di review — oppure l'invariante nel motore. Non urgente
sul funnel di oggi (con un solo scopo c'è quasi sempre un `SUPPORTED` che vince), **ma è una mina
che esplode esattamente quando il catalogo si allarga.**

---

## Il limite dichiarato è sciolto — riga riletta alla fonte, cura costruita (2026-08-26)

Il blocco qui sopra si fermava su un limite esplicito: _«il PDF del Kepmen non è su disco; io la riga
E23 non l'ho riletta»_. Il PDF ora è stato scaricato e la riga **riletta**: `kemenimipas.go.id`,
1.906.368 byte, 80 pagine, validato per **magic bytes** (`%PDF`) e non per stato HTTP. Riga **E23**,
colonna **Hak**, voce **4**, verbatim:

> «Melakukan kegiatan yang berhubungan dengan **wisata**, melakukan pembelian barang, serta
> mengunjungi keluarga dan teman»

La clausola regge: la raccomandazione di questo documento — insegnare la policy al pack invece di
dichiarare il motore mono-scopo — era corretta.

**Una coordinata era però sbagliata in entrambi i lettori indipendenti**: NB-2 la dava in «Lampiran
B.1», il factbase interno a pagina 37-38. È a **pagina 35**, Lampiran «Klasifikasi Visa Tinggal
Terbatas». Due sonde che concordano sulla sostanza possono sbagliare insieme sulla collocazione —
motivo per cui la rilettura alla fonte era un prerequisito e non una formalità.

**La cura è `seq-16`**, costruita e misurata: `E23.covered_purposes` passa a
`["EMPLOYMENT","TOURISM"]` sul **prodotto** e sulle sue **due** regole ELIGIBILITY SUPPORT (il
compilatore rifiuta una regola SUPPORT che rivendichi uno scopo non dichiarato dal prodotto:
`SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT` — le due superfici si muovono insieme o il pack non si
costruisce). Persona #15 passa da `NEEDS_INPUT` a `SUPPORTED_CANDIDATES ['E23']`, e **nessuna** delle
altre 19 personas si muove. Dettaglio, misure e cerimonia di firma: `GOLD-DIVERGENCE-TRIAGE.md`,
sezione «seq-16».

**Aperto e non deciso qui**: la stessa colonna Hak, voce **2**, concede «Membawa keluarga untuk
tinggal di wilayah Indonesia» — cioè `FAMILY`. Non è stato aggiunto: il GO era sul turismo, ed è una
seconda asserzione normativa. Decisione di Zero (Legge 5).

Il punto **(C)** qui sopra — i prodotti di sola review che prendono l'intervista in ostaggio quando
nulla è supportato — **resta aperto**: seq-16 lo rende meno probabile su questa forma (ora E23 vince
per la #15), non lo cura.
