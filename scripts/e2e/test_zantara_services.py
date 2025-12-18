#!/usr/bin/env python3
"""
Test Zantara Knowledge of Available Services

This script tests Zantara's knowledge of all available backend services
by asking specific questions about each service category.

Usage:
    python scripts/test_zantara_services.py [--token YOUR_TOKEN] [--url BACKEND_URL]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Load environment variables
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / "apps" / "backend-rag" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BACKEND_URL = os.getenv(
    "RAG_BACKEND_URL", "https://nuzantara-rag.fly.dev"
)
DEFAULT_TOKEN = os.getenv("JWT_TOKEN", "")

# Test questions organized by service category
TEST_QUESTIONS = {
    "Conversations": [
        "Come posso salvare una conversazione nel database?",
        "Quali endpoint API sono disponibili per gestire le conversazioni?",
        "Come posso caricare la cronologia delle conversazioni?",
    ],
    "Memory Service": [
        "Come funziona il servizio di memoria semantica?",
        "Come posso cercare memorie rilevanti per una query?",
        "Come posso salvare una nuova memoria?",
    ],
    "CRM Services": [
        "Come posso ottenere informazioni su un cliente dal CRM?",
        "Quali servizi CRM sono disponibili?",
        "Come posso creare una nuova pratica nel CRM?",
        "Come posso loggare un'interazione con un cliente?",
    ],
    "Agentic Functions": [
        "Quali funzioni agentiche sono disponibili?",
        "Come posso creare un client journey?",
        "Come funziona il monitoraggio proattivo della compliance?",
        "Come posso calcolare il pricing dinamico?",
    ],
    "Oracle Services": [
        "Come funziona l'Oracle V53 Ultra Hybrid?",
        "Quali domini di conoscenza sono disponibili nell'Oracle?",
        "Come posso fare una ricerca cross-oracle?",
    ],
    "Knowledge Base": [
        "Come posso cercare nella knowledge base?",
        "Quali collezioni di conoscenza sono disponibili?",
        "Come funziona la ricerca semantica?",
    ],
    "Ingestion": [
        "Come posso ingerire nuovi documenti nella knowledge base?",
        "Quali formati di documenti sono supportati?",
        "Come funziona il processo di ingestion?",
    ],
    "Image Generation": [
        "Come posso generare immagini con Zantara?",
        "Quale servizio di generazione immagini è disponibile?",
    ],
    "Productivity": [
        "Quali servizi di produttività sono disponibili?",
        "Come posso tracciare le attività del team?",
    ],
    "Notifications": [
        "Come funziona il sistema di notifiche?",
        "Come posso inviare notifiche ai clienti?",
    ],
    "Health & Monitoring": [
        "Come posso controllare lo stato di salute del sistema?",
        "Quali metriche sono disponibili?",
    ],
    "General API Knowledge": [
        "Quali sono tutti i servizi API disponibili nel backend?",
        "Come posso vedere la lista completa degli endpoint disponibili?",
        "Quali tools sono disponibili per Zantara?",
    ],
}


async def stream_chat(
    message: str,
    conversation_history: List[Dict[str, str]],
    token: str,
    backend_url: str,
) -> str:
    """
    Stream chat response from Zantara API
    
    Returns:
        Complete response text
    """
    url = f"{backend_url}/api/chat/stream"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    
    payload = {
        "message": message,
        "user_id": "test_user",
        "conversation_history": conversation_history,
        "metadata": {
            "client_locale": "it-IT",
            "client_timezone": "Europe/Rome",
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise Exception(f"HTTP {response.status_code}: {error_text.decode()}")
                
                accumulated = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                            if event.get("type") == "token" and event.get("data"):
                                accumulated += event.get("data", "")
                            elif event.get("type") == "error":
                                raise Exception(f"API Error: {event.get('data')}")
                        except json.JSONDecodeError:
                            continue
                
                return accumulated
    except Exception as e:
        logger.error(f"Error streaming chat: {e}")
        raise


async def test_service_category(
    category: str,
    questions: List[str],
    token: str,
    backend_url: str,
    conversation_history: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Test a service category by asking multiple questions
    
    Returns:
        Dictionary with test results
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {category}")
    logger.info(f"{'='*60}")
    
    results = {
        "category": category,
        "questions": [],
        "summary": {
            "total_questions": len(questions),
            "answered": 0,
            "partial": 0,
            "no_knowledge": 0,
        },
    }
    
    for i, question in enumerate(questions, 1):
        logger.info(f"\n[{i}/{len(questions)}] Q: {question}")
        
        try:
            # Add question to conversation history
            current_history = conversation_history.copy()
            current_history.append({"role": "user", "content": question})
            
            # Get response
            response = await stream_chat(question, conversation_history, token, backend_url)
            
            # Update conversation history
            conversation_history.append({"role": "user", "content": question})
            conversation_history.append({"role": "assistant", "content": response})
            
            # Analyze response
            response_lower = response.lower()
            
            # Check for indicators
            has_knowledge = any(
                indicator in response_lower
                for indicator in [
                    "api",
                    "endpoint",
                    "servizio",
                    "service",
                    "puoi",
                    "può",
                    "disponibile",
                    "available",
                    "funziona",
                    "works",
                    "chiamare",
                    "call",
                    "utilizzare",
                    "use",
                ]
            )
            
            no_knowledge_indicators = [
                "non so",
                "non conosco",
                "non ho informazioni",
                "i don't know",
                "i'm not sure",
                "non ho accesso",
                "non posso accedere",
            ]
            
            has_no_knowledge = any(indicator in response_lower for indicator in no_knowledge_indicators)
            
            if has_no_knowledge:
                status = "no_knowledge"
                results["summary"]["no_knowledge"] += 1
            elif has_knowledge and len(response) > 100:
                status = "answered"
                results["summary"]["answered"] += 1
            elif has_knowledge:
                status = "partial"
                results["summary"]["partial"] += 1
            else:
                status = "unclear"
                results["summary"]["partial"] += 1
            
            logger.info(f"Status: {status}")
            logger.info(f"Response length: {len(response)} chars")
            logger.info(f"Response preview: {response[:200]}...")
            
            results["questions"].append(
                {
                    "question": question,
                    "response": response,
                    "status": status,
                    "length": len(response),
                }
            )
            
            # Small delay between questions
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error asking question: {e}")
            results["questions"].append(
                {
                    "question": question,
                    "response": None,
                    "status": "error",
                    "error": str(e),
                }
            )
    
    return results


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description="Test Zantara's knowledge of available services"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=DEFAULT_TOKEN,
        help="JWT authentication token",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_BACKEND_URL,
        help="Backend URL",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Test only a specific category (default: all)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="zantara_services_test_results.json",
        help="Output file for results",
    )
    
    args = parser.parse_args()
    
    if not args.token:
        logger.error("❌ No token provided. Use --token or set JWT_TOKEN env var")
        return 1
    
    logger.info("=" * 60)
    logger.info("ZANTARA SERVICES KNOWLEDGE TEST")
    logger.info("=" * 60)
    logger.info(f"Backend URL: {args.url}")
    logger.info(f"Token: {args.token[:20]}...")
    
    # Select categories to test
    categories_to_test = (
        {args.category: TEST_QUESTIONS[args.category]}
        if args.category and args.category in TEST_QUESTIONS
        else TEST_QUESTIONS
    )
    
    if args.category and args.category not in TEST_QUESTIONS:
        logger.error(f"❌ Unknown category: {args.category}")
        logger.info(f"Available categories: {', '.join(TEST_QUESTIONS.keys())}")
        return 1
    
    # Run tests
    all_results = []
    conversation_history = []
    
    for category, questions in categories_to_test.items():
        try:
            results = await test_service_category(
                category, questions, args.token, args.url, conversation_history
            )
            all_results.append(results)
        except Exception as e:
            logger.error(f"❌ Error testing category {category}: {e}")
            all_results.append(
                {
                    "category": category,
                    "error": str(e),
                    "questions": [],
                }
            )
    
    # Generate summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    total_answered = 0
    total_partial = 0
    total_no_knowledge = 0
    total_questions = 0
    
    for result in all_results:
        if "summary" in result:
            summary = result["summary"]
            total_answered += summary["answered"]
            total_partial += summary["partial"]
            total_no_knowledge += summary["no_knowledge"]
            total_questions += summary["total_questions"]
            
            logger.info(f"\n{result['category']}:")
            logger.info(f"  Answered: {summary['answered']}/{summary['total_questions']}")
            logger.info(f"  Partial: {summary['partial']}/{summary['total_questions']}")
            logger.info(f"  No Knowledge: {summary['no_knowledge']}/{summary['total_questions']}")
    
    logger.info(f"\nOverall:")
    logger.info(f"  Total Questions: {total_questions}")
    logger.info(f"  Answered: {total_answered} ({total_answered/total_questions*100:.1f}%)")
    logger.info(f"  Partial: {total_partial} ({total_partial/total_questions*100:.1f}%)")
    logger.info(f"  No Knowledge: {total_no_knowledge} ({total_no_knowledge/total_questions*100:.1f}%)")
    
    # Save results
    output_data = {
        "test_date": str(Path(__file__).stat().st_mtime),
        "backend_url": args.url,
        "categories_tested": list(categories_to_test.keys()),
        "results": all_results,
        "summary": {
            "total_questions": total_questions,
            "answered": total_answered,
            "partial": total_partial,
            "no_knowledge": total_no_knowledge,
        },
    }
    
    output_path = Path(args.output)
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"\n✅ Results saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

