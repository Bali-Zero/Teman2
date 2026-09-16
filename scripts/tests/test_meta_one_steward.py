"""Unit tests for scripts/meta_one_steward.py.

Loaded via importlib (repo-root scripts/, same convention as
test_wr2_ig_metrics_scraper.py). Sealed to tmp_path — no real HOME, no
network (the HTTP `fetch` seam is always injected), TG_DRY_RUN=1 (set by the
autouse fixture in conftest.py). Covers spec §4.3/4.4 in
docs/marketing/meta-one-advanced-playbook.md: quota math + month rollover,
`use` idempotency, token classification guilt/innocence, the expiring-quota
rule at day-5, digest PII/secret hygiene, and heartbeat-status == run-verdict
on the ok/warning/error paths.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mos = _load("meta_one_steward")


def _isolate(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    last_seen_dir = tmp_path / "last_seen"
    queue_json = tmp_path / "queue.json"
    # Real Pro queue schema (verified live 2026-09-16): top-level LIST of
    # items with `state`, `instagram_published_at`, `instagram_post_url`,
    # `ig_media_id`, `engagement_metrics`, `topic_slug`, `id` — no
    # top-level "items" wrapper, and no `published_at` key at all.
    queue_json.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setenv("META_ONE_STATE_DIR", str(state_dir))
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(last_seen_dir))
    monkeypatch.setenv("META_ONE_QUEUE_JSON", str(queue_json))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("IG_LONG_LIVED_TOKEN", raising=False)
    return state_dir, last_seen_dir, queue_json


def _noop_notify(tier, dedup_key, text):
    return True


# ── quota constants + benefit math ──────────────────────────────────────


def test_advanced_quotas_match_help_centre_table():
    assert mos.ADVANCED_QUOTAS == {
        "ig_post_link": 4,
        "ig_reel_link": 4,
        "fb_post_link": 8,
        "fb_reel_link": 8,
        "support_chat": 1,
        "content_credit": 2,
    }


def test_build_benefits_defaults_zero_used():
    benefits = mos.build_benefits({})
    assert benefits["ig_post_link"] == {"used": 0, "quota": 4}
    assert benefits["support_chat"] == {"used": 0, "quota": 1}


# ── month rollover ───────────────────────────────────────────────────────


def test_read_usage_is_scoped_to_its_own_month(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    mos.cmd_use("ig_post_link", "WR2-000001", now=datetime(2026, 9, 15, tzinfo=timezone.utc))
    mos.cmd_use("ig_post_link", "WR2-000002", now=datetime(2026, 10, 1, tzinfo=timezone.utc))

    sept = mos.read_usage("2026-09")
    octo = mos.read_usage("2026-10")
    assert sept["ig_post_link"] == 1
    assert octo["ig_post_link"] == 1


# ── `use` idempotency ────────────────────────────────────────────────────


def test_use_is_idempotent_on_month_benefit_ref(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    rc1 = mos.cmd_use("ig_reel_link", "WR2-000042", now=now)
    rc2 = mos.cmd_use("ig_reel_link", "WR2-000042", now=now)
    assert rc1 == 0
    assert rc2 == 0
    lines = mos.usage_path().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_use_rejects_unknown_benefit(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rc = mos.cmd_use("carrier_pigeon", "WR2-000001")
    assert rc == 2


# ── token classification: guilt + innocence ─────────────────────────────


def test_probe_token_dead_on_400_oauthexception():
    def fetch(url, timeout):
        return 400, json.dumps({"error": {"type": "OAuthException", "message": "expired"}})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "dead"


def test_probe_token_dead_on_401_oauthexception():
    def fetch(url, timeout):
        return 401, json.dumps({"error": {"type": "OAuthException", "message": "bad token"}})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "dead"


def test_probe_token_alive_on_200_with_username():
    def fetch(url, timeout):
        return 200, json.dumps({"id": "17841400000000000", "username": "balizero0"})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "alive"
    assert details["username"] == "balizero0"


def test_probe_token_unknown_on_network_error_never_dead():
    def fetch(url, timeout):
        raise TimeoutError("timed out")

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "unknown"
    assert state != "dead"


def test_probe_token_unknown_on_no_token_never_dead():
    state, details = mos.probe_token(None)
    assert state == "unknown"


def test_probe_token_unknown_on_unexpected_status_never_dead():
    def fetch(url, timeout):
        return 500, "internal server error"

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "unknown"


def test_probe_token_dead_even_when_oauthexception_is_past_the_truncation_window():
    """Codex finding #2 (false negative): classification parses the FULL
    body; only the STORED diagnostic copy is truncated to 500 chars. A
    verbose error.message padding the body past 500 chars must not hide the
    error.type that proves guilt."""
    padding = "x" * 600

    def fetch(url, timeout):
        return 400, json.dumps({"error": {"type": "OAuthException", "message": f"expired {padding}"}})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "dead"


def test_probe_token_unknown_when_message_merely_mentions_oauthexception():
    """Codex finding #2 (false positive): classification checks
    error.type, never a substring match against the body text — a
    different error.type whose free-text message happens to mention
    "OAuthException" must NOT be misread as guilt."""

    def fetch(url, timeout):
        return 400, json.dumps({"error": {"type": "OtherError", "message": "see OAuthException docs"}})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "unknown"


def test_probe_token_dead_on_error_code_190_even_without_type_field():
    def fetch(url, timeout):
        return 401, json.dumps({"error": {"code": 190, "message": "token expired"}})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "dead"


def test_probe_token_unknown_on_500_even_with_oauthexception_in_body():
    """Excluded suspect, kept as a regression guard: 5xx never classifies,
    regardless of what the body says."""

    def fetch(url, timeout):
        return 500, json.dumps({"error": {"type": "OAuthException", "message": "boom"}})

    state, details = mos.probe_token("fake-token", fetch=fetch)
    assert state == "unknown"


# ── expiring-quota rule ──────────────────────────────────────────────────


def test_days_to_month_end_five_days_out():
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)  # Sept has 30 days
    assert mos.days_to_month_end(now) == 5


def test_quota_expiring_fires_at_day_minus_5_with_one_of_four_used():
    benefits = mos.build_benefits({"ig_post_link": 1})
    assert mos.quota_expiring(benefits, days_left=5) is True


def test_quota_expiring_silent_at_three_of_four_used():
    # ALL four link benefits at/above 50% usage — none crosses the threshold.
    benefits = mos.build_benefits({
        "ig_post_link": 3, "ig_reel_link": 3, "fb_post_link": 5, "fb_reel_link": 5,
    })
    assert mos.quota_expiring(benefits, days_left=5) is False


def test_quota_expiring_silent_when_far_from_month_end():
    benefits = mos.build_benefits({"ig_post_link": 1})
    assert mos.quota_expiring(benefits, days_left=6) is False


# ── queue reader: real Pro schema (instagram_published_at, not published_at) ──


def test_read_queue_counts_uses_instagram_published_at_field(tmp_path, monkeypatch):
    _, _, queue_json = _isolate(tmp_path, monkeypatch)
    # Only the REAL key is present — no `published_at` at all. Before the
    # fix, `item.get("published_at")` alone would have silently read None
    # here, even though the item was in fact published.
    queue_json.write_text(json.dumps([
        {"id": "WR2-000001", "state": "published", "instagram_published_at": "2026-09-14T10:00:00Z"},
        {"id": "WR2-000002", "state": "drafted"},
    ]), encoding="utf-8")
    counts = mos.read_queue_counts()
    assert counts["published"] == 1
    assert counts["drafted"] == 1
    assert counts["last_published_at"] == "2026-09-14T10:00:00Z"
    assert counts["last_published_at"] is not None


def test_read_queue_counts_picks_the_newest_instagram_published_at(tmp_path, monkeypatch):
    _, _, queue_json = _isolate(tmp_path, monkeypatch)
    queue_json.write_text(json.dumps([
        {"id": "WR2-000001", "state": "published", "instagram_published_at": "2026-09-10T10:00:00Z"},
        {"id": "WR2-000002", "state": "published", "instagram_published_at": "2026-09-15T10:00:00Z"},
    ]), encoding="utf-8")
    counts = mos.read_queue_counts()
    assert counts["published"] == 2
    assert counts["last_published_at"] == "2026-09-15T10:00:00Z"


def test_read_queue_counts_falls_back_to_legacy_published_at(tmp_path, monkeypatch):
    _, _, queue_json = _isolate(tmp_path, monkeypatch)
    queue_json.write_text(json.dumps([
        {"id": "WR2-000001", "state": "published", "published_at": "2026-09-11T10:00:00Z"},
    ]), encoding="utf-8")
    counts = mos.read_queue_counts()
    assert counts["last_published_at"] == "2026-09-11T10:00:00Z"


# ── _tg_notify reads the gateway VERDICT, not the subprocess returncode ──


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def test_tg_notify_p0_spooled_is_not_delivered(monkeypatch):
    """tg_notify.py's own contract is 'never fails the caller, exit 0' even
    when a P0 could only be spooled (budget exhausted, token missing, relay
    down). A caller that reads returncode==0 alone cannot tell that apart
    from a real-time send — this is the exact 'blind caller' shape being
    fixed: `_tg_notify` must read the verdict and report False here."""
    monkeypatch.setattr(
        mos.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, "tg_notify: p0_unsent_spooled\n"),
    )
    assert mos._tg_notify("p0", "some-key", "text") is False


def test_tg_notify_p0_sent_is_delivered(monkeypatch):
    monkeypatch.setattr(
        mos.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, "tg_notify: sent\n"),
    )
    assert mos._tg_notify("p0", "some-key", "text") is True


def test_tg_notify_digest_spooled_counts_as_delivered(monkeypatch):
    """Spooled IS the digest tier's normal, expected outcome (it is flushed
    later in a batch by tg_digest_flush.py) — unlike p0, this must count as
    delivered, or every digest tick would misreport as undelivered."""
    monkeypatch.setattr(
        mos.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, "tg_notify: spooled\n"),
    )
    assert mos._tg_notify("digest", "some-key", "text") is True


def test_tg_notify_digest_deduped_counts_as_delivered(monkeypatch):
    monkeypatch.setattr(
        mos.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, "tg_notify: deduped\n"),
    )
    assert mos._tg_notify("digest", "some-key", "text") is True


def test_tg_notify_missing_verdict_line_is_not_delivered(monkeypatch):
    """returncode==0 with no canonical verdict line at all (malformed/older
    gateway) must be treated as unknown, never as a silent success."""
    monkeypatch.setattr(
        mos.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(0, "some unrelated stderr noise\n"),
    )
    assert mos._tg_notify("p0", "some-key", "text") is False


def test_tick_surfaces_an_undelivered_p0_as_warning_not_success(tmp_path, monkeypatch):
    """End-to-end: a dead token fires a P0 that only spools (gateway down);
    the tick must record that fact in the ledger entry (p0_undelivered) and
    the run's own verdict must stay 'warning' — the blind old code silently
    read the spool as a successful notification and moved on."""
    _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    def half_blind_notify(tier, dedup_key, text):
        return tier != "p0"  # every p0 "spools" (False); digest still "delivers"

    result = mos.tick(now=_FAR_FROM_MONTH_END, probe_fn=dead_probe, tg_notify_fn=half_blind_notify)
    assert result["entry"]["p0_undelivered"] is True
    assert result["verdict"] == "warning"


def test_tick_records_p0_undelivered_false_when_notified_cleanly(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    result = mos.tick(now=_FAR_FROM_MONTH_END, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    assert result["entry"]["p0_undelivered"] is False


# ── digest hygiene: no secret, no stray @-handles ────────────────────────


def test_p0_token_dead_text_defaults_when_dead_since_is_none():
    text = mos._p0_token_dead_text(None)
    assert "data sconosciuta" in text
    assert "None" not in text


def test_p0_token_dead_text_uses_the_real_date():
    text = mos._p0_token_dead_text("2026-09-15")
    assert "2026-09-15" in text


def test_digest_never_contains_token_or_at_handles(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    entry = {
        "benefits": mos.build_benefits({"ig_post_link": 1}),
        "days_to_month_end": 5,
        "token_state": "alive",
        "token_dead_since": None,
        "followers_count": 1234,
        "export_age_days": 2.5,
        "queue": {"drafted": 3, "published": 1, "last_published_at": "2026-09-14T10:00:00Z"},
        "updated_at": "2026-09-15T06:20:00Z",
    }
    text = mos._digest_text(entry)
    assert "@" not in text
    assert "access_token" not in text
    assert "EAAG" not in text  # common Meta token prefix — must never leak


# ── heartbeat status == run verdict, on every path ───────────────────────

# Fixed instant, day 15, far from ANY month-end in either UTC or WITA — the
# real wall clock must never be able to flip an "ok" test to "warning" just
# because it happened to run near a month boundary (the exact brittleness
# Codex's finding #8 reproduced against test_heartbeat_matches_ok_verdict at
# real-world 2026-09-28).
_FAR_FROM_MONTH_END = datetime(2026, 6, 15, 6, 20, tzinfo=timezone.utc)


def test_heartbeat_matches_ok_verdict(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def alive_probe(token, **kw):
        return "alive", {"username": "balizero0", "id": "1"}

    rc = mos.cmd_tick(now=_FAR_FROM_MONTH_END, probe_fn=alive_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "ok"


def test_heartbeat_matches_warning_verdict_on_dead_token(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    rc = mos.cmd_tick(now=_FAR_FROM_MONTH_END, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "warning"


def test_heartbeat_matches_warning_verdict_on_unknown_token(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def unknown_probe(token, **kw):
        return "unknown", {"reason": "timeout"}

    rc = mos.cmd_tick(now=_FAR_FROM_MONTH_END, probe_fn=unknown_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "warning"


def test_heartbeat_matches_error_verdict_on_exception(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def raising_probe(token, **kw):
        raise RuntimeError("boom")

    rc = mos.cmd_tick(now=_FAR_FROM_MONTH_END, probe_fn=raising_probe, tg_notify_fn=_noop_notify)
    assert rc == 1
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "error"


def test_heartbeat_matches_warning_at_the_month_end_boundary_even_when_alive(tmp_path, monkeypatch):
    """Explicit boundary case (Codex finding #8): 5 days out, alive, empty
    usage is LEGITIMATELY 'warning' (a link benefit is <50% used with the
    window open) — this must be asserted on purpose, not stumbled into by
    an untested real clock."""
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)
    near_month_end = datetime(2026, 9, 25, 6, 20, tzinfo=timezone.utc)  # 5 days left in Sept (WITA)

    def alive_probe(token, **kw):
        return "alive", {"username": "balizero0", "id": "1"}

    rc = mos.cmd_tick(now=near_month_end, probe_fn=alive_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "warning"


def test_heartbeat_write_failure_is_reported_not_swallowed(tmp_path, monkeypatch):
    """Codex finding #4: organism_heartbeat() never raises — it reports
    failure by returning False. cmd_tick must check that return value
    instead of assuming a call that didn't raise succeeded."""
    _isolate(tmp_path, monkeypatch)

    def alive_probe(token, **kw):
        return "alive", {"username": "balizero0", "id": "1"}

    monkeypatch.setattr(mos, "organism_heartbeat", lambda *a, **kw: False)
    rc = mos.cmd_tick(now=_FAR_FROM_MONTH_END, probe_fn=alive_probe, tg_notify_fn=_noop_notify)
    assert rc == 1


def test_token_dead_since_persists_first_observed_date(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    now1 = datetime(2026, 9, 15, 6, 20, tzinfo=timezone.utc)
    now2 = datetime(2026, 9, 16, 6, 20, tzinfo=timezone.utc)
    r1 = mos.tick(now=now1, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    r2 = mos.tick(now=now2, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    assert r1["entry"]["token_dead_since"] == "2026-09-15"
    assert r2["entry"]["token_dead_since"] == "2026-09-15"


def test_token_dead_since_survives_an_unknown_response_in_between(tmp_path, monkeypatch):
    """Codex finding #6: dead(15th) -> unknown(16th) -> dead(17th) must keep
    reporting the 15th throughout — 'unknown' is not evidence of anything
    (the classifier's own contract) so it must neither erase a previously
    observed dead date nor manufacture a fresh one."""
    _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    def unknown_probe(token, **kw):
        return "unknown", {"reason": "timeout"}

    d15 = datetime(2026, 9, 15, 6, 20, tzinfo=timezone.utc)
    d16 = datetime(2026, 9, 16, 6, 20, tzinfo=timezone.utc)
    d17 = datetime(2026, 9, 17, 6, 20, tzinfo=timezone.utc)
    r1 = mos.tick(now=d15, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    r2 = mos.tick(now=d16, probe_fn=unknown_probe, tg_notify_fn=_noop_notify)
    r3 = mos.tick(now=d17, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    assert r1["entry"]["token_dead_since"] == "2026-09-15"
    assert r2["entry"]["token_dead_since"] == "2026-09-15"
    assert r3["entry"]["token_dead_since"] == "2026-09-15"


def test_token_dead_since_survives_a_month_rollover(tmp_path, monkeypatch):
    """Codex finding #6: the month-keyed ledger entry is a fresh dict every
    month — token_dead_since must NOT live only inside it, or a token that
    has been dead since September silently reports as 'just died today' on
    the first October tick."""
    _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    sept = datetime(2026, 9, 28, 6, 20, tzinfo=timezone.utc)
    octo = datetime(2026, 10, 2, 6, 20, tzinfo=timezone.utc)
    r1 = mos.tick(now=sept, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    r2 = mos.tick(now=octo, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    assert r1["entry"]["token_dead_since"] == "2026-09-28"
    assert r2["entry"]["token_dead_since"] == "2026-09-28"


def test_token_dead_since_clears_only_on_confirmed_alive(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    def alive_probe(token, **kw):
        return "alive", {"username": "balizero0", "id": "1"}

    d15 = datetime(2026, 9, 15, 6, 20, tzinfo=timezone.utc)
    d16 = datetime(2026, 9, 16, 6, 20, tzinfo=timezone.utc)
    mos.tick(now=d15, probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    r2 = mos.tick(now=d16, probe_fn=alive_probe, tg_notify_fn=_noop_notify)
    assert r2["entry"]["token_dead_since"] is None


# ── WITA calendar (Codex finding #3) ──────────────────────────────────────


def test_month_key_and_days_to_month_end_use_wita_not_utc():
    # 2026-09-30T22:30:00Z == 2026-10-01T06:30:00+08:00 (Asia/Makassar) — a
    # UTC-naive bucketing would call this September with 0 days left and
    # could fire a quota-expiring P0 for a month that (in WITA) already ended.
    instant = datetime(2026, 9, 30, 22, 30, 0, tzinfo=timezone.utc)
    assert mos._month_key(instant) == "2026-10"
    assert mos.days_to_month_end(instant) == 30  # Oct 1 -> Oct 31 inclusive-start


def test_use_attributes_to_the_wita_month_across_midnight_utc(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    # 2026-09-30T23:00:00Z is already 2026-10-01 07:00 WITA.
    instant = datetime(2026, 9, 30, 23, 0, 0, tzinfo=timezone.utc)
    mos.cmd_use("ig_post_link", "WR2-000099", now=instant)
    assert mos.read_usage("2026-10")["ig_post_link"] == 1
    assert mos.read_usage("2026-09")["ig_post_link"] == 0


# ── --selftest ────────────────────────────────────────────────────────────


def test_selftest_exits_zero_and_names_both_verdicts(capsys):
    rc = mos.selftest()
    out = capsys.readouterr().out
    assert rc == 0
    assert "token_state=dead verdict=warning" in out
    assert "token_state=alive verdict=ok" in out


# ── anti-token-leak fault injection (Codex findings #1 / #9) ─────────────


def test_synthetic_token_never_leaks_through_an_exception_path(tmp_path, monkeypatch, capsys):
    """A raw token VALUE embedded in an exception message (no `access_token=`
    prefix — e.g. a library that reformats the request URL) must be scrubbed
    from every diagnostic surface: stderr, the heartbeat note-on-disk, and
    the text handed to the Telegram notifier."""
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)
    synthetic_token = "SYNTHTOKEN123"
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", synthetic_token)

    notified_texts: list[str] = []

    def capturing_notify(tier, dedup_key, text):
        notified_texts.append(text)
        return True

    def leaking_probe(token, **kw):
        # No "access_token=" anywhere — just the bare value, the shape the
        # old regex-only redactor could not catch.
        raise RuntimeError(f"connection reset while calling graph API with token {synthetic_token}")

    rc = mos.cmd_tick(now=_FAR_FROM_MONTH_END, probe_fn=leaking_probe, tg_notify_fn=capturing_notify)
    assert rc == 1

    captured = capsys.readouterr()
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))

    assert synthetic_token not in captured.err
    assert synthetic_token not in captured.out
    assert synthetic_token not in json.dumps(hb)
    assert all(synthetic_token not in t for t in notified_texts)


def test_redact_scrubs_a_bare_token_value_with_no_access_token_prefix(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "SYNTHTOKEN123")
    text = mos._redact("error: token SYNTHTOKEN123 rejected")
    assert "SYNTHTOKEN123" not in text
    assert "REDACTED" in text


# ── `use` interprocess lock (Codex finding #7, optional) ─────────────────


def test_use_lock_survives_concurrent_callers_without_duplicate_lines(tmp_path, monkeypatch):
    import threading

    _isolate(tmp_path, monkeypatch)
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)
    barrier = threading.Barrier(5)

    def worker():
        barrier.wait()
        mos.cmd_use("ig_post_link", "WR2-RACE", now=now)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = mos.usage_path().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
