"""ToneCouncil — 3-round multi-LLM register selection (design §3).

Round 0: 3 proponents in parallel (isolated) — each picks a register.
Round 1: 3 proponents in parallel (challenge) — each scores the non-own
         proposals and criticizes the worst. Forces structural dissent.
Round 2: judge (Claude Sonnet) — sees everything, history last 14d, scars,
         hard rules. Veto allowed.

Design references:
- docs/war-room-2.0-design.md §3
- SYMBIOSIS.md:109-121 (Pilastro 4 Confronto)
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.council.prompts import (
    render_round_0_prompt,
    render_round_1_prompt,
    render_round_2_judge_prompt,
)
from backend.services.war_room.models import RegisterTone

logger = logging.getLogger(__name__)


ALL_REGISTERS: tuple[str, ...] = tuple(r.value for r in RegisterTone)

# Hard rules (§3.2 Round 2)
MAX_SAME_REGISTER_7D: int = 3
MAX_IRONIC_OR_MILITANT_7D: int = 3
GROUPTHINK_CONCORDANCE_THRESHOLD: float = 0.90


@dataclass
class CouncilProposal:
    author: str
    register: str
    rationale: str
    risk: str
    example_headline: str
    raw_output: str = ""
    ok: bool = True
    error: str | None = None


@dataclass
class CouncilChallenge:
    author: str
    best_not_mine_author: str | None = None
    best_not_mine_motivation: str = ""
    worst_author: str | None = None
    worst_critique: str = ""
    raw_output: str = ""
    ok: bool = True
    error: str | None = None


@dataclass
class JudgeDecision:
    chosen_register: str
    rationale: str
    rejected_registers: list[str] = field(default_factory=list)
    hard_rules_triggered: list[str] = field(default_factory=list)
    groupthink_detected: bool = False
    raw_output: str = ""


@dataclass
class ToneCouncilResult:
    topic: str
    decision: JudgeDecision
    proposals: list[CouncilProposal]
    challenges: list[CouncilChallenge]
    registers_last_14d: dict[str, int]
    scars_used: int
    degraded: bool = False
    duration_ms: float = 0.0
    runner_outputs: dict[str, list[RunnerResult]] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "chosen_register": self.decision.chosen_register,
            "rationale": self.decision.rationale,
            "rejected_registers": self.decision.rejected_registers,
            "hard_rules_triggered": self.decision.hard_rules_triggered,
            "groupthink_detected": self.decision.groupthink_detected,
            "degraded": self.degraded,
            "proposals": [
                {
                    "author": p.author,
                    "register": p.register,
                    "rationale": p.rationale,
                    "risk": p.risk,
                    "example_headline": p.example_headline,
                    "ok": p.ok,
                    "error": p.error,
                }
                for p in self.proposals
            ],
            "challenges": [
                {
                    "author": c.author,
                    "best_not_mine": {
                        "author": c.best_not_mine_author,
                        "motivation": c.best_not_mine_motivation,
                    },
                    "worst": {
                        "author": c.worst_author,
                        "critique": c.worst_critique,
                    },
                    "ok": c.ok,
                    "error": c.error,
                }
                for c in self.challenges
            ],
            "registers_last_14d": self.registers_last_14d,
            "scars_used": self.scars_used,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


def _is_valid_register(value: str | None) -> bool:
    return bool(value) and value in ALL_REGISTERS


def _concordance_ratio(proposals: list[CouncilProposal]) -> float:
    """Fraction of non-error proposals that picked the majority register."""
    valid = [p for p in proposals if p.ok and _is_valid_register(p.register)]
    if not valid:
        return 0.0
    counts = Counter(p.register for p in valid)
    top = counts.most_common(1)[0][1]
    return top / len(valid)


class ToneCouncil:
    """Run a 3-round tone deliberation.

    History + scars are injected by the caller (so the council stays pure-function-ish
    and testable without a DB). Typical wiring:

        council = ToneCouncil(
            proponents={"claude": runner_c, "gemini": runner_g, "deepseek": runner_d},
            judge=runner_c_sonnet,
        )
        result = await council.run(topic=..., research_json=..., registers_last_14d=...)
    """

    def __init__(
        self,
        proponents: dict[str, CLIRunner],
        judge: CLIRunner,
        *,
        brand_constraints: str = "",
        round_0_timeout: int = 90,
        round_1_timeout: int = 60,
        round_2_timeout: int = 60,
    ) -> None:
        if not proponents:
            raise ValueError("ToneCouncil requires at least one proponent")
        self.proponents = proponents
        self.judge = judge
        self.brand_constraints = brand_constraints
        self.round_0_timeout = round_0_timeout
        self.round_1_timeout = round_1_timeout
        self.round_2_timeout = round_2_timeout
        self.logger = logger

    # ── Main entry ──────────────────────────────────────────────────────

    async def run(
        self,
        *,
        topic: str,
        research_json: str | dict[str, Any] = "{}",
        registers_last_14d: dict[str, int] | None = None,
        recent_scars: list[str] | None = None,
        self_reflections: dict[str, str] | None = None,
    ) -> ToneCouncilResult:
        # Langfuse POC: wrap deliberation in a parent span so each LLM call
        # (Claude / Gemini / DeepSeek / judge) shows up as a child. No-op
        # when LANGFUSE_ENABLED=false or keys missing.
        lf_span_cm = _maybe_council_span(
            topic=topic,
            proponents=list(self.proponents.keys()),
        )
        async with lf_span_cm as _lf_span:
            return await self._run_impl(
                topic=topic,
                research_json=research_json,
                registers_last_14d=registers_last_14d,
                recent_scars=recent_scars,
                self_reflections=self_reflections,
                _lf_span=_lf_span,
            )

    async def _run_impl(
        self,
        *,
        topic: str,
        research_json: str | dict[str, Any] = "{}",
        registers_last_14d: dict[str, int] | None = None,
        recent_scars: list[str] | None = None,
        self_reflections: dict[str, str] | None = None,
        _lf_span: Any = None,
    ) -> ToneCouncilResult:
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        history = registers_last_14d or {}
        scars = recent_scars or []
        reflections = self_reflections or {}

        research_str = (
            research_json if isinstance(research_json, str) else json.dumps(research_json)
        )

        runner_outputs: dict[str, list[RunnerResult]] = {
            name: [] for name in self.proponents
        }
        runner_outputs["judge"] = []

        # Round 0 — propose (parallel, isolated)
        proposals = await self._round_0_propose(
            topic=topic,
            research_str=research_str,
            reflections=reflections,
            runner_outputs=runner_outputs,
        )
        valid_proposals = [p for p in proposals if p.ok and _is_valid_register(p.register)]
        degraded = len(valid_proposals) < len(self.proponents)

        # Round 1 — challenge (parallel)
        challenges = await self._round_1_challenge(
            proposals=proposals,
            runner_outputs=runner_outputs,
        )

        # Round 2 — judge (sequential, single call)
        decision = await self._round_2_judge(
            topic=topic,
            proposals=proposals,
            challenges=challenges,
            registers_last_14d=history,
            recent_scars=scars,
            runner_outputs=runner_outputs,
        )

        # Enforce hard rules even if judge ignored them
        decision = self._apply_hard_rules(
            decision=decision,
            proposals=valid_proposals,
            history=history,
        )

        duration_ms = (time.perf_counter() - t0) * 1000
        result = ToneCouncilResult(
            topic=topic,
            decision=decision,
            proposals=proposals,
            challenges=challenges,
            registers_last_14d=dict(history),
            scars_used=len(scars),
            degraded=degraded,
            duration_ms=duration_ms,
            runner_outputs=runner_outputs,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

        if _lf_span is not None:
            try:
                _lf_span.update(
                    output={
                        "chosen_register": getattr(decision, "chosen_register", None),
                        "rationale": getattr(decision, "rationale", None),
                        "duration_ms": duration_ms,
                        "degraded": degraded,
                        "scars_used": len(scars),
                    },
                )
            except Exception:
                pass

        return result

    # ── Rounds ──────────────────────────────────────────────────────────

    async def _round_0_propose(
        self,
        *,
        topic: str,
        research_str: str,
        reflections: dict[str, str],
        runner_outputs: dict[str, list[RunnerResult]],
    ) -> list[CouncilProposal]:
        import asyncio

        prompts = {
            name: render_round_0_prompt(
                proponent=name,
                topic=topic,
                research_json=research_str,
                brand_constraints=self.brand_constraints,
                self_reflection=reflections.get(name, ""),
            )
            for name in self.proponents
        }

        async def _one(name: str, runner: CLIRunner) -> CouncilProposal:
            parsed, result = await runner.run_json(
                prompts[name], timeout=self.round_0_timeout,
            )
            runner_outputs[name].append(result)
            if not result.ok or parsed is None:
                return CouncilProposal(
                    author=name,
                    register="",
                    rationale="",
                    risk="",
                    example_headline="",
                    raw_output=result.output,
                    ok=False,
                    error=result.error or "invalid JSON",
                )
            return CouncilProposal(
                author=name,
                register=str(parsed.get("register", "")).strip().lower(),
                rationale=str(parsed.get("rationale", "")).strip(),
                risk=str(parsed.get("risk", "")).strip(),
                example_headline=str(parsed.get("example_headline", "")).strip(),
                raw_output=result.output,
                ok=True,
            )

        return await asyncio.gather(
            *[_one(name, runner) for name, runner in self.proponents.items()]
        )

    async def _round_1_challenge(
        self,
        *,
        proposals: list[CouncilProposal],
        runner_outputs: dict[str, list[RunnerResult]],
    ) -> list[CouncilChallenge]:
        import asyncio

        payload = json.dumps(
            [
                {
                    "author": p.author,
                    "register": p.register,
                    "rationale": p.rationale,
                    "risk": p.risk,
                    "example_headline": p.example_headline,
                    "ok": p.ok,
                }
                for p in proposals
            ],
            ensure_ascii=False,
        )

        async def _one(name: str, runner: CLIRunner) -> CouncilChallenge:
            prompt = render_round_1_prompt(name, payload)
            parsed, result = await runner.run_json(prompt, timeout=self.round_1_timeout)
            runner_outputs[name].append(result)
            if not result.ok or parsed is None:
                return CouncilChallenge(
                    author=name,
                    raw_output=result.output,
                    ok=False,
                    error=result.error or "invalid JSON",
                )
            best = parsed.get("best_not_mine") or {}
            worst = parsed.get("worst") or {}
            return CouncilChallenge(
                author=name,
                best_not_mine_author=str(best.get("author", "")).strip().lower() or None,
                best_not_mine_motivation=str(best.get("motivation", "")).strip(),
                worst_author=str(worst.get("author", "")).strip().lower() or None,
                worst_critique=str(worst.get("critique", "")).strip(),
                raw_output=result.output,
                ok=True,
            )

        return await asyncio.gather(
            *[_one(name, runner) for name, runner in self.proponents.items()]
        )

    async def _round_2_judge(
        self,
        *,
        topic: str,
        proposals: list[CouncilProposal],
        challenges: list[CouncilChallenge],
        registers_last_14d: dict[str, int],
        recent_scars: list[str],
        runner_outputs: dict[str, list[RunnerResult]],
    ) -> JudgeDecision:
        proposals_json = json.dumps(
            [
                {
                    "author": p.author,
                    "register": p.register,
                    "rationale": p.rationale,
                    "risk": p.risk,
                    "example_headline": p.example_headline,
                    "ok": p.ok,
                }
                for p in proposals
            ],
            ensure_ascii=False,
        )
        challenges_json = json.dumps(
            [
                {
                    "author": c.author,
                    "best_not_mine": c.best_not_mine_author,
                    "worst": c.worst_author,
                }
                for c in challenges
            ],
            ensure_ascii=False,
        )
        history_str = ", ".join(
            f"{k}={v}" for k, v in sorted(registers_last_14d.items())
        )
        scars_str = "; ".join(recent_scars[:5]) if recent_scars else ""

        prompt = render_round_2_judge_prompt(
            topic=topic,
            brand_constraints=self.brand_constraints,
            registers_last_14d=history_str,
            recent_scars=scars_str,
            all_proposals_json=proposals_json,
            challenges_json=challenges_json,
        )
        parsed, result = await self.judge.run_json(prompt, timeout=self.round_2_timeout)
        runner_outputs["judge"].append(result)

        if not result.ok or parsed is None:
            # fallback: pick majority among ok proposals
            return self._fallback_decision(proposals)

        chosen = str(parsed.get("chosen_register", "")).strip().lower()
        if not _is_valid_register(chosen):
            return self._fallback_decision(proposals)

        return JudgeDecision(
            chosen_register=chosen,
            rationale=str(parsed.get("rationale", "")).strip(),
            rejected_registers=[
                str(r).strip().lower()
                for r in parsed.get("rejected_registers", []) or []
            ],
            hard_rules_triggered=[
                str(r).strip() for r in parsed.get("hard_rules_triggered", []) or []
            ],
            groupthink_detected=bool(parsed.get("groupthink_detected", False)),
            raw_output=result.output,
        )

    # ── Hard-rule enforcement ───────────────────────────────────────────

    def _apply_hard_rules(
        self,
        *,
        decision: JudgeDecision,
        proposals: list[CouncilProposal],
        history: dict[str, int],
    ) -> JudgeDecision:
        """Enforce structural rules judge may have overlooked.

        Deterministic safety layer (§3.2 "Hard Rules"). If judge chose a register
        that would violate a rule, we swap to the next-best valid register
        (majority of proposals that doesn't violate) or the least-used register
        in the last 14d among ok proposals.
        """
        violations: list[str] = []
        chosen = decision.chosen_register

        if history.get(chosen, 0) >= MAX_SAME_REGISTER_7D:
            violations.append(
                f"max_same_register_7d_exceeded:{chosen}={history[chosen]}"
            )
        if chosen in ("ironico", "militante"):
            cinico_like = history.get("ironico", 0) + history.get("militante", 0)
            if cinico_like >= MAX_IRONIC_OR_MILITANT_7D:
                violations.append(
                    f"max_ironic_militant_7d_exceeded:sum={cinico_like}"
                )

        # Groupthink detection (independent of what judge said)
        concordance = _concordance_ratio(proposals)
        groupthink = concordance >= GROUPTHINK_CONCORDANCE_THRESHOLD
        if groupthink and not decision.groupthink_detected:
            decision.groupthink_detected = True

        if not violations and not groupthink:
            if decision.hard_rules_triggered:
                return decision
            return decision

        # Pick fallback register: least-used among valid ones different from chosen.
        proposed_registers = {
            p.register for p in proposals if p.ok and _is_valid_register(p.register)
        }
        candidates = [
            r for r in ALL_REGISTERS
            if r != chosen and r in proposed_registers
        ] or [
            r for r in ALL_REGISTERS if r != chosen
        ]
        candidates.sort(key=lambda r: history.get(r, 0))
        new_chosen = candidates[0] if candidates else chosen

        if new_chosen == chosen:
            return decision  # no viable swap — accept violation transparently

        self.logger.info(
            "hard-rule enforcement swapped %s -> %s (violations=%s groupthink=%s)",
            chosen,
            new_chosen,
            violations,
            groupthink,
        )
        decision.rejected_registers = list({
            *decision.rejected_registers,
            chosen,
        })
        decision.hard_rules_triggered = list({
            *decision.hard_rules_triggered,
            *violations,
            *(["groupthink_swap"] if groupthink else []),
        })
        decision.chosen_register = new_chosen
        decision.rationale = (
            (decision.rationale or "")
            + f"\n[hard-rule enforcement: swapped from {chosen} to {new_chosen}]"
        ).strip()
        return decision

    def _fallback_decision(
        self, proposals: list[CouncilProposal],
    ) -> JudgeDecision:
        """Pick majority register among ok proposals — used if judge fails."""
        valid = [p for p in proposals if p.ok and _is_valid_register(p.register)]
        if valid:
            counts = Counter(p.register for p in valid)
            chosen = counts.most_common(1)[0][0]
        else:
            chosen = RegisterTone.ANALITICO.value  # safest editorial default
        return JudgeDecision(
            chosen_register=chosen,
            rationale="judge unavailable — fallback to majority-of-proposals (analitico if none)",
            hard_rules_triggered=["judge_fallback"],
            raw_output="",
        )


# ── Langfuse POC helpers (kept at module scope for testability) ─────────


class _NullAsyncCM:
    """Async context manager that yields None — used when Langfuse is off."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> None:
        return None


class _SyncSpanAsyncCM:
    """Adapt a sync Langfuse span CM to an `async with` caller."""

    def __init__(self, sync_cm: Any) -> None:
        self._sync_cm = sync_cm
        self._span: Any = None

    async def __aenter__(self) -> Any:
        self._span = self._sync_cm.__enter__()
        return self._span

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._sync_cm.__exit__(exc_type, exc, tb)


def _maybe_council_span(*, topic: str, proponents: list[str]) -> Any:
    """Return an async context manager wrapping a Langfuse span (or a no-op)."""
    try:
        from backend.core.observability import init_observability, is_enabled
    except Exception:
        return _NullAsyncCM()

    if not is_enabled():
        return _NullAsyncCM()
    try:
        init_observability(service_name="nuzantara-council")
        from langfuse import get_client

        lf = get_client()
        if lf is None:
            return _NullAsyncCM()
        sync_cm = lf.start_as_current_span(
            name="tone_council.run",
            input={"topic": topic[:500]},
            metadata={"proponents": proponents},
        )
        return _SyncSpanAsyncCM(sync_cm)
    except Exception:
        return _NullAsyncCM()
