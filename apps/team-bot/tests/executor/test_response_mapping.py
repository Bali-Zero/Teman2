"""map_backend_result — every branch of the status-code / network-error
mapping, plus the "a 200 whose body fails result_model validation is
INVALID_RESPONSE, not success" invariant that IS this module's whole
reason to exist (MANDATE.md F4: tool results are untrusted input)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from team_bot.executor.errors import ExecutorErrorCode
from team_bot.executor.http_client import BackendCallResult
from team_bot.executor.response_mapping import map_backend_result


class _Result(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    value: int


def test_timeout_maps_to_upstream_timeout_and_is_retryable() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=None, json_body=None, network_error="timeout"), result_model=_Result
    )
    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.UPSTREAM_TIMEOUT.value
    assert outcome.error.retryable is True


def test_network_error_maps_to_upstream_unavailable_and_is_retryable() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=None, json_body=None, network_error="network_error"), result_model=_Result
    )
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.UPSTREAM_UNAVAILABLE.value
    assert outcome.error.retryable is True


def test_401_maps_to_not_authorized_non_retryable() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=401, json_body=None, network_error=None), result_model=_Result
    )
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.NOT_AUTHORIZED.value
    assert outcome.error.retryable is False


def test_403_also_maps_to_not_authorized() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=403, json_body=None, network_error=None), result_model=_Result
    )
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.NOT_AUTHORIZED.value


def test_404_maps_to_not_found() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=404, json_body=None, network_error=None), result_model=_Result
    )
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.NOT_FOUND.value
    assert outcome.error.retryable is False


def test_5xx_maps_to_upstream_unavailable_and_is_retryable() -> None:
    for status in (500, 502, 503, 504):
        outcome = map_backend_result(
            BackendCallResult(status_code=status, json_body=None, network_error=None), result_model=_Result
        )
        assert outcome.error is not None, status
        assert outcome.error.code == ExecutorErrorCode.UPSTREAM_UNAVAILABLE.value, status
        assert outcome.error.retryable is True, status


def test_unmapped_status_code_maps_to_internal() -> None:
    # 400/409/422/an unexpected 2xx like 201 — deliberately conservative,
    # never guessed into a more specific bucket (see module docstring).
    for status in (400, 409, 422, 201):
        outcome = map_backend_result(
            BackendCallResult(status_code=status, json_body={"value": 1}, network_error=None),
            result_model=_Result,
        )
        assert outcome.error is not None, status
        assert outcome.error.code == ExecutorErrorCode.INTERNAL.value, status


def test_valid_200_body_produces_ok_result_with_validated_data() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=200, json_body={"value": 42}, network_error=None),
        result_model=_Result,
    )
    assert outcome.ok is True
    assert outcome.error is None
    assert outcome.data == {"value": 42}


def test_200_with_body_failing_result_model_validation_is_invalid_response() -> None:
    # UNTRUSTED input: a 200 with a schema-violating body is NOT success.
    outcome = map_backend_result(
        BackendCallResult(status_code=200, json_body={"value": "not-an-int"}, network_error=None),
        result_model=_Result,
    )
    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.INVALID_RESPONSE.value
    assert outcome.error.retryable is False


def test_200_with_empty_body_is_invalid_response_not_success() -> None:
    outcome = map_backend_result(
        BackendCallResult(status_code=200, json_body=None, network_error=None), result_model=_Result
    )
    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.INVALID_RESPONSE.value


def test_200_with_a_json_array_body_is_invalid_response() -> None:
    # A JSON body that parses but isn't even an object must not be treated
    # as a partial dict — result_model.model_validate would itself reject
    # a list, but this guards the isinstance(dict) short-circuit directly.
    outcome = map_backend_result(
        BackendCallResult(status_code=200, json_body=[1, 2, 3], network_error=None), result_model=_Result
    )
    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.code == ExecutorErrorCode.INVALID_RESPONSE.value
