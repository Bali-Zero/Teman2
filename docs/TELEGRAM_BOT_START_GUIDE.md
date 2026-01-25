# Come Avviare @zantara_bot su Telegram

**Data:** 2026-01-24  
**Account:** @archangelsamyaza  
**Chat ID:** 1125336968

---

## 🔍 PROBLEMA

Quando cerchi `@zantara_bot` in Telegram, vedi "Deleted Account" invece del bot.

---

## ✅ SOLUZIONE: Link Diretto

**Metodo più veloce:**

1. Apri Telegram dal tuo account (@archangelsamyaza)
2. Usa questo link diretto: **https://t.me/zantara_bot**
3. Oppure cerca esattamente: `zantara_bot` (senza @ nella ricerca)
4. Invia `/start`

---

## 📱 STEP DETTAGLIATI

### Metodo 1: Link Diretto (Raccomandato)

1. Apri Telegram
2. Incolla questo link nella barra di ricerca o nel browser:
   ```
   https://t.me/zantara_bot
   ```
3. Telegram aprirà la chat con il bot
4. Invia `/start`

### Metodo 2: Ricerca Manuale

1. Apri Telegram
2. Vai alla barra di ricerca (in alto)
3. Digita esattamente: `zantara_bot` (senza @)
4. Seleziona il bot quando appare
5. Invia `/start`

### Metodo 3: Da un Messaggio

Se hai ricevuto un messaggio dal bot in passato:

1. Vai alle chat
2. Cerca "zantara" o "Zantara AI"
3. Apri la chat
4. Invia `/start`

---

## ⚠️ NOTA SUL "DELETED ACCOUNT"

Il "Deleted Account" che vedi nei risultati di ricerca è probabilmente:

- Un vecchio contatto associato a quella ricerca
- Non è il bot stesso
- Ignoralo e usa il link diretto o la ricerca esatta

---

## ✅ VERIFICA DOPO /START

Dopo aver inviato `/start`, dovresti ricevere un messaggio di benvenuto dal bot.

Poi testa la configurazione:

```bash
cd apps/bali-intel-scraper
export $(grep -v '^#' .env.local | grep TELEGRAM | xargs)
python3 scripts/test_telegram_bot.py
```

**Output atteso:**

```
✅ Bot attivo: @zantara_bot
✅ Messaggio inviato con successo a chat ID 1125336968
✅ TUTTI I TEST PASSATI!
```

---

## 🔗 LINK UTILI

- **Bot diretto:** https://t.me/zantara_bot
- **Test configurazione:** `python3 scripts/test_telegram_bot.py`

---

**Last Updated:** 2026-01-24
