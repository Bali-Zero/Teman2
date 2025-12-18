#!/usr/bin/env python3
"""
Massive Real-World Testing of Zantara Integration
Tests Zantara's knowledge, communication style, and backend integration
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Configuration
WEBAPP_URL = os.getenv("NEXT_PUBLIC_API_URL", "https://nuzantara.fly.dev")
BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
TEST_EMAIL = os.getenv("TEST_EMAIL", "zero@balizero.com")
TEST_PIN = os.getenv("TEST_PIN", "010719")

# Test categories with expected behaviors
TEST_CATEGORIES = {
    "backend_services": {
        "name": "Backend Services Awareness",
        "questions": [
            "Cosa puoi fare per me? Dimmi tutti i servizi disponibili",
            "Puoi controllare il mio CRM?",
            "Hai accesso alle memorie delle conversazioni?",
            "Puoi cercare informazioni legali?",
            "Quali funzioni agentiche hai a disposizione?",
        ],
        "expected_keywords": ["CRM", "memoria", "legale", "servizi", "funzioni"],
        "expected_style": "naturale, non robotico",
    },
    "legal_knowledge": {
        "name": "Legal Knowledge & RAG",
        "questions": [
            "Cosa dice la legge UU-7-2021 sull'immigrazione?",
            "Quali sono i requisiti per ottenere un visto KITAS?",
            "Cosa prevede il PP-28-2025 per le licenze business?",
            "Cerca informazioni su permessi di lavoro in Indonesia",
            "Quali sono le leggi più recenti sul settore sanitario?",
        ],
        "expected_keywords": ["UU", "PP", "peraturan", "legge", "requisiti"],
        "expected_style": "preciso, con citazioni legali",
    },
    "communication_style": {
        "name": "Communication Style & Personality",
        "questions": [
            "Chi sei? Presentati",
            "Come comunichi normalmente?",
            "Dimmi qualcosa su di te",
            "Qual è il tuo stile di comunicazione?",
            "Come preferisci interagire con gli utenti?",
        ],
        "expected_keywords": ["Jakarta", "Jaksel", "collega", "naturale"],
        "expected_style": "Jaksel persona, mix English-Indonesian, non robotico",
    },
    "crm_integration": {
        "name": "CRM Integration",
        "questions": [
            "Controlla i miei clienti nel CRM",
            "Hai accesso al sistema CRM?",
            "Puoi vedere la storia dei miei clienti?",
            "Cosa sai sui miei clienti?",
            "Puoi aggiornare informazioni cliente?",
        ],
        "expected_keywords": ["CRM", "cliente", "clienti", "storia"],
        "expected_style": "offerta proattiva, linguaggio naturale",
    },
    "memory_integration": {
        "name": "Memory & Context",
        "questions": [
            "Ricordi le nostre conversazioni precedenti?",
            "Cosa sai di me?",
            "Hai memoria delle nostre chat?",
            "Cosa ricordi delle nostre interazioni?",
            "Puoi accedere alle memorie passate?",
        ],
        "expected_keywords": ["memoria", "ricordo", "conversazioni", "precedenti"],
        "expected_style": "riferimenti a conversazioni passate se disponibili",
    },
    "knowledge_base": {
        "name": "Knowledge Base Access",
        "questions": [
            "Cerca informazioni su KBLI codes",
            "Dimmi qualcosa sulle tasse in Indonesia",
            "Cosa sai sul settore immobiliare a Bali?",
            "Hai informazioni su visti e immigrazione?",
            "Cerca documenti su business licensing",
        ],
        "expected_keywords": ["KBLI", "tasse", "immobiliare", "visto", "licenza"],
        "expected_style": "risposte basate su knowledge base, citazioni",
    },
    "complex_queries": {
        "name": "Complex Multi-Domain Queries",
        "questions": [
            "Voglio aprire un business a Bali. Cosa devo sapere?",
            "Quali sono i requisiti per assumere dipendenti stranieri?",
            "Come posso ottenere licenze per un hotel?",
            "Cosa serve per importare merci in Indonesia?",
            "Quali sono i passaggi per ottenere un visto investitore?",
        ],
        "expected_keywords": ["requisiti", "licenza", "visto", "business"],
        "expected_style": "risposte complete, multi-dominio, strutturate",
    },
    "error_handling": {
        "name": "Error Handling & Graceful Responses",
        "questions": [
            "Cerca informazioni su qualcosa che non esiste: XYZ123ABC",
            "Dimmi qualcosa su un argomento completamente sconosciuto",
            "Cerca documenti che non ci sono",
            "Informazioni su un servizio inesistente",
        ],
        "expected_keywords": ["non ho", "non trovo", "non disponibile"],
        "expected_style": "graziose, offrono alternative, non semplicemente 'no'",
    },
}

RESULTS_FILE = Path("docs/ZANTARA_MASSIVE_TEST_REPORT.md")


class ZantaraTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=180.0)
        self.session_token = None
        self.results = {
            "test_date": datetime.now().isoformat(),
            "webapp_url": WEBAPP_URL,
            "backend_url": BACKEND_URL,
            "categories": {},
            "summary": {},
        }

    async def login(self) -> bool:
        """Login to get session token"""
        try:
            login_url = f"{BACKEND_URL}/api/auth/login"
            response = await self.client.post(
                login_url,
                json={"email": TEST_EMAIL, "pin": TEST_PIN},
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("data", {}).get("token") or data.get("token")
                if token:
                    self.session_token = token
                    self.client.headers.update({"Authorization": f"Bearer {token}"})
                    print(f"✅ Login successful: {TEST_EMAIL}")
                    return True
                else:
                    print(f"❌ Login failed: No token in response")
                    print(f"Response: {data}")
                    return False
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    async def send_chat_message(self, message: str) -> dict[str, Any]:
        """Send a chat message to Zantara and get full response"""
        try:
            chat_url = f"{BACKEND_URL}/api/chat/stream"
            
            # Prepare request
            payload = {
                "message": message,
                "user_id": TEST_EMAIL,
                "conversation_history": [],
                "metadata": {},
                "zantara_context": {},
            }

            # Stream response
            full_response = ""
            metadata_received = []
            
            async with self.client.stream("POST", chat_url, json=payload) as response:
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "response": response.text,
                    }

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data_str = line[6:]  # Remove "data: " prefix
                            data = json.loads(data_str)
                            
                            chunk_type = data.get("type", "")
                            chunk_data = data.get("data", "")
                            
                            if chunk_type == "token":
                                full_response += str(chunk_data)
                            elif chunk_type == "metadata":
                                metadata_received.append(chunk_data)
                            elif chunk_type == "done":
                                break
                        except json.JSONDecodeError:
                            continue

            return {
                "success": True,
                "response": full_response,
                "metadata": metadata_received,
                "length": len(full_response),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": "",
            }

    def analyze_response(
        self, response: str, category: dict[str, Any], question: str
    ) -> dict[str, Any]:
        """Analyze response quality"""
        analysis = {
            "has_expected_keywords": False,
            "keyword_matches": [],
            "is_natural": False,
            "is_robotic": False,
            "has_citations": False,
            "response_length": len(response),
            "quality_score": 0,
        }

        response_lower = response.lower()

        # Check for expected keywords
        expected_keywords = category.get("expected_keywords", [])
        found_keywords = []
        for keyword in expected_keywords:
            if keyword.lower() in response_lower:
                found_keywords.append(keyword)
        
        analysis["has_expected_keywords"] = len(found_keywords) > 0
        analysis["keyword_matches"] = found_keywords

        # Check for robotic language
        robotic_phrases = [
            "ho accesso al servizio",
            "posso utilizzare",
            "il sistema mi permette",
            "ho la capacità di",
            "sono in grado di",
        ]
        analysis["is_robotic"] = any(phrase in response_lower for phrase in robotic_phrases)

        # Check for natural language
        natural_indicators = [
            "lascia che",
            "fammi",
            "controllo",
            "vediamo",
            "posso aiutarti",
            "yo",
            "bro",
        ]
        analysis["is_natural"] = any(indicator in response_lower for indicator in natural_indicators)

        # Check for citations
        analysis["has_citations"] = any(
            marker in response for marker in ["UU-", "PP-", "Pasal", "peraturan"]
        )

        # Calculate quality score
        score = 0
        if analysis["has_expected_keywords"]:
            score += 30
        if analysis["is_natural"]:
            score += 25
        if not analysis["is_robotic"]:
            score += 25
        if analysis["has_citations"]:
            score += 20
        if analysis["response_length"] > 100:
            score += 10

        analysis["quality_score"] = min(score, 100)

        return analysis

    async def test_category(self, category_name: str, category_config: dict[str, Any]):
        """Test a specific category"""
        print(f"\n{'='*70}")
        print(f"🧪 Testing: {category_config['name']}")
        print(f"{'='*70}\n")

        category_results = {
            "name": category_config["name"],
            "questions": [],
            "average_score": 0,
            "total_tests": len(category_config["questions"]),
            "passed": 0,
        }

        for i, question in enumerate(category_config["questions"], 1):
            print(f"📝 Question {i}/{len(category_config['questions'])}: {question[:60]}...")
            
            # Send message
            result = await self.send_chat_message(question)
            
            if not result["success"]:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
                category_results["questions"].append({
                    "question": question,
                    "success": False,
                    "error": result.get("error"),
                })
                continue

            response = result["response"]
            print(f"   📊 Response length: {len(response)} chars")
            
            # Analyze response
            analysis = self.analyze_response(response, category_config, question)
            
            # Display analysis
            print(f"   ✅ Keywords found: {analysis['keyword_matches']}")
            print(f"   {'✅' if analysis['is_natural'] else '❌'} Natural language")
            print(f"   {'❌' if analysis['is_robotic'] else '✅'} Not robotic")
            print(f"   {'✅' if analysis['has_citations'] else '❌'} Has citations")
            print(f"   📈 Quality score: {analysis['quality_score']}/100")
            
            # Show response preview
            preview = response[:200].replace("\n", " ")
            print(f"   💬 Preview: {preview}...\n")

            # Store result
            question_result = {
                "question": question,
                "success": True,
                "response": response,
                "analysis": analysis,
                "metadata": result.get("metadata", []),
            }
            category_results["questions"].append(question_result)
            
            if analysis["quality_score"] >= 60:
                category_results["passed"] += 1

            # Small delay between questions
            await asyncio.sleep(2)

        # Calculate average score
        successful_tests = [
            q for q in category_results["questions"] if q.get("success") and "analysis" in q
        ]
        if successful_tests:
            category_results["average_score"] = sum(
                q["analysis"]["quality_score"] for q in successful_tests
            ) / len(successful_tests)

        self.results["categories"][category_name] = category_results
        print(f"\n✅ Category complete: {category_results['passed']}/{category_results['total_tests']} passed")
        print(f"   Average score: {category_results['average_score']:.1f}/100\n")

    async def run_all_tests(self):
        """Run all test categories"""
        print("🚀 Starting Massive Real-World Testing of Zantara")
        print("=" * 70)
        print(f"Webapp URL: {WEBAPP_URL}")
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Test Email: {TEST_EMAIL}")
        print("=" * 70)

        # Login
        if not await self.login():
            print("❌ Cannot proceed without login")
            return

        # Run tests for each category
        for category_name, category_config in TEST_CATEGORIES.items():
            await self.test_category(category_name, category_config)
            await asyncio.sleep(3)  # Delay between categories

        # Generate summary
        self.generate_summary()

        # Save results
        self.save_results()

    def generate_summary(self):
        """Generate test summary"""
        total_tests = 0
        total_passed = 0
        total_score = 0
        category_count = 0

        for category_name, category_data in self.results["categories"].items():
            total_tests += category_data["total_tests"]
            total_passed += category_data["passed"]
            if category_data["average_score"] > 0:
                total_score += category_data["average_score"]
                category_count += 1

        avg_score = total_score / category_count if category_count > 0 else 0
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        self.results["summary"] = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "pass_rate": pass_rate,
            "average_score": avg_score,
            "categories_tested": len(self.results["categories"]),
        }

    def save_results(self):
        """Save results to markdown file"""
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        md_content = f"""# Zantara Massive Real-World Test Report

**Test Date:** {self.results['test_date']}  
**Webapp URL:** {self.results['webapp_url']}  
**Backend URL:** {self.results['backend_url']}

## Summary

- **Total Tests:** {self.results['summary']['total_tests']}
- **Passed:** {self.results['summary']['total_passed']}
- **Pass Rate:** {self.results['summary']['pass_rate']:.1f}%
- **Average Score:** {self.results['summary']['average_score']:.1f}/100
- **Categories Tested:** {self.results['summary']['categories_tested']}

## Test Categories

"""

        for category_name, category_data in self.results["categories"].items():
            md_content += f"""### {category_data['name']}

- **Tests:** {category_data['passed']}/{category_data['total_tests']} passed
- **Average Score:** {category_data['average_score']:.1f}/100

#### Questions & Responses

"""

            for i, question_data in enumerate(category_data["questions"], 1):
                if not question_data.get("success"):
                    md_content += f"""**Q{i}:** {question_data['question']}  
❌ **Error:** {question_data.get('error', 'Unknown')}

"""
                else:
                    analysis = question_data.get("analysis", {})
                    md_content += f"""**Q{i}:** {question_data['question']}

**Response:** {question_data['response'][:500]}...

**Analysis:**
- Keywords found: {', '.join(analysis.get('keyword_matches', []))}
- Natural language: {'✅' if analysis.get('is_natural') else '❌'}
- Robotic language: {'❌' if analysis.get('is_robotic') else '✅'}
- Has citations: {'✅' if analysis.get('has_citations') else '❌'}
- Quality score: {analysis.get('quality_score', 0)}/100

"""

        md_content += f"""
## Detailed Results (JSON)

```json
{json.dumps(self.results, indent=2, ensure_ascii=False)}
```
"""

        RESULTS_FILE.write_text(md_content, encoding="utf-8")
        print(f"\n✅ Results saved to: {RESULTS_FILE}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def main():
    tester = ZantaraTester()
    try:
        await tester.run_all_tests()
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())

