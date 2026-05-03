# scripts/zantara-gateway/gemini_api_client.py
"""
Direct Gemini API client with MCP tool calling ReAct loop.

Calls generativelanguage.googleapis.com directly with streaming.
When Gemini requests a function call, executes it via MCP client
and feeds the result back. Loops until Gemini produces a final answer.

Free tier: 10 RPM, 250 req/day for Flash.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger("zantara-gateway.gemini-api")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _mcp_tools_to_gemini_declarations(mcp_tools: list[dict]) -> list[dict]:
    """Convert MCP tool definitions (OpenAI format) to Gemini functionDeclarations."""
    declarations = []
    for tool in mcp_tools:
        fn = tool.get("function", {})
        params = fn.get("parameters", {})
        # Gemini doesn't support "required" at top level of parameters
        # and needs "type": "OBJECT" uppercase
        clean_params = {
            "type": "OBJECT",
            "properties": params.get("properties", {}),
        }
        declarations.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "parameters": clean_params,
        })
    return declarations


async def stream_gemini_api(
    query: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
    system_prompt: str = "",
    mcp_tools: list[dict] | None = None,
    mcp_execute: Any = None,  # async callable(name, args) -> str
    max_tool_iterations: int = 3,
    timeout: int = 60,
) -> AsyncIterator[str]:
    """Call Gemini API with streaming + MCP tool ReAct loop.

    When Gemini returns a functionCall, we:
    1. Execute it via mcp_execute(name, args)
    2. Send the result back as functionResponse
    3. Gemini continues reasoning with the data
    4. Repeat up to max_tool_iterations
    """
    url = f"{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}"
    stream_url = f"{GEMINI_API_BASE}/models/{model}:streamGenerateContent?key={api_key}&alt=sse"

    contents: list[dict] = [{"role": "user", "parts": [{"text": query}]}]

    base_payload: dict = {}
    if system_prompt:
        base_payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    base_payload["generationConfig"] = {"temperature": 0.3, "maxOutputTokens": 4096}

    # Add tool declarations if available
    tool_declarations = []
    if mcp_tools and mcp_execute:
        tool_declarations = _mcp_tools_to_gemini_declarations(mcp_tools)
        base_payload["tools"] = [{"functionDeclarations": tool_declarations}]

    logger.info("Gemini API: model=%s tools=%d", model, len(tool_declarations))

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:

        for iteration in range(max_tool_iterations + 1):
            payload = {**base_payload, "contents": contents}

            # Last iteration or no tools: stream the response
            is_last = iteration == max_tool_iterations or not tool_declarations
            if is_last or iteration > 0:
                # Use streaming for user-facing responses
                async with client.stream("POST", stream_url, json=payload) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        logger.error("Gemini API %d: %s", resp.status_code, body.decode()[:300])
                        # Raise exception so gateway falls back to CLI spawn
                        raise RuntimeError(f"Gemini API {resp.status_code}: rate limit or overloaded")

                    function_calls: list[dict] = []
                    text_parts: list[str] = []

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        for candidate in chunk.get("candidates", []):
                            for part in candidate.get("content", {}).get("parts", []):
                                if "text" in part:
                                    text = part["text"]
                                    text_parts.append(text)
                                    yield f'data: {json.dumps({"type":"token","data":text},separators=(",",":"))}\n\n'

                                if "functionCall" in part:
                                    fc = part["functionCall"]
                                    function_calls.append(fc)
                                    yield f'data: {json.dumps({"type":"tool_call","data":{"name":fc.get("name",""),"args":fc.get("args",{})}},separators=(",",":"))}\n\n'

                            finish = candidate.get("finishReason", "")
                            if finish in ("STOP", "MAX_TOKENS", "SAFETY"):
                                yield "data: [DONE]\n\n"
                                return

                    # If no function calls, we're done
                    if not function_calls:
                        yield "data: [DONE]\n\n"
                        return

                    # Add model response to conversation
                    model_parts: list[dict] = []
                    if text_parts:
                        model_parts.append({"text": "".join(text_parts)})
                    for fc in function_calls:
                        model_parts.append({"functionCall": fc})
                    contents.append({"role": "model", "parts": model_parts})

                    # Execute function calls via MCP
                    response_parts: list[dict] = []
                    for fc in function_calls:
                        name = fc.get("name", "")
                        args = fc.get("args", {})
                        logger.info("Executing tool: %s", name)
                        try:
                            result = await mcp_execute(name, args)
                            yield f'data: {json.dumps({"type":"tool_result","data":{"name":name}},separators=(",",":"))}\n\n'
                        except Exception as e:
                            result = f"Error: {e}"
                            logger.warning("Tool %s failed: %s", name, e)

                        response_parts.append({
                            "functionResponse": {
                                "name": name,
                                "response": {"result": result},
                            }
                        })

                    contents.append({"role": "user", "parts": response_parts})
                    # Loop continues — Gemini will reason with tool results

            else:
                # First iteration with tools: use non-streaming to get function calls faster
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.error("Gemini API %d: %s", resp.status_code, resp.text[:300])
                    raise RuntimeError(f"Gemini API {resp.status_code}: rate limit or overloaded")

                data = resp.json()
                function_calls: list[dict] = []
                text_parts: list[str] = []

                for candidate in data.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        if "text" in part:
                            text = part["text"]
                            text_parts.append(text)
                            yield f'data: {json.dumps({"type":"token","data":text},separators=(",",":"))}\n\n'
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            function_calls.append(fc)
                            yield f'data: {json.dumps({"type":"tool_call","data":{"name":fc.get("name",""),"args":fc.get("args",{})}},separators=(",",":"))}\n\n'

                    finish = candidate.get("finishReason", "")
                    if finish in ("STOP", "MAX_TOKENS", "SAFETY") and not function_calls:
                        yield "data: [DONE]\n\n"
                        return

                if not function_calls:
                    yield "data: [DONE]\n\n"
                    return

                # Add model response + execute tools (same as above)
                model_parts = []
                if text_parts:
                    model_parts.append({"text": "".join(text_parts)})
                for fc in function_calls:
                    model_parts.append({"functionCall": fc})
                contents.append({"role": "model", "parts": model_parts})

                response_parts = []
                for fc in function_calls:
                    name = fc.get("name", "")
                    args = fc.get("args", {})
                    logger.info("Executing tool: %s", name)
                    try:
                        result = await mcp_execute(name, args)
                        yield f'data: {json.dumps({"type":"tool_result","data":{"name":name}},separators=(",",":"))}\n\n'
                    except Exception as e:
                        result = f"Error: {e}"
                    response_parts.append({
                        "functionResponse": {
                            "name": name,
                            "response": {"result": result},
                        }
                    })
                contents.append({"role": "user", "parts": response_parts})

    yield "data: [DONE]\n\n"
