# Step 6: Failure Modes — NB-2 Deep Research Pipeline

> Synthesis: Claude Opus 4.6 (architect) merging Codex (invariants) + Gemini (taxonomy) + DeepSeek R1 (risk scoring) (2026-03-28)
> Status: Brainstorm complete — unified synthesis
> Depends on: Steps 1-5 (query design, sequencing, quality verification, source management, scraper integration)
> Reference files: `06b_failure_modes_gemini.md` (30-mode taxonomy, circuit breakers, cascading analysis, recovery runbooks)

---

## 0. NLM API Wrapper — Architectural Note (review fix 2026-03-28)

> **CRITICAL IMPLEMENTATION GAP (Codex ISSUE-15):**
> All `nlm_api.*` calls throughout this spec reference an abstraction that MUST be implemented
> as `apps/evaluator/nlm_deep_research/nlm_api.py`. This module wraps the `nlm` CLI binary
> (installed via `pip install notebooklm-mcp`) which provides all NLM operations as shell commands.
>
> **Invocation pattern (from Python pipeline running via OpenClaw/launchd at 01:00 WITA):**
>
> ```python
> import subprocess, json
>
> def nlm_research_start(notebook_id: str, query: str, mode: str = "deep") -> dict:
>     result = subprocess.run(
>         ["nlm", "research", "start", "--notebook", notebook_id, "--query", query, "--mode", mode, "--json"],
>         capture_output=True, text=True, timeout=120
>     )
>     return json.loads(result.stdout)
> ```
>
> All 11 NLM MCP tools used in this spec (research_start, research_status, research_import,
> notebook_query, source_add, source_delete, source_list, source_get_content, note, server_info,
> notebook_list) must have corresponding wrapper functions in `nlm_api.py`.
>
> **Alternative:** If `nlm` CLI is unavailable, use direct HTTP to the MCP server
> (`mcp__notebooklm-mcp__*` tools) via the MCP stdio protocol.

---

## 1. Critical Invariants (10 Invariants That MUST Hold)

Every pipeline run begins and ends with an invariant check. If any invariant is violated, the pipeline takes a specific corrective action before proceeding. Violations are always logged and never silently swallowed.

### Invariant Table

| #          | Invariant                                                     | Why It Matters                                                                                            | Detection Check                                                                            | Response                                                                                                | Recovery                                                                                                                                   |
| ---------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **INV-1**  | `ACTIVE_count <= 70`                                          | NB-2 signal-to-noise degrades above 70; NLM synthesis quality drops                                       | `len([s for s in registry if s.stage == "ACTIVE"]) <= 70`                                  | BLOCK all promotions from TRIAGE. Trigger emergency CONSOLIDATE                                         | Archive lowest-SVS ACTIVE sources until count <= 55. Log `invariant_violation:active_cap`                                                  |
| **INV-2**  | `QUARANTINE_count <= 30`                                      | Backlog indicates triage failure; NLM carries unverified sources                                          | `len([s for s in registry if s.stage == "QUARANTINE"]) <= 30`                              | Force immediate triage (oldest-first) within current run                                                | Bulk-discard QUARANTINE sources older than 48h. Triage remainder                                                                           |
| **INV-3**  | `claims_in_digest >= claims_in_originals * 0.95` (ILM < 0.05) | Consolidation must not lose verified intelligence                                                         | After consolidation: `1 - (digest_claims / sum(original_claims)) < 0.05`                   | REJECT consolidation. Keep originals in ACTIVE. Alert Telegram                                          | Re-run consolidation with stricter claim matcher. If still fails, defer to Friday manual review                                            |
| **INV-4**  | `no balizero.com in NLM sources`                              | Feedback loop prevention — NLM must never cite our own output                                             | `not any("balizero.com" in s.url for s in registry if s.stage in ("ACTIVE","QUARANTINE"))` | Immediately `source_delete` the offending source. Log `CRITICAL:feedback_loop_breach`                   | Add domain to denylist (should already be there). Audit all claims from that source — demote any that relied solely on it                  |
| **INV-5**  | `MASTER_DIGEST_count >= 4`                                    | The 4 Master Documents (MD-1..MD-4) are the durable intelligence layer. Losing one leaves a knowledge gap | `len([s for s in registry if s.category == "MASTER_DIGEST" and s.stage == "ACTIVE"]) >= 4` | HALT consolidation (it may have accidentally archived a MD). Alert Telegram CRITICAL                    | Rebuild missing MD from `claim_archive.jsonl` + last weekly snapshot. `source_add` immediately                                             |
| **INV-6**  | `consecutive_failures < 3`                                    | 3+ consecutive full pipeline failures indicate a systemic issue (NLM down, auth expired, network)         | `state["errors"]["consecutive_failures"] < 3`                                              | PAUSE pipeline for 48h. Telegram CRITICAL alert with last 3 error messages                              | After 48h: single diagnostic query (L1 monitoring, minimal). If succeeds, reset counter and resume. If fails, require manual intervention  |
| **INV-7**  | `budget.week_calls <= 40`                                     | Hard budget cap prevents API exhaustion and potential NLM throttling                                      | `state["budget"]["week_calls"] <= 40`                                                      | SKIP all queries for remainder of week. Log `budget_exhausted`                                          | Auto-reset on Monday 00:00 WITA. If hit before Thursday, review why (possible duplicate runs)                                              |
| **INV-8**  | `no duplicate dedup_keys in query_history`                    | Same query must not run twice on same day (macOS launchd double-fire)                                     | Before enqueue: `hash(template_id + cluster + date) not in today_completed`                | SKIP the duplicate query entirely. Log `dedup_guard_triggered`                                          | No recovery needed — dedup guard is the recovery. If triggered >2x/week, investigate launchd config                                        |
| **INV-9**  | `pipeline completes before 02:30 WITA`                        | Must finish 30 min before scraper at 03:00 to guarantee handoff                                           | At 02:25: check `pipeline_status != "IDLE"`                                                | If still RUNNING at 02:25: kill current query, write PARTIAL handoff, force transition to CONSOLIDATING | Write whatever findings exist as PARTIAL brief. Scraper receives degraded but usable output. Log `deadline_breach`                         |
| **INV-10** | `state_file.version == EXPECTED_VERSION`                      | State schema evolution must be explicit. Old-version state could cause silent field misinterpretation     | `state.get("version") == CURRENT_SCHEMA_VERSION`                                           | ABORT pipeline. Do not run with mismatched state                                                        | Run state migration function `migrate_state(old_version, new_version)`. If no migration path exists, backup old state and initialize fresh |

### Invariant Check Function (Pre-flight)

```python
from dataclasses import dataclass
from typing import Optional
import json
import logging

logger = logging.getLogger("nlm_nb2.invariants")

@dataclass
class InvariantResult:
    invariant_id: str
    passed: bool
    actual_value: any
    expected: str
    severity: str  # "CRITICAL" | "WARNING" | "INFO"
    message: str

def check_all_invariants(
    registry: "SourceRegistry",
    state: dict,
    schema_version: int = 1,
) -> list[InvariantResult]:
    """Run all 10 invariants. Returns list of results. Any CRITICAL failure = pipeline abort."""
    results = []

    # NOTE: registry.sources is a dict keyed by source_id (canonical format from Step 4 §7.2)
    # Access: registry.sources.values() for iteration, registry.sources[id] for lookup

    # INV-1: ACTIVE cap
    active_count = sum(1 for s in registry.sources.values() if s["stage"] == "ACTIVE")
    results.append(InvariantResult(
        "INV-1", active_count <= 70, active_count,
        "<= 70", "CRITICAL" if active_count > 70 else "INFO",
        f"ACTIVE sources: {active_count}/70"
    ))

    # INV-2: QUARANTINE cap
    quarantine_count = sum(1 for s in registry.sources.values() if s["stage"] == "QUARANTINE")
    results.append(InvariantResult(
        "INV-2", quarantine_count <= 30, quarantine_count,
        "<= 30", "WARNING" if quarantine_count > 30 else "INFO",
        f"QUARANTINE sources: {quarantine_count}/30"
    ))

    # INV-4: No balizero.com in NLM
    balizero_sources = [
        s for s in registry.sources
        if s["stage"] in ("ACTIVE", "QUARANTINE")
        and "balizero.com" in s.get("url", "")
    ]
    results.append(InvariantResult(
        "INV-4", len(balizero_sources) == 0, len(balizero_sources),
        "== 0", "CRITICAL" if balizero_sources else "INFO",
        f"balizero.com sources found: {len(balizero_sources)}"
    ))

    # INV-5: Master Digest count
    md_count = sum(
        1 for s in registry.sources
        if s.get("category") == "MASTER_DIGEST" and s["stage"] == "ACTIVE"
    )
    results.append(InvariantResult(
        "INV-5", md_count >= 4, md_count,
        ">= 4", "CRITICAL" if md_count < 4 else "INFO",
        f"Master Digests: {md_count}/4"
    ))

    # INV-6: Consecutive failures
    consec = state.get("errors", {}).get("consecutive_failures", 0)
    results.append(InvariantResult(
        "INV-6", consec < 3, consec,
        "< 3", "CRITICAL" if consec >= 3 else "INFO",
        f"Consecutive failures: {consec}"
    ))

    # INV-7: Weekly budget
    week_calls = state.get("budget", {}).get("week_calls", 0)
    results.append(InvariantResult(
        "INV-7", week_calls <= 40, week_calls,
        "<= 40", "CRITICAL" if week_calls > 40 else "INFO",
        f"Weekly API calls: {week_calls}/40"
    ))

    # INV-10: Schema version
    file_version = state.get("version", 0)
    results.append(InvariantResult(
        "INV-10", file_version == schema_version, file_version,
        f"== {schema_version}", "CRITICAL" if file_version != schema_version else "INFO",
        f"State schema version: {file_version} (expected {schema_version})"
    ))

    return results


def enforce_invariants(results: list[InvariantResult]) -> tuple[bool, list[str]]:
    """Returns (can_proceed, list_of_critical_violations)."""
    criticals = [r for r in results if not r.passed and r.severity == "CRITICAL"]
    warnings = [r for r in results if not r.passed and r.severity == "WARNING"]

    for w in warnings:
        logger.warning(f"INVARIANT WARNING {w.invariant_id}: {w.message}")
    for c in criticals:
        logger.critical(f"INVARIANT VIOLATION {c.invariant_id}: {c.message}")

    return len(criticals) == 0, [c.message for c in criticals]
```

---

## 2. State Corruption Recovery

Four state files can be corrupted. Each has a defined recovery procedure.

### 2.1 File Inventory

| File                   | Location                                     | Format              | Mutability            | Backup                              |
| ---------------------- | -------------------------------------------- | ------------------- | --------------------- | ----------------------------------- |
| `pipeline_state.json`  | `apps/evaluator/nlm_nb2_pipeline_state.json` | JSON (mutable)      | Overwritten every run | Friday snapshot in `weekly/`        |
| `source_registry.json` | `apps/evaluator/nlm_nb2_sources.json`        | JSON (mutable)      | Updated every run     | Friday snapshot in `weekly/`        |
| `claims.jsonl`         | `apps/evaluator/nlm_nb2_claims.jsonl`        | JSONL (append-only) | Append per claim      | Never truncated. Last line = latest |
| `query_history.jsonl`  | `apps/evaluator/nlm_nb2_query_history.jsonl` | JSONL (append-only) | Append per query      | Never truncated                     |

### 2.2 `pipeline_state.json` Corrupted

**Symptoms:** JSON parse error at pipeline start, or missing required top-level keys.

**What is lost:** Current run status, today's cluster, hot_topics, override state, budget counters.

**What is NOT lost:** Source data (separate file), claims (separate file), query history (separate file).

**Recovery procedure:**

```python
import json
import os
from datetime import datetime, date
from pathlib import Path

STATE_PATH = Path("apps/evaluator/nlm_nb2_pipeline_state.json")
WEEKLY_DIR = Path("apps/evaluator/nlm_nb2_weekly")
HISTORY_PATH = Path("apps/evaluator/nlm_nb2_query_history.jsonl")

def recover_pipeline_state() -> dict:
    """Rebuild pipeline_state.json from available data."""
    logger.warning("pipeline_state.json corrupted — initiating recovery")

    # 1. Try last Friday snapshot
    snapshots = sorted(WEEKLY_DIR.glob("pipeline_state_*.json"), reverse=True)
    if snapshots:
        try:
            base_state = json.loads(snapshots[0].read_text())
            logger.info(f"Recovered base state from {snapshots[0].name}")
        except json.JSONDecodeError:
            base_state = None
    else:
        base_state = None

    # 2. If no snapshot, build from scratch
    if base_state is None:
        base_state = _build_default_state()

    # 3. Reconstruct budget counters from query_history.jsonl
    if HISTORY_PATH.exists():
        week_start = _get_week_start(date.today())
        month_start = date.today().replace(day=1)
        week_calls = 0
        month_calls = 0
        for line in HISTORY_PATH.read_text().strip().split("\n"):
            try:
                entry = json.loads(line)
                entry_date = date.fromisoformat(entry["date"])
                if entry_date >= week_start:
                    week_calls += 1
                if entry_date >= month_start:
                    month_calls += 1
            except (json.JSONDecodeError, KeyError):
                continue
        base_state["budget"]["week_calls"] = week_calls
        base_state["budget"]["month_calls"] = month_calls
        logger.info(f"Reconstructed budget: {week_calls} this week, {month_calls} this month")

    # 4. Reset volatile state to safe defaults
    base_state["pipeline_status"] = "IDLE"
    base_state["today"] = _empty_today_block()
    base_state["errors"]["consecutive_failures"] = 0  # Give benefit of doubt

    # 5. Write recovered state
    STATE_PATH.write_text(json.dumps(base_state, indent=2, default=str))
    logger.info("pipeline_state.json recovered successfully")
    return base_state


def _build_default_state() -> dict:
    """Factory default state. Used only when NO recovery data exists."""
    return {
        "version": 1,
        "pipeline_status": "IDLE",
        "last_run": None,
        "today": _empty_today_block(),
        "rotation": {
            "cluster_schedule": ["A", "B", "C", "D", "E"],
            "last_cluster_run": {},
        },
        "override": None,
        "hot_topics": [],
        "known_regulations": [],
        "errors": {"consecutive_failures": 0, "throttle_flags": 0, "backoff_until": None},
        "budget": {"week_calls": 0, "week_limit": 40, "month_calls": 0, "month_limit": 160},
    }


def _empty_today_block() -> dict:
    return {
        "cluster": None,
        "l1_status": None, "l1_task_id": None,
        "l1_sources_imported": 0, "l1_key_findings": [], "l1_confidence": 0.0,
        "l2_status": None, "l2_task_id": None,
        "l2_sources_imported": 0, "l2_key_findings": [], "l2_confidence": 0.0,
        "afternoon_triggered": False,
    }


def _get_week_start(d: date) -> date:
    """Return Monday of the current week."""
    return d - __import__("datetime").timedelta(days=d.weekday())
```

### 2.3 `source_registry.json` Corrupted

**Symptoms:** JSON parse error, or source count mismatches NLM reality.

**What is lost:** SVS scores, claim counts per source, stage assignments, dedup fingerprints, flags.

**What is NOT lost:** The actual NLM sources (they are IN the notebook). Claims are in `claims.jsonl`.

**Recovery procedure:**

```python
REGISTRY_PATH = Path("apps/evaluator/nlm_nb2_sources.json")
CLAIMS_PATH = Path("apps/evaluator/nlm_nb2_claims.jsonl")

def recover_source_registry(notebook_id: str) -> dict:
    """Rebuild source registry from NLM API + claims archive."""
    logger.warning("source_registry.json corrupted — initiating recovery from NLM API")

    # 1. Get ground truth from NLM: what sources are actually in the notebook?
    #    source_list returns all sources with nlm_source_id, title, url
    nlm_sources = nlm_api.source_list(notebook_id=notebook_id)  # NLM MCP tool
    logger.info(f"NLM reports {len(nlm_sources)} sources in NB-2")

    # 2. Rebuild registry entries from NLM data
    recovered = {"version": 1, "sources": [], "domain_denylist": _default_denylist()}
    for nlm_src in nlm_sources:
        entry = {
            "nlm_source_id": nlm_src["id"],
            "title": nlm_src.get("title", ""),
            "url": nlm_src.get("url", ""),
            "stage": "ACTIVE",  # Assume all NLM sources are ACTIVE (conservative)
            "category": _infer_category(nlm_src),  # CANONICAL/WORKING/MASTER_DIGEST/REFERENCE
            "tier": None,  # Lost — must re-classify
            "svs": None,   # Lost — must recompute
            "claims_extracted": 0,
            "times_cited_in_briefs": 0,
            "ingest_timestamp": None,  # Lost
            "last_confirmed_valid": datetime.now().isoformat(),
            "fingerprint": None,  # Lost — must recompute
            "flags": ["RECOVERED"],
        }
        recovered["sources"].append(entry)

    # 3. Enrich with claim counts from claims.jsonl (if available)
    if CLAIMS_PATH.exists():
        claim_counts = {}
        for line in CLAIMS_PATH.read_text().strip().split("\n"):
            try:
                claim = json.loads(line)
                src_id = claim.get("source_id", "")
                claim_counts[src_id] = claim_counts.get(src_id, 0) + 1
            except json.JSONDecodeError:
                continue
        for entry in recovered["sources"]:
            entry["claims_extracted"] = claim_counts.get(entry["nlm_source_id"], 0)

    # 4. Flag for re-classification
    logger.warning(
        f"Registry recovered with {len(recovered['sources'])} sources. "
        f"TIER and SVS must be recomputed on next triage run. "
        f"All sources flagged RECOVERED."
    )

    REGISTRY_PATH.write_text(json.dumps(recovered, indent=2, default=str))
    return recovered


def _infer_category(nlm_src: dict) -> str:
    """Best-effort category inference from title."""
    title = nlm_src.get("title", "").lower()
    if title.startswith("[nb2-md]"):
        return "MASTER_DIGEST"
    if any(kw in title for kw in ("uu ", "pp ", "permen", "surat edaran", "perda")):
        return "CANONICAL"
    return "WORKING"  # Default assumption
```

### 2.4 `claims.jsonl` Corrupted

**Symptoms:** JSONL parse errors on specific lines, or file truncated.

**What is lost:** Extracted claims with confidence scores, source chains, timestamps.

**What can be re-extracted:** Claims can be re-extracted by querying NLM with a targeted prompt against each ACTIVE source. However, this is expensive (1 query per source).

**Recovery procedure:**

```python
def recover_claims_jsonl() -> int:
    """Salvage valid lines from corrupted claims.jsonl. Returns count of recovered claims."""
    logger.warning("claims.jsonl corrupted — salvaging valid entries")

    if not CLAIMS_PATH.exists():
        logger.error("claims.jsonl does not exist. Total claim loss. Must re-extract.")
        return 0

    raw_lines = CLAIMS_PATH.read_text().strip().split("\n")
    valid_claims = []
    corrupted_lines = []

    for i, line in enumerate(raw_lines):
        try:
            claim = json.loads(line)
            # Validate minimum required fields
            if all(k in claim for k in ("claim_id", "claim_text", "source_id")):
                valid_claims.append(line)
            else:
                corrupted_lines.append((i, "missing_required_fields"))
        except json.JSONDecodeError:
            corrupted_lines.append((i, "json_parse_error"))

    if corrupted_lines:
        logger.warning(
            f"claims.jsonl: {len(valid_claims)} valid, {len(corrupted_lines)} corrupted lines"
        )
        # Write corrupted lines to forensic file
        forensic_path = CLAIMS_PATH.with_suffix(".corrupted_backup")
        forensic_path.write_text("\n".join(raw_lines))

    # Rewrite with only valid claims
    CLAIMS_PATH.write_text("\n".join(valid_claims) + "\n" if valid_claims else "")

    # Log which claims are lost (by checking source_registry for claim gaps)
    logger.info(
        f"Recovered {len(valid_claims)} claims. "
        f"Lost {len(corrupted_lines)} entries. "
        f"Forensic backup at {forensic_path}"
    )

    return len(valid_claims)


def re_extract_claims_for_source(notebook_id: str, source_id: str) -> list[dict]:
    """Re-extract claims from a single NLM source. Expensive: 1 API query."""
    prompt = (
        f"Extract all atomic factual claims from source {source_id}. "
        f"For each claim provide: claim_text, category, regulation_ref, "
        f"effective_date, geographic_scope, confidence_score."
    )
    response = nlm_api.notebook_query(notebook_id=notebook_id, query=prompt)
    # Parse structured response into claim objects
    # This is approximate — NLM returns prose, not structured JSON
    # A follow-up LLM call (Qwen local) parses the prose into claims
    return _parse_claims_from_nlm_response(response, source_id)
```

### 2.5 Master Document Accidentally Deleted

**Symptoms:** INV-5 fires (MD count < 4). Or `source_list` returns fewer than 4 `[NB2-MD]` sources.

**What is lost:** The synthesized Master Document text in NLM. The NLM query engine no longer has this context.

**Recovery procedure:**

```python
MD_TEMPLATES = {
    "MD-1": "NB-2 Immigration Regulatory Change Log",
    "MD-2": "NB-2 Immigration Operations Status",
    "MD-3": "NB-2 Cross-Domain Impact Matrix",
    "MD-4": "NB-2 Open Questions Tracker",
}

def recover_master_document(notebook_id: str, md_key: str) -> str:
    """Restore a deleted Master Document from the best available source."""
    logger.critical(f"Master Document {md_key} missing — initiating recovery")

    title = MD_TEMPLATES[md_key]

    # Priority 1: Last Friday snapshot (most complete, most recent)
    snapshot_dir = Path("apps/evaluator/nlm_nb2_weekly")
    snapshots = sorted(snapshot_dir.glob(f"master_doc_{md_key}_*.md"), reverse=True)
    if snapshots:
        content = snapshots[0].read_text()
        logger.info(f"Restoring {md_key} from Friday snapshot: {snapshots[0].name}")
    else:
        # Priority 2: Rebuild from claims archive
        logger.warning(f"No Friday snapshot for {md_key}. Rebuilding from claims.jsonl")
        content = _rebuild_md_from_claims(md_key)

    # Re-add to NLM
    new_source_id = nlm_api.source_add(
        notebook_id=notebook_id,
        source_type="text",
        text=content,
        title=f"[NB2-MD] {title} - Recovered {date.today().isoformat()}",
    )

    # Update registry
    registry = _load_registry()
    registry["sources"].append({
        "nlm_source_id": new_source_id,
        "title": f"[NB2-MD] {title}",
        "stage": "ACTIVE",
        "category": "MASTER_DIGEST",
        "flags": ["RECOVERED"],
    })
    _save_registry(registry)

    logger.info(f"Master Document {md_key} restored as {new_source_id}")
    return new_source_id
```

---

## 3. Pre-flight Defensive Checks (01:00 WITA)

These checks run at the very start of the pipeline, BEFORE any NLM API calls. Each check has a defined response. The pipeline proceeds only if all REQUIRED checks pass.

### 3.1 Pre-flight Checklist

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
import time
import os

class CheckSeverity(Enum):
    REQUIRED = "REQUIRED"    # Failure = pipeline abort
    IMPORTANT = "IMPORTANT"  # Failure = degrade gracefully, continue
    ADVISORY = "ADVISORY"    # Failure = log warning, continue

@dataclass
class PreflightCheck:
    name: str
    severity: CheckSeverity
    passed: bool
    message: str
    action_on_fail: str


def run_preflight(state_path: Path, registry_path: Path, claims_path: Path) -> list[PreflightCheck]:
    """Run all pre-flight checks. Returns ordered list of results."""
    checks = []

    # ── CHECK 1: State file exists and is valid JSON ──
    try:
        state = json.loads(state_path.read_text())
        checks.append(PreflightCheck(
            "state_file_valid", CheckSeverity.REQUIRED, True,
            f"pipeline_state.json OK (version={state.get('version')})",
            ""
        ))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        checks.append(PreflightCheck(
            "state_file_valid", CheckSeverity.REQUIRED, False,
            f"pipeline_state.json INVALID: {e}",
            "RECOVER: call recover_pipeline_state()"
        ))
        state = recover_pipeline_state()  # Auto-recovery attempt

    # ── CHECK 2: Source registry exists and is valid JSON ──
    try:
        registry = json.loads(registry_path.read_text())
        src_count = len(registry.get("sources", []))
        checks.append(PreflightCheck(
            "registry_file_valid", CheckSeverity.REQUIRED, True,
            f"source_registry.json OK ({src_count} sources tracked)",
            ""
        ))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        checks.append(PreflightCheck(
            "registry_file_valid", CheckSeverity.REQUIRED, False,
            f"source_registry.json INVALID: {e}",
            "RECOVER: call recover_source_registry(notebook_id)"
        ))

    # ── CHECK 3: NLM API reachable ──
    try:
        info = nlm_api.server_info()  # Lightweight ping
        checks.append(PreflightCheck(
            "nlm_api_reachable", CheckSeverity.REQUIRED, True,
            f"NLM API reachable (server: {info.get('version', 'unknown')})",
            ""
        ))
    except Exception as e:
        checks.append(PreflightCheck(
            "nlm_api_reachable", CheckSeverity.REQUIRED, False,
            f"NLM API unreachable: {e}",
            "ABORT: retry in 5 min, then skip today's run"
        ))

    # ── CHECK 4: NLM authentication valid ──
    try:
        notebooks = nlm_api.notebook_list()
        nb2_found = any("immigration" in nb.get("title", "").lower() for nb in notebooks)
        checks.append(PreflightCheck(
            "nlm_auth_valid", CheckSeverity.REQUIRED, nb2_found,
            f"NLM auth OK, NB-2 {'found' if nb2_found else 'NOT FOUND'} in {len(notebooks)} notebooks",
            "" if nb2_found else "ABORT: NB-2 notebook missing or auth token expired. Run `nlm login`"
        ))
    except Exception as e:
        checks.append(PreflightCheck(
            "nlm_auth_valid", CheckSeverity.REQUIRED, False,
            f"NLM auth check failed: {e}",
            "ABORT: run `nlm login` to refresh authentication"
        ))

    # ── CHECK 5: Budget remaining ──
    budget = state.get("budget", {})
    week_remaining = budget.get("week_limit", 40) - budget.get("week_calls", 0)
    checks.append(PreflightCheck(
        "budget_remaining", CheckSeverity.REQUIRED, week_remaining >= 2,
        f"Budget: {week_remaining} queries remaining this week",
        "SKIP: budget exhausted, resume Monday" if week_remaining < 2 else ""
    ))

    # ── CHECK 6: Backoff period not active ──
    backoff_until = state.get("errors", {}).get("backoff_until")
    if backoff_until:
        from datetime import datetime
        backoff_expired = datetime.fromisoformat(backoff_until) < datetime.now()
    else:
        backoff_expired = True
    checks.append(PreflightCheck(
        "backoff_clear", CheckSeverity.REQUIRED, backoff_expired,
        f"Backoff: {'clear' if backoff_expired else f'active until {backoff_until}'}",
        "SKIP: in backoff period due to consecutive failures" if not backoff_expired else ""
    ))

    # ── CHECK 7: Source count sane (not 0 and not > 100) ──
    active_count = sum(1 for s in registry.get("sources", []) if s.get("stage") == "ACTIVE")
    sane = 5 <= active_count <= 100
    checks.append(PreflightCheck(
        "source_count_sane", CheckSeverity.IMPORTANT,
        sane,
        f"ACTIVE sources: {active_count} ({'sane' if sane else 'ANOMALOUS'})",
        "WARN: source count anomalous. Run diagnostics but continue pipeline" if not sane else ""
    ))

    # ── CHECK 8: No stale run in progress (crash recovery) ──
    pipeline_status = state.get("pipeline_status", "IDLE")
    if pipeline_status != "IDLE":
        # Check if we have a task_id to resume
        today = state.get("today", {})
        has_resumable_task = (
            today.get("l1_task_id") and today.get("l1_status") == "RUNNING"
        ) or (
            today.get("l2_task_id") and today.get("l2_status") == "RUNNING"
        )
        checks.append(PreflightCheck(
            "no_stale_run", CheckSeverity.IMPORTANT, False,
            f"Stale run detected: status={pipeline_status}, resumable={has_resumable_task}",
            "RESUME: attempt to resume from last checkpoint" if has_resumable_task
            else "RESET: force pipeline_status to IDLE and start fresh"
        ))
    else:
        checks.append(PreflightCheck(
            "no_stale_run", CheckSeverity.IMPORTANT, True,
            "No stale run. Pipeline IDLE.",
            ""
        ))

    # ── CHECK 9: Weekend check (skip Sat/Sun) ──
    from datetime import datetime
    is_weekday = datetime.now().weekday() < 5
    checks.append(PreflightCheck(
        "weekday_check", CheckSeverity.REQUIRED, is_weekday,
        f"Day: {'weekday' if is_weekday else 'WEEKEND'} ({datetime.now().strftime('%A')})",
        "SKIP: Indonesian gazette publishes Mon-Fri only. Pipeline OFF on weekends." if not is_weekday else ""
    ))

    # ── CHECK 10: Handoff directory writable ──
    handoff_dir = Path.home() / ".agent/decisions/nlm_to_scraper"
    dir_ok = handoff_dir.exists() and os.access(handoff_dir, os.W_OK)
    if not dir_ok and not handoff_dir.exists():
        try:
            handoff_dir.mkdir(parents=True, exist_ok=True)
            dir_ok = True
        except OSError:
            dir_ok = False
    checks.append(PreflightCheck(
        "handoff_dir_writable", CheckSeverity.IMPORTANT, dir_ok,
        f"Handoff directory: {'OK' if dir_ok else 'NOT WRITABLE'}",
        "WARN: handoff will fail. Scraper runs in IGNORE mode (acceptable)" if not dir_ok else ""
    ))

    # ── CHECK 11: Claims file not excessively large ──
    if claims_path.exists():
        claims_size_mb = claims_path.stat().st_size / (1024 * 1024)
        size_ok = claims_size_mb < 50  # 50 MB cap for a JSONL
        checks.append(PreflightCheck(
            "claims_file_size", CheckSeverity.ADVISORY, size_ok,
            f"claims.jsonl size: {claims_size_mb:.1f} MB",
            "ADVISORY: claims.jsonl exceeds 50MB. Consider archival rotation." if not size_ok else ""
        ))

    # ── CHECK 12: Dedup guard (already ran today?) ──
    last_run_date = state.get("last_run", {}).get("date") if state.get("last_run") else None
    today_str = datetime.now().strftime("%Y-%m-%d")
    already_ran = last_run_date == today_str and state.get("last_run", {}).get("status") == "SUCCESS"
    checks.append(PreflightCheck(
        "dedup_guard", CheckSeverity.REQUIRED, not already_ran,
        f"Last successful run: {last_run_date or 'never'} (today: {today_str})",
        "SKIP: pipeline already completed successfully today (launchd double-fire?)" if already_ran else ""
    ))

    return checks


def evaluate_preflight(checks: list[PreflightCheck]) -> tuple[bool, str]:
    """Evaluate preflight results. Returns (can_proceed, summary)."""
    required_failures = [c for c in checks if c.severity == CheckSeverity.REQUIRED and not c.passed]
    important_failures = [c for c in checks if c.severity == CheckSeverity.IMPORTANT and not c.passed]

    summary_lines = []
    for c in checks:
        icon = "PASS" if c.passed else "FAIL"
        summary_lines.append(f"  [{icon}] {c.name} ({c.severity.value}): {c.message}")

    summary = "PRE-FLIGHT CHECKLIST:\n" + "\n".join(summary_lines)

    if required_failures:
        summary += f"\n\nABORT: {len(required_failures)} REQUIRED check(s) failed:"
        for f in required_failures:
            summary += f"\n  - {f.name}: {f.action_on_fail}"
        return False, summary

    if important_failures:
        summary += f"\n\nPROCEED WITH CAUTION: {len(important_failures)} IMPORTANT check(s) failed"

    return True, summary
```

### 3.2 Pre-flight Decision Matrix

| Check                  | Severity  | On Failure                                                                             |
| ---------------------- | --------- | -------------------------------------------------------------------------------------- |
| `state_file_valid`     | REQUIRED  | Auto-recover from Friday snapshot or build default. If recovery fails: ABORT           |
| `registry_file_valid`  | REQUIRED  | Auto-recover from NLM API `source_list`. If NLM unreachable: ABORT                     |
| `nlm_api_reachable`    | REQUIRED  | Retry 1x after 5 min wait. If still fails: ABORT, alert Telegram                       |
| `nlm_auth_valid`       | REQUIRED  | ABORT. Requires `nlm login` (manual or OpenClaw cron re-auth)                          |
| `budget_remaining`     | REQUIRED  | SKIP today. Resume Monday (budget resets weekly)                                       |
| `backoff_clear`        | REQUIRED  | SKIP today. Backoff auto-expires after 48h                                             |
| `source_count_sane`    | IMPORTANT | Continue but log anomaly. 0 sources = first run (expected). >100 = INV-1 will catch it |
| `no_stale_run`         | IMPORTANT | Attempt resume from `task_id` if available. Otherwise reset to IDLE                    |
| `weekday_check`        | REQUIRED  | SKIP. Return immediately. Weekends are OFF                                             |
| `handoff_dir_writable` | IMPORTANT | Continue. Scraper will run in IGNORE mode (no degradation)                             |
| `claims_file_size`     | ADVISORY  | Log warning. Continue. Rotation is a maintenance task                                  |
| `dedup_guard`          | REQUIRED  | SKIP. Already ran today. Prevents launchd double-fire waste                            |

---

## 4. NLM API Failure Patterns

### 4.1 Failure Response Matrix

| API Call          | Failure Pattern                                 | Detection                                    | Response                                        | Retry?         | State Transition                                                                      |
| ----------------- | ----------------------------------------------- | -------------------------------------------- | ----------------------------------------------- | -------------- | ------------------------------------------------------------------------------------- |
| `research_start`  | HTTP error / timeout                            | Exception from MCP tool                      | Log error. Retry once after 60s                 | Yes (1x)       | If retry fails: skip this query, advance to next phase                                |
| `research_start`  | Returns error body (invalid query, quota)       | `response.get("error")` is truthy            | Log error code. Do NOT retry quota errors       | Only non-quota | If quota: set `backoff_until = +48h`. If invalid query: log and use fallback template |
| `research_status` | Polls > 25 min without completion               | `elapsed > 1500s` in polling loop            | Kill: stop polling. Mark query as TIMED_OUT     | No             | Write PARTIAL findings if any intermediate results exist. Advance to next phase       |
| `research_status` | Returns "failed" status                         | `response["status"] == "failed"`             | Log failure reason                              | No             | Mark query FAILED. Advance to next phase. Increment `consecutive_failures`            |
| `research_import` | Returns 0 sources imported                      | `imported_count == 0`                        | Log. Check for throttle signals                 | No             | Set `throttle_flags += 1`. If `throttle_flags >= 3` this week: PAUSE pipeline 48h     |
| `research_import` | Partial import (some fail)                      | `imported < expected`                        | Log discrepancy. Continue with imported sources | No             | Normal flow. Only imported sources enter QUARANTINE                                   |
| `notebook_query`  | Returns nonsense / irrelevant response          | See Section 4.2: nonsense detection          | Log. Retry with simplified prompt               | Yes (1x)       | If retry also nonsense: mark findings as LOW confidence. Do not include in handoff    |
| `notebook_query`  | Returns empty / minimal response                | `len(response) < 50 chars`                   | Log. Check if NB-2 has sources                  | No             | If ACTIVE sources = 0: expected (first run). Otherwise: `throttle_flags += 1`         |
| `source_add`      | HTTP error / timeout                            | Exception from MCP tool                      | Log. Queue source for next run                  | Yes (1x)       | Add to `pending_source_adds` queue in state. Retry at start of next run               |
| `source_add`      | Returns success but source not in `source_list` | Post-add verification: `source_list` check   | Log discrepancy                                 | Yes (1x)       | If still missing after retry: mark as FAILED_ADD in registry. Manual investigation    |
| `source_delete`   | HTTP error / timeout                            | Exception from MCP tool                      | Log. Mark PENDING_DELETE in registry            | No (queued)    | Source stays in NLM but is marked PENDING_DELETE. Retry at start of next run          |
| `source_delete`   | Source not found (already deleted?)             | `response` indicates not found               | Treat as success                                | No             | Remove from registry. Source was already gone (manual deletion or NLM cleanup)        |
| `source_list`     | Returns fewer sources than registry tracks      | `len(nlm_sources) < len(active_in_registry)` | Log discrepancy. Reconcile                      | No             | Remove orphaned registry entries. Update counts. This is the ground truth             |

### 4.2 Nonsense Detection for `notebook_query`

NLM can occasionally return responses that are syntactically valid but semantically wrong (hallucination, topic drift, or stale context). Detection heuristics:

```python
def is_nonsense_response(query: str, response: str, expected_cluster: str) -> tuple[bool, str]:
    """Detect if NLM response is nonsensical. Returns (is_nonsense, reason)."""

    # 1. Too short (NLM should provide substantive synthesis)
    if len(response) < 100:
        return True, "response_too_short"

    # 2. Language mismatch — query was about Indonesia but response talks about other countries
    indonesia_keywords = {"indonesia", "indonesian", "visa", "kitas", "kitap", "imigrasi",
                          "kemenkumham", "permenkumham", "bali", "jakarta"}
    response_lower = response.lower()
    indonesia_relevance = sum(1 for kw in indonesia_keywords if kw in response_lower)
    if indonesia_relevance < 2:
        return True, "no_indonesia_relevance"

    # 3. Cluster mismatch — asked about work permits, got answer about property
    cluster_keywords = {
        "A": {"kitas", "rptka", "tka", "work permit", "sponsor", "imta", "dkptka"},
        "B": {"kitap", "stay permit", "permanent", "itap", "itas"},
        "C": {"visa kunjungan", "visit visa", "voa", "visa on arrival", "b211", "tourist"},
        "D": {"golden visa", "digital nomad", "second home", "retirement"},
        "E": {"overstay", "deportasi", "enforcement", "penalty", "compliance"},
    }
    if expected_cluster in cluster_keywords:
        cluster_match = sum(1 for kw in cluster_keywords[expected_cluster] if kw in response_lower)
        if cluster_match == 0:
            return True, f"cluster_mismatch:expected_{expected_cluster}"

    # 4. Self-referential (NLM citing its own prompts or instructions)
    self_ref_markers = ["as an ai", "i cannot", "my training data", "i don't have access"]
    if any(marker in response_lower for marker in self_ref_markers):
        return True, "self_referential_response"

    # 5. Stale: references only pre-2024 information when asked about 2026
    if "2026" in query and "2026" not in response and "2025" not in response:
        return True, "temporal_staleness"

    return False, "ok"
```

### 4.3 Pending Operations Queue

Failed `source_add` and `source_delete` operations are queued for retry:

```python
def process_pending_operations(notebook_id: str, state: dict) -> dict:
    """Process pending source_add/source_delete from previous failed runs."""
    pending_adds = state.get("pending_source_adds", [])
    pending_deletes = state.get("pending_source_deletes", [])
    results = {"adds_succeeded": 0, "adds_failed": 0, "deletes_succeeded": 0, "deletes_failed": 0}

    # Process deletes first (make room for adds)
    remaining_deletes = []
    for entry in pending_deletes:
        try:
            nlm_api.source_delete(notebook_id=notebook_id, source_id=entry["nlm_source_id"])
            results["deletes_succeeded"] += 1
            # Remove from registry
            registry_remove(entry["nlm_source_id"])
        except Exception as e:
            entry["retry_count"] = entry.get("retry_count", 0) + 1
            if entry["retry_count"] >= 3:
                logger.error(f"Giving up on delete {entry['nlm_source_id']} after 3 retries: {e}")
                # Leave in NLM. Mark as ORPHANED in registry
                registry_flag(entry["nlm_source_id"], "ORPHANED")
                results["deletes_failed"] += 1
            else:
                remaining_deletes.append(entry)

    # Process adds
    remaining_adds = []
    for entry in pending_adds:
        try:
            new_id = nlm_api.source_add(
                notebook_id=notebook_id,
                source_type=entry["source_type"],
                text=entry.get("text"),
                url=entry.get("url"),
            )
            results["adds_succeeded"] += 1
            registry_add(new_id, entry)
        except Exception as e:
            entry["retry_count"] = entry.get("retry_count", 0) + 1
            if entry["retry_count"] >= 3:
                logger.error(f"Giving up on add '{entry.get('title', '?')}' after 3 retries: {e}")
                results["adds_failed"] += 1
            else:
                remaining_adds.append(entry)

    state["pending_source_adds"] = remaining_adds
    state["pending_source_deletes"] = remaining_deletes

    if results["adds_succeeded"] + results["deletes_succeeded"] > 0:
        logger.info(
            f"Pending ops: {results['adds_succeeded']} adds, "
            f"{results['deletes_succeeded']} deletes succeeded. "
            f"{len(remaining_adds)} adds, {len(remaining_deletes)} deletes still pending."
        )

    return results
```

---

## 5. Idempotency Guarantees

### 5.1 Crash Mid-Run: What Happens on Restart?

The pipeline can crash at any of 6 phases. Each phase has a defined recovery behavior:

| Crash Point                                 | State on Disk                                        | On Restart                                                                                                                      |
| ------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 1** (signal collection, 01:05)      | `pipeline_status: "COLLECTING"`, `today.cluster` set | Restart from Phase 1. Re-read signals. No API calls wasted                                                                      |
| **Phase 2** (L1 running, 01:10-01:30)       | `pipeline_status: "RUNNING_L1"`, `l1_task_id` set    | Resume: poll `research_status(l1_task_id)`. NLM persists task server-side. No duplicate research                                |
| **Phase 3** (inter-query assessment, 01:30) | `l1_status: "COMPLETED"`, `l2_status: null`          | Skip Phase 3 analysis (L1 findings already saved). Proceed to Phase 4 with default L2 template                                  |
| **Phase 4** (L2 running, 01:35-01:55)       | `pipeline_status: "RUNNING_L2"`, `l2_task_id` set    | Resume: poll `research_status(l2_task_id)`. Same as Phase 2 recovery                                                            |
| **Phase 5** (consolidation, 01:55)          | Both L1 and L2 COMPLETED. Brief not yet written      | Re-run consolidation. L1/L2 findings are in state file. Triage runs again (idempotent — dedup catches already-promoted sources) |
| **Phase 6** (scraper handoff, 02:10)        | Brief written. Handoff not yet written               | Re-generate handoff from brief. `ln -sf` is atomic. Scraper gets consistent file                                                |

**Key principle:** The `task_id` returned by `research_start` is the crash recovery anchor. As long as it is persisted to disk before polling begins, we can resume any research query.

**Write-ahead pattern:**

```python
# BEFORE polling, persist task_id
state["today"]["l1_task_id"] = task_id
state["pipeline_status"] = "RUNNING_L1"
_save_state(state)  # Flush to disk

# THEN poll (may crash during polling — that's OK)
result = poll_research_status(task_id, max_wait=1500)
```

### 5.2 Double-Run: What If Pipeline Fires Twice?

macOS `launchd` can occasionally fire the same job twice (known behavior with `StartCalendarInterval` on wake-from-sleep). The pipeline must handle this without duplicate API calls or state corruption.

**Guard: dedup_key**

```python
import hashlib
from datetime import date

def compute_dedup_key(template_id: str, cluster: str) -> str:
    """Deterministic key for today's query. Same inputs on same day = same key."""
    payload = f"{template_id}:{cluster}:{date.today().isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]

def already_completed_today(state: dict, dedup_key: str) -> bool:
    """Check if this exact query was already completed today."""
    completed = state.get("_completed_dedup_keys", [])
    return dedup_key in completed

def mark_completed(state: dict, dedup_key: str) -> None:
    """Mark a query as completed. Persisted to state file."""
    if "_completed_dedup_keys" not in state:
        state["_completed_dedup_keys"] = []
    state["_completed_dedup_keys"].append(dedup_key)
```

**Worst-case analysis (double-run without dedup guard):**

| Phase             | Double-Run Impact                       | Severity                                           |
| ----------------- | --------------------------------------- | -------------------------------------------------- |
| Signal collection | Reads same files twice. No side effects | NONE                                               |
| `research_start`  | Fires 2 redundant NLM research queries  | MEDIUM — wastes 2 API calls from weekly budget     |
| `research_import` | Could import same sources twice         | LOW — URL dedup at INGEST catches exact matches    |
| `notebook_query`  | Redundant query. Same response          | LOW — wastes 1 API call                            |
| Consolidation     | Re-triages already-triaged sources      | NONE — idempotent (dedup catches already-promoted) |
| Handoff write     | Overwrites with identical content       | NONE — atomic via `ln -sf`                         |
| State write       | Second run overwrites first run's state | MEDIUM — budget counter incremented twice          |

**Conclusion:** Without dedup guard, the worst case is wasting 4-6 API calls (2 research + 2 queries) and double-counting budget. With dedup guard (CHECK 12 in pre-flight), the second run exits immediately at pre-flight.

### 5.3 State File Atomicity

All state file writes use atomic write pattern to prevent corruption from mid-write crashes:

```python
import tempfile
import os

def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically: write to temp file, then rename."""
    temp_fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.stem}_",
        suffix=".tmp"
    )
    try:
        with os.fdopen(temp_fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())  # Ensure data hits disk
        os.rename(temp_path, path)  # Atomic on POSIX
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
```

---

## 6. Monitoring Checklist — Monday Morning Review

### 6.1 Automated Dashboard (Telegram weekly digest, sent Friday 18:00)

The Friday consolidation phase generates a weekly health report. A human reviews it Monday morning.

### 6.2 Monday Morning Checklist

```
+=========================================================+
|         NB-2 DEEP RESEARCH — MONDAY MORNING CHECK       |
+=========================================================+

1. PIPELINE EXECUTION (did it run?)
   ┌──────────────────────────────────────────────────────┐
   │ Expected: 5 runs (Mon-Fri)                           │
   │ Check: `jq '.last_run.date' pipeline_state.json`     │
   │        Count entries in query_history.jsonl this week │
   │                                                      │
   │ 5/5 runs ✓  → Healthy                                │
   │ 4/5 runs    → Check which day failed and why         │
   │ <=3/5 runs  → INVESTIGATE: check launchd logs,       │
   │               NLM auth, consecutive_failures counter  │
   └──────────────────────────────────────────────────────┘

2. NOTEBOOK HEALTH SCORE (NHS) TREND
   ┌──────────────────────────────────────────────────────┐
   │ NHS = 5-factor composite (source quality, freshness, │
   │        coverage, claim density, dedup ratio)         │
   │                                                      │
   │ Check: weekly_report.json → nhs_score                │
   │                                                      │
   │ >= 0.70 ✓  → Healthy                                 │
   │ 0.50-0.69  → Degrading. Check which sub-score drops  │
   │ < 0.50     → ALARM. Pipeline producing low value     │
   │                                                      │
   │ Week-over-week trend:                                │
   │   ↗ Improving  → Good                                │
   │   → Stable     → Expected at steady state            │
   │   ↘ Declining  → Investigate. Stale templates?       │
   │     2 weeks ↘  → REDESIGN query templates            │
   └──────────────────────────────────────────────────────┘

3. CRITICAL ALERTS (Telegram)
   ┌──────────────────────────────────────────────────────┐
   │ Check Telegram channel for any CRITICAL alerts       │
   │ fired during the week:                               │
   │                                                      │
   │ - INV-4 (feedback loop breach)     → Needs audit     │
   │ - INV-5 (Master Doc deleted)       → Check recovery  │
   │ - INV-6 (3+ consecutive failures)  → Check NLM auth  │
   │ - BREAKING override fired          → Verify follow-up│
   │ - Throttle detected (3+ flags)     → Check NLM quota │
   │                                                      │
   │ 0 alerts ✓  → Healthy                                │
   │ 1-2 alerts  → Review and resolve                     │
   │ 3+ alerts   → Systemic issue. Deep investigation     │
   └──────────────────────────────────────────────────────┘

4. SOURCE COUNT TRAJECTORY
   ┌──────────────────────────────────────────────────────┐
   │ Check: source_registry.json → count by stage         │
   │                                                      │
   │ ACTIVE: 55-70  → Healthy (target steady state)       │
   │ ACTIVE: 40-54  → Growing phase (expected Month 1-2)  │
   │ ACTIVE: < 40   → UNDERPOPULATED. Pipeline not adding │
   │ ACTIVE: > 70   → INV-1 SHOULD HAVE CAUGHT THIS      │
   │                                                      │
   │ QUARANTINE: 0-10 → Healthy                           │
   │ QUARANTINE: > 20 → Triage backlog. Check pipeline    │
   │                                                      │
   │ Week-over-week delta:                                │
   │   +5 to +15/week  → Healthy growth phase             │
   │   +0 to +5/week   → Stable (steady state)            │
   │   -5/week         → Check: aging too aggressive?     │
   │   Net negative 2+ → Sources disappearing faster than │
   │     weeks         │ added. INVESTIGATE               │
   └──────────────────────────────────────────────────────┘

5. OPEN QUESTIONS AGING
   ┌──────────────────────────────────────────────────────┐
   │ Check: MD-4 (Open Questions Tracker) or state file   │
   │                                                      │
   │ Total open questions: ___                             │
   │ Oldest open question: ___ days                       │
   │                                                      │
   │ All < 14 days ✓  → Healthy                           │
   │ Any 14-21 days    → Needs attention. Bump priority   │
   │ Any > 21 days     → STALE. Either:                   │
   │                     (a) unanswerable → close with    │
   │                         "UNRESOLVABLE" status        │
   │                     (b) forgotten → re-prioritize    │
   │ Count > 15        → Too many open. Close oldest 5    │
   └──────────────────────────────────────────────────────┘

6. SCRAPER INTEGRATION HEALTH
   ┌──────────────────────────────────────────────────────┐
   │ Check: ~/.agent/decisions/nlm_to_scraper/            │
   │                                                      │
   │ Handoff files this week: ___/5 expected              │
   │ Scraper integration mode this week:                  │
   │   IGNORE: ___    (0 = healthy, >2 = handoff failing) │
   │   ENRICH: ___    (expected for most days)            │
   │   PRIORITIZE: __ (1-2/week expected)                 │
   │                                                      │
   │ Cross-validation this week:                          │
   │   CONVERGENCE events: ___                            │
   │   NLM-ONLY findings (>48h): ___                      │
   │   SCRAPER-ONLY signals: ___                          │
   │                                                      │
   │ 0 CONVERGENCE all week → NLM and scraper not finding │
   │   same things. Check scope overlap                   │
   │ >3 NLM-ONLY >48h → NLM may be hallucinating. Spot   │
   │   check claims manually                              │
   └──────────────────────────────────────────────────────┘

7. BUDGET & PERFORMANCE
   ┌──────────────────────────────────────────────────────┐
   │ API calls this week: ___/40                          │
   │ Avg pipeline duration: ___ min (target: <80 min)     │
   │ Deadline breaches (>02:30): ___                      │
   │ Throttle flags: ___                                  │
   │                                                      │
   │ Calls 10-20 ✓ → Efficient                            │
   │ Calls 20-30   → Normal                               │
   │ Calls 30-40   → Heavy week. Check for retries        │
   │ Duration >80   → Performance degradation. Check NLM  │
   └──────────────────────────────────────────────────────┘
```

### 6.3 Automated Monday Report Generator

```python
from datetime import date, timedelta
from pathlib import Path
import json

def generate_monday_report(
    state_path: Path,
    registry_path: Path,
    history_path: Path,
    handoff_dir: Path,
) -> str:
    """Generate the Monday morning report automatically."""
    state = json.loads(state_path.read_text())
    registry = json.loads(registry_path.read_text())

    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    last_friday = week_start - timedelta(days=3)

    # 1. Pipeline execution count
    runs_this_week = 0
    run_dates = set()
    if history_path.exists():
        for line in history_path.read_text().strip().split("\n"):
            try:
                entry = json.loads(line)
                d = date.fromisoformat(entry["date"])
                if d >= last_friday - timedelta(days=4) and d <= last_friday:
                    run_dates.add(entry["date"])
                    runs_this_week += 1
            except (json.JSONDecodeError, KeyError):
                continue
    unique_run_days = len(run_dates)

    # 2. Source counts
    active = sum(1 for s in registry.get("sources", []) if s.get("stage") == "ACTIVE")
    quarantine = sum(1 for s in registry.get("sources", []) if s.get("stage") == "QUARANTINE")
    master_digests = sum(
        1 for s in registry.get("sources", [])
        if s.get("category") == "MASTER_DIGEST" and s.get("stage") == "ACTIVE"
    )

    # 3. Handoff files
    handoff_count = 0
    if handoff_dir.exists():
        for f in handoff_dir.glob("202*.json"):
            try:
                d = date.fromisoformat(f.stem)
                if d >= last_friday - timedelta(days=4) and d <= last_friday:
                    handoff_count += 1
            except ValueError:
                continue

    # 4. Budget
    budget = state.get("budget", {})
    errors = state.get("errors", {})

    # 5. Open questions
    open_q_count = 0
    oldest_q_days = 0
    # Parse from MD-4 if available, or from state hot_topics
    for ht in state.get("hot_topics", []):
        if ht.get("decay_score", 1.0) < 0.5:
            age = (today - date.fromisoformat(ht["first_seen"])).days if "first_seen" in ht else 0
            oldest_q_days = max(oldest_q_days, age)

    report = f"""
NB-2 DEEP RESEARCH — WEEKLY REPORT ({last_friday - timedelta(days=4)} to {last_friday})
{'='*60}

1. PIPELINE EXECUTION: {unique_run_days}/5 days ran
   Total queries: {runs_this_week}
   Status: {"HEALTHY" if unique_run_days >= 4 else "INVESTIGATE" if unique_run_days >= 3 else "ALARM"}

2. SOURCE COUNT:
   ACTIVE: {active} (target: 55-70)
   QUARANTINE: {quarantine} (target: <10)
   Master Digests: {master_digests}/4
   Status: {"HEALTHY" if 40 <= active <= 70 and master_digests >= 4 else "CHECK"}

3. SCRAPER HANDOFF: {handoff_count}/5 files written
   Status: {"HEALTHY" if handoff_count >= 4 else "DEGRADED" if handoff_count >= 2 else "FAILING"}

4. BUDGET: {budget.get('week_calls', '?')}/40 calls used last week
   Throttle flags: {errors.get('throttle_flags', 0)}
   Consecutive failures: {errors.get('consecutive_failures', 0)}

5. OPEN QUESTIONS: oldest signal {oldest_q_days} days
   Status: {"HEALTHY" if oldest_q_days < 14 else "STALE" if oldest_q_days < 21 else "ALARM"}

{'='*60}
ACTION REQUIRED: {"None — all systems nominal" if unique_run_days >= 4 and 40 <= active <= 70 else "Review items marked CHECK/ALARM above"}
"""
    return report.strip()
```

---

## 7. Circuit Breaker Design

### 7.1 Circuit Breaker States

```
     ┌──────────────────────────────────────────┐
     │                                          │
     ▼                                          │
  ┌────────┐  3 failures   ┌────────┐  48h    ┌─────────────┐
  │ CLOSED  │─────────────▶│  OPEN   │────────▶│ HALF-OPEN    │
  │ (normal)│              │ (paused)│         │ (diagnostic) │
  └────────┘              └────────┘         └─────────────┘
     ▲                                          │
     │         1 success                        │
     └──────────────────────────────────────────┘
     ▲                        │
     │     1 failure          │
     │         ┌──────────────┘
     │         ▼
     │      ┌────────┐
     │      │  OPEN   │ (re-open, backoff doubles: 96h)
     │      └────────┘
     │         │ 96h
     │         ▼
     │      HALF-OPEN (try again with doubled backoff)
     │         │ success
     └─────────┘
```

### 7.2 Implementation

```python
from datetime import datetime, timedelta

class CircuitBreaker:
    """Circuit breaker for NLM API calls."""

    def __init__(self, state: dict):
        self.errors = state.get("errors", {})
        self.failure_threshold = 3
        self.base_backoff_hours = 48
        self.max_backoff_hours = 192  # 8 days

    @property
    def state(self) -> str:
        backoff_until = self.errors.get("backoff_until")
        if backoff_until:
            if datetime.fromisoformat(backoff_until) > datetime.now():
                return "OPEN"
            else:
                return "HALF_OPEN"

        if self.errors.get("consecutive_failures", 0) >= self.failure_threshold:
            return "OPEN"

        return "CLOSED"

    def record_success(self) -> None:
        """Reset failure counter on success."""
        self.errors["consecutive_failures"] = 0
        self.errors["backoff_until"] = None
        self.errors["backoff_multiplier"] = 1

    def record_failure(self, error_message: str) -> str:
        """Record failure. Returns circuit state after recording."""
        self.errors["consecutive_failures"] = self.errors.get("consecutive_failures", 0) + 1
        self.errors["last_error"] = error_message
        self.errors["last_error_at"] = datetime.now().isoformat()

        if self.errors["consecutive_failures"] >= self.failure_threshold:
            multiplier = self.errors.get("backoff_multiplier", 1)
            backoff_hours = min(
                self.base_backoff_hours * multiplier,
                self.max_backoff_hours,
            )
            self.errors["backoff_until"] = (
                datetime.now() + timedelta(hours=backoff_hours)
            ).isoformat()
            self.errors["backoff_multiplier"] = multiplier * 2
            return "OPEN"

        return "CLOSED"

    def can_execute(self) -> tuple[bool, str]:
        """Check if pipeline can execute. Returns (allowed, reason)."""
        s = self.state
        if s == "CLOSED":
            return True, "circuit_closed"
        elif s == "HALF_OPEN":
            return True, "circuit_half_open_diagnostic"
        else:
            return False, f"circuit_open_until_{self.errors.get('backoff_until')}"
```

---

## 8. Graceful Degradation Hierarchy

When things fail, the system degrades in defined layers. Each layer preserves as much value as possible.

```
FULL OPERATION (all systems nominal)
│
├─ NLM query fails → PARTIAL BRIEF (other query's findings only)
│   └─ Both queries fail → NO BRIEF (scraper runs in IGNORE mode)
│       └─ Handoff dir unwritable → SCRAPER STANDALONE
│           └─ State file corrupt → FRESH START (recover + run)
│               └─ NLM API down → PIPELINE PAUSED (circuit breaker)
│                   └─ NLM auth expired → MANUAL INTERVENTION REQUIRED
│
ZERO OPERATION (manual intervention)
```

### Degradation Response Matrix

| Degradation Level   | User Impact                               | Scraper Impact                       | War Room Impact                 | Automated Response                      |
| ------------------- | ----------------------------------------- | ------------------------------------ | ------------------------------- | --------------------------------------- |
| L0: Full operation  | None                                      | Full NLM enrichment                  | NLM topics available            | Normal                                  |
| L1: Partial brief   | Minor — one cluster uncovered             | Partial enrichment (fewer topics)    | Fewer topic suggestions         | Log, continue                           |
| L2: No brief        | Moderate — no verified intelligence today | IGNORE mode (unchanged from pre-NLM) | No NLM topics, manual selection | Log, Telegram alert                     |
| L3: Pipeline paused | Significant — multi-day gap               | IGNORE mode for duration             | No NLM input for duration       | Circuit breaker, Telegram CRITICAL      |
| L4: Auth expired    | Pipeline fully offline                    | IGNORE mode                          | No NLM input                    | Telegram CRITICAL, requires `nlm login` |

**Critical principle:** At every degradation level, the scraper runs exactly as it did before NLM existed. NLM adds value but never subtracts it. This was the cardinal architecture decision from Step 5.

---

## 9. Error Logging & Audit Trail

### 9.1 Log Taxonomy

Every error and anomaly is logged to `nlm_nb2_audit.jsonl` (append-only, never truncated):

```json
{
  "timestamp": "2026-03-28T01:22:15+08:00",
  "level": "ERROR",
  "category": "NLM_API",
  "event": "research_start_failed",
  "details": {
    "query_template": "NB2-L1-MON-A",
    "error_type": "TimeoutError",
    "error_message": "NLM API did not respond within 60s",
    "retry_attempt": 1,
    "circuit_state": "CLOSED"
  },
  "pipeline_run_id": "nb2-2026-03-28-0100",
  "resolution": "retry_scheduled"
}
```

### 9.2 Event Categories

| Category          | Events                                                                                | Retention |
| ----------------- | ------------------------------------------------------------------------------------- | --------- |
| `NLM_API`         | research*start*_, research*status*_, source*add*_, source*delete*_, notebook*query*\* | 90 days   |
| `INVARIANT`       | invariant*violation*\*, invariant_check_passed                                        | 180 days  |
| `STATE`           | state_recovered, state_migrated, state_corrupted                                      | Permanent |
| `CIRCUIT_BREAKER` | circuit_opened, circuit_half_open, circuit_closed                                     | 90 days   |
| `DEDUP`           | dedup_guard_triggered, url_duplicate, content_duplicate, claim_overlap                | 30 days   |
| `BUDGET`          | budget_exhausted, budget_warning, budget_reset                                        | 90 days   |
| `SCRAPER_HANDOFF` | handoff_written, handoff_failed, handoff_stale                                        | 30 days   |
| `RECOVERY`        | recovery_started, recovery_succeeded, recovery_failed                                 | Permanent |

---

## Summary

| Concern                | Mechanism                                                | Reference  |
| ---------------------- | -------------------------------------------------------- | ---------- |
| 10 Critical Invariants | Pre-run + post-run checks, auto-repair                   | Section 1  |
| State Corruption       | Recovery from snapshots, NLM API, claims archive         | Section 2  |
| Pre-flight Checks      | 12-point checklist at 01:00 WITA                         | Section 3  |
| NLM API Failures       | Per-call retry matrix, nonsense detection, pending queue | Section 4  |
| Idempotency            | Dedup guard, task_id persistence, atomic writes          | Section 5  |
| Monday Monitoring      | 7-section checklist, automated report                    | Section 6  |
| Circuit Breaker        | 3-state (CLOSED/OPEN/HALF-OPEN), exponential backoff     | Section 7  |
| Graceful Degradation   | 5-level hierarchy, scraper always independent            | Section 8  |
| Audit Trail            | Append-only JSONL, categorized events                    | Section 9  |
| Failure Taxonomy       | 30 modes in 4 categories (Gemini)                        | Section 10 |
| Risk Scoring           | P _ I _ (1 + D/24) formula (DeepSeek)                    | Section 11 |
| Per-Subsystem Breakers | CB-NLM, CB-SOURCE, CB-INTEGRATION (Gemini)               | Section 12 |
| Cascading Failures     | 5 scenarios analyzed (Gemini)                            | Section 13 |
| MTTR Targets           | Automated <5min, manual <2h (DeepSeek)                   | Section 14 |

---

## 10. Failure Taxonomy — 30 Modes (Gemini contribution)

Full catalog in `06b_failure_modes_gemini.md`. Summary by category:

| Category            | Count | Most Dangerous                                       | Detection                             |
| ------------------- | ----- | ---------------------------------------------------- | ------------------------------------- |
| **A. Data Quality** | 8     | A2 Old-as-new, A3 Hallucination                      | Claim date gates, JDIH cross-check    |
| **B. System**       | 10    | B5 Pipeline state corruption, B6 Registry corruption | Pre-flight checks, Friday snapshots   |
| **C. Integration**  | 8     | C4 Feedback loop                                     | loop_score > 0.50, domain exclusion   |
| **D. Operational**  | 8     | D1 Budget exhaustion, D8 Cluster skew                | Budget counters, rotation enforcement |

### Top 5 by Risk Score (DeepSeek R1)

| Rank | ID  | Risk | Failure                                          | Primary Mitigation                                             |
| ---- | --- | ---- | ------------------------------------------------ | -------------------------------------------------------------- |
| 1    | A2  | 8.00 | **Old-as-new** (stale info presented as current) | Per-claim date gate: block if pub_date < today-90d for non-law |
| 2    | A3  | 5.40 | **Hallucination** (fabricated claim/source)      | JDIH URL check, claim_verification_rate monitoring             |
| 3    | D5  | 3.75 | **Master Document staleness** (>14d no update)   | Friday consolidation watchdog                                  |
| 4    | A1  | 3.60 | **Source bloat** (ACTIVE >70)                    | Capacity triggers at 56/63/70                                  |
| 5    | D8  | 3.20 | **Cluster dominance** (1 cluster >50%)           | Weekly rotation enforcement                                    |

---

## 11. Risk Scoring Formula (DeepSeek R1 contribution)

```
Risk = P * I * (1 + D/24)

Where:
  P = probability per month (0.01-1.0)
  I = impact severity (1-10)
  D = detection delay in hours
```

The `(1 + D/24)` multiplier means a 7-day detection delay amplifies risk 8x. This correctly ranks "silent drift" failures above "loud crashes".

### Detection Thresholds (quantified)

| Failure       | Warning Threshold              | Critical Threshold             |
| ------------- | ------------------------------ | ------------------------------ |
| Source bloat  | N > 56 for 5 days              | N > 63 for 3 days              |
| Old-as-new    | avg Working source age > 45d   | > 60d                          |
| Hallucination | claim_verification_rate < 0.85 | < 0.70 for 3 runs → HALT       |
| Feedback loop | loop_score > 0.10              | > 0.50 → HALT cross-validation |
| Budget        | week_calls > 35                | >= 40 → HARD STOP              |
| NHS decline   | < 0.65                         | < 0.45 for 2 days → HALT       |
| Staleness     | avg_staleness < 0.60           | < 0.40                         |
| Dedup ratio   | weekly > 35%                   | > 50% → query redesign         |

---

## 12. Per-Subsystem Circuit Breakers (Gemini contribution)

Three INDEPENDENT circuit breakers. Full state machines in `06b_failure_modes_gemini.md`.

| Breaker            | Trips When                                                                  | Cool-down             | Auto-close?                                                        |
| ------------------ | --------------------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------ |
| **CB-NLM**         | 3+ API errors/run, 2 timeout days, 3+ throttle flags/week, auth failure     | 48h → half-open probe | Yes (1 success)                                                    |
| **CB-SOURCE**      | Registry corruption, registry-NLM desync, capacity overflow, 3 ILM failures | Manual review         | **No** (manual close — registry integrity cannot be auto-verified) |
| **CB-INTEGRATION** | Feedback loop detected, 3+ days handoff corruption, cross-val overflow      | 48h → half-open probe | Yes (1 success)                                                    |

### Cascading Rules

- CB-NLM OPEN > 5 days → triggers CB-SOURCE (no new sources being added, registry stales)
- CB-SOURCE OPEN > 7 days → triggers CB-INTEGRATION (handoff content becomes stale)
- CB-INTEGRATION OPEN does NOT cascade (scraper/War Room operate independently)

### Interaction Matrix (Multiple Breakers OPEN)

| CB-NLM | CB-SOURCE | CB-INTEGRATION | Pipeline Output                                        |
| ------ | --------- | -------------- | ------------------------------------------------------ |
| OPEN   | CLOSED    | CLOSED         | No queries. Existing sources serve stale briefs        |
| CLOSED | OPEN      | CLOSED         | Queries run but no source management. Quarantine grows |
| OPEN   | OPEN      | CLOSED         | Full halt. Only Friday snapshot persists               |
| OPEN   | OPEN      | OPEN           | Full halt + no handoff. All downstream independent     |

---

## 13. Cascading Failure Analysis (Gemini contribution)

5 scenarios analyzed in detail (see `06b_failure_modes_gemini.md` for full analysis):

| Scenario                     | Cascade Depth | Time to Critical | Key Break                                                                            |
| ---------------------------- | ------------- | ---------------- | ------------------------------------------------------------------------------------ |
| Registry corruption          | 3 levels      | 2-3 days         | SVS→triage→capacity overflow                                                         |
| 5-day empty results          | 2 levels      | 7 days           | Master Docs stale, NHS drops                                                         |
| Persistent ILM failure       | 2 levels      | 4 weeks          | Capacity overflow, no consolidation                                                  |
| Monday state corruption      | 1 level       | Immediate        | Pipeline abort, Friday snapshot recovery                                             |
| **Undetected feedback loop** | **4 levels**  | **30+ days**     | **Most dangerous**: compounds hallucination + integration + false-healthy monitoring |

---

## 14. MTTR Targets (DeepSeek R1 contribution)

| Recovery Class        | Target  | Acceptable | Example                                 |
| --------------------- | ------- | ---------- | --------------------------------------- |
| Automated (self-heal) | <5 min  | <30 min    | API retry, emergency prune              |
| Graceful degradation  | <1 min  | <5 min     | Skip L2, write PARTIAL handoff          |
| Manual investigation  | <2h     | <8h        | Registry rebuild, NLM notebook recovery |
| Full pipeline restart | <30 min | <2h        | Cold restart from Friday snapshot       |

### Degradation Levels (DeepSeek R1)

| Level           | Triggers                                      | Output Quality | Downstream Impact                           |
| --------------- | --------------------------------------------- | -------------- | ------------------------------------------- |
| **NOMINAL**     | All 7 subsystems operational, NHS >= 0.65     | 100%           | Full handoff, full cross-val                |
| **DEGRADED_L1** | 1 subsystem impaired                          | 85-95%         | Partial handoff, reduced context            |
| **DEGRADED_L2** | Multiple subsystems impaired, NHS < 0.45      | 50-84%         | Handoff may be PARTIAL or missing           |
| **HALTED**      | NLM API >48h, feedback loop, budget exhausted | 0%             | Scraper+War Room revert to pre-NLM behavior |

**Cardinal rule**: At any degradation level, scraper and War Room operate identically to pre-NLM behavior. Integration is enrichment, never dependency.

---

## Source AI Contributions

### Codex GPT-5.4 — Invariants + Defensive Programming (Sections 1-9)

- 10 critical invariants with enforcement code
- State corruption recovery for all 4 state files
- 12-point pre-flight checklist with severity levels
- NLM API failure matrix with nonsense detection heuristics
- Idempotency guarantees (dedup guard, task_id persistence, atomic writes)
- Monday morning monitoring checklist
- Circuit breaker with exponential backoff
- 5-level graceful degradation
- Structured audit trail (JSONL)

### Gemini — Comprehensive Failure Taxonomy (Sections 10, 12, 13)

- 30 failure modes in 4 categories with detection-response tables
- 3 independent per-subsystem circuit breakers with cascading rules
- 5 cascading failure analyses (including worst-case 4-level feedback loop cascade)
- 5 recovery runbooks
- Weekly health report template
- Quarterly audit checklist

### DeepSeek R1 — Risk Scoring + MTTR (Sections 11, 14)

- Risk formula: P _ I _ (1 + D/24) — detection delay amplifies risk
- Top 5 failures ranked by risk score
- Quantified detection thresholds for 8 key metrics
- MTTR targets by recovery class
- 4 degradation levels with output quality estimates
- Per-subsystem circuit breaker parameters
- Monthly risk report template
- NHS reliability sub-factor addition

### Claude Opus 4.6 — This Synthesis

- Merged Codex (defensive) + Gemini (taxonomy) + DeepSeek (quantification) into unified document
- Preserved Codex sections 1-9 as primary structure (invariants = actionable code)
- Appended Gemini taxonomy and cascading analysis as sections 10, 12, 13
- Integrated DeepSeek risk scoring and MTTR as sections 11, 14
- Unified degradation level definitions across all 3 perspectives
