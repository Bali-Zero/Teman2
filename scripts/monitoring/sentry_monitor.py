#!/usr/bin/env python3
"""
Sentry Error Monitor for Nuzantara
===================================
Monitors Sentry for new errors and prepares them for Claude Code auto-fix.

Usage:
    python scripts/sentry_monitor.py              # Check for new errors
    python scripts/sentry_monitor.py --watch      # Continuous monitoring (every 5 min)
    python scripts/sentry_monitor.py --fix        # Check and trigger Claude Code fix

Environment:
    SENTRY_AUTH_TOKEN: Sentry API token
    SENTRY_ORG: bali-zero-7p
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Configuration
SENTRY_ORG = "bali-zero-7p"
SENTRY_PROJECTS = ["nuzantara-backend", "nuzantara-frontend"]
SENTRY_API_BASE = "https://us.sentry.io/api/0"
SENTRY_AUTH_TOKEN = os.getenv(
    "SENTRY_AUTH_TOKEN",
    os.getenv(
        "SENTRY_NUZANTARA_SUPERTOKEN",
        "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",
    ),
)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
ERRORS_FILE = PROJECT_ROOT / "data" / "sentry_errors.json"
REPORT_FILE = PROJECT_ROOT / "data" / "sentry_report.md"


def get_headers() -> dict:
    """Get API headers."""
    return {
        "Authorization": f"Bearer {SENTRY_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }


def fetch_unresolved_issues(project: str) -> list[dict]:
    """Fetch unresolved issues from Sentry."""
    url = f"{SENTRY_API_BASE}/projects/{SENTRY_ORG}/{project}/issues/"
    params = {"query": "is:unresolved", "limit": 25}

    try:
        response = requests.get(url, headers=get_headers(), params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(
                f"[WARN] Failed to fetch issues for {project}: {response.status_code}"
            )
            return []
    except Exception as e:
        print(f"[ERROR] Exception fetching issues: {e}")
        return []


def fetch_issue_details(issue_id: str) -> dict | None:
    """Fetch detailed information about an issue including latest event."""
    url = f"{SENTRY_API_BASE}/issues/{issue_id}/events/latest/"

    try:
        response = requests.get(url, headers=get_headers(), timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def parse_stack_trace(event: dict) -> list[dict]:
    """Extract relevant stack trace frames from event."""
    frames = []

    try:
        exception = event.get("entries", [])
        for entry in exception:
            if entry.get("type") == "exception":
                values = entry.get("data", {}).get("values", [])
                for value in values:
                    stacktrace = value.get("stacktrace", {})
                    for frame in stacktrace.get("frames", []):
                        # Only include frames from our codebase
                        filename = frame.get("filename", "")
                        if (
                            "nuzantara" in filename
                            or "backend" in filename
                            or "mouth" in filename
                        ):
                            frames.append(
                                {
                                    "filename": filename,
                                    "function": frame.get("function"),
                                    "lineno": frame.get("lineNo"),
                                    "context_line": frame.get("contextLine"),
                                    "pre_context": frame.get("preContext", []),
                                    "post_context": frame.get("postContext", []),
                                }
                            )
    except Exception as e:
        print(f"[WARN] Error parsing stack trace: {e}")

    return frames


def map_to_local_file(filename: str) -> Path | None:
    """Map Sentry filename to local file path."""
    # Common mappings
    mappings = [
        ("backend/app/", PROJECT_ROOT / "apps/backend-rag/backend/app/"),
        ("backend/services/", PROJECT_ROOT / "apps/backend-rag/backend/services/"),
        ("backend/llm/", PROJECT_ROOT / "apps/backend-rag/backend/llm/"),
        ("app/", PROJECT_ROOT / "apps/mouth/src/app/"),
        ("components/", PROJECT_ROOT / "apps/mouth/src/components/"),
        ("lib/", PROJECT_ROOT / "apps/mouth/src/lib/"),
    ]

    for prefix, local_path in mappings:
        if prefix in filename:
            idx = filename.find(prefix)
            relative = filename[idx + len(prefix) :]
            full_path = local_path / relative
            if full_path.exists():
                return full_path

    return None


def generate_report(all_issues: list[dict]) -> str:
    """Generate markdown report of errors."""
    lines = [
        "# Sentry Error Report",
        f"Generated: {datetime.now().isoformat()}",
        f"Total unresolved issues: {len(all_issues)}",
        "",
        "---",
        "",
    ]

    for issue in all_issues:
        issue_id = issue.get("id")
        title = issue.get("title", "Unknown")
        culprit = issue.get("culprit", "Unknown")
        count = issue.get("count", 0)
        first_seen = issue.get("firstSeen", "")
        last_seen = issue.get("lastSeen", "")
        project = issue.get("project", {}).get("slug", "unknown")

        lines.extend(
            [
                f"## [{issue_id}] {title}",
                "",
                f"- **Project**: {project}",
                f"- **Culprit**: `{culprit}`",
                f"- **Occurrences**: {count}",
                f"- **First seen**: {first_seen}",
                f"- **Last seen**: {last_seen}",
                "",
            ]
        )

        # Fetch details
        details = fetch_issue_details(issue_id)
        if details:
            frames = parse_stack_trace(details)
            if frames:
                lines.append("### Stack Trace (relevant frames)")
                lines.append("```")
                for frame in frames[-5:]:  # Last 5 frames
                    local_file = map_to_local_file(frame["filename"] or "")
                    lines.append(f"File: {frame['filename']}:{frame['lineno']}")
                    if local_file:
                        lines.append(f"Local: {local_file}")
                    lines.append(f"Function: {frame['function']}")
                    if frame["context_line"]:
                        lines.append(f">>> {frame['context_line']}")
                    lines.append("")
                lines.append("```")

        lines.extend(["", "---", ""])

    return "\n".join(lines)


def save_errors(issues: list[dict]) -> None:
    """Save errors to JSON file."""
    ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ERRORS_FILE, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "count": len(issues),
                "issues": issues,
            },
            f,
            indent=2,
        )


def trigger_claude_fix() -> None:
    """Trigger Claude Code to fix errors."""
    print("[INFO] Triggering Claude Code for auto-fix...")
    print(
        f"""
To fix these errors with Claude Code:

1. Open terminal in project directory:
   cd {PROJECT_ROOT}

2. Run Claude Code with the sentry-fix command:
   claude /sentry-fix

3. Or manually:
   claude "Read {REPORT_FILE} and fix the errors listed"
"""
    )


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sentry Error Monitor")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring")
    parser.add_argument("--fix", action="store_true", help="Trigger Claude Code fix")
    parser.add_argument(
        "--interval", type=int, default=300, help="Watch interval in seconds"
    )
    args = parser.parse_args()

    def check_once():
        print(f"[{datetime.now().isoformat()}] Checking Sentry for errors...")

        all_issues = []
        for project in SENTRY_PROJECTS:
            print(f"  Checking {project}...")
            issues = fetch_unresolved_issues(project)
            for issue in issues:
                issue["project"] = {"slug": project}
            all_issues.extend(issues)

        if all_issues:
            print(f"[INFO] Found {len(all_issues)} unresolved issues")
            save_errors(all_issues)

            report = generate_report(all_issues)
            REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(REPORT_FILE, "w") as f:
                f.write(report)
            print(f"[INFO] Report saved to {REPORT_FILE}")

            if args.fix:
                trigger_claude_fix()
        else:
            print("[INFO] No unresolved issues found!")

        return all_issues

    if args.watch:
        print(f"[INFO] Starting continuous monitoring (interval: {args.interval}s)")
        while True:
            try:
                check_once()
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n[INFO] Stopping monitor...")
                break
    else:
        issues = check_once()
        return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
