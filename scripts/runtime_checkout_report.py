#!/usr/bin/env python3
"""runtime_checkout_report.py — which launchd organ runs from which checkout (SPEC split, P0).

The migration (P2) needs to move ~104 launchd organs off the dirty main checkout onto the
stable -deploy clone. Before moving anything you must KNOW, per organ, which checkout its
installed plist currently points at. This script is that map — read-only, INERT, no migration.

It cross-references:
  - organs_registry.yaml  (the source of truth: organ id, runtime, label, owner_module)
  - the installed *.plist files in ~/Library/LaunchAgents (what's ACTUALLY loaded)  [if present]
  - the repo's infra/launchagents/*.plist                                            [fallback]

and classifies each pro_launchd organ's runtime root as: deploy | dirty-main | external | unknown.

This is the P0 deliverable that replaces "hand-edit 104 plists": it makes the drift VISIBLE and
machine-readable so P2 can migrate from a list, not by eyeballing. It does NOT yet emit full
generated plists — the registry lacks the launchd schedule/env/args fields for that; enriching
the registry with those is its own step (flagged in the report as `registry_launchd_gap`).

Usage:
    python3 scripts/runtime_checkout_report.py [--repo DIR] [--launchagents DIR] [--json]
Exit: 0 always (it's a report). Use --strict to exit 1 if any organ runs from dirty-main.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

DEPLOY_MARKER = "nuzantara-deploy"


def _load_registry(repo: Path) -> list[dict]:
    reg = repo / "apps" / "organism" / "organism" / "organs_registry.yaml"
    d = yaml.safe_load(reg.read_text(encoding="utf-8"))
    return [o for o in d.get("organs", []) if isinstance(o, dict) and o.get("id")]


def _plist_paths(plist_text: str) -> list[str]:
    """Extract every /Users/.../nuzantara* path string from a plist."""
    return re.findall(r"/Users/[^<\s]+/nuzantara[A-Za-z0-9_./-]*", plist_text)


def _classify_root(paths: list[str]) -> str:
    if not paths:
        return "unknown"
    if any(DEPLOY_MARKER in p for p in paths):
        return "deploy"
    # any plain nuzantara path that is NOT -deploy = the dirty main checkout
    if any(re.search(r"/nuzantara(?![A-Za-z0-9-])", p) for p in paths):
        return "dirty-main"
    return "external"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path.home() / "Desktop" / "nuzantara"))
    ap.add_argument("--launchagents", default=str(Path.home() / "Library" / "LaunchAgents"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any organ runs from dirty-main")
    args = ap.parse_args()

    repo = Path(args.repo)
    la_dir = Path(args.launchagents)
    repo_la = repo / "infra" / "launchagents"

    organs = _load_registry(repo)
    rows = []
    gap = 0
    for o in organs:
        if o.get("runtime") != "pro_launchd" or o.get("enabled") is False:
            continue
        label = (o.get("recovery_params") or {}).get("label")
        # prefer the INSTALLED plist (truth), fall back to repo plist
        text = None
        src = None
        if label:
            for base in (la_dir, repo_la):
                p = base / f"{label}.plist"
                if p.exists():
                    try:
                        text = p.read_text(encoding="utf-8")
                        src = str(p)
                        break
                    except OSError:
                        continue
        paths = _plist_paths(text) if text else []
        root = _classify_root(paths) if text else "no-plist-found"
        # registry_launchd_gap: organ has no installed/repo plist we can read → can't generate yet
        if root in ("no-plist-found", "unknown"):
            gap += 1
        rows.append({
            "id": o["id"],
            "label": label,
            "owner_module": o.get("owner_module"),
            "runtime_root": root,
            "plist_src": src,
        })

    by_root: dict[str, int] = {}
    for r in rows:
        by_root[r["runtime_root"]] = by_root.get(r["runtime_root"], 0) + 1

    summary = {
        "total_pro_launchd": len(rows),
        "by_runtime_root": by_root,
        "registry_launchd_gap": gap,
        "note": "P2 must migrate every 'dirty-main' organ onto the -deploy clone.",
    }

    if args.json:
        print(json.dumps({"summary": summary, "organs": rows}, indent=2))
    else:
        print("=== runtime checkout report (P0, read-only) ===")
        print(f"total pro_launchd enabled organs: {summary['total_pro_launchd']}")
        for root, n in sorted(by_root.items(), key=lambda kv: -kv[1]):
            print(f"  {root:16s} {n}")
        print(f"registry_launchd_gap (no readable plist): {gap}")
        dm = [r for r in rows if r["runtime_root"] == "dirty-main"]
        if dm:
            print(f"\n-- {len(dm)} organs to migrate off dirty-main (sample 10) --")
            for r in dm[:10]:
                print(f"  {r['id']:38s} {r['label']}")

    if args.strict and by_root.get("dirty-main", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
