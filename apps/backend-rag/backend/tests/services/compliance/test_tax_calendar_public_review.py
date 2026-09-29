import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from backend.app.setup.cors_config import get_allowed_origins
from backend.services.compliance.obligations_register import load_catalog
from backend.services.compliance.tax_calendar_public_review import (
    DEFAULT_REVIEW_PATH,
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
