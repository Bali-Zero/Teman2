"""Obligation engine — AscentAI bottom-up extraction (Task 5).

Algorithm:
  1. Take a Regulation harvested by a feeder (T2/T3/T4).
  2. (Optional) Use foundations.NERExtractor on body_excerpt to find KBLI
     mentions, dates, money, organisations. NER is lazy-loaded — only
     materialised if NERExtractor is passed in.
  3. Shell out to `claude --print` (subprocess, NEVER SDK) with a prompt
     that returns a JSON list of atomic obligations.
  4. Parse the JSON, build Obligation dataclasses, and persist into
     SQLite at apps/mata-garuda/data/setup_team.sqlite with
     human_validated=False.

Banned per CLAUDE.md §1: anthropic SDK, ANTHROPIC_API_KEY env. Sanctioned
path: shell out to `claude --print`. Tests inject a `claude_runner` so we
never spawn the real CLI in CI.

SQLite schema (sqlite3, no ORM, plain text DDL):

  CREATE TABLE IF NOT EXISTS obligations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      text TEXT NOT NULL,
      obligation_type TEXT NOT NULL,
      article_ref TEXT,
      kbli_codes_affected TEXT,    -- JSON array as text
      deadline_pattern TEXT,
      sanction_if_missed TEXT,
      effective_date TEXT,         -- ISO date or NULL
      regulation_source_id TEXT NOT NULL,
      human_validated INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
      UNIQUE(regulation_source_id, article_ref, text)
  );

We cache one column-fixed connection per process (lazy init) but accept
an optional `db_path` for tests so they can use a tmp_path.
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import sqlite3
import subprocess
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Optional

from mata_garuda.domains.setup_team.types import (
    Obligation,
    ObligationType,
    Regulation,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "setup_team.sqlite"
)
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    obligation_type TEXT NOT NULL,
    article_ref TEXT,
    kbli_codes_affected TEXT,
    deadline_pattern TEXT,
    sanction_if_missed TEXT,
    effective_date TEXT,
    regulation_source_id TEXT NOT NULL,
    human_validated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE(regulation_source_id, article_ref, text)
);

CREATE INDEX IF NOT EXISTS idx_obligations_source
    ON obligations(regulation_source_id);
CREATE INDEX IF NOT EXISTS idx_obligations_type
    ON obligations(obligation_type);
CREATE INDEX IF NOT EXISTS idx_obligations_validated
    ON obligations(human_validated);
"""

PROMPT_TEMPLATE = """You extract atomic regulatory obligations from an Indonesian regulation excerpt.
Return ONLY a JSON array (no prose, no markdown fence). Each item must have:
  - "text": verbatim Indonesian obligation phrase
  - "obligation_type": exactly one of "filing"|"reporting"|"payment"|"operational"|"registration"
  - "article_ref": e.g. "Pasal 4 ayat (2)" or "" if not given
  - "deadline_pattern": e.g. "30 hari setelah ..." or "" if not given
  - "sanction_if_missed": short text or "" if not given
  - "effective_date": ISO date string YYYY-MM-DD or "" if not given
  - "kbli_codes_affected": JSON array of strings, e.g. ["63122"] or [] if none

Regulation source id: {source_id}
Title: {title}
Body excerpt:
{body}

Output:"""

VALID_OBLIGATION_TYPES = {
    "filing",
    "reporting",
    "payment",
    "operational",
    "registration",
}


def _strip_anthropic_env(env: dict) -> dict:
    """Defense-in-depth: never let the SDK key leak into the subprocess.

    Mirrors apps/backend-rag/backend/llm/claude_oauth_client.py — Bali Zero
    holds 3 Claude MAX plans; paying per token would duplicate quota.
    """
    out = dict(env)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        out.pop(k, None)
    return out


def _run_claude_cli(prompt: str, *, timeout_seconds: float = 120.0) -> str:
    """Default claude_runner: subprocess to `claude --print`.

    Returns stdout (str). Tests should inject a stub via the `claude_runner`
    parameter on extract_obligations() so CI never spawns the real CLI.
    """
    env = _strip_anthropic_env(os.environ)
    completed = subprocess.run(
        ["claude", "--print", prompt],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=env,
    )
    if completed.returncode != 0:
        logger.warning(
            "claude --print exit=%d stderr=%s",
            completed.returncode,
            completed.stderr[:200],
        )
        return ""
    return completed.stdout or ""


def _open_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open SQLite connection with WAL + busy-timeout (knowledge.db lesson)."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA_DDL)
    conn.commit()
    return conn


def _build_prompt(regulation: Regulation, kbli_hints: Iterable[str] = ()) -> str:
    body = regulation.body_excerpt or "(empty body — title-only signal)"
    hint_line = ""
    if kbli_hints:
        hint_line = f"\nKBLI mentions detected by NER: {sorted(set(kbli_hints))!r}"
    return PROMPT_TEMPLATE.format(
        source_id=regulation.source_id,
        title=regulation.title,
        body=body + hint_line,
    )


def _parse_claude_json(raw: str) -> list[dict]:
    """Tolerate markdown fences and stray prose. Returns [] on parse error."""
    if not raw:
        return []
    text = raw.strip()
    # Strip leading/trailing markdown fences if present.
    if text.startswith("```"):
        # Drop the opening fence (```json or ```).
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    # Locate first '[' if there's prose before.
    bracket_idx = text.find("[")
    if bracket_idx > 0:
        text = text[bracket_idx:]
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("claude JSON parse failed: %s — raw=%s", exc, raw[:200])
        return []
    if not isinstance(parsed, list):
        logger.warning("claude returned non-list: %s", type(parsed).__name__)
        return []
    return parsed


def _parse_iso_date(value) -> Optional[date]:
    """Forgiving ISO date parser."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _normalise_obligation_type(value: str) -> ObligationType:
    """Map LLM output → valid ObligationType. Default to 'reporting' on
    unknown values rather than raising — robust ingestion."""
    lo = (value or "").lower().strip()
    if lo in VALID_OBLIGATION_TYPES:
        return lo  # type: ignore[return-value]
    return "reporting"  # type: ignore[return-value]


def _items_to_obligations(
    items: list[dict], regulation: Regulation
) -> list[Obligation]:
    out: list[Obligation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        kbli_raw = item.get("kbli_codes_affected") or []
        if isinstance(kbli_raw, str):
            # Defensive: LLM sometimes returns CSV string instead of array.
            kbli_raw = [s.strip() for s in kbli_raw.split(",") if s.strip()]
        kbli_codes = tuple(str(c) for c in kbli_raw if c)
        out.append(
            Obligation(
                text=text,
                obligation_type=_normalise_obligation_type(
                    item.get("obligation_type", "reporting")
                ),
                article_ref=str(item.get("article_ref", "") or ""),
                deadline_pattern=str(item.get("deadline_pattern", "") or ""),
                sanction_if_missed=str(item.get("sanction_if_missed", "") or ""),
                effective_date=_parse_iso_date(item.get("effective_date")),
                kbli_codes_affected=kbli_codes,
                regulation_source_id=regulation.source_id,
                id=None,
                human_validated=False,
            )
        )
    return out


def _persist(
    conn: sqlite3.Connection, obligations: Iterable[Obligation]
) -> list[Obligation]:
    """Insert obligations; return them with `id` populated. INSERT OR IGNORE
    on the (regulation_source_id, article_ref, text) UNIQUE — re-running
    extract_obligations on the same regulation must not double-count.
    """
    out: list[Obligation] = []
    cursor = conn.cursor()
    for obl in obligations:
        cursor.execute(
            """
            INSERT OR IGNORE INTO obligations (
                text, obligation_type, article_ref, kbli_codes_affected,
                deadline_pattern, sanction_if_missed, effective_date,
                regulation_source_id, human_validated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obl.text,
                obl.obligation_type,
                obl.article_ref,
                json.dumps(list(obl.kbli_codes_affected)),
                obl.deadline_pattern,
                obl.sanction_if_missed,
                obl.effective_date.isoformat() if obl.effective_date else None,
                obl.regulation_source_id,
                1 if obl.human_validated else 0,
            ),
        )
        if cursor.lastrowid:
            new_id = cursor.lastrowid
        else:
            # Conflict — pull existing id.
            row = cursor.execute(
                """SELECT id FROM obligations
                   WHERE regulation_source_id=? AND article_ref=? AND text=?""",
                (obl.regulation_source_id, obl.article_ref, obl.text),
            ).fetchone()
            new_id = row["id"] if row else None
        out.append(
            Obligation(
                text=obl.text,
                obligation_type=obl.obligation_type,
                article_ref=obl.article_ref,
                deadline_pattern=obl.deadline_pattern,
                sanction_if_missed=obl.sanction_if_missed,
                effective_date=obl.effective_date,
                kbli_codes_affected=obl.kbli_codes_affected,
                regulation_source_id=obl.regulation_source_id,
                id=new_id,
                human_validated=obl.human_validated,
            )
        )
    conn.commit()
    return out


def extract_obligations(
    regulation: Regulation,
    *,
    claude_runner: Optional[Callable[[str], str]] = None,
    db_path: Path | str | None = None,
    ner_extractor=None,  # foundations.NERExtractor or None
) -> list[Obligation]:
    """Bottom-up obligation extraction → SQLite persist.

    Args:
        regulation: a Regulation harvested by a feeder.
        claude_runner: callable(prompt) → str. Defaults to `_run_claude_cli`
                       which shells out to `claude --print`. Tests MUST
                       inject a mock so CI never spawns the real CLI.
        db_path: SQLite path. Defaults to apps/mata-garuda/data/setup_team.sqlite.
        ner_extractor: optional foundations.NERExtractor instance. If passed,
                       used to extract KBLI mentions from body_excerpt as
                       hints in the prompt. None (default) → no NER.

    Returns:
        list[Obligation] with `id` populated (after SQLite insert).
    """
    runner = claude_runner or _run_claude_cli
    kbli_hints: list[str] = []
    if ner_extractor is not None and regulation.body_excerpt:
        try:
            entities = ner_extractor.extract(
                regulation.body_excerpt, labels=("ORG", "QUANTITY")
            )
            # KBLI codes are typically QUANTITY (5-digit numbers); we keep
            # everything that looks like a 5-digit code.
            for ent in entities:
                token = ent.text.strip()
                if token.isdigit() and len(token) == 5:
                    kbli_hints.append(token)
        except Exception as exc:
            logger.warning("NER extraction failed (degrading): %s", exc)

    prompt = _build_prompt(regulation, kbli_hints=kbli_hints)
    raw = runner(prompt)
    items = _parse_claude_json(raw)
    obligations = _items_to_obligations(items, regulation)
    if not obligations:
        return []
    conn = _open_db(db_path)
    try:
        persisted = _persist(conn, obligations)
    finally:
        conn.close()
    return persisted


__all__ = [
    "DEFAULT_DB_PATH",
    "PROMPT_TEMPLATE",
    "SCHEMA_DDL",
    "VALID_OBLIGATION_TYPES",
    "extract_obligations",
]
