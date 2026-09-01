#!/usr/bin/env python3
"""SOTA L1 (2026-05-24) — Agent Worktree Broker.

Closes the sibling-collision class documented in cicatrix incidents
2026-04-29 #1 + #2 (untracked file loss when sibling automation switches
branches mid-session) and the 17 stash orphans accumulated 2026-05-23.

Convergence 4/4 from the 4-LLM panel (Gemini 3.1 / GPT-5.5 codex /
DeepSeek V4 Pro / Claude Opus 4.7) on the invariant:

    ∀ w₁,w₂ : session(w₁) ∧ session(w₂)
    ⇒ working_tree(w₁) ∩ working_tree(w₂) = ∅

Reference: research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md

Each agent session (subagent dispatch / cron-spawned claude / parallel
Claude Code window) MUST run inside a dedicated worktree under
`<REPO_ROOT>/.worktrees/<LANE>-<TASK_ID>/`. The main checkout is
reserved for operator interactive use + cicatrix hotfixes.

Subcommands:
    --lane / --task-id      Create a new worktree (default action).
    --list                  Show active worktrees + age + WIP indicator.
    --cleanup               Remove worktrees whose TTL expired (WIP-safe).
    --release <task-id>     Tear down a specific worktree + branch.

Kill switch:
    AGENT_BROKER_ENABLED=false   Disables every create/cleanup/release op
                                  (lesson W33). --list stays available.

Logs:
    ~/logs/agent-broker.log     Rotating (RotatingFileHandler 1MB x 5).
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The file whose presence identifies a directory as THIS repo's main checkout.
# Same signature the two worktree hooks use (`infra/claude-hooks/`), on purpose:
# tools that must agree on "where is the main checkout" do not each invent a test.
ROOT_SIGNATURE = "scripts/agent_start.py"
REPO_ROOT_ENV = "NUZ_REPO_ROOT"


def _carries_root_signature(root: Path) -> bool:
    """True iff `root` carries the signature file.

    NOT the same question as "is the main checkout": a linked worktree is a full
    checkout and carries it too. Compose with `_main_checkout_of` before trusting
    this as an answer about the main checkout.
    """
    try:
        return (root / ROOT_SIGNATURE).is_file()
    except OSError:
        # An unreadable/absurd path is "not the repo", never a crash.
        return False


def _main_checkout_of(path: Path) -> Path | None:
    """The MAIN checkout owning `path`, or None if git cannot say.

    `git rev-parse --git-common-dir` reports the SHARED `.git` from anywhere
    inside a repo — including from a linked worktree, where the per-worktree
    git-dir differs. Its parent is therefore the main checkout whether `path` is
    the main checkout, a worktree, or a subdirectory of either.

    This is what stops the signature from over-accepting: `.worktrees/ops-task`
    contains `scripts/agent_start.py` (it is a checkout of this very repo), so a
    signature test alone would happily accept a worktree as "the main checkout"
    and nest `.worktrees` inside it — the W63 shape the signature was added to
    prevent. Normalising is friendlier than refusing and matches what this
    function is documented to return: someone who points at a worktree gets the
    main checkout, which is the only thing the broker may operate on.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=str(path), capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return Path(out.stdout.strip()).parent


def _derive_repo_root() -> Path:
    """The MAIN checkout, never the worktree this script happens to be sitting in.

    W105 upstream half (2026-07-26). This used to be `Path(__file__).resolve().parents[1]`
    — derived from the SCRIPT's location — so running the copy that lives inside a
    worktree pointed `WORKTREES_DIR` at `<worktree>/.worktrees` and the broker cheerfully
    nested a worktree inside a worktree (W63). That is not a hypothetical: every agent
    lane cds into its worktree, and `python scripts/agent_start.py` there is the
    documented quick-start, so the wrong copy is the CONVENIENT one to run.

    `git rev-parse --git-common-dir` answers with the MAIN repo's `.git` from anywhere
    inside it, including from a linked worktree — which is exactly the question being
    asked. Same derivation the worktree-isolation hook already uses for the same reason
    (`infra/claude-hooks/worktree_isolation.py::_derive_repo_root`); two tools that must
    agree about "where is the main checkout" should not each invent an answer.

    Signature-guarded: a derived root that does not carry `scripts/agent_start.py` is
    refused, so a cwd that has wandered into some OTHER git repo can never silently
    retarget the broker.

    The signature guard used to protect ONLY the git-derived answer, while the
    fallback `return script_dir` was bare — and that is the half that bit us
    (2026-08-08, m5). On m5 the main checkout is deliberately never pulled (W106b),
    so the way to run CURRENT code is `git show origin/main:<script> > /tmp/x.py`.
    Do that here and `script_dir` becomes `/` (parents[1] of `/tmp/x.py`), git says
    "not a git repository", the bare fallback returns `/`, `WORKTREES_DIR` becomes
    `/.worktrees` — and `--list` prints "(no active worktrees under .worktrees/)"
    while real worktrees sit there. It does not error. **An empty inventory read as
    cleanliness is the calm liar (W84)**, and the organ lying is the worktree broker,
    i.e. a sibling-race safety guard (#5).

    So every candidate is signature-checked, in the precedence the other three
    tools in this family already use (`infra/claude-hooks/README.md`):

      1. `NUZ_REPO_ROOT`  — explicit override; the SAME name `proprioception.py`
         and both worktree hooks read, so the out-of-tree escape hatch finally
         carries over to this script instead of stopping at the other two.
      2. git, asked from the CALLER's cwd.
      3. git, asked from the script's directory — the W105 reason git beats the
         script's own location: from a worktree it still answers "main checkout".
      4. the script's own directory — the ordinary in-repo case with no git.
      5. `~/nuzantara` — machine-agnostic (Pro `/Users/nuzantara`, m5
         `/Users/balizero`), the same last resort the hooks use. This is what makes
         a `/tmp` copy work rather than merely fail politely.

    Candidates that did NOT come out of git are normalised through
    `_main_checkout_of` before being returned, because a linked worktree carries
    the signature too: without that step `NUZ_REPO_ROOT=.worktrees/ops-task`
    would be accepted as "the main checkout" and the broker would nest under it
    (W63) — the signature answers "is this a checkout of this repo", never "is
    this THE main one". The git-derived candidates are already main checkouts by
    construction, and normalisation runs on the WINNER only, so no invocation
    pays for a candidate it never reaches.

    If NOTHING carries the signature we RAISE. Refusing to answer is the only
    honest option left: any Path we could return here produces a confident,
    empty, wrong inventory. An explicit `NUZ_REPO_ROOT` that fails is named in
    the error rather than silently skipped — a wrong override that degrades to a
    different repo is exactly the retarget the guard exists to stop.
    """
    def _normalise(p: Path) -> Path:
        """A worktree (or a subdirectory) resolves to the main checkout that owns it."""
        return _main_checkout_of(p) or p

    env_root = os.environ.get(REPO_ROOT_ENV, "").strip()
    if env_root:
        explicit = _normalise(Path(env_root).expanduser())
        if _carries_root_signature(explicit):
            return explicit
        # Deliberately terminal, not "try the next candidate": someone NAMED a
        # root. Falling through would run the broker against a different repo
        # than the one asked for, which is the exact retarget the signature
        # guard exists to prevent — and it would do it silently.
        raise SystemExit(
            f"ERROR: {REPO_ROOT_ENV}={env_root} does not resolve to a checkout "
            f"carrying {ROOT_SIGNATURE}. Fix or unset it; refusing to silently fall "
            "back to a different root than the one you named."
        )

    # (label, path, needs_normalising). Candidates that already came OUT of
    # `--git-common-dir` are main checkouts by construction; normalising them
    # again would spend a git subprocess to learn what we just asked. The flag
    # keeps the remaining normalisation LAZY — it runs on the winner only, not
    # once per invocation on a `~/nuzantara` we may never reach.
    candidates: list[tuple[str, Path, bool]] = []
    script_dir = Path(__file__).resolve().parents[1]

    # The CALLER's cwd first: running an out-of-tree copy (`python3 /tmp/x.py`)
    # from inside the checkout is a real and correct invocation, and asking git
    # only where the SCRIPT sits answers about /tmp — a repo the caller is
    # standing in gets ignored in favour of raising. The signature guard below
    # is what keeps this safe when the cwd has wandered into another project.
    try:
        cwd_root = _main_checkout_of(Path.cwd())
        if cwd_root is not None:
            candidates.append(("git --git-common-dir (cwd)", cwd_root, False))
    except OSError:
        pass  # cwd deleted underneath us

    script_root = _main_checkout_of(script_dir)
    if script_root is not None:
        candidates.append(("git --git-common-dir (script)", script_root, False))

    candidates.append(("script location", script_dir, True))
    candidates.append(("~/nuzantara", Path.home() / "nuzantara", True))

    tried: list[str] = []
    for label, cand, needs_norm in candidates:
        if not _carries_root_signature(cand):
            tried.append(f"{label}={cand}")
            continue
        return _normalise(cand) if needs_norm else cand

    raise SystemExit(
        "ERROR: cannot locate the nuzantara main checkout — every candidate lacks "
        f"the {ROOT_SIGNATURE} signature. Tried: " + "; ".join(tried) + ". "
        f"Set {REPO_ROOT_ENV}=/path/to/nuzantara and re-run. Refusing to guess: a "
        "guessed root reports an EMPTY worktree inventory, which reads as 'nothing "
        "to clean up' when the truth is 'I looked in the wrong place'."
    )


REPO_ROOT = _derive_repo_root()
WORKTREES_DIR = REPO_ROOT / ".worktrees"
TASK_METADATA_FILENAME = ".agent-task.json"
# Broker-generated files that must NOT count as user WIP (otherwise every
# freshly created worktree reads as dirty and is never cleanup-eligible).
# `node_modules` is a SYMLINK_TARGETS entry: .gitignore has `node_modules/`
# (directory-only pattern) but no bare `node_modules` rule, and git's ignore
# matching does not treat a symlink-to-a-directory as a directory — so the
# broker's own symlink shows up as `?? node_modules` in every worktree,
# permanently tripping the WIP guard and making `--cleanup` a no-op forever
# (found live: 3 worktrees sat 5-14h past a 60min TTL, silently "WARN"-skipped
# by the daily cron every run). Reproduced empirically before this fix.
# `.husky/_` is here for the same reason as node_modules: it is a
# SYMLINK_TARGETS entry, and .husky/.gitignore does not cover it, so without
# this the broker's own shim symlink would read as `?? .husky/_` and re-create
# the very never-cleanup-eligible bug the node_modules note describes.
# `apps/mouth/node_modules` is listed for that same reason, and the reason is
# NOT visible on every machine — which is exactly why it is listed rather than
# left to the ignore rules. Measured 2026-08-07 across the fleet: the symlink
# reads as ignored on M5 and Pro purely because a BARE `node_modules` line sits
# in their `.git/info/exclude` — a local, untracked, per-machine file. Mini has
# no such line (0 matches), and the repo's own .gitignore only carries the
# directory-only `node_modules/`, which does not match a symlink-to-a-directory.
# So on Mini this entry would read `?? apps/mouth/node_modules` and permanently
# trip the WIP guard. Trusting one machine's clean `git status` here would have
# been trusting a machine-local accident.
BROKER_GENERATED_FILES = frozenset(
    {
        ".agent-task.json",
        ".env.worktree",
        "node_modules",
        "apps/mouth/node_modules",
        ".husky/_",
    }
)
LSOF_FALLBACK_PATHS: tuple[Path, ...] = (Path("/usr/sbin/lsof"),)

# Lanes documented in CLAUDE.md + research synthesis.
# This is an ALLOW-list for create; --list/--cleanup/--release accept any lane
# that already has a metadata file on disk (forward-compat for new lanes).
KNOWN_LANES: set[str] = {
    "wr2",
    "wr3",
    "infra",
    "docs",
    "db",
    "cicatrix-fix",
    "mouth",  # reserved for Subhi per CLAUDE.md §12
    "intel",
    "cell",
    "organism",
    "mata-garuda",
    "backend-rag",
    "frontend",
    "ops",
}

# Lane / task-id validation: lowercase, digits, dash. No slashes (would break
# the branch ref and the directory path).
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,63}$")

# Symlinks created from main checkout into the new worktree (env-safe).
# Targets are relative paths inside the repo. If the target does not exist in
# main, the symlink is skipped silently — the agent will still get a working
# worktree, just without that helper artifact.
#
# `.husky/_` is load-bearing, not a convenience. `core.hooksPath` is the
# RELATIVE path `.husky/_`, which git resolves against each working tree — and
# `_` is husky's generated shim dir, produced by `npm install` in the main
# checkout and therefore never carried over by `git worktree add`. Without it a
# worktree resolves hooksPath to nothing and EVERY push from it silently skips
# the pre-push gate: no banner, no suite, exit 0. That is the worst shape a gate
# can fail in (superscar #2 — the push looks green because nothing ran), and it
# lands exactly where CLAUDE.md mandates all agent work happen. Measured
# 2026-07-16: three probe pushes from two worktrees, no gate; symlink the dir in
# and the same push runs the full suite.
# `apps/mouth/node_modules` is load-bearing for the same class of reason as
# `.husky/_`, one layer down. This is an npm WORKSPACE monorepo, so a workspace
# package's own deps are installed NESTED (`apps/mouth/node_modules/<pkg>`), not
# hoisted to the root — `recharts` lives only there. Node resolves upward from
# the importing file, so a worktree that symlinks only the ROOT node_modules
# still finds nothing, and `npm run typecheck` dies with
# `TS2307: Cannot find module 'recharts'` on two files. That is the command the
# pre-commit hook runs whenever apps/mouth TS/TSX is staged, so without this
# every mouth lane hits a hard failure whose cause names a package the lockfile
# demonstrably resolves — and the obvious readings ("the lock is broken", "the
# dep is missing") are both wrong. Measured 2026-08-07: only 5 of 37 live
# worktrees had this directory, each because someone ran the install by hand.
# Reproduced and proven in a fresh worktree before this change: typecheck exits
# 2 without the symlink and 0 with it, nothing else altered.
SYMLINK_TARGETS: tuple[tuple[str, str], ...] = (
    ("apps/backend-rag/.venv", "apps/backend-rag/.venv"),
    ("apps/backend-rag/.env", "apps/backend-rag/.env"),
    ("node_modules", "node_modules"),
    ("apps/mouth/node_modules", "apps/mouth/node_modules"),
    (".husky/_", ".husky/_"),
)

LOG_DIR = Path.home() / "logs"
LOG_FILE = LOG_DIR / "agent-broker.log"

KILL_SWITCH_ENV = "AGENT_BROKER_ENABLED"

# W62 ANTIBODY #1: cleanup must not reap a TTL-expired-but-clean worktree that
# is still being actively worked on. A worktree touched more recently than this
# threshold is treated as a live session and skipped (override with --force or
# skip_recent_minutes=0).
RECENT_ACTIVITY_MINUTES = 10

# W62 ANTIBODY #2/#3: a worktree older than this multiple of its TTL is a
# suspected orphan (surfaced by --list, gated by the CI hygiene test).
ORPHAN_TTL_MULTIPLE = 2

# ---------------------------------------------------------------------------
# RAM admission gate (2026-08-13, Zero's directive)
# ---------------------------------------------------------------------------
#
# Measured on M5 the night this was written (~03:20): 883 processes, load
# average 157 on 10 cores, swap 10801M/11264M used (96%), 1.6GB free RAM with
# 9.2GB in the compressor. The pytest holding the pre-push lock had 24 minutes
# of wall clock and 6 minutes of CPU — in the next 20 real seconds it earned
# 0.01 CPU-seconds. Not stuck: STARVED. It held the lock for hours; every
# session behind it queued; the fourth in line timed out at 75min. Zero's
# framing: reject the CREATION of a new lane when the machine is already this
# far underwater — it cannot save the 883 processes already running, but it
# stops the 884th from queuing behind the same starved lock.
#
# Signal choice — `memory_pressure`'s "free %" is a proxy that LIES (superscar
# #9): sampled at the same moment as the numbers above, it reported "33% free"
# while swap sat at 96%. Zero's instruction was therefore "use swap, not
# memory_pressure alone" — but a same-night cross-fleet sample (2026-08-13
# ~03:50-03:55, LC_ALL=C sysctl on all three machines) shows swap-% alone does
# NOT discriminate crisis from ordinary business on this fleet: Pro sat at
# 7859/9216MB=85% and Mini at 4788/5120MB=94% while both were plainly calm
# (see below) — macOS's swap file is a high-water mark that does not shrink
# back down once pressure has passed, so "swap mostly full" turns out to be
# this fleet's normal resting state, not a crisis signal by itself. The signal
# that DID separate crisis from calm cleanly, same snapshot:
#
#     machine  cores  load(5m)  load/core   swap%   verdict
#     M5(then)   10    ~420      ~42x        ~96%    CRISIS (the incident)
#     Pro        14     13.2     ~0.9x        85%    calm (near saturation, not over)
#     Mini       12      4.0     ~0.3x        94%    calm despite high swap%
#
# So the gate requires BOTH swap% and load-per-core over threshold (AND, not
# OR) — swap alone would have false-positived on calm Mini; load alone would
# ignore Zero's explicit "use swap" instruction. `os.getloadavg()` reads the
# getloadavg(3) syscall directly (floats, no text/locale exposure) — no need
# to shell out to `uptime`. Threshold picks (generous on purpose — requirement
# is "must reject tonight's numbers, must never fire on an ordinary day"):
# 5x/core load ratio and 90% swap are each far outside the calm-Pro/calm-Mini
# band above and far inside the crisis-M5 band, leaving wide margin either way.
#
# LOCALE GOTCHA (found writing this, M5, LANG=it_IT.UTF-8): `sysctl
# vm.swapusage` renders its numbers in the CALLER's locale — under it_IT the
# decimal separator is a COMMA ("used = 10858,38M"), not a period. A naive
# `float()` on that string raises ValueError on every Italian-locale session,
# which is to say on the one machine this gate exists to protect — the sample
# would silently read as "cannot measure" and the gate would fail-open FOREVER
# on M5, never once firing. Forcing `LC_ALL=C` on the subprocess env sidesteps
# it: verified empirically, same live sysctl call, comma with the session's
# real locale vs period under LC_ALL=C.
#
# Fail-open (superscar #2, "esiste non armato" cuts both ways: a gate that
# blocks work because IT is broken is worse than one that lets a broken
# machine through once): any sysctl/loadavg failure, timeout, or parse miss
# admits the lane, logging that the machine could NOT be measured — which is a
# distinct claim from "the machine is fine" and must never be read as one.
#
# LIMIT this gate does NOT claim to fix: it blocks the NEXT lane's admission.
# It does nothing for the 883 processes already running tonight, and nothing
# for a machine that crosses the threshold *after* a lane is already admitted.
RAM_ADMISSION_OVERRIDE_ENV = "AGENT_RAM_ADMISSION_OVERRIDE"
RAM_ADMISSION_SWAP_PCT_ENV = "AGENT_RAM_ADMISSION_SWAP_PCT_MAX"
RAM_ADMISSION_LOAD_RATIO_ENV = "AGENT_RAM_ADMISSION_LOAD_RATIO_MAX"
RAM_ADMISSION_DEFAULT_SWAP_PCT_MAX = 90.0
RAM_ADMISSION_DEFAULT_LOAD_RATIO_MAX = 5.0
# sysexits.h EX_TEMPFAIL: "temporary failure, user is invited to retry" — the
# semantically correct code for "not now", distinct from the generic exit 1
# every validation error in this file already uses, so a caller (cron wrapper,
# CI) can tell "machine is busy, retry later" apart from "you typo'd the lane".
RAM_ADMISSION_EXIT_CODE = 75


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _init_logger() -> logging.Logger:
    logger = logging.getLogger("agent_broker")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s agent_broker[%(process)d] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    # File handler with rotation (best-effort — failure must not crash the CLI).
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_048_576, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


logger = _init_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kill_switch_active() -> bool:
    """True if the broker is disabled via env var (lesson W33)."""
    val = os.environ.get(KILL_SWITCH_ENV, "").strip().lower()
    return val in {"false", "0", "no", "off", "disabled"}


def _hostname_short() -> str:
    """Return the short hostname (first dotted segment), lowercased.

    The hostname is reused as a branch-path segment, so we lowercase + strip
    anything outside [a-z0-9-].
    """
    raw = socket.gethostname().split(".")[0].lower()
    cleaned = re.sub(r"[^a-z0-9-]", "-", raw).strip("-")
    return cleaned or "unknown-host"


def _validate_id(label: str, value: str) -> None:
    if not ID_PATTERN.match(value):
        raise SystemExit(
            f"ERROR: invalid {label} '{value}' — must match {ID_PATTERN.pattern}"
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime:
    # Accept both `...Z` and `...+00:00`.
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around `git ...` that captures output.

    Returns the CompletedProcess. When check=True (default) raises
    CalledProcessError with stderr piped into the exception for diagnosis.
    """
    cmd = ["git", *args]
    cwd = cwd or REPO_ROOT
    logger.debug("git: %s (cwd=%s)", " ".join(cmd), cwd)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, proc.stdout, proc.stderr
        )
    return proc


def _branch_name(host: str, lane: str, task_id: str) -> str:
    return f"agent/{host}/{lane}/{task_id}"



def _refuse_if_nested(target: Path) -> None:
    """SystemExit if `target` would land inside an existing worktree (W63/W105).

    Judges the ENTITY: only paths git actually reports as worktrees count, and the main
    checkout is excluded (every worktree is "inside" it by construction — treating that
    as nesting would refuse every creation). A probe failure is NOT read as "nothing is
    nested" (family #2); it degrades to the structural check that a `.worktrees` segment
    must not appear twice in the path, which is the shape nesting always takes.
    """
    try:
        target_real = target.resolve()
    except Exception:
        target_real = target
    if str(target_real).count("/.worktrees/") > 1:
        raise SystemExit(
            f"ERROR: refusing to create a worktree inside another worktree: {target_real}\n"
            "       (a `.worktrees` segment appears twice — run agent_start.py against the "
            "main checkout)"
        )
    try:
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return
    except Exception:
        return
    repo_real = REPO_ROOT.resolve()
    for line in out.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        try:
            known = Path(line[len("worktree "):].strip()).resolve()
        except Exception:
            continue
        if known == repo_real:
            continue  # the main checkout contains them all — not nesting
        if known == target_real or known in target_real.parents:
            raise SystemExit(
                f"ERROR: refusing to create a worktree inside an existing one.\n"
                f"       target : {target_real}\n"
                f"       inside : {known}\n"
                "       Run agent_start.py against the main checkout instead."
            )


def _worktree_path(lane: str, task_id: str) -> Path:
    return WORKTREES_DIR / f"{lane}-{task_id}"


# ---------------------------------------------------------------------------
# RAM admission gate — sampling
# ---------------------------------------------------------------------------


def _float_env(name: str, default: float) -> float:
    """Parse a float from env, falling back to `default` on missing/bad value.

    A malformed override (typo, empty string) must not crash the broker — it
    degrades to the built-in default, same fail-open spirit as the rest of
    this gate.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("ignoring malformed %s=%r, using default %.1f", name, raw, default)
        return default


def _sample_swap_usage() -> tuple[float, float] | None:
    """Return (used_mb, total_mb) from `sysctl vm.swapusage`, or None on any
    failure (missing binary, timeout, unexpected output, unparseable number).

    `LC_ALL=C` on the subprocess env is load-bearing, not cosmetic: `sysctl`
    renders `vm.swapusage` in the CALLER's locale, and under `it_IT.UTF-8`
    (this machine's session locale) the decimal separator is a COMMA
    ("used = 10858,38M") — `float()` on that raises ValueError and every
    sample on this machine would read as unmeasurable, forever. See the
    RAM_ADMISSION module comment for the measured before/after.
    """
    try:
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        proc = subprocess.run(
            ["sysctl", "vm.swapusage"],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("RAM admission: sysctl vm.swapusage failed: %s", exc)
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        logger.warning(
            "RAM admission: sysctl vm.swapusage rc=%s stdout=%r",
            proc.returncode,
            proc.stdout,
        )
        return None
    # "vm.swapusage: total = 11264.00M  used = 10858.38M  free = 405.62M ..."
    m = re.search(r"total\s*=\s*([\d.]+)M\s+used\s*=\s*([\d.]+)M", proc.stdout)
    if not m:
        logger.warning("RAM admission: unparseable swapusage output: %r", proc.stdout)
        return None
    try:
        total_mb = float(m.group(1))
        used_mb = float(m.group(2))
    except ValueError:
        return None
    if total_mb <= 0:
        return None
    return used_mb, total_mb


def _sample_load_ratio() -> tuple[float, int] | None:
    """Return (load5, ncpu), or None on any failure.

    `os.getloadavg()` reads the getloadavg(3) syscall directly — floats, no
    text to parse, no locale exposure (unlike shelling out to `uptime`, whose
    output is also locale-formatted). The 5-minute average is used rather than
    1-minute: sustained pressure (what this gate protects against — a machine
    that has been drowning for many minutes) should not be judged by a single
    noisy 60s sample.
    """
    try:
        _load1, load5, _load15 = os.getloadavg()
        ncpu = os.cpu_count()
    except OSError as exc:
        logger.warning("RAM admission: getloadavg failed: %s", exc)
        return None
    if not ncpu or ncpu <= 0:
        return None
    return load5, ncpu


def check_ram_admission() -> tuple[bool, str]:
    """Admission decision for creating a NEW lane. Returns (admit, reason).

    admit=True means "go ahead" — either the machine is healthy, the operator
    overrode the gate, OR the machine could not be measured (fail-open: not
    being able to check is not the same claim as being fine, see the log line
    in the last branch). admit=False means both swap-% and load-per-core are
    over their configured thresholds — REFUSED, not merely warned.

    Both signals must be over threshold (AND), not either alone (OR): a same-
    night cross-fleet sample (see module comment) found swap-% alone reads
    ~85-94% on machines that were plainly calm (load well under 1x/core) —
    macOS's swap file is a high-water mark that does not shrink back down, so
    "swap mostly full" is this fleet's ordinary resting state. Load-per-core
    was the signal that cleanly separated the M5 incident (~42x/core) from
    calm Pro/Mini (~0.3-0.9x/core) that same night.
    """
    override = os.environ.get(RAM_ADMISSION_OVERRIDE_ENV, "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True, f"{RAM_ADMISSION_OVERRIDE_ENV} set — admission gate bypassed"

    # Defensive try/except HERE, not just inside the samplers: this is a
    # health-check probe, and a probe that can crash its own caller is a
    # broken gate, not a working one (superscar #2). The samplers already
    # catch the exceptions they anticipate (OSError, TimeoutExpired) — this
    # is the backstop for whatever they don't, so "the sampler raised" always
    # degrades to fail-open, never to an unhandled exception that takes the
    # whole `agent_start.py` invocation down with it.
    try:
        swap_sample = _sample_swap_usage()
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see above
        logger.warning("RAM admission: swap sampler raised %r — fail-open", exc)
        swap_sample = None
    try:
        load_sample = _sample_load_ratio()
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see above
        logger.warning("RAM admission: load sampler raised %r — fail-open", exc)
        load_sample = None
    if swap_sample is None or load_sample is None:
        msg = (
            "RAM admission gate: could not measure machine state "
            "(sysctl/getloadavg unavailable or unparseable) — admitting, "
            "fail-open. This is NOT a claim the machine is healthy."
        )
        logger.warning(msg)
        return True, msg

    used_mb, total_mb = swap_sample
    swap_pct = used_mb / total_mb * 100.0
    load5, ncpu = load_sample
    load_ratio = load5 / ncpu

    swap_max = _float_env(RAM_ADMISSION_SWAP_PCT_ENV, RAM_ADMISSION_DEFAULT_SWAP_PCT_MAX)
    load_max = _float_env(RAM_ADMISSION_LOAD_RATIO_ENV, RAM_ADMISSION_DEFAULT_LOAD_RATIO_MAX)

    if swap_pct >= swap_max and load_ratio >= load_max:
        reason = (
            f"REFUSED: machine is memory-distressed — swap {swap_pct:.1f}% used "
            f"(threshold {swap_max:.0f}%) AND load {load5:.1f} on {ncpu} cores = "
            f"{load_ratio:.1f}x/core (threshold {load_max:.1f}x/core). "
            "A new lane would queue behind an already-starved machine, not run. "
            "Close some sessions, or launch this lane on Mini/Pro instead. "
            f"One-time override: {RAM_ADMISSION_OVERRIDE_ENV}=1."
        )
        return False, reason

    return True, (
        f"RAM admission OK — swap {swap_pct:.1f}% used (threshold {swap_max:.0f}%), "
        f"load {load5:.1f}/{ncpu} cores = {load_ratio:.1f}x/core "
        f"(threshold {load_max:.1f}x/core)"
    )


# ---------------------------------------------------------------------------
# Metadata dataclass
# ---------------------------------------------------------------------------


@dataclass
class TaskMetadata:
    task_id: str
    lane: str
    branch: str
    host: str
    created_at: str
    ttl_minutes: int
    pid: int
    base_branch: str
    worktree_path: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "task_id": self.task_id,
                "lane": self.lane,
                "branch": self.branch,
                "host": self.host,
                "created_at": self.created_at,
                "ttl_minutes": self.ttl_minutes,
                "pid": self.pid,
                "base_branch": self.base_branch,
                "worktree_path": self.worktree_path,
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_path(cls, path: Path) -> "TaskMetadata":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            task_id=data["task_id"],
            lane=data["lane"],
            branch=data["branch"],
            host=data["host"],
            created_at=data["created_at"],
            ttl_minutes=int(data["ttl_minutes"]),
            pid=int(data["pid"]),
            base_branch=data.get("base_branch", "main"),
            worktree_path=data.get("worktree_path", ""),
        )

    def is_expired(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        try:
            created = _parse_iso(self.created_at)
        except ValueError:
            return False  # malformed timestamp → operator must intervene
        age_minutes = (now - created).total_seconds() / 60.0
        return age_minutes > self.ttl_minutes

    def age_minutes(self, *, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        try:
            created = _parse_iso(self.created_at)
        except ValueError:
            return -1.0
        return (now - created).total_seconds() / 60.0


# ---------------------------------------------------------------------------
# Symlink helper
# ---------------------------------------------------------------------------


def _create_symlinks(worktree: Path) -> list[str]:
    """Create env-safe symlinks from main checkout into the new worktree.

    Returns the list of relative symlink targets actually created (skips any
    target that does not exist in main, plus any that would clobber an existing
    file/dir in the worktree).
    """
    created: list[str] = []
    for source_rel, dest_rel in SYMLINK_TARGETS:
        source = REPO_ROOT / source_rel
        dest = worktree / dest_rel
        if not source.exists():
            logger.debug("symlink skip (no source): %s", source_rel)
            continue
        if dest.exists() or dest.is_symlink():
            logger.debug("symlink skip (dest exists): %s", dest_rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(source, dest)
            created.append(dest_rel)
        except OSError as exc:
            logger.warning("symlink failed %s -> %s: %s", dest_rel, source, exc)
    return created


# ---------------------------------------------------------------------------
# Subcommand: create
# ---------------------------------------------------------------------------


def cmd_create(
    lane: str,
    task_id: str,
    *,
    ttl_minutes: int = 60,
    base_branch: str = "main",
    allow_unknown_lane: bool = False,
) -> Path:
    """Create a new worktree + branch + metadata.

    Returns the absolute path to the new worktree.

    Raises SystemExit on validation or git error so the CLI exits non-zero.
    A RAM-distressed machine raises SystemExit(RAM_ADMISSION_EXIT_CODE)
    specifically (see check_ram_admission) rather than the generic exit 1
    every other validation failure here uses — a caller can tell "not now,
    retry" apart from "malformed request".
    """
    if _kill_switch_active():
        raise SystemExit(
            f"ERROR: broker disabled ({KILL_SWITCH_ENV}=false). "
            "Unset or set to 'true' to re-enable."
        )

    admit, admission_reason = check_ram_admission()
    if not admit:
        print(admission_reason, file=sys.stderr)
        logger.warning("RAM admission gate REFUSED create: %s", admission_reason)
        raise SystemExit(RAM_ADMISSION_EXIT_CODE)
    logger.info(admission_reason)

    _validate_id("lane", lane)
    _validate_id("task-id", task_id)

    if lane not in KNOWN_LANES and not allow_unknown_lane:
        known = ", ".join(sorted(KNOWN_LANES))
        raise SystemExit(
            f"ERROR: unknown lane '{lane}'. Known: {known}.\n"
            f"Pass --allow-unknown-lane to override."
        )

    if ttl_minutes <= 0:
        raise SystemExit("ERROR: --ttl-min must be > 0")

    host = _hostname_short()
    branch = _branch_name(host, lane, task_id)
    worktree = _worktree_path(lane, task_id)

    if worktree.exists():
        raise SystemExit(
            f"ERROR: worktree already exists at {worktree}. "
            f"Use --release {task_id} first or pick a different task-id."
        )

    # Pre-flight: branch must not already exist (worktree add -b would fail
    # with a less-clear error otherwise).
    existing_branches = _run_git(["branch", "--list", branch]).stdout.strip()
    if existing_branches:
        raise SystemExit(
            f"ERROR: branch '{branch}' already exists. "
            "Choose a different task-id or delete the stale branch."
        )

    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)

    # Base the worktree on the FRESH upstream tip, not the (possibly stale)
    # local branch. The main checkout routinely lags origin/main by dozens of
    # commits on this high-traffic repo (it is read-only for agents, so nothing
    # fast-forwards it). Branching from local `main` then yields a worktree N
    # commits behind → every PR opened from it conflicts with intervening work
    # on the same files (sibling-race / merge-train class, superscar #5).
    # Fetch origin/<base> and branch from there. If the fetch fails (offline —
    # Law 6 sovereignty: disconnection is a NORMAL state, not a fault), fall
    # back to the local ref with a loud warning rather than blocking work.
    start_point = base_branch
    try:
        _run_git(["fetch", "origin", base_branch])
        start_point = f"origin/{base_branch}"
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "could not fetch origin/%s (offline?) — basing worktree on LOCAL "
            "%s, which may lag upstream: %s",
            base_branch,
            base_branch,
            (exc.stderr or "").strip(),
        )

    logger.info(
        "creating worktree lane=%s task_id=%s branch=%s base=%s start=%s ttl_min=%d",
        lane,
        task_id,
        branch,
        base_branch,
        start_point,
        ttl_minutes,
    )

    # BACKSTOP (W105 upstream half): never create a worktree INSIDE another one.
    # `_derive_repo_root()` above already makes this unreachable in the normal case,
    # but it falls back to the script-relative answer when git cannot be asked — and a
    # fallback that can still nest is a fallback that will, eventually. `git worktree
    # list` is the authority on what is already a worktree; a path that lands under one
    # is refused with the reason, never created and explained afterwards (W63).
    _refuse_if_nested(worktree)

    try:
        _run_git(["worktree", "add", "-b", branch, str(worktree), start_point])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise SystemExit(f"ERROR: git worktree add failed: {stderr}") from exc

    symlinks = _create_symlinks(worktree)

    metadata = TaskMetadata(
        task_id=task_id,
        lane=lane,
        branch=branch,
        host=host,
        created_at=_utc_now_iso(),
        ttl_minutes=ttl_minutes,
        pid=os.getpid(),
        base_branch=base_branch,
        worktree_path=str(worktree),
    )
    (worktree / TASK_METADATA_FILENAME).write_text(metadata.to_json(), encoding="utf-8")

    # W59 auto-export (cicatrix 2026-05-27): write .env.worktree with BRANCH_EXPECTED
    # for opt-in adoption of W59 hook (PR #899). Operator/agent sources via:
    #   source .env.worktree
    # to auto-protect atomic git sequences from sibling HEAD-race.
    env_worktree_content = (
        "# Auto-generated by scripts/agent_start.py — W59 sibling-race guard env\n"
        "# Source this file before any atomic git sequence:\n"
        "#   source .env.worktree\n"
        f"export BRANCH_EXPECTED={branch}\n"
        f"export AGENT_TASK_ID={task_id}\n"
        f"export AGENT_LANE={lane}\n"
    )
    (worktree / ".env.worktree").write_text(env_worktree_content, encoding="utf-8")

    logger.info(
        "worktree ready path=%s symlinks=%s", worktree, ",".join(symlinks) or "(none)"
    )
    return worktree


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def _iter_metadata(worktrees_dir: Path | None = None) -> Iterable[TaskMetadata]:
    # Resolve at call-time (not import-time) so test fixtures that patch
    # the module-level WORKTREES_DIR after import take effect.
    worktrees_dir = worktrees_dir if worktrees_dir is not None else WORKTREES_DIR
    if not worktrees_dir.is_dir():
        return []
    out: list[TaskMetadata] = []
    for entry in sorted(worktrees_dir.iterdir()):
        meta_path = entry / TASK_METADATA_FILENAME
        if not meta_path.is_file():
            continue
        try:
            out.append(TaskMetadata.from_path(meta_path))
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("skip malformed metadata at %s: %s", meta_path, exc)
    return out


def _worktree_has_wip(worktree: Path) -> bool:
    """True if the worktree has uncommitted changes (tracked or untracked)."""
    proc = _run_git(["status", "--porcelain"], cwd=worktree, check=False)
    if proc.returncode != 0:
        # If git can't read the worktree (corrupt) treat as WIP to be safe.
        return True
    # Ignore broker-generated files (.agent-task.json, .env.worktree) when
    # computing WIP, otherwise every freshly created worktree reports dirty.
    relevant = []
    for line in proc.stdout.splitlines():
        # Porcelain v1: first 2 cols are status, then a space, then path.
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Strip "->" rename targets.
        path = path.split(" -> ")[-1].strip().strip('"')
        if path in BROKER_GENERATED_FILES:
            continue
        relevant.append(line)
    return bool(relevant)


def _worktree_recently_active(
    worktree: Path, *, threshold_minutes: int = RECENT_ACTIVITY_MINUTES
) -> bool:
    """True if the worktree shows filesystem activity within threshold_minutes.

    Distinct from age (created_at): this is a *liveness* probe so cleanup never
    reaps a worktree whose TTL clock expired while a session was still working
    in it (W62 ANTIBODY #1). Signal = newest mtime among the worktree dir, its
    `.git` pointer, and the REAL gitdir HEAD (the linked-worktree gitdir is
    under REPO_ROOT/.git/worktrees/<name>/; HEAD is bumped by commit/checkout —
    codex P2: the `.git` pointer alone is not enough for linked worktrees).

    NB: the gitdir `index` is deliberately NOT probed — `git status` (run by the
    WIP check that precedes this guard) rewrites the index mtime, so it would
    read as "active" on every cleanup pass. HEAD is stable under read-only
    status, so it tracks genuine commit/checkout activity only.

    This is a best-effort liveness heuristic, NOT a security control: an
    adversary could `touch` a path to keep an orphan alive. Its only job is to
    avoid reaping a genuinely active session; the 24h CI cap (find_stale_
    worktrees) is the hard ceiling no heuristic can opt out of.
    """
    if threshold_minutes <= 0:
        return False
    cutoff = time.time() - threshold_minutes * 60
    probes = [worktree, worktree / ".git"]
    real_gitdir = _resolve_worktree_gitdir(worktree)
    if real_gitdir is not None:
        probes.append(real_gitdir / "HEAD")
    try:
        return any(p.exists() and p.stat().st_mtime > cutoff for p in probes)
    except OSError:
        return True


def _resolve_lsof_path() -> str | None:
    """Return an executable lsof path, including macOS launchd's usual fallback."""
    resolved = shutil.which("lsof")
    if resolved:
        return resolved
    for candidate in LSOF_FALLBACK_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _worktree_has_live_process(worktree: Path) -> bool:
    """True if a live OS process has its cwd or an open file inside *worktree*.

    W80 ANTIBODY guard #1. Distinct from `_worktree_recently_active`, which
    reads FILE mtimes: a session that commits-and-reasons-for-minutes without
    touching files outlives the mtime threshold yet is plainly alive. The only
    unambiguous liveness signal is an actual process anchored to the directory,
    so we ask the kernel via `lsof +D`.

    `lsof +D <dir>` walks the directory tree and lists every process holding a
    file open under it — crucially this INCLUDES a process whose current working
    directory (cwd) is the worktree, because lsof reports the cwd fd. A live
    Claude/codex/agy session cd'd into the worktree therefore shows up even when
    it has no regular file open.

    FAIL-SAFE TO TRUE: if `lsof` is missing, errors, or times out, we treat the
    worktree as live (do NOT reap). The cost of a false "alive" is a worktree
    that lingers one more cleanup tick; the cost of a false "dead" is reaping a
    worktree out from under an active session (the W80 bug itself). The 24h CI
    cap (find_stale_worktrees) remains the hard ceiling no heuristic opts out of.

    This is a liveness heuristic, NOT a security control (W62 GOTCHA): an
    adversary could hold an idle fd open. Its job is only to avoid reaping a
    genuinely working session.
    """
    if not worktree.is_dir():
        # No directory ⇒ nothing to anchor a process to ⇒ not live. (Already
        # gone or never created; safe to let cleanup proceed.)
        return False
    lsof_path = _resolve_lsof_path()
    if lsof_path is None:
        logger.warning(
            "lsof not found — treating %s as live (fail-safe, no reap)", worktree
        )
        return True
    try:
        proc = subprocess.run(
            [lsof_path, "+D", str(worktree)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(
            "lsof probe failed for %s (%s) — treating as live (fail-safe)",
            worktree,
            exc,
        )
        return True
    # Parse STDOUT, do NOT key on the exit code. `lsof +D` mixes two cases into
    # rc=1: "found nothing" (truly dead) AND "found matches but hit a warning
    # while descending" (e.g. the linked-worktree `.git` *file* pointer, or a
    # transient entry it could not stat) — and in the SECOND case it STILL
    # prints the matching `cwd`/open-file lines to stdout. Keying on rc would
    # mis-read a live session (cwd anchored) as dead whenever lsof emitted any
    # descent warning. So: ANY data line beyond the `COMMAND ...` header ⇒ LIVE,
    # regardless of rc; only a header-only / empty stdout ⇒ dead. (Empirically
    # verified: a `sleep` child cwd'd into a linked worktree yields rc=1 + one
    # `cwd DIR` line — must read as LIVE.)
    data_lines = [
        ln
        for ln in proc.stdout.splitlines()
        if ln.strip() and not ln.startswith("COMMAND")
    ]
    return bool(data_lines)


def _ls_tree_entry(ref: str, path: str, *, cwd: Path) -> str:
    """mode+type+blob for `path` at `ref`, or "__ABSENT__" if the path does
    not exist there. Unlike `git rev-parse <ref>:<path>` (blob ID only),
    `git ls-tree` also carries the mode and object type — a `chmod +x`, or a
    tracked file replaced by a symlink whose target text equals the blob
    content, changes the ls-tree entry even though the blob is unchanged."""
    proc = _run_git(["ls-tree", ref, "--", path], cwd=cwd, check=False)
    if proc.returncode != 0:
        return "__ABSENT__"
    line = proc.stdout.strip()
    if not line:
        return "__ABSENT__"
    # ls-tree emits "<mode> <type> <blob>\t<path>" — keep mode+type+blob,
    # drop the trailing path (constant for a fixed `path` argument).
    return line.split("\t", 1)[0]


def _is_union_merge_path(path: str, *, cwd: Path) -> bool:
    """True iff this repo's `.gitattributes` declares `path` `merge=union`
    (an append-only ledger — see `.claude/skills/modus/PENDING-ARMS.md`)."""
    proc = _run_git(["check-attr", "merge", "--", path], cwd=cwd, check=False)
    if proc.returncode != 0:
        return False
    # Output form: "<path>: merge: union" (or "unspecified"/"text"/etc).
    return proc.stdout.strip().endswith(": merge: union")


def _content_subset_ok(
    base_ref: str, head_ref: str, main_ref: str, path: str, *, cwd: Path
) -> bool:
    """For a declared merge=union path: True iff every non-blank line the
    branch itself ADDED since its own merge-base is present in origin/main's
    current copy of the same path.

    Deliberately scoped to the branch's OWN added lines (`git diff
    base_ref..head_ref`), not — as an earlier version of this function did —
    every line present in HEAD's full snapshot. An append-only ledger is not
    append-ONLY in practice: a healer tick routinely edits an EXISTING row
    (correcting it, appending "NEW EVIDENCE", closing it) rather than only
    adding new ones. Once any such edit lands on origin/main to a row that
    predates this branch's merge-base, HEAD's frozen copy of that row no
    longer byte-matches main's copy, and a full-snapshot subset check reads
    the branch as unmerged even though the branch never touched that row and
    its own contribution is fully present. Measured live 2026-08-29: a
    merged, content-on-main ledger-append branch was refused reap for
    exactly this reason — one line it never wrote (a Sentry-lane row a later
    lane had edited) no longer matched, and that was read as the branch
    being unmerged. Scoping to the branch's own additions answers "is what I
    added still there", never "is the file exactly as I last saw it" — the
    append-only-superset half of W88's "diff VUOTO o pura-cancellazione
    (subset)" rule, applied to what the branch actually authored."""
    diff_proc = _run_git(
        ["diff", "--unified=0", "--no-color", base_ref, head_ref, "--", path],
        cwd=cwd,
        check=False,
    )
    if diff_proc.returncode != 0:
        return False
    added_lines = {
        ln[1:]
        for ln in diff_proc.stdout.splitlines()
        if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip()
    }
    if not added_lines:
        # The branch touched this union path but added no lines of its own —
        # a pure deletion/rotation. Fail-safe to False (protect, do not
        # reap): there is nothing here to verify a subset OF, and a branch
        # whose only contribution to an append-only ledger is a removal is
        # consequential enough (something someone else still wants could be
        # what was removed) to deserve a human/PR path rather than an
        # automatic pass.
        return False
    main_proc = _run_git(["show", f"{main_ref}:{path}"], cwd=cwd, check=False)
    if main_proc.returncode != 0:
        return False
    main_lines = {ln for ln in main_proc.stdout.splitlines() if ln.strip()}
    return added_lines.issubset(main_lines)


def _gh_pr_state_for_branch(
    branch: str, *, cwd: Path, timeout: int = 15
) -> str | None:
    """Best-effort GitHub PR state for `branch`'s most recently created PR.

    ``gh pr list --head <branch> --state all`` — the third, authoritative arm
    added 2026-09-01 alongside the pre-existing ancestry/content arms (see
    `_branch_merge_status`): GitHub is the only party that knows a SQUASH
    merge landed, which is how every PR in this repo merges (W88) — the
    ancestor test can never be true for a squash-merged branch, and the
    content/blob-equality fallback answers a different question ("is main's
    CURRENT copy byte-identical to mine", not "did my work land") and reads a
    fully-landed branch as unmerged the moment anyone edits one of its files
    afterward. Measured 2026-09-01: PR #5434 (MERGED) has 3 authored files of
    which 1 now differs from main; PR #5354 (MERGED) has 15 of which 2 differ.

    ``--head`` (exact filter), NEVER ``--search head:<branch>`` (a search
    QUALIFIER, prefix-matching and index-backed — superscar family #3,
    guard-over-match). Measured live 2026-09-01 on a real sibling pair in
    this repo: `agent/nuzantara/infra/organ-hb-cadence` is a strict prefix of
    `agent/nuzantara/infra/organ-hb-cadence-wiring`; `--search head:` for the
    SHORTER branch returned BOTH PRs (including the longer sibling's, #5440,
    created later), while `--head` returned only the one PR that actually
    belongs to it (#5431). Because this function is the AUTHORITATIVE arm
    (a MERGED verdict overrides the content check), the search-qualifier form
    would let a sibling branch's newer MERGED PR reap a DIFFERENT worktree
    whose own PR is still OPEN — silent deletion of live, unmerged work, the
    fail-OPEN direction every other branch of this function is deliberately
    fail-CLOSED against. `headRefName` is also fetched and used to filter the
    result set defensively before the `createdAt` tie-break, so a future `gh`
    regression that reintroduces prefix-matching degrades to "picks the wrong
    still-correctly-scoped row" at worst, never silently reads a plainly
    wrong branch's PR as this branch's own.

    Returns one of GitHub's own state strings — "MERGED" / "OPEN" / "CLOSED" —
    for the most recently created PR whose head is EXACTLY this branch (a
    branch can accumulate more than one PR over its life — closed-then-
    reopened, or rebuilt after a squash — ties are broken by `createdAt`,
    latest wins). Returns "NONE" when `gh` succeeded but no PR was ever
    opened for this branch — the single most dangerous row on the reaper's
    board (measured 2026-09-01: `wr2/websurface-cure`, `infra/hookw119`,
    `ops/fix5331` — real committed work that exists nowhere else), which the
    caller must protect and report distinctly, never fold silently into the
    generic "unmerged" message.

    Returns None on ANY failure to get a trustworthy answer — `gh` missing,
    timeout, non-zero exit, unparseable JSON, or an unrecognized `state`
    value. The caller MUST treat that as "cannot verify via GitHub" and fall
    through to the offline ancestry/content path, never as "NONE" and never
    as "MERGED" (W84: cannot-verify must never read as proven — an API
    failure may only ever make the verdict MORE conservative, never less).
    """
    try:
        proc = subprocess.run(
            [
                "gh", "pr", "list",
                "--head", branch,
                "--state", "all",
                "--json", "number,state,createdAt,headRefName",
            ],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning(
            "gh pr list failed for branch %s (%s) — falling back to offline "
            "ancestry/content check",
            branch, exc,
        )
        return None
    if proc.returncode != 0:
        logger.warning(
            "gh pr list exited %s for branch %s (%s) — falling back to "
            "offline ancestry/content check",
            proc.returncode, branch, (proc.stderr or "").strip(),
        )
        return None
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        logger.warning(
            "gh pr list returned unparseable JSON for branch %s — falling "
            "back to offline ancestry/content check",
            branch,
        )
        return None
    if not isinstance(data, list):
        return None
    # Defensive exact-match filter (belt-and-suspenders on top of `--head`):
    # only rows whose own headRefName is EXACTLY this branch ever count. This
    # is what keeps a future `gh` regression, or a differently-scoped `--head`
    # behavior on some other `gh` version, from silently reading a sibling
    # branch's PR as this branch's own.
    rows = [
        row for row in data
        if isinstance(row, dict) and row.get("headRefName") == branch
    ]
    if not rows:
        return "NONE"

    def _created_at(row: dict) -> str:
        return row.get("createdAt") or ""

    latest = max(rows, key=_created_at)
    state = latest.get("state")
    if state not in ("MERGED", "OPEN", "CLOSED"):
        logger.warning(
            "gh pr list returned unrecognized state %r for branch %s — "
            "falling back to offline ancestry/content check",
            state, branch,
        )
        return None
    return state


def _worktree_head_branch(worktree: Path) -> str:
    """Short branch name HEAD points to inside ``worktree``, or "" if detached
    or unreadable. Factored out of ``_branch_in_origin_main`` so a caller can
    tell "HEAD is on a different branch than the one under judgement" (e.g. a
    mid-flight `git checkout -b <rename>`) apart from "HEAD's branch genuinely
    has commits not in origin/main" — two distinct causes that function's own
    fail-safe collapses to the same False, and reporting the wrong one wastes
    a future reader's time re-deriving what was actually checked."""
    head = _run_git(
        ["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=worktree, check=False
    )
    return head.stdout.strip() if head.returncode == 0 else ""


def _branch_merge_status(
    worktree: Path, *, expect_branch: str | None = None
) -> tuple[bool, str]:
    """(merged, reason) — the full verdict AND why, behind `_branch_in_origin_main`
    (now a thin bool-only wrapper around this).

    W80 ANTIBODY guard #2. The reaper must NOT remove a worktree whose work is
    not yet consolidated upstream — a branch that is pushed-but-not-merged (open
    PR) carries the only physical checkout the operator may still be iterating on.

    Returning the reason alongside the verdict lets a caller's skip message
    name what was ACTUALLY checked instead of re-deriving (or, worse,
    assuming) a cause after the fact — the exact W65/W105 trap this file was
    already burned by once (a skip message asserted "unmerged commits not in
    origin/main" for a worktree whose real problem was a mid-flight branch
    rename, which the merge-status check never even looked at). `reason` is
    one of:

      "dir-gone"           — worktree directory no longer exists (merged=True)
      "head-mismatch"      — HEAD is on a different branch than expect_branch (merged=False)
      "ancestor"           — HEAD is a git ancestor of origin/main (merged=True)
      "gh-merged"          — branch's most recent PR is MERGED (merged=True)
      "gh-open"            — branch's most recent PR is still OPEN (merged=False)
      "gh-closed"          — branch's most recent PR was CLOSED unmerged (merged=False)
      "gh-no-pr"           — gh succeeded, no PR ever existed for this branch (merged=False)
      "content-match"      — gh unusable; every changed file matches origin/main by content (merged=True)
      "content-mismatch"   — gh unusable; at least one changed file differs from origin/main (merged=False)
      "probe-inconclusive" — merge-base itself failed, or gh unusable AND the
                              merge-base-vs-origin/main probe failed too (merged=False)

    Three arms, tried in order, on a HEAD that is not a plain ancestor of
    origin/main:

      1. ``git -C <wt> merge-base --is-ancestor HEAD origin/main`` (exit 0 ⇒
         HEAD is an ancestor of origin/main ⇒ every commit is already in main
         upstream). This is the only arm that needs neither `gh` nor a fresh
         fetch, and it is exact — never a proxy — for a branch with no
         commits of its own yet.
      2. The PULL REQUEST arm (added 2026-09-01): ``gh pr list --head
         <branch>`` (exact filter — see `_gh_pr_state_for_branch`'s docstring
         for why never the `--search head:` qualifier, which prefix-matches)
         — GitHub is the only party that knows a SQUASH merge landed, which
         is how every PR in this repo merges (W88), so the
         ancestor test in arm 1 can NEVER be true for a squash-merged branch.
         This arm is AUTHORITATIVE: a MERGED PR means landed regardless of
         what arm 3 would conclude from current file content (which can go
         stale the moment anyone else edits a touched file post-merge — see
         `_gh_pr_state_for_branch`'s docstring for the measured cases). A PR
         that is OPEN or CLOSED-unmerged, or a branch with NO PR at all,
         protects immediately — none of those fall through to arm 3, because
         "no PR" and "PR still open" are answers, not "cannot verify".
      3. The pre-existing per-file CONTENT check — used only when `gh` itself
         is unusable (missing/timeout/non-zero exit/bad JSON, i.e.
         `_gh_pr_state_for_branch` returns None, "cannot verify via GitHub").
         The branch is judged merged iff every file it authored since its
         merge-base matches on origin/main. Never the three-dot diff —
         post-squash the merge-base regresses and three-dot counts main's own
         progress as branch-only changes (the W88 second-degree trap). This
         arm is intentionally the LAST resort, not the primary check: it asks
         "is main's CURRENT copy byte-identical to mine", not "did my work
         land", and goes stale the instant anyone else touches a shared file.

    Arm 3's per-file check is TWO checks, not one, because "matches" means a
    different thing depending on the path (both findings opened 2026-08-09
    while curing the broker, see PENDING-ARMS.md):

      - Default: an ``git ls-tree`` ENTRY comparison (mode + type + blob),
        not a bare ``git rev-parse <ref>:<path>`` blob lookup. Blob-only
        comparison is blind to a change that alters a file's MODE or TYPE
        without altering its bytes — `chmod +x`, or a tracked file replaced
        by a symlink whose target text happens to equal the blob content —
        and a mode/type-only branch would read as already-merged and get
        reaped although its one real change is exactly what the comparison
        could not see.
      - A path this repo's `.gitattributes` declares ``merge=union``
        (currently the sole example: `.claude/skills/modus/PENDING-ARMS.md`,
        an append-only ledger) can NEVER satisfy blob equality again once any
        other lane appends a line after this branch merges — main's copy is
        thereafter a strict superset. For those paths the question is
        LINE-SUBSET (every non-blank line the branch authored is present in
        origin/main's current copy), not blob equality — W88's "diff VUOTO o
        pura-cancellazione (subset)" prescription, applied per-path instead
        of file-wide. A path's `merge` attribute is a DECLARATIVE trigger
        (`git check-attr merge`), not a filename special-case, so a second
        union-merge file inherits the right comparison for free.

    Why ``origin/main`` and not local ``main`` or ``@{upstream}`` (the refuter
    killed both earlier designs):
      - local ``main`` can lag origin → a truly-merged branch reads unmerged.
      - ``@{upstream}..HEAD`` (rev-list count) reads 0 for a branch that has
        already been merged AND its upstream advanced — protecting a zombie
        forever; and reads >0 for a branch pushed-but-not-merged — which is the
        bug case, but it ALSO reads >0 for the merge-base check, so we use the
        unambiguous ancestor test against the integration branch directly.

    FAIL-SAFE TO FALSE ("treat as NOT merged ⇒ do NOT reap") on any git error,
    any `gh` failure, or missing origin/main. A worktree we cannot prove is
    merged is protected.

    `expect_branch` is how a caller that is about to DELETE a branch says which
    entity the verdict must be about. Without it this function answers only
    about HEAD, and a detached HEAD sitting at an ancestor of origin/main
    returns True while the registered branch is unmerged — which is a data-loss
    path for `git branch -D`, not a fail-safe. Pass it from every call site that
    deletes; an earlier version of this docstring claimed detached HEAD failed
    safe, and that was simply not true.

    Note on freshness: arm 1 and arm 3 test against the locally-known
    origin/main ref and do NOT fetch themselves — `cmd_cleanup` fetches once
    per run (`_refresh_origin_main_once`) before calling this at all, so a
    stale ref here is a fetch-failure/offline case, not the normal path. Arm 2
    (the PR check) needs no fetch at all — it asks GitHub directly.
    """
    if not worktree.is_dir():
        # Directory already gone — nothing to protect; let cleanup proceed to
        # prune the stale metadata/pointer.
        return True, "dir-gone"

    if expect_branch is not None:
        # Every question below is answered by the worktree's HEAD, but the
        # caller is about to `git branch -D expect_branch` — a DIFFERENT
        # entity the moment HEAD is not that branch. Detach a worktree at
        # origin/main (`git checkout --detach origin/main`) and the ancestor
        # test passes instantly while the registered branch still holds
        # unmerged commits: the proof is about the location, not the entity
        # named in the verdict (#3, the shape of W105).
        #
        # Fail-safe to False on detached/renamed/unreadable HEAD: we have not
        # DISPROVEN the branch is merged, we have failed to ask about it, and
        # cannot-verify must never read as proven (W84).
        actual = _worktree_head_branch(worktree)
        if actual != expect_branch:
            logger.warning(
                "content-merge probe declined for %s: HEAD is %s, not the branch "
                "under judgement (%s) — cannot prove that branch is merged",
                worktree, actual or "detached/unknown", expect_branch,
            )
            return False, "head-mismatch"

    proc = _run_git(
        ["merge-base", "--is-ancestor", "HEAD", "origin/main"],
        cwd=worktree,
        check=False,
    )
    if proc.returncode == 0:
        return True, "ancestor"
    if proc.returncode == 1:
        # Ancestor check failed (unmerged commits present, by ancestry) — the
        # NORMAL case for a squash-merged branch (W88). Try the authoritative
        # PR arm before falling to the content check.
        branch_for_pr = expect_branch or _worktree_head_branch(worktree)
        if branch_for_pr:
            pr_state = _gh_pr_state_for_branch(branch_for_pr, cwd=worktree)
            if pr_state == "MERGED":
                return True, "gh-merged"
            if pr_state == "OPEN":
                return False, "gh-open"
            if pr_state == "CLOSED":
                return False, "gh-closed"
            if pr_state == "NONE":
                return False, "gh-no-pr"
            # pr_state is None: gh unusable (missing/timeout/error/bad JSON) —
            # fall through to the offline content check exactly as before
            # this arm was added.

        # ARM 3 (offline path): verify by CONTENT. A branch is safe to reap if
        # every file it authored (changed since its merge-base) matches on
        # origin/main — by ls-tree entry (mode+type+blob) normally, by
        # line-subset for a declared merge=union path (see this function's
        # own docstring).
        mb_proc = _run_git(
            ["merge-base", "origin/main", "HEAD"], cwd=worktree, check=False
        )
        if mb_proc.returncode != 0:
            return False, "probe-inconclusive"
        mb = mb_proc.stdout.strip()

        diff_proc = _run_git(
            ["diff", "--name-only", mb, "HEAD"], cwd=worktree, check=False
        )
        if diff_proc.returncode != 0:
            return False, "probe-inconclusive"

        for f in diff_proc.stdout.splitlines():
            f = f.strip()
            if not f:
                continue

            if _is_union_merge_path(f, cwd=worktree):
                if not _content_subset_ok(mb, "HEAD", "origin/main", f, cwd=worktree):
                    return False, "content-mismatch"
                continue

            bh = _ls_tree_entry("HEAD", f, cwd=worktree)
            mh = _ls_tree_entry("origin/main", f, cwd=worktree)
            if bh != mh:
                return False, "content-mismatch"

        # If all changed files match origin/main (entry or line-subset), the
        # content is merged.
        return True, "content-match"

    # rc >= 128 (bad ref, not a git dir, unknown HEAD): fail-safe to protect.
    logger.warning(
        "merge-base probe inconclusive for %s (rc=%s) — treating as unmerged "
        "(fail-safe, no reap): %s",
        worktree,
        proc.returncode,
        (proc.stderr or "").strip(),
    )
    return False, "probe-inconclusive"


def _branch_in_origin_main(worktree: Path, *, expect_branch: str | None = None) -> bool:
    """True iff the worktree's HEAD is fully merged into ``origin/main``.

    Thin bool-only wrapper around `_branch_merge_status` — see that function's
    docstring for the full three-arm rationale (ancestor / GitHub PR / content)
    and the meaning of every `reason` value. Callers that need to explain a
    "not merged" verdict (e.g. `cmd_cleanup`'s skip messages) should call
    `_branch_merge_status` directly rather than re-deriving the reason here.
    """
    merged, _reason = _branch_merge_status(worktree, expect_branch=expect_branch)
    return merged


def _resolve_worktree_gitdir(worktree: Path) -> Path | None:
    """Resolve the real gitdir of a linked worktree (REPO_ROOT/.git/worktrees/
    <name>). For a linked worktree, `worktree/.git` is a file
    `gitdir: <abs-path>`; return that path. Returns None on any error."""
    git_pointer = worktree / ".git"
    try:
        if git_pointer.is_file():
            text = git_pointer.read_text(encoding="utf-8").strip()
            if text.startswith("gitdir:"):
                return Path(text.split(":", 1)[1].strip())
        elif git_pointer.is_dir():
            return git_pointer
    except OSError:
        return None
    return None


def _is_orphan(meta: "TaskMetadata", *, now: datetime | None = None) -> bool:
    """True if age exceeds ORPHAN_TTL_MULTIPLE × ttl. Malformed timestamps
    (age_minutes == -1.0) are NOT orphans — operator must inspect them."""
    age = meta.age_minutes(now=now)
    if age < 0:
        return False
    return age > ORPHAN_TTL_MULTIPLE * meta.ttl_minutes


# Hard ceiling (W62 ANTIBODY #3): no worktree should survive this long. Enforced
# at PR-time by tests/integration/test_no_stale_worktrees.py. Independent of any
# per-task TTL — a runaway TTL cannot opt out of the absolute cap.
STALE_WORKTREE_MAX_AGE_MINUTES = 24 * 60


def find_stale_worktrees(
    worktrees_dir: Path | None = None,
    *,
    max_age_minutes: int = STALE_WORKTREE_MAX_AGE_MINUTES,
    strict_missing_metadata: bool = False,
    now: datetime | None = None,
) -> list[tuple[str, float]]:
    """Return [(name, age_minutes)] for worktrees older than max_age_minutes.

    Age signal (W62 audit decision): primary is the broker's own `created_at`
    metadata (the canonical age axis used by --list/--cleanup).

    For a worktree dir WITHOUT a valid `.agent-task.json`:
      - strict_missing_metadata=False (default): fall back to directory mtime so
        non-broker orphans are still caught when they happen to be old.
      - strict_missing_metadata=True (CI gate): an unmanaged/malformed worktree
        is ALWAYS reported (age = +inf), because a fresh-but-untracked dir under
        .worktrees/ has a recent mtime and would slip past a 24h mtime check
        (codex P3 false-negative). At PR time there is no live session, so any
        metadata-less worktree is a defect to fix.
    """
    worktrees_dir = worktrees_dir if worktrees_dir is not None else WORKTREES_DIR
    if not worktrees_dir.is_dir():
        return []
    now = now or datetime.now(timezone.utc)
    now_ts = now.timestamp()
    stale: list[tuple[str, float]] = []
    for entry in sorted(worktrees_dir.iterdir()):
        if not entry.is_dir():
            continue
        meta_path = entry / TASK_METADATA_FILENAME
        managed = False
        age = -1.0
        if meta_path.is_file():
            try:
                meta = TaskMetadata.from_path(meta_path)
                age = meta.age_minutes(now=now)
                managed = age >= 0
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                managed = False
        if not managed:
            if strict_missing_metadata:
                stale.append((entry.name, float("inf")))
                continue
            age = max(0.0, (now_ts - entry.stat().st_mtime) / 60.0)
        if age > max_age_minutes:
            stale.append((entry.name, age))
    return stale


def cmd_list() -> int:
    rows = list(_iter_metadata())
    if not rows:
        print("(no active worktrees under .worktrees/)")
        return 0
    print(
        f"{'TASK':<24} {'LANE':<14} {'HOST':<14} "
        f"{'AGE_MIN':>8} {'TTL':>5} {'WIP':<4} {'ORPHAN':<7} BRANCH"
    )
    now = datetime.now(timezone.utc)
    orphan_count = 0
    for meta in rows:
        wt = (
            Path(meta.worktree_path)
            if meta.worktree_path
            else _worktree_path(meta.lane, meta.task_id)
        )
        wip_flag = "yes" if wt.is_dir() and _worktree_has_wip(wt) else "no"
        age = meta.age_minutes(now=now)
        orphan = _is_orphan(meta, now=now)
        if orphan:
            orphan_count += 1
        orphan_flag = "ORPHAN" if orphan else ""
        print(
            f"{meta.task_id:<24} {meta.lane:<14} {meta.host:<14} "
            f"{age:>8.1f} {meta.ttl_minutes:>5d} {wip_flag:<4} "
            f"{orphan_flag:<7} {meta.branch}"
        )
    if orphan_count:
        print(
            f"\nWARN: {orphan_count} orphan worktree(s) detected "
            f"(age > {ORPHAN_TTL_MULTIPLE}× TTL) — review then run "
            "--cleanup or --release."
        )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: cleanup
# ---------------------------------------------------------------------------


def _refresh_origin_main_once(*, cwd: Path, timeout: int = 30) -> bool:
    """``git fetch origin main`` once per ``--cleanup`` run, so the ancestry/
    content merge-status arms compare against a fresh ``origin/main`` instead
    of whatever the last fetch — possibly days old — left in place. Cause (1)
    of the reaper-never-reaps defect measured 2026-09-01: `_branch_merge_status`
    (formerly `_branch_in_origin_main`)'s own docstring already said neither
    arm fetches, so a daily cron comparing against a stale `origin/main`
    called recently-merged work unmerged.

    Called ONCE per `cmd_cleanup` invocation, before the per-worktree loop —
    not once per worktree: linked worktrees share the same underlying git
    object database and remote-tracking refs, so a single fetch from any one
    of them (here, the main checkout) refreshes `origin/main` for every
    worktree's `_branch_merge_status` call in the same run.

    Best-effort: a failed/offline fetch is logged and `cmd_cleanup` proceeds
    against the locally-known `origin/main` ref, which only ever makes the
    ancestry/content arms MORE conservative (protect, never reap) — the
    authoritative GitHub PR arm doesn't need a fresh `origin/main` at all, it
    asks GitHub directly. Returns True on success, False otherwise (the
    caller only logs; cleanup proceeds unconditionally either way).
    """
    try:
        proc = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning(
            "cleanup: git fetch origin main raised %s — continuing with the "
            "locally-known origin/main ref",
            exc,
        )
        return False
    if proc.returncode != 0:
        logger.warning(
            "cleanup: git fetch origin main exited %s (%s) — continuing "
            "with the locally-known origin/main ref",
            proc.returncode, (proc.stderr or "").strip(),
        )
        return False
    return True


def cmd_cleanup(
    *, force: bool = False, skip_recent_minutes: int = RECENT_ACTIVITY_MINUTES
) -> int:
    """Remove expired worktrees. WIP-safe: emits WARNING and skips if dirty.

    Two guards protect a worktree from being reaped even when its TTL clock
    expired. Order matters — WIP is checked FIRST so a worktree that is BOTH
    recently-touched AND dirty still surfaces as a WIP failure (never silently
    swallowed as a "live session"):
      1. WIP guard — uncommitted changes present (tracked or untracked). This
         is a *failure* to clean (the operator must commit/stash) → exit 1.
      2. Recent-activity guard (W62 ANTIBODY #1) — applied only to CLEAN
         worktrees: filesystem activity within skip_recent_minutes marks a live
         session. This is *not* a failure; the next tick reaps it once idle.

    Pass force=True to override BOTH guards (operator escape hatch).
    skip_recent_minutes=0 disables only the recent-activity guard.
    Returns 0 if every expired worktree was removed cleanly OR no work
    needed; 1 if at least one removal was skipped for WIP / errored.

    Refreshes `origin/main` ONCE for the whole run (`_refresh_origin_main_once`)
    before any merge-status comparison — see that function's docstring for why
    once-per-run rather than once-per-worktree is sufficient.
    """
    if _kill_switch_active():
        raise SystemExit(
            f"ERROR: broker disabled ({KILL_SWITCH_ENV}=false). Unset to cleanup."
        )

    rows = list(_iter_metadata())
    if not rows:
        print("(nothing to cleanup)")
        return 0

    _refresh_origin_main_once(cwd=REPO_ROOT)

    now = datetime.now(timezone.utc)
    issues = 0
    for meta in rows:
        if not meta.is_expired(now=now):
            continue
        wt = (
            Path(meta.worktree_path)
            if meta.worktree_path
            else _worktree_path(meta.lane, meta.task_id)
        )
        # WIP guard FIRST: a dirty worktree is always a failure to clean,
        # even if it was touched recently (codex P2: recent+dirty must not
        # exit 0 silently).
        if wt.is_dir() and _worktree_has_wip(wt) and not force:
            logger.warning(
                "cleanup skip %s — uncommitted WIP present (use --force)",
                meta.task_id,
            )
            print(
                f"WARN: skip {meta.task_id} (WIP). "
                f"Commit or stash inside {wt}, then re-run --cleanup."
            )
            issues += 1
            continue
        # Recent-activity guard SECOND, on clean worktrees only: a live session
        # that simply outran its TTL clock — keep it, reap when idle.
        if (
            wt.is_dir()
            and not force
            and _worktree_recently_active(wt, threshold_minutes=skip_recent_minutes)
        ):
            logger.info(
                "cleanup skip %s — recent activity (<%dmin), likely live session",
                meta.task_id,
                skip_recent_minutes,
            )
            print(
                f"skip {meta.task_id} (recent activity <{skip_recent_minutes}min) "
                "— live session, will reap when idle"
            )
            continue
        # W80 guard THIRD (2-AND), on clean + idle worktrees only. A worktree is
        # auto-reapable ONLY when BOTH hold:
        #   (1) no live OS process is anchored to it (lsof cwd/open-fd), AND
        #   (2) its HEAD is fully merged into origin/main.
        # The W80 bug: committing-everything to satisfy stop_verify makes a
        # worktree clean + idle-on-mtime → reap-eligible while still being
        # worked on, and a pushed-but-not-merged branch lost its only checkout.
        # If EITHER guard says "protect", we skip (not a failure — like the
        # recent-activity guard, the next idle+merged tick reaps it).
        if wt.is_dir() and not force:
            if _worktree_has_live_process(wt):
                logger.info(
                    "cleanup skip %s — live process anchored to worktree (W80)",
                    meta.task_id,
                )
                print(
                    f"skip {meta.task_id} (live process in worktree) "
                    "— active session, will reap when idle"
                )
                continue
            merged, reason = _branch_merge_status(wt, expect_branch=meta.branch)
            if not merged:
                # Call `_branch_merge_status` ONCE and branch on its own
                # `reason` — never re-derive a cause after the fact (the
                # exact W65/W105 trap this file was already burned by: a skip
                # message must only ever name what was ACTUALLY checked).
                if reason == "head-mismatch":
                    actual_head = _worktree_head_branch(wt)
                    logger.warning(
                        "cleanup skip %s — worktree HEAD is on branch %s, "
                        "registered branch is %s (renamed mid-flight?) — "
                        "cannot verify merge status, protecting checkout",
                        meta.task_id,
                        actual_head,
                        meta.branch,
                    )
                    print(
                        f"WARN: skip {meta.task_id} (HEAD is on '{actual_head}', "
                        f"registered branch is '{meta.branch}') — cannot verify "
                        "merge status, protecting checkout"
                    )
                elif reason == "gh-no-pr":
                    # The single most dangerous row on the board (measured
                    # 2026-09-01: wr2/websurface-cure, infra/hookw119,
                    # ops/fix5331 — real committed work that exists nowhere
                    # else) — report it distinctly, never fold it into the
                    # generic "unmerged commits" message below.
                    logger.warning(
                        "cleanup skip %s — branch %s has no pull request at "
                        "all — this work exists nowhere else, protecting checkout",
                        meta.task_id,
                        meta.branch,
                    )
                    print(
                        f"WARN: skip {meta.task_id} (branch '{meta.branch}' has "
                        "no pull request at all) — protecting checkout, this "
                        "work exists nowhere else"
                    )
                elif reason == "gh-open":
                    logger.info(
                        "cleanup skip %s — branch %s has an OPEN pull request",
                        meta.task_id,
                        meta.branch,
                    )
                    print(
                        f"skip {meta.task_id} (branch '{meta.branch}' has an "
                        "OPEN pull request) — protecting checkout, will reap "
                        "once merged or closed"
                    )
                elif reason == "gh-closed":
                    logger.warning(
                        "cleanup skip %s — branch %s's pull request was "
                        "CLOSED without merging",
                        meta.task_id,
                        meta.branch,
                    )
                    print(
                        f"WARN: skip {meta.task_id} (branch '{meta.branch}''s "
                        "pull request was CLOSED without merging) — "
                        "protecting checkout, operator must inspect"
                    )
                else:
                    # "content-mismatch" / "probe-inconclusive": gh was
                    # unusable (missing/timeout/error) and the offline
                    # ancestry/content check also could not prove merged.
                    logger.warning(
                        "cleanup skip %s — branch %s has commits not in origin/main "
                        "(W80: unmerged work, refusing to reap its only checkout)",
                        meta.task_id,
                        meta.branch,
                    )
                    print(
                        f"WARN: skip {meta.task_id} (branch '{meta.branch}' has "
                        "unmerged commits not in origin/main) — protecting checkout"
                    )
                continue
        try:
            _remove_worktree(wt, meta.branch, delete_branch=False)
            print(f"removed expired worktree {meta.task_id} ({wt})")
        except subprocess.CalledProcessError as exc:
            issues += 1
            logger.error(
                "cleanup failed %s: %s", meta.task_id, (exc.stderr or "").strip()
            )
            print(f"ERROR: cleanup failed for {meta.task_id}: {exc.stderr}")
    return 0 if issues == 0 else 1


# ---------------------------------------------------------------------------
# Subcommand: release
# ---------------------------------------------------------------------------


def _branch_is_merged(branch: str, base: str = "main") -> bool:
    """True if every commit on branch is reachable from base."""
    proc = _run_git(["rev-list", "--count", f"{base}..{branch}"], check=False)
    if proc.returncode != 0:
        return False
    try:
        return int(proc.stdout.strip()) == 0
    except ValueError:
        return False


def _rev_exists(rev: str) -> bool:
    """True iff `rev` resolves in this repo (a branch that was deleted does not).

    `_branch_is_merged` conflates "base gone" with "not merged" — both arrive as
    False. That conflation is invisible in the verdict but decides the ERROR
    MESSAGE, and a message that names the wrong cause sends the reader off to
    fix something that is not broken (W106: cure and diagnosis expire together).
    """
    proc = _run_git(["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"], check=False)
    return proc.returncode == 0


def _remove_worktree(worktree: Path, branch: str, *, delete_branch: bool) -> None:
    """Remove worktree via `git worktree remove` and optionally delete branch."""
    _run_git(["worktree", "remove", "--force", str(worktree)])
    if delete_branch:
        # -D allows deleting branches not merged into HEAD (we already verified
        # merged-into-base separately).
        _run_git(["branch", "-D", branch])


def cmd_release(task_id: str, *, force: bool = False) -> int:
    """Tear down a worktree by task-id. Branch deleted only if merged into base.

    Merged-ness is the cheap ancestor count first, then — because that proxy
    lies on squash-merged branches (W88) — the same blob-per-file content
    fallback the cleanup reaper uses (`_branch_in_origin_main`, #2038).

    With --force, the branch is deleted unconditionally (operator escape).
    """
    if _kill_switch_active():
        raise SystemExit(
            f"ERROR: broker disabled ({KILL_SWITCH_ENV}=false). Unset to release."
        )

    _validate_id("task-id", task_id)
    matches = [m for m in _iter_metadata() if m.task_id == task_id]
    if not matches:
        raise SystemExit(f"ERROR: no worktree metadata for task-id '{task_id}'")
    if len(matches) > 1:
        raise SystemExit(
            f"ERROR: multiple worktrees for task-id '{task_id}' — "
            "pass full path manually"
        )
    meta = matches[0]
    wt = (
        Path(meta.worktree_path)
        if meta.worktree_path
        else _worktree_path(meta.lane, meta.task_id)
    )
    base = meta.base_branch or "main"

    if wt.is_dir() and _worktree_has_wip(wt) and not force:
        raise SystemExit(
            f"ERROR: worktree {wt} has uncommitted WIP. Commit, push, or pass --force."
        )

    merged = _branch_is_merged(meta.branch, base=base)
    proven_by = "ancestor of base" if merged else ""
    if not merged and wt.is_dir() and (base == "main" or not _rev_exists(base)):
        # W88: the ancestor proxy says "unmerged" for every squash-merged
        # branch. Fall back to the blob-per-file content check the cleanup
        # reaper uses. Gated on wt.is_dir() — with the checkout gone the
        # content check degenerates to True and would delete an unproven
        # branch (keep the fail-safe direction).
        #
        # NOT gated on `base == "main"` any more (2026-08-08). That gate meant a
        # stacked branch — recorded base `feature/x`, since squash-merged and
        # DELETED — skipped the content check entirely and was refused, even with
        # every one of its files already byte-identical on origin/main. The harm
        # is not the friction: the message's own way out is `--force`, which
        # deletes unconditionally AND skips the uncommitted-WIP check above. An
        # over-strict guard that pushes you to the nuclear option has made things
        # less safe, not more (W105). Content-on-origin/main is a SUFFICIENT proof
        # of safety whatever the recorded base was — the work is upstream, so
        # deleting the branch loses nothing — and `_branch_in_origin_main`
        # fail-safes to False on any git error or missing ref.
        merged, merge_reason = _branch_merge_status(wt, expect_branch=meta.branch)
        if merged:
            proven_by = (
                "merged PR" if merge_reason == "gh-merged"
                else "content already on origin/main"
            )
    if not merged and not force:
        if not _rev_exists(base):
            reason = (
                f"its recorded base branch {base} no longer exists, and its content "
                "is not (yet) on origin/main"
            )
        else:
            reason = f"it is not merged into {base}, by ancestry or by content"
        raise SystemExit(
            f"ERROR: refusing to delete branch {meta.branch}: {reason}. "
            "Open a PR + merge it, or pass --force to delete unconditionally "
            "(--force also skips the uncommitted-WIP check above)."
        )
    if merged and proven_by:
        logger.info(
            "release merged-check passed task_id=%s branch=%s proof=%s",
            task_id, meta.branch, proven_by,
        )

    try:
        _remove_worktree(wt, meta.branch, delete_branch=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise SystemExit(f"ERROR: release failed: {stderr}") from exc

    logger.info("released worktree task_id=%s branch=%s", task_id, meta.branch)
    print(f"released {task_id} (branch {meta.branch} deleted)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-start",
        description=(
            "Agent Worktree Broker — enforces worktree-per-session for every "
            "concurrent Claude / subagent / cron session."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  agent-start --lane wr2 --task-id render-cleanup\n"
            "  agent-start --list\n"
            "  agent-start --cleanup\n"
            "  agent-start --release render-cleanup\n"
        ),
    )
    # Operations (mutually exclusive at the group-of-flags level).
    p.add_argument("--lane", help="Lane identifier (e.g. wr2, infra, docs)")
    p.add_argument("--task-id", help="Task id (short slug, ticket id, uuid)")
    p.add_argument(
        "--ttl-min",
        type=int,
        default=60,
        help="TTL in minutes after which cleanup may reclaim (default: 60)",
    )
    p.add_argument(
        "--base-branch",
        default="main",
        help="Base branch to fork from (default: main)",
    )
    p.add_argument(
        "--allow-unknown-lane",
        action="store_true",
        help="Permit creating a worktree with a lane not in the known list",
    )

    p.add_argument(
        "--list",
        action="store_true",
        help="List active worktrees with age + WIP indicator",
    )
    p.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove worktrees whose TTL has expired (WIP-safe)",
    )
    p.add_argument(
        "--release",
        metavar="TASK_ID",
        help="Tear down a specific worktree + branch (branch must be merged)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="With --cleanup/--release: override WIP and merged-status guards",
    )
    p.add_argument(
        "--skip-recent-min",
        type=int,
        default=RECENT_ACTIVITY_MINUTES,
        help=(
            "With --cleanup: skip worktrees with filesystem activity in the last "
            f"N minutes (default: {RECENT_ACTIVITY_MINUTES}; 0 disables the guard)"
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Dispatch (subcommand flags are mutually exclusive at the semantic level).
    operations = sum(
        [bool(args.list), bool(args.cleanup), bool(args.release), bool(args.lane)]
    )
    if operations == 0:
        parser.print_help()
        return 2
    if operations > 1:
        print("ERROR: choose exactly one of --lane/--list/--cleanup/--release")
        return 2

    if args.list:
        return cmd_list()
    if args.cleanup:
        return cmd_cleanup(force=args.force, skip_recent_minutes=args.skip_recent_min)
    if args.release:
        return cmd_release(args.release, force=args.force)

    # Default: create.
    if not args.lane or not args.task_id:
        print("ERROR: --lane AND --task-id are both required to create a worktree")
        return 2

    worktree = cmd_create(
        args.lane,
        args.task_id,
        ttl_minutes=args.ttl_min,
        base_branch=args.base_branch,
        allow_unknown_lane=args.allow_unknown_lane,
    )
    # Single-line stdout contract for shell-glue:
    print(f"WORKTREE_READY {worktree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
