# DATA REFINEMENT PIPELINE: Indonesian Legal RAG

**Status**: IMPLEMENTED
**Target**: `apps/backend-rag`
**Goal**: Transform raw Indonesian legal documents (PDF/HTML) into high-precision vector embeddings.

---

## 1. THE PROBLEM
Raw ingestion of legal documents fails because:
1.  **Noise**: Headers/Footers (e.g., "Salinan sesuai dengan aslinya", page numbers) break semantic flow.
2.  **Bad Chunking**: Splitting by character count cuts "Pasal" (Articles) in half, losing legal context.
3.  **Missing Context**: A chunk saying "Ayat (1) Dilarang melakukan X" is useless without knowing *which Law* and *which Article* it belongs to.

## 2. THE SOLUTION: "Legal Refinery" Pipeline

We will implement a specialized `LegalIngestionService` that extends the generic ingestion with 4 specific stages.

### Stage 1: The Washer (Cleaning)
**Goal**: Remove non-content artifacts.
**Implementation**: `core/cleaners/legal_cleaner.py`

-   **Header/Footer Removal**:
    -   Regex: `^Halaman \d+ dari \d+`
    -   Regex: `^Salinan sesuai dengan aslinya.*`
    -   Regex: `^PRESIDEN REPUBLIK INDONESIA` (often repeated on every page header)
-   **Whitespace Normalization**: Fix broken line breaks common in PDF extraction.

### Stage 2: The Librarian (Metadata Extraction)
**Goal**: Identify the document *before* processing.
**Implementation**: `core/extractors/legal_metadata.py`

-   **Regex Extraction**:
    -   **Type**: `(UNDANG-UNDANG|PERATURAN PEMERINTAH|KEPUTUSAN PRESIDEN)`
    -   **Number**: `NOMOR\s+(\d+)`
    -   **Year**: `TAHUN\s+(\d{4})`
    -   **Topic**: Text following "TENTANG" until "DENGAN RAHMAT TUHAN..."
-   **Status Check**: (Optional) Cross-reference with external API to check if "Dicabut" (Revoked).

### Stage 3: The Architect (Structure Recognition)
**Goal**: Parse the hierarchical structure of Indonesian Law.
**Structure**:
1.  **Konsiderans**: "Menimbang", "Mengingat"
2.  **Batang Tubuh**:
    -   **BAB** (Chapter)
    -   **Bagian** (Part)
    -   **Paragraf**
    -   **Pasal** (Article) - *CRITICAL UNIT*
    -   **Ayat** (Clause)
3.  **Penjelasan**: (Elucidation) - Often at the end, needs to be linked back to the Pasal.

### Stage 4: The Butcher (Semantic Chunking)
**Goal**: Create self-contained chunks.
**Implementation**: `core/chunkers/legal_chunker.py`

**Strategy**: "Pasal-Aware Chunking"
Instead of `chunk_size=500`, we use a recursive logic:
1.  Split by `Pasal`.
2.  If `Pasal` > 1000 tokens, split by `Ayat`.
3.  **Context Injection**: PREPEND metadata to *every* chunk text.

**Example Chunk Text**:
```text
[CONTEXT: UNDANG-UNDANG NO 12 TAHUN 2024 - TENTANG IKN - BAB II - PASAL 5]
(1) Otorita Ibu Kota Nusantara berkedudukan di Ibu Kota Nusantara.
(2) Otorita Ibu Kota Nusantara merupakan lembaga setingkat kementerian...
```
*Result*: Even if retrieved in isolation, the LLM knows exactly what this is.

---

## 3. IMPLEMENTATION PLAN

### Step 1: Create Core Modules
Create a new directory `backend/core/legal/`:
-   `__init__.py`
-   `cleaner.py` (Regex patterns)
-   `parser.py` (Structure detection)
-   `chunker.py` (Pasal-aware logic)

### Step 2: Create Service
Create `backend/services/legal_ingestion_service.py`:
-   Class `LegalIngestionService`
-   Method `ingest_legal_doc(file_path)`
-   Uses the core modules above.

### Step 3: Integration
-   Update `ingestion_service.py` to route to `LegalIngestionService` if `doc_type == "legal"`.

---

## 4. PYTHON SCRIPT SPECIFICATIONS

### A. `cleaner.py` Snippet
```python
import re

def clean_legal_text(text: str) -> str:
    # Remove "Salinan" footer
    text = re.sub(r"Salinan sesuai dengan aslinya.*?(?=\n)", "", text, flags=re.IGNORECASE)
    # Remove Page Numbers
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
    # Normalize "Pasal 1" spacing
    text = re.sub(r"Pasal\s+(\d+)", r"Pasal \1", text)
    return text.strip()
```

### B. `chunker.py` Logic
```python
def chunk_by_pasal(text: str) -> list[str]:
    # Split by "Pasal X"
    # This is a simplified regex, needs robustness for "Pasal 12A" etc.
    splits = re.split(r"(?=\nPasal\s+\d+)", text)
    return [s.strip() for s in splits if s.strip()]
```
