#!/usr/bin/env python3
"""
Test Intel Router endpoints in production.

This script performs end-to-end tests of Intel Router endpoints
to verify functionality in production environment.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests

# Colors for terminal output
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"

BASE_URL = "https://nuzantara-rag.fly.dev"
API_KEY = None  # Set via environment variable or config


class IntelRouterTester:
    """Test Intel Router endpoints."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """Initialize tester."""
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

        self.results = []

    def test_health(self) -> Dict:
        """Test health endpoint."""
        print(f"{BLUE}Testing /health...{RESET}")
        try:
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            duration = time.time() - start_time

            result = {
                "endpoint": "/health",
                "status": "PASS" if response.status_code == 200 else "FAIL",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "response": response.json() if response.status_code == 200 else None,
            }

            if result["status"] == "PASS":
                print(f"  {GREEN}✅ PASS{RESET} ({result['duration_ms']}ms)")
            else:
                print(f"  {RED}❌ FAIL{RESET} (Status: {result['status_code']})")

            return result

        except Exception as e:
            print(f"  {RED}❌ ERROR: {e}{RESET}")
            return {
                "endpoint": "/health",
                "status": "ERROR",
                "error": str(e),
            }

    def test_metrics(self) -> Dict:
        """Test metrics endpoint."""
        print(f"{BLUE}Testing /api/intel/metrics...{RESET}")
        try:
            start_time = time.time()
            response = self.session.get(
                f"{self.base_url}/api/intel/metrics", timeout=10
            )
            duration = time.time() - start_time

            result = {
                "endpoint": "/api/intel/metrics",
                "status": "PASS" if response.status_code == 200 else "FAIL",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "has_data": False,
            }

            if response.status_code == 200:
                data = response.json()
                result["has_data"] = bool(data)
                result["response_keys"] = (
                    list(data.keys()) if isinstance(data, dict) else []
                )

                if result["status"] == "PASS":
                    print(f"  {GREEN}✅ PASS{RESET} ({result['duration_ms']}ms)")
                    print(f"    Keys: {', '.join(result['response_keys'][:5])}")
                else:
                    print(f"  {RED}❌ FAIL{RESET} (Status: {result['status_code']})")
            else:
                print(f"  {RED}❌ FAIL{RESET} (Status: {result['status_code']})")

            return result

        except Exception as e:
            print(f"  {RED}❌ ERROR: {e}{RESET}")
            return {
                "endpoint": "/api/intel/metrics",
                "status": "ERROR",
                "error": str(e),
            }

    def test_staging_pending(self) -> Dict:
        """Test staging pending endpoint."""
        print(f"{BLUE}Testing /api/intel/staging/pending...{RESET}")
        try:
            start_time = time.time()
            response = self.session.get(
                f"{self.base_url}/api/intel/staging/pending?type=all", timeout=10
            )
            duration = time.time() - start_time

            result = {
                "endpoint": "/api/intel/staging/pending",
                "status": "PASS" if response.status_code in [200, 401] else "FAIL",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "requires_auth": response.status_code == 401,
            }

            if response.status_code == 200:
                data = response.json()
                result["items_count"] = data.get("count", 0)
                result["has_items"] = len(data.get("items", [])) > 0
                print(f"  {GREEN}✅ PASS{RESET} ({result['duration_ms']}ms)")
                print(f"    Items: {result['items_count']}")
            elif response.status_code == 401:
                print(f"  {YELLOW}⚠️  Requires authentication (expected){RESET}")
            else:
                print(f"  {RED}❌ FAIL{RESET} (Status: {result['status_code']})")

            return result

        except Exception as e:
            print(f"  {RED}❌ ERROR: {e}{RESET}")
            return {
                "endpoint": "/api/intel/staging/pending",
                "status": "ERROR",
                "error": str(e),
            }

    def test_prometheus_metrics(self) -> Dict:
        """Test Prometheus metrics endpoint."""
        print(f"{BLUE}Testing /metrics (Prometheus)...{RESET}")
        try:
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/metrics", timeout=10)
            duration = time.time() - start_time

            result = {
                "endpoint": "/metrics",
                "status": "PASS" if response.status_code == 200 else "FAIL",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "intel_metrics_found": False,
            }

            if response.status_code == 200:
                metrics_text = response.text
                intel_metrics = [
                    "zantara_intel_articles",
                    "zantara_intel_classification",
                    "zantara_intel_scraper",
                ]

                found_metrics = [m for m in intel_metrics if m in metrics_text]
                result["intel_metrics_found"] = len(found_metrics) > 0
                result["found_metrics"] = found_metrics

                if result["status"] == "PASS":
                    print(f"  {GREEN}✅ PASS{RESET} ({result['duration_ms']}ms)")
                    print(f"    Intel metrics found: {len(found_metrics)}")
                else:
                    print(f"  {RED}❌ FAIL{RESET} (Status: {result['status_code']})")
            else:
                print(f"  {RED}❌ FAIL{RESET} (Status: {result['status_code']})")

            return result

        except Exception as e:
            print(f"  {RED}❌ ERROR: {e}{RESET}")
            return {
                "endpoint": "/metrics",
                "status": "ERROR",
                "error": str(e),
            }

    def run_all_tests(self) -> Dict:
        """Run all tests."""
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Intel Router Production Tests{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}")
        print(f"Base URL: {self.base_url}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        tests = [
            self.test_health,
            self.test_metrics,
            self.test_staging_pending,
            self.test_prometheus_metrics,
        ]

        for test_func in tests:
            result = test_func()
            self.results.append(result)
            time.sleep(0.5)  # Small delay between tests

        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate test report."""
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r.get("status") == "PASS")
        failed = sum(1 for r in self.results if r.get("status") == "FAIL")
        errors = sum(1 for r in self.results if r.get("status") == "ERROR")

        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Test Summary{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}")
        print(f"Total tests: {total_tests}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        if failed > 0:
            print(f"{RED}Failed: {failed}{RESET}")
        if errors > 0:
            print(f"{RED}Errors: {errors}{RESET}")
        print()

        # Average response time
        durations = [
            r.get("duration_ms", 0) for r in self.results if "duration_ms" in r
        ]
        if durations:
            avg_duration = sum(durations) / len(durations)
            print(f"Average response time: {avg_duration:.2f}ms")
            print()

        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "summary": {
                "total": total_tests,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "success_rate": round((passed / total_tests * 100), 2)
                if total_tests > 0
                else 0,
            },
            "results": self.results,
        }

        return report


def main():
    """Main test function."""
    import os

    base_url = os.getenv("INTEL_API_URL", BASE_URL)
    api_key = os.getenv("INTEL_API_KEY", API_KEY)

    tester = IntelRouterTester(base_url, api_key)
    report = tester.run_all_tests()

    # Save report
    report_file = (
        Path(__file__).parent.parent
        / "monitoring"
        / "intel_production_test_report.json"
    )
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"{BLUE}Report saved to: {report_file}{RESET}\n")

    # Exit code based on results
    if report["summary"]["failed"] > 0 or report["summary"]["errors"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
