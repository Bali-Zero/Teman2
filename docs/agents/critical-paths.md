# Critical paths — backend, prompt architecture, frontend

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

## 4. Critical Paths

### Backend Structure

```
apps/backend-rag/
├── backend/
│   ├── app/              # FastAPI app
│   │   ├── routers/      # API endpoints (live inventory: docs_sync.py --json)
│   │   ├── services/     # App-level services (CRM, auth, metrics)
│   │   ├── setup/        # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py  # ⚠️ Imported by ALL routers — test before deploy
│   │   └── main.py       # Entrypoint (alias for main_cloud.py)
│   ├── services/         # Core business logic
│   ├── core/             # Config, security, logging
│   ├── prompts/          # ⭐ Prompt Single Source of Truth (see below)
│   ├── channels/         # 7 channels (whatsapp, telegram, instagram, etc.)
│   ├── llm/              # LLM clients (Gemini, Ollama, OpenRouter)
│   └── migrations/       # custom SQL (legacy 001→124 py; live v2 092→246 sql in backend/db/migrations_v2/)
├── tests/                # Unit and integration tests
├── .venv/                # ⚠️ ALWAYS .venv on Pro and Mini
└── fly.toml
```

**IMPORTANT:** Routers in `backend/app/routers/`, NOT `backend/routers/`. Services in both `backend/services/` and `backend/app/services/`.

### Prompt Architecture (Single Source of Truth)

```
backend/prompts/
├── __init__.py              # Re-exports ZANTARA_MASTER_TEMPLATE, CREATOR_PERSONA, TEAM_PERSONA
├── zantara_core.py          # ⭐ THE file — all prompt sections as composable constants
├── channel_overlays.py      # Per-channel config (word limits, markdown, emoji)
├── few_shot_examples.py     # Consolidated few-shot examples
├── zantara_persona.py       # Backward compat wrapper → imports from zantara_core
├── whatsapp_persona.py      # Dynamic builder for WhatsApp context → imports from zantara_core
└── zantara_prompt_builder.py # Legacy builder → imports from zantara_core
```

**Rule:** To add/edit ANY Zantara prompt rule, edit ONLY `zantara_core.py`. All consumers import from it.

**Sections in `zantara_core.py`:**
`SECURITY_BOUNDARY` · `TOOL_USAGE_POLICY` · `SYSTEM_INSTRUCTIONS` · `KNOWLEDGE_GOVERNANCE` ·
`LANGUAGE_PROTOCOL` · `GREETING_RULES` · `CITATION_RULES` · `INTERNAL_MONOLOGUE` ·
`ESCALATION_PROTOCOL` · `CRASH_PROTOCOL` · `CLOSING_PHRASES` · `CREATOR_PERSONA` ·
`TEAM_PERSONA` · `ZANTARA_MASTER_TEMPLATE`

### Frontend Structure

```
apps/mouth/
├── app/              # Next.js App Router
├── components/       # React components
├── lib/              # Utilities
├── public/           # Static assets
└── styles/           # Tailwind CSS
```
