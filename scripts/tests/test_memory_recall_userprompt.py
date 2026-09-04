"""Unit tests for scripts/memory/mos_recall_userprompt.py (UserPromptSubmit
recall hook — the per-prompt sibling of mos_recall_sessionstart.py's
SessionStart recall). Fixtures live entirely in tmp_path; nothing under
~/.claude is touched. Mirrors test_memory_layers.py's monkeypatch-the-
resolver pattern rather than spawning a real subprocess, for speed and
determinism.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

import pytest

SCRIPTS_MEMORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
sys.path.insert(0, SCRIPTS_MEMORY)

import mos_recall_sessionstart as mos  # noqa: E402
import mos_recall_userprompt as mup  # noqa: E402

FRONT = """---
name: {name}
description: {desc}
metadata:
  type: {typ}
---

Body text about {topic} with several relevant words repeated: {topic} {topic}.
"""

FIXTURE_SCARS_MD = """### 🐛 W501 (P1 STRUCTURAL): a plist KeepAlive=true wrapped a one-shot nohup script and every exit was read as death, causing a restart storm (2026-06-01)

The launchd daemon relaunched the wrapper every few seconds because KeepAlive=true
treats a clean exit from a one-shot nohup child as a crash. Antidote: a real blocking
loop or StartInterval without KeepAlive.

### 🐛 W502 (P2 STRUCTURAL): a merge queue check got cancelled and the PR fell out silently (2026-06-02)

The merge queue removed the PR after a required check was cancelled mid-run, with
no alert surfaced to the author.
"""


def _write_memory(memdir, filename, name, desc, typ, topic):
    (memdir / filename).write_text(FRONT.format(name=name, desc=desc, typ=typ, topic=topic), encoding="utf-8")


def _write_pii_memory(memdir, filename, name, desc, typ):
    (memdir / filename).write_text(
        FRONT.format(name=name, desc=desc, typ=typ, topic="reachability"), encoding="utf-8"
    )


def _write_scars_fixture(scars_dir):
    scars_dir.mkdir(parents=True, exist_ok=True)
    (scars_dir / "cicatrix-scars.md").write_text(FIXTURE_SCARS_MD, encoding="utf-8")


def _run_main(monkeypatch, capsys, stdin_text, memdir=None, scars_dir=None, env=None):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    if memdir is not None:
        monkeypatch.setattr(mup.mos, "resolve_memdir", lambda cwd=None, home=None: str(memdir))
    if scars_dir is not None:
        monkeypatch.setattr(mup.mos, "resolve_scars_dir", lambda cwd=None: str(scars_dir))
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    rc = mup.main()
    out = capsys.readouterr().out
    return rc, out


# --- 1. scar-shaped prompt hits, stays inside budget --------------------

def test_scar_shaped_prompt_hits_and_stays_under_budget(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir1"
    memdir.mkdir()
    scars_dir = tmp_path / "scars1"
    _write_scars_fixture(scars_dir)
    _write_memory(memdir, "discovery_unrelated_2026_08_01.md", "discovery-unrelated",
                  "an unrelated finding about invoicing", "discovery", "invoicing")

    prompt = "il plist ha KeepAlive true e il servizio riparte in loop"
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir, scars_dir=scars_dir)

    assert rc == 0
    assert out != ""
    assert len(out.encode("utf-8")) <= mup.DEFAULT_MAX_BYTES
    hit_lines = [ln for ln in out.splitlines() if ln.startswith("- ")]
    assert len(hit_lines) <= mup.DEFAULT_TOPK
    assert "W501" in out
    assert mup.HEADER in out


# --- 2. too short -> silent ----------------------------------------------

def test_short_prompt_is_silent(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir2"
    memdir.mkdir()
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": "ok"}), memdir=memdir)
    assert rc == 0 and out == ""


# --- 3. slash command -> silent -------------------------------------------

def test_slash_command_is_silent(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir3"
    memdir.mkdir()
    prompt = "/context show me the memory files now please"
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir)
    assert rc == 0 and out == ""


# --- 4. nonsense / no lexical overlap -> silent (relevance floor) --------

def test_no_lexical_overlap_is_silent(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir4"
    memdir.mkdir()
    _write_memory(memdir, "discovery_widget_2026_08_01.md", "discovery-widget",
                  "a finding about manufacturing widgets", "discovery", "widget")
    prompt = "banana kayak zebra unicorn glitter parade"
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir)
    assert rc == 0 and out == ""


# --- 5. garbage stdin -> silent, exit 0 -----------------------------------

def test_garbage_stdin_is_silent(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir5"
    memdir.mkdir()
    rc, out = _run_main(monkeypatch, capsys, "not json {{{", memdir=memdir)
    assert rc == 0 and out == ""


# --- 6. PII in a matching memory is redacted ------------------------------

def test_pii_in_hit_is_redacted(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir6"
    memdir.mkdir()
    _write_pii_memory(
        memdir, "discovery_client_reachability_2026_08_01.md", "discovery-client-reachability",
        "client reachable at mario.rossi@example.com or +62 812 345 6789 about reachability",
        "discovery",
    )
    prompt = "how do I reach the client about their reachability question"
    # threshold forced to 0.0: the point of this test is the redaction path, not the
    # scoring path (that is covered by test 1/4 already) — a real hit is guaranteed.
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir,
                         env={mup.MIN_RELEVANCE_ENV: "0.0"})
    assert rc == 0
    assert out != ""
    assert "@" not in out
    assert "+62" not in out


# --- 7. kill switch -> silent regardless of relevance ---------------------

def test_kill_switch_silences_even_a_strong_hit(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir7"
    memdir.mkdir()
    scars_dir = tmp_path / "scars7"
    _write_scars_fixture(scars_dir)
    prompt = "il plist ha KeepAlive true e il servizio riparte in loop"
    rc, out = _run_main(
        monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir, scars_dir=scars_dir,
        env={mup.KILL_SWITCH_ENV: "1"},
    )
    assert rc == 0 and out == ""


# --- 8. timing budget: 50 candidates, whole hook < 1.5s -------------------

def test_fifty_candidates_stays_under_time_budget(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir8"
    memdir.mkdir()
    for i in range(50):
        _write_memory(memdir, f"discovery_widget_{i}_2026_08_01.md", f"discovery-widget-{i}",
                      f"a finding number {i} about manufacturing widgets and supply chains",
                      "discovery", "widget")
    prompt = "tell me about the manufacturing widget supply chain finding"
    start = time.perf_counter()
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir)
    elapsed = time.perf_counter() - start
    assert rc == 0
    assert elapsed < 1.5


# --- helper-level unit coverage (quiet-gate primitives) -------------------

@pytest.mark.parametrize("prompt, expected", [
    ("/help", True),
    ("!ls -la", True),
    ("  /context", True),
    ("normal question about the deploy pipeline", False),
])
def test_is_slash_or_bang(prompt, expected):
    assert mup.is_slash_or_bang(prompt) == expected


@pytest.mark.parametrize("prompt, expected", [
    ("ok", False),
    ("il plist ha KeepAlive true e riparte", True),
    ("a an the of to in on for is are", False),
])
def test_has_enough_informative_terms(prompt, expected):
    assert mup.has_enough_informative_terms(prompt) == expected


# --- 2026-09-04 follow-up: harness-envelope prompts and long pasted logs -----
# Live observation, minutes after the first merge: the hook fired on a
# background-task notification (not a human prompt) and emitted 3 weak hits
# for ~350B — a staff activity log, an unrelated keychain note, W102. Cures:
# an envelope-shape gate, a query-length cap, and a min_overlap floor.

NOTIFICATION_SHAPED_PROMPT = (
    "[SYSTEM NOTIFICATION - NOT USER INPUT] a background task has completed.\n"
    "<task-notification>\n"
    "  <task-id>keepalive-restart-storm-triage</task-id>\n"
    "  <status>completed</status>\n"
    "  <summary>plist KeepAlive nohup restart storm review finished, W501 W502"
    " staff activity log keychain note reviewed, no action needed</summary>\n"
    "</task-notification>"
)


@pytest.mark.parametrize("prefix", [
    "[SYSTEM NOTIFICATION - NOT USER INPUT] task finished",
    "<task-notification><status>done</status></task-notification>",
    '<teammate-message teammate_id="team-lead" summary="status update">hello</teammate-message>',
    '<cross-session-message from="worker">build finished</cross-session-message>',
    "<system-reminder>background context injected here</system-reminder>",
])
def test_is_harness_envelope_true_for_every_wrapper_shape(prefix):
    assert mup.is_harness_envelope(prefix)


@pytest.mark.parametrize("prompt", [
    "normal question about the merge queue and the cancelled check",
    "il plist ha KeepAlive true e il servizio riparte in loop",
])
def test_is_harness_envelope_false_for_ordinary_prompts(prompt):
    assert not mup.is_harness_envelope(prompt)


def test_notification_shaped_prompt_is_silent_even_with_a_strong_lexical_match(tmp_path, monkeypatch, capsys):
    """The notification text itself contains "plist KeepAlive nohup restart
    storm" and the W501/W502 scar numbers verbatim — a relevance-only gate
    would fire hard. The envelope gate must block it BEFORE scoring."""
    memdir = tmp_path / "memdir_notif"
    memdir.mkdir()
    scars_dir = tmp_path / "scars_notif"
    _write_scars_fixture(scars_dir)
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": NOTIFICATION_SHAPED_PROMPT}),
                         memdir=memdir, scars_dir=scars_dir)
    assert rc == 0 and out == ""


def test_long_pasted_log_with_one_incidental_keepalive_is_silent(tmp_path, monkeypatch, capsys):
    memdir = tmp_path / "memdir_log"
    memdir.mkdir()
    scars_dir = tmp_path / "scars_log"
    _write_scars_fixture(scars_dir)
    noise = " ".join(f"line{i} token{i} value{i}" for i in range(1, 400))  # ~5000 chars, no overlap
    prompt = noise + " one incidental KeepAlive mention buried in the middle of this log " + noise
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir, scars_dir=scars_dir)
    assert rc == 0 and out == ""


def test_query_is_truncated_to_max_query_chars(monkeypatch, tmp_path):
    memdir = tmp_path / "memdir_trunc"
    memdir.mkdir()
    captured = {}

    def _spy_recall(memdir_, cache_path, query, **kwargs):
        captured["query"] = query
        return [], {}

    monkeypatch.setattr(mup.mos, "resolve_memdir", lambda cwd=None, home=None: str(memdir))
    monkeypatch.setattr(mup.mos, "resolve_scars_dir", lambda cwd=None: None)
    monkeypatch.setattr(mup.mos, "recall", _spy_recall)
    long_prompt = "x" * 5000
    mup.build_recall_output(long_prompt, str(tmp_path))
    assert len(captured["query"]) == mup.MAX_QUERY_CHARS


def test_keepalive_scar_prompt_still_fires_after_the_follow_up_gates(tmp_path, monkeypatch, capsys):
    """Regression pin: the original scar-shaped-prompt case (test 1 above)
    must still clear every new gate (envelope shape, truncation, overlap)."""
    memdir = tmp_path / "memdir_regress"
    memdir.mkdir()
    scars_dir = tmp_path / "scars_regress"
    _write_scars_fixture(scars_dir)
    prompt = "il plist ha KeepAlive true e il servizio riparte in loop"
    rc, out = _run_main(monkeypatch, capsys, json.dumps({"prompt": prompt}), memdir=memdir, scars_dir=scars_dir)
    assert rc == 0
    assert out != ""
    assert len(out.encode("utf-8")) <= mup.DEFAULT_MAX_BYTES
    assert "W501" in out
