# Visione e Approvazione Articoli Pending

**Purpose:** Guida completa per visionare e approvare articoli prima della pubblicazione  
**Last Updated:** 2026-01-24

---

## 🎯 DOVE VISIONARE GLI ARTICOLI PRIMA DELLA PUBBLICAZIONE

Ci sono **4 modi** per visionare gli articoli pending prima di pubblicarli:

---

## 1. 📄 Preview HTML Locale (Raccomandato)

### Visualizza Lista Articoli

```bash
cd /Users/antonellosiano/Projects/nuzantara
./scripts/view_pending_articles.sh
```

**Output:**

- Lista tutti gli articoli pending
- Mostra ID, titolo, categoria
- Indica se preview HTML è disponibile
- Mostra path locale e URL online

### Apri Preview nel Browser

```bash
# Apri un singolo preview
open apps/bali-intel-scraper/data/previews/{article_id}.html

# Esempio:
open apps/bali-intel-scraper/data/previews/475c0ba228d7.html
```

### Apri Tutti i Preview

```bash
# Apri tutti i preview HTML nel browser
./scripts/open_all_previews.sh
```

**Cosa vedi:**

- ✅ Articolo completo formattato
- ✅ Cover image integrata
- ✅ Styling BaliZero completo
- ✅ Esattamente come apparirà pubblicato

---

## 2. 🌐 Preview Online (se deployato)

### URL Preview

```
https://bali-intel-scraper.fly.dev/preview/{article_id}
```

**Esempio:**

```
https://bali-intel-scraper.fly.dev/preview/475c0ba228d7
```

**Vantaggi:**

- ✅ Accessibile da qualsiasi dispositivo
- ✅ Condivisibile con team
- ✅ Preview esatto come pubblicato

**Nota:** Richiede che il servizio `bali-intel-scraper` sia deployato su Fly.io.

---

## 3. 📱 Telegram Approval (Automatico)

### Come Funziona

Quando l'Intel Scraper crea un articolo completo:

1. Genera preview HTML
2. Invia notifica Telegram con:
   - Titolo e categoria
   - Link al preview
   - Pulsanti Approve/Reject
3. Attende approvazione manuale
4. Pubblica automaticamente se approvato

### Configurazione

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_APPROVAL_CHAT_ID=1125336968
```

### Processo Approvazione

1. Ricevi notifica Telegram
2. Clicca "View Preview" per vedere articolo
3. Clicca "✅ Approve" per approvare
4. Articolo viene pubblicato automaticamente

**Vantaggi:**

- ✅ Approvazione rapida da mobile
- ✅ Notifiche automatiche
- ✅ Pubblicazione automatica dopo approvazione

---

## 4. 🖥️ News Room UI (Se Disponibile)

### URL

```
https://kita.balizero.com/intelligence
```

**Funzionalità:**

- ✅ Dashboard completa articoli pending
- ✅ Preview integrato
- ✅ Approvazione con un click
- ✅ Filtri per categoria, data, score

**Nota:** Richiede che il frontend sia deployato e configurato.

---

## 📋 WORKFLOW RACCOMANDATO

### Opzione A: Preview Locale + Pubblicazione Manuale

```bash
# 1. Visualizza lista articoli
./scripts/view_pending_articles.sh

# 2. Apri preview nel browser
open apps/bali-intel-scraper/data/previews/{article_id}.html

# 3. Se approvato, pubblica
export ADMIN_API_KEY=69ff6340462fd10b
python3 scripts/publish_pending_articles.py
```

### Opzione B: Telegram Approval (Automatico)

```bash
# 1. Configura Telegram
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_APPROVAL_CHAT_ID=1125336968

# 2. Avvia Intel Scraper
cd apps/bali-intel-scraper
python3 scripts/run_intel_feed.py --mode full

# 3. Approva via Telegram quando arriva notifica
# 4. Pubblicazione automatica dopo approvazione
```

### Opzione C: Preview Online + Pubblicazione Manuale

```bash
# 1. Apri preview online
open https://bali-intel-scraper.fly.dev/preview/{article_id}

# 2. Se approvato, pubblica
export ADMIN_API_KEY=69ff6340462fd10b
python3 scripts/publish_pending_articles.py
```

---

## 🔍 VERIFICA ARTICOLI PENDING

### Lista Completa

```bash
# Mostra tutti gli articoli pending con dettagli
./scripts/view_pending_articles.sh
```

### Verifica Preview Disponibili

```bash
# Lista file preview
ls -lh apps/bali-intel-scraper/data/previews/*.html

# Conta preview disponibili
ls apps/bali-intel-scraper/data/previews/*.html | wc -l
```

### Verifica Stato Approvazione

```bash
# Verifica status articoli
cd apps/bali-intel-scraper
for f in data/pending_articles/*.json; do
    echo "=== $(basename $f .json) ==="
    python3 -c "
import json
d = json.load(open('$f'))
print(f\"Status: {d.get('status')}\")
print(f\"Approved: {d.get('approved_at')}\")
print(f\"Telegram: {d.get('telegram_message_id')}\")
"
done
```

---

## 📊 STATO ARTICOLI

### Pending (In Attesa Approvazione)

- **Status:** `pending`
- **Approved:** `null`
- **Telegram:** `null` o `message_id`
- **Location:** `data/pending_articles/{id}.json`
- **Preview:** `data/previews/{id}.html`

### Approved (Approvato, Non Ancora Pubblicato)

- **Status:** `approved`
- **Approved:** `timestamp`
- **Telegram:** `message_id`
- **Location:** `data/pending_articles/{id}.json`
- **Next Step:** Pubblicazione via API

### Published (Pubblicato)

- **Status:** `published`
- **Location GitHub:** `apps/mouth/src/content/articles/{category}/{slug}.mdx`
- **URL:** `https://balizero.com/{category}/{slug}`

---

## 🚀 COMANDI RAPIDI

### Visione Rapida

```bash
# Lista articoli
./scripts/view_pending_articles.sh

# Apri tutti i preview
./scripts/open_all_previews.sh

# Apri singolo preview
open apps/bali-intel-scraper/data/previews/{article_id}.html
```

### Approvazione e Pubblicazione

```bash
# Dopo aver visionato e approvato:
export ADMIN_API_KEY=69ff6340462fd10b
python3 scripts/publish_pending_articles.py
```

---

## ⚠️ NOTE IMPORTANTI

1. **Preview HTML:** I preview HTML mostrano esattamente come apparirà l'articolo pubblicato.

2. **Cover Images:** Se l'immagine non è visibile nel preview locale, potrebbe essere un problema di path. Verifica che il file esista in `data/images/`.

3. **Telegram:** Se Telegram non è configurato, gli articoli non verranno inviati automaticamente per approvazione.

4. **Pubblicazione:** Dopo l'approvazione, gli articoli devono essere pubblicati manualmente tramite script o automaticamente via Telegram se configurato.

---

**Last Updated:** 2026-01-24  
**Next Step:** Usa `./scripts/view_pending_articles.sh` per vedere gli articoli pending
