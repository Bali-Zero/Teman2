# JAKSEL AI SYSTEM API DOCUMENTATION

## Overview

Jaksel AI is the **official personality voice** for ALL Zantara responses. It provides casual, friendly responses using Jakarta Selatan (Jaksel) slang, automatically adapted to the user's language (190+ languages supported).

**Current Status (December 2025):**
- **Role**: Official personality layer for ALL users
- **Activation**: Automatic (no user whitelist)
- **Primary Model:** `zantara:latest` (Gemma 9B Fine-tuned) via **Ollama Production** - *Active & Verified*
- **Endpoint:** `https://jaksel.balizero.com`
- **Fallback:** Gemini 2.5 Flash (Imitating Jaksel Style) - *Active Backup*
- **Availability:** 100% (Primary + Fallback)

## Architecture

The system uses a robust two-step process to ensure users always receive Jaksel-styled responses:

### Flow (`IntelligentRouter`)

1.  **Context Extraction**: Jaksel reads the user query to extract:
    - Language (auto-detected from query)
    - Formality level (casual/formal/neutral)
    - Tone indicators
    - User name (from email)

2.  **Gemini Processing**: Gemini 2.5 Flash elaborates the response:
    - RAG search for relevant documents
    - Reasoning and answer generation
    - Professional, accurate response

3.  **Jaksel Transformation**: Jaksel receives Gemini response and applies:
    - Personality layer (friendly, casual, cool)
    - Language adaptation (matches user's language)
    - Style transfer (adds Jaksel signature words)

4.  **Fallback**: If Oracle Cloud endpoint is unavailable:
    - System automatically uses Gemini 2.5 Flash with style-transfer prompt
    - Ensures 99.9%+ uptime

### The "Jaksel" Style
The system enforces specific linguistic traits:
-   **Language**: Adapts to user's language (Italian, English, Indonesian, Spanish, French, etc.)
-   **Slang**: Uses signature words like "basically", "literally", "which is", "praticamente", "kayak", "gitu"
-   **Tone**: Friendly, helpful, peer-to-peer (not robotic)
-   **Multilingual**: Maintains Jaksel personality across all languages
-   **No Info Handling**: Translates standard "I don't know" responses into character-appropriate apologies

## Endpoints

### Universal Chat

**Endpoint:** `POST /api/v1/chat` or `POST /api/oracle/universal-chat`

**Description:** Main chat endpoint. Jaksel personality is automatically applied to ALL users. The system detects the user's language from the query and adapts the response accordingly.

**Request Format:**
```json
{
  "message": "Ciao! Cos'è un contratto PT?",
  "user_id": "test@example.com",
  "conversation_id": "optional-uuid"
}
```

**Response Format:**
```json
{
  "success": true,
  "response": "Ciao! Praticamente, un contratto PT è basically un documento legale che definisce le regole della società, capisci? Ti spiego meglio...",
  "ai_used": "zantara-ai",
  "model": "gemma-9b-jaksel",
  "language": "it"
}
```

**Example Responses by Language:**

- **Italian**: "Ciao! Praticamente, il contratto è basically un accordo legale..."
- **English**: "Hey! Basically, a contract is literally a legal agreement..."
- **Indonesian**: "Halo! Kontrak itu basically kayak perjanjian gitu loh..."
- **Spanish**: "¡Hola! Básicamente, un contrato es literalmente un acuerdo legal..."

## User Activation

**ALL users** receive Jaksel-styled responses automatically. No whitelist or configuration needed.

## Deployment & Hosting

### Current Setup (Production)
-   **Hosting**: Oracle Cloud VM (24/7 uptime)
-   **Model**: `zantara:latest` (Gemma 9B Fine-tuned - Sahabat AI → Jaksel custom)
-   **Endpoint**: `https://jaksel.balizero.com`
-   **Runtime**: Ollama server
-   **Fallback**: Gemini 2.5 Flash (automatic if Oracle Cloud unavailable)

### Configuration

Jaksel configuration is centralized in `apps/backend-rag/backend/app/core/config.py`:

```python
jaksel_oracle_url: str = "https://jaksel.balizero.com"  # Production
jaksel_tunnel_url: str = "https://jaksel-ollama.nuzantara.com"  # Backup
jaksel_enabled: bool = True  # Feature flag
jaksel_local_url: str = "http://127.0.0.1:11434"  # Local dev
```

Set via environment variables:
- `JAKSEL_ORACLE_URL`
- `JAKSEL_TUNNEL_URL`
- `JAKSEL_ENABLED`
- `JAKSEL_LOCAL_URL`

## Troubleshooting

### "Why is it answering in Italian/English?"
-   The system automatically detects the user's language from the query
-   Jaksel adapts its response to match the user's language while maintaining personality
-   Check logs for `[Router] Applying Jaksel personality layer` and `Language detected:`

### "Why is the custom model not working?"
-   Check Oracle Cloud endpoint status: `https://jaksel.balizero.com`
-   System automatically falls back to Gemini 2.5 Flash if Oracle Cloud is unavailable
-   Check logs for fallback activation: `Using Gemini fallback for Jaksel style`

### "How do I disable Jaksel for specific users?"
-   Set `JAKSEL_ENABLED=false` in environment variables (disables for ALL users)
-   For per-user control, modify `IntelligentRouter` to add conditional logic

---

**Last Updated:** 2025-12-02
**Status:** Production Ready - Official Voice ✅
