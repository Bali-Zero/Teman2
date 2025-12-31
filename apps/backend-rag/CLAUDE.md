# Claude Memory - Backend RAG

## Session Update (2025-12-31 19:30 UTC)

### Image Generation URL Cleaning - COMPLETED
Fixed ugly pollinations.ai URLs appearing in chat when generating images.

**Problem:** AI was generating multiple image versions with raw URLs visible to users.

**Solution:** Added `cleanImageResponse()` function in the correct API file.

**Changes Made:**
1. **Chat API** (`apps/mouth/src/lib/api/chat/chat.api.ts`)
   - Added `cleanImageResponse()` function to filter pollinations URLs
   - Applied to streaming token handler (accumulated content)
   - Applied to final `onDone` callback
   - Filters: URLs, "Versione 1/2", intro/outro lines

2. **UI Updates** (`apps/mouth/src/app/chat/page.tsx`)
   - Sparkles icon (✨) opens "Genera Immagine" modal
   - Paperclip now handles both file attachment and image upload

**Result:** Clean response "Ecco l'immagine che hai richiesto! 🎨" without ugly URLs.

---

## Session Update (2025-12-31 18:40 UTC)

### Audio Integration - COMPLETED
Integrated full audio (TTS/STT) support using hybrid provider strategy.

**Changes Made:**
1. **Backend Audio Service** (`backend/app/services/audio_service.py`)
   - Hybrid TTS: Pollinations.ai (FREE) → OpenAI fallback
   - STT: OpenAI Whisper (reliable)
   - Voice options: alloy, echo, fable, onyx, nova, shimmer

2. **Frontend Proxy Fix** (`apps/mouth/src/app/api/[...path]/route.ts`)
   - Fixed multipart/form-data boundary mismatch
   - Delete Content-Type header for FormData to let fetch set correct boundary

3. **Chat TTS Button** (`apps/mouth/src/app/chat/page.tsx`)
   - Added speaker button (Volume2) to assistant messages
   - Shows loading spinner, stop icon when playing
   - Emerald highlight for active state

4. **Auth Middleware** (`backend/middleware/hybrid_auth.py`)
   - Added `/api/audio/` to public endpoints

**Status:**
- STT: Working (tested via curl + browser)
- TTS: Working (tested via curl + browser)
- Frontend integration: Complete

---

## Active Background Processes

### KG Extraction (Started 2025-12-31 08:30 UTC)
- **Status**: RUNNING
- **Machine**: nuzantara-rag (Fly.io) - PID 754
- **Command**: `python scripts/kg_incremental_extraction.py --limit 10000`
- **Log file**: `/tmp/kg_extraction.log`
- **Model**: `gemini-2.0-flash` (Vertex AI)
- **Rate**: ~24 chunks/min
- **Expected duration**: ~7 hours

**Monitor commands:**
```bash
# Check log
fly ssh console -a nuzantara-rag -C "tail -50 /tmp/kg_extraction.log"

# Check KG stats
fly ssh console -a nuzantara-rag -C "python -c \"
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    nodes = await conn.fetchval('SELECT COUNT(*) FROM kg_nodes')
    edges = await conn.fetchval('SELECT COUNT(*) FROM kg_edges')
    print(f'Nodes: {nodes:,} | Edges: {edges:,}')
asyncio.run(check())
\""
```

## KG Stats Snapshot (2025-12-31)
- Nodes: ~21,000
- Edges: ~17,000
- Coverage: 63.9%
- Target: 53,822 chunks

## Key Files
- **Image Gen Cleaning**: `apps/mouth/src/lib/api/chat/chat.api.ts` (cleanImageResponse)
- **Chat Page**: `apps/mouth/src/app/chat/page.tsx` (UI with sparkles modal)
- Audio Service: `backend/app/services/audio_service.py`
- Audio Router: `backend/app/routers/audio.py`
- Extraction script: `scripts/kg_incremental_extraction.py`
- KG Enhanced Retrieval: `backend/services/rag/kg_enhanced_retrieval.py`
- KG Builder: `backend/services/autonomous_agents/knowledge_graph_builder.py`
