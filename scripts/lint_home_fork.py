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
    pairs: list[dict[str, Any]], repo_root: Path, home: Path, label: str
) -> list[str]:
    """The --check arm: sha256 live vs repo twin for machine-applicable pairs."""
    breaches: list[str] = []
    for pair in pairs:
        if not pair_applies(pair, label):
            continue
        live = expand_home(pair["live"], home)
        repo = repo_root / pair["repo"]
        if not live.exists():
            continue  # this machine does not run that copy — not a breach
        if not repo.exists():
            breaches.append(
                f"NO-REPO-TWIN: {pair['live']} executes live but {pair['repo']} "
                f"is not in the repo — the live copy has no source of truth"
            )
            continue
        if sha256_file(live) != sha256_file(repo):
            breaches.append(
                f"DIVERGED: {pair['live']} != {pair['repo']} — a fix is stranded "
                f"on one side (port the newer content, then realign live from repo)"
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
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--system", action="store_true",
        help="also scan /Library/LaunchAgents + /Library/LaunchDaemons (read-only)",
    )
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--plist-dir", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    run_check = args.check or not args.discover
    run_discover = args.discover or not args.check

    label = machine_label()
    config = load_config(args.config)
    pairs = merge_pairs(config["pairs"], proprioception_pairs(args.repo_root))
    allow = list(config["allow"])

    breaches: list[str] = []
    undeclared: list[str] = []
    errors: list[str] = []

    if run_check:
        breaches = check_pairs(pairs, args.repo_root, args.home, label)

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

    exit_code = (1 if breaches else 0) | (2 if undeclared else 0) | (4 if errors else 0)

    if args.json:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "machine": label,
                    "check_breaches": breaches,
                    "discover_undeclared": undeclared,
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
        if not breaches:
            print("  clean — every live copy matches its repo twin")
    if run_discover:
        print(f"[discover] undeclared HOME-executed payloads: {len(undeclared)}")
        for f in undeclared:
            print(f"  - {f}")
        if not undeclared:
            print("  clean — every HOME-executed payload is declared, allowed, or repo-resident")
    if errors:
        print(f"[errors] {len(errors)} operational error(s) — scan is PARTIAL, not clean:")
        for e in errors:
            print(f"  - {e}")
    if exit_code:
        print(
            f"HOME-FORK LINT FAIL (exit {exit_code}: 1=diverged 2=undeclared 4=scan-error) — "
            f"superscar #1: declare the pair in infra/home-fork/declared-pairs.json (then "
            f"realign), or allow-list a known-benign payload"
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
