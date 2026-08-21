#!/usr/bin/env python3
"""baseline_debt_report.py — visibility over `.secrets.baseline`'s eternal-forgiveness gap.

`.secrets.baseline` (455 file entries measured 2026-08-21) makes the daily/weekly
"Detect Secrets" scan (`.github/workflows/security.yml`) permanently green for any
finding that carries an `is_secret` decision, true OR false — `detect_secrets_check_
unaudited.py` only checks the KEY exists, never its value. A finding entered as
`is_secret: false` therefore never resurfaces, forever, even if it is a real live
credential and even if the file it lives in changes around it later.

This is not hypothetical: on 2026-08-21 nine files under `apps/backend-rag/scripts/`
were found to carry a live Google OAuth triple (client_id + GOCSPX- client secret +
1// refresh token) in cleartext, unnoticed for months. detect-secrets has no
GOCSPX-/1// detector, so it classified the finding as generic "Base64 High Entropy
String" / "Secret Keyword" noise — and a SINGLE broad rule in
`scripts/detect_secrets_auto_triage.py`'s `AUTO_APPROVE_RULES`
(`apps/backend-rag/scripts/.*\\.(py|sh)$`, path-only, zero content check) blanket-
approved every finding under that whole directory, real or not, on every CI run.

This script is a PURE SIGNALER, modeled on `scripts/pending_arms_report.py` (superscar
family #2, "Esiste != Armato"): it never mutates `.secrets.baseline`, never mutates
`detect_secrets_auto_triage.py`, and never revokes/rotates anything. It only measures
and reports two structural risk axes that `detect_secrets_check_unaudited.py` cannot
see because it only asks "does a decision exist", never "how was the decision earned":

  1. APPROVAL BREADTH — for every `is_secret: false` finding, which rule earned that
     verdict: a narrow CONTENT_KEYED_RULES match (path AND the exact source line, so
     an unrelated secret added later on a different line is NOT covered), a broad
     AUTO_APPROVE_RULES match (path/extension glob only — approves every finding in
     scope regardless of content, past or future), a HARD_BLOCK (never auto-approved,
     residue for human review), or "no current rule" (baseline says false but the
     live ruleset would not re-approve it today — drifted, worth a second look).
     Broad-approved findings in files that STILL EXIST on HEAD are the highest-risk
     bucket: nothing has ever inspected their content, and the same blanket rule
     would silently approve a genuinely new secret added tomorrow.

  2. STALENESS — baseline entries for files no longer on HEAD (`git ls-tree`). These
     are dead weight: they cannot be re-triaged sensibly (nothing to read) and they
     inflate every future `--report` walk. Not a live-secret risk by themselves, but
     baseline bloat that makes the live entries harder to see.

A first version of --strict gated on the finding's own `type` (Private Key / Telegram
Bot Token / JSON Web Token / Basic Auth Credentials — that last type-name is itself an
earlier self-catch: an example DSN written out in full here once tripped this file's own
scan, the same class of finding this paragraph is discussing). Measured against this
repo's real baseline that produced 110 "high-signal" hits, almost all placeholder
database connection strings in test fixtures and `.env.example` files — a literal
`user:pass` pair behind a `postgres` scheme and colon-slash-slash prefix, `test`/`test`
or `user`/masked, pointing at a documentation-only `host/db` — the OAuth-9 finding
itself was NOT among them, because
detect-secrets classified it as generic entropy noise, not as any of those types. A gate
built on `type` alone would have been both too noisy to trust (family #3 lesson: a guard
nobody trusts gets disabled) AND blind to the one incident that motivated this script.
Replaced with CONTENT-SHAPE patterns for vendor-specific credential prefixes that have
near-zero legitimate-fixture collision risk (GOCSPX-, `1//`, `AKIA`, `gh[pousr]_`,
`xox[baprs]-`, `sk_live_`) — verified zero false positives across this repo's 326
live baseline files, and exactly the shape that caught the real leak.

Usage:
    python3 scripts/baseline_debt_report.py                # markdown report, exit 0
    python3 scripts/baseline_debt_report.py --json          # machine-readable
    python3 scripts/baseline_debt_report.py --strict        # exit 1 if a broad-approved
                                                              finding on HEAD sits in a
                                                              file whose content matches
                                                              a vendor-specific
                                                              high-confidence credential
                                                              shape (see HIGH_CONFIDENCE_
                                                              PATTERNS below)

--strict is NOT wired into CI by this change (see ledger). It exists so a human or a
future PR can promote it deliberately, the way pending_arms_report.py's --strict was
promoted separately from the script itself.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / ".secrets.baseline"
AUTO_TRIAGE_MODULE = REPO_ROOT / "scripts" / "detect_secrets_auto_triage.py"

# Vendor-specific magic-prefix credential shapes. Each has a near-zero
# legitimate-fixture collision rate in practice (unlike generic "sk-" or
# generic high-entropy strings, both of which this repo's own test fixtures
# use as placeholder text — see module docstring). Verified zero false
# positives across this repo's 326 live baseline files on 2026-08-21.
HIGH_CONFIDENCE_PATTERNS: dict[str, re.Pattern[bytes]] = {
    "google_oauth_client_secret": re.compile(rb"GOCSPX-[A-Za-z0-9_\-]{20,}"),
    "google_oauth_refresh_token": re.compile(rb"\b1//[A-Za-z0-9_\-]{30,}"),
    "aws_access_key_id": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}"),
    "slack_token": re.compile(rb"\bxox[baprs]-[0-9A-Za-z\-]{10,}"),
    "stripe_live_key": re.compile(rb"\bsk_live_[0-9a-zA-Z]{24,}"),
}


def _load_auto_triage():
    """Import detect_secrets_auto_triage.py by path (sibling script, reuse-first —
    avoids re-encoding its ~120 rules here, which would drift the moment either
    file is edited alone)."""
    spec = importlib.util.spec_from_file_location("detect_secrets_auto_triage", AUTO_TRIAGE_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {AUTO_TRIAGE_MODULE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _files_on_head() -> set[str]:
    """git ls-tree of HEAD — what the checkout actually has right now."""
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(line.strip() for line in r.stdout.splitlines() if line.strip())


def _high_confidence_shapes(file_path: str) -> list[str]:
    """Which HIGH_CONFIDENCE_PATTERNS match this file's live content, by name
    only — never returns or logs the matched bytes."""
    full = REPO_ROOT / file_path
    try:
        content = full.read_bytes()
    except OSError:
        return []
    return [name for name, pat in HIGH_CONFIDENCE_PATTERNS.items() if pat.search(content)]


def _classify_approval(mod: Any, file_path: str, line_number: int | None) -> str:
    """Re-derive which rule bucket earned a finding's is_secret:false, using the
    LIVE ruleset (not whatever was true when the baseline was generated)."""
    for pat, reason in mod.HARD_BLOCK_RULES:
        if pat.search(file_path):
            return "hard_block"
    for path_pat, content_pat, reason in mod.CONTENT_KEYED_RULES:
        if path_pat.search(file_path) and line_number:
            text = mod._line_text(file_path, line_number)
            if text is not None and content_pat.search(text):
                return "content_keyed"
    for pat, reason in mod.AUTO_APPROVE_RULES:
        if pat.search(file_path):
            return "auto_approve_broad"
    return "no_current_rule"


def analyze() -> dict[str, Any]:
    baseline = json.loads(BASELINE.read_text())
    results = baseline.get("results", {})
    on_head = _files_on_head()
    mod = _load_auto_triage()

    total_files = len(results)
    stale_files: list[str] = []
    live_files = 0

    approval_buckets: Counter[str] = Counter()
    broad_and_live: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    shape_cache: dict[str, list[str]] = {}
    high_confidence_broad_and_live: list[dict[str, Any]] = []

    for file_path, hits in results.items():
        exists = file_path in on_head
        if not exists:
            stale_files.append(file_path)
            continue
        live_files += 1
        for hit in hits:
            ftype = hit.get("type", "?")
            type_counts[ftype] += 1
            is_secret = hit.get("is_secret")
            if is_secret is not False:
                # unaudited or is_secret:true — not this script's axis (the
                # existing unaudited gate already covers "no decision"; a
                # true positive left in baseline as is_secret:true is its
                # own, differently-shaped problem, out of scope here).
                continue
            bucket = _classify_approval(mod, file_path, hit.get("line_number"))
            approval_buckets[bucket] += 1
            if bucket == "auto_approve_broad":
                entry = {
                    "file": file_path,
                    "line": hit.get("line_number"),
                    "type": ftype,
                }
                broad_and_live.append(entry)
                if file_path not in shape_cache:
                    shape_cache[file_path] = _high_confidence_shapes(file_path)
                shapes = shape_cache[file_path]
                if shapes:
                    high_confidence_broad_and_live.append({**entry, "shapes": shapes})

    # dedupe by file (a file can carry several findings, we only need to
    # name it once per matched shape for the report)
    high_confidence_by_file: dict[str, set[str]] = {}
    for e in high_confidence_broad_and_live:
        high_confidence_by_file.setdefault(e["file"], set()).update(e["shapes"])

    return {
        "baseline_generated_at": baseline.get("generated_at"),
        "total_baseline_files": total_files,
        "live_files": live_files,
        "stale_files_count": len(stale_files),
        "stale_files": sorted(stale_files),
        "approval_buckets": dict(approval_buckets),
        "broad_and_live_count": len(broad_and_live),
        "broad_and_live": broad_and_live,
        "high_confidence_shape_files_count": len(high_confidence_by_file),
        "high_confidence_shape_files": {f: sorted(s) for f, s in sorted(high_confidence_by_file.items())},
        "type_counts_live_files": dict(type_counts),
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = []
    lines.append("# .secrets.baseline debt report\n")
    lines.append(f"Baseline generated: {data['baseline_generated_at']}\n")
    lines.append(
        f"- Total baseline entries: **{data['total_baseline_files']}** "
        f"({data['live_files']} still on HEAD, {data['stale_files_count']} stale/deleted)\n"
    )
    lines.append("\n## Approval breadth (is_secret:false findings on live files)\n")
    for bucket, count in sorted(data["approval_buckets"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{bucket}`: {count}\n")
    lines.append(
        f"\n**{data['broad_and_live_count']}** findings are approved by a broad "
        "path/extension-only rule (no content ever inspected) in a file that still "
        "exists — the same rule would silently approve a genuinely new secret added "
        "tomorrow in the same path.\n"
    )
    if data["high_confidence_shape_files_count"]:
        lines.append(
            f"\n### ⚠️ {data['high_confidence_shape_files_count']} broad-approved "
            "file(s) match a vendor-specific high-confidence credential shape "
            "(GOCSPX- / 1// / AKIA / gh_ / xox- / sk_live_) — never printed here, only "
            "the shape name:\n"
        )
        for f, shapes in data["high_confidence_shape_files"].items():
            lines.append(f"  - `{f}` ({', '.join(shapes)})\n")
    lines.append(f"\n## Staleness\n{data['stale_files_count']} baseline entries reference files no longer on HEAD.\n")
    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any broad-approved, still-live file matches a high-confidence credential shape",
    )
    args = ap.parse_args()

    data = analyze()

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(render_markdown(data), end="")

    if args.strict and data["high_confidence_shape_files_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
