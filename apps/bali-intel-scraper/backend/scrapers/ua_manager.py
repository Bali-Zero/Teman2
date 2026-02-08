"""
User-Agent rotation for web scraping.

Provides realistic browser user agents to avoid detection.
"""

import random
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__, component="ua_manager")


@dataclass
class UserAgent:
    """User agent with metadata."""

    string: str
    browser: str
    os: str
    device: str
    usage_count: int = 0
    last_used: Optional[datetime] = None


class UserAgentManager:
    """Manages User-Agent rotation."""

    # Realistic user agents
    DEFAULT_UAS = [
        # Chrome on Windows
        UserAgent(
            string="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            browser="Chrome",
            os="Windows 10",
            device="Desktop",
        ),
        # Chrome on macOS
        UserAgent(
            string="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            browser="Chrome",
            os="macOS",
            device="Desktop",
        ),
        # Firefox on Windows
        UserAgent(
            string="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            browser="Firefox",
            os="Windows 10",
            device="Desktop",
        ),
        # Firefox on macOS
        UserAgent(
            string="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            browser="Firefox",
            os="macOS",
            device="Desktop",
        ),
        # Safari on macOS
        UserAgent(
            string="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            browser="Safari",
            os="macOS",
            device="Desktop",
        ),
        # Edge on Windows
        UserAgent(
            string="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            browser="Edge",
            os="Windows 10",
            device="Desktop",
        ),
        # Chrome on Linux
        UserAgent(
            string="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            browser="Chrome",
            os="Linux",
            device="Desktop",
        ),
        # Chrome on Android
        UserAgent(
            string="Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            browser="Chrome",
            os="Android",
            device="Mobile",
        ),
        # Safari on iPhone
        UserAgent(
            string="Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            browser="Safari",
            os="iOS",
            device="Mobile",
        ),
        # Safari on iPad
        UserAgent(
            string="Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            browser="Safari",
            os="iOS",
            device="Tablet",
        ),
    ]

    def __init__(self, user_agents: Optional[List[UserAgent]] = None):
        self._user_agents = user_agents or self.DEFAULT_UAS.copy()
        self._current_index = 0

    def add_user_agent(
        self,
        string: str,
        browser: str = "Unknown",
        os: str = "Unknown",
        device: str = "Desktop",
    ) -> UserAgent:
        """Add a custom user agent."""
        ua = UserAgent(string=string, browser=browser, os=os, device=device)
        self._user_agents.append(ua)
        return ua

    def get_random(self) -> str:
        """Get a random user agent."""
        ua = random.choice(self._user_agents)
        ua.usage_count += 1
        ua.last_used = datetime.now()
        return ua.string

    def get_by_browser(self, browser: str) -> Optional[str]:
        """Get a user agent for specific browser."""
        matching = [
            ua for ua in self._user_agents if ua.browser.lower() == browser.lower()
        ]
        if matching:
            ua = random.choice(matching)
            ua.usage_count += 1
            ua.last_used = datetime.now()
            return ua.string
        return None

    def get_by_device(self, device: str) -> Optional[str]:
        """Get a user agent for specific device type."""
        matching = [
            ua for ua in self._user_agents if ua.device.lower() == device.lower()
        ]
        if matching:
            ua = random.choice(matching)
            ua.usage_count += 1
            ua.last_used = datetime.now()
            return ua.string
        return None

    def get_round_robin(self) -> str:
        """Get user agent using round-robin."""
        ua = self._user_agents[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._user_agents)
        ua.usage_count += 1
        ua.last_used = datetime.now()
        return ua.string

    def get_least_used(self) -> str:
        """Get the least recently used user agent."""
        ua = min(self._user_agents, key=lambda x: x.usage_count)
        ua.usage_count += 1
        ua.last_used = datetime.now()
        return ua.string

    def get_stats(self) -> Dict:
        """Get usage statistics."""
        return {
            "total": len(self._user_agents),
            "by_browser": self._count_by("browser"),
            "by_os": self._count_by("os"),
            "by_device": self._count_by("device"),
            "most_used": max(self._user_agents, key=lambda x: x.usage_count).string
            if self._user_agents
            else None,
        }

    def _count_by(self, field: str) -> Dict[str, int]:
        """Count user agents by field."""
        counts = {}
        for ua in self._user_agents:
            key = getattr(ua, field)
            counts[key] = counts.get(key, 0) + 1
        return counts


# Global instance
ua_manager = UserAgentManager()


def get_ua(strategy: str = "random") -> str:
    """Get a user agent with specified strategy."""
    if strategy == "random":
        return ua_manager.get_random()
    elif strategy == "round_robin":
        return ua_manager.get_round_robin()
    elif strategy == "least_used":
        return ua_manager.get_least_used()
    else:
        return ua_manager.get_random()


__all__ = [
    "UserAgentManager",
    "UserAgent",
    "ua_manager",
    "get_ua",
]
