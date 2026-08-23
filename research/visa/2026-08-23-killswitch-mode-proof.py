"""Kill-switch MODE proof — drives the real evaluate_path.run_evaluation()
code path (not a mock) with IDENTICAL applicant facts across the three
VISA_ENGINE_EVALUATE_MODE positions, reusing the repo's own gold-pack test
fixtures (_patch_engine_chain / _facts_with_purposes / _UntouchedPool) from
backend/tests/services/visa_engine/test_evaluate_endpoint.py.

Run:
  cd apps/backend-rag && source .venv/bin/activate
  PYTHONPATH=. python /path/to/killswitch_mode_proof.py

No DB connection needed: OFF short-circuits before any I/O (sentinel pool
raises on touch), and SHADOW/ENFORCE monkeypatch the pack-binding/verify/
compile/persist boundary to the gold TEST pack (same technique the suite's
own test_enforce_mode_is_engine_after_durable_persistence uses) so the real
evaluator (evaluate_with_trace) and the real resolve_evaluate_mode() /
resolve_response_mode() gate run end-to-end.
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Ensure repo-root-relative imports work when invoked with PYTHONPATH=.
from backend.services.visa_engine import evaluate_path  # noqa: E402
from backend.services.visa_engine.enums import EngineMode  # noqa: E402

# Reuse the test module's own fixtures/helpers rather than reinventing them.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "tests"))
from backend.tests.services.visa_engine.test_evaluate_endpoint import (  # noqa: E402
    _facts_with_purposes,
    _patch_engine_chain,
    _UntouchedPool,
)


class _FakeMonkeyPatch:
    """Minimal stand-in for pytest.MonkeyPatch usable outside pytest, with
    the same setenv/delenv/setattr surface _patch_engine_chain expects."""

    def __init__(self) -> None:
        self._undo: list[callable] = []

    def setenv(self, name: str, value: str) -> None:
        old = os.environ.get(name)
        os.environ[name] = value
        self._undo.append((lambda n=name, o=old: os.environ.__setitem__(n, o) if o is not None else os.environ.pop(n, None)))

    def delenv(self, name: str, raising: bool = True) -> None:
        old = os.environ.pop(name, None)
        if old is not None:
            self._undo.append(lambda n=name, o=old: os.environ.__setitem__(n, o))

    def setattr(self, target, name: str, value) -> None:
        old = getattr(target, name)
        setattr(target, name, value)
        self._undo.append(lambda t=target, n=name, o=old: setattr(t, n, o))

    def undo(self) -> None:
        for fn in reversed(self._undo):
            fn()
        self._undo.clear()


async def run_mode(mode_value: str | None) -> dict:
    mp = _FakeMonkeyPatch()
    try:
        if mode_value is None:
            mp.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
            pool = _UntouchedPool()  # proves zero I/O touched when OFF-by-default
            save_calls: list = []
        else:
            mp.setenv(evaluate_path.EVALUATE_MODE_ENV, mode_value)
            resolved = evaluate_path.resolve_evaluate_mode()
            if resolved is EngineMode.OFF:
                pool = _UntouchedPool()
                save_calls = []
            else:
                save_calls, _, _ = _patch_engine_chain(mp)
                pool = object()

        body = await evaluate_path.run_evaluation(
            pool,
            facts=_facts_with_purposes(["TOURISM"]),
            traffic_source="real",
            request_category_hint=None,
            request_trace=f"trace-killswitch-proof-{mode_value}",
        )
        return {
            "env_value": mode_value,
            "resolved_mode": evaluate_path.resolve_evaluate_mode().value,
            "response_mode": body["mode"],
            "decision_state": body["decision"]["state"],
            "outage": body["decision"]["outage"],
            "persisted_rows": len(save_calls),
            "persisted_engine_mode": (
                save_calls[0]["engine_mode"].value if save_calls else None
            ),
        }
    finally:
        mp.undo()


async def main() -> None:
    results = []
    for mode_value in (None, "OFF", "BOGUS", "SHADOW", "ENFORCE"):
        results.append(await run_mode(mode_value))

    print(f"{'env VISA_ENGINE_EVALUATE_MODE':<32} {'resolved':<9} {'response.mode':<14} {'decision.state':<24} {'outage.code':<28} {'persisted_rows':<15} persisted_engine_mode")
    for r in results:
        print(
            f"{str(r['env_value']):<32} {r['resolved_mode']:<9} {r['response_mode']:<14} "
            f"{r['decision_state']:<24} {str(r['outage'].get('code') if r['outage'] else None):<28} "
            f"{r['persisted_rows']:<15} {r['persisted_engine_mode']}"
        )

    # Assertions -- fail loudly (non-zero exit) if the proof does not hold.
    by_env = {r["env_value"]: r for r in results}

    for safe in (None, "OFF", "BOGUS"):
        r = by_env[safe]
        assert r["resolved_mode"] == "OFF", r
        assert r["response_mode"] == "CURATED", r
        assert r["decision_state"] == "TEMPORARILY_UNAVAILABLE", r
        assert r["outage"]["code"] == "EVALUATE_SURFACE_DISABLED", r
        assert r["persisted_rows"] == 0, r

    shadow = by_env["SHADOW"]
    assert shadow["resolved_mode"] == "SHADOW", shadow
    assert shadow["response_mode"] == "CURATED", shadow
    assert shadow["decision_state"] != "TEMPORARILY_UNAVAILABLE", (
        "SHADOW should reach a real decision, not abstain on plumbing", shadow
    )
    assert shadow["persisted_rows"] == 1, shadow
    assert shadow["persisted_engine_mode"] == "SHADOW", shadow

    enforce = by_env["ENFORCE"]
    assert enforce["resolved_mode"] == "ENFORCE", enforce
    assert enforce["response_mode"] == "ENGINE", enforce
    assert enforce["decision_state"] != "TEMPORARILY_UNAVAILABLE", enforce
    assert enforce["persisted_rows"] == 1, enforce
    assert enforce["persisted_engine_mode"] == "ENFORCE", enforce

    # The load-bearing cross-check: IDENTICAL facts, IDENTICAL gold pack,
    # DIFFERENT env value -> the underlying legal verdict (decision_state)
    # is the SAME, but only ENFORCE's response is authoritative ("ENGINE").
    assert shadow["decision_state"] == enforce["decision_state"], (
        "same facts + same pack must reach the same verdict regardless of mode",
        shadow, enforce,
    )
    assert shadow["response_mode"] != enforce["response_mode"]

    print("\nPROOF HOLDS: identical facts -> identical decision_state "
          f"({shadow['decision_state']!r}) under SHADOW and ENFORCE, but only "
          "ENFORCE's response.mode is authoritative ('ENGINE' vs 'CURATED'). "
          "OFF / unset / invalid all fail SAFE to a non-authoritative, "
          "zero-persistence TEMPORARILY_UNAVAILABLE response.")


if __name__ == "__main__":
    asyncio.run(main())
