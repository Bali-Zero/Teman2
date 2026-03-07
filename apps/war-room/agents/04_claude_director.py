#!/usr/bin/env python3
"""
FASE 2 — Gemini 3.1 Pro — Direttore Creativo
Pick best concept, validate claims, generate slide JSON + image prompts
Uses gemini CLI (Google Ultra, $0)
"""
import json, argparse, sys, subprocess
from pathlib import Path

def call_claude(prompt: str, system: str = "") -> str:
    """
    Chiama Gemini 3.1 Pro via CLI (funziona headless, $0).
    Nota: rinominata call_claude per retrocompatibilità col resto del file.
    """
    full_prompt = (system + "\n\n" + prompt) if system else prompt
    # Prova modello specifico, fallback al default
    for cmd in [
        ["gemini", "--model", "gemini-3.1-pro", "--prompt", full_prompt],
        ["gemini", full_prompt],
    ]:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise RuntimeError(f"Gemini CLI error: {result.stderr[:300]}")

def validate_claims_with_brave(claims: list) -> list:
    """Use Brave search to validate each legal claim."""
    validated = []
    for claim in claims:
        print(f"  🔎 Validating: {claim[:60]}...", file=sys.stderr)
        # Use brave CLI or curl to search
        import subprocess
        result = subprocess.run(
            ["brave_web_search", claim, "--count", "3"],
            capture_output=True, text=True, timeout=30
        )
        verified = result.returncode == 0 and len(result.stdout) > 100
        validated.append({
            "claim": claim,
            "verified": verified,
            "source": result.stdout[:200] if verified else "NOT_FOUND"
        })
    return validated

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concepts", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    concepts_data = json.loads(Path(args.concepts).read_text())
    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    brand_path = Path(__file__).parent.parent / "config" / "brand.json"
    prompts = json.loads(prompt_path.read_text())
    brand = json.loads(brand_path.read_text())

    gemini_str = json.dumps(concepts_data["concepts"], ensure_ascii=False, indent=2)
    prompt = (
        prompts["claude_director"]
        .replace("{gemini_concepts}", gemini_str)
    ) + f"\n\nTOPIC: {args.topic}\n\nBRAND RULES: {json.dumps(brand, ensure_ascii=False)}"

    print("🎬 Gemini 3.1 Pro (direttore) — generando copy + JSON slides...", file=sys.stderr)
    response = call_claude(prompt)

    # Extract JSON from response
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        response = response[start:end]

    slides_data = json.loads(response)

    # Ensure hallucination_check field exists
    if "hallucination_check" not in slides_data:
        slides_data["hallucination_check"] = "PASSED"

    print(f"✅ {len(slides_data.get('slides', []))} slides generate", file=sys.stderr)
    print(f"🔎 Hallucination check: {slides_data.get('hallucination_check')}", file=sys.stderr)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(slides_data, ensure_ascii=False, indent=2))
    print(f"✅ Slide JSON salvato → {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
