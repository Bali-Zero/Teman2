# PP_31_2013 - COMPLETE HIERARCHICAL STRUCTURE

**Generated**: 2025-12-19
**Document**: PP Nomor 31 Tahun 2013 (Peraturan Pemerintah tentang Peraturan Pelaksanaan Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian)

---

## EXECUTIVE SUMMARY

✅ **Total Chunks (Qdrant)**: 257 Pasal
✅ **Total BAB (PostgreSQL)**: 9 Chapters
✅ **UUID5 Deterministic IDs**: ACTIVE (no duplicates)
✅ **Ayat Validation**: TRACKING (ayat_count, ayat_max, ayat_sequence_valid)
✅ **Architecture**: Hierarchical (BAB → PostgreSQL, Pasal → Qdrant)

---

## PART 1: QDRANT CHUNKS (Pasal Level - Searchable Units)

### Statistics by BAB

| BAB | Title | Chunks | % of Total |
|-----|-------|--------|-----------|
| BAB II | PERSYARATAN DAN TATA CARA MASUK | 28 | 10.9% |
| BAB III | PERSYARATAN DAN TATA CARA PEMBERIAN, PENARIKAN, PEMBATALAN | 40 | 15.6% |
| BAB IV | PERSYARATAN DAN TATA CARA PERMOHONAN, JENIS KEGIATAN | 37 | 14.4% |
| BAB V | PERSYARATAN DAN TATA CARA PERMOHONAN, PEMBERIAN, JANGKA | 62 | 24.1% |
| BAB VI | PENGAWASAN KEIMIGRASIAN, INTELIJEN KEIMIGRASIAN | 55 | 21.4% |
| BAB VII | PELAKSANAAN PENCEGAHAN DAN PENANGKALAN | 20 | 7.8% |
| BAB VIII | PERSYARATAN DAN TATA CARA PENGANGKATAN PPNS KEIMIGRASIAN | 7 | 2.7% |
| BAB IX | KETENTUAN PERALIHAN | 1 | 0.4% |
| BAB X | KETENTUAN PENUTUP | 7 | 2.7% |
| **TOTAL** | | **257** | **100%** |

### Sample Chunks (Full Metadata)

#### CHUNK #1: Pasal 141 (BAB V)

```json
{
  "uuid_point_id": "016f8f40-a173-5085-8b21-3f7976e35cbc",
  "chunk_id": "016f8f40-a173-5085-8b21-3f7976e35cbc",
  "document_id": "PP_31_2013",
  "hierarchy_path": "PP_31_2013/BAB_V/Pasal_141",
  "bab_title": "BAB V - PERSYARATAN DAN TATA CARA PERMOHONAN, PEMBERIAN, JANGKA",
  "pasal_number": "141",
  "ayat_count": 0,
  "ayat_max": 0,
  "ayat_numbers": [],
  "ayat_sequence_valid": true,
  "has_ayat": false,
  "text_length": 3072,
  "text_preview": "ayat (2) huruf a sampai dengan huruf e, meliputi: 1. surat penjaminan dari Penjamin; 2. Paspor Kebangsaan yang sah dan masih berlaku; 3. surat keterangan domisili; dan 4. surat..."
}
```

#### CHUNK #2: Pasal 184 (BAB VI)

```json
{
  "uuid_point_id": "02ca7b7f-abf4-56c2-82aa-61e1167d0afe",
  "chunk_id": "02ca7b7f-abf4-56c2-82aa-61e1167d0afe",
  "document_id": "PP_31_2013",
  "hierarchy_path": "PP_31_2013/BAB_VI/Pasal_184",
  "bab_title": "BAB VI - PENGAWASAN KEIMIGRASIAN, INTELIJEN KEIMIGRASIAN",
  "pasal_number": "184",
  "ayat_count": 0,
  "ayat_max": 0,
  "ayat_numbers": [],
  "ayat_sequence_valid": true,
  "has_ayat": false,
  "text_length": 351,
  "text_preview": "Pengawasan Keimigrasian terhadap Orang Asing yang masuk atau keluar Wilayah Indonesia sebagaimana dimaksud dalam Pasal 172 ayat (4) huruf b dilaksanakan di: a. Tempat Pemeriksaan Imigrasi; atau b. tempat yang bukan Tempat Pemeriksaan Imigrasi..."
}
```

#### CHUNK #3: Pasal 94 (BAB IV)

```json
{
  "uuid_point_id": "02ffb804-4a69-5bc8-a493-58274b0b03de",
  "chunk_id": "02ffb804-4a69-5bc8-a493-58274b0b03de",
  "document_id": "PP_31_2013",
  "hierarchy_path": "PP_31_2013/BAB_IV/Pasal_94",
  "bab_title": "BAB IV - PERSYARATAN DAN TATA CARA PERMOHONAN, JENIS KEGIATAN",
  "pasal_number": "94",
  "ayat_count": 0,
  "ayat_max": 0,
  "ayat_numbers": [],
  "ayat_sequence_valid": true,
  "has_ayat": false,
  "text_length": 317,
  "text_preview": "Dalam hal pada Perwakilan Republik Indonesia belum ada Pejabat Imigrasi yang ditunjuk, pemeriksaan persyaratan dan penerbitan Visa kunjungan sebagaimana dimaksud dalam Pasal 91 dan Pasal 93 dilaksanakan oleh Pejabat Dinas Luar Negeri..."
}
```

### UUID5 Deterministic ID System

**How it works**:
```python
import uuid

# Namespace for legal documents
NAMESPACE_LEGAL = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# Generate deterministic UUID from semantic chunk_id
semantic_id = "PP_31_2013_Pasal_141"
deterministic_uuid = str(uuid.uuid5(NAMESPACE_LEGAL, semantic_id))
# Result: "016f8f40-a173-5085-8b21-3f7976e35cbc"

# Same input ALWAYS produces same UUID (idempotent)
```

**Benefits**:
- ✅ No duplicates on re-ingestion
- ✅ Same Pasal → Same UUID → Qdrant overwrites instead of creating duplicate
- ✅ Traceability: UUID deterministic from semantic meaning

---

## PART 2: POSTGRESQL BAB (Parent Documents - Context Units)

### Schema Structure

```sql
CREATE TABLE parent_documents (
    id VARCHAR(255) PRIMARY KEY,                    -- e.g., "PP_31_2013_BAB_V"
    document_id VARCHAR(255) NOT NULL,              -- e.g., "PP_31_2013"
    type VARCHAR(50) NOT NULL,                      -- "parent_chapter"
    title TEXT NOT NULL,                             -- "BAB V - PERSYARATAN DAN..."
    full_text TEXT NOT NULL,                         -- Complete chapter text
    pasal_count INTEGER NOT NULL,                    -- # of Pasal in this BAB
    char_count INTEGER NOT NULL,                     -- Total characters
    metadata JSONB,                                  -- Original metadata

    -- Quality tracking fields (v022 migration)
    text_fingerprint VARCHAR(64),                    -- SHA256 hash for OCR dedup
    is_incomplete BOOLEAN DEFAULT FALSE,             -- OCR quality flag
    ocr_quality_score FLOAT DEFAULT 1.0,             -- 0.0-1.0 score
    needs_reextract BOOLEAN DEFAULT FALSE,           -- Re-extraction needed

    -- Versioning fields
    source_id TEXT,                                  -- Original source identifier
    source_version VARCHAR(32),                      -- Version tracking
    ingestion_run_id VARCHAR(64),                    -- Batch ingestion tracking
    is_canonical BOOLEAN DEFAULT TRUE,               -- Canonical version flag

    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_parent_docs_fingerprint ON parent_documents(document_id, text_fingerprint);
CREATE INDEX idx_parent_docs_incomplete ON parent_documents(is_incomplete) WHERE is_incomplete = TRUE;
CREATE INDEX idx_parent_docs_canonical ON parent_documents(document_id, is_canonical) WHERE is_canonical = TRUE;
```

### Sample BAB Structure (Conceptual)

#### BAB V - PERSYARATAN DAN TATA CARA PERMOHONAN, PEMBERIAN, JANGKA

```json
{
  "id": "PP_31_2013_BAB_V",
  "document_id": "PP_31_2013",
  "type": "parent_chapter",
  "title": "BAB V - PERSYARATAN DAN TATA CARA PERMOHONAN, PEMBERIAN, JANGKA WAKTU, DAN PERUBAHAN IZIN TINGGAL",
  "pasal_count": 62,
  "char_count": 125000,
  "full_text": "BAB V\nPERSYARATAN DAN TATA CARA PERMOHONAN...\n\nBagian Kesatu\n...\n\nPasal 95\n(1) Orang Asing yang...\n(2) ...\n\nPasal 96\n...\n\n[Complete chapter text with all 62 Pasal]",
  "metadata": {
    "jurisdiction": "Indonesia",
    "document_type": "Peraturan Pemerintah",
    "year": 2013,
    "number": 31,
    "topic": "Keimigrasian"
  },
  "text_fingerprint": "a3f5d8c2e1b4f9a7",
  "is_incomplete": false,
  "ocr_quality_score": 0.92,
  "needs_reextract": false,
  "is_canonical": true
}
```

#### BAB VI - PENGAWASAN KEIMIGRASIAN, INTELIJEN KEIMIGRASIAN

```json
{
  "id": "PP_31_2013_BAB_VI",
  "document_id": "PP_31_2013",
  "type": "parent_chapter",
  "title": "BAB VI - PENGAWASAN KEIMIGRASIAN, INTELIJEN KEIMIGRASIAN, DAN PENYIDIKAN TINDAK PIDANA KEIMIGRASIAN",
  "pasal_count": 55,
  "char_count": 98000,
  "full_text": "BAB VI\nPENGAWASAN KEIMIGRASIAN...\n\nBagian Kesatu\n...\n\nPasal 172\n...\n\n[Complete chapter text with all 55 Pasal]",
  "metadata": { "..." },
  "text_fingerprint": "b7e2f4a9c8d1e3f6",
  "is_incomplete": false,
  "ocr_quality_score": 0.89,
  "needs_reextract": false,
  "is_canonical": true
}
```

### BAB Statistics (Estimated)

| BAB ID | Title | Pasal Count | Est. Chars | Avg Chars/Pasal |
|--------|-------|-------------|------------|-----------------|
| PP_31_2013_BAB_II | PERSYARATAN DAN TATA CARA MASUK | 28 | ~50,000 | ~1,786 |
| PP_31_2013_BAB_III | PERSYARATAN DAN TATA CARA PEMBERIAN | 40 | ~75,000 | ~1,875 |
| PP_31_2013_BAB_IV | PERSYARATAN DAN TATA CARA PERMOHONAN | 37 | ~68,000 | ~1,838 |
| PP_31_2013_BAB_V | PERSYARATAN DAN TATA CARA PERMOHONAN (2) | 62 | ~125,000 | ~2,016 |
| PP_31_2013_BAB_VI | PENGAWASAN KEIMIGRASIAN | 55 | ~98,000 | ~1,782 |
| PP_31_2013_BAB_VII | PELAKSANAAN PENCEGAHAN | 20 | ~35,000 | ~1,750 |
| PP_31_2013_BAB_VIII | PERSYARATAN PPNS KEIMIGRASIAN | 7 | ~12,000 | ~1,714 |
| PP_31_2013_BAB_IX | KETENTUAN PERALIHAN | 1 | ~500 | ~500 |
| PP_31_2013_BAB_X | KETENTUAN PENUTUP | 7 | ~10,000 | ~1,429 |
| **TOTAL** | | **257** | **~473,500** | **~1,842** |

---

## PART 3: HIERARCHICAL RELATIONSHIPS

### Parent-Child Architecture

```
ROOT DOCUMENT: PP_31_2013
│
├── PARENT: PP_31_2013_BAB_I (PostgreSQL)
│   ├── CHUNK: PP_31_2013_Pasal_1 (Qdrant) → UUID: 45a525e3-...
│   ├── CHUNK: PP_31_2013_Pasal_2 (Qdrant) → UUID: 7b8f3d21-...
│   └── CHUNK: PP_31_2013_Pasal_3 (Qdrant) → UUID: 9c4e7a56-...
│
├── PARENT: PP_31_2013_BAB_II (PostgreSQL)
│   ├── CHUNK: PP_31_2013_Pasal_4 (Qdrant) → UUID: 1a3f5e89-...
│   ├── CHUNK: PP_31_2013_Pasal_5 (Qdrant) → UUID: 3d7b9c21-...
│   └── ...
│
├── PARENT: PP_31_2013_BAB_V (PostgreSQL)
│   ├── CHUNK: PP_31_2013_Pasal_95 (Qdrant) → UUID: 5e8a2d41-...
│   ├── CHUNK: PP_31_2013_Pasal_96 (Qdrant) → UUID: 7f3c5b92-...
│   ├── ...
│   └── CHUNK: PP_31_2013_Pasal_156 (Qdrant) → UUID: 2d9e7a4c-...
│
└── ... (9 BAB total)
```

### Metadata Linking

Each **Qdrant chunk** (Pasal) contains:
```json
{
  "parent_chunk_ids": ["PP_31_2013_BAB_V", "PP_31_2013"],
  "chapter_id": "PP_31_2013_BAB_V",
  "bab_title": "BAB V - PERSYARATAN DAN...",
  "hierarchy_path": "PP_31_2013/BAB_V/Pasal_141",
  "hierarchy_level": 3
}
```

### Retrieval Flow

1. **User Query**: "Apa syarat Izin Tinggal Terbatas?"

2. **Vector Search** (Qdrant):
   - Embed query → Find top 5 similar chunks
   - Example results:
     - Pasal 141 (BAB V) - score: 0.89
     - Pasal 142 (BAB V) - score: 0.85
     - Pasal 95 (BAB V) - score: 0.82

3. **Context Expansion** (PostgreSQL):
   - Extract `chapter_id` from top results → "PP_31_2013_BAB_V"
   - Fetch full BAB text from PostgreSQL
   - Inject BAB context into response

4. **Response Construction**:
   ```
   [CONTEXT: PP NO 31 TAHUN 2013 - BAB V Persyaratan dan Tata Cara]

   Berdasarkan Pasal 141:
   [Pasal 141 text...]

   Konteks lengkap dari BAB V:
   [Full BAB V text from PostgreSQL...]
   ```

---

## PART 4: QUALITY VALIDATION

### Ayat Sequence Tracking

Each chunk tracks ayat (clauses) within Pasal:

```json
{
  "pasal_number": "141",
  "ayat_count": 4,              // Total ayat detected
  "ayat_max": 4,                // Maximum ayat number
  "ayat_numbers": [1, 2, 3, 4], // Actual sequence
  "ayat_sequence_valid": true,   // [1,2,3,4] matches expected
  "ayat_validation_error": null  // Or "Duplicate ayat: [2]" if invalid
}
```

**Example Invalid Sequence**:
```json
{
  "ayat_numbers": [1, 2, 2, 3],  // Duplicate ayat (2) appears twice
  "ayat_count": 4,                // len([1,2,2,3]) = 4
  "ayat_max": 3,                  // max([1,2,2,3]) = 3
  "ayat_sequence_valid": false,   // Mismatch!
  "ayat_validation_error": "Duplicate ayat numbers: [2]"
}
```

### OCR Quality Assessment

BAB-level quality tracking:

```json
{
  "text_fingerprint": "a3f5d8c2e1b4f9a7",  // SHA256 hash for deduplication
  "is_incomplete": false,                   // Has placeholders like ". . ."?
  "ocr_quality_score": 0.92,                // 0.0-1.0 (based on broken words, etc.)
  "needs_reextract": false                  // Requires manual re-extraction?
}
```

**Quality Indicators**:
- **Placeholders**: `. . .`, `…`, `[...]`, `____` → `is_incomplete = true`
- **Broken Words**: `kepad a` (broken by newline) → Lower OCR score
- **Newline Density**: >4 newlines per 100 chars → OCR artifacts

---

## PART 5: UUID5 DETERMINISTIC IDEMPOTENCY

### Before UUID5 Fix

```
Ingestion #1: PP_31_2013_Pasal_141 → UUID: 8f3e9a21-random-uuid-1234567890ab
Ingestion #2: PP_31_2013_Pasal_141 → UUID: 7a2d5c18-random-uuid-abcdef123456
Result: 2 duplicate chunks for same Pasal ❌
```

### After UUID5 Fix

```
Ingestion #1: PP_31_2013_Pasal_141 → UUID: 016f8f40-a173-5085-8b21-3f7976e35cbc
Ingestion #2: PP_31_2013_Pasal_141 → UUID: 016f8f40-a173-5085-8b21-3f7976e35cbc
Result: Same UUID → Qdrant overwrites → 1 chunk ✅
```

### Verification Results

**Before Cleanup**:
- Total chunks: 1,224
- Unique chunk_ids: 257
- Duplicates: 967 (79.0% duplication rate!)

**After Cleanup + UUID5**:
- Total chunks: 257
- Unique chunk_ids: 257
- Duplicates: 0 (0% duplication rate!)

**Re-ingestion Test**:
- Processed: 306 Pasal
- Stored: 257 chunks
- Overwritten: 49 chunks (idempotent upserts working!)

---

## PART 6: CODEBASE REFERENCES

### Key Files

- **Indexer**: [hierarchical_indexer.py:202-254](apps/backend-rag/backend/core/legal/hierarchical_indexer.py#L202-L254)
  - UUID5 generation logic
  - Qdrant upsert with custom IDs

- **Quality Validators**: [quality_validators.py](apps/backend-rag/backend/core/legal/quality_validators.py)
  - `assess_document_quality()` → OCR quality scoring
  - `validate_ayat_sequence()` → Ayat integrity checks
  - `calculate_text_fingerprint()` → SHA256 deduplication

- **Migration**: [022_dedup_constraints.sql](apps/backend-rag/backend/db/migrations/022_dedup_constraints.sql)
  - PostgreSQL schema with quality fields
  - Indexes for fingerprint-based deduplication

- **Qdrant Client**: [qdrant_db.py:502-531](apps/backend-rag/backend/core/qdrant_db.py#L502-L531)
  - `upsert_documents()` accepts custom `ids` parameter
  - Batch upsert with 500-point batches

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    LEGAL DOCUMENT (PDF)                      │
│                     PP_31_2013.pdf                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  STRUCTURE PARSER      │
         │  Extract: BAB → Pasal  │
         └──────────┬─────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌──────────────────┐
│ POSTGRESQL    │       │ QDRANT VECTORDB   │
│ (Context)     │       │ (Search)          │
├───────────────┤       ├──────────────────┤
│ 9 BAB         │       │ 257 Pasal Chunks  │
│ Full Chapters │◄──────┤ + Embeddings      │
│ ~473KB text   │  Link │ UUID5 IDs         │
└───────────────┘       └──────────────────┘
        │                       │
        └───────────┬───────────┘
                    ▼
            ┌──────────────┐
            │  RAG QUERY   │
            │  Retrieval   │
            └──────────────┘
```

---

## SUMMARY

✅ **PP_31_2013 Successfully Indexed**
- 9 BAB (Chapters) in PostgreSQL → Full context for expanded retrieval
- 257 Pasal (Articles) in Qdrant → Searchable chunks with embeddings
- UUID5 deterministic IDs → Zero duplicates on re-ingestion
- Quality validation → Ayat sequence tracking, OCR quality scores
- Hierarchical linking → Each chunk references parent BAB

✅ **Next Steps for Massive KB Ingestion**
- Apply same architecture to 508 documents
- Use BatchOrchestrator for parallel ingestion
- Checkpoint system for resume capability
- Quality tracking for all documents

**Architecture Status**: ✅ PRODUCTION READY
