import asyncio
import logging
import uuid
import httpx
from typing import Dict, Any, List
from jose import jwt
import datetime

# Configuration
BASE_URL = "http://localhost:8080"
CHAT_ENDPOINT = f"{BASE_URL}/api/agentic-rag/query"
USER_ID = "tester_tester"
USER_EMAIL = "tester@balizero.com"
SESSION_ID = str(uuid.uuid4())
SECRET_KEY = "07XoX6Eu24amEuUye7MhTFO62jzaYJ48myn04DvECN0="  # From .env

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ZantaraTester")


def generate_token():
    """Generate a dev JWT token."""
    payload = {
        "sub": USER_EMAIL,
        "email": USER_EMAIL,
        "user_id": USER_ID,
        "role": "admin",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


async def send_message(
    client: httpx.AsyncClient, query: str, conversation_history: List[Dict] = None
) -> Dict[str, Any]:
    """Send a message to the Zantara Chat API."""
    token = generate_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "query": query,
        "session_id": SESSION_ID,
        "conversation_history": conversation_history or [],
        # "user_id" is extracted from token by backend, but passing it doesn't hurt if schema allows
    }

    try:
        logger.info(f"📤 Sending: '{query}'")
        # Increase timeout to 120s because RAG can be slow on first run
        response = await client.post(
            CHAT_ENDPOINT, json=payload, headers=headers, timeout=120.0
        )

        if response.status_code != 200:
            logger.error(f"❌ HTTP Error: {response.status_code} - {response.text}")
            return None

        data = response.json()
        logger.info(
            f"📥 Received ({response.elapsed.total_seconds():.2f}s): {data.get('answer', '')[:150]}..."
        )
        return data
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")
        return None


async def run_tests():
    """Execute the test suite."""
    logger.info(f"🚀 Starting Zantara Live Capabilities Test (Session: {SESSION_ID})")

    async with httpx.AsyncClient() as client:
        # Check Health
        try:
            health = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if health.status_code != 200:
                logger.critical("Backend not healthy. Aborting.")
                return
            logger.info("✅ Backend Health: OK")
        except Exception:
            logger.critical("Backend unreachable. Aborting.")
            return

        conversation_history = []

        # TEST 1: Identity & Fluidity
        logger.info("\n--- TEST 1: Identity & Fluidity ---")
        response1 = await send_message(
            client, "Ciao! Chi sei e qual è il tuo scopo?", conversation_history
        )
        if response1:
            # Note: The backend returns 'answer', frontend history expects 'role'/'content'
            conversation_history.append(
                {"role": "user", "content": "Ciao! Chi sei e qual è il tuo scopo?"}
            )
            conversation_history.append(
                {"role": "assistant", "content": response1.get("answer", "")}
            )

            answer = response1.get("answer", "").lower()
            if "zantara" in answer or "nuzantara" in answer:
                logger.info("✅ PASS: Identity Confirmed")
            else:
                logger.warning(f"⚠️ WARN: Identity unclear. Answer: {answer[:50]}...")

        # TEST 2: Tool Use (Team Knowledge)
        logger.info("\n--- TEST 2: Tool Use (Team Knowledge) ---")
        query2 = "Chi è il CEO di Nuzantara?"
        response2 = await send_message(client, query2, conversation_history)
        if response2:
            conversation_history.append({"role": "user", "content": query2})
            conversation_history.append(
                {"role": "assistant", "content": response2.get("answer", "")}
            )

            answer = response2.get("answer", "").lower()
            if "zainal" in answer:
                logger.info("✅ PASS: CEO Identified (Tool Use Likely)")
            else:
                logger.warning(
                    f"⚠️ WARN: Failed to identify CEO. Answer: {answer[:50]}..."
                )

        # TEST 3: Session Memory - Injection
        logger.info("\n--- TEST 3A: Session Memory Injection ---")
        query3 = (
            "Il mio nome in codice è 'Agente 007'. Ricordatelo per le prossime domande."
        )
        response3 = await send_message(client, query3, conversation_history)
        if response3:
            conversation_history.append({"role": "user", "content": query3})
            conversation_history.append(
                {"role": "assistant", "content": response3.get("answer", "")}
            )

        # TEST 4: Session Memory - Recall
        logger.info("\n--- TEST 3B: Session Memory Recall ---")
        query4 = "Qual è il mio nome in codice?"
        response4 = await send_message(client, query4, conversation_history)
        if response4:
            answer = response4.get("answer", "").lower()
            if "007" in answer:
                logger.info("✅ PASS: Memory Recall Successful")
            else:
                logger.warning(
                    f"❌ FAIL: Memory Recall Failed. Answer: {answer[:100]}..."
                )

        # TEST 5: RAG Capabilities
        logger.info("\n--- TEST 4: RAG Capabilities (KBLI) ---")
        query5 = "Spiegami cosa copre il KBLI 62019 con dettagli tecnici. Dammi una risposta breve."
        response5 = await send_message(client, query5, conversation_history)
        if response5:
            answer = response5.get("answer", "")
            if len(answer) > 20 and (
                "computer" in answer.lower() or "programma" in answer.lower()
            ):
                logger.info("✅ PASS: RAG Response Detailed")
            else:
                logger.warning(f"⚠️ WARN: RAG Response Weak. Answer: {answer[:100]}...")


if __name__ == "__main__":
    asyncio.run(run_tests())
