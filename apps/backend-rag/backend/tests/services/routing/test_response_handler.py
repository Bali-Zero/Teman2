from __future__ import annotations

import pytest

from backend.services.routing import response_handler as response_module
from backend.services.routing.response_handler import ResponseHandler


def test_classify_query_delegates_to_response_sanitizer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(response_module, "classify_query_for_rag", lambda message: "greeting")

    assert ResponseHandler().classify_query("Ciao") == "greeting"


def test_sanitize_response_delegates_with_quality_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_process_zantara_response(
        response: str,
        query_type: str,
        *,
        apply_santai: bool,
        add_contact: bool,
    ) -> str:
        captured.update(
            {
                "response": response,
                "query_type": query_type,
                "apply_santai": apply_santai,
                "add_contact": add_contact,
            },
        )
        return "Clean response"

    monkeypatch.setattr(response_module, "process_zantara_response", fake_process_zantara_response)

    result = ResponseHandler().sanitize_response(
        "Raw response",
        "business",
        apply_santai=False,
        add_contact=False,
    )

    assert result == "Clean response"
    assert captured == {
        "response": "Raw response",
        "query_type": "business",
        "apply_santai": False,
        "add_contact": False,
    }


def test_sanitize_response_returns_original_on_empty_or_sanitizer_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = ResponseHandler()

    assert handler.sanitize_response("", "business") == ""

    def fake_process_zantara_response(
        response: str,
        query_type: str,
        *,
        apply_santai: bool,
        add_contact: bool,
    ) -> str:
        raise ValueError("bad sanitizer")

    monkeypatch.setattr(response_module, "process_zantara_response", fake_process_zantara_response)

    assert handler.sanitize_response("Original", "business") == "Original"
