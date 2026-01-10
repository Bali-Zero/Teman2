# Verifica Vercel Environment Variables - Guida Completa

## Accesso Vercel Dashboard

1. Vai su: https://vercel.com/dashboard
2. Accedi con le tue credenziali
3. Seleziona il progetto: **nuzantara-mouth** (o il nome del progetto frontend)

## Verifica Environment Variables

### Step 1: Naviga alle Settings

1. Nel progetto Vercel, clicca su **Settings** (menu laterale)
2. Clicca su **Environment Variables** (sotto "General")

### Step 2: Verifica Variabili Richieste

Cerca queste variabili nella lista:

#### ✅ NUZANTARA_API_URL

- **Nome**: `NUZANTARA_API_URL`
- **Valore atteso**: `https://nuzantara-rag.fly.dev`
- **Ambiente**: Deve essere presente per:
  - ✅ Production
  - ✅ Preview
  - ✅ Development

#### ✅ NEXT_PUBLIC_API_URL

- **Nome**: `NEXT_PUBLIC_API_URL`
- **Valore atteso**: `https://nuzantara-rag.fly.dev`
- **Ambiente**: Deve essere presente per:
  - ✅ Production
  - ✅ Preview
  - ✅ Development

### Step 3: Verifica Valori

Per ogni variabile, verifica:

1. **Valore esatto**: Deve essere esattamente `https://nuzantara-rag.fly.dev`
   - ❌ NO: `https://nuzantara-rag.fly.dev/` (trailing slash)
   - ❌ NO: `http://nuzantara-rag.fly.dev` (HTTP invece di HTTPS)
   - ❌ NO: Spazi extra o caratteri nascosti
   - ✅ SÌ: `https://nuzantara-rag.fly.dev`

2. **Ambiente**: Verifica che sia impostata per tutti gli ambienti necessari
   - Production (obbligatorio)
   - Preview (consigliato)
   - Development (consigliato per test locali)

## Se le Variabili MANCANO

### Aggiungi NUZANTARA_API_URL

1. Clicca su **Add New**
2. **Key**: `NUZANTARA_API_URL`
3. **Value**: `https://nuzantara-rag.fly.dev`
4. Seleziona ambienti: ✅ Production, ✅ Preview, ✅ Development
5. Clicca **Save**

### Aggiungi NEXT_PUBLIC_API_URL

1. Clicca su **Add New**
2. **Key**: `NEXT_PUBLIC_API_URL`
3. **Value**: `https://nuzantara-rag.fly.dev`
4. Seleziona ambienti: ✅ Production, ✅ Preview, ✅ Development
5. Clicca **Save**

## Dopo Aver Aggiunto/Modificato

### Redeploy Necessario

⚠️ **IMPORTANTE**: Dopo aver aggiunto o modificato environment variables, devi **redeployare** il progetto.

1. Vai su **Deployments** (menu laterale)
2. Trova l'ultimo deployment
3. Clicca sui **3 puntini** (⋯) → **Redeploy**
4. Oppure crea un nuovo deployment:
   - Vai su **Deployments** → **Create Deployment**
   - Oppure fai push di un commit (trigger automatico)

### Verifica Deployment

Dopo il redeploy:

1. Attendi che il deployment completi (status: ✅ Ready)
2. Verifica che il nuovo deployment abbia le env vars:
   - Clicca sul deployment → **Settings** → **Environment Variables**
   - Dovresti vedere le variabili configurate

## Verifica con Vercel CLI (Opzionale)

Se hai Vercel CLI installato:

```bash
# Installa Vercel CLI (se non presente)
npm i -g vercel

# Login
vercel login

# Lista environment variables
vercel env ls

# Verifica variabile specifica
vercel env ls | grep NUZANTARA_API_URL
vercel env ls | grep NEXT_PUBLIC_API_URL
```

## Troubleshooting

### Problema: Variabili presenti ma non funzionano

**Possibili cause**:
1. Variabili non sono per l'ambiente corretto (es. solo Development ma serve Production)
2. Valore contiene caratteri extra o spazi
3. Deployment non è stato rigenerato dopo l'aggiunta

**Soluzione**:
1. Verifica che le variabili siano per **Production**
2. Copia e incolla il valore esatto: `https://nuzantara-rag.fly.dev`
3. Redeploya il progetto

### Problema: Non vedo le variabili nel deployment

**Causa**: Le variabili sono state aggiunte dopo il deployment

**Soluzione**: 
- Redeploya il progetto (vedi sopra)

### Problema: Variabili diverse per ambiente

**Nota**: Puoi avere valori diversi per Production/Preview/Development, ma per questo caso devono essere tutte `https://nuzantara-rag.fly.dev`

## Checklist Finale

- [ ] `NUZANTARA_API_URL` presente in Vercel
- [ ] Valore è esattamente `https://nuzantara-rag.fly.dev`
- [ ] Impostata per Production (e Preview/Development se necessario)
- [ ] `NEXT_PUBLIC_API_URL` presente in Vercel
- [ ] Valore è esattamente `https://nuzantara-rag.fly.dev`
- [ ] Impostata per Production (e Preview/Development se necessario)
- [ ] Progetto è stato redeployato dopo l'aggiunta/modifica
- [ ] Nuovo deployment è completato e attivo

## Test Post-Configurazione

Dopo aver configurato le variabili e redeployato:

1. Apri `https://zantara.balizero.com/dashboard`
2. Apri DevTools (F12) → Console
3. Cerca errori che menzionano:
   - "Failed to load"
   - "Network error"
   - "CORS"
4. Se vedi errori 401/403, controlla i log proxy (ora includono dettagli cookie)

## Supporto

Se dopo aver verificato tutto il problema persiste:

1. Controlla Vercel Logs:
   - Vercel Dashboard → Deployments → [Ultimo deployment] → **Logs**
   - Cerca errori che menzionano "NUZANTARA_API_URL" o "NEXT_PUBLIC_API_URL"

2. Verifica che il proxy funzioni:
   - Controlla `apps/mouth/src/app/api/[...path]/route.ts`
   - Verifica che `getBackendBaseUrl()` restituisca il valore corretto

3. Testa direttamente il backend:
   ```bash
   curl https://nuzantara-rag.fly.dev/health
   ```
