# 🚀 Sentry Production Deployment Guide

## Situazione Attuale

- **App:** `apps/mouth/` (Frontend Next.js)
- **Deployment Platform:** **Vercel** (non Fly.io)
- **Status:** ✅ Configurazione Sentry completa
- **Manca:** Credenziali Sentry da aggiungere

---

## Step 1: Creare Progetto Sentry (5 min)

### 1.1 Vai su Sentry

```bash
# Apri browser
open https://sentry.io
```

O visita manualmente: **https://sentry.io**

### 1.2 Crea Nuovo Progetto

1. Login a Sentry (o crea account se non ce l'hai)
2. Click su **"Create Project"**
3. Seleziona piattaforma: **"Next.js"**
4. Nome progetto: **"mouth"**
5. Click **"Create Project"**

---

## Step 2: Ottenere Credenziali (2 min)

### 2.1 DSN (Data Source Name)

Dopo aver creato il progetto, vedrai la pagina di onboarding con il DSN:

```
https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxx@o123456.ingest.sentry.io/123456
```

**O in alternativa:**

1. Vai su **Settings → Projects → mouth**
2. Click su **"Client Keys (DSN)"**
3. Copia il **DSN**

### 2.2 Organization Slug

1. Vai su **Settings → General Settings**
2. Copia l'**Organization Slug** (es. `my-company`)

### 2.3 Auth Token (per Source Maps)

1. Vai su **Settings → Developer Settings → Auth Tokens**
2. Click **"Create New Token"**
3. Nome: `mouth-source-maps`
4. Permissions:
   - ✅ **Project: Read & Write**
   - ✅ **Release: Admin**
5. Click **"Create Token"**
6. **⚠️ IMPORTANTE:** Copia il token subito (non sarà più visibile)

---

## Step 3: Configurare Localmente (Opzionale ma Consigliato)

### 3.1 Aggiornare .env.local

```bash
cd apps/mouth
```

Aggiungi queste righe a `.env.local`:

```bash
# Sentry Configuration
NEXT_PUBLIC_SENTRY_DSN=https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxx@o123456.ingest.sentry.io/123456
SENTRY_DSN=https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxx@o123456.ingest.sentry.io/123456
SENTRY_ORG=your-org-slug
SENTRY_PROJECT=mouth
SENTRY_AUTH_TOKEN=your-auth-token-here
```

**Sostituisci:**

- `xxxxx...` con il tuo DSN
- `your-org-slug` con il tuo Organization Slug
- `your-auth-token-here` con il token appena creato

### 3.2 Testare Localmente

```bash
# Test build con source maps
pnpm build

# Verifica che non ci siano errori
# Dovresti vedere nei log: "Sentry webpack plugin" o simile
```

---

## Step 4: Aggiungere a Vercel (Production)

### Metodo 1: Via Vercel Dashboard (Raccomandato)

1. Vai su: **https://vercel.com/dashboard**
2. Seleziona il progetto: **"mouth"**
3. Vai su **Settings → Environment Variables**
4. Aggiungi le seguenti variabili:

| Variable Name            | Value                                            | Environments                              |
| ------------------------ | ------------------------------------------------ | ----------------------------------------- |
| `NEXT_PUBLIC_SENTRY_DSN` | `https://xxx...@o123456.ingest.sentry.io/123456` | ✅ Production, ✅ Preview, ✅ Development |
| `SENTRY_DSN`             | `https://xxx...@o123456.ingest.sentry.io/123456` | ✅ Production, ✅ Preview, ✅ Development |
| `SENTRY_ORG`             | `your-org-slug`                                  | ✅ Production, ✅ Preview, ✅ Development |
| `SENTRY_PROJECT`         | `mouth`                                          | ✅ Production, ✅ Preview, ✅ Development |
| `SENTRY_AUTH_TOKEN`      | `your-auth-token`                                | ✅ Production, ✅ Preview, ✅ Development |

5. Click **"Save"** per ogni variabile

### Metodo 2: Via Vercel CLI

```bash
cd apps/mouth

# Aggiungi variabili a Production
vercel env add NEXT_PUBLIC_SENTRY_DSN production
# Incolla il DSN quando richiesto

vercel env add SENTRY_DSN production
# Incolla lo stesso DSN

vercel env add SENTRY_ORG production
# Incolla l'org slug

vercel env add SENTRY_PROJECT production
# Digita: mouth

vercel env add SENTRY_AUTH_TOKEN production
# Incolla l'auth token

# Ripeti per Preview e Development se necessario
```

---

## Step 5: Deploy (1 min)

### Opzione A: Auto-Deploy (Raccomandato)

Vercel fa auto-deploy quando pusshi su `main`:

```bash
git add .
git commit -m "feat: add Sentry error tracking"
git push origin main
```

Vercel rileverà le nuove env vars e farà il deploy automaticamente.

### Opzione B: Manual Deploy

```bash
cd apps/mouth
vercel --prod
```

---

## Step 6: Verificare (2 min)

### 6.1 Controllare Deploy

```bash
# Vercel deploy logs
vercel logs --follow

# Cerca "Sentry" nei logs
```

O vai su: **https://vercel.com/dashboard → Deployments**

### 6.2 Testare Error Tracking

**Metodo 1: Test Manuale**

1. Vai su: **https://balizero.com**
2. Apri DevTools Console
3. Esegui:
   ```javascript
   throw new Error('[TEST] Sentry production tracking');
   ```

**Metodo 2: Aggiungere Pagina Test (Temporanea)**

Crea `apps/mouth/src/app/test-sentry/page.tsx`:

```typescript
'use client';

import { useEffect } from 'react';

export default function TestSentryPage() {
  useEffect(() => {
    throw new Error('[TEST] Sentry error tracking working!');
  }, []);

  return <div>Testing Sentry...</div>;
}
```

Deploy e visita: `https://balizero.com/test-sentry`

### 6.3 Verificare su Sentry Dashboard

1. Vai su: **https://sentry.io/organizations/[your-org]/issues/**
2. Dovresti vedere l'errore test apparire entro **5-10 secondi**
3. Click sull'errore per vedere:
   - ✅ Stack trace con file names originali (source maps funzionano)
   - ✅ User context (se autenticato)
   - ✅ Browser info, URL, headers
   - ✅ Session replay (se l'errore è stato catturato in una sessione attiva)

---

## Step 7: Cleanup (Opzionale)

Se hai creato una pagina test, rimuovila:

```bash
rm -rf apps/mouth/src/app/test-sentry/
git add .
git commit -m "chore: remove Sentry test page"
git push origin main
```

---

## ✅ Checklist Finale

- [ ] Progetto Sentry creato
- [ ] DSN ottenuto
- [ ] Organization Slug ottenuto
- [ ] Auth Token creato
- [ ] Variabili aggiunte a `.env.local` (opzionale)
- [ ] Variabili aggiunte a Vercel (production)
- [ ] Deploy effettuato
- [ ] Error tracking testato
- [ ] Errore visibile su Sentry dashboard
- [ ] Source maps funzionanti (stack trace leggibile)

---

## 🎯 Success Metrics

Una volta completato, dovresti vedere su Sentry:

1. **Errors Dashboard**
   - Real-time error tracking
   - Stack traces con file names originali (no minification)
   - Line numbers corretti

2. **Performance Monitoring**
   - Page load times
   - API response times
   - Slow transactions

3. **Session Replays**
   - Video replay delle sessioni con errori
   - User journey prima dell'errore
   - DOM mutations e console logs

---

## 🐛 Troubleshooting

### Problema: Errori non appaiono su Sentry

**Soluzione 1:** Verifica variabili Vercel

```bash
# Via dashboard
vercel env ls

# Verifica che ci siano tutte le 5 variabili SENTRY_*
```

**Soluzione 2:** Controlla build logs

```bash
vercel logs --follow

# Cerca "Sentry webpack plugin" nei logs
# Se non c'è, le env vars potrebbero non essere caricate
```

**Soluzione 3:** Force redeploy

```bash
vercel --prod --force
```

### Problema: Source maps non funzionano (stack trace minificato)

**Causa:** `SENTRY_AUTH_TOKEN` mancante o permissions insufficienti

**Soluzione:**

1. Verifica il token su Sentry → Developer Settings → Auth Tokens
2. Verifica permissions: **Project: Read & Write** + **Release: Admin**
3. Rigenera il token se necessario
4. Aggiorna su Vercel
5. Redeploy

### Problema: Troppi errori / Quota exceeded

**Soluzione:** Aggiusta sample rates in `sentry.client.config.ts`:

```typescript
Sentry.init({
  // ...
  tracesSampleRate: 0.05, // Riduci da 0.1 a 0.05 (5%)
  replaysSessionSampleRate: 0.05, // Riduci da 0.1 a 0.05 (5%)
});
```

---

## 📊 Costo Stimato

Per **~1,000 utenti/giorno** con sample rate 10%:

| Metrica         | Quantità | Sentry Plan                   |
| --------------- | -------- | ----------------------------- |
| Traced requests | ~100/day | Free: 5k/month ✅             |
| Session replays | ~100/day | Free: 50/month ⚠️ (team: 500) |
| Errors          | Tutti    | Free: 5k/month ✅             |

**Raccomandazione:** Piano **Team ($26/mo)** per session replays sufficienti

---

## 🔗 Links Utili

- **Sentry Dashboard:** https://sentry.io/organizations/[your-org]/issues/
- **Vercel Dashboard:** https://vercel.com/dashboard
- **Vercel Logs:** https://vercel.com/dashboard → Deployments → Logs
- **Sentry Docs:** https://docs.sentry.io/platforms/javascript/guides/nextjs/

---

## 📞 Quick Commands

```bash
# Verifica configurazione locale
cd apps/mouth && ./verify-sentry.sh

# Verifica variabili Vercel
vercel env ls

# Deploy manuale
vercel --prod

# Logs in real-time
vercel logs --follow

# Test build locale
pnpm build
```

---

## 🎉 Conclusione

Seguendo questi step, avrai **Sentry error tracking completo** in produzione su Vercel per `apps/mouth/`.

**Tempo totale stimato:** 15-20 minuti

**Prossimo passo:** Monitora il dashboard Sentry nei primi giorni per identificare errori critici.
