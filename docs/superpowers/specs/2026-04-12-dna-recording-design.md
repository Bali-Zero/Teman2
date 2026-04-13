# DNA Recording — Design Spec

**Date:** 2026-04-12
**Status:** Approved for implementation
**Author:** Zero + Claude Sonnet 4.6
**Research base:** SELF_EVOLVING_AGENT_RESEARCH.md (49 Exa citations + 65 NLM sources) + deep research AgentSpawn / MemOcean / Crab Engram / Voyager

---

## 1. Problema

Le cellule di Nuzantara accumulano conoscenza durante la vita ma non la trasmettono strutturalmente.
Quando una cellula figlia nasce (sertifikat_parser da akta_archive, kontrak_parser da akta_archive)
eredita il codice ma non la saggezza operativa della madre.

**Il gap specifico:** non esiste un meccanismo formale per:

- registrare cosa una cellula ha imparato durante la vita
- trasferire selettivamente quella conoscenza a una figlia
- silenziare (non cancellare) conoscenza obsoleta
- propagare skill orizzontalmente tra cellule sorelle via Redis

---

## 2. Analogia biologica → implementazione

| Biologia                 | Nuzantara                                                                  |
| ------------------------ | -------------------------------------------------------------------------- |
| DNA                      | `genome` table in SQLite (struttura + precondizioni + procedure)           |
| RNA (trascrizione)       | prompt template generato dalla skill per un contesto specifico             |
| Proteina (traduzione)    | esecuzione subprocess `claude --print` con quel prompt                     |
| Epigenetic silencing     | `valid_to` timestamp: skill silenziata senza cancellazione                 |
| Germline vs Soma         | `scope='Project'` (trasferibile) vs `scope='Personal'` (locale)            |
| Horizontal Gene Transfer | Redis Stream `cell:skills` per skill transfer diretto tra sorelle          |
| Differenziazione         | `inherit_genome()`: figlia eredita per query filtrata, non copia integrale |
| CRISPR                   | DGM pattern: patch proposta → sandbox pytest → accept/rollback             |

---

## 3. Schema SQLite — `genome` module

Da aggiungere in `packages/cell-core/cell_core/genome.py`:

```python
"""Genome — DNA recording for Nuzantara cells.

Ogni cellula ha un genoma: skill acquisite, pattern osservati, cicatrici.
Il genoma è trasferibile alle cellule figlie via inherit_genome().
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS genome (
    id           TEXT PRIMARY KEY,        -- 'proxy_detection_v1'
    cell_origin  TEXT NOT NULL,           -- 'akta_archive'
    type         TEXT NOT NULL,           -- 'skill' | 'pattern' | 'scar' | 'insight'
    scope        TEXT NOT NULL DEFAULT 'Project',  -- 'Project' | 'Personal'

    -- Il DNA
    precondition TEXT,                    -- quando si applica questa conoscenza
    procedure    TEXT NOT NULL,           -- cosa fare (testo libero o codice)
    success_criterion TEXT,              -- come sapere se ha funzionato

    -- Validità temporale (non-destructive invalidation)
    valid_from   TEXT NOT NULL,           -- ISO date
    valid_to     TEXT,                    -- NULL = attiva; data = silenziata

    -- Fitness
    confidence   REAL NOT NULL DEFAULT 0.5,  -- 0.0-1.0
    uses         INTEGER NOT NULL DEFAULT 0,
    last_used    TEXT,

    -- Provenienza
    inherited_from TEXT,                  -- parent skill ID se differenziazione
    FOREIGN KEY (inherited_from) REFERENCES genome(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS genome_fts USING fts5(
    precondition, procedure, success_criterion,
    content=genome, content_rowid=rowid
);

CREATE INDEX IF NOT EXISTS idx_genome_cell ON genome(cell_origin);
CREATE INDEX IF NOT EXISTS idx_genome_type ON genome(type);
CREATE INDEX IF NOT EXISTS idx_genome_scope ON genome(scope);
CREATE INDEX IF NOT EXISTS idx_genome_confidence ON genome(confidence);
```

### Metodi chiave

```python
def record_skill(
    cell: str,
    skill_id: str,
    procedure: str,
    precondition: str = "",
    success_criterion: str = "",
    confidence: float = 0.5,
    scope: str = "Project",
) -> None:
    """Registra una skill acquisita nel genoma."""

def silence_skill(skill_id: str, reason: str = "") -> None:
    """Silenzia una skill obsoleta (non-destructive: setta valid_to)."""

def use_skill(skill_id: str) -> None:
    """Incrementa uses + last_used. Chiamare quando la skill viene applicata."""

def inherit_genome(
    parent_cell: str,
    fork_date: str,
    min_confidence: float = 0.7,
) -> list[dict]:
    """
    Trascrizione genetica: restituisce le skill trasferibili al momento del fork.

    Filtri applicati:
    - scope = 'Project'  (non Personal)
    - type IN ('skill', 'pattern')  (non scar o insight raw)
    - confidence >= min_confidence
    - valid_from <= fork_date
    - valid_to IS NULL OR valid_to > fork_date  (attive al momento del fork)

    Ordine: confidence DESC, uses DESC (le più affidabili e usate prima)
    """

def search_genome(query: str, limit: int = 5) -> list[dict]:
    """FTS5 search sul genoma. Usare prima di ragionare da zero."""
```

---

## 4. Dove vive il genoma

**Non in ogni cellula separatamente.** In `packages/cell-core/` come modulo condiviso.

```
packages/cell-core/
├── cell_core/
│   ├── genome.py       ← NUOVO: DNA recording
│   ├── memory_sqlite.py
│   ├── pulse.py
│   └── ...
```

Ogni cellula che usa cell-core ottiene automaticamente il DNA recording.
Il path del DB è configurabile via `CellConfig.db_path` (già esistente).

---

## 5. Integrazione con PulseLoop esistente

Il `PulseLoop` in `pulse.py` ha già il ciclo `reflect` (step 5) e `dream` (step 6).
Il DNA recording si aggancia qui — zero modifiche all'architettura:

```python
# Nel metodo single_pulse(), step 5 — REFLECT
# Aggiunta: se action_taken ha prodotto successo, proponi skill
if action_taken and action_outcome == "success":
    genome.record_skill(
        cell=self.config.name,
        skill_id=f"{proposal.action}_{int(time.time())}",
        procedure=proposal.reason,
        confidence=proposal.confidence,
    )

# Nel metodo single_pulse(), step 6 — DREAM
# Aggiunta: consolida skill con confidence bassa se mai usate da 30+ giorni
genome.silence_stale_skills(cell=self.config.name, unused_days=30)
```

**Nessuna breaking change.** Il genome è opzionale: se `None`, il PulseLoop funziona identico a oggi.

---

## 6. Flusso di differenziazione cellulare

Quando si crea una nuova cellula figlia (es. `sertifikat_parser` da `akta_archive`):

```python
# 1. Al momento del fork, trascrivi il genoma trasferibile
inherited = genome.inherit_genome(
    parent_cell="akta_archive",
    fork_date="2026-04-12",
    min_confidence=0.7,
)

# 2. Inietta nel prompt della figlia come contesto iniziale
dna_context = "\n".join([
    f"- [{s['type']}] {s['procedure']} (confidence={s['confidence']:.0%})"
    for s in inherited
])
# dna_context va nel system prompt della figlia

# 3. Registra l'ereditarietà
for skill in inherited:
    genome.record_skill(
        cell="sertifikat_parser",
        skill_id=f"inherited_{skill['id']}",
        procedure=skill['procedure'],
        confidence=skill['confidence'] * 0.9,  # leggero decay per nuova cellula
        inherited_from=skill['id'],
    )
```

---

## 7. Horizontal Gene Transfer via Redis

Per trasferire skill direttamente tra cellule sorelle (senza padre comune):

```python
# Pubblicare una skill su Redis Stream
redis.xadd("cell:skills", {
    "skill_id": "proxy_detection_v2",
    "cell_origin": "akta_archive",
    "procedure": "...",
    "confidence": "0.94",
    "scope": "Project",
})

# Consumer (es. kontrak_parser) legge e integra
for msg in redis.xread({"cell:skills": "$"}):
    skill = msg.data
    if skill["scope"] == "Project":
        genome.record_skill(
            cell="kontrak_parser",
            skill_id=f"hgt_{skill['skill_id']}",
            procedure=skill["procedure"],
            confidence=float(skill["confidence"]) * 0.85,  # HGT penalty
            inherited_from=skill["skill_id"],
        )
```

**Nota:** Redis è già nell'organismo (`garuda:raw`, `nexus:gaps`). `cell:skills` è un terzo stream.

---

## 8. I 3 gap aperti (territorio vergine)

Nessun sistema trovato nella ricerca li implementa:

1. **Vertical feedback** — figlia che migliora una skill e la propaga indietro alla madre.
   Soluzione ipotetica: skill con `confidence > inherited_confidence + 0.1` → proposta via Redis a madre.

2. **Confidence decay automatico** — skill non usata da N giorni decade esponenzialmente.
   Formula: `new_confidence = confidence * (0.95 ** days_unused)`. Soglia minima 0.3 prima del silenzio.

3. **Cross-domain HGT esplicito** — routing semantico delle skill: chi pubblica specifica i KBLI/domain
   a cui si applica, chi consuma filtra per rilevanza prima di integrare.

Questi tre si implementano dopo che il meccanismo base è testato e ha numeri.

---

## 9. Test di implementazione su Mata Garuda

Mata Garuda (`apps/mata-garuda/`) è la cellula candidata per il primo test perché:

- usa `cell-core` live con `PulseLoop` completo
- ha `KnowledgeBase` SQLite operativa (`data/knowledge.db`)
- ha `memory_bridge.py` che adatta KB → cell-core protocols
- ha `ReflectionEpisodicStore` già in produzione

**Il test concreto:** aggiungere `genome.py` a cell-core, wiring in `runner.py`,
eseguire `--once`, verificare che una skill viene registrata nel DB.

---

## 10. Riferimenti

- `SYMBIOSIS.md` — Pilastro 2 (Accumulazione), Pilastro 3 (Condivisione)
- `packages/cell-core/` — genoma condiviso (9 moduli, 110 test)
- `apps/mata-garuda/mata_garuda/cell/runner.py` — cellula candidata per test
- `apps/mata-garuda/mata_garuda/cell/memory_bridge.py` — bridge KB↔cell-core
- Paper: Voyager (Wang 2023), Reflexion (Shinn 2023), DGM (Zhang 2025), MemOcean (ChannelLabAI)
- Research interno: `docs/superpowers/specs/nlm-deep-research/SELF_EVOLVING_AGENT_RESEARCH.md`
