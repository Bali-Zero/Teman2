#!/usr/bin/env python3
"""Phase 1: Generate editorial content for all KBLI codes.
HIGH tier: NLM + DeepSeek-R1:32b (3 narrative) + deterministic (3 structured)
MEDIUM tier: Qwen3.5:9b (3 narrative) + deterministic (3 structured)
LOW tier: Qwen3.5:9b (whatItMeans only) + deterministic (3 structured)
"""
import json
import re
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
DEEPSEEK_MODEL = "deepseek-r1:32b"
QWEN_MODEL = "qwen3.5:9b"

# Reuse the exact system prompt from generate_gold_content.py
# It asks for 3 fields: whatItMeans, baliContext, zantaraOpener
SYSTEM_PROMPT_3FIELDS = """You are an expert on Indonesian business law writing precise, useful content for foreign investors in Bali.

For each KBLI 2025 business code provided, generate THREE fields:

1. whatItMeans: Plain English explanation, 3-4 sentences, ~250-400 chars.
   - Lead with the core activity using a dash
   - Name SPECIFIC examples from the uraian — translate them
   - Include scope clarifications when the uraian mentions them
   - Translate ALL Indonesian terms. No bureaucratic language.

2. baliContext: Bali-specific practical intelligence, 3-5 sentences, ~350-550 chars.
   - Include at least ONE of: price range (IDR), Bali location, enforcement reality, named permit
   - Include ONE insider tip or common mistake specific to THIS code
   - Write in English

3. zantaraOpener: One conversational chatbot sentence, ~100-160 chars.
   - Start with Bali context
   - Be specific to the business activity

Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}]}
No extra text, no markdown fences."""

SYSTEM_PROMPT_DEEPSEEK = """You are a senior Indonesian regulatory analyst. You have access to NotebookLM regulatory intelligence below.

Using BOTH the raw KBLI data AND the regulatory context provided, generate THREE editorial fields for each KBLI code. Your output must be more detailed and regulatory-precise than generic LLM output because you have actual regulatory citations.

For each code generate:

1. whatItMeans: 3-5 sentences explaining the business activity in plain English. Include specific examples from the uraian. Mention what IS and is NOT covered. ~300-500 chars.

2. baliContext: 4-6 sentences of Bali-specific practical intelligence. Include: specific permits beyond NIB, enforcement realities, pricing/location specifics, insider tips. Reference the regulatory context provided. ~400-700 chars.

3. zantaraOpener: One conversational chatbot sentence, ~100-160 chars.

Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}]}
No extra text, no markdown fences."""

SYSTEM_PROMPT_MINIMAL = """For each KBLI code, write a plain English explanation of what this business activity covers.
2-3 sentences, ~200-300 chars. Lead with the core activity. Translate all Indonesian terms.
Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "..."}]}
No extra text."""


def ollama_generate(prompt: str, model: str, system: str = "", timeout: int = 360) -> str:
    """Call Ollama generate endpoint. Returns raw response text."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 8192},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def parse_llm_response(raw: str) -> list[dict]:
    """Parse LLM JSON response, handling markdown fences and thinking tags."""
    text = raw
    # Strip <think>...</think> blocks (DeepSeek-R1)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown fences
    if "```" in text:
        text = text.split("```json")[-1] if "```json" in text else text.split("```")[1]
        text = text.split("```")[0]
    text = text.strip()
    parsed = json.loads(text)
    return parsed.get("results", []) if isinstance(parsed, dict) else parsed


def generate_high_tier(codes: list[dict], nlm_contexts: dict[str, str], batch_size: int = 2) -> dict[str, dict]:
    """Generate 3 narrative fields for HIGH tier codes using DeepSeek-R1:32b + NLM context."""
    results = {}
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i:i + batch_size]
        prompt_parts = []
        for c in batch:
            code = c["kode_kbli_2025"]
            nlm = nlm_contexts.get(code, "No regulatory context available.")
            prompt_parts.append(
                f"code: {code}\njudul: {c['judul']}\n"
                f"uraian: {c.get('uraian', '')[:800]}\n"
                f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
                f"sektor_id: {c.get('sektor_id', 'N/A')}\n\n"
                f"--- REGULATORY CONTEXT (from NotebookLM) ---\n{nlm[:2000]}\n---"
            )

        prompt = "\n\n".join(prompt_parts)
        batch_ids = [c['kode_kbli_2025'] for c in batch]
        print(f"  HIGH batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}: {batch_ids}...", end="", flush=True)

        try:
            raw = ollama_generate(prompt, DEEPSEEK_MODEL, system=SYSTEM_PROMPT_DEEPSEEK, timeout=600)
            parsed = parse_llm_response(raw)
            for item in parsed:
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }
            print(f" ✓")
        except Exception as e:
            print(f" ✗ {e}")

    return results


def generate_medium_tier(codes: list[dict], batch_size: int = 5) -> dict[str, dict]:
    """Generate 3 narrative fields for MEDIUM tier codes using Qwen3.5:9b."""
    results = {}
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i:i + batch_size]
        prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\njudul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:600]}\n"
            f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
            f"sektor_id: {c.get('sektor_id', 'N/A')}"
            for c in batch
        )
        print(f"  MEDIUM batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}...", end="", flush=True)

        try:
            raw = ollama_generate(prompt, QWEN_MODEL, system=SYSTEM_PROMPT_3FIELDS)
            parsed = parse_llm_response(raw)
            for item in parsed:
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }
            print(f" ✓")
        except Exception as e:
            print(f" ✗ {e}")

    return results


def generate_low_tier(codes: list[dict], batch_size: int = 10) -> dict[str, dict]:
    """Generate whatItMeans only for LOW tier codes using Qwen3.5:9b."""
    results = {}
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i:i + batch_size]
        prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\njudul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:400]}"
            for c in batch
        )
        print(f"  LOW batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}...", end="", flush=True)

        try:
            raw = ollama_generate(prompt, QWEN_MODEL, system=SYSTEM_PROMPT_MINIMAL, timeout=180)
            parsed = parse_llm_response(raw)
            for item in parsed:
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {"whatItMeans": item.get("whatItMeans", "")}
            print(f" ✓")
        except Exception as e:
            print(f" ✗ {e}")

    return results
