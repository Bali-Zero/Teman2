# WINDSURF PATCH — Nuzantara Backend Security & Reliability Fixes

**Data:** 2026-03-26
**Autore:** Claude Code (Air)
**Priorità:** ALTA — fix sequenziali, non parallelizzare
**Branch target:** `main`
**Working dir:** `apps/backend-rag/`

---

## REGOLE OBBLIGATORIE PER WINDSURF

1. **NON toccare questi file:** `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`, `dependencies.py`, `app_factory.py`, `service_initializer.py`
2. **NON refactorare** — solo i fix descritti, niente "miglioramenti" non richiesti
3. **NON rimuovere import** esistenti — solo aggiungerne se mancano
4. **Dopo ogni fix:** verifica sintassi con `python -m py_compile <file>`
5. **Test import chain dopo tutti i fix:** `PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"`
6. **Virtualenv:** `source venv/bin/activate` (non `.venv`)

---

## FIX 1 — SECURITY: Aggiungere auth a GET /api/whatsapp/conversations

**File:** `backend/app/routers/whatsapp_conversations.py`
**Priorità:** CRITICA
**Problema:** `GET /api/whatsapp/conversations` (linea 48) espone tutta la cronologia conversazioni senza autenticazione. `GET /conversations` e `GET /messages/{phone}` sono pubblici. Solo `POST /send` ha auth.

**Fix:**

```python
# PRIMA (linea 48-54) — NO AUTH:
@router.get("/conversations")
async def get_whatsapp_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Pool | None = Depends(get_optional_database_pool),
) -> Any:

# DOPO — con auth gate:
@router.get("/conversations")
async def get_whatsapp_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Pool | None = Depends(get_optional_database_pool),
    current_user: dict = Depends(get_current_user),  # noqa: ARG001 — auth gate
) -> Any:
```

Stesso fix per `GET /messages/{phone}` — trova l'handler corrispondente e aggiungi `current_user: dict = Depends(get_current_user),` come ultimo parametro Depends.

**Import già presente:** `from backend.app.dependencies import get_current_user` è già importato a linea 20. Niente da aggiungere.

---

## FIX 2 — SECURITY: Rimuovere debug endpoint pubblico che espone documenti legali

**File:** cerca con `grep -rn "parent-documents-public" backend/`
**Priorità:** CRITICA
**Problema:** Endpoint marcato "PUBLIC endpoint for testing - NO AUTH" che espone documenti legali interni.

**Fix:** Aggiungi `current_user: dict = Depends(get_current_user)` come parametro, oppure se è puro debug/test, **elimina l'endpoint completamente** (preferito).

Verifica prima: `grep -rn "parent-documents-public\|debug.*parent" backend/app/routers/`

---

## FIX 3 — RELIABILITY: Cache invalidation su tutte le mutazioni CRM

**File:** `backend/app/routers/crm_clients.py`
**Priorità:** ALTA
**Problema:** `invalidate_cache("zantara:crm_clients_stats:*")` è chiamata solo su create (linea 328), update (linea 653), e delete (linea 721) del router principale. Manca nei router correlati.

**Fix — verifica e aggiungi dove manca:**

```python
# Pattern corretto (già presente in crm_clients.py):
await invalidate_cache("zantara:crm_clients_stats:*")
```

**Cerca nei router CRM correlati** dove si fanno mutazioni senza invalidazione:

```bash
grep -rn "def.*update\|def.*create\|def.*delete\|def.*patch" \
  backend/app/routers/crm_*.py \
  backend/app/routers/practices*.py \
  | grep -v "test_\|#"
```

Per ogni endpoint POST/PUT/DELETE/PATCH nei file `crm_*.py` e `practices*.py` che non ha `await invalidate_cache(...)`, aggiungila prima del `return`.

Pattern namespace da invalidare:

- Dopo mutazioni clients: `"zantara:crm_clients_stats:*"`
- Dopo mutazioni practices: `"zantara:crm_practices:*"` e `"zantara:crm_clients_stats:*"`

**Import già presente** in `crm_clients.py` linea 27: `from backend.core.cache import cached, invalidate_cache`
Se non presente in altri file: aggiungere `from backend.core.cache import invalidate_cache`

---

## FIX 4 — RELIABILITY: Error logging con exc_info nei catch generici

**File:** `backend/app/utils/error_handlers.py`
**Priorità:** MEDIA
**Problema:** Il fallback generico logga l'errore ma non la stacktrace completa.

**Fix:**

```python
# PRIMA (ultima riga della funzione handle_database_error):
logger.error(f"Unexpected error: {e}", exc_info=True)
return HTTPException(status_code=500, detail="Internal server error")

# DOPO — aggiungere error_type nel detail per debug più rapido:
logger.error(f"Unexpected error [{type(e).__name__}]: {e}", exc_info=True)
return HTTPException(status_code=500, detail=f"Internal server error")
```

(Il detail pubblico rimane generico per sicurezza, ma il log interno è arricchito.)

---

## FIX 5 — RELIABILITY: Admin email list — documentare la procedura di aggiornamento

**File:** `backend/app/utils/crm_utils.py`
**Priorità:** BASSA
**Problema:** Le email admin sono hardcoded (linee ~9-30). Non è un security bug attivo (richiederebbe comunque auth per accedere al CRM), ma cambiare accesso richiede deploy.

**Fix — NON spostare in DB** (over-engineering per ora). Aggiungere solo un commento chiaro:

```python
# PRIMA:
CRM_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    ...
}

# DOPO — aggiungi commento sopra ogni set:
# To add/remove admin access: edit this set + deploy.
# For DB-driven RBAC, see GitHub issue #TODO.
CRM_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    ...
}
```

---

## FIX 6 — RELIABILITY: trusted_tools sincronizzazione streaming/non-streaming

**File:** `backend/services/rag/agentic/reasoning.py`
**Priorità:** MEDIA
**Problema:** I due set `trusted_tool_names` (non-streaming linea ~564, streaming linea ~1326) sono già sincronizzati (stesso contenuto). **Verificare** che rimangano sincronizzati estraendo in una costante condivisa.

**Fix:**

```python
# In cima al file reasoning.py, dopo gli import, aggiungi la costante:
# Trusted tools bypass evidence scoring — tool output IS the evidence
_TRUSTED_TOOL_NAMES: frozenset[str] = frozenset({
    "calculator",
    "get_pricing",
    "team_knowledge",
    "timesheet",
    "vector_search",
})

# Poi in entrambi i punti dove appare trusted_tool_names = {...}, sostituisci con:
trusted_tool_names = _TRUSTED_TOOL_NAMES
```

Questo garantisce che i due path (streaming e non-streaming) usino sempre lo stesso set.

---

## VERIFICA FINALE

Dopo tutti i fix, eseguire in ordine:

```bash
cd apps/backend-rag
source venv/bin/activate

# 1. Sintassi
python -m py_compile backend/app/routers/whatsapp_conversations.py
python -m py_compile backend/app/routers/crm_clients.py
python -m py_compile backend/app/utils/error_handlers.py
python -m py_compile backend/app/utils/crm_utils.py
python -m py_compile backend/services/rag/agentic/reasoning.py

# 2. Import chain critica
PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"

# 3. Test core
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=short -x

# 4. Se tutto passa: commit
git add -p  # staged interattivo, NON git add -A
git commit -m "fix(security+reliability): auth on whatsapp endpoints, cache invalidation, trusted_tools constant"
```

---

## NOTE IMPORTANTI

- **FIX 1 e FIX 2** sono i più critici (security) — farli per primi
- **FIX 6** è cosmetic/preventivo — farlo per ultimo
- **NON** cambiare la logica interna degli endpoint, solo aggiungere `Depends(get_current_user)`
- **NON** rimuovere il pattern `current_user: dict = Depends(get_current_user),  # noqa: ARG001` — il `# noqa` è intenzionale (parametro usato solo come auth gate)
- Se un file non esiste o il pattern non corrisponde: **segnalare** invece di inventare fix
