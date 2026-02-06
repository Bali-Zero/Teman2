# NUZANTARA Knowledge Base Architecture Brief

## Per Reasoning Architetturale con o1-pro / Antigravity Deep Think

**Data**: 2 Febbraio 2026
**Versione**: 1.0
**Scopo**: Definire l'architettura del "Grafo Totale" che unifica tutti i domini della Knowledge Base

---

## 1. EXECUTIVE SUMMARY

Nuzantara è un sistema RAG (Retrieval-Augmented Generation) specializzato in consulenza business per l'Indonesia. L'architettura attuale utilizza un **dual storage**:

- **Qdrant**: Vector database per semantic search (17 collections attive)
- **PostgreSQL**: Knowledge Graph relazionale (34,606 nodi, 30,628 archi)

**Obiettivo di questo brief**: Ragionare su come evolvere verso un **"Grafo Totale"** che:

1. Unifichi tutti i domini in un unico grafo connesso
2. Abiliti query cross-domain (es. "quale visa per aprire un ristorante a Bali?")
3. Supporti workflow dinamici basati su traversal del grafo
4. Mantenga backward compatibility con le collections esistenti

---

## 2. ARCHITETTURA ATTUALE

### 2.1 Qdrant Collections (17 attive)

| Collection               | Documents | Descrizione                              | Hybrid          |
| ------------------------ | --------- | ---------------------------------------- | --------------- |
| `visa_kb`                | 8,000+    | Tipi visa, requisiti, eligibilità        | BM25+Dense      |
| `tax_kb`                 | 5,000+    | Regolamenti fiscali, obblighi, treaties  | BM25+Dense      |
| `legal_kb`               | 3,500+    | Documenti legali, contratti, compliance  | BM25+Dense      |
| `kbli_2020`              | 1,790     | Codici attività economica (legacy)       | Dense only      |
| `kbli_2025`              | 1,562     | Codici KBLI aggiornati con PMA           | **DA INGERIRE** |
| `property_kb`            | 29        | Regolamenti immobiliari, zone, ownership | Dense only      |
| `team_profiles`          | 22        | Profili team Nuzantara                   | Dense only      |
| `pricing_catalog`        | 70        | Servizi e prezzi                         | Dense only      |
| `intel_news_*`           | 8 coll.   | News intelligence per settore            | BM25+Dense      |
| `training_conversations` | 2,898     | Conversazioni training per fine-tuning   | Dense only      |

### 2.2 Knowledge Graph Schema (PostgreSQL)

```sql
-- Nodi del grafo
CREATE TABLE kg_nodes (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(255) UNIQUE NOT NULL,  -- es. "kbli:47111", "visa:kitas_investor"
    entity_type VARCHAR(100) NOT NULL,        -- es. "kbli_code", "visa_type", "tax_obligation"
    name VARCHAR(500) NOT NULL,
    properties JSONB DEFAULT '{}',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Archi del grafo
CREATE TABLE kg_edges (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(255) NOT NULL,
    target_entity_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,  -- es. "REQUIRES", "ENABLES", "BLOCKED_BY"
    properties JSONB DEFAULT '{}',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (source_entity_id) REFERENCES kg_nodes(entity_id),
    FOREIGN KEY (target_entity_id) REFERENCES kg_nodes(entity_id)
);
```

**Statistiche attuali**:

- Nodi totali: **34,606**
- Archi totali: **30,628**
- Entity types: 15+
- Relationship types: 25+

---

## 3. DOMINI E LORO STRUTTURA

### 3.1 DOMAIN: KBLI (Classificazione Attività Economiche)

**Source**: BPS (Badan Pusat Statistik) + PP 28/2025 + Perpres 10/2021

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `kbli_code` | 1,562 | Codici attività 5 cifre |
| `kbli_section` | 21 | Sezioni (A-U) |
| `kbli_division` | 88 | Divisioni (2 cifre) |
| `kbli_group` | 240 | Gruppi (3 cifre) |
| `kbli_class` | 514 | Classi (4 cifre) |
| `risk_level` | 4 | RENDAH, MENENGAH_RENDAH, MENENGAH_TINGGI, TINGGI |
| `permit_type` | 50+ | NIB, SIUP, Izin Lokasi, etc. |
| `zone` | 100+ | Zone geografiche con restrizioni |

**Relationship Types**:
| Relationship | Significato |
|--------------|-------------|
| `BELONGS_TO` | Gerarchia KBLI (code → class → group → division → section) |
| `HAS_RISK_LEVEL` | KBLI → Risk Level |
| `REQUIRES` | KBLI → Permit necessario |
| `BLOCKED_BY` | KBLI → Regolamento che blocca |
| `RESTRICTED_TO` | KBLI → Zone permesse |
| `PIVOT_TO` | KBLI → KBLI alternativo suggerito |

**Attributi Chiave per KBLI Code**:

```json
{
  "kode": "47111",
  "judul": "Perdagangan Eceran Berbagai Macam Barang...",
  "deskripsi": "...",
  "sektor_id": "G",
  "per_skala": {
    "mikro": { "tingkat_risiko": "RENDAH", "perizinan": "NIB" },
    "kecil": { "tingkat_risiko": "RENDAH", "perizinan": "NIB" },
    "menengah": { "tingkat_risiko": "MENENGAH_RENDAH", "perizinan": "NIB, Sertifikat Standar" },
    "besar": { "tingkat_risiko": "MENENGAH_TINGGI", "perizinan": "NIB, Izin" }
  },
  "pma_status": "TERBUKA|TERBATAS|TERTUTUP|PRIORITAS",
  "pma_max_asing": 100,
  "pma_kondisi": null,
  "pma_prioritas": false
}
```

### 3.2 DOMAIN: VISA & IMMIGRATION

**Source**: Imigrasi Indonesia, UU Keimigrasian

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `visa_type` | 30+ | KITAS, KITAP, B211, VOA, etc. |
| `visa_category` | 8 | Investor, Worker, Spouse, Retirement, etc. |
| `sponsor_type` | 5 | Company, Indonesian Spouse, Self, Agent |
| `document_requirement` | 100+ | Passport, Photo, SKTT, etc. |

**Relationship Types**:
| Relationship | Significato |
|--------------|-------------|
| `ENABLES` | Visa → Attività permessa (es. KITAS_INVESTOR → run PT PMA) |
| `REQUIRES_DOCUMENT` | Visa → Documento necessario |
| `REQUIRES_SPONSOR` | Visa → Tipo sponsor |
| `CONVERTS_TO` | Visa → Visa successivo (es. B211 → KITAS) |
| `VALID_FOR_KBLI` | Visa → KBLI codes permessi |
| `DURATION` | Visa → Durata validità |

**Cross-Domain Connection VISA ↔ KBLI**:

```
visa:kitas_investor --[ENABLES]--> activity:run_pt_pma
activity:run_pt_pma --[REQUIRES]--> entity_type:pt_pma
entity_type:pt_pma --[OPERATES_KBLI]--> kbli:*
kbli:47111 --[HAS_PMA_STATUS]--> pma_status:TERBUKA
```

### 3.3 DOMAIN: TAX & FISCAL

**Source**: DJP (Direktorat Jenderal Pajak), PMK regulations

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `tax_type` | 15+ | PPh 21, PPh 23, PPN, PPh Badan, etc. |
| `tax_rate` | 50+ | Aliquote per tipo e threshold |
| `tax_incentive` | 20+ | Tax holiday, Super deduction, etc. |
| `tax_treaty` | 70+ | DTA con altri paesi |
| `tax_obligation` | 100+ | Obblighi dichiarativi |

**Relationship Types**:
| Relationship | Significato |
|--------------|-------------|
| `TAX_OBLIGATION` | Entity Type → Tax dovuta |
| `HAS_RATE` | Tax Type → Rate applicabile |
| `ELIGIBLE_FOR` | KBLI/Zone → Tax Incentive |
| `TREATY_WITH` | Indonesia → Country (riduzione ritenute) |
| `FILING_DEADLINE` | Tax Obligation → Date/Frequency |

**Cross-Domain Connection TAX ↔ KBLI**:

```
kbli:62011 (Software Development) --[ELIGIBLE_FOR]--> incentive:super_deduction_rd
incentive:super_deduction_rd --[REDUCES]--> tax:pph_badan
tax:pph_badan --[HAS_RATE]--> rate:22_percent
```

### 3.4 DOMAIN: LEGAL & CORPORATE

**Source**: Notarial documents, OJK, Kemenkumham

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `entity_type` | 10 | PT PMA, PT PMDN, CV, Firma, Yayasan, etc. |
| `document_type` | 50+ | Akta Pendirian, SK Menkumham, NPWP, etc. |
| `legal_requirement` | 200+ | Requisiti per costituzione/operatività |
| `regulation` | 500+ | UU, PP, Perpres, Permen, etc. |

**Document Hierarchy** (5 livelli):

```
regulation:uu_40_2007 (UU Perseroan Terbatas)
  └── regulation:pp_29_2016 (PP Modal Dasar)
       └── regulation:permen_ahu_2021 (Permen Pendaftaran)
            └── procedure:pendirian_pt
                 └── document:akta_pendirian
```

**Relationship Types**:
| Relationship | Significato |
|--------------|-------------|
| `GOVERNED_BY` | Entity Type → Regulation |
| `REQUIRES_DOCUMENT` | Procedure → Document |
| `AMENDS` | Regulation → Regulation precedente |
| `SUPERSEDES` | Regulation → Regulation abrogata |
| `MINIMUM_CAPITAL` | Entity Type → Amount |

### 3.5 DOMAIN: PROPERTY & REAL ESTATE

**Source**: BPN, UU Agraria, Perda

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `property_right` | 7 | Hak Milik, HGB, HGU, Hak Pakai, Strata, etc. |
| `zone_type` | 20+ | Residential, Commercial, Industrial, Tourism |
| `ownership_structure` | 5 | Direct, Nominee, PT PMA, Leasehold |

**Relationship Types**:
| Relationship | Significato |
|--------------|-------------|
| `AVAILABLE_TO` | Property Right → Nationality/Entity |
| `VALID_IN_ZONE` | Property Right → Zone Type |
| `MAX_DURATION` | Property Right → Years |
| `REQUIRES_ENTITY` | Ownership Structure → Entity Type |

**Cross-Domain Connection PROPERTY ↔ VISA ↔ KBLI**:

```
foreigner --[CAN_OBTAIN]--> property_right:hak_pakai
foreigner --[VIA]--> entity_type:pt_pma
pt_pma --[CAN_OBTAIN]--> property_right:hgb
pt_pma --[OPERATES_KBLI]--> kbli:68110 (Real Estate)
kbli:68110 --[HAS_PMA_STATUS]--> pma_status:TERBATAS
pma_status:TERBATAS --[CONDITION]--> "Max 67% foreign ownership"
```

### 3.6 DOMAIN: PRICING & SERVICES

**Source**: Internal Nuzantara

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `service` | 70 | Servizi offerti (Company Formation, Visa, etc.) |
| `package` | 15 | Bundle di servizi |
| `fee_component` | 100+ | Government fees, Service fees, etc. |

**NOTA IMPORTANTE**: Il dominio Pricing è **SEPARATO** dalla relazione `HAS_FEE` nel KG principale. I prezzi Nuzantara non devono inquinare il grafo delle conoscenze regolamentari.

**Relationship Types** (interni al dominio):
| Relationship | Significato |
|--------------|-------------|
| `INCLUDES` | Package → Service |
| `HAS_COMPONENT` | Service → Fee Component |
| `VALID_UNTIL` | Price → Date |

### 3.7 DOMAIN: INTEL & NEWS

**Source**: News aggregation, Government announcements

**Collections** (8 separate):

- `intel_news_regulatory`: Cambiamenti normativi
- `intel_news_tax`: Novità fiscali
- `intel_news_visa`: Aggiornamenti immigrazione
- `intel_news_investment`: Opportunità investimento
- `intel_news_property`: Mercato immobiliare
- `intel_news_economic`: Indicatori economici
- `intel_news_political`: Stabilità politica
- `intel_news_sector_*`: News per settore KBLI

**Entity Types**:
| Type | Descrizione |
|------|-------------|
| `news_item` | Singola news con metadata |
| `source` | Fonte (Kompas, Bisnis, etc.) |
| `topic` | Topic classificato |
| `impact_assessment` | Valutazione impatto su clienti |

### 3.8 DOMAIN: TEAM & INTERNAL

**Source**: Internal HR

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `team_member` | 22 | Profili team |
| `expertise` | 30+ | Aree di competenza |
| `language` | 10 | Lingue parlate |

**Relationship Types**:
| Relationship | Significato |
|--------------|-------------|
| `HAS_EXPERTISE` | Member → Domain |
| `SPEAKS` | Member → Language |
| `HANDLES` | Member → Service Type |

### 3.9 DOMAIN: TRAINING

**Source**: Historical conversations, curated Q&A

**Entity Types**:
| Type | Count | Descrizione |
|------|-------|-------------|
| `conversation` | 2,898 | Conversazioni complete |
| `qa_pair` | 10,000+ | Coppie domanda-risposta |
| `topic_tag` | 100+ | Tag per classificazione |

---

## 4. CROSS-DOMAIN RELATIONSHIPS (Il Cuore del Grafo Totale)

### 4.1 Matrice delle Connessioni

```
           KBLI   VISA   TAX   LEGAL  PROPERTY  PRICING  INTEL
KBLI        -      ✓      ✓      ✓       ✓         ✓       ✓
VISA        ✓      -      ✓      ✓       ✓         ✓       ✓
TAX         ✓      ✓      -      ✓       ✓         ✓       ✓
LEGAL       ✓      ✓      ✓      -       ✓         ✓       ✓
PROPERTY    ✓      ✓      ✓      ✓       -         ✓       ✓
PRICING     ✓      ✓      ✓      ✓       ✓         -       ✗
INTEL       ✓      ✓      ✓      ✓       ✓         ✗       -
```

### 4.2 Relationship Types Cross-Domain Chiave

| Relationship     | From        | To          | Esempio                                   |
| ---------------- | ----------- | ----------- | ----------------------------------------- |
| `ENABLES`        | visa        | activity    | KITAS_INVESTOR enables run_business       |
| `REQUIRES`       | activity    | entity_type | run_business requires PT_PMA              |
| `OPERATES`       | entity_type | kbli        | PT_PMA operates kbli:47111                |
| `TAX_OBLIGATION` | entity_type | tax         | PT_PMA has PPh_Badan obligation           |
| `ELIGIBLE_FOR`   | kbli        | incentive   | kbli:62011 eligible for tax_holiday       |
| `RESTRICTED_IN`  | kbli        | zone        | kbli:03111 restricted in protected_forest |
| `GOVERNED_BY`    | entity_type | regulation  | PT_PMA governed by UU_40_2007             |
| `IMPACTS`        | news        | domain      | news:new_dpi_2024 impacts kbli:\*         |

### 4.3 Esempio di Query Cross-Domain

**Query**: "Voglio aprire un ristorante a Bali come straniero"

**Traversal del Grafo**:

```
START: foreigner (nationality)
  │
  ├──[WANTS_TO]──> activity:restaurant_business
  │                    │
  │                    └──[MAPS_TO]──> kbli:56101 (Restoran)
  │                                        │
  │                                        ├──[HAS_PMA_STATUS]──> TERBUKA (100%)
  │                                        ├──[HAS_RISK_LEVEL]──> MENENGAH_TINGGI
  │                                        └──[REQUIRES]──> permit:izin_usaha_pariwisata
  │
  ├──[NEEDS_ENTITY]──> entity_type:pt_pma
  │                        │
  │                        ├──[REQUIRES_CAPITAL]──> IDR 10B minimum
  │                        ├──[REQUIRES_DOCUMENT]──> akta_pendirian, sk_menkumham, ...
  │                        └──[TAX_OBLIGATION]──> pph_badan, ppn, pph_21
  │
  ├──[NEEDS_VISA]──> visa:kitas_investor
  │                      │
  │                      ├──[REQUIRES_DOCUMENT]──> passport, photo, sponsor_letter
  │                      ├──[REQUIRES_INVESTMENT]──> USD 1.2M or IDR 10B
  │                      └──[VALID_FOR]──> 2 years
  │
  └──[LOCATION: bali]──> zone:bali_tourism
                             │
                             ├──[ALLOWS]──> kbli:56101 ✓
                             ├──[PROPERTY_OPTION]──> hgb_via_pt_pma
                             └──[SPECIAL_ZONE]──> kek_pariwisata (tax incentives)
```

---

## 5. IL CONCETTO DI "GRAFO TOTALE"

### 5.1 Definizione

Il **Grafo Totale** è una visione unificata dove:

1. **Ogni entità** in qualsiasi dominio è un **nodo** con `entity_id` univoco
2. **Ogni relazione** tra entità (anche cross-domain) è un **arco** tipizzato
3. **Le collections Qdrant** servono per semantic search sui contenuti testuali
4. **Il KG PostgreSQL** serve per traversal strutturato e reasoning

### 5.2 Principi Architetturali

1. **Single Source of Truth per Entity ID**
   - Formato: `{domain}:{type}:{id}` (es. `kbli:code:47111`, `visa:type:kitas_investor`)
   - Ogni nodo esiste UNA sola volta nel KG

2. **Separation of Concerns**
   - Qdrant: "Cosa dice il documento X riguardo Y?" (semantic)
   - KG: "Quali entità sono connesse a X e come?" (structural)

3. **Hybrid Query Pattern**

   ```
   User Query → Qdrant (semantic search) → Relevant Documents
                                              ↓
                                        Extract Entities
                                              ↓
                              KG (graph traversal) → Related Entities
                                              ↓
                                   Enrich with Qdrant content
                                              ↓
                                        LLM Response
   ```

4. **Confidence Scoring**
   - Ogni nodo e arco ha un `confidence` score (0.0-1.0)
   - Fonti ufficiali (BPS, DJP) = 1.0
   - Interpretazioni = 0.7-0.9
   - Inferenze = 0.5-0.7

### 5.3 GraphPathfinder Concept

Il `GraphPathfinder` è il motore di traversal che ricostruisce workflow completi:

```python
class GraphPathfinder:
    """
    Ricostruisce workflow dal grafo basandosi su:
    - STARTS_WITH: Punto di ingresso del workflow
    - NEXT_STEP: Sequenza ordinata di step
    - REQUIRES: Prerequisiti per ogni step
    - PRODUCES: Output di ogni step
    - USES: Strumenti/servizi usati
    - CONSULTS: Entità da consultare
    """

    def find_workflow_for_query(self, query: str, context: dict) -> Workflow:
        """
        Dual-Core Logic:
        - Se context.nationality == "foreign" → workflow PT PMA
        - Se context.nationality == "indonesian" → workflow PT PMDN
        """
        pass

    def get_workflow_by_id(self, workflow_id: str) -> Workflow:
        """Recupera workflow specifico per ID"""
        pass
```

---

## 6. DOMANDE PER IL REASONING ARCHITETTURALE

### 6.1 Struttura del Grafo

1. **Granularità dei nodi**: Fino a che livello di dettaglio creare nodi?
   - Es: Creare un nodo per ogni singolo requisito documento, o aggregare?

2. **Relazioni inverse**: Mantenere sempre relazioni bidirezionali esplicite o inferire?
   - Es: Se A `REQUIRES` B, creare anche B `REQUIRED_BY` A?

3. **Nodi virtuali vs fisici**: Come gestire entità derivate?
   - Es: "Foreigner who wants to open restaurant" è un nodo o una query?

### 6.2 Consistency & Updates

4. **Versioning**: Come gestire cambiamenti regolamentari?
   - Es: Perpres 10/2021 → Perpres 49/2021 → Perpres 14/2024

5. **Temporal validity**: Come rappresentare validità temporale?
   - Es: Tax rate valid from 2024-01-01 to 2024-12-31

6. **Conflict resolution**: Come gestire conflitti tra fonti?
   - Es: Sito BKPM dice X, Perpres dice Y

### 6.3 Query & Retrieval

7. **Hybrid retrieval strategy**: Quando usare Qdrant vs KG vs entrambi?
   - Query factual → KG first
   - Query open-ended → Qdrant first
   - Query procedural → Hybrid

8. **Traversal depth**: Quanto profondo andare nel grafo?
   - Default depth = 2? 3? Adaptive?

9. **Ranking cross-domain**: Come pesare risultati da domini diversi?

### 6.4 Scalabilità

10. **Sharding strategy**: Come partizionare se il grafo cresce troppo?
    - Per dominio? Per regione? Per temporal validity?

11. **Caching**: Quali query/traversal cachare?
    - Workflow comuni? Entity clusters?

12. **Incremental updates**: Come aggiornare senza rebuild completo?

### 6.5 Il Grafo Totale

13. **Hub nodes**: Quali entità dovrebbero essere hub centrali?
    - `entity_type:pt_pma` come hub? `visa:kitas_investor`?

14. **Bridge entities**: Come collegare domini che sembrano disconnessi?
    - Training conversations → come collegarle al grafo?

15. **Meta-graph**: Serve un grafo del grafo (schema graph)?
    - Per introspection e query planning?

---

## 7. PROPOSTA ARCHITETTURALE INIZIALE

### 7.1 Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                         │
│  (Chat Interface, API Endpoints, Webhooks)                      │
├─────────────────────────────────────────────────────────────────┤
│                        ORCHESTRATION LAYER                       │
│  (Query Router, GraphPathfinder, Response Synthesizer)          │
├─────────────────────────────────────────────────────────────────┤
│                        RETRIEVAL LAYER                           │
│  ┌─────────────────┐         ┌─────────────────┐                │
│  │     QDRANT      │ ←─────→ │   POSTGRESQL    │                │
│  │ (Semantic Search)│         │ (Knowledge Graph)│                │
│  │                 │         │                 │                │
│  │ 17 Collections  │         │ kg_nodes        │                │
│  │ BM25 + Dense    │         │ kg_edges        │                │
│  └─────────────────┘         └─────────────────┘                │
├─────────────────────────────────────────────────────────────────┤
│                        INGESTION LAYER                           │
│  (Parsers, Transformers, Entity Extractors, Relation Builders)  │
├─────────────────────────────────────────────────────────────────┤
│                        DATA SOURCES                              │
│  (BPS, DJP, BKPM, Imigrasi, Internal Docs, News Feeds)         │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Entity ID Convention

```
{namespace}:{type}:{identifier}

Esempi:
- kbli:code:47111
- kbli:section:G
- visa:type:kitas_investor
- tax:type:pph_badan
- tax:rate:pph_badan_2024
- legal:entity:pt_pma
- legal:document:akta_pendirian
- regulation:perpres:10_2021
- zone:province:bali
- zone:kek:mandalika
- service:nuzantara:company_formation
```

### 7.3 Relationship Type Convention

```
VERB_OBJECT (all caps, underscore separated)

Categorie:
- Structural: BELONGS_TO, PART_OF, CONTAINS
- Requirement: REQUIRES, NEEDS, DEPENDS_ON
- Enablement: ENABLES, ALLOWS, PERMITS
- Restriction: BLOCKS, RESTRICTS, LIMITS
- Temporal: PRECEDES, FOLLOWS, VALID_FROM
- Reference: GOVERNED_BY, DEFINED_IN, CITES
- Operational: OPERATES, HANDLES, PROCESSES
```

---

## 8. NEXT STEPS PROPOSTI

1. **Validazione architettura** con o1-pro/Antigravity
2. **Definizione schema completo** per tutti i domini
3. **Implementazione ingestion KBLI 2025** come pilot
4. **Test cross-domain queries** su subset
5. **Iterazione** basata su risultati

---

## 9. APPENDICI

### A. File di Riferimento

| File              | Path                                                                           | Descrizione            |
| ----------------- | ------------------------------------------------------------------------------ | ---------------------- |
| KBLI 2025 Dataset | `/Users/antonellosiano/Desktop/kbli_2025_reasoning/KBLI_2025_FINAL_CLEAN.json` | 1,562 codici con PMA   |
| KG Migration      | `apps/backend-rag/backend/migrations/migration_028_knowledge_graph_schema.py`  | Schema KG              |
| GraphPathfinder   | `apps/backend-rag/backend/services/rag/graph_pathfinder.py`                    | Concept implementation |
| Ingestion Example | `scripts/ingestion/ingest_kbli_platinum_2026.py`                               | Pattern ingestion      |

### B. Statistiche Attuali

- Qdrant Collections: 17
- KG Nodes: 34,606
- KG Edges: 30,628
- Ingestion Scripts: 49
- Total Documents: ~25,000+

### C. Regolamenti Chiave Indonesia

| Regolamento     | Ambito             | Impatto                     |
| --------------- | ------------------ | --------------------------- |
| UU 40/2007      | Perseroan Terbatas | Costituzione società        |
| UU 25/2007      | Penanaman Modal    | Investimenti esteri         |
| PP 28/2025      | Perizinan Berusaha | Licenze e rischi            |
| Perpres 10/2021 | DNI                | Lista negativa investimenti |
| Perpres 49/2021 | Update DNI         | Aggiornamento lista         |
| Perpres 14/2024 | DNI Update         | Aggiornamento 2024          |
| PMK 112/2022    | Tax                | NPWP unificato              |

---

**Fine del Brief**

_Questo documento è pronto per essere processato da o1-pro, Antigravity Deep Think, o altro tool di reasoning architetturale avanzato._
