# Intel Scraper - Dove Vengono Collocati gli Articoli Pubblicati

**Purpose:** Documentare dove vengono salvati e pubblicati gli articoli completi con cover image  
**Last Updated:** 2026-01-24

---

## 📍 POSIZIONI ARTICOLI

### 1. Articoli Pending (Pre-Approvazione)

**Directory Locale:**

```
apps/bali-intel-scraper/data/pending_articles/{article_id}.json
```

**Contenuto:**

- Articolo completo arricchito
- Cover image path
- Preview HTML path
- Metadata SEO/AEO
- Status: `pending`

**Esempio:**

```json
{
  "article_id": "475c0ba228d7",
  "title": "Article Title",
  "cover_image": "data/images/cover_xxx.png",
  "preview_html": "data/previews/475c0ba228d7.html",
  "status": "pending"
}
```

### 2. Cover Images

**Directory Locale:**

```
apps/bali-intel-scraper/data/images/cover_{timestamp}_{slug}.png
```

**Generazione:**

1. Gemini API (Imagen 4) - priorità 1
2. Browser automation - fallback
3. Internet search (Unsplash) - ultimo fallback

### 3. Preview HTML

**Directory Locale:**

```
apps/bali-intel-scraper/data/previews/{article_id}.html
```

**Contenuto:**

- Preview completo dell'articolo
- Cover image integrata
- Styling BaliZero
- Pronto per review Telegram

### 4. Articoli Pubblicati (Post-Approvazione)

**Destinazione:** GitHub Repository

**Repository:** `Balizero1987/Teman2`

**Percorsi GitHub:**

#### MDX File

```
apps/mouth/src/content/articles/{category}/{slug}.mdx
```

**Categorie → Folder:**

- `immigration` → `immigration`
- `business` → `business`
- `tax` / `tax-legal` / `legal` → `tax-legal`
- `property` → `property`
- `lifestyle` → `lifestyle`
- `tech` → `tech`

#### Cover Image

```
apps/mouth/public/static/news/{image_filename}
```

**URL Pubblico Immagine:**

```
https://balizero.com/static/news/{image_filename}
```

#### Article URL Pubblico

```
https://balizero.com/{category}/{slug}
```

**Esempio:**

- Categoria: `business`
- Slug: `indonesia-ai-partnership`
- URL: `https://balizero.com/business/indonesia-ai-partnership`

---

## 🔍 COME VERIFICARE PUBBLICAZIONI

### Script Automatico

```bash
cd /Users/antonellosiano/Projects/nuzantara
./scripts/monitor_intel_published_articles.sh
```

**Output:**

- Lista articoli completi
- Verifica cover image
- Verifica preview HTML
- Verifica pubblicazione GitHub
- URL pubblici

### Verifica Manuale

#### 1. Articoli Pending

```bash
ls -lh apps/bali-intel-scraper/data/pending_articles/*.json
```

#### 2. Cover Images

```bash
ls -lh apps/bali-intel-scraper/data/images/cover_*.png
```

#### 3. Preview HTML

```bash
ls -lh apps/bali-intel-scraper/data/previews/*.html
```

#### 4. Verifica GitHub (se hai GITHUB_TOKEN)

```bash
export GITHUB_TOKEN=your_token
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/Balizero1987/Teman2/contents/apps/mouth/src/content/articles/business/"
```

#### 5. Verifica URL Pubblico

```bash
curl -I https://balizero.com/business/article-slug
# HTTP 200 = pubblicato
```

---

## 🚀 FLUSSO COMPLETO

```
1. Intel Scraper avviato
   ↓
2. Articoli fetchati e arricchiti
   ↓
3. Cover image generata
   → Salvata in: data/images/cover_*.png
   ↓
4. Articolo salvato
   → Salvato in: data/pending_articles/{id}.json
   ↓
5. Preview HTML generato
   → Salvato in: data/previews/{id}.html
   ↓
6. Notifica Telegram inviata
   → Approvazione richiesta
   ↓
7. Approvazione manuale
   → Via Telegram o UI
   ↓
8. Pubblicazione via API
   → POST /api/articles/publish
   ↓
9. Commit GitHub
   → MDX: apps/mouth/src/content/articles/{category}/{slug}.mdx
   → Image: apps/mouth/public/static/news/{image_filename}
   ↓
10. Vercel Auto-Deploy
   → ~1 minuto
   ↓
11. Articolo Live
   → URL: https://balizero.com/{category}/{slug}
```

---

## 📊 STATO ARTICOLI

### Pending (Pre-Approvazione)

**Location:** `apps/bali-intel-scraper/data/pending_articles/`

**Status:** `pending`

**Contiene:**

- ✅ Articolo completo arricchito
- ✅ Cover image path
- ✅ Preview HTML path
- ✅ Metadata SEO/AEO

### Approved (Post-Approvazione, Pre-Pubblicazione)

**Status:** `approved`

**Contiene:**

- ✅ Tutto del pending
- ✅ `approved_at` timestamp
- ✅ `telegram_message_id`

### Published (Pubblicato)

**Location GitHub:**

- MDX: `apps/mouth/src/content/articles/{category}/{slug}.mdx`
- Image: `apps/mouth/public/static/news/{image_filename}`

**URL Pubblico:**

- `https://balizero.com/{category}/{slug}`

**Status:** `published`

---

## 🔔 NOTIFICHE

### Quando Vengono Inviate

1. **Articolo Completo Creato:**
   - Quando nuovo articolo con cover image viene salvato
   - Location: `data/pending_articles/{id}.json`

2. **Cover Image Generata:**
   - Quando cover image viene generata con successo
   - Location: `data/images/cover_*.png`

3. **Preview HTML Creato:**
   - Quando preview HTML viene generato
   - Location: `data/previews/{id}.html`

4. **Articolo Pubblicato:**
   - Quando articolo viene pubblicato su GitHub
   - URL: `https://balizero.com/{category}/{slug}`

### Formato Notifica

```
📰 Articolo Pubblicato!

Titolo: Article Title
Categoria: business
URL: https://balizero.com/business/article-slug

✅ Articolo completo con cover image pubblicato su balizero.com
```

---

## 📋 COMANDI RAPIDI

### Trova Articoli Completi

```bash
./scripts/monitor_intel_published_articles.sh
```

### Avvia Scraper con Monitoraggio

```bash
export TELEGRAM_BOT_TOKEN=your_token
./scripts/start_intel_and_notify.sh
```

### Verifica Articolo Specifico

```bash
# Leggi JSON
cat apps/bali-intel-scraper/data/pending_articles/{id}.json | jq

# Apri preview
open apps/bali-intel-scraper/data/previews/{id}.html

# Verifica URL pubblico
curl -I https://balizero.com/{category}/{slug}
```

---

## 🔍 TROUBLESHOOTING

### Cover Image Non Trovata

1. Verifica path nell'articolo JSON
2. Verifica che file esista:
   ```bash
   ls -lh apps/bali-intel-scraper/data/images/cover_*.png
   ```
3. Controlla logs per errori generazione

### Articolo Non Pubblicato

1. Verifica approvazione:

   ```bash
   cat apps/bali-intel-scraper/data/pending_articles/{id}.json | jq .status
   ```

2. Verifica API publish:

   ```bash
   curl -X POST https://nuzantara-rag.fly.dev/api/articles/publish \
     -H "X-API-Key: $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d @apps/bali-intel-scraper/data/pending_articles/{id}.json
   ```

3. Verifica GitHub:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
     "https://api.github.com/repos/Balizero1987/Teman2/commits?path=apps/mouth/src/content/articles/"
   ```

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
