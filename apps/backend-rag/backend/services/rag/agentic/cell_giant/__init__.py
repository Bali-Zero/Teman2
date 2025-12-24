"""
Cell-Giant Architecture - Nuzantara AI System

Il Gigante (LLM) ragiona come sovrano.
La Cellula (nostra KB) consiglia come consigliere fidato.
Zantara parla come unica voce.

"Non costruire un gigante. Diventa la coscienza di uno che esiste già."

Architecture:
1. giant_reason() - Il sovrano ragiona liberamente (domain-aware)
2. cell_calibrate() - Il consigliere calibra, corregge, arricchisce
3. synthesize_as_zantara() - La voce unica sintetizza

Pipeline Functions:
- cell_giant_pipeline() - Complete pipeline (sync)
- cell_giant_pipeline_stream() - Complete pipeline (streaming)

Configuration:
- GiantConfig - Configure Giant Reasoner behavior
- SynthesizerConfig - Configure Zantara Synthesizer behavior
- ResponseTone - Tone variations for responses
"""

# Core functions
from .giant_reasoner import giant_reason, GiantConfig, GiantResult
from .cell_conscience import (
    cell_calibrate,
    KNOWN_CORRECTIONS,
    PRACTICAL_INSIGHTS,
    BALI_ZERO_SERVICES,
)
from .zantara_synthesizer import (
    synthesize_as_zantara,
    synthesize_as_zantara_stream,
    cell_giant_pipeline,
    cell_giant_pipeline_stream,
    SynthesizerConfig,
    ResponseTone,
)

__all__ = [
    # Core Phase Functions
    "giant_reason",
    "cell_calibrate",
    "synthesize_as_zantara",
    "synthesize_as_zantara_stream",
    # Pipeline Functions
    "cell_giant_pipeline",
    "cell_giant_pipeline_stream",
    # Configuration
    "GiantConfig",
    "GiantResult",
    "SynthesizerConfig",
    "ResponseTone",
    # Data (for inspection/testing)
    "KNOWN_CORRECTIONS",
    "PRACTICAL_INSIGHTS",
    "BALI_ZERO_SERVICES",
]
