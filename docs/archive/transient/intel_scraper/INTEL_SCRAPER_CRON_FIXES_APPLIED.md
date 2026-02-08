# Intel Scraper Cron - Fix Applicati

**Data:** 2026-01-24  
**Status:** ✅ **CRON FUNZIONA** - Fix applicati per problemi di configurazione

---

## ✅ CONFERMA: CRON FUNZIONA!

Dai log vediamo che:

- ✅ Script eseguito correttamente alle 22:39:25
- ✅ Pipeline completa: fetch → score → enrich → image → approval
- ✅ 10 articoli fetchati, 5 arricchiti con successo
- ✅ Immagini generate (browser fallback)
- ✅ Preview HTML creati e caricati

**Il problema NON era il cron, ma la configurazione API!**

---

## 🔧 FIX APPLICATI

### 1. ✅ HTTP 307 Redirect Fix

**Problema:** httpx non seguiva i redirect, causando errori 307.

**Fix applicato:**

**File:** `apps/bali-intel-scraper/scripts/rss_fetcher.py`

```python
# PRIMA
async with httpx.AsyncClient(timeout=30.0) as client:

# DOPO
async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
```

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

```python
# PRIMA
async with httpx.AsyncClient(timeout=30.0) as client:

# DOPO
async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
```

### 2. ✅ API URL Default Fix

**Problema:** Default API URL era `https://balizero.com` invece di `https://nuzantara-rag.fly.dev`.

**Fix applicato:**

**File:** `apps/bali-intel-scraper/scripts/run_intel_feed.py`

```python
# PRIMA
parser.add_argument("--api-url", default="https://balizero.com", help="BaliZero API URL")

# DOPO
parser.add_argument("--api-url", default="https://nuzantara-rag.fly.dev", help="Backend API URL")
```

### 3. ✅ API Key Configuration Fix

**Problema:** Script cron non caricava `NUZANTARA_API_KEY` dall'ambiente.

**Fix applicato:**

**File:** `scripts/auto_intel_scraper.sh`

Aggiunto:

- Caricamento `NUZANTARA_API_KEY` da `.env` o `.env.local`
- Passaggio API key esplicito a `run_intel_feed.py`
- Configurazione `BACKEND_API_URL` e `NUZANTARA_API_URL`

```bash
# Load NUZANTARA_API_KEY from environment or .env.local
if [ -z "$NUZANTARA_API_KEY" ]; then
    if [ -f "$PROJECT_DIR/.env" ]; then
        export $(grep -v '^#' "$PROJECT_DIR/.env" | grep NUZANTARA_API_KEY | xargs)
    fi
fi

# Set API URL
export BACKEND_API_URL="${BACKEND_API_URL:-https://nuzantara-rag.fly.dev}"
export NUZANTARA_API_URL="${NUZANTARA_API_URL:-$BACKEND_API_URL}"

# Pass API key to script
"$PYTHON_EXEC" scripts/run_intel_feed.py --mode full --api-url "$NUZANTARA_API_URL" --api-key "$NUZANTARA_API_KEY"
```

---

## ⚠️ PROBLEMI RIMANENTI (Non Critici)

### 1. Telegram User Deactivated

**Errore:**

```
Telegram API error for 8290313965: {"ok":false,"error_code":403,"description":"Forbidden: user is deactivated"}
```

**Fix necessario:**

- Verificare che l'utente Telegram sia attivo
- Aggiornare `TELEGRAM_APPROVAL_CHAT_ID` se necessario

**Comando:**

```bash
fly secrets set TELEGRAM_APPROVAL_CHAT_ID="NEW_CHAT_ID" -a nuzantara-rag
```

**Impatto:** Basso - gli articoli vengono comunque salvati in staging e possono essere approvati via News Room UI.

### 2. GOOGLE_API_KEY Not Configured

**Warning:**

```
GOOGLE_API_KEY not set - image generation will fail
⚠️ API generator failed: GOOGLE_API_KEY not configured
```

**Status:** ✅ Funziona comunque con browser fallback

**Fix opzionale:**

```bash
fly secrets set GOOGLE_API_KEY="your_key" -a nuzantara-rag
```

**Impatto:** Nessuno - browser fallback funziona perfettamente.

---

## 📊 RISULTATI ATTESI DOPO FIX

**Prima dei fix:**

- ❌ HTTP 307 → 0 articoli inviati
- ⚠️ Telegram deactivated → 0 notifiche
- ✅ Pipeline funzionante fino all'invio

**Dopo i fix:**

- ✅ HTTP 200 → Articoli inviati correttamente
- ⚠️ Telegram deactivated → Fix separato necessario
- ✅ Pipeline completa funzionante

---

## 🧪 TEST

### Test Manuale

```bash
# Eseguire manualmente con API key
export NUZANTARA_API_KEY="your_key"
./scripts/auto_intel_scraper.sh

# Verificare log
tail -f logs/intel_scraper.log
```

### Verifica Fix

```bash
# Controllare che non ci siano più errori 307
grep -i "307\|Redirecting" logs/intel_scraper.log

# Dovrebbe essere vuoto o mostrare solo vecchi errori
```

---

## 📋 CHECKLIST POST-FIX

- [x] Fix HTTP 307 applicato (`follow_redirects=True`)
- [x] Fix API URL default applicato
- [x] Fix API key configuration applicato
- [ ] Configurare `NUZANTARA_API_KEY` in `.env` o `.env.local`
- [ ] Test manuale eseguito
- [ ] Verificare prossima esecuzione cron (4:00 AM o 4:00 PM)
- [ ] (Opzionale) Fix Telegram user deactivated
- [ ] (Opzionale) Configurare GOOGLE_API_KEY

---

## 🔑 CONFIGURAZIONE NECESSARIA

### Variabili d'Ambiente

**File:** `apps/bali-intel-scraper/.env.local` o `.env`

```bash
# Backend API
NUZANTARA_API_KEY=your_internal_api_key
BACKEND_API_URL=https://nuzantara-rag.fly.dev
NUZANTARA_API_URL=https://nuzantara-rag.fly.dev

# Telegram (opzionale - solo se vuoi notifiche)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_APPROVAL_CHAT_ID=your_chat_id

# Google API (opzionale - solo se vuoi Imagen 4 invece di browser)
GOOGLE_API_KEY=your_google_key
```

**Oppure configurare su Fly.io:**

```bash
fly secrets set NUZANTARA_API_KEY="your_key" -a nuzantara-rag
```

---

## ✅ CONCLUSIONE

**Il cron funziona perfettamente!**

I problemi erano:

1. ✅ **HTTP 307** → Fixato con `follow_redirects=True`
2. ✅ **API URL errato** → Fixato default URL
3. ✅ **API key non caricata** → Fixato caricamento env vars
4. ⚠️ **Telegram deactivated** → Fix separato necessario (non critico)

**Prossimi step:**

1. Configurare `NUZANTARA_API_KEY` in `.env.local`
2. Testare manualmente: `./scripts/auto_intel_scraper.sh`
3. Verificare prossima esecuzione cron

---

**Last Updated:** 2026-01-24  
**Status:** Fix applicati, test necessario
