"""First-class metrics for BOT A (client bot + its codex broker leg) — F11/B7.

MANDATE.md F11: "Metrics are first-class or the bot 'works' unfalsifiably."
This module is the CATALOGUE — every Prometheus instrument the client-bot
engine (B1), the codex broker leg (B2), and the ingress layer (B5) must
call into, pre-registered here so no lane invents its own metric object
or name under time pressure. Nothing in this file is wired into a live
request path: `final_gate.py`, the broker daemon, and the webhook router
do not exist yet or do not call these functions yet (B1/B2/B5 own that
wiring). This is instrumentation-as-contract, not instrumentation-as-fact
— see `docs/plans/2026-08-25-due-bot-live/ops/METRICS.md` for which lane
wires which call and the current wired/planned status per metric.

Team-bot (BOT B) metrics are NOT in this module. `apps/team-bot/` is a
standalone app that does not exist yet (B3's file ownership per
MANDATE.md "Cross-lane law") and must not import backend-rag internals.
Its metric NAMES are frozen as a naming contract in
`docs/plans/2026-08-25-due-bot-live/ops/METRICS.md` §Team bot for B3 to
implement verbatim in `apps/team-bot/team_bot/observability.py`.

Naming and threshold values below preserve the F3 tripwire table
(research capture §2.5) VERBATIM where it named a metric — those names
are frozen the same way F1-F11 are. Names not present in §2.5 are B7
additions closing gaps the team lead's mandate flagged explicitly:
tripwires "tied to BUSINESS invariants, not just technical ones" (F10
context carry-over, F1/F5 price provenance, F1 citation integrity) and
team-bot safety invariants (F6 confirmation bypass, F5/F7 RBAC scope
leak) live in `tripwires.py`, which references the counters defined here.

A ratio-shaped tripwire (`codex_quota_fallback_ratio`,
`codex_output_invalid_ratio`, `fallback_provider_failure_ratio`) is
deliberately NOT stored as a single pre-computed gauge: Prometheus best
practice is to store the numerator/denominator counters and let the
alerting layer compute the ratio over its own window, so the raw counts
survive a threshold change and a restart does not lose the ratio's
history mid-window.

`codex_auth_dead_total` reflects a pre-existing, empirically-anchored
classifier (the existing dark implementation's one tested AUTH_DEAD
pattern). `codex_quota_exhausted_total` does NOT yet have the same
grounding: B2a's stderr-regex AUTH/QUOTA/POLICY_BLOCKED split was
refuted (12 reproduced findings against one design defect) and replaced
by `docs/plans/2026-08-25-due-bot-live/SPEC-codex-error-classification.md`,
which states the classification "stays dark until a REAL codex exec
quota event and a REAL policy block have been observed... no caller may
take an irreversible action on it" until then. `codex_cli_version_mismatch_total`
is unrelated to that contested classifier — it is `wa_codex_daemon.py`'s
own pre-existing, deterministic version-pin guard, and safe to act on
today. See `tripwires.py`'s `requires_arming_condition` field for which
tripwires this constraint binds.

Author: Claude Opus 5 (lane B7 — control tower).
"""

from __future__ import annotations

from backend.app.metrics import (
    safe_register_counter,
    safe_register_gauge,
    safe_register_histogram,
)

# Alphabetically sorted (ruff RUF022 + repo convention, cf. contracts.py's
# __all__) — the grouped/annotated view of this same list lives in the
# "Metric groups" comment block immediately below and in ops/METRICS.md.
__all__ = [
    "client_bot_citation_integrity_fail_total",
    "client_bot_codex_route_seconds",
    "client_bot_containment_total",
    "client_bot_gate_eval_seconds",
    "client_bot_gate_verdict_total",
    "client_bot_handoff_context_carryover_total",
    "client_bot_handoff_context_missing_total",
    "client_bot_handoff_created_total",
    "client_bot_handoff_creation_failed_total",
    "client_bot_price_not_in_pricingtool_total",
    "client_bot_resolution_total",
    "client_bot_response_latency_seconds",
    "client_bot_synthetic_probe_age_seconds",
    "client_policy_unsupported_claim_escape_total",
    "codex_auth_dead_total",
    "codex_broker_heartbeat_age_seconds",
    "codex_broker_queue_depth",
    "codex_canary_probe_age_seconds",
    "codex_cli_version_mismatch_total",
    "codex_consecutive_failures",
    "codex_eligible_requests_total",
    "codex_exec_seconds",
    "codex_fence_violation_or_double_completion_total",
    "codex_jobs_total",
    "codex_output_invalid_total",
    "codex_quota_exhausted_total",
    "codex_quota_fallback_total",
    "codex_secret_canary_hits_total",
    "fallback_provider_failure_total",
    "fallback_provider_requests_total",
    "record_gate_verdict",
    "record_handoff_created",
    "record_handoff_creation_failed",
    "webhook_ack_latency_seconds",
]

# Metric groups, for a reader's orientation (__all__ above must stay
# alphabetical for the linter; this comment carries the same grouping the
# inline docstrings below elaborate on):
#   - FinalPolicyGate / F11 core: gate_verdict_total, gate_eval_seconds,
#     containment_total, resolution_total
#   - F10 handoff (the mandate's stated KPI): handoff_created_total,
#     handoff_creation_failed_total, handoff_context_carryover_total,
#     handoff_context_missing_total
#   - Business-invariant price/citation (B7 addition):
#     price_not_in_pricingtool_total, citation_integrity_fail_total
#   - End-to-end latency: response_latency_seconds
#   - F9 ingress: webhook_ack_latency_seconds
#   - F3 codex broker leg (Sol §2.5 verbatim names): broker_heartbeat_age_seconds,
#     broker_queue_depth, exec_seconds, codex_route_seconds,
#     consecutive_failures, auth_dead_total, quota_exhausted_total,
#     quota_fallback_total, eligible_requests_total, output_invalid_total,
#     jobs_total, secret_canary_hits_total, fence_violation_or_double_completion_total,
#     unsupported_claim_escape_total, fallback_provider_failure_total,
#     fallback_provider_requests_total, cli_version_mismatch_total
#   - Dead-man-switch synthetic probes (ASSEMBLY-LINE §7 pattern):
#     synthetic_probe_age_seconds, canary_probe_age_seconds
#   - Helpers: record_gate_verdict, record_handoff_created,
#     record_handoff_creation_failed

_SURFACE_LABEL = "surface"  # ClientSurface value: whatsapp|instagram|portal|kbli_widget
_VERDICT_LABEL = "verdict"  # GateVerdict value (policy/types.py) — closed vocabulary
_REASON_LABEL = "reason"  # GateReason value (policy/types.py) — closed vocabulary
_SEAT_LABEL = "seat"  # codex broker seat id, e.g. zantara-codex-seat1

# ---------------------------------------------------------------------------
# FinalPolicyGate / F11 core business instrument
# ---------------------------------------------------------------------------

client_bot_gate_verdict_total = safe_register_counter(
    "zantara_client_bot_gate_verdict_total",
    "FinalPolicyGate verdicts, one per evaluated candidate. The primary "
    "business-invariant instrument: a bot answering fast and wrongly shows "
    "up here as ALLOW volume with a wrong-reason distribution, not as "
    "downtime — see F1/F11 and tripwires.py.",
    (_SURFACE_LABEL, _VERDICT_LABEL, _REASON_LABEL),
)

client_bot_gate_eval_seconds = safe_register_histogram(
    "zantara_client_bot_gate_eval_seconds",
    "FinalPolicyGate evaluation latency (the 11 ordered checks), per surface.",
    (_SURFACE_LABEL,),
)

client_bot_containment_total = safe_register_counter(
    "zantara_client_bot_containment_total",
    "ALLOW verdicts that did not also produce a handoff — i.e. the bot "
    "answered without escalating. NOT the product KPI on its own (mandate: "
    "'the KPI that matters — not vendor-style containment claims') — read "
    "together with client_bot_handoff_context_carryover_total.",
    (_SURFACE_LABEL,),
)

client_bot_resolution_total = safe_register_counter(
    "zantara_client_bot_resolution_total",
    "Best-effort resolution signal: an ALLOW verdict with no further "
    "inbound message on the same thread within the surface's service "
    "window. Honestly approximate until a real closed-loop resolution "
    "signal exists (e.g. a client-confirmed close) — do not treat as a "
    "vendor-grade CSAT/resolution metric.",
    (_SURFACE_LABEL,),
)

# ---------------------------------------------------------------------------
# F10 handoff — "the KPI that matters" per the mandate's own words
# ---------------------------------------------------------------------------

client_bot_handoff_created_total = safe_register_counter(
    "zantara_client_bot_handoff_created_total",
    "Handoff rows durably created by ClientHandoffService, per surface. "
    "F10: the bot may say 'l'ho passato al team' ONLY after this fires.",
    (_SURFACE_LABEL,),
)

client_bot_handoff_creation_failed_total = safe_register_counter(
    "zantara_client_bot_handoff_creation_failed_total",
    "Handoff creation attempts that did NOT durably create a row. Any "
    "non-zero value here means some user was told 'puoi richiedere' "
    "instead of a false 'ho passato' — track this, never silently retry "
    "and claim success (F10).",
    (_SURFACE_LABEL,),
)

client_bot_handoff_context_carryover_total = safe_register_counter(
    "zantara_client_bot_handoff_context_carryover_total",
    "Handoffs where the consultant-facing record carries the full prior "
    "conversation context. This IS the product bar the mandate names — "
    "read this against client_bot_handoff_context_missing_total, never "
    "against raw handoff volume alone.",
    (_SURFACE_LABEL,),
)

client_bot_handoff_context_missing_total = safe_register_counter(
    "zantara_client_bot_handoff_context_missing_total",
    "Handoffs where the consultant-facing record is missing prior "
    "conversation context — a durable row was created (F10 satisfied) but "
    "the product bar (context carry-over) was not. Non-zero here is a "
    "product defect even though F10's literal text-gate passed.",
    (_SURFACE_LABEL,),
)

# ---------------------------------------------------------------------------
# Business-invariant price/citation instruments (B7 addition — closes the
# team lead's "tied to BUSINESS invariants, not just technical ones" gap)
# ---------------------------------------------------------------------------

client_bot_price_not_in_pricingtool_total = safe_register_counter(
    "zantara_client_bot_price_not_in_pricingtool_total",
    "A price-bearing candidate reached the gate with a price NOT sourced "
    "from a frozen PricingTool snapshot (GateReason.PRICE_NOT_IN_SNAPSHOT / "
    "PRICE_RECOMPUTED_BY_MODEL). Any non-zero value is a business-invariant "
    "breach (a client could receive an invented number), not a technical "
    "one — see tripwires.py, plane=CLIENT_SEND.",
    (_SURFACE_LABEL,),
)

client_bot_citation_integrity_fail_total = safe_register_counter(
    "zantara_client_bot_citation_integrity_fail_total",
    "A regulatory claim reached the gate uncited, mis-cited, or citing "
    "unused evidence (GateReason citation-integrity family, check 9). "
    "This is the anti-hallucination business invariant (SYMBIOSIS Law 2 / "
    "CLAUDE.md §6): correctness, not availability, is what this counts.",
    (_SURFACE_LABEL,),
)

# ---------------------------------------------------------------------------
# End-to-end latency
# ---------------------------------------------------------------------------

client_bot_response_latency_seconds = safe_register_histogram(
    "zantara_client_bot_response_latency_seconds",
    "End-to-end latency from inbound webhook ack to outbound send, per "
    "surface (broader than client_bot_gate_eval_seconds, which times the "
    "gate alone). F11's per-surface p95 instrument.",
    (_SURFACE_LABEL,),
)

# ---------------------------------------------------------------------------
# F9 ingress
# ---------------------------------------------------------------------------

webhook_ack_latency_seconds = safe_register_histogram(
    "zantara_webhook_ack_latency_seconds",
    "Time from inbound webhook receipt to the 200 ack, per surface. Sol "
    "§2.5: p95 > 200ms for 5 minutes pages an ingress issue and sheds all "
    "LLM work from the request path (the ack path must contain no LLM, "
    "Qdrant, CRM, PricingTool, media download, or outbound send).",
    (_SURFACE_LABEL,),
)

# ---------------------------------------------------------------------------
# F3 codex broker leg — Sol §2.5 verbatim names
# ---------------------------------------------------------------------------

codex_broker_heartbeat_age_seconds = safe_register_gauge(
    "zantara_codex_broker_heartbeat_age_seconds",
    "Seconds since the broker seat's last heartbeat. >45s: mark host "
    "offline, stop offering jobs, direct to Gemini (Sol §2.5).",
    (_SEAT_LABEL,),
)

codex_broker_queue_depth = safe_register_gauge(
    "zantara_codex_broker_queue_depth",
    "Waiting jobs for this seat. >=1: bypass Codex for subsequent "
    "messages — the queue must never grow (F3: 'Do not raise depth to "
    "improve throughput').",
    (_SEAT_LABEL,),
)

codex_exec_seconds = safe_register_histogram(
    "zantara_codex_exec_seconds",
    "codex exec wall-clock duration per seat. p90 > 12s over >=20 jobs: "
    "do not arm, or revert active traffic to Gemini (Sol §2.5).",
    (_SEAT_LABEL,),
)

client_bot_codex_route_seconds = safe_register_histogram(
    "zantara_client_bot_codex_route_seconds",
    "End-to-end latency for a client-bot turn routed through the codex "
    "leg, per surface. p95 > 15s in 3 consecutive 15-min windows: disable "
    "active codex routing, keep shadow/probes (Sol §2.5).",
    (_SURFACE_LABEL,),
)

codex_consecutive_failures = safe_register_gauge(
    "zantara_codex_consecutive_failures",
    "Current consecutive-failure streak for this seat (reset to 0 on any "
    "success). >=3: open the seat breaker for 5 minutes, half-open with "
    "one synthetic canary (Sol §2.5) — a GAUGE, not a counter, because the "
    "threshold reads the CURRENT streak, not a lifetime total.",
    (_SEAT_LABEL,),
)

codex_auth_dead_total = safe_register_counter(
    "zantara_codex_auth_dead_total",
    "AUTH_DEAD terminal observations for this seat (CodexExecAuthError, "
    "distinct from QUOTA per F3/B2a). >=1: latch seat offline, operator "
    "alert, manual OAuth recovery required (Sol §2.5) — see owner "
    "switchboard item 4.",
    (_SEAT_LABEL,),
)

codex_quota_exhausted_total = safe_register_counter(
    "zantara_codex_quota_exhausted_total",
    "QUOTA terminal observations for this seat (CodexExecQuotaError, "
    "distinct from AUTH_DEAD per F3/B2a). >=1: cooldown seat, alert with "
    "measured window/reset evidence — never collapsed into a generic CLI "
    "failure (Sol §2.5).",
    (_SEAT_LABEL,),
)

codex_quota_fallback_total = safe_register_counter(
    "zantara_codex_quota_fallback_total",
    "Client-bot turns that fell back to Gemini specifically because of a "
    "QUOTA observation on the codex leg. Numerator of "
    "codex_quota_fallback_ratio — compute the ratio in the alerting layer "
    "against codex_eligible_requests_total, never store it pre-computed.",
    (_SEAT_LABEL,),
)

codex_eligible_requests_total = safe_register_counter(
    "zantara_codex_eligible_requests_total",
    "Client-bot turns eligible to route through the codex leg (denominator "
    "for codex_quota_fallback_ratio). >5%/7d with >=50 eligible requests, "
    "or two exhausted windows in 7 days: produce an owner decision packet "
    "for stage 2 — never auto-provision a key (Sol §2.5; see "
    "ops/packets/QUOTA-WALL-STAGE2-PACKET.template.md).",
    (_SEAT_LABEL,),
)

codex_output_invalid_total = safe_register_counter(
    "zantara_codex_output_invalid_total",
    "OUTPUT_INVALID terminal observations (JSON/shape/hash/size rejected). "
    "Numerator of codex_output_invalid_ratio.",
    (_SEAT_LABEL,),
)

codex_jobs_total = safe_register_counter(
    "zantara_codex_jobs_total",
    "All terminal codex broker job observations for this seat, regardless "
    "of outcome. Denominator for codex_output_invalid_ratio (>1% over "
    ">=100 jobs, or 2 consecutive invalid outputs: quarantine CLI/model/"
    "schema combination, Gemini only — Sol §2.5).",
    (_SEAT_LABEL,),
)

codex_secret_canary_hits_total = safe_register_counter(
    "zantara_codex_secret_canary_hits_total",
    "Secret-canary token detections in codex broker output. >0: GLOBAL "
    "codex-leg kill switch, P0 operator alert (Sol §2.5) — the single "
    "highest-severity tripwire in this catalogue.",
    (_SEAT_LABEL,),
)

codex_cli_version_mismatch_total = safe_register_counter(
    "zantara_codex_cli_version_mismatch_total",
    "codex exec refused to run because the installed CLI no longer matches "
    "WA_CODEX_CLI_VERSION_PIN (wa_codex_daemon.py's own pre-existing, "
    "deterministic version-pin guard — NOT part of the contested stderr-"
    "regex AUTH_DEAD/QUOTA/POLICY_BLOCKED classification in "
    "SPEC-codex-error-classification.md, which stays dark/advisory until a "
    "real quota event and policy block are observed). >=1 is an "
    "operator-actionable CLI/config-drift signal distinct from AUTH_DEAD: "
    "the fix is re-approving the new CLI version or restoring the pinned "
    "one, never `codex login` — see tripwires.py's `codex.cli_version_"
    "mismatch` entry and owner switchboard item 4.",
    (_SEAT_LABEL,),
)

codex_fence_violation_or_double_completion_total = safe_register_counter(
    "zantara_codex_fence_violation_or_double_completion_total",
    "A completion arrived after its fence token was already terminal, or "
    "the same completion_key completed twice. >0: disable the active leg "
    "and investigate — no affected output may send (Sol §2.5).",
    (_SEAT_LABEL,),
)

client_policy_unsupported_claim_escape_total = safe_register_counter(
    "zantara_client_policy_unsupported_claim_escape_total",
    "A regulatory/pricing claim the golden or shadow evaluation judged "
    "unsupported nonetheless passed the gate as ALLOW. >0: block "
    "promotion (Sol §2.5) — this is the single metric that most directly "
    "operationalizes 'answers fast and wrongly is worse than down'.",
    (_SURFACE_LABEL,),
)

fallback_provider_failure_total = safe_register_counter(
    "zantara_fallback_provider_failure_total",
    "Gemini-leg (the fallback of last resort) failures. Numerator of "
    "fallback_provider_failure_ratio.",
    (_SURFACE_LABEL,),
)

fallback_provider_requests_total = safe_register_counter(
    "zantara_fallback_provider_requests_total",
    "Gemini-leg requests attempted (denominator for "
    "fallback_provider_failure_ratio). >1% failures over 30 min with "
    ">=100 requests: disable bot auto-replies and preserve human handoff "
    "only (Sol §2.5) — this is the fallback of last resort failing, the "
    "single most severe technical tripwire short of the secret canary.",
    (_SURFACE_LABEL,),
)


# ---------------------------------------------------------------------------
# Dead-man-switch synthetic probes (ASSEMBLY-LINE §7 pattern, generalized:
# "a synthetic transaction ... every 10-15 min with a dead-man switch: probe
# silent 15 min -> flag auto-off + owner alert"). Each is a Gauge set to the
# age (seconds since last successful probe run), not a timestamp, so the
# threshold comparison (">900s") is the same shape everywhere in this file.
# ---------------------------------------------------------------------------

client_bot_synthetic_probe_age_seconds = safe_register_gauge(
    "zantara_client_bot_synthetic_probe_age_seconds",
    "Seconds since a synthetic end-to-end client-bot probe last succeeded "
    "on this surface (send a fixed question, assert a known-good gate "
    "verdict/answer shape). >900s (15 min) with no successful probe: "
    "auto-flip that surface's CLIENT_BOT_<surface>_SEND_ENABLED to false "
    "and page the owner — a silent probe is silent failure, not silent "
    "health.",
    (_SURFACE_LABEL,),
)

codex_canary_probe_age_seconds = safe_register_gauge(
    "zantara_codex_canary_probe_age_seconds",
    "Seconds since a fixed-prompt canary conversation last completed "
    "through the codex leg and matched a known-good substring (Kimi "
    "refutation §5 FC2 mitigation) — distinct from "
    "codex_broker_heartbeat_age_seconds, which only proves the daemon "
    "process is alive, not that a real generation still works end to "
    "end. Same 900s dead-man threshold: cooldown the seat and alert.",
    (_SEAT_LABEL,),
)

# ---------------------------------------------------------------------------
# Helpers — thin, optional convenience wrappers. Callers may also touch the
# module-level metric objects directly; these exist so B1's future
# final_gate.py has one obvious call per FinalDecision instead of
# reimplementing the label mapping at each call site.
# ---------------------------------------------------------------------------


def record_gate_verdict(surface: str, verdict: str, reason: str) -> None:
    """Record one FinalPolicyGate verdict. `surface`/`verdict`/`reason` are
    the ``.value`` of ``ClientSurface``/``GateVerdict``/``GateReason`` —
    passed as plain strings here (not imported types) so this module has
    no import-time dependency on ``policy/types.py``'s freeze; the
    completeness test in ``test_observability.py`` binds the two instead.
    """
    client_bot_gate_verdict_total.labels(surface=surface, verdict=verdict, reason=reason).inc()


def record_handoff_created(surface: str, *, context_carried: bool) -> None:
    """Record a durably-created handoff (F10) and whether it met the
    context-carry-over product bar.
    """
    client_bot_handoff_created_total.labels(surface=surface).inc()
    if context_carried:
        client_bot_handoff_context_carryover_total.labels(surface=surface).inc()
    else:
        client_bot_handoff_context_missing_total.labels(surface=surface).inc()


def record_handoff_creation_failed(surface: str) -> None:
    """Record a handoff creation attempt that did NOT durably create a row."""
    client_bot_handoff_creation_failed_total.labels(surface=surface).inc()
