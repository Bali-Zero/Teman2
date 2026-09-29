import dataclasses
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

from backend.app.setup.cors_config import get_allowed_origins
from backend.services.compliance.obligations_register import ObligationRule, load_catalog
from backend.services.compliance.tax_calendar_public_review import (
    DEFAULT_REVIEW_PATH,
    PublicReview,
    is_publicly_cleared,
    load_public_reviews,
    rule_fingerprint,
)

GOOD = {
    "rule_id": "pph21_payment",
    "reviewer": "Test Signer",
    "reviewed_on": "2026-09-30",
    "rule_fingerprint": "a" * 64,
}


def _write(tmp_path: Path, reviews: list[dict]) -> Path:
    path = tmp_path / "review.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "reviews": reviews}), encoding="utf-8")
    return path


def test_shipped_file_loads_and_is_empty() -> None:
    assert load_public_reviews(DEFAULT_REVIEW_PATH) == {}


def test_valid_entry_loads(tmp_path: Path) -> None:
    reviews = load_public_reviews(_write(tmp_path, [GOOD]))

    assert reviews["pph21_payment"].reviewed_on.isoformat() == "2026-09-30"


@pytest.mark.parametrize(
    "reviews",
    [
        [{**GOOD, "extra": 1}],
        [GOOD, GOOD],
        [{**GOOD, "rule_id": "not_in_the_catalog"}],
        [{**GOOD, "rule_fingerprint": "xyz"}],
        [{**GOOD, "rule_fingerprint": "A" * 64}],
        [{**GOOD, "reviewed_on": "30/09/2026"}],
        [{**GOOD, "reviewed_on": "2026-13-45"}],
        [{k: v for k, v in GOOD.items() if k != "reviewer"}],
    ],
)
def test_loader_rejects_malformed_entries(tmp_path: Path, reviews: list[dict]) -> None:
    with pytest.raises(ValueError):
        load_public_reviews(_write(tmp_path, reviews))


def test_loader_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    path = tmp_path / "review.yaml"
    path.write_text("version: 1\nreviews: []\nextra: 1\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_public_reviews(path)


def test_fingerprint_is_stable_and_hex() -> None:
    first = next(r for r in load_catalog() if r.id == "pph21_payment")
    reloaded = next(r for r in load_catalog() if r.id == "pph21_payment")

    assert first is not reloaded
    assert rule_fingerprint(reloaded) == rule_fingerprint(first)
    assert re.fullmatch(r"[0-9a-f]{64}", rule_fingerprint(first))


def _pph21() -> ObligationRule:
    return next(r for r in load_catalog() if r.id == "pph21_payment")


def _cleared_at_own_fingerprint(rule: ObligationRule) -> dict[str, PublicReview]:
    review = PublicReview(rule.id, "Test Signer", date(2026, 9, 30), rule_fingerprint(rule))
    return {rule.id: review}


def _different_value(rule: ObligationRule, name: str) -> object:
    alternatives = {
        "id": "pph21_payment_edited",
        "name": rule.name + " (edited)",
        "authority": rule.authority + " (edited)",
        "legal_source": rule.legal_source + " (edited)",
        "verified": not rule.verified,
        "applies_if": rule.applies_if[:-1],
        "due": dataclasses.replace(rule.due, day=(rule.due.day or 1) + 1),
        "needs_review_reason": "edited after review",
        "trigger": "edited after review",
        "notes": "edited after review",
    }
    assert set(alternatives) == {f.name for f in dataclasses.fields(ObligationRule)}, (
        "ObligationRule gained or lost a field: give it a replacement value here"
    )
    return alternatives[name]


@pytest.mark.parametrize("field", [f.name for f in dataclasses.fields(ObligationRule)])
def test_fingerprint_changes_when_any_rule_field_changes(field: str) -> None:
    rule = _pph21()
    edited = dataclasses.replace(rule, **{field: _different_value(rule, field)})

    assert getattr(edited, field) != getattr(rule, field)
    assert rule_fingerprint(edited) != rule_fingerprint(rule)


def test_unverified_rule_is_withheld_even_at_its_own_fingerprint() -> None:
    rule = dataclasses.replace(_pph21(), verified=False, needs_review_reason=None)

    assert not is_publicly_cleared(rule, _cleared_at_own_fingerprint(rule))


def test_verified_review_free_rule_is_cleared_at_its_own_fingerprint() -> None:
    rule = _pph21()

    assert rule.verified and rule.needs_review_reason is None
    assert is_publicly_cleared(rule, _cleared_at_own_fingerprint(rule))


def test_cli_prints_the_fingerprint() -> None:
    rule = next(r for r in load_catalog() if r.id == "pph21_payment")
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.services.compliance.tax_calendar_public_review",
            "fingerprint",
            "pph21_payment",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert out.stdout.strip() == rule_fingerprint(rule)


def test_cors_defaults_include_the_tax_origin() -> None:
    assert "https://tax.balizero.com" in get_allowed_origins()
