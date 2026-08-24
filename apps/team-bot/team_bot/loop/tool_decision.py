"""ToolDecision — the parsed, single-call-enforced shape of one raw model turn.

Shared with B4's serving contract (MANDATE.md "Lanes": "B3/B4 share only the
ToolDecision schema and the serving endpoint contract"). The raw shape this
parses is the OpenAI-compatible ``message`` dict B4's own instruments
exchange with llama.cpp/Ollama — see
``scripts/duebot/serving_roundtrip_gate.py`` and
``scripts/duebot/golden_multilingual_gate.py``, and the recorded turns in
``docs/plans/2026-08-25-due-bot-live/evidence/14b-ollama-tmpl-golden.json``.

B4 measured (evidence/b4b-summary.json, both llama.cpp and Ollama) that
``parallel_tool_calls: false`` is honored by NEITHER serving stack — see
memory ``parallel-tool-calls-false-is-not-honored-locally.md``. The
single-tool-per-turn guarantee (F4) is therefore not the server's job: this
module enforces it by construction. ``ToolDecision.from_raw_message`` takes
``tool_calls[0]`` as ``selected_tool`` and preserves anything past it in
``discarded_tool_calls`` for audit ONLY — the loop that eventually consumes
a ``ToolDecision`` (out of scope here) must never execute anything in that
tuple.

Author: Claude Sonnet 5 (lane B3 — team-bot tool registry)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ProposedToolCall", "ToolDecision"]


class ProposedToolCall(BaseModel):
    """One raw ``tool_calls[i]`` entry, UNVALIDATED against any ``ToolSpec``.

    ``raw_arguments`` is deliberately the raw JSON *string* the model
    emitted, not a parsed/validated dict: structured-output grammars enforce
    only a SUBSET of JSON Schema (required/enum/type — NOT pattern/
    minLength/maxLength/maxItems), so re-validating this string against the
    matching ``ToolSpec.parameters_schema`` is a separate, later step this
    class does not perform. It only records what the model actually said.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: Annotated[str, Field(min_length=1, max_length=128)]
    tool_name: Annotated[str, Field(min_length=1, max_length=128)]
    raw_arguments: Annotated[str, Field(max_length=8_000)]

    def parsed_arguments(self) -> dict[str, Any] | None:
        """Best-effort JSON decode for callers that just want a look — NOT
        validation. Returns ``None`` on malformed JSON (Kimi FM5: 14B models
        sometimes drift into non-JSON prose here); a caller needing a hard
        guarantee must validate against the matching ``ToolSpec`` instead.
        """
        try:
            decoded = json.loads(self.raw_arguments)
        except (json.JSONDecodeError, TypeError):
            return None
        return decoded if isinstance(decoded, dict) else None


class ToolDecision(BaseModel):
    """The parsed, single-call-enforced shape of one raw assistant turn.

    - A raw message with a non-empty ``tool_calls`` list -> ``selected_tool``
      is its FIRST entry, verbatim; every later entry lands in
      ``discarded_tool_calls`` (audit only, never executed).
    - An empty/absent/``null`` ``tool_calls`` -> ``selected_tool`` is
      ``None``. This is EXACTLY gc-015's shape when ``raw_content`` narrates
      a completed action (see ``claim_gate.py``) and the ordinary, correct
      shape for a read answer, a clarifying question, or an abstention
      otherwise — ``ToolDecision`` alone cannot and does not distinguish
      those; that is ``ActionClaimGate``'s job.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    selected_tool: ProposedToolCall | None
    discarded_tool_calls: tuple[ProposedToolCall, ...] = Field(default=(), max_length=20)
    raw_content: Annotated[str, Field(max_length=8_000)] | None
    model_name: Annotated[str, Field(min_length=1, max_length=128)]
    decided_at: datetime

    @property
    def proposed_a_tool_call(self) -> bool:
        return self.selected_tool is not None

    @property
    def dropped_extra_calls(self) -> bool:
        """True iff the model violated the single-tool-per-turn rule (F4) —
        i.e. the serving layer returned more than one ``tool_calls`` entry
        despite ``parallel_tool_calls: false``, which B4 measured neither
        llama.cpp nor Ollama actually honors."""
        return len(self.discarded_tool_calls) > 0

    @classmethod
    def from_raw_message(
        cls,
        message: dict[str, Any],
        *,
        model_name: str,
        decided_at: datetime,
    ) -> ToolDecision:
        """Parse one raw OpenAI-compatible ``message`` dict into a
        ``ToolDecision``.

        ``message["tool_calls"]`` may be absent, ``None``, or ``[]`` — all
        three are observed across the two measured stacks (see gc-015 in
        ``evidence/14b-ollama-tmpl-golden.json``) and all three mean "no
        tool call this turn".
        """
        raw_calls = message.get("tool_calls") or []
        parsed: list[ProposedToolCall] = []
        for index, raw_call in enumerate(raw_calls):
            function = raw_call.get("function") or {}
            parsed.append(
                ProposedToolCall(
                    call_id=str(raw_call.get("id") or f"unindexed-{index}"),
                    tool_name=str(function.get("name") or ""),
                    raw_arguments=str(function.get("arguments") or ""),
                )
            )

        selected = parsed[0] if parsed else None
        discarded = tuple(parsed[1:])

        content = message.get("content")
        raw_content = content if isinstance(content, str) and content != "" else None

        return cls(
            selected_tool=selected,
            discarded_tool_calls=discarded,
            raw_content=raw_content,
            model_name=model_name,
            decided_at=decided_at,
        )
