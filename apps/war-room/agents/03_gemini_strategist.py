#!/usr/bin/env python3
"""
FASE 2 — Gemini 3.1 Pro Deep Think — Stratega di Business
Produce 3 narrative concepts asimmetrici dal dump processato
"""
import json, argparse, sys, subprocess
from pathlib import Path

def run_gemini(prompt: str) -> str:
    """Call Gemini via CLI (gemini -p "prompt")."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gemini error: {result.stderr}")
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dump_data = json.loads(Path(args.dump).read_text())
    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    prompts = json.loads(prompt_path.read_text())

    grok_str  = json.dumps(dump_data.get("grok_summary", dump_data), ensure_ascii=False, indent=2)
    manus_str = json.dumps(dump_data.get("manus_summary", {}), ensure_ascii=False, indent=2)
    prompt = (
        prompts["gemini_strategist"]
        .replace("{grok_dump}",  grok_str)
        .replace("{manus_dump}", manus_str)
    ) + f"\n\nTOPIC FOCUS: {args.topic}\n\nOutput ONLY valid JSON array of 3 concepts."

    print(f"🧠 Gemini 3.1 Pro thinking...", file=sys.stderr)
    response = run_gemini(prompt)

    # Extract JSON
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "[" in response:
        start = response.find("[")
        end = response.rfind("]") + 1
        response = response[start:end]

    concepts = json.loads(response)

    output = {
        "topic": args.topic,
        "model": "gemini-3.1-pro",
        "concepts": concepts,
        "count": len(concepts)
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"✅ {len(concepts)} concept generati → {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
