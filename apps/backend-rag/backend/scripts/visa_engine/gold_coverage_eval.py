"""Offline single-persona evaluator for gold-coverage authoring (2026-08-28).

Evaluates ONE synthetic persona (baseline gold facts + ``overrides``) against the
highest signed PRODUCTION pack in ``contracts/packs`` through the SAME path the
offline gold replay uses (``gold_replay_driver.replay_offline_decisions``): verify
→ compile → ``evaluator.evaluate`` → ``apply_public_policy_adapters``.  It prints
the normalized decision as JSON and never writes anything.  Like the driver's
offline mode it proves what the repository artifact does, not what production
serves.

Usage::

    cd apps/backend-rag && PYTHONPATH=. python -m backend.scripts.visa_engine.gold_coverage_eval \
        --persona /path/persona.json            # {"label": "...", "overrides": {"intent.purposes": {"status":"KNOWN","value":["TOURISM"]}, ...}}
    ... --dump-baseline                          # the shared gold baseline facts
    ... --dump-registry                          # every FactPath the engine knows

A persona file may also carry ``"expected_state"`` / ``"expected_candidates"``;
they are echoed back next to the actual decision so an authoring lane can see
its own miss without a second tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    _offline_identity_provider,
    _parse_utc,
    _repository_trust_store,
    build_persona_request,
    select_highest_repository_pack,
)
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.api_models import VisaOracleEvaluateRequest
from backend.services.visa_engine.bundle import verify_rule_pack
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import Persona


def _registry_rows() -> list[dict[str, Any]]:
    reg = DEFAULT_FACT_REGISTRY
    rows: list[dict[str, Any]] = []
    entries: Any = None
    for attr in (
        "_specs",
        "specs",
        "entries",
        "_entries",
        "definitions",
        "_definitions",
        "paths",
        "_paths",
        "by_path",
        "_by_path",
    ):
        cand = getattr(reg, attr, None)
        if cand is None:
            continue
        entries = cand() if callable(cand) else cand
        break
    if entries is None:
        entries = vars(reg)
    items = (
        entries.items()
        if hasattr(entries, "items")
        else [(getattr(e, "path", str(e)), e) for e in entries]
    )
    for key, val in items:
        if isinstance(val, dict):
            desc = {k: str(v)[:80] for k, v in val.items()}
        else:
            desc = {
                a: str(getattr(val, a))[:80]
                for a in dir(val)
                if not a.startswith("_") and not callable(getattr(val, a, None))
            }
        dotted = getattr(key, "value", key)
        desc.pop("path", None)
        rows.append({"path": str(dotted), **desc})
    return rows


@lru_cache(maxsize=4)
def _verified_compiled_pack(observed_at: datetime) -> tuple[Path, CompiledRulePack]:
    """Verify + compile the highest signed PRODUCTION pack, once per instant.

    Memoized on ``observed_at`` and ONLY on it, because that is the sole
    caller-supplied input either step grades against: a different instant is
    a different freshness/signature-validity verdict and must re-verify, and
    two calls at the SAME instant on the same checkout cannot disagree. The
    saving is not cosmetic — ``verify_rule_pack`` costs ~1.6s per call
    (measured 2026-09-06 on seq-19), which a 43-walk census pays 43 times
    for one useful answer.

    ``maxsize=4`` bounds the unpinned callers: ``_evaluate(as_of=None)``
    resolves a fresh ``datetime.now(UTC)`` per call, so those keys are all
    distinct and would otherwise grow without limit.

    The cache also skips re-READING ``PACKS_DIR``; a process that writes a
    new signed pack mid-run must call ``_verified_compiled_pack.cache_clear()``
    before evaluating against it.
    """

    pack_path, raw_pack = select_highest_repository_pack(PACKS_DIR)
    verified = verify_rule_pack(
        raw_pack, trust_store=_repository_trust_store(), observed_at=observed_at
    )
    return pack_path, build_compiled_pack(verified.pack)


#: Every field ``_evaluate`` names when it rebuilds the request to carry
#: disclosure flags. Pinned because the rebuild is BY HAND and nothing else ties
#: it to the model (council round 5, tp1-qwen3.8-max): a sixth field added to
#: ``VisaOracleEvaluateRequest`` would be dropped from the flagged request
#: silently, and it would stay silent downstream because
#: ``_apply_disclosed_review_flags`` overwrites candidates, missing facts,
#: no-path reasons and quotes anyway — the flagged decision would look exactly
#: as expected while being computed from a request the browser never sends.
_REBUILT_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "assessment_id",
        "collected_at",
        "facts",
        "disclosed_review_flags",
    }
)


def _evaluate(
    overrides: dict[str, dict[str, Any]],
    label: str,
    *,
    as_of: datetime | None = None,
    disclosed_review_flags: Sequence[str] = (),
) -> dict[str, Any]:
    # `disclosed_review_flags` defaults to the empty sequence, so every existing
    # caller — the coverage floor, the authoring CLI — evaluates exactly as
    # before. It exists because a walk's facts are only HALF its wire request:
    # the browser also sends whatever `mapDisclosedReviewFlags` (fact-mapper.ts)
    # raised, and `evaluate_path.py::_apply_disclosed_review_flags` rewrites the
    # whole decision to HUMAN_REVIEW_REQUIRED on any one of them. Evaluating
    # facts alone therefore measures a funnel the applicant never meets — which
    # is why the interview-walk census reported 0 human review from the day it
    # was written (2026-09-06) until the corpus gained this field. The
    # flags are validated through `VisaOracleEvaluateRequest`, never injected
    # into `apply_public_policy_adapters` directly, so an unknown flag name is a
    # loud ValidationError here and not a silently ignored string.
    # `as_of` defaults to None so production behaviour (evaluate at the real
    # wall clock) is unchanged. It exists so a TEST can pin the instant to the
    # pack's own `created_at` instead: the selected pack's `source_records`
    # carry a freshness_policy (MAX_AGE_SINCE_VERIFIED_AT) with as little as a
    # 604800s (7-day) window, so evaluating at `datetime.now(UTC)` is a clock
    # bomb — it is guaranteed to go stale exactly 7 days after the newest
    # source's verified_at, with zero code change, and it took the ENTIRE
    # merge queue down on 2026-08-30 (verified_at 2026-08-23T10:44:48Z +
    # 604800s = 2026-08-30T10:44:48Z). At that instant the engine correctly
    # started returning HUMAN_REVIEW_REQUIRED — the engine was right, the
    # wall-clock evaluation was the bug.
    now = as_of if as_of is not None else datetime.now(UTC)
    pack_path, compiled = _verified_compiled_pack(now)
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    if disclosed_review_flags:
        # Rebuilt field by field from the ALREADY-VALIDATED request, never via
        # a JSON dump/re-validate round trip of the whole payload (council
        # round 2, tp1-qwen3.8-max): only the flags are new input and only the
        # flags need validating. A round trip would put every fact through
        # JSON coercion and alias resolution on the path the census uses and
        # NOT on the path every other caller uses, so a coercion asymmetry
        # would move a flagged walk's facts while the census still saw the
        # HUMAN_REVIEW_REQUIRED it expected. `facts` is handed over as the
        # model object it already is — same idiom as
        # `VisaOracleEvaluateRequest.applicant_facts()` itself.
        model_fields = set(VisaOracleEvaluateRequest.model_fields)
        if model_fields != _REBUILT_REQUEST_FIELDS:
            raise RuntimeError(
                "VisaOracleEvaluateRequest's field set moved to "
                f"{sorted(model_fields)}; the by-hand rebuild below names "
                f"{sorted(_REBUILT_REQUEST_FIELDS)} and must move with it, or the "
                "flagged evaluation silently drops a field the browser sends"
            )
        request = VisaOracleEvaluateRequest(
            schema_version=request.schema_version,
            assessment_id=request.assessment_id,
            collected_at=request.collected_at,
            facts=request.facts,
            disclosed_review_flags=tuple(disclosed_review_flags),  # type: ignore[arg-type]
        )
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        compiled,
        effective_at=now,
        observed_at=now,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(
        decision,
        facts,
        compiled,
        disclosed_review_flags=request.effective_review_flags(),
    )
    actual = _decision_actual(decision)
    return {
        "label": label,
        "pack": {
            "file": pack_path.name,
            "sequence": compiled.sequence,
            "version": compiled.version,
        },
        "actual": actual,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--persona", type=Path, help="persona JSON with 'overrides' (and optional expectations)"
    )
    parser.add_argument("--dump-baseline", action="store_true")
    parser.add_argument("--dump-registry", action="store_true")
    parser.add_argument(
        "--as-of",
        type=_parse_utc,
        default=None,
        help=(
            "pin the evaluation/verification instant to this timezone-aware "
            "UTC ISO-8601 timestamp instead of the real wall clock (e.g. "
            "'2026-08-29T05:00:00Z'). Defaults to now — production behaviour "
            "is unchanged; this exists so a test can pin the instant to a "
            "pack's own created_at and avoid a freshness-window clock bomb."
        ),
    )
    args = parser.parse_args(argv)

    if args.dump_baseline:
        json.dump(gf._BASELINE_FACTS, sys.stdout, indent=2, sort_keys=True)
        print()
        return 0
    if args.dump_registry:
        json.dump(_registry_rows(), sys.stdout, indent=2)
        print()
        return 0
    if args.persona is None:
        parser.error("--persona, --dump-baseline or --dump-registry is required")
    spec = json.loads(args.persona.read_text(encoding="utf-8"))
    overrides = spec.get("overrides") or {}
    if not isinstance(overrides, dict):
        parser.error("'overrides' must be an object keyed by dotted FactPath")
    out = _evaluate(overrides, str(spec.get("label", args.persona.stem)), as_of=args.as_of)
    for key in ("expected_state", "expected_candidates", "product_code"):
        if key in spec:
            out[key] = spec[key]
    if "expected_state" in spec:
        out["state_matches"] = out["actual"].get("state") == spec["expected_state"]
    if "expected_candidates" in spec:
        cands = set(
            out["actual"].get("candidates") or out["actual"].get("candidate_products") or []
        )
        out["candidates_present"] = sorted(c for c in spec["expected_candidates"] if c in cands)
        out["candidates_missing"] = sorted(c for c in spec["expected_candidates"] if c not in cands)
    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
