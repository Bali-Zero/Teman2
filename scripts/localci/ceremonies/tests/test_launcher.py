from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from .conftest import SHIPPED


GOOD = "a" * 40


@pytest.mark.parametrize(
    ("args", "case"),
    [
        ((), "argc"),
        (("abc", "C3"), "non-hex"),
        ((GOOD, "bad"), "bad-name"),
        ((GOOD, "C3;id"), "shell-text"),
        ((GOOD, "../"), "traversal"),
        ((GOOD, "C3-bootstrap", "extra"), "argc-three"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_argv_refusals_are_64(rig_factory, args, case):
    rig = rig_factory()
    assert rig.run_args(args).returncode == 64, case


def _guilt(rig, case: str) -> None:
    if case.startswith("mode-"):
        rig.probe.chmod(int(case.removeprefix("mode-"), 8))
    elif case == "acl":
        subprocess.run(["/bin/chmod", "+a", f"{rig.user} allow write", str(rig.probe)], check=True)
    elif case == "dangling-link":
        rig.link.unlink(); rig.link.symlink_to(rig.trust / "missing")
    elif case == "usr-local-link":
        rig.link.unlink(); rig.link.symlink_to("/usr/local")
    elif case == "private-tmp-link":
        rig.link.unlink(); rig.link.symlink_to("/private/tmp")
    elif case == "writable-parent":
        rig.target.parent.chmod(0o775)


@pytest.mark.parametrize(
    "case",
    ["innocent", "mode-0775", "mode-0757", "mode-0777", "acl", "dangling-link", "usr-local-link", "private-tmp-link", "writable-parent"],
)
def test_trust_walk_table(rig_factory, case):
    rig = rig_factory()
    if case != "innocent":
        _guilt(rig, case)
    got = rig.run(rig.m2, "C3-bootstrap")
    assert got.returncode == (0 if case == "innocent" else 65), (case, got.stderr)


@pytest.mark.parametrize("case", ["dir-mode-0775", "file-mode-0757", "acl"])
def test_executable_closure_rejects_writable_or_acl_entries(rig_factory, case):
    rig = rig_factory()
    if case == "dir-mode-0775":
        rig.git_core.chmod(0o775)
    elif case == "file-mode-0757":
        rig.git_core_probe.chmod(0o757)
    else:
        subprocess.run(["/bin/chmod", "+a", f"{rig.user} allow write", str(rig.git_core_probe)], check=True)
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 65


@pytest.mark.parametrize("key", ["GIT_DIR", "GIT_CONFIG_PARAMETERS", "GIT_EXEC_PATH"])
def test_git_commands_ignore_hostile_caller_env(rig_factory, key):
    rig = rig_factory()
    clean = rig.run(rig.m2, "C3-bootstrap")
    hostile_value = {
        "GIT_DIR": str(rig.root / "hostile.git"),
        "GIT_CONFIG_PARAMETERS": "'credential.helper'='!false'",
        "GIT_EXEC_PATH": str(rig.root / "hostile-exec"),
    }[key]
    hostile = rig.run(rig.m2, "C3-bootstrap", caller_env={key: hostile_value})
    assert clean.returncode == hostile.returncode == 0


def test_c3_fetch_uses_branch_when_remote_also_has_main_tag(rig_factory):
    rig = rig_factory(with_main_tag=True)
    assert rig.tag_main is not None
    assert rig.run(rig.tag_main, "C3-bootstrap").returncode == 65
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 0


@pytest.mark.parametrize("plant", ["credential.helper", "include.path", "duplicate hooksPath", "core.bare=false"])
def test_config_allow_list_rejects_every_extra_or_changed_entry(rig_factory, plant):
    rig = rig_factory()
    rig.write_git_wrapper(plant=plant)
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 65


def test_c3_and_c12_each_match_the_exact_config_list(rig_factory):
    rig = rig_factory()
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 0
    assert rig.run(rig.m2, "C3").returncode == 0
    assert rig.run(rig.m2, "C12").returncode == 0


@pytest.mark.parametrize("kind", ["absent", "symlink", "unreadable", "directory", "garbage", "fifo"])
def test_bad_journal_table_halts(rig_factory, kind):
    rig = rig_factory()
    journal = rig.base / "last-main"
    if kind == "symlink":
        target = rig.root / "journal-target"; target.write_text(rig.m1 + "\n"); journal.symlink_to(target)
    elif kind == "unreadable":
        journal.write_text(rig.m1 + "\n"); journal.chmod(0)
    elif kind == "directory":
        journal.mkdir()
    elif kind == "garbage":
        journal.write_text("not-a-commit\n")
    elif kind == "fifo":
        os.mkfifo(journal)
    name = "C3" if kind == "absent" else "C3-bootstrap"
    assert rig.run(rig.m2, name).returncode == 65


def test_absent_journal_is_allowed_only_for_bootstrap(rig_factory):
    rig = rig_factory()
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 0
    journal = rig.base / "last-main"
    assert journal.read_text() == rig.m2 + "\n"
    assert journal.stat().st_mode & 0o777 == 0o444


@pytest.mark.parametrize(("previous", "current", "expected"), [("m1", "m2", 0), ("m2", "m2", 0), ("m2", "m1", 65)])
def test_journal_forward_same_and_rewind(rig_factory, previous, current, expected):
    rig = rig_factory()
    rig.set_journal(getattr(rig, previous))
    assert rig.run(getattr(rig, current), "C3").returncode == expected


BODY_CONTRACT = r'''print -r -- "argc=$#"
print -r -- "one=$1"
print -r -- "two=$2"
print -r -- "pwd=$PWD"
typeset +x LOGNAME OLDPWD PWD SHLVL
keys=$(/usr/bin/env | /usr/bin/cut -d= -f1 | /usr/bin/grep -v '^_$' | /usr/bin/sort | /usr/bin/paste -sd, -)
print -r -- "env=$keys"
'''


def test_body_contract_has_two_args_cwd_and_only_the_supplied_env(rig_factory):
    rig = rig_factory({"C3-bootstrap": BODY_CONTRACT})
    got = rig.run(rig.m2, "C3-bootstrap")
    run = rig.runs()[-1]
    wanted = ("argc=", "one=", "two=", "pwd=", "env=")
    lines = dict(line.split("=", 1) for line in got.stdout.splitlines() if line.startswith(wanted))
    assert got.returncode == 0
    assert lines == {"argc": "2", "one": rig.m2, "two": str(run), "pwd": str(run), "env": "HOME,LC_ALL,PATH"}


def test_body_reads_known_blob_through_helper(rig_factory):
    body = '"$2/g" cat-file blob "${1}:generation"\n'
    rig = rig_factory({"C3-bootstrap": body})
    got = rig.run(rig.m2, "C3-bootstrap")
    expected = rig._git_run(f"--git-dir={rig.remote}", "cat-file", "blob", f"{rig.m2}:generation") + "\n"
    assert got.returncode == 0
    assert got.stdout.splitlines(keepends=True)[-1] == expected


def test_body_git_helper_is_hardened_and_mode_0500(rig_factory):
    body = '/bin/cat "$2/g"\n/usr/bin/stat -f "mode=%Lp" "$2/g"\n'
    rig = rig_factory({"C3-bootstrap": body})
    got = rig.run(rig.m2, "C3-bootstrap")
    run = rig.runs()[-1]
    assert got.returncode == 0
    helper = got.stdout[got.stdout.index("#!/bin/zsh -f\n") :]
    assert helper.startswith("#!/bin/zsh -f\nexec /usr/bin/env -i ")
    assert f'HOME="{run}"' in helper
    assert "/Library/Developer/CommandLineTools/usr/bin/git" in helper
    assert "GIT_CONFIG_NOSYSTEM=1" in helper
    assert "-c protocol.allow=never" in helper
    assert f'-C "{run}/w.git" "$@"' in helper
    assert helper.endswith("mode=500\n")


STDIN_BODY = r'''read -r first || true
/usr/bin/head -c 1 >/dev/null || true
/bin/cat >/dev/null & child=$!
wait "$child"
print -r -- TAIL-RAN
'''


def test_hostile_stdin_cannot_truncate_the_body(rig_factory):
    rig = rig_factory({"C3-bootstrap": STDIN_BODY})
    got = rig.run(rig.m2, "C3-bootstrap", stdin="first\nsecond\nthird\n")
    assert got.returncode == 0
    assert "TAIL-RAN" in got.stdout


def test_watchdog_timeout_is_70_and_leaves_no_fetch_process(rig_factory):
    rig = rig_factory()
    rig.write_git_wrapper(mode="sleep")
    got = rig.run(rig.m2, "C3-bootstrap")
    alive, pid = rig.fetch_alive()
    if alive:
        rig.kill_fetch(pid)
    assert got.returncode == 70
    assert not alive


def test_fetch_failure_is_69(rig_factory):
    rig = rig_factory()
    rig.write_git_wrapper(mode="fail")
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 69


@pytest.mark.parametrize(("body", "expected"), [("exit 0\n", 0), ("exit 42\n", 42)])
def test_cleanup_and_receipt_after_body_success_or_failure(rig_factory, body, expected):
    rig = rig_factory({"C3-bootstrap": body})
    got = rig.run(rig.m2, "C3-bootstrap")
    run = rig.runs()[-1]
    assert got.returncode == expected
    assert [p.name for p in run.iterdir()] == ["receipt"]
    assert f"rc={expected}\n" in (run / "receipt").read_text()
    assert (run / "receipt").stat().st_mode & 0o777 == 0o400


def test_zshenv_presence_halts(rig_factory):
    rig = rig_factory()
    rig.zshenv.write_text("return 0\n")
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 65


def test_symlink_ceremony_is_refused(rig_factory):
    rig = rig_factory(symlink_ceremony="C3-bootstrap")
    assert rig.run(rig.m2, "C3-bootstrap").returncode == 65


def test_test_copy_diff_is_exactly_the_declared_patch_table(rig_factory):
    rig = rig_factory()
    source = SHIPPED.read_text()
    file_url = rig.remote.as_uri()
    c3_old = "C3-bootstrap|C3) REMOTE='https://github.com/Bali-Zero/Teman2.git'; fetch_ref=refs/heads/main; transport=(-c protocol.allow=never -c protocol.https.allow=always); transport_expected=$'command line:\\tprotocol.https.allow=always' ;;"
    c12_old = "C12) REMOTE='file:///Users/nuzantara/.nuzantara-pilots/local-ci/merger/repo.git'; fetch_ref=refs/merger/base; transport=(-c protocol.allow=never -c protocol.file.allow=always); transport_expected=$'command line:\\tprotocol.file.allow=always' ;;"
    frozen = [
        ("ceremony-home", "/Users/zero-ops", str(rig.home)),
        ("tool-root", "CLT=/Library/Developer/CommandLineTools", f"CLT={rig.clt}"),
        ("trust-owner", "-user root", f"-user {rig.user}"),
        ("link-parent-stop", "STOP=/;", f"STOP={rig.trust};"),
        (
            "trust-roots",
            'trust=(/ /Library /Library/Developer "$CLT" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" /bin /usr /usr/bin /System /usr/local /usr/local/localci /usr/local/localci/bin /usr/local/localci/bin/ceremony-launcher.zsh)',
            f'trust=("{rig.trust}" "{rig.clt}" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" "$GIT" "{rig.probe}" "{rig.link}" "{rig.launcher}")',
        ),
        (
            "closure-roots",
            '"$GIT" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core" /bin/realpath',
            '"$GIT" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core"',
        ),
        (
            "c3-file-remote",
            c3_old,
            f"C3-bootstrap|C3) REMOTE='{file_url}'; fetch_ref=refs/heads/main; transport=(-c protocol.allow=never -c protocol.file.allow=always); transport_expected=$'command line:\\tprotocol.file.allow=always' ;;",
        ),
        (
            "c12-fixture-remote",
            c12_old,
            f"C12) REMOTE='{file_url}'; fetch_ref=refs/merger/base; transport=(-c protocol.allow=never -c protocol.file.allow=always); transport_expected=$'command line:\\tprotocol.file.allow=always' ;;",
        ),
        ("zshenv-probe", "/etc/zshenv", str(rig.zshenv)),
        (
            "unprivileged-install",
            '/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 "$d/last-main.new" "$journal"',
            '/usr/bin/install -m 0444 "$d/last-main.new" "$journal"',
        ),
        ("watchdog-ticks", "ticks < 600", "ticks < 40"),
        ("watchdog-tick-duration", "zselect -t 100", "zselect -t 5"),
        ("watchdog-grace", "zselect -t 500", "zselect -t 5"),
    ]
    counts = {
        "ceremony-home": 2,
        "tool-root": 2,
        "trust-owner": 3,
        "link-parent-stop": 1,
        "trust-roots": 1,
        "closure-roots": 1,
        "c3-file-remote": 1,
        "c12-fixture-remote": 1,
        "zshenv-probe": 2,
        "unprivileged-install": 1,
        "watchdog-ticks": 1,
        "watchdog-tick-duration": 1,
        "watchdog-grace": 1,
    }
    assert [(patch.name, patch.old, patch.new) for patch in rig.patches] == frozen
    assert {patch.name: patch.count for patch in rig.patches} == counts
    expected = source
    for name, old, new in frozen:
        assert source.count(old) == counts[name], name
        expected = expected.replace(old, new)
    assert rig.launcher.read_text() == expected


def test_shipped_security_contract_is_literal():
    text = SHIPPED.read_text()
    assert "GIT_SSH_COMMAND" not in text
    assert "known_hosts" not in text
    assert "C3-bootstrap|C3) REMOTE='https://github.com/Bali-Zero/Teman2.git'; fetch_ref=refs/heads/main; transport=(-c protocol.allow=never -c protocol.https.allow=always)" in text
    assert "C12) REMOTE='file:///Users/nuzantara/.nuzantara-pilots/local-ci/merger/repo.git'; fetch_ref=refs/merger/base; transport=(-c protocol.allow=never -c protocol.file.allow=always)" in text
    assert 'fetch --no-tags "$REMOTE" "+${fetch_ref}:refs/ceremony/main"' in text
    assert 'merge-base --is-ancestor "$M" refs/ceremony/main' in text
    assert '"$2/g" cat-file blob "${1}:path"' in text
    assert "/Library/Developer/CommandLineTools/usr/bin/git -c core.hooksPath=/dev/null -c core.fsmonitor=false -c maintenance.auto=false -c protocol.allow=never" in text
    assert "/System/Volumes/Data|/System/Volumes/Data/*) exit 1" in text
    assert '/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 "$d/last-main.new" "$journal"' in text
    assert '/usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/zsh -f "$d/ceremony.zsh" "$M" "$d"' in text
