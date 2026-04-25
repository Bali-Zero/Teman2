"""
Zantara Core Prompt — v2 placeholder.

This module is the future home of the multi-language overhaul of
zantara_core.py. For now (PR-16a) it is a transparent re-export so the
ZANTARA_PROMPT_VERSION feature flag can be flipped between v1 and v2
without producing a behaviour change.

PR-16b will populate sections 1-7 (security, tool usage, system instructions,
knowledge governance, language protocol, greeting rules, citation rules)
using the multi-language pattern in backend.prompts.business_rules_i18n.

PR-17 will populate sections 8-14 (internal monologue, escalation, crash,
closing, creator persona, team persona, master template assembly).

Until those PRs land this file delegates to v1 — flipping the env var
ZANTARA_PROMPT_VERSION=v2 today is therefore a no-op.
"""

from backend.prompts.zantara_core import (  # noqa: F401 — re-exported for v1==v2 fallback
    CITATION_RULES,
    CLOSING_PHRASES,
    CRASH_PROTOCOL,
    CREATOR_PERSONA,
    ESCALATION_PROTOCOL,
    GREETING_RULES,
    INTERNAL_MONOLOGUE,
    KNOWLEDGE_GOVERNANCE,
    LANGUAGE_PROTOCOL,
    SECURITY_BOUNDARY,
    SYSTEM_INSTRUCTIONS,
    TEAM_PERSONA,
    TOOL_USAGE_POLICY,
    ZANTARA_MASTER_TEMPLATE,
)
