# 🚀 NUZANTARA - Development Workflow

**Workflow completo per sviluppo locale e deployment**

---

## 📋 Overview

Questo documento descrive il workflow di sviluppo per Nuzantara, completamente basato su sviluppo locale e deployment manuale su Fly.io.

---

## 🔄 Workflow Completo

### 1. Sviluppo Locale

```bash
# 1. Setup iniziale (una volta)
cd /path/to/nuzantara
cp .env.example .env
cp apps/backend-rag/.env.example apps/backend-rag/.env
cp apps/mouth/.env.example apps/mouth/.env.local

# 2. Installazione dipendenze
npm install
cd apps/backend-rag && pip install -r requirements.txt && cd ../..

# 3. Avvio servizi locali
docker compose up -d  # Qdrant, Redis, monitoring

# 4. Sviluppo backend (Terminal 1)
cd apps/backend-rag
uvicorn backend.app.main_cloud:app --reload --port 8080

# 5. Sviluppo frontend (Terminal 2)
cd apps/mouth
npm run dev  # http://localhost:3000
```

---

## 📝 Workflow di Modifica Codice

### Step 1: Creare Branch Locale

```bash
# Crea nuovo branch per feature/fix
git checkout -b feature/nome-feature
# oppure
git checkout -b fix/nome-bug
```

### Step 2: Sviluppare e Testare Localmente

```bash
# Backend: Esegui test prima di commitare
cd apps/backend-rag
pytest tests/ -v
ruff check . --fix  # Linting automatico

# Frontend: Verifica build e test
cd apps/mouth
npm run typecheck
npm run lint:fix
npm run build  # Verifica che compili
```

### Step 3: Commit Locale

```bash
# Dalla root del progetto
git add .
git commit -m "feat: descrizione della modifica"
# oppure: fix:, docs:, refactor:, test:, chore:
```

### Step 4: Backup Opzionale

```bash
# Se vuoi fare backup su un repository remoto (opzionale)
git remote add backup <repository-url>
git push backup feature/nome-feature
```

**Nota**: Il backup è completamente opzionale. Nessun riferimento a piattaforme specifiche nel codice.

---

## 🔨 Build Process

### Build Locale (Pre-Deployment Testing)

#### Backend Build Test

```bash
cd apps/backend-rag

# Test build Docker locale (simula produzione)
docker build -t nuzantara-rag-test .

# Verifica che l'immagine funzioni
docker run --rm -p 8080:8080 nuzantara-rag-test

# Test in container
docker run --rm nuzantara-rag-test python -c "import backend.main_cloud"
```

#### Frontend Build Test

```bash
cd apps/mouth

# Build produzione locale
npm run build

# Verifica che il build sia completo
ls -la .next/standalone
ls -la .next/static

# Test build Docker locale (simula produzione)
docker build -t nuzantara-mouth-test .

# Verifica che l'immagine funzioni
docker run --rm -p 3000:3000 nuzantara-mouth-test
```

### Build durante Deployment Fly.io

**Fly.io esegue automaticamente il build quando fai deploy:**

```bash
# Backend: Fly.io legge Dockerfile e builda automaticamente
./scripts/fly-backend.sh deploy
# → Fly.io esegue: docker build usando apps/backend-rag/Dockerfile
# → Installa dipendenze Python
# → Copia codice
# → Crea immagine Docker ottimizzata

# Frontend: Fly.io legge Dockerfile e builda automaticamente
./scripts/fly-frontend.sh deploy
# → Fly.io esegue: docker build usando apps/mouth/Dockerfile
# → Installa dipendenze npm
# → Esegue: npm run build
# → Crea immagine Docker con Next.js standalone
```

---

## 🚀 Deployment su Fly.io

### Opzione A: Deployment con Build Test Locale (Consigliato)

```bash
# 1. Test build backend locale
cd apps/backend-rag
docker build -t nuzantara-rag-test . || echo "❌ Build fallito!"

# 2. Test build frontend locale
cd ../mouth
npm run build || echo "❌ Build fallito!"
docker build -t nuzantara-mouth-test . || echo "❌ Build Docker fallito!"

# 3. Se build locali passano, deploy
cd ../..
./scripts/fly-backend.sh deploy
./scripts/fly-frontend.sh deploy
```

### Opzione B: Deployment Diretto (Fly.io builda automaticamente)

```bash
# Fly.io esegue il build automaticamente durante deploy
./scripts/fly-backend.sh deploy   # Build + Deploy backend
./scripts/fly-frontend.sh deploy  # Build + Deploy frontend
```

**Nota**: Fly.io builda sempre durante `flyctl deploy`, anche se hai già fatto build locale.

---

## 🔍 Verifica Deployment

### Health Check

```bash
# Backend
curl https://nuzantara-rag.fly.dev/health | jq

# Frontend
curl -I https://nuzantara-mouth.fly.dev
```

### Logs

```bash
# Backend logs
./scripts/fly-backend.sh logs

# Frontend logs
./scripts/fly-frontend.sh logs

# Logs recenti
./scripts/fly-backend.sh logs --recent
```

### Status

```bash
# Backend status
./scripts/fly-backend.sh status

# Frontend status
./scripts/fly-frontend.sh status
```

---

## 📊 Workflow Completo: Esempio Pratico

### Scenario: Aggiungere Nuova Feature

```bash
# 1. Crea branch
git checkout -b feature/nuova-api-endpoint

# 2. Sviluppa localmente
# ... modifica codice ...

# 3. Test locale
cd apps/backend-rag
pytest tests/ -v
ruff check . --fix

# 4. Commit
git add .
git commit -m "feat(api): aggiungi nuovo endpoint /api/example"

# 5. Test completo
cd apps/backend-rag
pytest tests/ --cov=backend --cov-report=html

# 6. Deploy backend
./scripts/fly-backend.sh deploy

# 7. Verifica produzione
curl https://nuzantara-rag.fly.dev/api/example

# 8. Merge in main (locale)
git checkout main
git merge feature/nuova-api-endpoint

# 9. Backup opzionale (se configurato)
git push backup main
```

---

## 🛠️ Scripts Disponibili

### Scripts Fly.io

```bash
# Backend
./scripts/fly-backend.sh deploy      # Deploy backend
./scripts/fly-backend.sh logs        # Vedi logs
./scripts/fly-backend.sh status       # Status app
./scripts/fly-backend.sh secrets     # Gestisci secrets

# Frontend
./scripts/fly-frontend.sh deploy     # Deploy frontend
./scripts/fly-frontend.sh logs      # Vedi logs
./scripts/fly-frontend.sh status     # Status app
```

### Scripts Testing

```bash
# Backend
cd apps/backend-rag
pytest tests/unit -v                # Solo unit tests
pytest tests/integration -v           # Solo integration tests
pytest tests/ --cov=backend           # Con coverage

# Frontend
cd apps/mouth
npm run test                          # Esegui test
npm run typecheck                     # Verifica TypeScript
npm run lint                          # Linting
npm run build                         # Build produzione locale
```

### Scripts Build

```bash
# Backend - Build Docker locale (test)
cd apps/backend-rag
docker build -t nuzantara-rag-test .
docker run --rm -p 8080:8080 nuzantara-rag-test  # Test locale

# Frontend - Build produzione locale
cd apps/mouth
npm run build                         # Build Next.js
docker build -t nuzantara-mouth-test .  # Build Docker locale
docker run --rm -p 3000:3000 nuzantara-mouth-test  # Test locale
```

### Scripts Utility

```bash
# Health check locale
npm run health-check

# Sentinel (system health)
python apps/core/sentinel.py

# Coverage gate (pre-push)
npm run coverage:gate
```

---

## 🔐 Gestione Secrets

### Fly.io Secrets

```bash
# Backend secrets
./scripts/fly-backend.sh secrets set KEY=value
./scripts/fly-backend.sh secrets list

# Frontend secrets
./scripts/fly-frontend.sh secrets set KEY=value
./scripts/fly-frontend.sh secrets list
```

### Secrets Comuni

```bash
# Backend
flyctl secrets set JWT_SECRET_KEY="..." --app nuzantara-rag
flyctl secrets set DATABASE_URL="..." --app nuzantara-rag
flyctl secrets set OPENAI_API_KEY="..." --app nuzantara-rag
flyctl secrets set GOOGLE_API_KEY="..." --app nuzantara-rag

# Frontend
flyctl secrets set NEXT_PUBLIC_API_URL="..." --app nuzantara-mouth
```

---

## 📦 Versionamento Git

### Branch Strategy

```bash
main          # Branch principale (produzione)
feature/*     # Nuove feature
fix/*         # Bug fixes
docs/*        # Documentazione
refactor/*    # Refactoring
```

### Commit Convention

```bash
feat:     # Nuova feature
fix:      # Bug fix
docs:     # Documentazione
refactor: # Refactoring
test:     # Test
chore:    # Build, config, etc.
```

### Esempi

```bash
git commit -m "feat(api): aggiungi endpoint conversazioni"
git commit -m "fix(auth): risolvi problema JWT expiration"
git commit -m "docs(readme): aggiorna istruzioni setup"
git commit -m "refactor(rag): ottimizza query routing"
```

---

## 🔄 Backup Opzionale

### Setup Iniziale (Una Volta)

```bash
# Aggiungi remote per backup (opzionale)
git remote add backup <repository-url>

# Verifica remotes
git remote -v
```

### Backup Periodico

```bash
# Push branch corrente
git push backup feature/nome-feature

# Push main
git push backup main

# Push tutti i branch
git push backup --all

# Push tags
git push backup --tags
```

**Nota**: Il backup è completamente opzionale. Nessun workflow automatizzato o CI/CD configurato nel codice.

---

## 🚨 Troubleshooting

### Deployment Fallisce

```bash
# 1. Verifica logs
./scripts/fly-backend.sh logs --recent

# 2. Verifica status
./scripts/fly-backend.sh status

# 3. Verifica secrets
./scripts/fly-backend.sh secrets list

# 4. Rollback se necessario
./scripts/fly-backend.sh releases
./scripts/fly-backend.sh releases rollback <version>
```

### Test Falliscono Localmente

```bash
# Backend
cd apps/backend-rag
pytest tests/ -v --tb=short  # Mostra errori dettagliati
ruff check . --show-source    # Mostra problemi linting

# Frontend
cd apps/mouth
npm run typecheck             # Errori TypeScript
npm run lint                  # Errori linting
```

### Problemi Database

```bash
# Verifica connessione
curl https://nuzantara-rag.fly.dev/health | jq .database

# Restart database (se necessario)
flyctl restart --app nuzantara-postgres
```

---

## 📈 Best Practices

### Prima di Deployare

1. ✅ **Test locali passano**: `pytest tests/ -v`
2. ✅ **Linting pulito**: `ruff check .`
3. ✅ **Build frontend OK**: `npm run build`
4. ✅ **TypeScript OK**: `npm run typecheck`
5. ✅ **Health check locale**: `curl http://localhost:8080/health`

### Durante Sviluppo

1. ✅ **Commit frequenti**: Piccoli commit incrementali
2. ✅ **Test prima di commit**: Esegui test localmente
3. ✅ **Branch separati**: Una feature = un branch
4. ✅ **Messaggi chiari**: Commit message descrittivi

### Dopo Deployment

1. ✅ **Verifica health**: Controlla `/health` endpoint
2. ✅ **Monitora logs**: Guarda logs per errori
3. ✅ **Test produzione**: Verifica che funzioni in produzione
4. ✅ **Backup opzionale**: Push su repository remoto per backup (se configurato)

---

## 🎯 Workflow Rapido (Daily)

```bash
# 1. Pull eventuali cambiamenti (se lavori su più macchine)
git pull

# 2. Crea branch per lavoro del giorno
git checkout -b feature/lavoro-oggi

# 3. Sviluppa e testa localmente
# ... codice ...

# 4. Test
cd apps/backend-rag && pytest tests/ -v

# 5. Commit
git add . && git commit -m "feat: descrizione"

# 6. Deploy (se pronto)
./scripts/fly-backend.sh deploy

# 7. Verifica produzione
curl https://nuzantara-rag.fly.dev/health

# 8. Merge in main
git checkout main
git merge feature/lavoro-oggi

# 9. Backup opzionale (se configurato)
git push backup main
```

---

## 🔨 Dettagli Build Process

### Backend Build (Python/FastAPI)

**Durante `flyctl deploy`:**
1. Fly.io legge `apps/backend-rag/Dockerfile`
2. Stage 1 (Builder): Installa dipendenze Python da `requirements.txt`
3. Stage 2 (Runtime): Copia dipendenze + codice sorgente
4. Crea immagine Docker ottimizzata (~500MB)
5. Deploy su Fly.io

**Build locale (test):**
```bash
cd apps/backend-rag
docker build -t nuzantara-rag-test .
# Verifica: docker run --rm -p 8080:8080 nuzantara-rag-test
```

### Frontend Build (Next.js)

**Durante `flyctl deploy`:**
1. Fly.io legge `apps/mouth/Dockerfile`
2. Stage 1 (Deps): Installa `node_modules` da `package.json`
3. Stage 2 (Builder): Esegue `npm run build` (crea `.next/`)
4. Stage 3 (Runner): Copia solo file necessari (standalone)
5. Crea immagine Docker ottimizzata (~200MB)
6. Deploy su Fly.io

**Build locale (test):**
```bash
cd apps/mouth
npm run build                    # Build Next.js
docker build -t nuzantara-mouth-test .
# Verifica: docker run --rm -p 3000:3000 nuzantara-mouth-test
```

### Quando Fly.io Builda

- ✅ **Sempre durante `flyctl deploy`**: Fly.io builda automaticamente
- ✅ **Build remoto**: Su server Fly.io (più veloce, cache ottimizzata)
- ✅ **Build locale opzionale**: Per testare prima di deployare

### Vantaggi Build Locale Prima

1. ✅ **Trova errori prima**: Build fallisce localmente = non deployi
2. ✅ **Risparmia tempo**: Non aspetti build remoto se fallisce
3. ✅ **Test completo**: Verifica che tutto funzioni localmente
4. ✅ **Debug più facile**: Errori visibili immediatamente

---

## 📚 Riferimenti

- **Deployment Guide**: `docs/DEPLOY_RUNBOOK.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Testing Guide**: `docs/TESTING_WORKFLOW.md`
- **Complete Workflow**: `docs/COMPLETE_WORKFLOW_GUIDE.md`

---

**Ultimo aggiornamento**: 2025-01-16  
**Workflow**: Locale-first con deployment manuale Fly.io  
**Build**: Automatico durante deploy, test locale opzionale

