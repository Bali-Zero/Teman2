# Debug Findings - Conversation Memory Issue

## ✅ Scoperte Importanti

### 1. Endpoint `/api/agentic-rag/stream` GIÀ Supporta Memory!

**File**: `apps/backend-rag/backend/app/routers/agentic_rag.py`

- ✅ Supporta `conversation_id` e `session_id` nel request model
- ✅ Recupera conversation history tramite `get_conversation_history_for_agentic()`
- ✅ Passa `conversation_history` a `AgenticRAGOrchestrator.stream_query()`

**Codice rilevante**:
```python
# Line 219-227
conversation_history: list[dict] = []
if request.user_id and (request.conversation_id or request.session_id):
    conversation_history = await get_conversation_history_for_agentic(
        conversation_id=request.conversation_id,
        session_id=request.session_id,
        user_id=request.user_id,
        db_pool=db_pool,
    )
```

### 2. `AgenticRAGOrchestrator.stream_query()` GIÀ Usa Conversation History!

**File**: `apps/backend-rag/backend/services/rag/agentic.py`

- ✅ Accetta `conversation_history` come parametro
- ✅ Usa `AdvancedContextWindowManager` per gestire context window
- ✅ **GIÀ ESTRAE ENTITÀ** dalla conversation history!
- ✅ Aggiunge entità estratte a `user_memory_facts`

**Codice rilevante** (line 1275-1293):
```python
# Extract entities from conversation history and add to user context
if history_to_use:
    try:
        from app.routers.oracle_universal import extract_entities_from_history
        extracted_entities = extract_entities_from_history(history_to_use)
        
        # Add extracted entities to user_memory_facts for context
        entity_facts = []
        if extracted_entities.get("name"):
            entity_facts.append(f"User's name is {extracted_entities['name']}")
        if extracted_entities.get("city"):
            entity_facts.append(f"User is from {extracted_entities['city']}")
        # ... etc
```

### 3. Frontend Passa `session_id` Correttamente

**File**: `apps/mouth/src/lib/api.ts`

- ✅ `sendMessageStreaming` accetta `conversationId` (che è il `session_id`)
- ✅ Passa `session_id` nel body della richiesta
- ✅ Log di debug presente: `[DEBUG] Sending message with user_id: ..., session_id: ...`

## 🔍 Problemi Potenziali Identificati

### Problema 1: Frontend Non Passa `conversation_id`

**Situazione**: Il frontend passa solo `session_id`, non `conversation_id`

**Impatto**: 
- Se `conversation_id` è `None`, il backend cerca per `session_id`
- Funziona, ma potrebbe essere meno efficiente

**Fix Necessario**: 
- Opzione A: Frontend passa anche `conversation_id` quando disponibile
- Opzione B: Backend usa solo `session_id` (già implementato)

### Problema 2: `user_id` vs `user_email` Mismatch

**Situazione**: 
- Frontend passa `user_id` (che può essere email o ID)
- Backend cerca conversazioni per `user_email` (email dal JWT)

**Codice rilevante** (`get_conversation_history_for_agentic`, line 88-100):
```python
user_email = user_id  # Assume user_id is email (common case)

# If user_id looks like an ID (numeric), try to get email from team_members
if user_id.isdigit() or (not "@" in user_id):
    # Try to find email...
```

**Impatto**: 
- Se `user_id` non è email, potrebbe non trovare conversazioni
- Il codice cerca di risolvere questo, ma potrebbe fallire

**Fix Necessario**: 
- Verificare che `user_id` passato dal frontend sia sempre email
- Oppure migliorare la logica di conversione `user_id` → `user_email`

### Problema 3: Entity Extraction Potrebbe Non Funzionare

**Situazione**: 
- Entity extraction è implementata
- Ma potrebbe non estrarre correttamente "Marco" e "Milano" da "Mi chiamo Marco e sono di Milano"

**Test da Eseguire**: 
- `test_debug_entity_extraction` per verificare pattern regex

## 📋 Checklist Verifica

### ✅ Già Implementato
- [x] Endpoint supporta `conversation_id` e `session_id`
- [x] Conversation history viene recuperata
- [x] Entity extraction è integrata
- [x] Entità vengono aggiunte a memory facts
- [x] Context window manager gestisce history

### ⚠️ Da Verificare
- [ ] Frontend passa `session_id` correttamente
- [ ] `user_id` è sempre email (non ID numerico)
- [ ] Entity extraction estrae "Marco" e "Milano" correttamente
- [ ] Conversation history viene passata al LLM
- [ ] LLM riceve le entità estratte nel prompt

## 🧪 Test da Eseguire

1. **Test Entity Extraction**:
   ```bash
   pytest tests/integration/test_conversation_memory_debug.py::TestConversationMemoryDebug::test_debug_entity_extraction -v -s
   ```

2. **Test Conversation History Retrieval**:
   ```bash
   pytest tests/integration/test_conversation_memory_debug.py::TestConversationMemoryDebug::test_debug_conversation_history_retrieval -v -s
   ```

3. **Test Full Flow**:
   ```bash
   pytest tests/integration/test_conversation_memory_debug.py::TestConversationMemoryDebug::test_debug_hybrid_oracle_query_flow -v -s --log-cli-level=DEBUG
   ```

## 🎯 Prossimi Passi

1. ✅ Eseguire test di debug per verificare entity extraction
2. ✅ Verificare che conversation history venga recuperata correttamente
3. ⏳ Verificare che `user_id` sia sempre email
4. ⏳ Verificare che frontend passi `session_id` correttamente
5. ⏳ Testare flusso completo end-to-end

## 📝 Note

- Il codice backend **GIÀ** supporta conversation memory!
- Il problema potrebbe essere nel frontend o nella conversione `user_id` → `user_email`
- Entity extraction è già integrata in `AgenticRAGOrchestrator.stream_query()`

