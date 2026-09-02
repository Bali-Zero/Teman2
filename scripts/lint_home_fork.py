#!/usr/bin/env python3
"""lint_home_fork.py — executable antidote for superscar #1 (HOME-fork drift).

THE FAMILY (dominant disease, ~30% of the scar corpus — W50/51/52, W68/70/72/73,
W76, W81, wr2-deploy-pull 2026-06-27): a launchd/cron job executes a COPY of a
script under $HOME that silently diverges from the git-tracked source of truth.
The fix lands in the repo but the live copy never sees it — or live work in the
HOME copy never returns to the repo.

THE ANTIDOTE, verbatim (cicatrix-superscar.md #1): "lint CI che fallisce se un
file eseguito-live diverge (cmp -s) dalla versione tracciata su git, o se una
config live punta a un path-HOME invece che al repo."

This lint is that rule with an exit contract, in two arms:

  --check     For every DECLARED pair (infra/home-fork/declared-pairs.json,
              merged at runtime with proprioception's own pair list so the two
              SSOTs cannot silently drift): sha256(live) vs sha256(repo twin).
              Divergence or missing repo twin => breach.
  --discover  Parse ~/Library/LaunchAgents/*.plist (Program/ProgramArguments)
              and `crontab -l`: every HOME-rooted payload path that is not
              inside the repo checkout, not a declared pair, and not
              allow-listed is an UNDECLARED finding — a fork candidate nobody
              is watching.

Default (no flag) runs both arms. Exit code is a bitmask:
    0 = clean · 1 = --check divergence · 2 = --discover undeclared ·
    4 = operational error (unreadable plist/dir, crontab failure, TCC denial —
        a scan that cannot see is NOT clean; fail-visible, W84 discipline).
Machine-aware: ~ expands per-machine (balizero on M5, nuzantara on Pro/Mini);
pairs carry a "machines" scope (m5|pro|mini|all). A live copy absent on this
machine is NOT a breach (the machine may simply not run that job).

Scope notes (deliberate): payload extraction reads Program + ProgramArguments
only — StandardOutPath/StandardErrorPath are logs, not executed code (flagging
them would be a #3-family over-match). A path under the repo's `.worktrees/` is
a FINDING, not a cured state: launchd armed against an ephemeral agent worktree
is exactly the W81 deploy-worktree trauma. System-wide /Library/LaunchAgents +
LaunchDaemons are scanned only with --system (user-level agents are the
organism's surface; system domain is vendor territory).

Complementary, not duplicative: scripts/proprioception.py probes the declared
pairs as a body-sense; scripts/launchagent_reconcile.py categorizes LaunchAgents
as a reporter. This lint adds undeclared-payload discovery + crontab coverage +
a CI/pre-push exit contract. It never modifies anything (pure reader).

Related gate: infra/scar-gates/test_W_homefork_live_vs_tracked.py (detector
self-test, guilt+innocence). Tests: scripts/tests/test_lint_home_fork.py.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import plistlib
import re
import stat
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

def _canonical_repo_root() -> Path:
    """Repo root, worktree-hardened: running from .worktrees/<lane>/ must lint
    against the MAIN checkout (a worktree is ephemeral — treating it as the
    source of truth would replay W81)."""
    root = Path(__file__).resolve().parent.parent
    parts = root.parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        return Path(*parts[:idx])
    return root


REPO_ROOT = _canonical_repo_root()
DEFAULT_CONFIG = REPO_ROOT / "infra" / "home-fork" / "declared-pairs.json"

# Executed-payload extensions (candidate even if not currently executable-bit).
_EXEC_EXTS = {".sh", ".bash", ".zsh", ".py", ".rb", ".pl", ".js", ".mjs"}


def machine_label(hostname: Optional[str] = None) -> str:
    """m5 | mini | pro | <bare hostname> — mirrors proprioception.machine_label."""
    host = (hostname or socket.gethostname()).split(".")[0].lower()
    if "air-m5" in host:
        return "m5"
    if "mini" in host:
        return "mini"
    if host == "nuzantara":
        return "pro"
    return host


def expand_home(path_str: str, home: Path) -> Path:
    """Expand ~ / $HOME / ${HOME} against an EXPLICIT home (testable, machine-aware)."""
    s = path_str.strip()
    if s == "~":
        return home
    if s.startswith("~/"):
        return home / s[2:]
    if s.startswith("${HOME}/"):
        return home / s[len("${HOME}/"):]
    if s.startswith("$HOME/"):
        return home / s[len("$HOME/"):]
    return Path(s)


def sha256_file(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _plutil_recovered_plist(plist_path: Path) -> Optional[Any]:
    """Recover a plist `plistlib` rejects but macOS's own parser accepts.

    Root cause seen in production (2026-08-07, Pro): a `<!-- ... -->` comment
    body containing a literal `--` (e.g. documenting a `--apply`/`--cleanup`
    flag) is invalid per the strict XML spec that Expat enforces, but
    `plutil`/CoreFoundation tolerate it — the exact same plist launchd itself
    loads and runs fine (`plutil -lint` reports these files OK). Without this
    fallback the census silently loses coverage on the affected plist's
    payload — an under-match blind spot on the very guard meant to catch
    home-fork drift. Re-serializing through `plutil -convert xml1 -o -`
    drops comments and normalizes the file so plistlib can read the result;
    a plist plutil ALSO rejects (binary garbage, truly malformed) still
    returns None here, unchanged from the pre-fallback behavior.
    """
    try:
        proc = subprocess.run(
            ["plutil", "-convert", "xml1", "-o", "-", str(plist_path)],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return plistlib.loads(proc.stdout)
    except Exception:  # noqa: BLE001 — genuinely unrecoverable, caller reports it
        return None


def _git_stdout(repo_root: Path, *args: str) -> Optional[bytes]:
    """stdout of a git command as BYTES, or None on any failure.

    Never raises: a lint that dies because git is absent, slow, or wrapped by a
    test double is worse than one that degrades. Normalising str→bytes is not
    cosmetic — the first draft assumed bytes, and a caller handing back text
    stdout blew up with a TypeError that no `except` here would have caught.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args], capture_output=True, timeout=15
        )
        if proc.returncode != 0:
            return None
        out = proc.stdout
        return out.encode("utf-8", "replace") if isinstance(out, str) else bytes(out)
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError, AttributeError):
        return None


def origin_main_sha(repo_root: Path, rel: str) -> Optional[str]:
    """sha256 of the blob at `origin/main:<rel>` — what the FLEET agreed the
    repo says, as opposed to what one machine's checkout happens to hold.

    None when the ref or the path is unreachable (no remote, shallow CI clone,
    file new on this branch). Callers must then fall back to the old
    checkout-only verdict — "could not attribute" is never "clean" (W84).
    """
    blob = _git_stdout(repo_root, "show", f"origin/main:{rel}")
    return None if blob is None else hashlib.sha256(blob).hexdigest()


def commits_behind_origin(repo_root: Path) -> Optional[int]:
    """How far this checkout trails origin/main. None when git can't say."""
    out = _git_stdout(repo_root, "rev-list", "--count", "HEAD..origin/main")
    if out is None:
        return None
    try:
        return int(out.decode().strip())
    except (UnicodeDecodeError, ValueError):
        return None


def fetch_origin_main(repo_root: Path, timeout: int = 25) -> tuple[bool, str]:
    """Refresh the `origin/main` ref this check arbitrates with. (ok, detail).

    DECLARED EXCEPTION to "a lint never mutates": this writes refs only — never
    the working tree, never a checked-out branch — so it is safe from any
    worktree sharing the object store. The twin guard
    (`proprioception.probe_home_fork_scripts`) already carries the identical
    exception with the identical wording; this is the missing half of that cure,
    not a new policy.

    Why it has to exist here too: everything above resolves origin/main out of
    the LOCAL object store, so the "fleet's copy" it attributes blame with can
    be exactly as stale as the checkout it was brought in to arbitrate. That is
    not a weaker verdict, it is a differently-wrong one — with a stale ref the
    direction test can name the CURRENT side as the stale one and prescribe
    overwriting it, which is the whole W106b trauma one layer down.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "--quiet", "origin", "main"],
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except OSError as exc:
        return False, f"{type(exc).__name__}"
    if proc.returncode == 0:
        return True, "ok"
    err = proc.stderr
    if isinstance(err, bytes):
        err = err.decode("utf-8", "replace")
    return False, (err or "").strip()[:120] or f"rc={proc.returncode}"


# ---------------------------------------------------------------- pairs


def load_config(config_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"lint_home_fork: cannot read config {config_path}: {exc}")
    data.setdefault("pairs", [])
    data.setdefault("allow", [])
    return data


def proprioception_pairs(repo_root: Path) -> list[dict[str, Any]]:
    """Best-effort merge-in of proprioception's own declared pairs (anti-drift).

    Read-only import; any failure (file moved, structure changed) degrades to
    an empty list — this lint's own JSON config remains the primary SSOT.
    """
    proprio = repo_root / "scripts" / "proprioception.py"
    if not proprio.exists():
        return []
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_lint_hf_proprio", proprio)
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        for entry in getattr(mod, "DEFAULT_REGISTRY", []):
            if entry.get("id") == "home_fork_scripts":
                machines = entry.get("machines", ["all"])
                return [
                    {"live": p["live"], "repo": p["repo"], "machines": machines}
                    for p in entry.get("args", {}).get("pairs", [])
                    if "live" in p and "repo" in p
                ]
    except Exception:  # noqa: BLE001 — degraded mode is the contract here
        return []
    return []


def merge_pairs(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for source in sources:
        for pair in source:
            key = (pair["live"], pair["repo"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(pair)
    return merged


def pair_applies(pair: dict[str, Any], label: str) -> bool:
    machines = pair.get("machines", ["all"])
    return "all" in machines or label in machines


def check_pairs(
    pairs: list[dict[str, Any]],
    repo_root: Path,
    home: Path,
    label: str,
    notices: Optional[list[str]] = None,
    skipped: Optional[list[str]] = None,
) -> list[str]:
    """The --check arm: sha256 live vs repo twin for machine-applicable pairs.

    A bare live-vs-checkout comparison knows THAT the two differ, never WHICH
    side is stale — and the remedy it printed ("realign live from repo") is
    only right when the checkout is the current one. On 2026-07-27 the M5
    checkout was 144 commits behind origin/main while both live copies matched
    origin/main exactly: following the prescription would have overwritten a
    current worktree-isolation hook with a two-day-old one. A guard whose cure
    causes the damage it exists to prevent is worse than no guard.

    So when the two differ we ask origin/main — the fleet's copy — which side
    moved, and only call it a HOME-fork when the LIVE copy is the stale one.
    A stale checkout goes to `notices` instead: real, differently owned, and
    on M5 not even fixable (pulling that checkout races ~45 live worktrees).

    `skipped` collects the pairs this machine CLAIMS (machines: all/<label>)
    whose live copy is not on disk. They are not breaches — nothing can drift
    when nothing is running — but they are not coverage either, and silence
    made them read as coverage. Measured 2026-08-06: `--check` reported
    "109 declared pair(s) ... clean" on the Pro while three of the ten
    wa-mirror pairs were never evaluated, including BOTH files the promotion
    PR existed for (their live copies had been moved to an attic hours
    earlier). The verdict was true; the conclusion a reader draws from it —
    "the promoted files are verified" — was not.

    A pair scoped to another machine is deliberately NOT collected here: that
    is legitimate non-applicability, not a blind spot, and reporting it would
    bury the real signal in fleet-wide noise on every run.
    """
    breaches: list[str] = []
    for pair in pairs:
        if not pair_applies(pair, label):
            continue
        live = expand_home(pair["live"], home)
        repo = repo_root / pair["repo"]
        if not live.exists():
            # Not a breach — but say so, or "clean" reads as "checked".
            if skipped is not None:
                skipped.append(f"{pair['live']} (declared for {label}, not on disk)")
            continue
        if not repo.exists():
            # ABSENCE is a proxy too. W106b cured the DIVERGENCE path — ask
            # origin/main which side is stale — but left this branch asserting
            # the harsher claim ("no source of truth") from the checkout alone.
            # A checkout that simply trails a merge is then accused of a breach
            # it does not have, in a message that is factually false, and the
            # remedy it prints ("declare the pair") is a no-op because the pair
            # IS declared. Measured live on M5 2026-08-08, minutes after #3777
            # merged: a correctly declared, correctly synced pair read as
            # NO-REPO-TWIN because that checkout is 170 commits behind by
            # design (pulling it races ~45 live worktrees).
            upstream = origin_main_sha(repo_root, pair["repo"])
            if upstream is None:
                # Genuinely unsourced — or unattributable (no remote, shallow
                # CI clone). Either way keep the loud verdict: "could not
                # attribute" is never "clean" (W84).
                breaches.append(
                    f"NO-REPO-TWIN: {pair['live']} executes live but {pair['repo']} "
                    f"is not in the repo — the live copy has no source of truth"
                )
                continue
            if sha256_file(live) == upstream:
                behind = commits_behind_origin(repo_root)
                trail = f" ({behind} commits behind)" if behind else ""
                if notices is not None:
                    notices.append(
                        f"CHECKOUT-STALE: {pair['repo']} is absent from this "
                        f"checkout{trail} but present on origin/main, and the "
                        f"LIVE copy {pair['live']} already matches it. The live "
                        f"copy HAS a source of truth — update the checkout, "
                        f"change nothing live."
                    )
                    continue
                # No notices sink: keep it visible rather than dropping a real
                # finding, but say which side actually moved.
                breaches.append(
                    f"DIVERGED: {pair['repo']} is absent from this checkout — "
                    f"the CHECKOUT is the stale side, update it, do not touch live"
                )
                continue
            breaches.append(
                f"DIVERGED: {pair['live']} != origin/main:{pair['repo']} (absent "
                f"from this checkout) — the LIVE copy is the stale side; realign "
                f"it from origin/main, never from this checkout"
            )
            continue
        live_sha, repo_sha = sha256_file(live), sha256_file(repo)
        if live_sha == repo_sha:
            continue

        upstream = origin_main_sha(repo_root, pair["repo"])
        if upstream is not None and live_sha == upstream:
            # The live copy IS the fleet's copy; the checkout trails it.
            behind = commits_behind_origin(repo_root)
            trail = f" ({behind} commits behind)" if behind else ""
            if notices is not None:
                notices.append(
                    f"CHECKOUT-STALE: {pair['repo']}{trail} — the LIVE copy "
                    f"{pair['live']} already matches origin/main. Do NOT realign "
                    f"live from this checkout: it would regress the live copy. "
                    f"Update the checkout instead."
                )
                continue
            # No notices sink offered: keep it visible as a breach rather than
            # dropping a real finding on the floor.

        if upstream is None:
            hint = "no origin/main to compare — direction unattributable"
        elif live_sha == upstream:
            # Only reachable with no notices sink: still say which side moved.
            hint = "the CHECKOUT is the stale side — update it, do not touch live"
        elif repo_sha == upstream:
            hint = "the checkout matches origin/main, so the LIVE copy is the stale side"
        else:
            hint = "BOTH sides differ from origin/main — read both before porting"
        breaches.append(
            f"DIVERGED: {pair['live']} != {pair['repo']} — a fix is stranded "
            f"on one side ({hint})"
        )
    return breaches


# ---------------------------------------------------------------- discover

def _path_token_re(home: Path) -> "re.Pattern[str]":
    return re.compile(
        r"(?:~|\$\{HOME\}|\$HOME|"
        + re.escape(str(home))
        + r"|/Users/[A-Za-z0-9_.-]+)/[^\s\"';|&<>)]*"
    )


def _normalize(token: str, home: Path) -> Optional[str]:
    """~-normalize a HOME-rooted token; None when it is another user's home."""
    expanded = expand_home(token.rstrip(":,"), home)
    try:
        return "~/" + str(expanded.relative_to(home))
    except ValueError:
        return None  # /Users/<other-user>/… — not THIS home; out of scope


_REDIRECT_RE = re.compile(r"[012&]?>>?\s*\S+")


def extract_home_paths(text: str, home: Path) -> set[str]:
    """HOME-rooted path tokens embedded in a shell string, ~-normalized.

    Redirection targets (`>> ~/logs/x.log`) are stripped first — a log sink is
    not an executed payload; flagging it would be a #3-family over-match.
    """
    found: set[str] = set()
    for match in _path_token_re(home).finditer(_REDIRECT_RE.sub(" ", text)):
        norm = _normalize(match.group(0), home)
        if norm:
            found.add(norm)
    return found


def is_payload_candidate(norm: str, home: Path) -> bool:
    """True iff the path plausibly IS executed code, not data it reads/writes.

    Precision-over-recall for arguments (over-match discipline, #3): a path
    counts when its extension is a script extension, or it exists on disk as
    an executable regular file. Known limit (documented, accepted): an
    interpreter argument with no extension and no exec bit slips through —
    rare, and the alternative flags every data/log/env argument as a fork.
    """
    expanded = expand_home(norm, home)
    if expanded.suffix.lower() in _EXEC_EXTS:
        return True
    try:
        return expanded.is_file() and os.access(expanded, os.X_OK)
    except OSError:
        return False


def _is_allowed(norm: str, home: Path, allow: list[str]) -> bool:
    expanded = str(expand_home(norm, home))
    for pattern in allow:
        pat_expanded = str(expand_home(pattern, home))
        if fnmatch.fnmatch(norm, pattern) or fnmatch.fnmatch(expanded, pat_expanded):
            return True
    return False


# A `.bak` SEGMENT, never `"bak" in name` (superscar #3, the substring trap
# applied to this rule's own trigger). The four dialects on the live disk are
# `.bak`, `.bak-tcc-20260716`, `.bak.20260726b` and `.bak-sync`; a rule anchored
# to `endswith(".bak")` would miss 82 of the 83 files actually there, and a bare
# `".bak" in name` would incriminate `recipes.baklava`.
#
# Case-insensitive and digit-tolerant because the disk is not: HFS+/APFS are
# case-INSENSITIVE by default, so `job.plist.BAK` is the same file to the OS and
# a case-sensitive rule would miss it; `config.bak1` is the numbered convention
# `cp` users reach for. `~` catches the backup-of-a-backup every editor writes
# and a trailing space catches the accidental `cp x "x.bak "`. The class stays
# safe — `baklava` fails on `l`, `bakery` on `e`.
#
# DECLARED FALSE-POSITIVE CLASS, kept deliberately: with IGNORECASE and `-` in
# the class, a name like `routes.BAK-DPS.csv` is flagged — `BAK` is the UN/LOCODE
# for Baku, not a backup. The trade was made with eyes open: dropping IGNORECASE
# would lose `com.x.plist.BAK`, a REAL backup on a case-insensitive filesystem,
# which is the filesystem this lint exists for. The finding is advisory (bit 8 is
# opt-in), so a false positive costs one line of output and never a red build,
# while the miss it would trade for costs a leaked key nobody sees.
#
# DECLARED LIMIT, not an oversight: this covers the `.bak` family ONLY. Other
# backup conventions on this disk — `~` suffixes, `.orig` from patch, `.old`,
# `.save`, editor `.swp` — are NOT reported. Widening is a measurement question
# (which of them actually occur beside a declared payload) and would be its own
# change with its own census; claiming coverage that was never measured is worse
# than a narrow rule that says so.
def _is_within(candidate: Path, home: Path) -> bool:
    """Is `candidate` really inside `home`, once `..` and symlinks are spent?

    A LEXICAL check is fooled, and this was MEASURED rather than reasoned:
    `home in Path("<home>/../../usr/local/bin").parents` is **True**, because
    `.parents` walks the string. That path resolves to `/usr/local/bin`.

    `os.path.realpath` is used instead of `Path.resolve()` deliberately.
    Measured on Python 3.11: `resolve()` on a symlink loop raises **RuntimeError**
    ("Symlink loop from ..."), which is NOT an OSError and would sail straight
    past the handlers below and crash the lint — a trap inside the fix for a
    trap. `realpath` never raises: a loop comes back unresolved, a missing path
    comes back as itself, and the stat below is left to render the verdict.

    Both sides are realpath'd. On macOS `/tmp` is a symlink to `/private/tmp`,
    so resolving only one side compares two spellings of one place and answers
    False for a directory that is plainly inside HOME.
    """
    # An embedded NUL makes realpath raise ValueError, which is NOT an OSError
    # and would sail past every handler in the caller and crash the lint. A
    # registry is JSON, and JSON can carry \u0000, so this is reachable from data
    # rather than only from a hostile filesystem.
    try:
        real_home = os.path.realpath(home)
        real_cand = os.path.realpath(candidate)
    except ValueError:
        return False
    return real_cand == real_home or real_cand.startswith(real_home + os.sep)


_BAK_SHADOW_RE = re.compile(r"\.bak(?:$|[-._0-9~ ])", re.IGNORECASE)


def discover_bak_shadows(
    pairs: list[dict],
    home: Path,
    label: str,
    errors: list[str],
    include_system: bool = False,
) -> list[str]:
    """`.bak*` files sitting in a directory that holds a declared live payload.

    WHY THIS IS A COVERAGE GAP AND NOT HOUSEKEEPING. `--check` compares exactly
    the paths the registry names. A backup beside one of them is invisible to
    it, and inherits everything the original had at the moment it was taken:

      - W65: the 2026-05-31 sweep chmod'd the LIVE
        `com.nuzantara.skills-bridge-consumer.plist` to 0400 and left its own
        backup world-readable — with the 64-hex API key still inside. The
        hardening hardened the file and not the copy it had just made.
      - The resurrection surface: a `.bak` under `~/Library/LaunchAgents/` is
        the reason a deliberately decommissioned job can come back. The WR2
        canva-renderer scar names "preserving on disk under
        ~/Library/LaunchAgents/ IS the attack surface for sibling-agent
        resurrection" in those words.
      - Silent-drift: a `.bak` of a script is a frozen fork of it, and the one
        thing this whole lint exists to catch is a frozen fork nobody compares.

    Reported, never fatal by default (`--strict-bak` opts in). Measured on Mini
    2026-08-31: 83 of them across 9 declared-pair directories, 35 in
    `~/.claude/hooks` alone. A finding that reddens every run from day one is a
    finding somebody disarms; this one is loud and countable instead, so the
    operator's purge has a number to shrink.

    DELETION IS NOT THIS LINT'S JOB and is not done anywhere in this PR:
    `~/.claude/hooks/` is live control-plane state, i.e. `operator[control-plane]`
    per Part A §2 of the repo's CLAUDE.md.
    """
    findings: list[str] = []
    dirs: dict[Path, list[str]] = {}
    for pair in pairs:
        # DELIBERATELY NOT machine-scoped, unlike every other check in this file.
        # `pair_applies()` is right for the DIVERGENCE check: comparing a payload's
        # content only means something where that payload is supposed to run.
        # It is wrong here, because the thing being reported is a FILE THAT EXISTS
        # ON THIS DISK. Measured on Mini 2026-08-31: filtering by machine hid 9 real
        # `.bak` files in `~/scripts/cron-agent-python/` — a directory whose every
        # declared pair is `machines:["pro"]` yet which is fully populated here. A
        # Pro script's backup sitting on Mini leaks and resurrects exactly as well
        # as a Mini one. `label` stays in the signature so the caller reads the same
        # as its siblings and a future machine-aware rule has somewhere to land.
        live = pair.get("live")
        if not isinstance(live, str) or not live:
            continue
        # `expand_home()` is this file's OWN resolver and handles `~/`, `$HOME/`
        # and `${HOME}/`. Hand-rolling a second one here (the first draft did,
        # `~`-only) is a second source of truth for the same question, which is
        # superscar #9 — and it silently missed `$HOME/...` pairs.
        resolved = expand_home(live, home)
        directory = resolved.parent
        # The file's own stated policy, docstring line 39: "LaunchDaemons are
        # scanned only with --system (user-level agents are the organism's
        # surface; system domain is vendor territory)". MEASURED: the registry
        # holds 7 pairs outside HOME (`/usr/local/bin`, `/Library/LaunchDaemons`,
        # `/usr/local/lib/wa-codex-broker/...`). Scanning those unasked reports
        # vendor backups as organism findings and lets a foreign unreadable
        # directory raise the error bit.
        if not include_system and not _is_within(directory, home):
            continue
        dirs.setdefault(directory, []).append(live)

    seen_inodes: set[tuple[int, int]] = set()
    for directory, declared_here in sorted(dirs.items()):
        # `Path.is_dir()` CANNOT be the gate here. Measured 2026-08-31: it
        # swallows OSError and returns False for a symlink loop (ELOOP/62) and
        # for a stat denied by permissions — so "there is nothing here" and "I
        # was not allowed to look" come back as the same answer, and the second
        # one would be reported as a clean scan. That is W84 exactly: a scan
        # that could not look is not a clean scan. stat() is called explicitly
        # so the two cases stay distinguishable.
        try:
            st = directory.stat()
        except (FileNotFoundError, NotADirectoryError):
            continue  # genuinely absent on this machine — silent, and correct
        except OSError as exc:
            errors.append(
                f"bak-scan unreachable ({type(exc).__name__}/errno {exc.errno}): {directory}"
            )
            continue
        if not stat.S_ISDIR(st.st_mode):
            continue
        # Identity is the INODE, never the lexical path. On case-insensitive
        # APFS `~/Scripts` and `~/scripts` are one directory with two spellings;
        # a symlinked alias is the same again. Keying on the string would report
        # the same 19 files twice and claim two affected directories where the
        # disk has one.
        ident = (st.st_dev, st.st_ino)
        if ident in seen_inodes:
            continue
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            # A TCC denial on ~/.claude/hooks is exactly how this would
            # otherwise report a serene zero over 35 files.
            #
            # ENOENT/ENOTDIR are DELIBERATELY not silent here, unlike at the stat
            # above, and two cross-family refuters disagreed about this. One
            # argued for symmetry: same world-state, same verdict. The other
            # argued they are not the same state, and that is the stronger case —
            # `stat` SUCCEEDED, so the directory was there; its disappearing now
            # means the scan STARTED and could not finish. "Nothing to scan" and
            # "I could not finish looking" are different claims, and only the
            # first one may be silent.
            errors.append(f"bak-scan unreadable ({type(exc).__name__}): {directory}")
            continue
        # DECLARED LIMIT: a `.bak` DIRECTORY is reported and its CONTENTS are
        # not walked, so `attic.bak/old.sh` is one finding ("attic.bak/") rather
        # than the files inside it. Deliberate — the operator's next step for a
        # directory is to look in it, and recursing turns one honest line into
        # an unbounded listing — but it is a real blind spot, and it belongs in
        # writing rather than in nobody's head.
        # A `.bak` DIRECTORY (a whole backed-up hooks tree) and a `.bak` SYMLINK
        # are both real surfaces — the first is more dangerous than a single
        # file, the second is still something a restore can resurrect — so both
        # are counted. They are ANNOTATED rather than silently called "files",
        # because the operator's purge sequence differs for each and a count
        # that hides the difference sends them at a `rm` that will not work.
        shadows: list[str] = []
        for entry in entries:
            if not _BAK_SHADOW_RE.search(entry.name):
                continue
            # ONE explicit lstat, not is_symlink()/is_dir(). Those swallow
            # OSError and answer False, so the `except` around them was very
            # nearly unreachable and an entry we could not stat would have been
            # labelled a plain file — a confident wrong answer where the honest
            # one is "I could not tell". lstat raises, so the handler is real.
            try:
                est = entry.lstat()
            except OSError:
                shadows.append(f"{entry.name} (unstattable)")
                continue
            if stat.S_ISLNK(est.st_mode):
                shadows.append(f"{entry.name} (symlink)")
            elif stat.S_ISDIR(est.st_mode):
                shadows.append(f"{entry.name}/")
            else:
                shadows.append(entry.name)
        seen_inodes.add(ident)
        if shadows:
            findings.append(
                f"{directory} — {len(shadows)} .bak shadow(s) beside "
                f"{len(declared_here)} declared pair(s): {', '.join(shadows[:6])}"
                + (f" (+{len(shadows) - 6} more)" if len(shadows) > 6 else "")
            )
    return findings


def discover_undeclared(
    plist_dirs: list[Path],
    crontab_text: str,
    home: Path,
    repo_root: Path,
    declared_lives: set[str],
    allow: list[str],
    errors: list[str],
) -> list[str]:
    """The --discover arm: HOME-executed payloads nobody declared.

    Operational failures (unreadable dir/plist — TCC denial included) go into
    `errors`, never silently skipped: a scan that cannot see is not clean.
    """
    findings: list[str] = []
    # (origin, normalized-path, always_payload) — Program / argv[0] IS executed
    # by construction; other args pass the payload-candidate filter.
    candidates: list[tuple[str, str, bool]] = []

    home_prefixes = ("~/", "$HOME/", "${HOME}/", str(home) + "/")

    def _collect_arg(origin: str, arg: str, position: int) -> None:
        stripped = arg.strip()
        is_whole_path = (
            stripped.startswith(home_prefixes)
            and not any(ch in stripped for ch in ";|><&\n")
        )
        if is_whole_path:
            # The whole arg is one path (plist args are pre-tokenized — this
            # preserves paths with spaces, e.g. ~/Library/Application Support/…).
            norm = _normalize(stripped, home)
            if norm:
                candidates.append((origin, norm, position == 0))
            return
        for embedded in sorted(extract_home_paths(stripped, home)):
            candidates.append((origin, embedded, False))

    for plist_dir in plist_dirs:
        if not plist_dir.exists():
            continue
        try:
            plist_paths = sorted(plist_dir.glob("*.plist"))
        except OSError as exc:
            errors.append(f"plist-dir unreadable ({type(exc).__name__}): {plist_dir}")
            continue
        for plist_path in plist_paths:
            try:
                payload = plistlib.loads(plist_path.read_bytes())
            except Exception as exc:  # noqa: BLE001 — fail-visible, not fail-open
                payload = _plutil_recovered_plist(plist_path)
                if payload is None:
                    errors.append(
                        f"plist unreadable/unparseable ({type(exc).__name__}): {plist_path}"
                    )
                    continue
            if not isinstance(payload, dict):
                errors.append(f"plist root is not a dict: {plist_path}")
                continue
            origin = f"plist:{plist_path.name}"
            program = payload.get("Program")
            if isinstance(program, str):
                _collect_arg(origin, program, 0)
            program_args = payload.get("ProgramArguments")
            if isinstance(program_args, list):
                for pos, arg in enumerate(program_args):
                    _collect_arg(origin, str(arg), pos)

    for line_no, line in enumerate(crontab_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for embedded in sorted(extract_home_paths(stripped, home)):
            candidates.append((f"crontab:line{line_no}", embedded, False))

    repo_resolved = repo_root.resolve()
    seen: set[tuple[str, str]] = set()
    for origin, norm, always_payload in candidates:
        if (origin, norm) in seen:
            continue
        seen.add((origin, norm))
        if not always_payload and not is_payload_candidate(norm, home):
            continue  # data/log/env argument, not executed code
        expanded = expand_home(norm, home)
        try:
            resolved = expanded.resolve()
        except OSError:
            resolved = expanded
        # Inside-repo on EITHER form: a .venv interpreter under the checkout is
        # a symlink resolving to Homebrew — still repo-resident, not a HOME-fork.
        inside_repo = False
        rel = None
        for probe in (expanded, resolved):
            try:
                rel = probe.relative_to(repo_resolved)
                inside_repo = True
                break
            except ValueError:
                continue
        if inside_repo and rel is not None and rel.parts[:1] == (".worktrees",):
            # W81: launchd armed against an ephemeral agent worktree is drift,
            # not a cured state — the worktree can be reaped under it.
            findings.append(
                f"WORKTREE-REF: {norm} executed by {origin} — payload lives in an "
                f"ephemeral agent worktree (W81 deploy-worktree trauma); repoint to "
                f"the tracked repo path"
            )
            continue
        if inside_repo:
            continue  # executes from the repo checkout — the cured state
        if norm in declared_lives:
            continue
        if _is_allowed(norm, home, allow):
            continue
        exists = "present" if expanded.exists() else "MISSING-ON-DISK"
        findings.append(f"UNDECLARED: {norm} [{exists}] executed by {origin}")
    return findings


# ---------------------------------------------------------------- main


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="declared pairs: live vs repo sha256")
    parser.add_argument("--discover", action="store_true", help="find undeclared HOME-executed payloads")
    parser.add_argument(
        "--strict-bak",
        action="store_true",
        help=(
            "treat .bak shadows beside declared pairs as a failure too (default: "
            "reported, exit unchanged — 83 pre-existing ones on Mini would make "
            "every run red, and a check that is always red is a check somebody "
            "turns off). Bit 8 in the exit code."
        ),
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--strict-checkout",
        action="store_true",
        help="treat a stale local checkout as a failure too (default: reported, exit 0 — "
        "on M5 that checkout is deliberately left behind, see AGENT worktree rule)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="skip the refs-only `git fetch origin main` and arbitrate with the "
        "cached origin/main ref (offline runs; same escape hatch the "
        "proprioception twin exposes)",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--system", action="store_true",
        help="also scan /Library/LaunchAgents + /Library/LaunchDaemons (read-only)",
    )
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--plist-dir", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    # `run_discover` below is `args.discover or not args.check`, so `--check
    # --strict-bak` computes no shadows at all and bit 8 can never be set: the
    # flag would be accepted, silently ignored, and the caller would read the
    # green as "no backups". A flag that does nothing while looking like it did
    # is superscar #2 in a single argument. Refuse it instead.
    if args.strict_bak and args.check and not args.discover:
        parser.error(
            "--strict-bak has no effect with --check alone (the .bak scan lives in "
            "--discover). Use --discover --strict-bak, or both modes."
        )


    run_check = args.check or not args.discover
    run_discover = args.discover or not args.check

    # Resolution is deliberate (worktree-hardened against W81, see
    # _canonical_repo_root's docstring) but was previously SILENT — an
    # invocation from inside a worktree with no explicit --config/--repo-root
    # gave zero indication it was reading the main checkout, not the
    # worktree's own files. Printed unconditionally, before any check/discover
    # work, so a stale-looking result is never mistaken for a checked one.
    resolved_config = args.config.resolve()
    resolved_repo_root = args.repo_root.resolve()
    if not args.json:
        print(f"[resolved] config={resolved_config} repo-root={resolved_repo_root}")

    label = machine_label()
    config = load_config(args.config)
    pairs = merge_pairs(config["pairs"], proprioception_pairs(args.repo_root))
    allow = list(config["allow"])

    breaches: list[str] = []
    undeclared: list[str] = []
    bak_shadows: list[str] = []
    errors: list[str] = []
    stale_checkout: list[str] = []
    skipped_pairs: list[str] = []

    if run_check:
        # Refresh the reference BEFORE anyone is blamed against it. A failure
        # here lands in `errors` (exit bit 4 = CANNOT-VERIFY), never in
        # `breaches` (bit 1 = drift): offline is a natural state, not a fault
        # (Law 6), and a healer that reads "there is a fork" when the truth is
        # "could not check this tick" spends an LLM session on a false premise.
        # Bit 4 is also what `origin_main_sha`'s own docstring demands —
        # "could not attribute" is never "clean" (W84) — so the honest signal
        # is a visible scan error, not a silent fallback to the cached ref.
        if not args.no_fetch:
            fetched, detail = fetch_origin_main(args.repo_root)
            if not fetched:
                errors.append(
                    f"CANNOT-VERIFY: `git fetch origin main` failed in "
                    f"{args.repo_root} ({detail}) — every direction verdict "
                    f"below was computed against a possibly-stale cached "
                    f"origin/main ref, so 'realign live from repo' must not be "
                    f"acted on from this run"
                )
        breaches = check_pairs(
            pairs,
            args.repo_root,
            args.home,
            label,
            notices=stale_checkout,
            skipped=skipped_pairs,
        )
        if args.strict_checkout:
            breaches += stale_checkout
            stale_checkout = []

    if run_discover:
        plist_dirs = [args.plist_dir or (args.home / "Library" / "LaunchAgents")]
        if args.system:
            plist_dirs += [Path("/Library/LaunchAgents"), Path("/Library/LaunchDaemons")]
        crontab = ""
        try:
            proc = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0:
                crontab = proc.stdout
            elif "no crontab for" not in proc.stderr.lower():
                # exit 1 with "no crontab" is the empty case; anything else is
                # an operational failure the report must not hide.
                errors.append(f"crontab -l failed (rc={proc.returncode}): {proc.stderr.strip()[:120]}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"crontab -l unavailable ({type(exc).__name__})")
        declared_lives = {p["live"] for p in pairs}
        undeclared = discover_undeclared(
            plist_dirs, crontab, args.home, args.repo_root, declared_lives, allow, errors
        )
        bak_shadows = discover_bak_shadows(pairs, args.home, label, errors, args.system)

    exit_code = (
        (1 if breaches else 0)
        | (2 if undeclared else 0)
        | (4 if errors else 0)
        | (8 if (bak_shadows and args.strict_bak) else 0)
    )

    if args.json:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "machine": label,
                    "resolved_config": str(resolved_config),
                    "resolved_repo_root": str(resolved_repo_root),
                    "check_breaches": breaches,
                    "check_stale_checkout": stale_checkout,
                    "check_skipped_live_absent": skipped_pairs,
                    "discover_undeclared": undeclared,
                    "discover_bak_shadows": bak_shadows,
                    "errors": errors,
                    "pairs_declared": len(pairs),
                    "exit": exit_code,
                },
                indent=2,
            )
        )
        return exit_code

    if run_check:
        print(f"[check] {len(pairs)} declared pair(s), machine={label}")
        for b in breaches:
            print(f"  - {b}")
        for s in stale_checkout:
            print(f"  ~ {s}")
        if not breaches:
            if stale_checkout:
                print(
                    f"  no HOME-fork — but {len(stale_checkout)} pair(s) differ only "
                    f"because this checkout trails origin/main (--strict-checkout to fail on it)"
                )
            else:
                verified = len(
                    [p for p in pairs if pair_applies(p, label)]
                ) - len(skipped_pairs)
                print(
                    f"  clean — {verified} live copy/copies match their repo twin"
                    if skipped_pairs
                    else "  clean — every live copy matches its repo twin"
                )
        if skipped_pairs:
            # Never touches the exit code: a diagnostic that can fail a build is
            # not a diagnostic. It exists so "clean" is not read as "checked".
            shown = skipped_pairs[:10]
            print(
                f"  {len(skipped_pairs)} pair(s) NOT checked — live copy absent on "
                f"this machine (showing {len(shown)} of {len(skipped_pairs)}):"
            )
            for s in shown:
                print(f"    ? {s}")
    if run_discover:
        print(f"[discover] undeclared HOME-executed payloads: {len(undeclared)}")
        for f in undeclared:
            print(f"  - {f}")
        if not undeclared:
            print("  clean — every HOME-executed payload is declared, allowed, or repo-resident")
        print(
            f"[discover] .bak shadows beside declared pairs: {len(bak_shadows)} "
            f"directory/ies{' (advisory — --strict-bak to fail on them)' if bak_shadows and not args.strict_bak else ''}"
        )
        for f in bak_shadows:
            print(f"  ~ {f}")
        # W84 in the OUTPUT layer, which is the layer a human actually reads: the
        # exit code already carried bit 4, but the line above it said "clean" —
        # so a scan that was DENIED printed the same word as a scan that found
        # nothing. Round 2 caught that; round 3 caught that the FIX was nested
        # under "no shadows", so a run with one finding AND one denied directory
        # printed the count and never mentioned the denial at all. The partial
        # scan is now announced whether or not anything was found, because the
        # incompleteness is a fact about the RUN, not about the findings.
        bak_scan_failed = [e for e in errors if e.startswith("bak-scan ")]
        if bak_scan_failed:
            print(
                f"  CANNOT-VERIFY — {len(bak_scan_failed)} director(y/ies) could not be "
                f"scanned; this run cannot claim to have seen everything"
            )
        elif not bak_shadows:
            print("  clean — no .bak shadow beside any declared live payload")
    if errors:
        print(f"[errors] {len(errors)} operational error(s) — scan is PARTIAL, not clean:")
        for e in errors:
            print(f"  - {e}")
    if exit_code:
        print(
            f"HOME-FORK LINT FAIL (exit {exit_code}: 1=diverged 2=undeclared 4=scan-error "
            f"8=.bak shadows under --strict-bak) — "
            f"superscar #1: declare the pair in infra/home-fork/declared-pairs.json (then "
            f"realign), or allow-list a known-benign payload"
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
