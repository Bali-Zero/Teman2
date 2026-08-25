"""Team-bot ingress + failover (lane B5, MANDATE.md F9).

Owns the pieces that sit BETWEEN Meta and the team-bot runtime that B3
builds in ``apps/team-bot/``: the Tailscale Funnel plumbing, the
leader-epoch CAS control record (superscar family #10's antidote — a
Single-Source-of-Truth the CRM backend itself can check, never a per-Mac
belief), the WABA callback-override client, and ``team-bot-failoverd`` —
the Pro-only daemon that watches Mini and promotes on sustained failure.

Deliberately NOT under ``apps/team-bot/`` (B3's file ownership, per
MANDATE.md's lane table) and deliberately NOT a second jobs/queue table —
this package is a thin control plane that ``apps/team-bot/`` will mount
(``control_router.py``) once it exists, and that the EXISTING backend-rag
CRM mutation endpoints can import in-process to reject a stale epoch (F7:
"Backend routes independently enforce ... the local authorizer is
early-deny only").

Module map:
    ``ingress_leader.py``     — pure CAS state machine (no I/O). The thing
                                that had to be "settled" before the drill
                                could be trusted (see B5's report to the
                                orchestrator).
    ``ingress_state_repo.py`` — Postgres-backed ``IngressLeaderStore``
                                implementation (asyncpg), thin adapter over
                                ``ingress_leader.py``'s logic.
    ``waba_override.py``      — typed client for
                                ``POST /{WABA-ID}/subscribed_apps`` +
                                read-back verification.
    ``control_router.py``     — ``/readyz`` / ``/livez`` / ``/leader``
                                FastAPI router, mountable by B3.
    ``failoverd.py``          — the Pro-only watch loop; every dependency
                                is injected so the drill suite in
                                ``backend/tests/duebot/failover/`` can run
                                it with zero real sockets (network_guard.py
                                enforces that at test-collection time).
"""

from __future__ import annotations
