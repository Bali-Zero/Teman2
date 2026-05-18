#!/usr/bin/env python3
"""WR3 NotebookLM subprocess client — used by wr3-brief-interpreter ONLY.

Symbiosis Law 2 (OSINT blindato):
  - ONE agent is allowed to read NB: wr3-brief-interpreter (and only this one).
  - NB source_ids NEVER pass downstream — caller must split into:
      * brief.json (public, scrubbed)
      * nb_source_ids.private.json (Pro-only, NEVER pushed downstream)

Routing map: ~/.claude/skills/bali-zero-brand/wr3/brief-interpreter/nb-routing-domain-map.md
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

NLM_CLI = os.environ.get("WR3_NLM_CLI", "notebooklm-mcp")
NLM_TIMEOUT_S = int(os.environ.get("WR3_NLM_TIMEOUT_S", "60"))


class NLMError(Exception):
    """Base for NLM subprocess errors."""


class NLMQuotaError(NLMError):
    """All 5 NB-INTEL down OR NLM auth failure. Episode HALTS (cannot ground)."""


@dataclass(frozen=True)
class NLMQuery:
    notebook_id: str
    question: str
    max_sources: int = 5


@dataclass(frozen=True)
class NLMAnswer:
    notebook_id: str
    question: str
    raw_text: str
    source_ids: tuple[str, ...]  # NEVER pass these downstream
    duration_ms: int


async def query_nb(
    query: NLMQuery,
    *,
    cli: str | None = None,
    timeout_s: int | None = None,
) -> NLMAnswer:
    """Query a NotebookLM via the notebooklm-mcp CLI subprocess.

    Returns answer + source_ids. Caller is RESPONSIBLE for not leaking
    source_ids to brief.json — they go in nb_source_ids.private.json only.
    """
    bin_path = cli or NLM_CLI
    if not shutil.which(bin_path):
        raise NLMError(f"NLM CLI not found at {bin_path!r}. Install via 'nlm login'.")

    args = [
        bin_path,
        "query",
        "--notebook", query.notebook_id,
        "--question", query.question,
        "--format", "json",
        "--max-sources", str(query.max_sources),
    ]

    started = asyncio.get_event_loop().time()
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_s or NLM_TIMEOUT_S,
        )
    except asyncio.TimeoutError as e:
        proc.kill()
        raise NLMError(f"NLM query timeout for {query.notebook_id}") from e

    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)

    if proc.returncode != 0:
        text = stderr.decode("utf-8", "replace")
        if "quota" in text.lower() or "rate" in text.lower():
            raise NLMQuotaError(f"NLM quota: {text[:200]}")
        raise NLMError(f"NLM exit {proc.returncode}: {text[:200]}")

    try:
        data = json.loads(stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise NLMError(f"NLM returned non-JSON: {stdout[:200]!r}") from e

    return NLMAnswer(
        notebook_id=query.notebook_id,
        question=query.question,
        raw_text=data.get("answer", ""),
        source_ids=tuple(data.get("source_ids") or []),
        duration_ms=duration_ms,
    )


def scrub_for_brief(answer: NLMAnswer) -> dict:
    """Return a brief.json-safe dict (NO source_ids).

    Symbiosis Law 2 enforcement at the data-shape boundary.
    """
    return {
        "answer_text": answer.raw_text,
        "notebook_questioned": answer.notebook_id,
        # NEVER include answer.source_ids here. Keep in nb_source_ids.private.json.
    }


def persist_private_sources(
    answers: list[NLMAnswer], episode_dir: Path
) -> Path:
    """Write nb_source_ids.private.json (Pro-side only, .gitignore'd).

    This file is NEVER pushed downstream. Symbiosis Law 2 boundary.
    """
    payload = {
        "warning": "NEVER push this file downstream. Symbiosis Law 2 (OSINT blindato).",
        "queries": [
            {
                "notebook_id": a.notebook_id,
                "question": a.question,
                "source_ids": list(a.source_ids),
                "duration_ms": a.duration_ms,
            }
            for a in answers
        ],
    }
    path = episode_dir / "nb_source_ids.private.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


if __name__ == "__main__":
    print(f"NLM CLI: {NLM_CLI}, timeout: {NLM_TIMEOUT_S}s")
    print("(no smoke test — would consume NB query quota)")
