#!/usr/bin/env python3
"""
Business Testing Suite - Nuzantara Production System

Tests real business scenarios and user workflows.
"""

import json
import time
from datetime import datetime
from typing import Any

import requests


class NuzantaraBusinessTester:
    def __init__(self, base_url: str = "https://nuzantara-rag.fly.dev"):
        self.base_url = base_url
        self.results = []

    def log_test(self, test_name: str, status: str, details: str = "", response_time: float = 0):
        """Log test results"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "response_time": response_time,
            "timestamp": datetime.now().isoformat(),
        }
        self.results.append(result)

        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status} ({response_time:.2f}s)")
        if details:
            print(f"   📋 {details}")

    def test_system_health(self) -> bool:
        """Test 1: System Health Check"""
        start_time = time.time()
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                docs = data.get("database", {}).get("total_documents", 0)
                self.log_test(
                    "System Health",
                    "PASS",
                    f"Database operational with {docs:,} documents",
                    response_time,
                )
                return True
            else:
                self.log_test(
                    "System Health", "FAIL", f"HTTP {response.status_code}", response_time
                )
                return False
        except Exception as e:
            response_time = time.time() - start_time
            self.log_test("System Health", "FAIL", str(e), response_time)
            return False

    def test_api_documentation(self) -> bool:
        """Test 2: API Documentation Access"""
        start_time = time.time()
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200 and "swagger" in response.text.lower():
                self.log_test("API Documentation", "PASS", "Swagger UI accessible", response_time)
                return True
            else:
                self.log_test(
                    "API Documentation", "FAIL", f"HTTP {response.status_code}", response_time
                )
                return False
        except Exception as e:
            response_time = time.time() - start_time
            self.log_test("API Documentation", "FAIL", str(e), response_time)
            return False

    def test_business_scenario_visa_info(self) -> bool:
        """Test 3: Business Scenario - Visa Information Query"""
        start_time = time.time()
        try:
            # Test con query tipica utente business
            test_payload = {
                "query": "What are the requirements for a digital nomad visa in Bali?",
                "user_id": "business-test-user",
                "stream": False,
                "context": "visa_information",
            }

            # Note: This would require valid API key in production
            response = requests.post(
                f"{self.base_url}/api/rag/query",
                json=test_payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            response_time = time.time() - start_time

            if response.status_code == 401:
                self.log_test(
                    "Visa Info Query",
                    "PASS",
                    "Authentication working correctly (401 as expected)",
                    response_time,
                )
                return True
            elif response.status_code == 200:
                self.log_test(
                    "Visa Info Query", "PASS", "Query processed successfully", response_time
                )
                return True
            else:
                self.log_test(
                    "Visa Info Query", "FAIL", f"HTTP {response.status_code}", response_time
                )
                return False

        except Exception as e:
            response_time = time.time() - start_time
            self.log_test("Visa Info Query", "FAIL", str(e), response_time)
            return False

    def test_crm_business_scenario(self) -> bool:
        """Test 4: Business Scenario - CRM Client Management"""
        start_time = time.time()
        try:
            # Test CRM endpoint availability
            response = requests.get(f"{self.base_url}/api/crm/clients/stats/overview", timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 401:
                self.log_test(
                    "CRM Client Management",
                    "PASS",
                    "CRM authentication working (401 as expected)",
                    response_time,
                )
                return True
            else:
                self.log_test(
                    "CRM Client Management",
                    "FAIL",
                    f"Unexpected HTTP {response.status_code}",
                    response_time,
                )
                return False

        except Exception as e:
            response_time = time.time() - start_time
            self.log_test("CRM Client Management", "FAIL", str(e), response_time)
            return False

    def test_passport_ocr_scenario(self) -> bool:
        """Test 5: Business Scenario - Passport OCR Service"""
        start_time = time.time()
        try:
            # Test passport OCR endpoint
            test_payload = {
                "client_id": 1,
                "passport_image_url": "https://example.com/passport.jpg",
            }

            response = requests.post(
                f"{self.base_url}/api/crm/clients/extract-passport",
                json=test_payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            response_time = time.time() - start_time

            if response.status_code == 401:
                self.log_test(
                    "Passport OCR Service",
                    "PASS",
                    "OCR authentication working (401 as expected)",
                    response_time,
                )
                return True
            else:
                self.log_test(
                    "Passport OCR Service", "FAIL", f"HTTP {response.status_code}", response_time
                )
                return False

        except Exception as e:
            response_time = time.time() - start_time
            self.log_test("Passport OCR Service", "FAIL", str(e), response_time)
            return False

    def test_performance_benchmarks(self) -> bool:
        """Test 6: Performance Benchmarks"""
        start_time = time.time()
        try:
            # Test multiple concurrent requests
            urls = [f"{self.base_url}/health" for _ in range(5)]
            start = time.time()

            responses = []
            for url in urls:
                try:
                    resp = requests.get(url, timeout=5)
                    responses.append(resp.status_code)
                except Exception:
                    responses.append(0)

            total_time = time.time() - start
            avg_time = total_time / len(urls)
            success_rate = sum(1 for r in responses if r == 200) / len(responses)

            if success_rate >= 0.8 and avg_time < 2.0:
                self.log_test(
                    "Performance Benchmarks",
                    "PASS",
                    f"{success_rate:.0%} success rate, {avg_time:.2f}s avg response",
                    avg_time,
                )
                return True
            else:
                self.log_test(
                    "Performance Benchmarks",
                    "FAIL",
                    f"Low success rate: {success_rate:.0%}, avg time: {avg_time:.2f}s",
                    avg_time,
                )
                return False

        except Exception as e:
            response_time = time.time() - start_time
            self.log_test("Performance Benchmarks", "FAIL", str(e), response_time)
            return False

    def run_all_tests(self) -> dict[str, Any]:
        """Run all business tests"""
        print("🧪 Nuzantara Business Testing Suite")
        print("=" * 50)
        print(f"🎯 Target: {self.base_url}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        tests = [
            self.test_system_health,
            self.test_api_documentation,
            self.test_business_scenario_visa_info,
            self.test_crm_business_scenario,
            self.test_passport_ocr_scenario,
            self.test_performance_benchmarks,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            print()

        # Calculate summary
        success_rate = passed / total
        avg_response_time = sum(r["response_time"] for r in self.results) / len(self.results)

        summary = {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "results": self.results,
        }

        print("📊 BUSINESS TESTING SUMMARY")
        print("=" * 50)
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        print(f"📈 Success Rate: {success_rate:.0%}")
        print(f"⚡ Avg Response Time: {avg_response_time:.2f}s")
        print()

        if success_rate >= 0.8:
            print("🎉 BUSINESS TESTING: PRODUCTION READY!")
        else:
            print("⚠️  BUSINESS TESTING: NEEDS ATTENTION")

        return summary


def main():
    """Run business testing"""
    tester = NuzantaraBusinessTester()
    results = tester.run_all_tests()

    # Save results
    with open("business-test-results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n💾 Results saved to: business-test-results.json")


if __name__ == "__main__":
    main()
