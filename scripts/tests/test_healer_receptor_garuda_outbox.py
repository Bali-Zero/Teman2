"""The second path, tested as a LOOP: the reader, its verdict, and its caller.

The reader alone is worthless. What this file refuses to let regress is the
whole chain — a receptor that classifies correctly, a healer tick that calls
it, and a page that leaves on a wire the broken one cannot mute. Two of these
assertions have a GUILT twin, because an assertion that has never failed on a
real defect is a sentence, not a test.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
RECEPTOR = REPO / "scripts" / "healer_receptor_garuda_outbox.py"
HEALER = REPO / "infra" / "healer" / "healer-run.sh"


def _load():
    spec = importlib.util.spec_from_file_location("healer_receptor_garuda_outbox", RECEPTOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.mark.parametrize(
    ("name", "payload", "expected"),
    [
        ("clean", {"status": "ok", "counts": {"undispatched": 0, "exhausted": 0, "older_than_24h": 0}}, 0),
        ("busy but healthy", {"status": "ok", "counts": {"undispatched": 4, "exhausted": 0, "older_than_24h": 0}}, 0),
        ("exhausted row", {"status": "ok", "counts": {"undispatched": 1, "exhausted": 1, "older_than_24h": 0}}, 1),
        ("stuck a day", {"status": "ok", "counts": {"undispatched": 2, "exhausted": 0, "older_than_24h": 2}}, 1),
        ("api could not look", {"status": "unknown", "error": "no database pool"}, 1),
        ("counts missing", {"status": "ok"}, 2),
        ("counts not numbers", {"status": "ok", "counts": {"exhausted": "two"}}, 2),
        ("not an object", ["ok"], 2),
    ],
)
def test_classify(name: str, payload: object, expected: int) -> None:
    code, reason = mod.classify(payload)
    assert code == expected, f"{name}: {reason}"
    assert reason, "a verdict with no reason cannot be acted on"


def test_unknown_status_is_blind_not_clean() -> None:
    """A shape nobody anticipated must never read like 'nothing is wrong'."""
    code, _ = mod.classify({"status": "maintenance"})
    assert code == mod.EXIT_BLIND


def test_the_selftest_corpus_passes_as_a_subprocess() -> None:
    proc = subprocess.run([sys.executable, str(RECEPTOR), "--selftest"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "failed: 0" in proc.stdout


def test_an_unknown_flag_is_refused_not_absorbed() -> None:
    """A receptor that swallows a flag does something other than it was asked."""
    proc = subprocess.run(
        [sys.executable, str(RECEPTOR), "--baseline", "/tmp/nope"], capture_output=True, text=True
    )
    assert proc.returncode == mod.EXIT_BLIND
    assert "unknown argument" in proc.stderr


def test_the_kill_switch_exists_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = subprocess.run(
        [sys.executable, str(RECEPTOR), "--json"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", mod.KILL_SWITCH_ENV: "1"},
    )
    assert proc.returncode == 0
    assert mod.KILL_SWITCH_ENV in proc.stdout


def test_an_unreachable_endpoint_is_blind_not_clean() -> None:
    """The day the API is down must not read like the day the queue is empty."""
    import urllib.error

    with patch.object(mod.urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
        payload, error = mod.fetch("https://example.invalid/health/garuda-outbox")
    assert payload is None
    assert error and "unreachable" in error


# ---------------------------------------------------------------------------
# The half that makes the other half real: somebody calls it, and it pages.
# ---------------------------------------------------------------------------

HEALER_SRC = HEALER.read_text(encoding="utf-8")


def _calls_receptor(src: str) -> bool:
    return "scripts/healer_receptor_garuda_outbox.py" in src


def _pages_on_the_second_path(src: str) -> bool:
    """The PAIRING, not the two words apart.

    The first version of this predicate asked for `"garuda-outbox-second-path"`
    and `telegram p0` anywhere in the file, and its guilt twin stayed green
    when the page was downgraded to a log line: every other receptor also
    says `telegram p0`, so the conjunction proved nothing about THIS one.
    That is the under-match half of cicatrix family #3, caught by the guilt
    control below before it ever shipped.
    """
    return 'telegram p0 "garuda-outbox-second-path"' in src


def test_the_healer_tick_actually_calls_this_receptor() -> None:
    """Existence is not arming (superscar #2): a receptor nobody runs is a file."""
    assert _calls_receptor(HEALER_SRC)


def test_GUILT_the_wiring_assertion_fails_when_the_call_is_removed() -> None:
    sabotaged = HEALER_SRC.replace("scripts/healer_receptor_garuda_outbox.py", "scripts/nothing.py")
    assert not _calls_receptor(sabotaged)


def test_the_healer_pages_this_finding_rather_than_only_logging_it() -> None:
    assert _pages_on_the_second_path(HEALER_SRC)


def test_GUILT_the_paging_assertion_fails_when_the_page_is_removed() -> None:
    sabotaged = HEALER_SRC.replace(
        'telegram p0 "garuda-outbox-second-path"', 'log "garuda-outbox-second-path"'
    )
    assert not _pages_on_the_second_path(sabotaged)


def test_the_healer_script_still_parses() -> None:
    proc = subprocess.run(["bash", "-n", str(HEALER)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
