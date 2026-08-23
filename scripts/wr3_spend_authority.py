#!/usr/bin/env python3
"""WR3 spend authority gate — fail-closed guard in front of every Veo/Flow spend.

This is the security-relevant module of the WR3 zero-spend packet: every
call site that is about to open a socket to FlowKit/Veo (credit-consuming)
MUST call `assert_spend_authorized(...)` first and let any
`SpendNotAuthorizedError` propagate. There is deliberately no bypass
argument, no "dry_run=False, force=True" escape hatch, and no default that
authorizes silently.

Threat model this module defends against:
  - A stale/forgotten `WR3_ZERO_SPEND=1` env var lying around from a
    previous session and someone SEPARATELY setting a spend-decision token,
    assuming the token wins. It does not: zero-spend always wins.
  - A decision token minted for episode A being replayed against episode B.
  - A decision token from yesterday (or a future date) authorizing spend
    "just this once" outside the day it was actually decided.
  - An unlogged authorization: if the append-only decision log cannot be
    written, the spend is refused rather than silently allowed through.

Stdlib-only by design: this module must NEVER import `wr3_flowkit_client`
(or vice versa) — that would create a circular import between the gate and
the thing it gates.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})

# <episode_id>:<who>:<YYYY-MM-DD> — every field character class deliberately
# excludes whitespace, so internal whitespace in any field fails validation
# by construction (see parse_decision docstring).
_EPISODE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_WHO_RE = re.compile(r"^[A-Za-z0-9._@-]+$")
_DATE_SHAPE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_DEFAULT_LOG_PATH = Path.home() / ".cache" / "wr3" / "spend-decisions.jsonl"


class SpendNotAuthorizedError(Exception):
    """Raised whenever a Veo/Flow spend is not authorized.

    Every charging call site must let this propagate — never catch it to
    fall back to "spend anyway".
    """


@dataclass(frozen=True)
class SpendDecision:
    """A validated, single-day, single-episode spend authorization."""

    episode_id: str
    who: str
    date: date
    raw: str


def zero_spend_enabled() -> bool:
    """True when WR3_ZERO_SPEND is set to a truthy value.

    Truthy (case-insensitive, surrounding whitespace stripped): "1", "true",
    "yes", "on". Everything else — including "0", "false", "", and unset —
    is false.
    """
    raw = os.environ.get("WR3_ZERO_SPEND", "")
    return raw.strip().lower() in _TRUTHY_VALUES


def parse_decision(raw: str) -> SpendDecision:
    """Parse and strictly validate a `<episode_id>:<who>:<YYYY-MM-DD>` token.

    Raises ValueError (never returns a partially-valid decision) when:
      - there are not exactly 3 colon-separated fields;
      - episode_id is empty or contains a character outside [A-Za-z0-9._-];
      - who is empty or contains a character outside [A-Za-z0-9._@-];
      - the date field is not exactly YYYY-MM-DD, or is not a real calendar
        date.

    Surrounding whitespace on the whole token is stripped before
    validation; internal whitespace (inside a field, or padding a field
    after a colon) is rejected because none of the field character classes
    above include whitespace.
    """
    if raw is None:
        raise ValueError("decision token is None")

    stripped = raw.strip()
    if not stripped:
        raise ValueError("decision token is empty")

    parts = stripped.split(":")
    if len(parts) != 3:
        raise ValueError(
            "decision token must have exactly 3 colon-separated fields "
            f"<episode_id>:<who>:<YYYY-MM-DD>, got {len(parts)} field(s): {raw!r}"
        )

    episode_id, who, date_str = parts

    if not episode_id or not _EPISODE_ID_RE.match(episode_id):
        raise ValueError(f"invalid episode_id field {episode_id!r} (expected [A-Za-z0-9._-]+)")

    if not who or not _WHO_RE.match(who):
        raise ValueError(f"invalid who field {who!r} (expected [A-Za-z0-9._@-]+)")

    if not _DATE_SHAPE_RE.match(date_str):
        raise ValueError(f"invalid date field {date_str!r} (expected exactly YYYY-MM-DD)")

    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"date field {date_str!r} is not a real calendar date") from exc

    return SpendDecision(episode_id=episode_id, who=who, date=parsed_date, raw=raw)


def log_decision(decision: SpendDecision, *, episode_id: str, log_path: Path | None = None) -> None:
    """Append one JSONL record to the spend-decision log. Fail closed.

    A failure to write MUST propagate as SpendNotAuthorizedError — an
    unlogged spend is exactly what this packet exists to prevent, so a
    logging failure is treated as an authorization failure, not a warning.
    """
    path = log_path if log_path is not None else Path(
        os.environ.get("WR3_SPEND_DECISION_LOG", str(_DEFAULT_LOG_PATH))
    )
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "episode_id": episode_id,
        "who": decision.who,
        "decision_date": decision.date.isoformat(),
        "raw": decision.raw,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        path.chmod(0o600)
    except OSError as exc:
        raise SpendNotAuthorizedError(
            f"failed to write spend-decision log at {path}: {exc} — spend refused (fail-closed)"
        ) from exc

    logger.info(
        "spend authorized+logged: episode=%s who=%s date=%s log=%s",
        episode_id,
        decision.who,
        decision.date.isoformat(),
        path,
    )


def assert_spend_authorized(*, episode_id: str, now: date | None = None) -> SpendDecision:
    """The gate every charging call site invokes before opening a socket.

    Raises SpendNotAuthorizedError when ANY of:
      - `zero_spend_enabled()` is true (checked FIRST — zero-spend always
        wins over a decision token, even a perfectly valid one for today);
      - WR3_SPEND_DECISION is unset or empty;
      - the token fails `parse_decision`;
      - the token's episode_id does not match `episode_id`;
      - the token's date is not exactly `now` (today by default) — neither
        a stale token nor a future-dated one authorizes.

    On success: logs the authorization via `log_decision` (itself
    fail-closed — see its docstring) and returns the `SpendDecision`.
    """
    today = now if now is not None else date.today()

    if zero_spend_enabled():
        raise SpendNotAuthorizedError(
            "WR3_ZERO_SPEND is active — spend refused unconditionally, "
            "regardless of any WR3_SPEND_DECISION token present"
        )

    raw = os.environ.get("WR3_SPEND_DECISION", "")
    if not raw or not raw.strip():
        raise SpendNotAuthorizedError("WR3_SPEND_DECISION is unset or empty — spend not authorized")

    try:
        decision = parse_decision(raw)
    except ValueError as exc:
        raise SpendNotAuthorizedError(f"WR3_SPEND_DECISION failed validation: {exc}") from exc

    if decision.episode_id != episode_id:
        raise SpendNotAuthorizedError(
            f"decision token was minted for episode {decision.episode_id!r}, "
            f"not the requesting episode {episode_id!r}"
        )

    if decision.date != today:
        raise SpendNotAuthorizedError(
            f"decision token is dated {decision.date.isoformat()}, "
            f"not today ({today.isoformat()}) — stale/future tokens do not authorize"
        )

    log_decision(decision, episode_id=episode_id)
    return decision
