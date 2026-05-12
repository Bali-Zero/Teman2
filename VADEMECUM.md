# VADEMECUM — Checklist operativa per costruire nell'organismo Nuzantara

> Leggi `SYMBIOSIS.md` per il _perché_. Leggi questo per il _come_.
> Serve la mappa del _cosa/dove_? Vedi [`INDEX.md`](INDEX.md).
> Ogni sezione risponde alla domanda: "cosa devo fare quando costruisco X?"

---

## Come usare questo documento

Per ogni cosa che stai per costruire, vai alla sezione corrispondente.
Segui la checklist nell'ordine. Non saltare punti.
Se un punto non si applica, scrivi _perché_ — non ignorarlo.

**Regola d'oro:** se al punto 3 di qualsiasi sezione non sai rispondere,
fermati e rileggilo. Non andare avanti.

---

## 1. Nuova automazione / script standalone

> Cron job, script bash, pipeline one-shot, bulk sync.

**Checklist:**

1. [ ] Dove vive nell'organismo? (organo produttore, organo consumatore)
2. [ ] Cosa produce? (Redis stream, SQLite row, file, niente?)
3. [ ] Chi legge quello che produce? (se nessuno → codice morto)
4. [ ] Ha una reflection post-run? (`claude --print` con output JSON → SQLite KB)
5. [ ] Logga in modo strutturato? (JSON, non print sparsi)
6. [ ] Ha un meccanismo di failure silenzioso? (non crasha l'organismo se fallisce)
7. [ ] È misurabile? (conta quante righe ha processato, quanti errori, quanto tempo)
8. [ ] Produce almeno un evento Redis se rileva qualcosa di significativo?

9. [ ] È registrata in `scripts/automation_catalog.json`? (descrizione, produces, consumes, LLM — senza entry, l'Excel inventory la mostra vuota)

**Minimo vitale:** punti 1, 3, 6, 9 obbligatori. Gli altri entro Sprint successivo.

**Pattern di riferimento:**

```python
# Fine di ogni run
reflection = {
    "run_date": today,
    "processed": n,
    "errors": err_count,
    "lesson": "..."  # generato via claude --print se errors > 0
}
kb.store(type="reflection", content=json.dumps(reflection), cell=CELL_NAME)
```

---

## 2. Nuovo agente cell-core (PulseLoop)

> Qualsiasi organo che usa `PulseLoop` da `packages/cell-core/`.

**Checklist:**

1. [ ] Nome cellula definito (`cell_name` in CellConfig) — snake_case, univoco
2. [ ] DB path configurabile (non hardcoded)
3. [ ] `Genome` istanziato e passato a `PulseLoop` (subclasse come `MataGarudaPulseLoop`)
4. [ ] Hook REFLECT (5b): `genome.record_skill()` solo se action non è errore e health != red
5. [ ] Hook DREAM (6b): `genome.silence_stale_skills()` durante sleep window
6. [ ] `scope='Project'` per skill trasferibili, `scope='Personal'` per cicatrici locali
7. [ ] `inherit_genome()` chiamato al momento del fork se è cellula figlia
8. [ ] `genome.search(query)` chiamato nel Thinker prima di ragionare da zero
9. [ ] Sensors dichiarano cosa producono (green/yellow/red + valore)
10. [ ] Actor pubblica su Redis stream dopo ogni azione significativa

**Minimo vitale:** punti 1, 2, 3, 4, 6.

### HGT — Horizontal Gene Transfer (opzionale, Sprint 5.2+)

Se la cellula partecipa al sistema circolatorio di conoscenza:

11. [ ] **Publisher** — se produce skill: `HGTPublisher` nel REFLECT hook, pubblica su `cell:skills` se confidence > 0.7 e scope='Project'
12. [ ] **Consumer** — se consuma skill: `HGTConsumer` con `interested_domains` dichiarati, integra con decay 0.9x
13. [ ] **Feedback** — se migliora skill ereditate: `VerticalFeedback` propone a parent se conf > inherited + 0.15
14. [ ] **Domain tag** — ogni `record_skill()` include `domain=` corretto (11 domini canonici in `hgt/domains.py`)
15. [ ] **Graceful degradation** — Redis down = cellula funziona in isolamento (Legge 4)
16. [ ] **No OSINT in HGT** — solo conoscenza operativa nei payload skill (Legge 2)

**Pattern di riferimento:** `apps/mata-garuda/mata_garuda/cell/runner.py` (publisher), `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py` (consumer)

### Observatory emit — silent-birth prevention (aggiunto 2026-05-12 post Gap 1 fix)

17. [ ] **Plist `EnvironmentVariables.CELL_OBSERVATORY_EMIT=true`** — senza questa env var il pulse hook in `cell_core/pulse.py:265` è no-op silenzioso, la cellula esegue ma non emette mai a `~/.cell-observatory/observatory.db` né al PG channel `cell_pulse_observed`. Verifica empirica 2026-05-12: solo `com.cell.organism.plist` ha l'env var → solo `cell_id='cell'` emette (1154 events/24h), seo-cell e sentinel sono silenti per default.

**Rationale**: `observatory.is_enabled()` legge `os.getenv("CELL_OBSERVATORY_EMIT","").lower() == "true"`. Un plist senza questa key produce cellule "nate silenti" — il bug è invisibile finché qualcuno non interroga l'observatory e nota che mancano cell_id. Vedi `research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md` per dettagli + procedura di fix retroattivo.

---

## 3. Nuovo router FastAPI

> Endpoint in `apps/backend-rag/backend/app/routers/`.

**Checklist:**

1. [ ] Importa solo da `backend.` — nessun import relativo
2. [ ] Usa `get_db`, `get_current_user` da `dependencies.py` — non re-implementare auth
3. [ ] Cache invalidation dopo ogni mutazione: `await invalidate_cache("zantara:namespace:*")`
4. [ ] Risponde a domande di traceability? (chi ha chiamato, quando, cosa ha cambiato)
5. [ ] Produce un evento Redis se la mutazione è significativa per altri organi?
6. [ ] Ha test in `backend/tests/`? (almeno happy path + 401)
7. [ ] **Aggiunto a `router_manifest.py` con `process_groups` corretto** (`_API` per light/public, `_RAG` per heavy/internal, `_BOTH` per entrambi). NON editare `router_registration.py` — legge il manifest automaticamente. (SCAR: PR #54/#55/#60 — 3 router registrati nel posto sbagliato → 404 silenzioso in produzione per settimane)
8. [ ] La documentazione OpenAPI (`summary=`, `description=`) è leggibile da un umano?
9. [ ] Verificato con `PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py -q`?

**Domanda chiave:** questo endpoint è isolato (muore dopo la response) o produce
conoscenza che persiste? Se produce conoscenza → va in KB o Redis, non solo in PG.

---

## 4. Nuovo servizio business logic

> File in `apps/backend-rag/backend/services/`.

**Checklist:**

1. [ ] Una responsabilità sola — se il file supera 300 righe, dividilo
2. [ ] Nessuna logica di routing o HTTP — quello è nel router
3. [ ] Errori tipizzati — eccezioni custom, non `raise Exception("string")`
4. [ ] Sa cosa ha fatto prima? (legge KB o Redis prima di agire)
5. [ ] Produce conoscenza dopo aver agito? (scrive in KB o Redis)
6. [ ] È testabile in isolamento? (no dipendenze hardcoded, usa dependency injection)
7. [ ] Usa `logger` non `print()`

---

## 5. Nuovo LLM prompt

> Qualsiasi testo che va a un modello.

**Checklist:**

1. [ ] È in `backend/prompts/zantara_core.py`? (SSOT — nessun prompt hardcoded altrove)
2. [ ] Ha un nome costante (`NOME_PROMPT = """..."""`)
3. [ ] Le variabili sono esplicite (`{variabile}`, non f-string con logica dentro)
4. [ ] È stato testato su almeno 3 input reali prima di andare in produzione?
5. [ ] Ha un fallback se il modello restituisce output malformato?
6. [ ] Se chiede output strutturato (JSON) → valida con Pydantic prima di usare
7. [ ] Se va a `claude --print` → ha guard anti-loop (`NUZANTARA_REFLECT=1`)?

**Errore comune:** prompt che funzionano in test e falliscono silenziosamente in
produzione perché l'LLM restituisce JSON con campo mancante e nessuno valida.

---

## 6. Nuova chain / agent workflow

> MetaChain, LangGraph subgraph, pipeline multi-step.

**Checklist:**

1. [ ] Cerca nel genome prima del primo step: `genome.search(query)` — esistono skill già note?
2. [ ] Ogni step ha un outcome strutturato (successo/fallimento/parziale)
3. [ ] I fallimenti producono scar: `genome.record_scar(cell, scar_id, procedure)`
4. [ ] I successi producono skill: `genome.record_skill(cell, skill_id, procedure, confidence)`
5. [ ] Il flusso è idempotente? (se lanciato due volte, non duplica dati)
6. [ ] Ha un timeout? (nessuna chain gira più di 5 minuti senza checkpoint)
7. [ ] Pubblica su Redis al termine (`garuda:raw`, `nexus:gaps`, o stream dedicato)?
8. [ ] Esiste un modo per interromperla? (kill switch, file disable, Redis flag)

---

## 7. Nuova migrazione DB

> File SQL in `apps/backend-rag/backend/db/migrations_v2/NNN_name.sql`.
> Il backend NON usa Alembic — usa il custom runner `backend/db/migration_manager.py`.
> Vedi `AUTONOMOUS_OPS.md` → "Schema-change discipline" per le regole hard.

**Checklist:**

1. [ ] File è SQL puro (non Python) in `migrations_v2/` con prefisso `NNN_` progressivo
2. [ ] Ha sia la sezione forward (in cima) che la sezione rollback dopo il marker `-- === ROLLBACK ===` — sempre, senza eccezioni
3. [ ] È testata su un DB fresh E su un DB con dati esistenti
4. [ ] Se aggiunge colonna NOT NULL → ha un default o una migrazione dati nello stesso file
5. [ ] Chi dipende dal vecchio schema? (cerca in `backend/services/` prima)
6. [ ] Il numero progressivo è corretto? (`ls backend/db/migrations_v2/ | tail -3` prima di scegliere)
7. [ ] `PYTHONPATH=. python -m backend.db.migrate apply-all --dry-run` passa pulito
8. [ ] È passata da Codex sandbox? (`./scripts/ai-dispatch.sh codex-sandbox "test migration"`)

**Hard rules (vedi `AUTONOMOUS_OPS.md`):**

- **MAI** `SQLModel.metadata.create_all()` per prod o CI (solo test scratch).
- **MAI** nuovi `apps/backend-rag/backend/migrations/apply_migration_NNN.py` senza approvazione umana esplicita — vanno convertiti a SQL.
- **MAI** rinominare o cancellare un file `migrations_v2/` già applicato in prod.

**Scar documentati:**

- Mai eseguire migration su prod senza averla testata su DB reale; il mock non rivela problemi di lock su tabelle grandi.
- 2026-04-19: il runner eseguiva la sezione ROLLBACK come parte della transazione forward — risolto in `migration_base.split_migration_sql()`. Da allora il marker `-- === ROLLBACK ===` è obbligatorio per qualunque migration con DDL reversibile.

---

## 8. Nuovo indice / collezione Qdrant

> Vector store in `apps/backend-rag/`.

**Checklist:**

1. [ ] Payload è flat? (nessun oggetto nested — `kode_kbli`, non `{"kbli": {"kode": ...}}`)
2. [ ] Usa `text-embedding-3-small` (1536 dims)? — **MAI cambiare senza re-indexing plan**
3. [ ] I campi del payload sono allineati con le collezioni esistenti?
4. [ ] Ha un processo di re-sync se il sorgente cambia?
5. [ ] È misurabile? (quanti documenti, quando è stato aggiornato, drift dal sorgente?)
6. [ ] Sa quando è stale? (timestamp `last_indexed` nel payload o in PG)

---

## 9. Nuova KB entry / regulation

> Qualsiasi conoscenza che va in SQLite KB o Qdrant.

**Checklist:**

1. [ ] Ha una fonte verificabile? (URL, documento ufficiale, data)
2. [ ] Ha una data di validità? (leggi cambiano — `valid_from`, `valid_to`)
3. [ ] È nel formato canonico del tipo? (regulation, skill, reflection, scar, pattern)
4. [ ] Qualcuno sa quando diventa stale? (cron che controlla, alert, manuale?)
5. [ ] È ingested via pipeline o manuale? (pipeline = ripetibile; manuale = punto di rottura)

---

## 10. Nuovo nodo nel Knowledge Graph (Neo4j)

> Entità in `apps/graph-engine/`.

**Checklist:**

1. [ ] Il label è nei tipi esistenti? (Company, Person, Visa, Property, Tax, KBLI, Regulation...)
2. [ ] Le properties sono flat e tipizzate?
3. [ ] Ha un `source` e un `updated_at`?
4. [ ] Gli archi che lo connettono esistono già nel subgraph? (check ontologia)
5. [ ] Aumenta la densità ontologica? (archi/nodi — più relazioni = più intelligente)
6. [ ] Viene interrogato dal gap detector? (se no, è un nodo cieco)

---

## 11. Nuovo LaunchAgent (plist)

> Daemon o scheduled job via `launchd` su Pro o Air.

**Checklist:**

1. [ ] Il `Label` segue la naming convention? (`com.nuzantara.*` per infra, `com.balizero.*` per business, `com.cell.*` per cell-core)
2. [ ] `ProgramArguments` usa path assoluto all'interprete? (`/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3`, non `python3`)
3. [ ] `EnvironmentVariables` include almeno `PATH` e `HOME`? (launchd NON eredita la shell — senza questi, ogni comando fallisce silenziosamente)
4. [ ] Se usa segreti (Telegram token, API keys) → sono in `EnvironmentVariables` del plist O caricati da `~/.nuzantara-secrets.env`?
5. [ ] `StandardOutPath` e `StandardErrorPath` puntano a `~/logs/`? (non `/tmp/` — sopravvive ai reboot, leggibile dal Sentinel)
6. [ ] Scheduling corretto? `StartInterval` (secondi, ricorrente) vs `StartCalendarInterval` (orario fisso) vs `KeepAlive` (daemon always-on)?
7. [ ] `RunAtLoad` è `true` solo per daemon che DEVONO partire al boot — per cron-style deve essere `false`
8. [ ] È registrato in `~/.agent/decisions/job_registry.json`? (senza entry, il Sentinel non lo vede)
9. [ ] Il registry entry ha: `host`, `type: "launchagent"`, `plist`, `schedule_seconds`, `staleness_threshold_s`, `restart_cmd`, `repair_scope`, `critical`
10. [ ] `restart_cmd` usa `launchctl kickstart -k gui/$(id -u)/<Label>` — non `launchctl start` (che non forza restart se già loaded)
11. [ ] Se è un daemon (`is_daemon: true` nel registry): ha un health endpoint o un modo per verificarne lo stato?
12. [ ] È stato caricato con `launchctl load`? Verifica con `launchctl list <Label>`
13. [ ] È registrato in `scripts/automation_catalog.json`? (descrizione, produces, consumes, LLM — senza entry, l'Excel inventory la mostra vuota)

**Scar documentato:** `launchd` non eredita `PATH`, `HOME`, né variabili d'ambiente dalla shell.
Ogni plist che non le dichiara esplicitamente fallisce con errori incomprensibili
(es. `command not found`, `FileNotFoundError`, `Connection refused` per servizi locali).

**Pattern di riferimento:**

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin</string>
    <key>HOME</key>
    <string>/Users/nuzantara</string>
</dict>
```

**Dopo il load:**

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.mio-job.plist
launchctl list com.nuzantara.mio-job  # verifica: LastExitStatus = 0
```

---

## 12. Deploy su Fly.io

> Solo `nuzantara-rag`, `nuzantara-postgres`, `nuzantara-qdrant`.

**Checklist:**

1. [ ] Import chain OK? `python -c "from backend.app.dependencies import get_current_user"`
2. [ ] Test core passano? (`pytest backend/tests/services/rag/` almeno)
3. [ ] Red team Gemini fatto? (`./scripts/ai-dispatch.sh redteam "descrizione deploy"`)
4. [ ] `fly.toml` non modificato da questa sessione? (file critico — hook blocca)
5. [ ] `auto_stop=off`, `min_machines=1` per `nuzantara-rag`? (cold start risolto)
6. [ ] Strategy è `rolling`? (mai `immediate` in produzione)
7. [ ] Hai un rollback plan? (versione precedente dell'immagine)

---

## 13. Nuova dipendenza Python

> `pip install` o aggiunta a `pyproject.toml`.

**Checklist:**

1. [ ] È davvero necessaria? (puoi farlo con la stdlib o con quello che c'è già?)
2. [ ] È nella whitelist implicita? (pydantic, pytest, httpx, fastapi, redis, qdrant-client...)
3. [ ] È vietata esplicitamente? (langchain, chromadb, anthropic, openai, litellm → NO)
4. [ ] Ha una licenza compatibile?
5. [ ] La installi nel venv giusto? (`.venv` su Pro, `venv` su Air)
6. [ ] L'hai aggiunta a `pyproject.toml` con version pinning?

---

## 14. Claude Code come organo (sessione di lavoro)

> Ogni sessione Claude Code è un pulse dell'organismo.

**Checklist inizio sessione:**

1. [ ] Hai letto le memorie recenti? (`mem recent`)
2. [ ] Hai letto le cicatrici rilevanti? (`cat ~/.claude/rules/cicatrix-scars.md`)
3. [ ] Hai letto SYMBIOSIS.md se stai costruendo qualcosa di nuovo?
4. [ ] Hai cercato nel genome prima di ragionare da zero? (`genome.search(query)`)

**Checklist fine sessione:**

1. [ ] Le decisioni architetturali sono salvate in MOS? (`mem save decision "..." 8`)
2. [ ] I bug trovati sono documentati? (`mem save discovery "..." 7`)
3. [ ] Le cicatrici nuove sono in `cicatrix-scars.md`?
4. [ ] Il REFLECT automatico girerà? (session-reflect.py via hook Stop)
5. [ ] Hai aggiornato `DOVE SIAMO` in SYMBIOSIS.md se un pilastro è cambiato?

**Il gap attuale:** `session-reflect.py` estrae skill/scar automaticamente con
`confidence=0.3`. Zero promuove manualmente a 0.6+ nel genome le skill validate.

---

## 15. Nuova / spostamento documentazione (`docs/`)

> L'inventory `docs/DOCS_INVENTORY.md` è la fonte di verità per lo stato dei
> ~570 file sotto `docs/**`. È **auto-generato**: non scriverlo a mano.

**Quando aggiungi un nuovo doc:**

1. [ ] Hai scelto la subdir giusta sotto `docs/`? (Se non esiste, è accettabile creare.)
2. [ ] Almeno un doc esistente o un libro sacro (CLAUDE/INDEX/SYMBIOSIS/VADEMECUM) lo linka? Altrimenti finirà candidato orphan dopo 90 giorni.
3. [ ] Hai rigenerato l'inventory? Una delle due:
   - **Locale ora:** `./scripts/docs_guardian.sh` (aggiorna `docs/DOCS_INVENTORY.md`)
   - **Lascialo al weekly cron:** ok, ma il CI check `Docs Guardian` sulla tua PR fallirà finché non lo rigeneri e committi.

**Quando sposti / rinomini un doc:**

1. [ ] Usa `git mv` (non `rm` + add) per preservare la history.
2. [ ] Grep dei riferimenti inbound: `rg -l "<old-name>.md"` e aggiorna tutti i link nello stesso commit.
3. [ ] Rigenera l'inventory come sopra.

**Quando archivi un doc (morte senza referenze):**

1. [ ] `git mv docs/<file>.md docs/archive/YYYY-MM-<slug>/` (mai `git rm` — reversibile con `git mv` opposto).
2. [ ] Verifica nessuna referenza in entrata da sacred books (`grep -l <file> CLAUDE.md INDEX.md SYMBIOSIS.md VADEMECUM.md`).

**Mai modificare a mano:**

- `docs/DOCS_INVENTORY.md` — rigenerato da `scripts/docs_audit.py`.
- `docs/AUTOMATIONS_REFERENCE.md` — rigenerato nightly 23:15 WITA da `scripts/generate_automations_reference.py`.
- Blocchi `<!-- DOCSYNC:KEY_START -->` — gestiti da `scripts/docs_sync.py`.

---

## Domande universali — il test finale

Prima di ogni PR, commit, o deploy, rispondi a queste 5:

| #   | Domanda                                                | Se la risposta è "no"                                      |
| --- | ------------------------------------------------------ | ---------------------------------------------------------- |
| 1   | Questo codice sa dove si trova nell'organismo?         | Aggiungi commento `# Organo: X → produce Y → consuma da Z` |
| 2   | Produce qualcosa che persiste oltre la sua esecuzione? | Aggiungi reflection, skill, o evento Redis                 |
| 3   | Se fallisce, l'organismo continua?                     | Aggiungi try/except + fallback silenzioso                  |
| 4   | Ha rispettato le cicatrici documentate?                | Rileggi cicatrix-scars.md prima di committare              |
| 5   | Tra un mese sarà misurabile?                           | Aggiungi almeno un counter o timestamp                     |

---

## Leggi inviolabili (da SYMBIOSIS.md — non negoziabili)

1. **CLI-only per LLM** — `claude --print`, `gemini --print`. Mai API HTTP Anthropic/Google/OpenAI. DeepSeek API unica eccezione.
2. **OSINT blindato** — dati intelligence mai fuori dal Pro. Mai frontend, mai cloud, mai team.
3. **Event-driven** — Redis Streams. Nessun polling, nessun orchestratore centrale.
4. **Graceful degradation** — se un organo non risponde, gli altri procedono.
5. **Zero come ultima istanza** — decisioni strutturali via Telegram. L'organismo propone, non decide.
6. **Sovranità locale** — vive su Pro (48GB) e Air (16GB). Disconnessione internet = stato naturale.
7. **Numeri prima** — senza metrica non è un miglioramento. Senza before/after non è evoluzione.
8. **Legge 8 (aggiunta 2026-04-12)** — ogni elemento nuovo deve rispondere alle 5 domande universali prima di esistere.

---

## Riferimenti rapidi

| Cosa cercare         | Dove                                                        |
| -------------------- | ----------------------------------------------------------- |
| Principi e filosofia | `SYMBIOSIS.md`                                              |
| Regole Claude Code   | `CLAUDE.md`                                                 |
| Cicatrici operative  | `.claude/rules/cicatrix-scars.md`                           |
| Genome DNA Recording | `packages/cell-core/cell_core/genome.py`                    |
| Design spec genome   | `docs/superpowers/specs/2026-04-12-dna-recording-design.md` |
| Memoria sessione     | `~/.claude/scripts/mem`                                     |
| REFLECT automatico   | `~/.claude/scripts/session-reflect.py`                      |
| Job registry         | `~/.agent/decisions/job_registry.json`                      |
| Pricing              | `PRICING_REFERENCE.md`                                      |
| Visa types           | `VISA_TYPES_REFERENCE.md`                                   |
| Prompt SSOT          | `apps/backend-rag/backend/prompts/zantara_core.py`          |

---

**Ultima legge:** se stai leggendo questo documento e stai cercando un modo per
giustificare di saltare un punto — fermati. Quella sensazione è il segnale che
il punto è esattamente quello che devi fare.

---

_Versione: 1.1 — 2026-04-13_
_Mantenuto da: Zero + Claude_
_Complementare a: SYMBIOSIS.md_
