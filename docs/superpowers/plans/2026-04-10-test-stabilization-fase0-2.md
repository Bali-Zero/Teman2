# Test Stabilization Fase 0-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendere affidabile la misurazione dei test — source of truth unica, CI realmente bloccante, Guardian/Sentinel che segnala errori reali.

**Architecture:** Fix chirurgici su file di configurazione esistenti. Nessuna nuova feature, nessun nuovo servizio. L'ordine è critico: prima unificare il test tree (Task 1), poi correggere CI (Task 2), poi Guardian (Task 3). Non invertire.

**Tech Stack:** Python/pytest, GitHub Actions, bash, Node/Vitest, Playwright

---

## Context — Stato Verificato

Prima di toccare qualsiasi file, sappi cosa è rotto e perché:

| Problema | File | Riga | Effetto |
|----------|------|------|---------|
| `pytest.ini` e `pyproject.toml` puntano a `tests/` (252 file) ma CI usa `backend/tests/` (572 file) | `apps/backend-rag/pytest.ini:7`, `apps/backend-rag/pyproject.toml:233` | — | Coverage locale ≠ CI coverage |
| CI genera `coverage-unit.xml` ma Codecov cerca `coverage.xml` | `.github/workflows/tests.yml:90,103` | — | Codecov riceve sempre file vuoto |
| Coverage gate usa `\|\| echo` — non fallisce mai | `.github/workflows/tests.yml:98` | — | Gate decorativo |
| Frontend CI chiama `npm run test:coverage:check` — script inesistente | `.github/workflows/tests.yml:187`, `apps/mouth/package.json` | — | Job frontend sempre broken |
| `apps/backend-rag/package.json` referenzia `scripts/test_automation/*` — directory inesistente | `apps/backend-rag/package.json:11-14` | — | `npm run test:*` sempre broken |
| `apps/mouth/package.json` ha `test:smoke` → `playwright.smoke.config.ts` inesistente | `apps/mouth/package.json:18` | — | `npm run test:smoke` rompe subito |
| `scripts/auto_sentinel.sh` hardcoda path Air `/Users/antonellosiano/Projects/nuzantara` | `scripts/auto_sentinel.sh:4` | — | Non funziona su Pro |
| `watchdog.py` usa `.venv` ma Air usa `venv` | `apps/evaluator/core_guardian/watchdog.py:64` | — | Watchdog non trova Python su Air |
| Guardian state file `core_guardian.last.json` è fermo al 2026-03-27 con `status: failed` | `.agent/decisions/state/core_guardian.last.json` | — | Automazione morta su Pro |

**Tree canonico scelto:** `apps/backend-rag/backend/tests/` (572 file, è quello che CI già usa con `PYTHONPATH=. pytest backend/tests/`). Il tree esterno `apps/backend-rag/tests/` (252 file) diventa legacy.

---

## Task 1: Unificare il test tree backend

**Files:**
- Modify: `apps/backend-rag/pytest.ini:7`
- Modify: `apps/backend-rag/pyproject.toml:233`

### Perché questo è il Task 1

Se pytest.ini punta a `tests/` ma CI lancia `backend/tests/`, ogni numero di coverage locale è diverso da CI. Finché non c'è un albero canonico, tutti i fix successivi misurano cose diverse.

- [ ] **Step 1: Verifica quanti test raccoglie pytest oggi con la config attuale**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest --collect-only -q 2>/dev/null | tail -5
```

Expected: conta test dall'albero `tests/` (quello esterno, ~252 file). Nota il numero.

- [ ] **Step 2: Verifica quanti test raccoglie il tree canonico**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/ --collect-only -q 2>/dev/null | tail -5
```

Expected: numero più alto (~572 file). Nota il numero. Questa sarà la nuova baseline.

- [ ] **Step 3: Aggiorna pytest.ini per puntare al tree canonico**

In `apps/backend-rag/pytest.ini`, cambia riga 7:

```ini
# Prima:
testpaths = tests

# Dopo:
testpaths = backend/tests
```

- [ ] **Step 4: Aggiorna pyproject.toml**

In `apps/backend-rag/pyproject.toml`, cambia riga 233:

```toml
# Prima:
testpaths = ["tests"]

# Dopo:
testpaths = ["backend/tests"]
```

- [ ] **Step 5: Verifica che pytest senza argomenti ora usi il tree canonico**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest --collect-only -q 2>/dev/null | tail -5
```

Expected: stesso numero del Step 2 (tree canonico). Se il numero è uguale, il fix è corretto.

- [ ] **Step 6: Verifica import chain (non rompere nulla)**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
```

Expected: `✅ Import chain OK`

- [ ] **Step 7: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/pytest.ini apps/backend-rag/pyproject.toml
git commit -m "fix(tests): unify backend test tree to backend/tests/ (canonical)

pytest.ini and pyproject.toml were pointing to outer tests/ tree (252 files)
while CI was running backend/tests/ (572 files). Coverage numbers were
therefore different between local and CI. Now both use backend/tests/.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Fix CI — tre bug indipendenti

**Files:**
- Modify: `.github/workflows/tests.yml` (righe 90, 98, 103, 187)
- Modify: `apps/mouth/package.json` (aggiungere script)
- Modify: `apps/backend-rag/package.json` (rimuovere script fantasma)
- Modify: `apps/mouth/package.json` (rimuovere o fixare test:smoke)

### 2A: Fix coverage filename mismatch (Codecov)

- [ ] **Step 1: Verifica lo stato attuale**

```bash
grep -n "coverage" /Users/nuzantara/Desktop/nuzantara/.github/workflows/tests.yml | head -20
```

Expected: vedi riga 90 con `coverage-unit.xml` e riga 103 con `coverage.xml`.

- [ ] **Step 2: Fix — allinea il filename**

In `.github/workflows/tests.yml`, cambia riga 90:

```yaml
# Prima:
--cov-report=xml:coverage-unit.xml \

# Dopo:
--cov-report=xml:coverage.xml \
```

E aggiorna anche l'artifact upload alla riga 114:

```yaml
# Prima:
apps/backend-rag/coverage-unit.xml

# Dopo:
apps/backend-rag/coverage.xml
```

### 2B: Fix coverage gate (rendere bloccante)

- [ ] **Step 3: Fix il gate — rimuovi `|| echo`**

In `.github/workflows/tests.yml`, cambia il blocco del "Check coverage threshold" (riga 95-98):

```yaml
# Prima:
      - name: Check coverage threshold
        run: |
          cd apps/backend-rag
          PYTHONPATH=. coverage report --fail-under=40 || echo "⚠️ Coverage below 40% — CRITICAL: check report"

# Dopo:
      - name: Check coverage threshold
        run: |
          cd apps/backend-rag
          PYTHONPATH=. coverage report --fail-under=40
```

### 2C: Fix frontend `test:coverage:check` mancante

- [ ] **Step 4: Aggiungi lo script mancante in `apps/mouth/package.json`**

Aggiungi `test:coverage:check` nelle scripts, dopo `test:ci`:

```json
"test:coverage:check": "vitest --run --coverage --reporter=verbose && node -e \"const r=require('./coverage/coverage-summary.json');const s=r.total.statements.pct;if(s<20){console.error('Coverage '+s+'% below 20% threshold');process.exit(1)}else{console.log('Coverage '+s+'% OK')}\"",
```

Nota: 20% è il threshold realistico per frontend ora a ~11%. È il minimo non-cosmetico che la suite attuale può raggiungere.

- [ ] **Step 5: Testa lo script localmente**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
npm run test:ci 2>/dev/null | tail -10
```

Expected: vitest gira e produce `coverage/coverage-summary.json`. Se non esiste ancora, lo crea.

### 2D: Fix `test:smoke` — rimuovere o creare il config

- [ ] **Step 6: Rimuovi `test:smoke` da `apps/mouth/package.json`** (il config non esiste, è meglio rimuovere che lasciare rotto)

In `apps/mouth/package.json`, rimuovi la riga:

```json
"test:smoke": "playwright test -c playwright.smoke.config.ts",
```

Se invece vuoi tenere il riferimento per il futuro, crea un config minimo:

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/mouth/playwright.smoke.config.ts << 'EOF'
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.smoke.spec.ts',
  use: {
    baseURL: process.env.BASE_URL || 'https://kita.balizero.com',
  },
  retries: 1,
  timeout: 30000,
});
EOF
```

Scegli l'opzione rimuovere (più sicura, non introduce file vuoto).

### 2E: Fix `apps/backend-rag/package.json` — rimuovi script fantasma

- [ ] **Step 7: Rimuovi i 4 script che puntano a directory inesistente**

In `apps/backend-rag/package.json`, rimuovi le righe 11-14:

```json
// Rimuovi queste 4 righe:
"test:automation": "cd ../.. && bash scripts/test_automation/test_master.sh 90",
"test:quality": "cd ../.. && python3 scripts/test_automation/test_quality_checker.py apps/backend-rag/tests/unit",
"test:coverage": "cd ../.. && python3 scripts/test_automation/coverage_monitor.py 90",
"test:generate": "cd ../.. && python3 scripts/test_automation/test_generator.py"
```

Il risultato deve essere:

```json
{
  "name": "@nuzantara/backend-rag",
  "version": "5.2.0",
  "private": true,
  "description": "Python FastAPI RAG backend with Qdrant and re-ranker (AMD64)",
  "scripts": {
    "start": "cd backend && uvicorn app.main_cloud:app --host 0.0.0.0 --port 8000",
    "dev": "cd backend && uvicorn app.main_cloud:app --reload",
    "deploy": "gcloud run deploy zantara-rag-backend --source backend --platform linux/amd64",
    "test": "cd backend && pytest"
  },
  "engines": {
    "python": ">=3.11"
  },
  "dependencies": {}
}
```

- [ ] **Step 8: Verifica che CI sia coerente — nessun riferimento a `test:automation` o simili**

```bash
grep -rn "test:automation\|test:quality\|test:coverage\|test:generate" /Users/nuzantara/Desktop/nuzantara/.github/
```

Expected: nessun output. Se c'è qualche match, va rimosso anche lì.

- [ ] **Step 9: Commit tutto il CI fix**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add .github/workflows/tests.yml apps/mouth/package.json apps/backend-rag/package.json
git commit -m "fix(ci): fix 4 broken CI issues — coverage filename, gate, missing scripts

- Align coverage filename: coverage-unit.xml → coverage.xml (Codecov was
  uploading empty file)
- Make coverage gate actually fail: remove '|| echo' fallback
- Add test:coverage:check script to mouth (was called in CI, didn't exist)
- Remove phantom test:automation/quality/coverage/generate scripts from
  backend-rag package.json (scripts/test_automation/ dir doesn't exist)
- Remove test:smoke from mouth (playwright.smoke.config.ts doesn't exist)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Fix Guardian/Sentinel

**Files:**
- Modify: `apps/evaluator/core_guardian/watchdog.py:64`
- Modify: `scripts/auto_sentinel.sh:4`
- Modify: `scripts/coverage_trend.py` (verifica path)

### 3A: Fix watchdog.py — venv path dinamico

Il problema: riga 64 hardcoda `.venv` ma Air usa `venv`.

- [ ] **Step 1: Leggi il contesto attorno alla riga 64**

```bash
sed -n '60,80p' /Users/nuzantara/Desktop/nuzantara/apps/evaluator/core_guardian/watchdog.py
```

- [ ] **Step 2: Fix — rileva automaticamente quale venv esiste**

In `watchdog.py`, sostituisci la riga 64:

```python
# Prima:
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

# Dopo:
def _find_venv_python(backend_dir: Path) -> Path:
    """Trova il Python del venv, compatibile con Pro (.venv) e Air (venv)."""
    for venv_name in (".venv", "venv"):
        candidate = backend_dir / venv_name / "bin" / "python"
        if candidate.exists():
            return candidate
    # Fallback: system python (non ideale ma non crashare)
    return Path(sys.executable)

VENV_PYTHON = _find_venv_python(BACKEND_DIR)
```

- [ ] **Step 3: Verifica che il file sia sintatticamente valido**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 -c "import ast; ast.parse(open('apps/evaluator/core_guardian/watchdog.py').read()); print('✅ Syntax OK')"
```

Expected: `✅ Syntax OK`

### 3B: Fix auto_sentinel.sh — path dinamico

- [ ] **Step 4: Fix il path hardcoded**

In `scripts/auto_sentinel.sh`, sostituisci le prime 6 righe:

```bash
#!/bin/bash

# Configuration — path dinamico, compatibile con Pro e Air
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/sentinel_nightly.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")
```

Così funziona su qualsiasi macchina indipendentemente dal path assoluto.

- [ ] **Step 5: Verifica il fix — il path deve puntare alla root del progetto**

```bash
cd /Users/nuzantara/Desktop/nuzantara
bash -c 'SCRIPT_DIR="$(cd "$(dirname "scripts/auto_sentinel.sh")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"; echo "PROJECT_DIR=$PROJECT_DIR"'
```

Expected: `PROJECT_DIR=/Users/nuzantara/Desktop/nuzantara` (o equivalente su Air).

### 3C: Fix coverage_trend.py — verifica path

- [ ] **Step 6: Leggi la configurazione di path in coverage_trend.py**

```bash
head -50 /Users/nuzantara/Desktop/nuzantara/scripts/coverage_trend.py
```

Expected: cerca se usa path hardcoded o `Path(__file__)`. Se usa path assoluti Air-only, fixare come watchdog.py.

- [ ] **Step 7: Se ci sono path hardcoded Air, fixarli con la stessa logica dinamica**

Se trovi righe tipo `/Users/antonellosiano/...`, sostituirle con path dinamici basati su `Path(__file__).resolve().parent.parent`.

### 3D: Verifica state files — reset manuale

- [ ] **Step 8: Resetta il state file core_guardian.last.json su Pro**

Il file attuale mostra `status: failed` dal 2026-03-27 per un errore git. Va resettato per permettere al prossimo run di funzionare:

```bash
cat > /Users/nuzantara/Desktop/nuzantara/.agent/decisions/state/core_guardian.last.json << 'EOF'
{
  "status": "reset",
  "timestamp": "2026-04-10T00:00:00+00:00",
  "note": "Manual reset after path unification. Next run will establish new baseline.",
  "passed": 0,
  "failed": 0,
  "errors": 0
}
EOF
```

- [ ] **Step 9: Aggiorna coverage_trend.last.json (fermo al 2026-03-26)**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/.agent/decisions/state/coverage_trend.last.json << 'EOF'
{
  "status": "reset",
  "timestamp": "2026-04-10T00:00:00+00:00",
  "note": "Manual reset after test tree unification. Coverage baseline: 59.30% (backend/tests/).",
  "detail": "59.30%"
}
EOF
```

- [ ] **Step 10: Commit Guardian fixes**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/evaluator/core_guardian/watchdog.py scripts/auto_sentinel.sh scripts/coverage_trend.py .agent/decisions/state/
git commit -m "fix(guardian): fix venv detection, sentinel path, reset stale state

- watchdog.py: detect .venv vs venv dynamically (Pro vs Air compat)
- auto_sentinel.sh: replace hardcoded Air path with script-relative path
- coverage_trend.py: fix any hardcoded paths if present
- Reset core_guardian.last.json (stuck at 2026-03-27 failed state)
- Reset coverage_trend.last.json (stale at 2026-03-26)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Smoke test end-to-end (verifica che tutto funzioni)

**Files:** nessun file nuovo — solo verifica

- [ ] **Step 1: Lancia i test backend con la nuova config**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=short
```

Expected: PASSED (questi test erano già verdi prima)

- [ ] **Step 2: Verifica coverage con il nuovo path**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=term-missing -q --tb=no -x 2>/dev/null | tail -5
```

Expected: percentuale coverage visibile, nessun "no data to report"

- [ ] **Step 3: Verifica import chain invariata**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
```

Expected: `✅ Import chain OK`

- [ ] **Step 4: Verifica che watchdog.py si avvii senza crash**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 -c "
import sys; sys.path.insert(0, '.')
# Solo verifica import e path resolution, non eseguire il watchdog
import apps.evaluator.core_guardian.watchdog as w
print(f'PROJECT_ROOT: {w.PROJECT_ROOT}')
print(f'VENV_PYTHON: {w.VENV_PYTHON}')
print(f'VENV exists: {w.VENV_PYTHON.exists()}')
" 2>/dev/null || python3 apps/evaluator/core_guardian/watchdog.py --dry-run 2>/dev/null | head -5
```

Expected: path sensati, nessun `sys.exit(1)`

- [ ] **Step 5: Verifica auto_sentinel.sh sintassi**

```bash
bash -n /Users/nuzantara/Desktop/nuzantara/scripts/auto_sentinel.sh && echo "✅ Shell syntax OK"
```

Expected: `✅ Shell syntax OK`

- [ ] **Step 6: Push (NO deploy — solo git push origin)**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git push origin main
```

Nota: il push triggera la CI su GitHub. I job non devono più fallire per i bug corretti in Task 2.

---

## Self-Review

### Spec coverage

| Problema originale | Task che lo risolve |
|---|---|
| Due test tree, pytest.ini punta a quello sbagliato | Task 1 |
| CI genera `coverage-unit.xml` ma Codecov cerca `coverage.xml` | Task 2, Step 2 |
| Coverage gate non fallisce (`\|\| echo`) | Task 2, Step 3 |
| `test:coverage:check` mancante in frontend | Task 2, Step 4 |
| Script fantasma `test:automation` ecc. in backend-rag | Task 2, Step 7 |
| `test:smoke` punta a config inesistente | Task 2, Step 6 |
| `watchdog.py` hardcoda `.venv` (non funziona su Air) | Task 3, Step 2 |
| `auto_sentinel.sh` hardcoda path Air | Task 3, Step 4 |
| Guardian state files fermi/stale | Task 3, Steps 8-9 |
| Verifica end-to-end che nulla sia rotto | Task 4 |

### Placeholder scan
Nessun "TBD", "TODO", "implement later" presente. Tutti i code block hanno contenuto reale.

### Type consistency
Non applicabile — questo piano non introduce nuovi tipi o interfacce.

### Cosa NON fa questo piano (scope boundary)

- Non scrive nuovi test (questo è Fase 3-4)
- Non tocca codice applicativo (router, servizi, componenti)
- Non cambia schema DB o API contracts
- Non fa deploy su Fly.io
- Il tree esterno `apps/backend-rag/tests/` (252 file legacy) NON viene cancellato — viene solo ignorato dalla config. La migrazione/cleanup è lavoro futuro separato.

---

**Piano salvato.** Due opzioni di esecuzione:

**1. Subagent-Driven (consigliato)** — subagent fresco per task, review tra task, iterazione veloce

**2. Inline Execution** — esecuzione nella sessione corrente con checkpoints

**Quale preferisci?**
