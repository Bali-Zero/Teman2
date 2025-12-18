"""
Locust Load Test Configuration
Smoke load tests for critical endpoints.

Scenarios:
- /health (throughput)
- /api/search/ (p95)
- /api/oracle/query (p95 + error rate)
- /api/agentic-rag/stream (SSE concurrency)
- /api/auth/login (rate, fail cases)

Usage:
    locust -f tests/load/locustfile.py --host=https://nuzantara-rag.fly.dev
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 2
"""

import os
import random
from datetime import datetime, timedelta, timezone

from jose import jwt
from locust import HttpUser, TaskSet, between, task


def generate_test_token():
    """Generate test JWT token"""
    payload = {
        "sub": "loadtest@example.com",
        "email": "loadtest@example.com",
        "role": "user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


class HealthCheckTasks(TaskSet):
    """Health endpoint load tests"""

    @task(10)
    def health_basic(self):
        """Test basic health endpoint"""
        self.client.get("/health", name="health_basic")

    @task(5)
    def health_ready(self):
        """Test readiness endpoint"""
        self.client.get("/health/ready", name="health_ready")

    @task(2)
    def health_detailed(self):
        """Test detailed health endpoint"""
        self.client.get("/health/detailed", name="health_detailed")


class SearchTasks(TaskSet):
    """Search endpoint load tests"""

    def on_start(self):
        """Setup: generate auth token"""
        self.token = generate_test_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(10)
    def search_basic(self):
        """Test basic search"""
        queries = ["KITAS", "visa", "residence permit", "immigration", "Bali"]
        query = random.choice(queries)
        self.client.get(
            f"/api/search/?query={query}&limit=5",
            headers=self.headers,
            name="search_basic",
        )

    @task(5)
    def search_with_tier(self):
        """Test search with tier filter"""
        self.client.get(
            "/api/search/?query=visa&tier=A&limit=10",
            headers=self.headers,
            name="search_with_tier",
        )

    @task(2)
    def search_with_limit(self):
        """Test search with custom limit"""
        self.client.get(
            "/api/search/?query=test&limit=20",
            headers=self.headers,
            name="search_with_limit",
        )


class OracleTasks(TaskSet):
    """Oracle endpoint load tests"""

    def on_start(self):
        """Setup: generate auth token"""
        self.token = generate_test_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def oracle_query(self):
        """Test Oracle query endpoint"""
        queries = [
            "What is KITAS?",
            "How to get a residence permit?",
            "What documents are needed for visa?",
        ]
        query = random.choice(queries)
        self.client.post(
            "/api/oracle/query",
            json={"query": query, "user_id": "loadtest@example.com"},
            headers=self.headers,
            name="oracle_query",
        )


class AgenticRAGTasks(TaskSet):
    """Agentic RAG SSE endpoint load tests"""

    def on_start(self):
        """Setup: generate auth token"""
        self.token = generate_test_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def agentic_rag_stream(self):
        """Test Agentic RAG streaming"""
        queries = [
            "Explain KITAS process",
            "What are visa requirements?",
            "How to apply for residence permit?",
        ]
        query = random.choice(queries)
        with self.client.post(
            "/api/agentic-rag/stream",
            json={"query": query, "user_id": "loadtest@example.com"},
            headers=self.headers,
            stream=True,
            name="agentic_rag_stream",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                # Read first few chunks to verify streaming works
                chunks_read = 0
                for chunk in response.iter_lines():
                    if chunk:
                        chunks_read += 1
                        if chunks_read >= 5:  # Read at least 5 chunks
                            break
                if chunks_read > 0:
                    response.success()
                else:
                    response.failure("No chunks received")
            else:
                response.failure(f"Status {response.status_code}")


class AuthTasks(TaskSet):
    """Auth endpoint load tests"""

    @task(5)
    def login_success(self):
        """Test successful login (if test user exists)"""
        self.client.post(
            "/api/auth/login",
            json={"email": "loadtest@example.com", "pin": "123456"},
            name="login_success",
        )

    @task(10)
    def login_fail(self):
        """Test failed login (wrong credentials)"""
        self.client.post(
            "/api/auth/login",
            json={"email": f"test{random.randint(1000, 9999)}@example.com", "pin": "wrong"},
            name="login_fail",
        )


class HealthUser(HttpUser):
    """User class for health endpoint load tests"""

    tasks = [HealthCheckTasks]
    wait_time = between(1, 3)
    weight = 3  # 30% of users


class SearchUser(HttpUser):
    """User class for search endpoint load tests"""

    tasks = [SearchTasks]
    wait_time = between(2, 5)
    weight = 3  # 30% of users


class OracleUser(HttpUser):
    """User class for Oracle endpoint load tests"""

    tasks = [OracleTasks]
    wait_time = between(5, 10)
    weight = 2  # 20% of users


class AgenticRAGUser(HttpUser):
    """User class for Agentic RAG endpoint load tests"""

    tasks = [AgenticRAGTasks]
    wait_time = between(10, 20)
    weight = 1  # 10% of users


class AuthUser(HttpUser):
    """User class for auth endpoint load tests"""

    tasks = [AuthTasks]
    wait_time = between(1, 3)
    weight = 1  # 10% of users
