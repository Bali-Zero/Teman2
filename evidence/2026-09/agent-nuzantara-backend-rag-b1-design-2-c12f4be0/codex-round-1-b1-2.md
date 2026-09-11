---
title: "B1.2 adversarial round 1 — Codex gpt-5.6-sol (effort high, read-only)"
reviewed_sha: 4963e47f917af712a6eb1ad1204ba0356765ab32
started: 2026-09-11T17:31:29Z
ended: 2026-09-11T17:39:23Z
---

VERDICT: BLOCK

1. `apps/backend-rag/backend/tests/fixtures/pipeline_score_fixtures.py:3` — BLOCKER  
   Evidenza: il registro dichiara che “every value” è misurato, ma la build spec ammette esplicitamente che sono stati misurati soltanto i coseni e nessun rank (`B1-2-build-spec.md:10-15`). Ciononostante vengono assegnati `dense_rank0=0/1`, collection e server (`pipeline_score_fixtures.py:58-60,79,235-265`). La riga 9 associa inoltre arbitrariamente al singolo source il massimo di due coseni di context (`:295-319`). L’inventory aveva già stabilito che la misura `(query, context)` non può esprimere rank, membership o fusion (`B1-2-inventory.md:95-109`). Dichiarare `dense_formatted` rende corretta la trasformazione, ma non trasforma questi dati in risultati realmente recuperati da quella collection: nasconde rank e associazione source→chunk inventati, contro D3.  
   Fix minimo: marcare rank, collection/server osservati e associazione della riga 9 come `None`/`unresolved`, distinguendo cosine misurato da configurazione simulata; oppure sostituirli con una vera ricevuta dense-retrieval che identifichi chunk e rank restituiti. Non chiamare “measured” i campi derivati o assunti.

2. `apps/backend-rag/backend/tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py:109` — BLOCKER  
   Evidenza: G4 richiede soltanto che esista da qualche parte una chiamata corretta a `pipeline_sources` e cerca score non etichettati esclusivamente negli `ast.Dict` (`:129-161,253-273`). Una mutazione concreta che passa G1–G5 è:

   ```python
   sources = pipeline_sources(node_id)
   sources[0].pop("score_kind")
   ```

   La chiamata soddisfa G4, non appare alcun nuovo dict literal, G1/G2 interrogano una copia fresca del registro e G5 lascia l’assert invariato. Anche il tripwire continua a passare perché lo scorer legge soltanto `score`, ignorando `score_kind` (`services/rag/agentic/reasoning_utils.py:610-665`). Il guard quindi non rispetta l’accettazione che impone rosso per qualsiasi source score non etichettato.  
   Fix minimo: confrontare l’intero AST normalizzato originale/variante, consentendo esclusivamente la sostituzione del sources literal con la chiamata esatta, oppure intercettare a runtime gli argomenti realmente ricevuti dallo scorer e validare lì ogni source.

3. `apps/backend-rag/backend/tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py:90` — BLOCKER  
   Evidenza: `_find_function` restituisce la prima definizione AST, mentre Python conserva l’ultima definizione omonima nella classe. Aggiungendo dopo la variante valida:

   ```python
   def test_no_keyword_overlap_pipeline_variant(self):
       assert True
   ```

   pytest esegue la variante indebolita, ma G4 e G5 continuano a esaminare la prima definizione valida (`:258-268,287-302`). Inoltre G5 confronta originale e variante correnti: indebolirli entrambi nello stesso modo passa ugualmente. D5 non è quindi protetto.  
   Fix minimo: fallire se una classe contiene più di una definizione per uno dei nomi protetti, verificare il binding runtime effettivo e pinning degli assert originali contro snapshot/hash indipendenti dalla copia corrente.

4. `apps/backend-rag/backend/tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py:170` — MAJOR  
   Evidenza: G1 controlla soltanto `score`, `score_raw` e `score_kind`; G2 usa cosine, collection e kind, ma confronta soltanto quei tre valori trasformati (`:194-222`). Una modifica come `dense_rank0=999`, `rounding_digits=2`, `lists=("bm25",)` o una variazione di provider, measurement reference, fallback, fusion, boosts o carried keys passa G1–G5. Il guard quindi non “pinna” la tabella D3 che sostiene di proteggere.  
   Fix minimo: aggiungere una tabella attesa indipendente e confrontare esplicitamente ogni campo, inclusi ordine e carried keys; usare `rounding_digits` nel calcolo verificato.

5. `apps/backend-rag/backend/tests/fixtures/pipeline_score_fixtures.py:25` — MAJOR  
   Evidenza: `@dataclass(frozen=True)` è solo superficialmente immutabile. `PIPELINE_TRIPWIRE_FIXTURES` è un normale dict (`:64`) e ogni `carried_keys` è un dict mutabile (`:87,243,265,291,318`). Un caller può eseguire `PIPELINE_TRIPWIRE_FIXTURES.clear()` oppure mutare `spec.carried_keys`, contaminando test successivi; `Final[Mapping]` non impone alcun vincolo runtime. La copia fresca prodotta da `pipeline_sources` (`:325-350`) non protegge il registro esportato.  
   Fix minimo: esporre `MappingProxyType` per registro e carried keys, oppure usare una rappresentazione profondamente immutabile, con test espliciti che le mutazioni falliscano.

Controlli senza rilievi: il diff fornito è additions-only, non modifica i nove originali né file di produzione/percorsi vietati; gli assert aggiunti corrispondono agli originali. La trasformazione reale è `1/(1+(1-cosine))` con rounding a quattro cifre (`result_formatter.py:90-96,143`), e tutti i valori numerici registrati — 0.5435, 0.5102, 0.5376, 0.5435, 0.5882, 0.5556, 0.6061, 0.6711, 0.5618 e 0.6250 — risultano corretti.
