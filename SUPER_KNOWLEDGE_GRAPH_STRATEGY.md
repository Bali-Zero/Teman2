# NUZANTARA Super Knowledge Graph

## Strategia Architetturale Definitiva - Opus 4.5

**Data**: 2 Febbraio 2026
**Versione**: 1.0
**Autore**: Claude Opus 4.5 (calibrazione su Antigravity + Gemini 2.5 Pro)

---

## EXECUTIVE SUMMARY

Questo documento definisce l'architettura completa per un Knowledge Graph che unifica:

- **300+ Regolamenti** (UU, PP, Perpres, Permen, Perda)
- **KBLI & Business** (1,562 codici + licenze + rischi)
- **Immigration** (30+ tipi visa + requisiti)
- **Tax** (15+ tipi imposte + incentivi + treaties)
- **Property** (diritti, zone, ownership structures)

**Filosofia Core**: Il grafo non è un database - è una **mappa navigabile** del sistema burocratico indonesiano dove ogni query diventa un pathfinding problem.

---

## PARTE 1: ARCHITETTURA FONDAMENTALE

### 1.1 I Tre Pilastri

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         QUERY LAYER                                      │
│  (Intent Classification → Hybrid Retrieval → Path Synthesis)            │
├─────────────────────────────────────────────────────────────────────────┤
│                         KNOWLEDGE LAYER                                  │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │       QDRANT            │    │         POSTGRESQL                  │ │
│  │   (Semantic Memory)     │◄──►│      (Structural Memory)            │ │
│  │                         │    │                                     │ │
│  │ • Full-text content     │    │ • kg_nodes (entities)               │ │
│  │ • Embeddings            │    │ • kg_edges (relationships)          │ │
│  │ • BM25 sparse vectors   │    │ • kg_regulations (law hierarchy)    │ │
│  │                         │    │ • kg_workflows (pre-computed paths) │ │
│  └─────────────────────────┘    └─────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│                         SOURCE LAYER                                     │
│  (BPS, DJP, BKPM, Imigrasi, BPN, Kemenkumham, News Feeds)               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Principio di Dualità

| Domanda                               | Chi Risponde  | Come                                |
| ------------------------------------- | ------------- | ----------------------------------- |
| "Cosa dice la legge X?"               | Qdrant        | Semantic search sul testo           |
| "Quali permessi servono per Y?"       | PostgreSQL KG | Graph traversal                     |
| "Posso fare Z come straniero a Bali?" | Entrambi      | Hybrid: intent→entities→path→enrich |

### 1.3 Entity ID Convention (URN)

```
{domain}:{type}:{identifier}

Regole:
- Tutto lowercase
- Spazi → underscore
- Caratteri speciali rimossi (tranne : _ .)
- Identificatori numerici preservati

Esempi:
- reg:uu:40_2007                    (UU 40/2007 Perseroan Terbatas)
- reg:pp:28_2025                    (PP 28/2025 Perizinan Berusaha)
- reg:perpres:49_2021               (Perpres 49/2021 DNI)
- kbli:code:47111                   (Codice KBLI)
- kbli:section:g                    (Sezione G - Perdagangan)
- kbli:risk:menengah_tinggi         (Livello rischio)
- legal:entity:pt_pma               (Tipo entità)
- legal:permit:nib                  (Tipo permesso)
- visa:type:kitas_investor          (Tipo visa)
- visa:sponsor:company              (Tipo sponsor)
- tax:type:pph_badan                (Tipo imposta)
- tax:incentive:tax_holiday         (Incentivo fiscale)
- geo:province:bali                 (Provincia)
- geo:zone:kek_mandalika            (Zona economica speciale)
- property:right:hgb                (Diritto proprietà)
```

---

## PARTE 2: SCHEMA DATABASE

### 2.1 Core Tables

```sql
-- ============================================
-- NUZANTARA KNOWLEDGE GRAPH SCHEMA
-- Version: 1.0
-- ============================================

-- Estensioni richieste
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Per fuzzy search

-- ============================================
-- 1. NODI (Entità del Grafo)
-- ============================================
CREATE TABLE kg_nodes (
    -- Identità
    id TEXT PRIMARY KEY,                      -- URN: 'kbli:code:47111'
    domain TEXT NOT NULL,                     -- 'kbli', 'visa', 'tax', 'legal', 'property', 'reg', 'geo'
    entity_type TEXT NOT NULL,                -- 'code', 'permit', 'visa_type', etc.

    -- Contenuto
    name TEXT NOT NULL,                       -- Nome leggibile
    name_id TEXT,                             -- Nome in Bahasa Indonesia
    name_en TEXT,                             -- Nome in English
    description TEXT,                         -- Descrizione breve

    -- Dati strutturati (domain-specific)
    properties JSONB DEFAULT '{}'::jsonb,

    -- Metadati
    source_document TEXT,                     -- Riferimento a documento Qdrant
    confidence FLOAT DEFAULT 1.0,             -- 1.0 = ufficiale, 0.7 = inferito

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system'
);

-- Indici per performance
CREATE INDEX idx_nodes_domain ON kg_nodes(domain);
CREATE INDEX idx_nodes_type ON kg_nodes(entity_type);
CREATE INDEX idx_nodes_domain_type ON kg_nodes(domain, entity_type);
CREATE INDEX idx_nodes_properties ON kg_nodes USING GIN (properties);
CREATE INDEX idx_nodes_name_trgm ON kg_nodes USING GIN (name gin_trgm_ops);

-- ============================================
-- 2. ARCHI (Relazioni del Grafo)
-- ============================================
CREATE TABLE kg_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Connessione
    source_id TEXT NOT NULL REFERENCES kg_nodes(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES kg_nodes(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,          -- 'REQUIRES', 'ENABLES', 'BLOCKED_BY'

    -- Metadati relazione
    properties JSONB DEFAULT '{}'::jsonb,     -- Condizioni, limiti, eccezioni
    weight FLOAT DEFAULT 1.0,                 -- Importanza/Confidence

    -- Traceability
    source_regulation TEXT,                   -- 'reg:perpres:49_2021' - da dove viene
    article_reference TEXT,                   -- 'Pasal 5 ayat 2'

    -- Versionamento Temporale (SCD Type 2)
    valid_from DATE DEFAULT CURRENT_DATE,
    valid_to DATE DEFAULT NULL,               -- NULL = attualmente valido

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',

    -- Constraint: no self-loops, unique active edges
    CONSTRAINT no_self_loop CHECK (source_id != target_id),
    CONSTRAINT unique_active_edge UNIQUE NULLS NOT DISTINCT (source_id, target_id, relationship_type, valid_to)
);

-- Indici per traversal veloce
CREATE INDEX idx_edges_source ON kg_edges(source_id);
CREATE INDEX idx_edges_target ON kg_edges(target_id);
CREATE INDEX idx_edges_type ON kg_edges(relationship_type);
CREATE INDEX idx_edges_source_type ON kg_edges(source_id, relationship_type);
CREATE INDEX idx_edges_active ON kg_edges(valid_to) WHERE valid_to IS NULL;
CREATE INDEX idx_edges_properties ON kg_edges USING GIN (properties);

-- ============================================
-- 3. REGOLAMENTI (Gerarchia Normativa)
-- ============================================
CREATE TABLE kg_regulations (
    id TEXT PRIMARY KEY,                      -- 'reg:uu:40_2007'

    -- Classificazione
    reg_type TEXT NOT NULL,                   -- 'uu', 'pp', 'perpres', 'permen', 'perda', 'se'
    reg_number TEXT NOT NULL,                 -- '40'
    reg_year INTEGER NOT NULL,                -- 2007

    -- Contenuto
    title TEXT NOT NULL,                      -- Titolo ufficiale
    title_short TEXT,                         -- Titolo breve
    subject_matter TEXT[],                    -- ['perseroan', 'pt', 'modal']

    -- Gerarchia
    parent_reg TEXT REFERENCES kg_regulations(id),  -- Regolamento padre (se derivato)
    amends TEXT[],                            -- Lista reg che modifica
    amended_by TEXT[],                        -- Lista reg che lo modificano
    supersedes TEXT[],                        -- Lista reg che abroga
    superseded_by TEXT,                       -- Reg che lo abroga

    -- Validità
    enacted_date DATE,
    effective_date DATE,
    expired_date DATE,                        -- NULL = ancora in vigore

    -- Contenuto full-text (reference a Qdrant)
    qdrant_collection TEXT,                   -- 'legal_kb'
    qdrant_document_ids TEXT[],               -- IDs dei chunks in Qdrant

    -- Metadati
    issuing_authority TEXT,                   -- 'DPR', 'Presiden', 'Menteri Keuangan'
    properties JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_regs_type ON kg_regulations(reg_type);
CREATE INDEX idx_regs_year ON kg_regulations(reg_year);
CREATE INDEX idx_regs_subject ON kg_regulations USING GIN (subject_matter);

-- ============================================
-- 4. WORKFLOW PRE-COMPUTATI
-- ============================================
CREATE TABLE kg_workflows (
    id TEXT PRIMARY KEY,                      -- 'wf:foreigner_pt_pma_bali'

    -- Descrizione
    name TEXT NOT NULL,
    description TEXT,

    -- Contesto applicabilità
    actor_type TEXT NOT NULL,                 -- 'foreigner', 'indonesian', 'company'
    goal_type TEXT NOT NULL,                  -- 'start_business', 'get_visa', 'buy_property'

    -- Percorso (array ordinato di step)
    steps JSONB NOT NULL,                     -- [{step_id, node_id, action, requirements}]

    -- Vincoli
    constraints JSONB DEFAULT '{}'::jsonb,    -- {min_capital, allowed_locations, etc}

    -- Metadati
    estimated_duration_days INTEGER,
    estimated_cost_idr BIGINT,
    difficulty_level TEXT,                    -- 'simple', 'moderate', 'complex'

    -- Validità
    valid_from DATE DEFAULT CURRENT_DATE,
    valid_to DATE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 5. VISTE PER QUERY SEMPLIFICATE
-- ============================================

-- Vista: Solo archi attualmente validi
CREATE VIEW kg_active_edges AS
SELECT * FROM kg_edges
WHERE valid_to IS NULL;

-- Vista: Solo regolamenti in vigore
CREATE VIEW kg_active_regulations AS
SELECT * FROM kg_regulations
WHERE expired_date IS NULL OR expired_date > CURRENT_DATE;

-- Vista: Grafo completo (nodi + archi) per export
CREATE VIEW kg_full_graph AS
SELECT
    e.id as edge_id,
    e.relationship_type,
    s.id as source_id,
    s.domain as source_domain,
    s.name as source_name,
    t.id as target_id,
    t.domain as target_domain,
    t.name as target_name,
    e.properties as edge_properties,
    e.source_regulation
FROM kg_active_edges e
JOIN kg_nodes s ON e.source_id = s.id
JOIN kg_nodes t ON e.target_id = t.id;
```

### 2.2 Relationship Types (Tassonomia Completa)

```sql
-- Tabella di riferimento per i tipi di relazione
CREATE TABLE kg_relationship_types (
    type_code TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    description TEXT,
    inverse_type TEXT,                        -- Relazione inversa
    domains_allowed TEXT[]                    -- Domini sorgente permessi
);

INSERT INTO kg_relationship_types VALUES
-- STRUTTURALI (Gerarchia)
('BELONGS_TO', 'structural', 'Appartenenza gerarchica', 'CONTAINS', ARRAY['kbli', 'geo']),
('CONTAINS', 'structural', 'Contiene elementi', 'BELONGS_TO', ARRAY['kbli', 'geo']),
('HAS_VARIANT', 'structural', 'Ha variante (es. per scala)', 'VARIANT_OF', ARRAY['kbli']),
('VARIANT_OF', 'structural', 'È variante di', 'HAS_VARIANT', ARRAY['kbli']),

-- REQUISITI (Dipendenze)
('REQUIRES', 'requirement', 'Richiede obbligatoriamente', 'REQUIRED_BY', ARRAY['kbli', 'visa', 'legal']),
('REQUIRED_BY', 'requirement', 'È richiesto da', 'REQUIRES', ARRAY['legal', 'visa']),
('DEPENDS_ON', 'requirement', 'Dipende da (soft)', NULL, ARRAY['kbli', 'legal', 'visa']),

-- ABILITAZIONI (Permessi)
('ENABLES', 'enablement', 'Abilita/Permette', 'ENABLED_BY', ARRAY['visa', 'legal']),
('ENABLED_BY', 'enablement', 'È abilitato da', 'ENABLES', ARRAY['kbli', 'legal']),
('OPERATES', 'enablement', 'Può operare/gestire', 'OPERATED_BY', ARRAY['legal']),
('OPERATED_BY', 'enablement', 'È operato da', 'OPERATES', ARRAY['kbli']),

-- RESTRIZIONI (Blocchi)
('BLOCKED_BY', 'restriction', 'Bloccato da regolamento', NULL, ARRAY['kbli', 'visa', 'property']),
('RESTRICTED_IN', 'restriction', 'Ristretto in zona/contesto', NULL, ARRAY['kbli', 'property']),
('EXCLUDED_FOR', 'restriction', 'Escluso per attore', NULL, ARRAY['kbli', 'property', 'visa']),

-- FISCALI
('TAX_OBLIGATION', 'fiscal', 'Ha obbligo fiscale', NULL, ARRAY['legal', 'kbli']),
('ELIGIBLE_FOR', 'fiscal', 'Idoneo a incentivo', NULL, ARRAY['kbli', 'geo', 'legal']),
('HAS_RATE', 'fiscal', 'Ha aliquota', NULL, ARRAY['tax']),

-- NORMATIVI (Traceability)
('GOVERNED_BY', 'regulatory', 'Regolato da', 'GOVERNS', ARRAY['kbli', 'visa', 'tax', 'legal', 'property']),
('GOVERNS', 'regulatory', 'Regola', 'GOVERNED_BY', ARRAY['reg']),
('DEFINED_IN', 'regulatory', 'Definito in', NULL, ARRAY['kbli', 'visa', 'tax', 'legal']),
('AMENDS', 'regulatory', 'Modifica', 'AMENDED_BY', ARRAY['reg']),
('AMENDED_BY', 'regulatory', 'Modificato da', 'AMENDS', ARRAY['reg']),
('SUPERSEDES', 'regulatory', 'Sostituisce/Abroga', 'SUPERSEDED_BY', ARRAY['reg']),
('SUPERSEDED_BY', 'regulatory', 'Sostituito da', 'SUPERSEDES', ARRAY['reg']),

-- GEOGRAFICI
('LOCATED_IN', 'geographic', 'Situato in', 'CONTAINS_LOCATION', ARRAY['geo', 'property']),
('APPLIES_IN', 'geographic', 'Si applica in', NULL, ARRAY['reg', 'tax']),

-- TEMPORALI (per workflow)
('PRECEDES', 'temporal', 'Precede (step)', 'FOLLOWS', ARRAY['legal']),
('FOLLOWS', 'temporal', 'Segue (step)', 'PRECEDES', ARRAY['legal']),

-- PROPRIETÀ
('CAN_HOLD', 'property', 'Può detenere', 'HELD_BY', ARRAY['legal', 'visa']),
('HELD_BY', 'property', 'Detenuto da', 'CAN_HOLD', ARRAY['property']);
```

---

## PARTE 3: MODELLAZIONE PER DOMINIO

### 3.1 DOMINIO: Regolamenti (300+ Leggi)

**Struttura Gerarchica Normativa Indonesiana:**

```
UU (Undang-Undang)                    ← Leggi del Parlamento
  └── PP (Peraturan Pemerintah)       ← Regolamenti Governativi
       └── Perpres (Peraturan Presiden) ← Decreti Presidenziali
            └── Permen (Peraturan Menteri) ← Regolamenti Ministeriali
                 └── Perda (Peraturan Daerah) ← Regolamenti Regionali
                      └── SE (Surat Edaran)    ← Circolari
```

**Nodi Regolamento:**

```python
# Esempio: UU 40/2007 (Perseroan Terbatas)
{
    "id": "reg:uu:40_2007",
    "domain": "reg",
    "entity_type": "uu",
    "name": "Undang-Undang Nomor 40 Tahun 2007 tentang Perseroan Terbatas",
    "name_short": "UU PT",
    "properties": {
        "reg_number": "40",
        "reg_year": 2007,
        "enacted_date": "2007-08-16",
        "issuing_authority": "DPR RI",
        "subject_tags": ["perseroan", "pt", "modal", "saham", "direksi", "komisaris"],
        "key_articles": {
            "pasal_1": "Definisi PT",
            "pasal_7": "Pendirian PT",
            "pasal_32": "Modal Dasar"
        }
    }
}
```

**Relazioni Regolamento:**

```
reg:uu:40_2007 --[GOVERNS]--> legal:entity:pt_pmdn
reg:uu:40_2007 --[GOVERNS]--> legal:entity:pt_pma
reg:uu:25_2007 --[GOVERNS]--> legal:entity:pt_pma  (UU Penanaman Modal)
reg:pp:29_2016 --[AMENDS]--> reg:uu:40_2007 (Modal Dasar)
reg:perpres:10_2021 --[GOVERNED_BY]--> reg:uu:25_2007
```

### 3.2 DOMINIO: KBLI & Business

**Pattern "Scale Explosion":**
Ogni codice KBLI viene espanso in varianti per scala, perché rischio e permessi dipendono dalla scala.

```python
# Input: KBLI 47111
{
    "kode": "47111",
    "judul": "Perdagangan Eceran Berbagai Macam Barang yang Utamanya Makanan...",
    "sektor_id": "G",
    "per_skala": {
        "mikro": {"tingkat_risiko": "RENDAH", "perizinan": "NIB"},
        "kecil": {"tingkat_risiko": "RENDAH", "perizinan": "NIB"},
        "menengah": {"tingkat_risiko": "MENENGAH_RENDAH", "perizinan": "NIB, Sertifikat Standar"},
        "besar": {"tingkat_risiko": "MENENGAH_TINGGI", "perizinan": "NIB, Izin"}
    },
    "pma_status": "TERBUKA",
    "pma_max_asing": 100
}

# Output: 5 Nodi
1. kbli:code:47111           (Padre - dati comuni)
2. kbli:variant:47111_mikro  (Rischio RENDAH)
3. kbli:variant:47111_kecil  (Rischio RENDAH)
4. kbli:variant:47111_menengah (Rischio MENENGAH_RENDAH)
5. kbli:variant:47111_besar  (Rischio MENENGAH_TINGGI)

# Relazioni generate:
kbli:code:47111 --[HAS_VARIANT]--> kbli:variant:47111_mikro
kbli:code:47111 --[HAS_VARIANT]--> kbli:variant:47111_kecil
kbli:code:47111 --[HAS_VARIANT]--> kbli:variant:47111_menengah
kbli:code:47111 --[HAS_VARIANT]--> kbli:variant:47111_besar

kbli:variant:47111_mikro --[REQUIRES]--> legal:permit:nib
kbli:variant:47111_besar --[REQUIRES]--> legal:permit:nib
kbli:variant:47111_besar --[REQUIRES]--> legal:permit:izin

kbli:code:47111 --[BELONGS_TO]--> kbli:class:4711
kbli:class:4711 --[BELONGS_TO]--> kbli:group:471
kbli:group:471 --[BELONGS_TO]--> kbli:division:47
kbli:division:47 --[BELONGS_TO]--> kbli:section:g

kbli:code:47111 --[GOVERNED_BY]--> reg:pp:28_2025
```

**PMA Status Modeling:**

```python
# TERBUKA (100% foreign OK)
kbli:code:47111.properties = {
    "pma_status": "TERBUKA",
    "pma_max_equity": 100,
    "pma_conditions": null
}
legal:entity:pt_pma --[OPERATES {access: "FULL"}]--> kbli:code:47111

# TERBATAS (Conditional)
kbli:code:50111.properties = {
    "pma_status": "TERBATAS",
    "pma_max_equity": 49,
    "pma_conditions": ["local_partner_required", "technology_transfer"]
}
legal:entity:pt_pma --[OPERATES {access: "RESTRICTED", max_equity: 49}]--> kbli:code:50111

# TERTUTUP (Closed)
kbli:code:01131.properties = {
    "pma_status": "TERTUTUP",
    "pma_max_equity": 0,
    "pma_conditions": null
}
kbli:code:01131 --[BLOCKED_BY]--> reg:perpres:10_2021
# NO edge from pt_pma to this KBLI

# PRIORITAS (Incentives)
kbli:code:62011.properties = {
    "pma_status": "TERBUKA",
    "pma_max_equity": 100,
    "pma_prioritas": true,
    "incentives": ["tax_holiday", "super_deduction"]
}
kbli:code:62011 --[ELIGIBLE_FOR]--> tax:incentive:tax_holiday
```

### 3.3 DOMINIO: Immigration

**Entity Types:**

```
visa:type:*          - Tipi di visa (KITAS, KITAP, B211, VOA, etc.)
visa:category:*      - Categorie (investor, worker, spouse, retirement)
visa:sponsor:*       - Tipi sponsor (company, spouse, agent, self)
visa:document:*      - Documenti richiesti (passport, photo, sktt)
```

**Visa Modeling:**

```python
# KITAS Investor
{
    "id": "visa:type:kitas_investor",
    "domain": "visa",
    "entity_type": "visa_type",
    "name": "KITAS Investor",
    "name_id": "Kartu Izin Tinggal Terbatas - Investor",
    "properties": {
        "category": "investor",
        "duration_months": 24,
        "extendable": true,
        "max_extensions": 4,
        "allows_work": true,
        "allows_business": true,
        "min_investment_usd": 1200000,
        "min_investment_idr": 10000000000,
        "requires_pt_pma": true,
        "requires_director_position": true
    }
}

# Relazioni
visa:type:kitas_investor --[REQUIRES]--> visa:document:passport
visa:type:kitas_investor --[REQUIRES]--> visa:document:photo_4x6
visa:type:kitas_investor --[REQUIRES]--> visa:document:sponsor_letter
visa:type:kitas_investor --[REQUIRES]--> visa:document:investment_proof

visa:type:kitas_investor --[REQUIRES]--> visa:sponsor:company
visa:sponsor:company --[REQUIRES]--> legal:entity:pt_pma

visa:type:kitas_investor --[ENABLES]--> legal:role:director
visa:type:kitas_investor --[ENABLES]--> legal:role:commissioner

# Conversion path
visa:type:b211_business --[CONVERTS_TO {after_months: 6}]--> visa:type:kitas_investor
visa:type:kitas_investor --[CONVERTS_TO {after_years: 5}]--> visa:type:kitap

# Governance
visa:type:kitas_investor --[GOVERNED_BY]--> reg:uu:6_2011  (UU Keimigrasian)
visa:type:kitas_investor --[GOVERNED_BY]--> reg:pp:31_2013
```

**Cross-Domain: Visa ↔ KBLI:**

```
# Un investor straniero può operare certi KBLI solo con KITAS Investor
visa:type:kitas_investor --[ENABLES]--> legal:entity:pt_pma
legal:entity:pt_pma --[OPERATES]--> kbli:code:* (filtered by pma_status)

# Query: "Quali KBLI può operare un KITAS Investor?"
# Traversal: visa:kitas_investor → pt_pma → KBLI (where pma_status != TERTUTUP)
```

### 3.4 DOMINIO: Tax

**Entity Types:**

```
tax:type:*           - Tipi imposta (pph_21, pph_23, pph_badan, ppn)
tax:rate:*           - Aliquote (pph_badan_22_percent)
tax:incentive:*      - Incentivi (tax_holiday, super_deduction)
tax:obligation:*     - Obblighi dichiarativi (spt_tahunan, spt_masa_ppn)
tax:treaty:*         - Trattati (dta_singapore, dta_netherlands)
```

**Tax Modeling:**

```python
# PPh Badan (Corporate Income Tax)
{
    "id": "tax:type:pph_badan",
    "domain": "tax",
    "entity_type": "tax_type",
    "name": "Pajak Penghasilan Badan",
    "name_en": "Corporate Income Tax",
    "properties": {
        "applies_to": ["pt_pma", "pt_pmdn", "cv", "firma"],
        "base": "net_income",
        "filing_frequency": "annual",
        "filing_deadline": "April 30"
    }
}

# Aliquote (possono cambiare nel tempo)
{
    "id": "tax:rate:pph_badan_2024",
    "domain": "tax",
    "entity_type": "tax_rate",
    "name": "PPh Badan Rate 2024",
    "properties": {
        "rate_percent": 22,
        "valid_from": "2024-01-01",
        "valid_to": null,
        "conditions": {
            "public_company_discount": 3,  # 19% se quotata
            "sme_rate": 0.5  # 0.5% su fatturato se < 4.8M IDR
        }
    }
}

# Relazioni
tax:type:pph_badan --[HAS_RATE]--> tax:rate:pph_badan_2024
legal:entity:pt_pma --[TAX_OBLIGATION]--> tax:type:pph_badan
legal:entity:pt_pma --[TAX_OBLIGATION]--> tax:type:ppn
legal:entity:pt_pma --[TAX_OBLIGATION]--> tax:type:pph_21  (withholding employees)

# Incentivi
tax:incentive:tax_holiday --[REDUCES {percent: 100, years: 5}]--> tax:type:pph_badan
kbli:code:62011 --[ELIGIBLE_FOR]--> tax:incentive:tax_holiday
geo:zone:kek_mandalika --[ELIGIBLE_FOR]--> tax:incentive:tax_holiday

# Treaty
tax:treaty:dta_singapore --[REDUCES {type: "withholding", new_rate: 10}]--> tax:type:pph_26
```

### 3.5 DOMINIO: Property

**Entity Types:**

```
property:right:*     - Diritti (hak_milik, hgb, hgu, hak_pakai, strata)
property:zone:*      - Zone (residential, commercial, industrial, tourism)
property:structure:* - Strutture ownership (direct, nominee, pt_pma, leasehold)
```

**Property Modeling:**

```python
# HGB (Hak Guna Bangunan)
{
    "id": "property:right:hgb",
    "domain": "property",
    "entity_type": "property_right",
    "name": "Hak Guna Bangunan",
    "name_en": "Right to Build",
    "properties": {
        "max_duration_years": 30,
        "extendable": true,
        "max_extension_years": 20,
        "renewable": true,
        "available_to_foreigner": false,
        "available_to_pt_pma": true,
        "registrable": true
    }
}

# Relazioni
property:right:hgb --[CAN_HOLD]--> legal:entity:pt_pma
property:right:hgb --[CAN_HOLD]--> legal:entity:pt_pmdn
property:right:hgb --[EXCLUDED_FOR]--> legal:actor:foreigner_individual

property:right:hak_milik --[CAN_HOLD]--> legal:actor:indonesian_citizen
property:right:hak_milik --[EXCLUDED_FOR]--> legal:entity:pt_pma
property:right:hak_milik --[EXCLUDED_FOR]--> legal:actor:foreigner_individual

property:right:hak_pakai --[CAN_HOLD]--> legal:actor:foreigner_individual
property:right:hak_pakai --[RESTRICTED_IN {max_years: 25}]--> geo:province:bali

# Zone restrictions
property:zone:pink_zone_bali --[BLOCKED_BY]--> reg:ingub:6_2025
kbli:code:55101 --[RESTRICTED_IN]--> property:zone:pink_zone_bali  (hotel moratorium)

# Governance
property:right:hgb --[GOVERNED_BY]--> reg:uu:5_1960  (UUPA)
property:right:hgb --[GOVERNED_BY]--> reg:pp:18_2021
```

---

## PARTE 4: CROSS-DOMAIN GRAPH

### 4.1 Il "Super Traversal" - Esempio Completo

**Query**: "Cittadino australiano con $50.000 vuole aprire un coffee shop a Bali"

```
                                    START
                                      │
                                      ▼
                        ┌─────────────────────────────┐
                        │  legal:actor:foreigner      │
                        │  nationality: AU            │
                        │  capital_usd: 50000         │
                        └─────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
        ┌───────────────────┐               ┌───────────────────┐
        │ VISA OPTIONS      │               │ BUSINESS INTENT   │
        │                   │               │                   │
        │ visa:type:b211    │               │ "coffee shop"     │
        │ visa:type:kitas   │               │ → kbli:code:56303 │
        └───────────────────┘               └───────────────────┘
                    │                                   │
                    │                                   ▼
                    │                       ┌───────────────────┐
                    │                       │ PMA STATUS CHECK  │
                    │                       │                   │
                    │                       │ 56303.pma_status  │
                    │                       │ = TERBUKA (100%)  │
                    │                       └───────────────────┘
                    │                                   │
                    ▼                                   ▼
        ┌───────────────────┐               ┌───────────────────┐
        │ VISA REQUIREMENTS │               │ ENTITY OPTIONS    │
        │                   │               │                   │
        │ kitas_investor:   │◄──────────────│ legal:entity:     │
        │ min_invest: $1.2M │   ENABLES     │ pt_pma            │
        │                   │               │ min_capital: 10B  │
        │ ❌ $50K < $1.2M   │               │ IDR               │
        └───────────────────┘               └───────────────────┘
                    │                                   │
                    │                                   │
                    ▼                                   ▼
        ┌───────────────────┐               ┌───────────────────┐
        │ CAPITAL CHECK     │               │ LOCATION CHECK    │
        │                   │               │                   │
        │ $50K = ~800M IDR  │               │ geo:province:bali │
        │ Required: 10B IDR │               │                   │
        │                   │               │ Check RESTRICTED  │
        │ ❌ INSUFFICIENT   │               │ edges for 56303   │
        └───────────────────┘               └───────────────────┘
                                                        │
                                                        ▼
                                            ┌───────────────────┐
                                            │ ZONE RESTRICTIONS │
                                            │                   │
                                            │ 56303 (Kedai Kopi)│
                                            │ → No moratorium   │
                                            │ → ✅ ALLOWED      │
                                            └───────────────────┘
                                                        │
                                                        ▼
                                            ┌───────────────────┐
                                            │     VERDICT       │
                                            │                   │
                                            │ ❌ BLOCKED        │
                                            │                   │
                                            │ Reason: Capital   │
                                            │ insufficient for  │
                                            │ PT PMA ($50K vs   │
                                            │ $650K required)   │
                                            │                   │
                                            │ ALTERNATIVES:     │
                                            │ 1. Local partner  │
                                            │ 2. Franchise      │
                                            │ 3. Increase capital│
                                            └───────────────────┘
```

### 4.2 Edge Properties per Condizioni Complesse

```python
# Invece di creare nodi condizione, usa edge properties

# Caso 1: Equity restriction
{
    "source_id": "legal:entity:pt_pma",
    "target_id": "kbli:code:50111",
    "relationship_type": "OPERATES",
    "properties": {
        "access_type": "RESTRICTED",
        "max_foreign_equity_percent": 49,
        "requires_local_partner": True,
        "technology_transfer_required": True
    },
    "source_regulation": "reg:perpres:49_2021",
    "article_reference": "Lampiran III No. 45"
}

# Caso 2: Zone-specific restriction
{
    "source_id": "kbli:code:55101",
    "target_id": "geo:zone:bali_pink_zone",
    "relationship_type": "RESTRICTED_IN",
    "properties": {
        "restriction_type": "MORATORIUM",
        "effective_date": "2025-01-01",
        "review_date": "2027-01-01"
    },
    "source_regulation": "reg:ingub:6_2025",
    "article_reference": "Pasal 3"
}

# Caso 3: Conditional tax incentive
{
    "source_id": "kbli:code:62011",
    "target_id": "tax:incentive:tax_holiday",
    "relationship_type": "ELIGIBLE_FOR",
    "properties": {
        "min_investment_idr": 500000000000,  # 500B
        "duration_options": {
            "5_years": {"min": 500000000000},
            "10_years": {"min": 1000000000000},
            "20_years": {"min": 5000000000000}
        },
        "location_bonus": ["kek", "special_zone"]
    },
    "source_regulation": "reg:pmk:130_2020"
}
```

---

## PARTE 5: IMPLEMENTAZIONE

### 5.1 Struttura Progetto

```
apps/backend-rag/
├── backend/
│   ├── services/
│   │   ├── kg/
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # Dataclasses per Node, Edge
│   │   │   ├── repository.py       # CRUD operations
│   │   │   ├── pathfinder.py       # Graph traversal engine
│   │   │   └── hybrid_retrieval.py # Qdrant + KG orchestration
│   │   └── rag/
│   │       └── ... (existing)
│   └── migrations/
│       ├── migration_030_kg_schema_v2.py
│       └── migration_031_relationship_types.py
│
├── scripts/
│   └── ingestion/
│       ├── kg/
│       │   ├── ingest_regulations.py
│       │   ├── ingest_kbli_2025.py
│       │   ├── ingest_visa.py
│       │   ├── ingest_tax.py
│       │   └── ingest_property.py
│       └── validators/
│           └── validate_kg_integrity.py
```

### 5.2 Core Models

```python
# apps/backend-rag/backend/services/kg/models.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from enum import Enum

class Domain(str, Enum):
    REG = "reg"
    KBLI = "kbli"
    VISA = "visa"
    TAX = "tax"
    LEGAL = "legal"
    PROPERTY = "property"
    GEO = "geo"

class RelationshipCategory(str, Enum):
    STRUCTURAL = "structural"
    REQUIREMENT = "requirement"
    ENABLEMENT = "enablement"
    RESTRICTION = "restriction"
    FISCAL = "fiscal"
    REGULATORY = "regulatory"
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"
    PROPERTY = "property"

@dataclass
class KGNode:
    """Rappresenta un nodo nel Knowledge Graph."""
    id: str                                    # URN: 'kbli:code:47111'
    domain: Domain
    entity_type: str
    name: str
    name_id: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    source_document: Optional[str] = None
    confidence: float = 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_urn(cls, urn: str) -> 'KGNode':
        """Parse URN to extract domain and type."""
        parts = urn.split(":")
        if len(parts) < 3:
            raise ValueError(f"Invalid URN format: {urn}")
        return cls(
            id=urn,
            domain=Domain(parts[0]),
            entity_type=parts[1],
            name=parts[2]  # placeholder, should be set properly
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain.value,
            "entity_type": self.entity_type,
            "name": self.name,
            "name_id": self.name_id,
            "name_en": self.name_en,
            "description": self.description,
            "properties": self.properties,
            "source_document": self.source_document,
            "confidence": self.confidence
        }

@dataclass
class KGEdge:
    """Rappresenta un arco nel Knowledge Graph."""
    source_id: str
    target_id: str
    relationship_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    source_regulation: Optional[str] = None
    article_reference: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @property
    def is_active(self) -> bool:
        """Check if edge is currently valid."""
        if self.valid_to is None:
            return True
        return self.valid_to > date.today()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "properties": self.properties,
            "weight": self.weight,
            "source_regulation": self.source_regulation,
            "article_reference": self.article_reference,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None
        }

@dataclass
class TraversalResult:
    """Risultato di un graph traversal."""
    path: List[str]                            # Sequenza di node IDs
    nodes: Dict[str, KGNode]                   # Nodi nel path
    edges: List[KGEdge]                        # Archi attraversati
    constraints_met: bool = True
    constraint_failures: List[str] = field(default_factory=list)
    total_weight: float = 0.0

@dataclass
class WorkflowStep:
    """Step di un workflow pre-computato."""
    step_number: int
    node_id: str
    action: str
    requirements: List[str] = field(default_factory=list)
    estimated_days: Optional[int] = None
    estimated_cost_idr: Optional[int] = None

@dataclass
class Workflow:
    """Workflow completo."""
    id: str
    name: str
    actor_type: str                            # 'foreigner', 'indonesian'
    goal_type: str                             # 'start_business', 'get_visa'
    steps: List[WorkflowStep] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    estimated_duration_days: Optional[int] = None
    estimated_cost_idr: Optional[int] = None
```

### 5.3 Repository Layer

```python
# apps/backend-rag/backend/services/kg/repository.py

import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import date
import asyncpg
from .models import KGNode, KGEdge, Domain

class KGRepository:
    """Repository per operazioni CRUD sul Knowledge Graph."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ==================== NODES ====================

    async def upsert_node(self, node: KGNode) -> str:
        """Insert or update a node."""
        query = """
            INSERT INTO kg_nodes (id, domain, entity_type, name, name_id, name_en,
                                  description, properties, source_document, confidence)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                name_id = EXCLUDED.name_id,
                name_en = EXCLUDED.name_en,
                description = EXCLUDED.description,
                properties = EXCLUDED.properties,
                source_document = EXCLUDED.source_document,
                confidence = EXCLUDED.confidence,
                updated_at = NOW()
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                node.id,
                node.domain.value,
                node.entity_type,
                node.name,
                node.name_id,
                node.name_en,
                node.description,
                json.dumps(node.properties),
                node.source_document,
                node.confidence
            )
            return result

    async def upsert_nodes_batch(self, nodes: List[KGNode]) -> int:
        """Batch insert/update nodes."""
        query = """
            INSERT INTO kg_nodes (id, domain, entity_type, name, name_id, name_en,
                                  description, properties, source_document, confidence)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                properties = kg_nodes.properties || EXCLUDED.properties,
                updated_at = NOW()
        """
        async with self.pool.acquire() as conn:
            await conn.executemany(
                query,
                [(n.id, n.domain.value, n.entity_type, n.name, n.name_id, n.name_en,
                  n.description, json.dumps(n.properties), n.source_document, n.confidence)
                 for n in nodes]
            )
            return len(nodes)

    async def get_node(self, node_id: str) -> Optional[KGNode]:
        """Get a node by ID."""
        query = "SELECT * FROM kg_nodes WHERE id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, node_id)
            if row:
                return self._row_to_node(row)
            return None

    async def get_nodes_by_domain(self, domain: Domain,
                                   entity_type: Optional[str] = None) -> List[KGNode]:
        """Get all nodes in a domain, optionally filtered by type."""
        if entity_type:
            query = "SELECT * FROM kg_nodes WHERE domain = $1 AND entity_type = $2"
            params = [domain.value, entity_type]
        else:
            query = "SELECT * FROM kg_nodes WHERE domain = $1"
            params = [domain.value]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_node(row) for row in rows]

    async def search_nodes(self, query: str, domain: Optional[Domain] = None,
                           limit: int = 20) -> List[KGNode]:
        """Fuzzy search nodes by name."""
        sql = """
            SELECT *, similarity(name, $1) as sim
            FROM kg_nodes
            WHERE name % $1
        """
        params = [query]

        if domain:
            sql += " AND domain = $2"
            params.append(domain.value)

        sql += " ORDER BY sim DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [self._row_to_node(row) for row in rows]

    # ==================== EDGES ====================

    async def create_edge(self, edge: KGEdge) -> str:
        """Create a new edge."""
        query = """
            INSERT INTO kg_edges (source_id, target_id, relationship_type, properties,
                                  weight, source_regulation, article_reference,
                                  valid_from, valid_to)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                edge.source_id,
                edge.target_id,
                edge.relationship_type,
                json.dumps(edge.properties),
                edge.weight,
                edge.source_regulation,
                edge.article_reference,
                edge.valid_from or date.today(),
                edge.valid_to
            )
            return str(result)

    async def create_edges_batch(self, edges: List[KGEdge]) -> int:
        """Batch create edges."""
        query = """
            INSERT INTO kg_edges (source_id, target_id, relationship_type, properties,
                                  weight, source_regulation, article_reference, valid_from)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT DO NOTHING
        """
        async with self.pool.acquire() as conn:
            await conn.executemany(
                query,
                [(e.source_id, e.target_id, e.relationship_type, json.dumps(e.properties),
                  e.weight, e.source_regulation, e.article_reference,
                  e.valid_from or date.today())
                 for e in edges]
            )
            return len(edges)

    async def get_outgoing_edges(self, node_id: str,
                                  relationship_type: Optional[str] = None,
                                  active_only: bool = True) -> List[KGEdge]:
        """Get all edges originating from a node."""
        if active_only:
            base = "SELECT * FROM kg_active_edges WHERE source_id = $1"
        else:
            base = "SELECT * FROM kg_edges WHERE source_id = $1"

        if relationship_type:
            base += " AND relationship_type = $2"
            params = [node_id, relationship_type]
        else:
            params = [node_id]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(base, *params)
            return [self._row_to_edge(row) for row in rows]

    async def get_incoming_edges(self, node_id: str,
                                  relationship_type: Optional[str] = None,
                                  active_only: bool = True) -> List[KGEdge]:
        """Get all edges pointing to a node."""
        if active_only:
            base = "SELECT * FROM kg_active_edges WHERE target_id = $1"
        else:
            base = "SELECT * FROM kg_edges WHERE target_id = $1"

        if relationship_type:
            base += " AND relationship_type = $2"
            params = [node_id, relationship_type]
        else:
            params = [node_id]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(base, *params)
            return [self._row_to_edge(row) for row in rows]

    # ==================== TRAVERSAL ====================

    async def get_neighbors(self, node_id: str, depth: int = 1,
                            direction: str = "both") -> Dict[str, Any]:
        """Get neighborhood subgraph up to specified depth."""
        # Recursive CTE for multi-hop traversal
        query = """
            WITH RECURSIVE neighborhood AS (
                -- Base case: starting node
                SELECT
                    id, domain, entity_type, name, properties,
                    0 as depth,
                    ARRAY[id] as path
                FROM kg_nodes
                WHERE id = $1

                UNION ALL

                -- Recursive case: neighbors
                SELECT
                    n.id, n.domain, n.entity_type, n.name, n.properties,
                    nb.depth + 1,
                    nb.path || n.id
                FROM neighborhood nb
                JOIN kg_active_edges e ON (
                    CASE
                        WHEN $3 = 'outgoing' THEN e.source_id = nb.id
                        WHEN $3 = 'incoming' THEN e.target_id = nb.id
                        ELSE e.source_id = nb.id OR e.target_id = nb.id
                    END
                )
                JOIN kg_nodes n ON (
                    CASE
                        WHEN e.source_id = nb.id THEN n.id = e.target_id
                        ELSE n.id = e.source_id
                    END
                )
                WHERE nb.depth < $2
                AND NOT n.id = ANY(nb.path)  -- Prevent cycles
            )
            SELECT DISTINCT id, domain, entity_type, name, properties, depth
            FROM neighborhood
            ORDER BY depth, id
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, node_id, depth, direction)

            nodes = {}
            for row in rows:
                nodes[row['id']] = {
                    'id': row['id'],
                    'domain': row['domain'],
                    'entity_type': row['entity_type'],
                    'name': row['name'],
                    'properties': json.loads(row['properties']) if row['properties'] else {},
                    'depth': row['depth']
                }

            # Get edges between these nodes
            node_ids = list(nodes.keys())
            edge_query = """
                SELECT * FROM kg_active_edges
                WHERE source_id = ANY($1) AND target_id = ANY($1)
            """
            edge_rows = await conn.fetch(edge_query, node_ids)
            edges = [self._row_to_edge(row).to_dict() for row in edge_rows]

            return {"nodes": nodes, "edges": edges}

    async def find_path(self, start_id: str, end_id: str,
                        max_depth: int = 5) -> Optional[List[str]]:
        """Find shortest path between two nodes."""
        query = """
            WITH RECURSIVE path_search AS (
                SELECT
                    $1::text as current_node,
                    ARRAY[$1::text] as path,
                    0 as depth

                UNION ALL

                SELECT
                    e.target_id,
                    ps.path || e.target_id,
                    ps.depth + 1
                FROM path_search ps
                JOIN kg_active_edges e ON e.source_id = ps.current_node
                WHERE ps.depth < $3
                AND NOT e.target_id = ANY(ps.path)
            )
            SELECT path
            FROM path_search
            WHERE current_node = $2
            ORDER BY array_length(path, 1)
            LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, start_id, end_id, max_depth)
            return row['path'] if row else None

    # ==================== HELPERS ====================

    def _row_to_node(self, row) -> KGNode:
        return KGNode(
            id=row['id'],
            domain=Domain(row['domain']),
            entity_type=row['entity_type'],
            name=row['name'],
            name_id=row.get('name_id'),
            name_en=row.get('name_en'),
            description=row.get('description'),
            properties=json.loads(row['properties']) if row['properties'] else {},
            source_document=row.get('source_document'),
            confidence=row.get('confidence', 1.0),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

    def _row_to_edge(self, row) -> KGEdge:
        return KGEdge(
            source_id=row['source_id'],
            target_id=row['target_id'],
            relationship_type=row['relationship_type'],
            properties=json.loads(row['properties']) if row['properties'] else {},
            weight=row.get('weight', 1.0),
            source_regulation=row.get('source_regulation'),
            article_reference=row.get('article_reference'),
            valid_from=row.get('valid_from'),
            valid_to=row.get('valid_to')
        )
```

### 5.4 GraphPathfinder Engine

```python
# apps/backend-rag/backend/services/kg/pathfinder.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging

from .models import KGNode, KGEdge, TraversalResult, Domain
from .repository import KGRepository

logger = logging.getLogger(__name__)

class ActorType(str, Enum):
    FOREIGNER = "foreigner"
    INDONESIAN = "indonesian"
    COMPANY_FOREIGN = "company_foreign"
    COMPANY_LOCAL = "company_local"

@dataclass
class QueryContext:
    """Contesto dell'utente che effettua la query."""
    actor_type: ActorType
    nationality: Optional[str] = None
    capital_usd: Optional[float] = None
    capital_idr: Optional[float] = None
    target_location: Optional[str] = None  # geo:province:bali
    target_activity: Optional[str] = None  # kbli:code:56303
    existing_visa: Optional[str] = None
    existing_entity: Optional[str] = None

    @property
    def capital_idr_computed(self) -> float:
        """Compute IDR capital (assume 1 USD = 16000 IDR)."""
        if self.capital_idr:
            return self.capital_idr
        if self.capital_usd:
            return self.capital_usd * 16000
        return 0

class GraphPathfinder:
    """
    Motore di traversal per il Knowledge Graph.

    Implementa backward chaining: parte dal goal e risale alle precondizioni.
    """

    # Costanti di business
    PMA_MIN_CAPITAL_IDR = 10_000_000_000  # 10 Milyar
    KITAS_INVESTOR_MIN_USD = 1_200_000     # $1.2M (o equivalente in IDR 10B)

    def __init__(self, repository: KGRepository):
        self.repo = repository

    async def solve(self, context: QueryContext) -> Dict[str, Any]:
        """
        Risolve il workflow completo per il contesto dato.

        Returns:
            {
                "status": "SUCCESS" | "BLOCKED" | "PARTIAL",
                "path": [...],
                "requirements": {...},
                "blockers": [...],
                "alternatives": [...]
            }
        """
        result = {
            "status": "SUCCESS",
            "path": [],
            "requirements": {},
            "blockers": [],
            "alternatives": [],
            "warnings": []
        }

        # Step 1: Validate target activity (KBLI)
        if context.target_activity:
            kbli_check = await self._check_kbli_eligibility(context)
            if kbli_check["blocked"]:
                result["status"] = "BLOCKED"
                result["blockers"].append(kbli_check)
                result["alternatives"] = await self._find_alternatives(context)
                return result
            result["path"].append({"step": "kbli", "details": kbli_check})

        # Step 2: Check location restrictions
        if context.target_location:
            location_check = await self._check_location_restrictions(context)
            if location_check["blocked"]:
                result["status"] = "BLOCKED"
                result["blockers"].append(location_check)
                return result
            result["path"].append({"step": "location", "details": location_check})

        # Step 3: Determine required entity type
        entity_check = await self._determine_entity_type(context)
        result["path"].append({"step": "entity", "details": entity_check})

        if entity_check.get("blocked"):
            result["status"] = "BLOCKED"
            result["blockers"].append(entity_check)
            return result

        # Step 4: Check capital requirements
        capital_check = await self._check_capital_requirements(context, entity_check)
        if capital_check.get("blocked"):
            result["status"] = "BLOCKED"
            result["blockers"].append(capital_check)
            result["alternatives"] = await self._find_capital_alternatives(context)
            return result
        result["path"].append({"step": "capital", "details": capital_check})

        # Step 5: Determine visa requirements
        visa_check = await self._determine_visa_requirements(context, entity_check)
        result["path"].append({"step": "visa", "details": visa_check})

        if visa_check.get("warnings"):
            result["warnings"].extend(visa_check["warnings"])

        # Step 6: Collect all permits required
        permits = await self._collect_required_permits(context)
        result["requirements"]["permits"] = permits

        # Step 7: Calculate tax obligations
        tax_obligations = await self._calculate_tax_obligations(context, entity_check)
        result["requirements"]["tax"] = tax_obligations

        return result

    async def _check_kbli_eligibility(self, context: QueryContext) -> Dict[str, Any]:
        """Check if the KBLI code is accessible to the actor."""
        kbli_node = await self.repo.get_node(context.target_activity)

        if not kbli_node:
            return {"blocked": True, "reason": f"KBLI code not found: {context.target_activity}"}

        props = kbli_node.properties
        pma_status = props.get("pma_status", "TERBUKA")

        # Foreigner check
        if context.actor_type == ActorType.FOREIGNER:
            if pma_status == "TERTUTUP":
                # Check for BLOCKED_BY edges
                blocked_edges = await self.repo.get_outgoing_edges(
                    context.target_activity, "BLOCKED_BY"
                )
                blocking_regs = [e.source_regulation for e in blocked_edges]

                return {
                    "blocked": True,
                    "reason": "KBLI closed to foreign investment (TERTUTUP)",
                    "pma_status": pma_status,
                    "blocking_regulations": blocking_regs
                }

            elif pma_status == "TERBATAS":
                max_equity = props.get("pma_max_asing", props.get("pma_max_equity", 49))
                conditions = props.get("pma_kondisi", [])

                return {
                    "blocked": False,
                    "pma_status": pma_status,
                    "max_foreign_equity": max_equity,
                    "conditions": conditions,
                    "requires_local_partner": max_equity < 100,
                    "warning": f"Foreign ownership limited to {max_equity}%"
                }

        # Check for priority/incentives
        incentives = []
        if props.get("pma_prioritas"):
            eligible_edges = await self.repo.get_outgoing_edges(
                context.target_activity, "ELIGIBLE_FOR"
            )
            incentives = [e.target_id for e in eligible_edges]

        return {
            "blocked": False,
            "pma_status": pma_status,
            "max_foreign_equity": props.get("pma_max_asing", 100),
            "available_incentives": incentives,
            "kbli_name": kbli_node.name
        }

    async def _check_location_restrictions(self, context: QueryContext) -> Dict[str, Any]:
        """Check if target activity is restricted in the location."""
        if not context.target_activity or not context.target_location:
            return {"blocked": False}

        # Check RESTRICTED_IN edges from KBLI to location
        restricted_edges = await self.repo.get_outgoing_edges(
            context.target_activity, "RESTRICTED_IN"
        )

        for edge in restricted_edges:
            # Check if restriction applies to target location
            if context.target_location in edge.target_id or edge.target_id in context.target_location:
                return {
                    "blocked": True,
                    "reason": "Activity restricted in this location",
                    "restriction_type": edge.properties.get("restriction_type", "MORATORIUM"),
                    "source_regulation": edge.source_regulation,
                    "details": edge.properties
                }

        return {"blocked": False, "location": context.target_location}

    async def _determine_entity_type(self, context: QueryContext) -> Dict[str, Any]:
        """Determine which legal entity type is required."""
        if context.actor_type == ActorType.FOREIGNER:
            # Foreigners must use PT PMA for business
            pt_pma = await self.repo.get_node("legal:entity:pt_pma")

            return {
                "blocked": False,
                "required_entity": "legal:entity:pt_pma",
                "entity_name": "PT PMA (Perseroan Terbatas Penanaman Modal Asing)",
                "reason": "Foreign nationals must establish PT PMA for business activities",
                "min_capital_idr": self.PMA_MIN_CAPITAL_IDR,
                "min_capital_usd_approx": self.PMA_MIN_CAPITAL_IDR / 16000
            }

        elif context.actor_type == ActorType.INDONESIAN:
            # Indonesians can choose various structures
            return {
                "blocked": False,
                "available_entities": [
                    {"id": "legal:entity:pt_pmdn", "name": "PT PMDN", "min_capital": 50_000_000},
                    {"id": "legal:entity:cv", "name": "CV (Commanditaire Vennootschap)", "min_capital": 0},
                    {"id": "legal:entity:ud", "name": "UD (Usaha Dagang)", "min_capital": 0},
                    {"id": "legal:entity:pt_perorangan", "name": "PT Perorangan", "min_capital": 0}
                ],
                "recommendation": "legal:entity:pt_pmdn" if context.capital_idr_computed > 50_000_000 else "legal:entity:cv"
            }

        return {"blocked": False, "required_entity": None}

    async def _check_capital_requirements(self, context: QueryContext,
                                          entity_check: Dict[str, Any]) -> Dict[str, Any]:
        """Check if user has sufficient capital."""
        user_capital = context.capital_idr_computed

        if context.actor_type == ActorType.FOREIGNER:
            required = self.PMA_MIN_CAPITAL_IDR

            if user_capital < required:
                shortfall = required - user_capital
                return {
                    "blocked": True,
                    "reason": "Insufficient capital for PT PMA",
                    "required_idr": required,
                    "available_idr": user_capital,
                    "shortfall_idr": shortfall,
                    "shortfall_usd_approx": shortfall / 16000
                }

        return {
            "blocked": False,
            "capital_sufficient": True,
            "available_idr": user_capital
        }

    async def _determine_visa_requirements(self, context: QueryContext,
                                            entity_check: Dict[str, Any]) -> Dict[str, Any]:
        """Determine which visa is needed."""
        if context.actor_type != ActorType.FOREIGNER:
            return {"visa_required": False}

        result = {
            "visa_required": True,
            "recommended_visa": None,
            "alternative_visas": [],
            "warnings": []
        }

        # Get available visas that ENABLE the required entity
        required_entity = entity_check.get("required_entity")
        if required_entity:
            enabling_edges = await self.repo.get_incoming_edges(required_entity, "ENABLES")

            for edge in enabling_edges:
                visa_node = await self.repo.get_node(edge.source_id)
                if visa_node and visa_node.domain == Domain.VISA:
                    visa_info = {
                        "id": visa_node.id,
                        "name": visa_node.name,
                        "properties": visa_node.properties
                    }

                    # Check if user meets visa requirements
                    min_investment = visa_node.properties.get("min_investment_idr", 0)
                    if context.capital_idr_computed >= min_investment:
                        if not result["recommended_visa"]:
                            result["recommended_visa"] = visa_info
                        else:
                            result["alternative_visas"].append(visa_info)
                    else:
                        result["warnings"].append(
                            f"{visa_node.name} requires IDR {min_investment:,} investment"
                        )

        # If no visa found through entity, suggest B211 as starting point
        if not result["recommended_visa"]:
            result["recommended_visa"] = {
                "id": "visa:type:b211_business",
                "name": "B211A Business Visa",
                "properties": {"duration_days": 60, "extendable": True}
            }
            result["warnings"].append(
                "Capital insufficient for KITAS Investor. Consider starting with B211 visa."
            )

        return result

    async def _collect_required_permits(self, context: QueryContext) -> List[Dict[str, Any]]:
        """Collect all permits required for the activity."""
        permits = []

        if not context.target_activity:
            return permits

        # Get REQUIRES edges from KBLI
        require_edges = await self.repo.get_outgoing_edges(
            context.target_activity, "REQUIRES"
        )

        for edge in require_edges:
            permit_node = await self.repo.get_node(edge.target_id)
            if permit_node:
                permits.append({
                    "id": permit_node.id,
                    "name": permit_node.name,
                    "mandatory": edge.properties.get("mandatory", True),
                    "estimated_days": edge.properties.get("processing_days"),
                    "source_regulation": edge.source_regulation
                })

        # Always include NIB for business
        nib_found = any(p["id"] == "legal:permit:nib" for p in permits)
        if not nib_found:
            permits.insert(0, {
                "id": "legal:permit:nib",
                "name": "NIB (Nomor Induk Berusaha)",
                "mandatory": True,
                "estimated_days": 1,
                "note": "Required for all business activities"
            })

        return permits

    async def _calculate_tax_obligations(self, context: QueryContext,
                                          entity_check: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate tax obligations based on entity type."""
        taxes = []

        required_entity = entity_check.get("required_entity")
        if not required_entity:
            return taxes

        # Get TAX_OBLIGATION edges from entity
        tax_edges = await self.repo.get_outgoing_edges(required_entity, "TAX_OBLIGATION")

        for edge in tax_edges:
            tax_node = await self.repo.get_node(edge.target_id)
            if tax_node:
                taxes.append({
                    "id": tax_node.id,
                    "name": tax_node.name,
                    "properties": tax_node.properties,
                    "frequency": tax_node.properties.get("filing_frequency", "monthly")
                })

        return taxes

    async def _find_alternatives(self, context: QueryContext) -> List[Dict[str, Any]]:
        """Find alternative KBLI codes if main one is blocked."""
        alternatives = []

        if not context.target_activity:
            return alternatives

        # Look for PIVOT_TO edges
        pivot_edges = await self.repo.get_outgoing_edges(context.target_activity, "PIVOT_TO")

        for edge in pivot_edges:
            alt_node = await self.repo.get_node(edge.target_id)
            if alt_node:
                # Check if alternative is accessible
                alt_props = alt_node.properties
                if alt_props.get("pma_status") != "TERTUTUP":
                    alternatives.append({
                        "id": alt_node.id,
                        "name": alt_node.name,
                        "pma_status": alt_props.get("pma_status"),
                        "reason": edge.properties.get("reason", "Similar activity")
                    })

        return alternatives

    async def _find_capital_alternatives(self, context: QueryContext) -> List[Dict[str, Any]]:
        """Suggest alternatives when capital is insufficient."""
        return [
            {
                "option": "Local Partner",
                "description": "Partner with Indonesian investor to meet capital requirements",
                "your_share": "Up to 49%",
                "complexity": "Medium"
            },
            {
                "option": "Franchise",
                "description": "Operate under existing franchise license",
                "investment": "Varies by franchise",
                "complexity": "Low"
            },
            {
                "option": "Consulting",
                "description": "Work as consultant for local company on KITAS Sponsored",
                "visa": "KITAS Tenaga Kerja",
                "complexity": "Low"
            },
            {
                "option": "Increase Capital",
                "description": f"Raise additional {(self.PMA_MIN_CAPITAL_IDR - context.capital_idr_computed)/16000:,.0f} USD",
                "target": f"${self.PMA_MIN_CAPITAL_IDR/16000:,.0f} total",
                "complexity": "Depends"
            }
        ]
```

### 5.5 Hybrid Retrieval Orchestrator

```python
# apps/backend-rag/backend/services/kg/hybrid_retrieval.py

from typing import List, Dict, Any, Optional
from enum import Enum
import logging

from qdrant_client import QdrantClient
from .repository import KGRepository
from .pathfinder import GraphPathfinder, QueryContext, ActorType
from .models import Domain

logger = logging.getLogger(__name__)

class QueryIntent(str, Enum):
    FACTUAL = "factual"           # "Quali permessi per KBLI 47111?"
    SCENARIO = "scenario"          # "Posso aprire un bar a Bali con $50k?"
    EXPLORATORY = "exploratory"    # "Com'è il business a Bali?"
    PROCEDURAL = "procedural"      # "Come apro una PT PMA?"

class HybridRetriever:
    """
    Orchestrator che combina Qdrant (semantic) e PostgreSQL KG (structural).
    """

    def __init__(self,
                 qdrant_client: QdrantClient,
                 kg_repository: KGRepository,
                 pathfinder: GraphPathfinder):
        self.qdrant = qdrant_client
        self.kg = kg_repository
        self.pathfinder = pathfinder

    async def retrieve(self,
                       query: str,
                       context: Optional[QueryContext] = None,
                       intent: Optional[QueryIntent] = None) -> Dict[str, Any]:
        """
        Main retrieval method.

        1. Classify intent if not provided
        2. Route to appropriate retrieval strategy
        3. Combine and re-rank results
        """
        # Step 1: Intent classification (would use LLM in production)
        if not intent:
            intent = await self._classify_intent(query)

        logger.info(f"Query intent classified as: {intent}")

        # Step 2: Route based on intent
        if intent == QueryIntent.FACTUAL:
            return await self._factual_retrieval(query)

        elif intent == QueryIntent.SCENARIO:
            if not context:
                context = await self._extract_context(query)
            return await self._scenario_retrieval(query, context)

        elif intent == QueryIntent.PROCEDURAL:
            return await self._procedural_retrieval(query, context)

        else:  # EXPLORATORY
            return await self._exploratory_retrieval(query)

    async def _classify_intent(self, query: str) -> QueryIntent:
        """
        Classify query intent based on patterns.
        In production, use LLM for better accuracy.
        """
        query_lower = query.lower()

        # Scenario indicators
        scenario_patterns = ["can i", "posso", "is it possible", "with $", "come straniero", "as foreigner"]
        if any(p in query_lower for p in scenario_patterns):
            return QueryIntent.SCENARIO

        # Procedural indicators
        procedural_patterns = ["how to", "come faccio", "steps to", "process for", "procedure"]
        if any(p in query_lower for p in procedural_patterns):
            return QueryIntent.PROCEDURAL

        # Factual indicators (specific codes, permits, regulations)
        factual_patterns = ["kbli", "permit", "license", "requirement for", "what is", "quali"]
        if any(p in query_lower for p in factual_patterns):
            return QueryIntent.FACTUAL

        # Default to exploratory
        return QueryIntent.EXPLORATORY

    async def _extract_context(self, query: str) -> QueryContext:
        """
        Extract context from query.
        In production, use LLM with structured output.
        """
        query_lower = query.lower()

        # Detect actor type
        actor_type = ActorType.FOREIGNER if any(
            w in query_lower for w in ["foreigner", "straniero", "expat", "foreign"]
        ) else ActorType.INDONESIAN

        # Detect capital (simple pattern matching)
        import re
        capital_match = re.search(r'\$(\d+[,\d]*)', query)
        capital_usd = float(capital_match.group(1).replace(',', '')) if capital_match else None

        # Detect location
        location = None
        locations = ["bali", "jakarta", "surabaya", "yogyakarta", "bandung"]
        for loc in locations:
            if loc in query_lower:
                location = f"geo:province:{loc}"
                break

        # Detect activity (would need KBLI lookup in production)
        activity = None
        activity_keywords = {
            "restaurant": "kbli:code:56101",
            "ristorante": "kbli:code:56101",
            "coffee shop": "kbli:code:56303",
            "cafe": "kbli:code:56303",
            "hotel": "kbli:code:55101",
            "software": "kbli:code:62011",
            "retail": "kbli:code:47111"
        }
        for keyword, kbli in activity_keywords.items():
            if keyword in query_lower:
                activity = kbli
                break

        return QueryContext(
            actor_type=actor_type,
            capital_usd=capital_usd,
            target_location=location,
            target_activity=activity
        )

    async def _factual_retrieval(self, query: str) -> Dict[str, Any]:
        """
        KG-first retrieval for factual queries.
        """
        result = {
            "strategy": "factual",
            "kg_results": [],
            "qdrant_results": [],
            "combined": []
        }

        # 1. Search nodes by name
        nodes = await self.kg.search_nodes(query, limit=10)
        result["kg_results"] = [n.to_dict() for n in nodes]

        # 2. For each node, get related edges
        for node in nodes[:3]:  # Top 3
            edges = await self.kg.get_outgoing_edges(node.id)
            node_dict = node.to_dict()
            node_dict["relations"] = [e.to_dict() for e in edges]
            result["combined"].append(node_dict)

        # 3. Enrich with Qdrant if node has source_document
        for item in result["combined"]:
            if item.get("source_document"):
                # Fetch from Qdrant for full text
                doc = await self._fetch_qdrant_document(item["source_document"])
                if doc:
                    item["full_text"] = doc.get("text", "")

        return result

    async def _scenario_retrieval(self, query: str, context: QueryContext) -> Dict[str, Any]:
        """
        Hybrid retrieval for scenario queries.
        Uses Pathfinder for structured analysis.
        """
        result = {
            "strategy": "scenario",
            "context": {
                "actor": context.actor_type.value,
                "capital_usd": context.capital_usd,
                "location": context.target_location,
                "activity": context.target_activity
            },
            "pathfinder_result": None,
            "supporting_documents": []
        }

        # 1. Run pathfinder
        pathfinder_result = await self.pathfinder.solve(context)
        result["pathfinder_result"] = pathfinder_result

        # 2. Get supporting documents from Qdrant
        if context.target_activity:
            kbli_code = context.target_activity.split(":")[-1]
            docs = await self._search_qdrant(
                f"KBLI {kbli_code} requirements permits",
                collection="kbli_2025",
                limit=3
            )
            result["supporting_documents"].extend(docs)

        # 3. Get regulation documents if blocked
        if pathfinder_result.get("blockers"):
            for blocker in pathfinder_result["blockers"]:
                if blocker.get("blocking_regulations"):
                    for reg_id in blocker["blocking_regulations"]:
                        reg_docs = await self._search_qdrant(
                            reg_id,
                            collection="legal_kb",
                            limit=2
                        )
                        result["supporting_documents"].extend(reg_docs)

        return result

    async def _procedural_retrieval(self, query: str,
                                     context: Optional[QueryContext]) -> Dict[str, Any]:
        """
        Workflow-oriented retrieval.
        """
        result = {
            "strategy": "procedural",
            "workflow": None,
            "steps": [],
            "documents": []
        }

        # 1. Search for pre-computed workflows
        # (In production, would query kg_workflows table)

        # 2. Get procedural documents from Qdrant
        docs = await self._search_qdrant(
            query,
            collection="legal_kb",
            limit=5,
            filter={"document_type": "procedure"}
        )
        result["documents"] = docs

        # 3. If context provided, run pathfinder for dynamic workflow
        if context:
            pathfinder_result = await self.pathfinder.solve(context)
            result["workflow"] = pathfinder_result

        return result

    async def _exploratory_retrieval(self, query: str) -> Dict[str, Any]:
        """
        Qdrant-first retrieval for exploratory queries.
        """
        result = {
            "strategy": "exploratory",
            "documents": [],
            "related_entities": []
        }

        # 1. Broad semantic search across collections
        collections = ["legal_kb", "visa_kb", "tax_kb", "property_kb", "intel_news"]

        for collection in collections:
            docs = await self._search_qdrant(query, collection=collection, limit=3)
            result["documents"].extend(docs)

        # 2. Extract entities from top documents and get KG context
        entities_mentioned = set()
        for doc in result["documents"][:5]:
            # Simple entity extraction (would use NER in production)
            text = doc.get("text", "")
            # Look for KBLI patterns
            import re
            kbli_matches = re.findall(r'\b\d{5}\b', text)
            for kbli in kbli_matches:
                entities_mentioned.add(f"kbli:code:{kbli}")

        # 3. Get KG context for mentioned entities
        for entity_id in list(entities_mentioned)[:5]:
            node = await self.kg.get_node(entity_id)
            if node:
                result["related_entities"].append(node.to_dict())

        return result

    async def _search_qdrant(self, query: str, collection: str,
                             limit: int = 5, filter: Dict = None) -> List[Dict]:
        """Search Qdrant collection."""
        try:
            # This is simplified - in production, use proper embedding
            results = self.qdrant.search(
                collection_name=collection,
                query_text=query,  # Assumes text embedding is configured
                limit=limit,
                query_filter=filter
            )
            return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]
        except Exception as e:
            logger.warning(f"Qdrant search failed for {collection}: {e}")
            return []

    async def _fetch_qdrant_document(self, doc_id: str) -> Optional[Dict]:
        """Fetch specific document from Qdrant."""
        # Parse collection from doc_id if encoded, otherwise default
        try:
            result = self.qdrant.retrieve(
                collection_name="legal_kb",  # Default collection
                ids=[doc_id]
            )
            return result[0].payload if result else None
        except Exception as e:
            logger.warning(f"Failed to fetch document {doc_id}: {e}")
            return None
```

---

## PARTE 6: INGESTION SCRIPTS

### 6.1 KBLI 2025 Ingestion

```python
# scripts/ingestion/kg/ingest_kbli_2025.py

"""
Ingestion script per KBLI 2025 nel Knowledge Graph.

Esegue:
1. Parsing del dataset KBLI_2025_FINAL_CLEAN.json
2. Creazione nodi KBLI (codice + varianti per scala)
3. Creazione gerarchia (section → division → group → class → code)
4. Creazione archi REQUIRES verso permessi
5. Creazione archi per PMA status
6. Validazione integrità
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

import asyncpg

# Adjust import path as needed
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.services.kg.models import KGNode, KGEdge, Domain
from backend.services.kg.repository import KGRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

KBLI_FILE = Path("/Users/antonellosiano/Desktop/kbli_2025_reasoning/KBLI_2025_FINAL_CLEAN.json")
DATABASE_URL = "postgresql://user:pass@localhost:5432/nuzantara"  # Adjust

# Risk level mappings
RISK_LEVELS = {
    "RENDAH": {"id": "kbli:risk:rendah", "name": "Risiko Rendah", "level": 1},
    "MENENGAH_RENDAH": {"id": "kbli:risk:menengah_rendah", "name": "Risiko Menengah Rendah", "level": 2},
    "MENENGAH_TINGGI": {"id": "kbli:risk:menengah_tinggi", "name": "Risiko Menengah Tinggi", "level": 3},
    "TINGGI": {"id": "kbli:risk:tinggi", "name": "Risiko Tinggi", "level": 4}
}

# Section names
SECTION_NAMES = {
    "A": "Pertanian, Kehutanan dan Perikanan",
    "B": "Pertambangan dan Penggalian",
    "C": "Industri Pengolahan",
    "D": "Pengadaan Listrik, Gas, Uap/Air Panas dan Udara Dingin",
    "E": "Treatment Air, Treatment Air Limbah, Treatment dan Pemulihan Material Sampah, dan Aktivitas Remediasi",
    "F": "Konstruksi",
    "G": "Perdagangan Besar dan Eceran; Reparasi dan Perawatan Mobil dan Sepeda Motor",
    "H": "Pengangkutan dan Pergudangan",
    "I": "Penyediaan Akomodasi dan Penyediaan Makan Minum",
    "J": "Informasi dan Komunikasi",
    "K": "Aktivitas Keuangan dan Asuransi",
    "L": "Real Estat",
    "M": "Aktivitas Profesional, Ilmiah dan Teknis",
    "N": "Aktivitas Penyewaan dan Sewa Guna Usaha Tanpa Hak Opsi, Ketenagakerjaan, Agen Perjalanan dan Penunjang Usaha Lainnya",
    "O": "Administrasi Pemerintahan, Pertahanan dan Jaminan Sosial Wajib",
    "P": "Pendidikan",
    "Q": "Aktivitas Kesehatan Manusia dan Aktivitas Sosial",
    "R": "Kesenian, Hiburan dan Rekreasi",
    "S": "Aktivitas Jasa Lainnya",
    "T": "Aktivitas Rumah Tangga Sebagai Pemberi Kerja",
    "U": "Aktivitas Badan Internasional dan Badan Ekstra Internasional Lainnya"
}

# ==================== INGESTION LOGIC ====================

@dataclass
class IngestionStats:
    nodes_created: int = 0
    edges_created: int = 0
    variants_created: int = 0
    permits_linked: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

async def create_reference_nodes(repo: KGRepository) -> None:
    """Create reference nodes for risk levels, sections, etc."""
    logger.info("Creating reference nodes...")

    # Risk levels
    risk_nodes = [
        KGNode(
            id=info["id"],
            domain=Domain.KBLI,
            entity_type="risk_level",
            name=info["name"],
            name_en=f"Risk Level {info['level']}",
            properties={"level": info["level"]}
        )
        for info in RISK_LEVELS.values()
    ]
    await repo.upsert_nodes_batch(risk_nodes)

    # Sections
    section_nodes = [
        KGNode(
            id=f"kbli:section:{code.lower()}",
            domain=Domain.KBLI,
            entity_type="section",
            name=name,
            name_id=name,
            properties={"section_code": code}
        )
        for code, name in SECTION_NAMES.items()
    ]
    await repo.upsert_nodes_batch(section_nodes)

    logger.info(f"Created {len(risk_nodes)} risk levels and {len(section_nodes)} sections")

async def ingest_kbli_record(record: Dict[str, Any], repo: KGRepository,
                              stats: IngestionStats) -> None:
    """Ingest a single KBLI record with all its variants and relationships."""
    kode = record["kode"]

    try:
        # 1. Create parent KBLI node
        parent_node = KGNode(
            id=f"kbli:code:{kode}",
            domain=Domain.KBLI,
            entity_type="code",
            name=record["judul"],
            name_id=record["judul"],
            description=record.get("deskripsi"),
            properties={
                "kode": kode,
                "sektor_id": record.get("sektor_id"),
                "pma_status": record.get("pma_status", "TERBUKA"),
                "pma_max_asing": record.get("pma_max_asing", 100),
                "pma_kondisi": record.get("pma_kondisi"),
                "pma_prioritas": record.get("pma_prioritas", False)
            }
        )
        await repo.upsert_node(parent_node)
        stats.nodes_created += 1

        # 2. Create hierarchy links
        section_code = record.get("sektor_id", "").lower()
        if section_code:
            await repo.create_edge(KGEdge(
                source_id=f"kbli:code:{kode}",
                target_id=f"kbli:section:{section_code}",
                relationship_type="BELONGS_TO",
                source_regulation="reg:bps:7_2025"
            ))

        # 3. Create scale variants
        per_skala = record.get("per_skala", {})
        for scale_name, scale_data in per_skala.items():
            if not scale_data:
                continue

            variant_id = f"kbli:variant:{kode}_{scale_name}"
            risk_level = scale_data.get("tingkat_risiko", "RENDAH")
            perizinan = scale_data.get("perizinan", "")

            # Create variant node
            variant_node = KGNode(
                id=variant_id,
                domain=Domain.KBLI,
                entity_type="variant",
                name=f"{kode} ({scale_name.capitalize()})",
                properties={
                    "scale": scale_name,
                    "risk_level": risk_level,
                    "perizinan_raw": perizinan
                }
            )
            await repo.upsert_node(variant_node)
            stats.variants_created += 1

            # Link parent → variant
            await repo.create_edge(KGEdge(
                source_id=f"kbli:code:{kode}",
                target_id=variant_id,
                relationship_type="HAS_VARIANT",
                properties={"scale": scale_name}
            ))

            # Link variant → risk level
            if risk_level in RISK_LEVELS:
                await repo.create_edge(KGEdge(
                    source_id=variant_id,
                    target_id=RISK_LEVELS[risk_level]["id"],
                    relationship_type="HAS_RISK_LEVEL",
                    source_regulation="reg:pp:28_2025"
                ))

            # Link variant → permits
            if perizinan:
                permits = [p.strip() for p in perizinan.split(",") if p.strip()]
                for permit_name in permits:
                    permit_id = f"legal:permit:{permit_name.lower().replace(' ', '_')}"

                    # Ensure permit node exists
                    await repo.upsert_node(KGNode(
                        id=permit_id,
                        domain=Domain.LEGAL,
                        entity_type="permit",
                        name=permit_name
                    ))

                    # Create requirement edge
                    await repo.create_edge(KGEdge(
                        source_id=variant_id,
                        target_id=permit_id,
                        relationship_type="REQUIRES",
                        source_regulation="reg:pp:28_2025"
                    ))
                    stats.permits_linked += 1

        # 4. Handle PMA status
        pma_status = record.get("pma_status", "TERBUKA")

        if pma_status == "TERTUTUP":
            # Create BLOCKED_BY edge
            await repo.create_edge(KGEdge(
                source_id=f"kbli:code:{kode}",
                target_id="reg:perpres:10_2021",
                relationship_type="BLOCKED_BY",
                properties={"block_type": "TERTUTUP", "foreign_investment": False},
                source_regulation="reg:perpres:10_2021"
            ))

        elif pma_status == "TERBATAS":
            # Create conditional OPERATES edge from PT PMA
            max_equity = record.get("pma_max_asing", 49)
            kondisi = record.get("pma_kondisi")

            await repo.create_edge(KGEdge(
                source_id="legal:entity:pt_pma",
                target_id=f"kbli:code:{kode}",
                relationship_type="OPERATES",
                properties={
                    "access_type": "RESTRICTED",
                    "max_foreign_equity": max_equity,
                    "conditions": kondisi
                },
                source_regulation="reg:perpres:49_2021"
            ))

        else:  # TERBUKA
            # Create full access OPERATES edge
            await repo.create_edge(KGEdge(
                source_id="legal:entity:pt_pma",
                target_id=f"kbli:code:{kode}",
                relationship_type="OPERATES",
                properties={"access_type": "FULL", "max_foreign_equity": 100},
                source_regulation="reg:perpres:10_2021"
            ))

        # 5. Handle priority sectors (incentives)
        if record.get("pma_prioritas"):
            await repo.create_edge(KGEdge(
                source_id=f"kbli:code:{kode}",
                target_id="tax:incentive:tax_holiday",
                relationship_type="ELIGIBLE_FOR",
                properties={"priority_sector": True},
                source_regulation="reg:perpres:10_2021"
            ))

        stats.edges_created += 5  # Approximate

    except Exception as e:
        stats.errors.append(f"Error processing KBLI {kode}: {str(e)}")
        logger.error(f"Failed to ingest KBLI {kode}: {e}")

async def main():
    """Main ingestion entry point."""
    logger.info("=" * 60)
    logger.info("KBLI 2025 Knowledge Graph Ingestion")
    logger.info("=" * 60)

    # Load data
    logger.info(f"Loading data from {KBLI_FILE}")
    with open(KBLI_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = data.get("data", [])
    logger.info(f"Loaded {len(records)} KBLI records")

    # Connect to database
    pool = await asyncpg.create_pool(DATABASE_URL)
    repo = KGRepository(pool)
    stats = IngestionStats()

    try:
        # Create reference nodes first
        await create_reference_nodes(repo)

        # Create base entity nodes (PT PMA, etc.)
        base_entities = [
            KGNode(id="legal:entity:pt_pma", domain=Domain.LEGAL, entity_type="entity_type",
                   name="PT PMA", name_en="Foreign Investment Limited Company"),
            KGNode(id="legal:entity:pt_pmdn", domain=Domain.LEGAL, entity_type="entity_type",
                   name="PT PMDN", name_en="Domestic Investment Limited Company"),
            KGNode(id="reg:perpres:10_2021", domain=Domain.REG, entity_type="perpres",
                   name="Perpres 10/2021", properties={"subject": "DNI"}),
            KGNode(id="reg:perpres:49_2021", domain=Domain.REG, entity_type="perpres",
                   name="Perpres 49/2021", properties={"subject": "DNI Amendment"}),
            KGNode(id="reg:pp:28_2025", domain=Domain.REG, entity_type="pp",
                   name="PP 28/2025", properties={"subject": "Perizinan Berusaha"}),
            KGNode(id="reg:bps:7_2025", domain=Domain.REG, entity_type="peraturan_bps",
                   name="Peraturan BPS 7/2025", properties={"subject": "KBLI 2025"}),
            KGNode(id="tax:incentive:tax_holiday", domain=Domain.TAX, entity_type="incentive",
                   name="Tax Holiday", properties={"type": "cit_exemption"})
        ]
        await repo.upsert_nodes_batch(base_entities)

        # Ingest KBLI records
        logger.info("Starting KBLI ingestion...")
        for i, record in enumerate(records):
            await ingest_kbli_record(record, repo, stats)
            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1}/{len(records)} records")

        # Print stats
        logger.info("=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Nodes created: {stats.nodes_created}")
        logger.info(f"Variants created: {stats.variants_created}")
        logger.info(f"Permits linked: {stats.permits_linked}")
        logger.info(f"Edges created (approx): {stats.edges_created}")
        logger.info(f"Errors: {len(stats.errors)}")

        if stats.errors:
            logger.warning("Errors encountered:")
            for err in stats.errors[:10]:
                logger.warning(f"  - {err}")

    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## PARTE 7: ROADMAP DI IMPLEMENTAZIONE

### Settimana 1-2: Foundation

| Task                 | Deliverable                     | Priority |
| -------------------- | ------------------------------- | -------- |
| Deploy schema SQL    | `migration_030_kg_schema_v2.py` | P0       |
| Ingest KBLI 2025     | 1,562 codes + 6,248 variants    | P0       |
| Ingest base entities | PT PMA, PT PMDN, permits        | P0       |
| Basic Pathfinder     | KBLI eligibility check          | P0       |

### Settimana 3-4: Visa & Tax

| Task               | Deliverable                   | Priority |
| ------------------ | ----------------------------- | -------- |
| Ingest Visa types  | 30+ visa nodes + requirements | P1       |
| Link Visa → Entity | ENABLES relationships         | P1       |
| Ingest Tax types   | PPh, PPN, incentivi           | P1       |
| Link Entity → Tax  | TAX_OBLIGATION edges          | P1       |

### Settimana 5-6: Regulations & Property

| Task                    | Deliverable              | Priority |
| ----------------------- | ------------------------ | -------- |
| Ingest 300+ regulations | Hierarchy + subject tags | P1       |
| Link all → Regulations  | GOVERNED_BY edges        | P1       |
| Ingest Property rights  | HGB, Hak Pakai, zones    | P2       |
| Geographic restrictions | RESTRICTED_IN edges      | P2       |

### Settimana 7-8: Integration & Testing

| Task               | Deliverable                 | Priority |
| ------------------ | --------------------------- | -------- |
| Hybrid Retrieval   | Qdrant + KG orchestration   | P1       |
| API endpoints      | `/kg/query`, `/kg/pathfind` | P1       |
| Integration tests  | 50+ test cases              | P1       |
| Performance tuning | Indexes, caching            | P2       |

---

## PARTE 8: VALIDATION QUERIES

```sql
-- Verifica integrità base
SELECT
    domain,
    entity_type,
    COUNT(*) as count
FROM kg_nodes
GROUP BY domain, entity_type
ORDER BY domain, count DESC;

-- Verifica archi per tipo
SELECT
    relationship_type,
    COUNT(*) as count
FROM kg_active_edges
GROUP BY relationship_type
ORDER BY count DESC;

-- Verifica KBLI con varianti
SELECT
    n.id,
    n.name,
    COUNT(e.id) as variant_count
FROM kg_nodes n
LEFT JOIN kg_edges e ON e.source_id = n.id AND e.type = 'HAS_VARIANT'
WHERE n.entity_type = 'code' AND n.domain = 'kbli'
GROUP BY n.id, n.name
HAVING COUNT(e.id) < 4
LIMIT 10;

-- Verifica PMA status distribution
SELECT
    properties->>'pma_status' as pma_status,
    COUNT(*) as count
FROM kg_nodes
WHERE domain = 'kbli' AND entity_type = 'code'
GROUP BY properties->>'pma_status';

-- Test traversal: cosa può operare PT PMA?
SELECT
    t.id as kbli,
    t.name,
    e.properties->>'access_type' as access,
    e.properties->>'max_foreign_equity' as max_equity
FROM kg_active_edges e
JOIN kg_nodes t ON e.target_id = t.id
WHERE e.source_id = 'legal:entity:pt_pma'
AND e.relationship_type = 'OPERATES'
LIMIT 20;
```

---

**Fine del Documento**

_Questo documento rappresenta la strategia completa per l'implementazione del Super Knowledge Graph di Nuzantara._
