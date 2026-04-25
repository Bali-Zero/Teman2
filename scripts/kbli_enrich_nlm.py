#!/usr/bin/env python3
"""NLM (NotebookLM) query wrapper for KBLI enrichment.
Queries NB-company, NB-tax, NB-operations via nlm CLI for regulatory intel.
"""
import subprocess
from pathlib import Path

NLM_BIN = str(Path.home() / ".local/bin/nlm")

# NLM notebook IDs from NLM_NOTEBOOKS registry
NB_COMPANY = "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4"
NB_TAX = "837b620b-2aca-43ab-812e-97ca92bdad1d"
NB_OPERATIONS = "3e1baa5f-680f-4499-9430-23a901576bcc"


def query_notebook(notebook_id: str, query: str, timeout: int = 120) -> str:
    """Query a single NLM notebook. Returns the response text."""
    try:
        result = subprocess.run(
            [NLM_BIN, "query", notebook_id, query],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[NLM TIMEOUT after {timeout}s]"
    except Exception as e:
        return f"[NLM ERROR: {e}]"


def query_regulatory_intel(codes: list[dict], timeout: int = 120) -> dict[str, str]:
    """Query NLM for regulatory intelligence on 1-2 KBLI codes.
    Queries company (licensing), tax, and operations notebooks.
    Returns {code: combined_intel_text}.
    """
    code_list = ", ".join(c["kode_kbli_2025"] for c in codes)
    titles = ", ".join(f"{c['kode_kbli_2025']} ({c['judul']})" for c in codes)

    query = (
        f"For KBLI codes {titles}: What are the specific licensing requirements, "
        f"risk level, PMA restrictions, mandatory certifications, "
        f"and any recent regulatory changes under PP28/2025 and BKPM 5/2025? "
        f"Include any Bali-specific enforcement or compliance requirements."
    )

    # Query all 3 notebooks
    company_resp = query_notebook(NB_COMPANY, query, timeout)
    tax_resp = query_notebook(NB_TAX, f"Tax implications for KBLI {code_list}: PBJT, PPh, PPN, LKPM obligations", timeout)
    ops_resp = query_notebook(NB_OPERATIONS, f"Operational compliance for KBLI {code_list}: permits, inspections, reporting", timeout)

    combined = f"## Licensing & Company\n{company_resp}\n\n## Tax\n{tax_resp}\n\n## Operations\n{ops_resp}"

    # Map combined intel to each code
    result = {}
    for c in codes:
        result[c["kode_kbli_2025"]] = combined
    return result


def research_bps_only(code: str, judul: str) -> str:
    """Run NLM fast research for a BPS_ONLY code to find sector-specific regulations."""
    try:
        result = subprocess.run(
            [NLM_BIN, "research", "start",
             "--query", f"Indonesian KBLI {code} {judul} licensing requirements regulations 2025 2026",
             "--mode", "fast",
             "--notebook", NB_COMPANY],
            capture_output=True, text=True, timeout=120,
        )
        return result.stdout.strip()
    except Exception as e:
        return f"[NLM Research Error: {e}]"
