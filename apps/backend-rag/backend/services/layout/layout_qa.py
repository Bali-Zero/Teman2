"""Layout-specific QA via qwen2.5vl:7b (Ollama).

Distinct from visual/vision_qa: this one scores the RENDERED composition —
text overflow, contrast, overlap, logo visibility — not the generative image.

Output is :class:`LayoutFlags`, which drives the patch loop in LayoutRenderer.
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


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_layout_qa_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


@dataclass
class LayoutFlags:
    text_overflow: bool
    low_contrast_regions: list[str]
    element_overlap: bool
    logo_visible: bool
    logo_position_ok: bool
    readability_score_0_10: int
    raw_response: str = ""
    ok: bool = True
    error: str | None = None

    @property
    def requires_patch(self) -> bool:
        return (
            self.text_overflow
            or self.element_overlap
            or bool(self.low_contrast_regions)
            or not self.logo_visible
            or not self.logo_position_ok
            or self.readability_score_0_10 < 6
        )


_LAYOUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text_overflow": {"type": "boolean"},
        "low_contrast_regions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "element_overlap": {"type": "boolean"},
        "logo_visible": {"type": "boolean"},
        "logo_position_ok": {"type": "boolean"},
        "readability_score_0_10": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
        },
    },
    "required": [
        "text_overflow",
        "low_contrast_regions",
        "element_overlap",
        "logo_visible",
        "logo_position_ok",
        "readability_score_0_10",
    ],
}


_LAYOUT_PROMPT = (
    "Sei il QA layout editor di Bali Zero. Controlla QUESTO screenshot di "
    "un render HTML/CSS. Rispondi SOLO JSON strict. Rileva SOLO problemi "
    "visibili ora, non possibilita ipotetiche."
)


class LayoutQAClient:
    """Send a screenshot to qwen2.5vl:7b and get structured layout flags."""

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

    async def analyze(self, png_bytes: bytes) -> LayoutFlags:
        start = time.perf_counter()
        image_b64 = base64.b64encode(png_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": _LAYOUT_PROMPT,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "think": False,
            "format": _LAYOUT_SCHEMA,
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
                return self._err(
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
            body = resp.json()
            content = body.get("message", {}).get("content", "").strip()
            if not content:
                return self._err("empty content")
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                return self._err(f"bad json: {exc}", raw=content)
            logger.debug(
                "layout qa | model=%s duration_ms=%.0f readability=%s",
                self.model,
                duration_ms,
                parsed.get("readability_score_0_10"),
            )
            return LayoutFlags(
                text_overflow=bool(parsed.get("text_overflow", False)),
                low_contrast_regions=list(parsed.get("low_contrast_regions", []) or []),
                element_overlap=bool(parsed.get("element_overlap", False)),
                logo_visible=bool(parsed.get("logo_visible", True)),
                logo_position_ok=bool(parsed.get("logo_position_ok", True)),
                readability_score_0_10=int(parsed.get("readability_score_0_10", 0)),
                raw_response=content,
                ok=True,
            )
        except httpx.ConnectError as exc:
            return self._err(f"ollama unreachable: {exc}")
        except httpx.TimeoutException:
            return self._err(f"timeout {self.timeout}s")
        except Exception as exc:  # noqa: BLE001
            return self._err(f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _err(message: str, *, raw: str = "") -> LayoutFlags:
        return LayoutFlags(
            text_overflow=False,
            low_contrast_regions=[],
            element_overlap=False,
            logo_visible=True,
            logo_position_ok=True,
            readability_score_0_10=0,
            raw_response=raw,
            ok=False,
            error=message,
        )
