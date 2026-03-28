#!/usr/bin/env python3
"""
Live comparison: Ollama local vs Gemini API for title generation.

Run: cd apps/backend-rag && PYTHONPATH=. python backend/scripts/test_ollama_vs_gemini.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


TEST_MESSAGES = [
    # Italian
    ("it_1", "Come aprire una PT PMA a Bali? Vorrei capire i requisiti e i costi"),
    ("it_2", "Quanto costa il visto KITAS per un anno?"),
    ("it_3", "Ciao, mi puoi aiutare con la registrazione NIB?"),
    # English
    ("en_1", "What are the requirements for a work permit in Indonesia?"),
    ("en_2", "I need help understanding the tax obligations for foreign companies"),
    ("en_3", "Can you explain the difference between PT PMA and PT PMDN?"),
    # Indonesian
    ("id_1", "Bagaimana cara mendaftarkan perusahaan asing di Indonesia?"),
    ("id_2", "Berapa biaya pembuatan visa kerja KITAS?"),
    # Short
    ("short_1", "KBLI 47911 apa itu?"),
    # Long
    (
        "long_1",
        "Ho bisogno di aprire una società a Bali per un progetto di e-commerce, voglio vendere prodotti artigianali balinesi online e ho bisogno di capire quale tipo di società è meglio, PT PMA o CV, e quali sono i costi e i tempi",
    ),
]


async def test_ollama_titles():
    """Test title generation via Ollama."""
    from backend.llm.ollama_client import MODEL_FAST, is_ollama_available, ollama_chat

    available = await is_ollama_available(MODEL_FAST)
    if not available:
        print(f"❌ Ollama not available or {MODEL_FAST} not loaded")
        return {}

    print(f"\n{'=' * 70}")
    print(f"🟢 OLLAMA ({MODEL_FAST}) — Local, Free")
    print(f"{'=' * 70}")

    results = {}
    total_time = 0

    for test_id, message in TEST_MESSAGES:
        prompt = f"""Generate a concise, professional title (max 50 characters) for a conversation starting with this message:

"{message[:200]}"

Requirements:
- Professional and clear
- Under 50 characters
- No quotes or special formatting
- Capture main topic/intent
- Language: Match the input language

Return ONLY the title text, nothing else."""

        start = time.perf_counter()
        result = await ollama_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_FAST,
            temperature=0.3,
            max_tokens=60,
            timeout=15.0,
        )
        elapsed = (time.perf_counter() - start) * 1000

        title = result.strip().strip('"').strip("'") if result else "FAILED"
        # Clean thinking tags if any
        if "<think>" in title:
            title = title.split("</think>")[-1].strip()
        title = title[:50]

        results[test_id] = {"title": title, "ms": elapsed}
        total_time += elapsed
        print(f"  [{test_id:8s}] {elapsed:6.0f}ms → {title}")

    avg = total_time / len(TEST_MESSAGES)
    print(f"\n  ⏱️  Average: {avg:.0f}ms | Total: {total_time:.0f}ms | Cost: $0.00")
    return results


async def test_gemini_titles():
    """Test title generation via Gemini Flash API."""
    try:
        from backend.llm.genai_client import get_genai_client
    except ImportError:
        print("❌ GenAI client not importable")
        return {}

    client = get_genai_client()
    if not client or not client.is_available:
        print("❌ Gemini client not available (check GOOGLE_API_KEY)")
        return {}

    print(f"\n{'=' * 70}")
    print("🔵 GEMINI FLASH (API) — Google Cloud")
    print(f"{'=' * 70}")

    results = {}
    total_time = 0

    for test_id, message in TEST_MESSAGES:
        prompt = f"""Generate a concise, professional title (max 50 characters) for a conversation starting with this message:

"{message[:200]}"

Requirements:
- Professional and clear
- Under 50 characters
- No quotes or special formatting
- Capture main topic/intent
- Language: Match the input language

Return ONLY the title text, nothing else."""

        start = time.perf_counter()
        try:
            result = await client.generate_content(
                contents=prompt,
                model="gemini-2.0-flash-lite",
                max_output_tokens=30,
                temperature=0.3,
            )
            title = (
                result.get("text", "").strip().strip('"').strip("'")[:50] if result else "FAILED"
            )
        except Exception as e:
            title = f"ERROR: {e}"

        elapsed = (time.perf_counter() - start) * 1000
        results[test_id] = {"title": title, "ms": elapsed}
        total_time += elapsed
        print(f"  [{test_id:8s}] {elapsed:6.0f}ms → {title}")

    avg = total_time / len(TEST_MESSAGES)
    cost = len(TEST_MESSAGES) * 0.000003
    print(f"\n  ⏱️  Average: {avg:.0f}ms | Total: {total_time:.0f}ms | Cost: ~${cost:.6f}")
    return results


async def compare():
    """Run both and compare side by side."""
    print("\n" + "🏁 TITLE GENERATION: OLLAMA vs GEMINI — LIVE COMPARISON")
    print(f"   Tests: {len(TEST_MESSAGES)} messages (IT/EN/ID/short/long)\n")

    ollama_results = await test_ollama_titles()
    gemini_results = await test_gemini_titles()

    if ollama_results and gemini_results:
        print(f"\n{'=' * 70}")
        print("📊 SIDE-BY-SIDE COMPARISON")
        print(f"{'=' * 70}")
        print(f"{'ID':10s} | {'Ollama':40s} | {'Gemini':40s}")
        print(f"{'-' * 10}-+-{'-' * 40}-+-{'-' * 40}")

        for test_id, _ in TEST_MESSAGES:
            o = ollama_results.get(test_id, {})
            g = gemini_results.get(test_id, {})
            o_title = o.get("title", "N/A")[:38]
            g_title = g.get("title", "N/A")[:38]
            o_ms = o.get("ms", 0)
            g_ms = g.get("ms", 0)
            winner = "🟢" if o_ms < g_ms else "🔵"
            print(f"{test_id:10s} | {o_title:38s} | {g_title:38s} {winner}")

        # Summary
        o_avg = sum(r["ms"] for r in ollama_results.values()) / len(ollama_results)
        g_avg = sum(r["ms"] for r in gemini_results.values()) / len(gemini_results)
        speedup = g_avg / o_avg if o_avg > 0 else 0

        print(
            f"\n  Ollama avg: {o_avg:.0f}ms | Gemini avg: {g_avg:.0f}ms | Speedup: {speedup:.1f}x",
        )
        print("  Cost saved: 100% (Ollama is free)")


if __name__ == "__main__":
    asyncio.run(compare())
