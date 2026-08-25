"""ToolExecutor — the end-to-end seam, exercised for get_required_documents
against a FAKE transport (never a real network — B6 law). Every gate in
``ToolExecutor.execute``'s ordered chain gets a guilt+innocence pair.

What this suite proves: the executor correctly composes flags, the F5
registry, the local scope gate, argument re-validation, auth resolution,
the network call, and untrusted-response validation into one ToolResult.

What this suite does NOT prove (stated so a reader does not over-read a
green run): there is no LIVE backend at ``/api/crm/practice-types/...``
today — see ``executor/tools/get_required_documents.py``'s own
"DISCOVERY" section — so nothing here proves this tool answers a real
question in production yet, only that the client-side machinery is
correct against whatever a backend eventually returns in this shape.
"""

from __future__ import annotations

import httpx
import pytest

from team_bot.executor.errors import ExecutorErrorCode
from team_bot.executor.http_client import BackendClient, BackendClientConfig
from team_bot.executor.tool_executor import ToolExecutor
from team_bot.loop.tool_decision import ProposedToolCall

from ._fakes import StaticTokenProvider, fake_transport, json_response

_VALID_PRINCIPAL = "USR-001"
_VALID_TOKEN_HEADERS = {"Authorization": "Bearer team-usr-001"}


def _call(tool_name: str, raw_arguments: str, *, call_id: str = "c1") -> ProposedToolCall:
    return ProposedToolCall(call_id=call_id, tool_name=tool_name, raw_arguments=raw_arguments)


def _backend_success_json() -> dict[str, object]:
    return {
        "practice_type": "limited_stay_kitas",
        "required_docs": ["passport", "passport_photo", "sponsor_letter"],
        "optional_docs": ["ktp", "npwp", "domicile_letter"],
    }


def _executor(*, transport: httpx.MockTransport, token_provider=None) -> ToolExecutor:
    client = BackendClient(BackendClientConfig(base_url="http://backend.example"), transport=transport)
    provider = token_provider if token_provider is not None else StaticTokenProvider(
        _VALID_PRINCIPAL, _VALID_TOKEN_HEADERS
    )
    return ToolExecutor(client, token_provider=provider)


def _enable_read_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_BOT_ENABLED", "true")
    monkeypatch.setenv("TEAM_BOT_READ_TOOLS_ENABLED", "true")


# ---------------------------------------------------------------------------
# 1. Feature flags — guilt (off) + innocence (on) for BOTH gating flags.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guilt_master_flag_off_denies_before_any_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEAM_BOT_ENABLED", raising=False)
    monkeypatch.setenv("TEAM_BOT_READ_TOOLS_ENABLED", "true")

    called = {"hit": False}

    def handler(request: httpx.Request) -> httpx.Response:
        called["hit"] = True
        return httpx.Response(200, json=_backend_success_json())

    executor = _executor(transport=fake_transport(handler))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.FEATURE_DISABLED.value
    assert called["hit"] is False, "network must never be reached while the master flag is off"


@pytest.mark.asyncio
async def test_guilt_read_tools_flag_off_denies_before_any_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEAM_BOT_ENABLED", "true")
    monkeypatch.delenv("TEAM_BOT_READ_TOOLS_ENABLED", raising=False)

    called = {"hit": False}

    def handler(request: httpx.Request) -> httpx.Response:
        called["hit"] = True
        return httpx.Response(200, json=_backend_success_json())

    executor = _executor(transport=fake_transport(handler))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )

    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.FEATURE_DISABLED.value
    assert called["hit"] is False


@pytest.mark.asyncio
async def test_innocence_both_flags_on_reaches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.ok is True


# ---------------------------------------------------------------------------
# 2. Registry / binding lookup.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guilt_unregistered_tool_name_is_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, {})))
    result = await executor.execute(
        _call("this_tool_does_not_exist_at_all", "{}"), principal_id=_VALID_PRINCIPAL
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.INTERNAL.value


@pytest.mark.asyncio
async def test_guilt_registered_but_unimplemented_tool_is_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, {})))
    # search_clients is a REAL F5 registry entry (R0) with no
    # executor/tools/search_clients.py yet — true today for 9 of 10 tools.
    result = await executor.execute(_call("search_clients", '{"query": "smith"}'), principal_id=_VALID_PRINCIPAL)
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.NOT_IMPLEMENTED.value


@pytest.mark.asyncio
async def test_innocence_get_required_documents_is_implemented(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.error is None
    assert result.ok is True


# ---------------------------------------------------------------------------
# 3. Local scope gate (principal presence).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guilt_missing_principal_is_not_authorized(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'), principal_id=""
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.NOT_AUTHORIZED.value


@pytest.mark.asyncio
async def test_innocence_well_formed_principal_passes_the_scope_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.ok is True


# ---------------------------------------------------------------------------
# 4. Argument re-validation.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guilt_malformed_json_arguments_is_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", "{not valid json"), principal_id=_VALID_PRINCIPAL
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.INVALID_ARGUMENTS.value


@pytest.mark.asyncio
async def test_guilt_schema_violating_arguments_is_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "not_a_real_type"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.INVALID_ARGUMENTS.value


@pytest.mark.asyncio
async def test_guilt_extra_property_in_arguments_is_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call(
            "get_required_documents",
            '{"practice_type": "limited_stay_kitas", "unexpected_field": "x"}',
        ),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.INVALID_ARGUMENTS.value


@pytest.mark.asyncio
async def test_innocence_well_formed_arguments_pass_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.ok is True


# ---------------------------------------------------------------------------
# 5. Auth resolution.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guilt_no_credential_for_principal_is_not_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    from team_bot.executor.auth import NullTokenProvider

    called = {"hit": False}

    def handler(request: httpx.Request) -> httpx.Response:
        called["hit"] = True
        return httpx.Response(200, json=_backend_success_json())

    executor = _executor(transport=fake_transport(handler), token_provider=NullTokenProvider())
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.NOT_AUTHORIZED.value
    assert called["hit"] is False, "network must never be reached with no resolvable credential"


@pytest.mark.asyncio
async def test_guilt_credential_for_a_different_principal_does_not_leak_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    provider = StaticTokenProvider("USR-002", _VALID_TOKEN_HEADERS)  # only USR-002 has a token
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())), token_provider=provider)
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,  # USR-001 asks — has no credential
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.NOT_AUTHORIZED.value


@pytest.mark.asyncio
async def test_innocence_resolvable_credential_reaches_the_network_with_the_right_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    seen_auth = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth["value"] = request.headers.get("authorization", "")
        return httpx.Response(200, json=_backend_success_json())

    executor = _executor(transport=fake_transport(handler))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.ok is True
    assert seen_auth["value"] == _VALID_TOKEN_HEADERS["Authorization"]


# ---------------------------------------------------------------------------
# 6. Network call + response mapping, incl. the broad-exception INTERNAL path.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guilt_backend_404_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(404, None)))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.NOT_FOUND.value


@pytest.mark.asyncio
async def test_guilt_backend_returns_a_malformed_body_is_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(
        transport=fake_transport(json_response(200, {"practice_type": "not_a_real_enum_value"}))
    )
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.INVALID_RESPONSE.value


@pytest.mark.asyncio
async def test_guilt_unexpected_exception_in_the_call_becomes_internal_never_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        # A bug class BackendClient.get does not catch on purpose (it only
        # catches httpx.HTTPError) — proves ToolExecutor's own broad
        # try/except around binding.call is what stops this from crashing
        # whatever calls execute().
        raise RuntimeError("a genuinely unexpected bug, not a documented failure mode")

    executor = _executor(transport=fake_transport(handler))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ExecutorErrorCode.INTERNAL.value


@pytest.mark.asyncio
async def test_innocence_full_success_path_produces_validated_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_read_tools(monkeypatch)
    executor = _executor(transport=fake_transport(json_response(200, _backend_success_json())))
    result = await executor.execute(
        _call("get_required_documents", '{"practice_type": "limited_stay_kitas"}'),
        principal_id=_VALID_PRINCIPAL,
    )
    assert result.ok is True
    assert result.error is None
    assert result.data == _backend_success_json()
    # R0 reads have nothing to audit (envelope.py's own documented rule).
    assert result.audit_ref is None
