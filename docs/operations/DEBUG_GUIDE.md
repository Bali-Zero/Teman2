# Debug Guide: Conversation Memory Issue

## 🔍 Problema

Zantara non ricorda informazioni fornite 1-2 turni prima nella stessa conversazione.

**Test Case**:
- Turn 1: "Mi chiamo Marco e sono di Milano"
- Turn 2: "Come mi chiamo?"
- Expected: "Ti chiami Marco, e sei di Milano!"

## 📋 Checklist Debug

### 1. Verificare Salvataggio Frontend

```bash
# Controlla se le conversazioni vengono salvate
python apps/backend-rag/scripts/check_frontend_save.py
```

**Cosa verificare**:
- ✅ Le conversazioni vengono salvate dopo ogni messaggio?
- ✅ Il `session_id` viene passato correttamente?
- ✅ Il `conversation_id` viene restituito e memorizzato?
- ✅ I messaggi contengono "Marco" e "Milano"?

### 2. Eseguire Test Debug con Logging

```bash
# Esegui test debug con logging dettagliato
cd apps/backend-rag
bash scripts/run_debug_tests.sh
```

Oppure manualmente:

```bash
pytest tests/integration/test_conversation_memory_debug.py \
    -v -s \
    --log-cli-level=DEBUG \
    --log-cli-format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

**Cosa verificare nei log**:
- ✅ Conversation history viene recuperata dal database?
- ✅ Entity extraction estrae "Marco" e "Milano"?
- ✅ Conversation history viene passata a `reason_with_gemini`?
- ✅ Le entità estratte vengono aggiunte a `user_memory_facts`?
- ✅ Il prompt contiene "CONVERSATION HISTORY"?
- ✅ Il prompt contiene "Marco" e "Milano"?

### 3. Verificare Flusso Frontend → Backend

#### Frontend (`apps/mouth/src/hooks/useChat.ts`)

**Verificare**:
1. `sessionId` viene generato e mantenuto?
2. `saveConversation` viene chiamato dopo ogni messaggio?
3. `conversation_id` viene restituito e memorizzato?
4. `conversation_id` viene passato nelle query successive?

**Log da cercare nel browser console**:
```
[DEBUG] Saving conversation with X messages, sessionId: ...
[DEBUG] Conversation saved successfully (X messages)
```

#### Backend (`apps/backend-rag/backend/app/routers/oracle_universal.py`)

**Verificare**:
1. `conversation_id` o `session_id` arrivano nella richiesta?
2. `get_conversation_history_for_query` viene chiamato?
3. La history viene recuperata correttamente?
4. `extract_entities_from_history` estrae le entità?
5. Le entità vengono aggiunte a `user_memory_facts`?
6. `conversation_history` viene passato a `reason_with_gemini`?

**Log da cercare**:
```
🔍 [DEBUG] Request details - user_email: ..., conversation_id: ..., session_id: ...
💬 [DEBUG] Conversation History: Retrieved X messages
🔍 [DEBUG] Extracting entities from X messages...
🔍 [DEBUG] Added name fact: ...
🔍 [DEBUG] Added city fact: ...
💬 Added X messages (Y user turns) from conversation history
```

### 4. Verificare reason_with_gemini

**Verificare** (`reason_with_gemini`):
1. `conversation_history` viene ricevuto?
2. Il `conversation_context` viene costruito correttamente?
3. Il prompt contiene la conversation history?
4. Il prompt contiene le entità estratte?

**Log da cercare**:
```
💬 Added X messages (Y user turns) from conversation history
💬 Conversation context preview: ...
```

### 5. Punti Critici da Verificare

#### Punto 1: Frontend non passa conversation_id
**Sintomo**: `conversation_id` è `None` nelle richieste
**Fix**: Modificare `useChat.ts` per passare `conversation_id` nelle query

#### Punto 2: Conversation history non recuperata
**Sintomo**: `get_conversation_history_for_query` ritorna lista vuota
**Fix**: Verificare che `conversation_id`/`session_id` siano corretti nel database

#### Punto 3: Entity extraction non funziona
**Sintomo**: Entità estratte sono `None`
**Fix**: Verificare pattern regex in `extract_entities_from_history`

#### Punto 4: Conversation history non passata a LLM
**Sintomo**: `reason_with_gemini` non riceve `conversation_history`
**Fix**: Verificare che `conversation_history` sia passato correttamente

#### Punto 5: Entità non aggiunte a memory facts
**Sintomo**: `user_memory_facts` non contiene entità estratte
**Fix**: Verificare che `entity_facts` vengano aggiunti a `user_memory_facts`

## 🔧 Script di Debug

### Script 1: Verifica Database
```bash
python apps/backend-rag/scripts/check_frontend_save.py
```

### Script 2: Test Debug
```bash
bash apps/backend-rag/scripts/run_debug_tests.sh
```

### Script 3: Test Specifico
```bash
pytest tests/integration/test_conversation_memory_debug.py::TestConversationMemoryDebug::test_debug_hybrid_oracle_query_flow -v -s --log-cli-level=DEBUG
```

## 📊 Log Analysis

### Log Pattern da Cercare

1. **Conversation Save**:
   ```
   [DEBUG] Saving conversation with X messages, sessionId: ...
   ```

2. **Conversation Retrieval**:
   ```
   📚 Retrieved X messages from conversation history
   ```

3. **Entity Extraction**:
   ```
   🔍 Extracted entities: name=Marco, city=Milano, budget=None, preferences=[]
   ```

4. **Memory Facts**:
   ```
   🔍 [DEBUG] Added name fact: User name: Marco
   🔍 [DEBUG] Added city fact: User city: Milano
   ```

5. **LLM Context**:
   ```
   💬 Added X messages (Y user turns) from conversation history
   ```

## 🐛 Problemi Comuni

### Problema 1: Frontend non passa conversation_id
**Sintomo**: `request.conversation_id` è sempre `None`
**Soluzione**: Modificare `useChat.ts` per passare `conversation_id` da `saveConversation` response

### Problema 2: Session ID non corrisponde
**Sintomo**: Conversation history non trovata anche se esiste
**Soluzione**: Verificare che `session_id` sia lo stesso tra save e query

### Problema 3: Entity extraction fallisce
**Sintomo**: Entità estratte sono `None`
**Soluzione**: Verificare pattern regex e formato messaggi

### Problema 4: Context window troppo piccolo
**Sintomo**: Solo ultimi 2-3 messaggi inclusi
**Soluzione**: Verificare logica di trimming in `reason_with_gemini`

## ✅ Verifica Finale

Dopo aver eseguito i fix, verificare:

1. ✅ Conversation viene salvata dopo ogni messaggio
2. ✅ `conversation_id` viene passato nelle query successive
3. ✅ Conversation history viene recuperata correttamente
4. ✅ Entity extraction estrae nome e città
5. ✅ Entità vengono aggiunte a memory facts
6. ✅ Conversation history viene passata a LLM
7. ✅ LLM risponde con informazioni dalla history

## 📝 Note

- I test debug hanno logging estensivo per isolare il problema
- Usare `-s` flag per vedere print statements
- Usare `--log-cli-level=DEBUG` per vedere tutti i log
- Verificare sia frontend che backend logs

