"""The single kill-switch registry for both bots — F11/B7.

MANDATE.md F11: "One kill switch per side-effect plane: client send, broker
generation, team replies, team mutations, failover automation." The team
lead's mandate for this lane is blunter: "A kill switch nobody can find at
3am is not a kill switch." This module is that one place.

Every entry here is a *planned* environment-variable flag, not a promise
that the flag is read today. `status` says which is true for each row —
check it before assuming a flag does anything: superscar family #2
("esiste != armato" — `.claude/rules/cicatrix-superscar.md`) is exactly
the failure mode of believing a kill switch works because a doc describes
it. `wired` means a named source file actually reads the env var via
`backend.app.core.config.Settings` (grep the file before trusting this
column too — it is maintained by hand, not generated). `planned` means
the owning lane has not landed the read yet; the flag is documented here
so its name is reserved and its default is agreed *before* anyone wires
it under time pressure.

The 5 mandate-named planes are `TripwirePlane` members below.
`tripwires.py` references these same plane values so a tripwire's
"automatic action" always names a real, single-gesture switch — never a
plane that exists only in prose.

Human-readable rendering of this exact registry lives in
`docs/plans/2026-08-25-due-bot-live/ops/KILL-SWITCHES.md`;
`test_kill_switches.py::test_markdown_doc_matches_registry` keeps the two
from drifting apart (every `env_var` here must appear verbatim in that
file, and vice versa for anything matching the `_ENABLED`/`_ENABLED=`
flag-name shape).

Author: Claude Opus 5 (lane B7 — control tower).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "KILL_SWITCHES",
    "KillSwitch",
    "KillSwitchStatus",
    "TripwirePlane",
    "by_env_var",
    "by_plane",
]


class TripwirePlane(StrEnum):
    """The 5 side-effect planes F11 names verbatim. Every KillSwitch and
    every Tripwire (`tripwires.py`) attaches to exactly one of these — a
    tripwire whose automatic action does not map to one of these planes
    is naming a switch that does not exist yet (write the KillSwitch row
    first).
    """

    CLIENT_SEND = "client_send"
    BROKER_GENERATION = "broker_generation"
    TEAM_REPLIES = "team_replies"
    TEAM_MUTATIONS = "team_mutations"
    FAILOVER_AUTOMATION = "failover_automation"


class KillSwitchStatus(StrEnum):
    """Honest status per superscar #2 — see module docstring."""

    WIRED = "wired"  # a named source file reads this env var today
    PLANNED = "planned"  # name + default agreed; no lane reads it yet


class KillSwitch(BaseModel):
    """One single-gesture off switch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    env_var: str
    plane: TripwirePlane
    default_dark: bool  # True == default value ships the effect OFF
    scope: str  # e.g. "surface:whatsapp", "seat:codex-broker-*", "global"
    effect_when_off: str
    owning_lane: str  # B1/B2/B3/B5 — who wires the read
    status: KillSwitchStatus
    verify_command: str  # how to prove the flip actually took effect


KILL_SWITCHES: tuple[KillSwitch, ...] = (
    # -- Client-bot per-surface send gates (F1/F2, go-live checklist §5.5) --
    KillSwitch(
        env_var="CLIENT_BOT_WA_SEND_ENABLED",
        plane=TripwirePlane.CLIENT_SEND,
        default_dark=True,
        scope="surface:whatsapp",
        effect_when_off="ChannelRouter evaluates and logs the FinalPolicyGate "
        "verdict but the WhatsApp adapter never calls the Meta send API — "
        "shadow mode.",
        owning_lane="B1",
        status=KillSwitchStatus.PLANNED,
        verify_command="grep CLIENT_BOT_WA_SEND_ENABLED apps/backend-rag/backend/"
        "channels/whatsapp/adapter.py, then send a shadow-mode probe and confirm "
        "no outbound Meta API call in wa_outbox_worker logs.",
    ),
    KillSwitch(
        env_var="CLIENT_BOT_IG_SEND_ENABLED",
        plane=TripwirePlane.CLIENT_SEND,
        default_dark=True,
        scope="surface:instagram",
        effect_when_off="Same as WA: gate evaluated, no Instagram DM sent.",
        owning_lane="B1",
        status=KillSwitchStatus.PLANNED,
        verify_command="grep CLIENT_BOT_IG_SEND_ENABLED apps/backend-rag/backend/"
        "channels/instagram/adapter.py.",
    ),
    KillSwitch(
        env_var="CLIENT_BOT_PORTAL_SEND_ENABLED",
        plane=TripwirePlane.CLIENT_SEND,
        default_dark=True,
        scope="surface:portal",
        effect_when_off="Portal chat evaluates the gate but the answer is not "
        "returned to the authenticated session.",
        owning_lane="B1",
        status=KillSwitchStatus.PLANNED,
        verify_command="grep CLIENT_BOT_PORTAL_SEND_ENABLED in the portal chat "
        "response path.",
    ),
    KillSwitch(
        env_var="CLIENT_BOT_KBLI_SEND_ENABLED",
        plane=TripwirePlane.CLIENT_SEND,
        default_dark=True,
        scope="surface:kbli_widget",
        effect_when_off="KBLI widget evaluates the gate but returns no "
        "classification to the caller.",
        owning_lane="B1",
        status=KillSwitchStatus.PLANNED,
        verify_command="grep CLIENT_BOT_KBLI_SEND_ENABLED in the kbli widget "
        "response path.",
    ),
    # -- Codex broker leg (F3) ------------------------------------------
    KillSwitch(
        env_var="CLIENT_BOT_CODEX_BROKER_ENABLED",
        plane=TripwirePlane.BROKER_GENERATION,
        default_dark=True,
        scope="global (all seats, all surfaces)",
        effect_when_off="wa_broker never offers job_kind=client_answer_v1 jobs "
        "to any codex seat; every client-bot turn routes to Gemini only. This "
        "is the leg-wide switch — codex_secret_canary_hits_total>0 must flip "
        "this to false automatically, not merely alert (Sol §2.5).",
        owning_lane="B2",
        status=KillSwitchStatus.PLANNED,
        verify_command="grep CLIENT_BOT_CODEX_BROKER_ENABLED in wa_broker job "
        "offer logic; confirm codex_jobs_total stops incrementing after flip.",
    ),
    KillSwitch(
        env_var="WA_CODEX_SEAT_<n>_BREAKER_LATCHED",
        plane=TripwirePlane.BROKER_GENERATION,
        default_dark=False,
        scope="seat:codex-broker-<n>",
        effect_when_off="N/A — this is a runtime-latched state, not an "
        "operator-set env var: codex_auth_dead_total>=1 or 3 consecutive "
        "failures set it; operator re-login clears it (existing dark "
        "implementation's breaker, generalized per F3).",
        owning_lane="B2",
        status=KillSwitchStatus.WIRED,
        verify_command="ssh into the seat's daemon host, check breaker state "
        "log line 'wa-codex-daemon: codex seat AUTH DEATH detected'.",
    ),
    # -- Team bot (F4-F9, go-live checklist §5.5 activation flags) --------
    KillSwitch(
        env_var="TEAM_BOT_INGRESS_ENABLED",
        plane=TripwirePlane.TEAM_REPLIES,
        default_dark=True,
        scope="global",
        effect_when_off="Meta webhook is not subscribed / durable insert path "
        "does not run; no inbound team-bot traffic is accepted at all — the "
        "first rung of the promotion ladder (§5.5).",
        owning_lane="B3",
        status=KillSwitchStatus.PLANNED,
        verify_command="curl the Funnel/forwarder URL and confirm 404/503 "
        "rather than a 200 ack when this is false.",
    ),
    KillSwitch(
        env_var="TEAM_BOT_REPLY_ENABLED",
        plane=TripwirePlane.TEAM_REPLIES,
        default_dark=True,
        scope="global",
        effect_when_off="Inbound messages are durably logged and audited but "
        "no model-generated reply is sent — ingress/audit-only rung.",
        owning_lane="B3",
        status=KillSwitchStatus.PLANNED,
        verify_command="send a synthetic WA message to the team number and "
        "confirm an audit row exists with zero outbound send.",
    ),
    KillSwitch(
        env_var="TEAM_BOT_READ_TOOLS_ENABLED",
        plane=TripwirePlane.TEAM_REPLIES,
        default_dark=True,
        scope="global",
        effect_when_off="R0/R1 read tools (client.lookup, practice.list_"
        "assigned, ...) are not exposed to the model — staff get owner-only "
        "fixed replies, no CRM read.",
        owning_lane="B3",
        status=KillSwitchStatus.PLANNED,
        verify_command="ask the bot a read question from an allowlisted staff "
        "number and confirm no tool_call is emitted while false.",
    ),
    KillSwitch(
        env_var="TEAM_BOT_MUTATIONS_ENABLED",
        plane=TripwirePlane.TEAM_MUTATIONS,
        default_dark=True,
        scope="global",
        effect_when_off="R2/R3 tools (practice.status_change, document.mark_"
        "received, reminder.create, practice.open_commit) are not registered "
        "at all — the single highest-severity client-bot-adjacent switch, "
        "since this is the only plane that can write to production CRM.",
        owning_lane="B3",
        status=KillSwitchStatus.PLANNED,
        verify_command="attempt a confirmed mutation against staging CRM and "
        "confirm 403/tool-not-found while false; team_bot_mutation_total must "
        "stay at 0.",
    ),
    KillSwitch(
        env_var="TEAM_BOT_FAILOVER_AUTO_ENABLED",
        plane=TripwirePlane.FAILOVER_AUTOMATION,
        default_dark=True,
        scope="global",
        effect_when_off="team-bot-failoverd never issues a WABA callback "
        "override automatically — Mini down means team-bot down until an "
        "operator manually repoints the webhook. F9/Sol disagreement #2: "
        "stays dark until a staging-WABA retry drill passes (mandate: "
        "'AUTO-failover stays DARK until a staging-WABA drill proves Meta's "
        "retry semantics').",
        owning_lane="B5",
        status=KillSwitchStatus.PLANNED,
        verify_command="run the synthetic failover drill (research capture "
        "§5.4); confirm zero callback-override calls in the fake Graph API "
        "log while false.",
    ),
)

_BY_ENV_VAR: dict[str, KillSwitch] = {k.env_var: k for k in KILL_SWITCHES}


def by_env_var(env_var: str) -> KillSwitch | None:
    return _BY_ENV_VAR.get(env_var)


def by_plane(plane: TripwirePlane) -> tuple[KillSwitch, ...]:
    return tuple(k for k in KILL_SWITCHES if k.plane == plane)
