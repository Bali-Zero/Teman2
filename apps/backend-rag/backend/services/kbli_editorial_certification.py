"""Cryptographic publication gate for KBLI generated/editorial prose.

The canonical catalogue intentionally retains legacy prose for adjudication.
Even a complete PMA locator tuple is not enough to make that prose public: a
reviewed block is publishable only while both its PMA fingerprint and its exact
stable-JSON content hash still match the checked-in certification registry.

This module mirrors the TypeScript gate used by Mouth and the standalone KBLI
navigator.  Keeping the implementation here makes the Qdrant and knowledge-
graph writers fail closed under the same contract instead of trusting a bare
``pma_verification_status == \"located\"`` check.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.services.kbli_pma_disclosure import PMA_LOCATED, disclose_pma

REGISTRY_ENV = "KBLI_EDITORIAL_CERTIFICATIONS_FILE"
REGISTRY_RELATIVE_PATH = Path("data/kbli-filiera/pma-editorial-certifications.json")
REGISTRY_SCHEMA_VERSION = 1
REGISTRY_HASH_ALGORITHM = "sha256-stable-json-v1"
CERTIFICATION_SECTIONS = frozenset({"canonicalIntel", "mouthGold", "standaloneGold"})

_STATUS_MAP = {
    "TERBUKA": "open",
    "TERBATAS": "restricted",
    "TERTUTUP": "closed",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _public_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _stable_value(value: Any) -> Any:
    """Normalize values to the semantics of the TypeScript stable JSON hash."""
    if isinstance(value, Mapping):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_stable_value(item) for item in value]
    if isinstance(value, float):
        # JSON.stringify serializes non-finite numbers as null, -0 as 0, and
        # integral doubles without a trailing `.0`.
        if not math.isfinite(value):
            return None
        if value == 0:
            return 0
        if value.is_integer():
            return int(value)
    return value


def stable_editorial_sha256(value: Any) -> str:
    """Return the ``sha256-stable-json-v1`` digest used by the TS clients."""
    serialized = json.dumps(
        _stable_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def pma_editorial_fingerprint(record: Mapping[str, Any]) -> str:
    """Hash every public PMA field that generated prose could repeat."""
    pma = disclose_pma(record)
    located = pma["pma_verification_status"] == PMA_LOCATED
    public = {
        "status": _STATUS_MAP.get(pma["pma_status"], "unknown") if located else "unknown",
        "maxForeign": pma["pma_max_asing"] if located else None,
        "condition": pma["pma_kondisi"] if located else None,
        "isPriority": pma["pma_prioritas"] is True if located else False,
        "note": pma["pma_nota"] if located else None,
        "source": _public_text(record.get("pma_source")) if located else None,
        "verificationStatus": PMA_LOCATED if located else "declared_gap",
        "officialBasis": pma["pma_official_basis"] if located else None,
        "sourceVintage": pma["pma_source_vintage"] if located else None,
        "capSpecial": pma["pma_cap_special"] is True if located else False,
        "capVerified": pma["pma_cap_verified"] is True if located else False,
        "routeTo": _public_text(record.get("pma_route_to")) if located else None,
    }
    return stable_editorial_sha256(public)


def has_publishable_pma_cap(record: Mapping[str, Any]) -> bool:
    """Return true only for an explicitly verified numeric/special PMA cap."""
    pma = disclose_pma(record)
    if pma["pma_verification_status"] != PMA_LOCATED or pma["pma_cap_verified"] is not True:
        return False
    cap = pma["pma_max_asing"]
    if isinstance(cap, bool):
        return False
    if isinstance(cap, (int, float)):
        return math.isfinite(cap)
    return cap == "special" and pma["pma_cap_special"] is True


def _registry_candidates() -> list[Path]:
    configured = os.environ.get(REGISTRY_ENV)
    if configured:
        return [Path(configured).expanduser().resolve()]

    here = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in (here.parent, *here.parents):
        candidate = parent / REGISTRY_RELATIVE_PATH
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def resolve_editorial_registry_path() -> Path:
    """Locate the registry in either the monorepo or the Fly image layout."""
    candidates = _registry_candidates()
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = "\n  ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "KBLI editorial certification registry not found. Searched:\n  " + searched
    )


def _validated_registry(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("KBLI editorial certification registry must be a JSON object")
    if payload.get("schemaVersion") != REGISTRY_SCHEMA_VERSION:
        raise ValueError("unsupported KBLI editorial certification schemaVersion")
    if payload.get("hashAlgorithm") != REGISTRY_HASH_ALGORITHM:
        raise ValueError("unsupported KBLI editorial certification hashAlgorithm")
    if not _SHA256_RE.fullmatch(str(payload.get("sourceDatasetSha256", ""))):
        raise ValueError("invalid sourceDatasetSha256 in KBLI editorial registry")

    for section_name in CERTIFICATION_SECTIONS:
        section = payload.get(section_name)
        if not isinstance(section, dict):
            raise ValueError(f"missing certification section {section_name}")
        for code, certification in section.items():
            if not isinstance(code, str) or not re.fullmatch(r"\d{5}", code):
                raise ValueError(f"invalid KBLI certification code {code!r}")
            if not isinstance(certification, dict):
                raise ValueError(f"invalid certification object for KBLI {code}")
            for field in ("pmaFingerprint", "contentSha256"):
                if not _SHA256_RE.fullmatch(str(certification.get(field, ""))):
                    raise ValueError(f"invalid {field} for KBLI {code}")
    return payload


def validate_editorial_registry(payload: Any) -> dict[str, Any]:
    """Validate an already decoded registry, including remotely fetched copies."""
    return _validated_registry(payload)


@lru_cache(maxsize=4)
def load_editorial_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load and structurally validate the fail-closed certification registry."""
    registry_path = Path(path).resolve() if path is not None else resolve_editorial_registry_path()
    with registry_path.open(encoding="utf-8") as handle:
        return _validated_registry(json.load(handle))


def assert_certified_source_dataset(
    source_bytes: bytes,
    registry: Mapping[str, Any] | None = None,
) -> None:
    """Raise unless dataset bytes are the exact snapshot reviewed by the registry."""
    active_registry = registry if registry is not None else load_editorial_registry()
    expected = active_registry.get("sourceDatasetSha256")
    actual = hashlib.sha256(source_bytes).hexdigest()
    if not isinstance(expected, str) or not hmac.compare_digest(actual, expected):
        raise ValueError(
            "canonical KBLI dataset bytes do not match the editorial review registry "
            f"(expected {expected}, got {actual})"
        )


def matches_editorial_certification(
    section: str,
    code: str,
    record: Mapping[str, Any],
    content: Any,
    registry: Mapping[str, Any] | None = None,
) -> bool:
    """Bind publication to exact reviewed PMA evidence and exact prose bytes."""
    if section not in CERTIFICATION_SECTIONS or content is None:
        return False
    if str(record.get("kode_kbli_2025") or "") != code:
        return False
    if not has_publishable_pma_cap(record):
        return False

    active_registry = registry if registry is not None else load_editorial_registry()
    certifications = active_registry.get(section)
    if not isinstance(certifications, Mapping):
        return False
    certification = certifications.get(code)
    if not isinstance(certification, Mapping):
        return False

    expected_pma = certification.get("pmaFingerprint")
    expected_content = certification.get("contentSha256")
    if not isinstance(expected_pma, str) or not isinstance(expected_content, str):
        return False
    return hmac.compare_digest(
        expected_pma,
        pma_editorial_fingerprint(record),
    ) and hmac.compare_digest(
        expected_content,
        stable_editorial_sha256(content),
    )


def neutral_kbli_chat_opener_text(code: str) -> str:
    return (
        f"Ask me about KBLI {code}: its official scope, licensing, risk, "
        "or foreign-ownership verification."
    )


def with_neutral_kbli_chat_opener(code: str, content: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a certified block and replace its legacy sales/status opener."""
    result = dict(content)
    result["zantaraOpener"] = neutral_kbli_chat_opener_text(code)
    return result


__all__ = [
    "assert_certified_source_dataset",
    "has_publishable_pma_cap",
    "load_editorial_registry",
    "matches_editorial_certification",
    "neutral_kbli_chat_opener_text",
    "pma_editorial_fingerprint",
    "resolve_editorial_registry_path",
    "stable_editorial_sha256",
    "validate_editorial_registry",
    "with_neutral_kbli_chat_opener",
]
