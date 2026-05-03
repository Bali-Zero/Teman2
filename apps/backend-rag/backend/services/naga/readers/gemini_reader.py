"""Gemini bulk reader — Pointer State Pattern.

Sends all sources into Gemini's 1M context window and extracts structured
evidence per sub-question.  The evidence map is persisted as a JSON file
on disk; the database stores only the file URI to avoid TOAST bloat on the
2 GB Fly.io PostgreSQL instance.

Usage::

    from backend.services.naga.readers.gemini_reader import gemini_bulk_read

    evidence_map, file_uri = await gemini_bulk_read(
        sub_questions=["What is KITAS?", "What is PT PMA?"],
        sources_content=[
            {"id": "s0", "url": "https://...", "content": "..."},
        ],
        generate_fn=my_gemini_wrapper,
        session_id="abc-123",
    )
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SOURCE_CHARS: int = 20_000
"""Maximum characters kept per source before truncation."""

_EMPTY_SUB_Q: dict[str, Any] = {
    "facts": [],
    "contradictions": [],
    "gaps": [],
    "data_points": [],
}

_CODE_BLOCK_RE: re.Pattern[str] = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def gemini_bulk_read(
    sub_questions: list[str],
    sources_content: list[dict[str, str]],
    generate_fn: Callable[..., Any],
    session_id: str = "",
    output_dir: str = "/tmp/naga",
) -> tuple[dict[str, Any], str]:
    """Send sources to Gemini and extract structured evidence.

    Args:
        sub_questions: Decomposed sub-questions to answer.
        sources_content: List of ``{"id": "s0", "url": "...", "content": "..."}``.
        generate_fn: Async callable that accepts a prompt string and returns
            ``{"text": "..."}`` with Gemini's response.
        session_id: Research session identifier.  When empty a UUID is
            generated automatically.
        output_dir: Root directory for evidence file storage.

    Returns:
        A tuple of ``(evidence_map, file_uri)`` where *evidence_map* is the
        parsed dict and *file_uri* is the absolute path where it was saved.
    """
    if not session_id:
        session_id = uuid.uuid4().hex[:12]
        logger.info("Generated session_id=%s (was empty)", session_id)

    prompt = _build_prompt(sub_questions, sources_content)

    logger.info(
        "Calling generate_fn with %d sub-questions, %d sources (%d chars prompt)",
        len(sub_questions),
        len(sources_content),
        len(prompt),
    )

    response = await generate_fn(prompt)
    raw_text: str = response.get("text", "")

    evidence_map = _parse_evidence(raw_text, sub_questions)

    file_uri = _save_evidence(evidence_map, session_id, output_dir)
    logger.info("Evidence saved to %s", file_uri)

    return evidence_map, file_uri


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prompt(
    sub_questions: list[str],
    sources_content: list[dict[str, str]],
) -> str:
    """Build the Gemini prompt with numbered sub-questions and sourced content.

    Each source is prefixed with ``[SOURCE {id}]`` and truncated to
    :data:`MAX_SOURCE_CHARS`.
    """
    parts: list[str] = [
        "You are a research analyst. Extract structured evidence from the "
        "sources below to answer each sub-question.\n",
        "## Sub-Questions\n",
    ]

    for idx, question in enumerate(sub_questions, start=1):
        parts.append(f"- **sub_q_{idx}**: {question}")

    parts.append("\n## Sources\n")

    for source in sources_content:
        sid = source.get("id", "?")
        url = source.get("url", "")
        content = source.get("content", "")

        if len(content) > MAX_SOURCE_CHARS:
            content = content[:MAX_SOURCE_CHARS] + "\n[TRUNCATED]"

        parts.append(f"[SOURCE {sid}] ({url})\n{content}\n")

    parts.append(_EXTRACTION_INSTRUCTIONS)

    return "\n".join(parts)


_EXTRACTION_INSTRUCTIONS: str = """
## Instructions

For EACH sub-question (sub_q_1, sub_q_2, ...) extract:

1. **facts** — list of objects: `{"text": "...", "source_ids": ["s0"], "confidence": 0.0-1.0}`
2. **contradictions** — list of objects: `{"claim_a": "...", "claim_b": "...", "source_ids": ["s0","s1"]}`
3. **gaps** — list of strings describing missing information
4. **data_points** — list of objects: `{"label": "...", "value": "...", "source_id": "s0"}`

Return ONLY a JSON object with keys sub_q_1, sub_q_2, etc.  No markdown, no explanation.

Example:
```json
{
  "sub_q_1": {
    "facts": [{"text": "...", "source_ids": ["s0"], "confidence": 0.9}],
    "contradictions": [],
    "gaps": ["No data on ..."],
    "data_points": [{"label": "Fee", "value": "Rp 2.000.000", "source_id": "s0"}]
  }
}
```
""".strip()


# ---------------------------------------------------------------------------
# JSON parsing + validation
# ---------------------------------------------------------------------------


def _parse_evidence(
    raw_text: str,
    sub_questions: list[str],
) -> dict[str, Any]:
    """Parse Gemini's raw text into a validated evidence map.

    Handles:
    - Markdown code-block wrappers (````` ``json ... `` `````)
    - Missing sub_q keys (backfilled with empty structure)
    - Missing per-sub_q keys (backfilled)
    - Invalid JSON (returns empty evidence with gap notes)
    """
    text = raw_text.strip()

    # Strip code-block wrappers
    match = _CODE_BLOCK_RE.match(text)
    if match:
        text = match.group(1).strip()

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse evidence JSON: %s", exc)
        return _empty_evidence(sub_questions, error=str(exc))

    if not isinstance(parsed, dict):
        logger.warning("Evidence JSON is not a dict (got %s)", type(parsed).__name__)
        return _empty_evidence(sub_questions, error="Expected JSON object, got non-dict")

    # Ensure every expected sub_q key exists and has all four fields
    for idx in range(1, len(sub_questions) + 1):
        key = f"sub_q_{idx}"
        if key not in parsed:
            parsed[key] = dict(_EMPTY_SUB_Q)  # shallow copy
        else:
            sub = parsed[key]
            for field_name, default in _EMPTY_SUB_Q.items():
                if field_name not in sub:
                    sub[field_name] = list(default) if isinstance(default, list) else default

    return parsed


def _empty_evidence(
    sub_questions: list[str],
    error: str = "unknown",
) -> dict[str, Any]:
    """Return an evidence map with empty facts and a gap noting the parse error."""
    result: dict[str, Any] = {}
    for idx in range(1, len(sub_questions) + 1):
        result[f"sub_q_{idx}"] = {
            "facts": [],
            "contradictions": [],
            "gaps": [f"Evidence parse error: {error}"],
            "data_points": [],
        }
    return result


# ---------------------------------------------------------------------------
# File persistence (Pointer State Pattern)
# ---------------------------------------------------------------------------


def _save_evidence(
    evidence_map: dict[str, Any],
    session_id: str,
    output_dir: str,
) -> str:
    """Write *evidence_map* to ``{output_dir}/{session_id}/evidence.json``.

    Creates directories as needed.  Returns the absolute file path.
    """
    session_dir = Path(output_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    file_path = session_dir / "evidence.json"
    file_path.write_text(json.dumps(evidence_map, indent=2, ensure_ascii=False))

    return str(file_path.resolve())
