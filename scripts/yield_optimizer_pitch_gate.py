#!/usr/bin/env python3
"""yield-optimizer PII fail-closed gate — deterministic Ollama-only pitch drafting.

`yield-optimizer` (`~/.claude/agents/yield-optimizer.md`, cron Sunday 04:00 WITA
on Pro via `infra/launchagents/wrappers/yield-optimizer-run.sh` ->
`claude-cascade.sh --agent yield-optimizer`) is a Claude Sonnet-5 AGENT, not a
Python daemon. Its own hard rule #1 — "CRM data NEVER to cloud LLM... Ollama
LOCAL only" — and its Failure-modes rule — "Ollama unreachable: STOP, no
fallback to cloud" — used to live ONLY as prose an LLM has to remember every
run: compliance for an autonomous agent, not a cancello in code (CLAUDE.md §14:
"il fail-closed e' la condotta richiesta, non uno stato gia' implementato").

This script IS that cancello. It is the ONLY sanctioned way for the agent's
Step 3 (draft pitch) to turn a CRM opportunity into WhatsApp pitch text:

  - The only model this file EVER calls is local Ollama, over its LOCAL HTTP
    API (127.0.0.1 by default). Nothing else is imported or shelled out to --
    no `claude`/`agy`/`kimi`/`codex` CLI, no `anthropic`/`openai`/
    `google.generativeai` SDK, no request to any non-localhost host.
    `test_no_cloud_references_in_file` in the paired test module pins this as
    a class-guard: any future edit that adds one of those tokens to THIS file
    goes red.
  - On Ollama failure (down, timeout, empty/bad response) the outcome is a
    named TERMINAL state, `SKIPPED_OLLAMA_FAIL` -- never a silent retry on a
    different backend, and no pitch text is ever returned for that
    opportunity. There is no cloud branch in this file to fall through to.
    Unlike `mos-plus-compression-worker.py`'s `choose_tier()` (which
    legitimately routes non-sensitive traffic to cloud tiers), this lane has
    no non-sensitive traffic at all -- every payload is a CRM client record --
    so `choose_tier()` below has nowhere to degrade a non-sensitive call TO;
    it raises instead (see its docstring).
  - Every call is logged to `YIELD_OPTIMIZER_GATE_LOG` with `client_id` +
    outcome ONLY -- client name/contact/case facts are never written to the
    log (yield-optimizer.md hard rule #5: "log only client_id, not name").
    This makes a rejection auditable rather than a silent no-op (cicatrix
    W114/W116: an astensione muta e' indistinguibile da "non e' mai partito").

Same shape as the three other hardened local-only PII lanes (censimento
2026-08-20):
  - wa-mirror-attention-classifier.py: exception -> default MEDIUM tagged
    `ollama_fail:*`, never cloud.
  - mos-plus-compression-worker.py::choose_tier(): `osint_sensitive` ->
    "ollama_local" hard-coded; retry stays local ("ollama_fallback").
  - wa-mirror-strategic-recap-updater.py: failure -> `action =
    "SKIPPED_OLLAMA_FAIL"`.

The Ollama HTTP-API pattern (`ollama_up()` / generate call) is reused from
`scripts/s7_yield_draft_local.py` (reuse-first) rather than re-derived --
that script is a separate, ALREADY-DETERMINISTIC, schema-correct rebuild of
this whole lane (real CRM schema, hard `sys.exit` before any PII read if
Ollama is down) that currently sits unarmed (no plist/cron references it).
Whether to retire the agent-based lane in favor of it is a business-logic
call outside this PR's scope: this file touches only the drafting boundary
of the lane that is actually scheduled today.

CLI usage -- payload via STDIN ONLY, never argv (a client fact on argv is
readable by any other user on the machine via `ps`; cicatrix W115 GOTCHA-3
caught exactly this in a sibling script):

    echo '{"client_id": "C123", "name": "Budi",
           "language": "Indonesian (Bahasa Indonesia)",
           "fact": "Their KITAS expires in 23 days (2026-09-12).",
           "pitch_goal": "renewal + KITAP eligibility check"}' \\
        | python3 scripts/yield_optimizer_pitch_gate.py

Exit codes: 0 = drafted (pitch text on stdout) · 2 = SKIPPED_OLLAMA_FAIL
(terminal -- nothing on stdout, the caller MUST skip this opportunity, never
retry on another backend) · 1 = bad input (malformed JSON / missing
client_id).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OLLAMA_HOST = os.environ.get("YIELD_OPTIMIZER_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"
OLLAMA_GENERATE_URL = f"{OLLAMA_HOST}/api/generate"
OLLAMA_MODEL = os.environ.get("YIELD_OPTIMIZER_OLLAMA_MODEL", "qwen3.5:9b")
GATE_LOG = Path(
    os.environ.get(
        "YIELD_OPTIMIZER_GATE_LOG",
        str(Path.home() / "logs" / "yield-optimizer-pii-gate.jsonl"),
    )
)

SKIPPED_OLLAMA_FAIL = "SKIPPED_OLLAMA_FAIL"
OLLAMA_LOCAL = "ollama_local"


def choose_tier(sensitive: bool) -> str:
    """Return the tier for drafting a yield-optimizer pitch.

    yield-optimizer processes ONLY CRM client records (name, contact info,
    case facts) -- there is no non-sensitive payload shape in this lane,
    unlike mos-plus-compression-worker's mixed traffic. `sensitive` exists so
    this function has the same guilt+innocence surface as the other hardened
    lanes' tier-choice functions; every real call site in this file passes
    sensitive=True. `sensitive=False` RAISES rather than degrading anywhere --
    there is no cloud tier wired into this script to degrade TO, so a False
    here is a caller bug, not a policy choice.
    """
    if not sensitive:
        raise ValueError(
            "yield-optimizer pitch drafting has no non-sensitive payload "
            "class -- this call site is a bug, not a policy choice"
        )
    return OLLAMA_LOCAL


def ollama_up(timeout: float = 3.0) -> bool:
    try:
        urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=timeout).read()
        return True
    except Exception:
        return False


def _log_outcome(client_id: str, outcome: str, detail: str = "") -> None:
    """Append one JSONL line. `client_id` ONLY -- never name/contact/facts
    (yield-optimizer.md hard rule #5)."""
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with GATE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "client_id": client_id,
                    "outcome": outcome,
                    "detail": detail,
                }
            )
            + "\n"
        )


def build_prompt(name: str, language: str, fact: str, pitch_goal: str) -> str:
    return (
        "You are a Bali Zero account executive writing a WhatsApp message to a client.\n"
        f"Client first name: {name}. Write in {language}.\n"
        f"Context: {fact}\n"
        f"Goal: invite them to discuss {pitch_goal}.\n"
        "Rules: 40-80 words. Warm but professional. NO marketing buzzwords, NO emoji, "
        "NO 'exciting opportunity'. Reference the specific fact above. End with a concrete "
        "next step (a suggested 20-30 min call this week). Output ONLY the message text.\n/no_think"
    )


def _call_ollama(prompt: str, timeout: float = 180.0) -> str:
    """The ONLY model call in this file. Talks to the local Ollama HTTP API
    exclusively -- see the module docstring's class-guard note."""
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.4},
        }
    ).encode()
    req = urllib.request.Request(
        OLLAMA_GENERATE_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    text = (resp.get("response") or "").strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    return text


def draft_pitch(
    client_id: str, prompt: str, sensitive: bool = True
) -> tuple[str, str | None]:
    """Returns (outcome, pitch_text_or_None).

    Never raises on an Ollama failure -- that IS the terminal outcome, not an
    exception for the caller to interpret or retry around. Never falls
    through to any other model on any failure branch.
    """
    tier = choose_tier(sensitive)  # raises if sensitive=False -- see docstring
    assert tier == OLLAMA_LOCAL

    if not ollama_up():
        _log_outcome(client_id, SKIPPED_OLLAMA_FAIL, "ollama_unreachable")
        return SKIPPED_OLLAMA_FAIL, None

    try:
        text = _call_ollama(prompt)
    except Exception as exc:  # noqa: BLE001 -- any failure here is terminal, never a cloud retry
        _log_outcome(client_id, SKIPPED_OLLAMA_FAIL, type(exc).__name__)
        return SKIPPED_OLLAMA_FAIL, None

    if not text:
        _log_outcome(client_id, SKIPPED_OLLAMA_FAIL, "empty_response")
        return SKIPPED_OLLAMA_FAIL, None

    _log_outcome(client_id, OLLAMA_LOCAL)
    return OLLAMA_LOCAL, text


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(f"[yield-optimizer-gate] bad JSON on stdin: {exc}", file=sys.stderr)
        return 1

    client_id = payload.get("client_id")
    if not client_id:
        print("[yield-optimizer-gate] missing client_id", file=sys.stderr)
        return 1

    prompt = build_prompt(
        name=payload.get("name", "there"),
        language=payload.get("language", "English"),
        fact=payload.get("fact", ""),
        pitch_goal=payload.get("pitch_goal", ""),
    )
    outcome, text = draft_pitch(client_id, prompt)
    if outcome == OLLAMA_LOCAL:
        print(text)
        return 0

    print(
        f"[yield-optimizer-gate] {SKIPPED_OLLAMA_FAIL} client_id={client_id}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
