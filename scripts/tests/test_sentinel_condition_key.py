"""An explicit dedup key that MOVES with the measurement is worse than none.

TRAUMA (measured on the live 31-day spool, 2026-08-06): `send_alert` passed
`--dedup-key sentinel:<md5(message)>`, and the message carries the counter:

    🔴 Sentinel | BLIND HEAL-LOOP: 16 TERMINAL job(s) parked in DLQ but ZERO
                 healing actions for 99 consecutive cycles

378 sentinel events produced **255 distinct keys** — 36 real conditions wearing
255 identities. That key is not merely useless, it is actively harmful: in
`tg_notify.notify()` the rule is `key = dedup_key or sha1(condition_identity())`,
so an explicit key WINS. A moving explicit key therefore (a) suppresses the
gateway's own normaliser and (b) defeats every mute window, because each
re-measurement looks like a brand-new condition. 168 of those events were one
condition, announced every ~4h for a month, never healed.

Replayed over the same 378 events (29.3 days) with the 6/24/72/168h ladder,
scoring both branches of `dedup_key or derived`: 12.90/day → 3.38/day, and
5.73 → 0.24/day on p0.

The cure has two halves and this file tests both:
  1. a named `condition` becomes `sentinel:<condition>` — stable by
     construction, and survives rewording of the message, which a derived key
     cannot;
  2. NO name means NO `--dedup-key` at all, so the gateway derives one. The
     normaliser is NOT re-implemented here: two constants that must agree,
     maintained in two files, is the drift this organism keeps relapsing into.

These assert on the ARGV the gateway is actually handed, because that is the
only surface that matters — asserting on a helper would prove the helper
(W116), not that send_alert speaks to the gateway the way this docstring says.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


def _wire(tmp_path, monkeypatch, *, real_local_dedup: bool):
    """A fake gateway that records its argv — the real one is never spawned."""
    fake = tmp_path / "tg_notify.py"
    argv_log = tmp_path / "argv.jsonl"
    fake.write_text(textwrap.dedent(f"""
        import json, sys
        with open({str(argv_log)!r}, "a") as fh:
            fh.write(json.dumps(sys.argv[1:]) + "\\n")
        print("tg_notify: sent", file=sys.stderr)
    """).strip() + "\n")

    import sentinel_lib.alerter as alerter

    # Redirect BOTH the gateway and the local dedup store, so the test never
    # reads or writes fleet state (W96: a test that writes production state).
    monkeypatch.setattr(alerter, "_gateway_script", lambda: str(fake))
    monkeypatch.setattr(alerter, "DEDUP_FILE", str(tmp_path / "dedup.json"))
    if not real_local_dedup:
        # Most tests are about the KEY handed to the gateway; the 1h local
        # fast-path would hide the second send and is exercised separately.
        monkeypatch.setattr(alerter, "_load_dedup", lambda: {})
        monkeypatch.setattr(alerter, "_mark_sent", lambda k: None)
    alerter._argv_log = argv_log
    return alerter


@pytest.fixture
def sentinel(tmp_path, monkeypatch):
    return _wire(tmp_path, monkeypatch, real_local_dedup=False)


@pytest.fixture
def sentinel_with_local_dedup(tmp_path, monkeypatch):
    return _wire(tmp_path, monkeypatch, real_local_dedup=True)


def _keys(alerter) -> list[str | None]:
    """The --dedup-key of every gateway invocation, None when absent."""
    out = []
    if not alerter._argv_log.exists():
        return out
    for line in alerter._argv_log.read_text().splitlines():
        argv = json.loads(line)
        out.append(argv[argv.index("--dedup-key") + 1] if "--dedup-key" in argv else None)
    return out


# ------------------------------------------------------------------ guilt
def test_a_named_condition_survives_a_moving_measurement(sentinel):
    """THE trauma, verbatim: the same condition, re-measured, must keep one key."""
    sentinel.send_alert("BLIND HEAL-LOOP: 16 jobs parked for 3 cycles",
                        level="CRITICAL", condition="blind_heal_loop")
    sentinel.send_alert("BLIND HEAL-LOOP: 18 jobs parked for 99 cycles",
                        level="CRITICAL", condition="blind_heal_loop")
    assert _keys(sentinel) == ["sentinel:blind_heal_loop"] * 2


def test_a_named_condition_survives_rewording(sentinel):
    """A name outlives an edit to the sentence — which is why it beats deriving."""
    sentinel.send_alert("BLIND HEAL-LOOP: 16 jobs parked", condition="blind_heal_loop")
    sentinel.send_alert("Heal loop idle: nothing has been retried in 4 days",
                        condition="blind_heal_loop")
    assert len(set(_keys(sentinel))) == 1


def test_no_condition_sends_no_key_so_the_gateway_derives_one(sentinel):
    """The half that is easy to get wrong: passing SOME key would beat the
    gateway's normaliser. Absence is the point, not a fallback."""
    sentinel.send_alert("something with no named condition 42")
    assert _keys(sentinel) == [None], (
        "an unnamed alert must reach the gateway with NO --dedup-key, or the "
        "explicit key wins over condition_identity() — the trauma, again"
    )


def test_the_key_never_carries_a_message_hash(sentinel):
    """Pins the exact defect: md5(message) must not reach the gateway."""
    import hashlib

    msg = "BLIND HEAL-LOOP: 16 jobs parked for 99 cycles"
    sentinel.send_alert(msg, condition="blind_heal_loop")
    key = _keys(sentinel)[0] or ""
    assert hashlib.md5(msg.encode()).hexdigest() not in key
    assert not any(len(p) == 32 and all(c in "0123456789abcdef" for c in p)
                   for p in key.split(":")), f"a bare hash is back in the key: {key}"


# --------------------------------------------------------------- innocence
def test_different_jobs_stay_different_conditions(sentinel):
    """INNOCENCE: on the live corpus `Tier N needed — dropbox-intake` and
    `— login-healthcheck` are separate conditions and must NOT collapse."""
    sentinel.send_alert("Tier 3 needed — dropbox-intake",
                        condition="tier-escalation:dropbox-intake")
    sentinel.send_alert("Tier 3 needed — login-healthcheck",
                        condition="tier-escalation:login-healthcheck")
    assert len(set(_keys(sentinel))) == 2


def test_the_condition_is_namespaced_to_sentinel(sentinel):
    """A bare condition name must not be able to collide with another source's."""
    sentinel.send_alert("x", condition="blind_heal_loop")
    assert _keys(sentinel)[0].startswith("sentinel:")


def test_level_still_routes_the_tier(sentinel):
    """INNOCENCE: naming a condition must not disturb the tier mapping."""
    sentinel.send_alert("a", level="CRITICAL", condition="c1")
    sentinel.send_alert("b", level="WARNING", condition="c2")
    tiers = []
    for line in sentinel._argv_log.read_text().splitlines():
        argv = json.loads(line)
        tiers.append(argv[argv.index("--tier") + 1])
    assert tiers == ["p0", "digest"]


def test_signature_stays_backward_compatible(sentinel):
    """~40 call sites pass (message) or (message, level=...). None may break."""
    assert sentinel.send_alert("positional only") is True
    assert sentinel.send_alert("with level", level="WARNING") is True
    assert sentinel.send_alert("positional level", "WARNING") is True
    assert len(_keys(sentinel)) == 3


def test_the_local_fastpath_still_saves_the_second_subprocess(sentinel_with_local_dedup):
    """INNOCENCE for the half NOT changed: the 1h exact-text guard still
    short-circuits a byte-identical repeat, so this diff did not quietly turn
    one suppression layer off while renaming another."""
    a = sentinel_with_local_dedup
    assert a.send_alert("identical text", condition="c") is True
    assert a.send_alert("identical text", condition="c") is False
    assert len(_keys(a)) == 1, "the second identical message spawned a gateway anyway"


def test_the_fastpath_does_not_swallow_a_changed_measurement(sentinel_with_local_dedup):
    """...and it must NOT suppress a re-measurement — that is the gateway's job,
    on the ladder. If the local guard ate these, naming the condition would be
    pointless because nothing would reach the gateway to be laddered."""
    a = sentinel_with_local_dedup
    assert a.send_alert("BLIND HEAL-LOOP: 16 jobs", condition="blind_heal_loop") is True
    assert a.send_alert("BLIND HEAL-LOOP: 17 jobs", condition="blind_heal_loop") is True
    assert _keys(a) == ["sentinel:blind_heal_loop"] * 2


# ------------------------------------------------- the wiring, not the helper
def test_the_blind_heal_loop_call_site_names_its_condition():
    """The 168-event offender. A parameter nothing passes is a parameter that
    changes nothing — this reads the caller, not the helper."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    assert 'send_alert(msg, level="CRITICAL", condition=cooldown_key)' in src, (
        "the BLIND HEAL-LOOP alert stopped naming its condition — 168 events "
        "over 29 days were this one call site"
    )


def test_the_tier_escalation_call_sites_name_the_job():
    """Three sites; the job must be IN the condition or they collapse together."""
    src = (REPO / "scripts" / "nuzantara-sentinel.py").read_text()
    found = src.count('condition=f"tier-escalation:{job_id}"')
    assert found == 3, f"expected 3 tier-escalation sites naming the job, found {found}"


def test_the_settings_watcher_names_the_content_not_the_clock():
    """The fourth producer, where the SAME rule gives the OPPOSITE answer.

    A census of the 31-day spool found 4 sentinel condition families, not 3:
    168 blind-heal-loop + 161 tier-escalation + 36 ocr-blocked + 12
    settings.json-changed. For the first three, collapsing re-measurements is
    the whole point. For this one it would be a REGRESSION: each alert is a
    DIFFERENT change that each needs its own session restart, and 6 of the 11
    measured gaps are inside the 6h first window — the gateway's derived
    identity (digits stripped) would have muted 6 genuine alerts.

    The entity is the file's md5; the timestamp is the measurement. Same rule,
    read correctly, keeps this producer fully audible at 12 alerts/month.
    """
    src = (REPO / "scripts" / "claude-settings-change-alert.sh").read_text()
    assert 'ALERT_CONDITION="settings-json:${MD5_SHORT}"' in src, (
        "the watcher must name the CONTENT hash; a timestamp-derived key moves, "
        "and no key at all collapses every change into one muted identity"
    )
    assert 'condition=os.environ.get("ALERT_CONDITION", "")' in src
    assert "TIMESTAMP" not in src.split("ALERT_CONDITION=")[1].split("\n")[0], (
        "the clock leaked back into the condition"
    )


def test_the_settings_watcher_survives_an_older_alerter():
    """Deploy skew must degrade to an UNNAMED alert, never to silence: the
    outer `except Exception` in that script swallows everything and exits 0, so
    a TypeError from an old ~/scripts alerter would lose the alert outright."""
    src = (REPO / "scripts" / "claude-settings-change-alert.sh").read_text()
    assert "except TypeError:" in src
    assert src.count("send_alert(msg, level=\"WARNING\")") == 1, (
        "the no-condition fallback call is missing — a version skew loses the alert"
    )


def test_no_call_site_hands_a_hash_to_condition():
    """A condition built from the message would re-create the trauma with a
    different spelling. Scan every caller in the tree, not just the ones I
    happened to edit (W107: census the producers)."""
    offenders = []
    for path in list(REPO.glob("scripts/**/*.py")) + list(REPO.glob("apps/**/*.py")):
        if "/tests/" in str(path) or path.name == __file__.rsplit("/", 1)[-1]:
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "condition=" in line and ("md5" in line or "sha1" in line or "hexdigest" in line):
                offenders.append(f"{path.relative_to(REPO)}:{i}")
    assert not offenders, f"a condition built from a hash is the trauma: {offenders}"
