#!/usr/bin/env python3
"""WR2 Manual Topic Injection Runner.

Entry point per Antonello/Damar che salta selezione topic autonoma e
invia direttamente topic+report al wr2-design-architect via Claude CLI.

Workflow:
1. Accept topic (string) + report (text or file path)
2. Build prompt structured for wr2-design-architect Step 2 (skip Step 1
   topic selection)
3. Invoke `claude -p` with the wr2-design-architect agent definition
4. Watch stdout for sub-agent invocations + NB queries + image-prompt-author
   calls + critic verdicts
5. Capture full transcript to observation log
6. Final carousel slides + queue entry

Usage:
    python3 _manual_inject_runner.py \\
        --topic "KEP-71 SPT extension" \\
        --report-file ~/Desktop/research/spt-research.md \\
        --archetype regulatory-explainer

Or inline:
    python3 _manual_inject_runner.py \\
        --topic "KEP-71 SPT extension" \\
        --report-text "DJP signed KEP-71/PJ/2026..."
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OBS_DIR = Path.home() / ".claude/skills/bali-zero-brand/_observations"
OBS_DIR.mkdir(parents=True, exist_ok=True)

ARCHETYPES = [
    "regulatory-explainer", "news-flash", "quote-led", "anti-cliche",
    "story-driven", "comparison", "calendar-tracker", "testimonial-data",
    "cultural-insight",
]


def build_prompt(topic: str, report: str, archetype: str | None,
                 audience_hint: str | None, register_hint: str | None,
                 primary_regulation_code: str | None = None,
                 primary_source_url: str | None = None,
                 qr_caption: str | None = None) -> str:
    """Build the prompt that activates wr2-design-architect with a manual
    topic+report (skipping autonomous topic selection)."""
    parts = [
        "You are wr2-design-architect. Skip the topic-selection step.",
        "A human (Antonello / Damar) has already chosen the topic and",
        "provided a research report. Your job: produce a complete carousel",
        "package using your standard pipeline, starting from Step 2 (brief",
        "interpretation), all the way through Step 7 (queue handoff).",
        "",
        "## INPUT",
        "",
        f"**Topic**: {topic}",
        "",
        "**Research report**:",
        "",
        "```markdown",
        report,
        "```",
        "",
    ]
    if archetype:
        parts += [f"**Archetype hint**: `{archetype}` (from Article 13 closed taxonomy)", ""]
    if audience_hint:
        parts += [f"**Audience hint**: `{audience_hint}`", ""]
    if register_hint:
        parts += [f"**Register hint**: `{register_hint}`", ""]
    # Article 14 SOTA brief fields (added 2026-05-12)
    if primary_regulation_code:
        parts += [f"**Primary regulation code** (Art 14.4 — renders as red badge top-right on cover): `{primary_regulation_code}`", ""]
    if primary_source_url:
        parts += [f"**Primary source URL** (Art 14.5 deferred — when enabled, renders as QR code on elegant-close): `{primary_source_url}`", ""]
    if qr_caption:
        parts += [f"**QR caption** (Art 14.5 deferred — caption above QR code): `{qr_caption}`", ""]

    parts += [
        "## REQUIREMENTS",
        "",
        "1. Load brand cortex (constitution, tokens, voice, anchors) as Step 1.",
        "2. Build the structured brief from the provided report — DO NOT",
        "   invent facts not in the report. If a fact is missing and you",
        "   need it, query NB-1/4/5 via `nlm query notebook ...` and log the",
        "   query. Cite sources for every regulatory claim.",
        "3. Storyboard 4-10 slides per the chosen archetype.",
        "4. Author original image prompts (vary across image-style modes —",
        "   no monotone desk-document repetition).",
        "5. Compose HTML, render PNG, run critic 4-rubric.",
        "6. Write outputs to",
        "   `~/nuzantara/apps/war-room/output/carousel/<slug>/`.",
        "7. Append entry to queue.json so it appears in Damar UI.",
        "",
        "## RULES",
        "",
        "- ABSOLUTELY NO INVENTED FACTS. Every regulatory citation,",
        "  number, date must trace to the report or to a NB query log.",
        "- Skip the autonomous topic-selection step (Step 1 of standard",
        "  pipeline) — topic is given.",
        "- If the report is too thin for a carousel, abort with",
        "  `STATUS: report_insufficient` and explain what's missing.",
        "",
        "## OUTPUT",
        "",
        "Final response: one-line summary (`READY <slug>`) plus the queue",
        "entry path. Detailed pipeline steps go to stdout for observability.",
    ]
    return "\n".join(parts)


def run_design_architect(prompt: str, obs_log: Path) -> tuple[int, str]:
    """Invoke wr2-design-architect via claude -p subprocess.

    Returns (exit_code, transcript). Defense-in-depth: strip ANTHROPIC_API_KEY
    from env before spawning (CLAUDE.md HARD RULE — only OAuth claude CLI).
    """
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    # Ensure ~/.local/bin and homebrew are in PATH for claude CLI lookup
    extra_paths = "/Users/nuzantara/.local/bin:/opt/homebrew/bin"
    env["PATH"] = extra_paths + ":" + env.get("PATH", "/usr/bin:/bin")

    # Use absolute path to avoid PATH lookup failures in detached subprocesses
    claude_bin = "/Users/nuzantara/.local/bin/claude"
    if not Path(claude_bin).exists():
        # Fallback: try homebrew path
        claude_bin = "/opt/homebrew/bin/claude"

    cmd = [
        claude_bin, "-p",
        "--model", "claude-opus-4-8",
        "--agent", "wr2-design-architect",  # explicit agent invocation
        # bypassPermissions is required: this is a DETACHED subprocess that cannot
        # answer an interactive permission prompt. The trust boundary is therefore
        # UPSTREAM, not here: the only caller is _damar-queue-server.py's
        # /api/inject-topic, which is CSRF/Origin-gated + localhost-bound (#1708).
        # Do NOT expose this runner to any un-gated input source.
        "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",  # observable: tool calls + sub-agent events
        "--include-partial-messages",
        "--verbose",  # required for stream-json
    ]
    obs_log.parent.mkdir(parents=True, exist_ok=True)
    with obs_log.open("w") as log:
        log.write(f"=== WR2 manual injection — {datetime.now(timezone.utc).isoformat()} ===\n\n")
        log.write("=== PROMPT ===\n")
        log.write(prompt)
        log.write("\n\n=== TRANSCRIPT ===\n")
        log.flush()

        # Streaming pattern: write prompt to stdin, tee stdout line-by-line
        # to log file in real time (NOT capture_output which buffers until exit).
        # This is what makes the observation log usable while pipeline runs.
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=env,
            bufsize=1,  # line-buffered
        )
        # Write prompt + close stdin so claude can start
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except BrokenPipeError:
            pass

        transcript_lines = []
        deadline = None  # 1h soft cap via wall-clock check on each line
        import time
        start = time.time()
        try:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                transcript_lines.append(line)
                if time.time() - start > 3600:
                    log.write("\n\n=== TIMEOUT after 3600s — killing process ===\n")
                    proc.kill()
                    proc.wait(timeout=10)
                    return 124, "timeout"
            rc = proc.wait()
        except KeyboardInterrupt:
            proc.kill()
            log.write("\n\n=== INTERRUPTED ===\n")
            return 130, "interrupted"

        log.write(f"\n\n=== EXIT {rc} ===\n")
    return rc, "".join(transcript_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Manually inject a topic+report to wr2-design-architect."
    )
    parser.add_argument("--topic", required=True, help="Carousel topic")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--report-file", help="Path to research report (md/txt)")
    src.add_argument("--report-text", help="Inline report text")
    parser.add_argument("--archetype", choices=ARCHETYPES,
                        default="regulatory-explainer",
                        help="Archetype hint (Article 13)")
    parser.add_argument("--audience", default=None,
                        help="founder | investor | digital-nomad | retiree | mass-tourist")
    parser.add_argument("--register", default=None,
                        help="rituale | analitico | ironico | militante | pedagogico | poetico | tecnico")
    parser.add_argument("--primary-regulation-code", default=None,
                        help="Article 14.4 — e.g. 'KEP-71/PJ/2026'; renders as red badge top-right on cover")
    parser.add_argument("--primary-source-url", default=None,
                        help="Article 14.5 deferred — e.g. 'https://pajak.go.id/...'; QR code target")
    parser.add_argument("--qr-caption", default=None,
                        help="Article 14.5 deferred — caption above QR (default 'PRIMARY SOURCE' / 'SUMBER ASLI')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the prompt and exit, without invoking claude")
    args = parser.parse_args()

    if args.report_file:
        report = Path(args.report_file).expanduser().read_text()
    else:
        report = args.report_text

    prompt = build_prompt(args.topic, report, args.archetype,
                          args.audience, args.register,
                          args.primary_regulation_code,
                          args.primary_source_url,
                          args.qr_caption)

    if args.dry_run:
        print(prompt)
        return 0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug_safe = "".join(c if c.isalnum() else "-" for c in args.topic.lower())[:60].strip("-")
    obs_log = OBS_DIR / f"{timestamp}__{slug_safe}.log"

    print(f"=== WR2 manual injection ===")
    print(f"Topic: {args.topic}")
    print(f"Archetype: {args.archetype}")
    print(f"Report length: {len(report)} chars")
    print(f"Observation log: {obs_log}")
    print(f"Invoking wr2-design-architect via claude -p (Opus 4.7, OAuth)...")
    print()

    exit_code, transcript = run_design_architect(prompt, obs_log)

    if exit_code == 0:
        print(f"\n✓ Pipeline completed. Transcript saved.")
        print(f"  Log: {obs_log}")
        # Show last 30 lines of transcript for quick observation
        print("\n--- Last 30 lines of transcript ---")
        for line in transcript.splitlines()[-30:]:
            print(f"  {line}")
    else:
        print(f"\n✗ Pipeline failed (exit {exit_code}). Check log: {obs_log}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
