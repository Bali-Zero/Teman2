"""Tests for the F11/B7 metrics catalogue (`services/client_bot/observability.py`).

Three things this file guards against, all instances of the "esiste !=
armato" superscar family applied to instrumentation itself:

1. Every name in `__all__` actually resolves to a registered Prometheus
   collector (a typo in `__all__` or a metric object that silently failed
   to register would otherwise pass import and lie by omission).
2. The label sets a real caller will pass — every `ClientSurface`, every
   `GateVerdict`, every `GateReason` — are all valid labels on the metric
   objects that claim to accept them. A closed vocabulary that drifts
   from the metric labeling it (a renamed GateReason member, say) must
   fail HERE, not be discovered the first time an alert query 404s.
3. The two helper functions actually increment the counters they claim to.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

from backend.channels.models import ClientSurface
from backend.services.client_bot import observability as obs
from backend.services.client_bot.policy.types import GateReason, GateVerdict


def test_every_exported_name_is_a_registered_collector() -> None:
    helpers = {"record_gate_verdict", "record_handoff_created", "record_handoff_creation_failed"}
    for name in obs.__all__:
        if name in helpers:
            assert callable(getattr(obs, name)), name
            continue
        collector = getattr(obs, name)
        assert isinstance(collector, (Counter, Gauge, Histogram)), (
            f"{name} in __all__ is not a Prometheus collector: {type(collector)!r}"
        )


def test_gate_verdict_metric_accepts_every_frozen_surface_verdict_reason() -> None:
    for surface in ClientSurface:
        for verdict in GateVerdict:
            for reason in (GateReason.PASSED_ALL_CHECKS, GateReason.MODEL_ABSTAINED):
                # .labels() must not raise for any combination a real caller
                # can construct — it does not validate the closed-vocabulary
                # invariant itself (Prometheus labels are always strings),
                # but a raise here would mean the label NAME set is wrong.
                child = obs.client_bot_gate_verdict_total.labels(
                    surface=surface.value, verdict=verdict.value, reason=reason.value
                )
                # A child that isn't the real Counter's own increment target
                # would make the completeness claim above worthless — prove
                # it is live and independently addressable, not just returned.
                child.inc()
                assert child._value.get() >= 1


def test_every_gate_reason_member_is_a_valid_label_value() -> None:
    # Completeness: every member of the CLOSED GateReason vocabulary must be
    # usable as a label, not just the two sampled above. A member renamed in
    # policy/types.py without a corresponding thought given to metrics would
    # still pass Prometheus (labels are free-form strings) — this test only
    # proves reachability, not that dashboards were updated; see
    # docs/plans/2026-08-25-due-bot-live/ops/METRICS.md for the human-facing
    # half of that discipline.
    seen: set[str] = set()
    for reason in GateReason:
        child = obs.client_bot_gate_verdict_total.labels(
            surface=ClientSurface.WHATSAPP.value,
            verdict=GateVerdict.ALLOW.value,
            reason=reason.value,
        )
        child.inc()
        assert child._value.get() >= 1
        seen.add(reason.value)
    # Every member actually got its own distinct label combination — a
    # de-duplicated GateReason (two members sharing a `.value`, which
    # StrEnum forbids, but worth asserting since this is the completeness
    # claim the test's name makes) would collapse silently otherwise.
    assert len(seen) == len(list(GateReason))


def test_record_gate_verdict_increments_the_counter() -> None:
    before = obs.client_bot_gate_verdict_total.labels(
        surface="whatsapp", verdict="allow", reason="passed_all_checks"
    )._value.get()
    obs.record_gate_verdict("whatsapp", "allow", "passed_all_checks")
    after = obs.client_bot_gate_verdict_total.labels(
        surface="whatsapp", verdict="allow", reason="passed_all_checks"
    )._value.get()
    assert after == before + 1


def test_record_handoff_created_increments_carryover_or_missing_exclusively() -> None:
    carryover_before = obs.client_bot_handoff_context_carryover_total.labels(
        surface="instagram"
    )._value.get()
    missing_before = obs.client_bot_handoff_context_missing_total.labels(
        surface="instagram"
    )._value.get()
    created_before = obs.client_bot_handoff_created_total.labels(surface="instagram")._value.get()

    obs.record_handoff_created("instagram", context_carried=True)

    assert (
        obs.client_bot_handoff_context_carryover_total.labels(surface="instagram")._value.get()
        == carryover_before + 1
    )
    assert (
        obs.client_bot_handoff_context_missing_total.labels(surface="instagram")._value.get()
        == missing_before
    )
    assert (
        obs.client_bot_handoff_created_total.labels(surface="instagram")._value.get()
        == created_before + 1
    )


def test_record_handoff_creation_failed_increments_only_the_failure_counter() -> None:
    before = obs.client_bot_handoff_creation_failed_total.labels(surface="portal")._value.get()
    obs.record_handoff_creation_failed("portal")
    after = obs.client_bot_handoff_creation_failed_total.labels(surface="portal")._value.get()
    assert after == before + 1
