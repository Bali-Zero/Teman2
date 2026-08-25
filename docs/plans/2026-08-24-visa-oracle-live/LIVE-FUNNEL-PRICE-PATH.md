# Il percorso REALMENTE live — dove un prezzo può raggiungere il visitatore, e da dove viene

> Misurato 2026-08-25 in questo worktree, sul codice sorgente — nessuna chiamata di rete a
> `balizero.com` in questa sessione. Risponde alla domanda lasciata esplicitamente aperta da
> `TWO-DOORS.md` §"Honest re-reading required": la sezione "the public funnel does NOT invent
> prices" di quel documento è stata scritta leggendo `visa_oracle.py` — il **modulo sbagliato**.
> Questo documento rilegge la stessa domanda contro il percorso che gira davvero:
> `apps/backend-rag/backend/app/routers/visa_check.py::submit_match` →
> `backend/services/visa_check/match_tree.py::recommend_visa` →
> `backend/services/visa_check/repository.py::VisaCheckRepository`, più tutto ciò che
> `/visa/match/[hash]` e `/visa/clock/[hash]` renderizzano — chat compresa, perché quella chat è
> risultata essere codice condiviso con `visa_oracle.py`.

## Sintesi

Il percorso principale (submit → risultato) **rispetta la regola d'oro #11**: l'unico numero di
prezzo che il visitatore vede viene da `PricingService` (il `PricingTool` del CLAUDE.md), non è mai
hardcoded, e degrada onestamente a "conferma su WhatsApp" quando manca una quotazione. Questo è
verificato, non presunto: ho letto ogni riga del bridge e del punto di rendering.

Due cose però **non** erano coperte dalla correzione di `TWO-DOORS.md`, e la ampliano invece di
smentirla:

1. Un widget di chat live-nel-tempo, presente su **entrambe** le pagine risultato
   (`/visa/match/[hash]` e `/visa/clock/[hash]`), che POSTA su `/api/v1/visa-oracle/chat` —
   esattamente il modulo `visa_oracle.py` che `TWO-DOORS.md` aveva dichiarato "morto dal frontend
   live". Non lo è: è dead per la RACCOMANDAZIONE (`/recommend`), ma **vivo** per la chat e
   l'handoff. Questa chat può enunciare "fees" trovate in un contesto RAG che **non** è
   `PricingTool` — un secondo canale di prezzo, non gated dallo stesso bridge.
2. Catalogo hardcoded (`catalogue.py`) con soglie finanziarie in IDR/USD (capitale minimo
   investitore, depositi Second Home, prova di risparmio) che raggiungono la pagina risultato nella
   sezione "Why it fits" e nella checklist pre-arrivo. Non sono "prezzi Bali Zero" nel senso della
   regola #11 — sono requisiti finanziari del programma visto, non parcelle del servizio — ma sono
   comunque cifre in valuta, hardcoded, mai passate da `PricingTool`, e mostrate senza alcun
   degrado quando la riga si applica.

Nessuna delle due cose fabbrica un **prezzo di servizio Bali Zero** falso. Ma la prima apre una
strada per cui l'LLM potrebbe farlo, e non è chiusa dallo stesso meccanismo che protegge
`/api/visa/match`.

---

## 1. Il prezzo del servizio — `estimated_cost_idr`, dalla submit al render

### 1.1 Backend: `POST /api/visa/match`

`apps/backend-rag/backend/app/routers/visa_check.py:225-268` (`submit_match`):

```python
result = recommend_visa(nationality=..., purpose=..., duration_months=..., budget_band=...)

cost: int | None = None
cost_source: str | None = None
if result.recommended_visa is not None:
    cost, cost_source = estimate_match_cost(visa_type=result.recommended_visa, pricing=_pricing)
```

`_pricing` è un `PricingService()` istanziato una sola volta a import-time (`visa_check.py:66`) —
lo stesso `PricingService` che il CLAUDE.md backend-rag chiama "Tool #2 / PricingTool", che carica
`backend/data/bali_zero_official_prices_2026.json` (`pricing_service.py:161`).

`estimate_match_cost` — `backend/services/visa_check/pricing_bridge.py:83-108` — non ha nessun
valore hardcoded: cerca `pricing.search_service(hint)` per una lista di stringhe (`_SEARCH_HINTS`,
righe 38-66), sceglie il candidato con punteggio più alto (`_best_pricing_candidate`,
righe 120-151), ed estrae il numero SOLO da `item["price"]`/`item["price_idr"]`
(`_extract_cost`, righe 214-221) — mai un default numerico. Se nessun hint produce un candidato:

```python
logger.warning("pricing_bridge: no quote found for %s (hints=%s)", visa_type.value, hints)
return None, None
```

Due `VisaType` sono dichiarati "known-None" a monte (`KNOWN_NONE_VISAS`, righe 26-31: `C6`, `E30A`)
— intenzionali, non bug, per costruzione del bridge.

**Verifica del degrado quando `PricingService` non è caricato.** Letto `pricing_service.py:278-284`:
se `self.loaded` è `False`, `search_service()` ritorna `{"error": "...", "contact": {...}}` — non
un dizionario di servizi. In `pricing_bridge.py:96-101`, `results.get("results")` e
`results.get("services")` sono entrambi `None`, quindi `services = results` (il dict `error/contact`
stesso). `_best_pricing_candidate` itera quelle due chiavi: `"error"` porta una stringa (non
iterabile come items → `_iter_candidate_items` ritorna `[]`), `"contact"` porta un dict di stringhe
(email/whatsapp, nessuna ha una chiave `price`) → nessun candidato con `_extract_cost` valorizzato.
Risultato: `candidates == []`, la funzione ritorna `None`. Nessun prezzo fittizio anche in questo
stato di guasto — verificato leggendo il codice, non eseguito (nessun `.venv` in questo worktree,
vedi §5).

`cost`/`cost_source` finiscono in `MatchResponse` (righe 279-289) e persistiti in Postgres
(`repository.py:100-159`, colonna `visa_checks.estimated_cost_idr`). Sul GET di ricarico
(`get_match`, righe 320-354) `cost_source` torna sempre `None` — commento a riga 343: "not
persisted; rebuildable if needed" — ma `estimated_cost_idr` sì, quindi il numero sopravvive al
refresh della pagina, la sua etichetta di provenienza no.

### 1.2 Frontend: `/visa/match/[hash]`

`apps/mouth/src/app/visa/match/[hash]/page.tsx` fa `fetch('/api/visa/match/${hash}')` (riga 47) e
renderizza (righe 178-208):

```tsx
{
  data.estimated_cost_idr ? (
    <div>{formatIDR(data.estimated_cost_idr)}</div>
  ) : (
    <p style={{ fontStyle: "italic" }}>
      Let&apos;s confirm the exact fee on WhatsApp — your case has specifics.
    </p>
  );
}
```

`formatIDR` (`packages/core/utils/currency.ts:33-35`) è un puro `Intl.NumberFormat` — nessun
default numerico, nessun fallback silenzioso.

**Degrado confermato end-to-end**: `estimated_cost_idr == null` ⇒ il ramo che renderizza un numero
non viene mai eseguito; il ramo alternativo è testo, non un placeholder come `0` o `"—"`. La CTA
WhatsApp (righe 293-304) fa lo stesso: `data.estimated_cost_idr ? formatIDR(...) : "To confirm"`.
Questo è l'equivalente del `CONTACT_REQUIRED` che il mandato chiedeva di verificare — esiste, ed
è cablato correttamente nel percorso REALMENTE live (non in `visa_oracle.py` come la vecchia
correzione aveva erroneamente concluso).

**Difetto minore trovato, non un'invenzione di prezzo**: il footer di `AppFrame` (righe 124-129)
recita sempre, per qualunque raccomandazione non-referral:

```
Cost from PricingTool (source: {data.cost_source ?? "PricingTool"}).
```

indipendentemente dal fatto che un costo sia stato trovato. Quando `estimated_cost_idr` è `null`
(nessuna quotazione), la sezione "Estimated cost" mostra correttamente il testo di degrado, ma il
footer sotto continua ad affermare "Cost from PricingTool" — un'affermazione di copy vuota di
riferimento, non un numero inventato, ma fuorviante quando letta isolata dal resto della pagina.

### 1.3 `/visa/clock/[hash]` — nessun prezzo

`apps/mouth/src/app/visa/clock/[hash]/page.tsx`: nessuna occorrenza di prezzo, fee, IDR o USD nel
rendering. L'unico riferimento monetario è un link esterno testuale nel footer, riga 99:
`<a href="https://balizero.com/pricing">pricing reference</a>` — un link, non una cifra. Verificato
con lettura integrale del file (233 righe) più `grep -niE "price|harga|fee|cost|IDR|Rp|USD|amount|tarif"`
sullo stesso file: zero hit oltre a quel link e alla parola "pricing" nell'URL/testo del link.

---

## 2. Cifre in valuta hardcoded nel catalogo — non prezzi Bali Zero, ma cifre reali sulla pagina

`backend/services/visa_check/catalogue.py` è la fonte di `VISA_META`. Il proprio docstring
(riga 11) è onesto sulla natura del dato: **"min_budget_idr: Bali Zero commercial judgement, not a
legal threshold"**. Sono soglie di idoneità del prodotto-visto (capitale minimo per investire,
deposito Second Home, prova di reddito), non parcelle di servizio Bali Zero — quindi la regola
d'oro #11 ("mai hardcodare i PREZZI, sempre da PricingTool") non li chiama in causa nel senso
letterale. Ma sono comunque **cifre in valuta**, hardcoded, senza alcun collegamento a
`PricingTool`, e raggiungono `/visa/match/[hash]` ogni volta che quel `VisaType` è nel ranking —
senza alcun degrado equivalente a "contact for pricing".

Trovate (grep completo su `catalogue.py` + `match_tree.py`, righe citate una per una — file letti
per intero, non solo grep-ati):

| VisaType                 | Campo            | Valore                                   | File:riga                  |
| ------------------------ | ---------------- | ---------------------------------------- | -------------------------- |
| `E23_FREELANCE`          | `min_budget_idr` | `25_800_000`                             | `catalogue.py:262`         |
| `E28A` (Investor)        | `min_budget_idr` | `500_000_000`                            | `catalogue.py:275`         |
| `E28A`                   | `notes`          | `"~IDR 10bn capital"`                    | `catalogue.py:276`         |
| `E33` (base Second Home) | `notes`          | `"USD 130,000 ... or USD 1,000,000 ..."` | `catalogue.py:319-320`     |
| `E33E`/`E33F`/`E33G`     | `min_budget_idr` | `500_000_000` / `None` / `50_000_000`    | `catalogue.py:333,346,358` |
| `E33F`                   | `notes`          | `"USD 3,000/mo passive income"`          | `catalogue.py:347`         |
| `E33G`                   | `notes`          | `"USD 60k savings proof"`                | `catalogue.py:359`         |

**`E33` (base) è inerte in questo funnel** — verificato: `purposes=frozenset()` (riga 305, commento
esplicito alle righe 301-304: "the match wizard has no second-home branch ... base E33 is never
surfaced by recommend_visa"). `_rank_for_purpose` (`match_tree.py:262-286`) filtra per
`purpose in meta.purposes`; un `frozenset()` vuoto non entra mai in nessun branch. Quindi la cifra
USD 130.000/1.000.000 di `E33` **non** raggiunge mai il visitatore da questo funnel — solo `E33E`,
`E33F`, `E33G` sono raggiungibili (branch `RETIREMENT` e `WORK_REMOTE`/`INVESTOR`).

Per le voci raggiungibili, il rendering è duplice:

- `_reason()` (`match_tree.py:245-256`) compone: `f"{meta.notes}{budget_note}."` dove
  `budget_note = f" (requires ≥ IDR {min_budget_idr // 1_000_000}M)"` — questa stringa diventa
  `data.reason`, mostrata in "Why it fits" su `/visa/match/[hash]` (riga 160-176 del componente).
- `pre_arrival_steps` (`match_tree.py:110-172`) — liste hardcoded, mostrate in "Pre-arrival
  checklist" (righe 210-232 del componente):
  - `_STEPS_DIGITAL_NOMAD[1]` (riga 112): `"Bank statement showing ≥ USD 60,000 balance (12 months)"`
  - `_STEPS_INVESTOR[1]` (riga 127): `"Investment plan document (IDR equivalent ≥ 10bn for E28A)"`
  - `_STEPS_RETIREMENT[0]` (riga 142): `"Proof of pension or passive income ≥ USD 3,000/month"`

Nessuna di queste ha un gate di tipo "contact for pricing": se il `Purpose` e il `BudgetBand`
producono quel `VisaType` nel ranking, la cifra è nel body della risposta, punto. Non ho trovato
(grep + lettura di `test_catalogue.py`, `test_match_tree.py` — nomi file, non contenuto integrale,
per lo scopo di questa verifica) un test che confronti queste cifre contro
`bali_zero_official_prices_2026.json` o una fonte regolatoria esterna con un gate di freshness:
se una soglia normativa cambia, questa stringa non ha meccanismo di allarme conosciuto in questo
sottoalbero. Non lo dichiaro un difetto di prezzo — sono soglie di idoneità, non parcelle — ma è
un punto di manutenzione aperto che il mandato mi chiede di segnalare come "currency string" reale.

---

## 3. La chat sulle pagine risultato — il canale che `TWO-DOORS.md` non aveva misurato

Questo è il ritrovamento che corregge silenziosamente la correzione precedente. `TWO-DOORS.md`
("Second correction") aveva stabilito che `VisaOracleService`/`visa_oracle.py` è **"dead from the
live frontend — nothing on the live page calls it"**, con una sola eccezione dichiarata:
`recommendVisas()` (mai importato da un componente pagina). Questo è vero per `recommendVisas()`.
**Non è vero per l'intero modulo**: `visa_oracle.py` espone anche `/chat` e `/handoff`, e questi
DUE endpoint sono raggiunti dal vivo, dalle stesse pagine risultato oggetto di questo audit.

### 3.1 La catena, verificata file per file

- `apps/mouth/src/app/visa/match/[hash]/page.tsx` (riga ~257) e
  `apps/mouth/src/app/visa/clock/[hash]/page.tsx` (riga ~146) montano entrambi
  `<ChatAccordion checkHash={data.hash} sessionJwt={data.session_jwt} .../>` quando
  `session_jwt` non è nullo — e non lo è mai su una risposta fresca (`visa_check.py` emette
  `session_jwt=_issue_visa_funnel_jwt(saved.hash)` su ogni POST e ogni GET, righe 221, 292, 322,
  353).
- `ChatAccordion.tsx` (righe 1-33) monta `<VisaChat checkHash={checkHash} sessionJwt={sessionJwt} />`
  quando l'utente apre l'accordion ("Ask 3 free questions").
- `VisaChat.tsx` (righe 100-112) chiama `sendChatMessage(sessionId, message, quizAnswers, messages, checkHash, sessionJwt)`.
- `apps/mouth/src/lib/visa-oracle/api.ts:267-289` (`sendChatMessage`) POSTA su
  `${API_BASE}/api/v1/visa-oracle/chat` con header `Authorization: Bearer ${sessionJwt}` quando
  `checkHash && sessionJwt` sono presenti (riga 283-285).
- Quell'endpoint è `apps/backend-rag/backend/app/routers/visa_oracle.py:886` (`@router.post("/chat")`)
  — lo stesso file/modulo che la correzione precedente aveva scagionato come morto. È **vivo**, ed
  è pubblico/anonimo (`public_endpoints.py:541-544`: "Anonymous visa Q&A chat — rate-limited by IP
  hash, no PII collected").

Stessa catena per l'handoff quando le 3 domande finiscono o l'LLM abbandona (ABSTAIN):
`VisaChat.tsx:70-79` (`doHandoff`) → `triggerHandoff()` (`api.ts:292-300`) →
`POST /api/v1/visa-oracle/handoff` → `visa_oracle.py:1202` (`@router.post("/handoff")`).

### 3.2 Come il prezzo entra (o non entra) nella risposta della chat

`chat()` (`visa_oracle.py:886-1199`) quando riceve `check_hash` (righe 949-987):

```python
ctx = await _get_ctx(body.check_hash, db_pool)          # visa_unified/bridge.py
if ctx is None:
    raise HTTPException(status_code=410, detail="Wizard context expired")
system_prompt_prefix = _augment(ctx, "")
```

`get_funnel_context` (`backend/services/visa_unified/bridge.py:35-79`) legge `visa_checks` con
**`WHERE hash = $1 AND branch = 'match'`** (riga 48). Questo filtro sul branch è letterale nel
codice, non una mia inferenza.

`augment_chat_system_prompt` (`bridge.py:82-121`), quando esiste una raccomandazione:

```python
cost_line = (
    f" Cost from PricingTool: IDR {context.estimated_cost_idr:,}."
    if context.estimated_cost_idr else ""
)
...
preamble = (
    f"Recommended visa: {context.recommended_visa}.{cost_line}{alts} "
    "Always quote this recommended visa and cost unless the user explicitly "
    "asks for an updated price; in that case say Bali Zero will confirm on WhatsApp. "
    "Do not invent alternative visas beyond the ones listed above.\n\n"
)
```

**Quando `estimated_cost_idr` è valorizzato**, questo è corretto e chiuso: il prezzo che l'LLM
riceve come fatto è testualmente lo stesso che `/api/visa/match` ha già calcolato da PricingTool,
e l'istruzione dice esplicitamente di non inventarne uno diverso.

**Quando `estimated_cost_idr` è `None`** (nessuna quotazione trovata dal bridge), `cost_line` è
stringa vuota — la frase "Cost from PricingTool: IDR X" sparisce del tutto dal preambolo — ma la
frase finale resta: **"Always quote this recommended visa and cost..."**, senza alcun costo
effettivamente fornito da quotare. È un'incoerenza di prompt reale, letta sul codice sorgente, non
un comportamento del modello che ho osservato (non ho eseguito il modello in questa sessione): non
affermo che l'LLM inventi un numero qui, affermo che l'istruzione che gli viene data non gli dice
cosa fare in questo caso specifico, e "always quote... cost" è un'istruzione che presume un valore
che non è stato passato. Rischio aperto, non un difetto confermato.

**Indipendentemente dal preambolo**, il `SYSTEM_PROMPT` di base del router (`visa_oracle.py:208-243`,
usato su OGNI chiamata a `/chat`, con o senza `check_hash`) dice testualmente:

> "Be concrete and specific. Give real numbers (stay days, extension limits, **fees**) only when
> they're in the **context**."

Il "context" qui (righe 1112-1141) è il testo recuperato da `HybridSearchService().search_hybrid(
collection="visa_oracle", ...)` — una collection Qdrant di knowledge-base generica, **non**
`PricingService`/`bali_zero_official_prices_2026.json`. Questo significa che, a prescindere dal
preambolo legato al wizard, il modello è esplicitamente autorizzato a citare una "fee" se compare
nel materiale indicizzato in quella collection. **Non ho verificato in questa sessione cosa sia
effettivamente indicizzato in `visa_oracle`** — la ricerca dell'ingestion pipeline per quella
collection tocca decine di file cross-cutting (`services/ingestion/`, `services/rag/agentic/`,
ecc.) condivisi da tutto il RAG, non solo dal funnel visa, ed è fuori dallo scope di questo audit
mirato al funnel live. Segnalo il canale come **secondo percorso di prezzo, non gated da
PricingTool**, senza affermare che oggi contenga cifre sbagliate — è una domanda aperta per chi
possiede l'ingestion di quella collection, non un difetto chiuso.

### 3.3 Effetto collaterale trovato: la chat è rotta (410) su `/visa/clock/[hash]`, il che la rende innocua lì

`get_funnel_context` filtra `branch = 'match'` (bridge.py:48). Una riga `visa_checks` creata da
`submit_clock`/`get_clock` ha `branch = 'clock'` (`repository.py:79`, `INSERT INTO visa_checks
(hash, branch, ...) VALUES ($1, 'clock', ...)`). Quindi **ogni** messaggio di chat inviato dal
widget montato su `/visa/clock/[hash]` fa fallire `get_funnel_context` (nessuna riga trovata per
quell'hash con quel filtro) → `ctx is None` → l'endpoint risponde **HTTP 410** prima di generare
qualunque testo. Effetto sul mandato: nessun prezzo (né corretto né sbagliato) può mai raggiungere
un visitatore dalla chat di Clock, perché quella chat non risponde mai — è un difetto funzionale
reale e verificabile via lettura di codice, adiacente ma distinto dalla domanda sui prezzi. Lo
segnalo perché la disciplina del mandato chiede di dire esplicitamente quando una superficie non è
raggiungibile, non solo quando lo è.

### 3.4 L'handoff, quando raggiunto dalla chat delle pagine risultato: non fabbrica, ma perde il prezzo vero

`handoff()` (`visa_oracle.py:1202-1334`) risolve prezzo e nome-visto da
`_fetch_session_snapshot_with_retry(db_pool, body.session_id)` — che legge una tabella di sessione
diversa (quella popolata da `/recommend`, il ramo morto), non `visa_checks`. Il `session_id` che
`VisaChat.tsx` genera e passa (`sessionIdRef.current`, da `getSession().sessionId` — uno storage
locale del browser, non il `check_hash`) non ha mai una riga in quella tabella quando si arriva da
`/visa/match/[hash]` o `/visa/clock/[hash]`. Quindi, per costruzione:

```python
server_top = server_visas[0] if server_visas else {}   # sempre {} in questo percorso
price = server_top.get("price") or "contact for pricing"   # sempre "contact for pricing"
visa_name = server_top.get("visa_name", "Indonesian Visa")  # sempre il placeholder generico
```

Nessun prezzo inventato — verificato, è letteralmente la stringa costante "contact for pricing"
ogni volta. Ma è anche un difetto di qualità distinto: il vero `estimated_cost_idr` che
`/api/visa/match` ha già calcolato e persistito per quello stesso `hash` non viene mai riusato qui,
quindi il lead che arriva su WhatsApp/Telegram da questo canale perde l'informazione di prezzo che
il sistema possedeva. Fuori dallo scope stretto ("mette un prezzo sbagliato davanti al
visitatore?" — no), ma dentro lo scope largo del mandato ("dov'è la fonte, e come degrada").

---

## 4. Sopravvivenza post-ritiro (owner ruling #4)

Verificato su `apps/mouth/next.config.ts:340-368` (commento esplicito a righe 348-358, che cita
`OWNER-RULINGS-2026-08-25.md` §4 verbatim):

```ts
{ source: "/visa", destination: "/visa-oracle", permanent: true },
{ source: "/visa/match", destination: "/visa-oracle", permanent: true },
```

Sono match **esatti** (niente `:path*`), e il commento lo dice apertamente: "this must NOT catch
`/visa/match/[hash]` (already-shared result pages, still meant to resolve) or `/visa/clock`, ...".
Confermo quindi esplicitamente, per ciascuna sezione sopra:

- **§1 (prezzo del servizio, `/visa/match/[hash]`)**: LIVE dopo il 301. Non redirectata.
- **§2 (soglie hardcoded)**: LIVE dopo il 301, stesse pagine.
- **§3 (chat + handoff)**: LIVE dopo il 301 — `/api/v1/visa-oracle/chat` e `/handoff` non sono
  toccati dai redirect di pagina (sono chiamate API lato client dopo che la pagina risultato è
  già caricata, non route Next.js).
- **`/visa/clock/[hash]`**: mai stato oggetto del redirect (non è nella lista sorgenti), LIVE
  come prima.

Nessuna delle superfici misurate in questo documento viene spenta dal ruling #4.

---

## 5. Disciplina di verifica — cosa renderebbe rossa ciascuna affermazione

Per onorare esplicitamente la richiesta "di' cosa avrebbe reso rossa questa prova":

- **§1 (degrado del prezzo)** sarebbe FALSIFICATA se `pricing_bridge.estimate_match_cost` avesse un
  ramo che ritorna un intero costante quando `candidates == []`, o se il componente React
  renderizzasse `formatIDR(data.estimated_cost_idr ?? 0)` invece del branch condizionale — ho letto
  entrambi i file per intero e nessuno dei due pattern è presente.
- **§2 (soglie catalogo)** sarebbe FALSIFICATA (nel senso di "sono anche prezzi Bali Zero mascherati")
  se `estimate_match_cost` le usasse come fallback di prezzo — non lo fa: `pricing_bridge.py` non
  importa né referenzia `catalogue.min_budget_idr` in nessun punto (grep mirato:
  `grep -n "min_budget_idr" backend/services/visa_check/pricing_bridge.py` → nessun hit).
- **§3.2 (canale RAG)** — l'affermazione "non è PricingTool" sarebbe FALSIFICATA se
  `HybridSearchService.search_hybrid` per la collection `visa_oracle` risultasse alimentata
  esclusivamente dallo stesso file `bali_zero_official_prices_2026.json`; non l'ho verificato (fuori
  scope dichiarato), quindi la dichiaro esplicitamente come NON provata in nessuna delle due
  direzioni, non come "provata sbagliata".
- **§3.3 (410 su Clock)** sarebbe FALSIFICATA se `get_funnel_context` non filtrasse per `branch`, o
  se esistesse un secondo lookup fallback per `branch='clock'` altrove in `bridge.py` — il file ha
  134 righe, letto per intero, un solo `SELECT` con quel filtro letterale.
- **Assenza di prezzo in `/visa/clock/[hash]` (§1.3)** — grep multi-ortografia eseguito sul file
  intero: `price|harga|fee|cost|IDR|Rp|USD|amount|tarif`, case-insensitive; unico hit è la parola
  "pricing" dentro l'URL/testo del link esterno, non un valore.
- Non ho eseguito la test-suite Python (`.venv` assente in questo worktree —
  `.venv/bin/python: No such file or directory`, verificato con `ls`); le affermazioni sul codice
  Python sono quindi lettura statica riga-per-riga, non esecuzione. Le ho compensate leggendo per
  intero (non solo grep) ogni file del percorso critico: `visa_check.py`, `match_tree.py`,
  `pricing_bridge.py`, `repository.py`, `catalogue.py`, `clock.py`, `bridge.py`, e le sezioni
  pertinenti di `visa_oracle.py` e `pricing_service.py`.

---

## Cosa NON è stato misurato qui

- Il contenuto reale della collection Qdrant `visa_oracle` (§3.2) — chi possiede l'ingestion di
  quella collection dovrebbe confermare se contiene mai una cifra di prezzo, e se sì da dove viene.
- Il comportamento a runtime dell'LLM quando il preambolo ha `cost_line` vuoto (§3.2) — è
  un'osservazione sul prompt, non un'osservazione su un output generato.
- Se `E28A`/`E33F`/`E33G` vengano effettivamente selezionati in produzione con che frequenza — qui
  importa solo che il codice li rende raggiungibili, non quanto spesso lo sono.
