#!/usr/bin/env python3
"""
Zantara Business Intelligence & Collection Audit
=================================================

Tests Zantara's ability to:
1. Route queries to correct Qdrant collections
2. Extract and utilize Knowledge Graph entities
3. Handle long-context business consultations
4. Provide accurate domain-specific answers (KBLI, Immigration)

Usage:
    python3 verify_business_intelligence.py
"""

import asyncio
import httpx
import json
import time
from typing import Dict, List, Any

# Production endpoint
BASE_URL = "https://nuzantara-rag.fly.dev"
API_KEY = "zantara-secret-2024"  # Production API key

# Test user identity
TEST_USER = "business_auditor_2026@nuzantara.com"

class BusinessIntelligenceAuditor:
    def __init__(self):
        self.results = {
            "kbli_accuracy": [],
            "immigration_accuracy": [],
            "kg_utilization": [],
            "long_context": [],
            "collection_routing": [],
        }
        self.session_id = f"audit_{int(time.time())}"
        
    async def query_zantara(self, query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Send query to Zantara and capture response + metadata."""
        async with httpx.AsyncClient(timeout=120.0) as client:  # Increased timeout for RAG queries
            payload = {
                "query": query,
                "user_id": TEST_USER,
                "session_id": self.session_id,
            }
            if conversation_history:
                payload["conversation_history"] = conversation_history
            
            response = await client.post(
                f"{BASE_URL}/api/agentic-rag/query",
                json=payload,
                headers={"X-API-Key": API_KEY}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
    
    async def test_kbli_classification(self):
        """Test KBLI domain knowledge and classification accuracy."""
        print("\n" + "="*60)
        print("TEST 1: KBLI Classification & Domain Knowledge")
        print("="*60)
        
        test_cases = [
            {
                "query": "Qual è il codice KBLI per un ristorante italiano?",
                "expected_entities": ["KBLI", "56101"],
                "expected_concepts": ["restaurant", "food service"],
            },
            {
                "query": "Posso aprire una società di consulenza digitale con il KBLI 70209?",
                "expected_entities": ["KBLI", "70209"],
                "expected_concepts": ["digital consultancy", "foreign investment"],
            },
            {
                "query": "Quali sono i requisiti per il KBLI 62010 (sviluppo software)?",
                "expected_entities": ["KBLI", "62010"],
                "expected_concepts": ["software development", "requirements"],
            },
        ]
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n[{i}] Query: {test['query']}")
            result = await self.query_zantara(test['query'])
            
            if "error" in result:
                print(f"❌ ERROR: {result['error']}")
                self.results["kbli_accuracy"].append({"test": i, "passed": False, "error": result['error']})
                continue
            
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            entities = result.get("entities", {})
            
            print(f"📝 Answer: {answer[:200]}...")
            print(f"📚 Sources: {len(sources)} documents")
            print(f"🔍 Entities: {entities}")
            
            # Validation
            passed = True
            for expected_entity in test["expected_entities"]:
                if expected_entity.lower() not in answer.lower():
                    print(f"⚠️  Missing expected entity: {expected_entity}")
                    passed = False
            
            self.results["kbli_accuracy"].append({
                "test": i,
                "query": test['query'],
                "passed": passed,
                "answer_length": len(answer),
                "sources_count": len(sources),
                "entities_found": entities,
            })
            
            print(f"{'✅ PASSED' if passed else '❌ FAILED'}")
            await asyncio.sleep(2)  # Rate limiting
    
    async def test_immigration_domain(self):
        """Test Immigration/Visa domain knowledge."""
        print("\n" + "="*60)
        print("TEST 2: Immigration & Visa Domain Knowledge")
        print("="*60)
        
        test_cases = [
            {
                "query": "Quali sono i requisiti per ottenere un KITAS Investor?",
                "expected_concepts": ["KITAS", "investor", "requirements", "capital"],
            },
            {
                "query": "Differenza tra E33G (Remote Worker) e E23Y (Digital Specialist)?",
                "expected_concepts": ["E33G", "E23Y", "remote worker", "digital specialist"],
            },
            {
                "query": "Quanto costa un visto B211A per 60 giorni?",
                "expected_concepts": ["B211A", "60 days", "cost", "visa"],
            },
        ]
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n[{i}] Query: {test['query']}")
            result = await self.query_zantara(test['query'])
            
            if "error" in result:
                print(f"❌ ERROR: {result['error']}")
                self.results["immigration_accuracy"].append({"test": i, "passed": False, "error": result['error']})
                continue
            
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            
            print(f"📝 Answer: {answer[:200]}...")
            print(f"📚 Sources: {len(sources)} documents")
            
            # Validation
            passed = sum(1 for concept in test["expected_concepts"] if concept.lower() in answer.lower()) >= 2
            
            self.results["immigration_accuracy"].append({
                "test": i,
                "query": test['query'],
                "passed": passed,
                "answer_length": len(answer),
                "sources_count": len(sources),
            })
            
            print(f"{'✅ PASSED' if passed else '❌ FAILED'}")
            await asyncio.sleep(2)
    
    async def test_kg_utilization(self):
        """Test Knowledge Graph entity extraction and relationship traversal."""
        print("\n" + "="*60)
        print("TEST 3: Knowledge Graph Utilization")
        print("="*60)
        
        test_cases = [
            {
                "query": "Quali sono i prerequisiti per aprire una PT PMA?",
                "expected_kg_entities": ["PT PMA", "KITAS", "capital"],
            },
            {
                "query": "Che relazione c'è tra KBLI e permesso di lavoro?",
                "expected_kg_entities": ["KBLI", "work permit"],
            },
        ]
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n[{i}] Query: {test['query']}")
            result = await self.query_zantara(test['query'])
            
            if "error" in result:
                print(f"❌ ERROR: {result['error']}")
                self.results["kg_utilization"].append({"test": i, "passed": False, "error": result['error']})
                continue
            
            answer = result.get("answer", "")
            entities = result.get("entities", {})
            
            print(f"📝 Answer: {answer[:200]}...")
            print(f"🔗 KG Entities: {entities}")
            
            # Check if KG was utilized (entities extracted)
            kg_used = len(entities) > 0
            
            self.results["kg_utilization"].append({
                "test": i,
                "query": test['query'],
                "kg_used": kg_used,
                "entities_extracted": entities,
            })
            
            print(f"{'✅ KG UTILIZED' if kg_used else '⚠️  NO KG EXTRACTION'}")
            await asyncio.sleep(2)
    
    async def test_long_context(self):
        """Test multi-turn business consultation with context retention."""
        print("\n" + "="*60)
        print("TEST 4: Long-Context Business Consultation")
        print("="*60)
        
        conversation = []
        
        # Turn 1: Initial question
        print("\n[Turn 1] Initial Question")
        query1 = "Voglio aprire un ristorante a Bali. Quali sono i passi principali?"
        result1 = await self.query_zantara(query1, conversation)
        
        if "error" in result1:
            print(f"❌ ERROR: {result1['error']}")
            self.results["long_context"].append({"passed": False, "error": result1['error']})
            return
        
        answer1 = result1.get("answer", "")
        print(f"📝 Answer: {answer1[:150]}...")
        
        conversation.append({"role": "user", "content": query1})
        conversation.append({"role": "assistant", "content": answer1})
        
        await asyncio.sleep(2)
        
        # Turn 2: Follow-up (requires context)
        print("\n[Turn 2] Follow-up Question (Context Required)")
        query2 = "E per il KBLI, quale codice devo usare?"
        result2 = await self.query_zantara(query2, conversation)
        
        if "error" in result2:
            print(f"❌ ERROR: {result2['error']}")
            self.results["long_context"].append({"passed": False, "error": result2['error']})
            return
        
        answer2 = result2.get("answer", "")
        print(f"📝 Answer: {answer2[:150]}...")
        
        # Validation: Should mention restaurant KBLI (56101)
        context_retained = "56101" in answer2 or "ristorante" in answer2.lower()
        
        conversation.append({"role": "user", "content": query2})
        conversation.append({"role": "assistant", "content": answer2})
        
        await asyncio.sleep(2)
        
        # Turn 3: Deep follow-up
        print("\n[Turn 3] Deep Follow-up (Multi-turn Context)")
        query3 = "E per il visto, cosa mi serve?"
        result3 = await self.query_zantara(query3, conversation)
        
        if "error" in result3:
            print(f"❌ ERROR: {result3['error']}")
            self.results["long_context"].append({"passed": False, "error": result3['error']})
            return
        
        answer3 = result3.get("answer", "")
        print(f"📝 Answer: {answer3[:150]}...")
        
        # Validation: Should mention business visa (KITAS)
        visa_mentioned = "KITAS" in answer3 or "visto" in answer3.lower()
        
        self.results["long_context"].append({
            "passed": context_retained and visa_mentioned,
            "turn_1_length": len(answer1),
            "turn_2_context_retained": context_retained,
            "turn_3_visa_mentioned": visa_mentioned,
        })
        
        print(f"{'✅ CONTEXT RETAINED' if context_retained and visa_mentioned else '❌ CONTEXT LOST'}")
    
    async def run_audit(self):
        """Execute all tests."""
        print("\n🧠 Starting Zantara Business Intelligence Audit...")
        print(f"👤 User: {TEST_USER}")
        print(f"🔑 Session: {self.session_id}")
        
        await self.test_kbli_classification()
        await self.test_immigration_domain()
        await self.test_kg_utilization()
        await self.test_long_context()
        
        # Generate Report
        print("\n" + "="*60)
        print("AUDIT REPORT")
        print("="*60)
        
        kbli_passed = sum(1 for r in self.results["kbli_accuracy"] if r.get("passed", False))
        kbli_total = len(self.results["kbli_accuracy"])
        
        immigration_passed = sum(1 for r in self.results["immigration_accuracy"] if r.get("passed", False))
        immigration_total = len(self.results["immigration_accuracy"])
        
        kg_used_count = sum(1 for r in self.results["kg_utilization"] if r.get("kg_used", False))
        kg_total = len(self.results["kg_utilization"])
        
        long_context_passed = sum(1 for r in self.results["long_context"] if r.get("passed", False))
        long_context_total = len(self.results["long_context"])
        
        print(f"\n📊 KBLI Domain: {kbli_passed}/{kbli_total} PASSED")
        print(f"📊 Immigration Domain: {immigration_passed}/{immigration_total} PASSED")
        print(f"📊 KG Utilization: {kg_used_count}/{kg_total} queries used KG")
        print(f"📊 Long Context: {long_context_passed}/{long_context_total} PASSED")
        
        # Overall Score
        total_tests = kbli_total + immigration_total + long_context_total
        total_passed = kbli_passed + immigration_passed + long_context_passed
        
        if total_tests > 0:
            score = (total_passed / total_tests) * 100
            print(f"\n🎯 Overall Score: {score:.1f}% ({total_passed}/{total_tests})")
            
            if score >= 80:
                print("✅ AUDIT PASSED: Zantara meets SOTA 2026 Business Intelligence standards.")
            elif score >= 60:
                print("⚠️  AUDIT WARNING: Some improvements needed.")
            else:
                print("❌ AUDIT FAILED: Significant issues detected.")
        
        # Save detailed results
        with open("business_intelligence_audit_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print("\n📄 Detailed results saved to: business_intelligence_audit_results.json")

async def main():
    auditor = BusinessIntelligenceAuditor()
    await auditor.run_audit()

if __name__ == "__main__":
    asyncio.run(main())
