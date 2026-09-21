"""tg_gateway_census: every entry is counted by the gateway its own code resolves, never by name."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tg_gateway_census.py"
spec = importlib.util.spec_from_file_location("tg_gateway_census", SCRIPT)
census_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census_mod)

SH_RESOLVER = '''#!/bin/bash
send() {
    local gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/nuzantara/scripts/tg_notify.py"
    "$gateway" --tier p0 "$1"
}
"$@" || send failed
'''

AGENT_JOB = '''from pathlib import Path
HOME = Path.home()

def _tg_gateway():
    explicit = os.environ.get("TG_NOTIFY_BIN", "")
    candidates = [Path(explicit)] if explicit else []
    candidates += [
        Path(__file__).resolve().parent.parent / "tg_notify.py",
        HOME / "nuzantara" / "scripts" / "tg_notify.py",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None
'''

JOB_HEALTH = '''import os, subprocess
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def send_alert(results):
    """Route alerts via the tg_notify gateway."""
    Path({marker!r}).write_text("the sending function ran")
    gateway = PROJECT_ROOT / "scripts" / "tg_notify.py"
    if not gateway.is_file():
        gateway = Path(os.path.expanduser("~/nuzantara/scripts/tg_notify.py"))
    subprocess.run(["python3", str(gateway), "--tier", "p0", "x"])
'''

RUN_SH = '''#!/bin/bash
JOB="${{1:?usage: run.sh <job-name>}}"
SCRIPT_DIR="{home}/scripts/cron-agent-python"
SCRIPT="$SCRIPT_DIR/${{JOB//-/_}}.py"
exec /usr/bin/python3 "$SCRIPT"
'''


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "scripts").mkdir(parents=True)
    (h / "nuzantara" / "scripts").mkdir(parents=True)
    (h / "Desktop").mkdir()
    (h / "scripts" / "tg_notify.py").write_text("# the 18-Aug fork, no routing tier\n")
    (h / "nuzantara" / "scripts" / "tg_notify.py").write_text("gateway_routed = True\n")
    (h / "Desktop" / "nuzantara").symlink_to(h / "nuzantara")
    monkeypatch.setenv("HOME", str(h))
    return h


def run(home: Path, crontab: str) -> dict:
    return census_mod.census(crontab, str(home))


def gateways(out: dict, i: int = 0) -> list[tuple[str, bool]]:
    return [(g["path"], g["routes"]) for g in out["entries"][i]["gateways"]]


def test_file_symlink_keeps_dirname_at_the_link(home):
    """A1 — ~/scripts/cron-state.sh is a symlink to the checkout, and still reaches the fork."""
    (home / "nuzantara" / "scripts" / "cron-state.sh").write_text(SH_RESOLVER)
    (home / "scripts" / "cron-state.sh").symlink_to(home / "nuzantara" / "scripts" / "cron-state.sh")
    out = run(home, "*/5 * * * * ~/scripts/cron-state.sh job /bin/true\n")
    assert gateways(out) == [(str(home / "scripts" / "tg_notify.py"), False)]
    assert out["summary"]["reach_nonrouting"] == 1


def test_directory_symlink_reaches_the_checkout(home):
    """A2 — the same file through the Desktop directory symlink routes."""
    (home / "nuzantara" / "scripts" / "cron-wrapper.sh").write_text(SH_RESOLVER)
    out = run(home, "0 * * * * $HOME/Desktop/nuzantara/scripts/cron-wrapper.sh job\n")
    assert gateways(out) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]


def test_the_producers_own_fallback_line_decides(home):
    """A3 — no sibling gateway: the fallback runs, and it is the file's line, not a model of it."""
    (home / "other").mkdir()
    wrapper = home / "other" / "w.sh"
    wrapper.write_text(SH_RESOLVER)
    out = run(home, "0 * * * * ~/other/w.sh\n")
    assert gateways(out) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]
    wrapper.write_text(SH_RESOLVER.replace("$HOME/nuzantara/scripts/tg_notify.py", "$HOME/scripts/tg_notify.py"))
    out = run(home, "0 * * * * ~/other/w.sh\n")
    assert gateways(out) == [(str(home / "scripts" / "tg_notify.py"), False)]


def test_run_sh_dispatch_and_sibling_import_reach_the_fork(home):
    """A4 — run.sh <job> -> <job>.py -> import agent_job -> _tg_gateway() -> ~/scripts/tg_notify.py."""
    d = home / "scripts" / "cron-agent-python"
    d.mkdir()
    (d / "run.sh").write_text(RUN_SH.format(home=home))
    (d / "agent_job.py").write_text(AGENT_JOB)
    (d / "fly_watcher.py").write_text("from agent_job import _tg_gateway\n")
    (d / "quiet_job.py").write_text("print('no alerts here')\n")
    out = run(home, "*/15 * * * * bash ~/scripts/cron-agent-python/run.sh fly-watcher\n"
                    "0 3 * * * bash ~/scripts/cron-agent-python/run.sh quiet-job\n")
    assert gateways(out, 0) == [(str(home / "scripts" / "tg_notify.py"), False)]
    assert gateways(out, 1) == []
    assert out["summary"]["reach_none"] == 1


def test_inline_python_slice_runs_without_the_sending_function(home, tmp_path):
    """A5 — only the assignment and its fallback run; the function that sends never does."""
    marker = tmp_path / "sent"
    (home / "nuzantara" / "scripts" / "job_health.py").write_text(JOB_HEALTH.format(marker=str(marker)))
    out = run(home, "*/10 * * * * python3 ~/Desktop/nuzantara/scripts/job_health.py\n")
    assert gateways(out) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]
    assert not marker.exists()


@pytest.mark.parametrize("body", [
    "from tg_notify import send\n",
    "GW = ROOT_DIR + '/tg_notify.py'\n",
])
def test_an_unmodelled_reference_is_unresolved_and_the_exit_says_so(home, tmp_path, body):
    """A6 — never guessed: the entry is UNRESOLVED and main() exits 3."""
    (home / "scripts" / "odd.py").write_text(body)
    ct = tmp_path / "ct"
    ct.write_text("0 * * * * python3 ~/scripts/odd.py\n")
    out = run(home, ct.read_text())
    assert out["entries"][0]["unresolved"]
    assert census_mod.main(["--crontab", str(ct)]) == 3


def test_comments_env_lines_and_dead_paths(home):
    """A7 — only active schedule lines count; a missing entry script never runs."""
    (home / "scripts" / "ok.sh").write_text("#!/bin/bash\ntrue\n")
    out = run(home, "MAILTO=x\n# 0 * * * * ~/scripts/ok.sh\n\n0 * * * * ~/scripts/ok.sh\n"
                    "0 1 * * * ~/Desktop/gone/cron-wrapper.sh kb-ingest\n")
    assert [e["line"] for e in out["entries"]] == [4, 5]
    assert out["summary"] == {"active": 2, "not_runnable": 1, "unresolved": 0, "reach_nonrouting": 0,
                              "reach_routing_only": 0, "reach_missing": 0, "reach_none": 1}


def test_a_message_naming_the_gateway_is_not_a_resolution(home):
    """Innocence: a log line mentioning tg_notify.py neither resolves nor goes UNRESOLVED."""
    (home / "scripts" / "quiet.sh").write_text('#!/bin/bash\necho "tg_notify.py is not called here"\n')
    out = run(home, "0 * * * * ~/scripts/quiet.sh\n")
    assert gateways(out) == [] and not out["entries"][0]["unresolved"]


def test_a_relative_script_is_anchored_by_the_entrys_own_cd(home):
    """`bash -c 'cd <abs> && python3 scripts/x.py'` resolves against that cd; without one it is UNRESOLVED."""
    (home / "nuzantara" / "scripts" / "job_health.py").write_text(JOB_HEALTH.format(marker="/nonexistent/m"))
    out = run(home, "0 * * * * bash -c 'cd ~/Desktop/nuzantara && python3 scripts/job_health.py'\n"
                    "0 * * * * python3 scripts/job_health.py\n")
    assert gateways(out, 0) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]
    assert not out["entries"][0]["unresolved"] and out["entries"][1]["unresolved"]


def test_a_variable_built_gateway_uses_the_variable_or_goes_unresolved(home):
    """`"$DIR/tg_notify.py"` is DIR's value, never the phantom absolute path /tg_notify.py."""
    (home / "scripts" / "known.sh").write_text(f'#!/bin/bash\nDIR="{home}/nuzantara/scripts"\n"$DIR/tg_notify.py" --tier p0 x\n')
    (home / "scripts" / "unknown.sh").write_text('#!/bin/bash\n"$DIR/tg_notify.py" --tier p0 x\n')
    out = run(home, "0 * * * * ~/scripts/known.sh\n0 * * * * ~/scripts/unknown.sh\n")
    assert gateways(out, 0) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]
    assert gateways(out, 1) == [] and out["entries"][1]["unresolved"]


def test_a_relative_child_is_placed_by_the_scripts_own_cd(home):
    """`cd "$(dirname "$0")" && python3 job.py` is followed; with no cd it is UNRESOLVED, never skipped."""
    (home / "scripts" / "job.py").write_text("from agent_job import _tg_gateway\n")
    (home / "scripts" / "agent_job.py").write_text(AGENT_JOB)
    (home / "scripts" / "with_cd.sh").write_text('#!/bin/bash\ncd "$(dirname "$0")" || exit 1\npython3 job.py\n')
    (home / "scripts" / "no_cd.sh").write_text("#!/bin/bash\npython3 job.py\n")
    out = run(home, "0 * * * * ~/scripts/with_cd.sh\n0 * * * * ~/scripts/no_cd.sh\n")
    assert gateways(out, 0) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]
    assert not out["entries"][0]["unresolved"] and out["entries"][1]["unresolved"]


def test_nothing_in_a_resolver_can_run_a_command(home, tmp_path):
    """Hostile shapes are refused, not run: a Python alias, bash arithmetic, a hostile argument."""
    m = tmp_path / "pwned"
    (home / "scripts" / "alias.py").write_text(
        f"from pathlib import Path\nget = Path.write_text\n"
        f"GW = get(Path({str(m)!r}), 'x') or Path('/x/tg_notify.py')\n")
    (home / "scripts" / "arith.sh").write_text(
        f'#!/bin/bash\nx="$"\nz="a[${{x}}(touch {m})]"\nw="${{a[z]}}"\nG="${{w}}/tg_notify.py"\n')
    (home / "scripts" / "arg.sh").write_text('#!/bin/bash\nJ="${a[$1]}"\n')
    run(home, f"0 * * * * python3 ~/scripts/alias.py\n0 * * * * ~/scripts/arith.sh\n"
              f"0 * * * * ~/scripts/arg.sh 'b[$(touch {m})]'\n")
    assert not m.exists()


def test_case_arms_and_cd_into_a_variable_are_decided_by_the_disk(home):
    """REPO set in case arms: every value is tried with the script's own cd; only one exists here."""
    (home / "nuzantara" / "scripts" / "job.py").write_text(JOB_HEALTH.format(marker="/nonexistent/m"))
    (home / "scripts" / "loop.sh").write_text(
        '#!/bin/bash\ncase "$(whoami)" in\n    nuzantara)  REPO="$HOME/nuzantara" ;;\n'
        '    other)      REPO="$HOME/Projects/nuzantara" ;;\nesac\ncd "$REPO"\nexec "$PY" scripts/job.py\n')
    out = run(home, "0 * * * * ~/scripts/loop.sh\n")
    assert gateways(out) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]
    assert not out["entries"][0]["unresolved"]


ALERTER = '''import os

def _gateway_script():
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tg_notify.py")
    if os.path.isfile(here):
        return here
    return os.path.join(os.environ.get("NUZANTARA_ROOT", ""), "scripts", "tg_notify.py")
'''

SENTINEL = '''import sys
from pathlib import Path
REPO: "Path" = Path(__file__).resolve().parents[1]

def send(message):
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        from sentinel_lib import alerter
        return alerter.send_alert(message)
    except Exception:
        gateway = REPO / "scripts" / "tg_notify.py"
        if not gateway.exists():
            return False

def selftest():
    if not (REPO / "scripts" / "tg_notify.py").exists():
        print("gateway missing")
'''


def test_a_package_reached_through_the_files_own_sys_path(home):
    """sys.path.insert(REPO/scripts) + `from sentinel_lib import alerter`; the except fallback; a probe."""
    (home / "nuzantara" / "scripts" / "sentinel_lib").mkdir()
    (home / "nuzantara" / "scripts" / "sentinel_lib" / "__init__.py").write_text("")
    (home / "nuzantara" / "scripts" / "sentinel_lib" / "alerter.py").write_text(ALERTER)
    (home / "nuzantara" / "apps").mkdir()
    (home / "nuzantara" / "apps" / "sentinel.py").write_text(SENTINEL)
    out = run(home, "0 * * * * python3 ~/nuzantara/apps/sentinel.py\n")
    e = out["entries"][0]
    assert not e["unresolved"]
    assert [(g["path"], sorted(os.path.basename(v) for v in g["via"])) for g in e["gateways"]] == [
        (str(home / "nuzantara" / "scripts" / "tg_notify.py"), ["alerter.py", "sentinel.py"])]


def test_a_script_spawned_through_a_path_expression_is_followed(home):
    """subprocess.run(["bash", str(child)]) with child = REPO / ... is evaluated, not skipped."""
    (home / "nuzantara" / "scripts" / "child.sh").write_text(SH_RESOLVER)
    (home / "nuzantara" / "apps").mkdir()
    (home / "nuzantara" / "apps" / "parent.py").write_text(
        "import subprocess\nfrom pathlib import Path\nREPO = Path(__file__).resolve().parents[1]\n"
        "def go():\n    child = REPO / 'scripts' / 'child.sh'\n    subprocess.run(['bash', str(child)])\n")
    out = run(home, "0 * * * * python3 ~/nuzantara/apps/parent.py\n")
    assert gateways(out) == [(str(home / "nuzantara" / "scripts" / "tg_notify.py"), True)]


def test_the_counterexamples_of_the_first_red_team(home, tmp_path):
    """Codex on 25a935791c: each input below once produced a wrong count with exit 0."""
    sc, nz = home / "scripts", home / "nuzantara" / "scripts"
    hc = sc / "healthcheck"  # no extension, a shebang
    hc.write_text(f'#!/bin/bash\n"{nz}/tg_notify.py" x\n')
    for k in range(9):  # job0 -> job1 -> ... -> job8 -> gateway: deeper than MAX_DEPTH
        nxt = f'"{sc}/job{k + 1}.sh"' if k < 8 else f'"{nz}/tg_notify.py" x'
        (sc / f"job{k}.sh").write_text(f"#!/bin/bash\n{nxt}\n")
    (home / "other").mkdir()
    (home / "other" / "lib.sh").write_text('#!/bin/bash\ngateway="$(dirname "$0")/tg_notify.py"\n')
    (home / "other" / "arglib.sh").write_text('#!/bin/bash\nDIR="$1"\nG="$DIR/tg_notify.py"\n')
    (sc / "caller.sh").write_text(f'#!/bin/bash\nsource "{home}/other/arglib.sh"\n')
    (sc / "bs.sh").write_text('#!/bin/bash\ngateway="$(dirname "${BASH_SOURCE[0]}")/tg_notify.py"\n')
    (sc / "envjob.py").write_text("import os\n\ndef gateway():\n"
                                  f"    return os.environ.get('TG_NOTIFY_BIN', {str(sc / 'tg_notify.py')!r})\n")
    (home / "gw").mkdir()
    (home / "gw" / "impl.py").write_text("gateway_routed = True\n")
    (home / "gw" / "tg_notify.py").symlink_to(home / "gw" / "impl.py")
    out = run(home, "\n".join([
        f"0 * * * * {hc}",
        f"0 * * * * bash {sc}/job0.sh",
        f"0 * * * * echo {nz}/tg_notify.py",
        f"0 * * * * bash -c 'source {home}/other/lib.sh' {sc}/job.sh",
        f"0 * * * * bash {sc}/caller.sh {nz}",
        f"0 * * * * {sc}/bs.sh",
        f"TG_NOTIFY_BIN={nz}/tg_notify.py",
        f"0 * * * * python3 {sc}/envjob.py",
        f"0 * * * * python3 {home}/gw/tg_notify.py",
    ]) + "\n")
    e = out["entries"]
    canon, fork = str(nz / "tg_notify.py"), str(sc / "tg_notify.py")
    assert [g["path"] for g in e[0]["gateways"]] == [canon]
    assert e[1]["unresolved"]
    assert e[2]["gateways"] == [] and not e[2]["unresolved"]
    assert [g["path"] for g in e[3]["gateways"]] == [fork]
    assert [g["path"] for g in e[4]["gateways"]] == [canon]
    assert [g["path"] for g in e[5]["gateways"]] == [fork]
    assert [g["path"] for g in e[6]["gateways"]] == [canon]
    assert [(g["path"], g["routes"]) for g in e[7]["gateways"]] == [(str(home / "gw" / "impl.py"), True)]


def test_the_escapes_of_the_first_red_team_do_not_run(home, tmp_path):
    m = tmp_path / "escaped"
    (home / "scripts" / "arith.sh").write_text('#!/bin/bash\nN="$[$1]"\n')
    (home / "scripts" / "esc.py").write_text(
        "import os\n\ndef gateway():\n"
        f"    [get('touch {m}') for get in [os.path.abspath.__globals__['os'].system]]\n"
        "    return '/x/tg_notify.py'\n")
    run(home, f"0 * * * * bash ~/scripts/arith.sh 'a[$(touch {m})]'\n0 * * * * python3 ~/scripts/esc.py\n")
    assert not m.exists()


def test_the_findings_of_the_second_red_team(home):
    """A sibling function's local never shadows the module value; a relative gateway placed by cd is not UNRESOLVED."""
    sc = home / "scripts"
    (sc / "real_dir").mkdir()
    (sc / "decoy_dir").mkdir()
    (sc / "real_dir" / "tg_notify.py").write_text("gateway_routed = True\n")
    (sc / "decoy_dir" / "tg_notify.py").write_text("\n")
    (sc / "sender.py").write_text(f'BASE = "{sc}/real_dir"\n\ndef helper():\n    BASE = "{sc}/decoy_dir"\n'
                                  f'    return BASE\n\nNOTIFY_BIN = BASE + "/tg_notify.py"\n')
    (sc / "wrapper.sh").write_text('#!/bin/bash\ncd "$(dirname "$0")"\nsource ./tg_notify.py\n')
    out = run(home, f"0 * * * * python3 {sc}/sender.py\n0 * * * * {sc}/wrapper.sh\n")
    assert [g["path"] for g in out["entries"][0]["gateways"]] == [str(sc / "real_dir" / "tg_notify.py")]
    assert [g["path"] for g in out["entries"][1]["gateways"]] == [str(sc / "tg_notify.py")]
    assert not out["entries"][1]["unresolved"]
