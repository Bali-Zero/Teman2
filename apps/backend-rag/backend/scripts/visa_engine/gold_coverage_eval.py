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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    _offline_identity_provider,
    _repository_trust_store,
    build_persona_request,
    select_highest_repository_pack,
)
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.bundle import verify_rule_pack
from backend.services.visa_engine.compiler import build_compiled_pack
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


def _evaluate(overrides: dict[str, dict[str, Any]], label: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    pack_path, raw_pack = select_highest_repository_pack(PACKS_DIR)
    verified = verify_rule_pack(raw_pack, trust_store=_repository_trust_store(), observed_at=now)
    compiled = build_compiled_pack(verified.pack)
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
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
    out = _evaluate(overrides, str(spec.get("label", args.persona.stem)))
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
