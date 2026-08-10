#!/usr/bin/env python3
"""launchagent_reconcile.py — inventory/reconcile report for ~/Library/LaunchAgents.

C3 of the WR2 next-level plan (research/operations/2026-06-30-wr2-next-level-plan.md,
D6): the LaunchAgents dir accreted 300+ entries (live plists + .bak/.disabled/archive
dirs) across months of cutovers. This tool RECONCILES three sources of truth —

    files on disk  ×  launchctl loaded state  ×  repo canon (infra/launchagents)

— and emits a categorized report. It is a SIGNALER, not an actuator (W81 antidote:
"reconciliation-report che allarma, non auto-attuatore"; W33: the operator decides
what gets disabled).

Categories (multi-tag — one file can appear in several):
  junk                file that is not a live `*.plist` (`.bak-*`, `.disabled-*`,
                      `.pre-*`, stray files). Parsed anyway: a backup still carries
                      a Label and may be the ONLY on-disk copy of a loaded job.
  zombie-loaded       label loaded in launchd with NO live plist file declaring it.
  present-not-loaded  live plist on disk whose label is not loaded (Esiste≠Armato).
  broken-target       live plist whose launch target does not exist on disk.
  repo-divergent      live plist that differs from its repo twin beyond the
                      env-specific keys (EnvironmentVariables, *Path, WorkingDirectory).
  home-fork-target    live plist whose payload lives under $HOME outside the repo /
                      deploy clone and is not a symlink into them (superscar #1).
                      Targets declared or allow-listed in
                      infra/home-fork/declared-pairs.json are excluded — that file
                      is the SSOT for "known, not a fork" (lint_home_fork.py already
                      enforces it; this tool must not re-report what it resolved).

What this tool does NOT do:
  - runtime health (exit codes × log content) → scripts/launchd_liveness_detector.py (W84)
  - bootout/unload/disable — NEVER (W33 kill-switch: operator-only)

--apply deletes ONLY `junk` files, and only when ALL of:
  - age >= --min-age-days (age = the YOUNGER of mtime and any filename-embedded
    YYYYMMDD stamp — a lying mtime must make the file look newer, not older)
  - the file is NOT the loaded source of its label (launchctl print path check)
  - a live `*.plist` with the SAME parsed Label exists (supersession proof) OR the
    file does not parse as a plist at all. A backup that is the only copy of its
    label is PROTECTED (only-copy) and left to the operator.

Keying is by parsed Label, never by filename (real drift observed:
com.matagaruda.kita-feed.daily.plist carries Label=com.matagaruda.kita-feed).

Scope: labels/files matching --prefixes (default: the organism's families).
Apple/Google/Homebrew agents are out of scope unless --all.

Usage:
    python3 scripts/launchagent_reconcile.py                # report only (default)
    python3 scripts/launchagent_reconcile.py --json         # machine-readable
    python3 scripts/launchagent_reconcile.py --apply        # delete eligible junk
    python3 scripts/launchagent_reconcile.py --alert        # Telegram summary

Stdlib-only, runs on macOS system python3 (3.9+).
"""
from __future__ import annotations

import argparse
import filecmp
import fnmatch
import json
import os
import plistlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_PREFIXES = (
    "com.balizero.",
    "com.nuzantara.",
    "com.matagaruda.",
    "ai.flowkit.",
    "ai.openclaw.",
    "com.osint-nexus.",
)

# Keys that legitimately differ per machine — excluded from the repo-divergence
# compare (red-team 2026-07-02 finding #7: raw byte-compare cries wolf on HOME,
# log paths, TCC cutovers).
ENV_SPECIFIC_KEYS = (
    "EnvironmentVariables",
    "StandardOutPath",
    "StandardErrorPath",
    "WorkingDirectory",
)

# Interpreters whose argv[1] is the real payload (best-effort, report-only).
INTERPRETERS = ("bash", "zsh", "sh", "python", "python3", "env", "node")

# Roots that plausibly host launchd wrapper/canon scripts, walked RECURSIVELY
# (basename match). A flat top-level-only search (pre-2026-07-07) missed real
# canons living one level deeper — infra/healer/, infra/mini-scripts/,
# scripts/mini-migration/, apps/backend-rag/scripts/ — and mis-flagged 7 of 15
# live findings as "no repo canon" while a byte-identical twin existed nearby.
# apps/*/scripts (not all of apps/) mirrors the top-level scripts/ convention
# without walking the ~36k-file app source trees.
CANON_EXCLUDE_DIRNAMES = {
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build", ".next", ".git", ".worktrees",
}


def _build_canon_index(repo_dir: Path) -> dict:
    """basename -> sorted candidate repo paths, built once per run (not once
    per target — the walk cost is paid a single time)."""
    index: dict = {}
    roots = [repo_dir / "scripts", repo_dir / "infra"]
    if (repo_dir / "apps").is_dir():
        roots.extend(sorted((repo_dir / "apps").glob("*/scripts")))
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in CANON_EXCLUDE_DIRNAMES]
            for fn in filenames:
                index.setdefault(fn, []).append(Path(dirpath) / fn)
    for paths in index.values():
        paths.sort(key=str)
    return index

# Path fragments that mark a RUNTIME (venv interpreter, pyenv shim…), not a
# payload: a `~/venvs/x/bin/python` under $HOME is infrastructure, not a
# HOME-fork of repo code — the fork signal lives in the script it runs.
RUNTIME_MARKERS = ("/venv/", "/.venv/", "/venvs/", "/.pyenv/", "/node_modules/")


def _is_runtime(path: Path) -> bool:
    s = str(path)
    if any(m in s for m in RUNTIME_MARKERS):
        return True
    return path.parent.name == "bin" and any(
        path.name.startswith(i) for i in (*INTERPRETERS, "uvicorn", "gunicorn")
    )


def _load_home_fork_config(repo_dir: Path) -> tuple[set[str], list[str]]:
    """Best-effort load of infra/home-fork/declared-pairs.json's declared live
    paths + allow patterns. Read-only import; any failure degrades to empty —
    that JSON stays the SSOT enforced by lint_home_fork.py, this is only a
    courtesy de-dupe so this tool does not re-flag what that tool already
    resolved (superscar #3 lesson: a guard that ignores ground-truth cries
    wolf on known-benign targets)."""
    config_path = repo_dir / "infra" / "home-fork" / "declared-pairs.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), []
    declared_lives = {p["live"] for p in data.get("pairs", []) if "live" in p}
    allow = [str(a) for a in data.get("allow", [])]
    return declared_lives, allow


def _normalize_home_path(path: Path, home: Path) -> Optional[str]:
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return None


def _expand_home_token(token: str, home: Path) -> Path:
    if token == "~":
        return home
    if token.startswith("~/"):
        return home / token[2:]
    return Path(token)


def _is_declared_or_allowed(
    path: Path, home: Path, declared_lives: set[str], allow: list[str]
) -> bool:
    norm = _normalize_home_path(path, home)
    if norm is None:
        return False
    if norm in declared_lives:
        return True
    expanded = str(path)
    for pattern in allow:
        pat_expanded = str(_expand_home_token(pattern, home))
        if fnmatch.fnmatch(norm, pattern) or fnmatch.fnmatch(expanded, pat_expanded):
            return True
    return False

_NAME_STAMP_RE = re.compile(r"(20\d{6})")


# ─────────────────────────────────────────────────────────────────────────
# launchctl adapters (injectable for tests)
# ─────────────────────────────────────────────────────────────────────────

def launchctl_list_text() -> str:
    """Raw `launchctl list` output; empty string on any failure."""
    try:
        return subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=20
        ).stdout
    except Exception:  # noqa: BLE001 — degrade to "loaded state unknown"
        return ""


def parse_loaded_labels(text: str) -> set:
    """Labels from `launchctl list` (PID\tStatus\tLabel; header skipped)."""
    labels = set()
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[2] == "Label":
            continue
        labels.add(parts[2].strip())
    return labels


def launchctl_loaded_path(label: str) -> Optional[str]:
    """The `path = ...` launchd reports for a loaded label (deletion protection:
    never delete the file launchd is actually running from). None if unknown."""
    try:
        out = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r"^\s*path = (.+)$", out, re.MULTILINE)
    return m.group(1).strip() if m else None


# ─────────────────────────────────────────────────────────────────────────
# plist helpers
# ─────────────────────────────────────────────────────────────────────────

def parse_plist(path: Path) -> Optional[dict]:
    """plistlib first; on failure fall back to `plutil -convert xml1`.

    launchd is more lenient than expat: real plists in this fleet carry
    `--apply` inside XML comments (`--` is illegal in XML comments), which
    plistlib rejects while launchd loads them fine (observed 2026-07-02 on 5
    live agents that would otherwise misclassify as zombies). plutil parses
    like launchd and re-emits canonical XML without comments.
    """
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 — try the lenient parser before giving up
        pass
    try:
        out = subprocess.run(
            ["plutil", "-convert", "xml1", "-o", "-", str(path)],
            capture_output=True, timeout=20,
        )
        if out.returncode != 0:
            return None
        data = plistlib.loads(out.stdout)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 — genuinely unparseable
        return None


def resolve_targets(plist: dict) -> list:
    """Candidate payload paths launchd would touch: Program, argv[0], and — when
    argv[0] is an interpreter — the first absolute-path argument after it.
    Best-effort by design (report-only; the liveness detector owns health)."""
    targets = []
    prog = plist.get("Program")
    if isinstance(prog, str):
        targets.append(prog)
    args = plist.get("ProgramArguments")
    if isinstance(args, list) and args:
        argv0 = str(args[0])
        targets.append(argv0)
        base = Path(argv0).name
        if any(base.startswith(i) for i in INTERPRETERS):
            for a in args[1:]:
                s = str(a)
                if s.startswith("/"):
                    targets.append(s)
                    break
    # dedupe, preserve order
    seen = set()
    out = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def canonical_for_compare(plist: dict) -> dict:
    return {k: v for k, v in plist.items() if k not in ENV_SPECIFIC_KEYS}


# Install-time template placeholder, e.g. `__HOME__`, `__REPO_ROOT__/scripts/x.sh`.
# A handful of repo canons (com.balizero.drive-intake-drain,
# com.balizero.dropbox-intake, com.balizero.wr2.ig-metrics-scrape.daily) ship
# with these tokens INSIDE ProgramArguments — not just EnvironmentVariables,
# the only place ENV_SPECIFIC_KEYS already excludes — so a correctly-installed
# live plist (tokens substituted with real paths) diffed byte-for-byte against
# its own template canon reads as permanently "repo-divergent". Ward-round
#2026-08-07, repo-divergent-placeholder-template-false-positive.
_TEMPLATE_PLACEHOLDER_RE = re.compile(r"__[A-Z0-9_]+__")


def _mask_templated(canon_value, live_value):
    """Recursively mask fields whose CANON side is a template placeholder.

    Only the CANON string decides whether a field is templated — if it
    contains a `__TOKEN__` pattern, BOTH sides are replaced with the same
    sentinel so the field can never register as a diff, regardless of what
    the installer actually substituted (this function does not need to know
    the correct value, only that canon says "this varies at install time").

    Structural shape must still agree for the mask to apply: a placeholder
    never hides a live value of the wrong type/length (e.g. live missing an
    argv element, or an extra key live-only) — that stays a real diff, which
    is exactly how genuine drift keeps getting caught.
    """
    if isinstance(canon_value, str):
        if _TEMPLATE_PLACEHOLDER_RE.search(canon_value):
            return "<template>", "<template>"
        return canon_value, live_value
    if (
        isinstance(canon_value, list)
        and isinstance(live_value, list)
        and len(canon_value) == len(live_value)
    ):
        masked_canon, masked_live = [], []
        for cv, lv in zip(canon_value, live_value):
            mc, ml = _mask_templated(cv, lv)
            masked_canon.append(mc)
            masked_live.append(ml)
        return masked_canon, masked_live
    if isinstance(canon_value, dict) and isinstance(live_value, dict):
        masked_canon, masked_live = {}, {}
        for k, cv in canon_value.items():
            if k in live_value:
                mc, ml = _mask_templated(cv, live_value[k])
                masked_canon[k] = mc
                masked_live[k] = ml
            else:
                masked_canon[k] = cv  # live missing the key: real diff, preserved
        for k, lv in live_value.items():
            if k not in canon_value:
                masked_live[k] = lv  # live-only key: real diff, preserved
        return masked_canon, masked_live
    return canon_value, live_value


# A leading per-machine home root, e.g. `/Users/nuzantara/`. Anchored and
# requiring the trailing slash: `/Users/nuzantara` alone is not a home PREFIX
# of anything, and an interior occurrence is not a root.
_USER_HOME_PREFIX_RE = re.compile(r"^/Users/[^/]+/")


def _rebase_homes(canon_value, live_value, live_home: Path):
    """Recursively rewrite a leading home root to `~/` so a plist correctly
    installed on THIS machine does not read as divergent purely because canon
    was authored under another account.

    Why this exists: `ENV_SPECIFIC_KEYS` already forgives `WorkingDirectory`
    and the two log paths, but NOT `ProgramArguments` — and the payload path
    lives in `ProgramArguments`. `com.nuzantara.worktree-gc-universal.daily`
    carries a comment saying it is "HOME-fork-scoped by nature (paths are
    per-machine under /Users/nuzantara/)", and on M5 (`balizero`) it was
    reported Repo-divergent every run for exactly that reason. Measured
    2026-08-08: every functional difference between the live M5 copy and
    origin/main was the username and nothing else.

    ASYMMETRIC ON PURPOSE, and this is the whole safety of it:

      * the CANON side gives up ANY `/Users/<user>/` prefix — canon is
        authored on whichever machine happened to write it, so which account
        appears there carries no meaning;
      * the LIVE side gives up ONLY this machine's own home. A live path under
        a FOREIGN home — the `/Users/nuzantara/...` copied onto M5 class, dead
        paths since the 2026-07-16 move — does not normalise, so it still
        differs from canon's `~/...` and stays flagged.

    A symmetric rebase would read those two cases as identical and silence the
    drift this report exists to catch (W94: the fix for an over-match births
    the under-match twin unless the corpus covers the composition).
    """
    if isinstance(canon_value, str) and isinstance(live_value, str):
        canon_out = _USER_HOME_PREFIX_RE.sub("~/", canon_value)
        live_prefix = str(live_home).rstrip("/") + "/"
        live_out = (
            "~/" + live_value[len(live_prefix):]
            if live_value.startswith(live_prefix)
            else live_value
        )
        return canon_out, live_out
    if (
        isinstance(canon_value, list)
        and isinstance(live_value, list)
        and len(canon_value) == len(live_value)
    ):
        pairs = [_rebase_homes(cv, lv, live_home)
                 for cv, lv in zip(canon_value, live_value)]
        return [p[0] for p in pairs], [p[1] for p in pairs]
    if isinstance(canon_value, dict) and isinstance(live_value, dict):
        rebased_canon, rebased_live = dict(canon_value), dict(live_value)
        for k, cv in canon_value.items():
            if k in live_value:
                rebased_canon[k], rebased_live[k] = _rebase_homes(
                    cv, live_value[k], live_home
                )
        return rebased_canon, rebased_live
    return canon_value, live_value


def plists_equivalent(live_plist: dict, repo_plist: dict, live_home: Path) -> bool:
    """True iff live and repo-canon agree once env-specific keys, install-time
    template placeholders and this machine's home root are all accounted for."""
    lc = canonical_for_compare(live_plist)
    cc = canonical_for_compare(repo_plist)
    masked_canon, masked_live = _mask_templated(cc, lc)
    rebased_canon, rebased_live = _rebase_homes(masked_canon, masked_live, live_home)
    return rebased_canon == rebased_live


def name_stamp_age_days(name: str, now: datetime) -> Optional[float]:
    """Age from a YYYYMMDD embedded in the filename, if any."""
    m = _NAME_STAMP_RE.search(name)
    if not m:
        return None
    try:
        stamped = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0.0, (now - stamped).total_seconds() / 86400.0)


def effective_age_days(path: Path, now: datetime) -> float:
    """The YOUNGER of mtime-age and filename-stamp-age: a lying mtime (chmod,
    xattr, copy) must make a file look NEWER — never older — for --apply."""
    mtime_age = max(
        0.0,
        (now - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).total_seconds() / 86400.0,
    )
    stamp_age = name_stamp_age_days(path.name, now)
    return min(mtime_age, stamp_age) if stamp_age is not None else mtime_age


def in_scope(name: str, prefixes) -> bool:
    return any(name.startswith(p) for p in prefixes)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


# ─────────────────────────────────────────────────────────────────────────
# The reconcile pass
# ─────────────────────────────────────────────────────────────────────────

def reconcile(
    agents_dir: Path,
    repo_dir: Path,
    loaded_labels: Optional[set],
    prefixes=DEFAULT_PREFIXES,
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Pure inventory pass. loaded_labels=None means launchctl was unavailable —
    loaded-state categories are skipped (degrade-open, never mass-misclassify)."""
    home = home or Path.home()
    now = now or datetime.now(timezone.utc)
    repo_infra = repo_dir / "infra" / "launchagents"
    repo_root = repo_dir.resolve()
    deploy_root = (home / "Desktop" / "nuzantara-deploy").resolve()

    # Canon index for wrapper scripts (basename match, built once). A HOME
    # target whose repo canon is byte-identical is NOT a fork — it is the
    # W84-safe placement (launchd payloads deliberately live OUTSIDE ~/Desktop
    # because launchd can lose its TCC grant there). The disease is DRIFT,
    # not location.
    canon_index = _build_canon_index(repo_dir)
    declared_lives, home_fork_allow = _load_home_fork_config(repo_dir)

    def _repo_canon_for(target: Path) -> Optional[Path]:
        candidates = canon_index.get(target.name)
        if not candidates:
            return None
        for cand in candidates:
            if filecmp.cmp(str(cand), str(target), shallow=False):
                return cand
        return candidates[0]

    live: dict = {}      # label -> {file, plist}
    junk: list = []
    archive_dirs: list = []
    unparseable_live: list = []

    for entry in sorted(agents_dir.iterdir()):
        if entry.is_dir():
            archive_dirs.append(entry.name)
            continue
        if not entry.is_file():
            continue
        if entry.name.endswith(".plist"):
            data = parse_plist(entry)
            if data is None:
                unparseable_live.append(entry.name)
                continue
            label = str(data.get("Label", entry.stem))
            if not (in_scope(label, prefixes) or in_scope(entry.name, prefixes)):
                continue
            live[label] = {"file": entry, "plist": data}
        else:
            data = parse_plist(entry)
            label = str(data.get("Label")) if data and data.get("Label") else None
            if not (in_scope(entry.name, prefixes) or (label and in_scope(label, prefixes))):
                continue
            junk.append({
                "file": entry,
                "label": label,
                "age_days": round(effective_age_days(entry, now), 1),
            })

    live_labels = set(live.keys())

    zombie_loaded = []
    present_not_loaded = []
    if loaded_labels is not None:
        scoped_loaded = {l for l in loaded_labels if in_scope(l, prefixes)}
        zombie_loaded = sorted(scoped_loaded - live_labels)
        present_not_loaded = sorted(live_labels - loaded_labels)

    broken_target = []
    home_fork_target = []
    canon_paired = []
    repo_divergent = []
    repo_symlinked = []

    for label, info in sorted(live.items()):
        f: Path = info["file"]
        plist: dict = info["plist"]
        targets = resolve_targets(plist)

        if targets and not Path(targets[0]).exists():
            broken_target.append({"label": label, "file": f.name, "target": targets[0]})

        for t in targets:
            tp = Path(t)
            if not tp.exists():
                continue
            rp = tp.resolve()
            if _is_runtime(rp):
                continue  # venv/pyenv interpreter = runtime, not a fork
            if not _is_under(rp, home):
                continue
            if _is_under(rp, repo_root) or _is_under(rp, deploy_root):
                continue
            if _is_under(rp, agents_dir.resolve()):
                continue
            norm = _normalize_home_path(rp, home)
            in_declared_lives = norm is not None and norm in declared_lives
            # "allow"-only match (not a declared pair): a human already ruled this
            # HOME path unrelated to the repo (TCC bridge, vendor binary,
            # separate-repo tool with no canon by design). _repo_canon_for() matches
            # by BASENAME ALONE — a generic name like "run.sh" can coincidentally
            # collide with an unrelated repo file and produce a spurious "canon", which
            # must never override that human ruling (guard-over-match, superscar #3
            # sibling: same-name ≠ same-entity). A declared PAIR's real canon is
            # untouched by this branch — its DIVERGED check still fires below.
            allow_only = not in_declared_lives and _is_declared_or_allowed(
                rp, home, set(), home_fork_allow
            )
            canon = _repo_canon_for(rp)
            if allow_only:
                pass
            elif canon is not None and filecmp.cmp(str(canon), str(rp), shallow=False):
                canon_paired.append({"label": label, "file": f.name, "target": t,
                                     "canon": str(canon.relative_to(repo_root))})
            elif canon is None and _is_declared_or_allowed(
                rp, home, declared_lives, home_fork_allow
            ):
                # No repo canon AND declared/allow-listed in declared-pairs.json:
                # a known-benign HOME-only target (TCC bridge, vendor binary,
                # separate-repo tool) — not a fork to (re-)report. A DIVERGED
                # canon (drift) is never suppressed by this branch — that is
                # the disease this whole tool exists to catch (superscar #1).
                pass
            else:
                detail = (
                    f"DIVERGED from canon {canon.relative_to(repo_root)}" if canon is not None
                    else "no repo canon (basename not found under scripts/, infra/, or apps/*/scripts/)"
                )
                home_fork_target.append({"label": label, "file": f.name, "target": t,
                                         "detail": detail})
            break

        twin = repo_infra / f.name
        if twin.is_file():
            if f.is_symlink() and _is_under(f.resolve(), repo_root):
                repo_symlinked.append(f.name)
            else:
                repo_plist = parse_plist(twin)
                if repo_plist is not None and not plists_equivalent(
                    plist, repo_plist, home
                ):
                    repo_divergent.append({"label": label, "file": f.name})

    return {
        "scanned_at": now.isoformat(),
        "agents_dir": str(agents_dir),
        "launchctl_available": loaded_labels is not None,
        "live_count": len(live),
        "live_labels": sorted(live_labels),
        "junk": [
            {"file": j["file"].name, "label": j["label"], "age_days": j["age_days"]}
            for j in junk
        ],
        "_junk_paths": {j["file"].name: j["file"] for j in junk},
        "_live_by_label": {l: str(i["file"]) for l, i in live.items()},
        "archive_dirs": archive_dirs,
        "unparseable_live": unparseable_live,
        "zombie_loaded": zombie_loaded,
        "present_not_loaded": present_not_loaded,
        "broken_target": broken_target,
        "home_fork_target": home_fork_target,
        "canon_paired": canon_paired,
        "repo_divergent": repo_divergent,
        "repo_symlinked": repo_symlinked,
    }


def junk_apply_eligibility(
    report: dict,
    min_age_days: float,
    loaded_labels: Optional[set],
    loaded_path_fn=launchctl_loaded_path,
) -> list:
    """Per-junk-file verdict: (name, eligible, reason). ALL protections must
    clear for eligible=True — see module docstring."""
    verdicts = []
    live_by_label = report["_live_by_label"]
    junk_paths = report["_junk_paths"]
    for j in report["junk"]:
        name, label, age = j["file"], j["label"], j["age_days"]
        path = junk_paths[name]
        if age < min_age_days:
            verdicts.append((name, False, f"younger than {min_age_days:.0f}d (age {age}d)"))
            continue
        if label is not None:
            if label not in live_by_label:
                verdicts.append((name, False, "only-copy of its label (no live plist) — operator decides"))
                continue
            if loaded_labels is not None and label in loaded_labels:
                lp = loaded_path_fn(label)
                if lp and Path(lp).resolve() == path.resolve():
                    verdicts.append((name, False, "IS the loaded source of its label"))
                    continue
        verdicts.append((name, True, "superseded backup" if label else "not a plist"))
    return verdicts


# ─────────────────────────────────────────────────────────────────────────
# Rendering + alert
# ─────────────────────────────────────────────────────────────────────────

def render_markdown(report: dict, verdicts) -> str:
    lines = [
        "# LaunchAgent reconcile report",
        "",
        f"- scanned: {report['scanned_at']}",
        f"- agents dir: `{report['agents_dir']}`",
        f"- launchctl loaded-state: {'available' if report['launchctl_available'] else 'UNAVAILABLE — loaded categories skipped'}",
        f"- live plists in scope: {report['live_count']}",
        f"- junk files in scope: {len(report['junk'])}",
        f"- archive dirs (never touched): {', '.join(report['archive_dirs']) or '—'}",
        "",
        "> REPORT-ONLY by default. `--apply` deletes junk that cleared every",
        "> protection below. It NEVER unloads/bootouts anything (W33) — zombie and",
        "> divergence findings are for the operator.",
        "> Runtime health (exit-code × log) lives in scripts/launchd_liveness_detector.py (W84).",
        "",
    ]

    def section(title, rows, fmt):
        lines.append(f"## {title} ({len(rows)})")
        if rows:
            lines.extend(fmt(r) for r in rows)
        else:
            lines.append("- none")
        lines.append("")

    section("Zombie loaded (label alive, no live plist file)", report["zombie_loaded"], lambda l: f"- `{l}`")
    section(
        "Present but not loaded (Esiste≠Armato)", report["present_not_loaded"], lambda l: f"- `{l}`"
    )
    section(
        "Broken target", report["broken_target"],
        lambda b: f"- `{b['label']}` → missing `{b['target']}`",
    )
    section(
        "HOME-fork target (superscar #1)", report["home_fork_target"],
        lambda h: f"- `{h['label']}` → `{h['target']}` ({h.get('detail', 'under $HOME, outside repo/deploy, not a repo symlink')})",
    )
    section(
        "Canon-paired HOME target (byte-identical to repo canon — W84-safe placement, not a fork)",
        report.get("canon_paired", []),
        lambda h: f"- `{h['label']}` → `{h['target']}` == `{h['canon']}`",
    )
    section(
        "Repo-divergent (env-specific keys excluded)", report["repo_divergent"],
        lambda d: f"- `{d['file']}`",
    )
    if report["unparseable_live"]:
        section("Unparseable live plists", report["unparseable_live"], lambda n: f"- `{n}`")

    lines.append(f"## Junk files ({len(report['junk'])})")
    if verdicts:
        for name, eligible, reason in verdicts:
            mark = "DELETE-ELIGIBLE" if eligible else "PROTECTED"
            lines.append(f"- [{mark}] `{name}` — {reason}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=10
        )
    except Exception:  # noqa: BLE001 — alerting is best-effort
        pass


# ─────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--agents-dir", default=str(Path.home() / "Library" / "LaunchAgents"))
    ap.add_argument("--repo-dir", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--prefixes", default=",".join(DEFAULT_PREFIXES),
                    help="comma-separated label/filename prefixes in scope")
    ap.add_argument("--all", action="store_true", help="no prefix filter (whole dir)")
    ap.add_argument("--min-age-days", type=float, default=30.0)
    ap.add_argument("--apply", action="store_true",
                    help="delete eligible junk files (report mode otherwise)")
    ap.add_argument("--json", action="store_true", help="print JSON to stdout")
    ap.add_argument("--alert", action="store_true", help="send Telegram summary")
    ap.add_argument("--out", default=None, help="markdown report path")
    args = ap.parse_args(argv)

    prefixes = ("",) if args.all else tuple(p for p in args.prefixes.split(",") if p)
    agents_dir = Path(args.agents_dir).expanduser()
    if not agents_dir.is_dir():
        print(f"agents dir not found: {agents_dir}", file=sys.stderr)
        return 2

    text = launchctl_list_text()
    loaded = parse_loaded_labels(text) if text.strip() else None

    report = reconcile(agents_dir, Path(args.repo_dir), loaded, prefixes=prefixes)
    verdicts = junk_apply_eligibility(report, args.min_age_days, loaded)

    md = render_markdown(report, verdicts)
    out = Path(args.out) if args.out else (
        Path.home() / "logs" / f"launchagent-reconcile-{datetime.now(timezone.utc):%Y%m%d}.md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)

    if args.json:
        clean = {k: v for k, v in report.items() if not k.startswith("_")}
        clean["junk_verdicts"] = [
            {"file": n, "eligible": e, "reason": r} for n, e, r in verdicts
        ]
        print(json.dumps(clean, indent=2, default=str))
    else:
        print(md)
    print(f"[launchagent-reconcile] report → {out}", file=sys.stderr)

    deleted = []
    if args.apply:
        junk_paths = report["_junk_paths"]
        for name, eligible, _reason in verdicts:
            if not eligible:
                continue
            try:
                junk_paths[name].unlink()
                deleted.append(name)
                print(f"[apply] deleted {name}", file=sys.stderr)
            except OSError as e:
                print(f"[apply] FAILED to delete {name}: {e}", file=sys.stderr)
        print(f"[apply] deleted {len(deleted)} junk file(s)", file=sys.stderr)

    if args.alert:
        n_eligible = sum(1 for _n, e, _r in verdicts if e)
        send_telegram(
            "LaunchAgent reconcile: "
            f"{report['live_count']} live, {len(report['junk'])} junk "
            f"({n_eligible} delete-eligible), "
            f"{len(report['zombie_loaded'])} zombie, "
            f"{len(report['present_not_loaded'])} not-loaded, "
            f"{len(report['broken_target'])} broken-target, "
            f"{len(report['home_fork_target'])} home-fork, "
            f"{len(report.get('canon_paired', []))} canon-paired, "
            f"{len(report['repo_divergent'])} repo-divergent. "
            f"Report: {out}"
            + (f" — APPLIED: deleted {len(deleted)}" if args.apply else "")
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
