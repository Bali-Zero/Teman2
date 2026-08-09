"""wa-attention: a persistent condition is news ONCE, then it is a reminder.

Zero's ruling, 2026-08-08, on a measurement of the live spool: over 32 days the
organism delivered 390 immediate (P0) Telegram alerts — 12.2/day against a
12/day budget, i.e. saturated every single day — and `wa-attention` was **165
of them, 42.3%**, for NINE recurring conditions re-raised about every 11 hours.
Those repeats were not extra news. Because the budget is a race rather than a
triage, they were pushing other sources' genuine P0s into the digest.

The rule now: first entry into HIGH → p0 · condition persists → digest · a NEW
critical reason → p0 again.

The load-bearing test in here is `test_reasons_improving_does_not_fire_a_p0`.
The old state key was `f"{phone}:{sorted(critical)[0]}"`, so a contact whose
reasons went from ["audit","deadline"] to ["deadline"] changed key, read as a
brand-new contact, and would have bought a P0 — **an alert fired by things
getting better**. Keying the episode on the phone alone is what closes that,
and without this test the obvious phone+reason implementation looks correct.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "wa-mirror-attention-telegram.py"


@pytest.fixture(scope="module")
def wa(tmp_path_factory):
    """Import the hyphenated script by path, in a throwaway world (W96).

    Same shape as test_wa_attention_pii_envelope.py: the module does real work
    at import (reads ~/.wa-mirror.env, mkdirs ~/.cache), and the state file it
    would touch is the LIVE alert ledger.
    """
    home = tmp_path_factory.mktemp("home")
    prev = {k: os.environ.get(k) for k in ("HOME", "WA_MIRROR_DATABASE_URL")}
    os.environ["HOME"] = str(home)
    os.environ["WA_MIRROR_DATABASE_URL"] = "postgresql://test/none"
    try:
        spec = importlib.util.spec_from_file_location("wa_attention_tier", SRC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wa_attention_tier"] = mod
        try:
            spec.loader.exec_module(mod)
        except ImportError as exc:  # asyncpg absent on a bare runner
            pytest.skip(f"dependency missing: {exc}")
        assert Path(mod.STATE_PATH).is_relative_to(home), (
            f"the import escaped the throwaway HOME: {mod.STATE_PATH}")
        yield mod
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(autouse=True)
def clean_state(wa):
    """Every test starts with no episode history."""
    Path(wa.STATE_PATH).unlink(missing_ok=True)
    yield
    Path(wa.STATE_PATH).unlink(missing_ok=True)


def _item(phone: str, reasons: list[str], n_high: int = 2, crm_id: int | None = 7):
    return {
        "phone": phone,
        "reasons": reasons,
        "n_high": n_high,
        "crm_id": crm_id,
        "crm_name": "Test Contact" if crm_id else None,
    }


class _FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquire()

    async def close(self):
        return None


def _run(wa, monkeypatch, items, force=False):
    """Run one scan; return the list of (tier, dedup_key, text) sent."""
    sent: list[tuple[str, str, str]] = []

    async def fake_create_pool(*_a, **_k):
        return _FakePool()

    async def fake_fetch(_conn):
        return items

    def fake_send(text, tier="p0", dedup_key=""):
        sent.append((tier, dedup_key, text))
        return True

    monkeypatch.setattr(wa.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(wa, "fetch_high_unresolved", fake_fetch)
    monkeypatch.setattr(wa, "send_telegram", fake_send)
    asyncio.run(wa.cmd_realtime(force=force))
    return sent


def _age_state(wa, hours: float):
    """Push every stored episode timestamp into the past."""
    state = json.loads(Path(wa.STATE_PATH).read_text())
    past = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    for ep in state.get("episodes", {}).values():
        ep["ts"] = past
    Path(wa.STATE_PATH).write_text(json.dumps(state))


# --------------------------------------------------------------------- guilt


def test_first_entry_into_high_is_a_p0(wa, monkeypatch):
    sent = _run(wa, monkeypatch, [_item("6281000000001", ["deadline"])])
    assert [t for t, _, _ in sent] == ["p0"], sent


def test_the_same_condition_a_second_time_is_a_digest_not_a_p0(wa, monkeypatch):
    """THE defect: 165 of 390 delivered P0s in 32 days were this repeat."""
    items = [_item("6281000000001", ["deadline"])]
    _run(wa, monkeypatch, items)
    _age_state(wa, hours=12)
    sent = _run(wa, monkeypatch, items)
    assert [t for t, _, _ in sent] == ["digest"], sent


def test_a_repeat_inside_the_window_sends_nothing_at_all(wa, monkeypatch):
    """The scan runs every 10 minutes. Without this, a persisting contact would
    write 144 spool records a day — the digest collapses to one LINE, but the
    spool would still carry every event."""
    items = [_item("6281000000001", ["deadline"])]
    _run(wa, monkeypatch, items)
    sent = _run(wa, monkeypatch, items)  # no ageing: still inside DEDUP_WINDOW
    assert sent == [], sent


def test_a_new_critical_reason_earns_a_fresh_p0(wa, monkeypatch):
    """Genuinely worse, not merely still true."""
    _run(wa, monkeypatch, [_item("6281000000001", ["deadline"])])
    sent = _run(wa, monkeypatch, [_item("6281000000001", ["deadline", "lawyer"])])
    assert [t for t, _, _ in sent] == ["p0"], sent


def test_a_resolved_contact_who_returns_is_a_fresh_p0(wa, monkeypatch):
    """Episode END is what makes 'first entry' mean first entry, not first
    ever. Without pruning, a real new problem would be filed as 'already told
    you' forever."""
    items = [_item("6281000000001", ["deadline"])]
    _run(wa, monkeypatch, items)
    _run(wa, monkeypatch, [])  # resolved: leaves the HIGH-unresolved set
    sent = _run(wa, monkeypatch, items)  # comes back
    assert [t for t, _, _ in sent] == ["p0"], sent


# ----------------------------------------------------------------- innocence


def test_reasons_improving_does_not_fire_a_p0(wa, monkeypatch):
    """The case the obvious implementation gets wrong.

    Old key was `phone:sorted(critical)[0]`. Going from ["audit","deadline"] to
    ["deadline"] changes that key, so the contact reads as brand new and buys a
    P0 — an alert fired BY THINGS GETTING BETTER. Episodes key on phone alone.
    """
    _run(wa, monkeypatch, [_item("6281000000001", ["audit", "deadline"])])
    _age_state(wa, hours=12)
    sent = _run(wa, monkeypatch, [_item("6281000000001", ["deadline"])])
    assert [t for t, _, _ in sent] == ["digest"], (
        f"an improvement was announced as new news: {sent}")


def test_migration_from_the_legacy_state_does_not_fire_a_burst(wa, monkeypatch):
    """First run after deploy reads ~9 live contacts. If the old `last_alerted`
    shape were ignored, every one would look like a first entry and fire the
    exact P0 burst this change exists to end."""
    Path(wa.STATE_PATH).write_text(json.dumps({
        "last_alerted": {
            "6281000000001:deadline": datetime.now(timezone.utc).isoformat(),
            "6281000000002:refund": datetime.now(timezone.utc).isoformat(),
        }
    }))
    sent = _run(wa, monkeypatch, [
        _item("6281000000001", ["deadline"]),
        _item("6281000000002", ["refund"]),
    ])
    assert [t for t, _, _ in sent] != ["p0"], f"legacy state fired a P0 burst: {sent}"


def test_a_genuinely_new_contact_still_cuts_through(wa, monkeypatch):
    """The whole point is not silence. A contact nobody has heard of must still
    reach the phone immediately, even while others are merely persisting."""
    _run(wa, monkeypatch, [_item("6281000000001", ["deadline"])])
    _age_state(wa, hours=12)
    sent = _run(wa, monkeypatch, [
        _item("6281000000001", ["deadline"]),          # persisting
        _item("6281000000002", ["refund"], crm_id=None),  # brand new lead
    ])
    tiers = sorted(t for t, _, _ in sent)
    assert tiers == ["digest", "p0"], f"expected one of each tier, got {sent}"


def test_force_still_surfaces_a_persisting_contact(wa, monkeypatch):
    items = [_item("6281000000001", ["deadline"])]
    _run(wa, monkeypatch, items)
    sent = _run(wa, monkeypatch, items, force=True)
    assert [t for t, _, _ in sent] == ["digest"], sent


def test_a_contact_with_no_critical_reason_is_never_alerted(wa, monkeypatch):
    sent = _run(wa, monkeypatch, [_item("6281000000001", ["greeting"])])
    assert sent == [], sent


# ------------------------------------------------------------------ envelope


def test_the_reminder_does_not_wear_the_alarm_banner(wa, monkeypatch):
    """A '🚨 HIGH attention' banner on the fourth reminder of the same contact
    is how a reader learns to stop reading the banner."""
    items = [_item("6281000000001", ["deadline"])]
    _run(wa, monkeypatch, items)
    _age_state(wa, hours=12)
    sent = _run(wa, monkeypatch, items)
    text = sent[0][2]
    assert "still unresolved" in text, text
    assert "🚨" not in text, f"the reminder is dressed as an alarm: {text}"


def test_the_reminder_keeps_the_pii_envelope(wa, monkeypatch):
    """The new digest path is a new rendering site, and the last defect in this
    file was a rendering site that printed a number in the clear."""
    items = [_item("6281000000001", ["deadline"], crm_id=None)]
    _run(wa, monkeypatch, items)
    _age_state(wa, hours=12)
    sent = _run(wa, monkeypatch, items)
    text = sent[0][2]
    assert "6281000000001" not in text, f"full number in the reminder: {text}"
    assert "****" in text, text


def test_the_two_tiers_never_share_a_dedup_key(wa, monkeypatch):
    """Same contact set, two tiers: colliding keys would make the gateway
    swallow the second as a duplicate of the first."""
    _run(wa, monkeypatch, [_item("6281000000001", ["deadline"])])
    _age_state(wa, hours=12)
    sent = _run(wa, monkeypatch, [
        _item("6281000000001", ["deadline"]),
        _item("6281000000002", ["refund"]),
    ])
    keys = [k for _, k, _ in sent]
    assert len(keys) == len(set(keys)), keys
    assert all(k.startswith("wa-attention:") for k in keys), keys
