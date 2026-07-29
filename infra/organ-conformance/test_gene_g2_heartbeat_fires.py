"""G2_heartbeat — executed, not grepped.

`check_organ_conformance.py` proves the gene is PRESENT: it greps the wrapper
for `organism_heartbeat` / `.organism/last_seen` / `heartbeat() {`. Nothing
proved the gene FIRES, and nothing proved the sidecar carries the run's REAL
verdict. A wrapper that writes `{"status":"ok"}` unconditionally at the end
passes the regex and is exactly the green-that-lies of superscar #2 — the
organ reports health for a run that reported ALL TIERS FAILED two lines up.

So this file runs a real wrapper end to end in a throwaway world and reads the
sidecar it actually wrote, on all four verdicts plus the abort path. The
subject is `scripts/nb-curator-daily.sh` — the one organ whose whole payload
can be faked cheaply (its brain is a single HOME-anchored script). It is one
organ, not a sweep: the value is that the CLASS of defect ("the heartbeat is
decorative") becomes detectable at all, and the pattern is copyable.

Sealed against W96 (a test must never touch production state): HOME, the
heartbeat directory and the Telegram spool are redirected into tmp_path, and
the gateway runs under TG_DRY_RUN=1 — no network, no ~/logs, no real
~/.organism, no real Telegram. Everything else is the REAL thing: the real
wrapper file, the real artifact gate, the real tg_notify.py, the real
heartbeat library resolved the way the wrapper resolves it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "nb-curator-daily.sh"
ORGAN_ID = "pro.nb_curator_daily"

# The wrapper is `#!/bin/zsh` and uses zsh-only expansion (`${0:A:h}`), so there
# is no bash fallback to degrade to. An absent zsh is an ENVIRONMENT fault, not
# a passing test: skipping here would rebuild the thing this file exists to
# catch (a check that cannot go red). The workflow installs zsh explicitly.
pytestmark = pytest.mark.skipif(
    shutil.which("zsh") is None and os.environ.get("CI", "") == "",
    reason="zsh absent on this dev machine; CI installs it and does not skip",
)


def _world(tmp_path: Path, brain_rc: int, write_report: bool) -> dict[str, str]:
    """A HOME rich enough to carry the wrapper to the point being measured.

    W108 §3: a fake world too poor measures itself. An earlier version of this
    harness left the heartbeat library unreachable and reported "the trap never
    fired" when the trap had fired perfectly.
    """
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    (home / "logs").mkdir()
    reports = home / "nuzantara" / "research" / "nb-health"
    reports.mkdir(parents=True)

    # The brain: prints the SUMMARY line the wrapper greps for, and (optionally)
    # writes the report the artifact gate will judge. It writes every candidate
    # path because the wrapper picks one by day-of-week.
    body = (
        "# NB health snapshot\n\nAll notebooks reachable. No action needed.\n"
        if write_report
        else ""
    )
    brain = home / "scripts" / "claude-cascade.sh"
    brain.write_text(
        "#!/bin/sh\n"
        'echo "SUMMARY: broken=0 stale=0 proposals=0 press_new=0"\n'
        + (
            f'for f in "$HOME"/nuzantara/research/nb-health/*.md; do :; done\n'
            f'python3 - <<\'PY\'\n'
            f"import datetime, os, pathlib\n"
            f"d = pathlib.Path(os.environ['HOME']) / 'nuzantara/research/nb-health'\n"
            f"now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)\n"
            f"for name in (now.strftime('%Y-%m-%d-health.md'),\n"
            f"             now.strftime('%Y-%m-%d-curation.md'),\n"
            f"             now.strftime('%Y-%m-nb-intel-curation.md')):\n"
            f"    (d / name).write_text({body!r})\n"
            f"PY\n"
            if write_report
            else ""
        )
        + f"exit {brain_rc}\n",
        encoding="utf-8",
    )
    brain.chmod(0o755)

    # Inherit PATH and friends, but never the caller's knobs for THIS organ: a
    # developer with NB_CURATOR_BRAIN or TG_RELAY_SSH exported in their shell
    # would otherwise measure their shell, not the wrapper.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("NB_CURATOR_", "ORGANISM_", "TG_"))
    }
    env.update(
        {
            "HOME": str(home),
            "NB_CURATOR_LOCK_FILE": str(tmp_path / "nb.lock"),
            "ORGANISM_LAST_SEEN_DIR": str(tmp_path / "last_seen"),
            "TG_DRY_RUN": "1",
            "TG_SPOOL_DIR": str(tmp_path / "spool"),
            "TG_SECRETS_FILE": str(tmp_path / "no-such-secrets.env"),
            # No agy in the fake HOME → the wrapper falls to the cascade brain.
            "NB_CURATOR_BRAIN": "agy",
        }
    )
    return env


def _run(tmp_path: Path, *, brain_rc: int = 0, write_report: bool = True,
         script: Path | None = None, extra_env: dict[str, str] | None = None) -> tuple[int, dict]:
    env = _world(tmp_path, brain_rc, write_report)
    env.update(extra_env or {})
    proc = subprocess.run(
        ["zsh", str(script or WRAPPER)],
        env=env, capture_output=True, text=True, timeout=300,
    )
    sidecar = tmp_path / "last_seen" / f"{ORGAN_ID}.json"
    payload = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    return proc.returncode, payload


def test_a_clean_run_reports_ok_and_says_what_it_did(tmp_path: Path) -> None:
    rc, hb = _run(tmp_path)
    assert rc == 0, "clean run should exit 0"
    assert hb.get("status") == "ok", f"expected ok, got {hb!r}"
    # The note must carry the work, not just liveness: "ok" with no counts is
    # indistinguishable from "the script reached its last line".
    assert "dedup=" in hb.get("note", "") and "brain=" in hb.get("note", "")
    assert hb.get("ts", "").endswith("Z")


def test_a_dead_brain_is_error_never_ok(tmp_path: Path) -> None:
    """Guilt. The run that made this gene necessary."""
    rc, hb = _run(tmp_path, brain_rc=7)
    assert rc == 1, "all-tiers-failed must exit 1"
    assert hb.get("status") == "error", f"expected error, got {hb!r}"
    assert "7" in hb.get("note", ""), "the note must carry the brain's exit code"


def test_a_missing_report_is_degraded_never_ok(tmp_path: Path) -> None:
    """Guilt, second shape: the brain succeeds and the ARTIFACT does not exist.

    This is the exact 2026-07-27 run — a flawless SUMMARY line, no report, a
    green receipt. The heartbeat must not agree with the brain.
    """
    rc, hb = _run(tmp_path, write_report=False)
    assert rc == 2, "artifact-gate failure must exit 2"
    assert hb.get("status") == "degraded", f"expected degraded, got {hb!r}"
    assert "artifact gate" in hb.get("note", "")


def test_a_run_that_dies_before_its_verdict_still_leaves_a_heartbeat(
    tmp_path: Path,
) -> None:
    """The EXIT trap. No sidecar reads as 'never scheduled', which is a
    different cure from 'died' — the organ must not be able to lie by silence.

    The death is injected (an unset variable under `set -u`, this wrapper's
    realistic abort) into a byte-copy of the real file, because there is no
    external way to make the real one abort at that point.
    """
    victim = tmp_path / "dying.sh"
    src = WRAPPER.read_text(encoding="utf-8")
    anchor = "trap _hb_on_exit EXIT"
    assert src.count(anchor) == 1, "trap anchor moved — this test is stale"
    victim.write_text(
        src.replace(anchor, anchor + '\necho "${DELIBERATELY_UNSET_IN_THE_TEST}"'),
        encoding="utf-8",
    )
    # The copy lives outside scripts/, so point the library resolution back at
    # the real one — otherwise the world is too poor to measure the trap.
    lib = REPO / "scripts" / "lib" / "heartbeat.sh"
    assert lib.is_file()
    rc, hb = _run(tmp_path, script=victim,
                  extra_env={"ORGANISM_HEARTBEAT_LIB": str(lib)})
    assert rc != 0
    assert hb.get("status") == "error", f"expected error, got {hb!r}"
    assert "aborted before verdict" in hb.get("note", "")


def test_a_run_blocked_by_the_lock_is_warning_not_ok(tmp_path: Path) -> None:
    """Innocence-adjacent: the organ is alive but did NO work.

    `ok` here would paint a green heartbeat every day for a curator whose lock
    is held by a hung run — alive and never curating. The wrapper must be able
    to say "alive, idle" as a third thing.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "flock").write_text("#!/bin/sh\nexit 1\n")
    (fake_bin / "flock").chmod(0o755)
    env = _world(tmp_path, brain_rc=0, write_report=False)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    proc = subprocess.run(
        ["zsh", str(WRAPPER)], env=env, capture_output=True, text=True, timeout=60
    )
    sidecar = tmp_path / "last_seen" / f"{ORGAN_ID}.json"
    assert proc.returncode == 0, "a held lock is not a failure"
    assert sidecar.exists(), "a skipped run is still a run — it must say so"
    hb = json.loads(sidecar.read_text())
    assert hb.get("status") == "warning", f"expected warning, got {hb!r}"


def test_the_sidecar_path_is_the_one_the_registry_promises() -> None:
    """The gene is only useful if the reader looks where the writer writes.

    A heartbeat at a path no `bridge_source` names is a file nobody reads —
    green by construction, silent by design.
    """
    import yaml  # provided by the workflow's `pip install pyyaml`

    registry = yaml.safe_load(
        (REPO / "apps/organism/organism/organs_registry.yaml").read_text()
    )
    entry = next(o for o in registry["organs"] if o["id"] == ORGAN_ID)
    assert entry["bridge_source"]["path"] == f"~/.organism/last_seen/{ORGAN_ID}.json"
    assert entry["bridge_source"]["timestamp_field"] == "ts"
    assert entry["bridge_source"]["status_field"] == "status"
    # And the wrapper must write under that id, not a name of its own invention.
    assert f'ORGAN_ID="{ORGAN_ID}"' in WRAPPER.read_text(encoding="utf-8")


def test_the_heartbeat_is_fresh_enough_to_be_believed(tmp_path: Path) -> None:
    """A stale sidecar left by an earlier run would satisfy every assertion
    above. Pin the timestamp to THIS run."""
    before = time.time()
    _rc, hb = _run(tmp_path)
    ts = hb["ts"]
    written = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    assert written >= before - 5, f"heartbeat ts {ts} predates the run"
