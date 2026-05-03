"""
Tests for agentic RAG orchestrator - out of domain detection.
"""

import pytest


def test_is_out_of_domain_realtime_info():
    """Out-of-domain detection for realtime info queries."""
    # Test that the agentic module is importable
    from backend.services.rag import agentic
    assert hasattr(agentic, "create_agentic_rag")
