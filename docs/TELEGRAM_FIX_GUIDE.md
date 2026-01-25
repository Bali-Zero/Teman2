# Telegram User Deactivated - Fix Guide

**Data:** 2026-01-24  
**Problema:** Telegram user `8290313965` è deactivated

---

## 🔍 PROBLEMA IDENTIFICATO

**Errore nei log:**

```
Telegram API error for 8290313965: {"ok":false,"error_code":403,"description":"Forbidden: user is deactivated"}
```

**Causa:** L'utente Telegram con chat ID `8290313965` è disattivato o non esiste più.

---

## ✅ SOLUZIONI

### Soluzione 1: Ottenere Nuovo Chat ID (RACCOMANDATO)

**Metodo A: Usare @userinfobot**

1. Apri Telegram
2. Cerca `@userinfobot`
3. Invia qualsiasi messaggio
4. Il bot risponderà con il tuo chat ID
5. Copia il chat ID

**Metodo B: Usare Script Automatico**

```bash
cd apps/bali-intel-scraper
source .env.local 2>/dev/null || export $(grep -v '^#' .env.local | xargs)

# Prima: Invia /start al bot su Telegram
# Poi esegui:
python3 scripts/get_telegram_chat_id.py
```

**Metodo C: Usare @JsonDumpBot**

1. Inizia una chat con `@JsonDumpBot`
2. Inoltra un messaggio dal bot a @JsonDumpBot
3. Il bot risponderà con JSON contenente il chat ID

### Soluzione 2: Verificare Chat ID Esistente

**Test configurazione:**

```bash
cd apps/bali-intel-scraper
source .env.local 2>/dev/null || export $(grep -v '^#' .env.local | xargs)

python3 scripts/test_telegram_bot.py
```

Questo script:

- ✅ Verifica che il bot token sia valido
- ✅ Testa invio messaggio a ogni chat ID
- ✅ Mostra errori dettagliati (deactivated, blocked, etc.)
- ✅ Suggerisce soluzioni

### Soluzione 3: Aggiornare Chat ID

**Opzione A: Aggiornare .env.local**

```bash
# In apps/bali-intel-scraper/.env.local
TELEGRAM_APPROVAL_CHAT_ID=NUOVO_CHAT_ID
```

**Opzione B: Aggiornare Fly.io Secrets**

```bash
fly secrets set TELEGRAM_APPROVAL_CHAT_ID="NUOVO_CHAT_ID" -a nuzantara-rag

# Per più utenti (comma-separated):
fly secrets set TELEGRAM_APPROVAL_CHAT_ID="CHAT_ID_1,CHAT_ID_2,CHAT_ID_3" -a nuzantara-rag
```

---

## 🧪 TEST CONFIGURAZIONE

### Test Completo

```bash
cd apps/bali-intel-scraper

# Carica variabili d'ambiente
source .env.local 2>/dev/null || export $(grep -v '^#' .env.local | xargs)

# Test bot
python3 scripts/test_telegram_bot.py
```

**Output atteso se tutto OK:**

```
✅ Bot attivo: @your_bot_name
✅ Messaggio inviato con successo a chat ID XXXXXX
✅ TUTTI I TEST PASSATI!
```

**Output se user deactivated:**

```
❌ Telegram API error 403 - Forbidden: user is deactivated
⚠️  L'utente Telegram è disattivato o non esiste più
💡 Soluzione: Verificare chat ID o ottenere un nuovo chat ID valido
```

---

## 📋 CHECKLIST FIX

- [ ] Ottenere nuovo chat ID valido
- [ ] Aggiornare `.env.local` con nuovo chat ID
- [ ] (Opzionale) Aggiornare Fly.io secrets
- [ ] Eseguire `test_telegram_bot.py` per verificare
- [ ] Testare invio messaggio manuale
- [ ] Verificare prossima esecuzione cron

---

## 🔧 SCRIPT DISPONIBILI

### 1. `test_telegram_bot.py`

Test completo configurazione Telegram:

- Verifica bot token
- Test invio messaggi
- Diagnostica errori dettagliati

**Usage:**

```bash
python3 scripts/test_telegram_bot.py
```

### 2. `get_telegram_chat_id.py`

Ottieni chat ID dai messaggi recenti:

- Mostra tutti i chat IDs che hanno inviato messaggi al bot
- Utile per trovare il tuo chat ID

**Usage:**

```bash
# Prima: Invia /start al bot su Telegram
# Poi:
python3 scripts/get_telegram_chat_id.py
```

---

## 💡 COME OTTENERE CHAT ID

### Metodo Rapido: @userinfobot

1. Apri Telegram
2. Cerca `@userinfobot`
3. Invia qualsiasi messaggio
4. Il bot risponde con:
   ```
   👤 Your user information:
   ID: 123456789
   First name: Your Name
   Username: @yourusername
   ```
5. Il numero `ID` è il tuo chat ID

### Metodo Alternativo: Script

```bash
# 1. Assicurati che TELEGRAM_BOT_TOKEN sia configurato
# 2. Invia /start al bot su Telegram
# 3. Esegui:
python3 scripts/get_telegram_chat_id.py
```

---

## ⚠️ NOTE IMPORTANTI

1. **L'utente deve avviare il bot:**
   - L'utente deve inviare `/start` al bot prima di ricevere messaggi
   - Se l'utente non ha mai avviato il bot, riceverà errore 403

2. **L'utente non deve aver bloccato il bot:**
   - Se l'utente ha bloccato il bot, riceverà errore 403 "blocked"

3. **Chat ID può cambiare:**
   - Se l'utente cancella e ricrea account Telegram, il chat ID cambia
   - Verificare periodicamente che il chat ID sia ancora valido

---

## ✅ DOPO IL FIX

Dopo aver aggiornato il chat ID:

1. **Test immediato:**

   ```bash
   python3 scripts/test_telegram_bot.py
   ```

2. **Test invio articolo:**

   ```bash
   # Eseguire pipeline manualmente
   python3 scripts/run_intel_feed.py --mode full --limit 1 --max-enrich 1
   ```

3. **Verificare log:**

   ```bash
   tail -f logs/intel_feed_*.log | grep -i telegram
   ```

4. **Attendere prossimo cron:**
   - 4:00 AM o 4:00 PM
   - Verificare che le notifiche Telegram arrivino correttamente

---

**Last Updated:** 2026-01-24  
**Status:** Script di test e diagnostica creati
