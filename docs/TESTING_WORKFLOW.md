# 🧪 NUZANTARA PRIME - Testing Workflow

**Best practices per sviluppo e testing del backend**

## Overview

Questo documento descrive il workflow consigliato per sviluppare e testare il backend, garantendo che solo codice testato venga pushato e prevenendo fallimenti nelle pipeline di testing automatizzato.

## Workflow Consigliato

### 1. Prima di Iniziare

```bash
# Assicurati di essere aggiornato
git pull origin main

# Verifica che i test passino
cd apps/backend-rag
python -m pytest tests/unit/ -v
```

### 2. Durante lo Sviluppo

**Test Incrementali:**
```bash
# Mentre sviluppi, testa i file che modifichi
cd apps/backend-rag
python -m pytest tests/unit/test_context_builder.py -v

# Oppure usa il validatore incrementale
python scripts/validate_tests.py
```

**Best Practice:**
- Esegui i test dopo ogni modifica significativa
- Non aspettare fino al push per scoprire problemi
- Usa `-v` per vedere output dettagliato

### 3. Prima del Commit

**Validazione Automatica (Pre-Commit Hook):**
```bash
git add .
git commit -m "feat: add new feature"
# Gli hook pre-commit eseguono automaticamente:
# - Linting (Ruff)
# - Formatting
# - Security checks
```

**Se gli hook falliscono:**
- La maggior parte dei problemi viene auto-fixata
- Riprova: `git add . && git commit -m "..."`

### 4. Prima del Push

**Validazione Automatica (Pre-Push Hook):**
```bash
git push origin main
# Il hook pre-push esegue automaticamente:
# - Backend unit tests
# Se i test falliscono, il push viene bloccato
```

**Validazione Manuale (Opzionale):**
```bash
# Validazione veloce (solo unit tests)
npm run validate:backend

# Oppure
./scripts/validate_backend_tests.sh --fast

# Validazione completa (tutti i test)
npm run validate:backend:full

# Oppure
./scripts/validate_backend_tests.sh --full --coverage
```

### 5. Se i Test Falliscono

**Workflow di Fix:**

1. **Vedi quali test falliscono:**
   ```bash
   cd apps/backend-rag
   python -m pytest tests/unit/ -v
   ```

2. **Fix i test:**
   - Leggi il messaggio di errore
   - Verifica cosa è cambiato nel codice
   - Aggiorna i test o il codice di conseguenza

3. **Verifica che i fix funzionino:**
   ```bash
   python -m pytest tests/unit/ -v
   ```

4. **Riprova il push:**
   ```bash
   git push origin main
   ```

## Comandi Utili

### Test Veloce (Solo Unit Tests)
```bash
cd apps/backend-rag
python -m pytest tests/unit/ -v
```

### Test Completo (Unit + Integration)
```bash
cd apps/backend-rag
python -m pytest tests/ -v
```

### Test con Coverage
```bash
cd apps/backend-rag
python -m pytest tests/unit/ --cov=backend --cov-report=term-missing
```

### Test Specifico
```bash
cd apps/backend-rag
python -m pytest tests/unit/test_context_builder.py::test_build_memory_context_with_facts -v
```

### Validazione Incrementale
```bash
# Analizza file modificati e esegue solo test rilevanti
python apps/backend-rag/scripts/validate_tests.py
```

## Commit Incrementali

**Best Practice: Commit Piccoli e Frequenti**

Invece di:
```bash
# ❌ BAD: Un grande commit con tutto
git add .
git commit -m "feat: add feature X, fix bug Y, refactor Z"
```

Fai:
```bash
# ✅ GOOD: Commit incrementali
git add file1.py
git commit -m "fix: restore build_memory_context method"

git add file2.py
git commit -m "feat: add build_backend_services_context"

git add file3.py
git commit -m "refactor: update combine_contexts logic"
```

**Vantaggi:**
- Ogni commit è testabile
- Più facile identificare problemi
- History più pulita
- Rollback più semplice

## Skip Hooks (Solo Emergenze)

⚠️ **Usa solo in emergenze!**

```bash
# Skip pre-commit hooks
git commit --no-verify -m "Emergency commit"

# Skip pre-push hooks
git push --no-verify origin main
```

**Quando è accettabile:**
- Hotfix critico per produzione
- Fix di sicurezza urgente
- Situazioni dove il tempo è critico

**Quando NON è accettabile:**
- Feature normale
- Refactoring
- "Non ho tempo di fixare i test"

## Troubleshooting

### Test Falliscono Localmente ma Passano su CI

**Possibili cause:**
1. **Differenze di ambiente:**
   - Verifica versioni Python: `python --version`
   - Verifica dipendenze: `pip list`

2. **Variabili d'ambiente:**
   - Verifica `.env` locale
   - CI usa variabili diverse

3. **Cache:**
   ```bash
   # Pulisci cache pytest
   cd apps/backend-rag
   rm -rf .pytest_cache
   python -m pytest tests/unit/ -v
   ```

### Test Passano Localmente ma Falliscono su CI

**Possibili cause:**
1. **Codice incompleto committato:**
   - Verifica che tutti i file siano committati
   - Verifica che non ci siano modifiche non committate

2. **Commit testato diverso da quello pushato:**
   - Verifica: `git log --oneline -5`
   - Assicurati di aver pushato il commit giusto

3. **Differenze tra locale e CI:**
   - Verifica che il codice sia completo prima del push
   - Usa `git diff` per vedere cosa stai pushato

## Automazione

### Pre-Push Hook

Il hook pre-push esegue automaticamente:
- Backend unit tests (solo se file Python modificati)
- Blocca il push se i test falliscono

**Configurazione:** `.pre-commit-config.yaml`

### Pre-Commit Hook

Il hook pre-commit esegue automaticamente:
- Linting (Ruff)
- Formatting
- Security checks

**Configurazione:** `.pre-commit-config.yaml`

## Automated Testing Pipeline

Dopo il push, la pipeline di testing automatizzato esegue:
1. **Test Job:**
   - Installa dipendenze
   - Esegue tutti i test unitari
   - Genera coverage report

2. **Deploy Job (solo se test passano):**
   - Deploy a Fly.io
   - Health check
   - Notifica risultato

**Se i test falliscono su CI:**
- Il deploy viene bloccato
- Ricevi notifica dell'errore
- Fix i test e riprova

## Best Practices

1. ✅ **Testa prima di commitare**
2. ✅ **Commit incrementali**
3. ✅ **Verifica che i test passino prima del push**
4. ✅ **Usa validazione manuale se necessario**
5. ✅ **Non skippare gli hook a meno di emergenze**
6. ✅ **Mantieni i test veloci (< 2 minuti)**
7. ✅ **Aggiorna i test quando modifichi il codice**

## Script Disponibili

- `scripts/validate_backend_tests.sh` - Validazione manuale
- `apps/backend-rag/scripts/validate_tests.py` - Validazione incrementale
- `npm run validate:backend` - Validazione veloce
- `npm run validate:backend:full` - Validazione completa

## Domande Frequenti

**Q: Perché i test vengono eseguiti due volte (pre-push e CI)?**
A: Pre-push cattura problemi prima, CI verifica in ambiente pulito.

**Q: Posso skippare i test se ho fretta?**
A: Solo in emergenze. In produzione, i test sono essenziali.

**Q: I test sono troppo lenti, cosa posso fare?**
A: Usa `--fast` per solo unit tests, o `validate_tests.py` per test incrementali.

**Q: Come faccio a vedere solo i test rilevanti?**
A: Usa `python apps/backend-rag/scripts/validate_tests.py` per test incrementali.
