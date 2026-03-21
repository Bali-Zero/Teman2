#!/usr/bin/env python3
"""
Manual test script for Portal Tax & Visa endpoints.

Usage:
    python test_portal_endpoints.py <JWT_TOKEN>

Requirements:
    - pip install requests
    - Client JWT token from Portal login

This script tests:
1. GET /api/portal/taxes - All tax obligations + summary
2. GET /api/portal/taxes/summary - Dashboard card
3. GET /api/portal/visa - Visa status + history
4. GET /api/portal/visa/summary - Dashboard card
"""

import json
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library not found")
    print("Install with: pip install requests")
    sys.exit(1)

# Configuration
BASE_URL = "https://nuzantara-rag.fly.dev"
ENDPOINTS = {
    "tax_full": "/api/portal/taxes",
    "tax_summary": "/api/portal/taxes/summary",
    "visa_full": "/api/portal/visa",
    "visa_summary": "/api/portal/visa/summary",
}


def colorize(text: str, color: str) -> str:
    """Add color to terminal output."""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def test_endpoint(endpoint_key: str, endpoint_path: str, token: str) -> dict:
    """Test a single endpoint and return results."""
    url = f"{BASE_URL}{endpoint_path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"\n{'=' * 80}")
    print(f"Testing: {colorize(endpoint_key, 'blue')} - {endpoint_path}")
    print(f"{'=' * 80}")

    try:
        response = requests.get(url, headers=headers, timeout=30)

        result = {
            "endpoint": endpoint_key,
            "url": url,
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
            "content_type": response.headers.get("content-type", ""),
        }

        # Status
        if response.status_code == 200:
            print(f"Status: {colorize('✅ 200 OK', 'green')}")
        elif response.status_code == 401:
            print(f"Status: {colorize('❌ 401 Unauthorized', 'red')}")
            print("⚠️  JWT token is invalid or expired")
        elif response.status_code == 403:
            print(f"Status: {colorize('❌ 403 Forbidden', 'red')}")
            print("⚠️  Token doesn't have client role")
        else:
            print(f"Status: {colorize(f'❌ {response.status_code}', 'red')}")

        # Response time
        rt = result["response_time_ms"]
        rt_color = "green" if rt < 500 else ("yellow" if rt < 1000 else "red")
        print(f"Response Time: {colorize(f'{rt}ms', rt_color)}")

        # Content
        if response.status_code == 200:
            try:
                data = response.json()
                result["data"] = data

                print(f"\n{colorize('Response Data:', 'blue')}")
                print(json.dumps(data, indent=2, default=str))

                # Endpoint-specific validation
                if endpoint_key == "tax_full":
                    assert "summary" in data, "Missing 'summary' key"
                    assert "obligations" in data, "Missing 'obligations' key"
                    print(f"\n✅ Found {len(data['obligations'])} tax obligations")
                    print(f"✅ Summary status: {data['summary'].get('status', 'N/A')}")

                elif endpoint_key == "tax_summary":
                    assert "total_due" in data, "Missing 'total_due' key"
                    assert "status" in data, "Missing 'status' key"
                    print(f"\n✅ Total due: Rp {data.get('total_due', 0):,.0f}")
                    print(f"✅ Status: {data.get('status', 'N/A')}")

                elif endpoint_key == "visa_full":
                    assert "summary" in data, "Missing 'summary' key"
                    assert "current_visa" in data, "Missing 'current_visa' key"
                    assert "history" in data, "Missing 'history' key"
                    has_visa = data["summary"].get("has_active_visa", False)
                    print(f"\n✅ Has active visa: {has_visa}")
                    print(f"✅ Visa history count: {len(data['history'])}")

                elif endpoint_key == "visa_summary":
                    assert "has_active_visa" in data, "Missing 'has_active_visa' key"
                    assert "status" in data, "Missing 'status' key"
                    print(f"\n✅ Has active visa: {data.get('has_active_visa', False)}")
                    print(f"✅ Status: {data.get('status', 'N/A')}")

            except json.JSONDecodeError:
                print(f"{colorize('❌ Invalid JSON response', 'red')}")
                result["error"] = "Invalid JSON"
            except AssertionError as e:
                print(f"{colorize(f'❌ Validation failed: {e}', 'red')}")
                result["error"] = str(e)
        else:
            result["error"] = response.text

        return result

    except requests.exceptions.Timeout:
        print(f"{colorize('❌ Request timeout (>30s)', 'red')}")
        return {"endpoint": endpoint_key, "success": False, "error": "Timeout"}
    except requests.exceptions.ConnectionError:
        print(f"{colorize('❌ Connection error', 'red')}")
        return {"endpoint": endpoint_key, "success": False, "error": "Connection failed"}
    except Exception as e:
        print(f"{colorize(f'❌ Unexpected error: {e}', 'red')}")
        return {"endpoint": endpoint_key, "success": False, "error": str(e)}


def main():
    """Main test execution."""
    print(f"\n{colorize('=' * 80, 'blue')}")
    print(colorize("NUZANTARA Portal Endpoints - Manual Test Suite", "blue"))
    print(f"{colorize('=' * 80, 'blue')}\n")

    # Check arguments
    if len(sys.argv) < 2:
        print(f"{colorize('❌ Error: JWT token required', 'red')}")
        print(f"\nUsage: python {sys.argv[0]} <JWT_TOKEN>")
        print("\nHow to get JWT token:")
        print("1. Login to Portal: https://portal.balizero.com")
        print("2. Open DevTools → Application → Storage → Cookies")
        print("3. Copy value of 'auth_token' or 'jwt_token' cookie")
        print("\nExample:")
        print(f"  python {sys.argv[0]} eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        sys.exit(1)

    token = sys.argv[1]

    # Validate token format
    if not token.startswith("eyJ"):
        warning_msg = "⚠️  Warning: Token doesn't look like a JWT"
        print(f"{colorize(warning_msg, 'yellow')}")
        print("JWT tokens typically start with 'eyJ'")
        proceed = input("\nContinue anyway? (y/n): ")
        if proceed.lower() != "y":
            sys.exit(1)

    print(f"Base URL: {colorize(BASE_URL, 'blue')}")
    print(f"Token: {colorize(token[:20] + '...', 'blue')}")
    print(f"Time: {colorize(datetime.now().isoformat(), 'blue')}\n")

    # Run tests
    results = []
    for endpoint_key, endpoint_path in ENDPOINTS.items():
        result = test_endpoint(endpoint_key, endpoint_path, token)
        results.append(result)

    # Summary
    print(f"\n{colorize('=' * 80, 'blue')}")
    print(colorize("TEST SUMMARY", "blue"))
    print(f"{colorize('=' * 80, 'blue')}\n")

    success_count = sum(1 for r in results if r.get("success", False))
    total_count = len(results)

    for result in results:
        status = (
            colorize("✅ PASS", "green")
            if result.get("success", False)
            else colorize("❌ FAIL", "red")
        )
        endpoint = result["endpoint"]
        print(f"{status} - {endpoint}")

    print(f"\n{colorize(f'Total: {success_count}/{total_count} passed', 'blue')}")

    if success_count == total_count:
        print(f"\n{colorize('🎉 All tests passed!', 'green')}")
        sys.exit(0)
    else:
        print(f"\n{colorize('❌ Some tests failed', 'red')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
