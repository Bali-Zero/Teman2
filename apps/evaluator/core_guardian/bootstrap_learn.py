"""
Core Guardian V5.5 — Bootstrap Historical Data into guardian_decisions

Hydrates the guardian_decisions table from three historical sources:

1. MOS SQLite (248+ memories): decisions, discoveries, facts → decision records
2. Cicatrix Scars (20 patterns): repeated bug patterns → high-severity records
3. Git log (30 days): commit messages mentioning fix/bug → lightweight records

This gives learn.py months of history to work with instead of starting cold.

Run once, idempotent (uses run_id prefix 'bootstrap-' to avoid duplicates).

Usage:
    python bootstrap_learn.py                    # full bootstrap
    python bootstrap_learn.py --dry-run          # preview without inserting
    python bootstrap_learn.py --source mos       # only MOS
    python bootstrap_learn.py --source cicatrix  # only cicatrix
    python bootstrap_learn.py --source git       # only git
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[Bootstrap %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bootstrap")

_GUARDIAN_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _GUARDIAN_DIR.parent.parent.parent
_CICATRIX_FILE = _PROJECT_ROOT / ".claude" / "rules" / "cicatrix-scars.md"
_MOS_DB_CMD = Path.home() / ".claude" / "scripts" / "mos-db"

BOOTSTRAP_RUN_ID = "bootstrap-mos-v1"


# ============================================================================
# Source 1: MOS SQLite Memories
# ============================================================================


def _query_mos(sql: str) -> str:
    """Query MOS SQLite via mos-db script (handles Pro/Air routing)."""
    try:
        result = subprocess.run(
            [str(_MOS_DB_CMD), "-csv", sql],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"MOS query failed: {e}")
        return ""


def extract_from_mos() -> list[dict]:
    """Extract decision records from MOS memories."""
    raw = _query_mos(
        "SELECT id, type, content, importance, created_at, tags "
        "FROM memories WHERE importance >= 6 ORDER BY created_at"
    )
    if not raw:
        logger.warning("No MOS data retrieved")
        return []

    records = []
    for line in raw.splitlines():
        if line.startswith("id,"):  # Skip header
            continue

        # Parse CSV — content can contain commas so we need careful parsing
        parts = _parse_csv_line(line)
        if len(parts) < 5:
            continue

        mem_id, mem_type, content, importance, created_at = parts[:5]
        tags = parts[5] if len(parts) > 5 else ""

        # Map MOS type → guardian severity
        severity_map = {
            "decision": "info",
            "discovery": "warning",
            "fact": "info",
            "unresolved": "warning",
            "pattern": "info",
        }

        # Map MOS type → guardian check_type
        check_type = _classify_content(content)

        # Extract action from content
        action = _extract_action(content, mem_type)

        records.append({
            "run_id": f"{BOOTSTRAP_RUN_ID}-mos-{mem_id}",
            "component": "bootstrap_mos",
            "check_type": check_type,
            "finding": content[:500],  # Cap at 500 chars for DB
            "severity": severity_map.get(mem_type, "info"),
            "action_taken": action,
            "rationale": f"Bootstrapped from MOS memory #{mem_id} (type={mem_type}, importance={importance})",
            "risk_score": _importance_to_risk(int(importance) if importance.isdigit() else 5),
            "timestamp": created_at,
            "metadata": json.dumps({
                "source": "mos",
                "mos_id": mem_id,
                "mos_type": mem_type,
                "importance": importance,
                "tags": tags,
            }),
        })

    logger.info(f"Extracted {len(records)} records from MOS")
    return records


def _parse_csv_line(line: str) -> list[str]:
    """Parse a CSV line using stdlib csv.reader (RFC 4180 compliant)."""
    import csv
    import io
    try:
        reader = csv.reader(io.StringIO(line))
        return next(reader)
    except (csv.Error, StopIteration):
        # Fallback: naive split
        return line.split(",")


def _classify_content(content: str) -> str:
    """Classify MOS content into a guardian check_type."""
    content_lower = content.lower()

    classifications = [
        ("rbac", ["rbac", "auth", "permission", "401", "unauthorized", "jwt", "token"]),
        ("deploy", ["deploy", "fly.io", "vercel", "production", "hotfix"]),
        ("crash", ["crash", "500", "error", "broken", "fail", "timeout", "down"]),
        ("security", ["secret", "credential", "vuln", "xss", "injection", "security"]),
        ("rag_pipeline", ["rag", "embedding", "vector", "qdrant", "search", "rerank"]),
        ("kg_quality", ["graph", "kg ", "node", "edge", "entity", "knowledge graph"]),
        ("crm", ["crm", "client", "practice", "invoice", "portal"]),
        ("cache", ["cache", "invalidat", "redis"]),
        ("migration", ["migration", "alembic", "schema", "table"]),
        ("test_quality", ["test", "pytest", "coverage", "regression"]),
        ("infra", ["cron", "backup", "drive", "ollama", "docker", "launchd"]),
        ("frontend", ["next.js", "vercel", "component", "tailwind", "css", "kbli"]),
        ("hr", ["hr ", "payroll", "leave", "bonus", "team_member"]),
        ("api_contract", ["endpoint", "router", "api ", "route"]),
    ]

    for check_type, keywords in classifications:
        if any(kw in content_lower for kw in keywords):
            return check_type

    return "general"


def _extract_action(content: str, mem_type: str) -> str:
    """Extract the action taken from memory content."""
    content_lower = content.lower()

    if mem_type == "unresolved":
        return "pending"
    if any(w in content_lower for w in ["deployed", "deploy", "merged", "live"]):
        return "fix_deployed"
    if any(w in content_lower for w in ["fix", "fixed", "risolto", "resolved"]):
        return "fix_applied"
    if any(w in content_lower for w in ["found", "trovato", "discovered", "bug"]):
        return "issue_detected"
    if any(w in content_lower for w in ["completato", "completed", "done", "implementato"]):
        return "task_completed"
    if any(w in content_lower for w in ["plan", "design", "progett"]):
        return "plan_created"
    return "logged"


def _importance_to_risk(importance: int) -> int:
    """Map MOS importance (1-10) to approximate risk score (0-100)."""
    # importance 10 → risk 80 (critical decisions)
    # importance 7 → risk 50 (standard)
    # importance 5 → risk 30 (low)
    return min(100, max(0, (importance - 3) * 12))


# ============================================================================
# Source 2: Cicatrix Scars
# ============================================================================


def extract_from_cicatrix() -> list[dict]:
    """Extract decision records from cicatrix-scars.md."""
    if not _CICATRIX_FILE.exists():
        logger.warning(f"Cicatrix file not found: {_CICATRIX_FILE}")
        return []

    content = _CICATRIX_FILE.read_text()
    records = []

    # Parse scar blocks: ### ... SCAR: <file>\n_Recurrence: N observations_\n```markdown\n...\n```
    scar_pattern = re.compile(
        r'### [^\n]*SCAR:\s*(.+?)\n'
        r'_Recurrence:\s*(\d+)\s*observations_\s*\n'
        r'\s*```\s*markdown\s*\n(.*?)```',
        re.DOTALL,
    )

    for match in scar_pattern.finditer(content):
        file_path = match.group(1).strip()
        recurrence = int(match.group(2))
        body = match.group(3).strip()

        # Extract TRAUMA line
        trauma_match = re.search(r'(?:\*\*)?TRAUMA(?:\*\*)?:?\s*(.+?)(?:\n|$)', body)
        trauma = trauma_match.group(1).strip() if trauma_match else body[:200]

        # Extract ANTIBODY line
        antibody_match = re.search(r'(?:\*\*)?ANTIBODY(?:\*\*)?:?\s*(.+?)(?:\n|$)', body)
        antibody = antibody_match.group(1).strip() if antibody_match else ""

        # Severity based on recurrence
        if recurrence >= 10:
            severity = "error"
        elif recurrence >= 6:
            severity = "warning"
        else:
            severity = "info"

        records.append({
            "run_id": f"{BOOTSTRAP_RUN_ID}-cicatrix",
            "component": "bootstrap_cicatrix",
            "check_type": "cicatrix_scar",
            "finding": f"[{file_path}] (recurrence={recurrence}) {trauma}",
            "severity": severity,
            "action_taken": "scar_recorded",
            "rationale": antibody[:300] if antibody else None,
            "risk_score": min(100, recurrence * 8),  # 5 obs → 40, 12 obs → 96
            "timestamp": "2026-03-16T01:25:00+00:00",  # Cicatrix generation date
            "metadata": json.dumps({
                "source": "cicatrix",
                "file": file_path,
                "recurrence": recurrence,
                "has_antibody": bool(antibody),
            }),
        })

    logger.info(f"Extracted {len(records)} records from cicatrix ({len(records)} scars)")
    return records


# ============================================================================
# Source 3: Git History
# ============================================================================


def extract_from_git() -> list[dict]:
    """Extract fix/bug commit messages from git log (30 days)."""
    try:
        result = subprocess.run(
            [
                "git", "log",
                "--since=30 days ago",
                "--format=%H|%aI|%s",
                "--", "apps/backend-rag/",
            ],
            cwd=str(_PROJECT_ROOT),
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        logger.error(f"Git log failed: {e}")
        return []

    records = []
    # Only include commits that mention fix/bug/hotfix/revert
    fix_pattern = re.compile(r'\b(fix|bug|hotfix|revert|broken|crash|regression)\b', re.IGNORECASE)

    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue

        commit_hash, timestamp, subject = parts

        if not fix_pattern.search(subject):
            continue

        # Extract affected files from commit
        files_result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            cwd=str(_PROJECT_ROOT),
            capture_output=True, text=True, timeout=10,
        )
        files = [
            f.split("apps/backend-rag/")[1]
            for f in files_result.stdout.strip().splitlines()
            if "apps/backend-rag/" in f and f.endswith(".py")
        ]

        records.append({
            "run_id": f"{BOOTSTRAP_RUN_ID}-git",
            "component": "bootstrap_git",
            "check_type": _classify_commit(subject),
            "finding": f"[{commit_hash[:8]}] {subject}" + (f" ({len(files)} files)" if files else ""),
            "severity": "warning" if "revert" in subject.lower() else "info",
            "action_taken": "fix_committed",
            "rationale": None,
            "risk_score": 40 if "revert" in subject.lower() else 20,
            "timestamp": timestamp,
            "metadata": json.dumps({
                "source": "git",
                "commit": commit_hash[:12],
                "files": files[:10],
            }),
        })

    logger.info(f"Extracted {len(records)} fix/bug commits from git log")
    return records


def _classify_commit(subject: str) -> str:
    """Classify a commit subject into a check_type."""
    s = subject.lower()
    if any(w in s for w in ["auth", "rbac", "jwt", "permission"]):
        return "rbac"
    if any(w in s for w in ["rag", "search", "embedding"]):
        return "rag_pipeline"
    if any(w in s for w in ["crm", "client", "practice"]):
        return "crm"
    if any(w in s for w in ["cache", "redis"]):
        return "cache"
    if any(w in s for w in ["deploy", "fly"]):
        return "deploy"
    if any(w in s for w in ["lint", "ruff", "type"]):
        return "code_quality"
    if any(w in s for w in ["hr", "leave", "payroll"]):
        return "hr"
    return "general_fix"


# ============================================================================
# Insert into PostgreSQL
# ============================================================================


async def insert_records(records: list[dict], dry_run: bool = False) -> int:
    """Insert bootstrap records into guardian_decisions via asyncpg."""
    if dry_run:
        logger.info(f"DRY RUN: Would insert {len(records)} records")
        return len(records)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set — cannot insert records")
        return 0

    import asyncpg
    try:
        conn = await asyncpg.connect(db_url, timeout=15)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return 0

    try:
        # Check if bootstrap already ran (idempotent)
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM guardian_decisions WHERE run_id LIKE 'bootstrap-%'"
        )
        if existing > 0:
            logger.warning(f"Bootstrap already ran ({existing} existing records). Use --force to re-run.")
            if "--force" not in sys.argv:
                return 0
            # Delete existing bootstrap records
            await conn.execute("DELETE FROM guardian_decisions WHERE run_id LIKE 'bootstrap-%'")
            logger.info(f"Deleted {existing} existing bootstrap records")

        # Batch insert
        inserted = 0
        for r in records:
            try:
                # Parse timestamp string to datetime for asyncpg
                ts = r["timestamp"]
                if isinstance(ts, str):
                    from datetime import datetime as _dt
                    try:
                        ts = _dt.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        try:
                            ts = _dt.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(
                                tzinfo=timezone.utc
                            )
                        except ValueError:
                            logger.warning(f"Unparseable timestamp '{ts}', using now()")
                            ts = _dt.now(timezone.utc)

                await conn.execute(
                    """
                    INSERT INTO guardian_decisions
                        (run_id, timestamp, component, check_type, finding, severity,
                         action_taken, rationale, rollback_plan, risk_score, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULL, $9, $10::jsonb)
                    """,
                    r["run_id"],
                    ts,
                    r["component"],
                    r["check_type"],
                    r["finding"],
                    r["severity"],
                    r["action_taken"],
                    r.get("rationale"),
                    r.get("risk_score"),
                    r.get("metadata", "{}"),
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert record: {e}")

        logger.info(f"Inserted {inserted}/{len(records)} records into guardian_decisions")
        return inserted

    finally:
        await conn.close()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    import asyncio

    dry_run = "--dry-run" in sys.argv
    source_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i + 1 < len(sys.argv):
            source_filter = sys.argv[i + 1]

    all_records: list[dict] = []

    # Source 1: MOS
    if source_filter is None or source_filter == "mos":
        logger.info("=== Extracting from MOS SQLite ===")
        mos_records = extract_from_mos()
        all_records.extend(mos_records)

    # Source 2: Cicatrix
    if source_filter is None or source_filter == "cicatrix":
        logger.info("=== Extracting from Cicatrix Scars ===")
        cicatrix_records = extract_from_cicatrix()
        all_records.extend(cicatrix_records)

    # Source 3: Git
    if source_filter is None or source_filter == "git":
        logger.info("=== Extracting from Git History ===")
        git_records = extract_from_git()
        all_records.extend(git_records)

    logger.info(f"=== Total: {len(all_records)} records ===")

    if not all_records:
        logger.info("No records to insert")
        return

    # Preview
    by_source = {}
    for r in all_records:
        src = r["component"]
        by_source[src] = by_source.get(src, 0) + 1
    for src, count in sorted(by_source.items()):
        logger.info(f"  {src}: {count} records")

    by_check = {}
    for r in all_records:
        ct = r["check_type"]
        by_check[ct] = by_check.get(ct, 0) + 1
    for ct, count in sorted(by_check.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"  check_type={ct}: {count}")

    # Insert
    inserted = asyncio.run(insert_records(all_records, dry_run=dry_run))

    if dry_run:
        print(json.dumps({
            "status": "dry_run",
            "total_records": len(all_records),
            "by_source": by_source,
            "by_check_type": dict(sorted(by_check.items(), key=lambda x: -x[1])[:15]),
            "sample": all_records[:3],
        }, indent=2, default=str))
    else:
        print(json.dumps({
            "status": "ok",
            "inserted": inserted,
            "total_records": len(all_records),
            "by_source": by_source,
        }, indent=2))


if __name__ == "__main__":
    main()
