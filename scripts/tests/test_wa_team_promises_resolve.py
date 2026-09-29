"""T3 promise gate tests — P2 resolver, pure unit half. The evidence picker is a
pure function over message dicts; the SQL and the guarded writes are proven
against real Postgres in test_wa_team_promises_resolve_real_pg.py. Synthetic
fixtures only.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

import scripts.wa_team_promises as wtp

T0 = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
LONG_AFTER = T0 + timedelta(days=30)


def _m(id_, direction, at, *, media=None, text=None):
    return {"id": id_, "direction": direction, "media_type": media, "text": text, "at": at}


def _h(hours):
    return T0 + timedelta(hours=hours)


# A — which text is a fulfilment: the catalog's own past-tense alternatives only.

@pytest.mark.parametrize("ptype,text", [
    ("send", "already sent the file"),
    ("send", "sudah saya kirim"),
    ("send", "gia inviato ieri"),
    ("send", "I have sent it"),
    ("submit", "already submitted"),
    ("check", "gia controllato"),
    ("process", "sudah proses"),
])
def test_is_fulfilment_true_for_the_catalogs_past_forms(ptype, text):
    assert wtp._is_fulfilment(ptype, text) is True


@pytest.mark.parametrize("ptype,text", [
    ("send", "I will send it tomorrow"),
    ("send", "akan saya kirim besok"),
    ("check", "I have to check"),
    ("process", "already processing"),
    ("send", "hello, how are you"),
    ("send", "already submitted"),
    ("check", "already sent"),
])
def test_is_fulfilment_false_for_future_ongoing_other_type_or_no_match(ptype, text):
    assert wtp._is_fulfilment(ptype, text) is False


# B — the picker: strength order, direction, time, window.

def test_media_beats_team_confirmed_beats_client_ack():
    msgs = [
        _m(1, "inbound", _h(1), text="thanks"),
        _m(2, "outbound", _h(2), text="already sent"),
        _m(3, "outbound", _h(3), media="document"),
    ]
    assert wtp._pick_evidence("send", T0, msgs, LONG_AFTER) == ("media_sent", 3, _h(3))
    assert wtp._pick_evidence("send", T0, msgs[:2], LONG_AFTER) == ("team_confirmed", 2, _h(2))
    assert wtp._pick_evidence("send", T0, msgs[:1], LONG_AFTER) == ("client_ack", 1, _h(1))


def test_earliest_evidence_of_the_winning_kind_is_chosen():
    msgs = [_m(5, "outbound", _h(5), media="image"), _m(4, "outbound", _h(4), media="document")]
    assert wtp._pick_evidence("send", T0, msgs, LONG_AFTER)[1] == 4


@pytest.mark.parametrize("media", ["sticker", "location", "text", None])
def test_a_non_document_media_type_is_not_media_sent(media):
    assert wtp._pick_evidence("send", T0, [_m(1, "outbound", _h(1), media=media)], LONG_AFTER) is None


def test_evidence_at_or_before_the_promise_is_ignored():
    msgs = [_m(1, "outbound", T0, media="document"), _m(2, "outbound", _h(-3), text="already sent")]
    assert wtp._pick_evidence("send", T0, msgs, LONG_AFTER) is None


def test_wrong_direction_never_counts():
    msgs = [
        _m(1, "inbound", _h(1), media="document"),
        _m(2, "inbound", _h(2), text="already sent"),
        _m(3, "outbound", _h(3), text="thanks"),
    ]
    assert wtp._pick_evidence("send", T0, msgs, LONG_AFTER) is None


def test_the_window_is_inclusive_at_its_edge_and_exclusive_past_it():
    edge = T0 + wtp._RESOLVE_WINDOW
    assert wtp._pick_evidence("send", T0, [_m(1, "outbound", edge, media="document")], LONG_AFTER)
    over = edge + timedelta(seconds=1)
    assert wtp._pick_evidence("send", T0, [_m(1, "outbound", over, media="document")], LONG_AFTER) is None


def test_client_ack_is_deferred_until_the_window_has_closed():
    ack = [_m(1, "inbound", _h(1), text="ok thanks")]
    assert wtp._pick_evidence("send", T0, ack, T0 + wtp._RESOLVE_WINDOW - timedelta(seconds=1)) is None
    assert wtp._pick_evidence("send", T0, ack, T0 + wtp._RESOLVE_WINDOW)[0] == "client_ack"


def test_strong_evidence_is_not_deferred():
    msgs = [_m(1, "outbound", _h(1), media="document")]
    assert wtp._pick_evidence("send", T0, msgs, _h(2)) == ("media_sent", 1, _h(1))


def test_an_inbound_message_without_an_ack_word_is_not_an_ack():
    assert wtp._pick_evidence("send", T0, [_m(1, "inbound", _h(1), text="where is it?")], LONG_AFTER) is None


# C — metrics, digest line, CLI wiring.

def test_resolve_metrics_every_field_is_a_bare_int():
    for f in dataclasses.fields(wtp.ResolveMetrics):
        assert f.type == "int", f"{f.name} is {f.type}, not int"


def test_resolution_digest_line_is_counts_and_stable_labels_only():
    line = wtp._resolution_digest_line(3, 2, 1, 5, [("Ari", 3), ("member-0a1b2c", 2)])
    assert line == (
        "promises resolved: media_sent 3 team_confirmed 2; "
        "acked (not confirmed) 1; overdue 5: Ari 3, member-0a1b2c 2"
    )


def test_resolution_digest_line_replaces_an_unsafe_label_and_rejects_non_ints():
    line = wtp._resolution_digest_line(0, 0, 0, 1, [("client 42 +00-INVALID", 1)])
    assert "42" not in line and "INVALID" not in line and "member-" in line
    with pytest.raises(TypeError):
        wtp._resolution_digest_line("3 (client 42)", 0, 0, 0, [])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        wtp._resolution_digest_line(0, 0, 0, 1, [("Ari", "3")])  # type: ignore[list-item]


@pytest.mark.asyncio
@pytest.mark.parametrize("other", ["--scan", "--judge", "--link", "--init-schema"])
async def test_cli_resolve_is_mutually_exclusive_with_other_modes(other):
    assert await wtp.cli_main(["--resolve", other]) == 2


class _NullPool:
    async def close(self):
        pass


@pytest.mark.asyncio
async def test_cli_resolve_prints_counts_only_and_passes_dry_run(monkeypatch, capsys):
    async def _fake_create_pool(**_kwargs):
        return _NullPool()

    seen = {}

    async def _run_resolve(_pool, *, dry_run, now=None):
        seen["dry_run"] = dry_run
        return wtp.ResolveMetrics(scanned=4, media_sent=1, team_confirmed=2, client_ack=1)

    monkeypatch.setattr(wtp.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(wtp, "run_resolve", _run_resolve)
    assert await wtp.cli_main(["--resolve", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert seen["dry_run"] is True
    assert "resolve DRY-RUN scanned=4" in out and "media_sent=1 team_confirmed=2 client_ack=1" in out
    assert await wtp.cli_main(["--resolve"]) == 0
    assert seen["dry_run"] is False
    assert "resolve OK scanned=4" in capsys.readouterr().out


def test_evidence_dated_after_now_is_ignored():
    msgs = [_m(1, "outbound", _h(10), media="document")]
    assert wtp._pick_evidence("send", T0, msgs, _h(9)) is None
    assert wtp._pick_evidence("send", T0, msgs, _h(10)) == ("media_sent", 1, _h(10))


@pytest.mark.parametrize("direction", ["received", "sent", "", None])
def test_only_the_two_current_directions_count_as_evidence(direction):
    msgs = [_m(1, direction, _h(1), text="ok thanks"), _m(2, direction, _h(2), media="document"),
            _m(3, direction, _h(3), text="already sent")]
    assert wtp._pick_evidence("send", T0, msgs, LONG_AFTER) is None


# R1 — a file is the fulfilment of send/submit only.

@pytest.mark.parametrize("ptype,expected", [
    ("send", "media_sent"), ("submit", "media_sent"),
    ("check", None), ("update", None), ("process", None),
])
def test_media_resolves_only_send_and_submit_promises(ptype, expected):
    picked = wtp._pick_evidence(ptype, T0, [_m(1, "outbound", _h(1), media="document")], LONG_AFTER)
    assert (picked[0] if picked else None) == expected


def test_a_check_promise_still_resolves_through_team_confirmed_after_media():
    msgs = [_m(1, "outbound", _h(1), media="document"), _m(2, "outbound", _h(2), text="gia controllato")]
    assert wtp._pick_evidence("check", T0, msgs, LONG_AFTER) == ("team_confirmed", 2, _h(2))


# The window is a literal seven days, not "whatever the constant says".

def test_the_resolve_window_is_literally_seven_days():
    assert wtp._RESOLVE_WINDOW == timedelta(days=7)
    inside = [_m(1, "outbound", T0 + timedelta(days=7), media="document")]
    outside = [_m(1, "outbound", T0 + timedelta(days=7, hours=1), media="document")]
    assert wtp._pick_evidence("send", T0, inside, LONG_AFTER) is not None
    assert wtp._pick_evidence("send", T0, outside, LONG_AFTER) is None


# The consumer: the scan tick sends the resolution line, once a day, best effort.

@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run,expected_calls", [(False, 1), (True, 0)])
async def test_the_scan_tick_calls_the_resolution_digest_only_when_not_dry_run(
    monkeypatch, dry_run, expected_calls
):
    async def _fake_create_pool(**_kwargs):
        return _NullPool()

    async def _run_scan(_pool, *, batch_size, dry_run):
        return wtp.ScanMetrics()

    calls = []

    async def _spy(_pool, _tick):
        calls.append(1)

    monkeypatch.setattr(wtp.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(wtp, "run_scan", _run_scan)
    monkeypatch.setattr(wtp, "_save_scan_metrics", lambda _m: None)
    monkeypatch.setattr(wtp, "_acquire_scan_lock_or_none", lambda: 99)
    monkeypatch.setattr(wtp, "_release_scan_lock", lambda _fd: None)

    async def _no_digest(_pool, _tick):
        return None

    monkeypatch.setattr(wtp, "_maybe_send_digest", _no_digest)
    monkeypatch.setattr(wtp, "_maybe_send_resolution_digest", _spy)
    args = ["--scan"] + (["--dry-run"] if dry_run else [])
    assert await wtp.cli_main(args) == 0
    assert len(calls) == expected_calls


def _wita(hour, minute=10):
    return datetime(2026, 9, 27, hour, minute, tzinfo=wtp._WITA)


@pytest.mark.asyncio
@pytest.mark.parametrize("hour,sent", [(0, 1), (3, 0), (12, 0), (23, 0)])
async def test_the_resolution_digest_goes_out_only_in_the_first_opportunity_of_the_day(
    monkeypatch, hour, sent
):
    fetched, out = [], []

    async def _fetch(_pool):
        fetched.append(1)
        return "promises resolved: media_sent 0 team_confirmed 0; acked (not confirmed) 0; overdue 0"

    monkeypatch.setattr(wtp, "_fetch_resolution_digest", _fetch)
    monkeypatch.setattr(wtp, "_send_resolution_digest", lambda text, *, yesterday_label: out.append(yesterday_label))
    await wtp._maybe_send_resolution_digest(None, _wita(hour))
    assert len(out) == sent and len(fetched) == sent
    if sent:
        assert out == ["2026-09-26"]


@pytest.mark.asyncio
async def test_a_failing_resolution_digest_never_raises_or_sends(monkeypatch):
    out = []

    async def _boom(_pool):
        raise RuntimeError("table missing")

    monkeypatch.setattr(wtp, "_fetch_resolution_digest", _boom)
    monkeypatch.setattr(wtp, "_send_resolution_digest", lambda text, *, yesterday_label: out.append(1))
    await wtp._maybe_send_resolution_digest(None, _wita(0))
    assert out == []
