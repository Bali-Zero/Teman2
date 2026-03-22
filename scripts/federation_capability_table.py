"""
Federation Capability Table — Maps the complete Nuzantara AI arsenal.

Used by the federation orchestrator to provide Qwen classifier with
routing context. Each capability has: agent, tool_type, domain tags,
and when_to_use description for intelligent dispatch.

Arsenal inventory (2026-03-23):
  - 109 NuzMCP tools (20 modules)
  - 13 NuzMCP-Advanced tools
  - 16 OpenClaw skills
  - 5 Gemini CLI extensions
  - 18 Gemini built-in tools
  - 7 Claude Code MCP servers
  - 5 AI dispatch commands
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

    Returns dict with needs_search, needs_explore, needs_sandbox, needs_redteam.
    This is a heuristic fallback — the Qwen classifier should override this.
    """
    domains = match_domains(task)
    best_agents = {CAPABILITY_DOMAINS[d]["best_agent"] for d in domains}

    return {
        "needs_search": "gemini-search" in best_agents,
        "needs_explore": "gemini-explore" in best_agents,
        "needs_sandbox": "codex-sandbox" in best_agents,
        "needs_redteam": "claude-review" in best_agents,
    }


# ═══════════════════════════════════════════════════════
# Summary stats
# ═══════════════════════════════════════════════════════
ARSENAL_SUMMARY = {
    "nuzmcp_tools": 109,
    "nuzmcp_modules": 20,
    "nuzmcp_advanced_tools": 13,
    "openclaw_skills": len(OPENCLAW_SKILLS),
    "gemini_tools": len(GEMINI_TOOLS),
    "claude_code_mcp_servers": 7,
    "dispatch_commands": 5,
    "workflow_chains": 8,
    "total_capabilities": 109 + 13 + len(OPENCLAW_SKILLS) + len(GEMINI_TOOLS) + 7 + 5 + 8,
}


if __name__ == "__main__":
    print(build_classifier_context())
    print(f"\n\n--- Arsenal Summary ---")
    for k, v in ARSENAL_SUMMARY.items():
        print(f"  {k}: {v}")
