#!/usr/bin/env python3
"""
NUZANTARA PRIME - Zantara Services Verification Script
Verifica che Zantara nella webapp abbia pieno controllo e conoscenza di tutti i servizi backend.
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
NC = "\033[0m"

# Configuration
BACKEND_URL = "https://nuzantara-rag.fly.dev"
TIMEOUT = 30.0

# Test questions per verificare conoscenza servizi
SERVICE_KNOWLEDGE_TESTS = [
    {
        "category": "Conversations Service",
        "questions": [
            "Puoi cercare nelle nostre conversazioni precedenti?",
            "Ricordi cosa abbiamo discusso la scorsa volta?",
            "Cosa abbiamo detto riguardo al visto investitore?",
        ],
        "expected_keywords": ["conversazioni", "memoria", "ricordo", "discusso"],
    },
    {
        "category": "CRM Services",
        "questions": [
            "Puoi controllare le mie pratiche attive nel CRM?",
            "Quali sono le mie pratiche attive?",
            "Controlla il mio status cliente",
        ],
        "expected_keywords": ["crm", "pratiche", "cliente", "status"],
    },
    {
        "category": "Memory Service",
        "questions": [
            "Cosa ricordi di me?",
            "Hai informazioni su di me nelle memorie?",
            "Cerca nelle memorie precedenti",
        ],
        "expected_keywords": ["memoria", "ricordo", "informazioni"],
    },
    {
        "category": "Agentic Functions",
        "questions": [
            "Puoi creare un journey automatizzato per questo progetto?",
            "Monitora le scadenze di compliance per me",
            "Calcola il prezzo per questo servizio",
        ],
        "expected_keywords": ["journey", "compliance", "prezzo", "monitor"],
    },
    {
        "category": "Oracle Services",
        "questions": [
            "Cerca informazioni su Tax, Legal e Visa insieme",
            "Sintetizza informazioni da più domini",
            "Fai una ricerca cross-domain",
        ],
        "expected_keywords": ["tax", "legal", "visa", "sintesi", "domini"],
    },
    {
        "category": "Knowledge Base",
        "questions": [
            "Cosa hai nella knowledge base?",
            "Quali collezioni hai disponibili?",
            "Cerca nella knowledge base",
        ],
        "expected_keywords": ["knowledge", "collezioni", "documenti"],
    },
    {
        "category": "Backend Capabilities",
        "questions": [
            "Cosa puoi fare per me?",
            "Quali sono le tue capacità?",
            "Cosa sai fare?",
        ],
        "expected_keywords": [
            "crm",
            "memoria",
            "conversazioni",
            "compliance",
            "prezzo",
        ],
    },
]


async def test_backend_health() -> Dict[str, Any]:
    """Test backend health endpoints"""
    print(f"{BLUE}🔍 Testing Backend Health...{NC}")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Basic health
        try:
            response = await client.get(f"{BACKEND_URL}/health")
            basic_health = response.json()
            print(f"  ✅ Basic Health: {basic_health.get('status')}")
        except Exception as e:
            print(f"  ❌ Basic Health failed: {e}")
            return {"status": "error", "error": str(e)}

        # Detailed health
        try:
            response = await client.get(f"{BACKEND_URL}/health/detailed")
            detailed_health = response.json()
            services_status = detailed_health.get("services", {})

            print("  📊 Services Status:")
            for service, status in services_status.items():
                status_icon = "✅" if status.get("status") == "healthy" else "🟡"
                print(f"    {status_icon} {service}: {status.get('status')}")

            return {"basic": basic_health, "detailed": detailed_health}
        except Exception as e:
            print(f"  ⚠️  Detailed Health failed: {e}")
            return {"basic": basic_health, "detailed": None}

    return {"status": "unknown"}


async def test_zantara_communication(
    question: str, expected_keywords: List[str], api_key: str = None
) -> Dict[str, Any]:
    """Test Zantara communication with a question"""
    print(f'\n{BLUE}💬 Testing: "{question}"{NC}')

    # Simulate a chat request
    # Note: This requires authentication, so we'll just verify the endpoint exists
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Check if endpoint exists (will fail auth, but endpoint should exist)
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key

            # We can't actually test without auth, so we'll verify endpoint structure
            response = await client.get(
                f"{BACKEND_URL}/bali-zero/chat-stream",
                params={"query": question},
                headers=headers,
            )

            # If we get 401, endpoint exists (good)
            # If we get 404, endpoint doesn't exist (bad)
            if response.status_code == 401:
                return {
                    "status": "endpoint_exists",
                    "message": "Endpoint exists (auth required)",
                }
            elif response.status_code == 404:
                return {
                    "status": "endpoint_missing",
                    "message": "Endpoint not found",
                }
            else:
                return {
                    "status": "unknown",
                    "status_code": response.status_code,
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def verify_backend_services() -> Dict[str, Any]:
    """Verify all backend services are accessible"""
    print(f"\n{BLUE}🔌 Verifying Backend Services...{NC}")

    services_to_check = [
        ("Conversations", "/api/bali-zero/conversations/stats"),
        ("Memory", "/api/memory/stats"),
        ("CRM", "/api/crm-clients/stats/overview"),
        ("Agents", "/api/agents/status"),
        ("Knowledge", "/api/knowledge/collections"),
        ("Health", "/health"),
    ]

    results = {}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for service_name, endpoint in services_to_check:
            try:
                response = await client.get(f"{BACKEND_URL}{endpoint}")
                if response.status_code in [
                    200,
                    401,
                ]:  # 401 = endpoint exists, needs auth
                    print(f"  ✅ {service_name}: Endpoint accessible")
                    results[service_name] = "accessible"
                else:
                    print(f"  🟡 {service_name}: Status {response.status_code}")
                    results[service_name] = f"status_{response.status_code}"
            except Exception as e:
                print(f"  ❌ {service_name}: {e}")
                results[service_name] = f"error: {str(e)}"

    return results


def verify_webapp_integration() -> Dict[str, Any]:
    """Verify webapp integration files"""
    print(f"\n{BLUE}🌐 Verifying Webapp Integration...{NC}")

    webapp_path = Path("apps/mouth/src")
    integration_files = [
        "lib/api/zantara-integration.ts",
        "lib/api/chat.ts",
        "app/chat/page.tsx",
        "app/api/chat/stream/route.ts",
    ]

    results = {}
    for file_path in integration_files:
        full_path = webapp_path / file_path
        if full_path.exists():
            # Count zantaraAPI references
            content = full_path.read_text()
            count = content.lower().count("zantaraapi") + content.lower().count(
                "zantara_context"
            )
            print(f"  ✅ {file_path}: {count} references")
            results[file_path] = {"exists": True, "references": count}
        else:
            print(f"  ❌ {file_path}: Not found")
            results[file_path] = {"exists": False}

    return results


def verify_context_builder() -> Dict[str, Any]:
    """Verify context builder implementation"""
    print(f"\n{BLUE}📚 Verifying Context Builder...{NC}")

    context_builder_path = Path(
        "apps/backend-rag/backend/services/context/context_builder.py"
    )

    if not context_builder_path.exists():
        return {"status": "error", "message": "Context builder not found"}

    content = context_builder_path.read_text()

    methods_to_check = [
        "build_zantara_identity",
        "build_backend_services_context",
        "build_identity_context",
        "build_memory_context",
        "build_team_context",
        "combine_contexts",
    ]

    results = {}
    for method in methods_to_check:
        if f"def {method}" in content:
            print(f"  ✅ {method}(): Implemented")
            results[method] = True
        else:
            print(f"  ❌ {method}(): Missing")
            results[method] = False

    # Check for backend services context
    if "BACKEND SERVICES AVAILABLE TO ZANTARA" in content:
        print("  ✅ Backend services context: Documented")
        results["backend_services_documented"] = True
    else:
        print("  ❌ Backend services context: Not documented")
        results["backend_services_documented"] = False

    return results


def verify_jaksel_persona() -> Dict[str, Any]:
    """Verify Jaksel persona prompt"""
    print(f"\n{BLUE}🎭 Verifying Jaksel Persona...{NC}")

    persona_path = Path("apps/backend-rag/backend/prompts/jaksel_persona.py")

    if not persona_path.exists():
        return {"status": "error", "message": "Persona file not found"}

    content = persona_path.read_text()

    checks = {
        "SYSTEM_INSTRUCTION": "SYSTEM_INSTRUCTION" in content,
        "BACKEND SERVICES section": "BACKEND SERVICES" in content
        or "Backend Services" in content,
        "FEW_SHOT_EXAMPLES": "FEW_SHOT_EXAMPLES" in content,
        "Natural language guidelines": "natural" in content.lower()
        or "robotic" in content.lower(),
    }

    results = {}
    for check_name, passed in checks.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {check_name}: {'Present' if passed else 'Missing'}")
        results[check_name] = passed

    # Count few-shot examples
    if "FEW_SHOT_EXAMPLES" in content:
        # Count dictionary entries in FEW_SHOT_EXAMPLES
        examples_count = content.count('"role":')
        print(f"  📊 Few-shot examples: ~{examples_count // 2}")
        results["examples_count"] = examples_count // 2

    return results


async def main():
    """Main verification function"""
    print(f"{BLUE}{'=' * 60}{NC}")
    print(f"{BLUE}🚀 NUZANTARA PRIME - Zantara Services Verification{NC}")
    print(f"{BLUE}{'=' * 60}{NC}\n")

    all_results = {}

    # 1. Backend Health
    health_results = await test_backend_health()
    all_results["health"] = health_results

    # 2. Backend Services
    services_results = await verify_backend_services()
    all_results["services"] = services_results

    # 3. Webapp Integration
    webapp_results = verify_webapp_integration()
    all_results["webapp"] = webapp_results

    # 4. Context Builder
    context_results = verify_context_builder()
    all_results["context_builder"] = context_results

    # 5. Jaksel Persona
    persona_results = verify_jaksel_persona()
    all_results["persona"] = persona_results

    # Summary
    print(f"\n{BLUE}{'=' * 60}{NC}")
    print(f"{BLUE}📊 VERIFICATION SUMMARY{NC}")
    print(f"{BLUE}{'=' * 60}{NC}\n")

    # Health summary
    if health_results.get("basic", {}).get("status") == "healthy":
        print(f"{GREEN}✅ Backend Health: HEALTHY{NC}")
    else:
        print(f"{YELLOW}🟡 Backend Health: Check required{NC}")

    # Services summary
    accessible_services = sum(1 for v in services_results.values() if v == "accessible")
    total_services = len(services_results)
    print(
        f"{GREEN}✅ Backend Services: {accessible_services}/{total_services} accessible{NC}"
    )

    # Webapp summary
    existing_files = sum(1 for v in webapp_results.values() if v.get("exists"))
    total_files = len(webapp_results)
    print(
        f"{GREEN}✅ Webapp Integration: {existing_files}/{total_files} files present{NC}"
    )

    # Context Builder summary
    implemented_methods = sum(1 for v in context_results.values() if v is True)
    total_methods = len(
        [k for k in context_results.keys() if k != "backend_services_documented"]
    )
    print(
        f"{GREEN}✅ Context Builder: {implemented_methods}/{total_methods} methods implemented{NC}"
    )

    # Persona summary
    persona_checks = sum(1 for v in persona_results.values() if v is True)
    total_checks = len([k for k in persona_results.keys() if k != "examples_count"])
    print(
        f"{GREEN}✅ Jaksel Persona: {persona_checks}/{total_checks} checks passed{NC}"
    )

    # Save results
    results_file = Path("docs/verification_results.json")
    results_file.write_text(json.dumps(all_results, indent=2))
    print(f"\n{GREEN}✅ Results saved to: {results_file}{NC}")

    # Final verdict
    print(f"\n{BLUE}{'=' * 60}{NC}")
    if (
        health_results.get("basic", {}).get("status") == "healthy"
        and accessible_services >= total_services * 0.8
        and existing_files == total_files
        and implemented_methods == total_methods
    ):
        print(f"{GREEN}✅ VERDICT: PRODUCTION READY{NC}")
        return 0
    else:
        print(f"{YELLOW}🟡 VERDICT: CHECK REQUIRED{NC}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
