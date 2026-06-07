from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.llm import deepseek_client as mod


def _response(text: str) -> mod.DeepSeekResponse:
    return mod.DeepSeekResponse(
        text=text,
        model="deepseek-v4-flash",
        input_tokens=1,
        output_tokens=1,
        cache_hit_tokens=0,
        finish_reason="stop",
    )


@pytest.mark.asyncio
async def test_complete_json_async_requires_json_token(monkeypatch):
    mocked = AsyncMock()
    monkeypatch.setattr(mod, "complete_async", mocked)

    with pytest.raises(mod.DeepSeekError, match="contain 'JSON'"):
        await mod.complete_json_async("return an object")

    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_complete_json_async_forces_json_object(monkeypatch):
    mocked = AsyncMock(return_value=_response('{"ok": true}'))
    monkeypatch.setattr(mod, "complete_async", mocked)

    result = await mod.complete_json_async(
        "Return JSON with ok=true",
        model="deepseek-v4-flash",
        endpoint="test",
    )

    assert result.text == '{"ok": true}'
    kwargs = mocked.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["endpoint"] == "test"


@pytest.mark.asyncio
async def test_complete_json_async_retries_deepseek_errors(monkeypatch):
    mocked = AsyncMock(
        side_effect=[
            mod.DeepSeekError("DeepSeek returned empty content"),
            _response('{"ok": true}'),
        ],
    )
    monkeypatch.setattr(mod, "complete_async", mocked)
    monkeypatch.setattr(mod.asyncio, "sleep", AsyncMock())

    result = await mod.complete_json_async("Return JSON with ok=true")

    assert result.text == '{"ok": true}'
    assert mocked.call_count == 2
    assert "PARSER FEEDBACK" in mocked.call_args_list[1].args[0]


@pytest.mark.asyncio
async def test_complete_json_async_retries_non_json_content(monkeypatch):
    mocked = AsyncMock(
        side_effect=[
            _response("not json"),
            _response('{"ok": true}'),
        ],
    )
    monkeypatch.setattr(mod, "complete_async", mocked)
    monkeypatch.setattr(mod.asyncio, "sleep", AsyncMock())

    result = await mod.complete_json_async("Return JSON with ok=true")

    assert result.text == '{"ok": true}'
    assert mocked.call_count == 2
