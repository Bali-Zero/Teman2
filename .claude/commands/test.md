# Test - Run Pytest con Coverage

Esegue i test pytest con report coverage.

## Argomenti

- `$ARGUMENTS`: Path opzionale per filtrare i test (es. `tests/unit/`, `tests/api/test_auth.py`)

## Istruzioni

1. **Setup ambiente**:
   ```bash
   cd apps/backend-rag
   ```

2. **Esegui test**:

   Se `$ARGUMENTS` specificato:
   ```bash
   pytest $ARGUMENTS -v --tb=short -x
   ```

   Se nessun argomento (test completi):
   ```bash
   pytest tests/unit tests/api -v --tb=short --cov=backend --cov-report=term-missing --cov-fail-under=80
   ```

3. **Analisi fallimenti**:
   - Per ogni test fallito, mostra:
     - Nome test e file
     - Assertion error
     - Suggerimento fix

4. **Coverage report**:
   - Mostra file con coverage < 80%
   - Suggerisci quali test aggiungere

## Shortcuts comuni

| Comando | Descrizione |
|---------|-------------|
| `/test` | Tutti i test unit + api |
| `/test tests/unit/` | Solo unit tests |
| `/test tests/api/` | Solo API tests |
| `/test tests/integration/` | Solo integration tests |
| `/test -k auth` | Test che contengono "auth" |
| `/test tests/unit/test_gemini_service.py` | File specifico |

## Output atteso

```
## Test Results

### Summary
- Total: 150 tests
- Passed: 148
- Failed: 2
- Duration: 45s

### Failed Tests
1. `test_auth_login_invalid_pin` (tests/api/test_auth.py:42)
   - AssertionError: Expected 401, got 400
   - Fix: Controllare validazione PIN in auth.py

2. `test_rag_empty_query` (tests/unit/test_rag.py:88)
   - ValueError: Query cannot be empty
   - Fix: Aggiungere validazione input

### Coverage
- Overall: 82%
- Files under 80%:
  - backend/services/gemini_service.py: 65%
  - backend/app/routers/agents.py: 72%

### Suggerimenti
- Aggiungere test per gemini_service edge cases
- Mockare meglio le chiamate API in agents router
```
