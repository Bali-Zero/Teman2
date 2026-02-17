# KB Sources for NotebookLM Golden Seeds

## Available Documents

### 1. Regulations (PDFs)

- **PP 28/2025** - Latest KBLI classification and business regulations
- **KBLI 2020** - Previous classification (reference)

### 2. Structured Data (JSON)

- **KBLI 2025 Final** - 9,612 business classifications with:
  - PMA status (foreign investment allowed)
  - Risk categories (low/medium/high)
  - Scale requirements
  - Sector mappings

## Upload to NotebookLM

Copy these files:

```bash
cp source_documents/PP\ Nomor\ 28\ Tahun\ 2025.pdf data/kb_sources/
cp source_documents/KBLI_2025_FINAL_CLEAN.json data/kb_sources/
cp data/kbli_pdfs/*.pdf data/kb_sources/
```

Then upload to: https://notebooklm.google.com
