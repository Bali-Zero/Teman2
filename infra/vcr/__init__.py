"""infra/vcr — Verified Claim Reconciliation, seat-health pilot (megatopic 0).

See drafts/2026-08-03-vcr-pilot-v2.1-and-build-workflow.md for the design spec.
This package does NOT re-implement seat probing: it wraps scripts/arsenal_probe.py
(transport + evaluator, already guilt/innocence self-tested) and adds the layer
that was missing — a 4-axis materialized state (truth/freshness/coverage/verifier),
observation hysteresis, verifier-drift detection, and one enforced accessor so
consumers stop parsing ~/.organism/arsenal/last.json each in their own way.
"""
