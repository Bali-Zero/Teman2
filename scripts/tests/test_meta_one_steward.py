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


def test_heartbeat_matches_ok_verdict(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def alive_probe(token, **kw):
        return "alive", {"username": "balizero0", "id": "1"}

    rc = mos.cmd_tick(probe_fn=alive_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "ok"


def test_heartbeat_matches_warning_verdict_on_dead_token(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def dead_probe(token, **kw):
        return "dead", {"http_status": 400}

    rc = mos.cmd_tick(probe_fn=dead_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "warning"


def test_heartbeat_matches_warning_verdict_on_unknown_token(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def unknown_probe(token, **kw):
        return "unknown", {"reason": "timeout"}

    rc = mos.cmd_tick(probe_fn=unknown_probe, tg_notify_fn=_noop_notify)
    assert rc == 0
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "warning"


def test_heartbeat_matches_error_verdict_on_exception(tmp_path, monkeypatch):
    _, last_seen_dir, _ = _isolate(tmp_path, monkeypatch)

    def raising_probe(token, **kw):
        raise RuntimeError("boom")

    rc = mos.cmd_tick(probe_fn=raising_probe, tg_notify_fn=_noop_notify)
    assert rc == 1
    hb = json.loads((last_seen_dir / f"{mos.ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "error"


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


# ── --selftest ────────────────────────────────────────────────────────────


def test_selftest_exits_zero_and_names_both_verdicts(capsys):
    rc = mos.selftest()
    out = capsys.readouterr().out
    assert rc == 0
    assert "dead" in out
    assert ("alive" in out) or ("ok" in out)
