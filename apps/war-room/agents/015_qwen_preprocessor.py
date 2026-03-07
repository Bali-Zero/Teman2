#!/usr/bin/env python3
"""
FASE 1.5 — Qwen3-32B Pre-Processor
Runs Qwen3-32B via Ollama locale (MacBook Pro M4 48GB)
Zero cost — locale
"""
import json, argparse, sys, subprocess
from pathlib import Path

def run_qwen_on_pro(prompt: str) -> str:
    """Chiama Qwen3:32b via Ollama locale — siamo sul Pro M4 48GB."""
    result = subprocess.run(
        ["ollama", "run", "qwen3:32b", "--nowordwrap"],
        input=prompt, capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"Qwen3 error: {result.stderr}")
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grok", required=False, default="")
    parser.add_argument("--manus", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    grok_path = Path(args.grok) if args.grok else None
    grok_data = json.loads(grok_path.read_text()) if grok_path and grok_path.exists() else []
    manus_data = json.loads(Path(args.manus).read_text())

    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    prompts = json.loads(prompt_path.read_text())

    prompt = prompts["qwen_preprocessor"] + f"""

RAW GROK DATA:
{json.dumps(grok_data, ensure_ascii=False, indent=2)}

MANUS LEGAL FACTS:
{json.dumps(manus_data, ensure_ascii=False, indent=2)}

Output ONLY valid JSON. No markdown, no prose."""

    print("🔄 Qwen3-32B pre-processor (Ollama locale Pro M4 48GB)...", file=sys.stderr)
    response = run_qwen_on_pro(prompt)

    # Extract JSON from response
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()

    # Find JSON boundaries
    if "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        response = response[start:end]

    result = json.loads(response)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"✅ Pre-processed dump → {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
