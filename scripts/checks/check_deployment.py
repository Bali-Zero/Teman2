#!/usr/bin/env python3
"""
Deployment validation script for Reranker Optimization
Checks all components are ready before deployment
"""

import sys
from pathlib import Path

import requests


def check_health_endpoint(url="http://localhost:8000/health"):
    """Check health endpoint is responding"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, data
        return False, f"Status code: {response.status_code}"
    except Exception as e:
        return False, str(e)


def check_reranker_enabled(health_data):
    """Check reranker is enabled in health response"""
    reranker = health_data.get("reranker", {})
    if isinstance(reranker, dict):
        return reranker.get("enabled", False)
    return reranker is True


def check_reranker_stats(health_data):
    """Check reranker stats are available"""
    reranker = health_data.get("reranker", {})
    if isinstance(reranker, dict):
        stats = reranker.get("stats", {})
        return stats is not None and len(stats) > 0
    return False


def check_config_file():
    """Check config file exists and has reranker settings"""
    config_path = Path(__file__).parent.parent / "app" / "config.py"
    if not config_path.exists():
        return False, "Config file not found"

    content = config_path.read_text()
    required_settings = ["enable_reranker", "reranker_cache_enabled", "reranker_cache_size"]

    missing = [s for s in required_settings if s not in content]
    if missing:
        return False, f"Missing settings: {missing}"

    return True, "Config file OK"


def check_service_files():
    """Check required service files exist"""
    base_path = Path(__file__).parent.parent
    required_files = ["services/reranker_service.py", "services/reranker_audit.py"]

    missing = []
    for file_path in required_files:
        if not (base_path / file_path).exists():
            missing.append(file_path)

    if missing:
        return False, f"Missing files: {missing}"

    return True, "All service files present"


def main():
    print("🔍 Reranker Optimization - Deployment Validation")
    print("=" * 60)

    all_checks_passed = True

    # Check 1: Service files
    print("\n1. Checking service files...")
    passed, msg = check_service_files()
    status = "✅" if passed else "❌"
    print(f"   {status} {msg}")
    if not passed:
        all_checks_passed = False

    # Check 2: Config file
    print("\n2. Checking configuration...")
    passed, msg = check_config_file()
    status = "✅" if passed else "❌"
    print(f"   {status} {msg}")
    if not passed:
        all_checks_passed = False

    # Check 3: Health endpoint
    print("\n3. Checking health endpoint...")
    passed, data = check_health_endpoint()
    status = "✅" if passed else "❌"
    print(f"   {status} Health endpoint: {'OK' if passed else data}")
    if not passed:
        all_checks_passed = False
        print("\n⚠️  Cannot continue without health endpoint")
        return 1

    # Check 4: Reranker enabled
    print("\n4. Checking reranker status...")
    reranker_enabled = check_reranker_enabled(data)
    status = "✅" if reranker_enabled else "⚠️"
    print(f"   {status} Reranker enabled: {reranker_enabled}")

    # Check 5: Reranker stats
    print("\n5. Checking reranker statistics...")
    stats_available = check_reranker_stats(data)
    status = "✅" if stats_available else "⚠️"
    print(f"   {status} Statistics available: {stats_available}")

    if stats_available:
        stats = data.get("reranker", {}).get("stats", {})
        print("\n   📊 Current Statistics:")
        print(f"      Total reranks: {stats.get('total_reranks', 0)}")
        print(f"      Avg latency: {stats.get('avg_latency_ms', 0):.2f}ms")
        print(f"      P95 latency: {stats.get('p95_latency_ms', 0):.2f}ms")
        print(f"      Cache hit rate: {stats.get('cache_hit_rate_percent', 0):.1f}%")
        print(f"      Cache enabled: {stats.get('cache_enabled', False)}")
        print(f"      Cache size: {stats.get('cache_size', 0)}/{stats.get('cache_max_size', 0)}")

    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ All critical checks passed - Ready for deployment")
        return 0
    else:
        print("❌ Some checks failed - Review before deployment")
        return 1


if __name__ == "__main__":
    sys.exit(main())
