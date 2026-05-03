"""Visual — Image generation + QA pipeline for War Room 2.0.

Modules:
- imagen_client: Google Gen AI Imagen 4 (Ultra for cover, Fast for slides)
- fireworks_fallback: Flux.1 Dev fallback when Imagen unavailable
- vision_qa: qwen2.5vl:7b Ollama JSON-structured flags
- qa_judge: Claude Haiku CLI final decision (pass|retry|reject)
- prompt_builder: 4-layer prompt assembly (scene + brand + style + negative)
- generator: VisualGenerator orchestrator with retry loop + cost tracking

Reference: docs/war-room-2.0-design.md §4, §5.
"""

from backend.services.visual.generator import (
    SlideResult,
    VisualGenerator,
    VisualGeneratorResult,
)
from backend.services.visual.imagen_client import (
    ImagenClient,
    ImagenError,
    ImagenQuality,
    ImagenResult,
)
from backend.services.visual.prompt_builder import (
    BRAND_SUFFIX,
    NEGATIVE_PROMPT,
    build_imagen_prompt,
)
from backend.services.visual.qa_judge import (
    QADecision,
    QAJudge,
    QAVerdict,
)
from backend.services.visual.vision_qa import (
    OllamaVisionClient,
    VisionFlags,
)

__all__ = [
    "BRAND_SUFFIX",
    "ImagenClient",
    "ImagenError",
    "ImagenQuality",
    "ImagenResult",
    "NEGATIVE_PROMPT",
    "OllamaVisionClient",
    "QADecision",
    "QAJudge",
    "QAVerdict",
    "SlideResult",
    "VisionFlags",
    "VisualGenerator",
    "VisualGeneratorResult",
    "build_imagen_prompt",
]
