"""AI Intel Sensor — perceives the AI research landscape.

Composite sensor: harvests arXiv, RSS newsletters, GitHub trending, YouTube.
Has a 24h cooldown — only fetches once per day. Between fetches, returns
green with no data (the organism is aware the world hasn't changed).

This is the Sentinel's eye — one of CELL's sensory organs.
The harvested data flows through the same pulse as health/db/qdrant readings.
The reasoner and cortex process it alongside infrastructure signals.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

logger = logging.getLogger("cell.sensors.ai_intel")

# Cooldown: harvest at most once per day
_COOLDOWN_SECONDS = 86400  # 24 hours
_LAST_HARVEST_FILE = Path(__file__).parent.parent.parent / "data" / ".ai_intel_last_harvest"

# ─── RSS feeds (verified 2026-04-10) ───
AI_RSS_FEEDS = [
    "https://jack-clark.net/feed/",
    "https://huggingface.co/blog/feed.xml",
    "https://www.technologyreview.com/feed/",
    "https://magazine.sebastianraschka.com/feed",
    "https://thegradient.pub/rss/",
]

# ─── YouTube channels ───
AI_YOUTUBE_CHANNELS = [
    "AndrejKarpathy",
    "TwoMinutePapers",
    "YannicKilcher",
    "AIExplainedYT",
    "Fireship",
    "3blue1brown",
]

# ─── arXiv categories ───
ARXIV_CATEGORIES = "cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.IR"


@dataclass
class AIIntelReading:
    """Structured reading from all AI intel sources."""
    timestamp: datetime
    status: str  # green/yellow/red
    harvested: bool  # True if fresh harvest happened this pulse
    items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def reachable(self) -> bool:
        return self.status != "red"


class AIIntelSensor:
    """Composite sensor: arXiv + RSS + GitHub + YouTube.

    Only harvests once per 24h. Returns cached count between harvests.
    """

    def __init__(
        self,
        arxiv_max: int = 15,
        rss_max_per_feed: int = 5,
        github_max: int = 10,
        youtube_channels: int = 3,
        youtube_videos_per: int = 2,
    ) -> None:
        self._arxiv_max = arxiv_max
        self._rss_max = rss_max_per_feed
        self._github_max = github_max
        self._yt_channels = youtube_channels
        self._yt_videos = youtube_videos_per

    def _should_harvest(self) -> bool:
        """Check if enough time has passed since last harvest."""
        _LAST_HARVEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not _LAST_HARVEST_FILE.exists():
            return True
        try:
            last_ts = float(_LAST_HARVEST_FILE.read_text().strip())
            return (time.time() - last_ts) > _COOLDOWN_SECONDS
        except (ValueError, OSError):
            return True

    def _mark_harvested(self) -> None:
        """Record that we just harvested."""
        _LAST_HARVEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_HARVEST_FILE.write_text(str(time.time()))

    async def read(self) -> AIIntelReading:
        """Read the AI research landscape. Harvests at most once per day."""
        now = datetime.now(timezone.utc)

        if not self._should_harvest():
            return AIIntelReading(
                timestamp=now,
                status="green",
                harvested=False,
                metadata={"reason": "cooldown_active", "next_harvest_in": "check .ai_intel_last_harvest"},
            )

        # Full harvest
        items: list[dict[str, Any]] = []
        counts: dict[str, int] = {"arxiv": 0, "rss": 0, "github": 0, "youtube": 0, "errors": 0}

        # ArXiv
        try:
            arxiv_items = self._fetch_arxiv()
            items.extend(arxiv_items)
            counts["arxiv"] = len(arxiv_items)
        except Exception as e:
            counts["errors"] += 1
            logger.warning(f"ArXiv harvest failed: {e}")

        # RSS
        for feed_url in AI_RSS_FEEDS:
            try:
                rss_items = self._fetch_rss(feed_url)
                items.extend(rss_items)
                counts["rss"] += len(rss_items)
            except Exception:
                counts["errors"] += 1

        # GitHub
        try:
            gh_items = self._fetch_github()
            items.extend(gh_items)
            counts["github"] = len(gh_items)
        except Exception as e:
            counts["errors"] += 1
            logger.warning(f"GitHub harvest failed: {e}")

        # YouTube
        for channel in AI_YOUTUBE_CHANNELS[:self._yt_channels]:
            try:
                yt_items = self._fetch_youtube(channel)
                items.extend(yt_items)
                counts["youtube"] += len(yt_items)
            except Exception:
                counts["errors"] += 1

        total = sum(v for k, v in counts.items() if k != "errors")
        self._mark_harvested()

        status = "green" if total > 0 else ("yellow" if counts["errors"] < 4 else "red")

        logger.info(f"AI Intel harvest: {total} items ({counts})")

        return AIIntelReading(
            timestamp=now,
            status=status,
            harvested=True,
            items=items,
            metadata={"counts": counts, "total": total},
        )

    # ─── Individual source fetchers ───

    def _fetch_arxiv(self) -> list[dict[str, Any]]:
        import re
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query=cat:{ARXIV_CATEGORIES}"
            f"&sortBy=submittedDate&sortOrder=descending"
            f"&max_results={self._arxiv_max}"
        )
        r = subprocess.run(
            ["curl", "-sL", url, "--connect-timeout", "15"],
            capture_output=True, text=True, timeout=25,
        )
        items = []
        for entry in re.findall(r"<entry>(.*?)</entry>", r.stdout, re.DOTALL):
            title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            abstract_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            id_m = re.search(r"<id>(.*?)</id>", entry)
            authors = re.findall(r"<name>(.*?)</name>", entry)
            if title_m and id_m:
                items.append({
                    "title": re.sub(r"\s+", " ", title_m.group(1)).strip(),
                    "url": id_m.group(1).strip(),
                    "content": re.sub(r"\s+", " ", abstract_m.group(1)).strip()[:500] if abstract_m else "",
                    "authors": ", ".join(authors[:5]),
                    "source": "arxiv",
                })
        return items

    def _fetch_rss(self, feed_url: str) -> list[dict[str, Any]]:
        import re
        r = subprocess.run(
            ["curl", "-sL", feed_url, "--connect-timeout", "10"],
            capture_output=True, text=True, timeout=15,
        )
        items = []
        # RSS <item>
        for entry in re.findall(r"<item>(.*?)</item>", r.stdout, re.DOTALL):
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", entry, re.DOTALL)
            link_m = re.search(r"<link>(.*?)</link>", entry)
            if title_m:
                items.append({
                    "title": re.sub(r"\s+", " ", title_m.group(1)).strip(),
                    "url": link_m.group(1).strip() if link_m else "",
                    "content": "",
                    "source": "rss",
                })
        # Atom <entry>
        if not items:
            for entry in re.findall(r"<entry>(.*?)</entry>", r.stdout, re.DOTALL):
                title_m = re.search(r"<title[^>]*>(.*?)</title>", entry, re.DOTALL)
                link_m = re.search(r'<link[^>]*href="([^"]+)"', entry)
                if title_m:
                    items.append({
                        "title": re.sub(r"\s+", " ", title_m.group(1)).strip(),
                        "url": link_m.group(1).strip() if link_m else "",
                        "content": "",
                        "source": "rss",
                    })
        return items[:self._rss_max]

    def _fetch_github(self) -> list[dict[str, Any]]:
        since = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        query = f"topic:machine-learning pushed:>={since} stars:>100"
        url = f"https://api.github.com/search/repositories?q={quote(query)}&sort=stars&order=desc&per_page={self._github_max}"
        r = subprocess.run(
            ["curl", "-sL", url, "-H", "Accept: application/vnd.github.v3+json", "--connect-timeout", "10"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(r.stdout) if r.stdout else {}
        items = []
        for repo in data.get("items", []):
            items.append({
                "title": repo["full_name"],
                "url": repo["html_url"],
                "content": repo.get("description", "")[:200],
                "stars": repo["stargazers_count"],
                "source": "github",
            })
        return items

    def _fetch_youtube(self, channel: str) -> list[dict[str, Any]]:
        r = subprocess.run(
            [
                "yt-dlp", "--flat-playlist",
                "--playlist-end", str(self._yt_videos),
                "--dump-json",
                f"https://www.youtube.com/@{channel}/videos",
            ],
            capture_output=True, text=True, timeout=60,
        )
        items = []
        for line in r.stdout.strip().split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    items.append({
                        "title": data.get("title", ""),
                        "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                        "content": "",
                        "channel": channel,
                        "views": data.get("view_count", 0),
                        "source": "youtube",
                    })
                except json.JSONDecodeError:
                    pass
        return items
