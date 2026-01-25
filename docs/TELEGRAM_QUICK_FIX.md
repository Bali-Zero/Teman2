# Telegram Chat ID - Quick Fix

**Problema:** Chat ID `8290313965` è deactivated  
**Soluzione:** Ottenere nuovo chat ID e aggiornare configurazione

---

## 🚀 FIX RAPIDO (2 minuti)

### Step 1: Ottieni Chat ID

**Metodo più veloce:**

1. Apri Telegram
2. Cerca `@userinfobot`
3. Invia qualsiasi messaggio
4. Copia il numero `ID` dalla risposta

**Esempio risposta:**

```
👤 Your user information:
ID: 123456789        ← Questo è il tuo chat ID
First name: Your Name
Username: @yourusername
```

### Step 2: Aggiorna Configurazione

**File:** `apps/bali-intel-scraper/.env.local`

```bash
# Sostituisci il vecchio chat ID con il nuovo
TELEGRAM_APPROVAL_CHAT_ID=123456789  # ← Il tuo nuovo chat ID
```

### Step 3: Test

```bash
cd apps/bali-intel-scraper
export $(grep -v '^#' .env.local | grep TELEGRAM | xargs)
python3 scripts/test_telegram_bot.py
```

**Dovrebbe mostrare:**

```
✅ Bot attivo: @zantara_bot
✅ Messaggio inviato con successo a chat ID 123456789
✅ TUTTI I TEST PASSATI!
```

---

## ✅ FATTO!

Dopo questi 3 step, il Telegram approval funzionerà correttamente.

**Prossima esecuzione cron:** Le notifiche Telegram arriveranno al nuovo chat ID.

---

**Last Updated:** 2026-01-24
