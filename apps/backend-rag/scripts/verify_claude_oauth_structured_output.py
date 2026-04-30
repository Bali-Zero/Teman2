#!/usr/bin/env python3
"""Verify that ClaudeOAuthChatModel supports `with_structured_output`.

Context: PR `solidify-rag-router` migrates the KG LangGraph router from
`json.loads(response.content)` to `llm.with_structured_output(QueryIntentSchema)`.
LangChain's default `with_structured_output` implementation requires either
native tool-calling (`bind_tools`) or JSON-mode support on the underlying
chat model. `ClaudeOAuthChatModel` shells out to the `claude` CLI as
text-in / text-out — neither path is implemented natively.

This script answers two questions:

1. **Static** — does the bound class implement `bind_tools` /
   `with_structured_output` overrides?
2. **Runtime** — if Claude CLI is available, does an actual structured-output
   round-trip return a valid `QueryIntentSchema`?

Run:

    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/verify_claude_oauth_structured_output.py

Exit codes:
- 0 — Claude OAuth path is structured-output-capable.
- 1 — Claude OAuth path is text-only; KG router will silently fall back to
       OpenAI / keyword detector. PR should document this and ensure
       `KG_REASONING_PROVIDER=openai` (or equivalent) on Fly.
- 2 — Could not import the module (bad venv).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _check_static() -> dict[str, bool]:
    """Inspect the class for tool-calling / structured-output hooks."""
    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    try:
        model = build_claude_oauth_chat_model(model="claude-sonnet-4-6")
    except Exception as exc:  # ImportError, missing langchain-core, etc.
        print(f"❌ Failed to build ClaudeOAuthChatModel: {type(exc).__name__}: {exc}")
        sys.exit(2)

    cls = type(model)
    base_method = getattr(cls.__base__, "with_structured_output", None)
    own_method = cls.__dict__.get("with_structured_output")

    overrides_with_structured = own_method is not None
    overrides_bind_tools = "bind_tools" in cls.__dict__
    has_with_structured_at_all = hasattr(model, "with_structured_output")

    print(f"  class:                       {cls.__module__}.{cls.__name__}")
    print(f"  base class:                  {cls.__base__.__module__}.{cls.__base__.__name__}")
    print(f"  has with_structured_output:  {has_with_structured_at_all}  (inherited from base if True)")
    print(f"  OVERRIDES with_structured:   {overrides_with_structured}")
    print(f"  OVERRIDES bind_tools:        {overrides_bind_tools}")
    print(f"  base.with_structured_output: {'present' if base_method else 'MISSING'}")

    return {
        "has_method": has_with_structured_at_all,
        "overrides_with_structured": overrides_with_structured,
        "overrides_bind_tools": overrides_bind_tools,
        "base_has_method": base_method is not None,
    }


def _check_runtime() -> bool:
    """Attempt a real structured-output call. Returns True on success."""
    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel, Field

    # Local copy of QueryIntentSchema to avoid importing the rag package
    # (which triggers Settings() validation requiring secrets in env).
    class QueryIntentSchema(BaseModel):
        intent: str = Field(description="Intent label")
        domain: str = Field(description="Domain label")
        entities: list[str] = Field(default_factory=list)
        citizenship: str = Field(default="domestic")

    model = build_claude_oauth_chat_model(model="claude-sonnet-4-6")

    try:
        structured = model.with_structured_output(QueryIntentSchema)
    except NotImplementedError as exc:
        print(f"❌ with_structured_output raised NotImplementedError: {exc}")
        return False
    except Exception as exc:
        print(f"❌ with_structured_output construction failed: {type(exc).__name__}: {exc}")
        return False

    print("  with_structured_output() returned an object — attempting call...")

    sys_msg = SystemMessage(
        content=(
            "Extract intent/domain/entities/citizenship as a JSON object. "
            "intent in {company_setup,visa,hire,property,tax,general}. "
            "domain in {visa,tax,property,kbli,company,general}."
        ),
    )
    user_msg = HumanMessage(content="Apa itu KITAS untuk foreign worker?")

    try:
        result = asyncio.run(structured.ainvoke([sys_msg, user_msg]))
    except Exception as exc:
        print(f"❌ ainvoke failed: {type(exc).__name__}: {exc}")
        return False

    if not isinstance(result, QueryIntentSchema):
        print(f"❌ Result is not a QueryIntentSchema (got {type(result).__name__}): {result!r}")
        return False

    print(f"✅ Got QueryIntentSchema: intent={result.intent} domain={result.domain} "
          f"entities={result.entities} citizenship={result.citizenship}")
    return True


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    _print_section("Static introspection")
    static = _check_static()

    static_ok = (
        static["has_method"]
        and (static["overrides_with_structured"] or static["overrides_bind_tools"])
    )

    if not static_ok:
        print(
            "\n⚠️  Static check: ClaudeOAuthChatModel inherits the BaseChatModel\n"
            "    default `with_structured_output`, which requires `bind_tools` /\n"
            "    function-calling. Neither is implemented on this subprocess wrapper.\n"
            "    The default path will likely raise NotImplementedError or coerce a\n"
            "    text response into JSON via prompt-engineering only.\n",
        )

    if os.getenv("VERIFY_RUN_CLAUDE_CALL") != "1":
        print(
            "\n(Skipping runtime call — set VERIFY_RUN_CLAUDE_CALL=1 to actually\n"
            " spawn `claude -p`. This consumes Max-plan quota.)\n",
        )
        return 0 if static_ok else 1

    _print_section("Runtime call (VERIFY_RUN_CLAUDE_CALL=1)")
    runtime_ok = _check_runtime()
    if not runtime_ok:
        print(
            "\n⚠️  Runtime check failed: structured output is not usable on the\n"
            "    Claude OAuth subprocess path. The KG router will hit\n"
            "    NotImplementedError and crash unless caller falls back. Ensure\n"
            "    `KG_REASONING_PROVIDER=openai` is set on Fly, or implement\n"
            "    `bind_tools` / `with_structured_output` overrides in\n"
            "    `backend/llm/claude_oauth_langchain.py` (e.g. via\n"
            "    `with_structured_output(method='function_calling')` shim that\n"
            "    prompts the CLI for JSON and parses it locally).\n",
        )
    return 0 if runtime_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
