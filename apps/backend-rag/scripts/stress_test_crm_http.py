import asyncio
import logging
import os
import random
import sys
import time
import uuid

import httpx

# Configuration
BASE_URL = os.getenv("API_URL", "http://localhost:8080")
API_KEY = os.getenv("ADMIN_API_KEY", "super-secret-key")  # Replace with actual if known or passed
CONCURRENT_REQUESTS = 5
TOTAL_CLIENTS = 50
CASES_PER_CLIENT = 2

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("crm_stress_test")


def random_string(length=8):
    return uuid.uuid4().hex[:length]


def generate_client_data():
    uid = random_string()
    return {
        "full_name": f"Test Client {uid}",
        "email": f"test.client.{uid}@example.com",
        "phone": f"+62812{random.randint(10000000, 99999999)}",
        "nationality": random.choice(["Italian", "Australian", "French", "American"]),
        "status": "lead",
        "client_type": "individual",
    }


def generate_practice_data(client_id):
    types = ["kitas_application", "pt_pma_setup", "visa_extension", "tax_consulting"]
    return {
        "client_id": client_id,
        "practice_type_code": random.choice(types),
        "status": "inquiry",
        "notes": f"Stress test case {random_string()}",
    }


async def create_client(client, headers):
    start = time.time()
    data = generate_client_data()
    try:
        # Note: created_by param required by CRM API
        response = await client.post(
            f"{BASE_URL}/api/crm/clients?created_by=stress_test", json=data, headers=headers
        )
        duration = time.time() - start
        if response.status_code in [200, 201]:
            return {"success": True, "data": response.json(), "duration": duration}
        else:
            logger.error(f"Failed to create client: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text, "duration": duration}
    except Exception as e:
        logger.error(f"Exception creating client: {e}")
        return {"success": False, "error": str(e), "duration": 0}


async def create_practice(client, client_id, headers):
    start = time.time()
    data = generate_practice_data(client_id)
    try:
        response = await client.post(
            f"{BASE_URL}/api/crm/practices/?created_by=stress_test", json=data, headers=headers
        )
        duration = time.time() - start
        if response.status_code in [200, 201]:
            return {"success": True, "data": response.json(), "duration": duration}
        else:
            logger.error(f"Failed to create practice: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text, "duration": duration}
    except Exception as e:
        logger.error(f"Exception creating practice: {e}")
        return {"success": False, "error": str(e), "duration": 0}


async def worker(queue, client, headers, results):
    while not queue.empty():
        task_type, payload = await queue.get()

        if task_type == "client":
            res = await create_client(client, headers)
            if res["success"]:
                client_id = res["data"]["id"]
                results["clients_created"] += 1
                results["latencies"].append(res["duration"])

                # Queue cases for this client
                for _ in range(CASES_PER_CLIENT):
                    await queue.put(("case", client_id))
            else:
                results["clients_failed"] += 1

        elif task_type == "case":
            client_id = payload
            res = await create_practice(client, client_id, headers)
            if res["success"]:
                results["cases_created"] += 1
                results["latencies"].append(res["duration"])
            else:
                results["cases_failed"] += 1

        queue.task_done()


async def main():
    logger.info(f"🚀 Starting CRM Stress Test against {BASE_URL}")
    logger.info(f"Target: {TOTAL_CLIENTS} clients, {TOTAL_CLIENTS * CASES_PER_CLIENT} cases")

    # Headers - Try to use X-API-Key if backend supports it (HybridAuthMiddleware)
    # Or simulate a logged in user via Cookie if we could (harder)
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

    queue = asyncio.Queue()
    results = {
        "clients_created": 0,
        "clients_failed": 0,
        "cases_created": 0,
        "cases_failed": 0,
        "latencies": [],
    }

    # Enqueue client creation tasks
    for _ in range(TOTAL_CLIENTS):
        queue.put_nowait(("client", None))

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check health first
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                logger.warning(f"⚠️ Health check failed: {resp.status_code}")
            else:
                logger.info("✅ Health check passed")
        except Exception as e:
            logger.critical(f"❌ Cannot connect to backend: {e}")
            logger.info("Make sure the backend is running (docker compose up or fly proxy)")
            return

        workers = [
            asyncio.create_task(worker(queue, client, headers, results))
            for _ in range(CONCURRENT_REQUESTS)
        ]

        start_time = time.time()
        await queue.join()
        total_time = time.time() - start_time

        for w in workers:
            w.cancel()

    # Report
    logger.info("=" * 50)
    logger.info("🏁 STRESS TEST COMPLETE")
    logger.info(f"⏱️ Total Time: {total_time:.2f}s")
    logger.info(
        f"👥 Clients: {results['clients_created']} created, {results['clients_failed']} failed"
    )
    logger.info(f"📁 Cases: {results['cases_created']} created, {results['cases_failed']} failed")

    if results["latencies"]:
        avg_latency = sum(results["latencies"]) / len(results["latencies"])
        max_latency = max(results["latencies"])
        logger.info(f"⚡ Avg Latency: {avg_latency * 1000:.2f}ms")
        logger.info(f"🐢 Max Latency: {max_latency * 1000:.2f}ms")

    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
