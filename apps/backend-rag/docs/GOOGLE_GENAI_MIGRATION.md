# Google GenAI SDK Migration Plan

**From**: `google-generativeai` (deprecated Nov 30, 2025)
**To**: `google-genai` v1.56.0+
**Date**: 2025-12-23
**Status**: ✅ **COMPLETED** - Deployed v912 on 2025-12-23

## Latest Update (2025-12-23)

### Model Configuration Update (Updated 2025-12-28)
- **Primary Model**: `gemini-3-flash` (was gemini-2.5-flash)
- **Fallback Model**: `gemini-2.0-flash` (stable)
- **OpenRouter**: ❌ Removed as fallback

### Service Account Update
- **Active SA**: `vertex-express@gen-lang-client-0498009027.iam.gserviceaccount.com`
- **Auth Method**: Vertex AI with Service Account (preferred for production)

## Migration Completion Summary

| Phase | Status | Notes |
|-------|--------|-------|
| Dependencies | ✅ Complete | google-genai 1.56.0, httpx 0.28.1, openai 2.14.0 |
| Core Migration | ✅ Complete | GenAIClient wrapper created |
| Secondary Services | ✅ Complete | All services updated |
| Tests | ✅ Complete | Mocking patterns updated |
| Deployment | ✅ Complete | v857 - healthy in production |

### Critical Fix Applied During Deployment

**Problem**: `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`

**Root Cause**: `openai==1.55.0` incompatible with `httpx>=0.28.1` (proxies parameter removed)

**Solution**:
```txt
# Before (BROKEN)
openai==1.55.0
httpx>=0.28.1

# After (FIXED)
openai>=1.57.0  # Must be >=1.57.0 for httpx 0.28.1 compatibility
httpx>=0.28.1,<1.0.0
```

**Final Versions in Production**:
- `google-genai` 1.56.0
- `openai` 2.14.0
- `httpx` 0.28.1

---

## Executive Summary

Google has deprecated the `google.generativeai` package in favor of the new unified `google.genai` SDK. This migration requires significant API changes but brings improved architecture, better async support, and access to new models (Gemini 2.0, Veo, Imagen).

## Dependency Conflict

### The Problem
```
google-genai requires: httpx>=0.28.1
current pin:           httpx==0.27.2 (for openai compatibility)
```

### Resolution
Update httpx and verify openai compatibility:
```txt
httpx>=0.28.1,<1.0.0  # Compatible with both google-genai and openai
```

## Files Requiring Changes

### Priority 1: Core Production Code (5 files)

| File | Usage | Complexity |
|------|-------|------------|
| `backend/llm/zantara_ai_client.py` | Main AI engine | High |
| `backend/services/gemini_service.py` | Jaksel persona | Medium |
| `backend/services/rag/agentic/llm_gateway.py` | RAG gateway | High |
| `backend/services/rag/vision_rag.py` | Vision processing | Medium |
| `backend/services/multimodal/pdf_vision_service.py` | PDF analysis | Low |

### Priority 2: Secondary Services (4 files)

| File | Usage |
|------|-------|
| `backend/services/oracle_google_services.py` | Oracle integration |
| `backend/services/image_generation_service.py` | Image generation |
| `backend/services/smart_oracle.py` | Smart Oracle |
| `backend/services/context/agentic_orchestrator_v2.py` | Orchestrator |

### Priority 3: Test Files (20 files)

All test files mocking `google.generativeai` need updates to mock `google.genai` instead.

## API Migration Guide

### 1. Import Changes

```python
# BEFORE
import google.generativeai as genai

# AFTER
from google import genai
from google.genai import types
```

### 2. Client Initialization

```python
# BEFORE
genai.configure(api_key=settings.google_api_key)
model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)

# AFTER
client = genai.Client(api_key=settings.google_api_key)
# Model is specified per-request, not at initialization
```

### 3. Chat Sessions

```python
# BEFORE
chat = model.start_chat(history=gemini_history)
response = await chat.send_message_async(message, stream=True)

# AFTER
chat = client.chats.create(
    model='gemini-2.0-flash',
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )
)
# For async:
response = await client.aio.chats.send_message(chat_id=chat.id, message=message)
```

### 4. Streaming

```python
# BEFORE
response = await chat.send_message_async(message, stream=True)
async for chunk in response:
    yield chunk.text

# AFTER
async for chunk in client.aio.models.generate_content_stream(
    model='gemini-2.0-flash',
    contents=message,
    config=types.GenerateContentConfig(...)
):
    yield chunk.text
```

### 5. Generation Config

```python
# BEFORE
genai.types.GenerationConfig(
    max_output_tokens=max_tokens,
    temperature=temperature
)

# AFTER
types.GenerateContentConfig(
    max_output_tokens=max_tokens,
    temperature=temperature,
    system_instruction=system_prompt,  # Moved here
)
```

### 6. Safety Settings

```python
# BEFORE
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}
]

# AFTER
config = types.GenerateContentConfig(
    safety_settings=[
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="BLOCK_NONE"
        )
    ]
)
```

## Migration Steps

### Phase 1: Dependencies (5 min)

1. Update `requirements.txt`:
```txt
# Google Cloud Integration
google-genai>=1.55.0  # NEW unified SDK (replaces google-generativeai)
# google-generativeai>=0.5.0  # DEPRECATED - remove after migration

# HTTP/Network
httpx>=0.28.1,<1.0.0  # Upgraded for google-genai compatibility
```

### Phase 2: Core Migration (1.5 hours)

1. Create `backend/llm/genai_client.py` - New client wrapper
2. Update `zantara_ai_client.py` - Migrate to new SDK
3. Update `gemini_service.py` - Migrate streaming
4. Update `llm_gateway.py` - Migrate fallback logic

### Phase 3: Secondary Services (30 min)

1. Update remaining service files
2. Verify all imports

### Phase 4: Tests (30 min)

1. Update mocks in test files
2. Run test suite
3. Fix any failures

### Phase 5: Cleanup (15 min)

1. Remove `google-generativeai` from requirements
2. Remove any backward compatibility code
3. Update documentation

## Rollback Plan

If issues arise:
1. Revert requirements.txt changes
2. Keep both SDKs temporarily: `google-generativeai>=0.5.0`
3. Use feature flag to switch between implementations

## Testing Checklist

- [x] Unit tests pass
- [x] Integration tests pass
- [x] Streaming works correctly
- [x] Chat sessions maintain history
- [x] Safety settings applied
- [x] Fallback to Gemini 2.0 works (OpenRouter removed)
- [x] Token estimation accurate
- [x] No memory leaks with client pooling
- [x] Production deployment healthy (v912)

## References

- [Migration Guide](https://ai.google.dev/gemini-api/docs/migrate)
- [New SDK Docs](https://ai.google.dev/gemini-api/docs)
- [PyPI: google-genai](https://pypi.org/project/google-genai/)
- [Deprecated SDK Notice](https://github.com/google-gemini/deprecated-generative-ai-python)
