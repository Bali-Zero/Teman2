"""turn_plan — the structural split that lets reads/searches chain freely
while keeping "one mutation per turn, always confirmed" a property of the
TYPE, never a runtime counter someone could forget to check.

Owner directive #1 §2 (2026-08-25, via the M5 design session) amends F4/F5:

    "Il vincolo 'un tool per turno' resta SOLO sulle MUTAZIONI (una
    mutazione per turno, sempre confermata). Letture e ricerche: catene
    multi-step libere (alza MAX_STEPS a un valore sensato, es. 8, con
    loop-detector e budget). I gradi di autonomia non si allentano."

``ToolDecision`` (``tool_decision.py``) is UNCHANGED by this module and must
stay that way: it still parses exactly ONE raw serving-layer message and
still enforces "first tool_calls entry wins, the rest are audit-only" —
that guarantee is real and valuable (B4 measured neither llama.cpp nor
Ollama honors ``parallel_tool_calls: false``) and has nothing to do with
the NEW relaxation, which is about how many SEQUENTIAL ``ToolDecision``
turns a loop is allowed to take before it must stop, not about how many
``tool_calls`` entries live inside one raw message.

The relaxation therefore lives ONE LEVEL UP, at the granularity of "what is
this loop allowed to do across its whole turn" — and that is exactly where
a type split, not a validator, can make the rule unrepresentable-if-violated:

- ``ReadPlan`` — an ordered, bounded sequence of ``ReadStep``s. Multiple
  reads across multiple sequential turns are exactly what the directive
  asks for, so this type can genuinely hold more than one.
- ``MutationDecision`` — exactly one ``ProposedToolCall``, full stop. There
  is no list, no tuple, no second slot anywhere in this type for a second
  mutation to occupy. A caller cannot construct one that lies about how
  many mutations were proposed, because there is no field to lie in — this
  is the "construction that cannot lie" standard ``claim_gate.py``'s own
  docstring names and ``reply_composer.py`` was rewritten to meet; the same
  standard now covers HOW MANY calls a turn is representable as making, not
  only WHETHER a reply is grounded in one.
- ``FinalAnswer`` — no tool call at all this step: a final answer, a
  clarifying question, or an abstention.
- ``classify_step`` dispatches one parsed ``ToolDecision`` into exactly one
  of the three (or ``StepClassification.UNKNOWN_TOOL`` for a hallucinated
  tool name), so a caller never has to guess which constructor to call.

Seam check (done, not silently adapted — reported to the orchestrator):
``ActionClaimGate`` and ``confirmation/reply_composer.py`` both consume a
bare ``ToolDecision`` and a ``TurnIntent`` of ``MUTATION`` /
``READ_OR_NONE`` — two values, not three or four. Re-reading both before
writing this module: NEITHER needs to change. Both operate at the
granularity of "the reply this whole turn produces to the staff member",
which happens exactly ONCE, after the read chain (if any) has already
finished — a multi-step read chain is entirely a pre-reply-composition
concern that never itself produces a reply. The terminal ``ToolDecision``
that ends a turn (the one that proposed the mutation, or the one with no
tool call at all) is still a single, ordinary ``ToolDecision`` and is
still exactly what ``compose_reply``'s ``tool_decision`` parameter expects
today. No incoherence found; no change made to either file.

GAP found, deliberately NOT closed here (flagged instead of silently
patched, per instruction): when a read chain ends via
``ReadStepOutcome.BUDGET_EXHAUSTED`` or a stuck-loop verdict from
``loop_detector.py`` — i.e. the model never reaches a ``FinalAnswer`` or a
``MutationDecision`` on its own — the (not-yet-built) loop still owes the
staff member SOME reply. Today's ``TurnIntent``/``compose_reply`` have no
dedicated branch for that; the natural fallback is
``TurnIntent.READ_OR_NONE`` with ``model_content=None``, which lands on
the existing generic ``_CLAIM_GATE_BLOCKED_FALLBACK`` template
("I want to make sure I get this right...") — serviceable, but written for
a different case (an ``ActionClaimGate`` BLOCK) and not worded for "I
searched but ran out of budget". Whoever wires the live loop should decide
whether that generic template is good enough or a fourth, dedicated
template belongs in ``reply_composer.py``; this module does not decide
that on its own.

Author: Claude Sonnet 5 (lane B3 — team-bot tool registry, directive #1 §2)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.registry import ToolKind, get_tool

from .tool_decision import ProposedToolCall, ToolDecision

__all__ = [
    "ABSOLUTE_MAX_READ_STEPS",
    "FinalAnswer",
    "MutationDecision",
    "ReadPlan",
    "ReadStep",
    "ReadStepOutcome",
    "ReadStepResult",
    "StepClassification",
    "UnknownToolError",
    "classify_step",
    "try_append_read_step",
]


# A hard, UNCONDITIONAL ceiling, independent of any env-driven budget
# (``team_bot.flags.max_read_steps``) — even a misconfigured
# ``TEAM_BOT_MAX_READ_STEPS`` cannot make a ``ReadPlan`` exceed this many
# steps, because it is a ``Field(max_length=...)`` on the type itself, not
# a value anything computes at runtime. The CONFIGURED budget (default 8
# per directive #1 §2, clamped to 1 — today's exact behavior — while the
# dark flag is off) is always <= this and is enforced separately, in
# ``try_append_read_step``, because it is a runtime value and cannot be a
# static Field constraint. 20 matches ``ToolDecision.discarded_tool_calls``'
# own ``max_length`` — this codebase's existing "generously more than any
# real scenario needs" ceiling, reused rather than inventing a new number.
ABSOLUTE_MAX_READ_STEPS = 20


class UnknownToolError(ValueError):
    """Raised when a ``ToolDecision`` names a tool absent from the F5
    registry entirely (a hallucinated tool name) — distinct from a
    kind-mismatch (calling the wrong constructor for a real, registered
    tool), which is a plain ``ValueError`` since it signals a caller/
    dispatch bug rather than a data-driven runtime shape a 14B model can
    actually produce.
    """


class StepClassification(StrEnum):
    """What ONE parsed ``ToolDecision`` is, for loop-dispatch purposes —
    deliberately NOT something ``ToolDecision`` itself knows (it only
    parses the wire shape; classifying a call against the F5 registry is a
    separate concern this module owns, so ``tool_decision.py`` stays
    registry-agnostic exactly as it is today)."""

    READ = "read"
    MUTATION = "mutation"
    FINAL = "final"
    UNKNOWN_TOOL = "unknown_tool"


def classify_step(decision: ToolDecision) -> StepClassification:
    """Pure, side-effect-free classification. Never raises — a
    hallucinated tool name is a real, expected shape for a 14B model to
    produce (not a programmer error), so it gets its own enum member
    rather than an exception here. A caller that needs to fail loudly for
    ``UNKNOWN_TOOL`` does so at the point it acts on the result, not here.
    """
    if decision.selected_tool is None:
        return StepClassification.FINAL
    spec = get_tool(decision.selected_tool.tool_name)
    if spec is None:
        return StepClassification.UNKNOWN_TOOL
    return StepClassification.READ if spec.kind is ToolKind.READ else StepClassification.MUTATION


class ReadStep(BaseModel):
    """One EXECUTED step of a read/search chain — a single call already
    confirmed, against the F5 registry, to be a ``ToolKind.READ`` tool.
    Immutable; a ``ReadPlan`` is built by appending these, never by
    mutating one in place."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_index: Annotated[int, Field(ge=0)]
    call: ProposedToolCall
    decided_at: datetime

    @classmethod
    def from_tool_decision(cls, decision: ToolDecision, *, step_index: int) -> ReadStep:
        if decision.selected_tool is None:
            raise ValueError("cannot build a ReadStep from a ToolDecision with no selected_tool")
        spec = get_tool(decision.selected_tool.tool_name)
        if spec is None:
            raise UnknownToolError(
                f"tool_name {decision.selected_tool.tool_name!r} is not in the F5 registry"
            )
        if spec.kind is not ToolKind.READ:
            raise ValueError(
                f"tool_name {decision.selected_tool.tool_name!r} is a {spec.kind.value} tool — "
                "ReadStep only represents a read call (use MutationDecision instead)"
            )
        return cls(step_index=step_index, call=decision.selected_tool, decided_at=decision.decided_at)


class ReadPlan(BaseModel):
    """An ORDERED, BOUNDED sequence of read/search steps taken so far this
    turn (directive #1 §2: "letture e ricerche: catene multi-step libere").

    This is the type that gives the multi-step relaxation its shape,
    without touching ``ToolDecision`` (still one raw message, still one
    selected call — unchanged) or ``MutationDecision`` (still exactly one
    call, below). ``steps`` is non-empty by construction — before any read
    has happened there is no ``ReadPlan`` yet, only ``None`` (see
    ``MutationDecision.preceding_reads`` / ``FinalAnswer.preceding_reads``,
    and ``try_append_read_step``'s own ``plan: ReadPlan | None`` parameter).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: Annotated[tuple[ReadStep, ...], Field(min_length=1, max_length=ABSOLUTE_MAX_READ_STEPS)]

    @model_validator(mode="after")
    def _steps_are_contiguous(self) -> ReadPlan:
        for expected_index, step in enumerate(self.steps):
            if step.step_index != expected_index:
                raise ValueError(
                    "ReadPlan.steps must be contiguous starting at 0 — step at position "
                    f"{expected_index} carries step_index={step.step_index}"
                )
        return self

    @classmethod
    def start(cls, first_step: ReadStep) -> ReadPlan:
        if first_step.step_index != 0:
            raise ValueError("a new ReadPlan must start with step_index 0")
        return cls(steps=(first_step,))

    def appended(self, next_step: ReadStep) -> ReadPlan:
        """Structural append only — checks step_index contiguity (a
        caller/programmer-error class of failure) and the hard
        ``ABSOLUTE_MAX_READ_STEPS`` ceiling (via the ``Field`` above,
        raising ``pydantic.ValidationError``). Does NOT know about the
        CONFIGURED, env-driven budget — see ``try_append_read_step`` for
        the entry point that enforces that one, since it is a runtime
        value and cannot be a static ``Field`` constraint."""
        if next_step.step_index != len(self.steps):
            raise ValueError(
                f"expected the next step to carry step_index={len(self.steps)}, got "
                f"{next_step.step_index}"
            )
        return ReadPlan(steps=(*self.steps, next_step))


class ReadStepOutcome(StrEnum):
    """Golden fixture ``team.tool-step-exhaustion`` (B6c,
    ``apps/backend-rag/backend/tests/duebot/goldens/team_fixtures.py``)
    names the expected shape verbatim: "The loop must stop at the budget
    and hand back a bounded, TYPED 'ran out of steps' outcome — never
    silently keep going or crash." This is that outcome — a returned
    value, never an exception, because running out of steps in a long
    legitimate read chain is an ordinary business trajectory, not a
    contract violation (contrast ``UnknownToolError``/the plain
    ``ValueError``s above, which ARE contract violations and do raise)."""

    APPENDED = "appended"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ReadStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ReadStepOutcome
    plan: ReadPlan


def try_append_read_step(plan: ReadPlan | None, decision: ToolDecision, *, max_steps: int) -> ReadStepResult:
    """The loop's actual per-step entry point for a READ call — the ONE
    place the CONFIGURED (soft, env-driven) step budget is enforced.

    ``max_steps`` is ``team_bot.flags.max_read_steps()`` — 1 when the dark
    flag is off (today's exact single-step behavior), up to
    ``TEAM_BOT_MAX_READ_STEPS`` (default 8, directive #1 §2's own example)
    once it is on. Passed in explicitly (never read from the environment
    here) so this function stays a pure, deterministic transform — the
    same "pure data/functions with no I/O" discipline every other unit in
    ``team_bot.loop``/``team_bot.registry`` already follows.

    Callers MUST classify with ``classify_step`` first and only call this
    for ``StepClassification.READ`` — passing a mutation or a no-call
    decision raises a plain ``ValueError`` (a dispatch bug, not a business
    outcome the caller needs a typed result for; ``classify_step`` exists
    precisely so no caller has to guess which case it is in).
    """
    if max_steps < 1:
        raise ValueError(f"max_steps must be >= 1, got {max_steps}")
    current_len = 0 if plan is None else len(plan.steps)
    if current_len >= max_steps:
        assert plan is not None  # current_len==0 can never reach here since max_steps>=1
        return ReadStepResult(outcome=ReadStepOutcome.BUDGET_EXHAUSTED, plan=plan)

    step = ReadStep.from_tool_decision(decision, step_index=current_len)
    new_plan = ReadPlan.start(step) if plan is None else plan.appended(step)
    return ReadStepResult(outcome=ReadStepOutcome.APPENDED, plan=new_plan)


class MutationDecision(BaseModel):
    """The ONE mutation this turn proposes. Directive #1 §2 keeps "one tool
    per turn" as a rule ONLY for mutations ("una mutazione per turno,
    sempre confermata") — this type is that rule made structural: ``call``
    is a single ``ProposedToolCall``, not a list, not a tuple, not an
    ``Optional`` wrapping a container that could hold more than one. There
    is no second slot to put a second call in, so there is nothing here
    for a future edit to silently widen back into ``ToolDecision``'s
    "select the first, discard the rest" shape (see that module's own
    docstring: the exact shape B4 measured neither serving stack actually
    honors for ``parallel_tool_calls: false``). A caller cannot construct
    a ``MutationDecision`` that represents two mutations; there is no
    field to represent a second one in.

    ``preceding_reads`` carries the read chain (if any) that led here, for
    AUDIT/CONTEXT ONLY — F6's confirmation state machine
    (``confirmation/store.py``) executes ``call`` alone, from the STORED,
    encrypted payload once confirmed; nothing in this field is ever
    re-executed or re-read at execute time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    call: ProposedToolCall
    model_name: Annotated[str, Field(min_length=1, max_length=128)]
    decided_at: datetime
    preceding_reads: ReadPlan | None = None

    @classmethod
    def from_tool_decision(
        cls, decision: ToolDecision, *, preceding_reads: ReadPlan | None = None
    ) -> MutationDecision:
        if decision.selected_tool is None:
            raise ValueError("cannot build a MutationDecision from a ToolDecision with no selected_tool")
        spec = get_tool(decision.selected_tool.tool_name)
        if spec is None:
            raise UnknownToolError(
                f"tool_name {decision.selected_tool.tool_name!r} is not in the F5 registry"
            )
        if spec.kind is not ToolKind.MUTATION:
            raise ValueError(
                f"tool_name {decision.selected_tool.tool_name!r} is a {spec.kind.value} tool — "
                "MutationDecision only represents a mutation call (use ReadStep instead)"
            )
        return cls(
            call=decision.selected_tool,
            model_name=decision.model_name,
            decided_at=decision.decided_at,
            preceding_reads=preceding_reads,
        )


class FinalAnswer(BaseModel):
    """The model proposed no tool call this turn at all — a final answer,
    a clarifying question, or an abstention. Ends the turn (with or
    without a preceding read chain) without ever proposing a mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: Annotated[str, Field(max_length=8_000)] | None
    model_name: Annotated[str, Field(min_length=1, max_length=128)]
    decided_at: datetime
    preceding_reads: ReadPlan | None = None

    @classmethod
    def from_tool_decision(
        cls, decision: ToolDecision, *, preceding_reads: ReadPlan | None = None
    ) -> FinalAnswer:
        if decision.selected_tool is not None:
            raise ValueError("cannot build a FinalAnswer from a ToolDecision that selected a tool call")
        return cls(
            content=decision.raw_content,
            model_name=decision.model_name,
            decided_at=decision.decided_at,
            preceding_reads=preceding_reads,
        )
