---
date: 2026-08-09
domain: operations
client_case: none
adversarial_review: codex
sources:
  - https://ai.google.dev/gemini-api/docs/pricing
  - https://ai.google.dev/gemini-api/docs/caching
  - https://developers.openai.com/api/docs/pricing
  - https://github.com/vectara/hallucination-leaderboard/
  - PG ledger llm_cost_events (query live 2026-08-09)
  - Cloud Monitoring serviceruntime/api/request_count, progetto nuzantara
---

# Quale LLM per il bot: costo e qualità contro gemini-3.5-flash

> Nasce dall'audit di spesa dello stesso giorno. Causa accertata: PR **#2611**
> (mergiata 2026-07-17T14:19Z) promuove `gemini-3.5-flash` a modello primario.
> **Il volume non è cresciuto: è sceso.** È salito il prezzo per chiamata.

## 0. Una sola base numerica

Il primo giro di questo documento citava quattro totali diversi chiamandoli tutti «il ledger».
Non erano errori di calcolo: erano **snapshot diversi di una finestra mobile**, presi a ore di
distanza e poi messi nella stessa frase. «Ultimi 30 giorni» ri-eseguito più tardi restituisce meno,
perché le righe vecchie escono dalla finestra. Da qui in avanti c'è **un solo snapshot**, congelato
insieme alla sua interrogazione in `apps/backend-rag/scripts/gemini_cost_model.py`.

Snapshot **2026-08-09, finestra mobile 30 giorni, `provider='gemini'`**:

| Modello | Endpoint | Chiamate | Token in | Token out | Costo a ledger |
|---|---|---|---|---|---|
| gemini-3.5-flash | `rag.gateway.chat` | 1.402 | 25.471.696 | 295.504 | $40,87 |
| gemini-3.5-flash | `rag.verifier` | 481 | 5.291.369 | 126.530 | $9,08 |
| gemini-3.5-flash | *(nessun endpoint)* | 276 | 650.475 | 21.268 | $1,17 |
| gemini-3.5-flash | `test` + `schematest` | 30 | 7.379 | 6.551 | $0,07 |
| **gemini-3.5-flash — totale** | | **2.189** | **31.420.919** | **449.853** | **$51,19** |
| altri modelli gemini | (2.5-flash, 3-flash-preview) | 398 | 1.222.876 | 66.705 | $0,13 |
| **tutti i gemini** | | **2.587** | | | **$51,32** |

Come si riconciliano i numeri che circolavano:

- **$51,31** (cruscotto `scripts/usage/`) = tutti i modelli gemini, costo registrato → qui $51,32.
  Combacia.
- **$51,18** = i token del solo 3.5-flash ricalcolati a listino ($1,50/$9,00). Contro i $51,19
  registrati: **0,02% di scarto**, cioè la tabella prezzi e il ledger concordano. È il numero
  fissato dal tripwire `test_measured_thirty_day_volume_still_reproduces_the_ledger`.
- **$50,00** = quanto sommavano le due sole corsie citate nella prima stesura. Mancavano tre
  endpoint ($1,24): non era un totale, era un sottoinsieme presentato come totale.

## 1. Il carico di lavoro reale (misurato, non stimato)

- **Media 18.168 token in ingresso contro 211 in uscita sul gateway** (la corsia che vale l'80% del
  conto). Il verifier ha un profilo diverso: 11.001 in / 263 out. **Non esiste una media unica per
  «Gemini»** — la prima stesura applicava quella del gateway a tutto.
- **L'input domina, ma molto meno di quanto dicesse il ledger.** Sul totale 3.5-flash: $47,13 di
  input contro $4,05 di output ricalcolati a listino — il 92%. ⚠️ **Quel 92% è un tetto, e adesso
  so quanto è ottimista.** Fino a oggi il ledger non leggeva `thoughts_token_count`, che Gemini
  fattura a tariffa OUTPUT. Misurato in questo turno su un prompt di 50 token:

  | Modello | `candidatesTokenCount` | **`thoughtsTokenCount`** | rapporto |
  |---|---|---|---|
  | `gemini-3.5-flash` | 505 | **1.383** | ×2,7 |
  | `gemini-2.5-flash` | 377 | **1.568** | ×4,2 |

  Il ragionamento costa **più del triplo della risposta visibile**, e non compariva da nessuna
  parte. Non estrapolo il ×2,7 al traffico reale — quel prompt è sintetico, il gateway ne manda da
  18k con function calling e il verifier gira a temperatura 0 su uno schema stretto, tre regimi di
  ragionamento diversi. Ma il segno non è più in dubbio: **il conto vero è sopra $51,18**, e la
  quota input sotto il 92%. Il numero esatto arriva dal ledger corretto dopo qualche giorno.
- **~2,9 chiamate al gateway per risposta completa.** Il verifier gira una volta per risposta
  (`reasoning.py:1005`), quindi 481 verdetti ≈ 481 risposte. Il raggruppamento temporale
  indipendente (gap 15s) ne conta 498: due metodi convergono su **~490 risposte in 30 giorni**.
- **Costo per risposta: ~$0,105.** Oggi poco rilevante perché il bot non è pubblico (scelta di
  Zero). È un moltiplicatore lineare il giorno che lo diventa.
- **Prefisso stabile di 5.103 token.** `ZANTARA_MASTER_TEMPLATE` è 22.638 char e i suoi tre soli
  slot variabili (`{user_memory}`, `{rag_results}`, `{query}`) stanno all'83-84%: c'è un prefisso
  contiguo, byte-identico a ogni chiamata. Vale il **28%** dell'input del gateway.
  (5.103 è una stima da 18.880 char a 3,7 char/token, non un `count_tokens`.)

### Perché il conto è esploso: una sola interrogazione, ancorata al merge

| Periodo | Chiamate | Media token in | Costo | **Costo per chiamata** |
|---|---|---|---|---|
| prima di #2611 (< 17/07 14:19Z) | 4.609 | 3.496 | $1,84 | $0,000399 |
| dopo #2611 | 2.437 | 13.166 | $51,24 | **$0,021027** |

**Il volume è calato del 47%** e il conto è salito di 28 volte. Costo per chiamata: **×52,7**.

Decomposizione, con la sua approssimazione dichiarata: prezzo input ×15
(`gemini-3-flash-preview` $0,10 → `gemini-3.5-flash` $1,50) × dimensione del prompt ×3,77
(3.496 → 13.166 token) = **×57 previsto contro ×52,7 misurato**. Il residuo del 7% è che il
periodo A non è un solo modello a un solo prezzo, ma un misto. *(La prima stesura dava «×31,7 =
×15 × ×2,2», che oltre a non moltiplicare — 15 × 2,2 = 33 — veniva da un raggruppamento mai
dichiarato e non riproducibile da questa tabella. Sostituita.)*

## 2. Costo — il nostro volume ri-prezzato, non una misura di quei modelli

Prezzi presi verbatim dalle pagine ufficiali il 2026-08-09. La colonna "30gg" è il costo dei
**nostri** token allo **loro** listino (`scripts/gemini_cost_model.py`).

> ⚠️ **Che cosa NON è questa tabella.** Le righe non-Gemini assumono lo stesso tokenizer, la stessa
> lunghezza di risposta e la stessa quantità di ragionamento nascosto che ha prodotto Gemini.
> Nessuna delle tre è garantita: tokenizer diversi divergono di decine di punti percentuali sullo
> stesso testo (Sonnet 5 ne è l'esempio in casa, ~30% in più). Sono **ordini di grandezza per
> scartare candidati**, non preventivi. Prima di agire su una riga: `count_tokens` reale.

| Modello | in /1M | out /1M | 30gg | vs oggi |
|---|---|---|---|---|
| gpt-5-nano | $0.05 | $0.40 | **$1.75** | 0.03× |
| ministral-3b-latest | $0.10 | $0.10 | $3.19 | 0.06× |
| gemini-2.5-flash-lite | $0.10 | $0.40 | **$3.32** | 0.06× |
| mistral-small-latest | $0.15 | $0.60 | $4.98 | 0.10× |
| gpt-5.4-nano | $0.20 | $1.25 | $6.85 | 0.13× |
| gemini-3.1-flash-lite | $0.25 | $1.50 | $8.53 | 0.17× |
| gpt-5-mini | $0.25 | $2.00 | $8.75 | 0.17× |
| gemini-2.5-flash | $0.30 | $2.50 | $10.55 | 0.21× |
| gemini-3.5-flash-lite | $0.30 | $2.50 | $10.55 | 0.21× |
| mistral-large-latest | $0.50 | $1.50 | $16.39 | 0.32× |
| gpt-5.4-mini | $0.75 | $4.50 | $25.59 | 0.50× |
| gpt-5.1 | $1.25 | $10.00 | $43.77 | 0.86× |
| mistral-medium-latest | $1.50 | $7.50 | $50.51 | 0.99× |
| gemini-3.6-flash | $1.50 | $7.50 | $50.51 | 0.99× |
| **gemini-3.5-flash (ATTUALE)** | **$1.50** | **$9.00** | **$51.18** | **1.00×** |
| gemini-3.1-pro-preview | $2.00 | $12.00 | $68.24 | 1.33× |

Esclusi **per regola, non per prezzo**: Anthropic (API a token vietata — unico canale è la CLI OAuth
sul MAX, marginale $0 ma spawn di processo, inadatta alla corsia interattiva); DeepSeek (ritirato da
Zero il 19/07); Kimi, Qwen, GLM (cloud cinese — confine PII assoluto, e il gateway vede domande
cliente). Grok/xAI: non verificato.

### Caching: due meccanismi diversi, e la prima stesura li ha confusi

| | Implicito | Esplicito |
|---|---|---|
| Attivazione | **già attivo** su ogni modello 2.5+ | richiede creare un oggetto cache |
| Soglia | 4.096 token su 3.5-flash (noi: 5.103) | — |
| Sconto token | −90% ($0,15/1M) | −90% ($0,15/1M) |
| Storage | **nessuno** | $1,00/1M/ora → **$3,73/mese** sul nostro prefisso |

Il risparmio massimo teorico sul prefisso è **$9,66/mese** (7.154.406 token cachabili — 1.402
chiamate × 5.103 — da $1,50 a $0,15), e vale per l'implicito **solo nella misura in cui le
richieste colpiscono davvero la cache**. Con l'esplicito resterebbero $5,93 netti dopo lo storage.
Il calcolo «−$5,98» della prima stesura sottraeva lo storage dell'**esplicito** da un risparmio
attribuito all'**implicito**: due meccanismi in una riga sola.

**Cosa resta vero e cosa no:** essere sopra soglia con un prefisso stabile prova l'**idoneità**, non
il colpo. Il campo `cached_content_token_count` non veniva letto da nessuno, quindi lo 0% a ledger
significava *non misurato*. Ora viene letto — ma **finché quel dato non gira in produzione per
qualche giorno, il tasso di hit reale è ignoto e con esso il segno dell'errore storico.** La leva 2
non è «costruire il caching»: è **leggere il numero che adesso registriamo**.

## 3. Qualità — cosa dice l'evidenza e cosa NON dice

Fonte primaria: **Vectara HHEM** (agg. 2026-05-11), 7.700+ documenti lunghi inclusi legal e
financial.

> **Che cosa misura davvero.** HHEM conta quante allucinazioni un modello introduce **generando il
> riassunto** di un documento che gli è stato fornito. **Non** misura la capacità di *giudicare* la
> fedeltà di una bozza scritta da un altro modello. Per la corsia gateway (che genera) è un proxy
> stretto; per la corsia verifier (che giudica) è un **proxy imparentato ma diverso** — restare
> ancorati a un testo e saper vedere che un altro se n'è staccato sono compiti correlati, non lo
> stesso compito. La prima stesura diceva «è *esattamente* ciò che HHEM misura»: falso.

| Modello | Allucinazione | Fedeltà |
|---|---|---|
| gpt-5.4-nano | **3.1%** | 96.9% |
| gemini-2.5-flash-lite | **3.3%** | 96.7% |
| gpt-5.4-mini | 5.5% | 94.5% |
| gemini-2.5-pro | 7.0% | 93.0% |
| gemini-2.5-flash | 7.8% | 92.2% |
| gemini-3.1-flash-lite-preview | 8.2% | 91.8% |
| gpt-5.5 | 9.3% | 90.7% |
| claude-haiku-4-5 | 9.8% | 90.2% |
| gemini-3.1-pro-preview | 10.4% | 89.6% |
| gpt-5-nano | 10.5% | 89.5% |
| gpt-5-mini | 12.9% | 87.1% |
| gemini-3-flash-preview | 13.5% | 86.5% |
| gemini-3-pro-preview | 13.6% | 86.4% |

Il risultato controintuitivo: **su fedeltà, i modelli piccoli battono i grandi**, e i Gemini 3.x
stanno peggio dei 2.5. Il modello che usavamo prima del 17/7 (`gemini-3-flash-preview`) è il
**penultimo della lista**: era economico e poco fedele.

Cosa se ne può concludere, e cosa no:

- ✅ `gemini-2.5-flash-lite` (3,3%) è **misurato più fedele di `gemini-3-flash-preview`** (13,5%),
  il modello che avevamo prima, **e costa un terzo**. ⚠️ **Su HHEM, cioè nel generare.** Sul
  *giudicare* — il compito del verifier — la misura diretta di §7 lo mette **ultimo fra i quattro
  provati** (28 false-accept su 30). Non è una contraddizione nei dati: è la distanza fra il proxy
  e il compito, e su questo asse il proxy inverte l'ordine.
- ❌ **Non** si può dire che sia più fedele di `gemini-3.5-flash`: quel modello non è in classifica.
  La prima stesura scriveva «più fedele di entrambi» e sei righe dopo ammetteva di non poterlo
  sapere. Contraddizione rimossa: sull'incumbent, **nessun dato**.
- ❌ Non è «la miglior fedeltà del board»: `gpt-5.4-nano` fa 3,1% nella tabella qui sopra, e il
  board completo scende più in basso ancora. È **il miglior Gemini misurato** tra quelli idonei.

### Le lacune, dichiarate

- **`gemini-3.5-flash` NON è in classifica HHEM.** È la lacuna più importante della ricerca: non
  sappiamo se il modello che paghiamo sia migliore o peggiore dei suoi rimpiazzi su questo asse.
- **Nessun dato di tool-calling.** BFCL (Berkeley, V4 agg. 12/04/2026) e llm-stats servono la
  tabella via JavaScript: entrambe le pagine tornano senza righe. Per la corsia gateway — che deve
  scegliere quali collezioni interrogare — non ho evidenza pubblica utilizzabile.
- **Nessun benchmark in bahasa Indonesia** ottenuto. Il bot risponde a clienti in ID/EN/IT/RU/FR.
- **Un solo asse.** HHEM non copre la scelta della lingua, il rispetto delle istruzioni, il tool-use.

> **Provenienza, dichiarata.** Le tre corsie di ricerca delegate a subagent sono morte tutte alla
> nascita con `401 OAuth access token has been revoked` e **non hanno prodotto una sola riga**:
> ogni dato di questo documento viene da fetch dirette della sessione, verificate una per una.
> Causa: la sessione porta in ambiente un `CLAUDE_CODE_OAUTH_TOKEN` revocato che gli spawn
> ereditano, mentre la credenziale su disco è viva (sonda `unset … ; claude -p` → PONG, RC=0).
> È lo scar [[m5-claude-oauth-revoked-deploy-rerouted-via-glm]] del 2026-08-08, riprodotto: il
> `/login` dell'operatore NON sana la corsia subagent della sessione già avviata. Conseguenza sul
> perimetro: Grok/xAI e i benchmark indonesiani erano assegnati a quelle corsie e **non sono mai
> stati tentati** — sono lacune non-provate, diverse da BFCL che ho tentato io e trovato illeggibile.

## 4. Le corsie vanno separate

Sono due lavori diversi che oggi girano sullo stesso modello caro:

**Corsia verifier** — giudice deterministico (`temperature=0.0`), output JSON schema-validato di
~95 token, compito = "questa bozza è fedele al contesto?".

| | costo 30gg | HHEM (proxy imparentato) | **false-accept misurati /30 (§7)** |
|---|---|---|---|
| gemini-3.5-flash (oggi) | $9,08 | non pubblicata | 26 |
| **gemini-2.5-flash** | **$1,90** | 7.8% | **8** |
| gemini-3.5-flash-lite | $1,90 | non pubblicata | 14 |
| gemini-2.5-flash-lite | $0,58 | **3.3%** | **28 — il peggiore** |
| gpt-5.4-nano | $1,22 | 3.1% | non misurato (non-Gemini) |

**Le due colonne di qualità si contraddicono, e vince quella misurata sul nostro compito.** Il
modello con la fedeltà HHEM migliore è quello che giudica peggio: HHEM misura il *generare*, non il
*giudicare*. Un benchmark pubblico su un compito adiacente ordina i candidati in modo diverso da
50 casi del nostro compito reale.

**Corsia gateway** — deve fare function calling e generare in 5 lingue. HHEM è un proxy debole e
non ho BFCL. Qui non si cambia sulla fiducia: si misura.

Scenari sul volume congelato:

| | 30gg | oggi | se il bot va pubblico (×20) |
|---|---|---|---|
| A. com'è oggi | $51,18 | 100% | ~$1.024/mese |
| B. solo verifier → **2.5-flash** (3× meglio, non solo più economico) | $44,01 | 86% | ~$880 |
| C. B + il prefisso colpisce la cache al 100% | $34,35 | 67% | ~$687 |
| D. tutto su 2.5-flash *(gateway incluso — NON raccomandato senza A/B sul tool-calling)* | $10,55 | 21% | ~$211 |

Lo scenario C è un **tetto**, non una previsione: presuppone hit su ogni chiamata (vedi §2).

## 5. Stato degli attuatori (verificato su disco e su Fly)

- **`VERIFIER_MODEL`** — variabile d'ambiente, default `gemini-3.5-flash`
  (`verification_service.py:101`), **non impostata** su nuzantara-rag. Cambiare corsia verifier è
  un `fly secrets set`, senza deploy di codice.
- **`PRIMARY_MODEL_NAME`** — è un secret su Fly ma **nessuna riga di codice lo legge** (0 occorrenze
  in `apps/` e `scripts/`). È una leva apparente: il modello primario è cablato in
  `ModelName.PRIMARY`. Cambiarlo richiede codice + deploy. Superscar #2, esiste ≠ armato.
- **`llm_gateway.py:259-260`** — `model_name_pro` e `model_name_flash` puntano **entrambi** a
  `ModelName.PRIMARY`: esiste uno slot progettato per due livelli, collassato su uno. Ogni turno,
  facile o difficile, paga il modello caro.

### Il ledger sotto-conta, e adesso sappiamo perché

2.587 righe gemini in 30 giorni contro **6.390** richieste reali a `generativelanguage.googleapis.com`
(Cloud Monitoring). Parte del divario è strutturale (`countTokens`, retry, i 429 del blackout), ma
il censimento dei punti d'ingresso ne nomina la causa maggiore: **ci sono corsie Gemini vive che il
recorder non lo chiamano affatto.**

| Punto d'ingresso | Registra? | Vivo in prod? |
|---|---|---|
| `genai_client.py:376` (`generate_content`) | ✅ | ✅ |
| `genai_client.py:554` (retry structured) | ✅ | ✅ |
| `llm_gateway.py:900` / `:1018` | ✅ | ✅ |
| `genai_client.py:706` (`generate_content_stream`) | ❌ | nessun chiamante trovato |
| `legal_ingestion_service.py:623` | ❌ | ✅ (router `legal_ingest`, worker) |
| `zantara_ai_client.py:393` / `:532` | ❌ | ✅ (`service_initializer:269`) |
| `gemini_service.py:249` | ❌ | ✅ (`query_expander:72`) |
| `chat_session.py:76` / `:98` | ❌ | da verificare |

Nessuno di questi passa dal `tracking_decorator` (usato solo per `@track_client_creation`).
**Non curato qui** — è un intervento su quattro moduli fuori dal perimetro di questa PR: va a
ledger W81 come debito tecnico, non nascosto in un diff di pricing.

## 6. Raccomandazione

1. **Verifier → `gemini-2.5-flash`** (NON `-lite`: vedi §7, la misura ha ribaltato la scelta che
   il solo HHEM suggeriva). Motivo primario **qualità, non costo**: 8 false-accept contro 26
   dell'incumbent sugli stessi 30 casi, zero falsi rifiuti. Il −$7,18/mese è un effetto collaterale.
   Reversibile con `fly secrets set VERIFIER_MODEL`, nessun deploy di codice.
   **Prima**: rifare la misura con un campione più grande e positivi parafrasati (§7).
2. **Caching: misurare, non costruire.** L'implicito è già attivo e gratuito; l'esplicito
   costerebbe $3,73/mese di storage per un guadagno marginale a questi volumi. La prossima azione è
   leggere `cache_hit_tokens` dal ledger corretto dopo qualche giorno di produzione.
3. **Gateway: non toccare senza A/B.** È la corsia che parla ai clienti, non ho evidenza di
   tool-calling, e HHEM non copre né la scelta della lingua né il function calling.
4. **Correggere le tariffe prima di fidarsi di qualunque confronto.** Fatto in questa PR: la riga
   `gemini-2.5-flash` portava $0,075/$0,30 — tariffe di due generazioni prima, 4× sotto sull'input
   e 8,33× sull'output — **e il test unitario asseriva gli stessi numeri sbagliati**, quindi tabella
   e test si confermavano a vicenda e nient'altro. Trovato solo rileggendo la riga contro il
   listino vivo.

## 7. Come si misura davvero un cambio di verifier

L'harness `apps/backend-rag/scripts/verifier_model_ab.py` esisteva già, ma su triple curate
**tutte positive**: ogni risposta vagliata usata come contesto di se stessa. Su soli positivi si
possono osservare i falsi rifiuti e l'accordo, **mai un false-accept** — cioè proprio il criterio
di decisione dichiarato al punto 1. Era una regola che nessuna esecuzione dell'harness poteva
testare.

Aggiunti casi negativi deterministici (`build_labelled_cases`): il contesto resta la risposta
vagliata, la bozza viene corrotta in due modi — **numero sbagliato** (la forma realistica: struttura
giusta, cifra sbagliata) e **norma inventata**. Accettare una bozza corrotta È il fallimento che il
verifier esiste per impedire.

### La prima versione della sonda aveva la malattia che misurava

Il primo giro con i negativi dava al modello in produzione **29 false-accept su 33**. Prima di
scriverlo ho letto due casi per intero, e il numero non reggeva:

- `(1) LKPM` → `(7) LKPM`. Ho corrotto **un numero d'elenco**, non un fatto. Il verifier ha dato
  0,95 chiamandolo «a minor numbering typo»: **ha ragione lui**. La sonda registrava come
  fallimento un comportamento corretto.
- `due 15 July` → `due 75 July`. Qui il verifier **nomina l'errore** — *«states 'due 75 July'
  instead of 'due 15 July'»* — e assegna comunque **0,9**, sopra la soglia di 0,7. Questo è un
  difetto vero, e di un tipo preciso: **non è cecità, è che il punteggio non segue il proprio
  ragionamento.**

Un numero conta solo se cambiarlo cambia un'affermazione. `corrupt_number` ora corrompe soltanto
cifre con peso semantico (valuta, data, durata, percentuale) e salta il resto: meno negativi, ma
ognuno è una contraddizione reale. Saltare è la direzione sicura — un negativo mancante sottostima
i fallimenti di un modello, un negativo fasullo ne **inventa**, e il secondo è quello che
boccerebbe un modello che funziona.

Altri due difetti dell'harness, trovati eseguendolo:

- **contava la sopravvivenza, non i verdetti.** `verify_response()` cattura da sé gli errori API e
  restituisce un segnaposto, quindi «la chiamata non ha sollevato» non dice nulla: un giro in cui
  **tutti e 100 i verdetti erano indisponibili** riportava `ok=25/25` su quattro modelli, e la
  guardia sul baseline (`n_ok == 0`) non poteva scattare per costruzione. Ora `verdicts=` e
  `returned=` sono due numeri distinti e la discrepanza è dichiarata a schermo.
- **girava su una chiave morta.** Il verifier costruisce un client proprio con
  `settings.google_api_key`, che su M5 è **diversa** dalla chiave dell'ambiente e risponde
  `429 RESOURCE_EXHAUSTED`. Produzione è sana (36h di ledger con `ko=0`), quindi la chiave esaurita
  è locale — ma la sonda che avevo usato per attribuire la colpa leggeva il client *condiviso*,
  non quello del verifier: **misuravo l'oggetto sbagliato**.

### Il risultato che conta più del costo: il gate accetta quasi tutto

Baseline `gemini-3.5-flash` — **il verifier che gira in produzione** — su 50 casi
(20 fedeli, 30 corrotti):

**26 false-accept su 30. Zero falsi rifiuti.**

Distribuzione dei punteggi (soglia del gate: 0,7):

| Tipo di caso | n | ≥0,7 | punteggi |
|---|---|---|---|
| fedele *(dovrebbe passare)* | 20 | 20 | `1.0` ×20 |
| **numero sbagliato** *(dovrebbe fallire)* | 10 | **10** | `0.9` ×9 · `0.8` ×1 |
| **norma inventata** *(dovrebbe fallire)* | 20 | **16** | `0.8` ×6 · `0.75` ×5 · `0.7` ×5 · `0.6` ×3 · `0.5` ×1 |

Non sono verdetti incerti: sulle cifre contraddette il modello accetta **con sicurezza** (0,9).
E non è cecità — nel caso letto per intero il verifier **nomina l'errore** e poi lo promuove.
Conseguenza operativa: il self-correction, che parte sotto 0,7, **non scatta quasi mai**
sull'infedeltà reale. Il gate esiste, è vivo dal #2973, e lascia passare l'87% delle bozze
infedeli.

> ⚠️ **Limite di questo campione, e non è piccolo.** I casi fedeli sono la risposta vagliata usata
> come contesto di se stessa: **copie verbatim**, non parafrasi. Il loro `1.0` non dice quanto
> scorerebbe una risposta legittima ma riformulata, quindi **questi dati NON permettono di
> concludere «basta alzare la soglia a 0,95»** — alzarla potrebbe respingere parafrasi buone, e
> questo campione non può misurarlo. Quello che i dati stabiliscono è più stretto e già grave:
> su bozze realmente infedeli il punteggio cade **sopra** la soglia.

### Cosa NON è ancora misurato

### Il confronto a quattro modelli — e ribalta la raccomandazione

50 casi identici per modello (20 fedeli, 30 corrotti), stesso harness, stessa chiave.

| Modello | **False-accept /30** | Falsi rifiuti /20 | Latenza | Accordo con l'incumbent | Verifier 30gg |
|---|---|---|---|---|---|
| `gemini-3.5-flash` *(oggi)* | 26 | 0 | 6,51s | — | $9,08 |
| **`gemini-2.5-flash`** | **8** | 0 | 8,20s | **60%** | **$1,90** |
| `gemini-3.5-flash-lite` | 14 | 0 | 3,83s | 76% | $1,90 |
| `gemini-2.5-flash-lite` | **28** | 0 | 4,13s | 88% | $0,58 |

Tre cose, e due sono contro quello che avevo scritto tre ore fa:

1. **`gemini-2.5-flash` giudica 3× meglio dell'incumbent e costa 1/5** — 8 false-accept contro 26,
   zero falsi rifiuti. È l'unico candidato che migliora davvero il gate.
2. **`gemini-2.5-flash-lite`, il modello che avevo raccomandato, è il PEGGIORE della lista** (28/30).
   L'avevo scelto sulla fedeltà HHEM (3,3%, la migliore fra i Gemini misurati). **HHEM misura il
   generare, non il giudicare**: l'avevo dichiarato come limite del proxy e il limite era reale.
   Seguire quella raccomandazione avrebbe peggiorato il fact-check risparmiando $8,50.
3. **L'accordo con l'incumbent è ANTI-correlato con la qualità**: 88% di accordo → il peggiore,
   60% → il migliore. Ovvio a posteriori — l'incumbent sbaglia 26 volte su 30, quindi somigliargli
   è un difetto — ma è esattamente il criterio che l'harness misurava prima di oggi, e avrebbe
   incoronato `2.5-flash-lite`. **Un test di somiglianza a un giudice sbagliato premia lo sbaglio.**

⚠️ Campione piccolo (30 negativi per modello) e positivi non realistici (copie verbatim, vedi
sopra). Prima di spostare `VERIFIER_MODEL` in produzione questo va rifatto con `--n` più alto e con
positivi parafrasati, altrimenti si sostituisce un giudizio su 30 casi a uno su nessuno.

Riproducibile:

```bash
cd apps/backend-rag
GOOGLE_API_KEY=<chiave viva> PYTHONPATH=. python -u scripts/verifier_model_ab.py --n 20
```

## §Solo-operatore

- La fattura vera di Cloud Billing (progetto `nuzantara`, `930328104463`) — non esposta da
  `gcloud`, nessun export BigQuery: serve la console.
- La scelta del modello per la corsia client-facing è una decisione qualità/business (Legge 5).
- Un'eventuale chiave OpenAI per il piano gateway/verifier: OpenAI è già in produzione per gli
  embedding, ma allargarne l'uso è autorizzazione di Zero.
- Ricarica crediti Gemini sulla chiave di sviluppo M5 (429) — oppure la si lascia morta e si usa la
  chiave AI Studio dedicata.

## Adversarial review

Round R1 condotto da **Codex GPT-5.6 sol** (generator ≠ grader) su documento + diff.
Verdetto: **DOES-NOT-SURVIVE**, 17 rilievi. Nessuno derogato. Esito, uno per uno:

**Accolti e corretti nel codice** (con test di colpevolezza e innocenza):

- **#12 CRITICA** — `gemini-2.5-flash` a $0,075/$0,30 invece di $0,30/$2,50. Corretto, più
  `gemini-3.6-flash` aggiunto; tripwire su tutte e sei le righe contro il listino ufficiale.
- **#13 ALTA** — il longest-match introdotto da questa PR faceva risolvere `gemini-3.5` alla riga
  *lite*, più economica. **Verificato peggiore del riportato**: `flash` finiva sulle tariffe
  DeepSeek e `gemini` su 2.5-flash. Le due direzioni di sottostringa non sono simmetriche e ora
  sono trattate separatamente: un'abbreviazione ambigua risolve a `unknown` e lo dichiara nel log.
- **#15 ALTA** — `create_token_usage()` (che alimenta il tetto di spesa del gateway) non riceveva
  cache né thinking: ledger e guardia operativa prezzavano la stessa chiamata in due modi. Corretto.
- **#8 ALTA** — l'harness non poteva misurare i false-accept. Corretto con casi negativi (§7), **e
  la misura che ne è uscita ha ribaltato la raccomandazione di questo stesso documento**: il
  modello che raccomandavo (`2.5-flash-lite`, scelto su HHEM) è risultato il peggiore dei quattro,
  e il criterio che l'harness usava prima — accordo con l'incumbent — è anti-correlato con la
  qualità. Il rilievo non era una formalità: senza, avremmo spostato il verifier sul giudice
  peggiore chiamandolo un risparmio.
  **E la correzione ha avuto essa stessa il difetto**: la prima versione corrompeva qualunque
  cifra, quindi mutava numeri d'elenco e contava come fallimento la reazione corretta del modello
  (29 false-accept apparenti, contaminati). Trovato leggendo due casi per intero invece di fidarsi
  del contatore. Ora corrompe solo cifre con peso semantico, con innocenza pinnata sugli
  enumeratori.
- **#17 MEDIA** — `cost_model.py` non era nel repo. Committato come
  `apps/backend-rag/scripts/gemini_cost_model.py`, con lo snapshot congelato.

**Accolti e corretti nel documento**: #1 (quattro basi numeriche → §0), #2 (le medie sono
per-endpoint), #3 (×31,7 irriproducibile → ×52,7 ri-derivato), #4 (il 92% è un tetto), #5
(contraddizione su 2.5-flash-lite), #6 (HHEM non misura il giudicare), #7 («miglior del board» era
falso), #10 (idoneità ≠ hit), #11 (implicito vs esplicito), #14 (l'affermazione «mai sotto-fattura»
ristretta al costo per-token di lettura Gemini).

**Ridimensionato da misura, non da opinione**: **#16** dice che la corsia streaming resta fuori dal
ledger — vero, ma `grep` non le trova **alcun chiamante di produzione**, quindi non è spesa
invisibile. Cercandolo però è emerso di peggio, che il rilievo non nominava: **quattro** altri
percorsi Gemini vivi non registrano nulla (§5). Il rilievo era giusto in piccolo e piccolo per
difetto.

**Nessun rilievo**: #9 (la semantica cached-as-subset è corretta per Gemini).
