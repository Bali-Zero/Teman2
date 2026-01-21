# 🚀 Guida Deploy - Nuzantara

## 📋 Quick Start

### Frontend (Vercel)

```bash
# Push a GitHub triggera deploy automatico
git push origin main
```

### Backend (Fly.io)

```bash
cd apps/backend-rag
flyctl deploy
```

## ✅ Pre-Deploy Checklist

- [ ] Test passanti: `npm test` (29/29)
- [ ] Nessuna vulnerabilità: `npm audit` (0)
- [ ] Linting OK: `npm run lint:check`
- [ ] Type check OK: `npm run typecheck` (errori non bloccanti OK)
- [ ] Commit creato con messaggio descrittivo

## 🔧 Configurazione

### Frontend (Vercel)

- **Deploy automatico**: Push su `main` branch
- **Build command**: Automatico (Next.js)
- **Environment**: Configurato su Vercel dashboard

### Backend (Fly.io)

- **Port**: Usa variabile `PORT` (default: 8080)
- **Host**: `0.0.0.0` (tutti gli indirizzi IPv4)
- **Health check**: `/health` endpoint
- **Grace period**: 30s
- **Workers**: 2 (per VM con 2 CPU)

## 📊 Status Deploy

### Ultimo Deploy

- **Data**: 2026-01-21
- **Commit**: `8b731041`
- **Frontend**: ✅ Deploy automatico Vercel
- **Backend**: ✅ Deploy Fly.io completato
- **URL Backend**: https://nuzantara-rag.fly.dev/

## ⚠️ Troubleshooting

### Warning Fly.io "app not listening"

**Risolto**: Il Dockerfile ora usa `${PORT:-8080}` invece di hardcodare `8080`.

### Test Falliti

**Risolto**: Tutti i test ora passano (29/29). Se falliscono, verificare:

1. Import logger presenti
2. Mock configurati correttamente
3. Console calls per test compatibility

### Vulnerabilità NPM

**Risolto**: Tutte le vulnerabilità sono state risolte. Se ne appaiono nuove:

```bash
npm audit fix --force
```

## 📚 Documentazione Correlata

- `DEPLOY_COMPLETE.md` - Status deploy completo
- `FIX_FLYIO_WARNING.md` - Fix warning Fly.io
- `SESSION_SUMMARY_2026_01_21.md` - Riepilogo sessione
- `CODEBASE_ANALYSIS_REPORT_2026_01_19.md` - Analisi codebase

## 🔍 Verifica Post-Deploy

1. **Frontend**: Verificare che compili correttamente su Vercel
2. **Backend**: Verificare health check su Fly.io
3. **Funzionalità**: Testare endpoint critici
4. **Logs**: Monitorare errori e warning

---

**Ultimo aggiornamento**: 2026-01-21
