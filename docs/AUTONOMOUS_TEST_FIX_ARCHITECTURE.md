# Autonomous Test-Fix-Retest Loop Architecture for Nuzantara

**Date:** 2026-03-08
**Author:** AI Architecture Research
**Status:** Design Proposal

---

## 1. Research Findings

### 1.1 Comparative Analysis of Existing Systems

| System                       | Approach                                                                                  | Strengths                                                                                                       | Weaknesses                                                                                 | Nuzantara Fit                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| **SWE-agent** (Princeton)    | Agent-Computer Interface for GitHub issues. Custom shell + editor commands. NeurIPS 2024. | 79.2% on SWE-bench Verified (with Claude Opus 4.5). Configurable via single YAML.                               | Designed for single-issue resolution, not continuous loops. No built-in coverage tracking. | HIGH — architecture pattern is directly applicable |
| **LIVE-SWE-agent**           | Self-evolving scaffold that improves its own implementation while solving problems.       | Outperforms manually designed agents. Autonomous scaffold evolution.                                            | Experimental, complex to integrate.                                                        | MEDIUM — self-improvement concept valuable         |
| **Qodo Cover** (ex-CodiumAI) | Autonomous test generation agent. Implements Meta's TestGen-LLM.                          | Generates tests, validates they run+pass+increase coverage. Only keeps valuable tests.                          | Focused on test generation only, not fix generation. $30/user/month.                       | HIGH — direct coverage improvement                 |
| **Aider**                    | AI pair programming in terminal. Git-aware, auto-commits.                                 | Excellent git integration, diff-based edits, supports Claude/GPT/DeepSeek. CLI-driven — perfect for automation. | No built-in test loop orchestration. Manual invocation.                                    | HIGH — best fix-generation agent for CLI pipelines |
| **OpenHands** (ex-OpenDevin) | Full autonomous software engineer. Docker sandbox. MIT license.                           | Complete dev environment (code, terminal, browser). 2.1K+ contributions.                                        | Heavy setup (Docker required). Overkill for targeted test-fix.                             | LOW — too heavyweight for our use case             |
| **Claude Code**              | Native CLI with `/test` command, Ralph Loop plugin for autonomous iteration.              | Built-in test→fix→retest loop. Browser automation. Context-aware. Already our primary tool.                     | Token-intensive for large codebases.                                                       | CRITICAL — our primary execution engine            |
| **Sourcegraph Cody**         | RAG-based codebase comprehension. 1M token context (Claude Sonnet 4).                     | Best codebase understanding. Multi-repo search.                                                                 | Not autonomous — assistive only. Enterprise pricing.                                       | LOW — we already have codebase context             |
| **Sweep AI**                 | Autonomous PR generation from GitHub issues.                                              | End-to-end issue→PR automation.                                                                                 | Shut down / limited availability.                                                          | SKIP                                               |

### 1.2 Key Academic Findings (2025-2026)

**Test-in-the-Loop Pipelines** (Survey: arxiv 2506.23749):

- Alternate generation with unit tests, using each failure as an oracle
- Analysis-augmented pipelines invoke compilers, debuggers, security analyzers to feed diagnostics
- RAG-in-the-Loop keeps LLM frozen, inserts deterministic retrieval between generations

**LLMLOOP** (ICSME 2025):

- Iterative feedback loops with multiple analysis methods
- Dedicated prompt per feedback type (lint error, test failure, type error)
- Demonstrated significant improvement over single-pass generation

**EDDOps** (Evaluation-Driven Development and Operations):

- Adapts TDD/BDD to LLM agents
- Evaluation evidence (offline + online) governs targeted changes
- Continuous feedback loops with dynamic evaluation triggers

**AgentCoder** (Multi-agent):

- Specialized roles: programmer agent, test designer agent, execution agent
- Role specialization dramatically improves fix quality
- Directly maps to OpenClaw's multi-agent architecture

### 1.3 The Ralph Loop Pattern (Claude Code Native)

The most relevant pattern for Nuzantara is Claude Code's own **Ralph Loop**:

1. Define success criteria upfront (test plan)
2. Claude Code attempts the task
3. Ralph Wiggum checks if criteria are met
4. If not → restart with same task + previous attempt context
5. Repeat until done or iteration limit hit

**Key insight:** This is already built into our toolchain. The architecture should orchestrate Ralph Loops at scale via OpenClaw, not reinvent them.

### 1.4 Critical Anti-Pattern Research

| Anti-Pattern             | Description                                   | Mitigation                                                                                      |
| ------------------------ | --------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **Infinite Loops**       | Fix A breaks B, fix B breaks A                | Max 3 fix attempts per failure. Global iteration cap. Dependency graph tracking.                |
| **Cosmetic Fixes**       | `# type: ignore`, `noqa`, suppressing errors  | Blocklist of suppression patterns. Diff review rejects suppressions.                            |
| **Test Weakening**       | Modifying assertions to match broken behavior | Tests are READ-ONLY in fix phase. Separate test-generation phase.                               |
| **Context Explosion**    | LLM chokes on 5000-line files                 | AST-based context extraction. Only send relevant functions + imports. Max 500 lines per prompt. |
| **Flaky Test Confusion** | Random failures treated as real bugs          | Run each test 3x before classifying as failure. Tag known flaky tests.                          |
| **Regression Cascade**   | One fix causes 10 new failures                | Bisect-and-revert: if fix causes >2 new failures, auto-revert.                                  |

---

## 2. Architecture Design

### 2.1 System Overview

```
                    NIGHTLY CRON (03:00 WITA)
                           |
                    [OpenClaw Gateway]
                           |
                    [Lobster Pipeline]
                           |
         +---------+-------+-------+---------+
         |         |               |         |
     PHASE 1    PHASE 2        PHASE 3    PHASE 4
      SCAN        FIX           VERIFY     REPORT
    (pytest)   (AI agents)    (full run)  (commit+PR)
         |         |               |         |
    [Coverage]  [Coder Agent]  [Regression] [Telegram]
    [Classify]  [Claude Code]  [Bisect]    [Learnings]
    [Queue]     [Aider]        [Revert]    [Git Push]
```

### 2.2 Phase 1: SCAN (Coverage Baseline + Failure Classification)

**Agent:** None (deterministic shell commands)
**Duration:** ~5 minutes
**Trigger:** Cron 03:00 WITA or manual `openclaw cron run <id>`

#### Step 1a: Run Full Test Suite with Coverage

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/ \
  --cov=backend \
  --cov-report=json:/tmp/nuz-coverage.json \
  --cov-report=term-missing \
  --tb=json \
  --json-report --json-report-file=/tmp/nuz-test-results.json \
  -q --timeout=120 \
  2>&1 | tee /tmp/nuz-test-output.log
```

**Required packages:** `pytest-cov`, `pytest-json-report`, `pytest-timeout`

#### Step 1b: Parse & Classify Failures

A Python script (`scripts/classify_test_failures.py`) processes the JSON output:

```python
"""
Failure Classification Engine

Reads pytest JSON report and classifies each failure into:
- IMPORT: ModuleNotFoundError, ImportError
- SYNTAX: SyntaxError, IndentationError
- TYPE: TypeError, AttributeError (wrong interface)
- LOGIC: AssertionError (wrong result)
- INTEGRATION: ConnectionError, TimeoutError, database errors
- FIXTURE: fixture not found, setup errors
- FLAKY: passes on re-run (detected by 3x retry)

Output: /tmp/nuz-failure-queue.json
Priority: IMPORT > SYNTAX > FIXTURE > TYPE > LOGIC > INTEGRATION > FLAKY
"""

import json
from dataclasses import dataclass
from typing import Literal
from pathlib import Path

FailureType = Literal["IMPORT", "SYNTAX", "FIXTURE", "TYPE", "LOGIC", "INTEGRATION", "FLAKY"]

PRIORITY = {"IMPORT": 1, "SYNTAX": 2, "FIXTURE": 3, "TYPE": 4, "LOGIC": 5, "INTEGRATION": 6, "FLAKY": 99}

ERROR_PATTERNS = {
    "IMPORT": ["ModuleNotFoundError", "ImportError", "No module named"],
    "SYNTAX": ["SyntaxError", "IndentationError", "invalid syntax"],
    "FIXTURE": ["fixture", "ERRORS", "SetupError", "not found"],
    "TYPE": ["TypeError", "AttributeError", "has no attribute", "unexpected keyword"],
    "LOGIC": ["AssertionError", "assert ", "!=", "Expected"],
    "INTEGRATION": ["ConnectionError", "TimeoutError", "OperationalError", "ConnectionRefusedError"],
}

@dataclass
class TestFailure:
    test_id: str           # e.g., "tests/unit/test_foo.py::test_bar"
    file_path: str         # source file under test
    test_file: str         # test file path
    error_type: FailureType
    error_message: str     # first 500 chars of traceback
    priority: int
    fix_attempts: int = 0
    status: str = "pending"  # pending | fixing | fixed | escalated

def classify(test_report_path: str) -> list[TestFailure]:
    with open(test_report_path) as f:
        report = json.load(f)

    failures = []
    for test in report.get("tests", []):
        if test.get("outcome") != "failed":
            continue

        longrepr = test.get("call", {}).get("longrepr", "")
        error_type = "LOGIC"  # default

        for etype, patterns in ERROR_PATTERNS.items():
            if any(p in longrepr for p in patterns):
                error_type = etype
                break

        # Extract source file from test path (convention: test_foo.py tests foo.py)
        test_path = test["nodeid"].split("::")[0]
        source_path = infer_source_from_test(test_path)

        failures.append(TestFailure(
            test_id=test["nodeid"],
            file_path=source_path,
            test_file=test_path,
            error_type=error_type,
            error_message=longrepr[:500],
            priority=PRIORITY[error_type],
        ))

    # Sort by priority (lowest number = highest priority)
    failures.sort(key=lambda f: f.priority)
    return failures

def infer_source_from_test(test_path: str) -> str:
    """Infer source file from test file path.
    tests/unit/services/test_crm.py -> backend/services/crm.py
    tests/unit/routers/test_auth.py -> backend/routers/auth.py
    """
    path = test_path.replace("backend/tests/unit/", "backend/")
    path = path.replace("test_", "")
    return path
```

#### Step 1c: Coverage Gap Analysis

```python
"""
Coverage Gap Analyzer

Reads pytest-cov JSON and identifies:
1. Files with <50% coverage (critical gaps)
2. Uncovered branches in high-import-count modules
3. Public API endpoints with no tests
4. Recently changed files (git log) with low coverage

Output: /tmp/nuz-coverage-gaps.json
"""

def analyze_coverage_gaps(
    coverage_path: str = "/tmp/nuz-coverage.json",
    git_log_days: int = 30,
) -> dict:
    with open(coverage_path) as f:
        cov = json.load(f)

    gaps = []
    for filepath, data in cov.get("files", {}).items():
        pct = data.get("summary", {}).get("percent_covered", 100)
        missing_lines = data.get("missing_lines", [])
        missing_branches = data.get("missing_branches", [])

        if pct < 80:  # Target: 80%+ coverage
            gaps.append({
                "file": filepath,
                "coverage_pct": pct,
                "missing_lines": len(missing_lines),
                "missing_branches": len(missing_branches),
                "priority": "critical" if pct < 50 else "high" if pct < 70 else "medium",
            })

    gaps.sort(key=lambda g: g["coverage_pct"])
    return {"gaps": gaps, "total_files": len(cov.get("files", {})), "gap_count": len(gaps)}
```

#### Phase 1 Output

```json
{
  "scan_id": "2026-03-08T03:00:00Z",
  "coverage": {
    "total_pct": 42.3,
    "files_analyzed": 236,
    "critical_gaps": 15,
    "high_gaps": 45,
    "medium_gaps": 30
  },
  "failures": {
    "total": 448,
    "by_type": {
      "IMPORT": 180,
      "SYNTAX": 12,
      "FIXTURE": 85,
      "TYPE": 62,
      "LOGIC": 78,
      "INTEGRATION": 25,
      "FLAKY": 6
    }
  },
  "queue": [
    {"test_id": "...", "error_type": "IMPORT", "priority": 1},
    ...
  ]
}
```

---

### 2.3 Phase 2: FIX (AI-Driven Repair)

**Agent:** OpenClaw `coder` agent (Claude Sonnet 4.6)
**Duration:** ~60-120 minutes (budget: 50 fixes per run)
**Branch:** `auto-fix/YYYY-MM-DD` (isolated)

#### Strategy: Batch by Error Type

Instead of fixing failures one by one, group by root cause:

```
IMPORT errors (180 failures)
  → Most are caused by ~15 missing/renamed modules
  → Fix the import, not 180 individual tests
  → 1 fix can resolve 10-30 failures

FIXTURE errors (85 failures)
  → ~8 broken fixtures cause cascading failures
  → Fix the fixture definition once

TYPE errors (62 failures)
  → Interface changes not propagated
  → Fix the source, not the tests

LOGIC errors (78 failures)
  → Actual behavioral bugs — most valuable to fix
  → But also most risky — need careful review
```

#### Fix Execution Flow

````
For each failure_group (sorted by priority):
  1. CONTEXT GATHER
     - Read test file (only the failing test function)
     - Read source file (only the relevant function via AST)
     - Read import chain (max 2 levels deep)
     - Read related passing tests (for behavior reference)
     - Total context budget: max 4000 tokens

  2. FIX GENERATION (via OpenClaw coder agent)
     Prompt template:
     """
     You are fixing a failing test in the Nuzantara backend.

     ## Error Classification: {error_type}

     ## Failing Test
     ```python
     {test_code}
     ```

     ## Error Output
     ```
     {error_message}
     ```

     ## Source Code Under Test
     ```python
     {source_code}
     ```

     ## Rules
     - Fix the SOURCE code, never the test (unless test has obvious typo)
     - Never add `# type: ignore`, `noqa`, or suppress errors
     - Never weaken assertions
     - Keep changes minimal — smallest diff that fixes the test
     - Maintain existing code style and patterns
     - If the fix requires understanding broader context you don't have, respond with ESCALATE

     ## Output
     Respond with ONLY the corrected source code, or ESCALATE with reason.
     """

  3. APPLY & VALIDATE
     - Apply fix to source file
     - Run ONLY the affected test(s): `pytest {test_id} -x -q`
     - If PASS:
       - Run related tests (same file): `pytest {test_file} -q`
       - If all pass → STAGE (git add)
       - If regression → REVERT fix, try next candidate
     - If FAIL:
       - Attempt 2: re-prompt with error output from attempt 1
       - Attempt 3: re-prompt with different strategy hint
       - If still fails → ESCALATE (mark as "needs human review")

  4. ITERATION LIMITS
     - Max 3 fix attempts per individual test
     - Max 50 fixes per nightly run
     - Max 120 minutes total runtime
     - If any single fix takes >5 minutes of LLM time → skip
````

#### OpenClaw Agent Invocation

```bash
# For each fix batch
openclaw agent --agent coder \
  --session-id "autofix-$(date +%Y%m%d-%H%M%S)" \
  --timeout 300 \
  --message "$(cat /tmp/nuz-fix-prompt-001.txt)" \
  --json 2>&1 | tee /tmp/nuz-fix-result-001.json
```

#### Why Coder Agent (not main)

- **Isolated workspace** — no CRM, no client comms, no intel tools
- **Sandbox off** — can execute pytest, ruff, git directly
- **No heartbeat** — won't waste tokens on idle pings
- **Claude Sonnet 4.6** — fast enough for fix generation, smart enough for logic bugs

---

### 2.4 Phase 3: VERIFY (Regression Check)

**Agent:** None (deterministic shell commands)
**Duration:** ~10 minutes

```bash
# Step 1: Run full test suite with all staged fixes
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/ \
  --cov=backend \
  --cov-report=json:/tmp/nuz-coverage-after.json \
  --tb=json \
  --json-report --json-report-file=/tmp/nuz-test-results-after.json \
  -q --timeout=120

# Step 2: Compare before/after
python3 scripts/compare_test_results.py \
  /tmp/nuz-test-results.json \
  /tmp/nuz-test-results-after.json \
  --output /tmp/nuz-regression-report.json
```

#### Regression Detection Logic

```python
def check_regressions(before_path: str, after_path: str) -> dict:
    """Compare before/after test results.

    A regression is: a test that PASSED before but FAILS after.
    This is DIFFERENT from a test that failed before and still fails.
    """
    before = load_test_results(before_path)
    after = load_test_results(after_path)

    before_pass = {t["nodeid"] for t in before if t["outcome"] == "passed"}
    after_fail = {t["nodeid"] for t in after if t["outcome"] == "failed"}

    regressions = before_pass & after_fail  # Tests that went from pass to fail

    if regressions:
        # Bisect: which fix caused the regression?
        # Use git log on the auto-fix branch to find which commit broke it
        return {
            "regressions": list(regressions),
            "action": "BISECT_AND_REVERT",
            "count": len(regressions),
        }

    # Calculate improvement
    before_fail = {t["nodeid"] for t in before if t["outcome"] == "failed"}
    after_pass = {t["nodeid"] for t in after if t["outcome"] == "passed"}
    newly_fixed = before_fail & after_pass

    return {
        "regressions": [],
        "newly_fixed": list(newly_fixed),
        "fixed_count": len(newly_fixed),
        "action": "PROCEED_TO_COMMIT",
    }
```

#### Bisect & Revert (if regressions detected)

```bash
# Find which commit introduced the regression
git bisect start HEAD auto-fix-start-tag
git bisect good auto-fix-start-tag
git bisect bad HEAD
# For each bisect step:
PYTHONPATH=. pytest {regressed_test_id} -x -q
# Result: identifies the offending commit
git revert {offending_commit} --no-edit
```

---

### 2.5 Phase 4: REPORT & COMMIT

**Agent:** OpenClaw `main` agent (for Telegram delivery)
**Duration:** ~2 minutes

#### Step 4a: Generate Report

```python
report = {
    "date": "2026-03-08",
    "duration_minutes": 47,
    "coverage": {
        "before": 42.3,
        "after": 44.1,
        "delta": "+1.8%",
    },
    "failures": {
        "before": 448,
        "after": 421,
        "fixed": 27,
        "escalated": 8,
        "skipped": 13,
    },
    "fixes_applied": [
        {"test": "test_crm_service.py::test_create_client", "type": "IMPORT", "fix": "updated import path"},
        ...
    ],
    "escalations": [
        {"test": "test_rag_pipeline.py::test_hybrid_search", "reason": "requires Qdrant connection"},
        ...
    ],
    "regressions_reverted": 0,
    "next_run": "2026-03-09T03:00:00+08:00",
}
```

#### Step 4b: Commit & Push

```bash
# Only if there are fixes and zero regressions
cd /path/to/nuzantara
git add -A apps/backend-rag/backend/
git commit -m "fix(auto): resolve ${FIXED_COUNT} test failures [coverage ${BEFORE}% → ${AFTER}%]

Automated test-fix loop run ${DATE}
- Fixed: ${FIXED_COUNT} failures (${IMPORT_COUNT} import, ${TYPE_COUNT} type, ${LOGIC_COUNT} logic)
- Escalated: ${ESCALATED_COUNT} (need human review)
- Regressions: 0 (verified)
- Coverage delta: +${DELTA}%

Co-authored-by: zan-coder <coder@nuzantara.ai>"

git push origin main
```

#### Step 4c: Update Learnings

```bash
# Append successful fix patterns to learnings
cat >> ~/.openclaw/workspace/.learnings/LEARNINGS.md << EOF

## Auto-Fix Run ${DATE}
- Import fixes: most caused by v5.2 refactor moving services/ subdirectories
- Fixture pattern: conftest.py in tests/unit/ missing async_client fixture
- Common type error: Optional[str] vs str | None migration incomplete
EOF
```

#### Step 4d: Telegram Summary

```
Nightly Auto-Fix Report (2026-03-08)

Coverage: 42.3% -> 44.1% (+1.8%)
Tests Fixed: 27/448
Escalated: 8 (need human review)
Regressions: 0

Top fixes:
- 15x import path corrections
- 5x fixture definitions
- 4x type annotation fixes
- 3x logic bug fixes

Duration: 47 min
Next run: tomorrow 03:00 WITA
```

---

## 3. Implementation Roadmap

### MVP (Week 1): Scan + Classify Only

**Goal:** Get structured visibility into test failures. (Note: test debt was cleaned 2026-03-20, 0 failures remain.)
**Effort:** 4 hours.

1. Install pytest plugins:

   ```bash
   pip install pytest-cov pytest-json-report pytest-timeout
   ```

2. Create `scripts/classify_test_failures.py` (from Phase 1 design above)

3. Create `scripts/analyze_coverage_gaps.py` (from Phase 1 design above)

4. Add OpenClaw cron job:

   ```bash
   openclaw cron add \
     --cron "0 3 * * *" \
     --tz Asia/Makassar \
     --exact \
     --name autofix-scan \
     --message "Run the test scan pipeline: cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=json:/tmp/nuz-coverage.json --json-report --json-report-file=/tmp/nuz-test-results.json -q --timeout=120 2>&1 | tail -50; python3 scripts/classify_test_failures.py /tmp/nuz-test-results.json; python3 scripts/analyze_coverage_gaps.py /tmp/nuz-coverage.json"
   ```

5. Review output for 3 nights, calibrate classification accuracy.

**Deliverables:**

- `scripts/classify_test_failures.py`
- `scripts/analyze_coverage_gaps.py`
- Cron job running nightly
- Baseline failure/coverage numbers

---

### Phase 2 (Week 2-3): Import + Fixture Auto-Fix

**Goal:** Fix the easiest 50% of failures (IMPORT + FIXTURE types).
**Effort:** 8-12 hours.

1. Create `scripts/generate_fix_prompts.py`:
   - Groups failures by root cause
   - Extracts minimal context via AST
   - Generates fix prompts for coder agent

2. Create Lobster pipeline `autofix-loop.lobster` (see Section 5)

3. Configure fix validation:
   - Test-only re-run after each fix
   - Regression detection
   - Auto-revert on regression

4. Run manually 3-5 times, tune prompts and thresholds.

**Deliverables:**

- `scripts/generate_fix_prompts.py`
- `workflows/autofix-loop.lobster`
- Import/fixture fix success rate >70%

---

### Phase 3 (Week 4-5): Full Autonomous Loop

**Goal:** All 4 phases running unattended nightly.
**Effort:** 8 hours.

1. Add TYPE and LOGIC fix strategies to prompt templates
2. Implement bisect-and-revert for regressions
3. Add coverage delta tracking (stop when <0.5% improvement per run)
4. Wire Telegram reporting
5. Add to `.learnings/` system for cross-run learning

**Deliverables:**

- Full 4-phase pipeline on cron
- Telegram reports
- Learnings accumulation
- Coverage trending dashboard (JSON files in `/tmp/nuz-coverage-history/`)

---

### Phase 4 (Week 6+): Test Generation

**Goal:** Generate new tests for uncovered code.
**Effort:** Ongoing.

1. Integrate Qodo Cover concepts:
   - Read uncovered functions from coverage report
   - Generate test using LLM + function signature + docstring
   - Validate test passes and increases coverage
   - Only keep tests that add value

2. Use OpenClaw coder agent for generation:

   ```
   "Given this function with 0% coverage, write a pytest test that:
   - Tests the happy path
   - Tests one edge case
   - Tests one error case
   - Uses async fixtures if the function is async
   - Follows existing test patterns in the same directory"
   ```

3. Target: +2-5% coverage per weekly run.

---

## 4. Risk Analysis

### 4.1 Risk Matrix

| Risk                                                   | Probability | Impact   | Mitigation                                                                                                           |
| ------------------------------------------------------ | ----------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| **LLM generates cosmetic fixes** (type: ignore, noqa)  | HIGH        | HIGH     | Blocklist in diff review. Reject any diff containing suppression patterns.                                           |
| **Infinite fix loop** (fix A breaks B, fix B breaks A) | MEDIUM      | HIGH     | Max 3 attempts per test. Global iteration cap of 50 fixes. Dependency graph.                                         |
| **Token cost explosion**                               | MEDIUM      | MEDIUM   | Context budget per fix (4000 tokens). Use Haiku for classification, Sonnet for fixes. Batch similar failures.        |
| **Test weakening** (LLM modifies test assertions)      | MEDIUM      | CRITICAL | Tests are READ-ONLY during fix phase. `git diff --stat` must show 0 changes to `tests/` directory. Hard gate.        |
| **Flaky test false positives**                         | LOW         | MEDIUM   | 3x retry before classifying as failure. Maintain flaky test registry.                                                |
| **Git conflicts with human work**                      | MEDIUM      | LOW      | Auto-fix runs on isolated branch. Merge to main only after verification. Or: run at 03:00 when no humans are coding. |
| **Coder agent timeout**                                | LOW         | LOW      | 5-minute timeout per fix. Skip and move to next.                                                                     |
| **Coverage regression** (fixes reduce coverage)        | LOW         | MEDIUM   | Compare coverage before/after. Reject if coverage decreases.                                                         |

### 4.2 Safety Rails (Non-Negotiable)

```python
SAFETY_RAILS = {
    # Files the auto-fixer MUST NEVER modify
    "readonly_files": [
        "backend/main.py",
        "backend/main_cloud.py",
        "backend/core/config.py",
        "backend/core/dependencies.py",
        "backend/prompts/**",
        "alembic/**",
        "fly.toml",
        "fly.staging.toml",
        "requirements.txt",
    ],

    # Patterns that MUST NOT appear in any generated diff
    "banned_diff_patterns": [
        "# type: ignore",
        "# noqa",
        "# pragma: no cover",
        "# pylint: disable",
        "pytest.skip(",
        "pytest.mark.skip",
        "@unittest.skip",
        "pass  # TODO",
        "raise NotImplementedError",  # unless already there
    ],

    # Directories where tests live (READ-ONLY during fix phase)
    "test_directories": [
        "backend/tests/",
    ],

    # Max lines changed per single fix
    "max_diff_lines": 50,

    # Max files changed per single fix
    "max_files_changed": 3,
}
```

---

## 5. OpenClaw Pipeline YAML (Lobster)

### 5.1 Main Pipeline: `autofix-loop.lobster`

```yaml
name: autofix-loop
description: "Autonomous test-fix-retest loop. Scans failures, applies AI fixes, verifies no regressions, commits and reports."

steps:
  # === PHASE 1: SCAN ===

  - id: create-branch
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara && git checkout -b auto-fix/$(date +%Y-%m-%d) 2>/dev/null || git checkout auto-fix/$(date +%Y-%m-%d) && git pull origin main --rebase 2>/dev/null; echo "BRANCH: auto-fix/$(date +%Y-%m-%d)"'
    timeoutMs: 15000

  - id: scan-tests
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=json:/tmp/nuz-coverage.json --json-report --json-report-file=/tmp/nuz-test-results.json -q --timeout=120 2>&1 | tail -30; echo "EXIT_CODE=$?"'
    timeoutMs: 600000

  - id: classify-failures
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python3 backend/scripts/classify_test_failures.py /tmp/nuz-test-results.json --output /tmp/nuz-failure-queue.json 2>&1'
    timeoutMs: 30000

  - id: coverage-gaps
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python3 backend/scripts/analyze_coverage_gaps.py /tmp/nuz-coverage.json --output /tmp/nuz-coverage-gaps.json 2>&1'
    timeoutMs: 30000

  - id: scan-summary
    command: bash -c 'echo "=== SCAN COMPLETE ===" && cat /tmp/nuz-failure-queue.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Failures: {d.get(\"total\",0)} | IMPORT:{d.get(\"by_type\",{}).get(\"IMPORT\",0)} FIXTURE:{d.get(\"by_type\",{}).get(\"FIXTURE\",0)} TYPE:{d.get(\"by_type\",{}).get(\"TYPE\",0)} LOGIC:{d.get(\"by_type\",{}).get(\"LOGIC\",0)}\")" 2>/dev/null || echo "Classification output not available"'
    timeoutMs: 10000

  # === PHASE 2: FIX (via coder agent) ===

  - id: generate-fix-prompts
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python3 backend/scripts/generate_fix_prompts.py /tmp/nuz-failure-queue.json --max-fixes 30 --output-dir /tmp/nuz-fix-prompts/ 2>&1'
    timeoutMs: 60000

  - id: apply-fixes
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara && for f in /tmp/nuz-fix-prompts/fix-*.txt; do [ -f "$f" ] || continue; echo "--- Fixing: $f ---"; openclaw agent --agent coder --session-id "autofix-$(basename $f .txt)-$(date +%s)" --timeout 300 --message "$(cat $f)" --json 2>&1 | tail -5; done; echo "=== ALL FIXES ATTEMPTED ==="'
    timeoutMs: 7200000

  # === PHASE 3: VERIFY ===

  - id: verify-no-regression
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=json:/tmp/nuz-coverage-after.json --json-report --json-report-file=/tmp/nuz-test-results-after.json -q --timeout=120 2>&1 | tail -30'
    timeoutMs: 600000

  - id: regression-check
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python3 backend/scripts/compare_test_results.py /tmp/nuz-test-results.json /tmp/nuz-test-results-after.json --output /tmp/nuz-regression-report.json 2>&1'
    timeoutMs: 30000

  - id: revert-if-regression
    command: bash -c 'REGRESSIONS=$(cat /tmp/nuz-regression-report.json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get(\"regression_count\",0))" 2>/dev/null || echo "0"); if [ "$REGRESSIONS" -gt "0" ]; then echo "REGRESSIONS DETECTED: $REGRESSIONS — reverting all fixes"; cd /Users/nuzantara/Desktop/nuzantara && git checkout main -- apps/backend-rag/backend/; echo "REVERTED"; else echo "NO REGRESSIONS — safe to merge"; fi'
    condition: $regression-check.completed
    timeoutMs: 30000

  # === PHASE 4: COMMIT & REPORT ===

  - id: merge-to-main
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara && FIXED=$(cat /tmp/nuz-regression-report.json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get(\"fixed_count\",0))" 2>/dev/null || echo "0"); if [ "$FIXED" -gt "0" ]; then git checkout main && git merge auto-fix/$(date +%Y-%m-%d) --no-edit && git push origin main; echo "MERGED: $FIXED fixes"; else echo "NO FIXES TO MERGE"; fi'
    timeoutMs: 30000

  - id: cleanup-branch
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara && git branch -d auto-fix/$(date +%Y-%m-%d) 2>/dev/null; echo "CLEANUP DONE"'
    timeoutMs: 10000

  - id: update-learnings
    command: bash -c 'REPORT=$(cat /tmp/nuz-regression-report.json 2>/dev/null); echo "## Auto-Fix Run $(date +%Y-%m-%d)" >> ~/.openclaw/workspace/.learnings/LEARNINGS.md; echo "$REPORT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"- Fixed: {d.get(\"fixed_count\",0)} tests\n- Escalated: {d.get(\"escalated_count\",0)}\n- Regressions reverted: {d.get(\"regression_count\",0)}\")" >> ~/.openclaw/workspace/.learnings/LEARNINGS.md 2>/dev/null; echo "LEARNINGS UPDATED"'
    timeoutMs: 10000

  - id: telegram-report
    command: bash -c 'BEFORE_COV=$(cat /tmp/nuz-coverage.json 2>/dev/null | python3 -c "import sys,json; print(f\"{json.load(sys.stdin).get(\"totals\",{}).get(\"percent_covered\",0):.1f}\")" 2>/dev/null || echo "?"); AFTER_COV=$(cat /tmp/nuz-coverage-after.json 2>/dev/null | python3 -c "import sys,json; print(f\"{json.load(sys.stdin).get(\"totals\",{}).get(\"percent_covered\",0):.1f}\")" 2>/dev/null || echo "?"); FIXED=$(cat /tmp/nuz-regression-report.json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get(\"fixed_count\",0))" 2>/dev/null || echo "0"); echo "{\"report\": \"Nightly Auto-Fix $(date +%Y-%m-%d)\", \"coverage_before\": \"${BEFORE_COV}%\", \"coverage_after\": \"${AFTER_COV}%\", \"tests_fixed\": $FIXED, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"'
    timeoutMs: 10000
```

### 5.2 Cron Registration

```bash
# Register the autofix pipeline as a nightly cron job
openclaw cron add \
  --cron "30 3 * * *" \
  --tz Asia/Makassar \
  --exact \
  --name autofix-nightly \
  --message "Run the autofix-loop Lobster pipeline: lobster run autofix-loop" \
  --session-target isolated \
  --payload-kind agentTurn
```

**Schedule:** 03:30 WITA (30 min after the existing nightly-code-quality at 03:00, so they don't overlap)

### 5.3 Test Generation Pipeline (Phase 4 Roadmap): `autofix-coverage.lobster`

```yaml
name: autofix-coverage
description: "Generate tests for uncovered code paths. Runs weekly to grow coverage."

steps:
  - id: find-gaps
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python3 backend/scripts/analyze_coverage_gaps.py /tmp/nuz-coverage.json --top 10 --output /tmp/nuz-testgen-targets.json 2>&1'
    timeoutMs: 30000

  - id: generate-tests
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara && for target in $(cat /tmp/nuz-testgen-targets.json | python3 -c "import sys,json; [print(g[\"file\"]) for g in json.load(sys.stdin).get(\"gaps\",[])[:10]]" 2>/dev/null); do openclaw agent --agent coder --session-id "testgen-$(echo $target | md5sum | head -c8)-$(date +%s)" --timeout 300 --message "Generate pytest tests for $target. Read the file first, then write tests following existing patterns in the tests/ directory. Target: happy path + 1 edge case + 1 error case. Use async if needed." --json 2>&1 | tail -5; done'
    timeoutMs: 3600000

  - id: validate-tests
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/ -q --timeout=120 --tb=short 2>&1 | tail -30'
    timeoutMs: 600000

  - id: coverage-delta
    command: bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=json:/tmp/nuz-coverage-after-testgen.json -q --timeout=120 2>&1 | tail -10; python3 -c "import json; b=json.load(open(\"/tmp/nuz-coverage.json\")); a=json.load(open(\"/tmp/nuz-coverage-after-testgen.json\")); print(f\"Coverage: {b.get(\"totals\",{}).get(\"percent_covered\",0):.1f}% -> {a.get(\"totals\",{}).get(\"percent_covered\",0):.1f}%\")"'
    timeoutMs: 600000
```

---

## 6. Metrics & Success Criteria

### 6.1 KPIs

| Metric                             | Target (MVP)          | Target (Mature)      | Measurement                 |
| ---------------------------------- | --------------------- | -------------------- | --------------------------- |
| **Coverage improvement per cycle** | +0.5-1%               | +2-5%                | `pytest-cov` JSON delta     |
| **Fix success rate**               | >50% (IMPORT/FIXTURE) | >60% (all types)     | Fixed / Attempted           |
| **Regression rate**                | <10%                  | <5%                  | Regressions / Fixes applied |
| **Time to convergence**            | Stop at <0.5% delta   | Stop at <0.2% delta  | Coverage delta trending     |
| **Human intervention rate**        | <30%                  | <20%                 | Escalated / Total failures  |
| **Token cost per run**             | <$5                   | <$3                  | Anthropic billing           |
| **Pipeline duration**              | <90 min               | <60 min              | Lobster timing              |
| **Failure backlog trend**          | Decreasing weekly     | Near-zero in 8 weeks | Failure count over time     |

### 6.2 Convergence Strategy

```
Week 1-2: Fix IMPORT errors (180 → ~20)     [~+5% coverage]
Week 3-4: Fix FIXTURE errors (85 → ~10)      [~+3% coverage]
Week 5-6: Fix TYPE errors (62 → ~15)          [~+2% coverage]
Week 7-8: Fix LOGIC errors (78 → ~30)         [~+2% coverage]
Week 9+:  Test generation for uncovered code  [+1-2% per week]

Expected trajectory (HISTORICAL — test debt cleaned 2026-03-20, 0 failures):
  Week 0:  448 failures, ~42% coverage  [baseline]
  ...
  2026-03-20: 0 failures (cleaned by Windsurf)
```

### 6.3 When to Stop

The loop should stop when ANY of:

- Coverage delta < 0.2% for 3 consecutive runs
- All remaining failures are INTEGRATION type (need real services)
- Human escalation rate > 80% (remaining issues are too complex for AI)
- Token cost per fixed test > $0.50 (diminishing returns)

---

## 7. OpenClaw Arsenal Mapping

### Which OpenClaw capability serves which phase:

| OpenClaw Feature        | Phase     | How It's Used                                                                        |
| ----------------------- | --------- | ------------------------------------------------------------------------------------ |
| **Cron scheduling**     | All       | Nightly trigger at 03:30 WITA                                                        |
| **Lobster pipelines**   | All       | Orchestrates the 4-phase flow with conditions and gates                              |
| **Coder agent**         | Phase 2   | Executes fix generation in isolated workspace                                        |
| **Main agent**          | Phase 4   | Sends Telegram report, updates learnings                                             |
| **Sandbox mode (off)**  | Phase 2   | Coder needs direct filesystem/git access                                             |
| **Session isolation**   | Phase 2   | Unique session-id per fix prevents context pollution                                 |
| **Loop detection**      | Phase 2   | Built-in circuit breaker (globalCircuitBreakerThreshold: 10) prevents infinite loops |
| **Memory (claude-mem)** | Phase 4   | Cross-run learning: what patterns worked, what failed                                |
| **Learnings system**    | Phase 4   | ERRORS.md + LEARNINGS.md accumulate fix patterns                                     |
| **Telegram channel**    | Phase 4   | Human notification of results                                                        |
| **Git integration**     | Phase 2-4 | Branch management, commit, push                                                      |
| **Context pruning**     | Phase 2   | cache-ttl 1h keeps agent context fresh                                               |
| **Compaction**          | Phase 2   | safeguard mode prevents context explosion                                            |
| **Fallback models**     | Phase 2   | If Sonnet 4.6 is down, fall back to Haiku → Gemini                                   |
| **llm-task plugin**     | Phase 1   | JSON-only classification prompts (cheap, fast)                                       |
| **Heartbeat (off)**     | Phase 2   | Coder agent doesn't waste tokens on idle pings                                       |

---

## Appendix A: Required New Files

```
apps/backend-rag/backend/scripts/
├── classify_test_failures.py     # Phase 1: failure classification
├── analyze_coverage_gaps.py      # Phase 1: coverage gap analysis
├── generate_fix_prompts.py       # Phase 2: prompt generation
├── compare_test_results.py       # Phase 3: regression detection
└── autofix_safety_check.py       # Phase 2: validates diffs against safety rails

~/.openclaw/workspace/workflows/
├── autofix-loop.lobster          # Main pipeline
└── autofix-coverage.lobster      # Test generation pipeline (Phase 4)
```

## Appendix B: Estimated Token Costs

| Phase                     | Model            | Tokens/Run | Cost/Run   |
| ------------------------- | ---------------- | ---------- | ---------- |
| Phase 1 (classify)        | llm-task (Haiku) | ~5K        | $0.005     |
| Phase 2 (30 fixes)        | Sonnet 4.6       | ~120K      | $2.40      |
| Phase 3 (verify)          | None (shell)     | 0          | $0.00      |
| Phase 4 (report)          | Haiku            | ~2K        | $0.002     |
| **Total per nightly run** |                  | **~127K**  | **~$2.41** |

Monthly cost (30 runs): ~$72 — well within operational budget for 448→0 failure reduction.

---

## Sources

### Systems & Tools

- [SWE-agent (GitHub)](https://github.com/SWE-agent/SWE-agent) — NeurIPS 2024, autonomous coding agent
- [SWE-agent Paper](https://arxiv.org/abs/2405.15793) — Agent-Computer Interfaces
- [LIVE-SWE-agent](https://github.com/OpenAutoCoder/live-swe-agent) — Self-evolving agent scaffold
- [Qodo Cover (GitHub)](https://github.com/Codium-ai/cover-agent) — Automated test coverage generation
- [Qodo AI Blog](https://www.qodo.ai/blog/we-created-the-first-open-source-implementation-of-metas-testgen-llm/) — TestGen-LLM implementation
- [OpenHands (GitHub)](https://github.com/OpenHands/OpenHands) — AI-Driven Development platform
- [Aider](https://aider.chat/) — AI pair programming in terminal
- [Ralph Wiggum Plugin](https://www.vibesparking.com/en/blog/ai/2026-01-03-ralph-wiggum-plugin-claude-code-iterative-ai-loops/) — Claude Code autonomous loops
- [Claude Code Testing](https://www.nathanonn.com/claude-code-testing-ralph-loop-verification/) — Test verification patterns
- [Sourcegraph Cody vs Qodo](https://www.augmentcode.com/tools/sourcegraph-cody-vs-qodo) — Feature comparison

### Research Papers

- [LLM-based Automated Program Repair Survey](https://arxiv.org/html/2506.23749v1) — Comprehensive taxonomy
- [SWE-EVO Benchmark](https://www.arxiv.org/pdf/2512.18470) — Agent evolution benchmarking
- [LLMLOOP](https://valerio-terragni.github.io/assets/pdf/ravi-icsme-2025.pdf) — Iterative LLM code improvement
- [EDDOps Architecture](https://arxiv.org/html/2411.13768v3) — Evaluation-Driven Development for LLM Agents
- [Autonomous Coding Agents Guide 2026](https://www.sitepoint.com/autonomous-coding-agents-guide-2026/) — Industry overview
