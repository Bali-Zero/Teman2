"""Public tax-calendar clearance: which catalog rules a Tax Department reviewer released.

Pure: reads one YAML file and the catalog, no database, no network. A rule is shown to anonymous
visitors only when it is verified, carries no needs_review_reason and has a review whose
rule_fingerprint matches the rule as it stands now.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from backend.services.compliance.obligations_register import ObligationRule, load_catalog

DEFAULT_REVIEW_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "tax_calendar_public_review.yaml"
)
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FILE_KEYS = frozenset({"version", "reviews"})
_REVIEW_KEYS = frozenset({"rule_id", "reviewer", "reviewed_on", "rule_fingerprint"})


@dataclass(frozen=True)
class PublicReview:
    rule_id: str
    reviewer: str
    reviewed_on: date
    rule_fingerprint: str


def _canonical(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canonical(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def rule_fingerprint(rule: ObligationRule) -> str:
    """sha256 over the whole rule, so any edited field changes it."""
    blob = json.dumps(_canonical(rule), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _parse_review(raw: Any, index: int, catalog_ids: set[str]) -> PublicReview:
    where = f"review #{index}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be a mapping")
    extra = set(raw) - _REVIEW_KEYS
    missing = _REVIEW_KEYS - set(raw)
    if extra:
        raise ValueError(f"{where}: unknown keys {sorted(extra)}")
    if missing:
        raise ValueError(f"{where}: missing keys {sorted(missing)}")
    rule_id, reviewer = raw["rule_id"], raw["reviewer"]
    if not isinstance(rule_id, str) or rule_id not in catalog_ids:
        raise ValueError(f"{where}: rule_id is not in the catalog")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError(f"{where}: reviewer must be a non-empty string")
    fingerprint = raw["rule_fingerprint"]
    if not isinstance(fingerprint, str) or not _FINGERPRINT_RE.match(fingerprint):
        raise ValueError(f"{where}: rule_fingerprint must be 64 lowercase hex characters")
    reviewed_on = raw["reviewed_on"]
    if type(reviewed_on) is date:  # an unquoted YAML date scalar
        parsed = reviewed_on
    elif isinstance(reviewed_on, str) and _ISO_DATE_RE.match(reviewed_on):
        try:
            parsed = date.fromisoformat(reviewed_on)
        except ValueError:
            raise ValueError(f"{where}: impossible reviewed_on") from None
    else:
        raise ValueError(f"{where}: reviewed_on must be YYYY-MM-DD")
    return PublicReview(rule_id, reviewer, parsed, fingerprint)


def load_public_reviews(path: str | Path = DEFAULT_REVIEW_PATH) -> dict[str, PublicReview]:
    """Load and strictly validate the review file; raise ValueError on anything malformed."""
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict) or set(doc) != _FILE_KEYS:
        raise ValueError("review file must be a mapping with exactly version and reviews")
    if doc["version"] != 1:
        raise ValueError("unsupported review file version")
    if not isinstance(doc["reviews"], list):
        raise ValueError("reviews must be a list")
    catalog_ids = {rule.id for rule in load_catalog()}
    reviews: dict[str, PublicReview] = {}
    for index, raw in enumerate(doc["reviews"]):
        review = _parse_review(raw, index, catalog_ids)
        if review.rule_id in reviews:
            raise ValueError(f"review #{index}: duplicate rule_id {review.rule_id!r}")
        reviews[review.rule_id] = review
    return reviews


def is_publicly_cleared(rule: ObligationRule, reviews: dict[str, PublicReview]) -> bool:
    review = reviews.get(rule.id)
    return (
        rule.verified
        and rule.needs_review_reason is None
        and review is not None
        and review.rule_fingerprint == rule_fingerprint(rule)
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] != "fingerprint":
        sys.stderr.write(
            "usage: python -m backend.services.compliance.tax_calendar_public_review "
            "fingerprint <rule_id>\n"
        )
        return 2
    for rule in load_catalog():
        if rule.id == argv[2]:
            sys.stdout.write(rule_fingerprint(rule) + "\n")
            return 0
    sys.stderr.write(f"unknown rule_id {argv[2]!r}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
