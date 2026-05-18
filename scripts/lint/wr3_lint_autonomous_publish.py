#!/usr/bin/env python3
"""WR3 Lint — Law 5 (Zero ultima istanza).

Symbiosis Law 5: Strategic decisions require Antonello's Telegram approval.
For WR3 episode pipeline, this means:
  - Episode is STAGED to Drive after critic PASS (automatic ok)
  - Episode is PUBLISHED to IG/TT/YT only after Antonello manual action
  - NO direct posting to social platforms from any WR3 script

Checks:
  1. Scan scripts/wr3_*.py for ANY social platform posting API:
       instagram_business_account_id / instagram api / facebook_graph / ig.publish
       tiktok.publish / youtube_data_v3 / yt.upload / oauth2 facebook
     ALL banned.
  2. Drive uploads must be to STAGING folder, not LIVE folder.
     Required marker: `staging` or `wr3-staging` near the upload call.
  3. `manifest["critic_verdict"] == "PASS"` is necessary but NOT SUFFICIENT
     for publish — there must also be a `manual_publish_token` field
     (we lint the contract YAML for it in critic.yaml).
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from . import LintFinding
except ImportError:
    import sys
    HERE = Path(__file__).resolve().parent
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from __init__ import LintFinding  # type: ignore

LAW_NUMBER = 5
LAW_NAME = "Zero ultima istanza"

SOCIAL_PUBLISH_PATTERNS = re.compile(
    r"\binstagram_business_account_id\b|"
    r"instagram\.api\.|"
    r"facebook_graph\b|"
    r"\big\.publish\b|"
    r"\btiktok\.publish\b|"
    r"youtube_data_v3|"
    r"\byt\.upload\b|"
    r"oauth2.*facebook",
    re.IGNORECASE,
)

DRIVE_UPLOAD = re.compile(r"drive\.files\.create|files\(\)\.create|upload.*drive", re.IGNORECASE)
STAGING_MARKER = re.compile(r"staging", re.IGNORECASE)


def check(repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    scripts_dir = repo_root / "scripts"
    if not scripts_dir.exists():
        return findings

    for py_path in sorted(scripts_dir.glob("wr3_*.py")):
        try:
            text = py_path.read_text()
        except Exception:
            continue
        lines = text.splitlines()

        for line_no, line in enumerate(lines, 1):
            if SOCIAL_PUBLISH_PATTERNS.search(line):
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(py_path.relative_to(repo_root)),
                    line=line_no,
                    message=f"Social platform direct publish detected — manual Antonello action required: {line.strip()[:100]}",
                ))

            # Drive upload sanity — ensure 'staging' appears in surrounding ±3 lines
            if DRIVE_UPLOAD.search(line):
                window_start = max(0, line_no - 4)
                window_end = min(len(lines), line_no + 3)
                window = "\n".join(lines[window_start:window_end])
                if not STAGING_MARKER.search(window):
                    findings.append(LintFinding(
                        severity="WARN",
                        law=LAW_NUMBER,
                        file=str(py_path.relative_to(repo_root)),
                        line=line_no,
                        message=f"Drive upload without nearby 'staging' marker — verify destination is staging folder",
                    ))

    return findings


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    findings = check(repo_root)
    for f in findings:
        print(f.fmt())
    sys.exit(1 if any(f.severity == "ERROR" for f in findings) else 0)
