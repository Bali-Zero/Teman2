"""Privacy-policy and one-shot retention worker tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.scripts.visa_engine import privacy_ops, register_privacy_policy, retention_worker
from backend.services.visa_engine import retention
from backend.services.visa_engine.privacy_policy import (
    default_policy_path,
    load_approved_privacy_policy,
)


def test_checked_in_privacy_policy_is_the_approved_v1_authority() -> None:
    policy = load_approved_privacy_policy()

    assert policy.policy_id == "visa-oracle-privacy-v1"
    assert policy.approved_by == "zero"
    assert policy.decision_retention_days == 30
    assert policy.idempotency_retention_hours == 24
    assert policy.telemetry_retention_days == 90
    assert policy.dsr_service_level_hours == 72
    assert policy.legal_hold_review_interval_days == 30
    assert policy.dpia_required_before_enforce is True


def _approved_active_policy() -> retention_worker.ActiveRetentionPolicy:
    return retention_worker.ActiveRetentionPolicy(
        policy_version="visa-oracle-privacy-v1",
        retention_interval=timedelta(days=30),
        idempotency_retention_interval=timedelta(hours=24),
        legal_hold_review_interval=timedelta(days=30),
        retention_anchor="EVALUATED_AT",
        approved_by="zero",
    )


def test_privacy_policy_loader_rejects_safety_drift(tmp_path: Path) -> None:
    raw = json.loads(default_policy_path().read_text(encoding="utf-8"))
    raw["telemetry"]["pii_free"] = False
    drifted = tmp_path / "policy.json"
    drifted.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="PII-free"):
        load_approved_privacy_policy(drifted)


def test_new_policy_registration_rejects_backdating_but_allows_change_window() -> None:
    policy = load_approved_privacy_policy()
    database_now = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)

    register_privacy_policy._assert_new_effective_window(
        policy=policy,
        effective_from=database_now - timedelta(minutes=5),
        database_now=database_now,
    )
    with pytest.raises(RuntimeError, match="backdate"):
        register_privacy_policy._assert_new_effective_window(
            policy=policy,
            effective_from=database_now - timedelta(minutes=5, seconds=1),
            database_now=database_now,
        )
    with pytest.raises(RuntimeError, match="predates"):
        register_privacy_policy._assert_new_effective_window(
            policy=policy,
            effective_from=datetime(2026, 8, 5, 23, 59, tzinfo=timezone.utc),
            database_now=database_now,
        )


@pytest.mark.asyncio
async def test_retention_worker_drains_bounded_batches_and_reports_only_aggregates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = object()
    monkeypatch.setattr(
        retention_worker,
        "_active_policy",
        AsyncMock(return_value=_approved_active_policy()),
    )
    purge_idempotency = AsyncMock(side_effect=[1_000, 7])
    purge_decisions = AsyncMock(side_effect=[4])
    monkeypatch.setattr(retention, "purge_expired_idempotency", purge_idempotency)
    monkeypatch.setattr(retention, "purge_expired_decisions", purge_decisions)
    monkeypatch.setattr(
        retention,
        "decision_retention_evidence",
        AsyncMock(
            return_value=retention.DecisionRetentionEvidence(
                expired_rows=0,
                expired_held_rows=2,
                max_lag_seconds=0,
                observed_at=datetime.now(timezone.utc),
            )
        ),
    )
    monkeypatch.setattr(
        retention,
        "idempotency_retention_evidence",
        AsyncMock(
            return_value=retention.IdempotencyRetentionEvidence(
                expired_rows=0,
                max_lag_seconds=0,
                observed_at=datetime.now(timezone.utc),
            )
        ),
    )

    result = await retention_worker.run_retention_cycle(
        pool,  # type: ignore[arg-type]
        apply=True,
        limit=1_000,
        max_batches=5,
        requested_by="visa-retention-scheduler",
        max_lag_seconds=3_600,
    )

    assert result.decision_deleted == 4
    assert result.idempotency_deleted == 1_007
    assert result.decision_expired_held == 2
    assert result.healthy is True
    assert purge_idempotency.await_count == 2
    assert purge_decisions.await_count == 1


@pytest.mark.asyncio
async def test_retention_worker_dry_run_alerts_without_deleting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        retention_worker,
        "_active_policy",
        AsyncMock(return_value=_approved_active_policy()),
    )
    purge_idempotency = AsyncMock()
    purge_decisions = AsyncMock()
    monkeypatch.setattr(retention, "purge_expired_idempotency", purge_idempotency)
    monkeypatch.setattr(retention, "purge_expired_decisions", purge_decisions)
    monkeypatch.setattr(
        retention,
        "decision_retention_evidence",
        AsyncMock(
            return_value=retention.DecisionRetentionEvidence(
                expired_rows=3,
                expired_held_rows=0,
                max_lag_seconds=3_601,
                observed_at=datetime.now(timezone.utc),
            )
        ),
    )
    monkeypatch.setattr(
        retention,
        "idempotency_retention_evidence",
        AsyncMock(
            return_value=retention.IdempotencyRetentionEvidence(
                expired_rows=0,
                max_lag_seconds=0,
                observed_at=datetime.now(timezone.utc),
            )
        ),
    )

    result = await retention_worker.run_retention_cycle(
        object(),  # type: ignore[arg-type]
        apply=False,
        limit=1_000,
        max_batches=20,
        requested_by="visa-retention-scheduler",
        max_lag_seconds=3_600,
    )

    assert result.healthy is False
    purge_idempotency.assert_not_awaited()
    purge_decisions.assert_not_awaited()


@pytest.mark.asyncio
async def test_retention_worker_rejects_unapproved_active_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        retention_worker,
        "_active_policy",
        AsyncMock(
            return_value=replace(_approved_active_policy(), policy_version="unexpected-policy")
        ),
    )

    with pytest.raises(RuntimeError, match="do not match"):
        await retention_worker.run_retention_cycle(
            object(),  # type: ignore[arg-type]
            apply=False,
            limit=1_000,
            max_batches=20,
            requested_by="visa-retention-scheduler",
            max_lag_seconds=3_600,
        )


@pytest.mark.asyncio
async def test_retention_worker_rejects_duration_drift_under_same_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        retention_worker,
        "_active_policy",
        AsyncMock(
            return_value=replace(_approved_active_policy(), retention_interval=timedelta(days=31))
        ),
    )

    with pytest.raises(RuntimeError, match="values do not match"):
        await retention_worker.run_retention_cycle(
            object(),  # type: ignore[arg-type]
            apply=False,
            limit=1_000,
            max_batches=20,
            requested_by="visa-retention-scheduler",
            max_lag_seconds=3_600,
        )


def test_privacy_ops_requires_hold_governance_fields() -> None:
    base = [
        "hold",
        "--decision-id",
        "11111111-1111-4111-8111-111111111111",
        "--case-reference",
        "DSR-2026-001",
        "--actor",
        "privacy.operator",
    ]
    with pytest.raises(SystemExit):
        privacy_ops._parse_args(base)

    args = privacy_ops._parse_args(
        [
            *base,
            "--reason-code",
            "LEGAL-CLAIM-PRESERVATION",
            "--approved-by",
            "privacy.approver",
            "--review-due-at",
            "2026-09-04T00:00:00+08:00",
        ]
    )
    assert args.action == "hold"
    assert args.review_due_at.utcoffset() == timedelta(hours=8)
