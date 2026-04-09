# scripts/zantara-gateway/gemini_api_client.py
"""
Direct Gemini API client — bypasses Gemini CLI for zero cold start.

Calls generativelanguage.googleapis.com directly with streaming.
Used on slow hardware (Intel Macs) where CLI boot takes 30s+.
Free tier: 10 RPM, 250 req/day for Flash, 15 RPM for Flash Lite.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

logger = logging.getLogger("zantara-gateway.gemini-api")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


async def stream_gemini_api(
    query: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
    system_prompt: str = "",
    tools: list[dict] | None = None,
    timeout: int = 60,
) -> AsyncIterator[str]:
    """Call Gemini API directly with streaming. Yields SSE lines.

    ~2-3s latency vs 30s with CLI on Intel.
    """
    url = f"{GEMINI_API_BASE}/models/{model}:streamGenerateContent?key={api_key}&alt=sse"

    contents = [{"role": "user", "parts": [{"text": query}]}]

    payload: dict = {"contents": contents}

    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    # Tool definitions (function declarations) for MCP-like tool calling
    if tools:
        payload["tools"] = [{"functionDeclarations": tools}]

    payload["generationConfig"] = {
        "temperature": 0.3,
        "maxOutputTokens": 4096,
    }

    logger.info("Gemini API call: model=%s tools=%d", model, len(tools or []))

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        async with client.stream("POST", url, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                error_text = body.decode("utf-8", errors="replace")[:500]
                logger.error("Gemini API error %d: %s", resp.status_code, error_text)
                yield f'data: {json.dumps({"type": "error", "data": f"Gemini API error: {resp.status_code}"})}\n\n'
                yield "data: [DONE]\n\n"
                return

            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                # SSE format: "data: {...}"
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if not data_str:
                        continue
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Extract text from candidates
                    candidates = chunk.get("candidates", [])
                    for candidate in candidates:
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])
                        for part in parts:
                            # Text response
                            if "text" in part:
                                text = part["text"]
                                yield f'data: {json.dumps({"type": "token", "data": text}, separators=(",", ":"))}\n\n'

                            # Function call (tool use)
                            if "functionCall" in part:
                                fc = part["functionCall"]
                                name = fc.get("name", "")
                                args = fc.get("args", {})
                                yield f'data: {json.dumps({"type": "tool_call", "data": {"name": name, "args": args}}, separators=(",", ":"))}\n\n'

                        # Check finish reason
                        finish = candidate.get("finishReason", "")
                        if finish in ("STOP", "MAX_TOKENS", "SAFETY"):
                            yield "data: [DONE]\n\n"
                            return

    yield "data: [DONE]\n\n"
