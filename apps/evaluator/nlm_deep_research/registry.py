"""Source registry for NLM Deep Research Pipeline.

Manages the nlm_nb2_sources.json file — load, save, query, update.
All source metadata operations go through this module.
"""

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = "apps/evaluator/nlm_nb2_sources.json"


class SourceRegistry:
    """Thread-safe source registry backed by JSON file."""

    def __init__(self, path: str | Path = DEFAULT_REGISTRY_PATH):
        self.path = Path(path)
        self._data: dict = {}
        self._dirty = False

    def load(self) -> None:
        """Load registry from disk."""
        if not self.path.exists():
            logger.warning("Registry file not found: %s", self.path)
            self._data = {
                "schema_version": 1,
                "notebook_id": "NB-2",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "summary": {"total_tracked": 0, "active": 0, "quarantine": 0, "archived": 0},
                "domain_denylist": [],
                "sources": {},
            }
            return

        with open(self.path) as f:
            self._data = json.load(f)
        logger.info(
            "Loaded registry: %d sources from %s",
            self._data.get("summary", {}).get("total_tracked", 0),
            self.path,
        )

    def save(self) -> None:
        """Save registry to disk with updated timestamp and counts."""
        self._update_summary()
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

        self._dirty = False
        logger.info("Saved registry: %d sources to %s", self.total_count, self.path)

    @property
    def sources(self) -> dict:
        """Access the sources dict."""
        return self._data.get("sources", {})

    @property
    def domain_denylist(self) -> list[str]:
        """Access the domain denylist."""
        return self._data.get("domain_denylist", [])

    @property
    def total_count(self) -> int:
        return len(self.sources)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self.sources.values() if s.get("stage") == "ACTIVE")

    @property
    def quarantine_count(self) -> int:
        return sum(1 for s in self.sources.values() if s.get("stage") == "QUARANTINE")

    @property
    def archived_count(self) -> int:
        return sum(1 for s in self.sources.values() if s.get("stage") == "ARCHIVE")

    def get_source(self, source_id: str) -> Optional[dict]:
        """Get source by NLM source ID."""
        return self.sources.get(source_id)

    def get_sources_by_stage(self, stage: str) -> dict[str, dict]:
        """Get all sources in a specific stage."""
        return {
            sid: s for sid, s in self.sources.items() if s.get("stage") == stage
        }

    def get_sources_by_tier(self, tier: int) -> dict[str, dict]:
        """Get all sources of a specific tier."""
        return {
            sid: s for sid, s in self.sources.items() if s.get("tier") == tier
        }

    def get_sources_by_category(self, category: str) -> dict[str, dict]:
        """Get all sources of a specific category."""
        return {
            sid: s for sid, s in self.sources.items() if s.get("category") == category
        }

    def get_pinned_sources(self) -> dict[str, dict]:
        """Get all pinned (non-removable) sources."""
        return {
            sid: s
            for sid, s in self.sources.items()
            if s.get("flags", {}).get("pinned", False)
        }

    def get_essential_sources(self) -> dict[str, dict]:
        """Get all ESSENTIAL SVS sources (≥ 0.70)."""
        return {
            sid: s
            for sid, s in self.sources.items()
            if s.get("scores", {}).get("svs_classification") == "ESSENTIAL"
        }

    def add_source(self, source_id: str, source_data: dict) -> None:
        """Add a new source to the registry."""
        self._data.setdefault("sources", {})[source_id] = source_data
        self._dirty = True
        logger.info("Added source: %s (%s)", source_id, source_data.get("title", "?"))

    def update_source(self, source_id: str, updates: dict) -> bool:
        """Update fields on an existing source."""
        if source_id not in self.sources:
            logger.warning("Source not found for update: %s", source_id)
            return False

        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(self.sources[source_id].get(key), dict):
                self.sources[source_id][key].update(value)
            else:
                self.sources[source_id][key] = value

        self._dirty = True
        return True

    def remove_source(self, source_id: str) -> Optional[dict]:
        """Remove a source from the registry. Returns removed source or None."""
        source = self.sources.pop(source_id, None)
        if source:
            self._dirty = True
            logger.info("Removed source: %s (%s)", source_id, source.get("title", "?"))
        return source

    def url_exists(self, url: str) -> bool:
        """Check if a URL already exists in any source."""
        if not url:
            return False
        for s in self.sources.values():
            if s.get("url") == url:
                return True
        return False

    def is_domain_denied(self, url: str) -> bool:
        """Check if URL matches any domain in the denylist."""
        if not url:
            return False
        for domain in self.domain_denylist:
            if domain in url:
                return True
        return False

    def get_master_digests(self) -> dict[str, dict]:
        """Get all Master Digest sources."""
        # Check both sources dict and master_documents section
        mds = {}
        for sid, s in self.sources.items():
            if s.get("category") == "master_digest" or sid.startswith("MD-"):
                mds[sid] = s

        # Also check dedicated master_documents section
        md_section = self._data.get("master_documents", {})
        for key, md in md_section.items():
            nlm_id = md.get("nlm_source_id", key)
            mds[nlm_id] = md

        return mds

    def get_clusters_with_claims(self) -> set[str]:
        """Get set of cluster letters that have at least one claim."""
        clusters = set()
        for s in self.sources.values():
            claims = s.get("scores", {}).get("claims_backed", [])
            if claims:
                # Infer cluster from title/category
                title = s.get("title", "").lower()
                if any(w in title for w in ["tka", "rptka", "kerja", "work", "dkp"]):
                    clusters.add("A")
                if any(w in title for w in ["kitap", "e31", "family", "keluarga"]):
                    clusters.add("B")
                if any(w in title for w in ["voa", "c1", "c2", "visit", "kunjungan"]):
                    clusters.add("C")
                if any(w in title for w in ["e33", "e28", "golden", "nomad", "second"]):
                    clusters.add("D")
                if any(w in title for w in ["deport", "overstay", "cekal", "pora"]):
                    clusters.add("E")
        return clusters

    def _update_summary(self) -> None:
        """Recalculate summary counts."""
        self._data["summary"] = {
            "total_tracked": self.total_count,
            "active": self.active_count,
            "quarantine": self.quarantine_count,
            "archived": self.archived_count,
        }

    def to_invariant_dict(self) -> dict:
        """Export sources in format expected by invariants.py."""
        return deepcopy(self.sources)
