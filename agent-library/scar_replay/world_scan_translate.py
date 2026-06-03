#!/usr/bin/env python3
"""
world_scan_translate.py — the ONE new piece of the world-scan.

Reuse-first audit (2026-06-04): ~80% of the world-scan already exists in-house
(wr2-external-bench runner, devils-advocate gate, ai-dispatch cascade, _proposed/
convention). The only genuinely new code is THIS: the translator that turns an
external failure-pattern (e.g. "chaos engineering: inject network latency to test
timeout handling") into a DRAFT replay-probe for scar_probes.py — a deterministic
fault-injection test where the baseline FAILS.

Anti-overfit / anti-"plausible-wisdom" firewall (council 2026-06-04, unanimous):
external best-practices DO NOT enter the harness as prose. A pattern only earns
ADOPT if it can be expressed as an EXECUTABLE probe whose baseline fails. If the
LLM can't articulate a concrete fixture (precondition + fault + assertion), it is
OBSERVE (worth watching, not yet a probe) — never silently promoted.

This module:
  1. Sends each extracted pattern to DeepSeek with a strict translation contract.
  2. Applies DETERMINISTIC executability checks on top of the LLM verdict (the LLM
     proposing "ADOPT" is necessary but NOT sufficient — the draft must contain the
     structural ingredients of a real probe).
  3. Emits a draft-probe markdown block + a category (ADOPT / OBSERVE / REJECT).

It does NOT write into scar_probes.py and does NOT auto-merge. Output is staged for
human review (Law 5 — the human decides what becomes a real probe).

Provenance (reuse-first §7):
  - DeepSeek curl shape: adapted from ~/scripts/eventbus/devils_advocate_runner.py
    (model deepseek-v4-pro, reasoning_effort high) — NOT the stale deepseek-reasoner
    in the devils-advocate.md spec.
  - cascade/quota-detection: pattern from ~/scripts/claude-cascade.sh.
  License: in-house (Nuzantara repo). No third-party code copied.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("world_scan_translate")

_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
_DEEPSEEK_MODEL = "deepseek-v4-pro"  # NOT deepseek-reasoner (deprecated, silent flash)


# --------------------------------------------------------------------------- #
# Data model                                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class DraftProbe:
    pattern_title: str
    category: str = "REJECT"          # ADOPT | OBSERVE | REJECT
    family: str = ""                  # snake_case family id for scar_probes.py
    incident_summary: str = ""        # what the candidate LLM would see (no fix)
    contract: str = ""                # what an antibody must guarantee
    fixture_sketch: str = ""          # how to build the pre-error state + inject the fault
    assertion_sketch: str = ""        # the executable, local check (NOT an LLM judgment)
    baseline_fails_rationale: str = ""# WHY the baseline fails by construction (headroom)
    source_refs: str = ""             # where this pattern came from
    executable: bool = False          # deterministic gate: does it have all probe ingredients?
    reasons: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# DeepSeek translation call (reuse of the devils_advocate curl shape)          #
# --------------------------------------------------------------------------- #

_TRANSLATE_SYSTEM = (
    "You convert an external software-failure pattern into the SPEC of a "
    "deterministic replay-probe for a self-improving ops agent. A replay-probe "
    "is a test that: (1) builds a minimal pre-error state in an ephemeral "
    "sandbox, (2) injects the exact fault, (3) asserts a LOCAL, EXECUTABLE "
    "outcome (exit code / file state / process state) — never an LLM judgment. "
    "The probe's BASELINE (no guard applied) must FAIL by construction. "
    "If the pattern CANNOT be expressed as a concrete deterministic fixture "
    "(e.g. it's a vague cultural/process recommendation, or needs real external "
    "infrastructure that can't be sandboxed), say so honestly — do NOT invent a "
    "fake fixture. Output STRICT JSON only."
)

_TRANSLATE_USER_TMPL = (
    "EXTERNAL FAILURE PATTERN:\n{pattern}\n\n"
    "Our agent operates on: local git worktrees, LaunchAgent cron jobs, shell "
    "scripts, Postgres via asyncpg, secrets in env vaults, file-based state. "
    "Probes must be reproducible in an ephemeral mktemp sandbox with NO network "
    "and NO paid services.\n\n"
    "Produce STRICT JSON with these keys:\n"
    '  "applicable": true|false   (is this failure class even relevant to our stack?)\n'
    '  "expressible": true|false  (can it be a deterministic sandbox fixture? be honest)\n'
    '  "family": "snake_case_id"\n'
    '  "incident_summary": "what went wrong, plain prose, NO fix, NO variant list"\n'
    '  "contract": "what env vars an antibody receives + what it must guarantee"\n'
    '  "fixture_sketch": "concrete steps to build pre-error state + inject the fault in bash/python"\n'
    '  "assertion_sketch": "the exact LOCAL executable check (exit code / file / branch / process)"\n'
    '  "baseline_fails_rationale": "why the baseline (no guard) fails by construction"\n'
    "Return ONLY the JSON object."
)


def _call_deepseek(api_key: str, pattern: str, timeout: int = 180) -> Optional[dict]:
    body = {
        "model": _DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": _TRANSLATE_SYSTEM},
            {"role": "user", "content": _TRANSLATE_USER_TMPL.format(pattern=pattern[:2000])},
        ],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 4000,
        "reasoning_effort": "high",
    }
    try:
        proc = subprocess.run(
            ["curl", "-sf", "-X", "POST", _DEEPSEEK_URL,
             "-H", f"Authorization: Bearer {api_key}",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("translate: deepseek call failed (%s)", exc)
        return None
    if proc.returncode != 0:
        logger.warning("translate: deepseek rc=%s: %s", proc.returncode, (proc.stderr or "")[:160])
        return None
    try:
        resp = json.loads(proc.stdout)
        content = resp["choices"][0]["message"]["content"] or ""
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        logger.warning("translate: bad deepseek response shape (%s)", exc)
        return None
    return _extract_json(content)


def _extract_json(text: str) -> Optional[dict]:
    """Pull the JSON object out of the model's reply (tolerates fences/prose)."""
    text = text.strip()
    # strip ```json fences
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # find the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Deterministic executability gate (the firewall — LLM verdict is NOT enough)  #
# --------------------------------------------------------------------------- #

# A draft is ADOPT-eligible only if the model returned ALL of these as non-empty
# and substantive. Anything vague/missing => OBSERVE (or REJECT if not applicable).
_MIN_FIELD_CHARS = {
    "fixture_sketch": 40,
    "assertion_sketch": 25,
    "baseline_fails_rationale": 25,
    "incident_summary": 40,
    "contract": 40,
}

# Heuristic markers that an assertion is genuinely LOCAL+EXECUTABLE, not a judgment.
_EXECUTABLE_MARKERS = re.compile(
    r"exit code|exit status|returncode|\$\?|rev-parse|HEAD|file exists|"
    r"\bgrep\b|\bdiff\b|process|pid|lock|state|stdout|stderr|"
    r"=\s*0|!=\s*0|non-zero|unchanged|present|absent",
    re.IGNORECASE,
)
# Anti-markers: an "assertion" that defers to an LLM/human is NOT a valid gate.
_JUDGMENT_MARKERS = re.compile(
    r"\bLLM\b|model judges|looks correct|seems|reasonable|review by|ask the|"
    r"human decides|subjectiv",
    re.IGNORECASE,
)


def _grade(d: dict) -> tuple[str, bool, list[str]]:
    """Deterministic grade on top of the LLM's self-report. Returns
    (category, executable, reasons)."""
    reasons: list[str] = []
    if not d.get("applicable", False):
        return "REJECT", False, ["not applicable to our stack (LLM)"]
    if not d.get("expressible", False):
        reasons.append("LLM says not expressible as a deterministic fixture")
        return "OBSERVE", False, reasons

    # field-substance checks
    for fld, need in _MIN_FIELD_CHARS.items():
        val = (d.get(fld) or "").strip()
        if len(val) < need:
            reasons.append(f"{fld} too thin ({len(val)}<{need} chars)")

    assertion = (d.get("assertion_sketch") or "")
    if _JUDGMENT_MARKERS.search(assertion):
        reasons.append("assertion defers to LLM/human judgment (not a local gate)")
    if not _EXECUTABLE_MARKERS.search(assertion):
        reasons.append("assertion lacks executable markers (exit code/file/branch/process)")

    fam = (d.get("family") or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", fam):
        reasons.append(f"family id not snake_case usable: {fam!r}")

    executable = len(reasons) == 0
    category = "ADOPT" if executable else "OBSERVE"
    return category, executable, reasons


def translate_pattern(api_key: str, pattern_title: str, pattern_text: str) -> DraftProbe:
    """Translate one external failure pattern into a DRAFT probe + category."""
    draft = DraftProbe(pattern_title=pattern_title, source_refs=pattern_title)
    d = _call_deepseek(api_key, pattern_text)
    if d is None:
        draft.category = "REJECT"
        draft.reasons = ["translation call failed (no JSON)"]
        return draft

    draft.family = (d.get("family") or "").strip()
    draft.incident_summary = (d.get("incident_summary") or "").strip()
    draft.contract = (d.get("contract") or "").strip()
    draft.fixture_sketch = (d.get("fixture_sketch") or "").strip()
    draft.assertion_sketch = (d.get("assertion_sketch") or "").strip()
    draft.baseline_fails_rationale = (d.get("baseline_fails_rationale") or "").strip()

    draft.category, draft.executable, draft.reasons = _grade(d)
    return draft


# --------------------------------------------------------------------------- #
# Markdown rendering for the _proposed/ staging file (human review)            #
# --------------------------------------------------------------------------- #


def render_draft_md(draft: DraftProbe) -> str:
    badge = {"ADOPT": "✅ ADOPT", "OBSERVE": "👁 OBSERVE", "REJECT": "✗ REJECT"}.get(
        draft.category, draft.category
    )
    lines = [
        f"### {badge} — {draft.pattern_title}",
        "",
        f"- **family**: `{draft.family or '(none)'}`",
        f"- **executable** (deterministic gate): {'yes' if draft.executable else 'NO'}",
    ]
    if draft.reasons:
        lines.append(f"- **gate notes**: {'; '.join(draft.reasons)}")
    lines += [
        f"- **source**: {draft.source_refs}",
        "",
        "**incident_summary** (what the antibody-author would see):",
        f"> {draft.incident_summary or '(empty)'}",
        "",
        "**contract** (what an antibody must guarantee):",
        f"> {draft.contract or '(empty)'}",
        "",
        "**fixture_sketch** (build pre-error state + inject fault):",
        "```",
        draft.fixture_sketch or "(empty)",
        "```",
        "**assertion_sketch** (LOCAL executable check — never an LLM judgment):",
        "```",
        draft.assertion_sketch or "(empty)",
        "```",
        f"**why baseline fails (headroom)**: {draft.baseline_fails_rationale or '(empty)'}",
        "",
        "_To promote: a human turns an ADOPT draft into a real `Probe` in "
        "`scar_probes.py` (with the fixture + assertion as code) and commits it. "
        "Never auto-merged._",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)
