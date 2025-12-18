# Peraturan.go.id Legal Document Spider

Scrapes Indonesian legal documents from https://peraturan.go.id/ for RAG system ingestion.

## Features

- **Smart API Detection**: Automatically detects if the site uses JSON API endpoints (faster) or falls back to HTML parsing
- **Automatic Pagination**: Handles pagination automatically by detecting "Next" buttons
- **PDF Download**: Downloads PDF files to `data/raw_laws/`
- **Metadata Extraction**: Extracts title, category (UU, Perpres, etc.), year, number, and PDF URL
- **Rate Limiting**: Respectful scraping with 1-3 second delays between requests
- **Retry Logic**: Automatic retries with exponential backoff for network errors
- **User Agent Rotation**: Uses fake-useragent for realistic browser headers

## Installation

### 1. Install Python Dependencies

```bash
cd apps/kb
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

Or install all browsers:

```bash
playwright install
```

## Usage

### Test Mode (First 5 Items)

```bash
python peraturan_spider.py --test
```

This will:
- Scrape the first 5 legal documents
- Download their PDFs
- Verify PDF validity
- Save metadata to `data/laws_metadata.jsonl`

### Full Scrape

```bash
# Scrape all available documents
python peraturan_spider.py

# Limit to specific number
python peraturan_spider.py --limit 100
```

## Output Structure

```
apps/kb/
├── data/
│   ├── raw_laws/              # Downloaded PDF files
│   │   ├── uu_2023_12_peraturan-tentang-xyz.pdf
│   │   └── ...
│   └── laws_metadata.jsonl    # Metadata in JSONL format
├── logs/                      # Execution logs
│   └── peraturan_spider_*.log
├── peraturan_spider.py        # Main scraper script
├── requirements.txt
└── README.md
```

## Metadata Format

Each line in `laws_metadata.jsonl` contains:

```json
{
  "title": "Peraturan tentang XYZ",
  "category": "UU",
  "year": 2023,
  "number": "12",
  "pdf_download_url": "https://peraturan.go.id/...",
  "local_filename": "uu_2023_12_peraturan-tentang-xyz.pdf",
  "scraped_at": "2024-01-15T10:30:00"
}
```

## Configuration

Edit constants in `peraturan_spider.py`:

- `MIN_DELAY` / `MAX_DELAY`: Rate limiting delays (default: 1-3 seconds)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `RETRY_DELAY`: Base delay for retries (default: 5 seconds)

## Error Handling

The spider includes:
- Network timeout handling (30s timeout)
- PDF validation (checks for PDF header)
- Graceful error recovery
- Detailed logging to `logs/peraturan_spider_*.log`

## Integration with RAG System

After scraping, you can ingest the documents into the RAG system:

1. PDFs are stored in `data/raw_laws/`
2. Metadata is in `data/laws_metadata.jsonl`
3. Use the RAG ingestion pipeline to process PDFs and add to Qdrant

## Notes

- The scraper respects rate limits to avoid IP bans
- PDFs are validated before saving (must start with `%PDF`)
- Duplicate downloads are skipped (checks file existence)
- The script automatically detects the best scraping method (API vs HTML)
