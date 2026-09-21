"""kg_kbli_licensing_from_canonical.py — Lot 0 + Phase 1a of the KG licensing-class cure.

Spec: docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md (r4), §4 (the
derivation rule), §5 (script design) and §6 (phases). Lot 0's two
phase-independent gestures (`--placeholders-only`, `--create-missing-node`)
shipped in PR #7017 and are live on PROD; this revision adds the Phase 1a
licence BUILD mode (the default when neither Lot-0 flag is given) and
`--census`. Phase 1b stays refused — `PHASE_1B_ENABLED` is a module constant
only the spec's §8 F2 PR may flip, never a runtime grep or a bare CLI flag.

  (build mode, default) derive licences from the canonical v10 `per_skala`
                         rows (§4), write them for S1/S2 codes (§5.2), leave
                         S3 alone unless the rendered and derived name sets
                         match exactly, refuse legacy-served codes outright.
  --placeholders-only    Lot 0(b) — delete the REQUIRES edges to the three
                         §2.1 placeholder nodes, archived first.
  --create-missing-node  Lot 0(c) — insert the one canonical code with no
                         `kbli:<code>` row (01122).
  --census               read-only: both §2 state tables (A live, B
                         post-lot), the 1a/1b split, the licence histogram,
                         the §2.3 one-store codes. Exits 4 when Table A and
                         Table B disagree — i.e. a placeholder edge is still
                         shaping a code's classification, the §2 ordering
                         rule not yet satisfied everywhere.

Scope discipline shared with `kg_kbli_license_fix.py`: `--only` mandatory (no
sweep, ever — `--census` is the one read-only exception), dry-run default,
one transaction per code with the node row locked, refusal instead of
guessing. `--apply` against the unpinned default dataset URL is refused
(`kbli_documents_phantom_cure.py` precedent): pass a commit-pinned raw URL or
a local file, and the sha256 of the bytes used is recorded in `_created_by` /
`_licensing_cure`.

Not in this file, on purpose: `--replace-legacy` (Phase 2, not measured —
hard refusal); the §7 detector and the F2 issuer render (separate PRs); a
production write of any kind (this build runs no `--apply`).

After `--apply`: `kbli_inspect_cache_bust.py --only <codes> --apply`, then a
FRESH `inspect_kbli` read (a probe made before the cure is poisoned for up to
30 days).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from backend.services.kbli_requires_kind import (
    classify_requires_target,
    permit_name_verdict,
)

logger = logging.getLogger("kg_kbli_licensing_from_canonical")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"
ALLOWLIST_URL = f"{RAW_BASE}/scripts/kbli_filiera/kg_oss_not_applicable_codes.json"

# The three §2.1 placeholder nodes — and ONLY those. Verified on PROD
# 2026-09-21: 10 + 6 + 1 REQUIRES edges from 17 distinct KBLI nodes.
PLACEHOLDER_TARGETS: frozenset[str] = frozenset(
    {
        "status_perizinan_pending",
        "izin_usaha_pending",
        "izin_usaha_status_pending_regulation",
    },
)
ARCHIVE_KEY = "_replaced_requires_pp28v10"
SCALE_ORDER: tuple[str, ...] = ("Mikro", "Kecil", "Menengah", "Besar")
SCALE_SET: frozenset[str] = frozenset(SCALE_ORDER)
NEW_NODE_SOURCE_COLLECTION = "kbli_2025_canonical"
NEW_LICENCE_SOURCE_COLLECTION = "kbli_2025_v10_pp28"

# §3: the phrase that marks a v10 row's issuer as outside the OSS path
# (PP 28/2025 Arts. 131(3)/132(2)/133(2)) — lives in `persyaratan` only.
NON_OSS_PHRASE = "Lembaga OSS hanya menerbitkan NIB"

# §4.1 — PP 28/2025, primary text, sha256 of the downloaded PDF. `--apply`
# refuses (SystemExit(2)) if this is incomplete: a mechanical pre-apply
# gate, not a note (see `_assert_legal_basis`).
LEGAL_BASIS: dict[str, str] = {
    "instrument": "PP 28/2025",
    "pdf_sha256": "8808de485eab2499cf3d8369921c097beaea68ae55aa767c61095d47a5a118fb",  # pragma: allowlist secret
    "tiers": "Pasal 128",
    "Rendah": "Pasal 130",
    "Menengah Rendah": "Pasal 131",
    "Menengah Tinggi": "Pasal 132",
    "Tinggi": "Pasal 133",
}

# §4.2 item 1 — the four risk tiers to the licence name the statute assigns.
# A row whose own `perizinan` is explicit always wins over this (see
# `licence_name`).
TIER: dict[str, str] = {
    "Rendah": "NIB",
    "Menengah Rendah": "NIB dan Sertifikat Standar",
    "Menengah Tinggi": "NIB dan Sertifikat Standar",
    "Tinggi": "NIB dan Izin",
}

# §4.2 item 2 — MR and MT share a licence name but not a legal effect
# (Pasal 131(2) vs 132(2),(6)); the distinction rides as data.
VERIFICATION_BY_TIER: dict[str, str] = {
    "Menengah Rendah": "self-declared",
    "Menengah Tinggi": "verified",
}

# Flipped ONLY by the spec's §8 F2 PR, in the same diff that adds the issuer
# field and its HTTP contract test — never a runtime grep, never a CLI flag
# alone (spec §5 item 1).
PHASE_1B_ENABLED = False


class Refusal(Exception):
    """A code this run will not act on; the reason is the message."""


class ShapeDefect(Exception):
    """A canonical row/field does not have one of the four normalised shapes."""


# =============================================================================
# Lot 0 — pure decision logic (unchanged from PR #7017)
# =============================================================================


@dataclass
class PlaceholderPlan:
    code: str
    remove: list[str] = field(default_factory=list)  # placeholder targets present


@dataclass
class MissingNodePlan:
    code: str
    name: str
    description: str
    properties: dict


def plan_placeholder_removal(code: str, node_exists: bool, edge_targets: list[str]) -> PlaceholderPlan:
    """Pure decision: which of this code's REQUIRES targets are placeholders.

    A code with no node is refused (there is no row to archive on). A code
    with no placeholder edge yields an empty plan — the second run is a no-op.
    Every non-placeholder target, `permit:kitas` included, is left alone.
    """
    if not node_exists:
        raise Refusal(f"{code}: no kbli:{code} node — nothing to archive on, refusing")
    present = sorted({t for t in edge_targets if t in PLACEHOLDER_TARGETS})
    return PlaceholderPlan(code=code, remove=present)


def derive_skala_usaha(rows: list[dict]) -> list[str]:
    seen = {s for r in rows for s in (r.get("skala_usaha") or [])}
    return [s for s in SCALE_ORDER if s in seen]


def build_missing_node(
    code: str,
    record: dict | None,
    node_exists: bool,
    *,
    run_id: str,
    at: str,
    dataset_sha256: str,
) -> MissingNodePlan:
    """Pure decision: the node to insert, from canonical-proven fields only."""
    if node_exists:
        raise Refusal(f"{code}: kbli:{code} already exists — --create-missing-node refuses")
    if record is None:
        raise Refusal(f"{code}: not in the canonical dataset — refusing to create a node")
    rows = record.get("per_skala") or []
    if not rows:
        raise Refusal(
            f"{code}: canonical per_skala is [] — its status is a §3 allowlist decision, not a Lot 0 gesture",
        )
    judul = (record.get("judul") or "").strip()
    uraian = (record.get("uraian") or "").strip()
    if not judul or not uraian:
        raise Refusal(f"{code}: canonical judul/uraian empty — refusing")
    props: dict = {
        "kode": code,
        "uraian": uraian,
        "skala_usaha": derive_skala_usaha(rows),
        "licensing_status": "REGULATED",  # spec §3: per_skala rows > 0
        "_created_by": {
            "run": run_id,
            "at": at,
            "reason": "canonical code without a KG node (spec §5.9); no edge, no licence written",
            "dataset_sha256": dataset_sha256,
        },
    }
    if record.get("sektor_id"):
        props["sektor_id"] = record["sektor_id"]
    if record.get("pp28_sources"):
        props["pp28_sources"] = [str(s) for s in record["pp28_sources"]]
    return MissingNodePlan(code=code, name=judul, description=uraian, properties=props)


# =============================================================================
# §4 — the derivation rule (pure, no DB)
# =============================================================================


def normalise_field(value: Any) -> list:
    """§4.2: `None` → `[]`, a non-empty string → `[value]`, a list → itself.

    Never iterate a string as characters. An empty string normalises to `[]`
    (same as absent) rather than `[""]`. Anything else (int/float/dict/bool)
    is a `ShapeDefect` — a row this defect touches makes the whole code
    refuse (§4.2 item 3), never a guess.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return value
    raise ShapeDefect(f"not None/str/list: {value!r} ({type(value).__name__})")


def licence_name(row: dict) -> str:
    """§4.2 item 1: the row's own `perizinan` wins; otherwise the tier maps."""
    perizinan = normalise_field(row.get("perizinan"))
    if perizinan:
        return "/".join(dict.fromkeys(perizinan))
    tier = row.get("kategori_risiko")
    if tier not in TIER:
        raise ShapeDefect(f"unknown kategori_risiko: {tier!r}")
    return TIER[tier]


def validate_skala(value: Any) -> list[str]:
    """A row's `skala_usaha` must be a non-empty subset of the four scales."""
    skala = normalise_field(value)
    if not skala or not set(skala) <= SCALE_SET:
        raise ShapeDefect(f"skala_usaha not a non-empty subset of {SCALE_ORDER}: {value!r}")
    return skala


@dataclass
class LicenceGroup:
    name: str
    kategori_risiko: str
    skala_usaha: list[str]
    jangka_waktu: str
    kewajiban: list[str] = field(default_factory=list)
    persyaratan: list[str] = field(default_factory=list)
    kewenangan: list[str] = field(default_factory=list)
    scope_uraian: list[str] = field(default_factory=list)
    fiktif_positif: bool = False
    pp28_row_indexes: list[Any] = field(default_factory=list)
    sertifikat_standar_verification: str | None = None


def derive_licence_groups(code: str, rows: list[dict] | None) -> list[LicenceGroup]:
    """§4.2: group `per_skala` rows by `(name, kategori_risiko)`, pinned aggregation.

    A malformed row (unknown tier, `skala_usaha` not a non-empty subset of the
    four scales, or any other shape defect) makes the WHOLE code refuse — the
    posture of `plan_licensing_only` in `kbli_documents_cure.py`.
    """
    if not rows:
        raise Refusal(f"{code}: canonical per_skala is [] — not eligible for a Phase 1 build")
    grouped: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for idx, row in enumerate(rows):
        try:
            name = licence_name(row)
            skala = validate_skala(row.get("skala_usaha"))
        except ShapeDefect as exc:
            raise Refusal(f"{code}: malformed per_skala row {idx} — {exc}") from exc
        tier = row["kategori_risiko"]
        key = (name, tier)
        if key not in grouped:
            grouped[key] = {
                "skala": set(),
                "jangka": [],
                "jangka_seen": set(),
                "kewajiban": [],
                "kewajiban_seen": set(),
                "persyaratan": [],
                "persyaratan_seen": set(),
                "kewenangan": [],
                "kewenangan_seen": set(),
                "scope_uraian": [],
                "scope_uraian_seen": set(),
                "fiktif_positif": False,
                "pp28_row_indexes": [],
            }
            order.append(key)
        g = grouped[key]
        g["skala"].update(skala)
        jangka = (row.get("jangka_waktu") or "").strip()
        if jangka and jangka not in g["jangka_seen"]:
            g["jangka_seen"].add(jangka)
            g["jangka"].append(jangka)
        for field_name in ("kewajiban", "persyaratan", "kewenangan", "scope_uraian"):
            for v in normalise_field(row.get(field_name)):
                seen_key = f"{field_name}_seen"
                if v not in g[seen_key]:
                    g[seen_key].add(v)
                    g[field_name].append(v)
        g["fiktif_positif"] = g["fiktif_positif"] or bool(row.get("fiktif_positif"))
        g["pp28_row_indexes"].append(row.get("scope_index"))

    groups: list[LicenceGroup] = []
    for name, tier in order:
        g = grouped[(name, tier)]
        groups.append(
            LicenceGroup(
                name=name,
                kategori_risiko=tier,
                skala_usaha=[s for s in SCALE_ORDER if s in g["skala"]],
                jangka_waktu="/".join(g["jangka"]),
                kewajiban=g["kewajiban"],
                persyaratan=g["persyaratan"],
                kewenangan=g["kewenangan"],
                scope_uraian=g["scope_uraian"],
                fiktif_positif=g["fiktif_positif"],
                pp28_row_indexes=g["pp28_row_indexes"],
                sertifikat_standar_verification=VERIFICATION_BY_TIER.get(tier),
            ),
        )
    return groups


def is_non_oss_issued(rows: list[dict]) -> bool:
    """§3: any row whose `persyaratan` carries the non-OSS-issuance phrase."""
    for row in rows:
        for text in normalise_field(row.get("persyaratan")):
            if isinstance(text, str) and NON_OSS_PHRASE in text:
                return True
    return False


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_node_properties(group: LicenceGroup) -> dict:
    """§5.3: the group's fields, plus source/verification/legal_basis — built once.

    `name` is not here: it is the node's own `name` column, not a property.
    """
    return {
        "kategori_risiko": group.kategori_risiko,
        "skala_usaha": group.skala_usaha,
        "jangka_waktu": group.jangka_waktu,
        "kewajiban": group.kewajiban,
        "persyaratan": group.persyaratan,
        "kewenangan": group.kewenangan,
        "scope_uraian": group.scope_uraian,
        "fiktif_positif": group.fiktif_positif,
        "pp28_row_indexes": group.pp28_row_indexes,
        "sertifikat_standar_verification": group.sertifikat_standar_verification,
        "source": NEW_LICENCE_SOURCE_COLLECTION,
        "legal_basis": LEGAL_BASIS["instrument"],
    }


def target_entity_id(code: str, node_properties: dict) -> str:
    """§5.3: code-scoped id — 0 collisions measured (round 3 #6, folded)."""
    digest = hashlib.sha256(canonical_json(node_properties).encode("utf-8")).hexdigest()[:12]
    return f"perizinan:pp28v10:{code}:{digest}"


def decode_jsonb(value: Any) -> Any:
    """Decode a `jsonb` column value regardless of the driver's codec state.

    Never "byte-equal" (round 3 #6): `JSONB` normalises whitespace, drops
    duplicate keys and reorders them on write.
    """
    if isinstance(value, (bytes, bytearray)):
        raise ShapeDefect("jsonb value is bytes — never compare raw bytes (W89 discipline)")
    if isinstance(value, str):
        return json.loads(value)
    return value


def validate_existing_target(
    entity_id: str,
    existing_entity_type: str,
    existing_name: str,
    existing_properties_raw: Any,
    expected_name: str,
    expected_properties: dict,
) -> None:
    """§5.3: on an existing `entity_id`, validate by DECODED value, never overwrite."""
    decoded = decode_jsonb(existing_properties_raw)
    if existing_entity_type != "perizinan" or existing_name != expected_name or decoded != expected_properties:
        raise Refusal(
            f"{entity_id}: an existing node's content differs from the derived one — refusing, never overwriting",
        )


# =============================================================================
# §5.2 — state classification and §5.7 idempotence (pure, no DB)
# =============================================================================


def admitted_targets(
    edges: list[tuple[str, str, str]],
    exclude: frozenset[str] = frozenset(),
) -> list[tuple[str, str]]:
    """§1's admission predicate, the router's own — `(target_id, name)` pairs.

    `edges` is `(target_entity_id, target_entity_type, target_name)`. `exclude`
    lets a caller compute Table B (post-lot) by dropping the placeholder ids
    even where a run hasn't deleted them yet.
    """
    out: list[tuple[str, str]] = []
    for target_id, target_type, target_name in edges:
        if target_id in exclude:
            continue
        kind = classify_requires_target(target_type)
        if kind == "license" and permit_name_verdict(target_id, target_name) == "permit":
            out.append((target_id, target_name))
    return out


def classify_state(admitted_count: int, status: str | None) -> str:
    """§2's four disjoint states of a code, under the router's predicate."""
    status = status or "REGULATED"
    if admitted_count == 0 and status == "PENDING_REGULATION":
        return "S1"
    if admitted_count == 0 and status == "REGULATED":
        return "S2"
    if admitted_count >= 1 and status == "PENDING_REGULATION":
        return "S3"
    if admitted_count >= 1 and status == "REGULATED":
        return "legacy_served"
    return "other"


def s3_comparison(rendered_names: list[str], derived_names: list[str]) -> dict:
    """§5.2: the rendered-vs-derived name sets an S3 code is judged by."""
    rendered_set, derived_set = set(rendered_names), set(derived_names)
    return {
        "match": rendered_set == derived_set,
        "rendered": sorted(rendered_set),
        "derived": sorted(derived_set),
    }


def digest_of_set(entity_ids: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(entity_ids)).encode("utf-8")).hexdigest()


@dataclass
class IdempotenceVerdict:
    status: str  # "UNCURED" | "CURED" | "DRIFTED"
    detail: str


def classify_idempotence(
    derived_ids: list[str],
    existing_ids: list[str],
    payloads_match: bool,
    current_status: str | None,
    cure_digest: str | None,
) -> IdempotenceVerdict:
    """§5.7: UNCURED / CURED / DRIFTED, decided from the graph, not the marker."""
    if not existing_ids:
        return IdempotenceVerdict("UNCURED", "no perizinan:pp28v10 targets on the graph yet")
    if sorted(existing_ids) != sorted(derived_ids):
        return IdempotenceVerdict(
            "DRIFTED",
            f"target set differs: existing={sorted(existing_ids)} derived={sorted(derived_ids)}",
        )
    if not payloads_match:
        return IdempotenceVerdict("DRIFTED", "a target's decoded properties differ from the derived value")
    expected_digest = digest_of_set(derived_ids)
    if current_status != "REGULATED" or cure_digest != expected_digest:
        return IdempotenceVerdict(
            "DRIFTED",
            f"status={current_status!r} digest={cure_digest!r} expected={expected_digest!r}",
        )
    return IdempotenceVerdict("CURED", "targets, payloads, status and digest all match — 0 writes")


def check_eligibility(
    code: str,
    record: dict | None,
    allowlist: frozenset[str],
    phase: str,
    node_exists: bool,
    placeholder_present: bool,
) -> list[dict]:
    """§5 item 1/§2 ordering rule: refuse in order, return canonical rows on pass."""
    if not node_exists:
        raise Refusal(f"{code}: no kbli:{code} node — run --create-missing-node first")
    if placeholder_present:
        raise Refusal(f"{code}: still carries a placeholder edge — run --placeholders-only first (spec §2 ordering)")
    if record is None:
        raise Refusal(f"{code}: not in the canonical dataset")
    rows = record.get("per_skala") or []
    if not rows:
        raise Refusal(f"{code}: canonical per_skala is [] — kg_kbli_license_fix.py's job, not this script's")
    if code in allowlist:
        raise Refusal(f"{code}: on the NOT_APPLICABLE_OSS allowlist — refusing")
    if is_non_oss_issued(rows) and phase != "1b":
        raise Refusal(f"{code}: non-OSS-issued (spec §3) — refuses under --phase 1a; needs --phase 1b")
    return rows


@dataclass
class BuildPlan:
    code: str
    action: str  # build | relabel | skip_s3 | skip_legacy | cured | drifted
    groups: list[LicenceGroup] = field(default_factory=list)
    targets: dict[str, dict] = field(default_factory=dict)  # entity_id -> node_properties
    edges: list[str] = field(default_factory=list)  # target entity_ids, derivation order
    pp28_sources: list[str] | None = None
    detail: str = ""


def plan_build(
    code: str,
    record: dict | None,
    allowlist: frozenset[str],
    phase: str,
    node_exists: bool,
    placeholder_present: bool,
    admitted: list[tuple[str, str]],
    current_status: str | None,
    existing_pp28_targets: dict[str, dict],
    cure_marker: dict | None,
) -> BuildPlan:
    """The single pure decision function build mode runs per `--only` code.

    Idempotence (§5.7) is decided BEFORE eligibility/state (§5.2's own
    ordering: "CURED/DRIFTED are decided before any of the above") — a code
    that is already correctly cured must not be re-refused by a later
    allowlist/phase check that has nothing to do with its current state.
    The one exception is the placeholder-edge ordering rule (§2/§5 item 8):
    it is a run-level precondition, not a business-eligibility refusal, so
    it is checked first and unconditionally — a stale placeholder edge is
    never excused by a CURED/DRIFTED verdict.

    Deriving the D set for idempotence does not require passing the
    eligibility gate: `rows` is read straight off the canonical record
    (`[]` when the code is missing from canonical entirely), so a code that
    is allowlisted, non-OSS-issued under phase 1a, or absent from the
    canonical dataset can still be classified CURED/DRIFTED from what the
    graph already carries.
    """
    if placeholder_present:
        raise Refusal(f"{code}: still carries a placeholder edge — run --placeholders-only first (spec §2 ordering)")

    candidate_rows = (record.get("per_skala") or []) if record else []
    groups = derive_licence_groups(code, candidate_rows) if candidate_rows else []
    targets: dict[str, dict] = {}
    for g in groups:
        props = build_node_properties(g)
        targets[target_entity_id(code, props)] = props
    derived_ids = sorted(targets)

    payloads_match = all(
        existing_pp28_targets.get(eid) == targets.get(eid) for eid in derived_ids if eid in existing_pp28_targets
    )
    idem = classify_idempotence(
        derived_ids=derived_ids,
        existing_ids=sorted(existing_pp28_targets),
        payloads_match=payloads_match,
        current_status=current_status,
        cure_digest=(cure_marker or {}).get("digest"),
    )
    if idem.status == "CURED":
        return BuildPlan(code, "cured", groups, {}, [], None, idem.detail)
    if idem.status == "DRIFTED":
        return BuildPlan(code, "drifted", groups, targets, derived_ids, None, idem.detail)

    # UNCURED: the code has no (or no matching) pp28v10 targets on the graph
    # yet, so the §5 item 1/§2 eligibility gate applies in full.
    check_eligibility(code, record, allowlist, phase, node_exists, placeholder_present)

    admitted_count = len(admitted)
    pp28_sources = [str(s) for s in record.get("pp28_sources")] if record and record.get("pp28_sources") else None
    state = classify_state(admitted_count, current_status)
    if state == "legacy_served":
        raise Refusal(f"{code}: legacy-served (admitted>=1, REGULATED) — needs --replace-legacy (Phase 2, refused)")
    if state == "other":
        raise Refusal(f"{code}: unexpected admitted={admitted_count} status={current_status!r} — refusing")
    if state == "S3":
        cmp = s3_comparison([name for _, name in admitted], [g.name for g in groups])
        if cmp["match"]:
            return BuildPlan(code, "relabel", groups, {}, [], pp28_sources, f"S3 exact match — relabel only: {cmp}")
        return BuildPlan(code, "skip_s3", groups, {}, [], None, f"S3 mismatch — nothing written: {cmp}")
    return BuildPlan(code, "build", groups, targets, derived_ids, pp28_sources, f"{state}: {len(targets)} target(s)")


def _assert_legal_basis(legal_basis: dict) -> None:
    """§4.1: `--apply` refuses outright if the legal-basis constant is incomplete."""
    required = {"instrument", "pdf_sha256", "tiers", "Rendah", "Menengah Rendah", "Menengah Tinggi", "Tinggi"}
    if not required.issubset(legal_basis):
        raise Refusal("LEGAL_BASIS constant incomplete — --apply refused (spec §4.1 mechanical gate)")


# =============================================================================
# I/O — dataset/allowlist loading, DB reads and writes
# =============================================================================


def _looks_like_local_path(source: str) -> bool:
    return not source.startswith(("http://", "https://")) and Path(source).exists()


async def _fetch_bytes(source: str) -> bytes:
    if _looks_like_local_path(source):
        return Path(source).read_bytes()
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(source)
        r.raise_for_status()
        return r.content


async def load_dataset(source: str) -> tuple[dict[str, dict], str]:
    raw = await _fetch_bytes(source)
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)["data"]
    logger.info("dataset: %d codes, sha256=%s", len(data), digest[:16])
    return {str(r.get("kode_kbli_2025")): r for r in data}, digest


async def load_allowlist(source: str) -> frozenset[str]:
    raw = await _fetch_bytes(source)
    data = json.loads(raw)
    codes = frozenset(data["codes"])
    logger.info("allowlist: %d NOT_APPLICABLE_OSS codes", len(codes))
    return codes


async def _node_exists(conn: asyncpg.Connection, code: str, *, lock: bool) -> bool:
    sql = "SELECT 1 FROM kg_nodes WHERE entity_id = $1" + (" FOR UPDATE" if lock else "")
    return await conn.fetchval(sql, f"kbli:{code}") is not None


async def _edge_targets(conn: asyncpg.Connection, code: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT target_entity_id FROM kg_edges WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES'",
        f"kbli:{code}",
    )
    return [r["target_entity_id"] for r in rows]


async def _requires_targets_full(conn: asyncpg.Connection, code: str) -> list[tuple[str, str, str]]:
    rows = await conn.fetch(
        "SELECT e.target_entity_id, n.entity_type, n.name FROM kg_edges e "
        "JOIN kg_nodes n ON n.entity_id = e.target_entity_id "
        "WHERE e.source_entity_id = $1 AND e.relationship_type = 'REQUIRES'",
        f"kbli:{code}",
    )
    return [(r["target_entity_id"], r["entity_type"], r["name"]) for r in rows]


async def _kbli_node_properties(conn: asyncpg.Connection, code: str) -> dict | None:
    row = await conn.fetchrow("SELECT properties FROM kg_nodes WHERE entity_id = $1", f"kbli:{code}")
    if row is None:
        return None
    props = decode_jsonb(row["properties"])
    # A node whose `properties` is a scalar must not crash the read (same
    # defense as kbli_notebook.py's inspect_kbli — 67 such kbli rows measured).
    return props if isinstance(props, dict) else {}


async def _existing_pp28v10_targets(conn: asyncpg.Connection, code: str) -> dict[str, dict]:
    rows = await conn.fetch(
        "SELECT entity_id, properties FROM kg_nodes WHERE entity_id LIKE $1",
        f"perizinan:pp28v10:{code}:%",
    )
    return {r["entity_id"]: decode_jsonb(r["properties"]) for r in rows}


async def apply_placeholder_plan(conn: asyncpg.Connection, plan: PlaceholderPlan, *, run_id: str, at: str) -> int:
    """Archive then delete, in one transaction on the locked node row."""
    entity_id = f"kbli:{plan.code}"
    async with conn.transaction():
        await _node_exists(conn, plan.code, lock=True)
        entries = [{"target": t, "at": at, "run": run_id, "reason": "placeholder"} for t in plan.remove]
        await conn.execute(
            "UPDATE kg_nodes SET properties = properties || jsonb_build_object($2::text, "
            "COALESCE(properties->$2::text, '[]'::jsonb) || $3::text::jsonb), updated_at = NOW() WHERE entity_id = $1",
            entity_id,
            ARCHIVE_KEY,
            json.dumps(entries),
        )
        tag = await conn.execute(
            "DELETE FROM kg_edges WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES' "
            "AND target_entity_id = ANY($2::text[])",
            entity_id,
            plan.remove,
        )
        deleted = int(tag.split()[-1])
        if deleted < len(plan.remove):
            raise RuntimeError(f"{plan.code}: planned {len(plan.remove)} deletions, tag says {tag} — rolling back")
    return deleted


async def apply_missing_node(conn: asyncpg.Connection, plan: MissingNodePlan) -> None:
    async with conn.transaction():
        tag = await conn.execute(
            "INSERT INTO kg_nodes (entity_id, entity_type, name, name_id, description, properties, "
            "confidence, source_collection) VALUES ($1, 'kbli', $2, $2, $3, $4::text::jsonb, 1.0, $5) "
            "ON CONFLICT (entity_id) DO NOTHING",
            f"kbli:{plan.code}",
            plan.name,
            plan.description,
            json.dumps(plan.properties, ensure_ascii=False),
            NEW_NODE_SOURCE_COLLECTION,
        )
        if tag != "INSERT 0 1":
            raise RuntimeError(f"{plan.code}: expected INSERT 0 1, got {tag} — rolling back")


async def apply_build_plan(conn: asyncpg.Connection, code: str, plan: BuildPlan, *, run_id: str, at: str) -> None:
    """§5.6: one transaction — target inserts, edge inserts, node update, or nothing."""
    entity_id = f"kbli:{code}"
    async with conn.transaction():
        await conn.fetchval("SELECT 1 FROM kg_nodes WHERE entity_id = $1 FOR UPDATE", entity_id)

        if plan.action == "relabel":
            # §5.5 node-update fields, minus `_licensing_cure` (declared limit, PR
            # body §"Rework 1"): an S3 exact-match relabel's target set is the
            # LEGACY admitted ids, not `perizinan:pp28v10:` ones, so §5.7's
            # digest-over-derived-ids cannot classify this code CURED on a
            # rerun — a marker whose digest names ids that do not exist on
            # this node would be a false claim.
            skala_union = [s for s in SCALE_ORDER if any(s in g.skala_usaha for g in plan.groups)]
            set_clauses = "'licensing_status','REGULATED','skala_usaha',$2::text::jsonb"
            relabel_params: list[Any] = [entity_id, json.dumps(skala_union)]
            if plan.pp28_sources:
                set_clauses += ",'pp28_sources',$3::text::jsonb"
                relabel_params.append(json.dumps(plan.pp28_sources))
            await conn.execute(
                f"UPDATE kg_nodes SET properties = properties || jsonb_build_object({set_clauses}), "
                "updated_at = NOW() WHERE entity_id = $1",
                *relabel_params,
            )
            return
        if plan.action != "build":
            return  # skip_s3 | skip_legacy | cured | drifted — nothing written

        name_by_eid = {target_entity_id(code, build_node_properties(g)): g.name for g in plan.groups}
        for eid, props in plan.targets.items():
            tag = await conn.execute(
                "INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, "
                "confidence, source_collection) VALUES ($1, 'perizinan', $2, NULL, $3::text::jsonb, 1.0, $4) "
                "ON CONFLICT (entity_id) DO NOTHING",
                eid,
                name_by_eid[eid],
                json.dumps(props, ensure_ascii=False),
                NEW_LICENCE_SOURCE_COLLECTION,
            )
            if tag == "INSERT 0 0":
                row = await conn.fetchrow("SELECT entity_type, name, properties FROM kg_nodes WHERE entity_id = $1", eid)
                validate_existing_target(eid, row["entity_type"], row["name"], row["properties"], name_by_eid[eid], props)
            relationship_id = f"{entity_id}|REQUIRES|{eid}"
            natural_dup = await conn.fetchval(
                "SELECT 1 FROM kg_edges WHERE source_entity_id = $1 AND target_entity_id = $2 "
                "AND relationship_type = 'REQUIRES'",
                entity_id,
                eid,
            )
            if not natural_dup:
                await conn.execute(
                    "INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, "
                    "relationship_type, properties, confidence, source_collection) "
                    "VALUES ($1, $2, $3, 'REQUIRES', $4::text::jsonb, 1.0, $5) ON CONFLICT (relationship_id) DO NOTHING",
                    relationship_id,
                    entity_id,
                    eid,
                    json.dumps(props, ensure_ascii=False),
                    NEW_LICENCE_SOURCE_COLLECTION,
                )

        skala_union = [s for s in SCALE_ORDER if any(s in g.skala_usaha for g in plan.groups)]
        cure_marker = {
            "run": run_id,
            "rows": sum(len(g.pp28_row_indexes) for g in plan.groups),
            "licences": len(plan.targets),
            "digest": digest_of_set(plan.edges),
            "at": at,
        }
        set_clauses = "'licensing_status','REGULATED','skala_usaha',$2::text::jsonb,'_licensing_cure',$3::text::jsonb"
        params: list[Any] = [entity_id, json.dumps(skala_union), json.dumps(cure_marker, ensure_ascii=False)]
        if plan.pp28_sources:
            set_clauses += ",'pp28_sources',$4::text::jsonb"
            params.append(json.dumps(plan.pp28_sources))
        await conn.execute(
            f"UPDATE kg_nodes SET properties = properties || jsonb_build_object({set_clauses}), "
            "updated_at = NOW() WHERE entity_id = $1",
            *params,
        )


# =============================================================================
# --census (read-only)
# =============================================================================


def _both_store_codes(by_code: dict[str, dict], statuses: dict[str, str]) -> list[str]:
    return sorted(
        code
        for code, record in by_code.items()
        if (record.get("per_skala") or []) and code in statuses
    )


def _state_counts(
    codes: list[str],
    statuses: dict[str, str],
    edges: dict[str, list[tuple[str, str, str]]],
    *,
    exclude_placeholder: bool,
) -> dict[str, int]:
    counts: dict[str, int] = {"S1": 0, "S2": 0, "S3": 0, "legacy_served": 0, "other": 0}
    exclude = PLACEHOLDER_TARGETS if exclude_placeholder else frozenset()
    for code in codes:
        admitted = admitted_targets(edges.get(code, []), exclude=exclude)
        state = classify_state(len(admitted), statuses.get(code))
        counts[state] = counts.get(state, 0) + 1
    return counts


async def run_census(dsn: str, dataset_source: str, allowlist_source: str) -> int:
    by_code, _ = await load_dataset(dataset_source)
    allowlist = await load_allowlist(allowlist_source)

    conn = await asyncpg.connect(dsn)
    try:
        # Restricted to the well-formed `kbli:<5 digits>` id shape, NOT
        # `entity_type = 'kbli'` — the router's own node fetch
        # (`kbli_notebook.py`: `SELECT * FROM kg_nodes WHERE entity_id = $1`)
        # is entity_type-agnostic, and measured on PROD this turn 10 such
        # nodes carry `entity_type = 'kbli_code'` instead of `'kbli'` (e.g.
        # 70201, 56101) — filtering on the type would have wrongly counted
        # them as one-store/no-KG-node. The id shape alone also excludes the
        # ~10K shadow/fragment ids (`005_02`, `01b286`, … — spec §6's
        # underscore shadow-id family plus other import debris).
        status_rows = await conn.fetch(
            "SELECT entity_id, properties FROM kg_nodes WHERE entity_id ~ '^kbli:[0-9]{5}$'",
        )
        statuses: dict[str, str] = {}
        for r in status_rows:
            props = decode_jsonb(r["properties"])
            # A node whose `properties` is a scalar (measured: kbli_notebook.py's
            # own comment — 67 such rows for entity_type='kbli') must not crash
            # the census; it resolves to the router's own default.
            if not isinstance(props, dict):
                props = {}
            statuses[r["entity_id"][len("kbli:"):]] = props.get("licensing_status", "REGULATED")

        edge_rows = await conn.fetch(
            "SELECT e.source_entity_id, e.target_entity_id, n.entity_type AS target_entity_type, "
            "n.name AS target_name FROM kg_edges e JOIN kg_nodes n ON n.entity_id = e.target_entity_id "
            "WHERE e.relationship_type = 'REQUIRES' AND e.source_entity_id ~ '^kbli:[0-9]{5}$'",
        )
        edges: dict[str, list[tuple[str, str, str]]] = {}
        for r in edge_rows:
            code = r["source_entity_id"][len("kbli:"):]
            edges.setdefault(code, []).append((r["target_entity_id"], r["target_entity_type"], r["target_name"]))
    finally:
        await conn.close()

    both = _both_store_codes(by_code, statuses)
    table_a = _state_counts(both, statuses, edges, exclude_placeholder=False)
    table_b = _state_counts(both, statuses, edges, exclude_placeholder=True)

    eligible_b: list[str] = []
    non_oss = 0
    for code in both:
        admitted = admitted_targets(edges.get(code, []), exclude=PLACEHOLDER_TARGETS)
        state = classify_state(len(admitted), statuses.get(code))
        if state not in ("S1", "S2"):
            continue
        if code in allowlist:
            continue
        rows = by_code[code].get("per_skala") or []
        if is_non_oss_issued(rows):
            non_oss += 1
        else:
            eligible_b.append(code)

    histogram: dict[int, int] = {}
    for code in eligible_b:
        try:
            groups = derive_licence_groups(code, by_code[code].get("per_skala") or [])
        except Refusal as exc:
            logger.warning("census: %s malformed, excluded from histogram — %s", code, exc)
            continue
        histogram[len(groups)] = histogram.get(len(groups), 0) + 1

    kg_only = sorted(set(statuses) - set(by_code))
    canonical_only = sorted(
        code for code, record in by_code.items() if (record.get("per_skala") or []) and code not in statuses
    )

    logger.info("=== Table A (live) — %d codes ===", len(both))
    logger.info("  %s", table_a)
    logger.info("=== Table B (post-lot, placeholders excluded) — %d codes ===", len(both))
    logger.info("  %s", table_b)
    logger.info("Phase split (Table B S1+S2, excl. allowlist): OSS-issued=%d non-OSS=%d", len(eligible_b), non_oss)
    logger.info("Licence histogram (OSS-issued S1/S2, licences per code): %s", dict(sorted(histogram.items())))
    logger.info("§2.3 one-store: %d KG-only codes (absent from canonical) — %s", len(kg_only), kg_only)
    logger.info("§2.3 one-store: %d canonical codes with no KG node — %s", len(canonical_only), canonical_only)

    if table_a != table_b:
        logger.warning("Table A != Table B — a placeholder edge is still shaping a code's classification")
        return 4
    return 0


# =============================================================================
# CLI
# =============================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default=None, help="comma-separated 5-digit codes (never swept); required except --census")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--placeholders-only", action="store_true")
    mode.add_argument("--create-missing-node", action="store_true")
    mode.add_argument("--census", action="store_true")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--phase", choices=("1a", "1b"), default="1a", help="build-mode phase (default 1a)")
    ap.add_argument("--replace-legacy", action="store_true", help="Phase 2, not measured — always refused")
    ap.add_argument("--dataset", default=DATASET_URL, help="canonical dataset: local path or commit-pinned raw URL")
    ap.add_argument("--allowlist", default=ALLOWLIST_URL, help="NOT_APPLICABLE_OSS list: local path or raw URL")
    ap.add_argument("--cure-run", default=None, help="run id recorded in the archive / cure marker")
    args = ap.parse_args(argv)

    if args.replace_legacy:
        ap.error("--replace-legacy is refused — Phase 2 is not measured (spec §6)")
    if args.phase == "1b" and not PHASE_1B_ENABLED:
        ap.error("--phase 1b is refused — PHASE_1B_ENABLED is False until spec §8 F2 ships")
    if args.census:
        if args.only:
            ap.error("--census is a read-only sweep — it does not take --only")
        args.codes = []
        return args
    if not args.only:
        ap.error("--only is mandatory (no sweep, ever) unless --census")
    args.codes = [c.strip() for c in args.only.split(",") if c.strip()]
    if not args.codes:
        ap.error("--only produced an empty code list")
    if args.apply and args.create_missing_node and args.dataset == DATASET_URL:
        ap.error("--apply with the unpinned default dataset is refused — pass a commit-pinned URL or a local file")
    if args.apply:
        try:
            _assert_legal_basis(LEGAL_BASIS)
        except Refusal as exc:
            ap.error(str(exc))
    return args


async def _run_build_mode(conn: asyncpg.Connection, args: argparse.Namespace, run_id: str, at: str) -> tuple[int, int, int, int]:
    by_code, _ = await load_dataset(args.dataset)
    allowlist = await load_allowlist(args.allowlist)
    acted = skipped = refused = drifted = 0
    for code in args.codes:
        node_exists = await _node_exists(conn, code, lock=False)
        edge_targets_full = await _requires_targets_full(conn, code) if node_exists else []
        placeholder_present = any(t[0] in PLACEHOLDER_TARGETS for t in edge_targets_full)
        admitted = admitted_targets(edge_targets_full)
        props = await _kbli_node_properties(conn, code) if node_exists else None
        current_status = (props or {}).get("licensing_status")
        cure_marker = (props or {}).get("_licensing_cure")
        existing_targets = await _existing_pp28v10_targets(conn, code) if node_exists else {}
        try:
            plan = plan_build(
                code,
                by_code.get(code),
                allowlist,
                args.phase,
                node_exists,
                placeholder_present,
                admitted,
                current_status,
                existing_targets,
                cure_marker,
            )
        except Refusal as exc:
            logger.warning("REFUSED %s", exc)
            refused += 1
            continue
        logger.info("%s: action=%s | %s", code, plan.action, plan.detail)
        if plan.action == "drifted":
            drifted += 1
            continue
        if plan.action in ("cured", "skip_s3", "skip_legacy"):
            skipped += 1
            continue
        acted += 1
        if args.apply:
            await apply_build_plan(conn, code, plan, run_id=run_id, at=at)
    return acted, skipped, refused, drifted


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = args.cure_run or f"kbli_phase1a:{at[:10]}"
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    if args.census:
        return await run_census(dsn, args.dataset, args.allowlist)

    by_code: dict[str, dict] = {}
    digest = ""
    if args.create_missing_node:
        by_code, digest = await load_dataset(args.dataset)

    conn = await asyncpg.connect(dsn)
    acted = skipped = refused = drifted = 0
    try:
        if args.placeholders_only or args.create_missing_node:
            for code in args.codes:
                try:
                    exists = await _node_exists(conn, code, lock=False)
                    if args.placeholders_only:
                        plan = plan_placeholder_removal(code, exists, await _edge_targets(conn, code))
                        if not plan.remove:
                            logger.info("%s: no placeholder edge — nothing to do", code)
                            skipped += 1
                            continue
                        logger.info(
                            "%s: %s placeholder edge(s) → %s",
                            code,
                            "DELETE+ARCHIVE" if args.apply else "would delete",
                            plan.remove,
                        )
                        if args.apply:
                            n = await apply_placeholder_plan(conn, plan, run_id=run_id, at=at)
                            logger.info("%s: deleted %d, archived under %s", code, n, ARCHIVE_KEY)
                    else:
                        node = build_missing_node(code, by_code.get(code), exists, run_id=run_id, at=at, dataset_sha256=digest)
                        logger.info(
                            "%s: %s node name=%r status=%s skala=%s keys=%s",
                            code,
                            "INSERT" if args.apply else "would insert",
                            node.name,
                            node.properties["licensing_status"],
                            node.properties["skala_usaha"],
                            sorted(node.properties),
                        )
                        if args.apply:
                            await apply_missing_node(conn, node)
                    acted += 1
                except Refusal as exc:
                    logger.warning("REFUSED %s", exc)
                    refused += 1
        else:
            acted, skipped, refused, drifted = await _run_build_mode(conn, args, run_id, at)
    finally:
        await conn.close()

    verb = "APPLIED" if args.apply else "DRY-RUN"
    logger.info(
        "%s: %d acted | %d nothing-to-do | %d refused | %d drifted (of %d asked)",
        verb,
        acted,
        skipped,
        refused,
        drifted,
        len(args.codes),
    )
    if drifted:
        return 4
    return 2 if refused else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(asyncio.run(main()))
