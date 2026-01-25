# Pubblicazione Articoli Pending

**Purpose:** Pubblicare articoli completi dall'Intel Scraper su balizero.com  
**Last Updated:** 2026-01-24

---

## 🎯 PROBLEMA

Gli articoli completi trovati dall'Intel Scraper sono in stato **"pending"** e non sono ancora pubblicati. Gli URL previsti (`https://balizero.com/{category}/{slug}`) non si aprono perché gli articoli non sono stati ancora commitati su GitHub.

---

## 📍 STATO ATTUALE

### Articoli Pending

**Location:** `apps/bali-intel-scraper/data/pending_articles/`

**Status:** `pending`

**Contiene:**

- ✅ Articolo completo arricchito
- ✅ Cover image path
- ✅ Preview HTML
- ✅ Metadata SEO/AEO
- ❌ **NON ancora pubblicato su GitHub**

### Perché gli URL non si aprono?

Gli articoli devono essere:

1. ✅ **Completati** (fatto - hanno cover image e preview)
2. ⏳ **Approvati** (via Telegram o UI)
3. ⏳ **Pubblicati** (tramite API `/api/articles/publish`)
4. ⏳ **Commitati su GitHub** (MDX file)
5. ⏳ **Deployati da Vercel** (~1 minuto)

---

## 🚀 SOLUZIONE: PUBBLICARE ARTICOLI PENDING

### Opzione 1: Script Automatico (Raccomandato)

```bash
cd /Users/antonellosiano/Desktop/nuzantara

# Configura API key
export ADMIN_API_KEY=69ff6340462fd10b
export API_URL=https://nuzantara-rag.fly.dev

# Esegui script di pubblicazione
python3 scripts/publish_pending_articles.py
```

**Lo script:**

- ✅ Trova tutti gli articoli pending
- ✅ Carica cover images
- ✅ Converte in formato EnrichedArticle
- ✅ Pubblica tramite API `/api/articles/publish`
- ✅ Mostra URL pubblici e commit SHA

### Opzione 2: Pubblicazione Manuale via API

```bash
# Per ogni articolo
curl -X POST https://nuzantara-rag.fly.dev/api/articles/publish \
  -H "X-API-Key: 69ff6340462fd10b" \
  -H "Content-Type: application/json" \
  -d @article_payload.json
```

### Opzione 3: Approvazione via Telegram

Se gli articoli sono stati inviati a Telegram per approvazione:

1. Apri Telegram bot
2. Approva articoli (voto 2/3 majority)
3. Gli articoli verranno pubblicati automaticamente

---

## 📋 PROCESSO COMPLETO

```
1. Intel Scraper crea articolo completo
   → Salvato in: data/pending_articles/{id}.json
   ↓
2. Articolo inviato a Telegram per approvazione
   → Status: pending
   ↓
3. Approvazione manuale (Telegram o UI)
   → Status: approved
   ↓
4. Pubblicazione via API
   → POST /api/articles/publish
   ↓
5. Commit GitHub
   → MDX: apps/mouth/src/content/articles/{category}/{slug}.mdx
   → Image: apps/mouth/public/static/news/{image_filename}
   ↓
6. Vercel Auto-Deploy
   → ~1 minuto
   ↓
7. Articolo Live
   → URL: https://balizero.com/{category}/{slug} ✅
```

---

## 🔍 VERIFICA PUBBLICAZIONE

### Verifica GitHub

```bash
# Verifica file MDX su GitHub
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/Balizero1987/Teman2/contents/apps/mouth/src/content/articles/"
```

### Verifica URL Pubblico

```bash
# Verifica se articolo è live
curl -I https://balizero.com/immigration/indonesia-s-golden-visa-who-actually-qualifies-and

# HTTP 200 = pubblicato ✅
# HTTP 404 = non ancora pubblicato ❌
```

### Verifica Status API

```bash
curl -X GET https://nuzantara-rag.fly.dev/api/articles/publish/status \
  -H "X-API-Key: 69ff6340462fd10b"
```

---

## 📊 ARTICOLI DA PUBBLICARE

Attualmente ci sono **12 articoli completi** in attesa di pubblicazione:

1. Indonesia's Golden Visa: Who Actually Qualifies and What It Costs
2. Insufficient Source Data: Cannot Verify Bali Property Market Trends
3. Indonesia Retirement Visa: Complete 2025 Guide...
4. Bali Villa Developer Claims 32% Rental Surge...
5. Indonesia's Golden Visa: What Expats Actually Need to Know
6. ... e altri 7 articoli

**Tutti hanno:**

- ✅ Cover image path
- ✅ Preview HTML
- ✅ Contenuto arricchito completo
- ❌ **NON ancora pubblicati**

---

## 🚀 COMANDI RAPIDI

### Pubblica Tutti gli Articoli Pending

```bash
cd /Users/antonellosiano/Desktop/nuzantara
export ADMIN_API_KEY=69ff6340462fd10b
python3 scripts/publish_pending_articles.py
```

### Verifica Articoli Pending

```bash
./scripts/intel_scraper_monitor_complete.sh
```

### Verifica Pubblicazione Specifica

```bash
# Verifica URL
curl -I https://balizero.com/immigration/indonesia-s-golden-visa-who-actually-qualifies-and

# Verifica GitHub
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/Balizero1987/Teman2/commits?path=apps/mouth/src/content/articles/"
```

---

## ⚠️ NOTE IMPORTANTI

1. **Cover Images:** Alcuni file immagine potrebbero non essere trovati localmente. Lo script gestisce questo caso e pubblica comunque l'articolo senza immagine se necessario.

2. **Rate Limiting:** Lo script include un delay di 2 secondi tra pubblicazioni per evitare rate limiting.

3. **Vercel Deploy:** Dopo la pubblicazione su GitHub, Vercel impiega ~1 minuto per fare il deploy. Gli URL saranno disponibili dopo questo tempo.

4. **Approvazione:** Se gli articoli richiedono approvazione manuale, devono essere approvati prima della pubblicazione.

---

**Last Updated:** 2026-01-24  
**Next Step:** Eseguire `scripts/publish_pending_articles.py` per pubblicare gli articoli
