#!/usr/bin/env python3
"""Playwright context injector — emit LLM-ready context for a site/action.

Reads docs/playwright/sites/*.yaml (the site atlas) and emits focused markdown
that any LLM (Claude, Gemini CLI, Codex, Ollama) can consume as system context.

Usage:
    # By site name + optional action
    inject.py --site canva
    inject.py --site canva --action generate_image_via_magic_media

    # By URL pattern (auto-detect site)
    inject.py --url https://www.canva.com/design/DAHE6lx1lf8/edit

    # List available
    inject.py --list
    inject.py --list canva  # list actions for one site

    # Different output shapes
    inject.py --site canva --format markdown   # default
    inject.py --site canva --format compact    # one-liner
    inject.py --site canva --format json       # structured

Exit codes: 0 OK, 1 no match, 2 config error.

Intended wiring:
    * Claude Code PreToolUse hook: invoke before mcp__playwright__* tool calls
    * Cron wrappers: CTX=$(inject.py --site $SITE) && gemini --system "$CTX" ...
    * Slash commands: /playwright-context canva → inserts markdown
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


_THIS = Path(__file__).resolve()
_REPO = _THIS.parent.parent.parent  # tools/playwright-context/ -> tools/ -> repo
SITES_DIR = _REPO / "docs" / "playwright" / "sites"
README_PATH = _REPO / "docs" / "playwright" / "NEXT-CLAUDE-README.md"
PLAYBOOK_PATH = _REPO / "docs" / "playwright" / "SITE-PLAYBOOK.md"


def load_all_sites() -> dict[str, dict[str, Any]]:
    sites: dict[str, dict[str, Any]] = {}
    if not SITES_DIR.is_dir():
        return sites
    for yml in sorted(SITES_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text())
            if isinstance(data, dict) and data.get("site"):
                sites[data["site"]] = data
        except Exception as e:
            print(f"WARN: failed to parse {yml}: {e}", file=sys.stderr)
    return sites


def match_site_by_url(url: str, sites: dict[str, dict]) -> str | None:
    for name, data in sites.items():
        for pat in data.get("url_patterns_match", []) or []:
            if pat and pat in url:
                return name
    return None


def format_markdown(site_data: dict[str, Any], action: str | None = None) -> str:
    """Render a site profile as focused markdown for LLM system prompt."""
    name = site_data.get("display_name") or site_data.get("site", "unknown")
    verified = site_data.get("verified", "unknown date")
    out: list[str] = []

    out.append(f"# Playwright site: {name}")
    out.append(f"_Last verified: {verified}_  ·  profile: `{site_data.get('profile_dir', 'TBD')}`")
    out.append("")

    # Account
    if acct := site_data.get("account_hint"):
        out.append(f"**Account**: {acct}")
        out.append("")

    # URLs
    urls = site_data.get("urls") or {}
    if urls:
        out.append("## URLs")
        for k, v in urls.items():
            if v:
                out.append(f"- `{k}`: {v}")
        out.append("")

    # If action specified, print only that flow
    flows = site_data.get("flows") or {}
    if action:
        if action not in flows:
            out.append(f"> **Action {action!r} not found.** Available: {', '.join(flows.keys()) or 'none'}")
        else:
            flow = flows[action]
            out.append(f"## Action: {action}")
            out.append(f"Entry: `{flow.get('entry', 'n/a')}`")
            out.append("")
            out.append("Steps:")
            for i, step in enumerate(flow.get("steps") or [], 1):
                out.append(f"{i}. `{yaml.safe_dump(step, default_flow_style=True).strip()}`")
            if output := flow.get("output") or flow.get("output_path"):
                out.append(f"\nOutput: {output}")
            out.append("")
    else:
        # Summary of all flows
        if flows:
            out.append(f"## Available flows ({len(flows)})")
            for fname, fdata in flows.items():
                first_step = (fdata.get("steps") or [{}])[0]
                hint = list(first_step.keys())[0] if first_step else "?"
                out.append(f"- `{fname}` — starts with `{hint}`")
            out.append("")

    # Selectors
    sels = site_data.get("selectors") or {}
    if sels:
        out.append("## Selectors")
        for k, v in sels.items():
            out.append(f"- `{k}`: `{v}`")
        out.append("")

    # Gotchas
    if gotchas := site_data.get("gotchas"):
        out.append(f"## Gotchas ({len(gotchas)})")
        for g in gotchas:
            if isinstance(g, dict):
                out.append(f"- **{g.get('id', '?')}**: {g.get('desc', '')}")
            else:
                out.append(f"- {g}")
        out.append("")

    # Recovery
    if login := site_data.get("login"):
        if recovery := login.get("recovery"):
            out.append("## Recovery (login expired)")
            out.append(f"```bash\n{recovery}\n```")
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def format_compact(site_data: dict[str, Any], action: str | None = None) -> str:
    """One-line summary for use in shell env or short context windows."""
    name = site_data.get("site")
    flows = site_data.get("flows") or {}
    if action and action in flows:
        steps = flows[action].get("steps") or []
        return f"[{name}/{action}] {len(steps)} steps, profile={site_data.get('profile_dir')}"
    return f"[{name}] flows={list(flows.keys())}, verified={site_data.get('verified')}"


def format_json(site_data: dict[str, Any], action: str | None = None) -> str:
    if action:
        flows = site_data.get("flows") or {}
        return json.dumps({
            "site": site_data.get("site"),
            "action": action,
            "flow": flows.get(action),
            "selectors": site_data.get("selectors"),
            "gotchas": site_data.get("gotchas"),
        }, indent=2, default=str)
    return json.dumps(site_data, indent=2, default=str)


def list_sites(sites: dict[str, dict], filter_site: str | None = None) -> str:
    if filter_site:
        if filter_site not in sites:
            return f"Site {filter_site!r} not found. Known: {', '.join(sites)}"
        flows = sites[filter_site].get("flows") or {}
        return f"Site: {filter_site}\nActions: {', '.join(flows) or '(none)'}\n"
    lines = [f"{len(sites)} sites registered:"]
    for name, data in sorted(sites.items()):
        flows = data.get("flows") or {}
        lines.append(f"  {name}: {len(flows)} flows, verified {data.get('verified', '?')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", help="Site name (e.g. canva, gemini, flow)")
    ap.add_argument("--url", help="URL to auto-match against url_patterns_match")
    ap.add_argument("--action", help="Flow name within site (use --list for available)")
    ap.add_argument("--format", choices=["markdown", "compact", "json"], default="markdown")
    ap.add_argument("--list", nargs="?", const="", help="List sites or actions for a given site")
    args = ap.parse_args()

    sites = load_all_sites()
    if not sites:
        print(f"ERROR: no sites loaded from {SITES_DIR}", file=sys.stderr)
        return 2

    if args.list is not None:
        print(list_sites(sites, args.list or None))
        return 0

    site_name = args.site
    if args.url and not site_name:
        site_name = match_site_by_url(args.url, sites)
        if not site_name:
            print(f"ERROR: no site matched URL {args.url!r}", file=sys.stderr)
            return 1

    if not site_name:
        print("ERROR: specify --site or --url", file=sys.stderr)
        return 2

    if site_name not in sites:
        print(f"ERROR: unknown site {site_name!r}. Known: {', '.join(sites)}", file=sys.stderr)
        return 1

    data = sites[site_name]
    renderer = {"markdown": format_markdown, "compact": format_compact, "json": format_json}[args.format]
    print(renderer(data, args.action))
    return 0


if __name__ == "__main__":
    sys.exit(main())
