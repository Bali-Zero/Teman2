# Development Guidelines - Nuzantara Platform

**Last Updated:** 2026-01-16
**Version:** 2.0

---

## 🎯 Principi Fondamentali

1. **Safety First** - Test locale prima di ogni push
2. **Verify Before Delete** - Verificare dipendenze prima di cleanup
3. **Build Locally** - Mai pushare senza test build
4. **Document Changes** - Ogni modifica importante va documentata

---

## 📦 Architettura Monorepo

### Struttura Workspace

```
nuzantara/                         # Root workspace (solo config)
├── apps/
│   ├── mouth/                     # Frontend Next.js → Vercel "mouth"
│   ├── backend-rag/               # Backend FastAPI → Fly.io
│   └── bali-intel-scraper/        # Scraper service
├── docs/                          # Documentazione
├── scripts/                       # Utility scripts
└── package.json                   # Workspace root config
```

### Deployment Mapping

| Workspace          | Platform | Project Name  | URL                        |
| ------------------ | -------- | ------------- | -------------------------- |
| `apps/mouth`       | Vercel   | `mouth`       | kita.balizero.com          |
| `apps/backend-rag` | Fly.io   | `backend-rag` | backend-rag.fly.dev        |
| Root (nuzantara)   | Vercel   | `nuzantara`   | ⚠️ Non usato (solo config) |

**IMPORTANTE:** Il deployment root "nuzantara" su Vercel NON serve - è solo configurazione workspace.

---

## ✅ Workflow Sviluppo

### 1. Prima di Modificare Codice

```bash
# Aggiornare branch
git pull origin main

# Reinstallare dipendenze se necessario
npm install

# Verificare ambiente funzionante
cd apps/mouth && npm run build
```

### 2. Durante Sviluppo

```bash
# Sviluppo locale
npm run dev

# Test continuo (watch mode)
npm run test

# Typecheck
npm run typecheck
```

### 3. Prima di Committare

**CHECKLIST OBBLIGATORIA:**

- [ ] ✅ Build locale completato: `npm run build`
- [ ] ✅ Test passati: `npm run test:ci`
- [ ] ✅ Typecheck OK: `npm run typecheck`
- [ ] ✅ Formato codice: `npm run format`
- [ ] ✅ Nessun file sensibile incluso (.env, credentials, etc)

```bash
# Workflow completo
cd apps/mouth
npm run build          # OBBLIGATORIO
npm run test:ci        # OBBLIGATORIO
npm run typecheck      # OBBLIGATORIO

# Solo se TUTTO OK:
git add .
git commit -m "feat: description"
git push origin main
```

### 4. Dopo Push

```bash
# Monitorare deployment
# Vercel: https://vercel.com/nuzantara-2026/mouth/deployments

# Verificare status dopo 2-3 minuti
# ✅ Ready → OK
# ❌ Error → Rollback immediato
```

---

## 🚫 Regole Anti-Pattern

### REGOLA 1: Mai Creare Stub Senza Verificare Originale

**❌ SBAGLIATO:**

```typescript
// File da eliminare: analytics.ts (270 righe)
// Creo stub minimo

// analytics.ts (nuovo)
export const analytics = {
  track: () => {}, // ← Solo 1 metodo, originale ne aveva 12!
};
```

**✅ CORRETTO:**

```bash
# 1. Verificare file originale
git show HEAD:apps/mouth/src/lib/analytics.ts | wc -l
# Output: 270 righe

# 2. Verificare exports
git show HEAD:apps/mouth/src/lib/analytics.ts | grep "export"
# Output: 12 export functions

# 3. Verificare se usato
grep -r "analytics" apps/mouth/src --include="*.tsx"
# Output: 15 file usano analytics

# 4. DECISIONE: NON ELIMINARE, è codice funzionante!
```

### REGOLA 2: Test Build Locale OBBLIGATORIO

**❌ SBAGLIATO:**

```bash
git add .
git commit -m "cleanup files"
git push    # ← Push senza build test!
# Risultato: Deployment fallito, 3 minuti persi
```

**✅ CORRETTO:**

```bash
npm run build    # ← Test build PRIMA di push
# ✓ Generating static pages (62/62)

git add .
git commit -m "cleanup files"
git push    # ← Push solo se build OK
```

**Tempo risparmiato:**

- Build locale: 2 minuti
- Deployment fallito: 3 minuti + debug 30 minuti
- **Risparmio: 31 minuti**

### REGOLA 3: Verificare Dipendenze Prima di Delete

**❌ SBAGLIATO:**

```bash
# Elimino file che sembrano legacy
git rm docs/LEGACY_*.md
git rm apps/mouth/src/lib/old-*.ts
git commit -m "cleanup legacy files"
# Risultato: Build fallito, file "old-analytics.ts" ancora usato!
```

**✅ CORRETTO:**

```bash
# 1. Lista file da eliminare
FILES_TO_DELETE=$(git diff --name-only --diff-filter=D)

# 2. Per ogni file, verificare se usato
for file in $FILES_TO_DELETE; do
  basename=$(basename $file .ts .tsx)
  USAGE=$(grep -r "$basename" apps/mouth/src --include="*.tsx" --include="*.ts")

  if [ ! -z "$USAGE" ]; then
    echo "⚠️  ATTENZIONE: $file ancora usato!"
    echo "$USAGE"
    exit 1
  fi
done

# 3. Solo se NESSUN file usato → commit
git commit -m "cleanup verified unused files"
```

### REGOLA 4: Monorepo - Test OGNI App Separatamente

**❌ SBAGLIATO:**

```bash
# Root
npm run build  # ← Non testa apps/mouth!

git push
# Risultato: "mouth" deployment fallito
#            "nuzantara" deployment OK (ma non serve)
```

**✅ CORRETTO:**

```bash
# Test TUTTE le app che deployano

# 1. Frontend
cd apps/mouth
npm run build
cd ../..

# 2. Backend (se modificato)
cd apps/backend-rag
pytest
cd ../..

# 3. Solo se TUTTO OK → push
git push origin main

# 4. Verificare ENTRAMBI i deployment
# - Vercel "mouth" → DEVE essere Ready
# - Fly.io "backend-rag" → Verificare se modificato
```

---

## 🗑️ Cleanup File - Procedura Sicura

### Checklist Pre-Cleanup

Prima di eliminare QUALSIASI file:

```bash
# 1. Identificare file da eliminare
git status
git diff --name-only

# 2. Categorizzare
DOCS_FILES=()        # Documentazione vera legacy
CODE_FILES=()        # File codice
CONFIG_FILES=()      # File configurazione
TEST_FILES=()        # File test

# 3. Per OGNI file codice, verificare:
for file in "${CODE_FILES[@]}"; do
  # a) Esiste ancora?
  [ -f "$file" ] || continue

  # b) Quanto è grande?
  lines=$(wc -l < "$file")
  echo "$file: $lines righe"

  # c) È importato?
  basename=$(basename "$file" .ts .tsx .js)
  imports=$(grep -r "from.*$basename\|import.*$basename" apps/ --include="*.tsx" --include="*.ts" | wc -l)

  if [ $lines -gt 50 ] && [ $imports -gt 0 ]; then
    echo "⚠️  $file: $lines righe, $imports import → NON ELIMINARE"
  fi
done
```

### Template Script Cleanup Sicuro

```bash
#!/bin/bash
# safe-cleanup.sh

set -e

echo "🔍 Verifica file da eliminare..."

# File da eliminare (modificare questa lista)
FILES_TO_DELETE=(
  "docs/OLD_README.md"
  "scripts/deprecated_script.sh"
)

# Verifica ogni file
for file in "${FILES_TO_DELETE[@]}"; do
  echo "Verifico: $file"

  # Se non esiste, skip
  [ -f "$file" ] || { echo "  ⏭️  File già eliminato"; continue; }

  # Conta righe
  lines=$(wc -l < "$file" 2>/dev/null || echo 0)

  # Se è codice (>10 righe), verifica imports
  if [ $lines -gt 10 ]; then
    basename=$(basename "$file" .ts .tsx .js .py)
    imports=$(grep -r "$basename" apps/ --include="*.tsx" --include="*.ts" --include="*.py" 2>/dev/null | wc -l)

    if [ $imports -gt 0 ]; then
      echo "  ❌ ERRORE: $file ancora usato in $imports file!"
      echo "  NON eliminare questo file!"
      exit 1
    fi
  fi

  echo "  ✅ Sicuro da eliminare ($lines righe, 0 import)"
done

echo ""
echo "✅ Tutti i file verificati sono sicuri da eliminare"
echo "Eseguire: git rm <files> && git commit && git push"
```

---

## 🔄 Ripristino File Eliminati per Errore

### Scenario: File Eliminato ma Ancora Usato

```bash
# 1. Identificare commit che ha eliminato
git log --all --full-history -- path/to/deleted/file.ts

# 2. Recuperare da commit precedente
git show COMMIT_HASH^:path/to/deleted/file.ts > path/to/deleted/file.ts

# 3. Verificare contenuto
cat path/to/deleted/file.ts
wc -l path/to/deleted/file.ts

# 4. Test build
npm run build

# 5. Se OK, committare
git add path/to/deleted/file.ts
git commit -m "fix: restore accidentally deleted file"
git push origin main
```

### Template Ripristino Multipli File

```bash
# Ripristinare più file dal commit prima del cleanup
CLEANUP_COMMIT="7d5f8bd0"

# File da ripristinare
FILES=(
  "apps/mouth/src/lib/enhanced-analytics.tsx"
  "apps/mouth/src/lib/metrics/dashboard-metrics.ts"
  "apps/mouth/src/components/providers/QueryProvider.tsx"
)

for file in "${FILES[@]}"; do
  git show ${CLEANUP_COMMIT}^:$file > $file
  echo "✅ Ripristinato: $file"
done

# Test build
cd apps/mouth && npm run build && cd ../..

# Commit tutti insieme
git add "${FILES[@]}"
git commit -m "fix: restore accidentally deleted implementation files"
git push origin main
```

---

## 📊 Quality Gates

### Build Gate (OBBLIGATORIO)

```bash
# apps/mouth/package.json
{
  "scripts": {
    "prebuild": "npm run typecheck",  # Typecheck prima di build
    "build": "next build",
    "postbuild": "echo '✅ Build completato con successo'"
  }
}
```

### Pre-commit Hook

```bash
# .husky/pre-commit
#!/usr/bin/env sh

echo "🔍 Running pre-commit checks..."

# Format check
npm run format:check || {
  echo "❌ Format errors. Run: npm run format"
  exit 1
}

# Build check (solo se modificato apps/mouth)
if git diff --cached --name-only | grep -q "apps/mouth/src"; then
  echo "📦 Testing build..."
  cd apps/mouth && npm run build && cd ../.. || {
    echo "❌ Build failed. Fix errors before commit."
    exit 1
  }
fi

echo "✅ Pre-commit checks passed"
```

---

## 🐛 Debug Tips

### Build Fallito Localmente

```bash
# 1. Pulire cache
rm -rf .next
rm -rf node_modules
npm install

# 2. Rebuild
npm run build 2>&1 | tee build.log

# 3. Analizzare errori
grep "Error:" build.log
grep "Module not found" build.log

# 4. Verificare import
# Se errore: Module not found: '@/lib/xxx'
ls -la apps/mouth/src/lib/xxx.*
```

### Deployment Fallito su Vercel

```bash
# 1. Verificare deployment logs su Vercel UI

# 2. Riprodurre in locale
cd apps/mouth
npm run build

# 3. Se build locale OK ma Vercel fallisce:
#    Verificare vercel.json e next.config.ts

# 4. Rollback veloce
git revert HEAD
git push origin main
```

---

## 📚 Risorse

- [Next.js Documentation](https://nextjs.org/docs)
- [Vercel Deployment](https://vercel.com/docs)
- [Monorepo Best Practices](https://monorepo.tools)
- [Git Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows)

---

## 🔄 Change Log

### v2.0 - 2026-01-16

- ✅ Aggiunte 4 regole anti-pattern critiche
- ✅ Aggiunta procedura cleanup sicuro
- ✅ Aggiunto template ripristino file
- ✅ Aggiunto debug tips

### v1.0 - 2026-01-01

- Initial version
