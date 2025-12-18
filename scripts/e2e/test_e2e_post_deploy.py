#!/usr/bin/env python3
"""
E2E Post-Deploy Tests - Communication Features
Tests the 3 scenarios from PROMPT 5 against production
"""

import os
import re
import sys
import time
from typing import Optional

import requests

RAG_BACKEND_URL = os.getenv("RAG_BACKEND_URL", "https://nuzantara-rag.fly.dev")
TS_BACKEND_URL = os.getenv("TS_BACKEND_URL", "https://nuzantara-backend.fly.dev")
TEST_EMAIL = os.getenv("TEST_EMAIL", "zero@balizero.com")
TEST_PIN = os.getenv("TEST_PIN", "010719")

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"


def test_pass(msg: str):
    print(f"{GREEN}✅ PASS{NC}: {msg}")


def test_fail(msg: str):
    print(f"{RED}❌ FAIL{NC}: {msg}")
    sys.exit(1)


def test_info(msg: str):
    print(f"{YELLOW}ℹ️  INFO{NC}: {msg}")


def get_token() -> Optional[str]:
    """Get authentication token"""
    try:
        response = requests.post(
            f"{TS_BACKEND_URL}/api/auth/team/login",
            json={"email": TEST_EMAIL, "pin": TEST_PIN},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if token:
            return token
        test_fail(f"Login response missing token: {data}")
    except Exception as e:
        test_fail(f"Login failed: {e}")
    return None


def test_chat_stream(query: str, token: str, session_id: str, timeout: int = 30) -> str:
    """Test chat stream endpoint"""
    try:
        url = f"{RAG_BACKEND_URL}/bali-zero/chat-stream"
        params = {
            "query": query,
            "user_email": TEST_EMAIL,
            "session_id": session_id,
        }
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, params=params, headers=headers, stream=True, timeout=timeout)
        response.raise_for_status()

        # Collect response chunks
        chunks = []
        for line in response.iter_lines(decode_unicode=True):
            if line:
                chunks.append(line)
            if len(chunks) > 100:  # Limit to first 100 lines
                break

        return " ".join(chunks)
    except Exception as e:
        test_fail(f"Chat stream failed: {e}")
    return ""


def main():
    print("🧪 E2E Post-Deploy Tests - Communication Features")
    print("=" * 50)
    print()

    # Test 1: Health Check
    print("📋 Test 1: Health Check")
    print("-" * 20)
    try:
        response = requests.get(f"{RAG_BACKEND_URL}/health", timeout=10)
        response.raise_for_status()
        test_pass("Health check")
    except Exception as e:
        test_fail(f"Health check failed: {e}")
    print()

    # Test 2: Login
    print("📋 Test 2: Login")
    print("-" * 15)
    token = get_token()
    if token:
        test_pass("Login successful")
        test_info(f"Token: {token[:20]}...")
    print()

    # Test 3: Scenario 1 - Same Language Response (Italian)
    print("📋 Test 3: Scenario 1 - Same Language Response")
    print("-" * 45)
    query_1 = "Ciao, come stai?"
    test_info(f"Query: {query_1}")

    response_1 = test_chat_stream(query_1, token, "e2e_test_1")
    response_lower = response_1.lower()

    italian_keywords = ["ciao", "bene", "come", "posso", "aiutarti", "grazie"]
    found_keywords = [kw for kw in italian_keywords if kw in response_lower]

    if len(found_keywords) >= 2:
        test_pass(f"Italian response contains Italian keywords: {found_keywords}")
        test_info(f"Response preview: {response_1[:200]}...")
    else:
        test_fail(f"Italian response missing Italian keywords. Found: {found_keywords}")
        test_info(f"Response: {response_1[:500]}")
    print()

    # Test 4: Scenario 2 - Empathetic Tone
    print("📋 Test 4: Scenario 2 - Empathetic Tone")
    print("-" * 40)
    query_2 = "Ho sbagliato tutto con il mio visto, sono disperato!"
    test_info(f"Query: {query_2}")

    response_2 = test_chat_stream(query_2, token, "e2e_test_2")
    response_lower = response_2.lower()

    empathetic_keywords = ["capisco", "tranquillo", "aiuto", "soluzione", "possibilità"]
    found_keywords = [kw for kw in empathetic_keywords if kw in response_lower]

    if len(found_keywords) >= 2:
        test_pass(f"Emotional response contains empathetic keywords: {found_keywords}")
        test_info(f"Response preview: {response_2[:200]}...")
    else:
        test_fail(f"Emotional response missing empathetic keywords. Found: {found_keywords}")
        test_info(f"Response: {response_2[:500]}")
    print()

    # Test 5: Scenario 3 - Step-by-Step Instructions
    print("📋 Test 5: Scenario 3 - Step-by-Step Instructions")
    print("-" * 50)
    query_3 = "Come faccio a richiedere il KITAS E33G?"
    test_info(f"Query: {query_3}")

    response_3 = test_chat_stream(query_3, token, "e2e_test_3")
    numbered_pattern = r"\b[1-9][\.\)]\s+"
    matches = re.findall(numbered_pattern, response_3)

    if len(matches) >= 2:
        test_pass(f"Procedural response contains numbered list ({len(matches)} items)")
        test_info(f"Response preview: {response_3[:300]}...")
    else:
        test_fail(f"Procedural response missing numbered list. Found {len(matches)} items")
        test_info(f"Response: {response_3[:500]}")
    print()

    # Summary
    print("=" * 50)
    print("✅ All E2E Post-Deploy Tests Passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()

