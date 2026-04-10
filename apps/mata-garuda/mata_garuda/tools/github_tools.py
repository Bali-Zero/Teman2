"""
Mata Garuda — GitHub trending repos via API + curl.

Fetches trending AI/ML repos. No auth needed for search API (60 req/h).
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")

GITHUB_API = "https://api.github.com/search/repositories"


@register_tool(name="fetch_github_trending")
def fetch_github_trending(
    topics: str = "machine-learning,artificial-intelligence,llm,rag",
    days: int = 1,
    max_results: int = 10,
    context_variables: dict | None = None,
) -> str:
    """Fetch trending GitHub repos in AI/ML topics.

    Args:
        topics: Comma-separated GitHub topics to search
        days: Look back N days for new/updated repos
        max_results: Maximum repos to return
    """
    from urllib.parse import quote

    since = (datetime.now() - timedelta(days=max(days, 3))).strftime("%Y-%m-%d")
    # Use first topic as primary search term — OR with parentheses breaks GitHub API
    primary_topic = topics.split(",")[0].strip()
    query = f"topic:{primary_topic} pushed:>={since} stars:>100"

    url = f"{GITHUB_API}?q={quote(query)}&sort=stars&order=desc&per_page={max_results}"

    try:
        result = subprocess.run(
            [
                "curl", "-sL", url,
                "-H", "Accept: application/vnd.github.v3+json",
                "--connect-timeout", "10",
            ],
            capture_output=True, text=True, timeout=15,
        )

        if result.returncode != 0:
            return f"[ERROR] GitHub API failed: {result.stderr[:200]}"

        data = json.loads(result.stdout)
        items = data.get("items", [])

        if not items:
            return f"[WARNING] No trending repos found for topics: {topics}"

        lines = [f"Found {len(items)} trending AI repos (last {days}d):"]
        for i, repo in enumerate(items, 1):
            lines.append(
                f"  {i}. {repo['full_name']} ★{repo['stargazers_count']}\n"
                f"     {repo.get('description', 'No description')[:100]}\n"
                f"     URL: {repo['html_url']}\n"
                f"     Language: {repo.get('language', 'N/A')} | "
                f"Forks: {repo.get('forks_count', 0)}"
            )
        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "[ERROR] GitHub API timeout"
    except json.JSONDecodeError:
        return "[ERROR] Invalid JSON from GitHub API"
    except Exception as e:
        return f"[ERROR] GitHub fetch failed: {e}"
