# Intelligent Visa Agent

AI-powered monitoring system for Indonesian Immigration websites using Gemini 2.0 Flash vision capabilities.

## Features

- 🤖 **Vision-Based Detection**: Uses Gemini to visually analyze immigration websites
- 📸 **Screenshot Analysis**: Captures and analyzes homepage banners for critical announcements
- 🔍 **Change Detection**: MD5 hashing to detect content updates
- 📝 **Human-in-the-Loop**: Saves discoveries to staging directory for approval
- 🎯 **Multi-Site Monitoring**:
  - National Immigration (imigrasi.go.id)
  - Regional offices (Ngurah Rai, Denpasar, Singaraja)
  - Labor Ministry (Kemnaker)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ 1. IntelligentVisaAgent                             │
│    - Playwright browser automation                  │
│    - Gemini 2.0 Flash vision analysis               │
│    - MD5 content hashing                            │
└─────────────────────────────────────────────────────┘
                         │
                         ▼ saves to
┌─────────────────────────────────────────────────────┐
│ 2. Staging Directory                                │
│    data/staging/visa/*.json                         │
│    data/staging/news/*.json                         │
└─────────────────────────────────────────────────────┘
                         │
                         ▼ picked up by
┌─────────────────────────────────────────────────────┐
│ 3. Backend API (intel.py)                           │
│    /api/intel/staging/pending                       │
│    /api/intel/staging/approve                       │
└─────────────────────────────────────────────────────┘
                         │
                         ▼ reviewed on
┌─────────────────────────────────────────────────────┐
│ 4. Intelligence Dashboard                           │
│    https://zantara.balizero.com/intelligence        │
│    - Visa Oracle tab                                │
│    - News Room tab                                  │
└─────────────────────────────────────────────────────┘
```

## Installation

### 1. Install Dependencies

```bash
cd apps/kb
pip install -r requirements.txt
playwright install webkit
```

### 2. Configure Environment Variables

Create `.env` file:

```bash
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: Backend URL (defaults to production)
BACKEND_API_URL=https://nuzantara-rag.fly.dev
```

## Usage

### Run Full Scan

```bash
cd apps/kb
python intelligent_visa_agent.py
```

### What It Does

1. **Visa Pages Scan**:
   - Screenshots imigrasi.go.id visa page
   - Asks Gemini to identify visa type links
   - Checks each page for content changes (MD5 hash)
   - Scrapes NEW or UPDATED pages
   - Saves to `data/staging/visa/*.json`

2. **News Scan**:
   - Screenshots immigration news page
   - Asks Gemini to identify policy changes
   - Saves critical news to `data/staging/news/*.json`

3. **Regional Offices**:
   - Scans homepage banners for announcements
   - Detects office closures, system maintenance, new services

### Output Format

Each discovery is saved as JSON in staging:

```json
{
  "id": "abc123def456",
  "type": "visa",
  "title": "🆕 NEW VISA: E28a Investor Kitas",
  "url": "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28a",
  "content": "TITLE: E28A - INVESTOR KITAS\nSOURCE: ...\n...",
  "status": "pending",
  "detected_at": "2026-01-05T12:34:56",
  "detection_type": "NEW",
  "source": "intelligent_visa_agent"
}
```

## Review Process

1. Agent runs daily and saves discoveries to staging
2. Team receives notification (optional Telegram integration)
3. Review at: https://zantara.balizero.com/intelligence/visa-oracle
4. Click **Approve** → ingests to Qdrant Knowledge Base
5. Click **Reject** → archives without ingestion

## Site Map Tracking

The agent maintains a hash map in `config/immigration_site_map.json`:

```json
{
  "imigrasi_national": {
    "https://imigrasi.go.id/.../e28a": "abc123...",
    "https://imigrasi.go.id/.../e33g": "def456..."
  }
}
```

When content hash changes → triggers NEW or UPDATED status.

## Error Handling

All JSON parsing from Gemini responses includes error handling:

```python
try:
    result = json.loads(text)
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse JSON: {e}")
    logger.debug(f"Raw response: {text}")
    return fallback_behavior
```

## Logging

Uses `loguru` for structured logging:

- `🚀` Starting scan
- `📸` Screenshot capture
- `🧠` Gemini analysis
- `🔍` Results
- `✅` Saved to staging
- `❌` Errors

## Scheduling

Run daily via cron:

```bash
# Run at 9 AM daily
0 9 * * * cd /path/to/apps/kb && python intelligent_visa_agent.py >> logs/agent.log 2>&1
```

Or use systemd timer, GitHub Actions, etc.

## Troubleshooting

### "OUTPUT_DIR not defined"
✅ Fixed in latest version (line 38)

### "VISA_URL not defined"
✅ Fixed in latest version (line 26)

### "Failed to parse JSON from Gemini"
- Check `logger.debug` output for raw Gemini response
- Gemini might return explanatory text instead of pure JSON
- Fallback to DOM-based extraction automatically

### "No items saved to staging"
- Check `config/immigration_site_map.json` - might have all pages already tracked
- Delete map file to force re-scan all pages as NEW

## Files

| File | Purpose |
|------|---------|
| `intelligent_visa_agent.py` | Main agent code |
| `config/immigration_site_map.json` | Content hash tracking |
| `data/immigration/visa_*.txt` | Raw scraped visa pages |
| `data/staging/visa/*.json` | Pending visa changes |
| `data/staging/news/*.json` | Pending news items |
| `*.png` | Screenshots (visa_page_analysis, banner_scan, news_scan) |

## Integration with Zantara

The agent integrates with the full Zantara Intelligence system:

1. **Backend**: `apps/backend-rag/backend/app/routers/intel.py`
2. **Frontend**: `apps/mouth/src/app/(workspace)/intelligence/`
3. **Qdrant Collections**:
   - `visa_oracle` (visa changes)
   - `bali_intel_bali_news` (news items)

## Future Enhancements

- [ ] Telegram bot notifications
- [ ] Auto-approve for low-risk changes
- [ ] Diff visualization (old vs new content)
- [ ] Multi-language change summaries (IT/EN/ID)
- [ ] Integration with CRM (notify clients affected by visa changes)

## Credits

Built by Gemini (concept & design) + Claude (implementation & fixes).
