#!/usr/bin/env python3
"""Test login credentials against the backend"""

import sys
import requests
import json

BACKEND_URL = "https://nuzantara-rag.fly.dev"
EMAIL = "zero@balizero.com"
PIN = "010719"

def test_login():
    """Test login with credentials"""

    print(f"🔐 Testing login credentials...")
    print(f"   Email: {EMAIL}")
    print(f"   PIN: {PIN}")
    print(f"   Backend: {BACKEND_URL}")
    print()

    # Test health endpoint
    print("1. Testing health endpoint...")
    try:
        health_endpoints = [
            f"{BACKEND_URL}/health",
            f"{BACKEND_URL}/healthz",
            f"{BACKEND_URL}/api/health",
        ]

        for endpoint in health_endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code < 500:
                    print(f"   ✅ {endpoint}: {response.status_code}")
                    print(f"      {response.text[:100]}")
                    break
            except Exception as e:
                continue
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")

    print()

    # Test login
    print("2. Testing login endpoint...")
    login_url = f"{BACKEND_URL}/api/auth/login"

    # Try with PIN
    print(f"   Trying with 'pin' field...")
    try:
        response = requests.post(
            login_url,
            json={"email": EMAIL, "pin": PIN},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")

        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("token"):
                print(f"   ✅ LOGIN SUCCESS!")
                print(f"   Token: {data['data']['token'][:50]}...")
                return True

    except Exception as e:
        print(f"   ❌ Error: {e}")

    print()

    # Try with password
    print(f"   Trying with 'password' field...")
    try:
        response = requests.post(
            login_url,
            json={"email": EMAIL, "password": PIN},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")

        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("token"):
                print(f"   ✅ LOGIN SUCCESS!")
                print(f"   Token: {data['data']['token'][:50]}...")
                return True

    except Exception as e:
        print(f"   ❌ Error: {e}")

    print()
    print("❌ LOGIN FAILED - Credentials may be incorrect")
    print()
    print("Possible issues:")
    print("  1. Email or PIN incorrect")
    print("  2. User not active in database")
    print("  3. Backend authentication system changed")
    print()
    print("Try:")
    print("  - Verify user exists: SELECT * FROM team_members WHERE email = '{EMAIL}'")
    print("  - Create test user: python scripts/create_test_user.py")

    return False

if __name__ == "__main__":
    success = test_login()
    sys.exit(0 if success else 1)
