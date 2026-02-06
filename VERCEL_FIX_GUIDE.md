# 🔧 FIX VERCEL DEPLOYMENT - Root Directory

## Problema Identificato

Vercel sta cercando il progetto nel path sbagliato:

- ❌ Attuale: `apps/mouth` (Root Directory nella configurazione Vercel)
- ✅ Corretto: `.` (root del repository)

Il monorepo ha questa struttura:

```
nuzantara/
├── pnpm-lock.yaml        ← Qui
├── pnpm-workspace.yaml    ← Qui
├── package.json           ← Qui
└── apps/
    └── mouth/             ← Progetto Vercel punta qui (SBAGLIATO)
        ├── package.json
        └── next.config.ts
```

## Soluzione: Correggere Root Directory su Vercel Dashboard

### Passo 1: Apri Settings

https://vercel.com/nuzantara-2026/mouth/settings

### Passo 2: Trova "Root Directory"

Nella sezione **General** → Scroll down fino a **Root Directory**

### Passo 3: Correggi il Valore

Attuale: `apps/mouth`  
Nuovo: `.` (punto, significa root del repo)

### Passo 4: Salva

Clicca **Save** in basso a destra

## Build Settings da Configurare

Dopo aver corretto Root Directory, verifica anche questi settings:

### Build Command

```bash
pnpm build --filter=mouth
```

### Output Directory

```
apps/mouth/.next
```

### Install Command

```bash
pnpm install
```

## Trigger Nuovo Deployment

Una volta salvate le modifiche, trigga nuovo deployment:

### Opzione 1: Da Dashboard

1. Vai su https://vercel.com/nuzantara-2026/mouth
2. Clicca sui 3 puntini dell'ultimo deployment
3. Clicca "Redeploy"

### Opzione 2: Da CLI

```bash
cd /Users/antonellosiano/Projects/nuzantara
vercel --prod
```

### Opzione 3: Push Git (automatico)

```bash
git commit --allow-empty -m "trigger: redeploy after fixing root directory"
git push origin main
```

## Verificare Deployment

```bash
cd apps/mouth
vercel ls
```

Aspetta status: `● Ready`

## Cleanup (dopo fix)

Rimuovere il `vercel.json` temporaneo:

```bash
cd /Users/antonellosiano/Projects/nuzantara
git rm apps/mouth/vercel.json
git commit -m "chore: remove temporary vercel.json after dashboard fix"
git push origin main
```

## Log Errori Attuali

Ultimi 3 deployment falliti per:

1. **Path duplicato**: `apps/mouth/apps/mouth`
2. **pnpm-lock.yaml non trovato**: Cercava in `apps/mouth/` invece che root
3. **npm registry errors**: `pnpm install` fallito per problemi rete/config

Tutti causati da Root Directory errato.

## Documentazione Vercel

- [Monorepo Guide](https://vercel.com/docs/monorepos)
- [Build Configuration](https://vercel.com/docs/projects/project-configuration)

---

**NEXT STEP:** Apri il browser e correggi Root Directory su Vercel Dashboard, poi trigga redeploy.
