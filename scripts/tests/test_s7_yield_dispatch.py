"""scripts/s7_yield_dispatch.py -- the fail-closed per-assignee delivery gate
for S7 Yield WhatsApp-pitch drafts.

Team-lead mandate (2026-08-20): a draft may reach ONLY the Bali Zero team
member the client is assigned to, and NEVER a default recipient when that
resolution fails. Required proofs, per cicatrix-superscar.md #3 (guard
conformance -- guilt + innocence + mutation for every gate):

  1. Guilt: every way `assigned_to` can fail to resolve to a valid, active,
     @balizero.com mailbox produces HELD, never a send.
  2. Innocence: a client with a valid active @balizero.com assignee is
     delivered, and delivered ONLY to that recipient's own clients (RBAC).
  3. Cooldown: a client contacted <90d ago is skipped; a client never
     contacted, or contacted >90d ago, is not blocked.
  4. Mutation: manually verified (see PR body) by deleting the `active`
     check in a scratch copy of resolve_recipient and re-running the guilt
     suite against it -- it goes red.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import s7_yield_dispatch as dispatch


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

ACTIVE_BZ = {"email": "budi@balizero.com", "active": True, "language": "id"}
INACTIVE_BZ = {"email": "sahira@balizero.com", "active": False, "language": "en"}
ACTIVE_GMAIL = {"email": "annafishchenko85@gmail.com", "active": True, "language": "en"}


def _team() -> dict[str, dict]:
    return {
        "budi@balizero.com": ACTIVE_BZ,
        "sahira@balizero.com": INACTIVE_BZ,
        "annafishchenko85@gmail.com": ACTIVE_GMAIL,
    }


# ---------------------------------------------------------------------------
# 1. Guilt -- resolve_recipient must HELD every non-valid shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "assigned_to,expected_reason",
    [
        (None, dispatch.HELD_NO_OWNER),
        ("", dispatch.HELD_NO_OWNER),
        ("   ", dispatch.HELD_NO_OWNER),
        ("+6281234567890", dispatch.HELD_NO_OWNER),  # phone number, not in roster
        ("nobody@balizero.com", dispatch.HELD_NO_OWNER),  # not in roster at all
        ("sahira@balizero.com", dispatch.HELD_OWNER_INACTIVE),  # left 2026-07-10
        ("annafishchenko85@gmail.com", dispatch.HELD_NON_COMPANY_ADDRESS),  # active, in roster, not @balizero.com
    ],
)
def test_gate_holds_every_invalid_shape(assigned_to, expected_reason):
    status, reason, team_row = dispatch.resolve_recipient(assigned_to, _team())
    assert status == dispatch.HELD
    assert reason == expected_reason
    assert team_row is None


def test_gate_never_returns_a_fallback_recipient():
    """No branch of resolve_recipient may hand back a team_row when HELD --
    there is no code path in this file that substitutes a default owner."""
    for assigned_to in (None, "", "ghost@balizero.com", "sahira@balizero.com", "annafishchenko85@gmail.com"):
        status, _reason, team_row = dispatch.resolve_recipient(assigned_to, _team())
        if status == dispatch.HELD:
            assert team_row is None


# ---------------------------------------------------------------------------
# 2. Innocence -- a valid assignee is resolved, case-insensitively
# ---------------------------------------------------------------------------


def test_gate_resolves_active_company_assignee():
    status, reason, team_row = dispatch.resolve_recipient("budi@balizero.com", _team())
    assert status == dispatch.VALID
    assert reason is None
    assert team_row == ACTIVE_BZ


def test_gate_is_case_insensitive():
    status, _reason, team_row = dispatch.resolve_recipient("Budi@BaliZero.COM", _team())
    assert status == dispatch.VALID
    assert team_row == ACTIVE_BZ


# ---------------------------------------------------------------------------
# 3. partition_rows -- RBAC grouping + cooldown + no-pitch
# ---------------------------------------------------------------------------


def _row(client_id, assigned_to, segment="S1", pitch="Hi there, ..."):
    return {
        "client_id": client_id,
        "assigned_to": assigned_to,
        "segment": segment,
        "lang": "English",
        "pitch": pitch,
        "signals": {},
    }


def test_partition_holds_inactive_and_delivers_active(capsys):
    rows = [
        _row(1, "budi@balizero.com"),
        _row(2, "sahira@balizero.com"),  # HELD: inactive
        _row(3, None),  # HELD: no owner
    ]
    held, by_recipient, recipient_rows, cooldown_skipped, no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc)
    )
    assert held[dispatch.HELD_OWNER_INACTIVE] == 1
    assert held[dispatch.HELD_NO_OWNER] == 1
    assert cooldown_skipped == 0
    assert no_pitch == 0
    assert list(by_recipient.keys()) == ["budi@balizero.com"]
    assert [r["client_id"] for r in by_recipient["budi@balizero.com"]] == [1]

    # privacy log contract: only client_id + segment + reason, never a name/pitch
    captured = capsys.readouterr()
    assert "Hi there" not in captured.out
    assert "client_id=2" in captured.out


def test_partition_delivers_only_the_recipients_own_clients():
    """RBAC innocence: a second recipient's email must not carry a client_id
    that belongs to the first recipient."""
    team = _team()
    team["dea@balizero.com"] = {"email": "dea@balizero.com", "active": True, "language": "en"}
    rows = [
        _row(10, "budi@balizero.com"),
        _row(11, "budi@balizero.com"),
        _row(20, "dea@balizero.com"),
    ]
    _held, by_recipient, _recipient_rows, _cooldown, _no_pitch = dispatch.partition_rows(
        rows, team, registry={}, cooldown_days=90, now=datetime.now(timezone.utc)
    )
    budi_ids = {r["client_id"] for r in by_recipient["budi@balizero.com"]}
    dea_ids = {r["client_id"] for r in by_recipient["dea@balizero.com"]}
    assert budi_ids == {10, 11}
    assert dea_ids == {20}
    assert budi_ids.isdisjoint(dea_ids)


def test_partition_skips_clients_in_cooldown():
    now = datetime.now(timezone.utc)
    registry = {dispatch._cooldown_key(1, "S1"): (now - timedelta(days=10)).isoformat()}
    rows = [_row(1, "budi@balizero.com")]
    _held, by_recipient, _recipient_rows, cooldown_skipped, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry=registry, cooldown_days=90, now=now
    )
    assert cooldown_skipped == 1
    assert by_recipient == {}


def test_partition_does_not_block_a_never_contacted_client():
    rows = [_row(1, "budi@balizero.com")]
    _held, by_recipient, _recipient_rows, cooldown_skipped, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc)
    )
    assert cooldown_skipped == 0
    assert by_recipient["budi@balizero.com"][0]["client_id"] == 1


def test_partition_does_not_block_a_client_whose_cooldown_expired():
    now = datetime.now(timezone.utc)
    registry = {dispatch._cooldown_key(1, "S1"): (now - timedelta(days=91)).isoformat()}
    rows = [_row(1, "budi@balizero.com")]
    _held, by_recipient, _recipient_rows, cooldown_skipped, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry=registry, cooldown_days=90, now=now
    )
    assert cooldown_skipped == 0
    assert by_recipient["budi@balizero.com"][0]["client_id"] == 1


def test_partition_skips_rows_with_no_pitch_text():
    """A dry-run-generated sidecar has pitch=None -- nothing to send, and it
    must not be silently promoted to a delivery."""
    rows = [_row(1, "budi@balizero.com", pitch=None)]
    _held, by_recipient, _recipient_rows, _cooldown, no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc)
    )
    assert no_pitch == 1
    assert by_recipient == {}


# ---------------------------------------------------------------------------
# 4. cooldown registry helpers
# ---------------------------------------------------------------------------


def test_registry_roundtrip_is_0600(tmp_path):
    path = tmp_path / "sub" / "dispatch-registry.json"
    dispatch.save_registry(path, {"1|S1": "2026-08-01T00:00:00+00:00"})
    assert path.exists()
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
    loaded = dispatch.load_registry(path)
    assert loaded == {"1|S1": "2026-08-01T00:00:00+00:00"}


def test_registry_missing_file_loads_empty(tmp_path):
    assert dispatch.load_registry(tmp_path / "nope.json") == {}


def test_mark_sent_then_in_cooldown():
    registry: dict[str, str] = {}
    now = datetime.now(timezone.utc)
    dispatch.mark_sent(registry, 5, "S2", now)
    assert dispatch.in_cooldown(registry, 5, "S2", 90, now + timedelta(days=1)) is True
    assert dispatch.in_cooldown(registry, 5, "S2", 90, now + timedelta(days=91)) is False


# ---------------------------------------------------------------------------
# 5. sidecar discovery -- latest per segment, never every historical file
# ---------------------------------------------------------------------------


def test_discover_latest_sidecars_keeps_only_newest_per_segment(tmp_path):
    for name in [
        "S1-20260601T040000Z-drafts.jsonl",
        "S1-20260817T040000Z-drafts.jsonl",  # newest S1
        "S2-20260810T040000Z-drafts.jsonl",
    ]:
        (tmp_path / name).write_text("")
    found = {p.name for p in dispatch.discover_latest_sidecars(tmp_path)}
    assert found == {"S1-20260817T040000Z-drafts.jsonl", "S2-20260810T040000Z-drafts.jsonl"}


def test_discover_latest_sidecars_empty_dir_returns_empty(tmp_path):
    assert dispatch.discover_latest_sidecars(tmp_path / "does-not-exist") == []


def test_read_sidecar_rows_skips_malformed_lines(tmp_path, capsys):
    path = tmp_path / "S1-x-drafts.jsonl"
    path.write_text('{"client_id": 1, "assigned_to": "a@balizero.com"}\nNOT JSON\n\n')
    rows = dispatch.read_sidecar_rows(path)
    assert rows == [{"client_id": 1, "assigned_to": "a@balizero.com"}]
    assert "malformed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 6. email builder -- never leaks a foreign client_id, escapes pitch text
# ---------------------------------------------------------------------------


def test_build_email_contains_only_the_given_rows():
    rows = [_row(1, "budi@balizero.com", pitch="Hello Budi <3"), _row(2, "budi@balizero.com", pitch="Hi Dea")]
    subject, body = dispatch.build_email("en", rows)
    assert "client_id=1" in body
    assert "client_id=2" in body
    assert "Hello Budi" in body
    # html.escape must have run on the pitch text
    assert "&lt;3" in body


def test_build_email_falls_back_to_indonesian_for_unknown_language():
    _subject, body = dispatch.build_email("xx-unknown", [_row(1, "budi@balizero.com")])
    assert dispatch._STRINGS["id"]["intro"] in body


# ---------------------------------------------------------------------------
# 7. send_email -- fail-closed on missing key, never sends
# ---------------------------------------------------------------------------


def test_send_email_without_api_key_never_sends(monkeypatch):
    monkeypatch.delenv("NOTIFICATIONS_API_KEY", raising=False)

    def _poison(*_a, **_k):
        raise AssertionError("send_email must never open a connection without an API key")

    monkeypatch.setattr(dispatch.urllib.request, "urlopen", _poison)
    ok, err = dispatch.send_email("budi@balizero.com", "subj", "<p>body</p>")
    assert ok is False
    assert "NOTIFICATIONS_API_KEY" in err


# ---------------------------------------------------------------------------
# 8. notify_zero -- aggregate counts only, never a client_id/name
# ---------------------------------------------------------------------------


def test_notify_zero_carries_no_client_identifiers(monkeypatch, tmp_path):
    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd

        class _R:
            returncode = 0

        return _R()

    monkeypatch.setattr(dispatch.subprocess, "run", _fake_run)
    held = dispatch.Counter({dispatch.HELD_OWNER_INACTIVE: 163, dispatch.HELD_NO_OWNER: 157})
    dispatch.notify_zero(held, valid_count=5, sent_or_simulated=5, cooldown_skipped=2, no_pitch=0, dry_run=True)

    text = captured["cmd"][-1]
    assert "163" in text
    assert "157" in text
    assert "@balizero.com" not in text  # no address/client identity, counts only
    assert "client_id" not in text
    # interprete assoluto -- mai "python3" risolto via PATH (W107/W108)
    assert captured["cmd"][0] == dispatch.sys.executable


def test_notify_zero_never_raises_when_gateway_is_unreachable(monkeypatch, capsys):
    def _boom(*_a, **_k):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(dispatch.subprocess, "run", _boom)
    # Must not raise -- a dead alert gateway must never crash the dispatcher
    # (W107/W108 discipline). Assert the completion is real, not implicit:
    # the exception was caught and logged, not swallowed silently either.
    dispatch.notify_zero(dispatch.Counter(), 0, 0, 0, 0, dry_run=True)
    assert "tg_notify invocation failed" in capsys.readouterr().err
