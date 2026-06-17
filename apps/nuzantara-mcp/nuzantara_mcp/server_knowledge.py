"""
Nuzantara MCP — KNOWLEDGE-ONLY server (cloud-safe / Cowork).

WHY THIS FILE EXISTS
--------------------
Cowork (Claude desktop) runs the conversation on Anthropic's CLOUD model.
The full `server.py` exposes CRM (list_clients, get_client, ...), intel/OSINT
(intel_*), drive, comms and admin tools — every result of those would carry
client PII or intelligence into a cloud endpoint, violating the project rule:
"PII assoluta: mai inviare dati cliente a endpoint cloud" + OSINT sovereignty
(UU PDP). See CLAUDE.md and cicatrix-scars.md.

This server is the ENFORCED boundary: it builds a FRESH FastMCP instance and
registers ONLY the PII-free knowledge modules. It is fail-closed by
construction — a module is reachable here only if it is imported + registered
below. If you add a new CRM/intel module to server.py, it does NOT appear in
Cowork. Documentation is not the boundary; this file is.

WHAT IT EXPOSES (all general business knowledge, zero client PII)
- knowledge: search_kbli, inspect_kbli, chat_kbli, ask_legal,
             list_visa_types, get_visa_details
- pricing:   calculate_pricing, get_all_prices, search_service_pricing

Transport: stdio. Same backend (NUZANTARA_BACKEND_URL) + auth (NUZANTARA_API_KEY)
as the full server.

BEFORE ADDING A MODULE HERE: confirm every tool it registers returns only
public/business knowledge — never client records, documents, or intelligence.

Run:
    PYTHONPATH=apps/nuzantara-mcp NUZANTARA_API_KEY=... \
        apps/nuzantara-mcp/.venv/bin/python \
        apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py
"""

import os
import sys

# Mirror server_lite.py: allow `from server import ...` as a sibling import.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP  # noqa: E402

# Reuse the proven HTTP helpers + auth from the full server. Importing `server`
# also builds the full server's own `mcp`, but we never expose it — we run ours.
from server import _call, _call_safe  # noqa: E402

# --- Allowlist: ONLY these PII-free modules are registered ---
from nuzantara_mcp.tools.knowledge import register as register_knowledge  # noqa: E402
from nuzantara_mcp.tools.pricing import register as register_pricing  # noqa: E402

mcp = FastMCP(
    name="Nuzantara Knowledge",
    instructions=(
        "PII-free knowledge layer for Bali Zero. Indonesian KBLI business "
        "classification, visa/KITAS types, legal & regulatory Q&A grounded in "
        "the Nuzantara RAG, and Bali Zero service pricing. No client data, no "
        "CRM, no intelligence — safe for cloud (Cowork) use."
    ),
)

register_knowledge(mcp, _call, _call_safe)
register_pricing(mcp, _call, _call_safe)

# Tidy: drop the graph-viz tool that ships inside the knowledge module — it is
# PII-free but is a debug tool, not knowledge. Keep the cloud surface minimal.
for _name in ("visualize_langgraph",):
    try:
        mcp.remove_tool(_name)
    except Exception:
        pass


if __name__ == "__main__":
    mcp.run()
