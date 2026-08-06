"""A condition announces itself when it is BORN, not while it lasts.

TRAUMA (measured on the live 31-day spool, 2026-08-06):
  5202 events / 30 days = 176/day, of which 1525 were tier=p0.
  The derived dedup key was sha1(source|text[:160]) — RAW. The three loudest
  sources each embed a changing number inside those 160 chars:
      log-size-watchdog  "= 4.7 MB"  + the log's own tail
      wa-mirror-bridge   "reconnect_attempt=591"
      sentinel           "for 115 consecutive cycles"
  So every repeat hashed to a brand-new key and the 6-hour dedup window never
  applied once: 5202 events presented as 2791 "distinct" conditions. With the
  identity rule: 362. The dedup was decorative for as long as it existed.

Two rules under test:
  1. Identity excludes MEASUREMENTS (numbers, sizes, dates, hashes) and is cut
     at the first sentence of the first line — everything after that is
     EVIDENCE (log tails, stack frames), unbounded variability that no prefix
     truncation can reliably exclude.
  2. A persisting condition gets QUIETER, never louder: each further send mutes
     it for the next rung of TG_REPEAT_LADDER_H. Silence beyond two windows
     means the condition died, so the ladder restarts.

Clock: a holder the test advances by hand — never an iterator of ticks, which
Python's logging would drain by reading time.time() per LogRecord (P3-FLAKY).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

H = 3600.0


@pytest.fixture
def tg(tmp_path, monkeypatch):
    """A hermetic gate: own spool, no network, no host secrets, frozen clock."""
    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SECRETS_FILE", "/dev/null")
    monkeypatch.setenv("TG_REPEAT_LADDER_H", "6,24,72")
    import tg_notify

    importlib.reload(tg_notify)
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(tg_notify.time, "time", lambda: clock["t"])
    tg_notify.advance = lambda hours: clock.__setitem__("t", clock["t"] + hours * H)
    tg_notify._spool = tmp_path
    return tg_notify


def _state(tg):
    return json.loads((tg._spool / "state.json").read_text())


def _entry(tg):
    d = _state(tg)["dedup"]
    assert len(d) == 1, f"expected one condition, got {list(d)}"
    return next(iter(d.values()))


# ------------------------------------------------------------------ identity
def test_measurements_are_not_identity(tg):
    """The exact shape that defeated dedup on the live fleet for 31 days."""
    a = "Log size alert: ~/logs/sentinel.error.log = 4.5 MB (>1MB threshold). tail A"
    b = "Log size alert: ~/logs/sentinel.error.log = 9.9 MB (>1MB threshold). tail Z"
    assert tg.condition_identity("lsw", a) == tg.condition_identity("lsw", b)


def test_counters_in_the_text_are_not_identity(tg):
    a = "wa-mirror disconnected: adit; reason=code_0; reconnect_attempt=1"
    b = "wa-mirror disconnected: adit; reason=code_0; reconnect_attempt=591"
    assert tg.condition_identity("wam", a) == tg.condition_identity("wam", b)


@pytest.mark.parametrize(
    "a,b,why",
    [
        ("Log size alert: ~/logs/a.log = 1 MB", "Log size alert: ~/logs/b.log = 1 MB", "log name"),
        ("wa-mirror disconnected: adit; reason=code_0", "wa-mirror disconnected: asya; reason=code_0", "person"),
        ("wa-mirror disconnected: adit; reason=code_0", "wa-mirror disconnected: adit; reason=closed", "cause"),
        ("CRON FAIL Job: garuda_indexer Exit: 1", "CRON FAIL Job: run_multimodal Exit: 1", "job name"),
        ("System Doctor RED: fly_rag failed", "System Doctor RED: backend unreachable", "which organ"),
    ],
)
def test_nouns_are_identity_and_stay_apart(tg, a, b, why):
    """INNOCENCE: normalisation strips measurements, never nouns."""
    assert tg.condition_identity("s", a) != tg.condition_identity("s", b), why


def test_evidence_after_the_first_sentence_is_ignored(tg):
    """A stack trace under the same headline is the same condition."""
    a = "CRON FAIL Job: garuda_indexer Exit: 1\nTraceback: foo.py line 3"
    b = "CRON FAIL Job: garuda_indexer Exit: 1\nTraceback: bar.py line 91"
    assert tg.condition_identity("c", a) == tg.condition_identity("c", b)


def test_two_sources_never_share_a_condition(tg):
    assert tg.condition_identity("a", "same words") != tg.condition_identity("b", "same words")


def test_explicit_dedup_key_still_wins(tg):
    """Callers that name their own condition are not second-guessed."""
    assert tg.notify("p0", "cron:x", "boom", "cron-fail:job-a") == "sent"
    assert tg.notify("p0", "cron:x", "totally other words", "cron-fail:job-a") == "deduped"


# ------------------------------------------------------- identity IS WIRED IN
# The tests above prove condition_identity() computes the right answer. They do
# NOT prove notify() asks it — reverting the one line that wires it left all of
# them green (mutation run, 2026-08-06). These go through notify(), which is the
# only surface that matters, and die when the wiring is cut.
def test_notify_uses_the_identity_not_the_raw_text(tg):
    """The live log-size shape: same log, different size AND different tail."""
    a = "Log size alert: ~/logs/sentinel.error.log = 4.5 MB (>1MB threshold). tail A"
    b = "Log size alert: ~/logs/sentinel.error.log = 9.9 MB (>1MB threshold). tail Z"
    assert tg.notify("digest", "lsw", a) == "spooled"
    assert tg.notify("digest", "lsw", b) == "deduped", "the raw key would call this new"


def test_notify_keeps_different_logs_apart(tg):
    """INNOCENCE through the same surface: nouns still separate conditions."""
    a = "Log size alert: ~/logs/sentinel.error.log = 4.5 MB (>1MB threshold). tail A"
    b = "Log size alert: ~/logs/flowkit.err.log = 2.5 MB (>1MB threshold). tail B"
    assert tg.notify("digest", "lsw", a) == "spooled"
    assert tg.notify("digest", "lsw", b) == "spooled"


def test_notify_collapses_a_moving_counter(tg):
    """wa-mirror's reconnect_attempt climbs on every single flap."""
    assert tg.notify("digest", "wam", "wa-mirror disconnected: adit; attempt=1") == "spooled"
    assert tg.notify("digest", "wam", "wa-mirror disconnected: adit; attempt=591") == "deduped"


def test_notify_collapses_a_changing_stack_trace(tg):
    """Same headline, different evidence below the first line."""
    assert tg.notify("digest", "c", "CRON FAIL Job: garuda Exit: 1\nTraceback foo") == "spooled"
    assert tg.notify("digest", "c", "CRON FAIL Job: garuda Exit: 1\nTraceback bar") == "deduped"


# -------------------------------------------------------------------- ladder
def test_first_occurrence_is_always_sent(tg):
    assert tg.notify("digest", "s", "the disk is full") == "spooled"


def test_repeat_inside_the_window_is_muted(tg):
    tg.notify("digest", "s", "the disk is full")
    tg.advance(5)
    assert tg.notify("digest", "s", "the disk is full") == "deduped"


def test_window_grows_with_each_send(tg):
    """6h → 24h → 72h: a condition that keeps being true gets quieter."""
    tg.notify("digest", "s", "the disk is full")
    tg.advance(7)  # past rung 1 (6h)
    assert tg.notify("digest", "s", "the disk is full") == "spooled"
    assert _entry(tg)["streak"] == 2
    tg.advance(7)  # would have passed rung 1, but rung 2 is 24h
    assert tg.notify("digest", "s", "the disk is full") == "deduped"
    tg.advance(20)  # 27h total → past rung 2
    assert tg.notify("digest", "s", "the disk is full") == "spooled"
    assert _entry(tg)["streak"] == 3


def test_ladder_saturates_at_the_last_rung(tg):
    """Past the end of the ladder the window stops growing — it does not wrap."""
    assert tg._mute_window_h(1) == 6.0
    assert tg._mute_window_h(2) == 24.0
    assert tg._mute_window_h(3) == 72.0
    assert tg._mute_window_h(4) == 72.0
    assert tg._mute_window_h(99) == 72.0


def test_a_streak_only_grows_while_the_condition_stays_alive(tg):
    """Advance just past each rung so the condition never dies: streak climbs."""
    seen = []
    for hours in (0, 7, 25, 73, 73):
        tg.advance(hours)
        tg.notify("digest", "s", "the disk is full")
        seen.append(_entry(tg)["streak"])
    assert seen == [1, 2, 3, 4, 5], seen


def test_a_condition_that_dies_restarts_the_ladder(tg):
    """Silence beyond two windows = it resolved. The next one is NEWS again."""
    tg.notify("digest", "s", "the disk is full")
    tg.advance(7)
    tg.notify("digest", "s", "the disk is full")
    assert _entry(tg)["streak"] == 2
    tg.advance(60)  # > 2 × 24h rung → died
    assert tg.notify("digest", "s", "the disk is full") == "spooled"
    assert _entry(tg)["streak"] == 1, "a resolved condition must be news again"


def test_a_resent_repeat_declares_how_much_it_was_muted(tg):
    """Suppressing silently would hide a worsening condition."""
    tg.notify("digest", "s", "the disk is full")
    tg.advance(1)
    tg.notify("digest", "s", "the disk is full")
    tg.advance(1)
    tg.notify("digest", "s", "the disk is full")
    tg.advance(7)
    tg.notify("digest", "s", "the disk is full")
    spooled = [json.loads(x) for x in (tg._spool / "pending.jsonl").read_text().splitlines() if x]
    last = spooled[-1]
    assert last.get("suppressed") == 2, spooled
    assert "ripetuta 2×" in last["text"]


def test_the_old_knob_still_names_the_first_window(tg, tmp_path, monkeypatch):
    """TG_DEDUP_HOURS was the flat window. The ladder must not orphan it: an
    operator who tightens it to hear a condition sooner would otherwise be
    parsed and ignored — a knob that lies (superscar #2 in a config file).
    """
    monkeypatch.delenv("TG_REPEAT_LADDER_H", raising=False)
    monkeypatch.setenv("TG_DEDUP_HOURS", "2")
    importlib.reload(tg)
    assert tg._mute_window_h(1) == 2.0, "the first rung IS TG_DEDUP_HOURS"
    assert tg._mute_window_h(2) == 24.0, "later rungs are unaffected"


def test_an_explicit_ladder_overrides_the_old_knob(tg, monkeypatch):
    """INNOCENCE: naming the ladder outright wins over the legacy single value."""
    monkeypatch.setenv("TG_DEDUP_HOURS", "2")
    monkeypatch.setenv("TG_REPEAT_LADDER_H", "9,48")
    importlib.reload(tg)
    assert tg._mute_window_h(1) == 9.0
    assert tg._mute_window_h(2) == 48.0


def test_the_dedup_entry_keeps_the_field_its_consumer_reads(tg):
    """CROSS-FILE CONTRACT (superscar #9): tg_digest_flush.py builds the digest
    footer from `sum(v["count"] - 1)` over this very dict. Adding `streak` is
    additive; dropping `count` would silently zero the footer on the other side
    of a file this test does not import. Changing a shared format from one side
    only is the whole family.
    """
    src = (REPO / "scripts" / "tg_digest_flush.py").read_text()
    assert 'v.get("count"' in src, "consumer changed — re-derive what it reads"
    tg.notify("digest", "s", "the disk is full")
    tg.advance(1)
    tg.notify("digest", "s", "the disk is full")
    assert _entry(tg)["count"] == 2, "the footer would read 0 suppressed"


def test_state_is_not_pruned_before_the_widest_rung(tg):
    """Pruning at the old 2×6h horizon would reset the streak forever."""
    tg.notify("digest", "s", "the disk is full")
    tg.advance(7)
    tg.notify("digest", "s", "the disk is full")
    tg.advance(30)  # far beyond 2×6h, inside 2×72h
    tg.notify("digest", "other unrelated thing", "x")  # triggers the prune pass
    assert any(v.get("streak", 0) >= 2 for v in _state(tg)["dedup"].values())
