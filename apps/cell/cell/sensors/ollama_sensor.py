"""OllamaSensor — monitors local Ollama daemon health.

Calls GET http://localhost:11434/api/tags to verify Ollama is running
and the required models are loaded. No HTTP client reuse needed —
Ollama is local, call cost is negligible.
"""
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("cell.sensors.ollama")


@dataclass
class OllamaReading:
    status: str  # "green", "yellow", "red"
    reachable: bool = False
    models_loaded: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class OllamaSensor:
    """Checks if Ollama is reachable and required models are available.

    status:
      green   — reachable, all required models present
      yellow  — reachable but a required model is missing
      red     — not reachable at all
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        required_models: list[str] | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._url = ollama_url
        self._required = required_models or ["qwen3.5:9b", "qwen3.5:27b"]
        self._timeout = timeout

    async def read(self) -> OllamaReading:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._url}/api/tags")
                response.raise_for_status()
                data = response.json()

            loaded = [m["name"] for m in data.get("models", [])]
            missing = [m for m in self._required if m not in loaded]

            if missing:
                logger.warning(f"OllamaSensor: models missing: {missing}")
                return OllamaReading(
                    status="yellow",
                    reachable=True,
                    models_loaded=loaded,
                    missing_models=missing,
                    metadata={"missing": missing, "loaded_count": len(loaded)},
                )

            return OllamaReading(
                status="green",
                reachable=True,
                models_loaded=loaded,
                missing_models=[],
                metadata={"loaded_count": len(loaded)},
            )

        except Exception as e:
            logger.warning(f"OllamaSensor: not reachable — {e}")
            return OllamaReading(
                status="red",
                reachable=False,
                metadata={"error": str(e)},
            )
