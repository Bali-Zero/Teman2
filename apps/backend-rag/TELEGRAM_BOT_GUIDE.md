# 🤖 Guida Rapida - Configurazione Bot Telegram Zantara

## 🎯 OBIETTIVO

Attivare il bot Telegram Zantara per rispondere alle domande degli utenti usando l'AI.

## 📋 PREREQUISITI

- Account Telegram
- Accesso a Fly.io (per configurare secrets)
- Token del bot da @BotFather

## 🔧 PASSAGGI

### 1️⃣ CREAZIONE BOT SU TELEGRAM

1. Apri Telegram e cerca **@BotFather**
2. Invia `/start`
3. Invia `/newbot`
4. Scegli nome: **Zantara AI Assistant**
5. Scegli username: **zantara_ai_bot** (o disponibile)
6. **Copia il token** che ricevi (es: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2️⃣ CONFIGURAZIONE AUTOMATICA

```bash
# Esegui lo script di configurazione
cd /Users/antonellosiano/Desktop/nuzantara/apps/backend-rag
./setup_telegram_bot.sh
```

Lo script ti chiederà:

- **Incolla il token** del bot
- Verificherà il formato
- Configurerà su Fly.io
- Testerà il bot
- Imposterà il webhook

### 3️⃣ CONFIGURAZIONE MANUALE (se preferisci)

```bash
# 1. Configura token su Fly.io
fly secrets set TELEGRAM_BOT_TOKEN="IL_TUO_TOKEN_QUI" --app nuzantara-rag

# 2. Test bot
curl "https://api.telegram.org/botIL_TUO_TOKEN_QUI/getMe"

# 3. Configura webhook
curl -X POST "https://api.telegram.org/botIL_TUO_TOKEN_QUI/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://nuzantara-rag.fly.dev/api/telegram/webhook"}'
```

## ✅ VERIFICA

### Test Bot Status

```bash
python3 -c "
import httpx
import asyncio

async def check():
    async with httpx.AsyncClient() as client:
        resp = await client.get('https://api.telegram.org/botIL_TUO_TOKEN_QUI/getMe')
        print(resp.json())

asyncio.run(check())
"
```

### Test Webhook

```bash
curl -X POST "https://api.telegram.org/botIL_TUO_TOKEN_QUI/getWebhookInfo"
```

## 🎉 UTILIZZO

1. **Trova il bot** su Telegram con il suo username
2. **Invia `/start`** per iniziare
3. **Fai domande** su visa, immigrazione, Bali, Indonesia
4. **Il bot risponderà** usando l'AI di Nuzantara

## 🚨 RISOLUZIONE PROBLEMI

### Bot non risponde?

1. **Verifica token**: `curl "https://api.telegram.org/botTOKEN/getMe"`
2. **Verifica webhook**: `curl "https://api.telegram.org/botTOKEN/getWebhookInfo"`
3. **Controlla logs**: `fly logs --app nuzantara-rag`

### Token non valido?

- Ricrea il bot su @BotFather
- Copia il nuovo token
- Riconfigura su Fly.io

### Webhook non funziona?

- Verifica URL: `https://nuzantara-rag.fly.dev/api/telegram/webhook`
- Controlla secret token: `fly secrets list --app nuzantara-rag`

## 📞 SUPPORTO

Se hai problemi:

1. Controlla i log dell'app: `fly logs --app nuzantara-rag`
2. Verifica configurazione secrets: `fly secrets list --app nuzantara-rag`
3. Testa API manualmente con curl

## 🎯 RISULTATO FINALE

Bot Telegram attivo che:

- ✅ Risponde alle domande degli utenti
- ✅ Usa l'AI di Nuzantara
- ✅ È integrato con il sistema CRM
- ✅ Funziona 24/7

---

**Una volta configurato, il bot sarà pronto per assistere gli utenti!** 🚀
