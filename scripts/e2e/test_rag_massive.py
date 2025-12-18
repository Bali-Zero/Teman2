#!/usr/bin/env python3
"""
Massive RAG Testing Script
Tests the RAG system with difficult and multi-topic questions
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))

# Configuration
BACKEND_URL = "https://nuzantara-rag.fly.dev"
API_KEY = "REDACTED-ROTATED-KEY"  # Default from frontend code
TEST_USER_EMAIL = "test@balizero.com"

# Test questions organized by category
TEST_QUESTIONS = {
    "legal_complex": [
        "Quali sono le differenze tra PT PMA e PT Lokal per un investitore straniero che vuole aprire un'azienda in Indonesia?",
        "Mi spieghi il processo completo per ottenere un KITAS per investimento, includendo tutti i requisiti e i tempi?",
        "Come funziona il sistema fiscale indonesiano per le PMA? Quali sono le aliquote e le scadenze?",
        "Quali sono le leggi attualmente in vigore riguardo al lavoro remoto per dipendenti stranieri in Indonesia?",
        "Mi serve una guida completa su come registrare un marchio in Indonesia, passo per passo.",
    ],
    "multi_topic": [
        "Confronta i costi tra KITAS lavorativo e investimento, e dimmi anche quali sono i requisiti per ciascuno.",
        "Quali sono tutti i passaggi necessari per aprire una PMA e ottenere il visto? Includi anche i costi.",
        "Dimmi tutto quello che devo sapere su tasse, visti e permessi per aprire un ristorante a Bali come straniero.",
        "Fammi un timeline completo: da quando arrivo in Indonesia a quando posso iniziare a lavorare legalmente.",
        "Quali sono le differenze tra i vari tipi di visti (turista, business, lavoro, investimento) e quando usarli?",
    ],
    "follow_up_queries": [
        "E per le tasse?",
        "E i tempi?",
        "Quanto costa tutto questo?",
        "Cosa serve per iniziare?",
        "E se voglio cambiare tipo di visto?",
    ],
    "edge_cases": [
        "Cosa succede se la mia legge è stata abrogata?",
        "Mi serve info su una legge del 2010 che potrebbe essere cambiata.",
        "Quali sono le leggi più recenti sui visti?",
        "C'è qualche legge abrogata che dovrei conoscere?",
        "Dimmi tutto sulle leggi fiscali, anche quelle vecchie.",
    ],
    "specific_legal": [
        "Articolo 1 della legge sugli investimenti stranieri: cosa dice esattamente?",
        "Quali sono gli articoli della legge sul lavoro che riguardano gli stranieri?",
        "Mi serve il testo completo della legge sulle PMA, articolo per articolo.",
        "Cosa dice la legge sulle tasse per le aziende con capitale straniero superiore al 50%?",
    ],
    "comparison": [
        "Confronta PT PMA vs PT Lokal: vantaggi, svantaggi, costi e requisiti.",
        "Quali sono le differenze tra KITAS e KITAP? Quando conviene uno o l'altro?",
        "Confronta i vari tipi di visti disponibili per gli stranieri in Indonesia.",
        "Quali sono le differenze tra aprire un'azienda a Jakarta vs Bali?",
    ],
}

# Results storage
results: List[Dict] = []


async def test_chat_stream(
    session: aiohttp.ClientSession,
    query: str,
    category: str,
    conversation_history: Optional[List[Dict]] = None,
) -> Dict:
    """Test a single chat stream query"""
    start_time = time.time()
    
    params = {
        "query": query,
        "user_email": TEST_USER_EMAIL,
        "user_role": "member",
    }
    
    if conversation_history:
        params["conversation_history"] = json.dumps(conversation_history)
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }
    
    url = f"{BACKEND_URL}/bali-zero/chat-stream"
    
    try:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                return {
                    "query": query,
                    "category": category,
                    "success": False,
                    "error": f"HTTP {response.status}: {await response.text()}",
                    "duration": time.time() - start_time,
                }
            
            # Read streaming response
            full_response = ""
            metadata_received = False
            tokens_received = 0
            
            async for line in response.content:
                line_str = line.decode("utf-8").strip()
                if not line_str or not line_str.startswith("data: "):
                    continue
                
                try:
                    data_str = line_str[6:]  # Remove "data: " prefix
                    data = json.loads(data_str)
                    
                    if data.get("type") == "metadata":
                        metadata_received = True
                    elif data.get("type") == "token":
                        full_response += data.get("data", "")
                        tokens_received += 1
                    elif data.get("type") == "done":
                        break
                except json.JSONDecodeError:
                    # Legacy format or non-JSON data
                    if "[METADATA]" not in line_str:
                        full_response += line_str.replace("data: ", "")
            
            duration = time.time() - start_time
            
            # Analyze response quality
            response_length = len(full_response)
            has_legal_terms = any(
                term in full_response.lower()
                for term in ["legge", "articolo", "regolamento", "requisito", "procedura"]
            )
            has_specific_info = any(
                term in full_response.lower()
                for term in ["kitas", "pma", "pt", "visto", "tassa", "fiscale"]
            )
            
            result = {
                "query": query,
                "category": category,
                "success": True,
                "response_length": response_length,
                "tokens_received": tokens_received,
                "metadata_received": metadata_received,
                "has_legal_terms": has_legal_terms,
                "has_specific_info": has_specific_info,
                "duration": duration,
                "response_preview": full_response[:200] + "..." if len(full_response) > 200 else full_response,
            }
            
            return result
            
    except Exception as e:
        return {
            "query": query,
            "category": category,
            "success": False,
            "error": str(e),
            "duration": time.time() - start_time,
        }


async def test_follow_up_sequence(
    session: aiohttp.ClientSession, base_query: str, follow_ups: List[str]
) -> List[Dict]:
    """Test a sequence of follow-up queries"""
    results = []
    history = []
    
    # First query
    result = await test_chat_stream(session, base_query, "follow_up_sequence", history)
    results.append(result)
    if result["success"]:
        history.append({"role": "user", "content": base_query})
        history.append({"role": "assistant", "content": result.get("response_preview", "")})
    
    # Follow-up queries
    for follow_up in follow_ups:
        result = await test_chat_stream(session, follow_up, "follow_up_sequence", history)
        results.append(result)
        if result["success"]:
            history.append({"role": "user", "content": follow_up})
            history.append({"role": "assistant", "content": result.get("response_preview", "")})
    
    return results


async def run_all_tests():
    """Run all test categories"""
    print("🚀 Starting Massive RAG Testing")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User: {TEST_USER_EMAIL}")
    print(f"Start Time: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        total_tests = sum(len(questions) for questions in TEST_QUESTIONS.values())
        completed = 0
        
        # Test each category
        for category, questions in TEST_QUESTIONS.items():
            print(f"\n📋 Testing Category: {category.upper()}")
            print("-" * 80)
            
            for question in questions:
                completed += 1
                print(f"\n[{completed}/{total_tests}] Testing: {question[:60]}...")
                
                result = await test_chat_stream(session, question, category)
                results.append(result)
                
                if result["success"]:
                    print(f"  ✅ Success ({result['duration']:.2f}s)")
                    print(f"  📊 Response: {result['response_length']} chars, {result['tokens_received']} tokens")
                    print(f"  🔍 Legal terms: {result['has_legal_terms']}, Specific info: {result['has_specific_info']}")
                    if result.get("metadata_received"):
                        print(f"  📡 Metadata received: ✅")
                else:
                    print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")
                
                # Small delay between requests
                await asyncio.sleep(1)
        
        # Test follow-up sequences
        print(f"\n\n📋 Testing Follow-Up Sequences")
        print("-" * 80)
        
        follow_up_tests = [
            ("Quali sono i tipi di visto disponibili?", ["E per lavoro?", "E i costi?", "E i tempi?"]),
            ("Come aprire una PMA?", ["E le tasse?", "E i visti necessari?"]),
        ]
        
        for base_query, follow_ups in follow_up_tests:
            print(f"\n🔄 Testing sequence: {base_query}")
            sequence_results = await test_follow_up_sequence(session, base_query, follow_ups)
            results.extend(sequence_results)
            
            for i, result in enumerate(sequence_results):
                if result["success"]:
                    print(f"  ✅ Query {i+1}: {result['duration']:.2f}s")
                else:
                    print(f"  ❌ Query {i+1} failed: {result.get('error')}")
            
            await asyncio.sleep(2)
    
    # Generate report
    print("\n\n" + "=" * 80)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 80)
    
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
    
    if successful > 0:
        avg_duration = sum(r["duration"] for r in results if r["success"]) / successful
        avg_length = sum(r.get("response_length", 0) for r in results if r["success"]) / successful
        avg_tokens = sum(r.get("tokens_received", 0) for r in results if r["success"]) / successful
        
        print(f"\n📈 Averages (successful tests):")
        print(f"  Duration: {avg_duration:.2f}s")
        print(f"  Response Length: {avg_length:.0f} chars")
        print(f"  Tokens: {avg_tokens:.0f}")
        
        # Quality metrics
        with_legal_terms = sum(1 for r in results if r.get("has_legal_terms"))
        with_specific_info = sum(1 for r in results if r.get("has_specific_info"))
        with_metadata = sum(1 for r in results if r.get("metadata_received"))
        
        print(f"\n🎯 Quality Metrics:")
        print(f"  Responses with legal terms: {with_legal_terms}/{successful} ({with_legal_terms/successful*100:.1f}%)")
        print(f"  Responses with specific info: {with_specific_info}/{successful} ({with_specific_info/successful*100:.1f}%)")
        print(f"  Responses with metadata: {with_metadata}/{successful} ({with_metadata/successful*100:.1f}%)")
    
    # Category breakdown
    print(f"\n📋 Results by Category:")
    for category in TEST_QUESTIONS.keys():
        category_results = [r for r in results if r["category"] == category]
        if category_results:
            cat_success = sum(1 for r in category_results if r["success"])
            print(f"  {category}: {cat_success}/{len(category_results)} successful")
    
    # Failed tests details
    failed_tests = [r for r in results if not r["success"]]
    if failed_tests:
        print(f"\n❌ Failed Tests Details:")
        for test in failed_tests:
            print(f"  - {test['category']}: {test['query'][:60]}...")
            print(f"    Error: {test.get('error', 'Unknown')}")
    
    # Save detailed results
    report_file = Path(__file__).parent / f"rag_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "backend_url": BACKEND_URL,
            "summary": {
                "total": total,
                "successful": successful,
                "failed": failed,
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed report saved to: {report_file}")
    print("\n✅ Testing completed!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())



















