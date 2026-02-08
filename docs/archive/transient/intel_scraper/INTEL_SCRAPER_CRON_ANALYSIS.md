# Intel Scraper Cron - Analisi Log e Problemi

**Data Analisi:** 2026-01-24  
**Status Cron:** ✅ **FUNZIONA** (lo script viene eseguito correttamente)

---

## ✅ CRON FUNZIONA!

Dai log vediamo che:

- ✅ Script eseguito alle 22:39:25
- ✅ Pipeline completa eseguita (fetch → score → enrich → image → approval)
- ✅ 10 articoli fetchati, 5 arricchiti
- ✅ Immagini generate con successo (browser fallback)
- ✅ Preview HTML creati e caricati su backend

**Il cron STA funzionando!** Il problema non è il cron, ma la configurazione.

---

## 🔍 PROBLEMI IDENTIFICATI

### 1. ❌ HTTP 307 Redirect (CRITICO)

**Errore:**

```
❌ API error: 307 - Redirecting...
```

**Causa:** L'endpoint `/api/intel/scraper/submit` sta facendo un redirect invece di rispondere direttamente.

**Possibili cause:**

- URL senza trailing slash (FastAPI fa redirect)
- Endpoint non trovato (redirect a 404)
- Problema di routing FastAPI

**Fix necessario:**

- Verificare che l'endpoint esista e risponda correttamente
- Aggiungere trailing slash se necessario
- Verificare che il router sia registrato correttamente

### 2. ⚠️ Telegram User Deactivated

**Errore:**

```
Telegram API error for 8290313965: {"ok":false,"error_code":403,"description":"Forbidden: user is deactivated"}
```

**Causa:** L'utente Telegram con ID `8290313965` è disattivato o ha bloccato il bot.

**Fix necessario:**

- Verificare che l'utente Telegram sia attivo
- Controllare che il bot possa inviare messaggi
- Aggiornare `TELEGRAM_APPROVAL_CHAT_ID` con un ID valido

### 3. ⚠️ GOOGLE_API_KEY Not Configured

**Warning:**

```
GOOGLE_API_KEY not set - image generation will fail
⚠️ API generator failed: GOOGLE_API_KEY not configured
```

**Impatto:** Basso - usa fallback browser automation che funziona.

**Fix opzionale:**

- Configurare `GOOGLE_API_KEY` per usare Imagen 4 API (più veloce)
- Oppure lasciare così (browser fallback funziona)

### 4. ⚠️ Could Not Extract Content (Google News RSS)

**Warning:**

```
❌ Could not extract content from https://news.google.com/rss/articles/...
⚠️ Could not fetch full article, using summary only
```

**Causa:** Google News RSS links sono redirect complessi che non possono essere estratti facilmente.

**Impatto:** Medio - usa solo summary invece di full article, ma l'enrichment funziona comunque.

**Fix opzionale:**

- Migliorare extractor per seguire redirect
- Oppure accettare che Google News RSS non fornisce full content

---

## 📊 STATISTICHE ESECUZIONE

**Ultima esecuzione (22:39:25):**

| Metrica                    | Valore                  |
| -------------------------- | ----------------------- |
| **Articoli fetchati**      | 10                      |
| **Articoli arricchiti**    | 5                       |
| **Immagini generate**      | 5 ✅                    |
| **Preview creati**         | 5 ✅                    |
| **Preview caricati**       | 5 ✅                    |
| **Telegram notifications** | 0 ❌ (user deactivated) |
| **Articoli inviati a API** | 0 ❌ (HTTP 307)         |

**Risultato:** Pipeline funziona fino all'invio API, poi fallisce per HTTP 307.

---

## 🛠️ FIX RICHIESTI

### Fix 1: HTTP 307 Redirect (PRIORITÀ ALTA)

**Verificare endpoint backend:**

```bash
# Test endpoint
curl -X POST https://nuzantara-rag.fly.dev/api/intel/scraper/submit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "title": "Test",
    "content": "Test content",
    "source_url": "https://example.com",
    "source_name": "Test",
    "category": "immigration",
    "relevance_score": 50
  }'
```

**Se ritorna 307:**

1. Verificare che il router sia registrato in `main_cloud.py`
2. Verificare che l'endpoint non abbia trailing slash issues
3. Controllare middleware che potrebbero fare redirect

**Fix nel codice:**

```python
# In rss_fetcher.py e article_deep_enricher.py
# Assicurarsi che l'endpoint non abbia trailing slash
endpoint = f"{api_url.rstrip('/')}/api/intel/scraper/submit"

# E aggiungere follow_redirects=True
response = await client.post(
    endpoint,
    json=payload,
    headers=headers,
    follow_redirects=True  # ← Aggiungere questo
)
```

### Fix 2: Telegram User (PRIORITÀ MEDIA)

**Verificare configurazione:**

```bash
# Controllare chat ID configurato
fly secrets list -a nuzantara-rag | grep TELEGRAM

# Aggiornare se necessario
fly secrets set TELEGRAM_APPROVAL_CHAT_ID="NEW_CHAT_ID" -a nuzantara-rag
```

**Verificare che l'utente Telegram:**

- Sia attivo (non disattivato)
- Abbia avviato il bot (`/start`)
- Non abbia bloccato il bot

### Fix 3: GOOGLE_API_KEY (PRIORITÀ BASSA)

**Opzionale - solo se vuoi usare Imagen 4 API:**

```bash
fly secrets set GOOGLE_API_KEY="your_key" -a nuzantara-rag
```

---

## ✅ CHECKLIST VERIFICA

- [x] Cron funziona ✅
- [x] Script eseguito correttamente ✅
- [x] Pipeline completa eseguita ✅
- [ ] HTTP 307 risolto ❌
- [ ] Telegram user attivo ❌
- [ ] GOOGLE_API_KEY configurato (opzionale) ⚠️

---

## 🎯 PROSSIMI STEP

1. **Testare endpoint API manualmente** per verificare HTTP 307
2. **Fixare redirect** aggiungendo `follow_redirects=True` o correggendo endpoint
3. **Verificare Telegram user** e aggiornare chat ID se necessario
4. **Monitorare prossima esecuzione** dopo i fix

---

**Conclusione:** Il cron funziona perfettamente! I problemi sono di configurazione API e Telegram, non di scheduling.
