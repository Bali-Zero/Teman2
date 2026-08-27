# HANDOFF — Visa Oracle retention scope P0 (aperto 2026-08-27 ~04:00 WITA, Pro)

Consegna della sessione `nuzantara-46`. Tutto pushato, worktree pulito, niente in volo.

> ⚠️ **AGGIORNATO 2026-08-27 (sessione successiva) — tre affermazioni di questo file sono cadute.**
> Zero ha autorizzato l'apply (verbatim: _«e puoi cominciare la migrazione»_), **la 289 è stata
> applicata in produzione** come `flypgadmin` e verificata sul catalogo vivo, e il divieto di
> mergiare #5059 da solo è quindi **decaduto**. Le sezioni interessate portano una nota in linea.
> Il resto del file — protocollo di sweep, trappole già pagate, difetto del runner — resta valido.

## Dove sta la roba

- Macchina: **Pro** (`nuzantara@Nuzantara`)
- Worktree: `/Users/nuzantara/nuzantara/.worktrees/db-visa-retention-scope-p0`
- Branch: `agent/nuzantara/db/visa-retention-scope-p0` — HEAD `fa96f2e03`, allineato con `origin`
- PR aperte, **zero check rossi** su tutte e tre (erano solo in coda: la CI stava smaltendo il blackout Actions del 26/8):
  - **#5059** — la cura P0 (questo branch)
  - **#5062** — `agent/nuzantara/backend-rag/preflight-superuser-falsepositive`
  - **#5067** — `agent/nuzantara/mouth/oracle-honest-shadow-copy`

## Cosa è stato curato

Le migrazioni 264/268 crearono due trigger `BEFORE INSERT` `SECURITY DEFINER` che risolvono la
retention policy con `SELECT ... INTO STRICT ... WHERE environment = NEW.environment AND
effective_period @> ...`. La **281** ha aggiunto `policy_scope` e allargato il vincolo di esclusione a
`(environment, policy_scope)`: da allora più policy attive possono coesistere per lo stesso
environment in scope diversi. **Quattro lettori non sono stati aggiornati.** In produzione ci sono 4
policy PRODUCTION attive (1 `VISA_DECISION` + 3 GARUDA), quindi `active_policy_available` rifiuta e
ogni INSERT romperebbe con `TOO_MANY_ROWS`.

La **289** aggiunge `AND policy_scope = 'VISA_DECISION'` a entrambi i binder; `retention.py` e
`retention_worker.py` ricevono lo stesso predicato.

## Il difetto trovato DENTRO la cura (leggi questo prima di toccare la 289)

`migration_manager.py:96` apre la connessione con `settings.database_url` — **lo stesso DSN del
runtime**, e in tutta la catena non c'è nessun `SET ROLE`. Il `release_command` di Fly gira quindi come
**`backend_rag_v2`**, che _non_ possiede i due binder (sono di `visa_ledger_owner`), non è membro di
quel ruolo e non è superuser. Misurato in produzione il 2026-08-27.

Un `CREATE OR REPLACE FUNCTION` nudo lì dentro **non fallisce soltanto: aborte il DEPLOY**, portandosi
via ogni modifica non correlata sulla stessa immagine. È successo davvero il **2026-08-26** alle cinque
migrazioni GARUDA. E **la CI non può vederlo**: `fly-deploy.yml` valida su un Postgres effimero dove il
ruolo che si connette possiede tutto ciò che ha creato.

Quindi la 289 ora avvolge ogni sostituzione in una guardia di catalogo che **declina** invece di
sollevare. Siccome una migrazione che declina viene comunque registrata `APPLIED` e mai ritentata
(cicatrice #2), il no-op è reso rumoroso **fuori** dalla migrazione dal check
`binder:retention-policy-scoped` in `operational_preflight.py`, che legge il corpo **vivo** da
`pg_proc`: non si soddisfa mergiando la PR, solo con la 289 realmente eseguita.

## ✅ LA DECISIONE CHE ASPETTAVA ZERO — ARRIVATA E ESEGUITA (2026-08-27)

> **Zero ha autorizzato** (_«e puoi cominciare la migrazione»_). La 289 è stata applicata a mano in
> produzione come `flypgadmin` e **verificata sul catalogo vivo**: entrambi i binder risolvono ora
> 1:1 (una sola lookup `effective_period @>`, un predicato `policy_scope` ciascuno), con owner,
> `SECURITY DEFINER` e `search_path` preservati. Chiuso anche il buco che il subagente non poteva
> chiudere: nessuna delle 4 funzioni di purge legge `visa_decision_retention_policies` — cancellano
> per marcatura di riga, quindi non esiste rischio di cancellazione cross-scope in nessuno stato.
> Il testo qui sotto è conservato come **storia del vincolo**, non come istruzione viva.

**Anche dopo il merge, la 289 declinerà in produzione.** Per farla mordere serve un apply da
`flypgadmin` / `postgres` / `repmgr` — cioè una **scrittura diretta sul DB di produzione**, che è
categoria `operator[secret]`. Zero non ha ancora dato il via libera. **Non farlo senza il suo sì
esplicito.** Finché non arriva, il preflight lo dichiara a voce alta invece di lasciarlo muto, che è
esattamente il punto del disegno.

## Prove che esistono (rieseguile, non fidarti di questo file)

```bash
cd /Users/nuzantara/nuzantara/.worktrees/db-visa-retention-scope-p0/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m pytest \
  backend/tests/scripts/visa_engine/test_operational_preflight.py \
  backend/tests/scripts/visa_engine/test_retention_binder_scope_survives_a_non_owner_runner.py \
  backend/tests/scripts/visa_engine/test_retention_binders_scope_to_visa_decision.py \
  backend/tests/test_retention_policy_scope_family_tripwire.py \
  backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py \
  -o addopts= -p no:randomly
# atteso: 99 passed
```

`-o addopts=` è **obbligatorio**: senza, `-q` diventa `-qq` e la riga `N passed` sparisce.

## ✅ SEQUENZA VINCOLATA — VINCOLO SCIOLTO (2026-08-27)

> **Il divieto è decaduto perché la sua premessa è caduta**: l'apply è stato autorizzato ed
> eseguito **prima** del merge, quindi i due binder in produzione sono già scoped. La metà Python
> non arriva più su un trigger cieco — arriva su un trigger curato, che è esattamente l'ordine che
> questa sezione chiedeva. Il ragionamento sotto resta la spiegazione di **perché** l'ordine
> contava, e va riletto tale e quale se un domani si ripete la sequenza su un altro binder.

**Non mergiare #5059 finché Zero non autorizza l'apply superuser della 289. Merge e apply stanno
nella STESSA finestra.**

Perché, in tre fatti misurati:

1. `.github/workflows/fly-deploy.yml` parte **da solo** sul push a `main` che tocca
   `apps/backend-rag/**`. Nessun passaggio umano tra il merge e la produzione.
2. Il `release_command` applica la 289, che **declina** (il runner non possiede i binder) — ma la
   metà Python della cura (`retention.py`, `retention_worker.py`) **viene rilasciata comunque**.
3. Con la metà Python sola, `active_policy_available` torna True, il gate si **apre**, e la scrittura
   raggiunge un trigger ancora cieco allo scope. Il test già in repo lo prova:
   `test_decision_insert_fails_ambiguous_before_289_when_garuda_check_also_active` — `TOO_MANY_ROWS`.

Oggi l'oracolo si ferma con garbo **prima** di scrivere. Dopo quel merge fallirebbe **durante**.
_(Non verificato: se l'API lo assorba fail-closed o esca 500. In nessuno dei due casi è un
miglioramento — non trattarlo come "tanto è già rotto".)_

## 🔴 CANARY PRIMA DI ENFORCE (RULED Zero, 2026-08-27)

Zero ha scelto: **si costruisce prima la leva di rollout, poi si prova ENFORCE.**

Stato misurato oggi: `resolve_evaluate_mode()` (`evaluate_path.py:212`) legge **solo** l'env
`VISA_ENGINE_EVALUATE_MODE`, globalmente. **Non esiste** canary, percentuale, cookie o header
per-richiesta. Togliere SHADOW oggi porta i visitatori reali da 0% a 100% in un colpo — che contraddice
il ruling ASSEMBLY-LINE dello stesso Zero (dark → 5% → 100%).

E in ENFORCE `run_evaluation` **fail-close**: se la scrittura della decisione fallisce risponde
`TEMPORARILY_UNAVAILABLE` in modalità ENGINE. Col retention gate rotto, ENFORCE oggi mostrerebbe a
ogni visitatore una pagina di guasto, non l'oracolo.

**Cosa costruire**: un override per-richiesta di `EngineMode`, default OFF, che non cambi nulla per
chi non lo porta. La forma la decide chi implementa, ma tre vincoli non negoziabili:

- default assente ⇒ comportamento **identico** a oggi (nessun visitatore tocca ENFORCE per sbaglio);
- non deve poter essere attivato da un parametro pubblico indovinabile;
- deve essere visibile nel record della decisione, così una riga nata in canary non si confonde con
  una nata in produzione vera.

**Aspettativa da tarare**: anche col canary, finché la 289 non è applicata la risposta ENFORCE sarà
`TEMPORARILY_UNAVAILABLE` — il gate è uno stato del DB, non una proprietà della richiesta. Il canary
permette comunque di provare live **tutto il resto** del percorso ENFORCE (routing, contratto ENGINE,
rendering, gestione del guasto). La decisione vera resta dietro l'apply.

⚠️ **L'oracolo chiede oggi 3 fatti su 45**: due richiedenti diversi ricevono una risposta
**byte-identica**. In SHADOW non lo vede nessuno. In ENFORCE diventa il consiglio su cui una persona
decide il proprio visto. Detto a Zero il 2026-08-27; è una sua chiamata (Legge 5), non da riaprire in
autonomia — ma nemmeno da dimenticare quando si proporrà il 100%.

## 🔴 PROVA VIVA SUL SITO — protocollo obbligatorio (RULED Zero, 2026-08-27)

Verbatim: _«e importante che ora faccia test live sul website direttamente e ad ogni tornata prende
tutti gli errori (non uno alla volta!) e si fixano e si riprova»_.

Questo **sostituisce** il modo di lavorare a rilievo-singolo. Un giro = uno **SWEEP COMPLETO**, poi un
**BATCH DI CURE**, poi **RI-SWEEP**. Mai curare a metà sweep.

**Fase A — SWEEP (nessuna modifica al codice, per nessun motivo).**
Passa OGNI superficie viva e registra OGNI errore in una lista prima di toccare qualsiasi cosa. Se
durante lo sweep ti viene voglia di aggiustare qualcosa: **annotalo e vai avanti**. Curare a metà
sweep è precisamente ciò che Zero ha vietato — nasconde gli errori a valle di quello che hai appena
cambiato, e il giro dopo li ritrovi.

Per ogni superficie raccogli tutti e quattro i canali, non solo quello che salta all'occhio:

1. **HTTP** — status, `retry-after`, corpo dell'errore
2. **Console del browser** — `console.error` e `console.warn`, non solo le eccezioni
3. **Rete** — richieste 4xx/5xx, CORS, CSP, risorse che non caricano
4. **Visivo** — testo rotto, placeholder, colori/logo, layout (screenshot **solo dopo** il testo)

Browser: `mcp__claude-in-chrome__*` — **mai** `mcp__playwright__*` se non ordinato. Text-first:
`get_page_text` / `find` / `javascript_tool` prima di ogni screenshot.

**Non partire da una lista di URL scritta a memoria**: enumerale dal repo (routes di `apps/mouth`,
`fly.toml`, i domini in CLAUDE.md §11) e scrivi in chiaro quali hai coperto e quali no. Due esempi
verificati in questa sessione, come punto di partenza non come elenco completo:

```bash
# API viva (misurata 2026-08-26: HTTP 200 + state TEMPORARILY_UNAVAILABLE)
curl -sS -X POST 'https://balizero.com/api/visa-oracle/evaluate?traffic_source=real' \
  -H 'content-type: application/json' -d '{...}' -w '\n[%{http_code}]\n'
```

Pagina funnel `/visa-oracle` (è `noindex,nofollow`) e il funnel più vecchio `/visa` — **sono due cose
diverse**, provale entrambe.

**Fase B — TRIAGE del lotto.** Con la lista chiusa, raggruppa per CAUSA, non per sintomo: dieci
console-error possono essere un solo difetto. Ordina per raggio d'azione (blocca il cliente > sporca i
dati > cosmetico). Dichiara quanti errori distinti hai, non quanti messaggi.

**Fase C — CURA IN BATCH.** Cura tutto il lotto, poi rideploya. Frontend `apps/mouth` → Vercel
auto-deploy sul push a `main`. Backend → `fly deploy` **dalla root del monorepo**, mai da
`apps/backend-rag` (i `COPY` del Dockerfile sono relativi alla root; il wrapper `fly` locale sbaglia
cwd — bypassalo con `ssh pro`).

**Fase D — RI-SWEEP DA ZERO.** Non ri-provare "solo quello che hai toccato": rifai la Fase A intera.
Una cura ne rompe un'altra, ed è l'unico modo per accorgersene. Ripeti finché lo sweep è pulito.

⚠️ **Aspettativa da tarare prima di gridare al bug**: la produzione gira in **SHADOW**. Il backend
risponde `CURATED` e il frontend solleva `NON_ENGINE_MODE` **di proposito** — quello NON è un errore da
curare, è lo stato voluto finché ENFORCE non viene armato (che dipende dalla decisione qui sotto). Ciò
che invece è da curare: tutto il resto del funnel, la copy, la rete, la console, il visivo — e ogni
punto in cui il sito **mente** al visitatore su cosa è successo (è esattamente il caso di #5067).

## Cosa NON è stato fatto, e perché

1. **Verdetto Gear-3 mai ottenuto.** Tre grader subagente sono andati idle senza consegnare
   (`gear3-grader-5059`, `-b`, `-c`). Un refuter cross-family (`codex -m gpt-5.6-sol`, stdout catturato
   direttamente) ha invece consegnato: `REFUTER: 4 — 1, 2, 3, 4`. Due erano buchi reali nella sonda e
   sono stati curati (`762cd080f`); due sono documentati come limiti noti nell'intestazione della 289.
   **Manca ancora il verdetto formale da pubblicare** via
   `scripts/harness_fable_gate.py --verdict <V> --sha <SHA>`.
2. **Merge non fatto.** Le migrazioni sono classe auto-merge-OFF: le mergia la sessione a mano dopo i
   suoi gate, mai il codeowner.
3. **PROVE-LIVE non fatta** — dipende dal punto 1 della sezione precedente.
4. **#5067 attende la parola di Zero sulla copy** rivolta al cliente (Legge 5).

## Trappole già pagate (non ripagarle)

- I test d'integrazione **bypassano `BaseMigration.apply()`**: eseguono l'SQL via asyncpg. Il vero
  cancello del runner (`_validate_sql`) è stato verificato a parte e passa, ma non è coperto da loro.
- Il corpo dentro `EXECUTE` è SQL dinamico: sul ramo che declina **un errore di sintassi è invisibile**.
  Regge solo perché CI e il test di innocenza esercitano il ramo abilitato. Se copi la forma, porta
  quel test.
- Rollback da ruolo non proprietario: la guardia declina, ma `migration_manager.py:250-260` cancella
  comunque la riga di `_schema_versions`. Il DB resta corretto, **mente il registro**. Leggi il corpo
  della funzione, mai il registro.
- Sul Postgres locale ci sono ~21 database `nuzantara_test_*` di **altre lane** (`m282`, worker xdist,
  `probe_intake_iso`). **Non cancellarli** — cicatrice #5. Le fixture di questa lane puliscono da sole.
