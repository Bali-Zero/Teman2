# Memory Recall Fix - Session Handover

**Date**: 2025-12-30
**Branch**: `auto/prompt-improvement-20251229-0616`
**Status**: DEPLOYED TO PRODUCTION

## Problem

Zantara could not recall client information shared in the same conversation session. When asked "Ti ricordi il cliente di cui abbiamo parlato?", Zantara would search Qdrant (RAG) instead of reading conversation history, resulting in:

```
"Mi dispiace, non ho trovato informazioni verificate sufficienti nei documenti ufficiali..."
```

### Root Cause Analysis

1. **ReAct Loop Override**: The ReAct orchestrator triggered `vector_search` for ALL questions, including recall questions
2. **ABSTAIN Mechanism**: Low RAG scores (0.20) triggered the uncertainty filter, causing Zantara to refuse answering
3. **System Prompt Ignored**: LLM called tools BEFORE processing system prompt guidance about conversation recall

## Solution

Added a **Conversation Recall Gate** that bypasses RAG entirely for recall questions.

### Files Modified

| File | Changes |
|------|---------|
| `backend/services/rag/agentic/orchestrator.py` | Added `RECALL_TRIGGERS`, `_is_conversation_recall_query()`, and Recall Gate early-exit |
| `backend/prompts/zantara_system_prompt.md` | Added CONVERSATION MEMORY section with trigger phrases |
| `backend/services/rag/agentic/prompt_builder.py` | Added CONVERSATION RECALL CHECK as priority 0 |

### Code Changes

#### 1. Recall Triggers (orchestrator.py)
```python
RECALL_TRIGGERS = [
    # Italian
    "ti ricordi", "ricordi quando", "di che parlavamo", "di che cliente",
    "il cliente di cui", "che mi hai detto", "prima hai detto",
    # English
    "do you remember", "remember when", "what did i say", "what did you say",
    "the client we discussed", "earlier you said", "you mentioned before",
    # Indonesian
    "ingat tidak", "kamu ingat", "tadi aku bilang", "sebelumnya",
    "klien yang tadi", "yang kita bahas",
]
```

#### 2. Detection Function
```python
def _is_conversation_recall_query(query: str) -> bool:
    query_lower = query.lower()
    return any(trigger in query_lower for trigger in RECALL_TRIGGERS)
```

#### 3. Recall Gate (in stream_query)
- Detects recall queries using trigger phrases
- Formats conversation history into prompt
- Sends directly to LLM WITHOUT function calling
- Returns response immediately (bypasses RAG)

## Test Results

### Before Fix
```
User: "Ti ricordi il cliente di cui abbiamo parlato?"
Logs: 🛡️ [Uncertainty Stream] Triggered ABSTAIN (Score: 0.20)
Response: "Mi dispiace, non ho trovato informazioni verificate..."
Time: ~20 seconds
```

### After Fix
```
User: "Ti ricordi il cliente di cui abbiamo parlato?"
Logs: 🧠 [Recall Gate] Detected conversation recall query - bypassing RAG
Response: "Sì, certamente. Il cliente si chiama Marco Bianchi.
          È di Napoli e vuole aprire una gelateria a Ubud
          con un budget di 400 milioni IDR."
Time: 5.25 seconds
```

## Verification

1. **Recall Gate Triggered**: ✅ Logs show `[Recall Gate] Detected conversation recall query`
2. **RAG Bypassed**: ✅ No `vector_search` tool calls
3. **Correct Response**: ✅ All client facts recalled accurately
4. **Performance**: ✅ Response time reduced from 20s to 5s

## Deployment

- **Deployed to**: Fly.io (`nuzantara-rag`)
- **Deploy time**: 2025-12-29 21:12 UTC
- **Health check**: PASSED

## Known Limitations

1. **Trigger-based**: Only works if user uses known trigger phrases
2. **No semantic detection**: Doesn't detect implicit recall (e.g., "il budget di prima")
3. **History limit**: Only checks last 20 messages

## Future Improvements

- Add semantic intent classification for recall queries
- Expand trigger phrases based on user feedback
- Consider hybrid approach (check history first, then RAG)

## Related Issues

- First message ABSTAIN: When user says "Ho un cliente: Marco Bianchi...", Zantara sometimes ABSTAINs instead of acknowledging. This is a separate issue related to the ReAct loop treating informational statements as questions requiring RAG.
