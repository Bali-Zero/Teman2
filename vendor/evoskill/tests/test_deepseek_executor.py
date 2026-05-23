from __future__ import annotations

import asyncio


def test_json_object_response_format_adds_explicit_json_instruction(monkeypatch) -> None:
    from src.harness.deepseek import executor

    captured: dict[str, object] = {}

    async def fake_post_once(payload, api_key):
        captured["payload"] = payload
        captured["api_key"] = api_key
        return {
            "choices": [{"message": {"content": "{\"ok\": true}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(executor, "_post_once", fake_post_once)

    asyncio.run(
        executor.execute_query(
            {
                "system": "Return a concise object.",
                "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
            },
            "Answer with the required fields.",
        )
    )

    payload = captured["payload"]
    assert payload["response_format"] == {"type": "json_object"}
    assert "json" in " ".join(m["content"] for m in payload["messages"]).lower()
