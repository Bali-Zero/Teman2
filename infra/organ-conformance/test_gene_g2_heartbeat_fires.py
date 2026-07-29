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
import shlex
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


# ---------------------------------------------------------------------------
# The library's OWN documented entry points.
#
# Everything above reaches the heartbeat through `nb-curator-daily.sh`, which is
# `#!/bin/zsh` but calls the library as `bash "$HEARTBEAT_LIB" ...` — the CLI
# form. That leaves the library's FIRST documented usage untested:
#
#     # Source pattern (bash):
#     #   source ~/nuzantara/scripts/lib/heartbeat.sh
#
# and the file goes out of its way to support being sourced from zsh too: the
# CLI-mode guard on its last line tests `ZSH_EVAL_CONTEXT` precisely so that a
# `source` from zsh does not fire the CLI path. That intent was defeated one
# line into the function by `local status=...`: in zsh `status` is a READ-ONLY
# special parameter (the last command's exit code), so the assignment aborts
# the function with `read-only variable: status` and NO sidecar is ever written.
#
# Measured before the fix: sourcing from zsh and calling the function returned
# rc=1 with that message and left no file; the same source+call under bash wrote
# a correct sidecar. No live caller was on the fatal path — all four sourcing
# call-sites in the repo are `#!/bin/bash`, and the one `#!/bin/zsh` wrapper
# invokes the CLI form — so this was a trap set for the next zsh caller, with the
# library's own header inviting them onto it.
# ---------------------------------------------------------------------------

HB_LIB = REPO / "scripts" / "lib" / "heartbeat.sh"
PROBE_ID = "pro.zsh_probe"


def _source_and_call(
    tmp_path: Path, shell: str, *args: str, tag: str = "probe"
) -> tuple[int, str, dict]:
    """SOURCE the library in `shell`, then call the function — the documented
    pattern, not the CLI fallback the wrapper uses."""
    seen = tmp_path / f"last_seen-{tag}"
    script = tmp_path / f"caller-{tag}.{shell}"
    # shlex.quote, not hand-rolled double quotes: the hostile-note case passes a
    # literal `"` and a backslash, and a naive f'"{a}"' produced `unmatched "`
    # in BOTH shells — the harness failing in a way that reads exactly like the
    # library failing. The bash leg is what exposed it.
    body = "\n".join(
        [
            f"source {shlex.quote(str(HB_LIB))}",
            "organism_heartbeat " + " ".join(shlex.quote(a) for a in args),
        ]
    )
    script.write_text(body + "\n", encoding="utf-8")
    proc = subprocess.run(
        [shell, str(script)],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    sidecar = seen / f"{args[0]}.json"
    payload = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    return proc.returncode, (proc.stdout + proc.stderr), payload


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_sourcing_the_library_and_calling_it_writes_a_heartbeat(
    tmp_path: Path, shell: str
) -> None:
    """Guilt (zsh) AND innocence (bash) on one assertion.

    Parametrised deliberately: the bash leg is the behaviour that already worked
    and must keep working, so a "fix" that repaired zsh by breaking the
    documented bash pattern cannot pass here.
    """
    rc, out, hb = _source_and_call(
        tmp_path, shell, PROBE_ID, "error", "rc=42 timeout", tag=shell
    )
    assert "read-only variable" not in out, (
        f"{shell}: the library aborted on a read-only special parameter — "
        f"a heartbeat that cannot be called is not a heartbeat.\n{out}"
    )
    assert rc == 0, f"{shell}: sourcing + calling must not fail the caller: {out}"
    assert hb.get("status") == "error", f"{shell}: expected error, got {hb!r}"
    assert hb.get("note") == "rc=42 timeout", f"{shell}: note lost: {hb!r}"
    assert hb.get("ts", "").endswith("Z")


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_the_status_whitelist_still_degrades_an_unknown_value(
    tmp_path: Path, shell: str
) -> None:
    """Innocence for the rename itself.

    `status` is not just a variable here — it is whitelisted and rewritten to
    "ok" when unrecognised. Renaming it means touching the `case`, the fallback
    assignment and the `printf`; miss one and the sidecar silently reports the
    wrong field or an empty one.
    """
    rc, out, hb = _source_and_call(
        tmp_path, shell, PROBE_ID, "not-a-real-status", "n", tag=f"wl-{shell}"
    )
    assert rc == 0, out
    assert hb.get("status") == "ok", f"{shell}: whitelist fallback lost: {hb!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_hostile_note_is_escaped_into_valid_json(
    tmp_path: Path, shell: str
) -> None:
    """The note is interpolated into JSON by hand, with `${note//pat/repl}`
    substitutions whose pattern semantics are NOT identical in bash and zsh.

    This asserts the OUTCOME (the file parses, and the note survives verbatim)
    rather than the mechanism, so it stays honest under either shell. Without
    it, "sourcing from zsh works now" would be a claim about one happy string.
    """
    hostile = 'a"b\\c\td'
    rc, out, hb = _source_and_call(
        tmp_path, shell, PROBE_ID, "ok", hostile, tag=f"esc-{shell}"
    )
    assert rc == 0, out
    # json.loads already ran in the helper — reaching here means it parsed.
    assert hb.get("note") == 'a"b\\c\td', f"{shell}: note mangled: {hb!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_long_hostile_note_still_leaves_PARSEABLE_json(
    tmp_path: Path, shell: str
) -> None:
    """The 500-char boundary, which the short hostile-note case cannot reach.

    The library escaped first and truncated second, so a note of 499 'a' plus a
    quote escaped to 501 chars and the cut landed BETWEEN the backslash and its
    quote. The orphaned trailing backslash then escaped the JSON's own closing
    quote and the whole sidecar stopped parsing — the reader gets nothing at
    all, which is strictly worse than a truncated note. Adversarial review
    (Codex, generator≠grader) found this; reproduced before the fix.
    """
    hostile = "a" * 499 + '"'
    rc, out, hb = _source_and_call(
        tmp_path, shell, PROBE_ID, "ok", hostile, tag=f"long-{shell}"
    )
    assert rc == 0, out
    # _source_and_call json.loads()es the file; an unparseable sidecar arrives
    # here as {} rather than raising, so assert on the content, not the parse.
    assert hb.get("status") == "ok", f"{shell}: sidecar did not parse: {hb!r}"
    assert hb.get("note", "").startswith("aaa")


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_warn_is_normalised_not_swallowed_into_ok(
    tmp_path: Path, shell: str
) -> None:
    """`warn` used to fall through the whitelist and be rewritten to `ok`.

    That is not cosmetic. `sentinel-aggregate.py` maps ok/success/healthy/
    starting -> ok and degraded/warning -> warning, so the rewrite turned
    agent_worktree_cleanup_cron's "WIP worktree skipped, reaper blocked" into a
    green organ. It must arrive as the reader's own word for it.
    """
    rc, out, hb = _source_and_call(
        tmp_path, shell, PROBE_ID, "warn", "wip skipped", tag=f"warn-{shell}"
    )
    assert rc == 0, out
    assert hb.get("status") == "warning", f"{shell}: expected warning, got {hb!r}"


def test_sourcing_does_not_change_the_callers_shell_state(tmp_path: Path) -> None:
    """A library that is DESIGNED to be sourced must not mutate its caller.

    Two leaks, both from file scope or the regex: `set -o pipefail` was set on
    whoever sourced this (changing their error semantics), and zsh's MATCH /
    MBEGIN / MEND were clobbered by the organ-id `[[ =~ ]]`.
    """
    seen = tmp_path / "last_seen-state"
    script = tmp_path / "state.zsh"
    script.write_text(
        "MATCH=sentinel; MBEGIN=99; MEND=99\n"
        f"source {shlex.quote(str(HB_LIB))}\n"
        f"organism_heartbeat {PROBE_ID} ok n\n"
        'print -r -- "pipefail=${options[pipefail]} MATCH=$MATCH '
        'MBEGIN=$MBEGIN MEND=$MEND"\n',
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["zsh", str(script)],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout.strip()
    assert "pipefail=off" in out, f"sourcing changed the caller's options: {out}"
    assert "MATCH=sentinel" in out, f"sourcing clobbered MATCH: {out}"
    assert "MBEGIN=99" in out and "MEND=99" in out, f"clobbered MBEGIN/MEND: {out}"
    # and it still did its job
    assert (seen / f"{PROBE_ID}.json").exists()


def test_the_workflow_arms_this_corpus_on_push_too(tmp_path: Path) -> None:
    """The gate that runs these cases must WAKE UP for the file they guard.

    `on.pull_request` here has no top-level paths, so PRs always trigger — but
    `on.push.paths` is a filter, and a path present only in the job's internal
    `git diff` pathspec is armed for PRs and silently skipped on merge to main.
    Superscar #2: a corpus that does not run is not a gate.
    """
    wf = (REPO / ".github/workflows/organ-conformance.yml").read_text(
        encoding="utf-8"
    )
    head, _, tail = wf.partition("jobs:")
    assert "scripts/lib/heartbeat.sh" in head, (
        "heartbeat.sh missing from on.push.paths — the post-merge run would skip"
    )
    assert "scripts/lib/heartbeat.sh" in tail, (
        "heartbeat.sh missing from the job's changed-paths pathspec"
    )


def test_sourcing_alone_does_not_fire_the_cli_path(tmp_path: Path) -> None:
    """Innocence for the last line of the library.

    Its CLI-mode guard exists so that `source`-ing from zsh does not execute
    `organism_heartbeat "$@"` with the CALLER's arguments. Load the library in a
    zsh script that was itself given arguments: if the guard regresses, those
    arguments are read as an organ id and a spurious heartbeat appears for an
    organ that never ran.
    """
    seen = tmp_path / "last_seen-guard"
    script = tmp_path / "sourcer.zsh"
    script.write_text(f"source {HB_LIB}\nexit 0\n", encoding="utf-8")
    proc = subprocess.run(
        ["zsh", str(script), PROBE_ID, "ok", "should not be written"],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    written = sorted(p.name for p in seen.glob("*.json")) if seen.exists() else []
    assert written == [], f"sourcing alone wrote a heartbeat: {written}"
