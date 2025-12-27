"""
Collaborator Service
--------------------

Loads real Bali Zero team data from JSON and provides search/list/stats helpers.
Replaces the legacy identity layers with a transparent, easy-to-edit dataset.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "data" / "team_members.json"


@dataclass
class CollaboratorProfile:
    id: str
    email: str
    name: str
    role: str
    department: str
    team: str
    language: str
    languages: list[str] = field(default_factory=list)
    expertise_level: str = "intermediate"
    age: int | None = None
    religion: str | None = None
    traits: list[str] = field(default_factory=list)
    notes: str | None = None
    pin: str | None = None
    location: str | None = None
    emotional_preferences: dict[str, str] = field(default_factory=dict)
    relationships: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize profile for JSON responses."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "department": self.department,
            "team": self.team,
            "language": self.language,
            "languages": self.languages,
            "expertise_level": self.expertise_level,
            "age": self.age,
            "religion": self.religion,
            "traits": self.traits,
            "notes": self.notes,
            "pin": self.pin,
            "location": self.location,
            "emotional_preferences": self.emotional_preferences,
            "relationships": self.relationships,
        }

    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        haystack = " ".join(
            [
                self.name.lower(),
                self.email.lower(),
                self.role.lower(),
                self.department.lower(),
                " ".join(self.traits).lower(),
            ]
        )
        return query_lower in haystack


class CollaboratorService:
    """
    Load collaborator profiles from JSON and expose search utilities.

    Compatible with the old API (TEAM_DATABASE, identify) so existing plugins/tools
    continue to work.
    """

    def __init__(self):
        if not DATA_PATH.exists():
            raise FileNotFoundError(f"Team data file not found: {DATA_PATH}")

        with DATA_PATH.open("r", encoding="utf-8") as f:
            raw_members = json.load(f)

        self.members: list[CollaboratorProfile] = [
            CollaboratorProfile(
                id=entry["id"],
                email=entry["email"].lower(),
                name=entry["name"],
                role=entry["role"],
                department=entry["department"],
                team=entry.get("team", entry["department"]),
                language=entry.get("preferred_language", entry.get("language", "en")),
                languages=entry.get("languages", []),
                expertise_level=entry.get("expertise_level", "intermediate"),
                age=entry.get("age"),
                religion=entry.get("religion"),
                traits=entry.get("traits", []),
                notes=entry.get("notes"),
                pin=entry.get("pin"),
                location=entry.get("location"),
                emotional_preferences=entry.get("emotional_preferences", {}),
                relationships=entry.get("relationships", []),
            )
            for entry in raw_members
        ]

        self.members_by_email: dict[str, CollaboratorProfile] = {
            profile.email: profile for profile in self.members
        }

        # Backwards compatibility: expose TEAM_DATABASE similar to old version
        self.TEAM_DATABASE: dict[str, dict] = {
            email: {
                "id": profile.id,
                "name": profile.name,
                "role": profile.role,
                "department": profile.department,
                "language": profile.language,
                "expertise_level": profile.expertise_level,
                "emotional_preferences": profile.emotional_preferences,
            }
            for email, profile in self.members_by_email.items()
        }

        self.cache: dict[str, tuple[CollaboratorProfile, datetime]] = {}
        self.cache_ttl = timedelta(minutes=10)

        logger.info("✅ CollaboratorService loaded %s team members", len(self.members))

    # ------------------------------------------------------------------ lookups
    async def identify(self, email: str | None) -> CollaboratorProfile:
        if not email:
            return self._anonymous_profile()

        email = email.lower().strip()
        now = datetime.now()

        if email in self.cache:
            profile, cached_at = self.cache[email]
            if now - cached_at < self.cache_ttl:
                return profile

        profile = self.members_by_email.get(email)
        if profile:
            self.cache[email] = (profile, now)
            return profile

        return self._anonymous_profile()

    def get_member(self, email: str) -> CollaboratorProfile | None:
        return self.members_by_email.get(email.lower())

    def list_members(self, department: str | None = None) -> list[CollaboratorProfile]:
        if not department:
            return list(self.members)
        dept = department.lower()
        return [
            profile
            for profile in self.members
            if profile.department.lower() == dept or profile.team.lower() == dept
        ]

    def search_members(self, query: str) -> list[CollaboratorProfile]:
        query = query.strip()
        if not query:
            return []
        return [profile for profile in self.members if profile.matches(query)]

    def get_team_stats(self) -> dict[str, Any]:
        by_department: dict[str, int] = {}
        for profile in self.members:
            dept = profile.department
            by_department[dept] = by_department.get(dept, 0) + 1

        return {
            "total": len(self.members),
            "departments": by_department,
            "languages": self._language_stats(),
        }

    # ------------------------------------------------------------------ helpers
    def _language_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for profile in self.members:
            stats[profile.language] = stats.get(profile.language, 0) + 1
        return stats

    def _anonymous_profile(self) -> CollaboratorProfile:
        return CollaboratorProfile(
            id="anonymous",
            email="anonymous@balizero.com",
            name="Guest",
            role="guest",
            department="general",
            team="general",
            language="en",
            languages=["en"],
            expertise_level="beginner",
            notes="Anonymous user profile",
        )
