"""
Mata Garuda — arXiv harvesting tools via curl + XML parse.

Fetches papers from arXiv Atom API — no external dependencies.
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")

ARXIV_API = "http://export.arxiv.org/api/query"


@register_tool(name="fetch_arxiv_papers")
def fetch_arxiv_papers(
    categories: str = "cs.AI,cs.CL,cs.LG",
    max_results: int = 20,
    context_variables: dict | None = None,
) -> str:
    """Fetch latest papers from arXiv for given categories.

    Args:
        categories: Comma-separated arXiv categories
        max_results: Maximum papers to fetch
    """
    cats = "+OR+".join(f"cat:{c.strip()}" for c in categories.split(","))
    url = f"{ARXIV_API}?search_query={cats}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

    try:
        result = subprocess.run(
            ["curl", "-sL", url, "--connect-timeout", "15"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return f"[ERROR] curl failed: {result.stderr[:200]}"

        xml = result.stdout
        papers = _parse_arxiv_atom(xml)

        if not papers:
            return "[WARNING] No papers found in arXiv response"

        lines = [f"Found {len(papers)} papers:"]
        for i, p in enumerate(papers, 1):
            lines.append(
                f"  {i}. {p['title'][:80]}\n"
                f"     Authors: {p['authors'][:60]}\n"
                f"     URL: {p['url']}\n"
                f"     Abstract: {p['abstract'][:150]}..."
            )
        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "[ERROR] arXiv API timeout"
    except Exception as e:
        return f"[ERROR] arXiv fetch failed: {e}"


def _parse_arxiv_atom(xml: str) -> list[dict]:
    """Parse arXiv Atom XML into list of paper dicts. Regex-based, no lxml."""
    papers = []
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)

    for entry in entries:
        title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        abstract_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        id_m = re.search(r"<id>(.*?)</id>", entry)
        authors = re.findall(r"<name>(.*?)</name>", entry)
        published_m = re.search(r"<published>(.*?)</published>", entry)
        categories = re.findall(r'category term="([^"]+)"', entry)

        if title_m and id_m:
            title = re.sub(r"\s+", " ", title_m.group(1)).strip()
            abstract = re.sub(r"\s+", " ", abstract_m.group(1)).strip() if abstract_m else ""
            url = id_m.group(1).strip()

            papers.append({
                "title": title,
                "abstract": abstract,
                "url": url,
                "authors": ", ".join(authors[:5]),
                "published": published_m.group(1) if published_m else "",
                "categories": ",".join(categories),
                "source": "arxiv",
            })

    return papers
