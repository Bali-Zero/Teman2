#!/usr/bin/env python3
"""
NUZANTARA PRIME - Online End-to-End Testing
Test completo del sistema con credenziali reali
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"

# Configuration
BACKEND_URL = "https://nuzantara-rag.fly.dev"
TIMEOUT = 60.0

# Credentials
EMAIL = "zero@balizero.com"
PIN = "010719"

# Test results
test_results = {
    "auth": {},
    "health": {},
    "services": {},
    "zantara_chat": [],
    "summary": {}
}


async def test_authentication() -> Dict[str, Any]:
    """Test authentication flow"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}🔐 TESTING AUTHENTICATION{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Step 1: Login with PIN
        print(f"{CYAN}Step 1: Login with PIN...{NC}")
        try:
            login_response = await client.post(
                f"{BACKEND_URL}/api/auth/login",
                json={"email": EMAIL, "pin": PIN}
            )
            
            if login_response.status_code == 200:
                login_data = login_response.json()
                # Try different possible token locations
                token = (
                    login_data.get("access_token") or
                    login_data.get("token") or
                    (login_data.get("data", {}).get("token") if isinstance(login_data.get("data"), dict) else None) or
                    (login_data.get("data", {}).get("access_token") if isinstance(login_data.get("data"), dict) else None)
                )
                
                if token:
                    print(f"  {GREEN}✅ Login successful{NC}")
                    print(f"  Token: {token[:30]}...")
                    print(f"  User: {login_data.get('data', {}).get('user', {}).get('name', 'N/A')} ({login_data.get('data', {}).get('user', {}).get('role', 'N/A')})")
                    test_results["auth"]["login"] = {"status": "success", "token": token[:30] + "..."}
                    return {"token": token, "status": "success", "user": login_data.get("data", {}).get("user", {})}
                else:
                    print(f"  {RED}❌ No token in response{NC}")
                    print(f"  Response keys: {list(login_data.keys())}")
                    test_results["auth"]["login"] = {"status": "failed", "reason": "no_token", "response": login_data}
                    return {"status": "failed", "error": "No token in response"}
            else:
                print(f"  {RED}❌ Login failed: {login_response.status_code}{NC}")
                print(f"  Response: {login_response.text[:200]}")
                test_results["auth"]["login"] = {"status": "failed", "status_code": login_response.status_code}
                return {"status": "failed", "error": login_response.text}
        except Exception as e:
            print(f"  {RED}❌ Login error: {e}{NC}")
            test_results["auth"]["login"] = {"status": "error", "error": str(e)}
            return {"status": "error", "error": str(e)}


async def test_health_endpoints(token: str) -> Dict[str, Any]:
    """Test health endpoints"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}🏥 TESTING HEALTH ENDPOINTS{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    results = {}
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Basic health
        print(f"{CYAN}Testing /health...{NC}")
        try:
            response = await client.get(f"{BACKEND_URL}/health", headers=headers)
            if response.status_code == 200:
                health_data = response.json()
                print(f"  {GREEN}✅ Basic Health: {health_data.get('status')}{NC}")
                results["basic"] = health_data
            else:
                print(f"  {RED}❌ Failed: {response.status_code}{NC}")
                results["basic"] = {"error": response.status_code}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["basic"] = {"error": str(e)}
        
        # Detailed health
        print(f"{CYAN}Testing /health/detailed...{NC}")
        try:
            response = await client.get(f"{BACKEND_URL}/health/detailed", headers=headers)
            if response.status_code == 200:
                detailed_data = response.json()
                services = detailed_data.get("services", {})
                print(f"  {GREEN}✅ Detailed Health retrieved{NC}")
                print(f"  Services status:")
                for service, status in services.items():
                    status_icon = "✅" if status.get("status") == "healthy" else "🟡"
                    print(f"    {status_icon} {service}: {status.get('status')}")
                results["detailed"] = detailed_data
            else:
                print(f"  {RED}❌ Failed: {response.status_code}{NC}")
                results["detailed"] = {"error": response.status_code}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["detailed"] = {"error": str(e)}
    
    test_results["health"] = results
    return results


async def test_backend_services(token: str) -> Dict[str, Any]:
    """Test backend services"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}🔌 TESTING BACKEND SERVICES{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    results = {}
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Conversations Service
        print(f"{CYAN}Testing Conversations Service...{NC}")
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/bali-zero/conversations/stats",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  {GREEN}✅ Conversations: Accessible{NC}")
                print(f"    Total messages: {data.get('total_messages', 'N/A')}")
                results["conversations"] = {"status": "accessible", "data": data}
            else:
                print(f"  {YELLOW}🟡 Status: {response.status_code}{NC}")
                results["conversations"] = {"status": f"status_{response.status_code}"}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["conversations"] = {"error": str(e)}
        
        # Memory Service
        print(f"{CYAN}Testing Memory Service...{NC}")
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/memory/stats",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  {GREEN}✅ Memory: Accessible{NC}")
                print(f"    Total memories: {data.get('total_memories', 'N/A')}")
                results["memory"] = {"status": "accessible", "data": data}
            else:
                print(f"  {YELLOW}🟡 Status: {response.status_code}{NC}")
                results["memory"] = {"status": f"status_{response.status_code}"}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["memory"] = {"error": str(e)}
        
        # CRM Service
        print(f"{CYAN}Testing CRM Service...{NC}")
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/crm-clients/by-email/{EMAIL}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  {GREEN}✅ CRM: Client found{NC}")
                print(f"    Client ID: {data.get('id', 'N/A')}")
                print(f"    Name: {data.get('full_name', 'N/A')}")
                results["crm"] = {"status": "accessible", "data": data}
            elif response.status_code == 404:
                print(f"  {YELLOW}🟡 CRM: Client not found (endpoint works){NC}")
                results["crm"] = {"status": "endpoint_works", "client_not_found": True}
            else:
                print(f"  {YELLOW}🟡 Status: {response.status_code}{NC}")
                results["crm"] = {"status": f"status_{response.status_code}"}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["crm"] = {"error": str(e)}
        
        # Agents Service
        print(f"{CYAN}Testing Agents Service...{NC}")
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/agents/status",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  {GREEN}✅ Agents: Accessible{NC}")
                print(f"    Available agents: {len(data.get('agents_available', []))}")
                results["agents"] = {"status": "accessible", "data": data}
            else:
                print(f"  {YELLOW}🟡 Status: {response.status_code}{NC}")
                results["agents"] = {"status": f"status_{response.status_code}"}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["agents"] = {"error": str(e)}
        
        # Knowledge Service
        print(f"{CYAN}Testing Knowledge Service...{NC}")
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/knowledge/collections",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                collections = data.get("collections", [])
                print(f"  {GREEN}✅ Knowledge: Accessible{NC}")
                print(f"    Collections: {len(collections)}")
                results["knowledge"] = {"status": "accessible", "collections": len(collections)}
            else:
                print(f"  {YELLOW}🟡 Status: {response.status_code}{NC}")
                results["knowledge"] = {"status": f"status_{response.status_code}"}
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{NC}")
            results["knowledge"] = {"error": str(e)}
    
    test_results["services"] = results
    return results


async def test_zantara_chat(token: str) -> List[Dict[str, Any]]:
    """Test Zantara chat communication"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}💬 TESTING ZANTARA CHAT{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    chat_tests = []
    
    # Test questions to verify natural communication
    test_questions = [
        {
            "question": "Cosa puoi fare per me?",
            "expected_keywords": ["crm", "memoria", "conversazioni", "compliance", "prezzo"],
            "description": "Test conoscenza servizi backend"
        },
        {
            "question": "Puoi controllare le mie pratiche attive nel CRM?",
            "expected_keywords": ["crm", "pratiche", "cliente"],
            "description": "Test comunicazione CRM"
        },
        {
            "question": "Cosa ricordi di me?",
            "expected_keywords": ["memoria", "ricordo"],
            "description": "Test comunicazione Memory Service"
        },
        {
            "question": "Puoi cercare informazioni su Tax, Legal e Visa insieme?",
            "expected_keywords": ["tax", "legal", "visa", "sintesi"],
            "description": "Test comunicazione Oracle Services"
        }
    ]
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for i, test in enumerate(test_questions, 1):
            print(f"\n{CYAN}Test {i}/{len(test_questions)}: {test['description']}{NC}")
            print(f"  Question: \"{test['question']}\"")
            
            try:
                # Use chat-stream endpoint
                params = {
                    "query": test["question"],
                    "stream": "true"
                }
                
                # Use GET with query params (as per webapp implementation)
                # Note: The endpoint uses X-API-Key header for auth, not Bearer token
                # But we'll try both methods
                api_key_headers = headers.copy()
                # Try with API key if available (check env var)
                import os
                api_key = os.getenv("NUZANTARA_API_KEY")
                if api_key:
                    api_key_headers["X-API-Key"] = api_key
                
                response = await client.get(
                    f"{BACKEND_URL}/bali-zero/chat-stream",
                    params=params,
                    headers=api_key_headers,
                    follow_redirects=True
                )
                
                if response.status_code == 200:
                    # Parse SSE stream
                    content = response.text
                    full_response_text = ""
                    
                    # Parse SSE format: data: {"type": "...", "content": "..."} or data: {"content": "..."}
                    if "data:" in content:
                        lines = content.split("\n")
                        message_parts = []
                        for line in lines:
                            if line.startswith("data:"):
                                try:
                                    json_str = line[5:].strip()  # Remove "data: " prefix
                                    if json_str:
                                        data_json = json.loads(json_str)
                                        # Extract content from different possible structures
                                        if "content" in data_json:
                                            message_parts.append(data_json["content"])
                                        elif "text" in data_json:
                                            message_parts.append(data_json["text"])
                                        elif "message" in data_json:
                                            message_parts.append(data_json["message"])
                                        elif "answer" in data_json:
                                            message_parts.append(data_json["answer"])
                                        elif data_json.get("type") == "content" and "data" in data_json:
                                            if isinstance(data_json["data"], str):
                                                message_parts.append(data_json["data"])
                                        # Also collect metadata for context
                                        if data_json.get("type") == "metadata":
                                            # Store metadata but don't add to content
                                            pass
                                except json.JSONDecodeError:
                                    # Skip invalid JSON lines
                                    pass
                                except Exception as e:
                                    pass
                        full_response_text = " ".join(message_parts)
                        content = full_response_text if full_response_text else content
                    else:
                        # Try JSON response
                        try:
                            json_response = response.json()
                            if "content" in json_response:
                                content = json_response["content"]
                            elif "message" in json_response:
                                content = json_response["message"]
                            elif "response" in json_response:
                                content = json_response["response"]
                        except:
                            pass
                    
                    print(f"  {GREEN}✅ Response received{NC}")
                    print(f"  Response length: {len(content)} chars")
                    
                    # Save full response for debugging
                    debug_file = Path(f"docs/chat_response_{i}.txt")
                    debug_file.write_text(content)
                    print(f"  Full response saved to: {debug_file}")
                    
                    print(f"  Response preview: {content[:300]}...")
                    
                    # Check for expected keywords (case insensitive)
                    content_lower = content.lower()
                    found_keywords = [
                        kw for kw in test["expected_keywords"]
                        if kw.lower() in content_lower
                    ]
                    
                    if found_keywords:
                        print(f"  {GREEN}✅ Found keywords: {', '.join(found_keywords)}{NC}")
                        chat_tests.append({
                            "question": test["question"],
                            "status": "success",
                            "keywords_found": found_keywords,
                            "response_length": len(content),
                            "response_preview": content[:200]
                        })
                    else:
                        print(f"  {YELLOW}🟡 No expected keywords found{NC}")
                        print(f"  Expected: {', '.join(test['expected_keywords'])}")
                        # Show what we actually got
                        print(f"  Actual response: {content[:300]}")
                        chat_tests.append({
                            "question": test["question"],
                            "status": "partial",
                            "keywords_found": [],
                            "response_length": len(content),
                            "response_preview": content[:200]
                        })
                else:
                    print(f"  {RED}❌ Failed: {response.status_code}{NC}")
                    chat_tests.append({
                        "question": test["question"],
                        "status": "failed",
                        "status_code": response.status_code
                    })
            except Exception as e:
                print(f"  {RED}❌ Error: {e}{NC}")
                chat_tests.append({
                    "question": test["question"],
                    "status": "error",
                    "error": str(e)
                })
    
    test_results["zantara_chat"] = chat_tests
    return chat_tests


async def main():
    """Main test function"""
    print(f"{BLUE}{'='*60}{NC}")
    print(f"{BLUE}🚀 NUZANTARA PRIME - Online End-to-End Testing{NC}")
    print(f"{BLUE}{'='*60}{NC}")
    print(f"\n{CYAN}Testing with credentials:{NC}")
    print(f"  Email: {EMAIL}")
    print(f"  PIN: {'*' * len(PIN)}\n")
    
    # Step 1: Authentication
    auth_result = await test_authentication()
    if auth_result.get("status") != "success":
        print(f"\n{RED}❌ Authentication failed. Cannot continue.{NC}")
        test_results["summary"] = {"status": "failed", "reason": "authentication_failed"}
        return 1
    
    token = auth_result["token"]
    
    # Step 2: Health endpoints
    await test_health_endpoints(token)
    
    # Step 3: Backend services
    await test_backend_services(token)
    
    # Step 4: Zantara chat
    await test_zantara_chat(token)
    
    # Summary
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}📊 TEST SUMMARY{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    # Count successes
    auth_success = test_results["auth"].get("login", {}).get("status") == "success"
    health_success = "basic" in test_results["health"] and "error" not in test_results["health"].get("basic", {})
    services_success = len([k for k, v in test_results["services"].items() if v.get("status") == "accessible"]) >= 3
    chat_success = len([t for t in test_results["zantara_chat"] if t.get("status") == "success"]) >= 2
    
    print(f"{GREEN if auth_success else RED}{'✅' if auth_success else '❌'} Authentication: {'Success' if auth_success else 'Failed'}{NC}")
    print(f"{GREEN if health_success else RED}{'✅' if health_success else '❌'} Health Endpoints: {'Success' if health_success else 'Failed'}{NC}")
    print(f"{GREEN if services_success else YELLOW}{'✅' if services_success else '🟡'} Backend Services: {len([k for k, v in test_results['services'].items() if v.get('status') == 'accessible'])}/{len(test_results['services'])} accessible{NC}")
    print(f"{GREEN if chat_success else YELLOW}{'✅' if chat_success else '🟡'} Zantara Chat: {len([t for t in test_results['zantara_chat'] if t.get('status') == 'success'])}/{len(test_results['zantara_chat'])} successful{NC}")
    
    # Save results
    results_file = Path("docs/online_test_results.json")
    results_file.write_text(json.dumps(test_results, indent=2))
    print(f"\n{GREEN}✅ Results saved to: {results_file}{NC}")
    
    # Final verdict
    if auth_success and health_success and services_success and chat_success:
        print(f"\n{GREEN}✅ VERDICT: ALL TESTS PASSED{NC}")
        test_results["summary"] = {"status": "success", "all_tests_passed": True}
        return 0
    else:
        print(f"\n{YELLOW}🟡 VERDICT: SOME TESTS FAILED{NC}")
        test_results["summary"] = {"status": "partial", "all_tests_passed": False}
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

