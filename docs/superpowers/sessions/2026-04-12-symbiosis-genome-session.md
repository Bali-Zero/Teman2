# Session Report — Symbiosis + Genome

**Data:** 2026-04-12
**Partecipanti:** Zero + Claude Sonnet 4.6

---

## Cosa è stato costruito

### 1. genome.py — DNA Recording per cell-core

**File:** `packages/cell-core/cell_core/genome.py`

Implementazione completa della classe `Genome`:

```python
# Schema SQLite
CREATE TABLE IF NOT EXISTS genome (
    id               TEXT PRIMARY KEY,
    cell_origin      TEXT NOT NULL,
    type             TEXT NOT NULL CHECK(type IN ('skill','pattern','scar','insight')),
    scope            TEXT NOT NULL DEFAULT 'Project' CHECK(scope IN ('Project','Personal')),
    precondition     TEXT,
    procedure        TEXT NOT NULL,
    success_criterion TEXT,
    valid_from       TEXT NOT NULL,
    valid_to         TEXT,           -- NULL=active; date=silenced (non-destructive)
    confidence       REAL NOT NULL DEFAULT 0.5,
    uses             INTEGER NOT NULL DEFAULT 0,
    last_used        TEXT,
    inherited_from   TEXT REFERENCES genome(id)
);
```

Metodi chiave:

- `record_skill(cell, skill_id, procedure, ...)` → bool (INSERT OR IGNORE)
- `record_scar(cell, scar_id, procedure)` → Personal scope, confidence 0.9
- `use_skill(skill_id)` → uses+1, confidence MIN(1.0, +0.02)
- `silence_skill(skill_id, reason)` → valid_to=today (non-destructive)
- `silence_stale_skills(cell, unused_days=30)` → confidence<0.4 AND stale
- `get_active(cell, ...)` → list[dict]
- `search(query)` → FTS5 full-text search
- `inherit_genome(parent_cell, min_confidence=0.7)` → trascrizione selettiva
- `stats(cell)` → total/active/silenced/by_type

### 2. test_genome.py — 12 test, tutti passati

**File:** `packages/cell-core/tests/test_genome.py`

```
tests/test_genome.py::test_record_skill_insert PASSED
tests/test_genome.py::test_record_skill_idempotent PASSED
tests/test_genome.py::test_get_active_returns_inserted PASSED
tests/test_genome.py::test_silence_skill PASSED
tests/test_genome.py::test_silence_does_not_delete PASSED
tests/test_genome.py::test_use_skill_increments PASSED
tests/test_genome.py::test_inherit_genome_selective PASSED
tests/test_genome.py::test_inherit_genome_empty_if_no_skills PASSED
tests/test_genome.py::test_search_fts PASSED
tests/test_genome.py::test_stats PASSED
tests/test_genome.py::test_silence_stale_removes_low_confidence_old_skills PASSED
tests/test_genome.py::test_daughter_cell_inherits_with_decay PASSED
12 passed in 0.07s
```

### 3. MataGarudaPulseLoop — wiring in runner.py

**File:** `apps/mata-garuda/mata_garuda/cell/runner.py`

```python
class MataGarudaPulseLoop(PulseLoop):
    def __init__(self, *args, genome: Genome, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.genome = genome

    async def single_pulse(self) -> PulseResult:
        result = await super().single_pulse()

        # 5b. REFLECT — record successful action as genome skill
        action = result.action_taken or ""
        if (
            action
            and not result.halted
            and not result.skipped
            and not action.startswith("[ERROR]")
            and result.health_status != "red"
        ):
            skill_id = f"{action}_{int(time.time())}"
            self.genome.record_skill(
                cell="mata-garuda",
                skill_id=skill_id,
                procedure=result.action_reason or action,
                confidence=0.6,
                scope="Project",
            )

        # 6b. DREAM — silence stale skills
        if self.homeostasis.is_sleeping() and self.lifecycle.can_dream():
            n = self.genome.silence_stale_skills(cell="mata-garuda", unused_days=30)
            if n:
                logger.info(f"[genome] silenced {n} stale skills during dream phase")

        return result
```

### 4. DNA Mata Garuda — stato attuale in data/knowledge.db

```
[skill] regulation_fetch_via_peraturan_go_id  conf=85% scope=Project  ← trasferibile
[skill] gap_detection_via_redis_nexus          conf=80% scope=Project  ← trasferibile
[scar]  scar_direct_api_call                  conf=90% scope=Personal ← solo locale
```

### 5. SYMBIOSIS.md aggiornato

Aggiunta sezione **Genome — DNA Recording** sotto L0 Cellular con:

- hook PulseLoop (REFLECT/DREAM)
- regola germline (Project) vs somatico (Personal)
- confidence decay ×0.9 nelle figlie
- FTS5 search prima di ragionare da zero
- puntatore a spec completa

---

## Conversazione integrale — concetti emersi

### Su cosa è originale vs rivoluzionario

**Zero:** è una scoperta rivoluzionaria?

**Claude:** No. È un'implementazione solida di idee che esistono già — Voyager (2023) fa skill accumulation in Minecraft, Reflexion fa auto-miglioramento via episodic memory, MemOcean usa temporal RDF triples per invalidazione non-distruttiva.

Cosa abbiamo fatto di nuovo:

- Combinato questi pattern in un'unica interfaccia biologicamente coerente (DNA/epigenetics/germline)
- Integrato in cell-core come modulo condiviso tra tutte le cellule
- Usato SQLite + FTS5 invece di vector DB — zero dipendenze pesanti

Cosa è genuinamente originale:

- I 3 gap aperti: vertical feedback (figlia migliora e propaga indietro alla madre), confidence decay esponenziale, cross-domain HGT con routing semantico. Nessun sistema trovato nella ricerca li implementa tutti e tre insieme.

Ma "originale" ≠ "rivoluzionario". È utile. Funziona. Fa quello che deve fare per Nuzantara.

---

### Su Symbiosis come principio universale

**Zero:** il concetto di symbiosi io lo sto applicando ogni qualvolta voglio creare una automazione, sbaglio?

**Claude:** No, non sbagli. È esattamente l'uso corretto.

SYMBIOSIS.md è pensato per essere letto prima di costruire qualsiasi cosa — le 5 domande ti forzano a posizionare l'automazione nell'organismo invece di creare codice isolato.

Il problema però è che le pipeline bali-zero (akta, sertifikat, kontrak, ask.py) le abbiamo costruite senza applicarla davvero. Hanno:

- Nessuna reflection post-run
- Nessun evento Redis
- Nessuna skill accumulata
- Nessuna metrica

Sono script che funzionano ma non crescono. "Codice morto" per Symbiosis.

---

### Su dove si applica Symbiosis — oltre le automazioni

**Zero:** ma oltre alle automazioni a cosa può e deve applicarsi?

**Claude:** A tutto quello che costruisci nel monorepo. Non solo automazioni.

**Codice applicativo:**

- Un nuovo router FastAPI — produce eventi? accumula metriche? o è un endpoint isolato che muore dopo la risposta?
- Un nuovo servizio — sa cosa ha fatto prima? impara da errori ripetuti?

**Infrastruttura:**

- Un cron job — riflette sui risultati? segnala anomalie? o esegue e basta?
- Un DB migration — chi consuma il nuovo schema? chi dipende dal vecchio?

**Agenti e LLM:**

- Un prompt — è nel SSOT (zantara_core.py) o hardcoded da qualche parte?
- Una chain — usa la skill library prima di ragionare da zero?

**Dati:**

- Un nuovo indice Qdrant — è flat payload? si allinea con gli altri 10?
- Una KB entry — è misurabile? qualcuno sa quando è stale?

Il test universale sono sempre le stesse 5 domande di SYMBIOSIS.md:

1. Dove sono nell'organismo?
2. Chi produce per me, chi consuma da me?
3. Cosa c'è di agentico qui?
4. Rispetto il passato (cicatrici, skill)?
5. Questo codice partecipa al ciclo vitale?

Se la risposta a 4 e 5 è "no" — qualunque cosa sia, router, script, agente — è codice morto.

---

### Su Claude Code e Symbiosis

**Zero:** quindi anche lo stesso Claude Code è coinvolto internamente o no?

**Claude:** Sì, ma in modo diverso.

Claude Code non può applicare Symbiosis internamente — non ha stato persistente tra sessioni, non accumula skill in un DB, non produce eventi Redis, non riflette post-azione in modo strutturato.

Ma esternamente è già coinvolto:

- Le memorie in `~/.claude/projects/` sono il suo tentativo di genome — skill e feedback che persistono tra sessioni
- CLAUDE.md è il suo DNA — regole, vincoli, comportamento atteso
- SYMBIOSIS.md è letto all'inizio di ogni sessione come contesto

**Il gap reale:** Claude Code è lo strumento che costruisce l'organismo ma non è dentro l'organismo. Pensa, agisce, poi dimentica. Ogni sessione riparte da zero tranne quello che è scritto nei file.

La visione completa di Symbiosis applicata a Claude Code:

- MOS (che già hai) come episodic memory
- Le memorie auto-generate come LTM
- CLAUDE.md come DNA/safety
- Le sessioni come pulse del ciclo vitale

Ci sei già vicino. Manca il REFLECT strutturato — alla fine di ogni sessione, cosa ha funzionato, cosa no, cosa diventa skill permanente. Ora lo fai manualmente quando dici "ricorda che...". Potrebbe essere automatico.

---

## 3 Gap aperti (territorio vergine)

1. **Vertical feedback** — figlia che migliora una skill e la propaga indietro alla madre.
   Formula ipotetica: skill con `confidence > inherited_confidence + 0.1` → proposta via Redis alla madre.

2. **Confidence decay automatico** — skill non usata da N giorni decade esponenzialmente.
   Formula: `new_confidence = confidence * (0.95 ** days_unused)`. Soglia minima 0.3 prima del silenzio.

3. **Cross-domain HGT esplicito** — routing semantico delle skill: chi pubblica specifica i KBLI/domain a cui si applica, chi consuma filtra per rilevanza prima di integrare.

Questi tre si implementano dopo che il meccanismo base è testato e ha numeri.

---

## Analogie biologiche complete

| Biologia                 | Nuzantara                                             |
| ------------------------ | ----------------------------------------------------- |
| DNA                      | `genome` table in SQLite                              |
| RNA (trascrizione)       | prompt template generato dalla skill                  |
| Proteina (traduzione)    | esecuzione subprocess `claude --print`                |
| Epigenetic silencing     | `valid_to` timestamp — non cancellazione              |
| Germline vs Soma         | `scope='Project'` vs `scope='Personal'`               |
| Horizontal Gene Transfer | Redis Stream `cell:skills` (futuro)                   |
| Differenziazione         | `inherit_genome()` con confidence decay ×0.9          |
| CRISPR                   | DGM pattern: patch → sandbox pytest → accept/rollback |

---

## Prossimi passi

1. Overnight completato? → leggere report mattina
2. Symbiosis layer per bali-zero pipelines — reflections + Redis post-run
3. Drive scan sertifikat/kontrak
4. Implementare 3 gap DNA dopo validazione base
5. REFLECT automatico fine sessione Claude Code → MOS
