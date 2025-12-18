"""
ZANTARA Feature Flags
Control experimental and optional features via environment variables
"""

from app.core.config import settings

# Skill Detection Layer (Experimental)
SKILL_DETECTION_ENABLED = settings.enable_skill_detection

# Collective Memory Workflow (Experimental - requires langgraph)
COLLECTIVE_MEMORY_ENABLED = settings.enable_collective_memory

# Advanced Analytics (Optional)
ADVANCED_ANALYTICS_ENABLED = settings.enable_advanced_analytics

# Tool Execution System (Optional)
TOOL_EXECUTION_ENABLED = settings.enable_tool_execution


def should_enable_skill_detection() -> bool:
    """
    Check if Skill Detection Layer should be enabled

    Returns:
        bool: True if skill detection should be enabled
    """
    return SKILL_DETECTION_ENABLED


def should_enable_collective_memory() -> bool:
    """
    Check if Collective Memory Workflow should be enabled
    Requires langgraph to be installed

    Returns:
        bool: True if collective memory should be enabled
    """
    if not COLLECTIVE_MEMORY_ENABLED:
        return False

    # Check if langgraph is available
    try:
        import importlib.util

        spec = importlib.util.find_spec("langgraph")
        return spec is not None
    except ImportError:
        return False


def should_enable_tool_execution() -> bool:
    """
    Check if Tool Execution should be enabled

    Returns:
        bool: True if tool execution should be enabled
    """
    return TOOL_EXECUTION_ENABLED


def get_feature_flags() -> dict:
    """
    Get all feature flags and their current status

    Returns:
        dict: Dictionary of feature flags
    """
    return {
        "skill_detection": SKILL_DETECTION_ENABLED,
        "collective_memory": should_enable_collective_memory(),
        "advanced_analytics": ADVANCED_ANALYTICS_ENABLED,
        "tool_execution": TOOL_EXECUTION_ENABLED,
    }
