# Zantara Persona - System Instruction and Few-Shot Examples
# OPTIMIZED FOR: INDONESIAN IDENTITY + POLYGLOT ADAPTABILITY
#
# NOTE: System prompt now comes from zantara_core.py (Single Source of Truth).
# This module re-exports SYSTEM_INSTRUCTION and FEW_SHOT_EXAMPLES for
# backward compatibility with oracle_service.py and gemini_service.py.

import logging

from backend.prompts.few_shot_examples import GENERAL_FEW_SHOT_EXAMPLES
from backend.prompts.zantara_core import ZANTARA_MASTER_TEMPLATE

logger = logging.getLogger(__name__)

# Export SYSTEM_INSTRUCTION — consumers expect this name
SYSTEM_INSTRUCTION: str = ZANTARA_MASTER_TEMPLATE

# Few-shot examples — backward compat alias
FEW_SHOT_EXAMPLES = GENERAL_FEW_SHOT_EXAMPLES
