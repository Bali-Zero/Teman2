"""
Session Fact Extractor

Lightweight, dependency-free helper to extract "session facts" from the raw
conversation history (before trimming/summarization).

This module is intentionally simple and safe:
- No external services
- No database
- Best-effort heuristics only
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SessionFacts:
    """Structured representation of extracted session facts."""

    facts: list[str]

    def to_prompt_block(self) -> str:
        """
        Render facts into a prompt-friendly block.

        Returns empty string when no facts were extracted.
        """
        if not self.facts:
            return ""
        bullets = "\n".join(f"- {fact}" for fact in self.facts)
        return f"### KEY FACTS (THIS SESSION)\n{bullets}\n\n"


class SessionFactExtractor:
    """
    Extract key facts from a conversation history.

    This is a heuristic extractor designed to be:
    - Fast (O(n))
    - Robust to malformed history entries
    - Conservative (avoid hallucinating facts)
    """

    _KEY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\b(company|azienda|societ[aà])\s*[:=]\s*(.+)$", re.I), "Company: {v}"),
        (re.compile(r"\b(budget|budgetto|budget)\s*[:=]\s*(.+)$", re.I), "Budget: {v}"),
        (
            re.compile(r"\b(location|locazione|based in|sono a)\s*[:=]?\s*(.+)$", re.I),
            "Location: {v}",
        ),
        (re.compile(r"\b(nationality|nazionalit[aà])\s*[:=]\s*(.+)$", re.I), "Nationality: {v}"),
        (re.compile(r"\b(passport)\s*[:=]\s*(.+)$", re.I), "Passport: {v}"),
        (re.compile(r"\b(deadline|scadenza|timeline)\s*[:=]\s*(.+)$", re.I), "Deadline: {v}"),
    )

    def __init__(self, max_facts: int = 8, max_value_len: int = 80) -> None:
        self.max_facts = max_facts
        self.max_value_len = max_value_len

    def extract_from_history(self, history: list[dict[str, Any]]) -> SessionFacts:
        """
        Extract facts from message history.

        Args:
            history: List of messages (dicts with keys like role/content).

        Returns:
            SessionFacts: extracted facts (may be empty).
        """
        if not isinstance(history, list) or not history:
            return SessionFacts(facts=[])

        facts: list[str] = []
        seen: set[str] = set()

        # Scan recent user messages first (reverse chronological)
        for msg in reversed(history):
            if len(facts) >= self.max_facts:
                break
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "")).lower()
            if role not in {"user", "human"}:
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            text = content.strip()
            if not text:
                continue

            # Normalize multi-line inputs: check each line independently
            for line in (ln.strip() for ln in text.splitlines() if ln.strip()):
                for pattern, template in self._KEY_PATTERNS:
                    m = pattern.search(line)
                    if not m:
                        continue
                    value = (m.group(2) or "").strip()
                    if not value:
                        continue
                    value = " ".join(value.split())
                    if len(value) > self.max_value_len:
                        value = value[: self.max_value_len].rstrip() + "..."
                    fact = template.format(v=value)
                    key = fact.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    facts.append(fact)
                    break
                if len(facts) >= self.max_facts:
                    break

        return SessionFacts(facts=facts)
