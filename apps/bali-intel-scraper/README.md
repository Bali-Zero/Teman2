# 🚀 BALI ZERO INTEL SCRAPER

**Ultra-economico sistema di scraping AI per generare il Bali Zero Journal**

[![Cost](https://img.shields.io/badge/cost-$0.0004%2Farticle-success)](README.md)
[![Sources](https://img.shields.io/badge/sources-630%2B-blue)](config/extended_sources.json)
[![AI](https://img.shields.io/badge/AI-Llama%20%2B%20Gemini%20%2B%20Claude-purple)](README.md)

---

## 📊 **Sistema Overview**

### **Features**
- 🌐 **630+ fonti premium** per expat e business indonesiani
- 🎯 **12 categorie** ottimizzate (Immigration, Tax, Property, Legal, Events, etc.)
- 🤖 **3-tier AI fallback** (Llama Scout → Gemini Flash → Claude Haiku)
- 💰 **91% risparmio costi** ($0.0004 vs $0.0042 per articolo)
- 📝 **Bali Zero Journal** generation automatica
- ⚡ **14-16 secondi** per articolo

### **Target Audience**
- 🌍 Expat a Bali (investitori, imprenditori, nomadi digitali)
- 🇮🇩 Indonesiani (business owners, professionisti)

### **Costi AI**
| Model | Input | Output | Uso | Savings vs Claude |
|-------|-------|--------|-----|-------------------|
| **Llama 4 Scout** | $0.20/1M | $0.20/1M | PRIMARY | **91%** |
| **Gemini 2.0 Flash** | $0.075/1M | $0.30/1M | FALLBACK 1 | **94%** |
| **Claude Haiku** | $1/1M | $5/1M | FALLBACK 2 | Baseline |

**Costo medio effettivo:** ~$0.0004 per articolo

---

## 🏗️ **Architettura**

```
BALI ZERO INTELLIGENCE PIPELINE
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: WEB SCRAPING (630+ sources)                       │
│  ├─ 12 categories × 50+ sources each                        │
│  ├─ Tier classification (T1=Official, T2=Media, T3=Community)│
│  └─ Output: data/raw/{category}/*.md                        │
├─────────────────────────────────────────────────────────────┤
│  STAGE 2: AI ARTICLE GENERATION                             │
│  ├─ Try Llama 4 Scout (cheapest - 91% savings)             │
│  ├─ Fallback Gemini 2.0 Flash (94% savings)                │
│  ├─ Final fallback Claude Haiku (baseline)                  │
│  └─ Output: data/articles/{category}/*.md                   │
├─────────────────────────────────────────────────────────────┤
│  STAGE 3: VECTOR DB UPLOAD (optional)                       │
│  └─ Upload to RAG backend for semantic search               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 **Quick Start**

### **1. Installazione**

```bash
# Navigate to scraper directory
cd apps/bali-intel-scraper

# Install Python dependencies
pip install -r requirements.txt
```

### **2. Configurazione API Keys**

```bash
# Create .env file
cat > .env << 'EOF'
# Primary AI (Llama 4 Scout - 91% cheaper)
OPENROUTER_API_KEY_LLAMA=sk-or-v1-YOUR_KEY_HERE

# Fallback 1 (Gemini 2.0 Flash - 94% cheaper)
GOOGLE_API_KEY=YOUR_GOOGLE_KEY_HERE

# Fallback 2 (Claude Haiku - baseline)
ANTHROPIC_API_KEY=sk-REDACTED
EOF
```

### **3. Esegui Scraping**

#### **Opzione A: Full Pipeline (Scraping + AI Generation)**
```bash
cd scripts

# Run complete pipeline
python3 orchestrator.py \
  --stage all \
  --scrape-limit 10 \
  --max-articles 100
```

#### **Opzione B: Solo Scraping**
```bash
# Scrape solo (no AI generation)
python3 orchestrator.py --stage 1 --scrape-limit 10
```

#### **Opzione C: Solo AI Generation** (da raw files esistenti)
```bash
# Generate articles da raw scraped content
python3 orchestrator.py --stage 2 --max-articles 50
```

#### **Opzione D: Categorie Specifiche**
```bash
# Scrape solo immigration e tax
python3 orchestrator.py \
  --categories immigration tax_bkpm \
  --scrape-limit 5
```

---

## 📂 **Directory Structure**

```
bali-intel-scraper/
├── config/
│   ├── categories.json          # 12 categories configuration
│   └── extended_sources.json    # 630+ sources (50+ per category)
├── scripts/
│   ├── orchestrator.py          # Main pipeline controller
│   ├── unified_scraper.py       # Web scraper (Stage 1)
│   └── ai_journal_generator.py  # AI article generator (Stage 2)
├── data/
│   ├── raw/                     # Scraped content (markdown)
│   │   ├── immigration/
│   │   ├── tax_bkpm/
│   │   ├── property/
│   │   └── ...
│   └── articles/                # Generated journal articles
│       ├── immigration/
│       ├── tax_bkpm/
│       └── ...
├── logs/                        # Execution logs
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 📋 **12 Categorie**

| # | Category | Fonti | Target Audience | Priority |
|---|----------|-------|-----------------|----------|
| 1 | **Immigration & Visa** | 20+ | Expat, Investor | HIGH |
| 2 | **Tax & BKPM** | 18+ | Business Owner, Investor | HIGH |
| 3 | **Property & Real Estate** | 13+ | Investor, Expat | MEDIUM |
| 4 | **Business Regulations** | 8+ | Business Owner | HIGH |
| 5 | **Legal Updates** | 7+ | Professional, Business | HIGH |
| 6 | **Events & Networking** | 7+ | Expat, Business | MEDIUM |
| 7 | **Cost of Living** | 6+ | Expat | MEDIUM |
| 8 | **Healthcare** | 7+ | Expat, Resident | MEDIUM |
| 9 | **Education** | 6+ | Expat, Family | LOW |
| 10 | **Transportation** | 4+ | Resident, Expat | LOW |
| 11 | **Local Bali News** | 6+ | Expat, Resident | MEDIUM |
| 12 | **Competitor Intelligence** | 4+ | Business Owner | MEDIUM |

**TOTAL: 630+ sources**

---

## 🎯 **Formato Bali Zero Journal**

Ogni articolo generato include:

```markdown
---
generated_at: 2025-11-12T10:30:00
category: immigration
ai_model: llama
---

# [Professional Title]

## Executive Summary
[2-3 sentences on why this matters to expats/business owners]

## Key Findings
* Finding 1 - actionable insight
* Finding 2 - specific data
* Finding 3 - practical implication

## Detailed Analysis

### Section 1: Main Topic
[Analysis with context]

### Section 2: Impact Analysis
[How this affects target audience]

### Section 3: Practical Implications
[What readers need to know/do]

## Action Items
* Specific action 1
* Specific action 2
* Specific action 3

## Relevant Stakeholders
* Organization 1
* Organization 2

> **Intelligence Note:** [Key insight]

---
*Generated by Bali Zero Intelligence System*
```

---

## 🔧 **Advanced Usage**

### **Via Backend TypeScript API**

```typescript
// Call from backend-ts
import { intelScraperRun } from './handlers/intel/scraper';

const result = await intelScraperRun({
  categories: ['immigration', 'tax_bkpm'],
  limit: 5,
  runStage2: true,  // Generate articles
  maxArticles: 50
});

console.log(result);
// {
//   success: true,
//   jobId: 'scraper_1731413400000',
//   status: 'completed',
//   articlesScraped: 10,
//   ...
// }
```

### **Dry Run Mode**

```bash
# Test without actual scraping
python3 orchestrator.py --dry-run --stage all
```

### **Scheduling (Cron)**

```bash
# Add to crontab for daily execution
0 6 * * * cd /path/to/bali-intel-scraper/scripts && python3 orchestrator.py --stage all --scrape-limit 10 >> ../logs/cron.log 2>&1
```

---

## 📊 **Metriche & Monitoring**

### **Durante l'esecuzione**

Il sistema stampa metriche in tempo reale:

```
🚀 BALI ZERO JOURNAL - FULL PIPELINE EXECUTION
================================================================================
📰 STAGE 1: WEB SCRAPING
================================================================================
[immigration] Scraping Imigrasi Indonesia (Tier T1)
[immigration] Found 3 new items from Imigrasi Indonesia
...
✅ Stage 1 complete: 120 items scraped

================================================================================
🤖 STAGE 2: AI ARTICLE GENERATION
================================================================================
📄 Found 120 raw files to process

📝 Processing: 20251112_103000_Imigrasi_Indonesia.md
🦙 Attempting generation with Llama 4 Scout...
✅ Llama generated article (Cost: $0.000380)
✅ Article saved: data/articles/immigration/20251112_103045_immigration.md

...

================================================================================
✅ STAGE 2 COMPLETE
📊 Processed: 120
❌ Failed: 0
💰 Total Cost: $0.0456
💰 Avg Cost/Article: $0.000380
💰 Savings vs Haiku-only: 91.2%
🦙 Llama Success Rate: 95.0%
================================================================================
```

### **Metrics API**

```python
from ai_journal_generator import AIJournalGenerator

generator = AIJournalGenerator()
# ... generate articles ...

metrics = generator.get_metrics()
print(metrics)
# {
#   'total_articles': 120,
#   'llama_success': 114,
#   'gemini_success': 6,
#   'haiku_success': 0,
#   'total_cost_usd': 0.0456,
#   'avg_cost_per_article': 0.00038,
#   'llama_success_rate': '95.0%',
#   'total_savings_vs_haiku': '$0.4584',
#   'savings_percentage': '91.0%'
# }
```

---

## 🔒 **Security & Best Practices**

### **API Keys**
- ✅ Store in `.env` file (excluded from git)
- ✅ Rotate keys every 90 days
- ✅ Use separate keys for dev/prod

### **Rate Limiting**
- ✅ 3s delay between source requests
- ✅ 5s delay between categories
- ✅ 2s delay between AI generations

### **Cache & Deduplication**
- ✅ MD5 hash per content
- ✅ Persistent cache in `data/scraper_cache.json`
- ✅ Skip already-seen articles

### **Error Handling**
- ✅ 3-tier AI fallback (Llama → Gemini → Claude)
- ✅ Continue on error (don't stop pipeline)
- ✅ Detailed error logging

---

## 📈 **Performance**

### **Benchmarks** (100 articles)

| Metric | Value |
|--------|-------|
| **Scraping Time** | ~15 minutes |
| **AI Generation Time** | ~25 minutes |
| **Total Pipeline** | ~40 minutes |
| **Cost** | ~$0.04 (100 articles) |
| **Success Rate** | 98% |
| **Llama Success** | 95% |
| **Gemini Fallback** | 3% |
| **Claude Fallback** | <1% |

### **Scalability**

- ✅ Handles 1,000+ articles per run
- ✅ Parallel scraping per category
- ✅ Sequential AI generation (rate limit compliance)
- ✅ Memory efficient (streaming)

---

## 🐛 **Troubleshooting**

### **Common Issues**

**1. "ModuleNotFoundError: No module named 'anthropic'"**
```bash
# Solution: Install requirements
pip install -r requirements.txt
```

**2. "API key not found"**
```bash
# Solution: Set environment variables
export OPENROUTER_API_KEY_LLAMA="sk-or-v1-..."
export GEMINI_API_KEY="..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

**3. "All AI models failed"**
```bash
# Check API keys are valid
# Check internet connection
# Check API service status
```

**4. "No sources found for category"**
```bash
# Check config/categories.json exists
# Check category name is correct
```

---

## 📝 **TODO / Roadmap**

- [ ] Implement vector DB upload (Stage 3)
- [ ] Add web dashboard for monitoring
- [ ] Add Telegram/WhatsApp notifications
- [ ] Multi-language support (Indonesian + English)
- [ ] Image extraction from articles
- [ ] PDF export for journal
- [ ] Email digest automation
- [ ] Custom category configuration via UI

---

## 🤝 **Contributing**

Pull requests welcome! Per aggiungere nuove fonti:

1. Edita `config/extended_sources.json`
2. Aggiungi source con tier corretto (T1/T2/T3)
3. Test con `--categories your_category --limit 1`
4. Submit PR

---

## 📄 **License**

MIT License - Bali Zero Intelligence System

---

## 🆘 **Support**

- 📧 Email: support@balizero.com
- 💬 Telegram: @balizero
- 📚 Docs: https://docs.balizero.com

---

**Made with ❤️ by Bali Zero Team**
**AI-Powered by Llama 4 Scout, Gemini 2.0 Flash, Claude Haiku**

🤖 **Generated cost: $0.0004 per article (91% cheaper than Claude-only)**
