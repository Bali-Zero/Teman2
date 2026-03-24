"""
Federation Capability Table v3 — Maps the complete Nuzantara AI arsenal.

3-tier taxonomy (2026-03-25):
  AGENTS    — Autonomous runtimes that accept tasks and return results (dispatchable)
  SERVICES  — Stateless tools called by agents (not dispatchable, called directly)
  PIPELINES — Scheduled/triggered multi-step workflows (not dispatchable, cron/manual)

Used by:
  - federation orchestrator (Qwen classifier routing)
  - ai-dispatch.sh (CLI dispatch)
  - generate_agent_cards.py (A2A card generation)
  - adk_agents.py (ADK agent registration)

Arsenal inventory (2026-03-25, v3):
  - 7 dispatchable agents
  - 5 callable services
  - 4 autonomous pipelines
  - 109 NuzMCP tools (20 modules)
  - 13 NuzMCP-Advanced tools
  - 35 NotebookLM MCP tools
  - 22 GWS CLI tools
  - 16 OpenClaw skills
  - 16 Gemini CLI tools (built-in + extensions)
  - 7 Google SDK/APIs
  - 8 workflow chains
"""

# ═══════════════════════════════════════════════════════
# TIER 1: AGENTS — Autonomous runtimes that accept tasks
# These can be dispatched to via ai-dispatch.sh or A2A.
# Each has its own CLI, reasoning capability, and can
# decide how to accomplish a task.
# ═══════════════════════════════════════════════════════
AGENTS = {
    "claude-code": {
        "name": "Claude Code (Opus 4.6)",
        "role": "Il Re — orchestra, sintetizza, decide, esegue",
        "tier": "agent",
        "strengths": [
            "multi-file refactor", "deploy pipeline", "architectural decisions",
            "complex debugging", "test writing", "code review synthesis",
        ],
        "limits": "max 200K context window, no Google Search",
        "cost": "$$$",
        "dispatch_cmd": None,  # Direct execution — IS the orchestrator
        "capabilities": ["coding", "refactoring", "debugging", "testing", "deploy", "orchestration"],
    },
    "gemini-search": {
        "name": "Gemini 3.1 Pro (Search)",
        "role": "Il Consigliere — grounded web search",
        "tier": "agent",
        "strengths": [
            "Indonesian regulations", "KBLI 2025", "visa rules", "tax law",
            "competitor research", "market data", "news", "citations with sources",
        ],
        "limits": "read-only, no code execution",
        "cost": "$0 (Google AI Ultra)",
        "dispatch_cmd": "search",
        "capabilities": ["web_research", "regulations", "citations"],
    },
    "gemini-explore": {
        "name": "Gemini 3.1 Pro (Explore)",
        "role": "Il Consigliere — 1M context codebase analysis",
        "tier": "agent",
        "strengths": [
            "cross-app dependency mapping", "large refactor planning",
            "codebase_investigator tool", "reading 100+ files at once",
            "architecture review", "import chain analysis",
        ],
        "limits": "read-only, sandbox mode, no writes",
        "cost": "$0 (Google AI Ultra)",
        "dispatch_cmd": "explore",
        "capabilities": ["codebase_analysis", "architecture_review", "dependency_mapping"],
    },
    "codex-sandbox": {
        "name": "Codex 5.4 (Sandbox)",
        "role": "Il Soldato — kernel-level sandbox execution",
        "tier": "agent",
        "strengths": [
            "DB migrations (alembic)", "schema changes", "risky code execution",
            "isolated testing", "upgrade/downgrade verification",
        ],
        "limits": "sandbox only, no network access, single file changes",
        "cost": "$0 (OpenAI free tier)",
        "dispatch_cmd": "sandbox",
        "capabilities": ["sandbox_execution", "migration_testing", "isolated_code"],
    },
    "claude-review": {
        "name": "Claude CLI (Opus 4.6)",
        "role": "Il Giudice — code review, red team",
        "tier": "agent",
        "strengths": [
            "security review", "pre-deploy audit", "logic errors",
            "red team analysis", "architectural critique",
        ],
        "limits": "read-only (plan mode), no code execution",
        "cost": "$0 (Max plan)",
        "dispatch_cmd": "claude-redteam",
        "capabilities": ["security_review", "red_team", "code_review"],
    },
    "aider": {
        "name": "Aider (OpenRouter/DeepSeek)",
        "role": "Il Mercenario — multi-model coding",
        "tier": "agent",
        "strengths": [
            "quick targeted fixes", "single-file refactors",
            "DeepSeek V3 for cost-effective coding", "Sonnet for refactors",
        ],
        "limits": "no orchestration awareness, single-task focus",
        "cost": "$ (OpenRouter rates)",
        "dispatch_cmd": "aider-fix",
        "capabilities": ["quick_fix", "single_file_refactor"],
    },
    "deepseek-reasoning": {
        "name": "DeepSeek R1 671b (API)",
        "role": "Il Pensatore — deep chain-of-thought reasoning",
        "tier": "agent",
        "strengths": [
            "architecture decisions", "migration strategies", "complex debugging",
            "trade-off analysis", "step-by-step reasoning", "27K+ reasoning tokens",
        ],
        "limits": "API-only (no CLI tools), slow (30-120s), no code execution",
        "cost": "¢ ($0.55/M input, $2.19/M output)",
        "dispatch_cmd": "reasoning",
        "capabilities": ["deep_reasoning", "architecture_design", "trade_off_analysis"],
    },
}


# ═══════════════════════════════════════════════════════
# TIER 2: SERVICES — Stateless tools called by agents
# These do NOT accept open-ended tasks. They execute
# specific commands and return structured results.
# Called directly by the orchestrator (Claude Code) or
# via ai-dispatch.sh wrapper commands.
# ═══════════════════════════════════════════════════════
SERVICES = {
    "notebooklm": {
        "name": "NotebookLM (Google AI Ultra)",
        "role": "L'Oracolo — knowledge synthesis with citations",
        "tier": "service",
        "tools": [
            "notebook_query", "cross_notebook_query", "research_start",
            "studio_create", "source_add", "pipeline", "batch",
        ],
        "access": "nlm CLI or NotebookLM MCP (mcp__notebooklm-mcp__*)",
        "dispatch_cmds": ["oracolo", "oracolo-nb", "research"],  # Multiple entry points
        "limits": "3-15s latency, cookie auth, 600 sources/notebook max, no live DB",
        "cost": "$0 (Google AI Ultra subscription)",
        "notebooks": {
            "NB-1": {"id": "f6ecd115-dd89-4c9b-b3dd-071e0e2f1876", "domain": "codebase", "status": "populated"},
            "NB-2": {"id": "84375bc3-12d0-4405-a774-9b89189d8c39", "domain": "immigration", "status": "created"},
            "NB-3": {"id": "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4", "domain": "company", "status": "created"},
            "NB-4": {"id": "837b620b-2aca-43ab-812e-97ca92bdad1d", "domain": "tax", "status": "created"},
            "NB-5": {"id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed", "domain": "property", "status": "created"},
            "NB-6": {"id": "3e1baa5f-680f-4499-9430-23a901576bcc", "domain": "operations", "status": "created"},
            "NB-7": {"id": "dd464d8f-6b8e-4543-8647-f62c498589b1", "domain": "editorial", "status": "created"},
            "NB-8": {"id": "1143b525-dd3f-40d7-a34d-2e9263b44460", "domain": "lifestyle", "status": "created"},
            "NB-9": {"id": "d2a05271-2f65-4c02-a44d-eefeb7c7f7cd", "domain": "research_lab", "status": "active"},
        },
    },
    "gws": {
        "name": "Google Workspace CLI (gws)",
        "role": "Il Segretario — unified Google Workspace automation",
        "tier": "service",
        "tools": [
            "gmail_send", "gmail_search", "gmail_list", "gmail_draft",
            "drive_list", "drive_upload", "drive_download", "drive_search",
            "calendar_create", "calendar_list", "calendar_freebusy",
            "sheets_read", "sheets_write", "sheets_append",
            "docs_create", "docs_export", "admin_users_list",
        ],
        "access": "gws CLI (command line)",
        "dispatch_cmds": [],  # Called directly by orchestrator, no ai-dispatch wrapper yet
        "limits": "requires Google Workspace account, CLI tool",
        "cost": "$0 (already paying Workspace)",
    },
    "ocr": {
        "name": "OCR Services (Tesseract MCP + Document AI)",
        "role": "Document scanner — text extraction from images/PDFs",
        "tier": "service",
        "tools": ["perform_ocr", "perform_batch_ocr", "perform_pdf_ocr"],
        "access": "OCR Tesseract MCP (mcp__ocr-tesseract__*) or Google Document AI SDK",
        "dispatch_cmds": [],
        "limits": "Indonesian language support varies, PDF quality dependent",
        "cost": "$0 (Tesseract) / ¢ (Document AI per page)",
    },
    "websearch": {
        "name": "Web Search (Exa + Brave)",
        "role": "Deep web search with full content and citations",
        "tier": "service",
        "tools": ["web_search_exa", "web_search_advanced_exa", "brave_web_search"],
        "access": "Exa MCP (mcp__exa__*) or Brave API",
        "dispatch_cmds": ["websearch"],
        "limits": "Exa: best from Claude Code MCP; Brave: API key needed for bash",
        "cost": "$0 (Exa free tier) / ¢ (Brave API)",
    },
    "canva": {
        "name": "Canva MCP",
        "role": "Design automation — create/edit designs, export assets",
        "tier": "service",
        "tools": [
            "generate-design", "create-design-from-candidate", "export-design",
            "get-design", "search-designs", "list-brand-kits", "upload-asset-from-url",
        ],
        "access": "Canva MCP (mcp__claude_ai_Canva__*)",
        "dispatch_cmds": [],
        "limits": "requires interactive Claude Code session, Canva Pro account",
        "cost": "$0 (Canva Pro subscription)",
    },
    "gitkraken": {
        "name": "GitKraken MCP (Premium Plus)",
        "role": "Git workflow intelligence — smart commits, PR triage, issue→branch, AI review",
        "tier": "service",
        "tools": [
            "gitlens_commit_composer", "gitlens_launchpad", "gitlens_start_review",
            "gitlens_start_work", "pull_request_create", "pull_request_get_detail",
            "pull_request_create_review", "issues_assigned_to_me", "issues_get_detail",
            "git_blame", "git_worktree", "git_log_or_diff",
        ],
        "access": "GitKraken MCP (gk mcp) — authenticated as Balizero1987",
        "dispatch_cmds": [],
        "limits": "requires gk auth login, Premium Plus annual subscription",
        "cost": "$0 (annual Premium Plus subscription)",
    },
}


# ═══════════════════════════════════════════════════════
# TIER 3: PIPELINES — Scheduled/triggered workflows
# These run autonomously on a schedule or are triggered
# manually. They are NOT dispatchable by the classifier.
# ═══════════════════════════════════════════════════════
PIPELINES = {
    "core-guardian": {
        "name": "Core Guardian V3",
        "role": "Autonomous code quality agent",
        "tier": "pipeline",
        "schedule": "every 3h (OpenClaw cron)",
        "components": ["watchdog", "scout", "surgeon"],
        "files": "apps/evaluator/core_guardian/",
        "status": "active (watchdog + scout), surgeon pending OpenClaw bridge",
    },
    "intel-scraper": {
        "name": "Bali Intel Scraper",
        "role": "News intelligence pipeline — scrape, enrich, publish",
        "tier": "pipeline",
        "schedule": "03:00 WITA (OpenClaw cron on Pro)",
        "trigger": "manual: submit_scraper_job MCP tool",
        "files": "apps/bali-intel-scraper/",
        "status": "active, runs ONLY on Pro (NOT on Fly.io)",
    },
    "war-room": {
        "name": "War Room Pipeline",
        "role": "Instagram carousel content creation for Bali Zero",
        "tier": "pipeline",
        "stages": ["research (Exa)", "strategy (ChatGPT)", "copywriting", "image prompts", "Canva carousel"],
        "files": "apps/war-room/agents/",
        "trigger": "manual: Claude Code session with Canva MCP",
        "status": "active, requires interactive session",
    },
    "seo-guardian": {
        "name": "SEO Guardian",
        "role": "AI SEO coverage monitoring + llms.txt freshness",
        "tier": "pipeline",
        "trigger": "manual: audit_geo_aeo() in evaluator",
        "files": "apps/evaluator/",
        "status": "active",
    },
    "nlm-daily-refresh": {
        "name": "NLM NB-1 Daily Refresh",
        "role": "Regenerate codebase bundle and upload to NB-1",
        "tier": "pipeline",
        "schedule": "04:30 WITA (OpenClaw cron on Pro)",
        "files": "scripts/nlm_nb1_daily_refresh.py",
        "status": "active",
    },
}


# ═══════════════════════════════════════════════════════
# Capability Domains — WHAT exists in the arsenal
# Maps domains to their best handler (agent, service, or
# "orchestrator" for tasks requiring tool composition)
# ═══════════════════════════════════════════════════════
CAPABILITY_DOMAINS = {
    # --- Business Intelligence ---
    "crm": {
        "description": "Client management, profiles, practices, invoicing",
        "tools": "NuzMCP: list_clients, get_client, create_client, update_client, get_client_stats, get_client_timeline, get_client_compliance (12 tools)",
        "best_handler": "orchestrator",  # Claude Code calls MCP tools directly
        "keywords": ["client", "cliente", "CRM", "practice", "fattura", "invoice"],
    },
    "compliance": {
        "description": "Visa expiry alerts, document tracking, regulatory compliance",
        "tools": "NuzMCP: get_compliance_alerts, track_compliance, get_expiry_alerts, get_compliance_summary (4 tools)",
        "best_handler": "orchestrator",
        "keywords": ["compliance", "expiry", "scadenza", "document", "rinnovo"],
    },
    "intel": {
        "description": "News intelligence, scraping, trend analysis",
        "tools": "NuzMCP: search_intel, publish_intel, get_intel_trends, get_intel_metrics, submit_scraper_job (8 tools)",
        "best_handler": "orchestrator",
        "keywords": ["intel", "news", "notizia", "scraping", "trend"],
    },
    "analytics": {
        "description": "Revenue, productivity, GA4, SEO metrics",
        "tools": "NuzMCP: get_revenue_analytics, get_team_productivity, get_completion_rates + GA4 MCP (8 tools) + GSC MCP (19 tools)",
        "best_handler": "orchestrator",
        "keywords": ["analytics", "revenue", "fatturato", "metrics", "GA4", "SEO", "GSC"],
    },

    # --- Knowledge & Regulations ---
    "regulations": {
        "description": "Indonesian law, KBLI codes, visa rules, tax, permits",
        "tools": "NuzMCP: search_kbli, chat_kbli, inspect_kbli, ask_legal, list_visa_types, get_visa_details + Gemini Search",
        "best_handler": "gemini-search",  # Agent: needs Google Search grounding
        "keywords": ["KBLI", "visa", "KITAS", "KITAP", "PMA", "tax", "pajak", "regulation", "normativa", "legge", "permit", "izin"],
    },
    "knowledge": {
        "description": "Knowledge base queries, legal docs, vector search, NLM grounded citations",
        "tools": "NuzMCP: recall_similar, search_kbli, ask_legal + NLM: notebook_query, cross_notebook_query",
        "best_handler": "orchestrator",  # Orchestrator calls NLM service when needed
        "keywords": ["knowledge", "RAG", "search", "cerca", "ask", "citation", "citazione"],
    },
    "pricing": {
        "description": "Service pricing, calculations, quotes",
        "tools": "NuzMCP: calculate_pricing, get_all_prices, search_service_pricing (3 tools)",
        "best_handler": "orchestrator",
        "keywords": ["price", "prezzo", "pricing", "quote", "preventivo", "costo"],
    },

    # --- Communications ---
    "comms": {
        "description": "Email, WhatsApp, Telegram, portal messaging",
        "tools": "NuzMCP: send_email, send_whatsapp, send_portal_message, list_emails, search_emails + gws gmail",
        "best_handler": "orchestrator",  # Orchestrator calls NuzMCP or gws service
        "keywords": ["email", "whatsapp", "telegram", "message", "messaggio", "send"],
    },

    # --- Content & Publishing ---
    "content": {
        "description": "Article composition, publishing, editorial pipeline",
        "tools": "NuzMCP: compose_article, publish_article, list_articles, get_article (6 tools)",
        "best_handler": "orchestrator",
        "keywords": ["article", "articolo", "blog", "content", "editorial", "publish"],
    },
    "content-creation": {
        "description": "Instagram carousel creation, social media content pipeline",
        "tools": "War Room Pipeline (pipeline) + Canva MCP (service)",
        "best_handler": "orchestrator",  # Orchestrator triggers war-room pipeline + canva service
        "keywords": [
            "carousel", "carosello", "war room", "instagram", "post bali zero",
            "contenuto", "social media", "content creation", "IG post", "slide",
        ],
    },

    # --- Infrastructure & DevOps ---
    "infrastructure": {
        "description": "Fly.io deploy, health checks, monitoring, logs",
        "tools": "NuzMCP-Advanced: check_fly_status, get_fly_logs, analyze_fly_health, check_deployment_readiness (13 tools)",
        "best_handler": "orchestrator",
        "keywords": ["fly", "deploy", "health", "log", "monitoring", "server", "infra"],
    },
    "codebase": {
        "description": "Multi-app analysis, dependency mapping, architecture review",
        "tools": "Gemini CLI: codebase_investigator (1M ctx) + NuzMCP-Advanced: search_codebase, get_file_structure",
        "best_handler": "gemini-explore",  # Agent: needs 1M context
        "keywords": ["codebase", "architecture", "dependency", "refactor", "multi-app", "monorepo"],
    },
    "database": {
        "description": "Alembic migrations, schema changes, DB operations",
        "tools": "Codex sandbox for safe migration testing + Claude Code for implementation",
        "best_handler": "codex-sandbox",  # Agent: needs kernel sandbox
        "keywords": ["migration", "alembic", "schema", "database", "DB", "model", "table"],
    },
    "testing": {
        "description": "Running tests, coverage, quality checks",
        "tools": "NuzMCP-Advanced: run_backend_tests, run_linting, run_type_checking + Claude Code pytest",
        "best_handler": "orchestrator",
        "keywords": ["test", "pytest", "coverage", "lint", "type check", "mypy", "ruff"],
    },

    # --- Security & Review ---
    "security": {
        "description": "Pre-deploy review, red team, vulnerability analysis",
        "tools": "Claude CLI: claude-redteam (Opus reasoning) + Claude CLI: claude-review",
        "best_handler": "claude-review",  # Agent: needs Opus reasoning
        "keywords": ["security", "review", "red team", "vulnerability", "deploy", "audit"],
    },

    # --- Google & External ---
    "google-workspace": {
        "description": "Drive, Sheets, Calendar, Gmail, Docs integration",
        "tools": "gws CLI (22 tools) + NuzMCP: drive/sheets tools + Google Workspace MCP",
        "best_handler": "orchestrator",  # Orchestrator calls gws service
        "keywords": ["drive", "sheets", "calendar", "google", "spreadsheet", "gmail", "email"],
    },
    "browser": {
        "description": "Web automation, scraping, visual QA",
        "tools": "Claude-in-Chrome MCP + Playwright MCP + OpenClaw browser-use",
        "best_handler": "orchestrator",
        "keywords": ["browser", "screenshot", "scrape", "web", "click", "navigate"],
    },

    # --- Workflows & Automation ---
    "workflows": {
        "description": "Deterministic multi-step automation chains",
        "tools": "NuzMCP: chain_daily_ops_autopilot, chain_new_client_onboarding, chain_practice_lifecycle_check, chain_intel_pipeline, chain_weekly_report, chain_client_health_monitor, chain_compliance_autopilot, chain_journey_accelerator (8 chains)",
        "best_handler": "orchestrator",
        "keywords": ["workflow", "chain", "automazione", "pipeline", "autopilot", "onboarding"],
    },

    # --- Portal & Journey ---
    "portal": {
        "description": "Client portal, visa status, document management",
        "tools": "NuzMCP: get_portal_dashboard, get_portal_visa_status, get_portal_timeline, list_portal_documents, send_portal_message (6 tools)",
        "best_handler": "orchestrator",
        "keywords": ["portal", "portale", "visa status", "document", "journey"],
    },

    # --- Observability ---
    "observability": {
        "description": "LangSmith tracing, query analytics, admin logs",
        "tools": "NuzMCP: langsmith_project_stats, langsmith_recent_runs + get_query_analytics, get_failed_queries + LangSmith MCP",
        "best_handler": "orchestrator",
        "keywords": ["langsmith", "tracing", "log", "admin", "analytics", "monitoring"],
    },

    # --- Deep Research ---
    "research": {
        "description": "Deep web research with auto-import, NLM synthesis, Exa/Brave citations",
        "tools": "NLM: research_start, cross_notebook_query + Exa MCP + Brave API",
        "best_handler": "orchestrator",  # Orchestrator calls NLM service + websearch service
        "keywords": ["research", "ricerca", "deep research", "investigate", "indaga", "fonti", "sources"],
    },

    # --- Reasoning ---
    "reasoning": {
        "description": "Complex architecture decisions, trade-off analysis, migration strategies",
        "tools": "DeepSeek R1 671b API (chain-of-thought with 27K+ reasoning tokens)",
        "best_handler": "deepseek-reasoning",  # Agent: needs deep reasoning
        "keywords": [
            "architecture decision", "design pattern", "migration strategy",
            "complex debug", "chain of thought", "step by step", "reasoning",
            "trade-off", "pros and cons", "compare approaches",
        ],
    },

    # --- Translation & OCR ---
    "translation": {
        "description": "Indonesian-English translation for documents, articles, client comms",
        "tools": "Google Cloud Translation API (200+ languages) + Gemini inline translation",
        "best_handler": "orchestrator",
        "keywords": ["translate", "traduci", "translation", "traduzione", "Indonesian", "English", "bahasa"],
    },
    "document-ocr": {
        "description": "Advanced OCR for Indonesian documents (passports, KITAS, contracts)",
        "tools": "OCR Tesseract MCP + Google Cloud Document AI",
        "best_handler": "orchestrator",  # Orchestrator calls ocr service
        "keywords": ["OCR", "scan", "passaporto", "passport", "document scan", "extract text"],
    },

    # --- Reputation ---
    "reputation": {
        "description": "Google Business Profile: reviews, posts, Q&A, insights",
        "tools": "GBP API: reviews, localPosts, questions, reportInsights + Places API",
        "best_handler": "orchestrator",
        "keywords": ["review", "recensione", "Google Business", "GBP", "listing", "reputation", "local SEO"],
    },

    # --- Media Generation ---
    "media-generation": {
        "description": "AI image generation (Imagen 4) and video generation (Veo 3)",
        "tools": "google-genai SDK: Imagen 4 ($0.03/img), Veo 3 ($0.35/sec) + Canva MCP",
        "best_handler": "orchestrator",  # Orchestrator calls canva service + genai SDK
        "keywords": ["image", "immagine", "generate image", "video", "Imagen", "Veo", "Canva", "design"],
    },

    # --- GPU Compute ---
    "gpu-compute": {
        "description": "Remote GPU runtime for ML inference, training, heavy computation",
        "tools": "Google Colab MCP: execute_code, create_notebook, pip_install",
        "best_handler": "orchestrator",
        "keywords": ["GPU", "training", "inference", "Colab", "compute", "ML"],
    },
}


# ═══════════════════════════════════════════════════════
# Backward compatibility: best_agent → best_handler
# Some code still references best_agent in CAPABILITY_DOMAINS.
# This ensures it works with both old and new field names.
# ═══════════════════════════════════════════════════════
for _domain_id, _domain_info in CAPABILITY_DOMAINS.items():
    if "best_handler" in _domain_info and "best_agent" not in _domain_info:
        _domain_info["best_agent"] = _domain_info["best_handler"]


# ═══════════════════════════════════════════════════════
# OpenClaw Skills — additional capabilities
# ═══════════════════════════════════════════════════════
OPENCLAW_SKILLS = {
    "antigravity-bridge": "Bridge between OpenClaw and Antigravity IDE for cross-IDE task injection",
    "api-gateway": "Connect to 100+ APIs (Google Workspace, Notion, Slack, Airtable, HubSpot) with managed OAuth",
    "browser-use": "Browser automation for web testing, form filling, screenshots, data extraction",
    "bz-newsroom": "Multi-agent marketing & journalism pipeline: research → brainstorm → creative → design",
    "coding-orchestrator": "Orchestrate coding tasks across agents when feature touches multiple apps",
    "crm-query": "Natural language → SQL against CRM PostgreSQL (read-only)",
    "cursor-cloud-agent": "Launch Cursor cloud agents for long-running background coding tasks (GPT-5)",
    "desktop-control": "Advanced desktop automation with mouse, keyboard, and screen control",
    "google-labs-flow": "Automate Google Labs Flow (AI filmmaking & storyboarding) via browser relay",
    "kbli-validator": "Validate KBLI 2025 codes from business descriptions with risk + PMA eligibility",
    "ontology": "Typed knowledge graph for structured agent memory and composable skills",
    "proactive-agent": "Transform agents into proactive partners that anticipate needs",
    "self-improving-agent": "Captures learnings, errors, corrections for continuous improvement",
    "tmux-coding-agents": "Spawn Claude Code, Gemini CLI, Kimi in tmux for parallel coding",
    "war-room-crew": "AI content pipeline: Preflight → Intel → Strategy → Creative → Production",
}

# ═══════════════════════════════════════════════════════
# Gemini CLI Tools (built-in + extensions)
# ═══════════════════════════════════════════════════════
GEMINI_TOOLS = {
    # Built-in tools
    "shell": "Execute shell commands",
    "read_file": "Read file contents",
    "write_file": "Write file contents",
    "edit_file": "Edit file with search/replace",
    "list_dir": "List directory contents",
    "google_web_search": "Google Search with grounded citations",
    "codebase_investigator": "Deep codebase analysis with 1M context",
    "memorize": "Save information to memory",
    "recall": "Recall saved information",
    "glob": "File pattern matching",
    "grep": "Content search",
    # Extensions (installed but disabled — can be enabled)
    "ext:advanced-seo-mcp": "SEO analysis and optimization (MCP)",
    "ext:co-researcher": "15 research skills: systematic review, literature, hypothesis, ethics",
    "ext:google-maps-platform": "Google Maps Platform APIs via MCP",
    "ext:google-workspace": "Gmail, Calendar, Drive, Docs via MCP",
    "ext:google-workspace-inbox": "Email inbox management",
}


# ═══════════════════════════════════════════════════════
# NotebookLM MCP Tools (35 tools via notebooklm-mcp-cli)
# ═══════════════════════════════════════════════════════
NOTEBOOKLM_TOOLS = {
    "notebook_list": "List all notebooks",
    "notebook_create": "Create a new notebook",
    "notebook_delete": "Delete a notebook",
    "notebook_get": "Get notebook details",
    "source_add": "Add source (file, url, text, youtube, drive)",
    "source_list": "List sources in a notebook",
    "source_delete": "Delete a source",
    "source_refresh": "Refresh source content",
    "notebook_query": "Chat with notebook sources (grounded, cited)",
    "cross_notebook_query": "Query across multiple notebooks simultaneously",
    "research_start": "Trigger autonomous Deep Research (web search, 80+ sources)",
    "research_status": "Check Deep Research progress",
    "research_import": "Import research results into notebook",
    "studio_create": "Generate: audio, podcast, video, quiz, flashcards, mind_map, study_guide, slides, infographic, timeline",
    "studio_status": "Check studio generation status",
    "download_artifact": "Download generated artifacts (MP3, PDF, PNG, JSON, CSV, PPTX)",
    "pipeline": "Multi-step workflows (create → add sources → query → generate)",
    "batch": "Batch operations across notebooks",
    "login": "Browser-based Google auth (one-time)",
    "profile_list": "List authenticated Google profiles",
    "profile_switch": "Switch active profile",
}

# ═══════════════════════════════════════════════════════
# Google Workspace CLI (gws) — unified Workspace access
# ═══════════════════════════════════════════════════════
GWS_TOOLS = {
    "gmail_send": "Send email with attachments",
    "gmail_search": "Search emails by query",
    "gmail_list": "List recent emails",
    "gmail_draft": "Create email draft",
    "drive_list": "List files in folder",
    "drive_upload": "Upload file to Drive",
    "drive_download": "Download file from Drive",
    "drive_mkdir": "Create Drive folder",
    "drive_search": "Search files by name/content",
    "calendar_create": "Create calendar event",
    "calendar_list": "List events",
    "calendar_freebusy": "Check availability",
    "sheets_read": "Read spreadsheet range",
    "sheets_write": "Write to spreadsheet",
    "sheets_append": "Append row to sheet",
    "sheets_find": "Search in spreadsheet",
    "docs_create": "Create Google Doc",
    "docs_append": "Append content to Doc",
    "docs_export": "Export Doc to PDF/text",
    "admin_users_list": "List Workspace users",
    "admin_users_update": "Update user settings",
    "chat_send": "Send Google Chat message",
}

# ═══════════════════════════════════════════════════════
# Google SDK/APIs installed (usable on-demand)
# ═══════════════════════════════════════════════════════
GOOGLE_SDKS = {
    "google-adk": "Agent Development Kit — multi-agent graphs, native MCP, model-agnostic",
    "a2a-sdk": "Agent-to-Agent Protocol — agent discovery, task lifecycle, streaming, push notifications",
    "google-cloud-translate": "Cloud Translation API — 200+ languages, ID↔EN critical for Bali Zero",
    "google-cloud-documentai": "Document AI — OCR 200+ languages, superior Indonesian doc processing",
    "google-genai": "Gemini API SDK — Imagen 4 (images), Veo 3 (video), Deep Research, grounding",
    "google-colab-mcp": "Colab MCP — remote GPU runtime from any agent",
    "google-api-python-client": "Google APIs — GBP (Business Profile), YouTube, Contacts, Forms, etc.",
}


# ═══════════════════════════════════════════════════════
# Routing functions — used by orchestrator + classifier
# ═══════════════════════════════════════════════════════

def build_classifier_context() -> str:
    """Build the capability context string for the Qwen classifier prompt."""
    lines = ["# Federation Capability Table v3\n"]

    lines.append("## Dispatchable Agents\n")
    for agent_id, info in AGENTS.items():
        caps = ", ".join(info.get("capabilities", info["strengths"])[:4])
        lines.append(f"- **{agent_id}**: {info['role']} — {caps}")

    lines.append("\n## Services (called by orchestrator, NOT dispatchable)\n")
    for svc_id, info in SERVICES.items():
        lines.append(f"- **{svc_id}**: {info['role']}")

    lines.append("\n## Domain → Handler Routing\n")
    for domain, info in CAPABILITY_DOMAINS.items():
        kw = ", ".join(info["keywords"][:5])
        handler = info["best_handler"]
        lines.append(f"- **{domain}** ({kw}) → {handler}")

    return "\n".join(lines)


def match_domains(task: str) -> list[str]:
    """Match task text against domain keywords. Returns matched domain names."""
    task_lower = task.lower()
    matches = []
    for domain, info in CAPABILITY_DOMAINS.items():
        for kw in info["keywords"]:
            if kw.lower() in task_lower:
                matches.append(domain)
                break
    return matches


def suggest_agents(task: str) -> dict[str, bool]:
    """Suggest which agents/services to use based on keyword matching.

    Returns dict with dispatch flags for agents and service needs.
    This is a heuristic fallback — the Qwen classifier should override this.
    """
    domains = match_domains(task)
    handlers = {CAPABILITY_DOMAINS[d]["best_handler"] for d in domains}

    task_lower = task.lower()

    # Keyword-based detection beyond domain matching
    reasoning_keywords = ["architecture decision", "design pattern", "migration strategy",
                          "complex debug", "chain of thought", "step by step", "reasoning",
                          "trade-off", "pros and cons", "compare approaches"]
    oracolo_keywords = ["how does", "come funziona", "trace the flow", "file path",
                        "which module", "import chain", "dependency"]
    websearch_keywords = ["latest", "current regulation", "2026 update", "web search",
                          "find sources", "citations", "aggiornamento"]
    aider_keywords = ["quick fix", "fix this", "small change", "one-line", "typo"]

    needs_reasoning = any(kw in task_lower for kw in reasoning_keywords)
    needs_oracolo = any(kw in task_lower for kw in oracolo_keywords)
    needs_websearch = any(kw in task_lower for kw in websearch_keywords)
    needs_aider = any(kw in task_lower for kw in aider_keywords)

    return {
        # Agent dispatch flags
        "needs_search": "gemini-search" in handlers,
        "needs_explore": "gemini-explore" in handlers,
        "needs_sandbox": "codex-sandbox" in handlers,
        "needs_reasoning": needs_reasoning or "deepseek-reasoning" in handlers,
        "needs_redteam": "claude-review" in handlers,
        "needs_aider": needs_aider,
        # Service flags (orchestrator calls these directly)
        "needs_websearch": needs_websearch,
        "needs_oracolo": needs_oracolo,
        "needs_oracolo_nb": False,  # Requires explicit domain tag
        "needs_notebook": "notebooklm" in handlers if False else any(  # NLM is a service now
            d in domains for d in ["research", "knowledge"]
        ),
        "needs_gws": any(d in domains for d in ["google-workspace", "comms"]),
        "needs_war_room": "content-creation" in domains,
    }


# ═══════════════════════════════════════════════════════
# Summary stats
# ═══════════════════════════════════════════════════════
ARSENAL_SUMMARY = {
    "agents": len(AGENTS),
    "services": len(SERVICES),
    "pipelines": len(PIPELINES),
    "nuzmcp_tools": 109,
    "nuzmcp_modules": 20,
    "nuzmcp_advanced_tools": 13,
    "notebooklm_tools": len(NOTEBOOKLM_TOOLS),
    "gws_tools": len(GWS_TOOLS),
    "google_sdks": len(GOOGLE_SDKS),
    "openclaw_skills": len(OPENCLAW_SKILLS),
    "gemini_tools": len(GEMINI_TOOLS),
    "claude_code_mcp_servers": 8,
    "workflow_chains": 8,
    "capability_domains": len(CAPABILITY_DOMAINS),
    "total_capabilities": (
        109 + 13 + len(NOTEBOOKLM_TOOLS) + len(GWS_TOOLS) + len(GOOGLE_SDKS)
        + len(OPENCLAW_SKILLS) + len(GEMINI_TOOLS) + 8 + 8
    ),
}


if __name__ == "__main__":
    print(build_classifier_context())
    print(f"\n\n--- Arsenal Summary (v3) ---")
    for k, v in ARSENAL_SUMMARY.items():
        print(f"  {k}: {v}")
    print(f"\n--- Tier Breakdown ---")
    print(f"  AGENTS ({len(AGENTS)}):    {', '.join(AGENTS.keys())}")
    print(f"  SERVICES ({len(SERVICES)}):  {', '.join(SERVICES.keys())}")
    print(f"  PIPELINES ({len(PIPELINES)}): {', '.join(PIPELINES.keys())}")
