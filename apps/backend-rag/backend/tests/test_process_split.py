"""
Integration tests for backend process split.
Verifies main_api.py and main_rag.py import correctly and have the right routes.
"""
import pytest


def test_main_api_imports_cleanly():
    """main_api.py must import without errors."""
    from backend.app.main_api import app
    assert app is not None
    assert app.title == "Zantara API Worker"


def test_main_rag_imports_cleanly():
    """main_rag.py must import without errors."""
    from backend.app.main_rag import app
    assert app is not None
    assert app.title == "Zantara RAG Worker"


def test_main_backward_compat():
    """main.py (original) must still work."""
    from backend.app.main import app
    assert app is not None


def test_api_has_health_route():
    """API worker must expose /health for Fly.io checks."""
    from backend.app.main_api import app
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert any('health' in p for p in paths), f"No health route in api process. Paths sample: {paths[:10]}"


def test_rag_has_health_route():
    """RAG worker must expose /health for Fly.io checks."""
    from backend.app.main_rag import app
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert any('health' in p for p in paths), f"No health route in rag process. Paths sample: {paths[:10]}"


def test_api_has_auth_route():
    """API worker must expose auth endpoints."""
    from backend.app.main_api import app
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert any('auth' in p for p in paths), f"No auth route in api process. Paths sample: {paths[:10]}"


def test_api_does_not_have_agentic_rag_routes():
    """API worker must NOT have agentic RAG endpoints."""
    from backend.app.main_api import app
    paths = [getattr(r, 'path', '') for r in app.routes]
    rag_paths = [p for p in paths if 'agentic' in p or '/orchestrator' in p]
    assert len(rag_paths) == 0, f"RAG routes leaked into api process: {rag_paths}"


def test_rag_has_rag_routes():
    """RAG worker must have agentic/chat/search endpoints."""
    from backend.app.main_rag import app
    paths = [getattr(r, 'path', '') for r in app.routes]
    assert any('agentic' in p or 'chat' in p or 'search' in p or 'kbli' in p for p in paths), \
        f"No RAG routes found. Paths sample: {paths[:20]}"


def test_route_counts_are_reasonable():
    """Sanity check: both processes have reasonable route counts and differ."""
    from backend.app.main_api import app as api_app
    from backend.app.main_rag import app as rag_app

    api_count = len([r for r in api_app.routes if hasattr(r, 'methods')])
    rag_count = len([r for r in rag_app.routes if hasattr(r, 'methods')])

    assert api_count > 50, f"API process has too few routes: {api_count}"
    assert rag_count > 20, f"RAG process has too few routes: {rag_count}"
    assert api_count != rag_count, \
        f"Both processes have identical route count ({api_count}) — split likely failed"
