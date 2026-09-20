"""The chat channel's 500 says that we failed, never how.

`inspect_kbli` learned this on 2026-09-19: its catch-all stopped interpolating
`str(e)` into the response body. The ledger row that carried that cure named the
half it did not fix — "check the sibling handlers in the same module and in
`kbli_notebook_chat.py` before closing" — and this is that half. `chat_kbli`'s
catch-all ended `detail=f"AI Engine error: {e!s}"`, so a fault anywhere in a long
route handed the caller whatever the failing layer happened to say: Postgres
(table and column names), Qdrant (collection and host:port), or the model provider
(an upstream error body with model ids and quota state). The route needs no
authentication, and the WhatsApp bot sits behind it.

The cure is opacity in the RESPONSE and nothing else — the log keeps the whole
string with `exc_info`, which the second guilt test asserts, because a cure that
blinded the operator to spare the client would be the same mistake facing the
other way.

The innocence half fences what the catch-all must keep doing: a healthy turn is
still a 200 with its answer, a malformed body is still a 422 that names the field,
and an `HTTPException` raised deeper in the route still reaches the client with its
own status and its own detail instead of being absorbed into the opaque 500 — that
last one is new behaviour, and it is here because an opacity cure with no
`except HTTPException: raise` above it would have silently swallowed the first
deliberate 404 anyone added to this route.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.kbli_notebook_chat as chat_module
from backend.app.dependencies import get_optional_database_pool, get_search_service

# The four things a failing layer leaks that a client has no business reading: the
# server's own words, our schema, our topology, and the upstream account state. Each
# is asserted separately so a partial cure cannot pass.
SERVER_WORDS = "syntax error at or near SELEKT"
SCHEMA_NAME = "kbli_documents_internal_v3"
TOPOLOGY = "qdrant-internal-3.flycast:6333"
UPSTREAM = "quota exceeded for project bali-zero-internal"
LEAKY_MESSAGE = f"{SERVER_WORDS} — table {SCHEMA_NAME} on {TOPOLOGY} ({UPSTREAM})"

PAYLOAD = {"query": "I want to open a restaurant in Bali", "session_id": "opacity-001"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(chat_module.router)
    app.dependency_overrides[get_search_service] = lambda: MagicMock(
        embed=AsyncMock(return_value=[0.1] * 1536)
    )
    app.dependency_overrides[get_optional_database_pool] = lambda: None

    gateway = MagicMock()
    gateway._available = True
    with patch.object(chat_module, "_llm_gateway_instance", gateway):
        yield TestClient(app, raise_server_exceptions=False)


def _raising(error):
    """Fail at the first await inside the try — the catch-all is what is under test."""
    return patch.object(chat_module, "_translate_query_for_kbli", AsyncMock(side_effect=error))


# --------------------------------------------------------------------------
# GUILT — the failing layer's words must not reach the response body
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.PostgresSyntaxError(LEAKY_MESSAGE),
        asyncpg.UndefinedColumnError(LEAKY_MESSAGE),
        RuntimeError(LEAKY_MESSAGE),
        ValueError(LEAKY_MESSAGE),
    ],
    ids=["syntax_error", "undefined_column", "runtime_error", "value_error"],
)
@pytest.mark.parametrize(
    "leak",
    [SERVER_WORDS, SCHEMA_NAME, TOPOLOGY, UPSTREAM],
    ids=["server_words", "schema", "topology", "upstream"],
)
def test_the_five_hundred_body_carries_none_of_the_engines_words(client, error, leak):
    with _raising(error):
        response = client.post("/kbli-notebook/chat", json=PAYLOAD)

    assert response.status_code == 500, response.text
    assert leak not in response.text


def test_the_operator_still_reads_the_whole_string_in_the_log(client, caplog):
    """Opacity is not amnesia: the cure moves the detail, it does not delete it."""
    with _raising(RuntimeError(LEAKY_MESSAGE)), caplog.at_level(logging.ERROR):
        response = client.post("/kbli-notebook/chat", json=PAYLOAD)

    assert response.status_code == 500
    assert LEAKY_MESSAGE in caplog.text


# --------------------------------------------------------------------------
# INNOCENCE — what the catch-all must keep doing
# --------------------------------------------------------------------------


def test_an_http_exception_raised_deeper_in_the_route_is_not_absorbed(client):
    with patch.object(
        chat_module,
        "_translate_query_for_kbli",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="KBLI code 99999 not found")),
    ):
        response = client.post("/kbli-notebook/chat", json=PAYLOAD)

    assert response.status_code == 404, response.text
    assert "99999" in response.json()["detail"]


def test_a_malformed_body_is_still_a_422_that_names_the_field(client):
    response = client.post("/kbli-notebook/chat", json={"session_id": "opacity-002"})

    assert response.status_code == 422, response.text
    assert "query" in response.text


def test_a_healthy_turn_is_still_a_200(client):
    """Innocence for every test above: they must fail for the ERROR, not the route."""
    with (
        patch.object(chat_module, "_translate_query_for_kbli", AsyncMock(return_value="restoran")),
        patch.object(chat_module, "_search_kbli_qdrant", AsyncMock(return_value=[])),
        patch.object(
            chat_module,
            "_generate_kbli_explanation_gemini",
            AsyncMock(return_value="Restoran is KBLI 56101."),
        ),
    ):
        response = client.post("/kbli-notebook/chat", json=PAYLOAD)

    assert response.status_code == 200, response.text
    assert response.json()["answer"]
