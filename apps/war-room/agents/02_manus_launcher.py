#!/usr/bin/env python3
"""
FASE 1 — Manus AI Launcher (API REST)
Target: fonti gov/fiscali high-level (DDTC, Hukumonline, BKPM/DJP, CNBC Indonesia)

Uses Manus REST API instead of browser automation.
Requires MANUS_API_KEY environment variable.
"""
import json
import argparse
import sys
import os
import time
from pathlib import Path
from datetime import datetime

import httpx

MANUS_API_URL = "https://api.manus.ai/v1"
POLL_INTERVAL = 20  # seconds between status checks
MAX_WAIT = 600      # max 10 minutes


def create_task(api_key: str, prompt: str) -> dict:
    """Create a Manus task via REST API."""
    resp = httpx.post(
        f"{MANUS_API_URL}/tasks",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": api_key,
        },
        json={"prompt": prompt},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_task(api_key: str, task_id: str) -> dict:
    """Get task status and results via list endpoint (filtered)."""
    # List endpoint returns all tasks — filter by ID
    resp = httpx.get(
        f"{MANUS_API_URL}/tasks",
        headers={
            "accept": "application/json",
            "x-api-key": api_key,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    tasks = data.get("data", [])
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return {"status": "not_found", "task_id": task_id}


def wait_for_completion(api_key: str, task_id: str) -> dict:
    """Poll task until completed or timeout."""
    start = time.time()
    while time.time() - start < MAX_WAIT:
        task = get_task(api_key, task_id)
        status = task.get("status", "unknown")
        print(f"  [{int(time.time() - start)}s] Status: {status}", file=sys.stderr)

        if status in ("completed", "done", "COMPLETED", "DONE"):
            return task
        if status in ("failed", "error", "FAILED", "ERROR", "cancelled"):
            return task

        time.sleep(POLL_INTERVAL)

    return {"status": "timeout", "task_id": task_id}


def extract_facts(task_result: dict) -> list[dict]:
    """Extract structured facts from Manus task output."""
    # Manus API returns output as a list of message objects
    output = task_result.get("output", [])

    # Collect all text content from output messages
    all_text = ""
    if isinstance(output, list):
        for msg in output:
            content = msg.get("content", "")
            if isinstance(content, str):
                all_text += content + "\n"
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        all_text += part.get("text", "") + "\n"
    elif isinstance(output, str):
        all_text = output

    if not all_text.strip():
        return []

    # Try to parse as JSON
    try:
        parsed = json.loads(all_text.strip())
        if isinstance(parsed, list):
            return [{"title": str(item)[:200], "brief": str(item), "category": "gov", "source": "manus"} for item in parsed]
        if isinstance(parsed, dict) and "facts" in parsed:
            return parsed["facts"]
    except (json.JSONDecodeError, TypeError):
        pass

    # Split text into facts by newlines/bullets
    lines = [l.strip() for l in all_text.split("\n") if l.strip() and len(l.strip()) > 20]
    return [{"title": line[:200], "brief": line, "category": "gov", "source": "manus"} for line in lines[:30]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true", help="Skip confirmation (for cron/auto mode)")
    args = parser.parse_args()

    api_key = os.environ.get("MANUS_API_KEY", "")
    if not api_key:
        print("MANUS_API_KEY not set — skipping Manus", file=sys.stderr)
        result = {"facts": [], "skipped": True, "reason": "no_api_key"}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    prompts = json.loads(prompt_path.read_text())

    task_prompt = prompts["manus_task_template"].format(
        topic=args.topic,
        keywords="#OSS #Coretax #KITAS KBLI perizinan"
    )

    if not args.force:
        print(f"\n  MANUS AI — Topic: {args.topic}", file=sys.stderr)
        print(f"  Conferma con 'SI': ", end="", file=sys.stderr)
        response = input().strip().upper()
        if response != "SI":
            result = {"facts": [], "skipped": True, "reason": "user_cancelled"}
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)

    print(f"Lancio Manus API per: {args.topic}", file=sys.stderr)

    try:
        task_info = create_task(api_key, task_prompt)
        task_id = task_info.get("id", task_info.get("task_id", ""))
        if not task_id:
            raise RuntimeError(f"No task ID in creation response: {task_info}")
        print(f"Task creato: {task_id} — {task_info.get('task_url', '')}", file=sys.stderr)

        completed = wait_for_completion(api_key, task_id)
        status = completed.get("status", "unknown")

        if status in ("completed", "done", "COMPLETED", "DONE"):
            facts = extract_facts(completed)
            result = {
                "topic": args.topic,
                "scraped_at": datetime.now().isoformat(),
                "source": "Manus AI (API)",
                "task_id": task_id,
                "task_url": task_info.get("task_url", ""),
                "facts": facts,
                "raw_output": completed.get("output", completed.get("result", "")),
            }
            print(f"Manus completato: {len(facts)} facts estratti", file=sys.stderr)
        else:
            print(f"Manus non completato (status: {status})", file=sys.stderr)
            result = {
                "facts": [],
                "status": status,
                "task_id": task_id,
                "reason": f"task_{status}",
            }

    except Exception as e:
        print(f"Manus API error: {e}", file=sys.stderr)
        result = {"facts": [], "skipped": True, "reason": str(e)}

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Output salvato → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
