import asyncio
import logging
import os
import sys
import httpx
import time
from typing import List, Dict, Any

# Configure Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ZantaraFleet")

# Configuration
API_URL = os.getenv("RAG_API_URL", "http://localhost:8080")
API_KEY = os.getenv("API_KEY", "dev_api_key_for_testing_only")  # Default dev key
TIMEOUT = 60.0


class AgentTester:
    def __init__(self, name: str, focus: str, questions: List[str]):
        self.name = name
        self.focus = focus
        self.questions = questions

    async def run_mission(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Runs the agent's assigned mission via API"""
        logger.info(f"🚀 {self.name} starting mission: {self.focus}")
        results = {"agent": self.name, "passed": 0, "failed": 0, "details": []}

        for q in self.questions:
            try:
                start_ts = time.time()

                # Payload for Agentic RAG
                rag_payload = {
                    "query": q,
                    "user_id": "fleet_tester",
                    "conversation_history": [],
                }

                # Payload for Oracle
                oracle_payload = {
                    "query": q,
                    "user_email": "fleet_tester@zantara.local",
                    "limit": 5,
                }

                # Try Agentic RAG Endpoint first
                endpoint = f"{API_URL}/api/agentic-rag/query"
                response = await client.post(
                    endpoint,
                    json=rag_payload,
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "x-api-key": API_KEY,
                    },
                )

                if response.status_code == 404:
                    # Fallback to Oracle
                    endpoint = f"{API_URL}/api/oracle/query"
                    logger.warning(
                        f"  ⚠️ Agentic endpoint 404, trying Oracle: {endpoint}"
                    )
                    response = await client.post(
                        endpoint,
                        json=oracle_payload,
                        headers={"x-api-key": API_KEY},  # Oracle uses x-api-key often
                    )

                # Check for logic errors masquerading as 200
                if response.status_code == 200:
                    data = response.json()
                    # Check for explicit success flag or error field
                    if data.get("success") is False:
                        error_msg = data.get("error") or "Unknown logical error"
                        raise Exception(f"Logic Error (200 OK): {error_msg}")
                    # Check for answer
                    answer = data.get("answer")
                    if not answer:
                        raise Exception("No answer in response")
                else:
                    response.raise_for_status()  # Raise for 4xx/5xx

                # If we got here, we have an answer
                answer = data.get("answer", "")
                valid = len(answer) > 10

                latency = time.time() - start_ts
                status = "✅ PASS" if valid else "❌ FAIL"
                logger.info(
                    f"  Query: '{q[:30]}...' -> {status} ({latency:.2f}s) via {endpoint}"
                )

                if valid:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

                results["details"].append(
                    {
                        "query": q,
                        "valid": valid,
                        "answer_preview": str(answer)[:50],
                        "latency": latency,
                        "endpoint": endpoint,
                    }
                )

            except Exception as e:
                logger.error(f"  ❌ Error on query '{q}': {e}")
                results["failed"] += 1
                results["details"].append({"query": q, "valid": False, "error": str(e)})

        return results


async def main():
    print("==================================================")
    print(f"🛸 ZANTARA AGENT FLEET VERIFICATION (Target: {API_URL})")
    print("==================================================")

    # Check connection first
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{API_URL}/health")
            if resp.status_code == 200:
                print("✅ Target System Online")
            else:
                print(f"⚠️ Target returned {resp.status_code} at /health")
        except Exception:
            print(f"❌ CRITICAL: Cannot connect to {API_URL}. Is the backend running?")
            print(
                "   Run 'docker compose up' or 'cd apps/backend-rag && ./start_backend.sh'"
            )
            sys.exit(1)

    fleet = [
        AgentTester(
            name="Alpha (KB)",
            focus="KNOWLEDGE",
            questions=[
                "Cos'è un KITAS Investor?",
                "Quali sono i requisiti per una PT PMA?",
            ],
        ),
        AgentTester(
            name="Beta (Tools)",
            focus="TOOLS",
            questions=[
                "Quanto costa il pacchetto KITAS Investor?",
                "Calcola il 10% di 52390123",
            ],
        ),
        AgentTester(
            name="Gamma (Comms)",
            focus="COMMUNICATION",
            questions=[
                "Ciao Zantara, chi sei?",
                "Tuliskan puisi pendek bahasa Indonesia",  # Check multi-language
            ],
        ),
    ]

    all_results = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for agent in fleet:
            res = await agent.run_mission(client)
            all_results.append(res)
            print(
                f"\n📊 Report {agent.name}: {res['passed']} Passed, {res['failed']} Failed"
            )

    print("\n==================================================")
    print("🏁 FLEET MISSION REPORT")
    total_passed = sum(r["passed"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)

    if total_failed == 0:
        print("✅ SUCCESS: All systems nominal.")
        sys.exit(0)
    else:
        print(f"❌ FAILURE: {total_failed} issues detected.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
