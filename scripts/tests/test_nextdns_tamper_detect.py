from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nextdns_tamper_detect import (  # noqa: E402
    find_silent_devices,
    count_blocked_attempts,
    build_digest,
)

NOW = datetime(2026, 5, 31, 8, 0, tzinfo=timezone.utc)


def test_device_silent_beyond_threshold_is_flagged():
    enrolled = ["surya-mac", "adit-win"]
    last_seen = {
        "adit-win": NOW - timedelta(hours=2),
        "surya-mac": NOW - timedelta(days=5),
    }
    silent = find_silent_devices(enrolled, last_seen, now=NOW, threshold_days=3)
    assert silent == ["surya-mac"]


def test_device_never_seen_is_flagged():
    enrolled = ["surya-mac", "adit-win"]
    last_seen = {"adit-win": NOW - timedelta(hours=1)}  # surya never reported
    silent = find_silent_devices(enrolled, last_seen, now=NOW, threshold_days=3)
    assert silent == ["surya-mac"]


def test_all_reporting_returns_empty():
    enrolled = ["surya-mac", "adit-win"]
    last_seen = {
        "surya-mac": NOW - timedelta(hours=1),
        "adit-win": NOW - timedelta(hours=1),
    }
    assert find_silent_devices(enrolled, last_seen, now=NOW, threshold_days=3) == []


def test_count_blocked_attempts_groups_by_device():
    logs = [
        {"device": {"name": "surya-mac"}, "domain": "web.whatsapp.com", "status": "blocked"},
        {"device": {"name": "surya-mac"}, "domain": "web.whatsapp.com", "status": "blocked"},
        {"device": {"name": "adit-win"}, "domain": "web.telegram.org", "status": "blocked"},
        {"device": {"name": "surya-mac"}, "domain": "google.com", "status": "default"},
    ]
    counts = count_blocked_attempts(
        logs, denylist={"web.whatsapp.com", "web.telegram.org"}
    )
    assert counts == {"surya-mac": 2, "adit-win": 1}


def test_digest_empty_state_says_zero_not_blank():
    msg = build_digest(silent=[], blocked={})
    assert "0 silenti" in msg
    assert "0 tentativi bloccati" in msg


def test_digest_flags_silent_device():
    msg = build_digest(silent=["surya-mac"], blocked={"surya-mac": 3})
    assert "surya-mac" in msg
    assert "SPARITI" in msg
