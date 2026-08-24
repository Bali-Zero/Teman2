"""The tripwire registry for both bots — F11/B7.

The team lead's mandate for this lane: "The tripwires must be tied to
BUSINESS invariants, not just technical ones — a bot that answers fast
and wrongly is worse than one that is down." This module is the single
place that claim is made checkable: every entry below is tagged
`kind=business` or `kind=technical`, and the business ones are exactly
the invariants a purely-technical health check (process up, latency low,
error rate low) cannot see — a wrong price, a fabricated citation, a CRM
mutation with no confirmation, a cross-client RBAC leak. A bot can be
fast and green on every technical row here while failing every business
one; that combination is precisely what this split exists to make
visible instead of unfalsifiable (ASSEMBLY-LINE's "one inversion").

Entries 1-13 preserve the F3 tripwire table (research capture §2.5)
VERBATIM — thresholds, actions, and metric names are frozen the same way
F1-F11 are; do not "improve" them without an owner ruling, per the
mandate's own framing ("initial arm/no-arm thresholds, not permanent
business KPIs" — they may be RETUNED on evidence, never silently dropped).
Entries after that are B7 additions closing the business-invariant gap
above, plus the team-bot side the frozen research names in prose but
never tabulates as tripwires.

`metric_status` on each row says whether `metric` names a Prometheus
instrument that already exists in `observability.py` (`wired`) or a
name reserved for `apps/team-bot/` to implement when B3 lands it
(`planned` — see `kill_switches.py`'s module docstring on why team-bot
code does not live here). `test_tripwires.py` enforces every `wired` row
against `observability.py.__all__` so this file cannot silently drift
from the metrics it claims to read.

`plane` is `None` for a tripwire whose automatic action is "page the
owner" with no single-gesture kill switch to flip — not every tripwire
maps onto one of the 5 F11 planes, and forcing one onto `None` here
would be inventing a switch that isn't real (see `kill_switches.py`).

Author: Claude Opus 5 (lane B7 — control tower).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from backend.services.client_bot.kill_switches import TripwirePlane

__all__ = [
    "TRIPWIRES",
    "MetricStatus",
    "Tripwire",
    "TripwireKind",
    "business_invariants",
    "by_plane",
]


class TripwireKind(StrEnum):
    TECHNICAL = "technical"  # health/latency/error-rate — availability class
    BUSINESS = "business"  # correctness/safety/compliance — the class a green
    # technical dashboard cannot see (team lead's explicit ask)


class MetricStatus(StrEnum):
    WIRED = "wired"  # `metric` is a registered instrument in observability.py
    PLANNED = "planned"  # naming contract only — apps/team-bot/ doesn't exist


class Tripwire(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    metric: str
    threshold: str  # human-readable — several are compound (ratio + window + min-n)
    kind: TripwireKind
    metric_status: MetricStatus
    plane: TripwirePlane | None
    automatic_action: str
    source: str  # mandate F-number / research §, for traceability
    packet_template: str | None = None  # non-None iff the action is "produce a packet"
    requires_arming_condition: str | None = None
    """Non-None means the metric this row reads is populated by a classifier
    that is not yet trustworthy enough to act on automatically — the
    `automatic_action` may be TAKEN (logged, observed) but must not yet be
    treated as reliable enough to drive an unattended kill-switch flip or
    an owner packet with confidence. Set on the QUOTA-derived rows per
    `SPEC-codex-error-classification.md`'s own arming condition: "stays
    dark until a REAL codex exec quota event and a REAL policy block have
    been observed and their exact stderr recorded... no caller may take
    an irreversible action on it" until then. `codex.auth_dead` is
    deliberately NOT gated this way — it reads a different, pre-existing,
    empirically-anchored classifier (one tested pattern), not the refuted
    stderr-regex split.
    """


TRIPWIRES: tuple[Tripwire, ...] = (
    # ======================================================================
    # 1-13: F3 codex-leg + ingress technical tripwires — Sol §2.5 VERBATIM
    # ======================================================================
    Tripwire(
        id="codex.heartbeat_stale",
        metric="codex_broker_heartbeat_age_seconds",
        threshold="> 45 s",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Mark host offline; stop offering jobs; direct to Gemini.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.queue_growing",
        metric="codex_broker_queue_depth",
        threshold=">= 1 waiting job",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Bypass Codex for subsequent messages; do not grow the queue.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.exec_slow",
        metric="codex_exec_seconds",
        threshold="p90 > 12 s over >= 20 jobs",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Do not arm, or revert active traffic to Gemini.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.route_slow",
        metric="client_bot_codex_route_seconds",
        threshold="p95 > 15 s in 3 consecutive 15-min windows",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Disable active Codex routing; keep shadow/probes.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.consecutive_failures",
        metric="codex_consecutive_failures",
        threshold=">= 3",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Open seat breaker for 5 minutes; half-open with one "
        "synthetic canary.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.auth_dead",
        metric="codex_auth_dead_total",
        threshold=">= 1",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Latch seat offline; operator alert; manual OAuth "
        "recovery required (owner switchboard item 4 — codex login).",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.quota_exhausted",
        metric="codex_quota_exhausted_total",
        threshold=">= 1",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Cooldown seat; alert with measured window/reset evidence "
        "— never hidden as a timeout.",
        source="F3; research §2.5",
        requires_arming_condition="SPEC-codex-error-classification.md: the QUOTA "
        "classification is advisory until a REAL quota event's exact stderr is "
        "observed and recorded there. Log/observe freely; do not treat this "
        "count as confident enough to drive the cooldown unattended until then.",
    ),
    Tripwire(
        id="codex.quota_fallback_ratio",
        metric="codex_quota_fallback_total / codex_eligible_requests_total",
        threshold="> 5% over 7 days with >= 50 eligible requests, OR 2 exhausted "
        "windows in 7 days",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=None,  # produces a packet, does not itself flip a switch
        automatic_action="Produce an owner decision packet for stage 2 (metered "
        "key) — never auto-provision a key.",
        source="F3; research §2.5",
        packet_template="docs/plans/2026-08-25-due-bot-live/ops/packets/"
        "QUOTA-WALL-STAGE2-PACKET.template.md",
        requires_arming_condition="Same as codex.quota_exhausted — this ratio's "
        "numerator inherits the same not-yet-arming-condition-met classification. "
        "A packet MAY still be produced (it recommends, it doesn't auto-act), but "
        "state the classification's advisory status in the packet's own Context "
        "section rather than presenting the ratio as settled fact.",
    ),
    Tripwire(
        id="codex.cli_version_mismatch",
        metric="codex_cli_version_mismatch_total",
        threshold=">= 1",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=None,  # the daemon already self-quarantines (refuses to run
        # unpinned); no additional switch to flip, page is the whole action
        automatic_action="Page operator: CLI/config drift detected — restore "
        "WA_CODEX_CLI_VERSION_PIN to the approved version, or re-approve the "
        "new CLI version after re-verifying it. `codex login` fixes nothing "
        "here — this is NOT an AUTH_DEAD/QUOTA condition (owner switchboard "
        "item 4's distinction).",
        source="B7 addition — wa_codex_daemon.py's pre-existing deterministic "
        "version-pin guard; SPEC-codex-error-classification.md flagged this as "
        "the one INTERNAL-class condition that IS operator-actionable and "
        "reliably distinguishable today, unlike the rest of that bucket.",
    ),
    Tripwire(
        id="codex.output_invalid_ratio",
        metric="codex_output_invalid_total / codex_jobs_total",
        threshold="> 1% over >= 100 jobs, OR 2 consecutive invalid outputs",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Quarantine the CLI/model/schema combination; Gemini only.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.secret_canary_hit",
        metric="codex_secret_canary_hits_total",
        threshold="> 0",
        kind=TripwireKind.BUSINESS,  # a secret leak IS a business-harm invariant,
        # not merely an SRE signal — the highest-severity row in this table.
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="GLOBAL codex-leg kill switch "
        "(CLIENT_BOT_CODEX_BROKER_ENABLED=false); P0 operator alert.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="codex.fence_violation",
        metric="codex_fence_violation_or_double_completion_total",
        threshold="> 0",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Disable the active leg and investigate; no affected "
        "output may send.",
        source="F3; research §2.5",
    ),
    Tripwire(
        id="ingress.ack_latency",
        metric="webhook_ack_latency_seconds",
        threshold="p95 > 200 ms for 5 minutes",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=None,  # pages an ingress issue; no single flag models "faster"
        automatic_action="Page ingress issue; shed all LLM work from the "
        "request path.",
        source="F9; research §2.5",
    ),
    Tripwire(
        id="fallback.failure_ratio",
        metric="fallback_provider_failure_total / fallback_provider_requests_total",
        threshold="> 1% over 30 minutes with >= 100 requests",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.CLIENT_SEND,
        automatic_action="Disable bot auto-replies; preserve human handoff only "
        "— the fallback of last resort is itself failing.",
        source="research §2.5",
    ),
    # ======================================================================
    # Business-invariant additions (B7) — the gap the team lead named
    # ======================================================================
    Tripwire(
        id="client.unsupported_claim_escape",
        metric="client_policy_unsupported_claim_escape_total",
        threshold="> 0 in golden/shadow evaluation",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.CLIENT_SEND,
        automatic_action="Block promotion to the next traffic cohort.",
        source="F3; research §2.5 (already business-shaped; carried here for "
        "completeness of the kind=business set)",
    ),
    Tripwire(
        id="client.price_not_in_pricingtool",
        metric="client_bot_price_not_in_pricingtool_total",
        threshold="> 0, OR >= 2 in 1 hour on the same surface",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.CLIENT_SEND,
        automatic_action="First occurrence: P0 page, no auto-flip (single-event "
        "triage). Second occurrence within 1h on the same surface: auto-flip "
        "that surface's CLIENT_BOT_<surface>_SEND_ENABLED to false.",
        source="B7 addition — F1/F5 (PricingTool-only invariant); ASSEMBLY-LINE "
        "P0-tier exemption from the review-cost cap applies to this class",
    ),
    Tripwire(
        id="client.citation_integrity_fail",
        metric="client_bot_citation_integrity_fail_total",
        threshold="> 0 in golden/shadow evaluation",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.CLIENT_SEND,
        automatic_action="Block promotion to the next traffic cohort.",
        source="B7 addition — CLAUDE.md §6 anti-hallucination discipline / "
        "SYMBIOSIS Law 2",
    ),
    Tripwire(
        id="client.handoff_creation_failing",
        metric="client_bot_handoff_creation_failed_total",
        threshold="> 0",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.WIRED,
        plane=None,  # ClientHandoffService itself is unhealthy; no single flag
        # models "make handoff creation work" — this pages, it doesn't disable.
        automatic_action="Page owner — users are receiving the degraded "
        "'puoi richiedere' copy instead of a true handoff (F10 is holding, "
        "but the service backing it is not).",
        source="B7 addition — F10",
    ),
    Tripwire(
        id="client.handoff_context_carryover_low",
        metric="client_bot_handoff_context_missing_total / "
        "client_bot_handoff_created_total",
        threshold="> 20% over 7 days",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.WIRED,
        plane=None,
        automatic_action="Weekly owner digest; 3 consecutive weeks over "
        "threshold feeds the MANDATE.md kill-criterion review — this is the "
        "mandate's own stated product bar failing, not a side metric.",
        source="B7 addition — mandate's own text: 'context carry-over to the "
        "consultant is the product bar'",
    ),
    Tripwire(
        id="client.synthetic_probe_silent",
        metric="client_bot_synthetic_probe_age_seconds",
        threshold="> 900 s (15 min) with no successful probe",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.CLIENT_SEND,
        automatic_action="Auto-flip that surface's CLIENT_BOT_<surface>_SEND_"
        "ENABLED to false; page owner (ASSEMBLY-LINE §7 dead-man switch, "
        "generalized to a non-purchase-funnel product).",
        source="B7 addition — ASSEMBLY-LINE §7",
    ),
    Tripwire(
        id="codex.canary_probe_silent",
        metric="codex_canary_probe_age_seconds",
        threshold="> 900 s (15 min) with no matching canary generation",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.WIRED,
        plane=TripwirePlane.BROKER_GENERATION,
        automatic_action="Cooldown the seat; alert — heartbeat alone proved the "
        "process alive, not that a real generation still works (Kimi §5 FC2).",
        source="B7 addition — LENS 6 Kimi refutation §5 FC2",
    ),
    # ======================================================================
    # Team-bot (BOT B) — naming contract only; apps/team-bot/ is B3's file
    # ownership and does not exist yet. `metric_status=PLANNED` throughout.
    # ======================================================================
    Tripwire(
        id="team.confirmation_bypass",
        metric="team_bot_mutation_without_confirmation_total",
        threshold="> 0",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.PLANNED,
        plane=TripwirePlane.TEAM_MUTATIONS,
        automatic_action="Freeze TEAM_BOT_MUTATIONS_ENABLED globally; P0 page — "
        "non-zero means F6's server-side state machine itself has a hole, not "
        "a user mistake.",
        source="B7 addition — F6",
    ),
    Tripwire(
        id="team.rbac_scope_leak",
        metric="team_bot_rbac_scope_leak_total",
        threshold="> 0",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.PLANNED,
        plane=TripwirePlane.TEAM_MUTATIONS,
        automatic_action="Freeze TEAM_BOT_MUTATIONS_ENABLED and TEAM_BOT_READ_"
        "TOOLS_ENABLED globally; P0 page — a CRM row reached or mutated "
        "outside the actor's assigned_to scope is a UU PDP-class incident "
        "(SYMBIOSIS Law 2).",
        source="B7 addition — F5/F7; Kimi refutation 'Team RBAC readiness' "
        "disagreement (research §7)",
    ),
    Tripwire(
        id="team.idempotency_double_execution",
        metric="team_bot_idempotency_double_execution_total",
        threshold="> 0",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.PLANNED,
        plane=TripwirePlane.TEAM_MUTATIONS,
        automatic_action="Freeze TEAM_BOT_MUTATIONS_ENABLED; P0 page — a "
        "confirmed action executed twice against production CRM.",
        source="B7 addition — F6",
    ),
    Tripwire(
        id="team.auto_failback",
        metric="team_bot_failover_event_total{outcome=auto_failback}",
        threshold="> 0",
        kind=TripwireKind.BUSINESS,
        metric_status=MetricStatus.PLANNED,
        plane=TripwirePlane.FAILOVER_AUTOMATION,
        automatic_action="Freeze TEAM_BOT_FAILOVER_AUTO_ENABLED immediately; P0 "
        "page — F9 states 'no automatic failback' as an architectural "
        "invariant; any occurrence means that invariant broke, not that it "
        "fired correctly.",
        source="B7 addition — F9",
    ),
    Tripwire(
        id="team.tool_output_degradation",
        metric="team_bot_json_parse_fail_total / team_bot_tool_call_total",
        threshold="> 10% over >= 50 calls",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.PLANNED,
        plane=TripwirePlane.TEAM_REPLIES,
        automatic_action="Fall back that tool to a fixed no-tool reply; alert "
        "owner (F4 Kimi FM1/FM5 mitigations degrading in practice).",
        source="F4; F11; LENS 6 Kimi refutation §1",
    ),
    Tripwire(
        id="team.replication_lag",
        metric="team_bot_replication_lag_seconds",
        threshold="> 60 s",
        kind=TripwireKind.TECHNICAL,
        metric_status=MetricStatus.PLANNED,
        plane=TripwirePlane.FAILOVER_AUTOMATION,
        automatic_action="Pro enters read-only mode (research §5.4 step 8).",
        source="F9; research §5.4",
    ),
)

_BY_PLANE_INDEX: dict[TripwirePlane | None, tuple[Tripwire, ...]] = {}
for _t in TRIPWIRES:
    _BY_PLANE_INDEX.setdefault(_t.plane, ())
    _BY_PLANE_INDEX[_t.plane] = (*_BY_PLANE_INDEX[_t.plane], _t)


def by_plane(plane: TripwirePlane | None) -> tuple[Tripwire, ...]:
    return _BY_PLANE_INDEX.get(plane, ())


def business_invariants() -> tuple[Tripwire, ...]:
    """The subset a purely-technical health dashboard cannot see — the set
    the team lead's mandate asked this lane to make explicit.
    """
    return tuple(t for t in TRIPWIRES if t.kind == TripwireKind.BUSINESS)
