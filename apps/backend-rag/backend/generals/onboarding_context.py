"""
Onboarding Context - AI_ONBOARDING as DNA for every General.

Every General MUST load and respect these rules before executing any task.
This is the constitution of the Nuzantara project.

Reference: docs/AI_ONBOARDING.md
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve AI_ONBOARDING.md path — works in both local dev and Docker.
# Walk up from this file until we find docs/AI_ONBOARDING.md or hit root.
_THIS_FILE = Path(__file__).resolve()


def _find_onboarding_path() -> Path:
    """Walk ancestors to find docs/AI_ONBOARDING.md."""
    current = _THIS_FILE.parent
    while current != current.parent:  # stop at filesystem root
        candidate = current / "docs" / "AI_ONBOARDING.md"
        if candidate.exists():
            return candidate
        current = current.parent
    # Fallback: relative to backend-rag root (may not exist in Docker)
    return _THIS_FILE.parent.parent.parent / "docs" / "AI_ONBOARDING.md"


_ONBOARDING_PATH = _find_onboarding_path()
_BACKEND_ROOT = _THIS_FILE.parent.parent.parent  # backend-rag/ (local) or /app/ (Docker)


def load_onboarding_document() -> str:
    """Load the full AI_ONBOARDING.md document."""
    try:
        return _ONBOARDING_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"⚠️ AI_ONBOARDING.md not found at {_ONBOARDING_PATH}")
        return ""


# ──────────────────────────────────────────────────────────
# THE GOLDEN RULES - Extracted as enforceable constants
# ──────────────────────────────────────────────────────────

VIRTUALENV_PATH = _BACKEND_ROOT / ".venv"

GOLDEN_RULES = {
    "virtualenv_mandatory": True,
    "no_root_execution": True,
    "absolute_imports_only": True,
    "async_first": True,
    "type_hints_required": True,
    "no_hardcoding": True,
    "separation_of_data_and_logic": True,
    "clean_logging": True,  # logger.info(), never logger.info()
    "quality_standard": True,
}

# Critical knowledge that prevents real bugs
CRITICAL_KNOWLEDGE = {
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536,
    "kbli_collection": "kbli_2025_final",
    "kbli_payload_structure": "flat",  # NOT nested under metadata/text
    "pricing_source": "PricingTool only",  # NEVER from KG fees
    "production_app": "nuzantara-rag",
    "production_region": "sin",  # Singapore
}

# Working directory rules
WORKING_DIRS = {
    "backend": str(_BACKEND_ROOT),
    "project_root": str(_ONBOARDING_PATH.parent.parent)
    if _ONBOARDING_PATH.exists()
    else str(_BACKEND_ROOT.parent),
    "virtualenv": str(VIRTUALENV_PATH),
}

# Pre-commit checklist for code tasks
PRE_EXECUTION_CHECKLIST = [
    "Virtualenv activated",
    "All new functions have type hints",
    "No hardcoded secrets or URLs",
    "Used async/await (no blocking calls)",
    "Absolute imports only",
    "Tests pass for modified code",
]


# ──────────────────────────────────────────────────────────
# ENFORCEMENT: Pre-flight checks for CodingGeneral
# ──────────────────────────────────────────────────────────


def validate_command(command: str) -> tuple[bool, str | None]:
    """
    Validate a shell command against Golden Rules.

    Returns:
        Tuple of (is_valid, warning_message)
    """
    warnings: list[str] = []

    # Rule: No hardcoded secrets
    secret_patterns = ["sk-", "api_key=", "password=", "token=", "secret="]
    for pattern in secret_patterns:
        if pattern in command.lower():
            warnings.append(f"⚠️ Possible hardcoded secret detected: '{pattern}'")

    # Rule: Prefer virtualenv Python
    if "python" in command and ".venv" not in command and "python3 -m" not in command:
        warnings.append(
            "⚠️ Using system Python instead of virtualenv. "
            f"Prefer: source {VIRTUALENV_PATH}/bin/activate && {command}"
        )

    # Rule: No logger.info() in production code
    if "logger.info(" in command and "python" in command:
        warnings.append("⚠️ Using logger.info() instead of logger. Use logging module.")

    if warnings:
        return True, " | ".join(warnings)  # Allow but warn
    return True, None


def get_enforced_env() -> dict[str, str]:
    """
    Return environment variables that enforce Golden Rules.

    These are merged into the execution environment of every command.
    """
    import os

    env = dict(os.environ)

    # Ensure PYTHONPATH includes backend root
    pythonpath = env.get("PYTHONPATH", "")
    backend_str = str(_BACKEND_ROOT)
    if backend_str not in pythonpath:
        env["PYTHONPATH"] = f"{backend_str}:{pythonpath}" if pythonpath else backend_str

    # Ensure virtualenv is in PATH
    venv_bin = str(VIRTUALENV_PATH / "bin")
    path = env.get("PATH", "")
    if venv_bin not in path:
        env["PATH"] = f"{venv_bin}:{path}"

    return env


def get_working_directory(task_payload: dict[str, Any]) -> str:
    """
    Determine the correct working directory for a task.

    Defaults to backend root (apps/backend-rag/) unless explicitly overridden.
    """
    custom_dir = task_payload.get("working_dir")
    if custom_dir:
        return custom_dir
    return str(_BACKEND_ROOT)


# ──────────────────────────────────────────────────────────
# CONTEXT: System instruction for IntelligenceGeneral
# ──────────────────────────────────────────────────────────


def get_intelligence_system_instruction() -> str:
    """
    Build system instruction for Intelligence General that includes
    AI_ONBOARDING context as mandatory knowledge.
    """
    onboarding_doc = load_onboarding_document()

    # Extract the essential rules for the LLM context
    return f"""You are an intelligence analyst for Project Nuzantara (Bali Zero).

## YOUR CONSTITUTION (from AI_ONBOARDING.md)

You MUST follow these rules in ALL your analysis and code output:

### Golden Rules
1. VIRTUALENV IS MANDATORY - Always reference .venv paths
2. NO ROOT EXECUTION - Use `python -m backend.scripts.script_name`
3. ABSOLUTE IMPORTS ONLY - `from backend.core import config` (never relative)
4. ASYNC FIRST - Use httpx, not requests. Use await, not blocking calls.
5. TYPE HINTS REQUIRED on all functions
6. NO HARDCODING - Secrets from env vars, data from Qdrant/Postgres
7. SEPARATION OF DATA AND LOGIC - Volatile data in KB, logic in services
8. CLEAN LOGGING - logger.info(), never logger.info()
9. QUALITY STANDARD - Tests, logging, error handling, type hints

### Critical Knowledge (prevents real bugs)
- Embedding model MUST be `text-embedding-3-small` (1536 dims)
- KBLI collection has FLAT payload (NOT nested under metadata/text)
- Pricing comes ONLY from PricingTool (never from KG fees)
- Production: nuzantara-rag on Fly.io (Singapore)

### Project Structure
- Backend: apps/backend-rag/backend/
- Services: backend/services/ (228 files)
- Routers: backend/app/routers/ (68 files)
- Tests: backend/tests/ (477 files)
- Frontend: apps/mouth/ (Next.js on Vercel)

### Your Role
- Provide comprehensive, accurate research reports
- Analyze queries thoroughly with actionable insights
- Cite sources when available
- Structure responses clearly
- Be concise but complete
- ANY code you suggest MUST follow the Golden Rules above

{"### Full Onboarding Reference (truncated)" if len(onboarding_doc) > 5000 else ""}
"""


# ──────────────────────────────────────────────────────────
# LOGGING: Compliance check results
# ──────────────────────────────────────────────────────────


def log_onboarding_compliance(general_name: str) -> None:
    """Log that a General has loaded onboarding context."""
    onboarding_exists = _ONBOARDING_PATH.exists()
    logger.info(
        f"📋 {general_name}: AI_ONBOARDING loaded={'✅' if onboarding_exists else '❌'} "
        f"path={_ONBOARDING_PATH} "
        f"golden_rules={len(GOLDEN_RULES)} "
        f"critical_knowledge={len(CRITICAL_KNOWLEDGE)}"
    )
