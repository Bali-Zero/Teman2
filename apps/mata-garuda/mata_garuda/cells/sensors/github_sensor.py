"""GitHub Sensor — perceives trending AI/ML repositories."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from urllib.parse import quote

from cell_core.types import SensorReading


class GitHubSensor:
    """Fetches trending repos via GitHub Search API."""

    name = "github"

    def __init__(self, topic: str = "machine-learning", days: int = 3, max_results: int = 10):
        self._topic = topic
        self._days = days
        self._max_results = max_results

    async def read(self, **context) -> SensorReading:
        since = (datetime.now() - timedelta(days=max(self._days, 3))).strftime("%Y-%m-%d")
        query = f"topic:{self._topic} pushed:>={since} stars:>100"
        url = f"https://api.github.com/search/repositories?q={quote(query)}&sort=stars&order=desc&per_page={self._max_results}"

        try:
            result = subprocess.run(
                ["curl", "-sL", url, "-H", "Accept: application/vnd.github.v3+json", "--connect-timeout", "10"],
                capture_output=True, text=True, timeout=15,
            )
            data = json.loads(result.stdout) if result.stdout else {}
            items = data.get("items", [])

            repos = []
            for repo in items:
                repos.append({
                    "title": repo["full_name"],
                    "url": repo["html_url"],
                    "description": repo.get("description", "")[:200],
                    "stars": repo["stargazers_count"],
                    "language": repo.get("language", ""),
                    "source": "github",
                })

            return SensorReading(
                sensor_name=self.name,
                status="green" if repos else "yellow",
                value=repos,
                metadata={"count": len(repos), "total": data.get("total_count", 0)},
            )
        except Exception as e:
            return SensorReading(
                sensor_name=self.name, status="red",
                metadata={"error": str(e)},
            )
