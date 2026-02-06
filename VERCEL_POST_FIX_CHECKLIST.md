# 🎯 VERCEL POST-FIX CHECKLIST

## Prima: Hai completato il fix manuale?

### Checklist Fix Manuale (Dashboard Vercel)

- [ ] Aperto https://vercel.com/nuzantara-2026/mouth/settings
- [ ] Root Directory cambiato da `apps/mouth` a `.`
- [ ] Build Command: `pnpm build --filter=mouth`
- [ ] Output Directory: `apps/mouth/.next`
- [ ] Install Command: `pnpm install`
- [ ] Cliccato "Save" nelle settings
- [ ] Cliccato "Clear Build Cache"
- [ ] Fatto "Redeploy" dell'ultimo deployment

---

## Dopo il Fix: Verifica Deployment

### Step 1: Aspetta Build Completo (3-5 min)

```bash
# Monitora status ogni 30 secondi
cd apps/mouth
watch -n 30 'vercel ls | head -10'
```

O manualmente:

```bash
cd apps/mouth
vercel ls
```

**Aspetta fino a vedere:**

```
Status: ● Ready     (invece di ● Error o ● Building)
```

### Step 2: Verifica Logs Se Ready

```bash
cd apps/mouth
vercel inspect $(vercel ls --json | jq -r '.[0].url') --logs
```

**Cerca nel log:**

- ✅ `pnpm install` completato senza errori
- ✅ `pnpm build --filter=mouth` completato
- ✅ Nessun `ERR_INVALID_THIS` o `ERR_PNPM_META_FETCH_FAIL`
- ✅ Build artifacts caricati

### Step 3: Test Produzione

Una volta deployment ● Ready:

```bash
# Ottieni URL produzione
cd apps/mouth
PROD_URL=$(vercel ls --json | jq -r '.[0].url')
echo "Testing: https://$PROD_URL"

# Test healthcheck
curl -I https://$PROD_URL
```

**Aspettati:**

```
HTTP/2 200
```

### Step 4: Verifica Sentry Funziona

Apri in browser:

```
https://mouth-nuzantara-2026.vercel.app
```

**Test Sentry:**

1. Apri DevTools Console
2. Trigger un errore di test (se hai pulsante debug)
3. Vai su Sentry dashboard: https://sentry.io/organizations/nuzantara-2026/
4. Verifica che errore appaia in Issues

---

## Se Deployment Ancora Error

### Diagnostica Avanzata

```bash
# 1. Verifica deployment ID più recente
cd apps/mouth
vercel ls --json | jq '.[0]'

# 2. Ottieni log completo
vercel inspect $(vercel ls --json | jq -r '.[0].url') --logs > /tmp/vercel-debug.log

# 3. Cerca errori specifici
cat /tmp/vercel-debug.log | grep -i "error\|failed\|err_"
```

### Controlli Dashboard

Apri: https://vercel.com/nuzantara-2026/mouth/settings

**Verifica:**

- [ ] Root Directory = `.` (punto, non `apps/mouth`)
- [ ] Build Cache vuota (appena pulita)
- [ ] No errori in Environment Variables
- [ ] Branch connesso è `main`

### Se Persiste: Ricrea Progetto

**Ultimo resort** (solo se ancora error):

```bash
# 1. Scarica env vars attuali
cd apps/mouth
vercel env pull .env.vercel.backup

# 2. Rimuovi progetto attuale
vercel remove mouth --yes

# 3. Ricrea progetto da zero
vercel --prod
# Segui wizard:
#   - Set up and deploy: Yes
#   - Which scope: nuzantara-2026
#   - Link to existing: No
#   - Project name: mouth
#   - Directory: . (root)
#   - Override settings: Yes
#   - Build Command: pnpm build --filter=mouth
#   - Output Directory: apps/mouth/.next
#   - Install Command: pnpm install
```

---

## Success Checklist

Una volta che deployment è ● Ready:

### Deployment Success

- [ ] `vercel ls` mostra status `● Ready`
- [ ] URL production accessibile
- [ ] Homepage carica senza errori
- [ ] DevTools console pulita (no errori critici)

### Sentry Success

- [ ] Sentry.init() in console (check DevTools)
- [ ] Test error appare in Sentry dashboard
- [ ] Session replay registra (se abilitato)
- [ ] User context tracciato

### Monorepo Success

- [ ] Build usa pnpm (non npm/yarn)
- [ ] Dependencies da root installate
- [ ] No warning "Moving X to node_modules/.ignored"
- [ ] Build cache pulita

---

## Cleanup Files (Opzionale)

Una volta confermato tutto funziona:

```bash
# Rimuovi file di debug
rm -f VERCEL_FAILURE_INVESTIGATION.md
rm -f VERCEL_FIX_GUIDE.md
rm -f VERCEL_MANUAL_FIX_REQUIRED.md
rm -f VERCEL_POST_FIX_CHECKLIST.md

# Mantieni vercel.json (consigliato per monorepo)
# O rimuovi se preferisci gestire da dashboard:
# git rm vercel.json
```

---

## Monitoring Continuo

### Setup Alerts

Vai su: https://vercel.com/nuzantara-2026/mouth/settings/notifications

**Abilita:**

- [ ] Deployment Failed
- [ ] Deployment Ready
- [ ] Build Time Exceeded

### Monitoring Commands

```bash
# Check deployment status
vercel ls | head -5

# Check logs ultimo deployment
vercel logs $(vercel ls --json | jq -r '.[0].url')

# Check Sentry errors
# (vai su Sentry dashboard)
```

---

## 🚀 Next Steps Dopo Success

1. **Commit cleanup** (se hai rimosso file debug)
2. **Test completo** tutte le feature principali
3. **Verifica Sentry** sta tracciando errori correttamente
4. **Update team** che deployment è fixed
5. **Monitor** per 24h per assicurarti stabilità

---

**Status:** Post-Fix Verification  
**Docs:** Questo file + vercel.json nella root  
**Support:** Se problemi persistono, crea issue con log completi
