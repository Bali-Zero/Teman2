"""Ollama qwen2.5vl:7b vision client for Visual QA.

Uses Ollama native /api/chat endpoint (think:false required for qwen3.5 variants;
for qwen2.5vl:7b it's safe to always pass think:false).

Only qwen2.5vl:7b is supported on Pro — per CLAUDE.md §10: qwen3.5 Q4_K_M strips
vision weights and will not describe images.

Output JSON schema is enforced via Ollama's `format` parameter, producing
:class:`VisionFlags` directly.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


VISION_MODEL_DEFAULT = "qwen2.5vl:7b"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


# The banned elements list mirrors brand.json `image_style.banned`.
BANNED_ELEMENTS: tuple[str, ...] = (
    "strette_di_mano",
    "passaporti_generici",
    "immagini_stock",
    "watermark",
    "mani_deformi",
    "dita_extra",
    "testo_storpio",
    "volti_distorti",
)


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_vision_qa_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


@dataclass
class VisionFlags:
    matches_brief: bool
    has_banned_elements: list[str]
    brand_fit_score_0_10: int
    text_area_available_ratio: float
    readability_issues: list[str]
    raw_response: str = ""
    ok: bool = True
    error: str | None = None

    @property
    def rejects_any(self) -> bool:
        return (
            not self.matches_brief
            or bool(self.has_banned_elements)
            or self.brand_fit_score_0_10 < 5
            or self.text_area_available_ratio < 0.2
        )


_VISION_PROMPT_TEMPLATE = (
    "Analizza questa immagine per una pubblicazione editoriale di Bali Zero. "
    "Rispondi SOLO con JSON strict. Brief originale dell'autore: "
    "{brief}"
)


_VISION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "matches_brief": {"type": "boolean"},
        "has_banned_elements": {
            "type": "array",
            "items": {"type": "string"},
        },
        "brand_fit_score_0_10": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
        },
        "text_area_available_ratio": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "readability_issues": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "matches_brief",
        "has_banned_elements",
        "brand_fit_score_0_10",
        "text_area_available_ratio",
        "readability_issues",
    ],
}


class OllamaVisionClient:
    """Async qwen2.5vl:7b client for single-image QA flag extraction."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str = VISION_MODEL_DEFAULT,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model
        self._client = http_client
        self.timeout = timeout

    async def analyze(
        self,
        image_bytes: bytes,
        brief: str,
    ) -> VisionFlags:
        start = time.perf_counter()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = _VISION_PROMPT_TEMPLATE.format(brief=brief[:800])

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "think": False,
            "format": _VISION_JSON_SCHEMA,
            "options": {"temperature": 0},
        }

        client = self._client or _get_module_client(self.timeout)

        try:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            if resp.status_code != 200:
                return VisionFlags(
                    matches_brief=False,
                    has_banned_elements=[],
                    brand_fit_score_0_10=0,
                    text_area_available_ratio=0.0,
                    readability_issues=[],
                    ok=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
            body = resp.json()
            content = body.get("message", {}).get("content", "").strip()
            if not content:
                return VisionFlags(
                    matches_brief=False,
                    has_banned_elements=[],
                    brand_fit_score_0_10=0,
                    text_area_available_ratio=0.0,
                    readability_issues=[],
                    ok=False,
                    error="empty content",
                )
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                return VisionFlags(
                    matches_brief=False,
                    has_banned_elements=[],
                    brand_fit_score_0_10=0,
                    text_area_available_ratio=0.0,
                    readability_issues=[],
                    raw_response=content,
                    ok=False,
                    error=f"bad json: {exc}",
                )

            logger.debug(
                "vision qa | model=%s duration_ms=%.0f brand_fit=%s",
                self.model,
                duration_ms,
                parsed.get("brand_fit_score_0_10"),
            )
            return VisionFlags(
                matches_brief=bool(parsed.get("matches_brief", False)),
                has_banned_elements=list(parsed.get("has_banned_elements", []) or []),
                brand_fit_score_0_10=int(parsed.get("brand_fit_score_0_10", 0)),
                text_area_available_ratio=float(
                    parsed.get("text_area_available_ratio", 0) or 0
                ),
                readability_issues=list(parsed.get("readability_issues", []) or []),
                raw_response=content,
                ok=True,
            )
        except httpx.ConnectError as exc:
            return VisionFlags(
                matches_brief=False,
                has_banned_elements=[],
                brand_fit_score_0_10=0,
                text_area_available_ratio=0.0,
                readability_issues=[],
                ok=False,
                error=f"ollama unreachable: {exc}",
            )
        except httpx.TimeoutException:
            return VisionFlags(
                matches_brief=False,
                has_banned_elements=[],
                brand_fit_score_0_10=0,
                text_area_available_ratio=0.0,
                readability_issues=[],
                ok=False,
                error=f"timeout {self.timeout}s",
            )
        except Exception as exc:  # noqa: BLE001
            return VisionFlags(
                matches_brief=False,
                has_banned_elements=[],
                brand_fit_score_0_10=0,
                text_area_available_ratio=0.0,
                readability_issues=[],
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
