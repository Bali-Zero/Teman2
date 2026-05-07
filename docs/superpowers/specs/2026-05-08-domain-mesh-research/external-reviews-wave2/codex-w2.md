## A. Wave 1 Fixes

1. **`pasal_id_client.py`: parser fallback non è sicuro per `work: null`**
   - `work = item.get("work", item)` gestisce `work` mancante e `work: {}`, ma non `work: null` o `work` non-dict.
   - Con `work: null`, la riga `work.get(...)` esplode con `AttributeError`.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/pasal_id_client.py:91-97`.
   - Fix: normalizzare `work = item.get("work") if isinstance(item.get("work"), dict) and item.get("work") else item`.

2. **`arxiv_sanity_scorer.py`: math del CV è corretta**
   - `cv = max(2, min(3, min_class))` produce `3` quando `min_class = 100`, quindi ok.
   - `min_class < 2` viene rifiutato subito dopo, quindi il caso insufficiente è coperto.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/arxiv_sanity_scorer.py:41-48`.

3. **`ner_extractor.py`: lazy load non thread-safe**
   - Due thread possono vedere `_pipeline is None` contemporaneamente e inizializzare due pipeline HuggingFace.
   - Questo è soprattutto pericoloso su Mini-Pro2: doppio download/caricamento modello e memoria duplicata.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/ner_extractor.py:42-51`.
   - Serve lock, oppure cache globale thread-safe.

## B. What Wave 1 Missed

1. **Import pubblico delle foundations rende fragile anche il cron leggero**
   - `foundations/__init__.py` importa subito `arxiv_sanity_scorer` e `ner_extractor`, quindi richiede `sklearn`, `transformers`, `torch` anche quando il cron vuole solo `probe_inventory`.
   - Il cron fa `from mata_garuda.foundations import probe_inventory`, quindi un env senza deps ML fa fallire anche il probe gov-apis.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/__init__.py:16-35`, `infra/scripts/domain-mesh-foundations-cron.sh:16-19`.
   - Fix: import diretto `from mata_garuda.foundations.gov_apis_health import probe_inventory`, oppure lazy exports.

2. **Retry sta coprendo errori deterministici di parsing**
   - `pasal_id_client`, `gdelt_client`, `opensanctions_id` retryano anche `KeyError`, `AttributeError`, `ValueError`, `JSONDecodeError`.
   - Un payload malformed viene scaricato/parlato 3 volte e poi può uscire come `RetryError`, nascondendo la causa reale.
   - Refs: `pasal_id_client.py:70-75`, `gdelt_client.py:32-43`, `opensanctions_id.py:32-40`.
   - Fix: retry solo per `httpx.TransportError`, timeout, 5xx/429 espliciti.

3. **`gdelt_client.py`: un articolo parziale rompe tutta la ricerca**
   - Usa `item["url"]`; se GDELT ritorna articolo senza URL, l’intera response fallisce.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/gdelt_client.py:44-53`.
   - Inoltre `query` viene interpolata raw dentro la query GDELT; operatori GDELT inseriti dall’input possono cambiare il filtro.
   - Ref: `gdelt_client.py:34-39`.

4. **`opensanctions_id.py`: ingest OOM-prone**
   - Scarica tutto in `response.text`, poi `split("\n")`; nessun limite bytes, streaming, max righe, o validazione schema.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/opensanctions_id.py:49-65`.
   - `match_name()` riscarica tutto a ogni chiamata.
   - Ref: `opensanctions_id.py:42-45`.

5. **`gov_apis_health.py`: isolation incompleta per portale**
   - Cattura solo `ConnectError` e `TimeoutException`; `TooManyRedirects`, `RemoteProtocolError`, `InvalidURL`, SSL/proxy errors, JSON inventory bad shape propagano e abortiscono tutto.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/gov_apis_health.py:53-74`, `:77-83`.

6. **Test mocks troppo happy-path**
   - Mancano test per timeout, malformed JSON, partial GDELT articles, OpenSanctions huge/invalid line, `work: null`, 429/rate limit, 5xx retry, bad inventory entry.
   - Esempi: `apps/mata-garuda/tests/foundations/test_gdelt_client.py:9-49`, `test_opensanctions_id.py:9-49`, `test_gov_apis_health.py:22-67`.

## C. Security

1. **OpenSanctions remote JSON non è bounded**
   - Non c’è auth, checksum, size cap, streaming cap, o schema validation. JSON non ha “billion laughs” XML-style, ma file enorme o nesting patologico può comunque fare OOM/CPU spike.
   - Ref: `opensanctions_id.py:49-65`.

2. **Gov probe sembra bot generico**
   - Nessun `User-Agent` custom, nessun `Accept`, nessuna classificazione 429.
   - Ref: `gov_apis_health.py:57-58`.
   - Per domini governativi conviene UA identificabile e rate policy esplicita.

3. **Bali calendar accetta input senza contratto**
   - Type hint `date`, ma nessuna runtime validation/range policy. Date storiche lontane vengono calcolate in proleptic Gregorian senza warning semantico.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/bali_calendar.py:47-80`.

4. **Pasal token non viene loggato ora, ma resta facile da esporre**
   - Il codice non stampa il token; bene.
   - Però `_headers()` costruisce `Authorization` direttamente e i test ispezionano il valore completo.
   - Ref: `pasal_id_client.py:64-68`, `apps/mata-garuda/tests/foundations/test_pasal_id_client.py:104-119`.
   - Evitare in futuro logging di call kwargs o exception context con headers.

## D. Operational Readiness

1. **Cron non è robusto al venv mancante**
   - `source "$REPO_ROOT/.venv/bin/activate" 2>/dev/null` ignora failure perché manca `set -e`; poi usa `python` dal PATH.
   - Questo viola anche la regola locale “no system Python”.
   - Ref: `infra/scripts/domain-mesh-foundations-cron.sh:1-16`.
   - Fix: usare `"$REPO_ROOT/.venv/bin/python"` e fallire se non eseguibile.

2. **Cron può lasciare snapshot corrotti**
   - Redirige direttamente nel file finale; se Python fallisce dopo apertura, resta JSON vuoto/parziale.
   - Ref: `infra/scripts/domain-mesh-foundations-cron.sh:16-32`.
   - Fix: scrivere su temp file e `mv` atomico solo a successo.

3. **Il piano promette alert, il codice ha TODO**
   - Piano: alert Telegram se operational % scende >10pp.
   - Script: solo log, TODO Phase 1.
   - Refs: `docs/superpowers/plans/2026-05-08-domain-mesh-phase0-foundations.md:1538`, `infra/scripts/domain-mesh-foundations-cron.sh:35-40`.

4. **Nessun kill-switch cron**
   - LaunchAgent schedulato, nessuna env `FOUNDATIONS_CRON_ENABLED=false`, nessun lock, nessun timeout globale.
   - Refs: `infra/launchagents/com.balizero.domain-mesh.foundations.daily.plist:7-31`, `infra/scripts/domain-mesh-foundations-cron.sh:1-40`.

5. **Inventory seed non validato**
   - `load_inventory()` fa solo `json.loads`; entry mal editata rompe runtime più avanti.
   - Ref: `gov_apis_health.py:49-55`, `apps/mata-garuda/data/gov_apis_inventory.json:1-55`.

## E. Other Flaws Before Phase 1

1. **Plan/test count drift**
   - Piano dichiara “24 tests”, ma i test foundations presenti sono circa 30.
   - Refs: `docs/superpowers/plans/2026-05-08-domain-mesh-phase0-foundations.md:1460-1467`, `:1664-1670`, `:1745-1749`.
   - È piccolo, ma segnala che la checklist non è più source-of-truth.

2. **OpenLLMetry init è silenzioso troppo spesso**
   - `ImportError` ritorna `False` senza logging; `Traceloop.init()` invece può propagare eccezioni runtime.
   - Ref: `apps/mata-garuda/mata_garuda/foundations/openllmetry_init.py:23-37`.
   - Serve comportamento coerente: o loud con log strutturato, o sempre dormant-safe con warning.

3. **Operational failure mode generale**
   - Pasal/GDELT/OpenSanctions falliscono loud ma spesso come `RetryError`.
   - Gov probe fallisce quiet per alcuni errori noti, loud per altri.
   - NER fallisce loud al primo `extract()` se HuggingFace/cache non disponibile.
   - Prima di Phase 1 serve un contratto comune: `FoundationUnavailable`, `MalformedUpstreamPayload`, `RateLimited`, `AuthMissing`.

Fonti esterne consultate: GDELT DOC 2.0 API docs confermano operatori dentro `query` e `sourcecountry` come operatore; FollowTheMoney/OpenSanctions docs confermano uso di stream JSON line-based/FtM per bulk entities.  
Links: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ · https://followthemoney.tech/docs/cli/
hook: Stop
hook: Stop
hook: Stop Completed
hook: Stop Completed
tokens used
109.353
[Pro] Review eseguita sul checkout locale. Nota operativa: Mini peer non raggiungibile e `nuz-sync` stale; test non eseguiti perché la sandbox read-only non offre temp dir scrivibile a pytest.
