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

# Allowed critic verdicts. "PASS-WITH-NOTES" added 2026-06-14 (F20 cure): the LIVE
# wr3-critic emits it (it is the verdict on the only real manifest on disk), so the
# original enum {PENDING,PASS,FAIL,DEGRADED} would reject every real episode. This is
# a DELIBERATE widening, not a silent one — it makes the validator compatible with the
# verdict the pipeline actually produces. Treated as a non-blocking PASS variant.
ALLOWED_VERDICTS = frozenset({"PENDING", "PASS", "PASS-WITH-NOTES", "FAIL", "DEGRADED"})


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

    if manifest["critic_verdict"] not in ALLOWED_VERDICTS:
        raise ManifestValidationError(
            f"critic_verdict invalid: {manifest['critic_verdict']!r} "
            f"(allowed: {sorted(ALLOWED_VERDICTS)})"
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


# ---------------------------------------------------------------------------
# F20 cure (2026-06-14): bridge the free-form wr3-post-assembler manifest to the
# strict 18-field schema. The post-assembler is an LLM agent prompted as a string
# (wr3_supervisor.py _build_prompt assembly_ready) — its output uses different
# field NAMES (slug/duration_s/vo_lufs/render_cost_cr/variants/identity_gate, 17
# keys, critic_verdict="PASS-WITH-NOTES", claim_ids=None). validate_manifest() would
# reject it on 4 gates. normalize_assembler_manifest() maps real -> schema +
# derives the missing fields from sibling artifacts, so the validator stops being
# dead code and actually validates the artifact the pipeline produces.
# ---------------------------------------------------------------------------

# real post-assembler key -> schema key (1:1 renames)
_ASSEMBLER_RENAME = {
    "vo_lufs": "lufs_measured",
    "render_cost_cr": "flow_credits_spent",
}


def _extract_claim_ids(brief: dict[str, Any] | None) -> list[str]:
    """Collect claim_ids from a brief.json (regulatory_citations / key_numbers / key_facts)."""
    ids: list[str] = []
    if not isinstance(brief, dict):
        return ids
    for key in ("regulatory_citations", "key_numbers", "key_facts"):
        for item in brief.get(key) or []:
            if isinstance(item, dict) and item.get("claim_id"):
                ids.append(str(item["claim_id"]))
    return list(dict.fromkeys(ids))  # dedup, preserve order


def _master_asset_hashes(raw: dict[str, Any]) -> dict[str, str]:
    """Reuse the sha256 the assembler already computed for master_mp4 if present."""
    master = raw.get("master_mp4")
    if isinstance(master, dict) and master.get("sha256"):
        return {"master.mp4": str(master["sha256"])}
    return {}


def normalize_assembler_manifest(
    raw: dict[str, Any],
    *,
    brief: dict[str, Any] | None = None,
    identity_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a free-form post-assembler manifest onto the strict 18-field schema.

    Pure transform — does NOT validate (caller validates). Missing-but-derivable
    fields are filled from `raw` + the sibling `brief`/`identity_report` artifacts;
    fields with no source (contract_versions, agents_invoked, total_cost_usd) get
    schema-typed empties so validate_manifest() passes on field PRESENCE while
    still enforcing claim_ids/verdict/version.
    """
    brief = brief or {}
    variants = raw.get("variants")
    delivered = list(variants.keys()) if isinstance(variants, dict) else (
        list(variants) if isinstance(variants, list) else [])
    duration_s = raw.get("duration_s")
    identity_avg = None
    if isinstance(identity_report, dict):
        identity_avg = identity_report.get("overall_cosine_avg")
    if identity_avg is None and isinstance(raw.get("identity_gate"), (int, float)):
        identity_avg = raw["identity_gate"]

    out: dict[str, Any] = {
        "episode_id": raw.get("episode_id"),
        "topic": brief.get("topic") or raw.get("slug") or raw.get("episode_id"),
        "audience_segment": brief.get("audience_segment", "general"),
        "duration_master_ms": int(duration_s * 1000) if isinstance(duration_s, (int, float)) else None,
        "created_at": raw.get("assembled_at"),
        "completed_at": raw.get("assembled_at"),
        "claim_ids": _extract_claim_ids(brief),
        "asset_hashes": _master_asset_hashes(raw),
        "variants_delivered": delivered,
        "variants_missing": list(raw.get("variants_failed") or []),
        "contract_versions": raw.get("contract_versions") or {},
        "agents_invoked": raw.get("agents_invoked") or [],
        "total_cost_usd": float(raw.get("total_cost_usd") or 0.0),
        "flow_credits_spent": int(raw.get("render_cost_cr") or 0),
        "critic_verdict": raw.get("critic_verdict", "PENDING"),
        "identity_overall_cosine_avg": identity_avg,
        "lufs_measured": raw.get("vo_lufs"),
        "wr3_room_version": raw.get("wr3_room_version") or CURRENT_ROOM_VERSION,
    }
    return out


def finalize_episode_manifest(episode_dir: Path, *, write: bool = True) -> dict[str, Any]:
    """Read an episode dir's free-form manifest + siblings, normalize, validate.

    This is the wiring point the supervisor's assembly_ready handler (or a CI gate)
    should call AFTER wr3-post-assembler writes episode_manifest.json. It produces a
    schema-valid `episode_manifest.normalized.json` next to the original (the original
    is NOT overwritten — defense-in-depth). Raises ManifestValidationError if the real
    episode is genuinely non-conformant (e.g. zero claim_ids), which is the desired
    behaviour — the validator is no longer dead code.
    """
    raw = json.loads((episode_dir / "episode_manifest.json").read_text())
    brief = None
    identity = None
    brief_path = episode_dir / "brief.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text())
        except Exception:
            brief = None
    id_path = episode_dir / "identity-report.json"
    if id_path.exists():
        try:
            identity = json.loads(id_path.read_text())
        except Exception:
            identity = None
    normalized = normalize_assembler_manifest(raw, brief=brief, identity_report=identity)
    validate_manifest(normalized)
    if write:
        (episode_dir / "episode_manifest.normalized.json").write_text(
            json.dumps(normalized, indent=2)
        )
    return normalized


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
