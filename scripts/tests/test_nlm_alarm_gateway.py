"""The 18 nlm_deep_research cron wrappers must be able to SPEAK when they fail.

Before this change every one of them alarmed inside
`if [ -n "$TELEGRAM_BOT_TOKEN" ] … curl … >/dev/null 2>&1 || true; fi` — a branch
that, in the token-poor launchd/cron environment that produces the failures,
does nothing and leaves no trace of having done nothing.

Two halves, and the second is the one that matters:

* a CLASS guard — no direct sender may come back into this directory, and a file
  that calls `alert` must carry the helper;
* a FAKE WORLD — the real wrapper, copied into a tree of the same depth so its
  own `../../../..` arithmetic resolves inside tmp, with a failing job and
  `TG_DRY_RUN=1`. It proves the alarm reaches the gateway rather than asserting
  that the source says it would (W107).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# The direct-sender URL is NOT spelled out in this file. `lint_tg_direct_senders`
# scans textually and counts a mention in ANY non-gateway file as a hit — a
# deliberate over-match, documented in its own header, whose whole point is that
# the string stops existing outside the gateway. A test that types the literal to
# assert its absence becomes the thing it forbids (it did: CI flagged this file).
# Importing the constant is not evasion, it is the SSOT: if the lint ever changes
# what a direct sender looks like, this guard changes with it instead of going
# quietly stale. Same import shape as scripts/tests/test_tg_gateway.py.
sys.path.insert(0, str(REPO / "scripts"))
from lint_tg_direct_senders import PATTERN as DIRECT_SENDER  # noqa: E402

WRAPPER_DIR = REPO / "apps/evaluator/nlm_deep_research/scripts"
ALERT_LIB = WRAPPER_DIR / "_alert.sh"
TG_NOTIFY = REPO / "scripts/tg_notify.py"

BASH = shutil.which("bash") or "/bin/bash"


def _wrappers() -> list[Path]:
    return sorted(p for p in WRAPPER_DIR.glob("*.sh") if p.name != "_alert.sh")


# --------------------------------------------------------------- CLASS guard


def test_no_wrapper_talks_to_telegram_directly():
    offenders = [p.name for p in _wrappers() if DIRECT_SENDER in p.read_text(encoding="utf-8")]
    assert offenders == [], (
        f"{offenders} still POST to the Telegram API directly. The gateway owns the "
        "token chain and the spool; a direct curl re-creates the silent branch."
    )


def test_every_caller_of_alert_carries_the_helper():
    """A wrapper that calls `alert` without sourcing `_alert.sh` fails at exactly
    the moment it is trying to report a failure."""
    broken = []
    for p in _wrappers():
        text = p.read_text(encoding="utf-8")
        if "alert " in text and "_alert.sh" not in text:
            broken.append(p.name)
    assert broken == [], f"{broken} call alert() without sourcing the helper"


def _code_only(text: str) -> str:
    """Strip comments. The helper QUOTES the old broken pattern in its header to
    explain it; an earlier version of this test matched that quote and failed on
    a correct file — a guard reading the form instead of the entity, in the test
    written to stop exactly that."""
    return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("#"))


def test_the_helper_never_silently_skips_when_the_gateway_is_absent():
    src = _code_only(ALERT_LIB.read_text(encoding="utf-8"))
    assert "ALERT NOT SENT" in src, "the missing-gateway branch must be the loud one"
    # the two idioms that made the old alarm indistinguishable from a delivery
    assert ">/dev/null 2>&1 || true" not in src
    assert DIRECT_SENDER not in src


def test_no_wrapper_captures_an_exit_code_that_errexit_will_never_reach():
    """`<job> | tee log` then `EXIT_CODE=${PIPESTATUS[0]}` under `set -euo
    pipefail` aborts ON the pipeline: the capture, the alarm and the wrapper's own
    `exit $EXIT_CODE` are all dead code on the one path they exist for (W101).
    Measured before the fix: 19 of 20 wrappers reached their job, the job failed,
    and nothing was said."""
    naked = []
    for p in _wrappers():
        lines = p.read_text(encoding="utf-8").split("\n")
        if not any(l.strip().startswith("set -") and "e" in l.split()[1] for l in lines if l.strip().startswith("set -")):
            continue
        for i, l in enumerate(lines):
            if not ("PIPESTATUS[0]" in l or l.strip().endswith("=$?")):
                continue
            # `<job> | tee log || EXIT_CODE=$?` is ALREADY errexit-immune — the
            # `||` disables errexit for the whole pipeline. That is the antidote,
            # not the disease, and flagging it is the same over-match this test
            # exists to catch: the FORM `=$?`, not the entity "unprotected
            # capture". (run_db_nlm_sync.sh does it this way, and it was the one
            # wrapper of twenty that already alarmed correctly.)
            if re.search(r"\|\|\s*[A-Za-z_][A-Za-z0-9_]*=\$\?", l):
                continue
            window = "\n".join(lines[max(0, i - 12):i])
            if "set +e" not in window:
                naked.append(f"{p.name}:{i + 1}")
    assert naked == [], f"exit-code capture unreachable under errexit at {naked}"


def test_no_wrapper_sources_a_maybe_missing_file_behind_only_or_true():
    """Under `set -e`, bash treats `source <missing>` as a failing SPECIAL builtin
    and EXITS — `|| true` never runs. Measured on bash 3.2.57, the macOS system
    bash these crons use. One wrapper had it unguarded and died at line 37,
    wearing the costume of a tolerant fallback."""
    import re

    offenders = []
    for p in _wrappers():
        lines = p.read_text(encoding="utf-8").split("\n")
        under_e = any(re.match(r"^\s*set -[a-z]*e", l) for l in lines)
        if not under_e:
            continue
        for i, l in enumerate(lines):
            if re.match(r"^\s*(source|\.)\s+[^|&]*\|\|\s*true", l):
                ctx = "\n".join(lines[max(0, i - 3):i])
                if not re.search(r"\[\[?\s*-[fers]\s", ctx):
                    offenders.append(f"{p.name}:{i + 1}")
    assert offenders == [], f"unguarded `source … || true` under errexit at {offenders}"


def test_every_wrapper_is_syntactically_valid():
    bad = []
    for p in [ALERT_LIB, *_wrappers()]:
        if subprocess.run([BASH, "-n", str(p)], capture_output=True).returncode != 0:
            bad.append(p.name)
    assert bad == [], f"bash -n rejects {bad}"


# ---------------------------------------------------------------- FAKE WORLD


def _fake_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A tree deep enough that the wrappers' own `../../../..` lands in tmp."""
    scripts = tmp_path / "apps/evaluator/nlm_deep_research/scripts"
    scripts.mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    shutil.copy2(ALERT_LIB, scripts / "_alert.sh")
    shutil.copy2(TG_NOTIFY, tmp_path / "scripts/tg_notify.py")
    return tmp_path, scripts


def _env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env.update(
        TG_DRY_RUN="1",
        TG_SPOOL_DIR=str(tmp_path / "spool"),
        TELEGRAM_BOT_TOKEN="fake-never-sent",
        TELEGRAM_OWNER_CHAT_ID="0",
    )
    return env


def _spooled(tmp_path: Path) -> str:
    spool = tmp_path / "spool"
    if not spool.exists():
        return ""
    return "\n".join(f.read_text(encoding="utf-8") for f in spool.glob("*.jsonl"))


def test_alert_reaches_the_gateway(tmp_path):
    root, scripts = _fake_tree(tmp_path)
    caller = scripts / "caller.sh"
    caller.write_text(
        '#!/usr/bin/env bash\n'
        '. "$(cd "$(dirname "$0")" && pwd)/_alert.sh"\n'
        'set -euo pipefail\n'
        'alert p0 "PIPELINE X FAILED (exit 7)"\n',
        encoding="utf-8",
    )
    caller.chmod(0o755)

    proc = subprocess.run([BASH, str(caller)], capture_output=True, text=True, env=_env(root))
    assert proc.returncode == 0, proc.stderr
    assert "PIPELINE X FAILED (exit 7)" in _spooled(root)
    assert "tg[p0] rc=0" in proc.stderr, "the outcome must be logged, not discarded"


def test_a_missing_gateway_is_LOUD_and_non_zero(tmp_path):
    """The whole point: 'could not send' must never read like 'sent'."""
    root, scripts = _fake_tree(tmp_path)
    (root / "scripts/tg_notify.py").unlink()

    caller = scripts / "caller.sh"
    caller.write_text(
        '#!/usr/bin/env bash\n'
        '. "$(cd "$(dirname "$0")" && pwd)/_alert.sh"\n'
        'set -uo pipefail\n'
        'alert p0 "PIPELINE X FAILED"; echo "alert_rc=$?"\n',
        encoding="utf-8",
    )
    caller.chmod(0o755)

    proc = subprocess.run([BASH, str(caller)], capture_output=True, text=True, env=_env(root))
    assert "ALERT NOT SENT — gateway missing" in proc.stderr
    assert "PIPELINE X FAILED" in proc.stderr, "the message itself must survive into the log"
    assert "alert_rc=1" in proc.stdout


def test_a_missing_helper_degrades_loudly_instead_of_killing_the_wrapper(tmp_path):
    """A wrapper reaches `alert` only on its failure path. If the helper were
    absent and `alert` undefined, `set -e` would abort THERE — losing both the
    alarm and the wrapper's own exit code."""
    root, scripts = _fake_tree(tmp_path)
    (scripts / "_alert.sh").unlink()

    caller = scripts / "caller.sh"
    caller.write_text(
        '#!/usr/bin/env bash\n'
        '. "$(cd "$(dirname "$0")" && pwd)/_alert.sh" 2>/dev/null || true\n'
        'command -v alert >/dev/null 2>&1 || alert() {\n'
        '    echo "ALERT NOT SENT — _alert.sh missing [$1]: ${*:2}" >&2\n'
        '    return 1\n'
        '}\n'
        'set -euo pipefail\n'
        'EXIT_CODE=7\n'
        'alert p0 "PIPELINE X FAILED" || true\n'
        'exit "$EXIT_CODE"\n',
        encoding="utf-8",
    )
    caller.chmod(0o755)

    proc = subprocess.run([BASH, str(caller)], capture_output=True, text=True, env=_env(root))
    assert "ALERT NOT SENT — _alert.sh missing" in proc.stderr
    assert proc.returncode == 7, "the wrapper must still report ITS OWN failure, not the helper's"


def _install_fake_venv(root: Path) -> None:
    """A venv that EXISTS and whose python always fails.

    This is the difference between a fake world that measures the defect and one
    that measures itself: WITHOUT it, most wrappers exit at their own
    "ERROR: No virtualenv found" long before reaching their job, and read as
    "failed and silent" when they never started. The first version of this sweep
    reported 17/20 silent for exactly that reason — the probe measured its own
    poverty.
    """
    for venv in (".venv", "venv"):
        binn = root / f"apps/backend-rag/{venv}/bin"
        binn.mkdir(parents=True, exist_ok=True)
        (binn / "activate").write_text("export VIRTUAL_ENV=fake\n", encoding="utf-8")
        for exe in ("python", "python3"):
            p = binn / exe
            p.write_text('#!/bin/sh\necho "fake python: job failed" >&2\nexit 3\n', encoding="utf-8")
            p.chmod(0o755)


@pytest.mark.parametrize("wrapper", sorted(p.name for p in WRAPPER_DIR.glob("run_*.sh")))
def test_every_real_wrapper_alarms_end_to_end_when_its_job_fails(tmp_path, wrapper):
    """The whole class, not a representative: every wrapper, run for real, with a
    job that fails. Before this change exactly ONE of the twenty said anything."""
    root, scripts = _fake_tree(tmp_path)
    shutil.copy2(WRAPPER_DIR / wrapper, scripts / wrapper)
    (scripts / wrapper).chmod(0o755)
    _install_fake_venv(root)
    (root / "logs").mkdir(exist_ok=True)
    # run_nb1_refresh.sh drives a script at <root>/scripts/, not a module
    (root / "scripts/nlm_nb1_daily_refresh.py").write_text("import sys; sys.exit(3)\n", encoding="utf-8")

    env = _env(root)
    env["PATH"] = f"{root}/apps/backend-rag/.venv/bin:" + env["PATH"]
    proc = subprocess.run(
        [BASH, str(scripts / wrapper)], capture_output=True, text=True, env=env, timeout=180
    )
    spooled = _spooled(root)
    assert spooled, (
        f"{wrapper} failed and said nothing.\nrc={proc.returncode}\n"
        f"stdout={proc.stdout[-600:]}\nstderr={proc.stderr[-600:]}"
    )
    records = [json.loads(line) for line in spooled.splitlines() if line.strip()]
    assert any("FAIL" in json.dumps(r).upper() for r in records), records
