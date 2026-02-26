#!/usr/bin/env python3
"""
Monitor Intel Router performance metrics.

This script monitors response times, throughput, and error rates
for Intel Router endpoints.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests

# Colors for terminal output
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"

BASE_URL = "https://nuzantara-rag.fly.dev"
ENDPOINTS = [
    "/health",
    "/metrics",
    "/api/intel/metrics",
]


def measure_endpoint_performance(url: str, iterations: int = 5) -> Dict:
    """Measure endpoint performance."""
    times = []
    errors = 0

    for i in range(iterations):
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            duration = time.time() - start_time

            if response.status_code == 200:
                times.append(duration * 1000)  # Convert to ms
            else:
                errors += 1
        except Exception:
            errors += 1

        if i < iterations - 1:
            time.sleep(0.5)  # Small delay between requests

    if not times:
        return {
            "url": url,
            "success": False,
            "errors": errors,
        }

    return {
        "url": url,
        "success": True,
        "iterations": iterations,
        "errors": errors,
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "avg_ms": round(sum(times) / len(times), 2),
        "p50_ms": round(sorted(times)[len(times) // 2], 2),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 2)
        if len(times) > 1
        else times[0],
    }


def analyze_performance(results: List[Dict]) -> Dict:
    """Analyze performance results."""
    analysis = {
        "total_endpoints": len(results),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "performance_status": "UNKNOWN",
        "recommendations": [],
    }

    if not results:
        return analysis

    # Check for performance issues
    slow_endpoints = [
        r for r in results if r.get("success") and r.get("avg_ms", 0) > 1000
    ]
    if slow_endpoints:
        analysis["performance_status"] = "DEGRADED"
        analysis["recommendations"].append(
            f"{len(slow_endpoints)} endpoint(s) with avg response time > 1000ms"
        )

    fast_endpoints = [
        r for r in results if r.get("success") and r.get("avg_ms", 0) < 200
    ]
    if len(fast_endpoints) == len([r for r in results if r.get("success")]):
        analysis["performance_status"] = "EXCELLENT"
    elif not slow_endpoints:
        analysis["performance_status"] = "GOOD"

    return analysis


def print_report(results: List[Dict], analysis: Dict):
    """Print performance report."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Intel Router Performance Report{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Endpoints tested: {analysis['total_endpoints']}")
    print()

    for result in results:
        if result.get("success"):
            print(f"{BLUE}{result['url']}{RESET}")
            print(
                f"  Avg: {result['avg_ms']}ms | Min: {result['min_ms']}ms | Max: {result['max_ms']}ms"
            )
            print(f"  P50: {result['p50_ms']}ms | P95: {result['p95_ms']}ms")

            # Status indicator
            if result["avg_ms"] < 200:
                status = f"{GREEN}✅ Excellent{RESET}"
            elif result["avg_ms"] < 500:
                status = f"{GREEN}✅ Good{RESET}"
            elif result["avg_ms"] < 1000:
                status = f"{YELLOW}⚠️  Acceptable{RESET}"
            else:
                status = f"{RED}🔴 Slow{RESET}"

            print(f"  Status: {status}")
        else:
            print(f"{RED}{result['url']}{RESET}")
            print(f"  {RED}❌ Failed ({result.get('errors', 0)} errors){RESET}")
        print()

    # Summary
    print(f"{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Performance Status: {analysis['performance_status']}{RESET}")

    if analysis["recommendations"]:
        print(f"\n{YELLOW}Recommendations:{RESET}")
        for rec in analysis["recommendations"]:
            print(f"  • {rec}")
    else:
        print(f"{GREEN}✅ All endpoints performing well{RESET}")
    print()


def main():
    """Main monitoring function."""
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    print(f"{BLUE}Measuring performance for {len(ENDPOINTS)} endpoints...{RESET}")
    print(f"Iterations per endpoint: {iterations}\n")

    results = []
    for endpoint in ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        print(f"Testing {endpoint}...")
        result = measure_endpoint_performance(url, iterations)
        results.append(result)

    analysis = analyze_performance(results)
    print_report(results, analysis)

    # Save report
    report_file = Path(__file__).parent / "intel_performance_report.json"
    with open(report_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "results": results,
                "analysis": analysis,
            },
            f,
            indent=2,
        )

    print(f"{BLUE}Report saved to: {report_file}{RESET}")

    # Exit code
    if analysis["performance_status"] == "DEGRADED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
