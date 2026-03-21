#!/usr/bin/env python3
"""
FASE 1.5 — Qwen3.5-27B Pre-Processor
Runs Qwen3.5-27B via Ollama REST API (localhost:11434)
Uses think:false to suppress chain-of-thought and get fast JSON output.
Zero cost — locale
"""
import json, argparse, sys, urllib.request, urllib.error
from pathlib import Path


def run_qwen_api(prompt: str) -> str:
    """Chiama Qwen3.5 via Ollama REST API — think:false, streaming, fast."""
    for model, timeout in [("qwen3.5:27b", 120), ("qwen3.5:9b", 90), ("gemma3:12b", 90)]:
        try:
            print(f"  Trying {model} via REST API (timeout={timeout}s)...", file=sys.stderr)
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "num_predict": 2048,
                    "temperature": 0.1,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "").strip()
                if text:
                    print(f"  {model} OK ({len(text)} chars)", file=sys.stderr)
                    return text
                print(f"  {model} empty response", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"  {model} connection error: {e}", file=sys.stderr)
        except TimeoutError:
            print(f"  {model} timeout — trying fallback", file=sys.stderr)
        except Exception as e:
            print(f"  {model} error: {e}", file=sys.stderr)
    raise RuntimeError("All Qwen/Gemma models failed via REST API")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentiment", required=False, default="")
    parser.add_argument("--research", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sentiment_path = Path(args.sentiment) if args.sentiment else None
    sentiment_data = json.loads(sentiment_path.read_text()) if sentiment_path and sentiment_path.exists() else []
    research_data = json.loads(Path(args.research).read_text())

    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    prompts = json.loads(prompt_path.read_text())

    # Tronca input per evitare prompt troppo lunghi
    facts_input = research_data.get("facts", research_data) if isinstance(research_data, dict) else research_data
    facts_trimmed = facts_input[:15] if isinstance(facts_input, list) else facts_input
    sentiment_trimmed = sentiment_data[:8] if isinstance(sentiment_data, list) else sentiment_data

    prompt = prompts["qwen_preprocessor"] + f"""

RAW SOCIAL SENTIMENT DATA:
{json.dumps(sentiment_trimmed, ensure_ascii=False, indent=2)}

FACTS:
{json.dumps(facts_trimmed, ensure_ascii=False, indent=2)}

Output ONLY valid JSON. No markdown, no prose, no explanation."""

    print("🔄 Qwen3.5-27B pre-processor (Ollama REST API, think:false)...", file=sys.stderr)

    try:
        response = run_qwen_api(prompt)
    except RuntimeError as e:
        print(f"  All models failed: {e} — using passthrough fallback", file=sys.stderr)
        result = {
            "facts": research_data.get("facts", []) if isinstance(research_data, dict) else research_data,
            "sentiment": research_data.get("sentiment", []) if isinstance(research_data, dict) else [],
            "topics": research_data.get("topics", []) if isinstance(research_data, dict) else [],
            "fallback": True,
        }
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"✅ Passthrough dump → {args.output}", file=sys.stderr)
        return

    # Extract JSON from response
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()

    # Strip any <think>...</think> block if model ignores think:false
    if "<think>" in response:
        end_think = response.rfind("</think>")
        if end_think != -1:
            response = response[end_think + len("</think>"):].strip()

    # Find JSON boundaries
    if "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        response = response[start:end]

    try:
        result = json.loads(response)
    except json.JSONDecodeError as e:
        print(f"Qwen output invalid JSON ({e}) — passthrough fallback", file=sys.stderr)
        result = None

    # Normalize: ensure expected keys exist (model may use different schema)
    if result is not None:
        src = research_data if isinstance(research_data, dict) else {}
        # Remap alternative key names to expected schema
        if "facts" not in result:
            # Try common alternative keys the model might use
            for alt in ("top_15_representative_posts", "legal_facts", "posts", "items", "data"):
                if alt in result:
                    result["facts"] = result.pop(alt)
                    break
            if "facts" not in result:
                result["facts"] = src.get("facts", [])
        if "sentiment" not in result:
            for alt in ("deduplicated_posts", "sentiment_posts", "classified_posts"):
                if alt in result:
                    result["sentiment"] = result.pop(alt)
                    break
            if "sentiment" not in result:
                result["sentiment"] = src.get("sentiment", [])
        if "topics" not in result:
            result["topics"] = src.get("topics", [])
    else:
        result = {
            "facts": research_data.get("facts", []) if isinstance(research_data, dict) else research_data,
            "sentiment": research_data.get("sentiment", []) if isinstance(research_data, dict) else [],
            "topics": research_data.get("topics", []) if isinstance(research_data, dict) else [],
            "fallback": True,
        }

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"✅ Pre-processed dump → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
