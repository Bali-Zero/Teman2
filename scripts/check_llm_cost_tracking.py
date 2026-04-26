"""CI gate: every paid LLM/media client MUST call record_llm_call.

Scans a fixed set of directories, identifies files that perform paid API
calls, and fails with exit 1 if any such file lacks cost tracking.
See docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md §4.2.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCAN_ROOTS: list[str] = [
    "apps/backend-rag/backend/llm/",
    "apps/backend-rag/backend/services/llm_clients/",
    "apps/backend-rag/backend/services/visual/",
    "apps/backend-rag/backend/services/knowledge_graph/",
    "apps/backend-rag/backend/services/council/",
    "apps/backend-rag/backend/app/services/",
    "apps/backend-rag/backend/core/",
]

WHITELIST_SUBSTRINGS: list[str] = [
    "__init__.py",
    "__pycache__",
    "/base.py",
    "/config.py",
    "/pricing.py",
    "/fallback_messages.py",
    "/retry_handler.py",
    "/token_estimator.py",
    "/provider_registry.py",
    "/metrics_emitter.py",
    "/llm/adapters/",
    # OTEL/Langfuse instrumentation config — references provider names
    # for instrumentor wiring, never makes paid LLM calls itself.
    "core/observability.py",
    # Ollama (local, zero cost):
    "ollama_client.py",
    "llm/providers/ollama.py",
    # Proxies that delegate to already-tracked clients:
    "article_composer/claude_client.py",
    "llm/zantara_ai_client.py",
    "llm/claude_oauth_langchain.py",
    "llm/providers/gemini.py",
    "llm/providers/openrouter.py",
    "llm/providers/__init__.py",
    "services/llm_clients/gemini_service.py",
    # KG non-gemini files:
    "knowledge_graph/ontology.py",
    "knowledge_graph/coreference.py",
    "knowledge_graph/incremental_builder.py",
    # Test files under core/ dir (if any):
    "/tests/",
]

_PAID_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(anthropic|openai|google\.genai|google\.generativeai)\b",
    re.MULTILINE,
)
_PAID_URL_RE = re.compile(
    r"(api\.openai\.com|api\.deepseek\.com|openrouter\.ai/api|"
    r"generativelanguage\.googleapis|api\.anthropic\.com)",
)
_TRACKING_RE = re.compile(r"(record_llm_call|@llm_cost_tracked|llm_cost_tracked\()")


def is_paid_client(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(_PAID_IMPORT_RE.search(src) or _PAID_URL_RE.search(src))


def tracks_cost(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(_TRACKING_RE.search(src))


def _is_whitelisted(path: Path) -> bool:
    p = str(path)
    return any(s in p for s in WHITELIST_SUBSTRINGS)


def scan_files(roots: list[Path]) -> list[str]:
    violations: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if _is_whitelisted(path):
                continue
            if is_paid_client(path) and not tracks_cost(path):
                violations.append(str(path))
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    roots = [repo_root / r for r in SCAN_ROOTS]
    violations = scan_files(roots)
    if violations:
        sys.stderr.write("LLM cost tracking violations:\n")
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write(
            "\nEach file above makes paid API calls but does not call "
            "record_llm_call or use @llm_cost_tracked. Either add tracking "
            "or add the file to WHITELIST_SUBSTRINGS in "
            "scripts/check_llm_cost_tracking.py with a reason comment.\n"
        )
        return 1
    sys.stdout.write("All paid LLM clients track cost.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
