#!/usr/bin/env python3
"""
Monitor Intel Router logs for errors and warnings.

This script monitors Fly.io logs for Intel-related errors and warnings,
providing real-time alerts and summary reports.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Colors for terminal output
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"


def run_fly_logs(limit: int = 100) -> List[str]:
    """Fetch logs from Fly.io."""
    try:
        result = subprocess.run(
            ["fly", "logs", "-a", "nuzantara-rag", "--limit", str(limit)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.split("\n")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error fetching logs: {e}{RESET}")
        return []
    except FileNotFoundError:
        print(
            f"{RED}Error: fly CLI not found. Install from https://fly.io/docs/hands-on/install-flyctl/{RESET}"
        )
        return []


def analyze_logs(logs: List[str]) -> Dict:
    """Analyze logs for Intel-related issues."""
    errors = []
    warnings = []
    intel_operations = []
    service_calls = {
        "IntelClassificationService": 0,
        "IntelStagingService": 0,
        "IntelApprovalService": 0,
        "IntelAnalyticsService": 0,
    }

    for line in logs:
        line_lower = line.lower()

        # Check for errors
        if "error" in line_lower and (
            "intel" in line_lower or "staging" in line_lower or "approval" in line_lower
        ):
            errors.append(line)

        # Check for warnings
        if "warning" in line_lower and (
            "intel" in line_lower or "staging" in line_lower
        ):
            warnings.append(line)

        # Track Intel operations
        if "/api/intel/" in line:
            intel_operations.append(line)

        # Track service calls
        for service_name in service_calls.keys():
            if service_name in line:
                service_calls[service_name] += 1

    return {
        "errors": errors,
        "warnings": warnings,
        "intel_operations": intel_operations,
        "service_calls": service_calls,
        "total_logs": len(logs),
    }


def print_report(analysis: Dict):
    """Print formatted analysis report."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Intel Router Log Analysis{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total logs analyzed: {analysis['total_logs']}")
    print()

    # Errors
    if analysis["errors"]:
        print(f"{RED}❌ ERRORS FOUND: {len(analysis['errors'])}{RESET}")
        for error in analysis["errors"][:10]:  # Show first 10
            print(f"  {RED}• {error[:100]}{RESET}")
        if len(analysis["errors"]) > 10:
            print(f"  ... and {len(analysis['errors']) - 10} more errors")
        print()
    else:
        print(f"{GREEN}✅ No errors found{RESET}\n")

    # Warnings
    if analysis["warnings"]:
        print(f"{YELLOW}⚠️  WARNINGS: {len(analysis['warnings'])}{RESET}")
        for warning in analysis["warnings"][:5]:  # Show first 5
            print(f"  {YELLOW}• {warning[:100]}{RESET}")
        if len(analysis["warnings"]) > 5:
            print(f"  ... and {len(analysis['warnings']) - 5} more warnings")
        print()
    else:
        print(f"{GREEN}✅ No warnings found{RESET}\n")

    # Intel operations
    print(f"{BLUE}📊 Intel Operations: {len(analysis['intel_operations'])}{RESET}")
    if analysis["intel_operations"]:
        # Count by endpoint
        endpoint_counts = {}
        for op in analysis["intel_operations"]:
            for endpoint in [
                "/api/intel/scraper/submit",
                "/api/intel/staging/",
                "/api/intel/metrics",
                "/api/intel/search",
            ]:
                if endpoint in op:
                    endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
                    break

        for endpoint, count in sorted(
            endpoint_counts.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  • {endpoint}: {count}")
    print()

    # Service calls
    print(f"{BLUE}🔧 Service Calls:{RESET}")
    for service, count in analysis["service_calls"].items():
        if count > 0:
            print(f"  • {service}: {count}")
    print()

    # Summary
    print(f"{BLUE}{'=' * 60}{RESET}")
    if analysis["errors"]:
        print(
            f"{RED}⚠️  ACTION REQUIRED: {len(analysis['errors'])} errors detected{RESET}"
        )
        return 1
    elif analysis["warnings"]:
        print(
            f"{YELLOW}⚠️  Review warnings: {len(analysis['warnings'])} warnings detected{RESET}"
        )
        return 0
    else:
        print(f"{GREEN}✅ All systems operational{RESET}")
        return 0


def main():
    """Main monitoring function."""
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    print(f"{BLUE}Fetching logs from Fly.io...{RESET}")
    logs = run_fly_logs(limit)

    if not logs:
        print(f"{RED}No logs retrieved{RESET}")
        return 1

    print(f"{GREEN}Analyzing {len(logs)} log lines...{RESET}")
    analysis = analyze_logs(logs)

    exit_code = print_report(analysis)

    # Save report to file
    report_file = Path(__file__).parent / "intel_logs_report.json"
    with open(report_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "analysis": {
                    "errors_count": len(analysis["errors"]),
                    "warnings_count": len(analysis["warnings"]),
                    "intel_operations_count": len(analysis["intel_operations"]),
                    "service_calls": analysis["service_calls"],
                },
                "errors": analysis["errors"][:20],  # Save first 20 errors
                "warnings": analysis["warnings"][:10],  # Save first 10 warnings
            },
            f,
            indent=2,
        )

    print(f"{BLUE}Report saved to: {report_file}{RESET}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
