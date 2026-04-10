"""ArXiv Sensor — perceives the latest AI/ML research papers."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from cell_core.types import SensorReading

from mata_garuda.tools.arxiv_tools import _parse_arxiv_atom


class ArXivSensor:
    """Fetches latest papers from arXiv Atom API."""

    name = "arxiv"

    def __init__(self, categories: str = "cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.IR", max_results: int = 15):
        self._categories = categories
        self._max_results = max_results

    async def read(self, **context) -> SensorReading:
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query=cat:{self._categories}"
            f"&sortBy=submittedDate&sortOrder=descending"
            f"&max_results={self._max_results}"
        )
        try:
            result = subprocess.run(
                ["curl", "-sL", url, "--connect-timeout", "15"],
                capture_output=True, text=True, timeout=25,
            )
            papers = _parse_arxiv_atom(result.stdout)
            return SensorReading(
                sensor_name=self.name,
                status="green" if papers else "yellow",
                value=papers,
                metadata={"count": len(papers), "source": "arxiv_api"},
            )
        except Exception as e:
            return SensorReading(
                sensor_name=self.name,
                status="red",
                metadata={"error": str(e)},
            )
