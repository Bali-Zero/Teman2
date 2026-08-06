"""An alarm must name a condition some organ will act on.

TRAUMA (measured on the live 31-day spool, 2026-08-06): `log_size_watchdog.sh`
alarmed on error logs above 1 MB. `log-rotate-run.sh` trims them at 10 MB.
Between those two independently-maintained constants sat a DEAD ZONE, and the
entire observed population lived in it — all 11 files over the alert line were
1.1-7.1 MB, so every one was permanently loud and permanently ineligible for
rotation. Three had stopped being written months earlier and would have been
announced forever.

That produced 1798 of the organism's 5202 Telegram events in 29.5 days: 34.6%,
the loudest source on the fleet, none of it actionable.

The gap had already been found once. log-rotate-run.sh's own comment, dated
2026-07-20, names the "1-50MB dead zone" and lowers its error threshold 50 -> 10
to close it. It closed half of it, and nothing detected the half that remained.

So the value was never the defect — the INDEPENDENCE was. Two constants that
must agree, maintained in two files with no link between them, drift apart again
the moment either is tuned. This test is that link: it fails the build if the
alarm line ever drops below the cure line.

It reads the DEFAULTS in the scripts, not the running environment, because an
operator override is a deliberate local act while a default is what the fleet
inherits.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WATCHDOG = REPO / "scripts" / "log_size_watchdog.sh"
ROTATOR = REPO / "infra" / "launchagents" / "wrappers" / "log-rotate-run.sh"

# `THRESHOLD_MB="${LOG_SIZE_WATCHDOG_THRESHOLD_MB:-${PRO_LOG_ROTATE_ERR_THRESHOLD_MB:-10}}"`
WATCHDOG_RE = re.compile(
    r'^THRESHOLD_MB=.*?PRO_LOG_ROTATE_ERR_THRESHOLD_MB:-(\d+)', re.MULTILINE
)
# `ERR_THRESHOLD_MB="${PRO_LOG_ROTATE_ERR_THRESHOLD_MB:-10}"`
ROTATOR_RE = re.compile(
    r'^ERR_THRESHOLD_MB="\$\{PRO_LOG_ROTATE_ERR_THRESHOLD_MB:-(\d+)\}"', re.MULTILINE
)


def _default(path: Path, rx: re.Pattern, what: str) -> int:
    assert path.is_file(), f"{path} is gone — this test cannot verify what it claims"
    m = rx.search(path.read_text())
    assert m, (
        f"could not read the {what} default out of {path.name}. The declaration "
        f"changed shape; re-derive it rather than deleting this test — a "
        f"tripwire that cannot parse its subject is worse than none (it reads "
        f"green while measuring nothing)."
    )
    return int(m.group(1))


def test_the_alarm_line_is_never_below_the_cure_line():
    """GUILT: this is the exact 1-vs-10 configuration that produced 34.6% of
    a month of Telegram traffic, none of it actionable."""
    alarm = _default(WATCHDOG, WATCHDOG_RE, "watchdog threshold")
    cure = _default(ROTATOR, ROTATOR_RE, "rotator error threshold")
    assert alarm >= cure, (
        f"DEAD ZONE {cure}>{alarm}MB: the watchdog alarms at {alarm}MB but the "
        f"rotator only acts at {cure}MB. Every error log between those sizes is "
        f"permanently loud and permanently ineligible for the cure. Raise the "
        f"watchdog to the rotator's threshold, or lower the rotator's."
    )


def test_the_watchdog_derives_from_the_rotators_knob():
    """The numbers agreeing TODAY is not the property under test — an operator
    who tunes the rotator must move the watchdog with it, or the next tuning
    reopens the zone. Two constants that happen to match are not linked."""
    src = WATCHDOG.read_text()
    assert "PRO_LOG_ROTATE_ERR_THRESHOLD_MB" in src, (
        "the watchdog no longer reads the rotator's knob — it is back to an "
        "independent constant, which is the defect this test exists for"
    )


def test_the_message_quotes_the_threshold_it_actually_used():
    """The alert text used to hardcode '>1MB threshold'. A message that names a
    number the code no longer uses is a lie the reader cannot detect."""
    src = WATCHDOG.read_text()
    msg = next((ln for ln in src.splitlines() if "Log size alert" in ln), "")
    assert msg, "the alert message vanished — re-derive this test"
    assert "${THRESHOLD_MB}" in msg, (
        f"the alert text hardcodes a threshold instead of quoting the one in "
        f"force: {msg.strip()[:120]}"
    )


def test_the_watchdog_still_uses_a_stable_dedup_key():
    """INNOCENCE for the neighbouring cure (#3668): this producer's key is
    `log-size:<path>` — it names the CONDITION and does not move with the size.
    A key that moved with the measurement would bypass condition_identity() and
    then defeat every mute window, which is what sentinel does."""
    src = WATCHDOG.read_text()
    assert '--dedup-key "log-size:${rel_path}"' in src, (
        "the dedup key changed; if it now contains the size or the log tail it "
        "will defeat the escalating mute ladder entirely"
    )


@pytest.mark.parametrize("env,expected", [
    ({}, 10),
    ({"PRO_LOG_ROTATE_ERR_THRESHOLD_MB": "25"}, 25),
    ({"LOG_SIZE_WATCHDOG_THRESHOLD_MB": "3"}, 3),
    ({"PRO_LOG_ROTATE_ERR_THRESHOLD_MB": "25", "LOG_SIZE_WATCHDOG_THRESHOLD_MB": "3"}, 3),
])
def test_threshold_resolution_order(env, expected):
    """Executed, not read: the shell's own parameter expansion decides this."""
    import subprocess

    expr = 'THRESHOLD_MB="${LOG_SIZE_WATCHDOG_THRESHOLD_MB:-${PRO_LOG_ROTATE_ERR_THRESHOLD_MB:-10}}"'
    assert expr in WATCHDOG.read_text(), "the expansion changed — re-derive this test"
    out = subprocess.run(
        ["bash", "-c", f'{expr}; echo "$THRESHOLD_MB"'],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", **env},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == str(expected)
