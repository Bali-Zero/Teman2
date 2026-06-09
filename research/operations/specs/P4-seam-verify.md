# PEZZO 4 — SEAM-VERIFY: verifica a ogni giuntura (non solo unit-test del pezzo isolato)

> **Spec studio (non implementazione).** Ciclo calibrato: reuse-first (disk-state VERIFICATO) +
> deep-research mirata SOTA + 1 red-team forte (Gemini). Pezzo 4 di 9.
>
> **Tesi centrale**: la SEAM-VERIFY al livello backend-API è **già ~60% costruita e LIVE** (le
> cicatrici la proponevano ED È STATA SCRITTA). Il pezzo NON green-fielda: (a) colma 4 gap reali con
> tool SOTA concreti, (b) **sostituisce l'inferenza-agente-delle-giunture con un grafo
> deterministico**, (c) chiude il buco-nero API↔frontend che nessuno copre.

---

## 0. La correzione che precede tutto — il difetto P0 del design iniziale

Il design iniziale diceva: *"l'agente identifica le giunture toccate e gira solo quei seam-test"*.
Il red-team l'ha distrutto (Gemini #1, P0):

> L'agente non ha un dependency-graph formale. Se si basa su euristica post-session, **non eseguirà i
> seam-test per le giunture che non ha capito di aver rotto** — nascondendo le regressioni proprio
> dove c'è allucinazione. "Gira solo i toccati" è un'ottimizzazione che nasconde le giunture che
> l'agente non ha capito di toccare.

**La risoluzione (research SOTA)**: non far inferire all'agente quali test girare. Usare un **grafo
deterministico**:

- **`pytest-testmon`** (Test Impact Analysis via `coverage.py`): traccia quali test eseguono quali
  righe. Dopo un diff, gira **solo** i test affetti — calcolato dai dati di copertura, **non
  dall'inferenza dell'LLM**. L'agente non sceglie; il diff sceglie.
- Mini-script **tree-sitter / `ast`** su `git diff`: trova i call-site a valle delle funzioni/firme
  toccate, fornisce il contesto come prompt — ma il *gating* resta su testmon, non sul prompt.

Questo è il cardine del pezzo: **la selezione delle giunture da verificare è deterministica
(coverage-graph), non cognitiva (agente)**. Toglie il bias che invalidava il principio.

---

## 1. GROUND — reuse-first disk-state (file aperti + esistenza VERIFICATA questo turn)

Anti-hallucination: ogni file qui sotto è stato `wc -l`-verificato esistente in questo turn (la
cicatrix W-meta insegna a non fidarsi dei file:line di un report).

### Cosa ESISTE già e gira LIVE (~60% della SEAM-VERIFY)

| Mattone | Stato | File (verificato) | Cosa fa |
|---|---|---|---|
| Integration test app COMPLETA | **GIÀ-PRONTO LIVE** | `apps/backend-rag/backend/tests/integration/test_endpoints_reachable.py` (274 righe) | Monta full-app con HybridAuthMiddleware, GET ogni route, fallisce su 404. 4 classi: TestRoutesAreMounted, TestAuthContractMatchesRegistry, TestHealthEndpointsCandidateForRegistry, TestRegistryMatchesAtLeastOneRoute. |
| Manifest↔registration parity | **GIÀ-PRONTO — regressione 2026-05-02 strutturalmente impossibile** | `apps/backend-rag/backend/tests/setup/test_router_manifest.py` (211) + `apps/backend-rag/backend/app/setup/router_manifest.py` (438) | Manifest SSOT, include_routers lo legge. TestManifestIntegrity (no-dup), TestRouterFileCoverage (orphan vs phantom). CI fallisce se sporco. |
| Public-endpoints registry | **GIÀ-PRONTO** | `apps/backend-rag/backend/tests/unit/middleware/test_public_endpoints_registry.py` (183) | B1 (no undocumented public route) + B2 (no stale entry). Flagga /health che ritorna 401. |
| Pre-deploy smoke | **GIÀ-PRONTO minimale** | `scripts/post-deploy-verify.sh` (127), `apps/backend-rag/tests/test_import_time.py` (140), `apps/backend-rag/scripts/smoke_test.py` (75) | Probe /health post-deploy, import-chain SPOF (`from backend.app.dependencies import get_current_user`), app-factory boot. |

> Significato: il pattern-killer "test verdi + sistema live rotto alla giuntura router/middleware" — la
> classe di cicatrici 2026-05-02 (3 hotfix in catena, 401→404→200) — **è già stato neutralizzato**.
> Le cicatrici proponevano questi test; qualcuno (sessione passata) li ha scritti davvero.

### I 4 GAP REALI (verificati)

1. **EventBus schema-contract**: producer (trigger SQL pg_notify) + consumer (Python) è protetto da
   ACID PG + replay outbox (PR #342), MA **niente schema-validation** che "il payload che il producer
   scrive = il tipo che il consumer si aspetta" (oggi comment-only). PG_CHANNEL_MAP = 7 canali.
2. **Migration-ORM parity**: runner robusto MA niente test "migration crea colonna X = model ha field
   X stesso tipo".
3. **Pre-push gating**: `test_endpoints_reachable` gira in CI MA **non è gating pre-push** — un agente
   può mergere senza eseguirlo.
4. **Hook post-session seam-verify**: **MANCA del tutto** (confermato: zero hook seam/parity/reachable
   in `~/.claude/hooks/`).

### Il buco che nessun gap vedeva (red-team Gemini #6, P0)

**API↔frontend-TypeScript**: la giuntura più fragile. Il backend cambia la forma di una risposta JSON
→ il frontend Vercel fallisce. `test_endpoints_reachable` verifica **200-OK, non compatibilità-payload
col client TS**. Nessuno dei 4 gap né dei 3 test esistenti copre il contratto API↔client TypeScript.

---

## 2. I 6 DIFETTI DEL RED-TEAM → risoluzione SOTA (research)

| # | Difetto (Gemini) | Sev | Risoluzione SOTA (research, tool concreto) |
|---|---|---|---|
| 1 | identificazione-giunture cieca (euristica agente) | **P0** | `pytest-testmon` (TIA coverage-graph) → selezione deterministica dal diff, non dall'LLM. + tree-sitter/`ast` su `git diff` per call-site. §0 |
| 2 | contratto EventBus illusorio (trigger SQL JSON-raw non passa da pydantic) | P1 | AsyncAPI + Spectral linter. Pydantic valida lato-consumer. **MA il fix vero**: il payload del trigger SQL va generato/validato da UN punto — vedi §3.2 (test che fa round-trip trigger→consumer su DB effimero, non solo modello opt-in). |
| 3 | no ORM-source-of-truth (asyncpg query-raw, no SQLAlchemy) | P1 | **`sqlc` + `sqlc-gen-python`**: schema-first. Migrations restano SQL raw, sqlc genera tipi Python dal DDL. Schema cambia + query rotta → **build fallisce** (mypy/pyright). NON impone SQLAlchemy. §3.3 |
| 4 | feedback-loop locale collassa (gating 30-60s × 50 iter) | P2 | testmon rende il gate **incrementale** (solo test affetti = secondi non minuti). Gating su testmon-subset pre-push, full-suite solo in CI. §3.1 |
| 5 | denominatore-giunture inconoscibile (cron impliciti) | P1 | **residuo onesto** (§5): la metrica copre le giunture DICHIARATE. Mitigazione: registro esplicito delle giunture-implicite (cron↔tabella) + testmon che, tracciando la copertura reale, SCOPRE accoppiamenti non dichiarati. Non azzera il problema. |
| 6 | buco-nero API↔frontend-TS | **P0** | **`openapi-typescript`** (genera tipi TS da `/openapi.json` FastAPI a build-time) + **Schemathesis** (property-fuzz dell'OpenAPI lato backend). Chiude la giuntura. §3.4 |

**Convergenza research↔red-team**: la research conferma che i 6 difetti sono reali E fornisce il tool
SOTA per ciascuno. Nessun difetto resta senza risposta tranne #5 (strutturalmente parziale → residuo).

---

## 3. DESIGN (estendere l'esistente + colmare i gap con tool SOTA)

### 3.0 SEAM-VERIFY come FASE del loop — ma deterministica

Dopo ogni pezzo costruito dall'agente:

```
1. git diff → testmon calcola i test affetti (coverage-graph, NON inferenza agente)
2. tree-sitter/ast scansiona il diff → call-site a valle delle firme toccate → contesto
3. gira il testmon-subset (seam-test delle giunture realmente affette) — secondi, non minuti
4. se il diff tocca un contratto (openapi/asyncapi/sqlc-query) → gira anche il contract-test relativo
5. gate: testmon-subset verde + contract-test verde → l'agente può dichiarare "fatto"
```

Il punto: **l'agente non sceglie cosa verificare**. Il coverage-graph + i contract-test lo impongono.

### 3.1 Pre-push gating incrementale (colma gap 3, risolve difetto 4)

- Pre-push (locale, veloce): `pytest --testmon` sul subset affetto dal diff → secondi. Più
  `test_router_manifest` (è statico, ~ms, sempre).
- CI (completo, lento OK): full `test_endpoints_reachable` + full suite.
- Quick-win: il gating-subset è il "Tier-1 deployabile in 1 giorno" — riusa i 3 test esistenti, ci
  mette davanti testmon.
- **No `--no-verify`**: l'hook (§3.5) rende il bypass visibile (logga lo skip), coerente con
  `stop_verify.py` esistente.

### 3.2 EventBus contract reale (colma gap 1, risolve difetto 2)

Il modello pydantic condiviso da solo è opt-in lato-Python (Gemini ha ragione). Il fix reale:

- 1 modello pydantic per ogni PG_CHANNEL_MAP entry (7 canali), in un modulo condiviso.
- Il **producer Python** (dove esiste, es. `lkpm_ingest_completed`) lo usa per serializzare.
- Per i **trigger SQL** (che scrivono JSON raw): un **round-trip test su DB effimero** (il sandbox di
  P3!) — inserisce una riga che fa scattare il trigger, cattura il pg_notify reale, valida il payload
  catturato contro il modello pydantic. Se il trigger SQL e il modello divergono → test rosso. Questo
  verifica la giuntura *polyglot* SQL→Python che il modello-solo non cattura.
- Spectral linta le definizioni AsyncAPI (correttezza formale).

### 3.3 Migration-ORM parity via sqlc (colma gap 2, risolve difetto 3)

- **NON** imporre SQLAlchemy models (sarebbe doppio-mantenimento, Gemini #3).
- Adottare `sqlc` + `sqlc-gen-python`: migrations SQL raw (gestite com'è), query SQL annotate per
  sqlc, generazione tipi Python dal DDL. Schema cambia + query non aggiornata → `mypy`/`pyright`
  fallisce sul codice generato → blocca l'agente pre-commit.
- **Adozione incrementale**: non riscrivere tutte le query asyncpg. Iniziare dai path critici
  (CRM, billing) dove il disallineamento schema-codice fa più male. Le altre restano raw fino a
  migrazione opportunistica.

### 3.4 API↔frontend contract (colma il buco-nero, risolve difetto 6 P0)

- **`openapi-typescript`**: genera `apps/mouth/src/types/api.ts` da `/openapi.json` di FastAPI a
  build-time. Il frontend importa quei tipi → un cambio di forma del payload backend rompe il
  `tsc --noEmit` (già nel pre-commit hook!) invece di rompere a runtime in produzione.
- **Schemathesis**: `schemathesis run http://localhost:8000/openapi.json` in pytest → property-fuzz
  che trova 500/discrepanze schema senza test manuali.
- Gating: la rigenerazione dei tipi TS è parte del CI; se il backend cambia l'OpenAPI e i tipi TS non
  sono rigenerati → diff non committato → CI fallisce.

### 3.5 Hook post-session seam-verify (colma gap 4)

- Hook `~/.claude/hooks/seam_verify.py`: a fine-sessione (o pre-commit), legge `git diff --name-only`,
  mappa i file modificati → giunture note (tabella §4), e **suggerisce/esegue** i seam-test rilevanti
  via testmon. Coerente con l'architettura hook esistente (stop_verify, dispatch_nudge).
- Non blocca su giunture non-mappate (non può), ma logga "file X modificato, nessuna giuntura
  dichiarata — verifica manuale?" per le giunture implicite (mitigazione parziale difetto 5).

---

## 4. MAPPA DELLE GIUNTURE — tipo → seam-test → stato

| Giuntura | Seam-test che la copre | Stato |
|---|---|---|
| router↔registration (manifest) | test_router_manifest.py | **LIVE** |
| route↔middleware-auth (PUBLIC_ENDPOINTS) | test_public_endpoints_registry.py | **LIVE** |
| route↔mounting (404) | test_endpoints_reachable.py | **LIVE** (non gating pre-push → §3.1) |
| import-chain SPOF (dependencies.py) | test_import_time.py | **LIVE** |
| EventBus producer↔consumer (payload) | round-trip test su DB effimero + pydantic | **DA COSTRUIRE** (§3.2) |
| migration↔query-asyncpg (schema) | sqlc gen + mypy | **DA COSTRUIRE** (§3.3) |
| API↔frontend-TS (payload) | openapi-typescript + Schemathesis | **DA COSTRUIRE** (§3.4, P0) |
| cron↔tabella (accoppiamento implicito) | — | **RESIDUO** (§5, non enumerabile a priori) |

---

## 5. RESIDUI ONESTI

1. **Denominatore inconoscibile (Gemini #5, P1)**: la metrica "# giunture coperte / # note" copre solo
   le giunture *dichiarate*. Le giunture *implicite* (un cron che legge una tabella che un altro cron
   scrive, mai dichiarato come contratto) restano scoperte — e sono la causa principale dei crash
   prod. **Mitigazione, non soluzione**: (a) registro esplicito delle giunture-implicite note; (b)
   testmon, tracciando la copertura reale, può SCOPRIRE che un test tocca codice di un'altra "area" →
   segnala un accoppiamento non dichiarato. Non azzera il problema. **Onestà: 100% della metrica ≠
   sistema sicuro alle giunture**, solo alle giunture mappate.
2. **sqlc adozione parziale**: finché non tutte le query asyncpg passano da sqlc, la parity copre solo
   i path migrati. Le query raw rimanenti restano non-verificate contro lo schema.
3. **EventBus trigger-SQL**: il round-trip test cattura la divergenza solo per i canali testati; un
   canale nuovo aggiunto senza il suo round-trip test resta scoperto (mitigabile con un meta-test che
   verifica che ogni PG_CHANNEL_MAP entry abbia il suo round-trip test — parità di copertura).

---

## 6. GATE FALSIFICABILI (Symbiosis Law 7)

- **G1 — testmon determinismo** (binario): introdurre una regressione-giuntura nota (es. cambiare la
  firma di una funzione consumata altrove) DEVE far girare e fallire il seam-test relativo via
  `pytest --testmon`, SENZA che l'agente lo selezioni a mano. Falsificabile: il test rosso compare nel
  subset testmon.
- **G2 — frontend contract** (binario): cambiare la forma di un payload backend (campo rinominato)
  DEVE rompere `tsc --noEmit` su `apps/mouth` (via tipi rigenerati da openapi-typescript), NON arrivare
  a runtime. Falsificabile: build TS rossa.
- **G3 — migration parity** (binario): rimuovere una colonna in una migration mentre una query sqlc la
  usa DEVE far fallire `mypy`/`pyright` sul codice generato. Falsificabile: type-check rosso.
- **G4 — EventBus round-trip** (binario): modificare un trigger SQL perché emetta un payload divergente
  dal modello pydantic DEVE far fallire il round-trip test su DB effimero. Falsificabile: test rosso.
- **G5 — copertura giunture** (numerico, con caveat §5): # giunture DICHIARATE coperte / # giunture
  DICHIARATE note = target 100% delle *note*, con il disclaimer esplicito che il denominatore esclude
  le implicite. Metrica di igiene, non di sicurezza assoluta.

---

## 7. DECISIONE (kill gate)

**GO**. Il pezzo è prevalentemente *estensione + adozione di tool SOTA*, non green-field — il 60% è
già LIVE. Priorità di implementazione (per leva):

1. **Frontend contract** (P0, openapi-typescript + Schemathesis) — chiude il buco-nero, riusa il
   `tsc` già nel pre-commit. Massima leva.
2. **Pre-push gating incrementale** (testmon) — risolve il difetto-cardine (selezione deterministica) +
   il feedback-loop. Quick-win, riusa i 3 test esistenti.
3. **EventBus round-trip** (DB effimero = P3) — colma la giuntura polyglot.
4. **sqlc parity** (incrementale, path critici prima).

**Metrica primaria falsificabile**: G1 (testmon fa fallire il seam-test SENZA selezione-agente) +
G2 (cambio-payload rompe il build TS, non il runtime). Se G1 non passa, la SEAM-VERIFY resta cognitiva
(bias agente) e il difetto P0 #1 non è chiuso.

**Dipendenza scoperta**: il round-trip test EventBus (§3.2) USA il DB effimero di **P3** (il sandbox).
Conferma il valore di P3 come substrato anche per la verifica-alle-giunture, non solo per la sicurezza.

---

## 8. Provenienza

- **Reuse-first**: Explore agent disk-state, 7 mattoni. 3 LIVE verificati `wc -l` (test_endpoints_
  reachable 274, test_router_manifest 211, test_public_endpoints_registry 183), 4 gap reali, 1 buco-
  nero. Memory importance-8.
- **Deep-research mirata** (Gemini 3.1 Pro, grounding-search, ≥3 fonti per punto): contract-testing
  SOTA (Schemathesis, Pact, openapi-typescript, Spectral, AsyncAPI), blast-radius (pytest-testmon TIA,
  tree-sitter/ast), migration-parity (sqlc + sqlc-gen-python). 13 fonti citate.
- **Red-team**: **Gemini 3.1 Pro** (`agy`) — 6 difetti, 2 P0 (giunture-cieche, frontend). Premiato per
  distruggere. Pezzo calibrato (1 red-team forte + research-come-constructive, non full-council —
  decisione "calibrato per pezzo": metodologico/deducibile dai fatti groundati, rollback facile).
- **Famiglia**: P3 (DB effimero usato dal round-trip EventBus). Il principio anti-allucinazione del
  ciclo (testmon deterministico vs inferenza-agente) è lo stesso che governa la verifica-output di P1.

> **Onestà finale**: la SEAM-VERIFY non rende il sistema "senza giunture rotte". Sposta la verifica da
> *cognitiva* (l'agente indovina cosa ha toccato — bias, allucinazione) a *deterministica* (il
> coverage-graph + i contract-test impongono cosa verificare). Le giunture *implicite* non dichiarate
> restano un residuo (§5). Il salto è: dal pattern-killer "verde-ma-rotto-alla-giuntura" che è costato
> 3-hotfix-in-catena, a "la giuntura toccata si verifica da sola o blocca il commit".
