"""EventBus channel ↔ consumer parity (Antibody Debt ledger #7, 2026-06-13).

SCAR CONTEXT: the connectome TAC (2026-06-13) flagged 5 PG channels as
"producer without consumer" — disk verification showed they ARE consumed, but
only by the pg-to-organism bridge daemon on the Pro, invisible to anyone
reading the backend handlers. Nothing prevented a NEW channel from being added
to PG_CHANNEL_MAP with no consumer at all: its events would be produced
durably into events_outbox and dropped silently until prune.

CHANNEL_CONSUMERS in event_bus.py is the normative declaration; these tests
keep it honest in all directions:

  - declaration coverage: every PG_CHANNEL_MAP channel declares ≥1 consumer;
  - "bridge" claims match scripts/pg-to-organism-bridge.py CHANNELS (AST);
  - "in_app" claims match an actual bus.subscribe of the channel's event_type
    somewhere in the backend source (static scan);
  - "external:*" claims point at a real module that names the channel;
  - reverse: bridge channels are PG_CHANNEL_MAP channels (or the documented
    bridge-only allowlist), so a renamed/dropped channel can't leave the
    bridge LISTENing a dead name.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.services.events.event_bus import CHANNEL_CONSUMERS, PG_CHANNEL_MAP

BACKEND_DIR = Path(__file__).resolve().parents[3]  # apps/backend-rag/backend
REPO_ROOT = BACKEND_DIR.parents[2]
BRIDGE_PATH = REPO_ROOT / "scripts" / "pg-to-organism-bridge.py"

# PG channels the bridge LISTENs that are NOT EventBus channels: they are
# raw NOTIFY producers outside PG_CHANNEL_MAP. Every entry needs a reason.
BRIDGE_ONLY_CHANNELS: frozenset[str] = frozenset(
    {
        # WR2 supervisor publishes NOTIFY wr2_status_change directly (WR2
        # queue system, pre-dates the EventBus map — see P0-2 scar note:
        # "wr2_status_change not in PG_CHANNEL_MAP").
        "wr2_status_change",
    }
)

# Modules whose source may satisfy an "in_app" claim: anything under backend/
# that calls .subscribe( — excluding the bus itself and tests.
_SUBSCRIBE_SCAN_EXCLUDE = ("tests", "__pycache__")


def _bridge_channels() -> set[str]:
    """Parse CHANNELS = [...] from the bridge script without importing it."""
    assert BRIDGE_PATH.is_file(), (
        f"bridge script not found at {BRIDGE_PATH} — if it moved, update this "
        f"test AND the CHANNEL_CONSUMERS docstring"
    )
    tree = ast.parse(BRIDGE_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "CHANNELS":
                    assert isinstance(node.value, (ast.List, ast.Tuple))
                    return {
                        el.value
                        for el in node.value.elts
                        if isinstance(el, ast.Constant) and isinstance(el.value, str)
                    }
    raise AssertionError("CHANNELS list not found in pg-to-organism-bridge.py")


def _subscribed_event_types() -> set[str]:
    """Event types that appear as a string literal in any backend module that
    also calls .subscribe( — a static lower bound for in-app consumption."""
    found: set[str] = set()
    event_types = set(PG_CHANNEL_MAP.values())
    for py in (BACKEND_DIR / "services").rglob("*.py"):
        if any(part in _SUBSCRIBE_SCAN_EXCLUDE for part in py.parts):
            continue
        if py.name == "event_bus.py":  # the bus defines, it does not consume
            continue
        text = py.read_text(errors="replace")
        if ".subscribe(" not in text:
            continue
        for et in event_types:
            if f'"{et}"' in text or f"'{et}'" in text:
                found.add(et)
    # app_factory subscribes the SSE handler outside backend/services/.
    app_factory = BACKEND_DIR / "app" / "setup" / "app_factory.py"
    if app_factory.is_file():
        text = app_factory.read_text(errors="replace")
        if ".subscribe(" in text:
            for et in event_types:
                if f'"{et}"' in text or f"'{et}'" in text:
                    found.add(et)
    return found


BRIDGE_CHANNELS = _bridge_channels()
SUBSCRIBED_EVENT_TYPES = _subscribed_event_types()


class TestDeclarationCoverage:
    def test_every_channel_is_declared(self) -> None:
        missing = set(PG_CHANNEL_MAP) - set(CHANNEL_CONSUMERS)
        assert not missing, (
            f"PG channel(s) with NO consumer declaration (orphan events would "
            f"be produced durably and dropped silently): {sorted(missing)} — "
            f"declare them in CHANNEL_CONSUMERS"
        )

    def test_no_stale_declarations(self) -> None:
        stale = set(CHANNEL_CONSUMERS) - set(PG_CHANNEL_MAP)
        assert not stale, f"CHANNEL_CONSUMERS declares non-existent channel(s): {sorted(stale)}"

    def test_every_channel_has_at_least_one_consumer(self) -> None:
        empty = [ch for ch, kinds in CHANNEL_CONSUMERS.items() if not kinds]
        assert not empty, f"channel(s) declared with ZERO consumers: {empty}"


class TestBridgeClaims:
    def test_bridge_claims_match_bridge_channels(self) -> None:
        claimed = {ch for ch, kinds in CHANNEL_CONSUMERS.items() if "bridge" in kinds}
        not_in_bridge = claimed - BRIDGE_CHANNELS
        assert not not_in_bridge, (
            f"channel(s) declare 'bridge' but pg-to-organism-bridge.py does "
            f"NOT LISTEN them: {sorted(not_in_bridge)}"
        )

    def test_bridge_channels_are_known(self) -> None:
        unknown = BRIDGE_CHANNELS - set(PG_CHANNEL_MAP) - BRIDGE_ONLY_CHANNELS
        assert not unknown, (
            f"bridge LISTENs channel(s) unknown to PG_CHANNEL_MAP and not in "
            f"the bridge-only allowlist (dead or renamed?): {sorted(unknown)}"
        )

    def test_bridge_covered_channels_declare_it(self) -> None:
        """If the bridge LISTENs an EventBus channel, the declaration must say
        so — otherwise CHANNEL_CONSUMERS under-reports reality."""
        undeclared = {
            ch
            for ch in BRIDGE_CHANNELS & set(PG_CHANNEL_MAP)
            if "bridge" not in CHANNEL_CONSUMERS.get(ch, frozenset())
        }
        assert not undeclared, (
            f"bridge LISTENs these channels but CHANNEL_CONSUMERS does not "
            f"declare 'bridge' for them: {sorted(undeclared)}"
        )


class TestInAppClaims:
    @pytest.mark.parametrize(
        "channel",
        [ch for ch, kinds in CHANNEL_CONSUMERS.items() if "in_app" in kinds],
    )
    def test_in_app_claim_has_a_subscriber(self, channel: str) -> None:
        event_type = PG_CHANNEL_MAP[channel]
        assert event_type in SUBSCRIBED_EVENT_TYPES, (
            f"channel {channel} declares 'in_app' but no backend module that "
            f"calls .subscribe( mentions event type '{event_type}'"
        )


class TestExternalClaims:
    def test_external_claims_point_at_real_modules(self) -> None:
        known_external = {
            "external:federation_alerts_daemon": (
                BACKEND_DIR / "services" / "federation_alerts" / "daemon.py",
                "federation_alert",
            ),
        }
        for ch, kinds in CHANNEL_CONSUMERS.items():
            for kind in kinds:
                if not kind.startswith("external:"):
                    continue
                assert kind in known_external, (
                    f"channel {ch} declares unknown external consumer '{kind}' "
                    f"— register it in this test with its module path"
                )
                path, needle = known_external[kind]
                assert path.is_file(), f"{kind}: module {path} does not exist"
                assert needle in path.read_text(errors="replace"), (
                    f"{kind}: {path} no longer mentions '{needle}'"
                )
