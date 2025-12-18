#!/usr/bin/env python3
"""
Test Chat Endpoint dopo deploy - Verifica fix Gemini 2.5 Flash
"""

import asyncio
import json
import sys
from pathlib import Path

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
EMAIL = "zero@balizero.com"
PIN = "010719"
TIMEOUT = 60.0

test_results = {
    "auth": {},
    "chat_tests": [],
    "errors_found": [],
    "summary": {}
}


async def login():
    """Login e ottieni token"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/auth/login",
                json={"email": EMAIL, "pin": PIN}
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("data", {}).get("token")
                if token:
                    return token
            return None
        except Exception as e:
            print(f"  {RED}❌ Login error: {e}{NC}")
            return None


async def test_chat_endpoint(token: str, question: str) -> dict:
    """Test chat endpoint e verifica risposta"""
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "query": question,
        "stream": "true"
    }
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(
                f"{BACKEND_URL}/bali-zero/chat-stream",
                params=params,
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code == 200:
                content = response.text
                
                # Check for old model error
                if "gemini-1.5-flash" in content.lower():
                    return {
                        "status": "error",
                        "error": "Old model (1.5-flash) still referenced",
                        "response_preview": content[:200]
                    }
                
                # Check for 404 error
                if "404" in content and "not found" in content.lower():
                    return {
                        "status": "error",
                        "error": "404 model not found error",
                        "response_preview": content[:300]
                    }
                
                # Check for successful response
                if "data:" in content and ("content" in content.lower() or "type" in content.lower()):
                    # Parse SSE to check for actual content
                    lines = content.split("\n")
                    has_content = False
                    for line in lines:
                        if line.startswith("data:"):
                            try:
                                data = json.loads(line[5:].strip())
                                if data.get("type") == "content" or "content" in data:
                                    has_content = True
                                    break
                            except:
                                pass
                    
                    if has_content:
                        return {
                            "status": "success",
                            "response_length": len(content),
                            "has_content": True
                        }
                    else:
                        return {
                            "status": "partial",
                            "response_length": len(content),
                            "note": "Response received but no content chunks found"
                        }
                
                return {
                    "status": "unknown",
                    "response_length": len(content),
                    "response_preview": content[:200]
                }
            else:
                return {
                    "status": "failed",
                    "status_code": response.status_code,
                    "response": response.text[:200]
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


async def main():
    """Main test function"""
    print(f"{BLUE}{'='*60}{NC}")
    print(f"{BLUE}🧪 TEST CHAT ENDPOINT - Post Deploy{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    # Step 1: Login
    print(f"{CYAN}Step 1: Authentication...{NC}")
    token = await login()
    if not token:
        print(f"  {RED}❌ Login failed - cannot continue{NC}")
        return 1
    
    print(f"  {GREEN}✅ Login successful{NC}")
    test_results["auth"] = {"status": "success"}
    
    # Step 2: Test chat endpoint
    print(f"\n{CYAN}Step 2: Testing Chat Endpoint...{NC}")
    test_questions = [
        "Ciao, come stai?",
        "Cosa puoi fare per me?",
        "Test semplice"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n  Test {i}/{len(test_questions)}: \"{question}\"")
        result = await test_chat_endpoint(token, question)
        test_results["chat_tests"].append({
            "question": question,
            **result
        })
        
        if result["status"] == "success":
            print(f"    {GREEN}✅ Success{NC}")
            print(f"    Response length: {result.get('response_length', 'N/A')} chars")
        elif result["status"] == "error":
            print(f"    {RED}❌ Error: {result.get('error', 'Unknown')}{NC}")
            test_results["errors_found"].append(result)
            if "response_preview" in result:
                print(f"    Preview: {result['response_preview'][:100]}...")
        elif result["status"] == "partial":
            print(f"    {YELLOW}🟡 Partial: {result.get('note', 'Unknown')}{NC}")
        else:
            print(f"    {YELLOW}🟡 Status: {result['status']}{NC}")
    
    # Summary
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}📊 TEST SUMMARY{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    success_count = sum(1 for t in test_results["chat_tests"] if t["status"] == "success")
    error_count = sum(1 for t in test_results["chat_tests"] if t["status"] == "error")
    
    print(f"{GREEN if success_count > 0 else RED}{'✅' if success_count > 0 else '❌'} Successful tests: {success_count}/{len(test_results['chat_tests'])}{NC}")
    print(f"{RED if error_count > 0 else GREEN}{'❌' if error_count > 0 else '✅'} Errors found: {error_count}{NC}")
    
    # Check for specific errors
    old_model_errors = [e for e in test_results["errors_found"] if "1.5-flash" in str(e).lower()]
    not_found_errors = [e for e in test_results["errors_found"] if "404" in str(e).lower() or "not found" in str(e).lower()]
    
    if old_model_errors:
        print(f"\n  {RED}❌ OLD MODEL ERRORS FOUND: {len(old_model_errors)}{NC}")
        print(f"     Il modello vecchio (1.5-flash) è ancora referenziato!")
    else:
        print(f"\n  {GREEN}✅ No old model references found{NC}")
    
    if not_found_errors:
        print(f"\n  {RED}❌ 404 ERRORS FOUND: {len(not_found_errors)}{NC}")
        print(f"     Errore 'model not found' ancora presente!")
    else:
        print(f"\n  {GREEN}✅ No 404 errors found{NC}")
    
    # Save results
    results_file = Path("docs/chat_test_post_deploy.json")
    results_file.write_text(json.dumps(test_results, indent=2))
    print(f"\n{GREEN}✅ Results saved to: {results_file}{NC}")
    
    # Final verdict
    if success_count > 0 and error_count == 0:
        print(f"\n{GREEN}✅ VERDICT: CHAT ENDPOINT FUNZIONA CORRETTAMENTE{NC}")
        test_results["summary"] = {"status": "success", "fix_verified": True}
        return 0
    elif error_count > 0:
        print(f"\n{RED}❌ VERDICT: ERRORI TROVATI - FIX NON COMPLETO{NC}")
        test_results["summary"] = {"status": "failed", "fix_verified": False}
        return 1
    else:
        print(f"\n{YELLOW}🟡 VERDICT: RISULTATI PARZIALI - VERIFICARE MANUALMENTE{NC}")
        test_results["summary"] = {"status": "partial", "fix_verified": False}
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

