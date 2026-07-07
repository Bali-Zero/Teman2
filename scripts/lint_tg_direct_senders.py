#!/usr/bin/env python3
"""lint_tg_direct_senders.py — the anti-regrowth guard for the Telegram gateway.

The 2026-07-06 census found ~240 tracked files calling api.telegram.org
directly. Those are GRANDFATHERED (infra/tg-gateway/grandfathered.json) and
will migrate to scripts/tg_notify.py cohort by cohort. This lint fails CI when
a NEW file joins the direct-sender family, so it can only shrink.

Verdict logic:
  exit 0  — no new direct senders
  exit 1  — new direct sender(s) outside the grandfather list (guilt)
  exit 2  — blind-scan guard: zero files scanned (a lint that scanned nothing
            must not report "clean" — W84 green-but-dead)

Modes:
  --freeze     regenerate grandfathered.json from the current tree
  --prune      report grandfathered entries that no longer send directly
  --selftest   guilt+innocence fixtures in a temp tree

Registered in infra/guard-conformance/registry.json (superscar #3: a guard
ships only with both a guilt and an innocence proof).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PATTERN = "api.telegram.org"
SCAN_SUFFIXES = {".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".plist", ".rb", ".pl", ".zsh", ".bash"}
# NOTE (deliberate over-match, superscar #3 traded consciously): the scan is
# textual, so a MENTION in a comment/docstring counts as a hit. That is the
# safe direction — keep the URL string out of non-gateway files entirely.
GATEWAY_ALLOWLIST = {
    "scripts/tg_notify.py",        # the gateway itself
    "scripts/tg_digest_flush.py",  # its flusher
    "scripts/lint_tg_direct_senders.py",  # this lint (pattern is its constant)
    "scripts/tests/test_tg_gateway.py",   # the gateway's own test fixtures
}


def _root() -> Path:
    return Path(os.environ.get("TG_LINT_ROOT", ".")).resolve()


def _grandfather_path(root: Path) -> Path:
    return root / "infra" / "tg-gateway" / "grandfathered.json"


def tracked_files(root: Path) -> list[Path]:
    env_list = os.environ.get("TG_LINT_FILES", "")
    if env_list:  # selftest fixture path: explicit file list, no git needed
        return [root / f for f in env_list.split(":") if f]
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [root / line for line in out.splitlines() if Path(line).suffix in SCAN_SUFFIXES]


def scan(root: Path) -> tuple[set[str], int]:
    """Return (relative paths of direct senders, files scanned)."""
    senders: set[str] = set()
    scanned = 0
    for path in tracked_files(root):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        scanned += 1
        if PATTERN in text:
            senders.add(str(path.relative_to(root)))
    return senders, scanned


def load_grandfathered(root: Path) -> set[str]:
    try:
        data = json.loads(_grandfather_path(root).read_text())
        return set(data.get("files", []))
    except (OSError, ValueError):
        return set()


def freeze(root: Path) -> int:
    senders, scanned = scan(root)
    if scanned == 0:
        print("lint_tg: BLIND SCAN — zero files scanned, refusing to freeze", file=sys.stderr)
        return 2
    payload = {
        "_doc": (
            "Direct api.telegram.org senders grandfathered at gateway birth "
            "(2026-07-06). This list only SHRINKS: migrate a file to "
            "scripts/tg_notify.py, then remove it here (or run --prune). "
            "New files must use the gateway — the lint fails CI otherwise."
        ),
        "frozen_at": "2026-07-06",
        "files": sorted(senders - GATEWAY_ALLOWLIST),
    }
    gp = _grandfather_path(root)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"lint_tg: froze {len(payload['files'])} grandfathered direct senders")
    return 0


def _guard_new_direct_sender(senders: set, grandfathered: set) -> set:
    """The guard proper (censused in guard-conformance registry, superscar #3).

    GUILT: a file outside grandfathered+gateway that hits api.telegram.org is
    flagged. INNOCENCE: grandfathered legacy senders and the gateway itself
    are never flagged.
    """
    return senders - grandfathered - GATEWAY_ALLOWLIST


def check_monotone(root: Path) -> tuple[bool, set]:
    """Anti-bypass (Codex finding 2026-07-06): a PR could add a sender AND
    grandfather it in the same diff. The list may only SHRINK vs origin/main.
    Returns (ok, added). Skips gracefully when origin/main has no list yet
    (gateway-birth PR) or git is unavailable (selftest override: TG_LINT_BASE_JSON).
    """
    base_override = os.environ.get("TG_LINT_BASE_JSON", "")
    try:
        if base_override:
            old_raw = Path(base_override).read_text()
        else:
            old_raw = subprocess.run(
                ["git", "-C", str(root), "show", "origin/main:infra/tg-gateway/grandfathered.json"],
                capture_output=True, text=True, check=True,
            ).stdout
        old = set(json.loads(old_raw).get("files", []))
    except Exception:
        print("lint_tg: monotone check skipped (no grandfathered.json on origin/main yet)")
        return True, set()
    added = load_grandfathered(root) - old
    return (not added), added


def lint(root: Path, prune: bool = False) -> int:
    senders, scanned = scan(root)
    if scanned == 0:
        print("lint_tg: BLIND SCAN — zero files scanned; not clean, BROKEN", file=sys.stderr)
        return 2
    grandfathered = load_grandfathered(root)
    offenders = _guard_new_direct_sender(senders, grandfathered)

    if prune:
        gone = grandfathered - senders
        if gone:
            print(f"lint_tg: {len(gone)} grandfathered files no longer send directly — prunable:")
            for f in sorted(gone):
                print(f"  - {f}")
        else:
            print("lint_tg: nothing to prune")

    if offenders:
        print(f"lint_tg: FAIL — {len(offenders)} NEW direct Telegram sender(s). "
              f"Use scripts/tg_notify.py (--tier p0|digest|log) instead:", file=sys.stderr)
        for f in sorted(offenders):
            print(f"  - {f}", file=sys.stderr)
        return 1

    mono_ok, added = check_monotone(root)
    if not mono_ok:
        print(f"lint_tg: FAIL — grandfathered.json GREW by {len(added)} entr(y/ies) vs "
              f"origin/main (the list only shrinks; migrate to the gateway instead):",
              file=sys.stderr)
        for f in sorted(added):
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"lint_tg: clean ({scanned} files scanned, {len(grandfathered)} grandfathered)")
    return 0


def selftest() -> int:
    import tempfile

    failures = []

    def check(name, cond):
        print(("  ok  " if cond else "  FAIL") + f" {name}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "infra" / "tg-gateway").mkdir(parents=True)
        (root / "scripts").mkdir()
        old = root / "scripts" / "old_sender.sh"
        old.write_text("curl https://api.telegram.org/botX/sendMessage\n")
        innocent = root / "scripts" / "clean_tool.py"
        innocent.write_text("print('uses gateway via tg_notify')\n")
        docmention = root / "scripts" / "README.txt"  # not in SCAN_SUFFIXES
        docmention.write_text("mentions api.telegram.org harmlessly\n")
        gateway = root / "scripts" / "tg_notify.py"
        gateway.write_text("API = 'https://api.telegram.org'\n")

        os.environ["TG_LINT_ROOT"] = str(root)
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:scripts/clean_tool.py:scripts/tg_notify.py"

        # freeze grandfathers the existing offender
        check("freeze exits 0", freeze(root) == 0)
        gf = json.loads((root / "infra/tg-gateway/grandfathered.json").read_text())["files"]
        check("old sender grandfathered", "scripts/old_sender.sh" in gf)
        check("gateway NOT grandfathered", "scripts/tg_notify.py" not in gf)

        # innocence: clean tree passes
        check("clean tree passes", lint(root) == 0)

        # guilt: a NEW direct sender fails
        new = root / "scripts" / "new_sender.py"
        new.write_text("requests.post('https://api.telegram.org/bot')\n")
        os.environ["TG_LINT_FILES"] += ":scripts/new_sender.py"
        check("new sender FAILS", lint(root) == 1)

        # innocence: gateway allowlist never flagged even when new
        os.environ["TG_LINT_FILES"] = "scripts/tg_notify.py:scripts/clean_tool.py"
        check("gateway alone passes", lint(root) == 0)

        # blind-scan guard
        os.environ["TG_LINT_FILES"] = "scripts/does_not_exist.py"
        check("blind scan → exit 2", lint(root) == 2)

        # monotone guard: grandfathered.json growing vs base = FAIL
        os.environ["TG_LINT_FILES"] = "scripts/old_sender.sh:scripts/clean_tool.py"
        base = root / "base_grandfathered.json"
        base.write_text(json.dumps({"files": []}))  # base list EMPTY, current has old_sender
        os.environ["TG_LINT_BASE_JSON"] = str(base)
        check("grandfather growth → FAIL", lint(root) == 1)
        base.write_text(json.dumps({"files": ["scripts/old_sender.sh"]}))  # base == current
        check("grandfather stable → pass", lint(root) == 0)
        os.environ.pop("TG_LINT_BASE_JSON", None)

        os.environ.pop("TG_LINT_FILES", None)
        os.environ.pop("TG_LINT_ROOT", None)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main() -> int:
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    root = _root()
    if "--freeze" in args:
        return freeze(root)
    return lint(root, prune="--prune" in args)


if __name__ == "__main__":
    sys.exit(main())
