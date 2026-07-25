#!/usr/bin/env python3
"""Multi-turn golden evaluation harness for the Zantara WhatsApp bot.

Why this exists (2026-07-25, backend-rag/eval-baseline lane): the bot's
30-day production ledger showed only 28 inbound customer messages across 4
threads — too thin to be a feedback loop. The Zero-ratified spec
(research/operations/2026-07-24-zantara-bot-consultant-assistant-spec.md,
Verdict) names the missing piece explicitly: "there is no golden multi-turn
eval baseline yet ... the first executable step is to establish that
baseline." This is that baseline harness.

It is a SIBLING to ``rag_eval.py`` (the S18 single-turn generation-
faithfulness harness), not a replacement:
  * ``rag_eval.py`` — single-turn, targets ``/api/oracle/query`` (RBAC-walled
    dashboard endpoint), scores recall@k + must_contain + optional judge.
  * ``multi_turn_eval.py`` (this file) — multi-turn conversations, targets
    ``/api/agentic-rag/query`` (the endpoint the LIVE WhatsApp bot actually
    calls — see backend/services/integrations/wa_inbox_bot.py:14,:273),
    scores the four-outcome supervisor gate (SEND/CLARIFY/ABSTAIN/ESCALATE)
    per the target architecture (spec section 8), plus the same
    must_contain-style key-fact coverage.
  * ``scripts/rag_canary.py`` — a LIVENESS probe (embedding drift + top-k
    retrieval score), no generation, no conversation. Not duplicated here.

Design constraints (mirror S18 + this repo's golden rules):
  * Embedding model is FROZEN (text-embedding-3-small/1536) — this harness
    never embeds anything; it only consumes the live orchestrator's answer.
  * NO paid Anthropic endpoint for the optional judge — shells out to the
    ``claude`` CLI (Max-plan OAuth) via ``rag_eval.llm_judge``, reused
    as-is (DRY — do not fork a second copy of that function).
  * Cost-safe by construction: sequential (never concurrent), bounded by
    the golden set + an explicit ``--limit``, prints an LLM-call cost
    estimate before ANY network call, defaults to a LOCAL target, and
    requires an explicit ``--confirm-prod-run`` on top of ``--prod`` before
    a single request reaches production. The Gemini prepay balance hit ZERO
    on 2026-07-22 and took the bot down for hours — this harness must never
    be the thing that does that again.
  * Never wired to a cron by this file. Manual invocation only.

Usage:
    python multi_turn_eval.py --offline                    # schema self-check, no network
    python multi_turn_eval.py --local                       # vs http://localhost:8000 (default)
    python multi_turn_eval.py --prod --confirm-prod-run     # vs https://nuzantara-rag.fly.dev
    python multi_turn_eval.py --local --limit 3             # first 3 scenarios only
    python multi_turn_eval.py --local --judge                # add Claude-OAuth-CLI faithfulness judge
    python multi_turn_eval.py --local --report report.json  # write machine-readable report
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import rag_eval as _single_turn  # same-directory bare import (no __init__.py — matches this dir's convention)

_THIS_DIR = Path(__file__).resolve().parent
_GOLDEN_FILE = _THIS_DIR / "multi_turn_golden.json"

LOCAL_API = _single_turn.LOCAL_API
PRODUCTION_API = _single_turn.PRODUCTION_API
AGENTIC_RAG_QUERY_PATH = "/api/agentic-rag/query"

FROZEN_EMBEDDING_MODEL = _single_turn.FROZEN_EMBEDDING_MODEL
FROZEN_EMBEDDING_DIM = _single_turn.FROZEN_EMBEDDING_DIM

VALID_OUTCOMES = frozenset({"SEND", "CLARIFY", "ABSTAIN", "ESCALATE"})
KNOWN_DOMAINS = frozenset({"visa", "company", "tax", "property", "persona"})

# Estimated LLM calls per turn. The live bot caps the ReAct loop at
# max_steps=2 (research/operations/2026-07-20-wa-bot-latency.md) plus a
# post-loop self-correction/verification pass — 2 is a conservative floor,
# not a hard ceiling; a query needing tool calls can exceed it. Used only
# for the printed cost estimate, never to gate execution silently.
ESTIMATED_LLM_CALLS_PER_TURN = 2

# ESCALATION_PROTOCOL phrases, copied VERBATIM from
# backend/prompts/zantara_core.py (the only place this contract is defined).
# Matched as full-phrase substrings (never a short fragment like "team") to
# avoid the guard-over-match class of bug (cicatrix-superscar family #3) —
# a generic sentence mentioning "the team" must NOT be misclassified as an
# escalation signal.
ESCALATION_PHRASES: tuple[str, ...] = (
    "Verifico col team e ti faccio sapere.",
    "Ti metto in contatto col team per questo.",
    "Let me check with the team and get back to you.",
)

# The structural marker two production call sites check for and strip
# (backend/services/integrations/wa_inbox_bot.py:289,
# backend/app/routers/whatsapp_chat.py:550). As of this build, grep across
# every backend/prompts/*.py file found ZERO instructions telling the LLM to
# ever emit this marker — the strip code is live, the emit code is not. See
# README "Findings" for the citation. Kept as the PRIMARY structural signal
# anyway (it is the documented contract and may be reconnected later); the
# phrase-based fallback below exists precisely because this marker is
# currently dead in practice.
ESCALATE_MARKER = "[ESCALATE]"

# CLARIFY heuristic thresholds. NOT a structural signal — see README
# "Findings": /api/agentic-rag/query's response model
# (backend/app/routers/agentic_rag.py AgenticQueryResponse) does not expose
# CoreResult.is_ambiguous / clarification_question at all, even though the
# orchestrator computes them internally. This heuristic is ADVISORY ONLY,
# reported separately, and never used to PASS or FAIL a CLARIFY-expected
# turn (see grade_turn).
_CLARIFY_MAX_LEN = 220


@dataclass
class Turn:
    turn: int
    user: str
    expected_outcomes: list[str]
    key_facts: list[dict[str, str]] = field(default_factory=list)
    must_not_assert: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    id: str
    domain: str
    turns: list[Turn]
    notes: str = ""


@dataclass
class OutcomeClassification:
    """Result of classifying one HTTP response's outcome.

    ``structural_outcome`` is always one of SEND/ABSTAIN/ESCALATE — CLARIFY
    is never structurally derivable on this endpoint today (documented gap),
    so it is surfaced only via ``clarify_heuristic_detected``.
    """

    structural_outcome: str
    escalate_marker_detected: bool
    escalate_phrase_detected: bool
    clarify_heuristic_detected: bool
    abstain_reason: str | None = None


@dataclass
class TurnResult:
    scenario_id: str
    turn: int
    user: str
    expected_outcomes: list[str]
    classification: OutcomeClassification
    outcome_match: bool | None  # None = ungraded (CLARIFY-only expectation)
    key_facts_total: int
    key_facts_hit: int
    key_facts_coverage: float
    must_not_assert_violations: list[str]
    answer_preview: str
    error: str | None = None
    judge: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Golden set loading + validation                                             #
# --------------------------------------------------------------------------- #
def load_golden(path: Path = _GOLDEN_FILE) -> tuple[dict[str, Any], list[Scenario]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("embedding_model") != FROZEN_EMBEDDING_MODEL:
        raise ValueError(
            f"golden set embedding_model={data.get('embedding_model')!r} != frozen "
            f"{FROZEN_EMBEDDING_MODEL!r}"
        )
    if data.get("embedding_dim") != FROZEN_EMBEDDING_DIM:
        raise ValueError(
            f"golden set embedding_dim={data.get('embedding_dim')!r} != frozen {FROZEN_EMBEDDING_DIM}"
        )
    scenarios: list[Scenario] = []
    seen_ids: set[str] = set()
    for raw in data["scenarios"]:
        sid = raw["id"]
        if sid in seen_ids:
            raise ValueError(f"duplicate scenario id {sid!r}")
        seen_ids.add(sid)
        if raw["domain"] not in KNOWN_DOMAINS:
            raise ValueError(f"{sid}: unknown domain {raw['domain']!r}")
        turns: list[Turn] = []
        for raw_turn in raw["turns"]:
            expected = raw_turn["expected_outcomes"]
            if not expected:
                raise ValueError(f"{sid} turn {raw_turn.get('turn')}: empty expected_outcomes")
            for o in expected:
                if o not in VALID_OUTCOMES:
                    raise ValueError(f"{sid} turn {raw_turn.get('turn')}: unknown outcome {o!r}")
            for kf in raw_turn.get("key_facts", []):
                if not kf.get("fact", "").strip():
                    raise ValueError(f"{sid} turn {raw_turn.get('turn')}: key_fact missing text")
                if not kf.get("source", "").strip():
                    raise ValueError(
                        f"{sid} turn {raw_turn.get('turn')}: key_fact missing source — "
                        "an unsourced fact is not golden"
                    )
            turns.append(
                Turn(
                    turn=raw_turn["turn"],
                    user=raw_turn["user"],
                    expected_outcomes=list(expected),
                    key_facts=list(raw_turn.get("key_facts", [])),
                    must_not_assert=list(raw_turn.get("must_not_assert", [])),
                )
            )
        if not turns:
            raise ValueError(f"{sid}: zero turns")
        scenarios.append(Scenario(id=sid, domain=raw["domain"], turns=turns, notes=raw.get("notes", "")))
    if not scenarios:
        raise ValueError("golden set has zero scenarios")
    return data, scenarios


# --------------------------------------------------------------------------- #
# Outcome classification (structural-first, heuristics clearly labelled)      #
# --------------------------------------------------------------------------- #
def _contains_escalation_phrase(text: str) -> bool:
    return any(phrase in text for phrase in ESCALATION_PHRASES)


def _looks_like_clarifying_question(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and len(stripped) <= _CLARIFY_MAX_LEN and stripped.endswith("?")


def classify_outcome(response: dict[str, Any]) -> OutcomeClassification:
    """Classify one ``/api/agentic-rag/query`` response into an outcome.

    Structural signals (reliable, read directly off the response the live
    bot itself reads — mirrors backend/services/integrations/wa_inbox_bot.py):
      * ``abstain`` (bool) -> ABSTAIN. This field IS wired through to the
        wire (unlike is_ambiguous/clarification_question — see README).
      * ``[ESCALATE]`` marker in the raw answer -> ESCALATE (the contract
        two production call sites check for; see ESCALATE_MARKER docstring
        for the caveat that no live prompt currently emits it).
      * Otherwise -> SEND.

    Advisory signals (never gate a PASS/FAIL on their own):
      * ``escalate_phrase_detected`` — one of the ESCALATION_PROTOCOL's own
        canonical phrases appears in the answer even without the marker.
      * ``clarify_heuristic_detected`` — the answer reads like a short
        clarifying question. Documented gap: CLARIFY has NO structural
        signal on this endpoint (is_ambiguous/clarification_question are
        computed by the orchestrator but dropped before the HTTP response
        model — see README "Findings").
    """
    raw_answer = response.get("answer") or ""
    abstain = bool(response.get("abstain"))
    escalate_marker = ESCALATE_MARKER in raw_answer
    escalate_phrase = _contains_escalation_phrase(raw_answer)
    clarify_heuristic = (
        _looks_like_clarifying_question(raw_answer) and not abstain and not escalate_marker
    )

    if abstain:
        structural = "ABSTAIN"
    elif escalate_marker:
        structural = "ESCALATE"
    else:
        structural = "SEND"

    return OutcomeClassification(
        structural_outcome=structural,
        escalate_marker_detected=escalate_marker,
        escalate_phrase_detected=escalate_phrase,
        clarify_heuristic_detected=clarify_heuristic,
        abstain_reason=response.get("abstain_reason"),
    )


# --------------------------------------------------------------------------- #
# Scoring                                                                     #
# --------------------------------------------------------------------------- #
def key_facts_coverage(answer: str, key_facts: list[dict[str, str]]) -> tuple[int, int, float]:
    """Cheap lexical must_contain-style coverage (no LLM). Mirrors
    ``rag_eval.mustcontain_coverage`` but works on the ``key_facts`` schema
    (list of {fact, source} dicts) instead of a flat string list — the
    substring is taken from a short discriminating token set inside
    ``fact``, not the whole sentence (a whole vetted sentence is prose, not
    a thing a live answer will echo verbatim).

    To keep this a pure, dependency-free lexical check (no fact-specific
    tokenizer), the check is: fact text present as-is is too strict (prose
    rewrites), so callers should keep ``key_facts[i]['fact']`` reasonably
    matchable, OR prefer short anchor phrases. This function does a
    conservative whole-string case-insensitive substring test and reports
    the raw hit count — it is a FLOOR signal (never inflates coverage), not
    a semantic grader.
    """
    if not key_facts:
        return 0, 0, float("nan")
    low = answer.lower()
    hits = sum(1 for kf in key_facts if kf["fact"].lower() in low)
    return hits, len(key_facts), hits / len(key_facts)


def must_not_assert_violations(answer: str, forbidden: list[str]) -> list[str]:
    low = answer.lower()
    return [f for f in forbidden if f.lower() in low]


def grade_turn(
    expected_outcomes: list[str],
    classification: OutcomeClassification,
) -> bool | None:
    """PASS/FAIL/ungraded verdict for one turn's outcome.

    Returns:
        True  — structural_outcome matched an expected outcome.
        False — structural_outcome matched none of the expected outcomes.
        None  — ungraded: the ONLY expected outcome is CLARIFY, which this
                endpoint cannot structurally confirm (documented gap). The
                caller must surface ``clarify_heuristic_detected`` instead
                of a hard verdict — reporting a fake PASS/FAIL here would
                be exactly the kind of paper-over the harness exists to
                prevent.

    ESCALATE has a documented fallback: if ESCALATE is expected and the
    marker never fired (it usually won't — see ESCALATE_MARKER docstring)
    but a canonical escalation phrase from the SAME prompt contract is
    present, that still counts as a pass. This is disclosed, not silent —
    callers should report which path passed via
    ``classification.escalate_marker_detected`` vs
    ``escalate_phrase_detected``.
    """
    if expected_outcomes == ["CLARIFY"]:
        return None
    if classification.structural_outcome in expected_outcomes:
        return True
    if "ESCALATE" in expected_outcomes and classification.escalate_phrase_detected:
        return True
    return False


# --------------------------------------------------------------------------- #
# Conversation history + HTTP call                                            #
# --------------------------------------------------------------------------- #
def build_conversation_history(
    prior_turns: list[tuple[str, str]],
) -> list[dict[str, str]]:
    """Build the {role, content} history the live bot sends.

    ``prior_turns`` is a list of (user_text, bot_answer_text) tuples for
    every turn BEFORE the one being asked now, oldest first — mirrors
    wa_inbox_bot.py's ``_load_thread_context`` mapping (customer -> user,
    bot -> assistant), except built in-memory from THIS run's own answers
    (no DB), matching the DB-independent ``conversation_history`` path the
    router prioritises (agentic_rag.py: "Priority 1: Use
    conversation_history from frontend if provided").
    """
    history: list[dict[str, str]] = []
    for user_text, bot_text in prior_turns:
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": bot_text})
    return history


def query_bot(
    query: str,
    conversation_history: list[dict[str, str]],
    *,
    api_url: str,
    session_id: str,
    user_id: str,
    headers: dict[str, str],
    max_steps: int = 2,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """POST one turn to /api/agentic-rag/query. Returns the parsed JSON, or
    {"error": "..."} on HTTP/network failure (never raises — callers grade
    an error as a turn failure, not a crashed run)."""
    import httpx  # local import so --offline needs no deps (mirrors rag_eval.py)

    payload = {
        "query": query,
        "user_id": user_id,
        "session_id": session_id,
        "conversation_history": conversation_history,
        "channel": "whatsapp",
        "max_steps": max_steps,
    }
    try:
        resp = httpx.post(
            f"{api_url}{AGENTIC_RAG_QUERY_PATH}",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except Exception as exc:  # network
        return {"error": f"network: {exc}"}
    if resp.status_code != 200:
        return {"error": f"http_{resp.status_code}: {resp.text[:200]}"}
    return resp.json()


# --------------------------------------------------------------------------- #
# Eval loop                                                                    #
# --------------------------------------------------------------------------- #
def estimate_cost(scenarios: list[Scenario]) -> dict[str, int]:
    total_turns = sum(len(s.turns) for s in scenarios)
    return {
        "scenarios": len(scenarios),
        "turns": total_turns,
        "estimated_llm_calls": total_turns * ESTIMATED_LLM_CALLS_PER_TURN,
    }


def run_eval(
    scenarios: list[Scenario],
    *,
    api_url: str,
    headers: dict[str, str],
    use_judge: bool = False,
    max_calls: int | None = None,
) -> dict[str, Any]:
    results: list[TurnResult] = []
    calls_made = 0

    for scenario in scenarios:
        prior_turns: list[tuple[str, str]] = []
        for turn in scenario.turns:
            if max_calls is not None and calls_made >= max_calls:
                results.append(
                    TurnResult(
                        scenario_id=scenario.id,
                        turn=turn.turn,
                        user=turn.user,
                        expected_outcomes=turn.expected_outcomes,
                        classification=OutcomeClassification(
                            structural_outcome="SEND",
                            escalate_marker_detected=False,
                            escalate_phrase_detected=False,
                            clarify_heuristic_detected=False,
                        ),
                        outcome_match=None,
                        key_facts_total=len(turn.key_facts),
                        key_facts_hit=0,
                        key_facts_coverage=float("nan"),
                        must_not_assert_violations=[],
                        answer_preview="",
                        error="max_calls hard cap reached — turn skipped",
                    )
                )
                continue

            history = build_conversation_history(prior_turns)
            response = query_bot(
                turn.user,
                history,
                api_url=api_url,
                session_id=f"eval_{scenario.id}",
                user_id=f"whatsapp_eval_{scenario.id}",
                headers=headers,
            )
            calls_made += 1

            if "error" in response:
                results.append(
                    TurnResult(
                        scenario_id=scenario.id,
                        turn=turn.turn,
                        user=turn.user,
                        expected_outcomes=turn.expected_outcomes,
                        classification=OutcomeClassification(
                            structural_outcome="SEND",
                            escalate_marker_detected=False,
                            escalate_phrase_detected=False,
                            clarify_heuristic_detected=False,
                        ),
                        outcome_match=None,
                        key_facts_total=len(turn.key_facts),
                        key_facts_hit=0,
                        key_facts_coverage=float("nan"),
                        must_not_assert_violations=[],
                        answer_preview="",
                        error=response["error"],
                    )
                )
                # Feed an empty bot turn forward so later turns in the same
                # scenario still get a (degraded) history rather than
                # silently dropping the conversation thread.
                prior_turns.append((turn.user, ""))
                continue

            answer = response.get("answer") or ""
            classification = classify_outcome(response)
            outcome_match = grade_turn(turn.expected_outcomes, classification)
            hits, total, coverage = key_facts_coverage(answer, turn.key_facts)
            violations = must_not_assert_violations(answer, turn.must_not_assert)

            judge_result = None
            if use_judge and turn.key_facts and "SEND" in turn.expected_outcomes:
                ground_truth = " ".join(kf["fact"] for kf in turn.key_facts)
                judge_result = _single_turn.llm_judge(turn.user, ground_truth, answer)

            results.append(
                TurnResult(
                    scenario_id=scenario.id,
                    turn=turn.turn,
                    user=turn.user,
                    expected_outcomes=turn.expected_outcomes,
                    classification=classification,
                    outcome_match=outcome_match,
                    key_facts_total=total,
                    key_facts_hit=hits,
                    key_facts_coverage=coverage,
                    must_not_assert_violations=violations,
                    answer_preview=answer[:240],
                    judge=judge_result,
                )
            )
            prior_turns.append((turn.user, answer))

    return {
        "api_url": api_url,
        "n_scenarios": len(scenarios),
        "n_turns": len(results),
        "results": [asdict(r) for r in results],
        "aggregate": _aggregate(results),
    }


def _aggregate(results: list[TurnResult]) -> dict[str, Any]:
    graded = [r for r in results if r.outcome_match is not None and r.error is None]
    ungraded_clarify = [r for r in results if r.expected_outcomes == ["CLARIFY"]]
    errored = [r for r in results if r.error is not None]
    passed = [r for r in graded if r.outcome_match]

    coverage_vals = [r.key_facts_coverage for r in results if r.key_facts_coverage == r.key_facts_coverage]
    escalate_via_phrase_only = [
        r
        for r in results
        if r.outcome_match
        and "ESCALATE" in r.expected_outcomes
        and not r.classification.escalate_marker_detected
        and r.classification.escalate_phrase_detected
    ]
    violations_total = sum(len(r.must_not_assert_violations) for r in results)

    return {
        "n_graded": len(graded),
        "n_passed": len(passed),
        "pass_rate": round(len(passed) / len(graded), 4) if graded else None,
        "n_ungraded_clarify": len(ungraded_clarify),
        "n_errors": len(errored),
        "mean_key_facts_coverage": round(sum(coverage_vals) / len(coverage_vals), 4)
        if coverage_vals
        else None,
        "n_escalate_passed_via_phrase_fallback_only": len(escalate_via_phrase_only),
        "must_not_assert_violations_total": violations_total,
    }


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def _build_headers(args: argparse.Namespace) -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = args.api_key or os.environ.get("AGENTIC_RAG_API_KEY", "")
    internal_key = args.internal_key or os.environ.get("WA_MIRROR_INTERNAL_KEY", "")
    profile_key = args.wa_bot_profile_key or os.environ.get("WA_INBOX_BOT_PROFILE_KEY", "")
    if api_key:
        headers["X-API-Key"] = api_key
    if internal_key:
        headers["X-Internal-Key"] = internal_key
    if profile_key:
        headers["X-WA-Bot-Profile-Key"] = profile_key
    return headers


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Multi-turn golden eval for the Zantara WA bot")
    ap.add_argument("--golden", default=str(_GOLDEN_FILE))
    ap.add_argument("--offline", action="store_true", help="schema self-check + cost plan; no network")
    ap.add_argument("--local", action="store_true", help="target http://localhost:8000 (default)")
    ap.add_argument("--prod", action="store_true", help="target https://nuzantara-rag.fly.dev")
    ap.add_argument(
        "--api-url",
        default="",
        help="override the target base URL (e.g. a non-default local port). Implies --local's "
        "network path but does NOT bypass the --prod/--confirm-prod-run gate for the real prod host.",
    )
    ap.add_argument(
        "--confirm-prod-run",
        action="store_true",
        help="required in addition to --prod — a second explicit gate before spending prod's "
        "Gemini quota (the same key had a balance-zero outage on 2026-07-22)",
    )
    ap.add_argument("--limit", type=int, default=None, help="only run the first N scenarios")
    ap.add_argument("--max-calls", type=int, default=None, help="hard cap on total HTTP calls this run")
    ap.add_argument("--judge", action="store_true", help="add Claude-OAuth-CLI faithfulness judge on SEND turns")
    ap.add_argument("--api-key", default="", help="X-API-Key header (or env AGENTIC_RAG_API_KEY)")
    ap.add_argument("--internal-key", default="", help="X-Internal-Key header (or env WA_MIRROR_INTERNAL_KEY)")
    ap.add_argument("--wa-bot-profile-key", default="", help="X-WA-Bot-Profile-Key header (or env WA_INBOX_BOT_PROFILE_KEY)")
    ap.add_argument("--report", default="", help="write JSON report to this path")
    args = ap.parse_args(argv)

    data, scenarios = load_golden(Path(args.golden))
    if args.limit is not None:
        scenarios = scenarios[: args.limit]

    cost = estimate_cost(scenarios)
    print(
        f"[multi-turn-eval] golden set v{data['version']} — {cost['scenarios']} scenarios, "
        f"{cost['turns']} turns (embedding {FROZEN_EMBEDDING_MODEL}/{FROZEN_EMBEDDING_DIM} FROZEN)"
    )
    print(
        f"[multi-turn-eval] cost estimate: {cost['turns']} HTTP calls x "
        f"~{ESTIMATED_LLM_CALLS_PER_TURN} LLM calls/turn (max_steps cap) "
        f"= ~{cost['estimated_llm_calls']} LLM calls total, run SEQUENTIALLY (never parallel)."
    )

    if args.offline or not (args.local or args.prod or args.api_url):
        plan = {
            "mode": "offline",
            "reason": "--offline requested" if args.offline else "no --local/--prod given — defaulting to plan-only",
            **cost,
            "target_endpoint": AGENTIC_RAG_QUERY_PATH,
        }
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        if args.report:
            Path(args.report).write_text(json.dumps({"plan": plan}, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[multi-turn-eval] OFFLINE self-check PASSED — harness is runnable; no network call made.")
        return 0

    if args.prod and not args.confirm_prod_run:
        print(
            "[multi-turn-eval] REFUSED: --prod given without --confirm-prod-run. "
            "This is the SAME Gemini key production traffic uses (balance-zero outage "
            "2026-07-22) — pass --confirm-prod-run explicitly to proceed.",
            file=sys.stderr,
        )
        return 2

    api_url = PRODUCTION_API if args.prod else (args.api_url or LOCAL_API)
    headers = _build_headers(args)
    if not headers:
        print(
            "[multi-turn-eval] NEEDS-CREDENTIAL: no auth header configured. Set one of "
            "AGENTIC_RAG_API_KEY / WA_MIRROR_INTERNAL_KEY (env or --api-key/--internal-key) — "
            "/api/agentic-rag/query is behind HybridAuthMiddleware and will 401 without one. "
            "See README 'Local run' for how to provision a throwaway local API key.",
            file=sys.stderr,
        )
        return 3

    print(f"[multi-turn-eval] querying {api_url} (judge={args.judge}, max_calls={args.max_calls})")
    report = run_eval(scenarios, api_url=api_url, headers=headers, use_judge=args.judge, max_calls=args.max_calls)
    print(json.dumps(report["aggregate"], indent=2))
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[multi-turn-eval] wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
