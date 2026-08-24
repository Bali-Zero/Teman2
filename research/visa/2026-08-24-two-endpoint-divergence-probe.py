"""Second divergence probe (team-lead's sharpened ask, 2026-08-24): the SAME
QuizAnswers facts through the two BACKEND services directly, not two UIs.

  Door A — POST /api/v1/visa-oracle/recommend
    apps/mouth/src/lib/visa-oracle/api.ts:241 (currently orphaned: no live
    component calls it, see report) -> app/routers/visa_oracle.py's
    RecommendRequest{nationality,purpose,duration,family} ->
    VisaOracleService.recommend_visas() (visa_oracle_service.py:210) — a
    pure, LLM-free PricingService keyword-scoring function. No DB, no
    network beyond loading the pricing JSON already on disk.

  Door B — POST /api/visa-oracle/evaluate
    app/routers/visa_oracle_evaluate.py -> services/visa_engine/
    evaluate_path.py's `run_evaluation()`. That function itself needs a
    live asyncpg.Pool (pack-binding resolution, retention gate, pricing
    catalog, persistence) which this offline probe does not have. Per that
    module's OWN docstring, `apply_public_policy_adapters()` is
    deliberately factored out as "a pure helper" so that "offline evidence
    tools" do not drift from the endpoint — this probe uses exactly that:
    evaluator.evaluate() (the real engine) + apply_public_policy_adapters()
    (the real, pure post-processing every /evaluate response gets), against
    the real signed PRODUCTION pack. What is NOT exercised: DB-backed pack
    binding/retention-gate resolution (assumed to succeed — same PROD pack
    used throughout), PricingService quote attachment, and persistence —
    none of which change `decision.state`/`decision.candidates`, which is
    what this comparison is about.

Read-only: imports existing pure functions from both services, no edits to
either, no DB writes, no network calls, no PR.

Run: cd apps/backend-rag && PYTHONPATH=. .venv/bin/python3 ../../research/visa/2026-08-24-two-endpoint-divergence-probe.py
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Throwaway STEP-6d key — see the sibling probe's identical comment.
_THROWAWAY_KEY_SECRET = base64.urlsafe_b64encode(b"\x00" * 32).rstrip(b"=").decode("ascii")
os.environ["VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON"] = json.dumps(
    [
        {
            "kid": "probe-throwaway-key-2",
            "secret": _THROWAWAY_KEY_SECRET,
            "environment": "PRODUCTION",
            "valid_from": "2020-01-01T00:00:00+00:00",
        }
    ]
)

from backend.services.visa_engine.compiler import build_compiled_pack, compile_rule_pack
from backend.services.visa_engine.crypto import resolve_identity_provider
from backend.services.visa_engine.enums import DecisionState, FactPath, VisaPurpose
from backend.services.visa_engine.evaluate_path import apply_public_policy_adapters
from backend.services.visa_engine.evaluator import evaluate
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import (
    ApplicantFacts,
    KnownCountrySet,
    KnownNonNegativeInteger,
    KnownPurposeSet,
    RulePack,
    UnknownFact,
)
from backend.services.visa_oracle.visa_oracle_service import VisaOracleService

PACK_PATH = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-prod-013.signed.json"
)
EFFECTIVE_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)

# QuizAnswers.purpose (7 values, lib/visa-oracle/types.ts) -> engine VisaPurpose.
# Exhaustive: QuizAnswers has no "other" bucket, unlike match_tree.Purpose.
_PURPOSE_MAP = {
    "visit": VisaPurpose.TOURISM,
    "work": VisaPurpose.EMPLOYMENT,
    "invest": VisaPurpose.INVESTMENT,
    "retire": VisaPurpose.RETIREMENT,
    "digital_nomad": VisaPurpose.REMOTE_WORK,
    "family": VisaPurpose.FAMILY,
    "study": VisaPurpose.STUDY,
}

# QuizAnswers.duration (4 buckets) -> a representative day count, using the
# SAME DURATION_THRESHOLDS the old service itself scores against
# (visa_oracle_service.py) so both doors are judged against the identical
# semantic duration, not two different guesses at it.
_DURATION_THRESHOLDS_DAYS = {
    "short": (0, 60),
    "medium": (61, 365),
    "long": (366, 1825),
    "permanent": (1825, 99999),
}


def _midpoint_days(bucket: str) -> int:
    lo, hi = _DURATION_THRESHOLDS_DAYS[bucket]
    hi_capped = min(hi, 3650)  # keep "permanent" representable, not literally 99999
    return (lo + hi_capped) // 2


def _default_unknown_facts() -> dict[str, object]:
    default = UnknownFact(status="UNKNOWN", reason="NOT_ASKED")
    return {path.value: default for path in FactPath if not path.value.startswith("derived.")}


def build_quiz_facts(*, nationality: str, purpose: str, duration: str) -> ApplicantFacts:
    """QuizAnswers -> ApplicantFacts, honestly. `family` is DELIBERATELY not
    mapped onto any engine fact — see the report's Finding on why not."""

    import uuid

    facts_wire = _default_unknown_facts()

    code = nationality.strip().upper()
    if len(code) in (2, 3) and code.isalpha():
        # Best-effort: only ISO-2 is directly usable; QuizAnswers.nationality
        # is a free string in practice (the UI seeds it from a
        # country-name/ISO list not audited here), so a non-2-letter code
        # degrades honestly to UNKNOWN rather than guessed.
        if len(code) == 2:
            facts_wire[FactPath.PERSON_NATIONALITIES.value] = KnownCountrySet(
                status="KNOWN", value=(code,)
            )

    mapped = _PURPOSE_MAP.get(purpose)
    if mapped is not None:
        facts_wire[FactPath.INTENT_PURPOSES.value] = KnownPurposeSet(
            status="KNOWN", value=(mapped.value,)
        )

    facts_wire[FactPath.INTENT_STAY_DAYS.value] = KnownNonNegativeInteger(
        status="KNOWN", value=_midpoint_days(duration)
    )

    return ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=uuid.uuid4(),
        collected_at=datetime.now(timezone.utc),
        facts=facts_wire,
    )


def load_prod_pack():
    raw = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack = RulePack.model_validate(raw)
    report = compile_rule_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)
    if not report.ok:
        raise SystemExit("pack fails compile_rule_pack")
    return build_compiled_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)


CASES = [
    # (label, nationality, purpose, duration, family_bool)
    ("visit / short / solo", "US", "visit", "short", False),
    ("work / medium / solo", "US", "work", "medium", False),
    ("invest / long / solo", "US", "invest", "long", False),
    ("retire / permanent / spouse", "US", "retire", "permanent", True),
    ("digital_nomad / medium / solo", "US", "digital_nomad", "medium", False),
    ("family / long / spouse_children", "US", "family", "long", True),
    ("study / medium / solo", "US", "study", "medium", False),
    ("visit / short / spouse (garbage-vs-family-bonus probe)", "US", "visit", "short", True),
]


def main() -> None:
    old_service = VisaOracleService()
    compiled = load_prod_pack()
    identity_provider = resolve_identity_provider()

    rows = []
    for label, nat, purpose, duration, family_bool in CASES:
        old_top3 = old_service.recommend_visas(
            nationality=nat, purpose=purpose, duration=duration, family=family_bool
        )

        facts = build_quiz_facts(nationality=nat, purpose=purpose, duration=duration)
        decision = evaluate(
            facts, compiled, effective_at=EFFECTIVE_AT, observed_at=EFFECTIVE_AT,
            identity_provider=identity_provider,
        )
        decision = apply_public_policy_adapters(decision, facts, compiled)

        rows.append(
            {
                "label": label,
                "old_top3": [
                    {"visa_name": r["visa_name"], "category": r["category"], "score": r["score"]}
                    for r in old_top3
                ],
                "engine_state": decision.state.value,
                "engine_candidates": [
                    {"code": c.product_code, "reason_codes": list(c.reason_codes)}
                    for c in decision.candidates
                ],
                "engine_review_reasons": [r.code for r in decision.review_reasons],
            }
        )

    print(json.dumps(rows, indent=2, default=str))


if __name__ == "__main__":
    main()
