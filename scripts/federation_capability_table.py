"""
Federation Capability Table — Maps the complete Nuzantara AI arsenal.

Used by the federation orchestrator to provide Qwen classifier with
routing context. Each capability has: agent, tool_type, domain tags,
and when_to_use description for intelligent dispatch.

Arsenal inventory (2026-03-23, v2):
  - 109 NuzMCP tools (20 modules)
  - 13 NuzMCP-Advanced tools
  - 35 NotebookLM MCP tools (notebooks, sources, studio, research, pipeline, batch)
  - 16 OpenClaw skills
  - 5 Gemini CLI extensions
  - 16 Gemini built-in tools
  - 8 Claude Code MCP servers (+ google-colab)
  - 5 AI dispatch commands
  - 12 Google SDK/APIs installed (ADK, A2A, Translation, DocumentAI, etc.)
  - gws CLI (unified Google Workspace)
  - GBP API (Google Business Profile)
"""

# ═══════════════════════════════════════════════════════
# Agent Profiles — WHO can do WHAT
# ═══════════════════════════════════════════════════════
AGENTS = {
    "claude-code": {
        "name": "Claude Code (Opus 4.6)",
        "role": "Il Re — orchestra, sintetizza, decide, esegue",
        "strengths": [
            "multi-file refactor", "deploy pipeline", "architectural decisions",
            "complex debugging", "test writing", "code review synthesis",
        ],
        "limits": "max 200K context window, no Google Search",
        "cost": "$$$",
        "dispatch_cmd": None,  # Direct execution, no dispatch
    },
    "gemini-search": {
        "name": "Gemini 3.1 Pro (Search)",
        "role": "Il Consigliere — grounded web search",
        "strengths": [
            "Indonesian regulations", "KBLI 2025", "visa rules", "tax law",
            "competitor research", "market data", "news", "citations with sources",
        ],
        "limits": "read-only, no code execution",
        "cost": "$0 (Google AI Ultra)",
        "dispatch_cmd": "search",
    },
    "gemini-explore": {
        "name": "Gemini 3.1 Pro (Explore)",
        "role": "Il Consigliere — 1M context codebase analysis",
        "strengths": [
            "cross-app dependency mapping", "large refactor planning",
            "codebase_investigator tool", "reading 100+ files at once",
            "architecture review", "import chain analysis",
        ],
        "limits": "read-only, sandbox mode, no writes",
        "cost": "$0 (Google AI Ultra)",
        "dispatch_cmd": "explore",
    },
    "codex-sandbox": {
        "name": "Codex 5.4 (Sandbox)",
        "role": "Il Soldato — kernel-level sandbox execution",
        "strengths": [
            "DB migrations (alembic)", "schema changes", "risky code execution",
            "isolated testing", "upgrade/downgrade verification",
        ],
        "limits": "sandbox only, no network access, single file changes",
        "cost": "$0 (OpenAI free tier)",
        "dispatch_cmd": "sandbox",
    },
    "claude-review": {
        "name": "Claude CLI (Opus 4.6)",
        "role": "Il Giudice — code review, red team",
        "strengths": [
            "security review", "pre-deploy audit", "logic errors",
            "red team analysis", "architectural critique",
        ],
        "limits": "read-only (plan mode), no code execution",
        "cost": "$0 (Max plan)",
        "dispatch_cmd": "claude-redteam",
    },
    "aider": {
        "name": "Aider (OpenRouter/DeepSeek)",
        "role": "Il Mercenario — multi-model coding",
        "strengths": [
            "quick targeted fixes", "single-file refactors",
            "DeepSeek V3 for cost-effective coding", "Sonnet for refactors",
        ],
        "limits": "no orchestration awareness, single-task focus",
        "cost": "$ (OpenRouter rates)",
        "dispatch_cmd": "aider-fix",
    },
    "notebooklm": {
        "name": "NotebookLM (Google AI Ultra)",
        "role": "L'Oracolo — knowledge synthesis with citations",
        "strengths": [
            "multi-document synthesis with exact citations",
            "cross-domain query (5+ notebooks in 1 call)",
            "Deep Research (autonomous web search, 120/day)",
            "audio/podcast generation", "quiz/flashcard/mind map generation",
        ],
        "limits": "3-15s latency, cookie auth fragile, 50 sources/notebook, no live DB access",
        "cost": "$0 (Google AI Ultra subscription)",
        "dispatch_cmd": "nlm-query",
    },
    "gws": {
        "name": "Google Workspace CLI (gws)",
        "role": "Il Segretario — unified Google Workspace automation",
        "strengths": [
            "Gmail send/search", "Drive CRUD", "Calendar events/free-busy",
            "Sheets read/write/append", "Docs create/export", "Admin user management",
        ],
        "limits": "requires Google Workspace account, CLI tool",
        "cost": "$0 (already paying Workspace)",
        "dispatch_cmd": "gws",
    },
}

# ═══════════════════════════════════════════════════════
# Capability Domains — WHAT exists in the arsenal
# ═══════════════════════════════════════════════════════
CAPABILITY_DOMAINS = {
    # --- Business Intelligence ---
    "crm": {
        "description": "Client management, profiles, practices, invoicing",
        "tools": "NuzMCP: list_clients, get_client, create_client, update_client, get_client_stats, get_client_timeline, get_client_compliance (12 tools)",
        "best_agent": "claude-code",
        "keywords": ["client", "cliente", "CRM", "practice", "fattura", "invoice"],
    },
    "compliance": {
        "description": "Visa expiry alerts, document tracking, regulatory compliance",
        "tools": "NuzMCP: get_compliance_alerts, track_compliance, get_expiry_alerts, get_compliance_summary (4 tools)",
        "best_agent": "claude-code",
        "keywords": ["compliance", "expiry", "scadenza", "document", "rinnovo"],
    },
    "intel": {
        "description": "News intelligence, scraping, trend analysis",
        "tools": "NuzMCP: search_intel, publish_intel, get_intel_trends, get_intel_metrics, submit_scraper_job (8 tools)",
        "best_agent": "claude-code",
        "keywords": ["intel", "news", "notizia", "scraping", "trend"],
    },
    "analytics": {
        "description": "Revenue, productivity, GA4, SEO metrics",
        "tools": "NuzMCP: get_revenue_analytics, get_team_productivity, get_completion_rates + GA4 MCP (8 tools) + GSC MCP (19 tools)",
        "best_agent": "claude-code",
        "keywords": ["analytics", "revenue", "fatturato", "metrics", "GA4", "SEO", "GSC"],
    },

    # --- Knowledge & Regulations ---
    "regulations": {
        "description": "Indonesian law, KBLI codes, visa rules, tax, permits",
        "tools": "NuzMCP: search_kbli, chat_kbli, inspect_kbli, ask_legal, list_visa_types, get_visa_details + Gemini Search",
        "best_agent": "gemini-search",
        "keywords": ["KBLI", "visa", "KITAS", "KITAP", "PMA", "tax", "pajak", "regulation", "normativa", "legge", "permit", "izin"],
    },
    "knowledge": {
        "description": "Knowledge base queries, legal docs, vector search",
        "tools": "NuzMCP: recall_similar, search_kbli, ask_legal (7 tools)",
        "best_agent": "claude-code",
        "keywords": ["knowledge", "RAG", "search", "cerca", "ask"],
    },
    "pricing": {
        "description": "Service pricing, calculations, quotes",
        "tools": "NuzMCP: calculate_pricing, get_all_prices, search_service_pricing (3 tools)",
        "best_agent": "claude-code",
        "keywords": ["price", "prezzo", "pricing", "quote", "preventivo", "costo"],
    },

    # --- Communications ---
    "comms": {
        "description": "Email, WhatsApp, Telegram, portal messaging",
        "tools": "NuzMCP: send_email, send_whatsapp, send_portal_message, list_emails, search_emails, list_telegram_conversations (6 tools)",
        "best_agent": "claude-code",
        "keywords": ["email", "whatsapp", "telegram", "message", "messaggio", "send"],
    },

    # --- Content & Publishing ---
    "content": {
        "description": "Article composition, publishing, editorial pipeline",
        "tools": "NuzMCP: compose_article, publish_article, list_articles, get_article (6 tools) + OpenClaw: bz-newsroom, war-room-crew",
        "best_agent": "claude-code",
        "keywords": ["article", "articolo", "blog", "content", "editorial", "publish"],
    },

    # --- Infrastructure & DevOps ---
    "infrastructure": {
        "description": "Fly.io deploy, health checks, monitoring, logs",
        "tools": "NuzMCP-Advanced: check_fly_status, get_fly_logs, analyze_fly_health, check_deployment_readiness, execute_recovery_action (13 tools)",
        "best_agent": "claude-code",
        "keywords": ["fly", "deploy", "health", "log", "monitoring", "server", "infra"],
    },
    "codebase": {
        "description": "Multi-app analysis, dependency mapping, architecture review",
        "tools": "Gemini CLI: codebase_investigator (1M ctx) + NuzMCP-Advanced: search_codebase, get_file_structure, find_documentation",
        "best_agent": "gemini-explore",
        "keywords": ["codebase", "architecture", "dependency", "refactor", "multi-app", "monorepo"],
    },
    "database": {
        "description": "Alembic migrations, schema changes, DB operations",
        "tools": "Codex sandbox for safe migration testing + Claude Code for implementation",
        "best_agent": "codex-sandbox",
        "keywords": ["migration", "alembic", "schema", "database", "DB", "model", "table"],
    },
    "testing": {
        "description": "Running tests, coverage, quality checks",
        "tools": "NuzMCP-Advanced: run_backend_tests, run_linting, run_type_checking + Claude Code pytest",
        "best_agent": "claude-code",
        "keywords": ["test", "pytest", "coverage", "lint", "type check", "mypy", "ruff"],
    },

    # --- Security & Review ---
    "security": {
        "description": "Pre-deploy review, red team, vulnerability analysis",
        "tools": "Claude CLI: claude-redteam (Opus reasoning) + Claude CLI: claude-review",
        "best_agent": "claude-review",
        "keywords": ["security", "review", "red team", "vulnerability", "deploy", "audit"],
    },

    # --- Google & External ---
    "google-workspace": {
        "description": "Drive, Sheets, Calendar integration",
        "tools": "NuzMCP: drive (5 tools), sheets (4 tools) + Gemini ext: google-workspace",
        "best_agent": "claude-code",
        "keywords": ["drive", "sheets", "calendar", "google", "spreadsheet"],
    },
    "browser": {
        "description": "Web automation, scraping, visual QA",
        "tools": "OpenClaw: browser-use + Claude-in-Chrome MCP + Playwright MCP",
        "best_agent": "claude-code",
        "keywords": ["browser", "screenshot", "scrape", "web", "click", "navigate"],
    },

    # --- Workflows & Automation ---
    "workflows": {
        "description": "Deterministic multi-step automation chains",
        "tools": "NuzMCP: chain_daily_ops_autopilot, chain_new_client_onboarding, chain_practice_lifecycle_check, chain_intel_pipeline, chain_weekly_report, chain_client_health_monitor, chain_compliance_autopilot, chain_journey_accelerator (8 chains)",
        "best_agent": "claude-code",
        "keywords": ["workflow", "chain", "automazione", "pipeline", "autopilot", "onboarding"],
    },

    # --- Portale & Journey ---
    "portal": {
        "description": "Client portal, visa status, document management",
        "tools": "NuzMCP: get_portal_dashboard, get_portal_visa_status, get_portal_timeline, list_portal_documents, send_portal_message (6 tools)",
        "best_agent": "claude-code",
        "keywords": ["portal", "portale", "visa status", "document", "journey"],
    },

    # --- Memory & LangSmith ---
    "observability": {
        "description": "LangSmith tracing, query analytics, admin logs",
        "tools": "NuzMCP: langsmith_project_stats, langsmith_recent_runs, langsmith_run_detail + get_query_analytics, get_failed_queries, get_admin_logs + LangSmith MCP",
        "best_agent": "claude-code",
        "keywords": ["langsmith", "tracing", "log", "admin", "analytics", "monitoring"],
    },

    # --- NotebookLM (NEW) ---
    "notebook-research": {
        "description": "Deep web research with auto-import of sources into knowledge base",
        "tools": "NLM MCP: research_start (Deep Research, autonomous 80+ web searches), cross_notebook_query (multi-domain synthesis)",
        "best_agent": "notebooklm",
        "keywords": ["research", "ricerca", "deep research", "investigate", "indaga", "fonti", "sources"],
    },
    "notebook-synthesis": {
        "description": "Multi-document synthesis with exact citations from curated knowledge",
        "tools": "NLM MCP: notebook_query, cross_notebook_query (across 7+ domain notebooks)",
        "best_agent": "notebooklm",
        "keywords": ["synthesis", "sintesi", "compare", "confronta", "multi-domain", "cross-domain", "citazione", "citation"],
    },
    "notebook-media": {
        "description": "AI-generated audio podcasts, quizzes, flashcards, mind maps, study guides from knowledge",
        "tools": "NLM MCP: studio_create (audio/podcast/video), download_artifact (quiz/flashcard/mind_map/study_guide/timeline/slide_deck/infographic)",
        "best_agent": "notebooklm",
        "keywords": ["podcast", "audio", "quiz", "flashcard", "mind map", "study guide", "guida", "briefing"],
    },
    "notebook-management": {
        "description": "Create, populate, and manage knowledge notebooks",
        "tools": "NLM MCP: notebook_create, notebook_list, notebook_delete, source_add (file/url/text/youtube/drive), source_list, source_delete, pipeline, batch",
        "best_agent": "notebooklm",
        "keywords": ["notebook", "create notebook", "add source", "populate", "knowledge base"],
    },

    # --- Google Workspace unified (NEW) ---
    "email-automation": {
        "description": "Email send, search, draft, label management via gws CLI",
        "tools": "gws gmail send/search/list/draft + NuzMCP: send_email, search_emails, list_emails",
        "best_agent": "gws",
        "keywords": ["email", "gmail", "send email", "draft", "invia email", "posta"],
    },
    "calendar-scheduling": {
        "description": "Calendar events, free-busy check, appointment booking",
        "tools": "gws calendar create/list/free-busy + Google Calendar MCP (gcal_*)",
        "best_agent": "gws",
        "keywords": ["calendar", "appuntamento", "appointment", "meeting", "schedule", "disponibilità", "free time"],
    },
    "document-generation": {
        "description": "Create Google Docs, export PDF, proposals, reports, audit trails",
        "tools": "gws docs create/append/export + gws drive upload",
        "best_agent": "gws",
        "keywords": ["document", "documento", "PDF", "proposal", "preventivo", "report", "Google Doc", "audit trail"],
    },

    # --- Google Business Profile (NEW) ---
    "reputation": {
        "description": "Google Business Profile: reviews, posts, Q&A, insights, listing management",
        "tools": "GBP API: reviews.list/updateReply, localPosts.create, questions.answers.upsert, reportInsights + Places API for competitor monitoring",
        "best_agent": "claude-code",
        "keywords": ["review", "recensione", "Google Business", "GBP", "listing", "reputation", "local SEO", "Google Maps"],
    },

    # --- Translation & OCR (NEW) ---
    "translation": {
        "description": "Indonesian-English translation for documents, articles, client comms",
        "tools": "Google Cloud Translation API (200+ languages) + Gemini inline translation",
        "best_agent": "claude-code",
        "keywords": ["translate", "traduci", "translation", "traduzione", "Indonesian", "English", "bahasa"],
    },
    "document-ocr": {
        "description": "Advanced OCR for Indonesian documents (passports, KITAS, contracts, notarial acts)",
        "tools": "Google Cloud Document AI (200+ languages, superior to tesseract) + OCR Tesseract MCP (fallback)",
        "best_agent": "claude-code",
        "keywords": ["OCR", "scan", "passaporto", "passport", "document scan", "extract text"],
    },

    # --- AI Agent Framework (NEW) ---
    "agent-framework": {
        "description": "Multi-agent orchestration framework, agent-to-agent communication",
        "tools": "Google ADK (Agent Development Kit) for multi-agent graphs + A2A Protocol SDK for inter-agent communication + Agent Cards",
        "best_agent": "claude-code",
        "keywords": ["agent", "multi-agent", "A2A", "agent card", "orchestration", "framework", "ADK"],
    },

    # --- GPU Compute (NEW) ---
    "gpu-compute": {
        "description": "Remote GPU runtime for ML inference, training, heavy computation",
        "tools": "Google Colab MCP: execute_code, create_notebook, pip_install + Colab free/Pro GPU",
        "best_agent": "claude-code",
        "keywords": ["GPU", "training", "inference", "Colab", "compute", "ML", "machine learning"],
    },

    # --- Image & Video Generation (NEW) ---
    "media-generation": {
        "description": "AI image generation (Imagen 4) and video generation (Veo 3) for marketing",
        "tools": "google-genai SDK: Imagen 4 ($0.03/img), Veo 3 ($0.35/sec) + Canva MCP (20+ tools)",
        "best_agent": "claude-code",
        "keywords": ["image", "immagine", "generate image", "video", "Imagen", "Veo", "Canva", "design", "marketing visual"],
    },
}

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
    # Notebook CRUD
    "notebook_list": "List all notebooks",
    "notebook_create": "Create a new notebook",
    "notebook_delete": "Delete a notebook",
    "notebook_get": "Get notebook details",
    # Source management
    "source_add": "Add source (file, url, text, youtube, drive)",
    "source_list": "List sources in a notebook",
    "source_delete": "Delete a source",
    "source_refresh": "Refresh source content",
    # Querying
    "notebook_query": "Chat with notebook sources (grounded, cited)",
    "cross_notebook_query": "Query across multiple notebooks simultaneously",
    # Deep Research
    "research_start": "Trigger autonomous Deep Research (web search, 80+ sources)",
    "research_status": "Check Deep Research progress",
    "research_import": "Import research results into notebook",
    # Studio (media generation)
    "studio_create": "Generate: audio_overview, podcast, video, quiz, flashcards, mind_map, study_guide, slide_deck, infographic, timeline, data_table, report",
    "studio_status": "Check studio generation status",
    # Artifacts
    "download_artifact": "Download generated artifacts (MP3, PDF, PNG, JSON, CSV, PPTX)",
    # Automation
    "pipeline": "Multi-step workflows (create → add sources → query → generate)",
    "batch": "Batch operations across notebooks",
    # Authentication
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


def build_classifier_context() -> str:
    """Build the capability context string for the Qwen classifier prompt."""
    lines = ["# Federation Capability Table\n"]
    lines.append("## Agents\n")
    for agent_id, info in AGENTS.items():
        lines.append(f"- **{agent_id}**: {info['role']} — strengths: {', '.join(info['strengths'][:4])}")

    lines.append("\n## Domain → Best Agent Routing\n")
    for domain, info in CAPABILITY_DOMAINS.items():
        kw = ", ".join(info["keywords"][:5])
        lines.append(f"- **{domain}** ({kw}) → {info['best_agent']}")
        lines.append(f"  Tools: {info['tools'][:100]}")

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
    """Suggest which agents to dispatch based on keyword matching.

    Returns dict with dispatch flags for all agent types.
    This is a heuristic fallback — the Qwen classifier should override this.
    """
    domains = match_domains(task)
    best_agents = {CAPABILITY_DOMAINS[d]["best_agent"] for d in domains}

    return {
        "needs_search": "gemini-search" in best_agents,
        "needs_explore": "gemini-explore" in best_agents,
        "needs_sandbox": "codex-sandbox" in best_agents,
        "needs_redteam": "claude-review" in best_agents,
        "needs_notebook": "notebooklm" in best_agents,
        "needs_gws": "gws" in best_agents,
    }


# ═══════════════════════════════════════════════════════
# Summary stats
# ═══════════════════════════════════════════════════════
ARSENAL_SUMMARY = {
    "nuzmcp_tools": 109,
    "nuzmcp_modules": 20,
    "nuzmcp_advanced_tools": 13,
    "notebooklm_tools": len(NOTEBOOKLM_TOOLS),
    "gws_tools": len(GWS_TOOLS),
    "google_sdks": len(GOOGLE_SDKS),
    "openclaw_skills": len(OPENCLAW_SKILLS),
    "gemini_tools": len(GEMINI_TOOLS),
    "claude_code_mcp_servers": 8,  # +google-colab
    "dispatch_commands": 5,
    "workflow_chains": 8,
    "capability_domains": len(CAPABILITY_DOMAINS),
    "agents": len(AGENTS),
    "total_capabilities": (
        109 + 13 + len(NOTEBOOKLM_TOOLS) + len(GWS_TOOLS) + len(GOOGLE_SDKS)
        + len(OPENCLAW_SKILLS) + len(GEMINI_TOOLS) + 8 + 5 + 8
    ),
}


if __name__ == "__main__":
    print(build_classifier_context())
    print(f"\n\n--- Arsenal Summary ---")
    for k, v in ARSENAL_SUMMARY.items():
        print(f"  {k}: {v}")
