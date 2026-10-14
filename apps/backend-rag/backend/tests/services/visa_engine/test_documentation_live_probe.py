"""The post-deploy probe's checker: guilt (it flags) and innocence (it passes)."""

from __future__ import annotations

from typing import Any

from backend.scripts.visa_engine.documentation_live_probe import check_documentation
from backend.services.visa_engine.documentation_catalog import documentation_for

_OBSERVED = "2026-10-14T01:00:00+00:00"


def _body(*codes: str, override: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "display": {
            "candidates": [
                {"product_code": c, "documentation": (override or documentation_for(c, _OBSERVED))}
                for c in codes
            ]
        }
    }


def test_a_healthy_replay_passes() -> None:
    assert check_documentation([_body("E33F", "E31B")]) == []


def test_an_e33f_without_documentation_is_flagged() -> None:
    unknown = documentation_for("E31B", _OBSERVED)
    failures = check_documentation([_body("E33F", override=unknown), _body("E31B")])
    assert any("E33F documentation is 'UNKNOWN'" in f for f in failures)


def test_an_e31b_that_became_available_is_flagged() -> None:
    available = documentation_for("E33F", _OBSERVED)
    failures = check_documentation([_body("E33F"), _body("E31B", override=available)])
    assert any("E31B documentation is 'AVAILABLE'" in f for f in failures)


def test_an_e33f_list_without_the_penjamin_letter_is_flagged() -> None:
    bare = {**documentation_for("E33F", _OBSERVED), "requirements": [{"en": "x", "id": "y"}]}
    failures = check_documentation([_body("E33F", override=bare), _body("E31B")])
    assert any("penjamin letter" in f for f in failures)


def test_an_empty_replay_cannot_pass() -> None:
    assert len(check_documentation([])) == 2
    assert len(check_documentation([_body("E31B")])) == 1
