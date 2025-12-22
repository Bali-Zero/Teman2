#!/usr/bin/env python3
"""
Test script per verificare i fix di Zantara:
1. Greetings detection ("ciao" → risposta diretta)
2. Session isolation (sessioni diverse isolate)
3. Memory hallucination prevention (prima query senza memory facts)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import httpx

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Configuration
API_URL = os.getenv("API_URL", "https://nuzantara-rag.fly.dev")
TEST_EMAIL = os.getenv("TEST_EMAIL", "zero@balizero.com")
TEST_PIN = os.getenv("TEST_PIN", "010719")

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_test(name: str, status: str, details: str = ""):
    """Print test result"""
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    color = GREEN if status == "PASS" else RED if status == "FAIL" else YELLOW
    print(f"{icon} {color}{name}{RESET}")
    if details:
        print(f"   {details}")


async def get_auth_token(client: httpx.AsyncClient) -> str | None:
    """Get JWT token by logging in"""
    try:
        response = await client.post(
            f"{API_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "pin": TEST_PIN},
        )
        if response.status_code == 200:
            data = response.json()
            # Token is nested in data.data.token
            if isinstance(data.get("data"), dict):
                token = data["data"].get("token")
                if token:
                    return token
            # Fallback: try root level
            token = data.get("access_token") or data.get("token")
            if token:
                return token
            print(f"   ⚠️ Login successful but no token found. Response keys: {list(data.keys())}")
        else:
            print(f"   ⚠️ Login failed: HTTP {response.status_code}, {response.text[:200]}")
    except Exception as e:
        print(f"   ⚠️ Login error: {e}")
    return None


async def test_greeting_detection(token: str):
    """Test 1: Greeting detection - "ciao" should return direct response"""
    print_header("TEST 1: Greetings Detection")
    
    session_id = str(uuid4())
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.post(
                f"{API_URL}/api/agentic-rag/query",
                json={
                    "query": "ciao",
                    "user_id": TEST_EMAIL,
                    "session_id": session_id,
                },
                headers=headers,
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "").lower()
                route_used = data.get("route_used", "")
                tools_called = data.get("tools_called", 0)
                
                # Check if greeting was detected
                is_greeting_route = "greeting" in route_used.lower()
                has_greeting_response = any(
                    word in answer
                    for word in ["ciao", "hello", "come posso aiutarti", "how can i help"]
                )
                no_tools_called = tools_called == 0
                
                if is_greeting_route and has_greeting_response and no_tools_called:
                    print_test(
                        "Greeting Detection",
                        "PASS",
                        f"Route: {route_used}, Tools: {tools_called}, Answer: {answer[:50]}...",
                    )
                    return True
                else:
                    print_test(
                        "Greeting Detection",
                        "FAIL",
                        f"Route: {route_used}, Tools: {tools_called}, Answer: {answer[:100]}",
                    )
                    return False
            else:
                print_test(
                    "Greeting Detection",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )
                return False
                
        except Exception as e:
            print_test("Greeting Detection", "FAIL", f"Error: {str(e)}")
            return False


async def test_session_isolation(token: str):
    """Test 2: Session isolation - different sessions should have different contexts"""
    print_header("TEST 2: Session Isolation")
    
    session_1 = str(uuid4())
    session_2 = str(uuid4())
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            # First message in session 1
            response_1a = await client.post(
                f"{API_URL}/api/agentic-rag/query",
                json={
                    "query": "Il mio nome è Marco",
                    "user_id": TEST_EMAIL,
                    "session_id": session_1,
                },
                headers=headers,
            )
            
            # First message in session 2
            response_2a = await client.post(
                f"{API_URL}/api/agentic-rag/query",
                json={
                    "query": "Il mio nome è Luca",
                    "user_id": TEST_EMAIL,
                    "session_id": session_2,
                },
                headers=headers,
            )
            
            # Second message in session 1 (should remember "Marco")
            response_1b = await client.post(
                f"{API_URL}/api/agentic-rag/query",
                json={
                    "query": "Come mi chiamo?",
                    "user_id": TEST_EMAIL,
                    "session_id": session_1,
                },
                headers=headers,
            )
            
            # Second message in session 2 (should remember "Luca")
            response_2b = await client.post(
                f"{API_URL}/api/agentic-rag/query",
                json={
                    "query": "Come mi chiamo?",
                    "user_id": TEST_EMAIL,
                    "session_id": session_2,
                },
                headers=headers,
            )
            
            if all(
                r.status_code == 200
                for r in [response_1a, response_2a, response_1b, response_2b]
            ):
                answer_1b = response_1b.json().get("answer", "").lower()
                answer_2b = response_2b.json().get("answer", "").lower()
                
                # Check if sessions are isolated
                session_1_remembers_marco = "marco" in answer_1b
                session_2_remembers_luca = "luca" in answer_2b
                session_1_not_luca = "luca" not in answer_1b
                session_2_not_marco = "marco" not in answer_2b
                
                if (
                    session_1_remembers_marco
                    and session_2_remembers_luca
                    and session_1_not_luca
                    and session_2_not_marco
                ):
                    print_test(
                        "Session Isolation",
                        "PASS",
                        f"Session 1: {answer_1b[:60]}... | Session 2: {answer_2b[:60]}...",
                    )
                    return True
                else:
                    print_test(
                        "Session Isolation",
                        "FAIL",
                        f"Session 1: {answer_1b[:100]} | Session 2: {answer_2b[:100]}",
                    )
                    return False
            else:
                print_test(
                    "Session Isolation",
                    "FAIL",
                    f"HTTP errors: {[r.status_code for r in [response_1a, response_2a, response_1b, response_2b]]}",
                )
                return False
                
        except Exception as e:
            print_test("Session Isolation", "FAIL", f"Error: {str(e)}")
            return False


async def test_memory_prevention(token: str):
    """Test 3: Memory prevention - first query should not have memory facts"""
    print_header("TEST 3: Memory Hallucination Prevention")
    
    # Create a completely new session
    new_session = str(uuid4())
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            # First query in new session
            response = await client.post(
                f"{API_URL}/api/agentic-rag/query",
                json={
                    "query": "Ciao, sono nuovo qui",
                    "user_id": TEST_EMAIL,
                    "session_id": new_session,
                },
                headers=headers,
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "").lower()
                debug_info = data.get("debug_info", {})
                
                # Check if answer doesn't mention facts from previous sessions
                # Common memory hallucination patterns
                memory_patterns = [
                    "so che",
                    "ricordo che",
                    "hai detto",
                    "mi hai detto",
                    "preferisci",
                    "ti piace",
                    "il tuo",
                ]
                
                has_memory_hallucination = any(pattern in answer for pattern in memory_patterns)
                
                if not has_memory_hallucination:
                    print_test(
                        "Memory Prevention",
                        "PASS",
                        f"First query doesn't mention previous facts. Answer: {answer[:80]}...",
                    )
                    return True
                else:
                    print_test(
                        "Memory Prevention",
                        "FAIL",
                        f"Answer mentions previous facts: {answer[:150]}",
                    )
                    return False
            else:
                print_test(
                    "Memory Prevention",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )
                return False
                
        except Exception as e:
            print_test("Memory Prevention", "FAIL", f"Error: {str(e)}")
            return False


async def main():
    """Run all tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{'ZANTARA FIXES - MANUAL TEST SUITE':^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"\nAPI URL: {API_URL}")
    print(f"Test Email: {TEST_EMAIL}\n")
    
    # Get auth token once for all tests
    print(f"{YELLOW}🔐 Logging in...{RESET}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await get_auth_token(client)
        if not token:
            print(f"{RED}❌ Failed to get auth token. Cannot run tests.{RESET}")
            return False
    
    print(f"{GREEN}✅ Authentication successful{RESET}\n")
    
    results = []
    
    # Test 1: Greeting detection
    result_1 = await test_greeting_detection(token)
    results.append(("Greeting Detection", result_1))
    
    # Test 2: Session isolation
    result_2 = await test_session_isolation(token)
    results.append(("Session Isolation", result_2))
    
    # Test 3: Memory prevention
    result_3 = await test_memory_prevention(token)
    results.append(("Memory Prevention", result_3))
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print_test(name, status)
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Results: {passed}/{total} tests passed{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

