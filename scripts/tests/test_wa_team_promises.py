"""T3 promise extractor tests — no real DB (spec P1 bullet 4).

Covers: tense split en/id/it (guilt: a past-tense line is NOT a promise;
innocence: a future promise IS one), watermark idempotency, the D6 due_at
default, and a payload test that fails if a body window or a name reaches
the digest line.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from scripts.wa_team_promises import (
    DEFAULT_DUE_AT_HOURS,
    ExtractMetrics,
    _digest_line,
    _load_watermark,
    _save_watermark,
    _thread_key,
    find_candidates_in_message,
)
import scripts.wa_team_promises as wa_team_promises

BASE = _dt.datetime(2026, 9, 25, 10, 0, tzinfo=_dt.timezone.utc)


def _scan(body: str, base: _dt.datetime = BASE):
    return find_candidates_in_message(
        message_id=1, client_id=42, team_member_phone="628110000000",
        team_member_email="adit@balizero.com", chat_jid="628299999999@s.whatsapp.net",
        counterpart_phone=None, counterpart_lid=None, body=body, base_dt=base,
    )


# ---------------------------------------------------------------------------
# Tense split — guilt (past tense is NOT a promise) / innocence (future IS)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "akan saya kirim dokumennya besok pagi",       # ID future
    "I will send the documents tomorrow",          # EN future
    "invierò i documenti domani",                  # IT future
])
def test_innocence_future_tense_is_a_promise(body):
    candidates, fulfilments = _scan(body)
    assert len(candidates) == 1
    assert candidates[0].promise_type == "send"
    assert fulfilments == 0


@pytest.mark.parametrize("body", [
    "sudah saya kirim dokumennya tadi pagi",        # ID past
    "I have already sent the documents",            # EN past
    "già inviato tutto stamattina",                 # IT past
])
def test_guilt_past_tense_is_not_a_promise(body):
    candidates, fulfilments = _scan(body)
    assert candidates == []
    assert fulfilments == 1


def test_guilt_past_tense_does_not_leak_into_other_types_same_message():
    """A message with a past-tense 'send' and a future 'check' yields ONE
    promise (check), not two, and the past one is counted as fulfilment."""
    candidates, fulfilments = _scan(
        "sudah saya kirim invoice-nya, akan saya cek juga statusnya besok"
    )
    assert [c.promise_type for c in candidates] == ["check"]
    assert fulfilments == 1


# ---------------------------------------------------------------------------
# due_at: cue vs D6 default (+48h)
# ---------------------------------------------------------------------------

def test_due_at_uses_temporal_cue_when_present():
    candidates, _ = _scan("akan saya kirim besok")  # "besok" = tomorrow = +24h
    assert candidates[0].from_cue is True
    assert candidates[0].due_at == BASE + _dt.timedelta(hours=24)


def test_due_at_falls_back_to_d6_default_without_a_cue():
    candidates, _ = _scan("I will check this for you")
    assert candidates[0].from_cue is False
    assert candidates[0].due_at == BASE + _dt.timedelta(hours=DEFAULT_DUE_AT_HOURS)


# ---------------------------------------------------------------------------
# thread_key
# ---------------------------------------------------------------------------

def test_thread_key_prefers_chat_jid_then_counterpart_phone_then_lid():
    via_jid = _thread_key("6281", "jid@x", "6282", "lid@x")
    via_phone = _thread_key("6281", None, "6282", "lid@x")
    via_lid = _thread_key("6281", None, None, "lid@x")
    assert via_jid != via_phone != via_lid
    assert _thread_key(None, "jid@x", None, None) is None


# ---------------------------------------------------------------------------
# Watermark idempotency
# ---------------------------------------------------------------------------

def test_watermark_round_trip_and_idempotent_reload(tmp_path, monkeypatch):
    wm_file = tmp_path / "wa_team_promises_last_id.txt"
    monkeypatch.setattr(wa_team_promises, "WATERMARK_FILE", wm_file)
    assert _load_watermark() is None  # unseeded

    _save_watermark(1000)
    assert _load_watermark() == 1000

    # Re-saving the same value twice must not corrupt / duplicate the file.
    _save_watermark(1000)
    assert _load_watermark() == 1000
    assert wm_file.read_text().strip() == "1000"


# ---------------------------------------------------------------------------
# Payload test — the digest line must never carry a body window or a name
# ---------------------------------------------------------------------------

def test_digest_line_never_carries_a_body_window_or_a_name():
    secret_client_name = "Ida Ayu Ratih Purnamasari"
    body = f"akan saya kirim paspor {secret_client_name} besok ke kantor imigrasi"
    candidates, _ = _scan(body)
    assert candidates  # sanity: the fixture actually produced a promise
    assert secret_client_name in candidates[0].promise_text  # stored locally — OK

    metrics = ExtractMetrics(
        promises_created=3, open_total=7, overdue_total=2,
        by_type={"send": 3},
    )
    line = _digest_line(metrics)

    assert line == "promises: new 3 open 7 overdue 2"
    assert secret_client_name not in line
    assert body not in line
    assert candidates[0].promise_text not in line
    # Structural guarantee, not just this fixture: the function's only inputs
    # are the three int fields, so no candidate/body text can ever reach it.
    assert set(line.replace("promises: new ", "").replace(
        " open ", " ").replace(" overdue ", " ").split()) <= {"3", "7", "2"}
