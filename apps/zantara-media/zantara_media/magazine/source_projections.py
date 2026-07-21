"""Deterministic public projections for the Bali Zero Magazine collectors.

The functions in this module are a one-way data boundary: they accept the
small, already-public producer artifacts and emit only the closed projection
shape consumed by :mod:`zantara_media.magazine.loaders`. Raw payloads,
NotebookLM identifiers, source titles, and verbatim regulatory excerpts never
cross the boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from zantara_media.magazine.adapters import default_adapter_registry


_SLUG_PART = re.compile(r"[^a-z0-9]+")
_ALLOWED_DOMAINS = {
    "immigration",
    "company",
    "tax",
    "property",
    "compliance",
    "general",
}
_OFFICIAL_HOST_SUFFIXES = (".go.id", ".gov.id")


@dataclass(frozen=True, slots=True)
class PublishedRevisions:
    current_edition: int = 0
    current_breaking: int = 0


@dataclass(frozen=True, slots=True)
class PreparedMorningInputs:
    manifest_path: Path
    asset_manifest_path: Path
    projection_paths: tuple[Path, ...]


def _slug(value: str, *, fallback: str) -> str:
    normalized = _SLUG_PART.sub("-", value.casefold()).strip("-")
    return normalized[:96] or fallback


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _timestamp(value: object, *, fallback: datetime) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        parsed = fallback
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("collector timestamp must be timezone-aware")
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _freshness(completed_at: str, cutoff: datetime) -> str:
    age = cutoff.astimezone(timezone.utc) - _instant(completed_at)
    if age <= timedelta(hours=36):
        return "fresh"
    if age <= timedelta(days=7):
        return "delayed"
    return "archived"


def _public_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return value.strip()


def _official_url(value: str | None) -> bool:
    if value is None:
        return False
    host = (urlsplit(value).hostname or "").casefold()
    return host.endswith(_OFFICIAL_HOST_SUFFIXES)


def _domain(value: object) -> str:
    normalized = str(value or "").strip().casefold().replace("_", "-")
    aliases = {
        "visa": "immigration",
        "immigration": "immigration",
        "company": "company",
        "investment": "company",
        "business": "company",
        "tax": "tax",
        "property": "property",
        "real-estate": "property",
        "regulatory": "compliance",
        "regulation": "compliance",
        "legal": "compliance",
        "hr": "compliance",
        "health": "compliance",
        "compliance": "compliance",
    }
    result = aliases.get(normalized, normalized)
    return result if result in _ALLOWED_DOMAINS else "general"


def _severity(value: object, *, score: int | None = None) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"critical", "high", "medium", "low"}:
        return normalized
    if score is not None:
        if score >= 5:
            return "high"
        if score >= 4:
            return "medium"
    return "low"


def _confidence(value: object) -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in {"high", "medium", "low"} else "medium"


def _projection(
    *,
    system_id: str,
    source_schema_version: str,
    cutoff: datetime,
    completed_at: str,
    status: str,
    collector_id: str,
    items_seen: int,
    candidates: Sequence[Mapping[str, Any]],
    source_count: int,
    unreachable_source_count: int,
    watermark_seed: object,
) -> dict[str, Any]:
    watermark = f"sha256:{_digest(watermark_seed)}"
    run_seed = {
        "system_id": system_id,
        "collector_id": collector_id,
        "completed_at": completed_at,
        "watermark": watermark,
    }
    freshness = _freshness(completed_at, cutoff)
    return {
        "schema_version": "magazine-public-projection.v1",
        "source_schema_version": source_schema_version,
        "system_id": system_id,
        "cutoff": _timestamp(cutoff, fallback=cutoff),
        "watermark": watermark,
        "collector_run": {
            "schema_version": "collector-run.v1",
            "run_id": f"{system_id}-{_digest(run_seed)[:24]}",
            "collector_id": collector_id,
            "started_at": completed_at,
            "completed_at": completed_at,
            "status": status,
            "freshness": freshness,
            "items_seen": max(0, items_seen),
            "items_eligible": len(candidates),
            "source_count": max(0, source_count),
            "unreachable_source_count": max(
                0, min(unreachable_source_count, source_count)
            ),
            "watermark": watermark,
            "verified_at": completed_at,
        },
        "candidates": list(candidates),
    }


def build_regulatory_projection(
    payload: Mapping[str, Any], *, cutoff: datetime
) -> dict[str, Any]:
    completed_at = _timestamp(payload.get("run_at"), fallback=cutoff)
    rows = payload.get("deltas", [])
    if not isinstance(rows, list):
        raise ValueError("regulatory deltas must be a list")
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        citation = str(row.get("citation") or "Regulatory update").strip()
        citation_slug = _slug(citation, fallback=_digest(row)[:16])
        source_url = _public_url(row.get("source"))
        official = _official_url(source_url)
        evidence_id = f"evidence-regulatory-{citation_slug}"
        first_seen = _timestamp(row.get("first_seen_at"), fallback=_instant(completed_at))
        title = str(row.get("title_en") or row.get("title_id") or citation).strip()
        summary = str(row.get("summary") or title).strip()
        service_domain = _domain(row.get("service_line"))
        candidates.append(
            {
                "public_id": f"regulatory-{_digest(citation)[:24]}",
                "slug": _slug(title, fallback=citation_slug),
                "language": "en",
                "domain": service_domain,
                "severity": _severity(row.get("severity")),
                "first_seen_at": first_seen,
                "event_occurred_at": first_seen,
                "updated_at": completed_at,
                "title": title,
                "deck": summary[:320],
                "summary": summary,
                "why_it_matters": str(
                    row.get("impact_note")
                    or "The relevant Bali Zero practice should review the verified change."
                ).strip(),
                "curiosity_text": f"The change is catalogued under {service_domain}.",
                "claims": [
                    {
                        "claim_id": f"claim-regulatory-{citation_slug}",
                        "claim_kind": "fact",
                        "legal_effect": "none",
                        "normalized_text": f"{citation}: {title}",
                        "numeric_value": None,
                        "numeric_unit": None,
                        "as_of": str(payload.get("today") or "") or None,
                        "evidence_ids": [evidence_id],
                        "breaking_gate": "official-primary" if official else None,
                    }
                ],
                "evidence_refs": [
                    {
                        "evidence_id": evidence_id,
                        "root_source_id": f"root-{_digest(source_url or citation)[:24]}",
                        "canonical_url": source_url,
                        "publisher": (urlsplit(source_url).hostname if source_url else None)
                        or "Regulatory Watcher",
                        "document_citation": citation,
                        "published_at": None,
                        "retrieved_at": completed_at,
                        "source_type": "official" if official else "research",
                        "primary_document_status": "verified" if official else "unresolved",
                        "root_resolution_status": "resolved" if source_url else "unresolved",
                        "independence_verdict": "independent" if source_url else "ambiguous",
                        "evidence_note": "Sanitized regulatory delta metadata.",
                        "upstream_root_source_ids": [],
                        "syndication_group_fingerprint": f"regulatory-{_digest(source_url or citation)[:24]}",
                        "independence_ruleset_version": "magazine-source.v1",
                        "independence_reason": (
                            "Official primary host." if official else "Single-source morning evidence."
                        ),
                        "counts_toward_breaking": official,
                    }
                ],
                "asset_digests": [],
                "legal_effect_claim_ids": [],
                "novelty": 0.9,
                "recency": 1.0,
                "operational_impact": {
                    "critical": 1.0,
                    "high": 0.9,
                    "medium": 0.65,
                    "low": 0.35,
                }[_severity(row.get("severity"))],
                "confidence": _confidence(row.get("confidence")),
                "lifecycle_state": "verified",
                "expected_current_version": 0,
            }
        )
    unreachable = payload.get("unreachable_sources", [])
    unreachable_count = len(unreachable) if isinstance(unreachable, list) else 0
    seen = payload.get("seen_citations", [])
    seen_count = len(seen) if isinstance(seen, list) else len(rows)
    source_count = max(1, seen_count + unreachable_count) if rows or unreachable_count else 0
    status = "degraded" if bool(payload.get("partial")) else "healthy"
    return _projection(
        system_id="regulatory-watcher",
        source_schema_version="regulatory-public.v1",
        cutoff=cutoff,
        completed_at=completed_at,
        status=status,
        collector_id="daily-regulatory-watcher",
        items_seen=len(rows),
        candidates=candidates,
        source_count=source_count,
        unreachable_source_count=unreachable_count,
        watermark_seed=payload,
    )


def build_mata_garuda_projection(
    payload: Mapping[str, Any], *, cutoff: datetime
) -> dict[str, Any]:
    completed_at = _timestamp(payload.get("generated_at"), fallback=cutoff)
    rows = payload.get("items", [])
    if not isinstance(rows, list):
        raise ValueError("MATA GARUDA items must be a list")
    candidates: list[dict[str, Any]] = []
    publishers: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        url = _public_url(row.get("url"))
        source = str(row.get("source") or "MATA GARUDA").strip()
        publishers.add(source)
        public_seed = url or f"{title}|{row.get('timestamp', '')}"
        public_id = f"mata-{_digest(public_seed)[:24]}"
        evidence_id = f"evidence-{public_id}"
        score_value = row.get("relevance_score", 0)
        score = int(score_value) if isinstance(score_value, (int, str)) else 0
        observed_at = _timestamp(row.get("timestamp"), fallback=_instant(completed_at))
        summary = str(row.get("summary") or title).strip()
        evidence = []
        claim_evidence: list[str] = []
        if url is not None:
            claim_evidence.append(evidence_id)
            evidence.append(
                {
                    "evidence_id": evidence_id,
                    "root_source_id": f"root-{_digest(url)[:24]}",
                    "canonical_url": url,
                    "publisher": source,
                    "document_citation": None,
                    "published_at": observed_at,
                    "retrieved_at": completed_at,
                    "source_type": "journalism",
                    "primary_document_status": "not-primary",
                    "root_resolution_status": "resolved",
                    "independence_verdict": "independent",
                    "evidence_note": "Public-safe MATA GARUDA feed entry.",
                    "upstream_root_source_ids": [],
                    "syndication_group_fingerprint": f"mata-{_digest(url)[:24]}",
                    "independence_ruleset_version": "magazine-source.v1",
                    "independence_reason": "Canonical public URL retained from the public-safe feed.",
                    "counts_toward_breaking": False,
                }
            )
        candidates.append(
            {
                "public_id": public_id,
                "slug": _slug(title, fallback=public_id),
                "language": "en",
                "domain": _domain(row.get("domain")),
                "severity": _severity(None, score=score),
                "first_seen_at": observed_at,
                "event_occurred_at": observed_at,
                "updated_at": completed_at,
                "title": title,
                "deck": summary[:320],
                "summary": summary,
                "why_it_matters": "This public signal may affect Bali Zero clients or operations.",
                "curiosity_text": None,
                "claims": [
                    {
                        "claim_id": f"claim-{public_id}",
                        "claim_kind": "fact" if claim_evidence else "analysis",
                        "legal_effect": "none",
                        "normalized_text": title,
                        "numeric_value": None,
                        "numeric_unit": None,
                        "as_of": None,
                        "evidence_ids": claim_evidence,
                        "breaking_gate": None,
                    }
                ],
                "evidence_refs": evidence,
                "asset_digests": [],
                "legal_effect_claim_ids": [],
                "novelty": min(1.0, max(0.2, score / 5)),
                "recency": 0.9,
                "operational_impact": min(1.0, max(0.2, score / 5)),
                "confidence": "medium",
                "lifecycle_state": "verified",
                "expected_current_version": 0,
            }
        )
    return _projection(
        system_id="mata-garuda",
        source_schema_version="mata-garuda-public.v1",
        cutoff=cutoff,
        completed_at=completed_at,
        status="healthy",
        collector_id="kita-feed-generator",
        items_seen=len(rows),
        candidates=candidates,
        source_count=len(publishers),
        unreachable_source_count=0,
        watermark_seed=payload,
    )


def build_notebooklm_projection(
    payload: Mapping[str, Any], *, cutoff: datetime
) -> dict[str, Any]:
    completed_at = _timestamp(payload.get("generated_at"), fallback=cutoff)
    notebooks = payload.get("notebooks", [])
    if not isinstance(notebooks, list):
        raise ValueError("NotebookLM notebooks must be a list")
    source_count = 0
    unhealthy = 0
    for notebook in notebooks:
        if not isinstance(notebook, Mapping):
            continue
        raw_count = notebook.get("source_count", 0)
        if isinstance(raw_count, int) and not isinstance(raw_count, bool):
            source_count += max(0, raw_count)
        if notebook.get("health") not in {None, "healthy"}:
            unhealthy += 1
    return _projection(
        system_id="notebooklm",
        source_schema_version="notebooklm-public.v1",
        cutoff=cutoff,
        completed_at=completed_at,
        status="healthy" if unhealthy == 0 else "degraded",
        collector_id="nb-inventory",
        items_seen=len(notebooks),
        candidates=[],
        source_count=source_count,
        unreachable_source_count=unhealthy,
        watermark_seed={
            "generated_at": completed_at,
            "notebook_count": len(notebooks),
            "source_count": source_count,
            "unhealthy": unhealthy,
        },
    )


def build_intel_lake_projection(
    rows: Sequence[Mapping[str, Any]],
    *,
    cutoff: datetime,
    completed_at: str | None = None,
    status: str = "healthy",
) -> dict[str, Any]:
    verified_at = _timestamp(completed_at, fallback=cutoff)
    candidates: list[dict[str, Any]] = []
    publishers: set[str] = set()
    for row in rows:
        if row.get("is_probe_sandbox") is True:
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        canonical_url = _public_url(row.get("canonical_url"))
        publisher = str(row.get("source_domain") or "Intel Lake").strip()
        publishers.add(publisher)
        public_seed = canonical_url or f"{publisher}|{title}"
        public_id = f"intel-{_digest(public_seed)[:24]}"
        evidence_id = f"evidence-{public_id}"
        first_seen = _timestamp(row.get("first_seen_at"), fallback=_instant(verified_at))
        updated_at = _timestamp(row.get("last_seen_at"), fallback=_instant(verified_at))
        summary = str(row.get("summary") or title).strip()
        tags = row.get("topic_tags", [])
        domain = "general"
        if isinstance(tags, (list, tuple)):
            for tag in tags:
                mapped = _domain(tag)
                if mapped != "general":
                    domain = mapped
                    break
        evidence = []
        claim_evidence: list[str] = []
        if canonical_url is not None:
            claim_evidence.append(evidence_id)
            official = _official_url(canonical_url)
            evidence.append(
                {
                    "evidence_id": evidence_id,
                    "root_source_id": f"root-{_digest(canonical_url)[:24]}",
                    "canonical_url": canonical_url,
                    "publisher": publisher,
                    "document_citation": None,
                    "published_at": _timestamp(
                        row.get("published_at"), fallback=_instant(first_seen)
                    ),
                    "retrieved_at": verified_at,
                    "source_type": "official" if official else "journalism",
                    "primary_document_status": "verified" if official else "not-primary",
                    "root_resolution_status": "resolved",
                    "independence_verdict": "independent",
                    "evidence_note": "Sanitized Intel Lake canonical item.",
                    "upstream_root_source_ids": [],
                    "syndication_group_fingerprint": f"intel-{_digest(canonical_url)[:24]}",
                    "independence_ruleset_version": "magazine-source.v1",
                    "independence_reason": "Canonical public URL retained from Intel Lake.",
                    "counts_toward_breaking": official,
                }
            )
        confidence_raw = row.get("confidence_score")
        confidence_score = (
            float(confidence_raw)
            if isinstance(confidence_raw, (int, float))
            and not isinstance(confidence_raw, bool)
            else 0.5
        )
        confidence_score = min(1.0, max(0.0, confidence_score))
        confidence = (
            "high" if confidence_score > 0.60 else "medium" if confidence_score >= 0.15 else "low"
        )
        candidates.append(
            {
                "public_id": public_id,
                "slug": _slug(title, fallback=public_id),
                "language": str(row.get("language") or "en").strip(),
                "domain": domain,
                "severity": _severity(row.get("severity")),
                "first_seen_at": first_seen,
                "event_occurred_at": _timestamp(
                    row.get("published_at"), fallback=_instant(first_seen)
                ),
                "updated_at": updated_at,
                "title": title,
                "deck": summary[:320],
                "summary": summary,
                "why_it_matters": "This verified public signal may affect Bali Zero clients or operations.",
                "curiosity_text": None,
                "claims": [
                    {
                        "claim_id": f"claim-{public_id}",
                        "claim_kind": "fact" if claim_evidence else "analysis",
                        "legal_effect": "none",
                        "normalized_text": title,
                        "numeric_value": None,
                        "numeric_unit": None,
                        "as_of": None,
                        "evidence_ids": claim_evidence,
                        "breaking_gate": (
                            "official-primary"
                            if canonical_url is not None and _official_url(canonical_url)
                            else None
                        ),
                    }
                ],
                "evidence_refs": evidence,
                "asset_digests": [],
                "legal_effect_claim_ids": [],
                "novelty": 0.7,
                "recency": 0.9,
                "operational_impact": 0.6,
                "confidence": confidence,
                "lifecycle_state": "verified",
                "expected_current_version": 0,
            }
        )
    return _projection(
        system_id="intel-lake",
        source_schema_version="intel-public.v1",
        cutoff=cutoff,
        completed_at=verified_at,
        status=status,
        collector_id="intel-lake-public-snapshot",
        items_seen=len(rows),
        candidates=candidates,
        source_count=len(publishers),
        unreachable_source_count=0,
        watermark_seed={"completed_at": verified_at, "candidates": candidates},
    )


def _unavailable_projection(
    system_id: str, source_schema_version: str, *, cutoff: datetime
) -> dict[str, Any]:
    return _projection(
        system_id=system_id,
        source_schema_version=source_schema_version,
        cutoff=cutoff,
        completed_at=_timestamp(cutoff, fallback=cutoff),
        status="unavailable",
        collector_id=f"{system_id}-public-export",
        items_seen=0,
        candidates=[],
        source_count=0,
        unreachable_source_count=0,
        watermark_seed={"system_id": system_id, "status": "unavailable"},
    )


def _read_object(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError(f"collector artifact must be an object: {path}")
    return parsed


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)


def _validate_public_projection(system_id: str, projection: Mapping[str, Any]) -> None:
    """Apply the same closed-boundary validation used by the publication loader."""
    if projection.get("system_id") != system_id:
        raise ValueError("projection system_id does not match its named source")
    registry = default_adapter_registry()
    adapter = registry.get(system_id)
    collector_run = projection.get("collector_run")
    candidates = projection.get("candidates")
    if not isinstance(collector_run, Mapping) or not isinstance(candidates, list):
        raise ValueError("projection must contain collector_run and candidates")
    adapter.collector_run(collector_run)
    adapter.candidates(candidates)


def prepare_morning_inputs(
    *,
    repo_root: Path,
    state_dir: Path,
    cutoff: datetime,
    intel_rows: Sequence[Mapping[str, Any]],
    intel_status: str,
) -> PreparedMorningInputs:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")
    edition_date = (cutoff.astimezone(timezone.utc) + timedelta(hours=8)).date().isoformat()
    projection_dir = state_dir / "inputs" / "projections" / edition_date
    packet_dir = state_dir / "packets"
    journal_path = state_dir / "outcomes.jsonl"

    regulatory_raw = _read_object(
        repo_root / "research" / "regulatory" / f"{edition_date}-delta.json"
    )
    mata_raw = _read_object(
        repo_root / "apps" / "mata-garuda" / "data" / "kita_feed.json"
    )
    notebook_raw = _read_object(
        repo_root / "research" / "nb-health" / "nb-inventory-live.json"
    )

    projections = {
        "intel-lake": build_intel_lake_projection(
            intel_rows,
            cutoff=cutoff,
            completed_at=_timestamp(cutoff, fallback=cutoff),
            status=intel_status,
        ),
        "mata-garuda": (
            build_mata_garuda_projection(mata_raw, cutoff=cutoff)
            if mata_raw is not None
            else _unavailable_projection(
                "mata-garuda", "mata-garuda-public.v1", cutoff=cutoff
            )
        ),
        "notebooklm": (
            build_notebooklm_projection(notebook_raw, cutoff=cutoff)
            if notebook_raw is not None
            else _unavailable_projection(
                "notebooklm", "notebooklm-public.v1", cutoff=cutoff
            )
        ),
        "regulatory-watcher": (
            build_regulatory_projection(regulatory_raw, cutoff=cutoff)
            if regulatory_raw is not None
            else _unavailable_projection(
                "regulatory-watcher", "regulatory-public.v1", cutoff=cutoff
            )
        ),
    }
    for system_id, projection in projections.items():
        _validate_public_projection(system_id, projection)

    projection_paths: list[Path] = []
    projection_inputs: list[dict[str, str]] = []
    for system_id in sorted(projections):
        path = projection_dir / f"{system_id}.public.json"
        _write_json_atomic(path, projections[system_id])
        projection_paths.append(path)
        projection_inputs.append(
            {"system_id": system_id, "projection_path": str(path.resolve())}
        )

    revisions = resolve_published_revisions(packet_dir, journal_path)
    manifest_path = state_dir / "inputs" / f"morning-{edition_date}.json"
    _write_json_atomic(
        manifest_path,
        {
            "schema_version": "magazine-morning-input.v2",
            "projection_inputs": projection_inputs,
            "expected_current_revision": revisions.current_edition,
            "expected_breaking_revision": revisions.current_breaking,
        },
    )
    asset_manifest_path = state_dir / "inputs" / f"assets-{edition_date}.json"
    if not asset_manifest_path.is_file():
        _write_json_atomic(
            asset_manifest_path,
            {"schema_version": "asset-intents.v1", "intents": []},
        )
    return PreparedMorningInputs(
        manifest_path=manifest_path,
        asset_manifest_path=asset_manifest_path,
        projection_paths=tuple(projection_paths),
    )


def resolve_published_revisions(packet_dir: Path, journal_path: Path) -> PublishedRevisions:
    if not packet_dir.is_dir() or not journal_path.is_file():
        return PublishedRevisions()
    completed: set[str] = set()
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        if row.get("state") == "completed" and isinstance(row.get("operation_id"), str):
            completed.add(str(row["operation_id"]))
    edition_revision = 0
    breaking_revision = 0
    for path in packet_dir.glob("*.json"):
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        packet_id = packet.get("packet_id")
        if not isinstance(packet_id, str):
            continue
        schema = packet.get("schema_version")
        if schema == "edition.v1":
            operation = f"/api/machine/publications/editions:{packet_id}"
            if operation in completed:
                edition_revision = max(edition_revision, int(packet["edition_revision"]))
        elif schema == "story.v1":
            operation = f"/api/machine/publications/breaking:{packet_id}"
            if operation in completed:
                breaking_revision = max(
                    breaking_revision, int(packet["expected_breaking_revision"]) + 1
                )
    return PublishedRevisions(
        current_edition=edition_revision,
        current_breaking=breaking_revision,
    )
