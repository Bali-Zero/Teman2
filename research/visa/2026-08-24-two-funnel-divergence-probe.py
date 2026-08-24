"""Two-funnel divergence probe (read-only, no code changes to either funnel).

Drives the SAME applicant facts through:
  (A) the OLD /visa/match funnel's real decision logic —
      backend.services.visa_check.match_tree.recommend_visa() — unmodified.
  (B) the NEW /visa-oracle engine's real evaluator —
      backend.services.visa_engine.evaluator.evaluate() — unmodified, run
      against the REAL signed PRODUCTION rule pack
      (rulepack-prod-013.signed.json, seq-13, 38 products/111 rules), via the
      exact same fact-adapter the codebase's own STEP-6c SHADOW wiring uses
      (shadow.build_shadow_facts()) — not a hand-rolled re-implementation.

This script imports existing pure functions; it does not edit
quiz-logic.ts, match_tree.py, shadow.py, or the engine. It performs no DB
writes and no network calls — evaluate() is documented pure/total
(services/visa_engine/shadow.py's own comment), so the pack is loaded
straight off disk and compiled in-process, mirroring what
tests/services/visa_engine/gold_harness/loader.py does for the (smaller,
TEST-environment) gold fixture, pointed at the real PRODUCTION pack instead.

Run: PYTHONPATH=apps/backend-rag python3 research/visa/2026-08-24-two-funnel-divergence-probe.py
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.services.visa_check.catalogue import VisaType
from backend.services.visa_check.match_tree import BudgetBand, Purpose, recommend_visa
from backend.services.visa_engine import shadow
from backend.services.visa_engine.compiler import build_compiled_pack, compile_rule_pack
from backend.services.visa_engine.crypto import resolve_identity_provider
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.evaluator import evaluate
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import RulePack

# STEP-6d fail-closed guard: evaluate() refuses the placeholder
# facts_fingerprint/decision_id provider on a PRODUCTION-environment pack
# (backend.services.visa_engine.evaluator._placeholder_identity_provider).
# This mints a THROWAWAY, all-zero, LOCAL-ONLY HMAC key -- never a real
# production secret, never read from any env/keychain -- purely so
# evaluate() can compute a decision offline. Exact pattern reused from
# tests/services/visa_engine/test_shadow_match.py::
# test_provisioned_prod_key_writes_a_real_shadow_row. Nothing here is
# persisted, transmitted, or written to any table.
_THROWAWAY_KEY_SECRET = base64.urlsafe_b64encode(b"\x00" * 32).rstrip(b"=").decode("ascii")
os.environ["VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON"] = json.dumps(
    [
        {
            "kid": "probe-throwaway-key",
            "secret": _THROWAWAY_KEY_SECRET,
            "environment": "PRODUCTION",
            "valid_from": "2020-01-01T00:00:00+00:00",
        }
    ]
)

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


def load_prod_pack():
    raw = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack = RulePack.model_validate(raw)
    report = compile_rule_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)
    if not report.ok:
        details = "; ".join(f"{e.code}: {e.message} (rule={e.rule_id})" for e in report.errors)
        raise SystemExit(f"rulepack-prod-013.signed.json fails compile_rule_pack: {details}")
    return build_compiled_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY), pack


# ---------------------------------------------------------------------------
# Representative old-funnel input alphabet.
#
# match_tree.recommend_visa() has exactly 3 hard branches (OTHER -> referral;
# LONG_TOURISM & months>6 -> referral; INVESTOR & UNDER_50M -> referral) plus
# a scored fallback for every other combination. `nationality` is accepted
# by the function signature but immediately discarded
# (`del nationality  # reserved for future visa-waiver rules`) -- so it is
# held fixed at a neutral "US" for the whole sweep; one row varies it to
# make that discard visible on the engine side, where nationality DOES
# populate a fact.
# ---------------------------------------------------------------------------

CASES = [
    # (label, nationality, purpose, duration_months, budget_band)
    ("work_remote / 6mo / mid",      "USA", Purpose.WORK_REMOTE,   6,  BudgetBand.MID_50_500M),
    ("investor / 12mo / under50m",   "USA", Purpose.INVESTOR,      12, BudgetBand.UNDER_50M),
    ("investor / 12mo / over500m",   "USA", Purpose.INVESTOR,      12, BudgetBand.OVER_500M),
    ("work_employee / 24mo / mid",   "USA", Purpose.WORK_EMPLOYEE, 24, BudgetBand.MID_50_500M),
    ("family / 12mo / mid",          "USA", Purpose.FAMILY,        12, BudgetBand.MID_50_500M),
    ("long_tourism / 2mo / under50m","USA", Purpose.LONG_TOURISM,  2,  BudgetBand.UNDER_50M),
    ("long_tourism / 8mo / mid",     "USA", Purpose.LONG_TOURISM,  8,  BudgetBand.MID_50_500M),
    ("retirement / 60mo / over500m", "USA", Purpose.RETIREMENT,    60, BudgetBand.OVER_500M),
    ("student / 12mo / under50m",    "USA", Purpose.STUDENT,       12, BudgetBand.UNDER_50M),
    ("other / 6mo / mid",            "USA", Purpose.OTHER,         6,  BudgetBand.MID_50_500M),
    ("work_remote / 1mo / under50m", "USA", Purpose.WORK_REMOTE,   1,  BudgetBand.UNDER_50M),
    ("work_remote / 6mo / mid (nationality varied: high-scrutiny)",
                                      "IRN", Purpose.WORK_REMOTE,   6,  BudgetBand.MID_50_500M),
]


def main() -> None:
    compiled, _pack = load_prod_pack()

    rows = []
    for label, nat, purpose, months, band in CASES:
        old = recommend_visa(
            nationality=nat, purpose=purpose, duration_months=months, budget_band=band
        )
        old_top = old.recommended_visa.value if old.recommended_visa else None
        old_alts = [v.value for v in old.alternatives]

        facts = shadow.build_shadow_facts(
            nationality=nat, purpose=purpose, duration_months=months, match_hash=f"probe-{label}"
        )
        assert facts is not None, f"build_shadow_facts returned None for {label}"

        decision = evaluate(
            facts,
            compiled,
            effective_at=EFFECTIVE_AT,
            observed_at=EFFECTIVE_AT,
            identity_provider=resolve_identity_provider(),
        )

        engine_candidates = [
            {"code": c.product_code, "rank": c.rank, "reason_codes": list(c.reason_codes)}
            for c in decision.candidates
        ]
        engine_codes = {c.product_code for c in decision.candidates}

        agree = None
        if old_top is not None:
            agree = old_top in engine_codes and decision.state == DecisionState.SUPPORTED_CANDIDATES
        else:
            # Old funnel referred to a human (no code). Engine "agrees" in
            # spirit only if it ALSO abstains/refers (HUMAN_REVIEW_REQUIRED,
            # NEEDS_INPUT, or NO_SUPPORTED_PATH) rather than confidently
            # naming a SUPPORTED product the old funnel never offered.
            agree = decision.state != DecisionState.SUPPORTED_CANDIDATES

        rows.append(
            {
                "label": label,
                "input": {
                    "nationality": nat,
                    "purpose": purpose.value,
                    "duration_months": months,
                    "budget_band": band.value,
                },
                "old_funnel": {
                    "referral_mode": old.referral_mode,
                    "recommended_visa": old_top,
                    "alternatives": old_alts,
                },
                "engine": {
                    "state": decision.state.value,
                    "candidates": engine_candidates,
                    "missing_facts_count": len(decision.missing_facts),
                    "review_reasons": [r.code for r in decision.review_reasons],
                    "no_path_reasons": [r.code for r in decision.no_path_reasons],
                },
                "agree": agree,
            }
        )

    print(json.dumps(rows, indent=2, default=str))


if __name__ == "__main__":
    main()
