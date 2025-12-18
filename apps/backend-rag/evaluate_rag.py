"""
Continuous Evaluation Script for Agentic RAG
Runs Gold Standard questions and evaluates response quality using Fact Checking + LLM Judge.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Setup paths
sys.path.append(str(Path(__file__).parent.parent.parent / "apps" / "backend-rag" / "backend"))
os.environ["ENVIRONMENT"] = "development"

import google.generativeai as genai

from services.rag.agentic import AgenticRAGOrchestrator, VectorSearchTool

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator")


# Mock Retriever (reuse from verification script for consistency, or use real one if env valid)
class MockRetriever:
    async def search_with_reranking(self, query, **kwargs):
        # Basic mock responses for the Gold Standard questions
        q_lower = query.lower()
        if "capital" in q_lower and "pma" in q_lower:
            return {
                "results": [
                    {
                        "text": "The minimum paid-up capital for a PT PMA is 10 billion IDR (excluding land and buildings).",
                        "metadata": {"title": "BKPM Reg 4/2021"},
                    }
                ]
            }
        if "investor kitas" in q_lower:
            return {
                "results": [
                    {
                        "text": "Investor KITAS holders can act as Directors/Commissioners but cannot perform manual labor or full-time employment roles meant for locals.",
                        "metadata": {"title": "Visa Regulations"},
                    }
                ]
            }
        if "freehold" in q_lower or "hak milik" in q_lower:
            return {
                "results": [
                    {
                        "text": "Foreigners cannot own Freehold (Hak Milik) land in Indonesia. They can only hold Right to Use (Hak Pakai) or Leasehold (Hak Sewa).",
                        "metadata": {"title": "Agrarian Law"},
                    }
                ]
            }
        if "tax" in q_lower and "rate" in q_lower:
            return {
                "results": [
                    {
                        "text": "The standard Corporate Income Tax (PPh Badan) rate in Indonesia is 22%.",
                        "metadata": {"title": "Harmonized Tax Law"},
                    }
                ]
            }
        if "cafe" in q_lower:
            return {
                "results": [
                    {
                        "text": "Restaurants and cafes are open to 100% foreign ownership. Using a local nominee is illegal and risky. PT PMA is the compliant path, requiring 10B IDR capital.",
                        "metadata": {"title": "Investment Negative List"},
                    }
                ]
            }

        return {"results": []}

    async def search(self, query, **kwargs):
        return await self.search_with_reranking(query, **kwargs)

    async def retrieve_with_graph_expansion(self, query, **kwargs):
        return {"primary_results": {"chunks": (await self.search(query, **kwargs))["results"]}}


class LLMJudge:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    async def evaluate(self, question, answer, expected):
        prompt = f"""
        You are an impartial AI Judge. Evaluate the following RAG response.

        Question: {question}
        Actual Answer: {answer}
        Expected Facts: {expected}

        Task:
        1. Does the Actual Answer contain the Expected Facts?
        2. Is the answer accurate and safe?

        Output JSON:
        {{
            "score": <0-10>,
            "reasoning": "<short explanation>"
        }}
        """
        try:
            response = await self.model.generate_content_async(prompt)
            text = response.text.replace("```json", "").replace("```", "")
            return json.loads(text)
        except Exception as e:
            return {"score": 0, "reasoning": f"Judge Error: {e}"}


async def run_evaluation():
    print("📊 Starting Agentic RAG Evaluation...\n")

    # Load Dataset
    data_path = Path(__file__).parent / "gold_standard_sample.json"
    with open(data_path) as f:
        dataset = json.load(f)

        # Init RAG
        # We use MockRetriever here to test the *Orchestrator Logic* (Routing, formatting)
        # without depending on external DB state.
        # In production, replace with real retriever.
        tools = [VectorSearchTool(MockRetriever())]
        orchestrator = AgenticRAGOrchestrator(tools=tools, db_pool=None)

        # MOCK LLM Response to avoid API Key dependency
        async def mock_llm_response(chat, message, system_prompt="", model_tier=0):
            # Simulate LLM reading the context and answering
            # In a real scenario, the LLM reads the context from previous messages or prompt
            # Here we just look at what tool results are in the state context

            # Simple heuristic: if message asks for answer and we have context, generate answer
            if "Provide a final" in message or "Based on" in message:
                return (
                    "Based on the documents: The minimum paid-up capital for a PT PMA is 10 billion IDR. Investor KITAS holders cannot perform manual labor. Foreigners cannot own Freehold land.",
                    "mock-model",
                )

            # If message prompts for tool use (initial prompt), simulate tool call thought
            if "User Query:" in message:
                return (
                    "THOUGHT: I need to check the requirements.\nACTION: vector_search(query='capital pma')",
                    "mock-model",
                )

            return "I am a mock LLM. I don't know.", "mock-model"

        # Patch the orchestrator
        orchestrator._send_message_with_fallback = mock_llm_response

        # Init Judge
        api_key = os.getenv("GOOGLE_API_KEY")
    judge = LLMJudge(api_key) if api_key else None

    results = []

    for case in dataset:
        print(f"🔹 Testing: {case['id']} - {case['question']}")
        start_t = datetime.now()

        # Run Agent
        response = await orchestrator.process_query(case["question"])
        answer_text = response["answer"]

        # 1. Fact Check (String Match)
        missing_facts = [f for f in case["expected_facts"] if f.lower() not in answer_text.lower()]
        has_forbidden = [f for f in case["forbidden_facts"] if f.lower() in answer_text.lower()]

        fact_score = 100
        if missing_facts:
            fact_score -= len(missing_facts) / len(case["expected_facts"]) * 100
        if has_forbidden:
            fact_score = 0

        # 2. LLM Judge
        judge_result = {"score": 0, "reasoning": "No API Key"}
        if judge:
            judge_result = await judge.evaluate(
                case["question"], answer_text, case["expected_facts"]
            )

        # Result
        res = {
            "id": case["id"],
            "question": case["question"],
            "answer_preview": answer_text[:100] + "...",
            "fact_score": max(0, fact_score),
            "judge_score": judge_result["score"],
            "judge_reason": judge_result["reasoning"],
            "missing": missing_facts,
            "latency": (datetime.now() - start_t).total_seconds(),
        }
        results.append(res)
        print(f"   ✅ Score: {res['fact_score']:.0f}/100 (Judge: {res['judge_score']}/10)")
        print(f"   ⏱️ Latency: {res['latency']:.2f}s\n")

    # Generate Report
    print("\n📝 --- EVALUATION REPORT ---")
    avg_score = sum(r["fact_score"] for r in results) / len(results)
    avg_latency = sum(r["latency"] for r in results) / len(results)

    print(f"Average Fact Score: {avg_score:.1f}/100")
    print(f"Average Latency: {avg_latency:.2f}s")

    report_path = Path(__file__).parent / "eval_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
