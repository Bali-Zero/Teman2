"""
Load testing with Locust.

Run with: locust -f tests/load/locustfile.py
"""

from locust import HttpUser, task, between
import random


class ScraperUser(HttpUser):
    """Simulate scraper API load."""

    wait_time = between(1, 5)

    @task(3)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health/live")

    @task(2)
    def get_articles(self):
        """Test articles listing."""
        self.client.get("/articles?limit=20")

    @task(1)
    def scrape_url(self):
        """Test scrape endpoint."""
        urls = [
            "https://example.com/news/1",
            "https://example.com/news/2",
            "https://example.com/news/3",
        ]

        self.client.post(
            "/scrape", json={"url": random.choice(urls), "use_browser": False}
        )


class ReadOnlyUser(HttpUser):
    """Simulate read-only API usage."""

    wait_time = between(0.5, 2)

    @task(5)
    def list_sources(self):
        """Test sources listing."""
        self.client.get("/sources")

    @task(3)
    def get_stats(self):
        """Test stats endpoint."""
        self.client.get("/stats")

    @task(2)
    def search_articles(self):
        """Test search functionality."""
        queries = ["bali", "tourism", "politics", "economy"]
        self.client.get(f"/search?q={random.choice(queries)}")
