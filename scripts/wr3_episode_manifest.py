#!/usr/bin/env python3
"""WR3 episode manifest builder — 18-field manifest with sha256 + claim_ids.

Symbiosis Law 7 (Numeri prima):
  Every claim has claim_id, every asset has sha256, every contract has version.
Symbiosis Law 8 (Passato/Presente/Futuro):
  Manifest sha256 anchors enable past-episode comparison + dedup.

18 mandatory fields (see _validate_manifest below).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANDATORY_FIELDS = (
    "episode_id",
    "topic",
    "audience_segment",
    "duration_master_ms",
    "created_at",
    "completed_at",
    "claim_ids",
    "asset_hashes",
    "variants_delivered",
    "variants_missing",
    "contract_versions",
    "agents_invoked",
    "total_cost_usd",
    "flow_credits_spent",
    "critic_verdict",
    "identity_overall_cosine_avg",
    "lufs_measured",
    "wr3_room_version",
)

CURRENT_ROOM_VERSION = "0.1.0"  # bump on schema/agent set change


@dataclass
class ManifestBuilder:
    episode_id: str
    topic: str
    audience_segment: str = "general"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    duration_master_ms: int | None = None
    claim_ids: list[str] = field(default_factory=list)
    asset_hashes: dict[str, str] = field(default_factory=dict)
    variants_delivered: list[str] = field(default_factory=list)
    variants_missing: list[str] = field(default_factory=list)
    contract_versions: dict[str, str] = field(default_factory=dict)
    agents_invoked: list[str] = field(default_factory=list)
    total_cost_usd: float = 0.0
    flow_credits_spent: int = 0
    critic_verdict: str = "PENDING"
    identity_overall_cosine_avg: float | None = None
    lufs_measured: float | None = None
    wr3_room_version: str = CURRENT_ROOM_VERSION

    def add_claim(self, claim_id: str) -> None:
        if claim_id and claim_id not in self.claim_ids:
            self.claim_ids.append(claim_id)

    def hash_asset(self, label: str, path: Path) -> str:
        if not path.exists():
            self.asset_hashes[label] = "MISSING"
            return "MISSING"
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        digest = h.hexdigest()
        self.asset_hashes[label] = digest
        return digest

    def record_agent(self, agent: str, contract_version: str, cost_usd: float = 0.0) -> None:
        if agent not in self.agents_invoked:
            self.agents_invoked.append(agent)
        self.contract_versions[agent] = contract_version
        self.total_cost_usd += cost_usd

    def finalize(self) -> dict[str, Any]:
        self.completed_at = datetime.now(timezone.utc).isoformat()
        manifest = {
            "episode_id": self.episode_id,
            "topic": self.topic,
            "audience_segment": self.audience_segment,
            "duration_master_ms": self.duration_master_ms,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "claim_ids": list(self.claim_ids),
            "asset_hashes": dict(self.asset_hashes),
            "variants_delivered": list(self.variants_delivered),
            "variants_missing": list(self.variants_missing),
            "contract_versions": dict(self.contract_versions),
            "agents_invoked": list(self.agents_invoked),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "flow_credits_spent": self.flow_credits_spent,
            "critic_verdict": self.critic_verdict,
            "identity_overall_cosine_avg": self.identity_overall_cosine_avg,
            "lufs_measured": self.lufs_measured,
            "wr3_room_version": self.wr3_room_version,
        }
        validate_manifest(manifest)
        return manifest

    def write(self, episode_dir: Path) -> Path:
        manifest = self.finalize()
        path = episode_dir / "episode_manifest.json"
        path.write_text(json.dumps(manifest, indent=2))
        return path


class ManifestValidationError(Exception):
    """Manifest missing mandatory field or has invalid value."""


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Raise ManifestValidationError if any of the 18 fields is missing/invalid."""
    missing = [f for f in MANDATORY_FIELDS if f not in manifest]
    if missing:
        raise ManifestValidationError(f"Manifest missing fields: {missing}")

    if manifest["critic_verdict"] not in {"PENDING", "PASS", "FAIL", "DEGRADED"}:
        raise ManifestValidationError(
            f"critic_verdict invalid: {manifest['critic_verdict']!r}"
        )

    if manifest["wr3_room_version"] != CURRENT_ROOM_VERSION:
        raise ManifestValidationError(
            f"wr3_room_version mismatch: {manifest['wr3_room_version']!r} "
            f"vs runtime {CURRENT_ROOM_VERSION!r}"
        )

    # Sanity: at least 1 claim_id (every episode has at least one factual claim)
    if not manifest["claim_ids"]:
        raise ManifestValidationError("claim_ids empty — episode must cite at least one fact")


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    validate_manifest(data)
    return data


if __name__ == "__main__":
    builder = ManifestBuilder(
        episode_id="smoke-manifesto-zantara",
        topic="Manifesto Zantara — Bali Zero brand intro 60s",
        audience_segment="new-arrivals-bali",
    )
    builder.add_claim("claim-uu-6-2011-art-117")
    builder.record_agent("wr3-brief-interpreter", "1.0.0", cost_usd=0.12)
    builder.record_agent("wr3-script-editor", "1.0.0", cost_usd=0.11)
    builder.variants_delivered = ["tiktok", "ig-reels", "yt-shorts", "fb"]
    builder.identity_overall_cosine_avg = 0.74
    builder.lufs_measured = -13.8
    builder.duration_master_ms = 60_500
    builder.critic_verdict = "PASS"

    # Hash a fake asset for the smoke
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(b"fake_master_mp4")
        tmp_path = Path(tmp.name)
    builder.hash_asset("master.mp4", tmp_path)
    tmp_path.unlink()

    manifest = builder.finalize()
    print(json.dumps(manifest, indent=2))
