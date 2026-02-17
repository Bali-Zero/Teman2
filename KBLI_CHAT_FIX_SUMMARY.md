# KBLI Notebook Chat Fix - Summary

## Problem

The `/api/v1/kbli-notebook/chat` endpoint was returning an empty `answer` field:

```json
{
    "answer": "",  // EMPTY - should contain generated text
    "detected_kbli": [...],
    "results": [...]
}
```

## Root Causes Identified

1. **Invalid Model Name**: The code was using `gemini-2.5-flash` which is not widely available. This could cause the LLM to fail silently.

2. **Empty Response Handling**: When the LLM returned an empty response (due to safety blocks, invalid model, or other issues), the code wasn't properly validating and falling back.

3. **Insufficient Logging**: When LLM calls failed, there wasn't enough logging to diagnose the issue in production.

4. **Missing Availability Check**: The code wasn't checking if the LLM gateway was available before attempting to generate answers.

## Files Modified

### 1. `backend/services/rag/agentic/llm_gateway.py`

**Changes:**

- Fixed model names from `gemini-2.5-flash` to `gemini-2.0-flash-001` (primary) and `gemini-1.5-flash-001` (fallback)
- Enhanced response extraction to handle cases where `response.text` is empty but candidates contain text
- Added detailed logging for empty responses with finish reason
- Improved error handling for function calls vs empty responses

**Key Code Changes:**

```python
# Before (line 121-123):
self.model_name_pro = "gemini-2.5-flash"
self.model_name_flash = "gemini-2.5-flash"
self.model_name_fallback = "gemini-2.0-flash-001"

# After:
self.model_name_pro = "gemini-2.0-flash-001"
self.model_name_flash = "gemini-2.0-flash-001"
self.model_name_fallback = "gemini-1.5-flash-001"
```

### 2. `backend/app/routers/kbli_notebook.py`

**Changes:**

- Added LLM availability check in `chat_kbli` endpoint
- Enhanced `_generate_kbli_explanation` with validation for empty responses
- Added ultimate fallback if answer is still empty after explanation generation
- Improved `_translate_query_for_kbli` with availability check
- Added comprehensive logging at each step
- Added new `/llm-health` diagnostic endpoint

**Key Code Changes:**

```python
# Added LLM availability check
gateway = _get_llm_gateway()
if not gateway._available:
    logger.error("❌ LLM Gateway not available...")

# Added empty response validation
if not response_text or not response_text.strip():
    raise RuntimeError(f"LLM returned empty response from model {model_used}")

# Added ultimate fallback in chat endpoint
if not answer or not answer.strip():
    logger.error("❌ CRITICAL: Answer is empty...")
    # Ultimate fallback implementation
```

### 3. `.env.example`

**Changes:**

- Added clearer documentation about which variables are critical for chat functionality
- Added notes about Google API Key vs Service Account authentication

### 4. `test_kbli_chat_fix.py` (New File)

**Purpose:**

- Test script to verify the fix works correctly
- Tests LLM Gateway availability
- Tests KBLI explanation generation
- Tests empty results fallback
- Provides troubleshooting guidance

## How to Test the Fix

### 1. Check LLM Health Endpoint

```bash
curl https://your-api-domain/api/v1/kbli-notebook/llm-health
```

Expected response (when healthy):

```json
{
  "llm_available": true,
  "models": {
    "gemini_pro": true,
    "gemini_flash": true,
    "gemini_flash_lite": true,
    "openrouter": false
  },
  "test_generation": {
    "success": true,
    "model_used": "gemini-2.0-flash-001",
    "response_preview": "OK"
  }
}
```

### 2. Test Chat Endpoint

```bash
curl -X POST https://your-api-domain/api/v1/kbli-notebook/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"query": "voglio aprire un ristorante"}'
```

Expected response (truncated):

```json
{
  "answer": "Ho trovato i seguenti codici KBLI rilevanti...",
  "detected_kbli": ["56101"],
  "results": [...],
  "sources": [...],
  "suggested_queries": [...]
}
```

### 3. Run Local Test Script

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
python test_kbli_chat_fix.py
```

## Configuration Requirements

### Required Environment Variables

| Variable         | Required For | Description                         |
| ---------------- | ------------ | ----------------------------------- |
| `GOOGLE_API_KEY` | LLM Chat     | Google AI Studio API Key            |
| `OPENAI_API_KEY` | Embeddings   | OpenAI API Key for query embeddings |
| `QDRANT_URL`     | Search       | Qdrant vector database URL          |

### Alternative: Service Account (Production Recommended)

Instead of `GOOGLE_API_KEY`, you can use:

- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON file
- `GOOGLE_CREDENTIALS_JSON` - Service account JSON content

## Fallback Behavior

If the LLM fails, the system now provides a deterministic fallback:

```python
# Fallback message format (Italian)
"Ho trovato {N} codici KBLI rilevanti per la tua ricerca:

**KBLI {code}** - {title}
{description}

..."
```

## Monitoring & Debugging

### New Log Messages

Look for these log messages to verify the fix:

- `✅ LLMGateway: Model configuration ready (...)` - Gateway initialized
- `✅ GenAI client initialized with ...` - Client ready
- `✅ KBLI explanation generated. Model: ..., Length: ... chars` - Generation successful
- `❌ LLM returned empty response. Model: ...` - Empty response detected
- `⚠️ LLMGateway: Empty text response from ... Finish reason: ...` - Detailed failure info

### Health Check

Use the new health endpoint for monitoring:

```
GET /api/v1/kbli-notebook/llm-health
```

## Deployment Checklist

- [ ] Set `GOOGLE_API_KEY` environment variable (or Service Account credentials)
- [ ] Verify `QDRANT_URL` is accessible
- [ ] Verify `OPENAI_API_KEY` is set
- [ ] Deploy the code changes
- [ ] Test the `/llm-health` endpoint
- [ ] Test the `/chat` endpoint with sample queries
- [ ] Monitor logs for any errors

## Rollback Plan

If issues occur, the changes are backwards compatible. The fallback mechanism will continue to provide deterministic responses even if the LLM is unavailable.

To fully rollback:

1. Revert the modified files
2. Redeploy
3. The old behavior will be restored (though it had the empty answer bug)
