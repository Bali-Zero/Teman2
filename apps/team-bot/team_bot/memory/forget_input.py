""""dimentica X" / "forget X" / "lupakan X" extraction — deterministic,
runs BEFORE the LLM, exactly like `confirmation_input.py`'s confirm-code
parsers (F4: "Confirmation parser runs BEFORE the LLM"; the same discipline
applies here for the same reason — a deletion command is the last thing
this system should let a 14B slot-filler interpret loosely).

Mirrors `confirmation_input.py`'s shape on purpose: the keyword
("dimentica"/"forget"/"lupakan") is REQUIRED and the target must
IMMEDIATELY follow it — never a scan of the rest of the message. Without
that constraint, a message like "il cliente CL-1042 ha dimenticato la
password, apri PR-3090" would offer two ID-shaped tokens as false
candidates; requiring adjacency to the keyword means only a token that is
actually the OBJECT of "dimentica" is ever extracted, the same
guilt/innocence argument `confirmation_input.py`'s own docstring makes for
its "PR-3090 contains a valid-shaped 4-digit token" collision.

Two forms:
- "dimentica CL-1042" / "forget PR-3090" -> forgets episodic references to
  ONE target only (`ForgetScope.TARGET` — `store.py.forget_target`).
- "dimentica tutto" / "forget everything" / "lupakan semua" -> full wipe
  of the requesting member's own memory (`ForgetScope.MEMBER` —
  `store.py.forget_member`). There is no third form that names another
  member's principal_id — this parser has no way to express "forget
  someone else", which is correct: the confirming/forgetting principal is
  always the server-resolved caller (F7), never a value read out of the
  message text.

Author: Claude Sonnet 5 (lane B8 — per-member memory)
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.registry.envelope import TARGET_ID_PATTERN

from .store import ForgetScope

__all__ = ["ForgetRequest", "parse_forget_text"]

_EVERYTHING_TOKENS = frozenset({"tutto", "everything", "semua"})

# Keyword MANDATORY, target must immediately follow (only whitespace/colon
# in between) — same adjacency discipline as confirmation_input.py's
# _TEXT_PATTERN.
_TEXT_PATTERN = re.compile(
    r"\b(?:dimentica|forget|lupakan)\b\s*:?\s*((?:PR|CL)-[0-9]{4,10}|tutto|everything|semua)\b",
    re.IGNORECASE,
)


class ForgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: ForgetScope
    target_id: Annotated[str, Field(pattern=TARGET_ID_PATTERN)] | None = None

    @model_validator(mode="after")
    def _scope_constrains_target(self) -> ForgetRequest:
        if self.scope == ForgetScope.TARGET and self.target_id is None:
            raise ValueError("target_id is required when scope is target")
        if self.scope == ForgetScope.MEMBER and self.target_id is not None:
            raise ValueError("target_id must be unset when scope is member")
        return self


def parse_forget_text(text: str) -> ForgetRequest | None:
    """Returns `None` when the message is not a forget command at all — a
    bare mention of "dimenticare" without an adjacent target/"tutto" never
    matches, same innocence guarantee `confirmation_input.py` gives a bare
    "sì"/"ok"."""
    match = _TEXT_PATTERN.search(text)
    if match is None:
        return None
    raw = match.group(1)
    if raw.lower() in _EVERYTHING_TOKENS:
        return ForgetRequest(scope=ForgetScope.MEMBER)
    return ForgetRequest(scope=ForgetScope.TARGET, target_id=raw.upper())
