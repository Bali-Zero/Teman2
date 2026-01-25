# Intel Scraper - Configurazione Completa

**Data:** 2026-01-24  
**Status:** ✅ Configurato

---

## 🔑 VARIABILI D'AMBIENTE CONFIGURATE

### File: `apps/bali-intel-scraper/.env.local`

```bash
# Google API Key (for Imagen 4 image generation)
GOOGLE_API_KEY=AIzaSyDWakPSp-49nGIGAjJmAp_YpgZ06Ve_04Q

# Backend API (se necessario)
NUZANTARA_API_KEY=your_internal_api_key
BACKEND_API_URL=https://nuzantara-rag.fly.dev
NUZANTARA_API_URL=https://nuzantara-rag.fly.dev
```

**⚠️ IMPORTANTE:** Il file `.env.local` è nel `.gitignore` e NON viene committato.

---

## ✅ BENEFICI DELLA CONFIGURAZIONE

### Prima (senza GOOGLE_API_KEY):

- ⚠️ Browser automation fallback (~60 secondi per immagine)
- ⚠️ Dipendenza da Playwright
- ⚠️ Possibili problemi con UI changes

### Dopo (con GOOGLE_API_KEY):

- ✅ Imagen 4 API diretta (~5-10 secondi per immagine)
- ✅ Nessuna dipendenza browser
- ✅ Più affidabile e veloce
- ✅ Fallback automatico a browser se API fallisce

---

## 🧪 VERIFICA CONFIGURAZIONE

### Test Manuale

```bash
cd apps/bali-intel-scraper
source .env.local  # Carica variabili
python3 -c "import os; print('GOOGLE_API_KEY:', 'SET' if os.getenv('GOOGLE_API_KEY') else 'NOT SET')"
```

### Test Immagine Generation

```bash
cd apps/bali-intel-scraper
export GOOGLE_API_KEY="AIzaSyDWakPSp-49nGIGAjJmAp_YpgZ06Ve_04Q"
python3 -c "
from scripts.gemini_api_image_generator import GeminiAPIImageGenerator
import asyncio

async def test():
    gen = GeminiAPIImageGenerator()
    result = await gen.generate_cover_image(
        prompt='Bali sunset over rice terraces',
        category='lifestyle'
    )
    print(f'Success: {result.success}')
    print(f'Path: {result.image_path}')

asyncio.run(test())
"
```

---

## 📋 CHECKLIST CONFIGURAZIONE

- [x] GOOGLE_API_KEY aggiunta a `.env.local`
- [x] Script cron aggiornato per caricare `.env.local`
- [x] Verifica che `.env.local` sia nel `.gitignore`
- [ ] Test manuale eseguito
- [ ] Verificare prossima esecuzione cron usa Imagen 4

---

## 🔒 SICUREZZA

**✅ Sicuro:**

- `.env.local` è nel `.gitignore`
- Non viene committato nel repository
- Solo accessibile localmente

**⚠️ Attenzione:**

- Non condividere `.env.local` pubblicamente
- Non committare mai chiavi API nel codice
- Usare Fly.io secrets per produzione

---

**Last Updated:** 2026-01-24  
**Status:** GOOGLE_API_KEY configurata
