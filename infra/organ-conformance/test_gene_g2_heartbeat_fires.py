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
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "nb-curator-daily.sh"
ORGAN_ID = "pro.nb_curator_daily"

# The locale the collation test needs. Named once so the test's control
# experiment and CI's locale-generation step cannot drift apart.
LOCALE_UTF8 = "it_IT.UTF-8"

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
def test_an_unrecognised_status_degrades_and_never_greens(
    tmp_path: Path, shell: str
) -> None:
    """This test used to assert the DEFECT, and asserting it is what hid it.

    The whitelist's fallback was `*) hb_status="ok"`, and this case pinned that
    as correct behaviour under the name "still degrades an unknown value" -- but
    rewriting an unknown value to `ok` is not degrading it, it is the opposite.
    `sentinel-aggregate.py` maps ok/success/healthy/starting -> ok, so an organ
    reporting a status this library did not recognise was published as HEALTHY.

    Adversarial review (Codex, generator != grader) found it by asking what
    happens to the near-misses a caller actually writes. Every one of them fell
    through: `failed` (the list only had `fail`), any uppercase spelling, and
    words like `crash` or `timeout` that no vocabulary lists. The fallback is now
    `warning` -- visible, and not the `dead` that a raw pass-through would page
    for.
    """
    for bad in ("not-a-real-status", "failed", "ERROR", "FAIL", "crash", "timeout"):
        rc, out, hb = _source_and_call(
            tmp_path, shell, PROBE_ID, bad, "n", tag=f"wl-{shell}-{bad}"
        )
        assert rc == 0, out
        assert hb.get("status") not in (
            "ok",
            "success",
            "healthy",
            "starting",
        ), f"{shell}: {bad!r} was published as healthy: {hb!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_failure_synonyms_land_on_error_not_merely_non_ok(
    tmp_path: Path, shell: str
) -> None:
    """Guilt, sharper than "not green": a failure must read as a FAILURE.

    Degrading `failed` to `warning` would satisfy the test above while still
    under-reporting a dead organ, so pin the actual mapping.
    """
    for bad in ("fail", "failed", "failure", "FATAL", "crashed", "dead"):
        rc, out, hb = _source_and_call(
            tmp_path, shell, PROBE_ID, bad, "n", tag=f"err-{shell}-{bad}"
        )
        assert rc == 0, out
        assert hb.get("status") == "error", f"{shell}: {bad!r} -> {hb!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_innocence_the_healthy_vocabulary_still_reads_healthy(
    tmp_path: Path, shell: str
) -> None:
    """The other half of the whitelist change.

    A fallback that degrades everything unknown is only safe if the words that
    SHOULD be green still are -- including `disabled`, whose mapping to `ok` is a
    deliberate exception documented in the library (passing it through would make
    the reader call the organ dead and the healer would resurrect exactly the
    organ an operator switched off).
    """
    for good, expected in (
        ("ok", "ok"),
        ("OK", "ok"),
        ("success", "success"),
        ("healthy", "healthy"),
        ("starting", "starting"),
        ("disabled", "ok"),
    ):
        rc, out, hb = _source_and_call(
            tmp_path, shell, PROBE_ID, good, "n", tag=f"ok-{shell}-{good}"
        )
        assert rc == 0, out
        assert hb.get("status") == expected, f"{shell}: {good!r} -> {hb!r}"


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

    The first version of this test searched the raw YAML, so the COMMENT
    explaining why the path is in the pathspec satisfied the assertion on its
    own: deleting the real `git diff` argument and keeping the comment left the
    test green. Adversarial review demonstrated exactly that mutation. It judged
    the form (the string appears somewhere) instead of the entity (the workflow
    actually filters on it), which is the over-match this repo keeps re-learning
    — and a regression proof that a mutation cannot turn red is not a proof.

    Stripping comments cured only half of that. The version after it split the
    file on `jobs:` and asked whether the path appeared on each side — which is
    CONTAINMENT, not configuration: an unrelated `env:` entry naming the path
    before `jobs:` satisfied the first assertion with both real filter entries
    deleted. Adversarial review demonstrated that mutation too. So this reads the
    parsed document: the path must be an ELEMENT of `on.push.paths`, and it must
    appear in the `run:` body of the step that actually enumerates changed files.
    """
    import yaml  # local: only this test needs it

    wf_path = REPO / ".github/workflows/organ-conformance.yml"
    doc = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    # PyYAML resolves the bare key `on` to the boolean True (the "Norway
    # problem"), so both spellings have to be tried or this reads as unarmed.
    triggers = doc.get("on", doc.get(True)) or {}
    push_paths = (triggers.get("push") or {}).get("paths") or []
    assert "scripts/lib/heartbeat.sh" in push_paths, (
        "scripts/lib/heartbeat.sh is not an element of on.push.paths "
        f"({push_paths!r}) — the post-merge run would skip this corpus"
    )

    # The job's own changed-file enumeration: find the step whose script runs the
    # diff, and require the path inside THAT script rather than anywhere in the
    # file. An empty candidate set would pass a bare `all()`, so it is asserted.
    # The path must be an ARGUMENT of the git-diff command, not a substring of
    # the step. Two weaker versions were defeated in turn: matching the raw step
    # accepted the COMMENT that explains the pathspec, and stripping only
    # whole-line comments still accepted an inline `# scripts/lib/heartbeat.sh`
    # on a live line. Both left the real argument deletable with the test green.
    # So the command is reassembled across its `\` continuations and tokenised
    # the way a shell would — `shlex` drops comments and unquotes, so what is
    # left is what `git diff` actually receives.
    def _git_diff_args(script: str) -> list[str]:
        flat = re.sub(r"\\\n\s*", " ", script)
        args: list[str] = []
        for line in flat.splitlines():
            if "git diff" not in line:
                continue
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:  # unbalanced quotes — fail loud, never silently empty
                raise AssertionError(f"cannot tokenise the diff command: {line!r}")
            args.extend(tokens)
        return args

    steps = [
        _git_diff_args(step["run"])
        for job in (doc.get("jobs") or {}).values()
        for step in (job.get("steps") or [])
        if "git diff" in (step.get("run") or "")
    ]
    assert steps, "no step runs `git diff` — this test's premise moved"
    # Guard against a silently empty tokenisation (an empty set satisfies the
    # `any` below by vacuity in the wrong direction — it would just fail, but
    # for the wrong reason and with a misleading message). Note the token is
    # `CHANGED=$(git`, not `git`: the first draft of this guard looked for the
    # bare word and failed on the UNMUTATED workflow — the safety check was
    # stricter than the thing it was protecting.
    assert any("diff" in " ".join(args) for args in steps), (
        "tokenising the git-diff step produced no recognisable command"
    )
    assert any("scripts/lib/heartbeat.sh" in args for args in steps), (
        "scripts/lib/heartbeat.sh is not an ARGUMENT of any `git diff` — the job "
        "would wake up and then decide it has nothing to check. (A mention in a "
        "comment does not count; that is what the two earlier versions of this "
        "assertion accepted.)"
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


# ---------------------------------------------------------------------------
# Round-2 adversarial findings (Codex, generator != grader). Every one of these
# was verified on disk before being written down; none was taken on the
# refuter's word (W65: the refuter hallucinates too).
# ---------------------------------------------------------------------------


def _call_with_env(
    tmp_path: Path, shell: str, note: str, tag: str, extra_env: dict
) -> tuple[int, str, Path]:
    """Like `_source_and_call`, but the caller controls the environment and gets
    the RAW sidecar path back — these cases are about the file being readable at
    all, so they must not go through a helper that json.loads()es it for them."""
    seen = tmp_path / f"last_seen-{tag}"
    script = tmp_path / f"caller-{tag}.{shell}"
    script.write_text(
        f"source {shlex.quote(str(HB_LIB))}\n"
        f"organism_heartbeat {PROBE_ID} ok {shlex.quote(note)}\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [shell, str(script)],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen), **extra_env},
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, (proc.stdout + proc.stderr), seen / f"{PROBE_ID}.json"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_control_character_in_the_note_still_leaves_parseable_json(
    tmp_path: Path, shell: str
) -> None:
    """The escape chain covered \\n \\r \\t and nothing else in U+0000-U+001F.

    A note assembled from a command's stderr carries those bytes routinely, and a
    literal 0x08 inside a JSON string is not valid JSON -- so the reader got
    NOTHING, which is the failure mode this organ exists to prevent. Guilt on the
    two controls that have JSON escapes (\\b, \\f) and one that does not (\\x1f).
    """
    rc, out, sidecar = _call_with_env(
        tmp_path, shell, "a\bb\fc\x1fd", f"ctl-{shell}", {}
    )
    assert rc == 0, out
    assert sidecar.exists(), f"{shell}: no sidecar written: {out}"
    payload = json.loads(sidecar.read_text())  # raises = the defect is back
    assert payload["status"] == "ok"
    assert "\b" not in payload["note"] and "\x1f" not in payload["note"]


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_multibyte_note_cannot_be_split_by_the_byte_truncation(
    tmp_path: Path, shell: str
) -> None:
    """`${note:0:500}` is CHARACTER-based in a UTF-8 locale and BYTE-based under
    LC_ALL=C -- and LC_ALL=C is what cron hands you.

    So the exact same code that is safe on a developer's terminal could cut a
    two-byte character in half on the machine that matters, leaving a lone
    continuation byte: the file was then not even valid UTF-8 and reading it
    failed before parsing started. The dev machine was structurally incapable of
    reproducing it, which is why the env is pinned here rather than inherited.
    """
    rc, out, sidecar = _call_with_env(
        tmp_path, shell, "a" * 499 + "é" + "b" * 40, f"utf-{shell}", {"LC_ALL": "C"}
    )
    assert rc == 0, out
    assert sidecar.exists(), f"{shell}: no sidecar written: {out}"
    raw = sidecar.read_bytes()
    raw.decode("utf-8")  # raises UnicodeDecodeError = the defect is back
    payload = json.loads(raw.decode("utf-8"))
    assert payload["status"] == "ok"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_calling_with_no_arguments_does_not_kill_a_sourcing_caller(
    tmp_path: Path, shell: str
) -> None:
    """`local id="${1:?...}"` EXITS a non-interactive shell when unset.

    Sourced, that shell is the caller's, so a script that mistyped its own
    heartbeat call was killed by it -- measured, bash returned 127 and zsh 1, and
    the line after the call never ran. The library's closing line promises the
    exact opposite ("heartbeat MUST never break the caller"), and a promise only
    the happy path keeps is not one.
    """
    seen = tmp_path / f"last_seen-noargs-{shell}"
    script = tmp_path / f"noargs-{shell}.sh"
    script.write_text(
        f"source {shlex.quote(str(HB_LIB))}\n"
        "organism_heartbeat\n"
        "echo SURVIVED\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [shell, str(script)],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "SURVIVED" in proc.stdout, (
        f"{shell}: the heartbeat killed its own caller "
        f"(rc={proc.returncode}): {proc.stdout + proc.stderr}"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_sourcing_alone_does_not_clobber_a_caller_variable(
    tmp_path: Path, shell: str
) -> None:
    """`_organism_hb_dir` was assigned at FILE scope, so merely sourcing the
    library overwrote a caller variable of that name.

    Same class as the `set -o pipefail` leak the header already warns about, just
    quieter -- and the underscore prefix is a convention, not a guarantee that
    nobody else uses the name.

    BOTH axes, because they are separate defects with the same symptom and a
    mutation test proved the difference: a file-scope assignment leaks on SOURCE,
    while dropping `local` from an in-function assignment leaks only once the
    function is CALLED. A corpus that checks sourcing alone stays green through
    the second one -- measured, not assumed.
    """
    seen = tmp_path / f"last_seen-var-{shell}"
    script = tmp_path / f"var-{shell}.sh"
    script.write_text(
        "_organism_hb_dir=caller-sentinel\n"
        f"source {shlex.quote(str(HB_LIB))}\n"
        'echo "after_source=${_organism_hb_dir}"\n'
        f"organism_heartbeat {PROBE_ID} ok n\n"
        'echo "dir=${_organism_hb_dir}"\n',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [shell, str(script)],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "after_source=caller-sentinel" in proc.stdout, (
        f"{shell}: SOURCING clobbered the caller's variable: {proc.stdout}"
    )
    assert "dir=caller-sentinel" in proc.stdout, (
        f"{shell}: CALLING clobbered the caller's variable: {proc.stdout}"
    )
    assert (seen / f"{PROBE_ID}.json").exists(), "and it still must do its job"


def test_bash_rematch_survives_the_call() -> None:
    """The zsh twin of this was fixed and the bash one was DECLARED and left.

    The organ-id check used `[[ =~ ]]`, which sets BASH_REMATCH globally; `local
    BASH_REMATCH` does not shadow it on bash 3.2, so the library clobbered a
    caller mid-parse. Curing one shell and writing the other down as a "known,
    smaller residue" is the asymmetric-cure shape (W106b): the fix is to stop
    using a regex at all, which sets no globals in EITHER shell.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        seen = Path(td) / "last_seen-rematch"
        script = Path(td) / "rematch.sh"
        script.write_text(
            '[[ "pre-42" =~ pre-([0-9]+) ]]\n'
            f"source {shlex.quote(str(HB_LIB))}\n"
            f"organism_heartbeat {PROBE_ID} ok n\n"
            'echo "re=${BASH_REMATCH[0]}/${BASH_REMATCH[1]}"\n',
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["bash", str(script)],
            env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "re=pre-42/42" in proc.stdout, (
            f"the library clobbered the caller's BASH_REMATCH: {proc.stdout}"
        )
        assert (seen / f"{PROBE_ID}.json").exists(), "and it still must do its job"


# ---------------------------------------------------------------------------
# Round-3 adversarial findings. Round 2's fixes introduced three new ways to
# break the contract they were fixing — the sharpest being that the cure for
# "an unrecognised status must not read healthy" put an external command in the
# VERDICT path, so a failing `tr` downgraded `error` to `warning` and a `tr`
# that printed nothing turned it into `ok`. Measured, both shells.
# ---------------------------------------------------------------------------


def _script(tmp_path: Path, shell: str, tag: str, body: str) -> tuple[int, str, Path]:
    seen = tmp_path / f"seen-{tag}"
    script = tmp_path / f"{tag}.{shell}"
    script.write_text(body, encoding="utf-8")
    proc = subprocess.run(
        [shell, str(script), str(HB_LIB)],
        env={**os.environ, "ORGANISM_LAST_SEEN_DIR": str(seen)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, (proc.stdout + proc.stderr), seen / f"{PROBE_ID}.json"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_broken_sanitiser_can_never_soften_the_verdict(
    tmp_path: Path, shell: str
) -> None:
    """The cure that caught the disease it was curing.

    Round 2 normalised the status with `printf | tr 'A-Z' 'a-z'`. Round 3 showed
    what that costs: with `tr` returning non-zero the `||` fallback rewrote the
    status to `warning`, and with a `tr` that exits 0 printing NOTHING the empty
    arm rewrote it to `ok`. Either way an `error` — which the reader turns into
    `dead` — was published as something softer, by the very code written to stop
    statuses being published softer than they are.

    So the verdict path now runs no external command at all, and this pins it
    from the outside: sabotage `tr` in the caller's shell and the status must be
    untouched.
    """
    for sabotage, label in (("tr(){ return 23; }", "fails"), ("tr(){ :; }", "empty")):
        rc, out, sidecar = _script(
            tmp_path,
            shell,
            f"trsab-{shell}-{label}",
            f'source "$1"\n{sabotage}\norganism_heartbeat {PROBE_ID} error n\n',
        )
        assert rc == 0, out
        assert sidecar.exists(), f"{shell}/{label}: no sidecar: {out}"
        payload = json.loads(sidecar.read_text())
        assert payload["status"] == "error", (
            f"{shell}: a {label} `tr` softened the verdict to "
            f"{payload['status']!r} — the note may be lost, the verdict may not"
        )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_failing_date_does_not_kill_an_errexit_caller(
    tmp_path: Path, shell: str
) -> None:
    """`ts="$(date …)"` makes the ASSIGNMENT carry date's exit status.

    Under a caller's `set -e` that killed the caller — measured rc=42, with the
    line after the call never reached. Not hypothetical: `scripts/outbox-prune.sh`
    and `scripts/wr2-cron-wrapper.sh` both run `set -euo pipefail` and call this
    without `|| true`.

    Surviving is only half the contract, and the first version of this test got
    the other half backwards: it asserted the fallback timestamp was the EPOCH,
    on the reasoning that a ts we could not obtain should read STALE. Checked
    against the readers rather than reasoned about, that was worse than the
    disease — so this test now pins the opposite, and would fail against its own
    earlier expectation:

    - `sentinel-aggregate.py` computes `age = now - ts` and compares it against
      `expected_hb * DEAD_MULTIPLIER`. An EPOCH ts is an age of ~56 years: a
      confident, actionable DEAD verdict on an organ that is running fine.
    - `healer_receptor_registry.py` branches on the sidecar's EXISTENCE first
      (absent -> `never_armed`). Writing the fake ts overwrote the last GENUINE
      heartbeat and moved the organ out of the honest bucket.

    The fault was the clock; the receipt accused the organ. So: write nothing,
    keep the last true beat, and let a genuinely dead organ go stale on its own.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"date-{shell}",
        f'set -e -o pipefail\nsource "$1"\n'
        f'organism_heartbeat {PROBE_ID} ok "the last true beat"\n'
        f"date(){{ return 42; }}\n"
        f"organism_heartbeat {PROBE_ID} ok n\necho SURVIVED\n",
    )
    assert "SURVIVED" in out, f"{shell}: a failing date killed the caller (rc={rc})"
    assert rc == 0, out
    payload = json.loads(sidecar.read_text())
    assert payload["note"] == "the last true beat", (
        f"{shell}: a dead clock overwrote the last genuine heartbeat with "
        f"{payload!r} — that fabricates a death and names the wrong component"
    )
    assert not payload["ts"].startswith("1970-"), (
        f"{shell}: EPOCH ts is read as ~56 years of age by sentinel-aggregate.py, "
        "i.e. a false DEAD verdict on a healthy organ"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_dead_clock_with_no_previous_beat_leaves_the_honest_absence(
    tmp_path: Path, shell: str
) -> None:
    """The other half of the same contract, and the reason "write nothing" is safe.

    With no prior sidecar there is nothing to preserve, so the question is what
    the readers should see. `healer_receptor_registry.py` classifies a MISSING
    sidecar as `never_armed` — a distinct, honest bucket. Creating an EPOCH file
    instead moved the organ into `dead`, which pages. Absence is the truth here.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"date-noprev-{shell}",
        f'set -e -o pipefail\nsource "$1"\ndate(){{ return 42; }}\n'
        f"organism_heartbeat {PROBE_ID} ok n\necho SURVIVED\n",
    )
    assert "SURVIVED" in out, f"{shell}: rc={rc} {out}"
    assert not sidecar.exists(), (
        f"{shell}: a dead clock invented a sidecar ({sidecar.read_text()!r}); "
        "a never-armed organ must stay never_armed, not become dead"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_an_errexit_caller_survives_the_whole_call(tmp_path: Path, shell: str) -> None:
    """Innocence for the happy path under the options real callers actually set.

    The other cases in this file run without `set -e`, so none of them could have
    caught the date defect above. Real wrappers run `set -euo pipefail`.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"errexit-{shell}",
        f'set -euo pipefail\nsource "$1"\norganism_heartbeat {PROBE_ID} ok "rc=42 timeout"\n'
        "echo SURVIVED\n",
    )
    assert "SURVIVED" in out, f"{shell}: rc={rc} {out}"
    assert json.loads(sidecar.read_text())["status"] == "ok"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
@pytest.mark.parametrize(
    "reserved",
    [
        # the names the function used to declare — a revert of the namespacing
        # is caught by whichever one it brings back
        "_rest", "id", "hb_status", "note", "ts", "tmp", "hb_path",
        # …and the ones it declares TODAY. Round 5 showed the namespace only
        # lowered the odds: `readonly _organism_hb_id` killed the caller exactly
        # as `readonly id` had. Any name can be made readonly by someone, so the
        # guarantee cannot come from choosing better names — it comes from the
        # wrapper that absorbs whatever the body does.
        "_organism_hb_id", "_organism_hb_status", "_organism_hb_note",
        "_organism_hb_ts", "_organism_hb_len", "_organism_hb_dir",
        "_organism_hb_tmp", "_organism_hb_path",
    ],
)
def test_an_internal_local_name_cannot_kill_the_caller(
    tmp_path: Path, shell: str, reserved: str
) -> None:
    """`local X` aborts a bash caller that has `readonly X` — for EVERY X.

    This test used to name one word, `_rest`, because that was the one that bit.
    Deleting that single temporary read like a cure and was not: `id`,
    `hb_status`, `note` and `ts` were each still declared bare, and each still
    killed a caller that had reserved that word — measured, all four, rc=1
    `readonly variable`, with the line after the call never reached. One name is
    an instance; the rule is the class.

    The parameters below are therefore the words the function USED to declare, so
    a revert of the namespacing is caught by whichever one it brings back.
    """
    rc, out, _ = _script(
        tmp_path,
        shell,
        f"ro-{shell}-{reserved}",
        f'set -e\nsource "$1"\nreadonly {reserved}=caller-sentinel\n'
        f"organism_heartbeat {PROBE_ID} ok n\necho SURVIVED\n",
    )
    assert "SURVIVED" in out, (
        f"{shell}: a caller with `readonly {reserved}` was killed by its own "
        f"heartbeat writer (rc={rc}): {out}"
    )
    assert rc == 0, out


def test_every_local_the_function_declares_is_namespaced() -> None:
    """Structural backstop for the namespacing — hardened after round 5.

    The first version regex-matched `local <name>` per line and stopped the scan
    at the first `}` in column zero. All of these defeated it while staying legal
    shell, and each would have reopened the collision class in silence:

        local _organism_hb_ts retries=0      # second name on the same line
        local _organism_hb_ts \
              retries=0                      # continued onto the next line
        typeset retries=0                    # a synonym of local
        declare retries=0                    # another

    The namespace is not what keeps the caller alive (the wrapper is — see
    test_an_internal_local_name_cannot_kill_the_caller). It is what keeps this
    library from stepping on a caller's variable, which is a separate promise
    and still worth enforcing.
    """
    src = HB_LIB.read_text()
    # Continuations first, so a declaration split across lines is one line here.
    flat = re.sub(r"\\\n\s*", " ", src)
    body_start = flat.index("_organism_heartbeat_write() {")
    body = flat[body_start:]

    declared: list[str] = []
    offenders: list[str] = []
    for line in body.splitlines():
        code = line.split("#", 1)[0]
        m = re.match(r"\s*(?:local|typeset|declare)\s+(.*)", code)
        if not m:
            continue
        for word in m.group(1).split():
            if word.startswith("-"):      # flags: `local -r`, `typeset -i`
                continue
            name = word.split("=", 1)[0]
            if not name:
                continue
            declared.append(name)
            if not name.startswith("_organism_hb_"):
                offenders.append(name)

    assert not offenders, (
        "every name declared inside the heartbeat writer must be prefixed "
        f"`_organism_hb_` so it cannot shadow a caller's variable: {offenders}"
    )
    # An empty scan passes the loop above and proves nothing — the same
    # empty-set-as-clean-bill trap this file guards elsewhere.
    assert len(declared) >= 6, f"only {len(declared)} declarations found — scan is broken"


def test_the_public_entry_point_is_a_wrapper_that_cannot_propagate_failure() -> None:
    """The contract is structural, and this pins the structure.

    Every round of review found another statement able to kill the caller before
    `return 0`: `${1:?}`, a bare `ts="$(date …)"`, `local` on a name the caller
    had made readonly, and the `&& mv` AND-list at the end. Enumerating them is
    a losing game — the guarantee has to hold for statements nobody has thought
    of yet. So `organism_heartbeat` is a thin wrapper that calls the writer and
    swallows its status, and this test fails if that shape is edited away.
    """
    src = HB_LIB.read_text()
    entry = src[src.index("organism_heartbeat() {") : src.index("_organism_heartbeat_write() {")]
    assert "( _organism_heartbeat_write \"$@\" ) || :" in entry, (
        "the entry point must run the writer in a SUBSHELL and absorb its status. "
        "`|| :` alone is not enough: it absorbs an exit STATUS, and a caller who "
        "has made one of our names readonly makes the writer hit a plain "
        "ASSIGNMENT to that name, which is FATAL in a non-interactive shell — "
        "there is no status left to absorb. Measured on 3 of the 8 names."
    )
    assert "2>/dev/null" not in entry, (
        "stderr must NOT be swallowed here — a heartbeat that cannot be written "
        "has to be able to say so, or the silence is itself a green that lies"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
@pytest.mark.parametrize(
    "word", ["unhealthy", "panic", "killed", "down", "aborted", "exception"]
)
def test_an_unambiguous_failure_word_is_not_softened_to_warning(
    tmp_path: Path, shell: str, word: str
) -> None:
    """The failure-synonym list was arbitrary, and one entry made it incoherent.

    `fail`/`failed`/`failure`/`fatal`/`crash`/`crashed`/`dead`/`timeout` mapped to
    `error`, while `down`, `panic`, `killed`, `aborted`, `exception` — and
    `unhealthy` — fell through to the unknown arm and published as `warning`.
    `unhealthy` is the direct negation of `healthy`, which the SAME list accepts
    verbatim: a caller writing the negative form of an accepted word had its
    verdict quietly softened.

    Unknown strings still degrade to `warning` on purpose (see the innocence case
    below) — this is about words that are not ambiguous.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"word-{shell}-{word}",
        f'source "$1"\norganism_heartbeat {PROBE_ID} {word} "probe failed"\n',
    )
    assert rc == 0, out
    assert json.loads(sidecar.read_text())["status"] == "error", (
        f"{shell}: {word!r} published as "
        f"{json.loads(sidecar.read_text())['status']!r}, not error"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_an_unrecognised_word_still_only_reaches_warning(
    tmp_path: Path, shell: str
) -> None:
    """Innocence for the arm above: widening the failure list must not widen it
    into "anything I do not recognise is a death". An unknown string is not
    evidence of failure, and `error` pages. `warning` is visible without paging.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"unknown-{shell}",
        f'source "$1"\norganism_heartbeat {PROBE_ID} rebalancing n\n',
    )
    assert rc == 0, out
    assert json.loads(sidecar.read_text())["status"] == "warning"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_sanitiser_that_loses_bytes_cannot_eat_the_callers_own_text(
    tmp_path: Path, shell: str
) -> None:
    """The sentinel strip was `${note%X}`, which trusted a zero exit from `tr`.

    A `tr` that exits zero while dropping its last byte turned a note of `AX`
    into `A`: the sentinel was gone, so the strip ate the caller's own `X`, and
    nothing said so. Testing `*X)` alone does NOT catch it — `AX` plus the
    sentinel is `AXX`, and one dropped byte leaves `AX`, still ending in `X`.

    The proof is length: `tr -c <set> ' '` substitutes and never deletes, so its
    output cannot be shorter than its input. Shorter means bytes went missing.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"drop-{shell}",
        f'source "$1"\ntr(){{ sed "s/X$//"; }}\n'
        f'organism_heartbeat {PROBE_ID} ok "AX"\n',
    )
    assert rc == 0, out
    note = json.loads(sidecar.read_text())["note"]
    assert note != "A", (
        f"{shell}: a byte-dropping sanitiser silently ate the caller's trailing X"
    )
    assert "dropped" in note, f"{shell}: expected the explicit marker, got {note!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
@pytest.mark.parametrize("note", ["AX", "X", "", "caffè X", "plain"])
def test_a_working_sanitiser_never_declares_a_note_lost(
    tmp_path: Path, shell: str, note: str
) -> None:
    """Innocence for the length check: it must not fire on real input.

    The comparison is one-sided on purpose. Under UTF-8 a multibyte character
    counts as ONE in `${#...}` while `tr` turns each of its bytes into a space,
    so a legitimate run can only ever come out LONGER — hence `caffè X` here,
    which would trip a naive equality check.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"keep-{shell}-{abs(hash(note)) % 9973}",
        f'source "$1"\norganism_heartbeat {PROBE_ID} ok "{note}"\n',
    )
    assert rc == 0, out
    assert "dropped" not in json.loads(sidecar.read_text())["note"], (
        f"{shell}: a healthy sanitiser declared {note!r} lost"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_the_id_whitelist_is_ascii_not_collation(tmp_path: Path, shell: str) -> None:
    """`[a-zA-Z]` is a COLLATION range, and its meaning depends on the locale.

    Measured: `LC_ALL=it_IT.UTF-8 bash -c 'id=éa; echo "${id//[a-zA-Z0-9_.]/}"'`
    prints nothing — bash accepted an accented letter into a whitelist that
    exists to keep shell metacharacters and traversal out of a filesystem path —
    while zsh rejected it. A safety whitelist whose meaning depends on the
    caller's locale is not a whitelist, so the set is enumerated now.

    FAILS CLOSED on the environment. Setting `LC_ALL=it_IT.UTF-8` does not make
    the locale exist: where it has not been generated the shell warns, falls back
    to C collation, and `[a-zA-Z]` then rejects `é` all by itself — so every
    assertion below passes WITH THE DEFECT RESTORED. `ubuntu-latest` is a moving
    label and no job step generated this locale, so that was the live state, not
    a hypothetical.

    The fix is a control experiment: before trusting a negative, prove the
    apparatus can produce a POSITIVE. Under a genuinely collating locale the OLD
    pattern absorbs `é`; if it does not, this machine cannot exhibit the defect
    and the test says so instead of nodding. The control is bash-only by
    measurement — zsh does not collate here (`[é]` vs bash's `[]`), which is why
    the original bug was invisible from a zsh prompt.
    """
    if shell == "bash":
        control = subprocess.run(
            [
                shell,
                "-c",
                'shopt -u globasciiranges; v=éa; printf "[%s]" "${v//[a-zA-Z0-9_.]/}"',
            ],
            env={**os.environ, "LC_ALL": LOCALE_UTF8},
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert control.stdout == "[]", (
            f"control experiment failed: under LC_ALL={LOCALE_UTF8} this bash did "
            f"not collate (`{control.stdout}`, stderr={control.stderr.strip()!r}). "
            "The locale is probably not generated here, so the assertions below "
            "would pass even with `[a-zA-Z0-9_.]` restored. Generate the locale "
            "(CI does this explicitly) rather than trusting this test's silence."
        )

    seen = tmp_path / f"seen-locale-{shell}"
    script = tmp_path / f"locale-{shell}.sh"
    bash_collation = "shopt -u globasciiranges\n" if shell == "bash" else ""
    script.write_text(
        bash_collation + 'source "$1"\norganism_heartbeat "$2" error n\n',
        encoding="utf-8",
    )
    for bad_id in ("éa", "aé", "pro.café"):
        proc = subprocess.run(
            [shell, str(script), str(HB_LIB), bad_id],
            env={
                **os.environ,
                "ORGANISM_LAST_SEEN_DIR": str(seen),
                "LC_ALL": LOCALE_UTF8,
            },
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        written = sorted(p.name for p in seen.glob("*")) if seen.exists() else []
        assert written == [], (
            f"{shell}: non-ASCII id {bad_id!r} passed the whitelist: {written}"
        )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_trailing_newline_survives_and_stays_valid_json(
    tmp_path: Path, shell: str
) -> None:
    """Command substitution eats ALL trailing newlines, so a note ending in one
    lost it silently even though `\\n` is in the keep-set and the escape phase
    handles it. A sentinel character carries it across.

    Asserted on the PARSED value, not on the printed line: `echo` in zsh
    interprets `\\n`, so eyeballing the file through it shows a line break where
    the bytes are a backslash and an `n`. That display artefact cost a false
    alarm during this very fix.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"nl-{shell}",
        f'source "$1"\nn=$\'tail\\n\'\norganism_heartbeat {PROBE_ID} ok "$n"\n',
    )
    assert rc == 0, out
    payload = json.loads(sidecar.read_text())  # raises if the escape regressed
    assert payload["note"] == "tail\n", f"{shell}: note={payload['note']!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_clock_that_answers_with_garbage_is_not_believed(
    tmp_path: Path, shell: str
) -> None:
    """`|| printf ''` does not unsay what a command already printed.

    `date(){ printf BROKEN; return 42; }` left `BROKEN` inside the command
    substitution, and the guard that followed only asked whether the result was
    EMPTY — so `"ts":"BROKEN"` went into the sidecar, over the last good beat.
    Emptiness was a proxy for "the clock answered"; the answer is the entity, so
    its SHAPE is now checked.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"garbage-clock-{shell}",
        f'set -e -o pipefail\nsource "$1"\n'
        f'organism_heartbeat {PROBE_ID} ok "the last true beat"\n'
        f'date(){{ printf BROKEN; return 42; }}\n'
        f"organism_heartbeat {PROBE_ID} ok n\necho SURVIVED\n",
    )
    assert "SURVIVED" in out, f"{shell}: rc={rc} {out}"
    payload = json.loads(sidecar.read_text())
    assert payload["ts"] != "BROKEN", f"{shell}: a broken clock's stdout became the ts"
    assert payload["note"] == "the last true beat", (
        f"{shell}: the garbage timestamp overwrote a good heartbeat: {payload!r}"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_clock_failure_is_reported_not_merely_survived(
    tmp_path: Path, shell: str
) -> None:
    """Silence is the failure mode this whole organ exists to prevent.

    The first cure for the EPOCH defect returned 0 and wrote nothing — correct
    about the sidecar, and a green that lies to everyone above it: the caller,
    launchd and the operator all saw an ordinary success while the organ drifted
    toward stale for a fault that was never the organ's.
    """
    rc, out, _ = _script(
        tmp_path,
        shell,
        f"clock-voice-{shell}",
        f'source "$1"\ndate(){{ return 42; }}\n'
        f"organism_heartbeat {PROBE_ID} ok n\n",
    )
    assert rc == 0, out
    assert "clock unavailable" in out, (
        f"{shell}: a heartbeat that could not be written said nothing: {out!r}"
    )
    assert PROBE_ID in out, f"{shell}: the warning does not name the organ: {out!r}"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_failed_rename_does_not_kill_an_errexit_caller(
    tmp_path: Path, shell: str
) -> None:
    """`set -e` does not spare the LAST command of an `&&` list.

    The write was `{ printf … } > tmp && mv tmp path`. A failing `mv` — full
    disk, a directory in the way, a racing sweeper — made the whole list fail
    one line before `return 0`, and took the caller with it.
    """
    rc, out, _ = _script(
        tmp_path,
        shell,
        f"mv-fail-{shell}",
        f'set -euo pipefail\nsource "$1"\nmv(){{ return 42; }}\n'
        f"organism_heartbeat {PROBE_ID} ok n\necho SURVIVED\n",
    )
    assert "SURVIVED" in out, f"{shell}: a failed rename killed the caller (rc={rc})"
    assert rc == 0, out


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_sanitiser_that_corrupts_the_sentinel_at_equal_length_is_caught(
    tmp_path: Path, shell: str
) -> None:
    """The length invariant has a blind spot, and identity has the other one.

    A `tr` that SUBSTITUTES the last byte instead of dropping it keeps the
    length: `AB` -> `ABX` -> `ABY` passes the length test, `${note%X}` removes
    nothing, and the corrupted sentinel is published as if it were the caller's
    text. Length catches deletion; the suffix catches corruption; neither alone
    covers both, and both were demonstrated on this code one round apart.
    """
    rc, out, sidecar = _script(
        tmp_path,
        shell,
        f"corrupt-{shell}",
        f'source "$1"\ntr(){{ sed "s/X$/Y/"; }}\n'
        f'organism_heartbeat {PROBE_ID} ok "AB"\n',
    )
    assert rc == 0, out
    note = json.loads(sidecar.read_text())["note"]
    assert note != "ABY", f"{shell}: a corrupted sentinel was published verbatim"
    assert "dropped" in note, f"{shell}: expected the explicit marker, got {note!r}"
