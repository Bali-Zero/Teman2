# Intel Scraper - Monitoring e Notifiche

**Purpose:** Monitorare Intel Scraper e ricevere notifiche per articoli completi pubblicati  
**Last Updated:** 2026-01-24

---

## 🎯 OVERVIEW

Questa guida descrive come avviare l'Intel Scraper e monitorare dove vengono collocati gli articoli completi con cover image.

---

## 🚀 AVVIO INTEL SCRAPER

### Script Disponibili

#### 1. Avvio con Monitoraggio Completo

```bash
cd /Users/antonellosiano/Desktop/nuzantara
./scripts/run_and_monitor_intel.sh
```

**Funzionalità:**

- ✅ Avvia Intel Scraper
- ✅ Monitora articoli completi in tempo reale
- ✅ Invia notifiche Telegram
- ✅ Log completo

#### 2. Avvio Semplice con Notifiche

```bash
cd /Users/antonellosiano/Desktop/nuzantara
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_APPROVAL_CHAT_ID=1125336968
./scripts/start_intel_with_notifications.sh
```

#### 3. Avvio Manuale

```bash
cd apps/bali-intel-scraper
python3 scripts/run_intel_feed.py --mode full
```

**Mode disponibili:**

- `full` - RSS + deep enrichment + immagini
- `quick` - RSS + scoring solo
- `massive` - 790+ sources web scraping
- `enrich-only` - Solo arricchimento articoli pending

---

## 📍 DOVE VENGONO COLLOCATI GLI ARTICOLI

### 1. Articoli Pending (Pre-Approvazione)

**Directory:** `apps/bali-intel-scraper/data/pending_articles/`

**Formato:** `{article_id}.json`

**Contenuto:**

- Articolo completo arricchito
- Cover image path
- Preview HTML path
- Metadata SEO/AEO

**Esempio:**

```json
{
  "id": "475c0ba228d7",
  "title": "Article Title",
  "headline": "Article Headline",
  "cover_image": "data/images/cover_xxx.png",
  "category": "business",
  ...
}
```

### 2. Cover Images

**Directory:** `apps/bali-intel-scraper/data/images/`

**Formato:** `cover_{timestamp}_{slug}.png`

**Generazione:**

- Gemini API (Imagen 4) - priorità 1
- Browser automation - fallback
- Internet search (Unsplash) - ultimo fallback

### 3. Preview HTML

**Directory:** `apps/bali-intel-scraper/data/previews/`

**Formato:** `{article_id}.html`

**Contenuto:**

- Preview completo dell'articolo
- Cover image integrata
- Styling BaliZero
- Pronto per review Telegram

### 4. Articoli Pubblicati (Post-Approvazione)

**Destinazione:** GitHub Repository

**API Endpoint:** `https://nuzantara-rag.fly.dev/api/articles/publish`

**Output:**

- MDX file nel repository GitHub
- Cover image commitata
- Article URL pubblico
- Commit SHA

**Verifica pubblicazione:**

```bash
curl -X GET https://nuzantara-rag.fly.dev/api/articles/publish/status \
  -H "X-API-Key: $ADMIN_API_KEY"
```

---

## 🔍 MONITORAGGIO

### Script di Monitoraggio

**Script:** `scripts/monitor_intel_scraper.sh`

**Funzionalità:**

- Monitora nuovi articoli in `data/pending_articles/`
- Verifica presenza cover image
- Verifica preview HTML
- Invia notifiche Telegram

**Uso:**

```bash
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_APPROVAL_CHAT_ID=1125336968
./scripts/monitor_intel_scraper.sh
```

### Trova Articoli Pubblicati

**Script:** `scripts/find_published_articles.py`

**Funzionalità:**

- Lista tutti gli articoli completi
- Verifica cover image
- Verifica preview HTML
- Verifica pubblicazione GitHub

**Uso:**

```bash
export ADMIN_API_KEY=your_key
./scripts/find_published_articles.py
```

---

## 📊 FLUSSO COMPLETO

```
1. Intel Scraper avviato
   ↓
2. Articoli fetchati e arricchiti
   ↓
3. Cover image generata
   ↓
4. Articolo salvato in: data/pending_articles/{id}.json
   ↓
5. Preview HTML generato in: data/previews/{id}.html
   ↓
6. Notifica Telegram inviata
   ↓
7. Approvazione manuale (via Telegram o UI)
   ↓
8. Pubblicazione via API: /api/articles/publish
   ↓
9. Articolo pubblicato su GitHub
   ↓
10. Article URL disponibile pubblicamente
```

---

## 🔔 NOTIFICHE

### Configurazione Telegram

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_APPROVAL_CHAT_ID=1125336968
```

### Notifiche Automatiche

Le notifiche vengono inviate quando:

- ✅ Nuovo articolo completo creato
- ✅ Cover image generata
- ✅ Preview HTML creato
- ✅ Articolo pubblicato su GitHub

### Formato Notifica

```
📰 Nuovo Articolo Completo

Titolo: Article Title
Categoria: business
ID: 475c0ba228d7

📷 Cover Image: ✅
📄 Preview: ✅

📁 File: data/pending_articles/475c0ba228d7.json
```

---

## 📋 COMANDI RAPIDI

### Avviare Scraper con Monitoraggio

```bash
cd /Users/antonellosiano/Desktop/nuzantara
./scripts/run_and_monitor_intel.sh
```

### Trovare Articoli Completi

```bash
./scripts/find_published_articles.py
```

### Monitorare Solo (senza avviare scraper)

```bash
export TELEGRAM_BOT_TOKEN=your_token
./scripts/monitor_intel_scraper.sh
```

### Verificare Pubblicazioni GitHub

```bash
export ADMIN_API_KEY=your_key
curl -X GET https://nuzantara-rag.fly.dev/api/articles/publish/status \
  -H "X-API-Key: $ADMIN_API_KEY"
```

---

## 🔍 VERIFICA ARTICOLI

### Lista Articoli Pending

```bash
ls -lh apps/bali-intel-scraper/data/pending_articles/*.json
```

### Lista Cover Images

```bash
ls -lh apps/bali-intel-scraper/data/images/cover_*.png
```

### Lista Preview HTML

```bash
ls -lh apps/bali-intel-scraper/data/previews/*.html
```

### Verifica Articolo Specifico

```bash
# Leggi JSON articolo
cat apps/bali-intel-scraper/data/pending_articles/{article_id}.json | jq

# Apri preview HTML
open apps/bali-intel-scraper/data/previews/{article_id}.html
```

---

## 📚 RISORSE

- `PIPELINE_DOCUMENTATION.md` - Documentazione pipeline completa
- `INTEGRAZIONE_PUBLISH_COMPLETA.md` - Integrazione pubblicazione
- Scripts in `scripts/` directory

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
