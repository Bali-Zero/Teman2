# SEO Guardian Agent Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first autonomous self-growing agent (SEO Guardian) that observes GSC/GA4 data, takes low-risk SEO actions autonomously, measures impact, and learns from results + human corrections.

**Architecture:** OpenClaw cron jobs drive the agent cycle (OBSERVE→DECIDE→ACT→MEASURE→LEARN). State is file-based in `~/.openclaw/workspace/autonomous/seo-guardian/`. The existing `seo_guardian_core.py` is refactored to produce structured JSON output. A new `seo_guardian_agent.py` orchestrates the full cycle. MCP tools are called by Claude inside cron prompts (not via shell CLI).

**Tech Stack:** Python 3.11, Google APIs (GSC, GA4, Indexing), OpenClaw cron, JSONL for memory, Telegram for delivery.

**Spec:** `docs/superpowers/specs/2026-03-14-autonomous-agents-design.md`

---

## Chunk 1: Infrastructure + OBSERVE Refactor

### File Structure

| File                                                              | Action | Purpose                                             |
| ----------------------------------------------------------------- | ------ | --------------------------------------------------- |
| `~/.openclaw/workspace/autonomous/seo-guardian/config.yaml`       | Create | Agent identity, data sources, risk levels, schedule |
| `~/.openclaw/workspace/autonomous/seo-guardian/state.json`        | Create | Runtime state (last run, metrics baseline)          |
| `~/.openclaw/workspace/autonomous/seo-guardian/patterns.json`     | Create | Learned rules (empty initially)                     |
| `~/.openclaw/workspace/autonomous/seo-guardian/corrections.jsonl` | Create | Human override rules                                |
| `~/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl`      | Create | Append-only action log (empty initially)            |
| `~/.openclaw/workspace/autonomous/seo-guardian/decisions.log`     | Create | Human-readable decision log (empty initially)       |
| `apps/evaluator/seo_guardian_core.py`                             | Modify | Add argparse CLI + `--mode report` for JSON output  |

### Task 1: Create Agent Workspace Directory

**Files:**

- Create: `~/.openclaw/workspace/autonomous/seo-guardian/` (directory)

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p ~/.openclaw/workspace/autonomous/seo-guardian
```

- [ ] **Step 2: Verify directory exists**

```bash
ls -la ~/.openclaw/workspace/autonomous/seo-guardian/
```

Expected: empty directory

### Task 2: Create config.yaml

**Files:**

- Create: `~/.openclaw/workspace/autonomous/seo-guardian/config.yaml`

- [ ] **Step 1: Write config.yaml**

```yaml
agent:
  name: "seo-guardian"
  version: "1.0"
  description: "Monitors SEO performance, optimizes metadata, manages indexing"

observe:
  sources:
    - type: "script"
      path: "apps/evaluator/seo_guardian_core.py"
      args: ["--mode", "report"]
    - type: "file"
      path: "apps/evaluator/indexing_state.json"
    - type: "file"
      path: "apps/bali-intel-scraper/data/published_articles.json"

decide:
  risk_levels:
    LOW:
      - "submit_indexing_batch"
      - "update_meta_description"
      - "report_anomaly"
    MEDIUM:
      - "add_faq_schema"
      - "modify_article_metadata"
      - "create_redirect"
    HIGH:
      - "edit_article_body"
      - "remove_page"
      - "change_url_structure"
  max_actions_per_run:
    LOW: 10
    MEDIUM: 3

act:
  tools:
    - "apps/evaluator/kbli_indexing_submit.py"
    - "apps/evaluator/articles_indexing_submit.py"
    - "mcp:nuzantara-mcp.compose_article"
    - "mcp:nuzantara-mcp.publish_article"
    - "mcp:nuzantara-mcp.search_kbli"
    - "git commit"
  dry_run: false

measure:
  delay_hours: 48
  metrics:
    - "ctr_delta"
    - "position_delta"
    - "indexed_count"
    - "error_count"

learn:
  min_samples: 5
  confidence_threshold: 0.7
  human_override: true

delivery:
  channel: "telegram"
  to: "1125336968"
  report_format: "markdown"
```

- [ ] **Step 2: Verify YAML is valid**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate && python3 -c "import yaml; yaml.safe_load(open('$HOME/.openclaw/workspace/autonomous/seo-guardian/config.yaml')); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify pyyaml is installed in venv**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate && python3 -c "import yaml; print(f'pyyaml OK: {yaml.__version__}')" || pip install pyyaml
```

Expected: `pyyaml OK: <version>`

### Task 3: Create Initial State Files

**Files:**

- Create: `~/.openclaw/workspace/autonomous/seo-guardian/state.json`
- Create: `~/.openclaw/workspace/autonomous/seo-guardian/patterns.json`
- Create: `~/.openclaw/workspace/autonomous/seo-guardian/corrections.jsonl`
- Create: `~/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl` (empty)
- Create: `~/.openclaw/workspace/autonomous/seo-guardian/decisions.log` (empty)

- [ ] **Step 1: Write state.json with initial baseline**

```json
{
  "paused": false,
  "last_observe_run": null,
  "last_measure_run": null,
  "last_learn_run": null,
  "baseline": {
    "total_kbli_pages": 1563,
    "kbli_indexed": 700,
    "total_articles": 0,
    "avg_ctr": null,
    "avg_position": null
  },
  "current_metrics": {}
}
```

- [ ] **Step 2: Write patterns.json (empty array)**

```json
[]
```

- [ ] **Step 3: Write corrections.jsonl with base rules**

```jsonl
{"rule": "never_touch", "scope": "/lifestyle/*", "reason": "owner preference — content managed manually", "date": "2026-03-14"}
{"rule": "max_indexing_batch", "scope": "kbli_indexing_submit.py", "value": 50, "reason": "conservative daily limit to avoid API quota issues", "date": "2026-03-14"}
{"rule": "no_content_edit", "scope": "/kbli/*", "reason": "SSG pages — content changes require build + deploy", "date": "2026-03-14"}
```

- [ ] **Step 4: Create empty memory.jsonl and decisions.log**

```bash
touch ~/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl
touch ~/.openclaw/workspace/autonomous/seo-guardian/decisions.log
```

- [ ] **Step 5: Verify all files exist**

```bash
ls -la ~/.openclaw/workspace/autonomous/seo-guardian/
```

Expected: 6 files (config.yaml, state.json, patterns.json, corrections.jsonl, memory.jsonl, decisions.log)

### Task 4: Refactor seo_guardian_core.py — Add argparse CLI

**Files:**

- Modify: `apps/evaluator/seo_guardian_core.py:229-231` (replace `__main__` block)
- Modify: `apps/evaluator/seo_guardian_core.py:1-6` (add argparse import)
- Modify: `apps/evaluator/seo_guardian_core.py:214-226` (extend `run()` method)

- [ ] **Step 1: Add argparse import**

At the top of `seo_guardian_core.py`, add `argparse` to imports:

```python
import argparse
```

(Add after `import asyncio` on line 3)

- [ ] **Step 2: Add `run_report()` method to NuzantaraSEOGuardian**

Add this method after the existing `run()` method (after line 226):

```python
    async def run_report(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the guardian and output structured JSON report.
        Used by the autonomous agent system.
        """
        logger.info("=== SEO Guardian: REPORT MODE ===")
        plan = await self.run()

        # Enrich with indexing state
        indexing_state_path = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
        indexing_state = {}
        if indexing_state_path.exists():
            with open(indexing_state_path) as f:
                raw = json.load(f)
                indexing_state = {
                    "total_submitted": raw.get("total_submitted", 0),
                    "failed_count": len(raw.get("failed", [])),
                    "last_run": raw.get("last_run"),
                }

        report = {
            "timestamp": date.today().isoformat(),
            "mode": "report",
            "seo_plan": plan,
            "indexing_state": indexing_state,
            "opportunities": self._extract_opportunities(plan),
        }

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Report saved to %s", out)

        return report

    def _extract_opportunities(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract actionable opportunities from the SEO plan."""
        opportunities = []

        # High-impression zero-click pages
        for gap in plan.get("critical_gaps", []):
            opportunities.append({
                "type": "ctr_optimization",
                "risk": "LOW",
                "query": gap.get("query", ""),
                "impressions": gap.get("impressions", 0),
                "current_ctr": gap.get("ctr", 0),
                "current_position": gap.get("position", 0),
                "suggested_action": "update_meta_description",
            })

        # Indexing gaps
        indexing_state_path = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
        if indexing_state_path.exists():
            with open(indexing_state_path) as f:
                state = json.load(f)
            pending = 1563 - state.get("total_submitted", 0)
            if pending > 0:
                opportunities.append({
                    "type": "indexing_submission",
                    "risk": "LOW",
                    "pending_urls": pending,
                    "suggested_action": "submit_indexing_batch",
                    "batch_size": min(pending, 50),
                })

        return opportunities
```

- [ ] **Step 3: Replace `__main__` block with argparse CLI**

Replace lines 229-231 with:

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Nuzantara SEO Guardian")
    parser.add_argument(
        "--mode",
        choices=["run", "report"],
        default="run",
        help="run: standard execution. report: structured JSON output for agent system.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for report mode (default: stdout as JSON)",
    )
    args = parser.parse_args()

    guardian = NuzantaraSEOGuardian()

    if args.mode == "report":
        report = asyncio.run(guardian.run_report(output_path=args.output))
        if not args.output:
            print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        asyncio.run(guardian.run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test report mode (dry run)**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
GA4_PROPERTY_ID=505466833 python3 apps/evaluator/seo_guardian_core.py --mode report 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK: {len(d.get(\"opportunities\",[]))} opportunities found')"
```

Expected: `OK: N opportunities found` (N ≥ 0)

- [ ] **Step 5: Test report mode with file output**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
GA4_PROPERTY_ID=505466833 python3 apps/evaluator/seo_guardian_core.py --mode report --output /tmp/seo-test-report.json 2>/dev/null
python3 -c "import json; d=json.load(open('/tmp/seo-test-report.json')); print(f'OK: mode={d[\"mode\"]}, timestamp={d[\"timestamp\"]}')"
rm /tmp/seo-test-report.json
```

Expected: `OK: mode=report, timestamp=2026-03-14`

- [ ] **Step 6: Test backward compatibility (original mode still works)**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
GA4_PROPERTY_ID=505466833 python3 apps/evaluator/seo_guardian_core.py --mode run 2>&1 | grep -c "SEO Cycle Complete"
```

Expected: `1`

- [ ] **Step 7: Commit**

```bash
git add apps/evaluator/seo_guardian_core.py
git commit -m "feat(seo): add --mode report CLI to seo_guardian_core.py

Adds argparse CLI with run (default, backward compat) and report modes.
Report mode outputs structured JSON with opportunities extraction for
the autonomous agent system."
```

---

## Chunk 2: Agent Script (DECIDE + ACT + MEASURE + LEARN)

### File Structure

| File                                     | Action | Purpose                                                                |
| ---------------------------------------- | ------ | ---------------------------------------------------------------------- |
| `apps/evaluator/seo_guardian_agent.py`   | Create | Main agent script: load state → check corrections → decide → act → log |
| `apps/evaluator/seo_guardian_measure.py` | Create | Measure script: compare pre/post metrics, update memory                |
| `apps/evaluator/seo_guardian_learn.py`   | Create | Learn script: extract patterns from memory, update patterns.json       |

### Task 5: Create seo_guardian_agent.py (DECIDE + ACT)

**Files:**

- Create: `apps/evaluator/seo_guardian_agent.py`

- [ ] **Step 1: Write the agent script**

```python
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(PROJECT_ROOT))
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
```

- [ ] **Step 2: Test dry-run mode (no observe)**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_agent.py --dry-run 2>&1 | tail -5
```

Expected: JSON output with `"status": "completed"` and `"dry_run": true`

- [ ] **Step 3: Test with observe-first**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
GA4_PROPERTY_ID=505466833 python3 apps/evaluator/seo_guardian_agent.py --dry-run --observe-first 2>&1 | tail -5
```

Expected: JSON output showing opportunities processed

- [ ] **Step 4: Verify memory.jsonl was written and contains git_sha field**

```bash
wc -l ~/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl
python3 -c "import json; e=json.loads(open('$HOME/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl').readline()); print(f'git_sha field: {\"git_sha\" in e}')"
tail -10 ~/.openclaw/workspace/autonomous/seo-guardian/decisions.log
```

Expected: at least 1 line in memory.jsonl, `git_sha field: True`, decision log entries visible

- [ ] **Step 5: Test kill switch**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 -c "import json; s=json.load(open('$HOME/.openclaw/workspace/autonomous/seo-guardian/state.json')); s['paused']=True; json.dump(s,open('$HOME/.openclaw/workspace/autonomous/seo-guardian/state.json','w'),indent=2)"
python3 apps/evaluator/seo_guardian_agent.py --dry-run 2>&1 | grep -c paused
python3 -c "import json; s=json.load(open('$HOME/.openclaw/workspace/autonomous/seo-guardian/state.json')); s['paused']=False; json.dump(s,open('$HOME/.openclaw/workspace/autonomous/seo-guardian/state.json','w'),indent=2)"
```

Expected: `1` (paused status detected)

- [ ] **Step 6: Commit**

```bash
git add apps/evaluator/seo_guardian_agent.py
git commit -m "feat(seo): add seo_guardian_agent.py — autonomous DECIDE+ACT cycle

Reads observe output, checks corrections, classifies risk, executes
LOW actions autonomously. Supports --dry-run and --observe-first flags.
Logs all decisions to memory.jsonl and decisions.log."
```

### Task 6: Create seo_guardian_measure.py (MEASURE)

**Files:**

- Create: `apps/evaluator/seo_guardian_measure.py`

- [ ] **Step 1: Write the measure script**

```python
"""
SEO Guardian — MEASURE
========================
Compares pre/post metrics for actions logged in memory.jsonl.
Updates each action entry with measured results.

Usage:
    python seo_guardian_measure.py           # measure pending actions
    python seo_guardian_measure.py --status  # show measurement status
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Measure] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENT_DIR = Path.home() / ".openclaw" / "workspace" / "autonomous" / "seo-guardian"
MEMORY_PATH = AGENT_DIR / "memory.jsonl"
STATE_PATH = AGENT_DIR / "state.json"


def load_memory() -> list[dict]:
    if not MEMORY_PATH.exists():
        return []
    entries = []
    with open(MEMORY_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def save_memory(entries: list[dict]) -> None:
    with open(MEMORY_PATH, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_pending_measurements(entries: list[dict], min_age_hours: int = 48) -> list[int]:
    """Find entries that are old enough to measure but haven't been measured yet."""
    cutoff = datetime.now() - timedelta(hours=min_age_hours)
    pending = []
    for i, entry in enumerate(entries):
        if entry.get("measured"):
            continue
        if entry.get("dry_run") and entry.get("result", {}).get("type") in ("logged_for_review", "pending_confirmation"):
            continue  # Skip dry-run/pending entries
        ts = entry.get("timestamp")
        if ts:
            action_time = datetime.fromisoformat(ts)
            if action_time < cutoff:
                pending.append(i)
    return pending


async def measure_indexing_action(entry: dict) -> dict:
    """Measure the impact of an indexing submission action."""
    # Check current indexing state
    indexing_state_path = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
    if indexing_state_path.exists():
        with open(indexing_state_path) as f:
            state = json.load(f)
        return {
            "measured_at": datetime.now().isoformat(),
            "current_submitted": state.get("total_submitted", 0),
            "current_failed": len(state.get("failed", [])),
            "success": True,
        }
    return {"measured_at": datetime.now().isoformat(), "success": False, "reason": "state file not found"}


async def measure_action(entry: dict) -> dict | None:
    """Route measurement to the appropriate handler."""
    action = entry.get("action", "")
    if action == "submit_indexing_batch":
        return await measure_indexing_action(entry)
    if action == "report_anomaly":
        # Reports don't need measurement
        return {"measured_at": datetime.now().isoformat(), "success": True, "type": "report_no_measurement"}
    # Default: mark as measured with no data
    return {"measured_at": datetime.now().isoformat(), "success": True, "type": "no_measurement_available"}


async def run_measure() -> dict:
    """Main measurement loop."""
    entries = load_memory()
    pending = get_pending_measurements(entries)

    if not pending:
        logger.info("No actions pending measurement")
        return {"status": "no_pending", "total_entries": len(entries)}

    logger.info("Measuring %d actions (of %d total)", len(pending), len(entries))
    measured_count = 0

    for idx in pending:
        entry = entries[idx]
        measurement = await measure_action(entry)
        if measurement:
            entry["measured"] = True
            entry["measurement"] = measurement
            measured_count += 1
            logger.info("Measured: %s → %s", entry.get("action"), measurement.get("type", "OK"))

    save_memory(entries)

    # Update state
    state: dict[str, Any] = {}
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            state = json.load(f)
    state["last_measure_run"] = datetime.now().isoformat()
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return {"status": "completed", "measured": measured_count, "total_entries": len(entries)}


def print_status() -> None:
    entries = load_memory()
    measured = sum(1 for e in entries if e.get("measured"))
    unmeasured = sum(1 for e in entries if not e.get("measured") and not e.get("dry_run"))
    dry_run = sum(1 for e in entries if e.get("dry_run"))

    print(f"\n=== SEO Guardian Measurement Status ===")
    print(f"Total actions:   {len(entries)}")
    print(f"Measured:        {measured}")
    print(f"Pending:         {unmeasured}")
    print(f"Dry-run (skip):  {dry_run}")
    print(f"=======================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Guardian — MEASURE")
    parser.add_argument("--status", action="store_true", help="Show measurement status")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    result = asyncio.run(run_measure())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Seed memory.jsonl with test entry for measurement**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 -c "
import json
from datetime import datetime, timedelta
# Seed an entry 49 hours old (past 48h threshold) for measurement testing
entry = {
    'timestamp': (datetime.now() - timedelta(hours=49)).isoformat(),
    'action': 'submit_indexing_batch',
    'risk': 'LOW',
    'params': {'batch_size': 5},
    'dry_run': False,
    'result': {'success': True, 'stdout': 'test'},
    'git_sha': None,
    'measured': False,
}
with open('$HOME/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl', 'a') as f:
    f.write(json.dumps(entry) + '\n')
print('Seeded test entry')
"
```

Expected: `Seeded test entry`

- [ ] **Step 3: Test measurement run (should find the seeded entry)**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_measure.py 2>&1
```

Expected: JSON with `"status": "completed"`, `"measured": 1`

- [ ] **Step 4: Test status display**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_measure.py --status
```

Expected: `Measured: 1`, `Pending: 0`

- [ ] **Step 5: Commit**

```bash
git add apps/evaluator/seo_guardian_measure.py
git commit -m "feat(seo): add seo_guardian_measure.py — MEASURE phase

Finds actions in memory.jsonl older than 48h, measures their impact
by checking current state, and updates entries with measurement data."
```

### Task 7: Create seo_guardian_learn.py (LEARN)

**Files:**

- Create: `apps/evaluator/seo_guardian_learn.py`

- [ ] **Step 1: Write the learn script**

```python
"""
SEO Guardian — LEARN
======================
Extracts patterns from measured actions in memory.jsonl.
Updates patterns.json with statistical rules.

Usage:
    python seo_guardian_learn.py           # extract patterns
    python seo_guardian_learn.py --status  # show current patterns
"""

import argparse
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Learn] %(levelname)s: %(message)s")

AGENT_DIR = Path.home() / ".openclaw" / "workspace" / "autonomous" / "seo-guardian"
MEMORY_PATH = AGENT_DIR / "memory.jsonl"
PATTERNS_PATH = AGENT_DIR / "patterns.json"
STATE_PATH = AGENT_DIR / "state.json"

MIN_SAMPLES = 5
CONFIDENCE_THRESHOLD = 0.7


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


def extract_patterns(entries: list[dict]) -> list[dict]:
    """Extract statistical patterns from measured actions."""
    # Group by action type
    by_action: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        if entry.get("measured") and not entry.get("dry_run"):
            by_action[entry.get("action", "unknown")].append(entry)

    patterns = []
    for action_type, actions in by_action.items():
        if len(actions) < MIN_SAMPLES:
            logger.info("Skipping %s: only %d samples (need %d)", action_type, len(actions), MIN_SAMPLES)
            continue

        # Calculate success rate
        successes = sum(1 for a in actions if a.get("result", {}).get("success"))
        success_rate = successes / len(actions)

        pattern = {
            "action": action_type,
            "sample_size": len(actions),
            "success_rate": round(success_rate, 2),
            "confidence": round(min(success_rate, len(actions) / (MIN_SAMPLES * 2)), 2),
            "first_seen": min(a.get("timestamp", "") for a in actions),
            "last_seen": max(a.get("timestamp", "") for a in actions),
            "extracted_at": datetime.now().isoformat(),
        }

        if pattern["confidence"] >= CONFIDENCE_THRESHOLD:
            pattern["recommendation"] = "continue"
        else:
            pattern["recommendation"] = "review"

        patterns.append(pattern)
        logger.info(
            "Pattern: %s — %d samples, %.0f%% success, confidence=%.2f → %s",
            action_type, len(actions), success_rate * 100,
            pattern["confidence"], pattern["recommendation"],
        )

    return patterns


def run_learn() -> dict:
    """Main learn loop."""
    entries = load_jsonl(MEMORY_PATH)
    measured = [e for e in entries if e.get("measured")]

    if not measured:
        logger.info("No measured actions to learn from")
        return {"status": "no_data", "total_entries": len(entries), "measured": 0}

    patterns = extract_patterns(entries)

    # Save patterns
    with open(PATTERNS_PATH, "w") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)

    # Update state
    state = {}
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            state = json.load(f)
    state["last_learn_run"] = datetime.now().isoformat()
    state["patterns_count"] = len(patterns)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return {
        "status": "completed",
        "total_entries": len(entries),
        "measured_entries": len(measured),
        "patterns_extracted": len(patterns),
        "patterns": patterns,
    }


def print_status() -> None:
    patterns = []
    if PATTERNS_PATH.exists():
        with open(PATTERNS_PATH) as f:
            patterns = json.load(f)

    print(f"\n=== SEO Guardian Learned Patterns ===")
    if not patterns:
        print("No patterns extracted yet (need 5+ measured samples per action type)")
    else:
        for p in patterns:
            print(f"  {p['action']}: {p['sample_size']} samples, "
                  f"{p['success_rate']*100:.0f}% success, "
                  f"confidence={p['confidence']:.2f} → {p['recommendation']}")
    print(f"=====================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Guardian — LEARN")
    parser.add_argument("--status", action="store_true", help="Show current patterns")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    result = run_learn()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test with existing memory**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_learn.py --status
```

Expected: "No patterns extracted yet" (need 5+ samples) or pattern list

- [ ] **Step 3: Test learn run**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_learn.py 2>&1
```

Expected: JSON with `"status"` field (likely `"no_data"` or `"completed"` depending on measured entries)

- [ ] **Step 4: Commit**

```bash
git add apps/evaluator/seo_guardian_learn.py
git commit -m "feat(seo): add seo_guardian_learn.py — LEARN phase

Extracts statistical patterns from measured actions in memory.jsonl.
Requires 5+ samples and 0.7 confidence threshold. Updates patterns.json."
```

---

## Chunk 3: OpenClaw Cron Jobs + Validation

### Task 8: Add 3 Cron Jobs to OpenClaw

**Files:**

- Modify: `~/.openclaw/cron/jobs.json`

- [ ] **Step 1: Read current jobs.json to find insertion point**

```bash
python3 -c "import json; d=json.load(open('$HOME/.openclaw/cron/jobs.json')); print(f'{len(d[\"jobs\"])} jobs')"
```

- [ ] **Step 2: Add seo-guardian-observe cron job**

Add to `jobs` array in `~/.openclaw/cron/jobs.json` (must match OpenClaw schema exactly):

```json
{
  "id": "seo-guardian-observe-001",
  "name": "seo-guardian-observe",
  "description": "SEO Guardian: daily OBSERVE → DECIDE → ACT cycle",
  "enabled": true,
  "createdAtMs": 1773532800000,
  "updatedAtMs": 1773532800000,
  "schedule": {
    "kind": "cron",
    "timezone": "Asia/Makassar",
    "expr": "0 7 * * *"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "You are the SEO Guardian autonomous agent. Run the OBSERVE → DECIDE → ACT cycle.\n\n1. OBSERVE + DECIDE + ACT: exec: cd ~/Desktop/nuzantara && source venv/bin/activate && GA4_PROPERTY_ID=505466833 python3 apps/evaluator/seo_guardian_agent.py --observe-first 2>&1\n\n2. Read the JSON output and format a Telegram report:\n   - Number of opportunities found\n   - Actions taken (with risk level)\n   - Actions blocked by corrections\n   - Actions skipped (HIGH risk)\n\nFormat as a clean Markdown Telegram message with emoji status indicators."
  },
  "delivery": {
    "mode": "announce",
    "channel": "telegram",
    "to": "1125336968"
  },
  "state": {
    "consecutiveErrors": 0,
    "nextRunAtMs": 0,
    "lastRunAtMs": 0
  }
}
```

- [ ] **Step 3: Add seo-guardian-measure cron job**

```json
{
  "id": "seo-guardian-measure-001",
  "name": "seo-guardian-measure",
  "description": "SEO Guardian: daily MEASURE phase — check impact of past actions",
  "enabled": true,
  "createdAtMs": 1773532800000,
  "updatedAtMs": 1773532800000,
  "schedule": {
    "kind": "cron",
    "timezone": "Asia/Makassar",
    "expr": "30 7 * * *"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "You are the SEO Guardian MEASURE phase.\n\nexec: cd ~/Desktop/nuzantara && source venv/bin/activate && python3 apps/evaluator/seo_guardian_measure.py 2>&1\n\nRead the JSON output. If any actions were measured, format a brief Telegram update:\n- How many actions measured\n- Success/failure for each\n\nIf no actions pending measurement, respond with a one-line status update only."
  },
  "delivery": {
    "mode": "announce",
    "channel": "telegram",
    "to": "1125336968"
  },
  "state": {
    "consecutiveErrors": 0,
    "nextRunAtMs": 0,
    "lastRunAtMs": 0
  }
}
```

- [ ] **Step 4: Add seo-guardian-weekly cron job**

```json
{
  "id": "seo-guardian-weekly-001",
  "name": "seo-guardian-weekly",
  "description": "SEO Guardian: weekly LEARN + comprehensive report",
  "enabled": true,
  "createdAtMs": 1773532800000,
  "updatedAtMs": 1773532800000,
  "schedule": {
    "kind": "cron",
    "timezone": "Asia/Makassar",
    "expr": "0 8 * * 1"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "You are the SEO Guardian weekly LEARN + REPORT phase.\n\n1. exec: cd ~/Desktop/nuzantara && source venv/bin/activate && python3 apps/evaluator/seo_guardian_learn.py 2>&1\n2. exec: cd ~/Desktop/nuzantara && source venv/bin/activate && python3 apps/evaluator/seo_guardian_measure.py --status 2>&1\n3. Read ~/.openclaw/workspace/autonomous/seo-guardian/state.json for current state\n4. Read ~/.openclaw/workspace/autonomous/seo-guardian/patterns.json for learned patterns\n5. Count entries in ~/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl\n\nFormat a comprehensive weekly Telegram report:\n📊 *SEO Guardian Weekly Report*\n- Total actions this week\n- Patterns learned (if any)\n- Current indexing progress\n- Recommendations for next week\n- Any corrections that should be added"
  },
  "delivery": {
    "mode": "announce",
    "channel": "telegram",
    "to": "1125336968"
  },
  "state": {
    "consecutiveErrors": 0,
    "nextRunAtMs": 0,
    "lastRunAtMs": 0
  }
}
```

- [ ] **Step 5: Validate jobs.json is valid JSON**

```bash
python3 -c "import json; d=json.load(open('$HOME/.openclaw/cron/jobs.json')); seo=[j for j in d['jobs'] if 'seo-guardian' in j.get('name','')]; print(f'OK: {len(seo)} SEO Guardian jobs found: {[j[\"name\"] for j in seo]}')"
```

Expected: `OK: 3 SEO Guardian jobs found: ['seo-guardian-observe', 'seo-guardian-measure', 'seo-guardian-weekly']`

### Task 9: End-to-End Dry Run Validation

- [ ] **Step 1: Run full observe + agent cycle in dry-run**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
GA4_PROPERTY_ID=505466833 python3 apps/evaluator/seo_guardian_agent.py --dry-run --observe-first 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Status: {d[\"status\"]}, Actions: {d[\"actions_taken\"]}, Blocked: {d[\"actions_blocked\"]}, Skipped: {d[\"actions_skipped\"]}')"
```

Expected: `Status: completed, Actions: N, Blocked: M, Skipped: K`

- [ ] **Step 2: Verify all agent files populated**

```bash
echo "=== Agent workspace ==="
ls -la ~/.openclaw/workspace/autonomous/seo-guardian/
echo "=== memory.jsonl entries ==="
wc -l ~/.openclaw/workspace/autonomous/seo-guardian/memory.jsonl
echo "=== Last 3 decisions ==="
tail -3 ~/.openclaw/workspace/autonomous/seo-guardian/decisions.log
echo "=== State ==="
python3 -c "import json; print(json.dumps(json.load(open('$HOME/.openclaw/workspace/autonomous/seo-guardian/state.json')), indent=2))"
```

Expected: All files present, memory has entries, decisions logged, state updated

- [ ] **Step 3: Run measure**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_measure.py 2>&1
```

Expected: JSON with `"status"` field

- [ ] **Step 4: Run learn**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source venv/bin/activate
python3 apps/evaluator/seo_guardian_learn.py 2>&1
```

Expected: JSON with `"status"` field

- [ ] **Step 5: Final commit — all agent scripts**

```bash
git add apps/evaluator/seo_guardian_core.py apps/evaluator/seo_guardian_agent.py apps/evaluator/seo_guardian_measure.py apps/evaluator/seo_guardian_learn.py
git commit -m "feat(seo): complete SEO Guardian autonomous agent system

Full OBSERVE→DECIDE→ACT→MEASURE→LEARN cycle:
- seo_guardian_core.py: refactored with --mode report (structured JSON)
- seo_guardian_agent.py: autonomous DECIDE+ACT with risk classification
- seo_guardian_measure.py: post-action impact measurement
- seo_guardian_learn.py: pattern extraction from measured actions

Agent workspace: ~/.openclaw/workspace/autonomous/seo-guardian/
OpenClaw cron: 3 jobs (observe daily 7am, measure daily 7:30am, learn weekly Mon 8am)"
```
