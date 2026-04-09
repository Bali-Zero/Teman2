"""
Mata Garuda — NotebookLM tools via nlm CLI subprocess.

NLM is the analytical brain — 600 sources of context per notebook.
CLI-only: no HTTP API calls.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from uuid import uuid4

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")


@register_tool(name="nlm_query")
def nlm_query(
    notebook_id: str,
    question: str,
    context_variables: dict | None = None,
) -> str:
    """Query a NotebookLM notebook for analytical synthesis.

    Args:
        notebook_id: NLM notebook UUID
        question: Question to ask NLM (grounded on its 600 sources)
    """
    try:
        result = subprocess.run(
            ["nlm", "notebook", "query", "--notebook", notebook_id, "--question", question],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return f"[WARNING] NLM query returned empty. stderr: {result.stderr[:200]}"
    except FileNotFoundError:
        return "[ERROR] nlm CLI not found"
    except subprocess.TimeoutExpired:
        return "[ERROR] NLM query timeout (120s)"
    except Exception as e:
        return f"[ERROR] NLM query failed: {e}"


@register_tool(name="nlm_add_source")
def nlm_add_source(
    notebook_id: str,
    url: str,
    context_variables: dict | None = None,
) -> str:
    """Add a URL source to a NotebookLM notebook.

    Args:
        notebook_id: NLM notebook UUID
        url: URL to add as source
    """
    try:
        result = subprocess.run(
            ["nlm", "source", "add", "--notebook", notebook_id, "--url", url],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return f"[SUCCESS] Added source to NLM: {url}"
        return f"[ERROR] NLM add source failed: {result.stderr[:200]}"
    except FileNotFoundError:
        return "[ERROR] nlm CLI not found"
    except Exception as e:
        return f"[ERROR] NLM add source failed: {e}"


@register_tool(name="nlm_add_text")
def nlm_add_text(
    notebook_id: str,
    title: str,
    text: str,
    context_variables: dict | None = None,
) -> str:
    """Add text content as a source to a NotebookLM notebook.

    Args:
        notebook_id: NLM notebook UUID
        title: Title for the source
        text: Text content to add
    """
    tmp = Path(f"/tmp/nlm_source_{uuid4().hex[:8]}.txt")
    try:
        tmp.write_text(f"# {title}\n\n{text}")
        result = subprocess.run(
            ["nlm", "source", "add", "--notebook", notebook_id, "--file", str(tmp)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return f"[SUCCESS] Added text source '{title}' to NLM"
        return f"[ERROR] NLM add text failed: {result.stderr[:200]}"
    except FileNotFoundError:
        return "[ERROR] nlm CLI not found"
    except Exception as e:
        return f"[ERROR] NLM add text failed: {e}"
    finally:
        tmp.unlink(missing_ok=True)
