#!/usr/bin/env python3
"""
Manual Test Script for Feedback P1 Endpoints
Tests the new /api/v2/feedback endpoint with curl-like requests
"""

import asyncio
import json
import os
from uuid import uuid4

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_URL", "http://localhost:8080")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")


async def test_feedback_endpoint():
    """Test POST /api/v2/feedback endpoint"""
    headers = {
        "Content-Type": "application/json",
    }
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 70)
        print("TESTING FEEDBACK P1 ENDPOINTS")
        print("=" * 70)

        # Test 1: Positive rating (5) - should NOT create review_queue
        print("\n1. Testing positive rating (5) - should NOT create review_queue")
        session_id = str(uuid4())
        response = await client.post(
            f"{BASE_URL}/api/v2/feedback",
            headers=headers,
            json={
                "session_id": session_id,
                "rating": 5,
                "feedback_type": "positive",
                "feedback_text": "Great conversation!",
            },
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Review Queue ID: {data.get('review_queue_id')}")
            assert data.get("review_queue_id") is None, "Should NOT create review_queue for rating 5"
            print("   ✅ PASS: No review_queue created")
        else:
            print(f"   Response: {response.text}")

        # Test 2: Low rating (2) - should create review_queue
        print("\n2. Testing low rating (2) - should create review_queue")
        session_id = str(uuid4())
        response = await client.post(
            f"{BASE_URL}/api/v2/feedback",
            headers=headers,
            json={
                "session_id": session_id,
                "rating": 2,
                "feedback_type": "negative",
                "feedback_text": "Had some issues",
            },
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Review Queue ID: {data.get('review_queue_id')}")
            assert data.get("review_queue_id") is not None, "Should create review_queue for rating 2"
            print("   ✅ PASS: Review_queue created")
        else:
            print(f"   Response: {response.text}")

        # Test 3: Rating 1 - should create review_queue with urgent priority
        print("\n3. Testing rating 1 - should create review_queue")
        session_id = str(uuid4())
        response = await client.post(
            f"{BASE_URL}/api/v2/feedback",
            headers=headers,
            json={
                "session_id": session_id,
                "rating": 1,
                "feedback_type": "issue",
                "feedback_text": "Found a bug",
            },
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Review Queue ID: {data.get('review_queue_id')}")
            assert data.get("review_queue_id") is not None, "Should create review_queue for rating 1"
            print("   ✅ PASS: Review_queue created")
        else:
            print(f"   Response: {response.text}")

        # Test 4: High rating with correction_text - should create review_queue
        print("\n4. Testing high rating (4) with correction_text - should create review_queue")
        session_id = str(uuid4())
        response = await client.post(
            f"{BASE_URL}/api/v2/feedback",
            headers=headers,
            json={
                "session_id": session_id,
                "rating": 4,
                "feedback_type": "positive",
                "feedback_text": "Good but...",
                "correction_text": "The correct answer should be X",
            },
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Review Queue ID: {data.get('review_queue_id')}")
            assert data.get("review_queue_id") is not None, "Should create review_queue when correction_text present"
            print("   ✅ PASS: Review_queue created due to correction_text")
        else:
            print(f"   Response: {response.text}")

        # Test 5: Get rating
        print("\n5. Testing GET /api/v2/feedback/ratings/{session_id}")
        response = await client.get(
            f"{BASE_URL}/api/v2/feedback/ratings/{session_id}",
            headers=headers,
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Rating: {data.get('rating')}")
            print(f"   Feedback Type: {data.get('feedback_type')}")
            print("   ✅ PASS: Rating retrieved")
        else:
            print(f"   Response: {response.text}")

        # Test 6: Get stats
        print("\n6. Testing GET /api/v2/feedback/stats")
        response = await client.get(
            f"{BASE_URL}/api/v2/feedback/stats",
            headers=headers,
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total Pending: {data.get('total_pending')}")
            print(f"   Total Resolved: {data.get('total_resolved')}")
            print(f"   Low Ratings Count: {data.get('low_ratings_count')}")
            print("   ✅ PASS: Stats retrieved")
        else:
            print(f"   Response: {response.text}")

        print("\n" + "=" * 70)
        print("TESTS COMPLETED")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_feedback_endpoint())


