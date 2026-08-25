"""Check 3 — secret, internal-reasoning, and instruction-scaffold egress
(research capture Sol §1.6).

Three distinct failure classes, each with a distinct verdict:

- A secret/credential pattern or a caller-supplied canary token: reuses
  ``wa_finalize.py::scan_text_for_secret_egress`` — the existing, proven
  pattern set (private-key blocks, SSH keys, OpenAI-style keys, JWTs, token
  assignments, bearer tokens) — rather than re-deriving it. That function
  is PUBLIC (no leading underscore) precisely because it is meant to be
  reused; importing it keeps the security-pattern list in exactly one
  place instead of two copies that can silently drift. A canary-token hit
  specifically is terminal (``CANARY_HIT`` -> ``POLICY_BLOCKED``, and per
  F3/Sol §2.5 "Any canary/secret hit globally disables the Codex leg" —
  wiring that global kill switch is the caller's job, this check only
  reports the reason); any other secret pattern is
  ``SECRET_EGRESS_DETECTED`` -> also ``POLICY_BLOCKED`` (per
  ``_LEGAL_REASONS_BY_VERDICT`` in the golden test suite).
- A structural internal-reasoning marker (an opening private prompt-section
  name, an explicit "internal monologue"/chain-of-thought tag) ->
  ``INTERNAL_REASONING_LEAK`` -> ``TEXT_DEFECT`` (retryable — this is a
  generation-shape defect, not a policy breach).
- The internal KG-workflow diagnostics scaffold (the same anchored two-
  string block ``wa_finalize.py`` already strips at the WA boundary) ->
  ``INSTRUCTION_SCAFFOLD_LEAK`` -> ``TEXT_DEFECT``.

Deliberately NOT a free-form "does this text sound like model reasoning"
detector — per the team lead's framing for this lane, enumerating natural
language phrasings is unbounded (the team-bot's 16-false-ALLOW lesson).
Every pattern below is a STRUCTURAL marker (a literal tag, a literal
section-header pair, a literal secret shape) — the same anchoring
discipline ``wa_finalize.py``'s own scanners already use, not a new one
invented here.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.services.client_bot.policy.check_result import CheckOutcome
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.services.integrations.wa_finalize import scan_text_for_secret_egress

__all__ = ["check_egress"]

# Anchored at the very start of the text, mirroring
# wa_finalize._INTERNAL_MONOLOGUE_LEAK_RE's own rationale: a leaked private
# prompt-section marker or chain-of-thought preamble is a stray artifact at
# the head of the payload, not something a legitimate client answer
# discusses mid-paragraph (a client answer *about* internal-monologue
# leaks, hypothetically, would not open with the marker itself).
# "let me think step by step" added per B1b golden-fixture verification
# ("client.internal-reasoning-leakage") — a well-known chain-of-thought
# preamble phrase, still a bounded literal, not an open phrasing scan.
_INTERNAL_REASONING_MARKER_RE = re.compile(
    r"^[^A-Za-z0-9]{0,32}(?:internal[ _-]+monologue(?:[ _-]+instructions)?"
    r"|chain[ _-]+of[ _-]+thought"
    r"|let[ _-]+me[ _-]+think(?:[ _-]+step[ _-]+by[ _-]+step)?"
    r"|<\s*(?:thinking|internal_reasoning|internal)\s*>"
    r"|\[\s*internal\s*\])(?:[^A-Za-z0-9]|$)",
    re.IGNORECASE,
)

# The same literal KG-workflow scaffold block wa_finalize.py strips at the
# WA boundary — anchored on the SAME two literal strings (heading prefix +
# closing trailer sentence, always emitted together by the same call site)
# rather than a loose "workflow" keyword. See wa_finalize.py's own comment
# for why a bare-substring match would be unsafe (family #3, guard-over-match).
_KG_WORKFLOW_TRAILER = (
    "IMPORTANT: This is a suggested workflow. Always verify current requirements with the user."
)
_KG_WORKFLOW_SCAFFOLD_RE = re.compile(
    r"##\s+SUGGESTED WORKFLOW \(from .*?" + re.escape(_KG_WORKFLOW_TRAILER),
    re.DOTALL,
)

# Unanchored (unlike the two patterns above) — deliberately, and narrowly:
# a legitimate Bali Zero regulatory/pricing/procedural answer has no
# reason to ever mention "my system prompt"/"system instructions" at ANY
# position, so this is safe to match mid-text without the family-#3
# over-match risk a broader phrase would carry. Verified against the B6b
# golden fixture "client.prompt-injection-in-retrieved-text", whose
# candidate leaks this phrase mid-sentence, not at the very start.
_SYSTEM_PROMPT_LEAK_RE = re.compile(
    r"\b(?:my|the)\s+system\s+(?:prompt|instructions)\b", re.IGNORECASE
)


def check_egress(answer: str, canary_tokens: Sequence[str] = ()) -> CheckOutcome | None:
    """None means pass. Order matters: a canary/secret hit is checked
    before the structural-leak scan because it is the more severe,
    terminal failure — if text somehow matches both classes, the caller
    needs the POLICY_BLOCKED signal, not the retryable one.
    """
    secret_hit = scan_text_for_secret_egress(answer, canary_tokens)
    if secret_hit is not None:
        if secret_hit == "canary_token":
            return CheckOutcome(
                verdict=GateVerdict.POLICY_BLOCKED,
                reason=GateReason.CANARY_HIT,
                reason_detail="canary_token",
            )
        return CheckOutcome(
            verdict=GateVerdict.POLICY_BLOCKED,
            reason=GateReason.SECRET_EGRESS_DETECTED,
            # Pattern name only — never the matched content (CLAUDE.md §14).
            reason_detail=secret_hit,
        )

    if _INTERNAL_REASONING_MARKER_RE.match(answer):
        return CheckOutcome(
            verdict=GateVerdict.TEXT_DEFECT,
            reason=GateReason.INTERNAL_REASONING_LEAK,
            reason_detail="internal_reasoning_marker",
        )

    if _KG_WORKFLOW_SCAFFOLD_RE.search(answer):
        return CheckOutcome(
            verdict=GateVerdict.TEXT_DEFECT,
            reason=GateReason.INSTRUCTION_SCAFFOLD_LEAK,
            reason_detail="kg_workflow_scaffold",
        )

    if _SYSTEM_PROMPT_LEAK_RE.search(answer):
        return CheckOutcome(
            verdict=GateVerdict.TEXT_DEFECT,
            reason=GateReason.INSTRUCTION_SCAFFOLD_LEAK,
            reason_detail="system_prompt_mention",
        )

    return None
