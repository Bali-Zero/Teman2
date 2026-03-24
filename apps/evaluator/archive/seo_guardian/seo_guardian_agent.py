"""
SEO Guardian Agent — DECIDE + ACT
===================================
Reads OBSERVE output (state.json), applies corrections, classifies
actions by risk level, executes LOW risk autonomously, logs everything.

Usage:
    python seo_guardian_agent.py                    # full run
    python seo_guardian_agent.py --dry-run          # log actions, don't execute
    python seo_guardian_agent.py --observe-first    # run observe, then decide+act
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Agent] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENT_DIR = Path.home() / ".openclaw" / "workspace" / "autonomous" / "seo-guardian"
CONFIG_PATH = AGENT_DIR / "config.yaml"
STATE_PATH = AGENT_DIR / "state.json"
PATTERNS_PATH = AGENT_DIR / "patterns.json"
CORRECTIONS_PATH = AGENT_DIR / "corrections.jsonl"
MEMORY_PATH = AGENT_DIR / "memory.jsonl"
DECISIONS_LOG = AGENT_DIR / "decisions.log"


def load_json(path: Path) -> Any:
    if not path.exists():
        return {} if path.suffix == ".json" else []
    with open(path) as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def append_jsonl(path: Path, entry: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_decision(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(DECISIONS_LOG, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    logger.info(message)


def check_paused() -> bool:
    state = load_json(STATE_PATH)
    return state.get("paused", False)


def check_corrections(action_type: str, scope: str) -> str | None:
    """Check if any correction rule blocks this action. Returns reason or None."""
    corrections = load_jsonl(CORRECTIONS_PATH)
    for rule in corrections:
        rule_type = rule.get("rule", "")
        rule_scope = rule.get("scope", "")

        if rule_type == "never_touch":
            # Glob-style scope check (simple prefix match with wildcard)
            if rule_scope.endswith("/*"):
                prefix = rule_scope[:-2]
                if scope.startswith(prefix):
                    return f"Blocked by correction: {rule_type} on {rule_scope} — {rule.get('reason', '')}"
            elif scope == rule_scope:
                return f"Blocked by correction: {rule_type} on {rule_scope} — {rule.get('reason', '')}"

        if rule_type == "max_indexing_batch" and action_type == "submit_indexing_batch":
            # This is handled in the action execution, not blocking
            pass

        if rule_type == "no_content_edit" and action_type in ("edit_article_body", "update_meta_description"):
            if rule_scope.endswith("/*"):
                prefix = rule_scope[:-2]
                if scope.startswith(prefix):
                    return f"Blocked by correction: {rule_type} on {rule_scope} — {rule.get('reason', '')}"

    return None


def get_max_indexing_batch() -> int:
    """Get max indexing batch size from corrections (default 50)."""
    corrections = load_jsonl(CORRECTIONS_PATH)
    for rule in corrections:
        if rule.get("rule") == "max_indexing_batch":
            return rule.get("value", 50)
    return 50


def classify_risk(action_type: str) -> str:
    """Classify action risk level from config.yaml."""
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    risk_levels = config.get("decide", {}).get("risk_levels", {})
    for level, actions in risk_levels.items():
        if action_type in actions:
            return level
    return "HIGH"  # Unknown actions default to HIGH (safest)


def execute_indexing_batch(batch_size: int, dry_run: bool = False) -> dict:
    """Execute KBLI indexing batch submission."""
    script = PROJECT_ROOT / "apps" / "evaluator" / "kbli_indexing_submit.py"
    cmd = [sys.executable, str(script), "--batch", str(batch_size)]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=str(PROJECT_ROOT))
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def run_observe() -> dict:
    """Run the OBSERVE phase using seo_guardian_core.py."""
    script = PROJECT_ROOT / "apps" / "evaluator" / "seo_guardian_core.py"
    output_path = AGENT_DIR / "last_observe.json"

    try:
        import os
        env = os.environ.copy()
        env["GA4_PROPERTY_ID"] = "505466833"
        result = subprocess.run(
            [sys.executable, str(script), "--mode", "report", "--output", str(output_path)],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT), env=env,
        )
        if result.returncode == 0 and output_path.exists():
            with open(output_path) as f:
                return json.load(f)
        logger.error("Observe failed: %s", result.stderr[-300:] if result.stderr else "no output")
        return {}
    except Exception as e:
        logger.error("Observe error: %s", e)
        return {}


async def run_agent(dry_run: bool = False, observe_first: bool = False) -> dict:
    """Main agent loop: OBSERVE (optional) → DECIDE → ACT → LOG."""

    # Kill switch check
    if check_paused():
        log_decision("PAUSED: Agent is paused via state.json. Exiting.")
        return {"status": "paused"}

    # OBSERVE (optional — can also be run as separate cron job)
    observe_data = {}
    if observe_first:
        log_decision("OBSERVE: Running seo_guardian_core.py --mode report")
        observe_data = await run_observe()
        if not observe_data:
            log_decision("OBSERVE: Failed to get data. Aborting run.")
            return {"status": "observe_failed"}

        # Update state.json with observe timestamp
        state = load_json(STATE_PATH)
        state["last_observe_run"] = datetime.now().isoformat()
        state["current_metrics"] = {
            "total_queries": observe_data.get("seo_plan", {}).get("gsc_summary", {}).get("total_queries", 0),
            "critical_gaps": len(observe_data.get("seo_plan", {}).get("critical_gaps", [])),
            "indexing_submitted": observe_data.get("indexing_state", {}).get("total_submitted", 0),
        }
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
    else:
        # Load last observe output
        last_observe = AGENT_DIR / "last_observe.json"
        if last_observe.exists():
            with open(last_observe) as f:
                observe_data = json.load(f)

    # DECIDE: Build action plan from opportunities
    opportunities = observe_data.get("opportunities", [])
    actions_taken = []
    actions_blocked = []
    actions_skipped = []

    log_decision(f"DECIDE: {len(opportunities)} opportunities found")

    low_count = 0
    medium_count = 0
    max_low = 10
    max_medium = 3

    for opp in opportunities:
        action_type = opp.get("suggested_action", "unknown")
        risk = classify_risk(action_type)
        scope = opp.get("query", opp.get("type", ""))

        # Check corrections
        block_reason = check_corrections(action_type, scope)
        if block_reason:
            actions_blocked.append({"action": action_type, "reason": block_reason})
            log_decision(f"  BLOCKED: {action_type} — {block_reason}")
            continue

        # Check limits
        if risk == "LOW" and low_count >= max_low:
            actions_skipped.append({"action": action_type, "reason": "max LOW actions reached"})
            continue
        if risk == "MEDIUM" and medium_count >= max_medium:
            actions_skipped.append({"action": action_type, "reason": "max MEDIUM actions reached"})
            continue
        if risk == "HIGH":
            actions_skipped.append({"action": action_type, "reason": "HIGH risk — requires approval"})
            log_decision(f"  SKIPPED: {action_type} — HIGH risk, requires approval")
            continue

        # ACT
        if risk == "LOW":
            log_decision(f"  ACT [LOW]: {action_type}")

            if action_type == "submit_indexing_batch":
                batch_size = min(opp.get("batch_size", 50), get_max_indexing_batch())
                result = execute_indexing_batch(batch_size, dry_run=dry_run)
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "action": action_type,
                    "risk": "LOW",
                    "params": {"batch_size": batch_size},
                    "dry_run": dry_run,
                    "result": result,
                    "git_sha": None,
                    "measured": False,
                }
                append_jsonl(MEMORY_PATH, entry)
                actions_taken.append(entry)
                low_count += 1

            elif action_type == "report_anomaly":
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "report_anomaly",
                    "risk": "LOW",
                    "params": {"query": opp.get("query"), "ctr": opp.get("current_ctr"), "position": opp.get("current_position")},
                    "dry_run": dry_run,
                    "result": {"success": True, "type": "report_only"},
                    "git_sha": None,
                    "measured": False,
                }
                append_jsonl(MEMORY_PATH, entry)
                actions_taken.append(entry)
                low_count += 1

            elif action_type == "update_meta_description":
                # For now, log as report — actual meta editing requires git ops
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "update_meta_description",
                    "risk": "LOW",
                    "params": {"query": opp.get("query"), "impressions": opp.get("impressions")},
                    "dry_run": True,  # Always dry-run for v1.0 until proven safe
                    "result": {"success": True, "type": "logged_for_review"},
                    "git_sha": None,  # Will contain SHA when actual git commits are made
                    "measured": False,
                }
                append_jsonl(MEMORY_PATH, entry)
                actions_taken.append(entry)
                low_count += 1

            elif action_type == "add_citation_guard":
                # Citation guard is fixed by running the generator
                action_type = "generate_ai_ingestion_files"

            if action_type == "generate_ai_ingestion_files":
                log_decision(f"  ACT [LOW]: Running AI Ingestion Generator...")
                mouth_dir = PROJECT_ROOT / "apps" / "mouth"
                # Use npx tsx to run the script
                cmd = ["npx", "tsx", "scripts/generate-llms-full.ts"]
                
                if dry_run:
                    result = {"success": True, "dry_run": True}
                else:
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(mouth_dir), timeout=120)
                        result = {
                            "success": res.returncode == 0,
                            "stdout": res.stdout[-500:],
                            "stderr": res.stderr[-500:]
                        }
                    except Exception as e:
                        result = {"success": False, "error": str(e)}

                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "generate_ai_ingestion_files",
                    "risk": "LOW",
                    "params": {},
                    "dry_run": dry_run,
                    "result": result,
                    "git_sha": None,
                    "measured": False,
                }
                append_jsonl(MEMORY_PATH, entry)
                actions_taken.append(entry)
                low_count += 1

        elif risk == "MEDIUM":
            # MEDIUM: log for Telegram confirmation
            entry = {
                "timestamp": datetime.now().isoformat(),
                "action": action_type,
                "risk": "MEDIUM",
                "params": opp,
                "dry_run": True,
                "result": {"success": True, "type": "pending_confirmation"},
                "git_sha": None,
                "measured": False,
            }
            append_jsonl(MEMORY_PATH, entry)
            actions_taken.append(entry)
            medium_count += 1
            log_decision(f"  PENDING [MEDIUM]: {action_type} — logged for Telegram confirmation")

    # Summary
    summary = {
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "actions_taken": len(actions_taken),
        "actions_blocked": len(actions_blocked),
        "actions_skipped": len(actions_skipped),
        "details": {
            "taken": actions_taken,
            "blocked": actions_blocked,
            "skipped": actions_skipped,
        },
    }

    log_decision(
        f"SUMMARY: {len(actions_taken)} taken, {len(actions_blocked)} blocked, "
        f"{len(actions_skipped)} skipped (dry_run={dry_run})"
    )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Guardian Agent — DECIDE + ACT")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without executing")
    parser.add_argument("--observe-first", action="store_true", help="Run OBSERVE before DECIDE+ACT")
    args = parser.parse_args()

    result = asyncio.run(run_agent(dry_run=args.dry_run, observe_first=args.observe_first))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
