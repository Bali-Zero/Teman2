"""scripts/s7_yield_dispatch.py -- the fail-closed per-assignee WhatsApp
delivery gate for S7 Yield pitch drafts.

Channel changed from email/Brevo to WhatsApp 2026-08-21 (Zero: Brevo's
NOTIFICATIONS_API_KEY does not exist on any of the three machines). This
corpus covers the WHOLE rewritten dispatcher, per cicatrix-superscar.md #3
(guard conformance -- guilt + innocence + mutation for every gate) and the
Law-2 derogation in SYMBIOSIS.md (2026-08-21):

  1. Guilt: every way a recipient can fail to resolve to a valid, active,
     @balizero.com, non-service-account, WhatsApp-reachable team member
     produces HELD, never a send.
  2. Innocence: a client with a fully valid assignee is delivered, and
     delivered ONLY to that recipient's own clients (RBAC).
  3. Fresh-assignment: `assigned_to` is re-verified against `clients` AT
     SEND TIME -- a stale sidecar copy is never trusted, in either
     direction (a stale-good copy whose fresh value is gone must HELD; a
     stale-bad copy whose fresh value is now valid must be delivered to the
     FRESH owner).
  4. Content scan: the free-text pitch is scanned for forbidden PII shapes
     (passport-like tokens, long digit runs, address markers, implausible
     years) independently of the field-level allowlist -- an LLM can write
     a forbidden fact INTO a sentence that no field filter would catch.
  5. Allowlist formatter: build_whatsapp_message() must never surface a key
     it was not explicitly told to read, even when a row carries extra or
     forbidden fields (full_name, npwp, ...).
  6. Cooldown: unchanged from the email version -- 90-day dedup per
     (client_id, segment).
  7. Mutation: manually verified (see PR body) by deleting checks in a
     scratch copy of resolve_recipient/_is_service_account and re-running
     the guilt suite against it -- it goes red.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import s7_yield_dispatch as dispatch


# ---------------------------------------------------------------------------
# fixtures -- team roster
# ---------------------------------------------------------------------------

ACTIVE_BZ = {"email": "budi@balizero.com", "active": True, "language": "id", "whatsapp": "6281234567890"}
ACTIVE_BZ_2 = {"email": "dea@balizero.com", "active": True, "language": "en", "whatsapp": "6289990000000"}
INACTIVE_BZ = {"email": "sahira@balizero.com", "active": False, "language": "en", "whatsapp": "6288888888888"}
ACTIVE_GMAIL = {"email": "annafishchenko85@gmail.com", "active": True, "language": "en", "whatsapp": "6287777777777"}
ACTIVE_BZ_NO_WA = {"email": "marta@balizero.com", "active": True, "language": "en", "whatsapp": None}
SERVICE_ACCOUNT_EXACT = {"email": "healthcheck@balizero.com", "active": True, "language": "en", "whatsapp": "628111"}
SERVICE_ACCOUNT_PREFIX = {
    "email": "qa.crm.portal.smoke@balizero.com", "active": True, "language": "en", "whatsapp": "628222",
}


def _team() -> dict[str, dict]:
    return {
        "budi@balizero.com": ACTIVE_BZ,
        "dea@balizero.com": ACTIVE_BZ_2,
        "sahira@balizero.com": INACTIVE_BZ,
        "annafishchenko85@gmail.com": ACTIVE_GMAIL,
        "marta@balizero.com": ACTIVE_BZ_NO_WA,
        "healthcheck@balizero.com": SERVICE_ACCOUNT_EXACT,
        "qa.crm.portal.smoke@balizero.com": SERVICE_ACCOUNT_PREFIX,
    }


# ---------------------------------------------------------------------------
# 1. resolve_recipient -- guilt: every non-valid shape HELDs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "assigned_to,expected_reason",
    [
        (None, dispatch.HELD_NO_OWNER),
        ("", dispatch.HELD_NO_OWNER),
        ("   ", dispatch.HELD_NO_OWNER),
        ("+6281234567890", dispatch.HELD_NO_OWNER),  # phone number, not in roster
        ("nobody@balizero.com", dispatch.HELD_NO_OWNER),  # not in roster at all
        ("healthcheck@balizero.com", dispatch.HELD_SERVICE_ACCOUNT),  # exact denylist match
        ("qa.crm.portal.smoke@balizero.com", dispatch.HELD_SERVICE_ACCOUNT),  # prefix denylist match
        # a service-account address absent from the roster entirely is STILL
        # service_account, never no_owner -- the denylist check runs BEFORE
        # the roster lookup in resolve_recipient's own code path.
        ("test.autocheck@balizero.com", dispatch.HELD_SERVICE_ACCOUNT),
        ("sahira@balizero.com", dispatch.HELD_OWNER_INACTIVE),  # left 2026-07-10
        ("annafishchenko85@gmail.com", dispatch.HELD_NON_COMPANY_ADDRESS),  # active, in roster, not @balizero.com
        ("marta@balizero.com", dispatch.HELD_NO_WHATSAPP_NUMBER),  # active, @balizero.com, no number on file
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
    for assigned_to in (
        None, "", "ghost@balizero.com", "sahira@balizero.com",
        "annafishchenko85@gmail.com", "marta@balizero.com", "healthcheck@balizero.com",
    ):
        status, _reason, team_row = dispatch.resolve_recipient(assigned_to, _team())
        if status == dispatch.HELD:
            assert team_row is None


# ---------------------------------------------------------------------------
# 2. resolve_recipient -- innocence
# ---------------------------------------------------------------------------


def test_gate_resolves_active_company_whatsapp_reachable_assignee():
    status, reason, team_row = dispatch.resolve_recipient("budi@balizero.com", _team())
    assert status == dispatch.VALID
    assert reason is None
    assert team_row == ACTIVE_BZ


def test_gate_is_case_insensitive():
    status, _reason, team_row = dispatch.resolve_recipient("Budi@BaliZero.COM", _team())
    assert status == dispatch.VALID
    assert team_row == ACTIVE_BZ


# ---------------------------------------------------------------------------
# 3. _is_service_account -- direct unit coverage of the denylist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email_lower,expected",
    [
        ("healthcheck@balizero.com", True),
        ("test.autocheck@balizero.com", True),
        ("qa.crm.portal.smoke@balizero.com", True),
        ("qa.crm.portal.anything@balizero.com", True),
        ("budi@balizero.com", False),
        ("healthcheck.budi@balizero.com", False),  # not an EXACT match, not a prefix match either
        ("notqa.crm.portal.x@balizero.com", False),  # does not START with the denylisted prefix
    ],
)
def test_is_service_account(email_lower, expected):
    assert dispatch._is_service_account(email_lower) is expected


# ---------------------------------------------------------------------------
# 4. scan_pitch_for_forbidden_content -- guilt + innocence
# ---------------------------------------------------------------------------


def test_scan_flags_passport_like_token():
    violations = dispatch.scan_pitch_for_forbidden_content("Your passport AB1234567 needs renewal soon.")
    assert "passport_like" in violations


def test_scan_flags_long_digit_run_npwp_shaped():
    violations = dispatch.scan_pitch_for_forbidden_content("Your NPWP is 12.345.678.9-012.345 on file.")
    assert "long_document_number" in violations


def test_scan_flags_long_digit_run_ktp_shaped():
    violations = dispatch.scan_pitch_for_forbidden_content("KTP number 3201234567890123 confirmed.")
    assert "long_document_number" in violations


def test_scan_does_not_flag_an_8_digit_date_as_a_document_number():
    """A YYYYMMDD expiry date is exactly 8 digits -- must stay under the
    long_document_number threshold (NPWP=15, KTP=16 digits)."""
    violations = dispatch.scan_pitch_for_forbidden_content("Your KITAS expires on 20260912.")
    assert "long_document_number" not in violations


def test_scan_flags_address_marker():
    violations = dispatch.scan_pitch_for_forbidden_content("Please drop by Jl. Sunset Road for pickup.")
    assert "address_like" in violations


def test_scan_flags_implausible_year_as_dob_like():
    violations = dispatch.scan_pitch_for_forbidden_content("Born in 1985, still a valid client.")
    assert "dob_like" in violations


def test_scan_does_not_flag_a_plausible_expiry_year():
    violations = dispatch.scan_pitch_for_forbidden_content("Your KITAS expires on 12 September 2026.")
    assert "dob_like" not in violations


def test_scan_clean_pitch_has_no_violations():
    violations = dispatch.scan_pitch_for_forbidden_content(
        "Hi Andrea -- your KITAS expires on 12 September. Shall I prepare the document list?"
    )
    assert violations == []


def test_scan_empty_text_has_no_violations():
    assert dispatch.scan_pitch_for_forbidden_content("") == []
    assert dispatch.scan_pitch_for_forbidden_content(None) == []


# ---------------------------------------------------------------------------
# 5. partition_rows -- fresh-assignment re-verification + RBAC + cooldown +
#    no-pitch + content-scan
# ---------------------------------------------------------------------------


def _row(client_id, segment="S1", pitch="Hi there, your document expires soon.",
         lang="English", display_name="Test T.", stale_assigned_to=None, signals=None):
    return {
        "client_id": client_id,
        "assigned_to": stale_assigned_to,  # sidecar's possibly-stale copy -- partition_rows must IGNORE this
        "segment": segment,
        "lang": lang,
        "display_name": display_name,
        "pitch": pitch,
        "signals": signals or {},
    }


def test_partition_uses_fresh_assignment_not_stale_sidecar_copy():
    """Law-2 requirement: a reassignment since draft time must be honored --
    the sidecar said budi, the CURRENT clients row says dea."""
    rows = [_row(1, stale_assigned_to="budi@balizero.com")]
    held, by_recipient, _recipient_rows, cooldown_skipped, no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments={1: "dea@balizero.com"},
    )
    assert not held
    assert cooldown_skipped == 0
    assert no_pitch == 0
    assert list(by_recipient.keys()) == ["dea@balizero.com"]
    assert by_recipient["dea@balizero.com"][0]["client_id"] == 1


def test_partition_holds_when_fresh_assignment_vanished_even_if_stale_copy_was_valid():
    """The sidecar's stale copy names a perfectly valid active assignee, but
    the client is no longer in current_assignments (deleted, unassigned, or
    the id simply didn't come back from the fresh query) -- must HELD, never
    trust the stale copy as a fallback."""
    rows = [_row(2, stale_assigned_to="budi@balizero.com")]
    held, by_recipient, *_ = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments={},
    )
    assert held[dispatch.HELD_NO_OWNER] == 1
    assert by_recipient == {}


def test_partition_holds_inactive_and_no_owner(capsys):
    rows = [
        _row(1, stale_assigned_to="ignored"),
        _row(2, stale_assigned_to="ignored"),
        _row(3, stale_assigned_to="ignored", pitch="Hi there, ..."),
    ]
    held, by_recipient, _recipient_rows, cooldown_skipped, no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments={1: "budi@balizero.com", 2: "sahira@balizero.com"},  # 3 absent -> no_owner
    )
    assert held[dispatch.HELD_OWNER_INACTIVE] == 1
    assert held[dispatch.HELD_NO_OWNER] == 1
    assert cooldown_skipped == 0
    assert no_pitch == 0
    assert list(by_recipient.keys()) == ["budi@balizero.com"]
    assert [r["client_id"] for r in by_recipient["budi@balizero.com"]] == [1]

    # privacy log contract: only client_id + segment + reason, never a pitch
    captured = capsys.readouterr()
    assert "Hi there" not in captured.out
    assert "client_id=2" in captured.out


def test_partition_delivers_only_the_recipients_own_clients():
    """RBAC innocence: a second recipient's email must not carry a client_id
    that belongs to the first recipient."""
    rows = [_row(10), _row(11), _row(20)]
    current = {10: "budi@balizero.com", 11: "budi@balizero.com", 20: "dea@balizero.com"}
    _held, by_recipient, _recipient_rows, _cooldown, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments=current,
    )
    budi_ids = {r["client_id"] for r in by_recipient["budi@balizero.com"]}
    dea_ids = {r["client_id"] for r in by_recipient["dea@balizero.com"]}
    assert budi_ids == {10, 11}
    assert dea_ids == {20}
    assert budi_ids.isdisjoint(dea_ids)


def test_partition_skips_clients_in_cooldown():
    now = datetime.now(timezone.utc)
    registry = {dispatch._cooldown_key(1, "S1"): (now - timedelta(days=10)).isoformat()}
    rows = [_row(1)]
    _held, by_recipient, _recipient_rows, cooldown_skipped, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry=registry, cooldown_days=90, now=now,
        current_assignments={1: "budi@balizero.com"},
    )
    assert cooldown_skipped == 1
    assert by_recipient == {}


def test_partition_does_not_block_a_never_contacted_client():
    rows = [_row(1)]
    _held, by_recipient, _recipient_rows, cooldown_skipped, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments={1: "budi@balizero.com"},
    )
    assert cooldown_skipped == 0
    assert by_recipient["budi@balizero.com"][0]["client_id"] == 1


def test_partition_does_not_block_a_client_whose_cooldown_expired():
    now = datetime.now(timezone.utc)
    registry = {dispatch._cooldown_key(1, "S1"): (now - timedelta(days=91)).isoformat()}
    rows = [_row(1)]
    _held, by_recipient, _recipient_rows, cooldown_skipped, _no_pitch = dispatch.partition_rows(
        rows, _team(), registry=registry, cooldown_days=90, now=now,
        current_assignments={1: "budi@balizero.com"},
    )
    assert cooldown_skipped == 0
    assert by_recipient["budi@balizero.com"][0]["client_id"] == 1


def test_partition_skips_rows_with_no_pitch_text():
    """A dry-run-generated sidecar has pitch=None -- nothing to send, and it
    must not be silently promoted to a delivery."""
    rows = [_row(1, pitch=None)]
    _held, by_recipient, _recipient_rows, _cooldown, no_pitch = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments={1: "budi@balizero.com"},
    )
    assert no_pitch == 1
    assert by_recipient == {}


def test_partition_holds_pitch_flagged_by_content_scan(capsys):
    """Even with a fully valid recipient, a pitch that fails the content
    scan must never be delivered -- and the flagged TEXT must never reach
    the log, only the violation CATEGORY name."""
    rows = [_row(1, pitch="Your passport AB1234567 needs renewal.")]
    held, by_recipient, *_ = dispatch.partition_rows(
        rows, _team(), registry={}, cooldown_days=90, now=datetime.now(timezone.utc),
        current_assignments={1: "budi@balizero.com"},
    )
    assert held[dispatch.HELD_PITCH_CONTENT_FLAGGED] == 1
    assert by_recipient == {}
    captured = capsys.readouterr()
    assert "passport_like" in captured.out
    assert "AB1234567" not in captured.out


# ---------------------------------------------------------------------------
# 6. cooldown registry helpers -- unchanged behavior from the email version
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
# 7. sidecar discovery -- latest per segment, never every historical file
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
# 8. load_current_assignments -- fresh re-verification query
# ---------------------------------------------------------------------------


def test_load_current_assignments_empty_list_skips_query(monkeypatch):
    def _poison(*_a, **_k):
        raise AssertionError("must not query pg.sh when there are no client ids at all")

    monkeypatch.setattr(dispatch.subprocess, "run", _poison)
    assert dispatch.load_current_assignments([]) == {}


def test_load_current_assignments_skips_non_integer_ids(monkeypatch, capsys):
    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd

        class _R:
            returncode = 0
            stdout = '{"id": 1, "assigned_to": "budi@balizero.com"}\n'
            stderr = ""

        return _R()

    monkeypatch.setattr(dispatch.subprocess, "run", _fake_run)
    out = dispatch.load_current_assignments([1, "not-an-int", None])
    assert out == {1: "budi@balizero.com"}
    assert "non-integer" in capsys.readouterr().err
    assert "1" in captured["cmd"][-1]


def test_load_current_assignments_unassigned_client_maps_to_none(monkeypatch):
    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stdout = '{"id": 1, "assigned_to": null}\n'
            stderr = ""

        return _R()

    monkeypatch.setattr(dispatch.subprocess, "run", _fake_run)
    assert dispatch.load_current_assignments([1]) == {1: None}


def test_load_current_assignments_exits_on_pg_failure(monkeypatch):
    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 1
            stdout = ""
            stderr = "pg.sh: connection refused\n"

        return _R()

    monkeypatch.setattr(dispatch.subprocess, "run", _fake_run)
    with pytest.raises(SystemExit) as exc_info:
        dispatch.load_current_assignments([1])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# 9. load_team_roster
# ---------------------------------------------------------------------------


def test_load_team_roster_parses_rows_lowercasing_the_key():
    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stdout = '{"email": "Budi@BaliZero.com", "active": true, "language": "id", "whatsapp": "628123"}\n'
            stderr = ""

        return _R()

    import scripts.s7_yield_dispatch as _mod  # local import so monkeypatch scope stays obvious
    orig = _mod.subprocess.run
    _mod.subprocess.run = _fake_run
    try:
        roster = dispatch.load_team_roster()
    finally:
        _mod.subprocess.run = orig
    assert "budi@balizero.com" in roster
    assert roster["budi@balizero.com"]["whatsapp"] == "628123"


def test_load_team_roster_exits_on_pg_failure(monkeypatch):
    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 1
            stdout = ""
            stderr = "boom\n"

        return _R()

    monkeypatch.setattr(dispatch.subprocess, "run", _fake_run)
    with pytest.raises(SystemExit) as exc_info:
        dispatch.load_team_roster()
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# 10. _fact_line -- segment-aware signal formatting
# ---------------------------------------------------------------------------


def test_fact_line_positive_days_uses_expires_wording():
    line = dispatch._fact_line("en", {"document_type": "kitas", "days_until_expiry": 22, "expiry_date": "2026-09-12"})
    assert "expires" in line
    assert "22" in line


def test_fact_line_negative_days_uses_already_expired_wording():
    line = dispatch._fact_line("en", {"document_type": "visa", "days_until_expiry": -5, "expiry_date": "2026-08-01"})
    assert "already expired" in line
    assert "5" in line  # abs(days), never a literal "-5"
    assert "-5" not in line


def test_fact_line_repeat_segment_uses_completed_services_count():
    line = dispatch._fact_line("en", {"document_type": "repeat", "days_until_expiry": 3})
    assert "3" in line
    assert "completed services" in line


def test_fact_line_last_contact_segment_with_date():
    line = dispatch._fact_line("en", {"document_type": "last_contact", "expiry_date": "2026-05-01"})
    assert "No recent contact" in line
    assert "2026-05-01" in line


def test_fact_line_corporate_segment():
    line = dispatch._fact_line("en", {"document_type": "corporate"})
    assert "no active service" in line.lower()


def test_fact_line_indonesian_wrapper_by_default_on_unknown_language():
    line = dispatch._fact_line("xx-unknown", {"document_type": "kitas", "days_until_expiry": 5, "expiry_date": "2026-09-01"})
    assert "habis" in line  # Indonesian wrapper is the fallback


# ---------------------------------------------------------------------------
# 11. batch_rows
# ---------------------------------------------------------------------------


def test_batch_rows_splits_at_batch_size():
    rows = [{"client_id": i} for i in range(12)]
    batches = dispatch.batch_rows(rows, batch_size=5)
    assert [len(b) for b in batches] == [5, 5, 2]


def test_batch_rows_empty_list_returns_no_batches():
    assert dispatch.batch_rows([]) == []


def test_batch_rows_under_batch_size_is_a_single_batch():
    rows = [{"client_id": i} for i in range(3)]
    assert dispatch.batch_rows(rows, batch_size=5) == [rows]


# ---------------------------------------------------------------------------
# 12. build_whatsapp_message -- allowlist formatter
# ---------------------------------------------------------------------------


def test_build_whatsapp_message_is_allowlist_only():
    """A row carrying extra/forbidden fields (full_name, npwp, an internal
    assigned_to) must never leak them -- the formatter reads ONLY the named
    allowlist fields."""
    row = {
        "client_id": 42,
        "display_name": "Andrea M.",
        "segment": "S1",
        "lang": "English",
        "pitch": "Hi Andrea, your KITAS expires soon.",
        "signals": {"document_type": "kitas", "days_until_expiry": 22, "expiry_date": "2026-09-12"},
        # forbidden / extra fields that must NEVER be read or surfaced
        "full_name": "Andrea Marchetti",
        "npwp": "123456789012345",
        "assigned_to": "budi@balizero.com",
    }
    text = dispatch.build_whatsapp_message("en", [row])
    assert "Andrea M." in text
    assert "Marchetti" not in text
    assert "123456789012345" not in text
    assert "budi@balizero.com" not in text
    assert "#42" in text
    assert "22" in text


def test_build_whatsapp_message_multi_client_header_count():
    rows = [
        {"client_id": 1, "display_name": "A B.", "lang": "English", "pitch": "p1", "signals": {}},
        {"client_id": 2, "display_name": "C D.", "lang": "English", "pitch": "p2", "signals": {}},
        {"client_id": 3, "display_name": "E F.", "lang": "English", "pitch": "p3", "signals": {}},
    ]
    text = dispatch.build_whatsapp_message("en", rows)
    assert "3 clients" in text
    assert "#1" in text and "#2" in text and "#3" in text
    assert "p1" in text and "p2" in text and "p3" in text


def test_build_whatsapp_message_wraps_in_the_team_members_language():
    row = {"client_id": 1, "display_name": "A B.", "lang": "English", "pitch": "hello", "signals": {}}
    id_text = dispatch.build_whatsapp_message("id", [row])
    en_text = dispatch.build_whatsapp_message("en", [row])
    assert "DRAF" in id_text
    assert "DRAFT" in en_text


def test_build_whatsapp_message_falls_back_to_client_when_display_name_missing():
    row = {"client_id": 9, "lang": "English", "pitch": "hi", "signals": {}}
    text = dispatch.build_whatsapp_message("en", [row])
    assert "Client" in text


# ---------------------------------------------------------------------------
# 13. send_whatsapp -- fail-closed on missing key, never sends
# ---------------------------------------------------------------------------


def test_send_whatsapp_without_api_key_never_sends(monkeypatch):
    monkeypatch.delenv("NUZANTARA_API_KEY", raising=False)

    def _poison(*_a, **_k):
        raise AssertionError("send_whatsapp must never open a connection without an API key")

    monkeypatch.setattr(dispatch.urllib.request, "urlopen", _poison)
    ok, err = dispatch.send_whatsapp("budi@balizero.com", "text")
    assert ok is False
    assert "NUZANTARA_API_KEY" in err


def test_send_whatsapp_success_path_posts_email_and_text_never_a_phone(monkeypatch):
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key-value")
    captured = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def _fake_urlopen(req, timeout=20):
        captured["body"] = json.loads(req.data.decode())
        captured["header_values"] = list(dict(req.header_items()).values())
        return _Resp()

    monkeypatch.setattr(dispatch.urllib.request, "urlopen", _fake_urlopen)
    ok, err = dispatch.send_whatsapp("budi@balizero.com", "hello team")
    assert ok is True
    assert err == ""
    assert captured["body"] == {"team_email": "budi@balizero.com", "text": "hello team"}
    assert "test-key-value" in captured["header_values"]
    # the caller passes an email, never a phone number -- the body has no digit-run
    assert not any(ch.isdigit() for ch in captured["body"]["team_email"])


def test_send_whatsapp_http_error_never_reads_response_body(monkeypatch):
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key-value")

    def _fake_urlopen(req, timeout=20):
        raise dispatch.urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr(dispatch.urllib.request, "urlopen", _fake_urlopen)
    ok, err = dispatch.send_whatsapp("budi@balizero.com", "text")
    assert ok is False
    assert "500" in err


# ---------------------------------------------------------------------------
# 14. notify_zero -- aggregate counts only, never a client_id/email/pitch
# ---------------------------------------------------------------------------


def test_notify_zero_carries_no_client_identifiers(monkeypatch):
    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd

        class _R:
            returncode = 0

        return _R()

    monkeypatch.setattr(dispatch.subprocess, "run", _fake_run)
    held = dispatch.Counter(
        {
            dispatch.HELD_OWNER_INACTIVE: 163,
            dispatch.HELD_NO_OWNER: 157,
            dispatch.HELD_SERVICE_ACCOUNT: 2,
            dispatch.HELD_NO_WHATSAPP_NUMBER: 1,
            dispatch.HELD_PITCH_CONTENT_FLAGGED: 3,
            dispatch.HELD_NON_COMPANY_ADDRESS: 4,
        }
    )
    dispatch.notify_zero(held, valid_count=5, sent_or_simulated=5, cooldown_skipped=2, no_pitch=0, dry_run=True)

    text = captured["cmd"][-1]
    for n in ("163", "157", "2", "1", "3", "4"):
        assert n in text
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
