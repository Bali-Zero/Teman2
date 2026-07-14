from __future__ import annotations

from scripts.intake_capacity_quality_report import (
    OVERVIEW_SQL,
    Targets,
    build_metrics,
    evaluate_targets,
)


def test_overview_counts_only_completed_classification_outputs() -> None:
    assert OVERVIEW_SQL.count("stage_output->'classify' ? 'doc_type'") == 2
    assert "stage_output ? 'classify'" not in OVERVIEW_SQL


def test_build_metrics_separates_recognition_accuracy_and_drain() -> None:
    metrics = build_metrics(
        {
            "arrivals": 100,
            "completions": 120,
            "backlog": 20,
            "dead": 0,
            "classified": 96,
            "recognized": 95,
            "completion_p50_seconds": 90,
            "completion_p95_seconds": 240,
            "backlog_age_p95_seconds": 500,
        },
        {"approved_fields": 198, "corrected_fields": 2, "auto_fields": 50},
        hours=10,
    )

    assert metrics["recognition_coverage_pct"] == 98.96
    assert metrics["verified_field_acceptance_pct"] == 99.0
    assert metrics["backlog_drain_ratio"] == 1.2
    assert metrics["arrivals_per_hour"] == 10.0
    assert metrics["completions_per_hour"] == 12.0


def test_targets_require_real_human_sample_before_quality_pass() -> None:
    metrics = build_metrics(
        {
            "arrivals": 10,
            "completions": 12,
            "backlog": 5,
            "dead": 0,
            "classified": 10,
            "recognized": 10,
        },
        {"approved_fields": 9, "corrected_fields": 0, "auto_fields": 1000},
        hours=1,
    )

    gate = evaluate_targets(metrics, Targets(minimum_verified_fields=100))

    assert gate["recognition_coverage"] == "PASS"
    assert gate["verified_field_acceptance"] == "INSUFFICIENT_SAMPLE"
    assert gate["backlog_drain"] == "PASS"
    assert gate["dead_letter"] == "PASS"


def test_targets_fail_slow_drain_bad_labels_and_dead_letters() -> None:
    metrics = build_metrics(
        {
            "arrivals": 20,
            "completions": 5,
            "backlog": 40,
            "dead": 1,
            "classified": 20,
            "recognized": 16,
        },
        {"approved_fields": 80, "corrected_fields": 20, "auto_fields": 0},
        hours=1,
    )

    gate = evaluate_targets(metrics, Targets())

    assert set(gate.values()) == {"FAIL"}
