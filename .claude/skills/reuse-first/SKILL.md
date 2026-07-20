---
name: reuse-first
description: Use BEFORE implementing/building/writing-from-scratch any non-trivial component (queue, OCR, adapter, entity-resolution, review-UI, scraper, parser, etc.). Codifies "search for working code others already wrote before writing your own — adapt, don't reinvent". TRIGGER on every "implementa / costruisci / scrivi da zero / build / let's add X" where X is a buildable component, not a one-liner. Born from a real session where searching GitHub revealed ~70% of a document-intake system was already written by others (text-extract-api, paperless-gpt, pgqueuer, splink, instructor).
allowed-tools: Read, Edit, Write, Bash, WebSearch, WebFetch
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# Reuse-First — codice prima di scrivere

**Principio**: prima di implementare X, cerca chi ha già fatto X. Adatta, non reinventare.

La domanda d'apertura non è _"come lo scrivo?"_ ma _"chi l'ha già scritto, e quanto ne posso prendere?"_.
Quasi sempre la risposta è: più di quanto pensi. Settimane di lavoro evaporano quando scopri che il
70% del sistema esiste già, testato, in repo di altri.

**Tradeoff dichiarato**: questa skill costa 10-30 min di ricerca up-front. Per task triviali (un
helper di 10 righe, un rename, un fix con causa nota) → salta, usa giudizio. È per i componenti
_buildabili_: roba che altrimenti ti porteresti via giorni.

---

## La procedura (7 passi)

### 1. Scomponi in mattoni

Prima di cercare, decomponi la cosa da costruire nei suoi componenti atomici. Non cerchi
"document-intake system" (troppo vago) — cerchi i mattoni: `queue`, `OCR adapter`, `entity
resolution`, `review UI`, `structured extraction`. Ogni mattone è una query di ricerca distinta.

### 2. Doppia ricerca per ogni mattone

Per OGNI mattone, due ricerche indipendenti:

- **(a) Dentro il repo nostro** — riuso interno. `grep`/`rg` per funzioni/classi/pattern che già
  risolvono il mattone. Spesso un collega-sessione l'ha già scritto. Costo zero, licenza nostra.
- **(b) Repo di ALTRI su GitHub** — riuso esterno. Due sotto-categorie:
  - _repo-applicazione_ che risolvono lo stesso problema end-to-end (es. `paperless-gpt`, `text-extract-api`)
  - _librerie_ per il singolo mattone (es. `pgqueuer` per la coda, `splink` per entity-resolution, `instructor` per structured output)
  - Strumenti: `WebSearch "<mattone> site:github.com"`, poi `WebFetch` su README / struttura repo / file chiave per capire cosa fa davvero e come.

### 3. Classifica ogni trovato

Per ogni candidato, assegna UNA etichetta:

| Etichetta                     | Quando                                           | Azione                                              |
| ----------------------------- | ------------------------------------------------ | --------------------------------------------------- |
| **[COPIA-DIRETTO]**           | file/funzione self-contained, licenza permissiva | vendora con attribuzione                            |
| **[FORKA-E-ADATTA]**          | repo-app vicino al bisogno, licenza permissiva   | forka, taglia il superfluo, adatta ai vincoli       |
| **[STUDIA-PATTERN-RISCRIVI]** | il codice è GPL/AGPL ma il _pattern_ è buono     | leggi, capisci, **ri-scrivi da zero** — MAI copiare |
| **[INSTALLA-LIB]**            | libreria matura risolve il mattone               | aggiungi a dependencies, non scrivere niente        |
| **[SCRIVI-NUOVO]**            | nient'altro regge — ultima scelta, non la prima  | scrivi, ma documenta _perché_ niente andava bene    |

### 4. GATE LICENZE (load-bearing — non saltabile)

Prima di copiare **una sola riga** nel repo, verifica la licenza:

- **MIT / Apache-2.0 / BSD** → vendorabile nel repo CON attribuzione (header + NOTICE).
- **GPL / AGPL / LGPL-strong** → **SOLO leggere il pattern e ri-scrivere**. Copiarne anche un frammento
  nel nostro repo lo **contamina** (copyleft = obbligo di rilasciare tutto con quella licenza). → `[STUDIA-PATTERN-RISCRIVI]`.
- **Nessuna LICENSE** (repo senza file licenza) → default = "all rights reserved" → **non copiabile**.
  Si può solo leggere per ispirazione, non importare.
- In dubbio → tratta come non-copiabile finché non hai verificato. Verifica SEMPRE, mai presumere "tanto è open".

### 5. Valuta maturità

Un repo trovato ≠ un repo da usare. Controlla:

- **Stelle** + **ultima commit** (abbandonato >12-18 mesi = diffida) + **issue/PR aperte** (segnale di bug noti irrisolti).
- **Demo vs produzione**: tanti repo sono prove-di-concetto belle in README e rotte in pratica.
- **Cloud-only quando serve locale**: se il repo presume un servizio cloud/paid e a te serve local/PII
  → non scartare a priori (vedi passo 6), ma sappi che dovrai sostituire quel layer.

### 6. Adatta ai vincoli nostri

Il repo di altri non conosce i nostri vincoli. Adatta:

- **PII locale (Symbiosis Law 2)** — i dati intelligence/cliente non escono dal Pro. Un repo che manda
  testo a un'API cloud va riscritto per girare local (Ollama, asyncpg locale).
- **No paid API** — niente chiavi a pagamento (vedi CLAUDE.md). Sostituisci OpenAI→Ollama/embeddings local dove serve.
- **Stack nostro** — `asyncpg` non `psycopg2`, `httpx` async non `requests`, Ollama per LLM/vision, Mac/arm64.
- **Regola chiave**: un repo cloud-only **non si scarta**, si riscrive il layer-cloud in locale — _se il
  PATTERN sottostante è buono_. Il valore è il pattern, non l'implementazione del trasporto.

### 7. Documenta la provenienza

Per ogni pezzo riusato, traccia: **da quale repo, quale licenza, quale file/commit**. In un header,
un commento, o un `PROVENANCE.md`. Serve per: audit licenze, aggiornamenti upstream, e onestà
intellettuale. Tracciabilità non opzionale.

---

## Mini-esempio reale (la sessione che ha generato questa skill, 2026-06-04)

Task: costruire un sistema di **document-intake** (akta/visa docs → estrazione → CRM). Reazione
istintiva: "scrivo coda + OCR + parser + dedup + UI". Reazione corretta: scomponi e cerca.

| Mattone                   | Trovato (altri)    | Esito                                         |
| ------------------------- | ------------------ | --------------------------------------------- |
| OCR/extract               | `text-extract-api` | [FORKA-E-ADATTA] — local, no cloud            |
| pipeline doc→LLM          | `paperless-gpt`    | [STUDIA-PATTERN-RISCRIVI] — pattern di intake |
| coda su Postgres          | `pgqueuer`         | [INSTALLA-LIB] — già asyncpg-native           |
| entity resolution / dedup | `splink`           | [INSTALLA-LIB]                                |
| structured LLM output     | `instructor`       | [INSTALLA-LIB]                                |

Risultato: **~70% già scritto da altri**. Settimane → giorni. Il codice nuovo si è ridotto al collante
e all'adattamento ai vincoli (PII local, asyncpg, Ollama).

---

## Anti-pattern (riconoscili e fermati)

- **Reinventare per orgoglio** — "lo scrivo meglio io". Quasi mai vero per mattoni standard (code,
  OCR, dedup). Il tempo speso a riscrivere è tempo rubato al problema vero (i _nostri_ vincoli).
- **Copiare GPL/AGPL nel repo** — contamina la licenza dell'intero progetto. SEMPRE [STUDIA-PATTERN-RISCRIVI]
  per copyleft, mai copia-incolla.
- **Adottare una lib cloud per dati PII** — viola Law 2. Un default OpenAI/cloud non si accetta solo
  perché "è il README ufficiale". Riscrivi il layer in local o scarta.
- **Clonare repo morti** — demo abbandonate (ultima commit 2 anni fa, 30 issue aperte) costano più del
  green-field. Maturità prima dell'entusiasmo.
- **Saltare il gate licenze** — "tanto è su GitHub, è open" è falso: no-LICENSE = all-rights-reserved.
  Verifica sempre prima di importare.
- **Cercare il sistema intero invece dei mattoni** — query troppo larghe non trovano niente. Scomponi (passo 1).

---

## Integrazione con le altre skill

- Gira **dentro lo STEP 1 GROUND** di `sota-architecture-loop`: "lo stato esterno ai tuoi priors"
  include _anche il codice che altri hanno già scritto_, non solo NB/web.
- Complementare a `karpathy-discipline` §2 (Simplicity First): il codice più semplice è spesso quello
  che non scrivi affatto perché esiste già.
