"""The spool has three writers and only one applied the restriction.

Measured on Pro, 2026-08-06:

    archive-p0.jsonl        -rw-------    written by tg_notify._append
    state.json              -rw-r--r--    written by tg_notify._save_state
    archive/2026-*.jsonl    -rw-r--r--    written by tg_digest_flush._archive
                                          1.6 MB, 33 days, EVERY event

`_append` opens with `0o600` and the flock file is `0o600`, so the author knew
the rule. `_save_state` used `Path.write_text` and `_archive` used `open("a")`
— both take the umask. Superscar #4: the restriction lands where the author was
thinking about it and is missed where a different idiom was used.

The two unprotected paths are the LARGER exposure, not the smaller. state.json
carries `last_text` — 200 characters of every alert, which for wa-attention
includes a client's name. The daily archive is the complete record and still
holds 560 rows whose dedup key carries a raw client phone number, from before
the 2026-07-26 grouping fix replaced it with a set signature.

The cure carried the shape of the disease and this corpus is why that was
caught: the first version of `harden()` only chmod'd, so it repaired files that
already existed and let each new day's archive be BORN 0644 under the umask via
`open("a")`. `test_a_brand_new_archive_file_is_born_private` is that bug.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

GATEWAY = REPO / "scripts" / "tg_notify.py"
FLUSH = REPO / "scripts" / "tg_digest_flush.py"


def _mode(p: Path) -> str:
    return oct(stat.S_IMODE(p.stat().st_mode))


def _group_or_other_readable(p: Path) -> bool:
    return bool(p.stat().st_mode & 0o077)


@pytest.fixture
def spool(tmp_path, monkeypatch):
    """A throwaway spool with a PERMISSIVE umask, so a missing mode shows up.

    Under a 0077 umask every file would come out 0600 by accident and the whole
    corpus would pass against unfixed code — a test measuring the environment
    instead of the code. 0022 is what Pro actually runs.
    """
    d = tmp_path / "spool"
    d.mkdir()
    monkeypatch.setenv("TG_SPOOL_DIR", str(d))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SECRETS_FILE", "/dev/null")
    # Dummy credentials: the digest flush refuses to archive unless a send
    # SUCCEEDS, and `bool(token and chat)` is checked before TG_DRY_RUN is even
    # consulted. Without these the archive is never written and the test would
    # be measuring its own missing config, not the file mode (W108).
    # DRY_RUN short-circuits send_telegram before any network call; the
    # hermeticity is asserted, not assumed, in the archive test below.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-never-used")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "0")
    old = os.umask(0o022)
    yield d
    os.umask(old)


# --------------------------------------------------------------------- guilt
def test_every_file_the_gateway_writes_is_private(spool):
    """One pass through the real gateway, then read the modes off disk."""
    subprocess.run([sys.executable, str(GATEWAY), "--tier", "digest",
                    "--source", "t", "--", "hello"], check=True,
                   capture_output=True, env={**os.environ})
    subprocess.run([sys.executable, str(GATEWAY), "--tier", "p0",
                    "--source", "t", "--", "fire"], check=True,
                   capture_output=True, env={**os.environ})
    written = [p for p in spool.iterdir() if p.is_file()]
    assert written, "the gateway wrote nothing — the probe measured its own setup"
    leaky = {p.name: _mode(p) for p in written if _group_or_other_readable(p)}
    assert not leaky, f"spool files readable beyond the owner: {leaky}"


def test_state_json_is_private(spool):
    """state.json is singled out because it is the one that carries CONTENT:
    `last_text` keeps 200 characters of every alert. It was 0644 on Pro."""
    subprocess.run([sys.executable, str(GATEWAY), "--tier", "digest",
                    "--source", "t", "--", "x"], check=True, capture_output=True)
    st = spool / "state.json"
    assert st.exists(), "no state written — nothing was measured"
    assert not _group_or_other_readable(st), f"state.json is {_mode(st)}"


def test_a_brand_new_archive_file_is_born_private(spool):
    """The bug THIS fix had on its first draft.

    A chmod-only `harden()` repairs files that already exist. The daily archive
    file does not exist until the first flush of the day, so `open("a")`
    created it under the umask and it was 0644 for its whole life — every day,
    forever, on the largest file in the spool. Protecting only what is already
    there is not protection.
    """
    subprocess.run([sys.executable, str(GATEWAY), "--tier", "digest",
                    "--source", "t", "--", "spool me"], check=True, capture_output=True)
    r = subprocess.run([sys.executable, str(FLUSH)], capture_output=True, text=True)
    adir = spool / "archive"
    assert adir.is_dir(), f"nothing archived, so nothing measured: {r.stdout}{r.stderr}"
    created = list(adir.glob("*.jsonl"))
    assert created, f"the archive is empty: {r.stdout}{r.stderr}"
    assert (spool / "sent-dry.jsonl").exists(), (
        "the flush took the REAL send path — this test was not hermetic")
    leaky = {p.name: _mode(p) for p in created if _group_or_other_readable(p)}
    assert not leaky, f"a NEW archive file was born world-readable: {leaky}"


def test_an_existing_loose_file_is_repaired(spool):
    """33 days of 0644 archives are already on Pro. The fix must heal them on
    the next write, not only protect what it creates — otherwise the exposure
    survives the cure and needs a separate repair pass nobody will run."""
    from tg_notify import harden

    victim = spool / "already-loose.jsonl"
    victim.write_text("{}\n")
    os.chmod(victim, 0o644)
    assert _group_or_other_readable(victim), "setup failed: the file is not loose"
    harden(victim)
    assert not _group_or_other_readable(victim), f"still {_mode(victim)}"


# ----------------------------------------------------------------- innocence
def test_hardening_never_takes_down_the_alert_it_carries(spool, monkeypatch):
    """INNOCENCE, and it is the whole reason this swallows OSError: a spool the
    process cannot chmod (foreign owner, read-only mount) must degrade, never
    raise. An alerter that dies because it could not tidy its own permissions
    has traded a privacy defect for a silence defect."""
    import tg_notify

    def boom(*a, **k):
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(tg_notify.os, "chmod", boom)
    monkeypatch.setattr(tg_notify.os, "open", boom)
    assert tg_notify.harden(spool / "whatever.jsonl") == spool / "whatever.jsonl"


def test_harden_does_not_truncate(spool):
    """INNOCENCE: harden() opens the file to create it privately. O_CREAT
    without O_TRUNC — if that ever became O_TRUNC the spool would be silently
    emptied on every append, which is worse than the leak it fixes."""
    from tg_notify import harden

    f = spool / "has-content.jsonl"
    f.write_text('{"a": 1}\n{"b": 2}\n')
    harden(f)
    assert f.read_text() == '{"a": 1}\n{"b": 2}\n', "harden() ate the spool"


def test_the_gateway_still_works_at_all(spool):
    """INNOCENCE: the selftest is the gateway's own guilt+innocence corpus.
    If hardening broke a write path, this is where it shows."""
    r = subprocess.run([sys.executable, str(GATEWAY), "--selftest"],
                       capture_output=True, text=True)
    assert "SELFTEST PASS" in r.stdout, r.stdout + r.stderr


def test_the_records_are_still_readable_after_hardening(spool):
    """INNOCENCE: 0600 must not mean 0000 — the owner still reads its own
    spool, and tg_digest_flush is the owner."""
    subprocess.run([sys.executable, str(GATEWAY), "--tier", "digest",
                    "--source", "t", "--", "readable?"], check=True, capture_output=True)
    pending = spool / "pending.jsonl"
    rows = [json.loads(l) for l in pending.read_text().splitlines() if l.strip()]
    assert rows and rows[0]["text"] == "readable?"
