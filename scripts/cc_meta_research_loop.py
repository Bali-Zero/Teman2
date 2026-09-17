#!/usr/bin/env python3
"""cc_meta_research_loop — an Opus-orchestrated, multi-seat research loop whose
only subject is THIS harness: how Claude Code is configured here, what the
frontier of practice looks like elsewhere, and where the two diverge.

WHY THIS EXISTS. The fleet already owns a dozen frontier seats (arsenal_probe.py
knows how to reach each one) and a large Claude Code surface — dozens of hooks,
57 agent definitions, 37 skills, 26 plugin slots, a 1M-context Opus seat. Nobody
has ever asked those seats what the surface SHOULD look like, and the config has
only ever grown by accretion: every scar added a hook, no round ever removed one.
This driver closes that gap in the only shape this repo accepts — generator is
never grader, every claim carries a command that would falsify it, and a seat we
cannot reach is reported as MISSING EVIDENCE rather than silently dropped
(scar #2: the absence of an answer is not an answer).

WHAT IT IS NOT. It does not edit settings.json, installs nothing, and —
deliberately — NEVER EXECUTES the verification commands the models write. A
model-authored shell string executed by the tool that asked for it is a command
injection with extra steps; the commands are printed for a human or an Opus
session to run. The output is a report, not a mutation.

BANS HONOURED. Claude is reached ONLY through the `claude` CLI on the
subscription OAuth path (CLAUDE.md §3): no anthropic SDK, no ANTHROPIC_API_KEY,
no Bedrock/Vertex. Other seats use credentials arsenal_probe already resolves,
and no credential value is ever logged. No client PII is in scope: the only
payload that leaves this machine is the Claude Code configuration SHAPE — key
names, hook script basenames, counts. Never env values, never repo content,
never a client record.

LOOP SHAPE (one round):
  1. probe    — which seats are alive right now (empirical, per run)
  2. fan-out  — each live seat gets a DIFFERENT lens over the same inventory
  3. harvest  — responses parsed into atomic proposals {claim, surface, verify}
  4. grade    — each proposal judged by a seat that did NOT author it
  5. converge — SUPPORTED proposals become known state; UNVERIFIABLE ones become
                the next round's open questions. Stop when a round adds no new
                SUPPORTED proposal, or --rounds is exhausted.

Usage:
    python3 scripts/cc_meta_research_loop.py --rounds 2
    python3 scripts/cc_meta_research_loop.py --inventory-only
    python3 scripts/cc_meta_research_loop.py --seats agy,codex --rounds 1
    python3 scripts/cc_meta_research_loop.py --dry-run     # plan only, no seat calls

Output: research/agent-craft/cc-meta-loop/<UTC>-<runid>/
        inventory.json · round-N/{raw_answers,proposals,verdicts}.json · REPORT.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import arsenal_probe as ap  # noqa: E402  (seat reachability + credential resolution)

HOME = Path.home()
OUT_ROOT = _REPO_ROOT / "research" / "agent-craft" / "cc-meta-loop"

OLLAMA_MODEL = "qwen3.5:9b"  # same model arsenal_probe probes locally
SEAT_TIMEOUT = 300  # a research answer is not a PONG; the 15s probe budget would kill every seat


# ─────────────────────────────────────────────────────────────────────────────
# 1. INVENTORY — the payload every seat reasons over.
# ─────────────────────────────────────────────────────────────────────────────


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _hook_shape(hooks: Optional[dict]) -> dict:
    """Event -> [{matcher, commands}]. Command BASENAMES only: a hook command
    carries an absolute path with a username, which is machine identity rather
    than configuration, and identity is not what we are asking about."""
    out: dict[str, list[dict]] = {}
    for event, matchers in (hooks or {}).items():
        entries = []
        for m in matchers or []:
            cmds = []
            for h in m.get("hooks", []) or []:
                c = (h.get("command") or "").strip()
                base = re.sub(r"^.*/", "", c.split()[0]) if c else ""
                cmds.append(base or h.get("type", "?"))
            entries.append({"matcher": m.get("matcher", "*"), "commands": cmds})
        out[event] = entries
    return out


def build_inventory() -> dict:
    settings = _read_json(HOME / ".claude" / "settings.json") or {}
    local = _read_json(HOME / ".claude" / "settings.local.json") or {}
    proj = _read_json(_REPO_ROOT / ".claude" / "settings.json") or {}
    mcp = _read_json(_REPO_ROOT / ".mcp.json") or {}

    def _count(pattern: str, root: Path) -> int:
        try:
            return len(list(root.glob(pattern)))
        except Exception:
            return 0

    perms = settings.get("permissions", {}) or {}
    global_hooks = _hook_shape(settings.get("hooks"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": ap.machine_label(),
        "claude_code": {
            "model": settings.get("model"),
            "fallbackModel": settings.get("fallbackModel"),
            "effortLevel": settings.get("effortLevel"),
            "modelSettings": settings.get("modelSettings"),
            "alwaysThinkingEnabled": settings.get("alwaysThinkingEnabled"),
            "outputStyle": settings.get("outputStyle"),
            "sandbox": settings.get("sandbox"),
            "cleanupPeriodDays": settings.get("cleanupPeriodDays"),
            "statusLine": bool(settings.get("statusLine")),
            "permissions": {
                "defaultMode": perms.get("defaultMode"),
                "allow_rules": len(perms.get("allow", []) or []),
                "deny_rules": len(perms.get("deny", []) or []),
                "ask_rules": len(perms.get("ask", []) or []),
            },
            "env_names_only": sorted((settings.get("env") or {}).keys()),
            "skillOverrides": settings.get("skillOverrides"),
        },
        "hooks_global": global_hooks,
        "hooks_project": _hook_shape(proj.get("hooks")),
        "hook_counts_global": {
            ev: sum(len(e["commands"]) for e in entries) for ev, entries in global_hooks.items()
        },
        "extensions": {
            "agents_global": _count("agents/*.md", HOME / ".claude"),
            "agents_repo": _count(".claude/agents/*.md", _REPO_ROOT),
            "skills_global": _count("skills/*", HOME / ".claude"),
            "skills_repo": _count(".claude/skills/*", _REPO_ROOT),
            "commands_global": _count("commands/*.md", HOME / ".claude"),
            "commands_repo": _count(".claude/commands/*.md", _REPO_ROOT),
            "plugins_enabled": sorted(k for k, v in (settings.get("enabledPlugins") or {}).items() if v),
            "plugins_disabled": sorted(k for k, v in (settings.get("enabledPlugins") or {}).items() if not v),
            "mcp_servers_declared": sorted((mcp.get("mcpServers") or {}).keys()),
            "mcp_enabled": settings.get("enabledMcpjsonServers"),
            "mcp_disabled": settings.get("disabledMcpjsonServers"),
        },
        "local_overrides_present": bool(local),
        "context_doors_bytes": {
            name: (_REPO_ROOT / name).stat().st_size
            for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md", "SYMBIOSIS.md", "INDEX.md")
            if (_REPO_ROOT / name).exists()
        },
        "global_claude_md_bytes": (HOME / ".claude" / "CLAUDE.md").stat().st_size
        if (HOME / ".claude" / "CLAUDE.md").exists()
        else 0,
        "usage_context": {
            "shape": "solo developer, 3-machine fleet, long autonomous sessions (100k-400k tokens), "
            "many concurrent sessions in git worktrees, heavy cron/daemon automation",
            "subscription": "Claude MAX seats (OAuth CLI only) + external frontier seats "
            "(Gemini, Codex, Kimi, Qwen/GLM via a token plan, local Ollama)",
        },
    }


def build_hook_inventory() -> list[dict]:
    """Static audit of every REGISTERED hook script, because a hooks round that
    reasons over counts alone produces advice about counts. For each script:
    where it is registered, its timeout, and the four facts that decide whether a
    hook is cheap or expensive — does it read the transcript, does it spawn, does
    it emit a real decision, and which exit codes it can take.

    Exit-code semantics are the whole game and are easy to get wrong: for
    PreToolUse only exit 2 denies; exit 1 is a NON-blocking error and the tool
    proceeds. A script whose failure branch exits 1 while its comments say
    fail-closed is fail-OPEN (measured on this machine, guardrails-client.sh)."""
    settings = _read_json(HOME / ".claude" / "settings.json") or {}
    proj = _read_json(_REPO_ROOT / ".claude" / "settings.json") or {}
    regs: dict[str, dict] = {}
    for scope, cfg in (("global", settings), ("project", proj)):
        for event, matchers in (cfg.get("hooks") or {}).items():
            for m in matchers or []:
                for h in m.get("hooks", []) or []:
                    cmd = (h.get("command") or "").strip()
                    if not cmd:
                        continue
                    # The script is the first token that names a FILE. Two shapes
                    # defeat a naive "first token": `env A=1 B=2 python3 /x/y.py`
                    # (the interpreter and its assignments come first) and quoted
                    # paths (the quote sticks to the basename and the file stops
                    # being readable — measured: `data_plane_guard.py"`).
                    # Three shapes defeat a naive "first token", all three
                    # measured on this machine: `env A=1 python3 /x/y.py` (the
                    # interpreter comes first), a quoted path (the quote sticks to
                    # the basename and the file stops being readable), and a
                    # trailing `2>/dev/null` (a token with a slash that is not the
                    # script — it reported a hook named "null"). ${CLAUDE_PROJECT_DIR}
                    # must be expanded or the script is unreadable for no reason.
                    expanded = cmd.replace("${CLAUDE_PROJECT_DIR}", str(_REPO_ROOT)).replace(
                        "$CLAUDE_PROJECT_DIR", str(_REPO_ROOT)
                    )
                    toks = [t.strip("\"'") for t in expanded.split()]
                    toks = [t for t in toks if not t.startswith(("-", ">", "2>", "&")) and t != "/dev/null"]
                    tok = next(
                        (t for t in toks if t.endswith((".sh", ".py"))),
                        next((t for t in toks if "/" in t and "=" not in t), toks[0] if toks else cmd),
                    )
                    name = re.sub(r"^.*/", "", tok)
                    r = regs.setdefault(
                        name,
                        {"script": name, "registrations": [], "timeouts": [], "path": tok},
                    )
                    r["registrations"].append(f"{scope}:{event}:{m.get('matcher','*') or '*'}")
                    if h.get("timeout"):
                        r["timeouts"].append(h["timeout"])
    for r in regs.values():
        path = Path(os.path.expanduser(r["path"]))
        if not path.is_absolute():
            for base in (HOME / ".claude" / "hooks", _REPO_ROOT / "scripts" / "hooks", _REPO_ROOT):
                if (base / r["script"]).exists():
                    path = base / r["script"]
                    break
        try:
            body = path.read_text(errors="replace")
        except Exception:
            r["readable"] = False
            continue
        r["readable"] = True
        r["lines"] = body.count("\n") + 1
        # M1: a Python hook usually exits via `return 0` inside main() plus
        # sys.exit(main()), so scanning for `exit(N)` alone reported exit_codes=[2]
        # for a script with six fail-open paths — and the loop's seat then accused
        # it of blocking every Bash call. Count both spellings.
        r["exit_codes"] = sorted(
            {int(m) for m in re.findall(r"\bexit[( ]\s*(\d)", body)}
            | {int(m) for m in re.findall(r"^\s*return\s+(\d)\s*$", body, re.MULTILINE)}
        )
        r["reads_transcript"] = bool(re.search(r"transcript_path|\.jsonl", body))
        r["spawns"] = bool(re.search(r"nohup|subprocess|Popen|&\s*$|curl ", body, re.MULTILINE))
        r["emits_decision"] = bool(re.search(r"permissionDecision|hookSpecificOutput", body))
        r["emits_context"] = "additionalContext" in body
        r["gated_on_env"] = sorted(set(re.findall(r"([A-Z][A-Z0-9_]{5,})\s*(?:==|!=|,\s*\"0\")", body)))[:6]
    return sorted(regs.values(), key=lambda r: r["script"])


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEATS — one-shot invocation, reusing arsenal_probe's resolution.
# ─────────────────────────────────────────────────────────────────────────────

# lens: the ANGLE a seat must take. Distinct lenses are what makes a fan-out
# worth more than N copies of one question — identical prompts to N seats
# produce roughly one distinct finding plus N-1 paraphrases.
SEAT_LENSES = {
    "agy": (
        "WEB-GROUNDED FRONTIER. You have Google Search. Find what teams OUTSIDE this "
        "machine do with Claude Code in 2026 that this configuration does not: "
        "settings.json keys, hook events, plugin/marketplace patterns, subagent and "
        "skill layouts, context and token economics. Cite URLs. Prefer official "
        "Anthropic documentation and changelogs over blog folklore."
    ),
    "codex": (
        "ENGINEERING CRITIQUE. You are a senior engineer reading another team's agent "
        "harness. Attack it on operational grounds: hook fan-out cost per tool call, "
        "failure modes, permission-rule blast radius, startup latency, what a hook that "
        "runs on EVERY PostToolUse costs across a 300-turn session. Name what to "
        "DELETE, not only what to add."
    ),
    "kimi": (
        "LONG-CONTEXT AND TOKEN ECONOMICS. Tokens only: what in this configuration "
        "burns context every turn, what could be deferred, cached, or moved behind "
        "on-demand retrieval, and what must stay resident. Quantify where you can "
        "(tokens per turn, per session)."
    ),
    "claude": (
        "HARNESS-NATIVE. You are Claude Code itself. Name the CAPABILITIES of this "
        "harness that this configuration does not use at all, and the ones it uses in a "
        "degraded shape. Be specific about the mechanism, not the benefit."
    ),
    "tp1-glm-5.2": (
        "ADVERSARIAL ALTERNATIVE. Assume the configuration is over-engineered. Argue "
        "for the SIMPLEST configuration that keeps the same guarantees, and name "
        "precisely what would be lost."
    ),
    "tp1-qwen3.8-max": (
        "COMBINATORICS. Hunt COMBOS: pairs or triples of features (hook+skill, "
        "subagent+MCP, output-style+model-routing) worth more together than apart, that "
        "this config has the parts for but has never wired together."
    ),
    "tp1-qwen3.7-max": (
        "COMBINATORICS. Hunt COMBOS: pairs or triples of features (hook+skill, "
        "subagent+MCP, output-style+model-routing) worth more together than apart, that "
        "this config has the parts for but has never wired together."
    ),
    "ollama": (
        "OFFLINE SANITY. No web access. From the inventory alone, name internal "
        "inconsistencies: settings that contradict each other, dead entries, duplicated "
        "mechanisms."
    ),
}


# A second lens set, selected with --lens-set hooks. The default set asks "what
# is missing from this config"; this one asks only about the hook layer, because
# that layer is where this machine spends its per-tool-call budget and where the
# first round found every one of its confirmed defects.
HOOK_LENSES = {
    "codex": (
        "HOOK MECHANICS, ON DISK. You can read files. For EVERY registered hook script in "
        "the inventory, decide whether its registration is justified: does it run on events "
        "it needs, does it exit with the code that actually produces the effect its comments "
        "claim (for PreToolUse only exit 2 denies — exit 1 is a non-blocking error and the "
        "tool proceeds), does it read the transcript or spawn subprocesses on hot paths, and "
        "is its timeout a sane budget in SECONDS. Name every hook that is dead, mis-exited, "
        "double-registered, or whose cost is paid on every call for a throttled effect. Quote "
        "the file and line."
    ),
    "claude": (
        "HOOK CONTRACT, HARNESS-NATIVE. You are Claude Code. Enumerate the hook EVENTS and "
        "output contracts this harness offers (every event name, matcher semantics, the JSON "
        "output fields such as hookSpecificOutput/permissionDecision/additionalContext, exit "
        "code semantics per event, timeout units, what reaches the model's context vs only "
        "the debug log, and what a hook can and cannot change). Then name which of those "
        "mechanisms this configuration uses WRONGLY and which it does not use at all. Be "
        "exact about the mechanism; if you are not certain an event or field exists, say so "
        "instead of guessing."
    ),
    "jules": (
        "HOOK MECHANICS, ON DISK. Read the hook scripts and name every registration that is "
        "dead, mis-exited, or pays its cost on every tool call for a throttled effect."
    ),
}

DEFAULT_SEATS = ["agy", "codex", "kimi", "claude", "tp1-glm-5.2", "tp1-qwen3.8-max"]

PROPOSAL_SCHEMA = """Answer with ONE json object and nothing else. No prose before or after.
{"proposals":[{
 "id":"kebab-case-slug",
 "claim":"one sentence: what should change, stated as a fact about the config",
 "surface":"settings.json|hooks|skills|subagents|plugins|mcp|context|model-routing|workflow|other",
 "why":"the mechanism, one or two sentences, no marketing",
 "expected_gain":"tokens|latency|reliability|capability|cost + a rough magnitude",
 "verification_command":"a READ-ONLY shell command that would prove or disprove the claim on this machine; empty string if none exists",
 "risk":"what breaks if this is wrong",
 "confidence":"high|medium|low",
 "source":"url or 'reasoning'"
}]}
At most 8 proposals. A proposal with no verification_command is worth less than one with it.
Never propose anything requiring a paid per-token Anthropic API key: that path is banned here."""

GRADER_SCHEMA = """Answer with ONE json object and nothing else.
{"verdicts":[{"id":"<proposal id>","verdict":"SUPPORTED|UNVERIFIABLE|REJECTED","reason":"one sentence","better_verification":"a sharper read-only command, or empty"}]}
SUPPORTED = you would bet the change is correct AND the verification command would show it.
UNVERIFIABLE = plausible, but nothing offered would settle it.
REJECTED = wrong, already true in the inventory, or banned here."""


def _call_cli(cmd: list[str], timeout: int, capture_via_files: bool = False) -> tuple[bool, str]:
    try:
        res = ap.run_probe_cmd(cmd, timeout=timeout, capture_via_files=capture_via_files)
    except Exception as exc:  # a seat that explodes is a dead seat, not a crashed loop
        return False, f"{type(exc).__name__}: {exc}"
    text = (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")
    return bool(text.strip()), text


def ask_seat(seat: str, prompt: str, timeout: int = SEAT_TIMEOUT) -> dict:
    """One-shot question to one seat. Returns {seat, ok, raw, error, ms}."""
    t0 = time.monotonic()
    ok, raw, err = False, "", None

    if seat == "claude":
        binp, _ = ap.resolve_bin("claude")
        if not binp:
            err = "claude CLI not found"
        else:
            # OAuth CLI only, and Sonnet rather than Opus: the orchestrator IS Opus,
            # and a seat that agrees with the orchestrator by construction is not a seat.
            # --restricted is load-bearing, not hygiene. MEASURED on M5 2026-09-17:
            # without it a headless `claude -p "Reply with exactly: PONG"` costs
            # 54,906 input tokens, takes 15s and answers the fleet mailbox that the
            # global SessionStart/PostToolUse hooks inject — never the prompt. With
            # it: 15,511 input tokens and the literal answer PONG. A seat that
            # replies to another session's context is not a seat.
            ok, raw = _call_cli(
                [binp, "-p", prompt, "--model", "claude-sonnet-5", "--restricted"], timeout
            )
    elif seat == "agy":
        binp, _ = ap.resolve_bin("agy", ["~/.local/bin/agy"])
        if not binp:
            err = "agy not found"
        else:
            # capture_via_files: agy leaves a detached grandchild holding the stdout fd,
            # so communicate() never sees EOF and the answer stays in the pipe buffer
            # (arsenal_probe, measured 2026-08-26).
            ok, raw = _call_cli([binp, "-p", prompt], timeout, capture_via_files=True)
    elif seat == "kimi":
        binp, _ = ap.resolve_bin("kimi", ["~/.kimi-code/bin/kimi"])
        if not binp:
            err = "kimi not found"
        else:
            ok, raw = _call_cli([binp, "-p", prompt, "-m", "kimi-code/k3"], timeout, capture_via_files=True)
    elif seat == "codex":
        binp, _ = ap.resolve_bin("codex", ["/opt/homebrew/bin/codex"])
        if not binp:
            err = "codex not found"
        else:
            ok, raw = _call_cli(
                [binp, "exec", "--sandbox", "read-only", "--skip-git-repo-check", prompt],
                timeout,
                capture_via_files=True,
            )
    elif seat == "ollama":
        binp, _ = ap.resolve_bin("ollama", ["/opt/homebrew/bin/ollama"])
        if not binp:
            err = "ollama not found"
        else:
            ok, raw = _call_cli([binp, "run", OLLAMA_MODEL, prompt], timeout)
    elif seat.startswith("tp1-"):
        model = ap.TP1_SEAT_MODELS.get(seat)
        token, note = ap.load_tp1_settings_key()
        if model is None:
            err = f"unknown tp1 seat {seat}"
        elif token is None:
            err = note or "TP1 credential unavailable"
        else:
            status, body, ev = ap.http_post_json(
                ap.TP1_CHAT_COMPLETIONS_URL,
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                {"model": model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]},
                timeout,
                [token],
            )
            if status == 200:
                try:
                    raw = json.loads(body)["choices"][0]["message"]["content"]
                    ok = bool(raw.strip())
                except Exception as exc:
                    err = f"unparsable TP1 body: {type(exc).__name__}"
            else:
                err = f"HTTP {status}: {ap.scrub(ev, [token])[:160]}"
    else:
        err = f"unsupported seat {seat}"

    return {
        "seat": seat,
        "ok": ok,
        "raw": ap.scrub(raw)[:60000],
        "error": err,
        "ms": int((time.monotonic() - t0) * 1000),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. HARVEST — models do not respect "json only"; parse defensively.
# ─────────────────────────────────────────────────────────────────────────────


def extract_json(text: str) -> Optional[dict]:
    """First balanced {...} that parses. Tolerates ```json fences and prose."""
    if not text:
        return None
    candidates: list[str] = []
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))
    start = text.find("{")
    while start != -1 and len(candidates) < 4:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
        start = text.find("{", start + 1)
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict) and ("proposals" in obj or "verdicts" in obj):
                return obj
        except Exception:
            continue
    return None


def normalize_proposals(seat: str, payload: Optional[dict]) -> list[dict]:
    if not payload or not isinstance(payload.get("proposals"), list):
        return []
    out = []
    for p in payload["proposals"][:8]:
        if not isinstance(p, dict) or not p.get("claim"):
            continue
        pid = str(p.get("id") or "")[:60] or re.sub(r"\W+", "-", str(p["claim"]).lower())[:48]
        out.append(
            {
                "id": f"{seat}:{pid}",
                "author": seat,
                "claim": str(p.get("claim"))[:400],
                "surface": str(p.get("surface", "other"))[:40],
                "why": str(p.get("why", ""))[:600],
                "expected_gain": str(p.get("expected_gain", ""))[:200],
                "verification_command": str(p.get("verification_command", ""))[:400],
                "risk": str(p.get("risk", ""))[:300],
                "confidence": str(p.get("confidence", "low"))[:10],
                "source": str(p.get("source", ""))[:300],
            }
        )
    return out


def _claim_key(claim: str, surface: str = "") -> tuple:
    return (surface.lower(), re.sub(r"[^a-z0-9 ]", "", claim.lower())[:70])


def dedup(proposals: list[dict]) -> list[dict]:
    """Two seats naming the same change must collapse: agreement is signal,
    duplication is noise."""
    seen: dict[tuple, dict] = {}
    for p in proposals:
        key = _claim_key(p["claim"], p["surface"])
        if key in seen:
            seen[key].setdefault("also_proposed_by", []).append(p["author"])
        else:
            seen[key] = dict(p)
    return list(seen.values())


# ─────────────────────────────────────────────────────────────────────────────
# 4. GRADE — generator is never grader (CLAUDE.md §5, applied to research).
# ─────────────────────────────────────────────────────────────────────────────


MIN_INDEPENDENT_SEATS = 3


def grading_independence(live_seats: list[str]) -> str:
    """M2: with one seat there is no grader; with two, every verdict comes from the
    only other participant and one lazy grader reason gets stamped onto every
    proposal (observed 2026-09-17: codex emitted a single reason and it was
    attached to 8 verdicts, which then LOOKED earned). The loop must say which
    of the three regimes it ran in rather than printing verdicts that read the
    same in all three."""
    n = len(live_seats)
    if n >= MIN_INDEPENDENT_SEATS:
        return "INDEPENDENT"
    if n == 2:
        return "RECIPROCAL — each verdict comes from the only other seat; not independent"
    return "NONE — a single seat cannot grade itself; every proposal stays UNGRADED"


def grade_round(proposals: list[dict], live_seats: list[str], inventory: dict, timeout: int) -> dict:
    """Each proposal goes to a seat that did not author it. One batched call per
    grader: N proposals in one call beats N calls of one, and the grader sees its
    peers' claims side by side, which is where contradictions surface."""
    if not proposals or len(live_seats) < 2:
        return {}
    assignments: dict[str, list[dict]] = {s: [] for s in live_seats}
    for i, p in enumerate(proposals):
        for offset in range(len(live_seats)):
            cand = live_seats[(i + offset) % len(live_seats)]
            if cand != p["author"] and cand not in (p.get("also_proposed_by") or []):
                assignments[cand].append(p)
                break
    inv_blob = json.dumps(inventory, indent=1)[:12000]

    def _grade(seat: str) -> list[dict]:
        batch = assignments[seat]
        if not batch:
            return []
        listing = json.dumps(
            [{k: p[k] for k in ("id", "claim", "surface", "why", "verification_command")} for p in batch],
            indent=1,
        )[:20000]
        prompt = (
            "You are grading proposals written by OTHER models about a Claude Code "
            "configuration. You did not write them. Be adversarial: most proposals about "
            "agent harnesses sound plausible and are unfalsifiable.\n\n"
            f"CURRENT CONFIGURATION (authoritative — read it before judging):\n{inv_blob}\n\n"
            f"PROPOSALS:\n{listing}\n\n{GRADER_SCHEMA}"
        )
        res = ask_seat(seat, prompt, timeout)
        payload = extract_json(res["raw"]) if res["ok"] else None
        rows = []
        for v in (payload or {}).get("verdicts") or []:
            if isinstance(v, dict) and v.get("id"):
                rows.append(
                    {
                        "id": str(v["id"]),
                        "grader": seat,
                        "verdict": str(v.get("verdict", "UNVERIFIABLE")).upper()[:12],
                        "reason": str(v.get("reason", ""))[:300],
                        "better_verification": str(v.get("better_verification", ""))[:300],
                    }
                )
        return rows

    verdicts: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(live_seats))) as pool:
        for rows in pool.map(_grade, live_seats):
            for v in rows:
                verdicts.setdefault(v["id"], v)
    return verdicts


# ─────────────────────────────────────────────────────────────────────────────
# 5. LOOP
# ─────────────────────────────────────────────────────────────────────────────


def probe_live(seats: list[str], timeout_mult: float = 2.0) -> dict[str, str]:
    """Empirical, this run, this machine. A seat we cannot reach is reported as
    missing evidence in the report, never silently dropped (scar #2)."""

    def _p(seat: str) -> tuple[str, str]:
        try:
            row = ap.probe_seat(seat, timeout_mult=timeout_mult, live_gen=False)
            return seat, row.get("status", "UNKNOWN_ERR")
        except Exception as exc:
            return seat, f"PROBE_ERR:{type(exc).__name__}"

    status: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(seats))) as pool:
        for seat, st in pool.map(_p, seats):
            status[seat] = st
    return status


def round_prompt(inventory: dict, lens: str, known: list[dict], open_questions: list[str]) -> str:
    inv_blob = json.dumps(inventory, indent=1)[:40000]
    known_blob = "\n".join(f"- [{p['surface']}] {p['claim']}" for p in known[:40]) or "(none yet)"
    open_blob = "\n".join(f"- {q}" for q in open_questions[:20]) or "(none)"
    return (
        "You are one seat in a multi-model research loop orchestrated by Claude Opus. "
        "The subject is ONE Claude Code installation: the configuration below, on a "
        "solo-developer fleet of three machines running long autonomous sessions.\n\n"
        f"YOUR LENS — answer ONLY from this angle:\n{lens}\n\n"
        f"CURRENT CONFIGURATION (JSON, reduced to shapes and names; env VALUES are "
        f"deliberately absent):\n{inv_blob}\n\n"
        f"ALREADY ESTABLISHED — do not repeat these:\n{known_blob}\n\n"
        f"OPEN QUESTIONS from the previous round — settling one is worth more than a new "
        f"topic:\n{open_blob}\n\n"
        "Hard constraints on this machine: Claude models are reached ONLY through the "
        "`claude` CLI on a subscription OAuth token (every paid per-token Anthropic path, "
        "Bedrock and Vertex included, is banned); no client personal data may ever enter a "
        "prompt, log or report.\n\n"
        f"{PROPOSAL_SCHEMA}"
    )


def write_report(run_dir: Path, inventory: dict, rounds: list[dict], seat_status: dict) -> Path:
    all_props: dict[str, dict] = {}
    all_verdicts: dict[str, dict] = {}
    for r in rounds:
        for p in r["proposals"]:
            all_props[p["id"]] = p
        all_verdicts.update(r["verdicts"])

    lines = [
        "# Claude Code meta-configuration — multi-seat research loop",
        "",
        f"- run `{run_dir.name}` · machine `{inventory['machine']}` · {inventory['generated_at']}",
        f"- rounds: {len(rounds)} · proposals: {len(all_props)} · graded: {len(all_verdicts)}",
        f"- grading independence: **{grading_independence([s for s, st in seat_status.items() if ap.healthy(st) or st == 'SKIPPED_PROBE'])}**",
        "",
        "## Seat reachability (empirical, this run)",
        "",
        "| seat | status | used |",
        "|---|---|---|",
    ]
    for seat, st in sorted(seat_status.items()):
        lines.append(f"| {seat} | {st} | {'yes' if ap.healthy(st) else 'NO — evidence missing'} |")
    lines.append("")
    dead = [s for s, st in seat_status.items() if not ap.healthy(st)]
    if dead:
        lines += [
            f"> {len(dead)} seat(s) unreachable: **{', '.join(dead)}**. Their lens is a hole in "
            "this report, not a negative finding.",
            "",
        ]

    def _bucket(name: str) -> list[dict]:
        return [p for pid, p in all_props.items() if (all_verdicts.get(pid, {}).get("verdict") or "UNGRADED") == name]

    for bucket, heading, blurb in (
        ("SUPPORTED", "## GAP — supported by an independent grader", "A seat that did not write it would bet on it."),
        ("UNVERIFIABLE", "## OPEN — plausible, nothing settles it", "Next round's questions, or a human measurement."),
        ("REJECTED", "## REJECTED", "Wrong, already true, or banned here."),
        ("UNGRADED", "## UNGRADED", "No grader was reachable for these."),
    ):
        rows = _bucket(bucket)
        if not rows:
            continue
        lines += [heading, "", f"_{blurb}_", ""]
        for p in sorted(rows, key=lambda x: x["surface"]):
            v = all_verdicts.get(p["id"], {})
            also = sorted(set(p.get("also_proposed_by") or []))
            agree = f" (also: {', '.join(also)})" if also else ""
            lines += [
                f"### [{p['surface']}] {p['claim']}",
                "",
                f"- author `{p['author']}`{agree} · confidence {p['confidence']}",
            ]
            if v:
                lines.append(f"- grader `{v['grader']}`: **{v['verdict']}** — {v['reason']}")
            lines += [
                f"- why: {p['why']}",
                f"- expected gain: {p['expected_gain']}",
                f"- risk: {p['risk']}",
            ]
            cmd = v.get("better_verification") or p["verification_command"]
            lines.append(
                f"- verify (NOT executed by this loop): `{cmd}`" if cmd else "- verify: **none offered** — treat as opinion"
            )
            if p["source"]:
                lines.append(f"- source: {p['source']}")
            lines.append("")

    lines += ["## Loop convergence", ""]
    for i, r in enumerate(rounds, 1):
        sup = sum(1 for v in r["verdicts"].values() if v["verdict"] == "SUPPORTED")
        lines.append(
            f"- round {i}: {len(r['proposals'])} new proposals from {len(r['answered_by'])} seats "
            f"({', '.join(r['answered_by']) or 'none'}), {sup} supported"
        )
    lines += [
        "",
        "> No verification command in this report was executed by the loop. A model-authored "
        "shell string run by the tool that requested it is an injection channel; running them "
        "is a human's or an Opus session's act.",
    ]
    path = run_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Multi-seat research loop over this machine's Claude Code configuration."
    )
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--seats", default=",".join(DEFAULT_SEATS))
    parser.add_argument("--timeout", type=int, default=SEAT_TIMEOUT)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="plan + inventory, no seat calls")
    parser.add_argument("--no-probe", action="store_true", help="skip liveness probe, try every named seat")
    parser.add_argument("--lens-set", choices=("default", "hooks"), default="default")
    parser.add_argument("--focus", default="", help="extra instruction appended to every lens")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    lenses = SEAT_LENSES if args.lens_set == "default" else HOOK_LENSES
    if args.focus:
        lenses = {k: f"{v}\n\nADDITIONAL FOCUS FROM THE ORCHESTRATOR: {args.focus}" for k, v in lenses.items()}
    seats = [s.strip() for s in args.seats.split(",") if s.strip()]
    unknown = [s for s in seats if s not in lenses]
    if unknown:
        print(f"error: no lens defined for seat(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    inventory = build_inventory()
    if args.lens_set == "hooks":
        inventory["hook_scripts"] = build_hook_inventory()
    if args.inventory_only:
        print(json.dumps(inventory, indent=1))
        return 0

    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%MZ')}-{uuid.uuid4().hex[:6]}"
    run_dir = Path(args.out) if args.out else OUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "inventory.json").write_text(json.dumps(inventory, indent=1) + "\n")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "run_dir": str(run_dir),
                    "seats": seats,
                    "rounds": args.rounds,
                    "seat_calls_per_round": len(seats) * 2,
                    "inventory_bytes": len(json.dumps(inventory)),
                },
                indent=1,
            )
        )
        return 0

    if args.no_probe:
        seat_status = {s: "SKIPPED_PROBE" for s in seats}
        live = list(seats)
    else:
        seat_status = probe_live(seats)
        live = [s for s in seats if ap.healthy(seat_status[s])]
    print(
        f"seats: {len(live)}/{len(seats)} live — " + ", ".join(f"{s}={seat_status[s]}" for s in seats),
        file=sys.stderr,
    )
    if not live:
        print("error: 0 live seats — a loop with no seats is not a clean run (scar #2)", file=sys.stderr)
        return 3

    known: list[dict] = []
    open_questions: list[str] = []
    rounds: list[dict] = []

    for rnd in range(1, args.rounds + 1):
        rdir = run_dir / f"round-{rnd}"
        rdir.mkdir(exist_ok=True)

        def _ask(seat: str, _k=known, _o=open_questions) -> dict:
            return ask_seat(seat, round_prompt(inventory, lenses[seat], _k, _o), args.timeout)

        with ThreadPoolExecutor(max_workers=len(live)) as pool:
            answers = list(pool.map(_ask, live))
        (rdir / "raw_answers.json").write_text(json.dumps(answers, indent=1) + "\n")

        proposals: list[dict] = []
        answered_by: list[str] = []
        for a in answers:
            props = normalize_proposals(a["seat"], extract_json(a["raw"]) if a["ok"] else None)
            if props:
                answered_by.append(a["seat"])
            proposals.extend(props)
        proposals = dedup(proposals)
        known_keys = {_claim_key(p["claim"], p["surface"]) for p in known}
        proposals = [p for p in proposals if _claim_key(p["claim"], p["surface"]) not in known_keys]
        (rdir / "proposals.json").write_text(json.dumps(proposals, indent=1) + "\n")
        print(f"round {rnd}: {len(proposals)} new proposals from {len(answered_by)} seats", file=sys.stderr)

        verdicts = grade_round(proposals, live, inventory, args.timeout)
        (rdir / "verdicts.json").write_text(json.dumps(verdicts, indent=1) + "\n")

        supported = [p for p in proposals if verdicts.get(p["id"], {}).get("verdict") == "SUPPORTED"]
        unverifiable = [p for p in proposals if verdicts.get(p["id"], {}).get("verdict") == "UNVERIFIABLE"]
        known = known + supported
        open_questions = [f"{p['claim']} — what would settle it?" for p in unverifiable]
        rounds.append({"round": rnd, "proposals": proposals, "verdicts": verdicts, "answered_by": answered_by})
        print(f"round {rnd}: {len(supported)} supported, {len(unverifiable)} open", file=sys.stderr)
        if not supported and rnd > 1:
            print("converged: a round added no supported proposal", file=sys.stderr)
            break

    report = write_report(run_dir, inventory, rounds, seat_status)
    if args.json:
        print(json.dumps({"run_dir": str(run_dir), "report": str(report), "rounds": len(rounds)}, indent=1))
    else:
        print(f"\nreport: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
