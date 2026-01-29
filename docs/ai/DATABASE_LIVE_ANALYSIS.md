# 🗄️ DATABASE LIVE ANALYSIS - Nuzantara

> Analisi in carne e ossa di PostgreSQL e Qdrant

---

## 📊 Overview Infrastruttura Dati

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐             │
│  │    PostgreSQL       │    │      Qdrant         │             │
│  │   (Fly.io Postgres) │    │   (Qdrant Cloud)    │             │
│  │                     │    │                     │             │
│  │  • 70 tabelle       │    │  • 5 collections    │             │
│  │  • Relational data  │    │  • 6,757 vectors    │             │
│  │  • ACID compliant   │    │  • Hybrid search    │             │
│  └─────────────────────┘    └─────────────────────┘             │
│                                                                 │
│  ┌─────────────────────┐                                        │
│  │       Redis         │                                        │
│  │   (Upstash Redis)   │                                        │
│  │                     │                                        │
│  │  • Session cache    │                                        │
│  │  • Rate limiting    │                                        │
│  └─────────────────────┘                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🐘 POSTGRESQL

### Connection Info

```
Host: Fly.io Postgres (internal)
Database: nuzantara
Schema: public
Tables: 70
```

### Tutte le Tabelle (70)

#### 🔐 Auth & Users (5 tabelle)

| Tabella          | Descrizione           |
| ---------------- | --------------------- |
| `users`          | Utenti sistema (team) |
| `user_profiles`  | Profili estesi        |
| `user_stats`     | Statistiche utente    |
| `auth_audit_log` | Log autenticazione    |
| `team_members`   | Membri del team       |

#### 👥 CRM (9 tabelle)

| Tabella                 | Descrizione               |
| ----------------------- | ------------------------- |
| `clients`               | Clienti                   |
| `practices`             | Pratiche (visa, business) |
| `practice_types`        | Tipi di pratica           |
| `interactions`          | Interazioni con clienti   |
| `client_family_members` | Familiari dei clienti     |
| `documents`             | Documenti clienti         |
| `document_categories`   | Categorie documenti       |
| `renewal_alerts`        | Alert rinnovi             |
| `crm_settings`          | Impostazioni CRM          |

#### 💬 Chat & Memory (6 tabelle)

| Tabella                     | Descrizione               |
| --------------------------- | ------------------------- |
| `conversations`             | Storico conversazioni     |
| `conversation_ratings`      | Valutazioni conversazioni |
| `memory_facts`              | Fatti estratti            |
| `episodic_memories`         | Memorie episodiche        |
| `collective_memories`       | Memorie collettive        |
| `collective_memory_sources` | Fonti memorie             |

#### 📰 Content & Intel (8 tabelle)

| Tabella                   | Descrizione           |
| ------------------------- | --------------------- |
| `zantara_content`         | Contenuti CMS         |
| `content_versions`        | Versioni contenuti    |
| `content_distributions`   | Distribuzioni         |
| `content_analytics_daily` | Analytics giornalieri |
| `news_items`              | News/articoli         |
| `news_subscriptions`      | Iscrizioni newsletter |
| `user_saved_news`         | News salvate          |
| `intel_signals`           | Segnali intelligence  |

#### 🏢 Business (8 tabelle)

| Tabella               | Descrizione             |
| --------------------- | ----------------------- |
| `business_structures` | Strutture societarie    |
| `company_profiles`    | Profili aziende         |
| `kbli_codes`          | Codici KBLI             |
| `kbli_combinations`   | Combinazioni KBLI       |
| `indonesian_licenses` | Licenze indonesiane     |
| `oss_issues`          | Problemi OSS            |
| `oss_system_info`     | Info sistema OSS        |
| `regulatory_updates`  | Aggiornamenti normativi |

#### 🏠 Property (4 tabelle)

| Tabella                     | Descrizione         |
| --------------------------- | ------------------- |
| `property_listings`         | Annunci immobiliari |
| `property_due_diligence`    | Due diligence       |
| `property_legal_structures` | Strutture legali    |
| `property_market_data`      | Dati di mercato     |

#### 🛂 Immigration (3 tabelle)

| Tabella               | Descrizione           |
| --------------------- | --------------------- |
| `visa_types`          | Tipi di visto         |
| `immigration_offices` | Uffici immigrazione   |
| `immigration_issues`  | Problemi immigrazione |

#### 💰 Tax (3 tabelle)

| Tabella                       | Descrizione              |
| ----------------------------- | ------------------------ |
| `tax_audit_risk_factors`      | Fattori rischio audit    |
| `tax_optimization_strategies` | Strategie ottimizzazione |
| `tax_treaty_benefits`         | Benefici trattati        |

#### 🧠 Knowledge Graph (4 tabelle)

| Tabella              | Descrizione          |
| -------------------- | -------------------- |
| `kg_entities`        | Entità grafo         |
| `kg_relationships`   | Relazioni grafo      |
| `golden_routes`      | Route ottimali       |
| `cultural_knowledge` | Conoscenza culturale |

#### 📊 Analytics & Logs (8 tabelle)

| Tabella                | Descrizione         |
| ---------------------- | ------------------- |
| `query_analytics`      | Analytics query     |
| `query_clusters`       | Cluster query       |
| `query_route_clusters` | Cluster per route   |
| `activity_log`         | Log attività        |
| `audit_events`         | Eventi audit        |
| `email_activity_log`   | Log email           |
| `knowledge_feedback`   | Feedback conoscenza |
| `review_queue`         | Coda review         |

#### ⚙️ System (12 tabelle)

| Tabella                | Descrizione             |
| ---------------------- | ----------------------- |
| `team_timesheet`       | Timesheet team          |
| `team_access`          | Accessi team            |
| `departments`          | Dipartimenti            |
| `folder_access_rules`  | Regole accesso cartelle |
| `google_drive_tokens`  | Token Google Drive      |
| `media_assets`         | Asset media             |
| `parent_documents`     | Documenti padre         |
| `automation_runs`      | Esecuzioni automazioni  |
| `compliance_deadlines` | Scadenze compliance     |
| `migration_log`        | Log migrazioni          |
| `schema_migrations`    | Migrazioni schema       |

---

### 📦 "Mega Tabella": `parent_documents`

Questa è la tabella che raccoglie TUTTI i documenti sorgente (leggi, regolamenti, etc.):

```sql
CREATE TABLE parent_documents (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    type TEXT,                    -- 'law', 'regulation', 'policy'
    title TEXT,
    full_text TEXT,               -- Testo completo del documento
    summary TEXT,
    char_count INTEGER,
    pasal_count INTEGER,          -- Numero di articoli/pasal
    metadata JSONB,
    created_at TIMESTAMPTZ,
    drive_file_id VARCHAR(255),   -- Link a Google Drive
    drive_web_view_link TEXT,
    mime_type VARCHAR(100),
    text_fingerprint VARCHAR(64), -- Hash per dedup
    is_incomplete BOOLEAN,
    ocr_quality_score FLOAT,
    needs_reextract BOOLEAN,
    source_id TEXT,
    source_version VARCHAR(32),
    ingestion_run_id VARCHAR(64),
    is_canonical BOOLEAN
);
```

**Questa tabella è il "source of truth" per i documenti legali in PostgreSQL.**
I chunk vengono poi vettorializzati e caricati in Qdrant (`legal_unified`).

---

### Schema Tabelle Principali

#### `clients`

```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    whatsapp VARCHAR(50),
    nationality VARCHAR(100),
    passport_number VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    client_type VARCHAR(50) DEFAULT 'individual',
    assigned_to VARCHAR(255),
    first_contact_date TIMESTAMPTZ,
    last_interaction_date TIMESTAMPTZ,
    address TEXT,
    notes TEXT,
    tags JSONB DEFAULT '[]',
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255),
    avatar_url TEXT,
    google_drive_folder_id VARCHAR(100),
    date_of_birth DATE,
    passport_expiry DATE,
    company_name VARCHAR(255),

    CONSTRAINT clients_email_or_phone
        CHECK (email IS NOT NULL OR phone IS NOT NULL)
);
```

#### `practices`

```sql
CREATE TABLE practices (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES clients(id),
    practice_type_id INTEGER NOT NULL REFERENCES practice_types(id),
    status VARCHAR(50) DEFAULT 'inquiry',
    priority VARCHAR(20) DEFAULT 'normal',
    inquiry_date TIMESTAMPTZ DEFAULT NOW(),
    start_date TIMESTAMPTZ,
    completion_date TIMESTAMPTZ,
    expiry_date DATE,
    next_renewal_date DATE,
    quoted_price NUMERIC(12,2),
    actual_price NUMERIC(12,2),
    currency VARCHAR(10) DEFAULT 'IDR',
    payment_status VARCHAR(50) DEFAULT 'unpaid',
    paid_amount NUMERIC(12,2) DEFAULT 0,
    assigned_to VARCHAR(255),
    documents JSONB DEFAULT '[]',
    missing_documents JSONB DEFAULT '[]',
    notes TEXT,
    internal_notes TEXT,
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255)
);
```

#### `conversations`

```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    messages JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- messages JSONB structure:
-- [
--   {"role": "user", "content": "...", "timestamp": "..."},
--   {"role": "assistant", "content": "...", "timestamp": "..."}
-- ]
```

---

## 🔷 QDRANT (Vector Database)

### Connection Info

```
URL: https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333
Region: us-east4 (GCP)
Status: ✅ Online (green)
```

### Collections Overview (Aggiornato 2026-01-28)

| Collection                        | Points    | Vector Size | Distance | Sparse | Status    |
| --------------------------------- | --------- | ----------- | -------- | ------ | --------- |
| **visa_oracle**                   | 82        | 1536        | Cosine   | bm25   | ✅ Attiva |
| **training_conversations_hybrid** | 3,525     | 1536        | Cosine   | bm25   | ✅ Attiva |
| **tax_genius_hybrid**             | 332       | 1536        | Cosine   | bm25   | ✅ Attiva |
| **kbli_unified**                  | 2,818     | 1536        | Cosine   | bm25   | ✅ Attiva |
| **legal_unified**                 | 0         | 1536        | Cosine   | bm25   | ⚠️ VUOTA  |
| **bali_zero_pricing_hybrid**      | 0         | -           | -        | -      | ⚠️ VUOTA  |
| **TOTALE**                        | **6,757** |             |          |        |           |

### ⚠️ PROBLEMA: `legal_unified` è VUOTA!

La collection esiste ma non contiene dati. I documenti legali sono disponibili ma non ingeriti:

**Location documenti legali:**

```
~/Desktop/kb/ricerca/LEGAL ARCHITECT/
├── INDONESIAN_BUSINESS_COMPLIANCE_LAW_2025.md (31KB)
├── INDONESIAN_CORPORATE_TAX_PROCEDURAL_LAW_2025.md (42KB)
├── INDONESIAN_IMMIGRATION_INVESTMENT_INFRASTRUCTURE_LAW_2025.md (52KB)
├── INDONESIAN_IMMIGRATION_LAW_2025_OFFICIAL_REGULATIONS.md (41KB)
├── INDONESIAN_LEGAL_CODES.md (15KB)
├── INDONESIAN_LEGAL_FRAMEWORK_CONTRACTS_PROPERTY_MARRIAGE.md (35KB)
├── INDONESIAN_REAL_ESTATE_CASE_LAW_FOREIGNERS.md (59KB)
└── INDONESIA_IMMIGRATION_REGULATIONS_2025_COMPLETE.md (38KB)
```

**Totale: 8 documenti, ~313KB di contenuto legale da ingerire**

**Script per ingestion:** `scripts/ingestion/ingest_laws.py`

---

### 📋 visa_oracle (82 points)

**Scopo:** Knowledge base visti e immigrazione Indonesia

**Schema Payload:**

```json
{
  "text": "Full document text with context",
  "metadata": {
    "code": "C22B",
    "title": "VISA PROGRAM MAGANG",
    "category": "Visit Visa",
    "validity": "90 days",
    "sla": "5-7 Working Days",
    "doc_type": "visa",
    "version": "2025.12.22",
    "has_requirements": true,
    "has_legal_basis": true,
    "requirements_count": 21,
    "legal_basis_count": 5,
    "source": "Official Immigration Website",
    "is_kitas": false,
    "is_visit_visa": true
  }
}
```

**Sample Data:**

- C22B: Visa Program Magang (Industri)
- C4: Visa Tugas Pemerintahan
- C14: Visa Film Production
- KITAS varianti
- Procedure documents

---

### 📚 training_conversations_hybrid (3,525 points)

**Scopo:** Training data per RAG - conversazioni simulate

**Schema Payload:**

```json
{
  "text": "Conversation chunk text",
  "source": "training-data/legal/legal_058.md",
  "filename": "legal_058_intellectual_property",
  "title": "Intellectual Property Basics",
  "category": "legal",
  "chunk_index": 0,
  "total_chunks": 52,
  "data_version": "bali_zero_2025_corrected"
}
```

**Categories:**

- `legal` - Legale, IP, contratti
- `tax` - Fiscalità
- `visa` - Immigration
- `business` - Setup aziende

---

### 💰 tax_genius_hybrid (332 points)

**Scopo:** Knowledge base fiscalità Indonesia

**Schema Payload:**

```json
{
  "text": "Tax guidance chunk",
  "metadata": {
    "source": "training-data/tax/tax_019.md",
    "title": "PPN/VAT 11% - Full Cycle Guide",
    "category": "value_added_tax",
    "subcategory": "ppn",
    "topics": ["PPN", "VAT", "PKP", "e-Faktur"],
    "language": "id",
    "tier": "A",
    "chunk_index": 26,
    "total_chunks": 161
  }
}
```

**Topics:**

- PPh 21 (Employee tax)
- PPN/VAT 11%
- PPh Badan (Corporate tax)
- e-Faktur system
- NPWP procedures

---

### 🏢 kbli_unified (2,818 points)

**Scopo:** Codici KBLI (classificazione business Indonesia)

**Schema Payload:**

```json
{
  "text": "KBLI description and context",
  "metadata": {
    "kode": "1039",
    "judul": "Industri Pengolahan Buah-buahan",
    "prefix_2": "10",
    "prefix_3": "103",
    "digit_count": 4,
    "sources": ["OSS_RBA_API", "PP_28_2025"],
    "doc_type": "kbli",
    "version": "PP_28_2025",
    "risk_level": "Rendah",
    "pma_allowed": false,
    "pma_max_percentage": "100%",
    "scales": ["Kecil", "Menengah"],
    "sektor": "Industri"
  }
}
```

**Metadata Fields:**

- `risk_level`: Rendah/Menengah/Tinggi
- `pma_allowed`: true/false (investimento straniero)
- `scales`: Mikro/Kecil/Menengah/Besar
- `sektor`: Settore economico

---

## 🔄 Hybrid Search Architecture

Tutte le collection usano **Hybrid Search** (Dense + Sparse):

```
Query "How much is KITAS?"
         │
         ▼
┌─────────────────────────────────────────┐
│           EMBEDDING                      │
│   text-embedding-004 (Google)           │
│   → Vector 1536 dimensions              │
└─────────────────────┬───────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐
│  Dense Search   │    │  Sparse Search  │
│  (Cosine sim)   │    │     (BM25)      │
│                 │    │                 │
│  Semantic       │    │  Keyword        │
│  matching       │    │  matching       │
└────────┬────────┘    └────────┬────────┘
         │                      │
         └──────────┬───────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │   RRF Fusion        │
         │  (Reciprocal Rank)  │
         └─────────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │   Top-K Results     │
         │   with scores       │
         └─────────────────────┘
```

---

## 📈 Stats Summary

### PostgreSQL

```
Tabelle totali:    70
Tabelle CRM:       9
Tabelle Chat:      6
Tabelle Content:   8
Tabelle Business:  8
Tabelle System:    12
```

### Qdrant

```
Collections:       5
Vettori totali:    6,757
Vector size:       1536 (Google embedding)
Distance metric:   Cosine
Sparse vectors:    BM25 (all collections)
Status:            All green ✅
```

### Data Volume Estimates

```
visa_oracle:       ~100 KB (82 docs)
training_convos:   ~5 MB (3,525 chunks)
tax_genius:        ~500 KB (332 chunks)
kbli_unified:      ~3 MB (2,818 codes)
```

---

## 🔗 Relazioni Chiave

```
clients ─────┬──── practices (1:N)
             ├──── interactions (1:N)
             ├──── client_family_members (1:N)
             └──── documents (1:N)

practices ───┬──── practice_types (N:1)
             └──── renewal_alerts (1:N)

users ───────┬──── conversations (1:N)
             ├──── user_profiles (1:1)
             └──── team_timesheet (1:N)

zantara_content ─┬── content_versions (1:N)
                 └── content_distributions (1:N)
```

---

_"Data is the new oil, well-structured data is refined oil" 🛢️_
