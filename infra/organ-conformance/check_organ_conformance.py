#!/usr/bin/env python3
"""check_organ_conformance.py — conformance-at-birth gate for launchd/cron organs.

DNA/GENOME mutation (research/operations/2026-07-06-dna-self-healing-genome.md):
every organ must be BORN with the genes self-healing needs. This gate scans the
tracked *.plist files, resolves each payload wrapper, and verifies the statically
checkable genes defined in genes.json (the single source shared with
scripts/organ_birth.py — gate and generator can never disagree on the contract).

Baseline discipline (the grandfather rule, panel-hardened 2026-07-06):
  - a plist listed in genes.json:grandfathered may keep its recorded missing
    genes forever (report-only) — but a PR that makes it WORSE (regression:
    missing genes beyond the recorded set) FAILS;
  - a plist NOT in the baseline is NEW and must carry every applicable gene.
  This kills the grandfather trap: fixing a typo in an old organ never demands
  a full gene retrofit; only regressions and new dark tissue are blocked.

Exit codes (fail-visible, W84 blind-scan guard):
  0 conformant · 1 findings · 2 blind scan (zero plists traversed — a scan
  that saw nothing is NOT a clean scan) · 4 malformed input (plist/genes.json)

Usage:
  python3 infra/organ-conformance/check_organ_conformance.py [--json] [--repo ROOT]
  python3 infra/organ-conformance/check_organ_conformance.py --update-baseline
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import plistlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
GENES_PATH = HERE / "genes.json"
REGISTRY_REL = "apps/organism/organism/organs_registry.yaml"
PAIRS_REL = "infra/home-fork/declared-pairs.json"
KEEPALIVE_LINT_REL = "scripts/lint_plist_keepalive.py"

# --- gene detection patterns (definitions live in genes.json; logic lives here) ---
RE_HEARTBEAT = re.compile(r"organism_heartbeat|\.organism/last_seen|heartbeat\(\)\s*\{")
RE_KILL_SWITCH = re.compile(r"\b[A-Z][A-Z0-9_]*_ENABLED\b")
RE_SET_U = re.compile(r"^\s*set\s+-[a-zA-Z]*u", re.MULTILINE)
RE_CLAUDE_SPAWN = re.compile(r"claude[\"']?\s+-p\b|CLAUDE_BIN[\"']?\s+-p\b|\bclaude\b.*--print\b")
RE_STRICT_MCP = re.compile(r"--strict-mcp-config")
RE_STDIN_NULL = re.compile(r"<\s*/dev/null")
RE_TCC_STRATEGY = re.compile(r"SSH_CONNECTION|TRAMPOLINED|ssh\s+.*localhost")
RE_SINGLE_INSTANCE = re.compile(r"PIDFILE|pidfile|flock\b|mkdir\s+[\"']?\S*\.lock")
RE_HOME_PAYLOAD = re.compile(r"^(?:~|\$HOME|/Users/[^/]+)/(?!Desktop/nuzantara/)")


def _load_keepalive_module(repo_root: Path):
    """Import scripts/lint_plist_keepalive.py for payload resolution reuse
    (single implementation of argv->wrapper logic in the organism)."""
    path = repo_root / KEEPALIVE_LINT_REL
    spec = importlib.util.spec_from_file_location("lint_plist_keepalive", path)
    if spec is None or spec.loader is None:  # pragma: no cover — repo damage
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_tracked_plists(repo_root: Path, roots: list[str]) -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--"]
        + [f"{r}/**/*.plist" for r in roots]
        + [f"{r}/*.plist" for r in roots],
        capture_output=True, text=True, check=False,
    )
    return [repo_root / line for line in out.stdout.splitlines() if line.strip()]


def _first_path_token(argv: list[str]) -> Optional[str]:
    for tok in argv:
        if "/" in tok and not tok.startswith("-"):
            return tok
    return None


def _pair_declared(pairs: dict[str, Any], token: str) -> bool:
    """True if a HOME payload token matches a declared live pair (tail match:
    '~/scripts/x.sh' and '/Users/u/scripts/x.sh' both end 'scripts/x.sh')."""
    def _tail(p: str) -> str:
        p = re.sub(r"^(~|\$HOME|/Users/[^/]+)/", "", p)
        return p
    token_tail = _tail(token)
    for pair in pairs.get("pairs", []):
        if _tail(str(pair.get("live", ""))) == token_tail:
            return True
    return False


def analyze_plist(
    plist_path: Path,
    repo_root: Path,
    ka_mod,
    basename_index: dict[str, list[Path]],
    registry_text: str,
    pairs: dict[str, Any],
    keepalive_failed: set[str],
) -> dict[str, Any]:
    """Return {path, label, missing: [gene..], advisory: [gene..], notes: [..]}."""
    rel = str(plist_path.relative_to(repo_root))
    result: dict[str, Any] = {"path": rel, "label": None, "missing": [], "advisory": [], "notes": []}

    try:
        payload = plistlib.loads(plist_path.read_bytes())
        if not isinstance(payload, dict):
            raise ValueError("plist root is not a dict")
    except Exception as exc:  # noqa: BLE001 — malformed = its own exit class
        result["malformed"] = f"{type(exc).__name__}: {exc}"
        return result

    label = str(payload.get("Label", ""))
    result["label"] = label

    # G1 — registry entry (label textually present in organs_registry.yaml)
    if not label or label not in registry_text:
        result["missing"].append("G1_registry")

    # G8 — KeepAlive sanity (delegated: lint_plist_keepalive FAIL-class findings)
    if rel in keepalive_failed:
        result["missing"].append("G8_keepalive_sane")

    argv = ka_mod.extract_argv(payload)
    token = _first_path_token(argv)

    # G3 — HOME payload must have a declared pair
    home_payload = bool(token and RE_HOME_PAYLOAD.match(token))
    if home_payload and not _pair_declared(pairs, token):
        result["missing"].append("G3_declared_pair")

    # Resolve wrapper text (repo canon) for content genes
    wrapper, reason = ka_mod.resolve_wrapper(argv, repo_root, basename_index)
    text = ""
    if wrapper is not None:
        try:
            text = wrapper.read_text(encoding="utf-8", errors="replace")
            result["wrapper"] = str(wrapper.relative_to(repo_root)) if wrapper.is_relative_to(repo_root) else str(wrapper)
        except OSError:
            result["notes"].append(f"wrapper unreadable: {wrapper}")
    elif ka_mod._has_inline_shell_flag(argv):
        # bash -c '<inline>' — analyze the inline command string itself
        text = " ".join(argv)
        result["wrapper"] = "<inline>"
    else:
        result["notes"].append(f"wrapper unresolved ({reason}) — content genes unverifiable")

    if text:
        is_bash = "<inline>" in str(result.get("wrapper", "")) or str(result.get("wrapper", "")).endswith(".sh")
        if not RE_HEARTBEAT.search(text):
            result["missing"].append("G2_heartbeat")
        if not RE_KILL_SWITCH.search(text):
            result["missing"].append("G5_kill_switch")
        if is_bash and not RE_SET_U.search(text):
            result["missing"].append("G9_fail_visible")
        llm_spawn = bool(RE_CLAUDE_SPAWN.search(text))
        if llm_spawn:
            hardened = (
                RE_STRICT_MCP.search(text)
                and RE_STDIN_NULL.search(text)
                and RE_TCC_STRATEGY.search(text)
            )
            if not hardened:
                result["missing"].append("G6_spawn_hardened")
            if not RE_SINGLE_INSTANCE.search(text):
                result["missing"].append("G10_single_instance")
        elif not RE_SINGLE_INSTANCE.search(text):
            result["advisory"].append("G10_single_instance")
    else:
        # Content genes unverifiable — recorded as missing so the baseline
        # captures the blindness explicitly instead of passing it silently.
        result["missing"].extend(["G2_heartbeat", "G5_kill_switch"])

    return result


def run(repo_root: Path) -> dict[str, Any]:
    try:
        genes_doc = json.loads(GENES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"errors": [f"genes.json unreadable: {exc}"], "exit": 4}

    registry_path = repo_root / REGISTRY_REL
    registry_text = registry_path.read_text(encoding="utf-8") if registry_path.exists() else ""
    if not registry_text:
        return {"errors": [f"registry missing: {REGISTRY_REL}"], "exit": 4}

    pairs_path = repo_root / PAIRS_REL
    try:
        pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"errors": [f"declared-pairs unreadable: {exc}"], "exit": 4}

    ka_mod = _load_keepalive_module(repo_root)
    roots = genes_doc.get("scan_roots", ["infra", "apps", "scripts"])
    plists = _git_tracked_plists(repo_root, roots)
    if not plists:
        return {"errors": ["blind scan: zero tracked plists traversed"], "exit": 2}

    errors: list[str] = []
    ka_index = ka_mod.build_basename_index([repo_root / r for r in roots], errors)

    # One lint_plist_keepalive pass; map FAIL-class findings to plist rel-paths.
    ka_json = ka_mod.run([repo_root / r for r in roots], repo_root, verbose=False)
    keepalive_failed = {f.split(":", 1)[0] for f in ka_json.get("findings", [])}

    grandfathered: dict[str, list[str]] = genes_doc.get("grandfathered", {})
    organs: list[dict[str, Any]] = []
    failures: list[str] = []
    regressions: list[str] = []
    malformed: list[str] = []

    for plist_path in sorted(plists):
        organ = analyze_plist(
            plist_path, repo_root, ka_mod, ka_index, registry_text, pairs, keepalive_failed
        )
        organs.append(organ)
        if "malformed" in organ:
            malformed.append(f"{organ['path']}: {organ['malformed']}")
            continue
        missing = set(organ["missing"])
        if not missing:
            continue
        baseline = grandfathered.get(organ["path"])
        if baseline is None:
            failures.append(
                f"NEW organ without genes: {organ['path']} missing {sorted(missing)}"
            )
        else:
            regression = missing - set(baseline)
            if regression:
                regressions.append(
                    f"REGRESSION: {organ['path']} lost {sorted(regression)} "
                    f"(baseline allowed only {sorted(baseline)})"
                )
            organ["grandfathered"] = True

    exit_code = 0
    if failures or regressions:
        exit_code = 1
    if malformed:
        exit_code |= 4

    return {
        "schema": 1,
        "scanned": len(plists),
        "failures": failures,
        "regressions": regressions,
        "malformed": malformed,
        "grandfathered_count": sum(1 for o in organs if o.get("grandfathered")),
        "organs": organs,
        "errors": errors,
        "exit": exit_code,
    }


def update_baseline(repo_root: Path) -> int:
    report = run(repo_root)
    if report.get("exit") in (2, 4) and not report.get("organs"):
        print(json.dumps(report, indent=1), file=sys.stderr)
        return report["exit"]
    genes_doc = json.loads(GENES_PATH.read_text(encoding="utf-8"))
    genes_doc["grandfathered"] = {
        o["path"]: sorted(o["missing"])
        for o in report.get("organs", [])
        if o.get("missing") and "malformed" not in o
    }
    GENES_PATH.write_text(
        json.dumps(genes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"baseline updated: {len(genes_doc['grandfathered'])} grandfathered organs "
        f"of {report.get('scanned', 0)} scanned"
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Organ conformance-at-birth gate")
    parser.add_argument("--repo", default=None, help="repo root (default: git toplevel of this file)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    if args.repo:
        repo_root = Path(args.repo).resolve()
    else:
        out = subprocess.run(
            ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        repo_root = Path(out.stdout.strip() or ".").resolve()

    if args.update_baseline:
        return update_baseline(repo_root)

    report = run(repo_root)
    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        for line in report.get("errors", []):
            print(f"✗ ERROR {line}")
        for line in report.get("malformed", []):
            print(f"✗ MALFORMED {line}")
        for line in report.get("regressions", []):
            print(f"✗ {line}")
        for line in report.get("failures", []):
            print(f"✗ {line}")
        if report.get("exit") == 0:
            print(
                f"✓ organ conformance: {report.get('scanned', 0)} plists scanned, "
                f"{report.get('grandfathered_count', 0)} grandfathered (report-only), "
                f"0 regressions, 0 non-conformant births"
            )
    return int(report.get("exit", 4))


if __name__ == "__main__":
    sys.exit(main())
