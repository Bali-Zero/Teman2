# VERCEL ENVIRONMENT VARIABLES CHECKLIST

**Data:** 2026-01-13  
**Purpose:** Verifica configurazione Sentry e altre env vars in Vercel

---

## 🔍 VERIFICA SENTRY ENV VARS

### Variabili Richieste:

#### 1. Sentry DSN (Server-side):

- **Nome:** `SENTRY_DSN`
- **Formato:** `https://xxx@sentry.io/xxx`
- **Scopo:** Error tracking server-side
- **Required:** ✅ Sì (se Sentry è abilitato)

#### 2. Sentry DSN (Client-side):

- **Nome:** `NEXT_PUBLIC_SENTRY_DSN`
- **Formato:** `https://xxx@sentry.io/xxx`
- **Scopo:** Error tracking client-side
- **Required:** ✅ Sì (se Sentry è abilitato)

#### 3. Sentry Organization:

- **Nome:** `SENTRY_ORG`
- **Formato:** `your-org-name`
- **Scopo:** Sentry organization per source maps
- **Required:** ⚠️ Opzionale (per source maps upload)

#### 4. Sentry Project:

- **Nome:** `SENTRY_PROJECT`
- **Formato:** `your-project-name`
- **Scopo:** Sentry project per source maps
- **Required:** ⚠️ Opzionale (per source maps upload)

---

## 📋 CHECKLIST VERIFICA

### Step 1: Accesso Vercel Dashboard

- [ ] Accedere a: https://vercel.com/dashboard
- [ ] Selezionare progetto: `nuzantara-2026` o `mouth`
- [ ] Andare su tab "Settings"
- [ ] Andare su sezione "Environment Variables"

### Step 2: Verifica Sentry Variables

- [ ] Verificare presenza `SENTRY_DSN`
- [ ] Verificare presenza `NEXT_PUBLIC_SENTRY_DSN`
- [ ] Verificare formato corretto (https://xxx@sentry.io/xxx)
- [ ] Verificare che siano configurate per tutti gli environments:
  - [ ] Production
  - [ ] Preview
  - [ ] Development (opzionale)

### Step 3: Verifica Opzionali (Source Maps)

- [ ] Verificare presenza `SENTRY_ORG` (opzionale)
- [ ] Verificare presenza `SENTRY_PROJECT` (opzionale)
- [ ] Se presenti, verificare valori corretti

### Step 4: Verifica Altre Env Vars Critiche

- [ ] `NEXT_PUBLIC_API_URL` - Backend API URL
- [ ] `NEXT_PUBLIC_FRONTEND_URL` - Frontend URL
- [ ] `NEXT_PUBLIC_WS_URL` - WebSocket URL (se usato)
- [ ] Altre variabili specifiche del progetto

---

## 🔧 CONFIGURAZIONE VERCEL

### Come Aggiungere/Modificare Env Vars:

1. **Via Dashboard:**
   - Settings → Environment Variables
   - Click "Add New"
   - Inserire nome e valore
   - Selezionare environments (Production/Preview/Development)
   - Click "Save"

2. **Via CLI:**

   ```bash
   cd apps/mouth
   vercel env add SENTRY_DSN production
   vercel env add NEXT_PUBLIC_SENTRY_DSN production
   vercel env add SENTRY_ORG production
   vercel env add SENTRY_PROJECT production
   ```

3. **Verifica via CLI:**
   ```bash
   cd apps/mouth
   vercel env ls
   ```

---

## ✅ VERIFICA FUNZIONAMENTO

### Test Sentry Integration:

1. **Verificare Build:**
   - Build deve completare senza errori
   - Se Sentry non configurato, build funziona comunque (conditional)

2. **Verificare Runtime:**
   - Generare errore intenzionale in produzione
   - Verificare che errore appaia in Sentry dashboard
   - Verificare stack trace completo

3. **Verificare Source Maps:**
   - Se `SENTRY_ORG` e `SENTRY_PROJECT` configurati
   - Source maps devono essere uploadati durante build
   - Stack traces devono mostrare codice originale

---

## 🚨 TROUBLESHOOTING

### Problema: Sentry non cattura errori

- ✅ Verificare `SENTRY_DSN` e `NEXT_PUBLIC_SENTRY_DSN` configurati
- ✅ Verificare formato corretto (https://...)
- ✅ Verificare che siano per environment corretto (Production)
- ✅ Verificare Sentry dashboard per eventuali rate limits

### Problema: Source maps non funzionano

- ✅ Verificare `SENTRY_ORG` e `SENTRY_PROJECT` configurati
- ✅ Verificare valori corretti (case-sensitive)
- ✅ Verificare build logs per upload source maps
- ✅ Verificare Sentry project settings

### Problema: Build fallisce con Sentry

- ✅ Verificare che env vars siano presenti
- ✅ Verificare formato corretto
- ✅ Verificare che Sentry plugin sia installato: `@sentry/nextjs`
- ✅ Verificare `next.config.ts` per configurazione Sentry

---

## 📊 CURRENT STATUS

### Verifica Completata:

- [ ] Date: \***\*\_\_\_\*\***
- [ ] Verificato da: \***\*\_\_\_\*\***
- [ ] Status: ✅/❌

### Variabili Presenti:

- [ ] `SENTRY_DSN`: ✅/❌
- [ ] `NEXT_PUBLIC_SENTRY_DSN`: ✅/❌
- [ ] `SENTRY_ORG`: ✅/❌/N/A
- [ ] `SENTRY_PROJECT`: ✅/❌/N/A

### Note:

```
[Inserire note qui]
```

---

## 🔗 LINKS UTILI

- Vercel Dashboard: https://vercel.com/dashboard
- Sentry Dashboard: https://sentry.io (se configurato)
- Vercel Docs: https://vercel.com/docs/environment-variables
- Sentry Next.js Docs: https://docs.sentry.io/platforms/javascript/guides/nextjs/

---

**Last Updated:** 2026-03-22
**Next Review:** After deployment
