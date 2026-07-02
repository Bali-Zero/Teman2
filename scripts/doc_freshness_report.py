#!/usr/bin/env python3
"""Doc-freshness report — reconciliation signaler for the documentation organs.

Measures what the marker/inventory gates cannot see:

  1. ATLAS DEAD PATHS  — repo-relative references in the atlas files
                         (INDEX/VADEMECUM/README/AI_ONBOARDING/AUTOMATIONS_REFERENCE)
                         that no longer exist on disk.
  2. ORGAN ARMING      — age of each generated doc output vs its declared
                         cadence (built ≠ armed: an on-demand generator with
                         no cadence rots silently — W81 family).
  3. COVERAGE          — enumerable organs vs their catalogs: LaunchAgent
                         plists documented anywhere; apps without README.
  4. DOC↔CODE PAIRING  — per-app README age vs the app's code age ("code
                         moved N days after its doc was last touched").

Report-only by design (W81 antidote: reconciliation-report = signaler, not
auto-actuator; exit 0 even when findings exist). No daemon (W84) — run on
demand, via workflow_dispatch CI, or from the weekly docs-guardian cron.

Scope honesty (#3 under-match, declared): only path-shaped tokens (containing
"/" and starting with a known repo prefix) are checked — bare aspirational
filenames (e.g. `PRICING_REFERENCE.md` in VADEMECUM) are NOT flagged.

No external dependencies. Python stdlib only.

Usage:
    python scripts/doc_freshness_report.py            # markdown to stdout
    python scripts/doc_freshness_report.py --json     # machine-readable
    python scripts/doc_freshness_report.py --write P  # also write to file P
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

ATLAS_FILES = [
    "INDEX.md",
    "VADEMECUM.md",
    "README.md",
    "docs/AI_ONBOARDING.md",
    "docs/AUTOMATIONS_REFERENCE.md",
]

# Path-shaped tokens must start with one of these to be checked (entity match,
# not bare substring — #3 family antidote).
REF_PREFIXES = (
    "apps/",
    "scripts/",
    "docs/",
    "packages/",
    "infra/",
    ".claude/",
    ".github/",
    "shared/",
    "config/",
    "data/",
    "research/",
    # NOT "migrations_v2/": in the docs that token is backend-relative
    # shorthand (apps/backend-rag/backend/db/migrations_v2/), root-resolution
    # would flag it falsely (innocence probe, 2026-07-02).
)

# Declared cadences for generated outputs (organ → (path, cadence_days, generator)).
# cadence_days=None → no declared cadence: age is reported, verdict NO-CADENCE.
GENERATED_OUTPUTS = [
    ("DOCS_INVENTORY", "docs/DOCS_INVENTORY.md", 7, "scripts/docs_audit.py (weekly docs-guardian cron, Pro)"),
    ("DOCS_TRENDS", "docs/DOCS_TRENDS.md", 31, "scripts/docs_history_analyzer.py (monthly by design — NOT armed)"),
    ("AUTOMATIONS_REFERENCE", "docs/AUTOMATIONS_REFERENCE.md", None, "scripts/generate_automations_reference.py (on demand)"),
    ("AUTOMATION_CATALOG", "scripts/automation_catalog.json", None, "hand-maintained JSON"),
]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`\n]+)`")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def _git_last_commit_ts(pathspecs: list[str]) -> int:
    """Unix ts of the last commit touching pathspecs, 0 if unknown."""
    out = _git(["log", "-1", "--format=%ct", "--", *pathspecs]).strip()
    try:
        return int(out)
    except ValueError:
        return 0


def _age_days(ts: int) -> int:
    if ts <= 0:
        return -1
    now = datetime.now(tz=timezone.utc)
    then = datetime.fromtimestamp(ts, tz=timezone.utc)
    return (now.date() - then.date()).days


def _tracked(prefix: str) -> list[str]:
    return [l.strip() for l in _git(["ls-files", prefix]).splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# 1. Atlas dead paths
# ---------------------------------------------------------------------------

def _candidate_refs(doc_rel: str, text: str) -> list[tuple[str, str]]:
    """Extract (kind, target) candidates: markdown links + path-shaped code tokens."""
    out: list[tuple[str, str]] = []
    for m in LINK_RE.finditer(text):
        out.append(("link", m.group(1).strip()))
    for m in CODE_RE.finditer(text):
        out.append(("code", m.group(1).strip()))
    return out


def _normalize(token: str) -> str:
    """Strip anchors/queries, trailing :line and punctuation."""
    token = token.split("#", 1)[0].split("?", 1)[0].strip()
    token = re.sub(r":\d+(-\d+)?$", "", token)  # file.py:12 / file.py:12-30
    return token.rstrip(").,:;")


def _is_checkable_path(token: str) -> bool:
    if not token or " " in token:
        return False
    if token.startswith(("http://", "https://", "mailto:", "#", "/", "~")):
        return False
    if any(ch in token for ch in "*?{}$<>|"):
        return False  # glob / placeholder / expansion — not a literal path
    if "..." in token:
        return False
    if "NNN" in token:
        # NNN = migration-number naming template (VADEMECUM §migrations).
        # Plain substring, NOT \bNNN\b: in `NNN_name.sql` the underscore is a
        # word char, so the word-boundary never matches (caught by tests).
        return False
    return "/" in token and token.startswith(REF_PREFIXES)


def scan_atlas_dead_paths() -> list[dict[str, str]]:
    """Dead repo-relative references across the atlas files."""
    dead: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for rel in ATLAS_FILES:
        doc = REPO_ROOT / rel
        if not doc.is_file():
            dead.append({"doc": rel, "ref": rel, "kind": "atlas-file-missing"})
            continue
        text = doc.read_text(encoding="utf-8", errors="ignore")
        for kind, raw in _candidate_refs(rel, text):
            token = _normalize(raw)
            if kind == "link":
                if token.startswith(("http://", "https://", "mailto:", "#")) or not token:
                    continue
                # Links resolve relative to the doc's directory (docs_audit rule)
                resolved = (doc.parent / token).resolve()
                try:
                    rel_resolved = resolved.relative_to(REPO_ROOT.resolve())
                except ValueError:
                    continue
                if not resolved.exists() and (rel, str(rel_resolved)) not in seen:
                    seen.add((rel, str(rel_resolved)))
                    dead.append({"doc": rel, "ref": str(rel_resolved), "kind": "link"})
            else:
                if not _is_checkable_path(token):
                    continue
                if not (REPO_ROOT / token).exists() and (rel, token) not in seen:
                    seen.add((rel, token))
                    dead.append({"doc": rel, "ref": token, "kind": "code"})
    return dead


# ---------------------------------------------------------------------------
# 2. Organ arming (output age vs declared cadence)
# ---------------------------------------------------------------------------

def scan_organ_arming() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, rel, cadence, generator in GENERATED_OUTPUTS:
        path = REPO_ROOT / rel
        if not path.exists():
            rows.append(
                {"organ": name, "path": rel, "age_days": -1, "cadence_days": cadence,
                 "verdict": "MISSING", "generator": generator}
            )
            continue
        age = _age_days(_git_last_commit_ts([rel]))
        if cadence is None:
            verdict = "NO-CADENCE"
        elif age < 0:
            verdict = "UNKNOWN"
        elif age <= cadence:
            verdict = "OK"
        else:
            verdict = "STALE"
        rows.append(
            {"organ": name, "path": rel, "age_days": age, "cadence_days": cadence,
             "verdict": verdict, "generator": generator}
        )
    return rows


# ---------------------------------------------------------------------------
# 3. Coverage
# ---------------------------------------------------------------------------

def scan_coverage() -> dict[str, Any]:
    labels = [
        rel.rsplit("/", 1)[-1][: -len(".plist")]
        for rel in _tracked("infra/launchagents/")
        if rel.endswith(".plist")
    ]
    haystack = ""
    for rel in ("scripts/automation_catalog.json", "docs/AUTOMATIONS_REFERENCE.md"):
        p = REPO_ROOT / rel
        try:
            haystack += p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    undocumented = sorted(l for l in labels if l not in haystack)

    app_names: set[str] = set()
    apps_with_readme: set[str] = set()
    for rel in _tracked("apps/"):
        parts = rel.split("/", 2)
        if len(parts) >= 2 and parts[1]:
            app_names.add(parts[1])
        if len(parts) == 3 and parts[2] == "README.md":
            apps_with_readme.add(parts[1])
    apps_without_readme = sorted(app_names - apps_with_readme)

    return {
        "plists_total": len(labels),
        "plists_undocumented": undocumented,
        "apps_total": len(app_names),
        "apps_without_readme": apps_without_readme,
    }


# ---------------------------------------------------------------------------
# 4. Doc <-> code pairing
# ---------------------------------------------------------------------------

def scan_doc_code_pairing(min_gap_days: int = 30, top: int = 15) -> list[dict[str, Any]]:
    """Apps whose code last moved > min_gap_days AFTER their README's last touch."""
    app_names: set[str] = set()
    with_readme: set[str] = set()
    for rel in _tracked("apps/"):
        parts = rel.split("/", 2)
        if len(parts) >= 2 and parts[1]:
            app_names.add(parts[1])
        if len(parts) == 3 and parts[2] == "README.md":
            with_readme.add(parts[1])
    rows: list[dict[str, Any]] = []
    for app in sorted(with_readme):
        readme_ts = _git_last_commit_ts([f"apps/{app}/README.md"])
        code_ts = _git_last_commit_ts(
            [f"apps/{app}", f":(exclude)apps/{app}/README.md"]
        )
        if readme_ts <= 0 or code_ts <= 0:
            continue
        gap = (code_ts - readme_ts) // 86400
        if gap >= min_gap_days:
            rows.append(
                {"app": app, "readme_age_days": _age_days(readme_ts),
                 "code_age_days": _age_days(code_ts), "gap_days": int(gap)}
            )
    rows.sort(key=lambda r: (-r["gap_days"], r["app"]))
    return rows[:top]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def gather() -> dict[str, Any]:
    return {
        "dead_paths": scan_atlas_dead_paths(),
        "organ_arming": scan_organ_arming(),
        "coverage": scan_coverage(),
        "doc_code_pairing": scan_doc_code_pairing(),
    }


def render_markdown(data: dict[str, Any]) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out: list[str] = []
    out.append("# Doc-Freshness Report")
    out.append("")
    out.append(f"_Generated by `scripts/doc_freshness_report.py` · {ts} · report-only (signaler, not gate)_")
    out.append("")

    dead = data["dead_paths"]
    out.append(f"## 1. Atlas dead paths ({len(dead)})")
    out.append("")
    if dead:
        out.append("| Doc | Dead reference | Kind |")
        out.append("| --- | -------------- | ---- |")
        for d in dead:
            out.append(f"| {d['doc']} | `{d['ref']}` | {d['kind']} |")
    else:
        out.append("None — every path-shaped reference in the atlas resolves on disk.")
    out.append("")

    out.append("## 2. Organ arming (output age vs declared cadence)")
    out.append("")
    out.append("| Organ | Output | Age (d) | Cadence (d) | Verdict | Generator |")
    out.append("| ----- | ------ | ------: | ----------: | ------- | --------- |")
    for r in data["organ_arming"]:
        cad = r["cadence_days"] if r["cadence_days"] is not None else "—"
        out.append(
            f"| {r['organ']} | `{r['path']}` | {r['age_days']} | {cad} "
            f"| **{r['verdict']}** | {r['generator']} |"
        )
    out.append("")

    cov = data["coverage"]
    und = cov["plists_undocumented"]
    pct = (
        round(100 * (cov["plists_total"] - len(und)) / cov["plists_total"])
        if cov["plists_total"]
        else 0
    )
    out.append("## 3. Coverage")
    out.append("")
    out.append(
        f"- LaunchAgents: **{cov['plists_total']} plists tracked**, "
        f"{len(und)} documented nowhere ({pct}% coverage)."
    )
    if und:
        out.append(f"  - Undocumented: {', '.join('`' + u + '`' for u in und[:20])}"
                   + (f" … +{len(und) - 20} more" if len(und) > 20 else ""))
    out.append(
        f"- Apps: **{cov['apps_total']} tracked**, "
        f"{len(cov['apps_without_readme'])} without README.md."
    )
    if cov["apps_without_readme"]:
        out.append(
            "  - No README: "
            + ", ".join("`" + a + "`" for a in cov["apps_without_readme"])
        )
    out.append("")

    pairs = data["doc_code_pairing"]
    out.append("## 4. Doc↔code pairing (code moved ≥30d after its README)")
    out.append("")
    if pairs:
        out.append("| App | README age (d) | Code age (d) | Gap (d) |")
        out.append("| --- | -------------: | -----------: | ------: |")
        for p in pairs:
            out.append(
                f"| `apps/{p['app']}` | {p['readme_age_days']} "
                f"| {p['code_age_days']} | {p['gap_days']} |"
            )
    else:
        out.append("None above threshold.")
    out.append("")
    out.append(
        "> Scope honesty: bare filenames without a path prefix are NOT checked "
        "(declared under-match, #3 family); repomap liveness is machine-local "
        "state and out of scope for a repo-side report."
    )
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc-freshness reconciliation report")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser.add_argument("--write", metavar="PATH", help="also write the report to PATH")
    args = parser.parse_args()

    try:
        data = gather()
    except Exception as exc:  # catastrophic only — report-only otherwise
        print(f"doc_freshness_report: fatal: {exc}", file=sys.stderr)
        return 2

    output = json.dumps(data, indent=2) if args.json else render_markdown(data)
    print(output)
    if args.write:
        Path(args.write).write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
