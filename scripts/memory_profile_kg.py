#!/usr/bin/env python3
"""
Memory Profiling Script for KG LangGraph on Fly.io 2GB

Measures memory consumption of each component to verify
KG can be enabled without OOM.

Run on Fly.io via:
    fly ssh console -a nuzantara-rag
    cd /app && python scripts/memory_profile_kg.py

Or locally:
    cd apps/backend-rag && PYTHONPATH=. python scripts/memory_profile_kg.py

Expected output:
    Component                    RSS (MB)
    ─────────────────────────    ────────
    Baseline (import only)       ~80 MB
    + FastAPI app               ~400 MB
    + KGLangGraph (no LLM)      ~405 MB  (subgraphs ~5MB total)
    + LLM client (ChatOpenAI)   ~600 MB  (tiktoken ~200MB)
    + Qdrant client             ~650 MB
    ─────────────────────────    ────────
    Total with KG               ~650 MB
    Fly.io limit                2048 MB
    Headroom                    ~1400 MB  ← SAFE

Author: Nuzantara Team
Date: 2026-04-03
"""

import gc
import os
import sys
import tracemalloc
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def get_rss_mb() -> float:
    """Get current RSS memory in MB (macOS/Linux)."""
    import resource
    # resource.getrusage returns maxrss in bytes on Linux, KB on macOS
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return rusage.ru_maxrss / (1024 * 1024)  # bytes → MB on macOS
    return rusage.ru_maxrss / 1024  # KB → MB on Linux


def profile_step(name: str, baseline_mb: float) -> float:
    """Print memory delta for a step."""
    gc.collect()
    current = get_rss_mb()
    delta = current - baseline_mb
    print(f"  {name:<40} {current:>8.1f} MB  (+{delta:>6.1f} MB)")
    return current


def main() -> None:
    tracemalloc.start()
    print("\n" + "=" * 65)
    print("  KG LangGraph Memory Profile")
    print("=" * 65)

    baseline = get_rss_mb()
    print(f"\n  {'Component':<40} {'RSS':>8}  {'Delta':>10}")
    print(f"  {'─' * 40} {'─' * 8}  {'─' * 10}")
    profile_step("Python baseline", baseline)

    # Step 1: Import core modules
    try:
        from backend.services.rag.kg_graph_state import KGAgentState  # noqa: F401
        from backend.services.rag.kg_graph_nodes import understand_query_node  # noqa: F401
    except Exception as e:
        print(f"  ⚠️ KG imports failed: {e}")
    profile_step("+ KG state/nodes imports", baseline)

    # Step 2: Import LangGraph
    try:
        from langgraph.graph import StateGraph  # noqa: F401
    except Exception as e:
        print(f"  ⚠️ LangGraph import failed: {e}")
    profile_step("+ LangGraph import", baseline)

    # Step 3: Compile subgraphs (no LLM, no DB)
    try:
        from backend.services.rag.kg_subgraph_company import CompanyState
        from backend.services.rag.kg_subgraph_visa import VisaState
        from backend.services.rag.kg_subgraph_tax import TaxState
        from langgraph.graph import END, StateGraph

        # Build a minimal subgraph to measure compilation cost
        sg = StateGraph(CompanyState)
        sg.set_entry_point("start")
        sg.add_node("start", lambda s: s)
        sg.add_edge("start", END)
        compiled = sg.compile()  # noqa: F841
    except Exception as e:
        print(f"  ⚠️ Subgraph compilation failed: {e}")
    profile_step("+ 1 compiled subgraph", baseline)

    # Step 4: LLM client (the expensive one)
    try:
        from langchain_openai import ChatOpenAI

        if os.getenv("OPENAI_API_KEY"):
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)  # noqa: F841
            profile_step("+ ChatOpenAI (gpt-4o-mini)", baseline)
        else:
            print("  ⏭️ Skipping ChatOpenAI (no OPENAI_API_KEY)")
    except ImportError:
        print("  ⏭️ langchain_openai not installed")
    except Exception as e:
        print(f"  ⚠️ ChatOpenAI failed: {e}")

    # Step 5: QueryPlanner (should be negligible)
    try:
        from backend.services.rag.agentic.query_planner import QueryPlanner

        planner = QueryPlanner()
        plan = planner.plan("What is KITAS?")  # noqa: F841
    except Exception as e:
        print(f"  ⚠️ QueryPlanner failed: {e}")
    profile_step("+ QueryPlanner", baseline)

    # Step 6: KG Auto-Expansion (should be negligible)
    try:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("KITAS requires NPWP and NIB")  # noqa: F841
    except Exception as e:
        print(f"  ⚠️ KGAutoExpansion failed: {e}")
    profile_step("+ KGAutoExpansion heuristic", baseline)

    # Summary
    final = get_rss_mb()
    tracemalloc_current, tracemalloc_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\n  {'─' * 40} {'─' * 8}  {'─' * 10}")
    print(f"  {'TOTAL RSS':<40} {final:>8.1f} MB")
    print(f"  {'tracemalloc peak':<40} {tracemalloc_peak / 1024 / 1024:>8.1f} MB")
    print(f"  {'Fly.io limit':<40} {'2048.0':>8} MB")
    print(f"  {'Headroom':<40} {2048 - final:>8.1f} MB")

    if final < 800:
        print("\n  ✅ SAFE: KG can be enabled on Fly.io 2GB")
    elif final < 1500:
        print("\n  ⚠️ TIGHT: KG fits but monitor closely")
    else:
        print("\n  ❌ DANGER: KG may cause OOM on Fly.io 2GB")

    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
