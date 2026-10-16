"""Mutation sweep for the ceremony launcher against its macOS harness.

Each rule edits a temporary checkout. KILLED means pytest ran and failed (exit
1); exit 0 is SURVIVED, any other exit is ERROR, and a non-unique rule is
STALE. The real checkout is never mutated.

    python3 scripts/localci/tests/mutants/ceremony_launcher_mutants.py [--only NAME ...] [--list]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LAUNCHER = "scripts/localci/ceremonies/launcher.zsh"
ANCHOR_TARGET = LAUNCHER   # read by test_mutant_anchors.py: the file every (old, new, tests) rule of this table edits
TEST = "scripts/localci/ceremonies/tests/test_launcher.py"


def node(name: str) -> tuple[str, ...]:
    return (f"{TEST}::{name}",)


PERM = node("test_trust_walk_table[mode-0775]")
STDIN = node("test_hostile_stdin_cannot_truncate_the_body")
BODY = node("test_body_contract_has_two_args_cwd_and_only_the_supplied_env")
WATCH = node("test_watchdog_timeout_is_70_and_leaves_no_fetch_process")
JABS = node("test_bad_journal_table_halts[absent]")
REWIND = node("test_journal_forward_same_and_rewind[m2-m1-65]")
CONFIG = node("test_config_allow_list_rejects_every_extra_or_changed_entry[credential.helper]")
STATIC = node("test_shipped_security_contract_is_literal")
ZSHENV = node("test_zshenv_presence_halts")
PARENT = node("test_trust_walk_table[writable-parent]")
HELPER = node("test_body_git_helper_is_hardened_and_mode_0500")
FETCH_REF = node("test_c3_fetch_uses_branch_when_remote_also_has_main_tag")
CLOSURE = node("test_executable_closure_rejects_writable_or_acl_entries")
GIT_ENV = node("test_git_commands_ignore_hostile_caller_env")
ARGC = node("test_argv_refusals_are_64")
SYMLINK = node("test_symlink_ceremony_is_refused")
BODY_AT_M = node("test_body_runs_from_m_not_from_the_fetched_tip")
MODE_AT_M = node("test_ceremony_mode_is_judged_at_m_not_at_the_fetched_tip")

# name: (old text, replacement, tests that must turn red)
MUTANTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "perm-dash-0022-misses-0775": (
        '-perm +0022 -o -acl \\) \\) -print || exit 65; /usr/bin/find',
        '-perm -0022 -o -acl \\) \\) -print || exit 65; /usr/bin/find',
        PERM,
    ),
    "ceremony-from-stdin": (
        '/usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/zsh -f "$d/ceremony.zsh" "$M" "$d"',
        '/bin/cat "$d/ceremony.zsh" | /usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/zsh -f -s -- "$M" "$d"',
        STDIN,
    ),
    "body-without-argv": ('/bin/zsh -f "$d/ceremony.zsh" "$M" "$d"', '/bin/zsh -f "$d/ceremony.zsh"', BODY),
    "body-inherits-env": ('/usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/zsh', 'HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/zsh', BODY),
    "fetch-not-execd": (
        '( exec "${gcmd[@]}" -C "$d/w.git" fetch --no-tags "$REMOTE" "+${fetch_ref}:refs/ceremony/main" ) & fetch_pid=$!',
        '( "${gcmd[@]}" -C "$d/w.git" fetch --no-tags "$REMOTE" "+${fetch_ref}:refs/ceremony/main"; : ) & fetch_pid=$!',
        WATCH,
    ),
    "journal-absent-accepted": ('  [[ "$NAME" == C3-bootstrap ]] || exit 65', "  true", JABS),
    "rewind-accepted": ('  g -C "$d/w.git" merge-base --is-ancestor "$PREV_M" "$M" || exit 65', "  true", REWIND),
    "config-list-not-allowlisted": ('[[ "$actual" == "$(/usr/bin/printf \'%s\\n\' "$expected" | /usr/bin/sort)" ]] || exit 65', "true", CONFIG),
    "transport-unpinned": ('transport=(-c protocol.allow=never -c protocol.file.allow=always)', 'transport=(-c protocol.file.allow=always)', STATIC),
    "body-helper-uses-path-git": ('/Library/Developer/CommandLineTools/usr/bin/git -c core.hooksPath', 'git -c core.hooksPath', HELPER),
    "body-helper-allows-network": (' -c protocol.allow=never -C \\"$d/w.git\\"', ' -C \\"$d/w.git\\"', HELPER),
    "zshenv-not-asserted": ('[[ ! -e /etc/zshenv && ! -L /etc/zshenv ]] || exit 65', "true", ZSHENV),
    "link-parent-not-judged": (
        'q=$r; while true; do [[ -z "$(/usr/bin/find "$q" -prune \\( ! -user root -o -perm +0022 -o -acl \\) -print)" ]] || exit 1; [[ "$q" == "$STOP" ]] && break; [[ "$q" == / ]] && exit 1; q=${q:h}; done',
        '[[ -z "$(/usr/bin/find "$r" -prune \\( ! -user root -o -perm +0022 -o -acl \\) -print)" ]] || exit 1',
        PARENT,
    ),
    "timeout-same-rc-as-fetch-fail": ("  return 70\n", "  return 69\n", WATCH),
    "fetch-ref-ambiguous": ("fetch_ref=refs/heads/main", "fetch_ref=main", FETCH_REF),
    "closure-perm-dash": (
        '"$CLT/usr/share/git-core" /bin/realpath \\( -type l \\( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \\) -o ! -type l \\( ! -user root -o -perm +0022 -o -acl \\) \\) -print',
        '"$CLT/usr/share/git-core" /bin/realpath \\( -type l \\( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \\) -o ! -type l \\( ! -user root -o -perm -0022 -o -acl \\) \\) -print',
        CLOSURE,
    ),
    "closure-acl-dropped": (
        '"$CLT/usr/share/git-core" /bin/realpath \\( -type l \\( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \\) -o ! -type l \\( ! -user root -o -perm +0022 -o -acl \\) \\) -print',
        '"$CLT/usr/share/git-core" /bin/realpath \\( -type l \\( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \\) -o ! -type l \\( ! -user root -o -perm +0022 \\) \\) -print',
        CLOSURE,
    ),
    "gcmd-without-env-i": ('gcmd=(/usr/bin/env -i HOME="$d"', 'gcmd=(/usr/bin/env HOME="$d"', GIT_ENV),
    "argc-relaxed": ("(( $# == 2 )) || exit 64", "(( $# >= 2 )) || exit 64", ARGC),
    "ceremony-symlink-accepted": (
        "[[ \"$tree_entry\" == *$'\\t'* && \"$tree_path\" == \"$ceremony_path\" && ( \"$tree_mode\" == 100644 || \"$tree_mode\" == 100755 ) && \"$tree_type\" == blob ]] || exit 65",
        "true",
        SYMLINK,
    ),
    "body-read-at-tip": (
        'cat-file blob "${M}:${ceremony_path}"',
        'cat-file blob "refs/ceremony/main:${ceremony_path}"',
        BODY_AT_M,
    ),
    "tree-judged-at-tip": ('ls-tree "$M" -- "$ceremony_path"', 'ls-tree refs/ceremony/main -- "$ceremony_path"', MODE_AT_M),
}

def run_tests(tree: Path, tests: tuple[str, ...]) -> int:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(PYTHONPATH=str(tree), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "--tb=short", "-p", "no:cacheprovider", *tests],
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", metavar="NAME")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    names = args.only or list(MUTANTS)
    if unknown := [name for name in names if name not in MUTANTS]:
        print(f"unknown mutant(s): {unknown}", file=sys.stderr)
        return 2
    if args.list:
        print("\n".join(names))
        return 0
    with tempfile.TemporaryDirectory(prefix="ceremony-launcher-mutants-") as tmp:
        tree = Path(tmp)
        shutil.copytree(ROOT / "scripts/localci/ceremonies", tree / "scripts/localci/ceremonies")
        original = (tree / LAUNCHER).read_text()
        for tests in sorted({MUTANTS[name][2] for name in names}):
            if (rc := run_tests(tree, tests)) != 0:
                print(f"baseline: pytest exit {rc} on {' '.join(tests)}", file=sys.stderr)
                return 2
        survived: list[str] = []
        stale: list[str] = []
        errors: list[str] = []
        for name in names:
            old, new, tests = MUTANTS[name]
            count = original.count(old)
            if count != 1 or old == new:
                stale.append(name)
                print(f"{name:36} STALE (text occurs {count} times)", flush=True)
                continue
            (tree / LAUNCHER).write_text(original.replace(old, new))
            rc = run_tests(tree, tests)
            (tree / LAUNCHER).write_text(original)
            verdict = {0: "SURVIVED", 1: "KILLED"}.get(rc, f"ERROR (pytest exit {rc})")
            if verdict == "SURVIVED":
                survived.append(name)
            elif verdict != "KILLED":
                errors.append(name)
            print(f"{name:36} {verdict}", flush=True)
    killed = len(names) - len(survived) - len(stale) - len(errors)
    print(f"{killed}/{len(names)} killed; survivors: {survived or 'none'}; errors: {errors or 'none'}; stale: {stale or 'none'}")
    return 1 if survived or stale or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
