"""
Core Guardian — Unified Check Runner

Runs all quality checks and produces a consolidated report.
Designed to be called from the watchdog or manually.

Usage:
    python -m apps.evaluator.core_guardian.checks.run_all [--json] [--severity=warning]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from apps.evaluator.core_guardian.checks.cache_invalidation_audit import (
    run_audit as run_cache_audit,
)
from apps.evaluator.core_guardian.checks.empty_catch_audit import (
    run_audit as run_catch_audit,
)
from apps.evaluator.core_guardian.checks.rbac_audit import (
    run_audit as run_rbac_audit,
)
from apps.evaluator.core_guardian.checks.dead_code_audit import (
    run_audit as run_dead_code_audit,
)
from apps.evaluator.core_guardian.checks.api_contract_audit import (
    run_audit as run_contract_audit,
)


def _find_project_root() -> Path:
    """Find project root by walking up from this file."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".git").exists() and (current / "apps" / "backend-rag").exists():
            return current
        current = current.parent
    raise RuntimeError("Cannot find project root")


def run_all(project_root: Path | None = None, severity_filter: str = "all") -> dict:
    """Run all checks and return consolidated results."""
    root = project_root or _find_project_root()

    results = {}
    total_findings = 0
    total_errors = 0
    t0 = time.monotonic()

    # 1. Cache Invalidation
    print("▸ Running cache invalidation audit...", flush=True)
    cache_res = run_cache_audit(root)
    results["cache_invalidation"] = {
        "findings": len(cache_res),
        "details": [str(f) for f in cache_res],
    }
    total_findings += len(cache_res)

    # 2. Empty Catch Blocks
    print("▸ Running empty catch audit...", flush=True)
    catch_res = run_catch_audit(root)
    results["empty_catches"] = {
        "findings": catch_res.total,
        "files_scanned": catch_res.files_scanned,
        "details": [str(f) for f in catch_res.findings],
    }
    total_findings += catch_res.total

    # 3. RBAC
    print("▸ Running RBAC audit...", flush=True)
    rbac_res = run_rbac_audit(root)
    errors_only = [f for f in rbac_res.findings if f.severity == "error"]
    results["rbac"] = {
        "findings": rbac_res.total,
        "errors": len(errors_only),
        "warnings": rbac_res.total - len(errors_only),
        "endpoints_scanned": rbac_res.endpoints_scanned,
        "details": [str(f) for f in rbac_res.findings],
    }
    total_findings += rbac_res.total
    total_errors += len(errors_only)

    # 4. Dead Code / Hardcoded
    print("▸ Running dead code audit...", flush=True)
    dead_res = run_dead_code_audit(root)
    results["dead_code"] = {
        "findings": dead_res.total,
        "files_scanned": dead_res.files_scanned,
        "details": [str(f) for f in dead_res.findings],
    }
    total_findings += dead_res.total

    # 5. API Contract
    print("▸ Running API contract audit...", flush=True)
    contract_res = run_contract_audit(root)
    results["api_contract"] = {
        "findings": contract_res.total,
        "frontend_calls": len(contract_res.frontend_endpoints),
        "backend_routes": len(contract_res.backend_endpoints),
        "details": [str(f) for f in contract_res.findings],
    }
    total_findings += contract_res.total

    elapsed = time.monotonic() - t0

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 2),
        "total_findings": total_findings,
        "total_errors": total_errors,
        "checks": results,
    }

    return summary


def main() -> None:
    json_output = "--json" in sys.argv
    root = _find_project_root()

    report = run_all(root)

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"  Core Guardian — Quality Report")
        print(f"  {report['timestamp']} ({report['elapsed_seconds']}s)")
        print(f"{'=' * 60}")
        print(f"  Total findings: {report['total_findings']}")
        print(f"  Critical errors: {report['total_errors']}")
        print()

        for name, data in report["checks"].items():
            count = data["findings"]
            icon = "✅" if count == 0 else ("🔴" if data.get("errors", 0) > 0 else "⚠️")
            print(f"  {icon} {name}: {count} findings")

        print(f"\n{'=' * 60}")

        # Print details for non-zero checks
        for name, data in report["checks"].items():
            if data["findings"] > 0:
                print(f"\n--- {name} ({data['findings']}) ---")
                for detail in data["details"][:20]:  # Cap at 20 per check
                    print(f"  {detail}")
                if data["findings"] > 20:
                    print(f"  ... and {data['findings'] - 20} more")


if __name__ == "__main__":
    main()
