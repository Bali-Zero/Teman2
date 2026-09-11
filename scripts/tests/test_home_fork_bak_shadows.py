"""`--discover` must see the `.bak` files sitting beside a declared HOME payload.

TRAUMA. `--check` compares exactly the paths the registry names, so a backup
taken beside one of them is outside its field of view entirely — and a backup is
not inert:

  - W65: the 2026-05-31 hardening sweep chmod'd the live
    `com.nuzantara.skills-bridge-consumer.plist` to 0400 and left the backup it
    had just made world-readable, with the 64-hex API key still in it. The
    hardening hardened the file and not the copy of the file.
  - Resurrection: the WR2 canva-renderer scar says, in those words, that
    "preserving on disk under `~/Library/LaunchAgents/` IS the attack surface for
    sibling-agent resurrection". Two `.plist.bak-*` are sitting there right now.
  - Frozen fork: a `.bak` of a script is a fork of that script that nothing in
    this repo ever compares — which is the entire disease this lint exists for.

Guilt + innocence per superscar #3. The fixtures drive the real CLI through the
seams the file already has (`--config` for the registry, `--home` for the fake
HOME) rather than a new `--fixture-dir` flag: one fewer surface, and it exercises
the same argument path production uses.

MEASURED, not asserted from the spec: on Mini 2026-08-31 the live run reports 83
shadows across 9 directories, 35 of them in `~/.claude/hooks`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_LINT = _SCRIPTS / "lint_home_fork.py"


def _world(tmp_path: Path, pairs: list[dict]) -> tuple[Path, Path]:
    """A fake HOME plus a registry that names paths inside it."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "pairs.json"
    cfg.write_text(json.dumps({"pairs": pairs, "allow": []}), encoding="utf-8")
    return home, cfg


def _run(home: Path, cfg: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(_LINT), "--discover", "--home", str(home), "--config", str(cfg), *extra],
        capture_output=True,
        text=True,
    )


def _declare(home: Path, rel: str, *, machines: list[str] | None = None) -> dict:
    live = home / rel
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    pair: dict = {"live": f"~/{rel}", "repo": "scripts/lint_home_fork.py"}
    if machines is not None:
        pair["machines"] = machines
    return pair


# --------------------------------------------------------------------------- guilt


def test_a_bak_beside_a_declared_payload_is_reported(tmp_path: Path) -> None:
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / "thing.sh.bak-tcc-20260716").write_text("old", encoding="utf-8")

    r = _run(home, cfg)
    assert "thing.sh.bak-tcc-20260716" in r.stdout, r.stdout
    assert "1 .bak shadow(s)" in r.stdout, r.stdout


def test_a_bak_whose_ORIGINAL_is_gone_is_still_reported(tmp_path: Path) -> None:
    """The resurrection case: the live file was retired, its backup was not.

    This is the WR2 canva-renderer shape — the plist was booted out and the
    `.bak` left on disk is the sole copy a sibling agent can reload from. A rule
    keyed to "a backup OF a file that is still here" would go quiet at exactly
    the moment the surface becomes most dangerous.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "Library/LaunchAgents/com.x.plist")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "Library" / "LaunchAgents" / "com.retired.plist.bak-tcc-20260716").write_text("x", encoding="utf-8")
    (home / "Library" / "LaunchAgents" / "com.x.plist").unlink()

    r = _run(home, cfg)
    assert "com.retired.plist.bak-tcc-20260716" in r.stdout, r.stdout


def test_a_pair_scoped_to_ANOTHER_machine_is_still_scanned(tmp_path: Path) -> None:
    """The under-match this lint shipped with in its first draft.

    Filtering the directory set by `pair_applies(machine)` hid 9 real `.bak`
    files in `~/scripts/cron-agent-python/` on Mini, because every pair naming
    that directory is `machines:["pro"]` — while the directory itself is fully
    populated on Mini. The reported thing is a FILE ON THIS DISK; the machine
    label of the pair says nothing about whether that file is here.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/cron-agent-python/job.py", machines=["some-other-host"])
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / "cron-agent-python" / "job.py.bak.20260726").write_text("old", encoding="utf-8")

    r = _run(home, cfg)
    assert "job.py.bak.20260726" in r.stdout, r.stdout


@pytest.mark.parametrize(
    "name",
    [
        "thing.sh.bak",  # bare
        "thing.sh.bak-tcc-20260716",  # suffixed, the fleet's dominant form
        "thing.sh.bak.20260726b",  # dotted + letter
        ".cron-runner.sh.bak-20260728",  # dotfile original (real, in ~/scripts)
    ],
)
def test_every_naming_dialect_on_the_live_disk_is_caught(tmp_path: Path, name: str) -> None:
    """Four shapes taken verbatim from the live census, not invented.

    A rule anchored to `endswith('.bak')` would miss three of these four, and the
    three it misses are 82 of the 83 files actually on the disk.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / name).write_text("old", encoding="utf-8")

    r = _run(home, cfg)
    assert name in r.stdout, r.stdout


def test_strict_bak_turns_the_report_into_a_failure(tmp_path: Path) -> None:
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / "thing.sh.bak").write_text("old", encoding="utf-8")

    lenient = _run(home, cfg)
    strict = _run(home, cfg, "--strict-bak")
    assert not (lenient.returncode & 8), f"bit 8 set without the flag: rc={lenient.returncode}"
    assert strict.returncode & 8, f"bit 8 not set with the flag: rc={strict.returncode}\n{strict.stdout}"


def test_strict_bak_does_not_clobber_the_other_exit_bits(tmp_path: Path) -> None:
    """Bit 8 is additive.

    An exit code that REPLACED 1/2/4 would silently downgrade a real divergence
    into "you have some backups" — a guard whose new rule eats its old verdict.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    pair["repo"] = "scripts/this-repo-path-does-not-exist.py"
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / "thing.sh.bak").write_text("old", encoding="utf-8")

    r = _run(home, cfg, "--check", "--strict-bak")
    assert r.returncode & 8, f"rc={r.returncode}"
    # Bit 1 BY NAME, not `& ~8`. The refuter's point: `& ~8` is satisfied by any
    # surviving bit, so moving NO-REPO-TWIN from `breaches` to `errors` — a
    # plausible severity refactor — would turn bit 1 into bit 4, downgrade the
    # divergence verdict, and leave this test green under a name that claims to
    # protect it.
    assert r.returncode & 1, f"the divergence bit did not survive alongside bit 8: rc={r.returncode}"


# ------------------------------------------------------------------------ innocence


def test_a_directory_with_no_backups_is_silent(tmp_path: Path) -> None:
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")

    r = _run(home, cfg)
    assert "clean — no .bak shadow" in r.stdout, r.stdout
    assert not (r.returncode & 8), f"rc={r.returncode}"
    assert not (_run(home, cfg, "--strict-bak").returncode & 8)


def test_a_backup_in_an_UNRELATED_directory_is_not_reported(tmp_path: Path) -> None:
    """Scope is "beside a declared payload", not "anywhere under HOME".

    `~/Downloads/tax-return.pdf.bak` is none of this lint's business, and a rule
    that walked all of HOME would bury the nine directories that matter.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "Downloads").mkdir()
    (home / "Downloads" / "unrelated.txt.bak").write_text("x", encoding="utf-8")

    r = _run(home, cfg)
    assert "unrelated.txt.bak" not in r.stdout, r.stdout
    assert "clean — no .bak shadow" in r.stdout, r.stdout


def test_a_file_that_merely_contains_the_letters_bak_is_not_a_backup(tmp_path: Path) -> None:
    """Superscar #3, the substring trap, applied to this rule's own trigger.

    `bakery.sh` and `run-bak-report.py` contain the letters; neither is a backup.
    The rule keys on a `.bak` SEGMENT, never on `"bak" in name`.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    for benign in ("bakery.sh", "run-bak-report.py", "bak", "backup.sh", "recipes.baklava"):
        (home / "scripts" / benign).write_text("x", encoding="utf-8")

    r = _run(home, cfg)
    assert "clean — no .bak shadow" in r.stdout, r.stdout


def test_a_directory_that_does_not_exist_here_is_silent_not_an_error(tmp_path: Path) -> None:
    """A pair for a machine whose directory this box does not have is not a fault.

    Distinguishing "not here" from "here and unreadable" is the point: only the
    second is CANNOT-VERIFY (W84).
    """
    home, cfg = _world(tmp_path, [])
    cfg.write_text(
        json.dumps({"pairs": [{"live": "~/nowhere/at/all.sh", "repo": "scripts/lint_home_fork.py"}], "allow": []}),
        encoding="utf-8",
    )

    r = _run(home, cfg)
    assert "clean — no .bak shadow" in r.stdout, r.stdout
    assert not (r.returncode & 4), f"a missing directory was reported as a scan error: rc={r.returncode}"


def test_an_UNREADABLE_directory_is_a_scan_error_and_never_reads_clean(tmp_path: Path) -> None:
    """W84: a scan that could not look is not a clean scan.

    A TCC denial on `~/.claude/hooks` is precisely how this rule would otherwise
    report a serene zero over 35 files.
    """
    if os.geteuid() == 0:
        pytest.skip(
            "chmod 0o000 does not stop root, so under a root runner this test "
            "would go red for the runner's identity rather than for a broken "
            "guard — and a red that means two different things is worse than a "
            "skip that means one."
        )
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "locked/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    locked = home / "locked"
    locked.chmod(0o000)
    try:
        r = _run(home, cfg)
    finally:
        locked.chmod(0o755)
    assert r.returncode & 4, f"unreadable directory did not raise the error bit: rc={r.returncode}"
    assert "bak-scan unreadable" in (r.stdout + r.stderr), r.stdout + r.stderr
    # The refuter's point, and it was right: asserting the bit and the string
    # left a mutant alive that printed "clean" anyway. The word a human reads
    # has to change too.
    assert "clean — no .bak shadow" not in r.stdout, r.stdout
    assert "CANNOT-VERIFY" in r.stdout, r.stdout


def test_a_SYMLINK_LOOP_is_a_scan_error_and_never_reads_clean(tmp_path: Path) -> None:
    """The failure mode `Path.is_dir()` hides, measured rather than assumed.

    `is_dir()` swallows OSError and answers False for ELOOP (errno 62) and for a
    permission-denied stat — so "nothing is here" and "I was not allowed to
    look" arrive as the same answer, and the second reads as a clean scan. This
    fixture is the loop; the code must call it CANNOT-VERIFY, not clean.
    """
    home, cfg = _world(tmp_path, [])
    cfg.write_text(
        json.dumps(
            {"pairs": [{"live": "~/loop/thing.sh", "repo": "scripts/lint_home_fork.py"}], "allow": []},
            ),
        encoding="utf-8",
    )
    (home / "a").symlink_to(home / "loop")
    (home / "loop").symlink_to(home / "a")

    r = _run(home, cfg)
    assert r.returncode & 4, f"a symlink loop read as a clean scan: rc={r.returncode}\n{r.stdout}"
    assert "bak-scan unreachable" in (r.stdout + r.stderr), r.stdout + r.stderr


def test_a_declared_live_whose_parent_is_a_FILE_is_silent(tmp_path: Path) -> None:
    """ENOTDIR is "provably nothing to scan", not a fault to escalate."""
    home, cfg = _world(tmp_path, [])
    (home / "notadir").write_text("i am a file", encoding="utf-8")
    cfg.write_text(
        json.dumps(
            {"pairs": [{"live": "~/notadir/thing.sh", "repo": "scripts/lint_home_fork.py"}], "allow": []},
            ),
        encoding="utf-8",
    )

    r = _run(home, cfg)
    assert not (r.returncode & 4), f"rc={r.returncode}\n{r.stdout}"
    assert "clean — no .bak shadow" in r.stdout, r.stdout


# ------------------------------------------ findings from the cross-family refutation


def test_a_pair_OUTSIDE_home_is_not_scanned_without_system(tmp_path: Path) -> None:
    """The file's own policy, which the first draft broke.

    Docstring line 39: "LaunchDaemons are scanned only with --system (user-level
    agents are the organism's surface; system domain is vendor territory)".
    Measured: the real registry holds 7 pairs outside HOME (`/usr/local/bin`,
    `/Library/LaunchDaemons`, `/usr/local/lib/wa-codex-broker/...`). Walking
    those unasked turns a vendor's backup into an organism finding.
    """
    home, cfg = _world(tmp_path, [])
    outside = tmp_path / "usrlocal" / "bin"
    outside.mkdir(parents=True)
    (outside / "vendor.sh").write_text("x", encoding="utf-8")
    (outside / "vendor.sh.bak-tcc-20260716").write_text("x", encoding="utf-8")
    cfg.write_text(
        json.dumps(
            {"pairs": [{"live": str(outside / "vendor.sh"), "repo": "scripts/lint_home_fork.py"}], "allow": []}
        ),
        encoding="utf-8",
    )

    assert "vendor.sh.bak" not in _run(home, cfg).stdout
    assert "vendor.sh.bak" in _run(home, cfg, "--system").stdout


def test_a_DOLLAR_HOME_pair_is_resolved_like_a_tilde_one(tmp_path: Path) -> None:
    """`expand_home()` already existed; the first draft hand-rolled a `~`-only
    second resolver, so a `$HOME/...` pair went unscanned. Two resolvers for one
    question is superscar #9 — the weaker one always wins somewhere.

    NOT under `~/scripts`. The first version of this test put the fixture there
    and a mutation restoring the `~`-only resolver SURVIVED it: proprioception
    injects `~/scripts/...` pairs unconditionally, so the shadow was found
    through a path that has nothing to do with the resolver under test. A test
    satisfiable by an unrelated code path proves nothing about the one it names.
    """
    home, cfg = _world(tmp_path, [])
    (home / "dollar-lane").mkdir(parents=True, exist_ok=True)
    (home / "dollar-lane" / "dollar.sh").write_text("x", encoding="utf-8")
    (home / "dollar-lane" / "dollar.sh.bak").write_text("x", encoding="utf-8")
    cfg.write_text(
        json.dumps(
            {"pairs": [{"live": "$HOME/dollar-lane/dollar.sh", "repo": "scripts/lint_home_fork.py"}], "allow": []}
        ),
        encoding="utf-8",
    )

    assert "dollar.sh.bak" in _run(home, cfg).stdout


@pytest.mark.parametrize("name", ["thing.sh.BAK", "thing.sh.Bak-Sync", "config.bak1"])
def test_uppercase_and_numbered_backups_are_caught(tmp_path: Path, name: str) -> None:
    """HFS+/APFS are case-INSENSITIVE by default, so `job.plist.BAK` is the same
    file to the OS; `config.bak1` is what `cp` users type. A case-sensitive rule
    lets `--strict-bak` return 0 with real backups on the disk.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / name).write_text("old", encoding="utf-8")

    assert name in _run(home, cfg).stdout


def test_baklava_survives_the_widened_rule(tmp_path: Path) -> None:
    """Innocence re-proved AFTER widening, not assumed to survive it.

    Adding `[0-9]` and IGNORECASE is exactly the kind of loosening that turns a
    cured over-match back into one (W94: the cure of an under-match births the
    over-match twin). `l` and `e` are still outside the separator class.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    for benign in ("recipes.baklava", "BAKERY.SH", "run-bak-report.py", "notes.BAKLAVA"):
        (home / "scripts" / benign).write_text("x", encoding="utf-8")

    assert "clean — no .bak shadow" in _run(home, cfg).stdout


def test_a_bak_DIRECTORY_and_a_bak_SYMLINK_are_annotated_not_called_files(tmp_path: Path) -> None:
    """Both are real surfaces — a backed-up hooks TREE is worse than one file —
    but the operator's purge differs, so the count must not hide which is which.
    """
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / "tree.bak-sync").mkdir()
    (home / "scripts" / "link.sh.bak").symlink_to(home / "scripts" / "thing.sh")

    out = _run(home, cfg).stdout
    assert "tree.bak-sync/" in out, out
    assert "link.sh.bak (symlink)" in out, out


def test_strict_bak_with_check_alone_REFUSES_instead_of_being_ignored(tmp_path: Path) -> None:
    """`run_discover = args.discover or not args.check`, so `--check
    --strict-bak` computes no shadows and bit 8 can never be set. Accepted and
    silently ignored is superscar #2 in a single argument.
    """
    home, cfg = _world(tmp_path, [])
    cfg.write_text(json.dumps({"pairs": [], "allow": []}), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-B", str(_LINT), "--check", "--strict-bak", "--home", str(home), "--config", str(cfg)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, f"rc={r.returncode} out={r.stdout!r} err={r.stderr!r}"
    assert "--strict-bak has no effect with --check alone" in r.stderr, r.stderr


def test_one_directory_reached_by_two_names_is_counted_once(tmp_path: Path) -> None:
    """Identity is the inode, never the spelling.

    A symlinked alias — and, on case-insensitive APFS, a differently-cased
    spelling — is the same directory. Keying on the string reports its files
    twice and claims two affected directories where the disk has one.
    """
    home, cfg = _world(tmp_path, [])
    real = home / "scripts"
    real.mkdir(parents=True, exist_ok=True)
    (real / "thing.sh").write_text("x", encoding="utf-8")
    (real / "thing.sh.bak").write_text("old", encoding="utf-8")
    (home / "alias").symlink_to(real)
    cfg.write_text(
        json.dumps(
            {
                "pairs": [
                    {"live": "~/scripts/thing.sh", "repo": "scripts/lint_home_fork.py"},
                    {"live": "~/alias/thing.sh", "repo": "scripts/lint_home_fork.py"},
                ],
                "allow": [],
            }
        ),
        encoding="utf-8",
    )

    out = _run(home, cfg).stdout
    line = [ln for ln in out.splitlines() if ln.startswith("[discover] .bak shadows")][0]
    assert "1 directory/ies" in line, out
    assert out.count("thing.sh.bak") == 1, out


def test_a_DOTDOT_escape_from_home_is_not_scanned(tmp_path: Path) -> None:
    """Lexical containment is fooled; measured, not reasoned.

    `home in Path("<home>/../../usr/local/bin").parents` is TRUE — `.parents`
    walks the string — while the path resolves outside HOME entirely. The first
    cure for the out-of-HOME finding used exactly that lexical test and let this
    through.
    """
    home, cfg = _world(tmp_path, [])
    outside = tmp_path.parent / f"escape-{tmp_path.name}"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "vendor.sh.bak").write_text("x", encoding="utf-8")
    # TWO levels: home is `<tmp>/home`, so one `..` only reaches `<tmp>`, which
    # still contains the fixture and proves nothing. The first draft did exactly
    # that and the lexical-containment mutant survived it — a fixture that
    # cannot reach the state it names is not a test of that state.
    rel = f"~/../../{outside.name}/vendor.sh"
    cfg.write_text(
        json.dumps({"pairs": [{"live": rel, "repo": "scripts/lint_home_fork.py"}], "allow": []}),
        encoding="utf-8",
    )

    assert "vendor.sh.bak" not in _run(home, cfg).stdout


def test_home_itself_is_still_scanned_after_the_containment_guard(tmp_path: Path) -> None:
    """Innocence for the guard: a payload at the HOME ROOT must not be excluded.

    `real_cand == real_home` is the equality half of `_is_within`; without it a
    pair like `~/.zshrc` would silently stop being scanned. On macOS this also
    pins the realpath-both-sides rule — `/tmp` is a symlink to `/private/tmp`,
    so resolving one side only answers False for a directory plainly inside HOME.
    """
    home, cfg = _world(tmp_path, [])
    (home / "roothing.sh").write_text("x", encoding="utf-8")
    (home / "roothing.sh.bak").write_text("x", encoding="utf-8")
    cfg.write_text(
        json.dumps({"pairs": [{"live": "~/roothing.sh", "repo": "scripts/lint_home_fork.py"}], "allow": []}),
        encoding="utf-8",
    )

    assert "roothing.sh.bak" in _run(home, cfg).stdout


@pytest.mark.parametrize("name", ["thing.sh.bak~", "thing.sh.bak "])
def test_tilde_and_trailing_space_dialects(tmp_path: Path, name: str) -> None:
    """Backup-of-a-backup, and the accidental `cp x "x.bak "`."""
    home, cfg = _world(tmp_path, [])
    pair = _declare(home, "scripts/thing.sh")
    cfg.write_text(json.dumps({"pairs": [pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / name).write_text("old", encoding="utf-8")

    assert name.strip() in _run(home, cfg).stdout


# ------------------------------------------- round-3 refutation (attacking the cures)


def _load_lint():
    """Import the lint as a module, for the cases the CLI cannot reach."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("lint_home_fork", _LINT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_a_directory_that_vanishes_AFTER_stat_is_lost_verification_not_absence(tmp_path: Path) -> None:
    """Two refuters disagreed here and the corpus records which one won.

    One argued for symmetry — same world-state at stat and at iterdir, same
    verdict. The other argued they are different states, and that is the stronger
    case: `stat` SUCCEEDED, so the directory was there, and its disappearing now
    means the scan STARTED and could not finish. "Nothing to scan" may be silent;
    "I could not finish looking" may not.

    The same refuter also showed this branch IS deterministically testable — the
    previous revision declared it untestable and shipped a surviving mutant on
    that basis. Monkeypatching `iterdir` opens the window with no race at all.
    """
    mod = _load_lint()
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    (home / "scripts" / "thing.sh").write_text("x", encoding="utf-8")

    real_iterdir = mod.Path.iterdir

    def exploding(self):  # noqa: ANN001, ANN202
        if self.name == "scripts":
            raise FileNotFoundError(2, "vanished mid-scan")
        return real_iterdir(self)

    errors: list[str] = []
    mod.Path.iterdir = exploding
    try:
        found = mod.discover_bak_shadows(
            [{"live": "~/scripts/thing.sh", "repo": "scripts/lint_home_fork.py"}], home, "mini", errors
        )
    finally:
        mod.Path.iterdir = real_iterdir

    assert found == []
    assert errors and errors[0].startswith("bak-scan unreadable"), errors


def test_a_FAILED_first_alias_does_not_suppress_the_second(tmp_path: Path) -> None:
    """The false-clean round 3 found, and the worst defect of the three rounds.

    The inode was recorded BEFORE the enumeration succeeded. So: `~/alias` and
    `~/scripts` are one directory; the alias is stat'd, its iterdir fails, the
    inode is already marked seen — and `~/scripts` is then skipped as a duplicate.
    A directory full of backups is never scanned and the run prints clean.
    """
    mod = _load_lint()
    home = tmp_path / "home"
    real = home / "scripts"
    real.mkdir(parents=True)
    (real / "thing.sh").write_text("x", encoding="utf-8")
    (real / "thing.sh.bak").write_text("old", encoding="utf-8")
    (home / "alias").symlink_to(real)

    real_iterdir = mod.Path.iterdir
    state = {"failed_once": False}

    def flaky(self):  # noqa: ANN001, ANN202
        if self.name == "alias" and not state["failed_once"]:
            state["failed_once"] = True
            raise PermissionError(13, "denied")
        return real_iterdir(self)

    errors: list[str] = []
    mod.Path.iterdir = flaky
    try:
        found = mod.discover_bak_shadows(
            [
                {"live": "~/alias/thing.sh", "repo": "scripts/lint_home_fork.py"},
                {"live": "~/scripts/thing.sh", "repo": "scripts/lint_home_fork.py"},
            ],
            home,
            "mini",
            errors,
        )
    finally:
        mod.Path.iterdir = real_iterdir

    assert any("thing.sh.bak" in f for f in found), (
        f"the second alias was suppressed by the first one's FAILED scan: {found} {errors}"
    )


def test_a_partial_scan_is_announced_even_when_something_WAS_found(tmp_path: Path) -> None:
    """Round 2's cure was nested under "no shadows", so a run with one finding
    and one denied directory printed the count and never mentioned the denial.
    Incompleteness is a fact about the RUN, not about the findings.
    """
    home, cfg = _world(tmp_path, [])
    ok = _declare(home, "scripts/thing.sh")
    locked_pair = _declare(home, "locked/other.sh")
    cfg.write_text(json.dumps({"pairs": [ok, locked_pair], "allow": []}), encoding="utf-8")
    (home / "scripts" / "thing.sh.bak").write_text("old", encoding="utf-8")
    if os.geteuid() == 0:
        pytest.skip("chmod 0o000 does not stop root")
    (home / "locked").chmod(0o000)
    try:
        r = _run(home, cfg)
    finally:
        (home / "locked").chmod(0o755)

    assert "thing.sh.bak" in r.stdout, r.stdout
    assert "CANNOT-VERIFY" in r.stdout, "a denied directory went unmentioned because something was found"


def test_an_UNSTATTABLE_entry_is_labelled_so_and_not_called_a_plain_file(tmp_path: Path) -> None:
    """`is_symlink()`/`is_dir()` swallow OSError and answer False, so the entry
    would have been labelled a plain file — a confident wrong answer where the
    honest one is "I could not tell"."""
    mod = _load_lint()
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    (home / "scripts" / "thing.sh").write_text("x", encoding="utf-8")
    (home / "scripts" / "thing.sh.bak").write_text("old", encoding="utf-8")

    real_lstat = mod.Path.lstat

    def blind(self):  # noqa: ANN001, ANN202
        if self.name.endswith(".bak"):
            raise PermissionError(13, "denied")
        return real_lstat(self)

    mod.Path.lstat = blind
    try:
        found = mod.discover_bak_shadows(
            [{"live": "~/scripts/thing.sh", "repo": "scripts/lint_home_fork.py"}], home, "mini", []
        )
    finally:
        mod.Path.lstat = real_lstat

    assert any("(unstattable)" in f for f in found), found


def test_a_live_path_carrying_a_NUL_does_not_crash_the_lint(tmp_path: Path) -> None:
    """A registry is JSON and JSON can carry \u0000; `os.path.realpath` raises
    ValueError on it, which is not an OSError and would crash the run."""
    mod = _load_lint()
    home = tmp_path / "home"
    home.mkdir(parents=True)
    errors: list[str] = []
    assert mod.discover_bak_shadows([{"live": "~/scr\x00ipts/x.sh", "repo": "r"}], home, "mini", errors) == []


# ------------------------------------------------------------- premise of the fixtures


def test_the_fixture_seam_is_the_one_production_uses(tmp_path: Path) -> None:
    """Guard against a fake world so poor it only measures itself (W108).

    If `--home`/`--config` stopped steering the scan, every guilt case above would
    go quiet and read green. This asserts the steering itself: the same tree
    reported under one registry and not under another.

    The directory is deliberately NOT `~/scripts`. Pairs come from
    `merge_pairs(config["pairs"], proprioception_pairs(repo_root))` — a second,
    hardcoded source that names `~/scripts/...` whatever the registry says — so a
    fixture there would be scanned under an empty registry too and this test
    would prove nothing about `--config`. (Worth knowing in its own right: on a
    real machine the `.bak` scan covers proprioception's pairs as well as the
    registry's.)
    """
    home, cfg = _world(tmp_path, [])
    (home / "custom-lane").mkdir(parents=True, exist_ok=True)
    (home / "custom-lane" / "thing.sh.bak").write_text("old", encoding="utf-8")

    empty = _run(home, cfg)
    assert "custom-lane" not in empty.stdout, empty.stdout

    cfg.write_text(
        json.dumps({"pairs": [_declare(home, "custom-lane/thing.sh")], "allow": []}),
        encoding="utf-8",
    )
    steered = _run(home, cfg)
    assert "custom-lane" in steered.stdout and "thing.sh.bak" in steered.stdout, steered.stdout
