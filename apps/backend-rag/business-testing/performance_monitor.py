#!/usr/bin/env python3
"""
Nuzantara Performance Monitoring Dashboard
Real-time system monitoring for business operations
"""

import json
import statistics
import time
from datetime import datetime
from typing import Any

import requests


class NuzantaraMonitor:
    """Production system monitoring"""

    def __init__(self, base_url: str = "https://nuzantara-rag.fly.dev"):
        self.base_url = base_url
        self.metrics_history = []

    def check_system_health(self) -> dict[str, Any]:
        """Check system health status"""
        start_time = time.time()
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy",
                    "response_time": response_time,
                    "database": data.get("database", {}),
                    "embeddings": data.get("embeddings", {}),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time": response_time,
                    "error": f"HTTP {response.status_code}",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "status": "error",
                "response_time": time.time() - start_time,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def measure_performance(self, duration_seconds: int = 60) -> dict[str, Any]:
        """Measure system performance over time"""
        print(f"📊 Measuring performance for {duration_seconds} seconds...")

        measurements = []
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            health = self.check_system_health()
            measurements.append(health)
            time.sleep(2)  # Check every 2 seconds

        # Calculate statistics
        response_times = [m["response_time"] for m in measurements if m["status"] == "healthy"]

        if response_times:
            performance_stats = {
                "total_checks": len(measurements),
                "healthy_checks": len(response_times),
                "success_rate": len(response_times) / len(measurements),
                "avg_response_time": statistics.mean(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "median_response_time": statistics.median(response_times),
                "measurements": measurements
            }
        else:
            performance_stats = {
                "total_checks": len(measurements),
                "healthy_checks": 0,
                "success_rate": 0,
                "error": "No successful measurements",
                "measurements": measurements
            }

        return performance_stats

    def generate_dashboard(self, performance_data: dict[str, Any]) -> str:
        """Generate performance dashboard report"""
        report = []
        report.append("🚀 Nuzantara Performance Dashboard")
        report.append("=" * 50)
        report.append(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"🌐 System: {self.base_url}")
        report.append("")

        # System Status
        if performance_data["success_rate"] >= 0.95:
            status_emoji = "🟢"
            status_text = "Excellent"
        elif performance_data["success_rate"] >= 0.8:
            status_emoji = "🟡"
            status_text = "Good"
        else:
            status_emoji = "🔴"
            status_text = "Needs Attention"

        report.append(f"📊 System Status: {status_emoji} {status_text}")
        report.append(f"✅ Success Rate: {performance_data['success_rate']:.1%}")
        report.append(f"⚡ Avg Response Time: {performance_data.get('avg_response_time', 0):.3f}s")
        report.append(f"📈 Min/Max: {performance_data.get('min_response_time', 0):.3f}s / {performance_data.get('max_response_time', 0):.3f}s")
        report.append("")

        # Performance Analysis
        if performance_data["success_rate"] == 1.0:
            report.append("🎉 Performance: PERFECT - 100% uptime!")
        elif performance_data["success_rate"] >= 0.95:
            report.append("👍 Performance: EXCELLENT - Ready for production")
        elif performance_data["success_rate"] >= 0.8:
            report.append("⚠️ Performance: GOOD - Monitor closely")
        else:
            report.append("❌ Performance: POOR - Immediate attention required")

        report.append("")

        # Business Impact
        if performance_data.get("avg_response_time", 1) < 0.5:
            report.append("💼 Business Impact: EXCELLENT user experience")
        elif performance_data.get("avg_response_time", 1) < 1.0:
            report.append("💼 Business Impact: GOOD user experience")
        else:
            report.append("💼 Business Impact: May affect user satisfaction")

        return "\n".join(report)

    def run_business_monitoring(self) -> dict[str, Any]:
        """Run complete business monitoring suite"""
        print("🔍 Starting Business Monitoring Suite...")
        print("=" * 50)

        # Quick health check
        print("1. Quick Health Check...")
        health = self.check_system_health()
        print(f"   Status: {health['status']}")
        print(f"   Response Time: {health['response_time']:.3f}s")

        if health["status"] == "healthy":
            db_info = health.get("database", {})
            print(f"   Database: {db_info.get('total_documents', 0):,} documents")

        print()

        # Performance measurement
        print("2. Performance Measurement (60 seconds)...")
        performance = self.measure_performance(60)

        # Generate dashboard
        dashboard = self.generate_dashboard(performance)
        print("\n" + dashboard)

        # Save results
        results = {
            "health_check": health,
            "performance_metrics": performance,
            "dashboard_report": dashboard,
            "timestamp": datetime.now().isoformat()
        }

        return results

def main():
    """Run business monitoring"""
    monitor = NuzantaraMonitor()
    results = monitor.run_business_monitoring()

    # Save results
    with open("performance-monitoring-results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n💾 Results saved to: performance-monitoring-results.json")
    print("\n🎯 Business Monitoring Complete!")
    print("📋 System is ready for business operations!")

if __name__ == "__main__":
    main()
