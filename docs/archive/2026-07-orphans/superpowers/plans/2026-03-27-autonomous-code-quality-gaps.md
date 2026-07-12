# Autonomous Code Quality Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 8 gaps to make Nuzantara's code quality pipeline fully autonomous — zero manual intervention needed after a fix lands.

**Architecture:** Extend existing Surgeon/Watchdog/Sentinel stack. Each gap gets a state file (`~/.agent/decisions/state/<job_id>.last.json`) that Sentinel reads. Surgeon gains a merge-bot path. Watchdog gains auto-trigger logic. CI gains migration step.

**Tech Stack:** Python 3.11, git worktrees, GitHub Actions (YAML), asyncpg, pytest, ruff, mypy, vulture, pip-audit, gh CLI

---

## File Map

| File                                       | Action | Purpose                                                            |
| ------------------------------------------ | ------ | ------------------------------------------------------------------ |
| `apps/evaluator/core_guardian/surgeon.py`  | Modify | Add `merge_to_main()` and `write_last_json()`                      |
| `apps/evaluator/core_guardian/watchdog.py` | Modify | Add `auto_dispatch_surgeon()` on regression                        |
| `apps/evaluator/core_guardian/scout.py`    | Modify | Add mypy + vulture runners, write `.last.json`                     |
| `.github/workflows/fly-deploy.yml`         | Modify | Add migration step between gate and deploy                         |
| `scripts/rag_canary.py`                    | Modify | Add `.last.json` write on Pro + register in job_registry           |
| `scripts/dep_audit.py`                     | Create | pip-audit scan → auto-PR via `gh pr create`                        |
| `scripts/coverage_trend.py`                | Create | Track passed-count trend in `.agent/decisions/coverage_trend.json` |
| `~/.agent/decisions/job_registry.json`     | Modify | Register new jobs: dep_audit, rag_canary_pro, coverage_trend       |

---

## Task 1 — Surgeon merge-bot: merge `cg/fix-*` to main after all gates pass

**Files:**

- Modify: `apps/evaluator/core_guardian/surgeon.py:187-230` (after commit block in `run_fix()`)

- [ ] **Step 1.1: Read current commit block in surgeon.py**

```bash
grep -n "git commit\|commit_result\|keep_branch" apps/evaluator/core_guardian/surgeon.py | head -30
```

Expected: shows commit block around line 600-650.

- [ ] **Step 1.2: Write the failing test**

Create `apps/evaluator/core_guardian/tests/test_surgeon_merge.py`:

```python
"""Tests for Surgeon merge-bot path."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from surgeon import merge_to_main, write_last_json


class TestMergeToMain(unittest.TestCase):
    @patch("surgeon.subprocess.run")
    @patch("surgeon.PROJECT_ROOT", Path("/fake/root"))
    def test_merge_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = merge_to_main("cg/fix-abc123")
        self.assertIsNone(result)
        # Should call: fetch, checkout main, merge --ff-only, push, checkout back
        self.assertGreaterEqual(mock_run.call_count, 3)

    @patch("surgeon.subprocess.run")
    @patch("surgeon.PROJECT_ROOT", Path("/fake/root"))
    def test_merge_conflict_returns_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="CONFLICT")
        result = merge_to_main("cg/fix-abc123")
        self.assertIsNotNone(result)
        self.assertIn("CONFLICT", result)

    def test_write_last_json_creates_file(self) -> None:
        import tempfile, json, os
        with tempfile.TemporaryDirectory() as d:
            state_dir = Path(d)
            write_last_json("test_job", "ok", state_dir=state_dir)
            f = state_dir / "test_job.last.json"
            self.assertTrue(f.exists())
            data = json.loads(f.read_text())
            self.assertEqual(data["status"], "ok")
            self.assertIn("ts", data)
            self.assertEqual(data["job"], "test_job")
```

- [ ] **Step 1.3: Run test to verify it fails**

```bash
cd apps/evaluator/core_guardian
python -m pytest tests/test_surgeon_merge.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'merge_to_main'`

- [ ] **Step 1.4: Add `merge_to_main()` and `write_last_json()` to surgeon.py**

Find the section after `def cleanup_worktree(` and add before the `# --- Claude Code Bridge ---` marker:

```python
# --- Merge Bot ---

def get_default_branch() -> str:
    """Detect default branch name (main or master)."""
    result = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip().split("/")[-1]
    return "main"


def merge_to_main(branch_name: str) -> str | None:
    """
    Merge a cg/fix-* branch into main and push.
    Returns error string or None on success.

    Safety: uses --ff-only (never creates a merge commit, fails if diverged).
    On success, triggers GitHub Actions deploy pipeline automatically.
    """
    default_branch = get_default_branch()
    try:
        # Ensure we have latest
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=str(PROJECT_ROOT), capture_output=True, timeout=30,
        )
        # Checkout default branch
        r = subprocess.run(
            ["git", "checkout", default_branch],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return f"checkout {default_branch} failed: {r.stderr[:200]}"

        # Fast-forward only — never create a merge commit
        r = subprocess.run(
            ["git", "merge", "--ff-only", branch_name],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            # Abort: go back to default branch cleanly
            subprocess.run(
                ["git", "checkout", default_branch],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )
            return f"merge --ff-only failed: {r.stderr[:300]}"

        # Push → triggers GitHub Actions
        r = subprocess.run(
            ["git", "push", "origin", default_branch],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return f"push failed: {r.stderr[:200]}"

        logger.info(f"✅ Merged {branch_name} → {default_branch} + pushed (CI triggered)")
        return None
    except Exception as e:
        return f"merge_to_main exception: {e}"


def write_last_json(
    job_id: str,
    status: str,
    detail: str = "",
    state_dir: Path | None = None,
) -> None:
    """Write ~/.agent/decisions/state/<job_id>.last.json for Sentinel monitoring."""
    if state_dir is None:
        state_dir = AGENT_DIR / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job": job_id,
        "status": status,  # "ok" | "failed" | "skipped"
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(state_dir / f"{job_id}.last.json", payload)
```

- [ ] **Step 1.5: Hook merge-bot into `run_fix()` after successful commit**

Find the block in `run_fix()` after the git commit succeeds (look for `"outcome": "ok"`). Add:

```python
        # --- MERGE BOT: merge cg/fix-* → main ---
        merge_error = merge_to_main(branch_name)
        if merge_error:
            logger.warning(f"Merge to main failed (branch kept): {merge_error}")
            send_telegram_alert(f"⚠️ Surgeon fix committed but merge failed:\n{merge_error}")
            # Write state as "merged_failed" — Sentinel will alert
            write_last_json("core_guardian", "failed", detail=f"merge failed: {merge_error}")
        else:
            write_last_json("core_guardian", "ok", detail=f"merged {branch_name}")
```

Also add `write_last_json("core_guardian", "failed", ...)` in the failure path at the bottom of `run_fix()`.

- [ ] **Step 1.6: Run tests**

```bash
cd apps/evaluator/core_guardian
python -m pytest tests/test_surgeon_merge.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 1.7: Commit**

```bash
git add apps/evaluator/core_guardian/surgeon.py apps/evaluator/core_guardian/tests/test_surgeon_merge.py
git commit -m "feat(surgeon): merge-bot — ff-only merge + push to main after gates pass"
```

---

## Task 2 — Watchdog → Surgeon auto-trigger on regression

**Files:**

- Modify: `apps/evaluator/core_guardian/watchdog.py` (add after regression alert)

- [ ] **Step 2.1: Write the failing test**

Create `apps/evaluator/core_guardian/tests/test_watchdog_trigger.py`:

```python
"""Tests for Watchdog → Surgeon auto-dispatch."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import watchdog as wd


class TestAutoDispatchSurgeon(unittest.TestCase):
    import unittest

    @patch("watchdog.subprocess.run")
    @patch("watchdog.BACKEND_DIR", Path("/fake/backend"))
    def test_dispatch_calls_surgeon(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="backend/app/foo.py:5:1: ANN001")
        wd.auto_dispatch_surgeon(regressions=["backend/app/foo.py"])
        # subprocess.run should have been called at least once (ruff then surgeon)
        self.assertGreater(mock_run.call_count, 0)

    @patch("watchdog.subprocess.run")
    def test_empty_regressions_skips(self, mock_run: MagicMock) -> None:
        wd.auto_dispatch_surgeon(regressions=[])
        mock_run.assert_not_called()
```

(Add `import unittest` at top of file.)

- [ ] **Step 2.2: Run test to verify it fails**

```bash
cd apps/evaluator/core_guardian
python -m pytest tests/test_watchdog_trigger.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'watchdog' has no attribute 'auto_dispatch_surgeon'`

- [ ] **Step 2.3: Add `auto_dispatch_surgeon()` to watchdog.py**

Add after the `send_telegram_alert` function (around line 120):

```python
def auto_dispatch_surgeon(regressions: list[str]) -> None:
    """
    On regression detected, identify SAFE_RUFF violations in failing files
    and dispatch Surgeon for each one.

    Only dispatches for codes in SAFE_RUFF_CODES (deterministic fixes, low risk).
    Max 2 files per regression event to avoid thrashing.
    """
    if not regressions:
        return

    SAFE_RUFF_CODES = {"ANN001", "ANN204", "DTZ003", "DTZ005"}
    SURGEON_SCRIPT = Path(__file__).parent / "surgeon.py"

    if not SURGEON_SCRIPT.exists():
        logger.warning("surgeon.py not found — skipping auto-dispatch")
        return

    dispatched = 0
    for target_file in regressions[:2]:  # max 2 files per event
        # Run ruff on the file to identify violations
        try:
            result = subprocess.run(
                [str(VENV_PYTHON), "-m", "ruff", "check", target_file,
                 "--select", ",".join(SAFE_RUFF_CODES), "--output-format", "json"],
                cwd=str(BACKEND_DIR),
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            import json as _json
            violations = _json.loads(result.stdout)
            if not violations:
                continue
            # Take first violation code
            code = violations[0].get("code", "")
            if code not in SAFE_RUFF_CODES:
                continue

            logger.info(f"Auto-dispatching Surgeon for {target_file} ({code})")
            subprocess.Popen(
                [str(VENV_PYTHON), str(SURGEON_SCRIPT),
                 f"Fix {code} in {target_file}", target_file, code],
                cwd=str(PROJECT_ROOT),
            )
            dispatched += 1
        except Exception as e:
            logger.warning(f"auto_dispatch_surgeon failed for {target_file}: {e}")

    if dispatched > 0:
        logger.info(f"Auto-dispatched Surgeon for {dispatched} file(s)")
```

- [ ] **Step 2.4: Wire auto_dispatch_surgeon into the regression handler**

Find the block where watchdog sends the regression alert (look for `send_telegram_alert` with "regression"). After the alert, add:

```python
    # Auto-dispatch Surgeon for safe ruff violations in affected files
    failing_files = [t.get("classname", "").replace(".", "/") + ".py"
                     for t in failed_tests if t.get("classname")]
    if failing_files:
        auto_dispatch_surgeon(regressions=failing_files)
```

- [ ] **Step 2.5: Run tests**

```bash
cd apps/evaluator/core_guardian
python -m pytest tests/test_watchdog_trigger.py -v
```

Expected: PASS.

- [ ] **Step 2.6: Commit**

```bash
git add apps/evaluator/core_guardian/watchdog.py apps/evaluator/core_guardian/tests/test_watchdog_trigger.py
git commit -m "feat(watchdog): auto-dispatch Surgeon on regression for safe ruff codes"
```

---

## Task 3 — dep_audit: pip-audit → auto-PR on high/critical vulns

**Files:**

- Create: `scripts/dep_audit.py`
- Modify: `~/.agent/decisions/job_registry.json`

- [ ] **Step 3.1: Write the failing test**

Create `scripts/tests/test_dep_audit.py`:

```python
"""Tests for dep_audit.py."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import dep_audit


class TestDepAudit(unittest.TestCase):
    def test_parse_pip_audit_output(self) -> None:
        sample = json.dumps([
            {"name": "requests", "version": "2.25.0",
             "vulns": [{"id": "GHSA-xxx", "fix_versions": ["2.28.0"],
                        "aliases": ["CVE-2023-xxx"], "description": "test",
                        "severity": "HIGH"}]}
        ])
        vulns = dep_audit.parse_pip_audit_output(sample)
        self.assertEqual(len(vulns), 1)
        self.assertEqual(vulns[0]["package"], "requests")
        self.assertEqual(vulns[0]["severity"], "HIGH")

    def test_parse_empty_output(self) -> None:
        vulns = dep_audit.parse_pip_audit_output("[]")
        self.assertEqual(vulns, [])

    def test_format_pr_body(self) -> None:
        vulns = [{"package": "foo", "version": "1.0", "severity": "HIGH",
                  "fix": "1.1", "cve": "CVE-2023-001", "desc": "test vuln"}]
        body = dep_audit.format_pr_body(vulns)
        self.assertIn("foo", body)
        self.assertIn("HIGH", body)
        self.assertIn("CVE-2023-001", body)

    @patch("dep_audit.subprocess.run")
    def test_run_pip_audit_returns_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"name":"x","version":"1","vulns":[]}]')
        result = dep_audit.run_pip_audit(Path("/fake/requirements.txt"))
        self.assertIsInstance(result, str)
```

- [ ] **Step 3.2: Run test to verify it fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python -m pytest scripts/tests/test_dep_audit.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'dep_audit'`

- [ ] **Step 3.3: Create scripts/dep_audit.py**

````python
#!/usr/bin/env python3
"""
Dep Audit — Weekly dependency vulnerability scanner with auto-PR.

Runs pip-audit on requirements.txt, filters HIGH/CRITICAL, opens a GitHub PR
with upgrade suggestions. Registers state in ~/.agent/decisions/state/dep_audit.last.json
for Sentinel monitoring.

Usage:
    python3 scripts/dep_audit.py                # Full scan + PR if vulns found
    python3 scripts/dep_audit.py --dry-run      # Scan only, no PR
    python3 scripts/dep_audit.py --min-severity CRITICAL  # Only critical
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[DepAudit %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dep_audit")

PROJECT_ROOT = Path(__file__).parent.parent
REQUIREMENTS_FILE = PROJECT_ROOT / "apps" / "backend-rag" / "requirements.txt"
VENV_PYTHON = PROJECT_ROOT / "apps" / "backend-rag" / ".venv" / "bin" / "python"
STATE_DIR = Path.home() / ".agent" / "decisions" / "state"
SEVERITY_ORDER = ["UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def run_pip_audit(requirements: Path) -> str:
    """Run pip-audit and return raw JSON output."""
    cmd = [
        str(VENV_PYTHON), "-m", "pip_audit",
        "--requirement", str(requirements),
        "--format", "json",
        "--progress-spinner", "off",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # pip-audit exits 1 if vulns found — that's OK
    return result.stdout or "[]"


def parse_pip_audit_output(raw: str) -> list[dict]:
    """Parse pip-audit JSON → flat list of {package, version, severity, fix, cve, desc}."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    vulns = []
    for pkg in data:
        for vuln in pkg.get("vulns", []):
            aliases = vuln.get("aliases", [])
            cve = next((a for a in aliases if a.startswith("CVE-")), vuln.get("id", ""))
            fix_versions = vuln.get("fix_versions", [])
            vulns.append({
                "package": pkg["name"],
                "version": pkg["version"],
                "severity": vuln.get("severity", "UNKNOWN").upper(),
                "fix": fix_versions[0] if fix_versions else "N/A",
                "cve": cve,
                "desc": vuln.get("description", "")[:120],
            })
    return vulns


def filter_by_severity(vulns: list[dict], min_severity: str) -> list[dict]:
    min_idx = SEVERITY_ORDER.index(min_severity.upper()) if min_severity.upper() in SEVERITY_ORDER else 3
    return [v for v in vulns if SEVERITY_ORDER.index(v["severity"]) >= min_idx]


def format_pr_body(vulns: list[dict]) -> str:
    lines = ["## 🔒 Dependency Security Audit", "",
             f"Found **{len(vulns)}** HIGH/CRITICAL vulnerabilities in `requirements.txt`.", "",
             "| Package | Current | Severity | Fix Version | CVE |",
             "|---------|---------|----------|-------------|-----|"]
    for v in vulns:
        lines.append(f"| {v['package']} | {v['version']} | {v['severity']} | {v['fix']} | {v['cve']} |")
    lines += ["", "### Auto-generated upgrade commands", "```bash",
              "cd apps/backend-rag && source .venv/bin/activate"]
    for v in vulns:
        if v["fix"] != "N/A":
            lines.append(f"pip install '{v['package']}>={v['fix']}'")
    lines += ["pip freeze > requirements.txt", "```", "",
              "_Auto-opened by dep_audit.py — review before merging._"]
    return "\n".join(lines)


def open_github_pr(vulns: list[dict]) -> str | None:
    """Create a GitHub PR with upgrade suggestions. Returns PR URL or error string."""
    branch = f"deps/security-audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    try:
        # Create branch
        subprocess.run(["git", "checkout", "-b", branch], cwd=str(PROJECT_ROOT),
                       capture_output=True, timeout=15)
        # No actual code changes — PR is informational with manual upgrade steps
        # Create an empty commit to open the PR
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m",
             f"security: dep audit {datetime.now(timezone.utc).strftime('%Y-%m-%d')} ({len(vulns)} vulns)"],
            cwd=str(PROJECT_ROOT), capture_output=True, timeout=15,
        )
        subprocess.run(["git", "push", "origin", branch], cwd=str(PROJECT_ROOT),
                       capture_output=True, timeout=30)

        body = format_pr_body(vulns)
        result = subprocess.run(
            ["gh", "pr", "create",
             "--title", f"security: {len(vulns)} HIGH/CRITICAL dependency vulnerabilities",
             "--body", body,
             "--label", "security",
             "--head", branch],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
        )
        # Checkout back
        subprocess.run(["git", "checkout", "-"], cwd=str(PROJECT_ROOT),
                       capture_output=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        return f"gh pr create failed: {result.stderr[:200]}"
    except Exception as e:
        return f"PR creation exception: {e}"


def write_last_json(status: str, detail: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "job": "dep_audit",
        "status": status,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    (STATE_DIR / "dep_audit.last.json").write_text(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Dependency vulnerability audit + auto-PR")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, no PR")
    parser.add_argument("--min-severity", default="HIGH", choices=SEVERITY_ORDER[2:])
    args = parser.parse_args()

    if not REQUIREMENTS_FILE.exists():
        logger.error(f"requirements.txt not found: {REQUIREMENTS_FILE}")
        write_last_json("failed", "requirements.txt not found")
        return 1

    logger.info(f"Running pip-audit on {REQUIREMENTS_FILE}...")
    raw = run_pip_audit(REQUIREMENTS_FILE)
    all_vulns = parse_pip_audit_output(raw)
    vulns = filter_by_severity(all_vulns, args.min_severity)

    if not vulns:
        logger.info(f"✅ No {args.min_severity}+ vulnerabilities found ({len(all_vulns)} total scanned)")
        write_last_json("ok", f"0 high/critical vulns ({len(all_vulns)} total)")
        return 0

    logger.warning(f"⚠️ {len(vulns)} {args.min_severity}+ vulnerabilities found")
    for v in vulns:
        logger.warning(f"  {v['package']} {v['version']} → {v['severity']} ({v['cve']})")

    if args.dry_run:
        logger.info("Dry-run: skipping PR creation")
        write_last_json("ok", f"dry-run: {len(vulns)} vulns found, no PR")
        return 0

    pr_url = open_github_pr(vulns)
    if pr_url and pr_url.startswith("https://"):
        logger.info(f"✅ PR opened: {pr_url}")
        write_last_json("ok", f"{len(vulns)} vulns → PR {pr_url}")
    else:
        logger.error(f"PR creation failed: {pr_url}")
        write_last_json("failed", f"PR failed: {pr_url}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
````

- [ ] **Step 3.4: Create scripts/tests/ directory and run tests**

```bash
mkdir -p scripts/tests
touch scripts/tests/__init__.py
python -m pytest scripts/tests/test_dep_audit.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 3.5: Register dep_audit in job_registry.json**

Add to `~/.agent/decisions/job_registry.json` inside `"jobs"`:

```json
"dep_audit": {
  "host": "Nuzantara",
  "type": "openclaw",
  "schedule_seconds": 604800,
  "staleness_threshold_s": 691200,
  "restart_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/dep_audit.py",
  "test_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/dep_audit.py --dry-run"
}
```

- [ ] **Step 3.6: Smoke test**

```bash
python3 scripts/dep_audit.py --dry-run 2>&1 | tail -5
```

Expected: `No HIGH+ vulnerabilities found` or `dry-run: N vulns found, no PR`.

- [ ] **Step 3.7: Commit**

```bash
git add scripts/dep_audit.py scripts/tests/test_dep_audit.py scripts/tests/__init__.py
git commit -m "feat(automation): dep_audit — pip-audit scan with auto-PR on HIGH/CRITICAL vulns"
```

---

## Task 4 — RAG canary on Pro: register + write .last.json

**Files:**

- Modify: `scripts/rag_canary.py` (add `.last.json` write)
- Modify: `~/.agent/decisions/job_registry.json`

- [ ] **Step 4.1: Check what rag_canary.py currently writes**

```bash
grep -n "last_run\|write\|json\|state" scripts/rag_canary.py | head -20
```

Expected: shows it writes `scripts/.rag_canary/last_run.json` but NOT `~/.agent/decisions/state/rag_canary_pro.last.json`.

- [ ] **Step 4.2: Write the failing test**

Create `scripts/tests/test_rag_canary_state.py`:

```python
"""Test that rag_canary writes sentinel-compatible .last.json."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import rag_canary


class TestRagCanaryLastJson(unittest.TestCase):
    def test_write_sentinel_state_ok(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            state_dir = Path(d)
            rag_canary.write_sentinel_state("ok", "5/5 queries passed", state_dir=state_dir)
            f = state_dir / "rag_canary_pro.last.json"
            self.assertTrue(f.exists())
            data = json.loads(f.read_text())
            self.assertEqual(data["job"], "rag_canary_pro")
            self.assertEqual(data["status"], "ok")

    def test_write_sentinel_state_failed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            state_dir = Path(d)
            rag_canary.write_sentinel_state("failed", "drift detected", state_dir=state_dir)
            f = state_dir / "rag_canary_pro.last.json"
            data = json.loads(f.read_text())
            self.assertEqual(data["status"], "failed")
```

- [ ] **Step 4.3: Run test to verify it fails**

```bash
python -m pytest scripts/tests/test_rag_canary_state.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'rag_canary' has no attribute 'write_sentinel_state'`

- [ ] **Step 4.4: Add write_sentinel_state() to rag_canary.py**

After the `RESULTS_FILE` constant block (around line 32), add:

```python
SENTINEL_STATE_DIR = Path.home() / ".agent" / "decisions" / "state"


def write_sentinel_state(
    status: str,
    detail: str = "",
    state_dir: Path | None = None,
) -> None:
    """Write Sentinel-compatible .last.json for this job."""
    target_dir = state_dir or SENTINEL_STATE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job": "rag_canary_pro",
        "status": status,  # "ok" | "failed"
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    import json as _json
    (target_dir / "rag_canary_pro.last.json").write_text(_json.dumps(payload, indent=2))
```

Then find `if __name__ == "__main__"` or the main result-saving block, and call `write_sentinel_state()`:

```python
    # After writing last_run.json
    overall_ok = (drift_ok if args.drift_only else True) and (golden_ok if args.golden_only else True)
    write_sentinel_state(
        "ok" if overall_ok else "failed",
        detail=f"drift={'ok' if drift_ok else 'FAIL'} golden={'ok' if golden_ok else 'FAIL'}",
    )
```

(Adjust variable names to match what's actually in the file — the logic mirrors whatever `main()` already returns.)

- [ ] **Step 4.5: Run tests**

```bash
python -m pytest scripts/tests/test_rag_canary_state.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 4.6: Register rag_canary_pro in job_registry.json**

```json
"rag_canary_pro": {
  "host": "Nuzantara",
  "type": "openclaw",
  "schedule_seconds": 21600,
  "staleness_threshold_s": 28800,
  "restart_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/rag_canary.py",
  "test_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/rag_canary.py --golden-only --verbose"
}
```

- [ ] **Step 4.7: Run canary once to verify state file is created**

```bash
python3 scripts/rag_canary.py --golden-only 2>&1 | tail -5
cat ~/.agent/decisions/state/rag_canary_pro.last.json
```

Expected: JSON with `"status": "ok"` or `"failed"`.

- [ ] **Step 4.8: Commit**

```bash
git add scripts/rag_canary.py scripts/tests/test_rag_canary_state.py
git commit -m "feat(canary): rag_canary_pro writes sentinel .last.json + registered in job_registry"
```

---

## Task 5 — Migration auto-apply in fly-deploy.yml

**Files:**

- Modify: `.github/workflows/fly-deploy.yml`

- [ ] **Step 5.1: Read migration_manager.py to understand apply_migrations() signature**

```bash
grep -n "async def apply\|async def run\|migration" apps/backend-rag/backend/db/migration_manager.py | head -20
```

- [ ] **Step 5.2: Create migration runner script**

Create `apps/backend-rag/scripts/run_migrations.py`:

```python
#!/usr/bin/env python3
"""
CI-safe migration runner. Reads DATABASE_URL from env.
Exits 0 on success, 1 on failure.

Usage:
    PYTHONPATH=. python scripts/run_migrations.py
    PYTHONPATH=. python scripts/run_migrations.py --dry-run  # list pending only
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[Migration %(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("migration_runner")

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main(dry_run: bool = False) -> int:
    from backend.db.migration_manager import MigrationManager

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return 1

    mgr = MigrationManager(database_url=db_url)
    try:
        await mgr.connect()
        pending = await mgr.get_pending_migrations()
        if not pending:
            logger.info("✅ No pending migrations")
            return 0

        logger.info(f"Found {len(pending)} pending migration(s):")
        for m in pending:
            logger.info(f"  → {m}")

        if dry_run:
            logger.info("Dry-run: not applying")
            return 0

        await mgr.apply_migrations()
        logger.info(f"✅ Applied {len(pending)} migration(s)")
        return 0
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1
    finally:
        await mgr.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
```

- [ ] **Step 5.3: Write test for migration runner**

Create `apps/backend-rag/backend/tests/test_migration_runner.py`:

```python
"""Tests for run_migrations.py CLI."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestMigrationRunner(unittest.IsolatedAsyncioTestCase):
    @patch("backend.db.migration_manager.MigrationManager")
    async def test_no_pending_returns_0(self, MockMgr: MagicMock) -> None:
        inst = AsyncMock()
        inst.get_pending_migrations = AsyncMock(return_value=[])
        MockMgr.return_value = inst

        import scripts.run_migrations as runner
        result = await runner.main()
        self.assertEqual(result, 0)

    @patch.dict("os.environ", {}, clear=True)
    async def test_missing_database_url_returns_1(self) -> None:
        import importlib
        import scripts.run_migrations as runner
        importlib.reload(runner)
        result = await runner.main()
        self.assertEqual(result, 1)
```

- [ ] **Step 5.4: Run test to verify it fails**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m pytest backend/tests/test_migration_runner.py -v 2>&1 | head -20
```

Expected: import errors or `AttributeError: 'MigrationManager' has no 'get_pending_migrations'` — check what methods exist and adjust.

- [ ] **Step 5.5: Add migration job to fly-deploy.yml**

Add a new job `run-migrations` between `pre-deploy-gate` and `deploy`:

```yaml
run-migrations:
  name: Apply pending DB migrations
  needs: pre-deploy-gate
  runs-on: ubuntu-latest

  steps:
    - uses: actions/checkout@v4

    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"
        cache: "pip"
        cache-dependency-path: apps/backend-rag/requirements.txt

    - name: Install dependencies
      run: |
        cd apps/backend-rag
        pip install --upgrade pip
        pip install -r requirements.txt -q

    - name: Run migrations (idempotent, safe to re-run)
      run: |
        cd apps/backend-rag
        PYTHONPATH=. python scripts/run_migrations.py
      env:
        DATABASE_URL: ${{ secrets.DATABASE_URL }}

    - name: Verify migration status
      run: |
        cd apps/backend-rag
        PYTHONPATH=. python scripts/run_migrations.py --dry-run
      env:
        DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

Also update the `deploy` job's `needs`:

```yaml
deploy:
  name: Fly.io rolling deploy
  needs: run-migrations # was: pre-deploy-gate
```

- [ ] **Step 5.6: Verify YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/fly-deploy.yml'))" && echo "✅ YAML valid"
```

- [ ] **Step 5.7: Commit**

```bash
git add .github/workflows/fly-deploy.yml apps/backend-rag/scripts/run_migrations.py apps/backend-rag/backend/tests/test_migration_runner.py
git commit -m "feat(ci): auto-apply DB migrations in fly-deploy pipeline before rolling deploy"
```

---

## Task 6 — mypy in Scout + coverage trend tracking

**Files:**

- Modify: `apps/evaluator/core_guardian/scout.py`
- Create: `scripts/coverage_trend.py`
- Modify: `~/.agent/decisions/job_registry.json`

- [ ] **Step 6.1: Check scout.py structure**

```bash
grep -n "def run\|def scan\|def check\|ruff\|mypy\|vulture" apps/evaluator/core_guardian/scout.py | head -30
```

- [ ] **Step 6.2: Write failing test for Scout mypy**

Create `apps/evaluator/core_guardian/tests/test_scout_mypy.py`:

```python
"""Tests for Scout mypy runner."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import scout


class TestScoutMypy(unittest.TestCase):
    @patch("scout.subprocess.run")
    def test_run_mypy_returns_violations(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="backend/app/foo.py:10: error: Incompatible return value type\nFound 1 error in 1 file"
        )
        result = scout.run_mypy(Path("/fake/backend"))
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    @patch("scout.subprocess.run")
    def test_run_mypy_clean_returns_empty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="Success: no issues found")
        result = scout.run_mypy(Path("/fake/backend"))
        self.assertEqual(result, [])
```

- [ ] **Step 6.3: Run test to verify it fails**

```bash
cd apps/evaluator/core_guardian
python -m pytest tests/test_scout_mypy.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'scout' has no attribute 'run_mypy'`

- [ ] **Step 6.4: Add run_mypy() and run_vulture() to scout.py**

Find the section after the existing `run_ruff()` or equivalent function and add:

```python
def run_mypy(backend_dir: Path) -> list[dict]:
    """
    Run mypy on backend/ for type errors.
    Returns list of {file, line, code, message} dicts.
    Non-blocking: failures are logged, not fatal.
    """
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "mypy", "backend/",
             "--ignore-missing-imports", "--no-error-summary",
             "--output", "json"],
            cwd=str(backend_dir),
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONPATH": str(backend_dir)},
        )
        violations = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json as _json
                entry = _json.loads(line)
                if entry.get("severity") in ("error", "warning"):
                    violations.append({
                        "file": entry.get("file", ""),
                        "line": entry.get("line", 0),
                        "code": entry.get("error_code", "mypy"),
                        "message": entry.get("message", ""),
                    })
            except Exception:
                # Fallback: plain text mypy output
                if ": error:" in line or ": warning:" in line:
                    violations.append({"file": line.split(":")[0], "line": 0,
                                       "code": "mypy", "message": line})
        return violations
    except Exception as e:
        logger.warning(f"mypy failed: {e}")
        return []


def run_vulture(backend_dir: Path, min_confidence: int = 80) -> list[dict]:
    """
    Run vulture for dead code detection.
    Returns list of {file, line, type, message} dicts.
    Only reports items with >= min_confidence.
    """
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "vulture", "backend/",
             "--min-confidence", str(min_confidence)],
            cwd=str(backend_dir),
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONPATH": str(backend_dir)},
        )
        violations = []
        for line in result.stdout.strip().splitlines():
            # Format: path/file.py:42: unused function 'foo' (80% confidence)
            if "%" not in line:
                continue
            parts = line.split(":")
            if len(parts) < 3:
                continue
            violations.append({
                "file": parts[0],
                "line": int(parts[1]) if parts[1].isdigit() else 0,
                "type": "dead_code",
                "message": ":".join(parts[2:]).strip(),
            })
        return violations
    except Exception as e:
        logger.warning(f"vulture failed: {e}")
        return []
```

Also make sure both functions are called in Scout's main scan loop and their findings appended to the Scout report.

- [ ] **Step 6.5: Create scripts/coverage_trend.py**

```python
#!/usr/bin/env python3
"""
Coverage Trend Tracker — records pytest passed count over time.
Detects regressions and writes to .agent/decisions/coverage_trend.json.

Usage:
    python3 scripts/coverage_trend.py [--passed N]
    # --passed N: manually specify; else reads from .agent/decisions/baseline.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_FILE = PROJECT_ROOT / ".agent" / "decisions" / "baseline.json"
TREND_FILE = PROJECT_ROOT / ".agent" / "decisions" / "coverage_trend.json"
STATE_DIR = Path.home() / ".agent" / "decisions" / "state"
MAX_HISTORY = 30  # keep last 30 entries


def read_current_passed() -> int | None:
    """Read passed count from baseline.json (written by Watchdog)."""
    if not BASELINE_FILE.exists():
        return None
    try:
        data = json.loads(BASELINE_FILE.read_text())
        return data.get("passed")
    except Exception:
        return None


def load_trend() -> list[dict]:
    if not TREND_FILE.exists():
        return []
    try:
        return json.loads(TREND_FILE.read_text())
    except Exception:
        return []


def append_entry(trend: list[dict], passed: int) -> list[dict]:
    trend.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
    })
    return trend[-MAX_HISTORY:]


def detect_regression(trend: list[dict]) -> str | None:
    """Return warning message if last entry is lower than 7-entry rolling avg."""
    if len(trend) < 3:
        return None
    window = trend[-8:-1]  # previous 7 entries
    if not window:
        return None
    avg = sum(e["passed"] for e in window) / len(window)
    current = trend[-1]["passed"]
    if current < avg - 5:  # tolerance: 5 tests
        return f"Regression: {current} < avg {avg:.0f} (delta={current - avg:.0f})"
    return None


def write_sentinel_state(status: str, detail: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "job": "coverage_trend",
        "status": status,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    (STATE_DIR / "coverage_trend.last.json").write_text(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--passed", type=int, help="Override passed count (for testing)")
    args = parser.parse_args()

    passed = args.passed if args.passed is not None else read_current_passed()
    if passed is None:
        print("No passed count available — skipping", file=sys.stderr)
        write_sentinel_state("skipped", "baseline.json missing or no passed count")
        return 0

    trend = load_trend()
    trend = append_entry(trend, passed)
    TREND_FILE.write_text(json.dumps(trend, indent=2))

    regression = detect_regression(trend)
    if regression:
        print(f"⚠️  {regression}", file=sys.stderr)
        write_sentinel_state("failed", regression)
        return 1

    print(f"✅ Coverage trend OK — {passed} passed ({len(trend)} entries tracked)")
    write_sentinel_state("ok", f"{passed} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.6: Write test for coverage_trend.py**

Create `scripts/tests/test_coverage_trend.py`:

```python
"""Tests for coverage_trend.py."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import coverage_trend as ct


class TestCoverageTrend(unittest.TestCase):
    def test_append_entry(self) -> None:
        trend = ct.append_entry([], 3900)
        self.assertEqual(len(trend), 1)
        self.assertEqual(trend[0]["passed"], 3900)

    def test_max_history(self) -> None:
        trend = []
        for i in range(35):
            trend = ct.append_entry(trend, 3900 + i)
        self.assertEqual(len(trend), ct.MAX_HISTORY)

    def test_no_regression_stable(self) -> None:
        trend = [{"ts": "2026-01-01", "passed": 3900 + i} for i in range(8)]
        result = ct.detect_regression(trend)
        self.assertIsNone(result)

    def test_detects_regression(self) -> None:
        trend = [{"ts": "2026-01-01", "passed": 3900} for _ in range(8)]
        trend.append({"ts": "2026-01-02", "passed": 3800})  # 100 drop
        result = ct.detect_regression(trend)
        self.assertIsNotNone(result)
        self.assertIn("Regression", result)

    def test_write_sentinel_state(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ct.STATE_DIR = Path(d)
            ct.write_sentinel_state("ok", "test")
            f = Path(d) / "coverage_trend.last.json"
            data = json.loads(f.read_text())
            self.assertEqual(data["status"], "ok")
```

- [ ] **Step 6.7: Run all new tests**

```bash
python -m pytest scripts/tests/test_coverage_trend.py apps/evaluator/core_guardian/tests/test_scout_mypy.py -v
```

Expected: All PASS.

- [ ] **Step 6.8: Register coverage_trend in job_registry.json**

```json
"coverage_trend": {
  "host": "Nuzantara",
  "type": "shell",
  "schedule_seconds": 86400,
  "staleness_threshold_s": 93600,
  "restart_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/coverage_trend.py"
}
```

- [ ] **Step 6.9: Commit**

```bash
git add apps/evaluator/core_guardian/scout.py apps/evaluator/core_guardian/tests/test_scout_mypy.py scripts/coverage_trend.py scripts/tests/test_coverage_trend.py
git commit -m "feat(scout): add mypy + vulture runners; feat(trend): coverage trend tracker with regression detection"
```

---

## Task 7 — Hook all new jobs into Sentinel state monitoring

**Files:**

- Modify: `~/.agent/decisions/job_registry.json` (staleness thresholds)
- Verify: Sentinel reads `.last.json` files correctly

- [ ] **Step 7.1: Verify Sentinel reads state files**

```bash
grep -n "last.json\|collect_state\|state_dir\|staleness" /Users/nuzantara/scripts/nuzantara-sentinel.py | head -20
```

Expected: Sentinel reads `STATE_DIR/*.last.json` — all our new jobs write to that exact path.

- [ ] **Step 7.2: Run dep_audit dry-run and verify Sentinel can read its state**

```bash
python3 scripts/dep_audit.py --dry-run
cat ~/.agent/decisions/state/dep_audit.last.json
```

Expected: Valid JSON with `"status": "ok"`.

- [ ] **Step 7.3: Run coverage_trend and verify**

```bash
python3 scripts/coverage_trend.py
cat ~/.agent/decisions/state/coverage_trend.last.json
```

Expected: Valid JSON with `"status": "ok"`.

- [ ] **Step 7.4: Run rag_canary --golden-only and verify**

```bash
python3 scripts/rag_canary.py --golden-only 2>&1 | tail -3
cat ~/.agent/decisions/state/rag_canary_pro.last.json
```

Expected: State file written.

- [ ] **Step 7.5: Verify Surgeon writes state on next fix (dry-run)**

```bash
# Pick a small file with a known ruff violation and dry-run
grep -rn "DTZ005\|ANN001" apps/backend-rag/backend/app/routers/ --include="*.py" -l | head -1
```

Then:

```bash
cd apps/evaluator/core_guardian
python surgeon.py "Fix DTZ005 dry-run" "backend/app/routers/found_file.py" DTZ005 --dry-run
cat ~/.agent/decisions/state/core_guardian.last.json
```

- [ ] **Step 7.6: Update job_registry.json with all new entries**

Full set of additions to `~/.agent/decisions/job_registry.json`:

```json
"dep_audit": {
  "host": "Nuzantara",
  "type": "shell",
  "schedule_seconds": 604800,
  "staleness_threshold_s": 691200,
  "restart_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/dep_audit.py",
  "test_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/dep_audit.py --dry-run"
},
"rag_canary_pro": {
  "host": "Nuzantara",
  "type": "shell",
  "schedule_seconds": 21600,
  "staleness_threshold_s": 28800,
  "restart_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/rag_canary.py",
  "test_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/rag_canary.py --golden-only"
},
"coverage_trend": {
  "host": "Nuzantara",
  "type": "shell",
  "schedule_seconds": 86400,
  "staleness_threshold_s": 93600,
  "restart_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/coverage_trend.py"
}
```

- [ ] **Step 7.7: Commit registry**

```bash
git add ~/.agent/decisions/job_registry.json 2>/dev/null || true
git commit -m "chore(registry): add dep_audit + rag_canary_pro + coverage_trend to job registry"
```

---

## Self-Review

### Spec Coverage

| Gap                          | Task   | Status |
| ---------------------------- | ------ | ------ |
| Surgeon merge-bot            | Task 1 | ✅     |
| Watchdog→Surgeon trigger     | Task 2 | ✅     |
| dep_audit auto-PR            | Task 3 | ✅     |
| RAG canary on Pro            | Task 4 | ✅     |
| Migration auto-apply in CI   | Task 5 | ✅     |
| mypy in Scout                | Task 6 | ✅     |
| vulture dead code            | Task 6 | ✅     |
| Coverage trend               | Task 6 | ✅     |
| Sentinel integration for ALL | Task 7 | ✅     |

### Notes

- Tasks 1–2 modify existing autonomous agents: test with `--dry-run` before committing to live worktrees
- Task 5 requires `DATABASE_URL` to be in GitHub Actions secrets — verify before pushing
- Task 3 requires `gh` CLI configured and authenticated for PR creation
- All new `.last.json` files follow the Sentinel pattern: `{"job", "status", "detail", "ts"}`
