#!/usr/bin/env python3
"""arsenal_probe.py — empirical liveness of every AI seat, per machine, per context.

THE DISEASE IT KILLS (scar #2 "Esiste != Armato" — cron theater / blind autopilot):
the multi-LLM cascade recommended since 2026-05-24 was never armed. Tier order was
assumed rather than measured — Codex 401-silent, agy keychain-bound-under-ssh, GLM
529/401, DeepSeek 402 all degrade a 4-deep cascade to effectively 2-deep with no
alarm. This tool makes every seat's liveness EMPIRICAL: fire a real 1-shot probe,
classify the OUTPUT CONTENT (never exit code alone — an exit-0 wrapper can still
carry a dead payload, W84), and write a report the healer/proprioception/humans can
all read without re-deriving the taxonomy themselves.

SIGNALER, NEVER ACTUATOR: no retries-until-alive, no credential repair, no restart.
A probe result is a fact about right now, on this machine, in this context — nothing
more.

Redaction (scar #4 "Secret in the clear" — non-negotiable): credential values
(keychain tokens, env.master secrets, Authorization headers) live only in local
variables long enough to build one outbound request. They are never logged, never
placed in an exception string, and any evidence tail that might carry a token-shaped
substring is passed through scrub() before it can reach stdout, the report, or a
heartbeat sidecar.

Blind-scan guard (W84 "green-but-dead" — the guard that watches AGAINST the same
disease this tool is built to detect): a run that probed 0 seats is not "clean", it
is an infrastructure failure masquerading as calm. Exit 2, never exit 0, on 0 seats
probed.

Usage:
    python3 scripts/arsenal_probe.py                       # probe all seats, write report
    python3 scripts/arsenal_probe.py --seats claude,glm     # subset
    python3 scripts/arsenal_probe.py --json                 # full report to stdout
    python3 scripts/arsenal_probe.py --quiet                # one summary line
    python3 scripts/arsenal_probe.py --strict                # exit 1 on required-seat strict-fail
    python3 scripts/arsenal_probe.py --read-last --json      # re-emit last.json, no probing
    python3 scripts/arsenal_probe.py --selftest               # classifier + scrub + blind-scan self-checks

Report: ~/.organism/arsenal/last.json (atomic write, prev.json retained).
Heartbeat: ~/.organism/last_seen/<machine>.arsenal_probe.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional

SCHEMA_VERSION = 1
REPORT_DIR = Path.home() / ".organism" / "arsenal"
HEARTBEAT_DIR = Path.home() / ".organism" / "last_seen"

# ---------------------------------------------------------------- status taxonomy

LIVE = "LIVE"
AUTH_DEAD = "AUTH_DEAD"
CONTEXT_AUTH = "CONTEXT_AUTH"
QUOTA_DEAD = "QUOTA_DEAD"
BALANCE_DEAD = "BALANCE_DEAD"
MODEL_ERR = "MODEL_ERR"
SHED = "SHED"
TIMEOUT = "TIMEOUT"
CRED_UNAVAILABLE = "CRED_UNAVAILABLE"
NOT_INSTALLED = "NOT_INSTALLED"
UNKNOWN_ERR = "UNKNOWN_ERR"

# Persistent + fixable — these are the only statuses a strict run may fail on.
STRICT_FAIL = {AUTH_DEAD, BALANCE_DEAD, MODEL_ERR, UNKNOWN_ERR}
# A host limitation, not a seat death — never strict-fails regardless of required-ness.
CONTEXT_LIMITED = {CONTEXT_AUTH, CRED_UNAVAILABLE, NOT_INSTALLED}

# The OLD standalone per-token DeepSeek door was RETIRED 2026-07-19 (owner
# order, pre-auth revoked — never top up). DeepSeek remains live through the
# Alibaba Token Plan (TP1) door below; that subscription-backed door is distinct
# from the retired balance-metered endpoint.
#
# Honest design boundary: these are seven independently probeable seats pinned
# to the live text roster verified from TP1's /models door on 2026-08-23. This
# probe does NOT claim to enumerate the door dynamically. One model failure must
# remain one row and must never suppress the other six probes.
TP1_SEAT_MODELS = {
    "tp1-deepseek-v4-pro": "deepseek-v4-pro",
    "tp1-deepseek-v4-flash-0731": "deepseek-v4-flash-0731",
    "tp1-glm-5.2": "glm-5.2",
    "tp1-qwen3.8-max": "qwen3.8-max",
    "tp1-qwen3.7-max": "qwen3.7-max",
    "tp1-qwen3.7-plus": "qwen3.7-plus",
    "tp1-qwen3.6-flash": "qwen3.6-flash",
}

ALL_SEATS = [
    "claude",
    "glm",
    "kimi",
    "agy",
    "codex",
    "codex-spark",
    "ollama",
    "nlm",
    "qwen-cloud-code",
    "jules",
    *TP1_SEAT_MODELS,
]

REQUIRED_SEATS = {
    # kimi PONG-proven on all three machines 2026-07-19 (mini device-code
    # authorized by the operator same day).
    "mini": ["claude", "glm", "codex", "kimi", "ollama"],
    "pro": ["claude", "codex", "kimi", "ollama", "nlm"],
    "m5": ["claude", "glm", "agy", "codex", "kimi"],
}

# 2026-08-07 incident: these used to run 30-180s. agy in particular ALWAYS consumed its
# FULL timeout regardless of value — its own process exits in ~1s but a detached
# grandchild inherits the stdout pipe without closing it, so subprocess.run's
# communicate() never sees EOF (empirically verified: PONG present in partial stdout
# at every timeout tested, from 12s to 45s). Since all seats probe concurrently in a
# ThreadPoolExecutor and the whole run blocks on the SLOWEST one before printing
# anything, agy's old 120s timeout alone explained "0 bytes for 60s" under any outer
# `timeout 60` wrapper — the process was still inside as_completed(), not hung, but
# indistinguishable from hung to anything watching stdout. ~15s per seat (mandate) is
# empirically safe for the fast path (claude/codex/kimi/glm/ollama/nlm all replied in
# 0.03-15s live on Pro 2026-08-07) AND for the agy-style pipe-leak case, because every
# probe now judges the REPLY in partial stdout before accepting TIMEOUT (see the
# `live` computed before `res.timed_out` check in each probe_* function below) — a
# seat that already said PONG is LIVE even if its process never cleanly exits.
DEFAULT_TIMEOUTS = {
    "claude": 15,
    "glm": 15,
    "kimi": 15,
    "agy": 15,
    "codex": 15,
    "codex-spark": 15,
    "jules": 15,
    "ollama": 15,
    "nlm": 15,
    "qwen-cloud-code": 15,
    **{seat: 15 for seat in TP1_SEAT_MODELS},
}
OLLAMA_LIVE_GEN_TIMEOUT = 120

TP1_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
TP1_CHAT_COMPLETIONS_URL = f"{TP1_BASE_URL}/chat/completions"

# NOT 8. Three of the seven TP1 models (deepseek-v4-pro, deepseek-v4-flash-0731,
# glm-5.2) are THINKING models: max_tokens caps reasoning + answer TOGETHER
# (same trap as the Opus-5 note in CLAUDE.md Sec.5, on another vendor). Measured
# live 2026-08-23: at max_tokens=8 all three spent the whole budget on
# reasoning (usage.completion_tokens_details.reasoning_tokens == 8),
# choices[0].message.content came back empty, and the probe misreported three
# LIVE seats as UNKNOWN_ERR (superscar #2, inverted — a board that marks live
# models dead is worse than no board). Measured again with more room: reasoning
# ran as long as 171 tokens on qwen3.7-max before it answered "PONG". 256
# leaves headroom above that observed high-water mark. Do not "optimise" this
# back toward 8 without re-measuring reasoning_tokens on all seven models.
TP1_PROBE_MAX_TOKENS = 256

PONG_PROMPT = "Reply with exactly: PONG"


# ---------------------------------------------------------------- environment

def machine_label() -> str:
    host = socket.gethostname().split(".")[0].lower()
    if "air-m5" in host:
        return "m5"
    if "mini" in host:
        return "mini"
    if host == "nuzantara":
        return "pro"
    return host


def is_ssh_context() -> bool:
    return bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))


def context_info() -> dict:
    return {"ssh": is_ssh_context(), "interactive": sys.stdin.isatty()}


# ---------------------------------------------------------------- redaction (scar #4)

# Token-shaped substrings that must never survive into a report, log, or exception
# string: Bearer headers, common API-key prefixes, and any long alnum/._- run (24+
# chars covers keychain tokens, JWTs, hex digests) that isn't obviously prose.
_SECRET_RE = re.compile(
    r"(Bearer\s+\S+"
    r"|sk-[A-Za-z0-9_\-]{8,}"
    r"|ghp_[A-Za-z0-9]{8,}"
    r"|xox[a-z]-[A-Za-z0-9\-]{8,}"
    r"|eyJ[A-Za-z0-9._\-]{20,}"
    r"|[A-Za-z0-9._\-]{24,})"
)

_SECRET_ENV_NAME_RE = re.compile(r"(TOKEN|KEY|PASSWORD|SECRET)", re.IGNORECASE)


def scrub(text: str, extra_secrets: Optional[list[str]] = None) -> str:
    """Redact credential-shaped substrings from evidence before it can be logged.

    extra_secrets: exact credential VALUES this probe loaded (keychain token, parsed
    env.master value) — replaced unconditionally even if they don't match the
    generic shape (e.g. a short-but-still-sensitive value).
    """
    out = text
    for secret in extra_secrets or []:
        if secret:
            out = out.replace(secret, "<REDACTED>")
    out = _SECRET_RE.sub("<REDACTED>", out)
    return out


def evidence_tail(text: str, extra_secrets: Optional[list[str]] = None, limit: int = 160) -> str:
    """The tail, not the head — the name is a promise the old slice broke.

    Errors live at the tail (a stack trace's cause, an HTTP status line, a CLI's
    final message); a head-truncation keeps the greeting and drops the diagnosis.
    #29 (2026-07-26): a real AUTH_DEAD verdict was only recoverable because an
    external Codex rollout log happened to still be on disk — this field alone,
    head-truncated at 160 chars, cut off before reaching the actual error.
    """
    scrubbed = scrub((text or "").strip().replace("\n", " "), extra_secrets)
    return scrubbed[-limit:]


# ---------------------------------------------------------------- classification

# Each pattern is checked against the LOWERCASED evidence text. Order matters where
# patterns could both match (e.g. a 401 body could also contain a stray "quota"
# substring in prose) — the ordering in classify_seat() reflects the spec's own
# taxonomy priority (auth class before generic-error class).
# Numeric codes are word-bounded: classification runs on RAW provider output
# (scrub happens only at evidence_tail), and provider request-ids are long digit
# runs that would otherwise contain 401/429/1211 by accident — e.g. a z.ai
# request id minted at 12:11 (`...0706**1211**...`). \b between digits does not
# split a digit run, so ids stay innocent while bracketed/spaced codes still match
# (scar #3: match the entity, not the substring).
# The bare phrase "oauth token" (no failure word) is the same over-match risk one
# level up: a benign sentence merely mentioning it — "checking oauth token cache
# for refresh eligibility" — used to classify AUTH_DEAD with no error present at
# all. #34 (2026-07-26, round 2): first attempt required "expired|invalid|revoked"
# immediately adjacent to "oauth token" — too strict. Real failure text routinely
# interposes a verb/adverb: Pro's cron-agent learning-pipeline log recorded a real
# incident as "OAuth token silently revoked mid-cron" (logs/cron-agent/
# learning-pipeline.log:701 — an AI-summarized retrospective, not a raw captured
# stderr string, but a genuine observed event, not authored to fit a regex). Strict
# adjacency would have read that seat as alive through a real auth death — the
# exact failure direction this classifier must never create. Bounded proximity
# (up to 40 chars) survives the interposed word while still requiring failure
# context, so the bare-mention over-match stays fixed. This also corrects the
# precedent this pattern claimed the first time: `claude-cascade.sh` actually
# carries the adjacent-only form only in RAW_RETRYABLE_PATTERN, used solely for
# a whole-payload anchored envelope check (^...$) — a stricter context than this
# classifier's substring search. The role that matches THIS classifier's own —
# scanning a diagnostic text blob, not anchoring a whole payload — is
# claude-cascade.sh's AUTH_PATTERN (checked against stderr), which is unbounded
# (`oauth token.*(expired|invalid|revoked)`). Bounded-40 sits between the two:
# tighter than AUTH_PATTERN's unbounded form, looser than RAW_RETRYABLE_PATTERN's
# bare adjacency. The other alternatives (401/token_revoked/refresh_token_reused/
# authentication failed) are already failure-shaped and untouched.
_AUTH_DEAD_PAT = re.compile(
    r"\b401\b|authentication failed|token_revoked|refresh_token_reused|"
    r"oauth token\b.{0,40}(expired|invalid|revoked)",
    re.IGNORECASE,
)
_QUOTA_DEAD_PAT = re.compile(
    r"out of extra usage|usage limit|weekly limit|quota|\b429\b|rate.?limit|exhausted",
    re.IGNORECASE,
)
_BALANCE_DEAD_PAT = re.compile(r"\b402\b|insufficient balance", re.IGNORECASE)
_MODEL_ERR_PAT = re.compile(r"\b1211\b|unknown model", re.IGNORECASE)
_SHED_PAT = re.compile(r"\b529\b|overloaded", re.IGNORECASE)


def classify_generic(evidence: str, live_signal: bool, seat: str, ssh_context: bool) -> str:
    """Classify by OUTPUT CONTENT (scar #2) — never by exit code alone.

    live_signal is the seat-specific positive proof (e.g. "PONG" in stdout, HTTP 200
    + "model" in body) already evaluated by the caller; this function only decides
    the negative-path taxonomy when live_signal is False.
    """
    if live_signal:
        return LIVE
    text = evidence or ""
    if _AUTH_DEAD_PAT.search(text):
        # agy's GUI-keychain failure is context-limited, not a credential death, when
        # we're running headless (ssh) or have no GUI session — the cure differs
        # (context, not credential) so it gets its own status.
        if seat == "agy" and ssh_context:
            return CONTEXT_AUTH
        return AUTH_DEAD
    if _BALANCE_DEAD_PAT.search(text):
        return BALANCE_DEAD
    if _MODEL_ERR_PAT.search(text):
        return MODEL_ERR
    if _SHED_PAT.search(text):
        return SHED
    if _QUOTA_DEAD_PAT.search(text):
        return QUOTA_DEAD
    return UNKNOWN_ERR


def healthy(status: str) -> bool:
    return status == LIVE


def context_limited(status: str) -> bool:
    return status in CONTEXT_LIMITED


def is_strict_fail(status: str) -> bool:
    return status in STRICT_FAIL


# ---------------------------------------------------------------- subprocess helper

class ProbeResult:
    __slots__ = ("returncode", "stdout", "stderr", "timed_out")

    def __init__(self, returncode: int, stdout: str, stderr: str, timed_out: bool = False):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


def run_probe_cmd(
    cmd: list[str], timeout: float, env: Optional[dict] = None, stdin_devnull: bool = True
) -> ProbeResult:
    """Run a probe subprocess. stdin_devnull defaults to True — NON-NEGOTIABLE (2026-08-07
    incident): every seat probe must never inherit an open stdin, because a hook/launchd/
    agent-harness caller can hand this process a pipe that is never explicitly closed. No
    caller in this file opts out; the parameter survives only so a test can override it.
    """
    try:
        kwargs: dict[str, Any] = dict(
            capture_output=True, text=True, timeout=timeout, env=env
        )
        if stdin_devnull:
            kwargs["stdin"] = subprocess.DEVNULL
        p = subprocess.run(cmd, **kwargs)
        return ProbeResult(p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
        return ProbeResult(-1, out or "", err or "", timed_out=True)
    except FileNotFoundError:
        return ProbeResult(-2, "", "not found")


# Common install roots for the seat CLIs on this organism's machines (Pro/Mini user
# `nuzantara`, M5 user `balizero` — both covered since these are all `~`-relative).
# 2026-08-07 root cause: probe_claude's ONLY fallback was the wrong absolute guess
# (/opt/homebrew/bin/claude — claude has never lived there, it's a `~/.local/bin/claude`
# symlink) and probe_ollama/probe_nlm had NO fallback at all — so a PATH-poor calling
# context (a hook/launchd receptor whose $PATH lacks ~/.local/bin or /opt/homebrew/bin)
# reported NOT_INSTALLED for seats that were genuinely installed and answering fine in
# an interactive shell seconds earlier (scar family #2 Esiste!=Armato, W108 lineage: the
# sensor was measuring its OWN environment's poverty, not the seat's absence).
COMMON_BIN_DIRS = ["~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", "~/.kimi-code/bin"]


def resolve_bin(name: str, extra_paths: Optional[list[str]] = None) -> tuple[Optional[str], bool]:
    """Resolve a seat binary. Returns (path_or_None, found_via_path).

    found_via_path=True means this process's own $PATH (shutil.which) resolved it — the
    normal case. False means resolution only succeeded via an explicit fallback candidate
    (extra_paths or COMMON_BIN_DIRS) — the binary IS installed, this process's $PATH was
    just thin. A caller that reports NOT_INSTALLED only after trying $PATH AND every known
    install root has earned the right to call it that; before this fix, NOT_INSTALLED
    could mean either thing and a probe run under a poor-$PATH context (like a hook
    receptor) could not tell them apart — distinguishing them is the point (docs/runbooks/
    arsenal-probe.md), not adding a new status the taxonomy has to carry forever.
    """
    found = shutil.which(name)
    if found:
        return found, True
    candidates = list(extra_paths or [])
    candidates += [f"{d}/{name}" for d in COMMON_BIN_DIRS]
    for p in candidates:
        expanded = os.path.expanduser(p)
        if Path(expanded).exists():
            return expanded, False
    return None, False


def _path_note(via_path: bool) -> str:
    return "" if via_path else "[NOT_ON_PATH: resolved via fallback dir, binary present but $PATH was thin] "


# ---------------------------------------------------------------- credential loaders

def load_keychain_token(service: str, timeout: float = 10) -> tuple[Optional[str], Optional[str]]:
    """Returns (token, cred_status). cred_status is CRED_UNAVAILABLE-worthy note or None.

    Never raises; a locked keychain (exit 36 / errSecInteractionNotAllowed-class) or a
    missing entry both come back as (None, "<reason>") — a host limitation, not a
    probe crash.
    """
    security = shutil.which("security")
    if not security:
        return None, "security binary not on PATH"
    res = run_probe_cmd([security, "find-generic-password", "-s", service, "-w"], timeout=timeout)
    if res.returncode != 0:
        # Never echo the (empty-on-fail) stdout/stderr verbatim — it's diagnostic
        # noise at worst, but treat consistently with the "never log credential
        # material" rule anyway by only reporting the exit code.
        return None, f"keychain lookup failed (exit {res.returncode}) — locked or absent"
    token = res.stdout.strip()
    if not token:
        return None, "keychain entry empty"
    return token, None


def load_env_master_key(var_name: str, path: str = "~/.openclaw/workspace/.env.master") -> tuple[Optional[str], Optional[str]]:
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return None, f"{p} not found"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return None, f"{p} unreadable: {type(e).__name__}"
    for line in text.splitlines():
        if line.startswith(f"{var_name}="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value, None
    return None, f"{var_name} not set in {p}"


def load_tp1_settings_key(
    path: str = "~/.qwen/settings.json",
) -> tuple[Optional[str], Optional[str]]:
    """Load only env.BAILIAN_TOKEN_PLAN_API_KEY from Qwen's local settings.

    The credential value is returned only to the probe caller. Diagnostics name
    the missing field or file but never include settings content or a value.
    """
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return None, f"{p} not found"
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # ValueError covers json.JSONDecodeError AND UnicodeDecodeError (a stray
        # non-UTF-8 byte in the settings file raises the latter from read_text
        # itself, before json.loads ever runs) — Kimi round-2 finding #1: an
        # undecodable file must degrade this one credential lookup to
        # CRED_UNAVAILABLE (context-limited, non-strict-fail), never propagate
        # as a raw exception that would otherwise only be caught by the
        # generic Exception handler in probe_seat() and mis-tagged UNKNOWN_ERR
        # (strict-fail) for all seven TP1 seats at once.
        return None, f"{p} unreadable: {type(e).__name__}"
    if not isinstance(parsed, dict):
        return None, f"env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}"
    env = parsed.get("env")
    if not isinstance(env, dict):
        return None, f"env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}"
    value = env.get("BAILIAN_TOKEN_PLAN_API_KEY")
    if not isinstance(value, str) or not value.strip():
        return None, f"env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}"
    return value.strip(), None


# ---------------------------------------------------------------- HTTP helper

def http_post_json(
    url: str, headers: dict, body: dict, timeout: float, secret_values: list[str]
) -> tuple[Optional[int], str, str]:
    """POST JSON, return (status_code_or_None, full_body, evidence_tail). Never raises
    past this boundary, and the Authorization/x-api-key header value never appears in
    either returned string even on error (scar #4 — errors are the #1 leak vector).

    full_body: the ENTIRE response/error text, scrubbed but NOT truncated. A
    positive-proof marker (e.g. glm's `"model"` field) can sit near the START of a
    long JSON body and fall outside a tail window — a live-check that inspects only
    evidence_tail can misclassify a genuinely LIVE seat as dead (worst direction for
    a dispatch panel: it silently diverts work away from an available seat instead of
    failing loud). Callers whose positive-proof check needs to find a marker
    ANYWHERE in the body must inspect full_body, never the tail alone (see
    probe_glm — found live on M5 2026-08-21, a real HTTP 200 with `"model"` early in
    the body was misread UNKNOWN_ERR by a tail-only check).

    evidence_tail: the same text truncated to the tail (errors live at the tail — see
    evidence_tail()'s own docstring) — kept for compact logging/display; existing
    callers that only need a short diagnostic string are unaffected."""

    def _scrub_and_split(raw: str) -> tuple[str, str]:
        full = scrub((raw or "").strip().replace("\n", " "), secret_values)
        return full, full[-160:]

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            full, tail = _scrub_and_split(raw)
            return resp.status, full, tail
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        full, tail = _scrub_and_split(raw)
        return e.code, full, tail
    except urllib.error.URLError as e:
        # str(e.reason) could theoretically echo a header on some transports; scrub
        # unconditionally rather than trust the transport not to leak (defense-in-depth).
        full, tail = _scrub_and_split(f"{type(e).__name__}: {e.reason}")
        return None, full, tail
    except TimeoutError:
        return None, "timed out", "timed out"
    except Exception as e:  # a probe must never crash the whole run
        full, tail = _scrub_and_split(f"{type(e).__name__}: {e}")
        return None, full, tail


# ---------------------------------------------------------------- per-seat probes

def probe_claude(timeout: float, env_overrides: Optional[dict] = None) -> tuple[str, str, int]:
    t0 = time.monotonic()
    env_bin = os.environ.get("ARSENAL_CLAUDE_BIN")
    if env_bin:
        binp, via_path = env_bin, True
    else:
        # claude has never lived at /opt/homebrew/bin — it's a ~/.local/bin/claude
        # symlink (verified 2026-08-07); COMMON_BIN_DIRS now covers this generically,
        # this stays as the accurate, seat-specific first guess.
        binp, via_path = resolve_bin("claude", ["~/.local/bin/claude"])
    if not binp:
        return NOT_INSTALLED, "claude binary not found (checked $PATH + common install dirs)", 0
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # scar-load-bearing: never let the paid key leak in
    # A stray GLM-session env (AUTH_TOKEN + base URL) would silently probe z.ai
    # while reporting it as the MAX seat — strip both for a clean MAX-context probe.
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("ANTHROPIC_BASE_URL", None)
    # Strip a bare, AMBIENT CLAUDE_CODE_OAUTH_TOKEN before applying the slot-1
    # fallback below (2026-08-08 live incident: this probe, run from Bash
    # inside an interactive Claude Code session, inherited that session's own
    # token — stale from an earlier /login cycle — and reported claude
    # AUTH_DEAD while the actual on-disk credential the `claude` binary
    # resolves by default was perfectly LIVE; unsetting the env var and
    # re-probing flipped AUTH_DEAD -> LIVE instantly. Same class the
    # ANTHROPIC_AUTH_TOKEN/BASE_URL strip above already guards against for
    # GLM: a probe must test the SEAT's own credential, not whatever the
    # calling shell happens to be carrying. A deliberate caller that wants to
    # test one SPECIFIC token still can, via env_overrides below — that path
    # is unaffected and remains the only sanctioned way to inject one.
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    # Headless/cron callers (launchd, sshd) often carry only the slotted
    # CLAUDE_CODE_OAUTH_TOKEN_{1,2,3} vars, never the bare one the `claude`
    # binary actually reads — same fallback already established in
    # organ_birth.py / regulatory-watcher-run.sh (CLAUDE.md's sanctioned
    # CLI-subprocess auth path). Without this the probe reports a false
    # UNKNOWN_ERR ("Not logged in") even when the MAX-plan session backing
    # slot 1 is perfectly alive.
    if env.get("CLAUDE_CODE_OAUTH_TOKEN_1"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = env["CLAUDE_CODE_OAUTH_TOKEN_1"]
    if env_overrides:
        env.update(env_overrides)
    res = run_probe_cmd(
        [binp, "-p", PONG_PROMPT, "--model", "claude-sonnet-5"], timeout=timeout, env=env
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)
    live = "PONG" in res.stdout
    # scar W104: judge the REPLY, never the raw exit-code/timeout signal alone — a
    # seat that already answered PONG in partial stdout is LIVE even if the probe's
    # own timeout fired before the process cleanly exited (see run_probe_cmd/
    # DEFAULT_TIMEOUTS comment — this is exactly the agy pipe-leak shape, kept generic
    # here in case another CLI ever exhibits the same grandchild-holds-the-pipe defect).
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    combined = res.stdout + res.stderr
    # claude CLI's unauthenticated shape ("Not logged in · Please run
    # /login") carries no 401/oauth-token marker, only this short prose, and
    # fell through classify_generic() to a bare UNKNOWN_ERR — same shape as
    # kimi's "No providers configured" below. Matched locally so the shared
    # _AUTH_DEAD_PAT keeps its existing guilt+innocence corpus untouched.
    if not live and re.search(r"not logged in", combined, re.IGNORECASE):
        return AUTH_DEAD, ev or "claude not logged in", latency_ms
    status = classify_generic(combined, live, "claude", is_ssh_context())
    return status, ev, latency_ms


def probe_glm(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    token, cred_note = load_keychain_token("glm-coding-plan-token")
    if token is None:
        return CRED_UNAVAILABLE, cred_note or "credential unavailable", int((time.monotonic() - t0) * 1000)
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {"model": "glm-5.2", "max_tokens": 8, "messages": [{"role": "user", "content": PONG_PROMPT}]}
    status_code, full_body, ev = http_post_json(
        "https://api.z.ai/api/anthropic/v1/messages", headers, body, timeout, [token]
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if status_code is None:
        return TIMEOUT if "timed out" in ev else UNKNOWN_ERR, ev, latency_ms
    # live-check runs on full_body (untruncated), never on the tail alone — see
    # http_post_json's docstring: the "model" field can sit before the last 160
    # chars of a long body, and a tail-only check misreads a genuinely LIVE seat
    # as dead (worst direction for a dispatch panel).
    live = status_code == 200 and '"model"' in full_body
    status = classify_generic(f"HTTP {status_code} {ev}", live, "glm", is_ssh_context())
    return status, f"HTTP {status_code} {ev}", latency_ms


def probe_agy(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp, via_path = resolve_bin("agy", ["~/.local/bin/agy"])
    if not binp:
        return NOT_INSTALLED, "agy binary not found (checked $PATH + common install dirs)", 0
    res = run_probe_cmd([binp, "-p", PONG_PROMPT], timeout=timeout)
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)
    live = "PONG" in res.stdout
    # THE 2026-08-07 incident: agy's own process exits in ~1s but a detached
    # grandchild keeps stdout's pipe fd open, so subprocess.run's communicate()
    # never sees EOF — this probe ALWAYS hit its full timeout (verified live at
    # 12s/15s/45s, PONG present in partial stdout every time) even though the
    # seat is genuinely LIVE. Judge the reply, not the fact that the process
    # never cleanly exited.
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    status = classify_generic(res.stdout + res.stderr, live, "agy", is_ssh_context())
    return status, ev, latency_ms


def probe_kimi(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp, via_path = resolve_bin("kimi", ["~/.kimi-code/bin/kimi"])
    if not binp:
        return NOT_INSTALLED, "kimi binary not found (checked $PATH + common install dirs)", 0
    res = run_probe_cmd(
        [binp, "-p", PONG_PROMPT, "-m", "kimi-code/k3"],
        timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)
    live = "PONG" in res.stdout
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    combined = res.stdout + res.stderr
    # kimi-code's unauthenticated state prints "No providers configured" /
    # "not logged in" with no 401 marker — that is a credential death (cure:
    # `kimi login`, operator device-code flow). Matched locally so the shared
    # _AUTH_DEAD_PAT keeps its existing guilt+innocence corpus untouched.
    if not live and re.search(r"no providers configured|not logged in", combined, re.IGNORECASE):
        return AUTH_DEAD, ev or "kimi not logged in", latency_ms
    status = classify_generic(combined, live, "kimi", is_ssh_context())
    return status, ev, latency_ms


def probe_codex(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp, via_path = resolve_bin("codex", ["/opt/homebrew/bin/codex"])
    if not binp:
        return NOT_INSTALLED, "codex binary not found (checked $PATH + common install dirs)", 0
    res = run_probe_cmd(
        [binp, "exec", "--sandbox", "read-only", "--skip-git-repo-check", PONG_PROMPT],
        timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)
    live = "PONG" in res.stdout
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    status = classify_generic(res.stdout + res.stderr, live, "codex", is_ssh_context())
    return status, ev, latency_ms



def probe_codex_spark(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp, via_path = resolve_bin("codex", ["/opt/homebrew/bin/codex"])
    if not binp:
        return NOT_INSTALLED, "codex binary not found (checked $PATH + common install dirs)", 0
    res = run_probe_cmd(
        [binp, "exec", "-m", "gpt-5.3-codex-spark", "--sandbox", "read-only", "--skip-git-repo-check", PONG_PROMPT],
        timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)
    live = "PONG" in res.stdout
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    status = classify_generic(res.stdout + res.stderr, live, "codex", is_ssh_context())
    return status, ev, latency_ms



def probe_jules(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp, via_path = resolve_bin("python3")
    if not binp:
        return NOT_INSTALLED, "python3 binary not found", 0
    res = run_probe_cmd(
        [binp, "scripts/jules_dispatch.py", "list-sources"],
        timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)

    live = False
    if res.returncode == 0:
        lines = [line for line in res.stdout.splitlines() if line.strip()]
        if len(lines) > 0:
            live = True

    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms

    combined = res.stdout + res.stderr
    # 2026-08-21 (healer tick, Mini): jules_dispatch.py's own credential-missing
    # shape — "jules_dispatch: no API key — add it with: security
    # add-generic-password ..." (get_api_key(), exit 2) — carries no 401/oauth
    # marker and previously fell through classify_generic() to a bare
    # UNKNOWN_ERR, same class as the nlm fix above: a Keychain lookup that
    # genuinely found nothing (`security find-generic-password -s
    # jules-api-key` -> item not found, verified on this host) is a
    # provisioning gap, not an ambiguous failure — CRED_UNAVAILABLE names it
    # precisely and puts it in CONTEXT_LIMITED, matching how glm's identical
    # "credential missing" shape is already classified. Matched before
    # classify_generic (mirrors probe_nlm's AUTH_DEAD special-case) so the
    # existing UNKNOWN_ERR guilt case (empty stdout, rc=0, no error text —
    # test_probe_jules_no_sources_is_unknown_err) stays untouched: that shape
    # never contains this marker.
    if not live and re.search(r"no API key", combined, re.IGNORECASE):
        return CRED_UNAVAILABLE, ev or "jules credential missing", latency_ms
    status = classify_generic(combined, live, "jules", is_ssh_context())
    return status, ev, latency_ms


def probe_ollama(timeout: float, live_gen: bool = False) -> tuple[str, str, int]:
    t0 = time.monotonic()
    # ollama ships via Homebrew (/opt/homebrew/bin/ollama on Apple Silicon) but had NO
    # fallback path at all before 2026-08-07 — COMMON_BIN_DIRS now covers it generically.
    binp, via_path = resolve_bin("ollama", ["/opt/homebrew/bin/ollama"])
    if not binp:
        return NOT_INSTALLED, "ollama binary not found (checked $PATH + common install dirs)", 0
    path_note = _path_note(via_path)
    res = run_probe_cmd([binp, "list"], timeout=timeout)
    latency_ms = int((time.monotonic() - t0) * 1000)
    model_listed = "qwen3.5" in res.stdout
    if res.timed_out and not model_listed:
        return TIMEOUT, path_note + (evidence_tail(res.stdout + res.stderr) or "probe timed out"), latency_ms
    if not model_listed:
        ev = path_note + evidence_tail(res.stdout + " " + res.stderr)
        status = classify_generic(res.stdout + res.stderr, False, "ollama", is_ssh_context())
        return status, ev or "qwen3.5 not listed", latency_ms
    if not live_gen:
        return LIVE, path_note + "qwen3.5 listed", latency_ms
    # A bare `ollama run <model>` with no prompt argument drops into an interactive
    # REPL that reads stdin — under the mandatory stdin=DEVNULL contract (every
    # subprocess, no exceptions) that would read immediate EOF and exit having
    # generated nothing, silently turning every --live-gen probe into a false-dead
    # reading. Passing the prompt as an argv token makes it one-shot and non-interactive,
    # so DEVNULL stdin (now unconditional in run_probe_cmd) is safe here too.
    gen_res = run_probe_cmd(
        [binp, "run", "qwen3.5:9b", PONG_PROMPT],
        timeout=OLLAMA_LIVE_GEN_TIMEOUT * timeout / DEFAULT_TIMEOUTS["ollama"],
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    live = bool(gen_res.stdout.strip())
    if gen_res.timed_out and not live:
        return TIMEOUT, path_note + "live-gen timed out", latency_ms
    ev = path_note + evidence_tail(gen_res.stdout + " " + gen_res.stderr)
    status = classify_generic(gen_res.stdout + gen_res.stderr, live, "ollama", is_ssh_context())
    return status, ev or "live-gen produced no output", latency_ms


def probe_nlm(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    # nlm lives at ~/.local/bin/nlm — had NO fallback path at all before 2026-08-07.
    binp, via_path = resolve_bin("nlm", ["~/.local/bin/nlm"])
    if not binp:
        return NOT_INSTALLED, "nlm binary not found (checked $PATH + common install dirs)", 0
    res = run_probe_cmd([binp, "list", "notebooks"], timeout=timeout)
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = _path_note(via_path) + evidence_tail(res.stdout + " " + res.stderr)
    live = False
    try:
        parsed = json.loads(res.stdout)
        live = isinstance(parsed, (list, dict))
    except (json.JSONDecodeError, ValueError):
        live = False
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    combined = res.stdout + res.stderr
    # nlm's expired-credential shape ("Run nlm login to re-authenticate")
    # carries no 401/oauth-token marker, only this prose, and fell through
    # classify_generic() to a bare UNKNOWN_ERR despite docs/runbooks/
    # arsenal-probe.md documenting "nlm AUTH_DEAD -> `nlm login` on Pro" as
    # the expected cure. Matched locally (claude/kimi pattern) so the shared
    # _AUTH_DEAD_PAT keeps its existing guilt+innocence corpus untouched.
    if not live and re.search(r"nlm login|not logged in", combined, re.IGNORECASE):
        return AUTH_DEAD, ev or "nlm not logged in", latency_ms
    status = classify_generic(combined, live, "nlm", is_ssh_context())
    return status, ev, latency_ms


def probe_qwen_cloud_code(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp, via_path = resolve_bin("qwen", ["~/.local/share/mise/installs/node/22/bin/qwen"])
    if not binp:
        return NOT_INSTALLED, "qwen binary not found (checked $PATH + mise node 22)", 0
    path_note = _path_note(via_path)
    # Arming gate (council + Fable gate 2026-08-08, decision SHIP-AFTER-FIXES): the probe
    # authenticates via Keychain service `qwen-cloud-code-token` (the runtime originally
    # shipped with a cleartext 0644 settings.json key, P0 — since chmod 0600 + rotated).
    # CORRECTED 2026-08-14 (PROBE-1-residual, research/operations/2026-08-14-probe1-tp1-burn-rate.md):
    # the "operator rotation pending" framing below was stale — the Keychain entry is
    # present on M5 and the seat has answered PONG (verified 2026-08-10) and carried ~1330
    # calls / ~212M tokens of real production use 2026-08-08→14 via `~/.qwen/settings.json`
    # (the qwen CLI's own credential path, independent of this probe). If this branch still
    # fires it means Keychain is genuinely unreadable RIGHT NOW (locked/absent on THIS
    # machine) — a live host condition, not a standing "rotation never happened" fact.
    # Still deliberately NOT in REQUIRED_SEATS on any machine: machine-scoped candidate
    # seat (M5 only) whose promotion into required-fleet status is a separate operator+
    # Claude-lane decision from the PROBATION->ARMED promotion recorded in FLEET_TOPOLOGY.json.
    token, cred_note = load_keychain_token("qwen-cloud-code-token")
    if not token:
        return (
            AUTH_DEAD,
            path_note + f"keychain gate: {cred_note} — seat cannot authenticate at probe time (keychain locked/absent on this host)",
            0,
        )
    env = dict(os.environ)
    env["BAILIAN_TOKEN_PLAN_API_KEY"] = token
    # --safe-mode: this build boots MCP servers/hooks/skills on every invocation
    # (measured: pushed the 1-token probe past the 15 s fleet mandate); safe-mode
    # disables all customizations, which a probe does not need.
    res = run_probe_cmd([binp, "-p", PONG_PROMPT, "--safe-mode"], timeout=timeout, env=env)
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = path_note + evidence_tail(res.stdout + " " + res.stderr, extra_secrets=[token])
    live = "PONG" in res.stdout
    if res.timed_out and not live:
        return TIMEOUT, ev or "probe timed out", latency_ms
    status = classify_generic(res.stdout + res.stderr, live, "qwen-cloud-code", is_ssh_context())
    return status, ev, latency_ms


def _tp1_has_live_answer(status_code: Optional[int], full_body: str) -> tuple[bool, Optional[str]]:
    """Positive proof for the OpenAI-compatible TP1 chat-completions door.

    Returns (is_live, note). Thinking models (deepseek-v4-pro,
    deepseek-v4-flash-0731, glm-5.2) can return HTTP 200 with an empty
    `message.content` while `message.reasoning_content` is populated — that is
    the model spending its whole token budget on reasoning, not a dead seat
    (see TP1_PROBE_MAX_TOKENS comment above). That shape is LIVE only when the
    choice's `finish_reason` is NOT "length" — Kimi round-2 finding #2: a
    length-truncated reasoning-only reply (a throttled/degraded model that
    burns the WHOLE 256-token budget on reasoning and never reaches an
    answer) produced nothing usable for a real caller and must not be
    reported LIVE forever just because reasoning_content is non-empty. A
    content-bearing answer is unaffected by finish_reason — it already proved
    the model answered. An HTTP 200 with both content and reasoning_content
    empty has no positive proof and is not live.
    """
    if status_code != 200:
        return False, None
    try:
        parsed = json.loads(full_body)
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            return False, None
        first = choices[0]
        if not isinstance(first, dict):
            return False, None
        message = first.get("message")
        if not isinstance(message, dict):
            return False, None
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return True, None
        reasoning_content = message.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            if first.get("finish_reason") == "length":
                return False, "reasoning-only response truncated by finish_reason=length (thinking budget exhausted, no answer reached)"
            return True, "reasoning-only response, no final content (thinking budget exhausted before answer)"
        return False, None
    except (json.JSONDecodeError, AttributeError, TypeError):
        return False, None


def _tp1_model_mismatch_note(requested_model: str, full_body: str) -> Optional[str]:
    """Kimi round-2 finding #4: a gateway that silently reroutes the requested
    slug to a fallback still returns HTTP 200 + non-empty content, so
    _tp1_has_live_answer alone reports LIVE for the SEAT WE THINK WE ASKED FOR.
    This adds a non-fatal note when the response's own echoed `model` field
    disagrees with what we requested — informational only, never changes the
    LIVE/dead verdict (a gateway is free to omit or normalize the field)."""
    try:
        parsed = json.loads(full_body)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    echoed = parsed.get("model")
    if isinstance(echoed, str) and echoed and echoed != requested_model:
        return f"requested {requested_model} but response echoed model={echoed}"
    return None


def probe_tp1_model(model: str, timeout: float) -> tuple[str, str, int]:
    """Probe one TP1 text model; credentials and failures are model-local."""
    t0 = time.monotonic()
    token, cred_note = load_tp1_settings_key()
    if token is None:
        return (
            CRED_UNAVAILABLE,
            cred_note or "TP1 credential unavailable",
            int((time.monotonic() - t0) * 1000),
        )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": TP1_PROBE_MAX_TOKENS,
        "messages": [{"role": "user", "content": PONG_PROMPT}],
    }
    status_code, full_body, ev = http_post_json(
        TP1_CHAT_COMPLETIONS_URL,
        headers,
        body,
        timeout,
        [token],
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if status_code is None:
        status = TIMEOUT if "timed out" in ev else UNKNOWN_ERR
        return status, f"{model}: {ev}", latency_ms
    live, note = _tp1_has_live_answer(status_code, full_body)
    status = classify_generic(
        f"HTTP {status_code} {full_body}",
        live,
        "tp1",
        is_ssh_context(),
    )
    evidence = f"{model}: HTTP {status_code} {ev}"
    if note:
        evidence = f"{evidence} ({note})"
    mismatch_note = _tp1_model_mismatch_note(model, full_body)
    if mismatch_note:
        evidence = f"{evidence} ({mismatch_note})"
    return status, evidence, latency_ms


PROBE_FUNCS: dict[str, Callable[..., tuple[str, str, int]]] = {
    "claude": probe_claude,
    "glm": probe_glm,
    "kimi": probe_kimi,
    "agy": probe_agy,
    "codex": probe_codex,
    "codex-spark": probe_codex_spark,
    "jules": probe_jules,
    "ollama": probe_ollama,
    "nlm": probe_nlm,
    "qwen-cloud-code": probe_qwen_cloud_code,
    **{
        seat: partial(probe_tp1_model, model)
        for seat, model in TP1_SEAT_MODELS.items()
    },
}


def probe_seat(seat: str, timeout_mult: float, live_gen: bool) -> dict:
    base_timeout = DEFAULT_TIMEOUTS.get(seat, 60) * timeout_mult
    fn = PROBE_FUNCS[seat]
    try:
        if seat == "ollama":
            status, ev, latency_ms = fn(base_timeout, live_gen=live_gen)
        else:
            status, ev, latency_ms = fn(base_timeout)
    except Exception as e:  # a single seat's probe must never take down the whole run
        status, ev, latency_ms = UNKNOWN_ERR, evidence_tail(f"{type(e).__name__}: {e}"), 0
    return {
        "seat": seat,
        "status": status,
        "healthy": healthy(status),
        "latency_ms": latency_ms,
        "evidence": ev,
    }


# ---------------------------------------------------------------- report / heartbeat

def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.rename(path)


def write_report(report: dict) -> None:
    last_path = REPORT_DIR / "last.json"
    if last_path.exists():
        prev_path = REPORT_DIR / "prev.json"
        try:
            prev_path.write_text(last_path.read_text())
        except OSError:
            pass  # retaining prev.json is best-effort, never fatal to the run
    _atomic_write_json(last_path, report)


def write_heartbeat(machine: str, degraded: bool, summary_line: str) -> None:
    # Sidecar carries the PROBE's own health (did it run and produce a report),
    # never the arsenal's observed health — same fix as pro.fly_restart_loop_detector
    # (research/operations/2026-07-03-heartbeat-organs-tac.md, PR #1924): a dead AI
    # seat is a finding, not a monitor failure, so it must not flip organs_heartbeat's
    # UNHEALTHY_STATUSES gate. Dead seats stay visible via the dedicated arsenal_seats
    # proprioception probe (--read-last, per-seat status) and healer Telegram on
    # transitions — this field only ever reflects "the probe ran to completion".
    heartbeat = {
        "organ": f"{machine}.arsenal_probe",
        "status": "ok",
        "degraded": degraded,
        "note": summary_line,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _atomic_write_json(HEARTBEAT_DIR / f"{machine}.arsenal_probe.json", heartbeat)


def load_last_report() -> Optional[dict]:
    path = REPORT_DIR / "last.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def compute_transitions(prev: Optional[dict], current_seats: list[dict]) -> list[dict]:
    if not prev:
        return []
    prev_status = {s["seat"]: s["status"] for s in prev.get("seats", [])}
    transitions = []
    for s in current_seats:
        old = prev_status.get(s["seat"])
        if old is not None and old != s["status"]:
            transitions.append({"seat": s["seat"], "from": old, "to": s["status"]})
    return transitions


# ---------------------------------------------------------------- table / summary

def render_table(report: dict) -> str:
    lines = [f"arsenal_probe — {report['machine']} — {report['ts']}"]
    for s in report["seats"]:
        req = " (required)" if s.get("required") else ""
        lines.append(f"  {s['seat']:<9} {s['status']:<16} {s['latency_ms']:>6}ms  {s['evidence']}{req}")
    for t in report.get("transitions", []):
        lines.append(f"  TRANSITION {t['seat']}: {t['from']} -> {t['to']}")
    summ = report["summary"]
    lines.append(
        f"summary: live={summ['live']} dead_strict={summ['dead_strict']} "
        f"context_limited={summ['context_limited']} transient={summ['transient']}"
    )
    # scar family #2/#97 (Esiste!=Armato / display-cap-reads-as-complete): always
    # declare N of M explicitly — never let a reader infer "0 seats" reads as clean.
    total = len(report["seats"])
    lines.append(f"{summ['live']} of {total} seats OK")
    return "\n".join(lines)


def summary_line(report: dict) -> str:
    summ = report["summary"]
    total = len(report.get("seats", []))
    return (
        f"arsenal_probe {report['machine']}: {summ['live']} of {total} seats OK "
        f"({summ['dead_strict']} dead_strict, {summ['context_limited']} context_limited, "
        f"{summ['transient']} transient)"
    )


# ---------------------------------------------------------------- read-last

def read_last(seats_filter: Optional[list[str]] = None) -> dict:
    """--read-last: NO probing, re-emit last.json as {"findings": [seats not in ok-set]}
    for the proprioception wrap consumer. Missing report -> NEVER_RAN sentinel."""
    report = load_last_report()
    if report is None:
        return {"findings": [{"seat": "(all)", "status": "NEVER_RAN"}]}
    seats = report.get("seats", [])
    if seats_filter:
        seats = [s for s in seats if s["seat"] in seats_filter]
    findings = [
        {"seat": s["seat"], "status": s["status"]}
        for s in seats
        if s["status"] != LIVE
    ]
    return {"findings": findings}


# ---------------------------------------------------------------- run

def run(seats: list[str], timeout_mult: float, live_gen: bool, machine: str) -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    required = set(REQUIRED_SEATS.get(machine, []))

    seat_results: list[dict] = []
    if seats:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(seats)) as pool:
            futures = {pool.submit(probe_seat, s, timeout_mult, live_gen): s for s in seats}
            for fut in concurrent.futures.as_completed(futures):
                seat_results.append(fut.result())
        # stable order regardless of thread completion order
        order = {s: i for i, s in enumerate(seats)}
        seat_results.sort(key=lambda r: order[r["seat"]])

    for r in seat_results:
        r["required"] = r["seat"] in required

    prev = load_last_report()
    transitions = compute_transitions(prev, seat_results)

    live_n = sum(1 for r in seat_results if r["status"] == LIVE)
    dead_strict_n = sum(1 for r in seat_results if is_strict_fail(r["status"]))
    context_limited_n = sum(1 for r in seat_results if context_limited(r["status"]))
    transient_n = sum(1 for r in seat_results if r["status"] in (QUOTA_DEAD, SHED, TIMEOUT))

    report = {
        "schema": SCHEMA_VERSION,
        "machine": machine,
        "ts": ts,
        "context": context_info(),
        "seats": seat_results,
        "transitions": transitions,
        "summary": {
            "live": live_n,
            "dead_strict": dead_strict_n,
            "context_limited": context_limited_n,
            "transient": transient_n,
        },
    }
    return report


# ---------------------------------------------------------------- selftest

_SELFTEST_CANNED = [
    # (seat, evidence_text_lower_ok, expected_status, description)
    ("claude", "PONG", LIVE, "claude PONG"),
    ("qwen-cloud-code", "PONG", LIVE, "qwen-cloud-code PONG"),
    ("glm", 'HTTP 200 {"model": "glm-5.2", "id": "x"}', LIVE, "glm 200+model"),
    (
        "glm",
        'HTTP 400 {"error": {"code": 1211, "message": "Unknown Model"}}',
        MODEL_ERR,
        "glm 1211 config drift",
    ),
    ("glm", "HTTP 529 overloaded, please retry", SHED, "glm 529 shed"),
    (
        "codex",
        "Error: 401 token_revoked: refresh_token_reused",
        AUTH_DEAD,
        "codex token_revoked",
    ),
    (
        "agy",
        "Error: OAuth token invalid, authentication failed",
        AUTH_DEAD,
        "agy auth-fail no-ssh",
    ),
    ("deepseek", "HTTP 402 Insufficient Balance", BALANCE_DEAD, "deepseek 402"),
    ("claude", "out of extra usage for this session", QUOTA_DEAD, "claude quota string"),
    ("codex", "rate limit exceeded, 429", QUOTA_DEAD, "codex 429 quota"),
    # innocence (scar #3): a request-id minted at 12:11 contains "1211" as a digit-run —
    # must NOT classify MODEL_ERR; the real signal here is the 529 shed.
    (
        "glm",
        "API Error: 529 overloaded [20260706121155c8877b89100e44a6]",
        SHED,
        "request-id digit-run stays innocent",
    ),
]


def _selftest_classifier() -> list[str]:
    failures = []
    for seat, evidence, expected, desc in _SELFTEST_CANNED:
        got = classify_generic(evidence, live_signal=(expected == LIVE), seat=seat, ssh_context=False)
        if got != expected:
            failures.append(f"{desc}: got {got}, want {expected}")
    # agy CONTEXT_AUTH vs AUTH_DEAD split — same evidence, different ssh context
    agy_auth_ev = "OAuth token invalid, authentication failed"
    got_ssh = classify_generic(agy_auth_ev, live_signal=False, seat="agy", ssh_context=True)
    if got_ssh != CONTEXT_AUTH:
        failures.append(f"agy auth-fail+ssh: got {got_ssh}, want {CONTEXT_AUTH}")
    got_no_ssh = classify_generic(agy_auth_ev, live_signal=False, seat="agy", ssh_context=False)
    if got_no_ssh != AUTH_DEAD:
        failures.append(f"agy auth-fail+no-ssh: got {got_no_ssh}, want {AUTH_DEAD}")
    return failures


def _selftest_scrub() -> list[str]:
    failures = []
    planted = "sk-abc123def456ghi789jkl0"  # pragma: allowlist secret  # planted FAKE token — exists to prove scrub() removes it
    text = f"request failed with token {planted} rejected"
    scrubbed = scrub(text)
    if planted in scrubbed:
        failures.append("scrub() failed to remove a planted fake sk- token")
    bearer_token = "abcdefghijklmnop1234567890"  # pragma: allowlist secret  # fake value — exists to prove scrub() removes it
    bearer_text = f"Authorization: Bearer {bearer_token} was rejected"
    scrubbed2 = scrub(bearer_text)
    if bearer_token in scrubbed2:
        failures.append("scrub() failed to remove a Bearer token value")
    exact = "not-shaped-like-a-token-but-secret"
    scrubbed3 = scrub(f"value was {exact} exactly", extra_secrets=[exact])
    if exact in scrubbed3:
        failures.append("scrub() failed to remove an exact extra_secrets value")
    return failures


def _selftest_blind_scan() -> list[str]:
    report = run(seats=[], timeout_mult=1.0, live_gen=False, machine="selftest")
    code = exit_code_for(report, strict=False, probed_count=0)
    if code != 2:
        return [f"blind-scan (0 seats probed) gave exit {code}, want 2"]
    return []


def _selftest_read_last(tmp_dir: Path) -> list[str]:
    failures = []
    global REPORT_DIR
    saved = REPORT_DIR
    REPORT_DIR = tmp_dir
    try:
        never_ran = read_last()
        if never_ran != {"findings": [{"seat": "(all)", "status": "NEVER_RAN"}]}:
            failures.append(f"--read-last with no report: got {never_ran}")
        fixture = {
            "schema": 1,
            "machine": "selftest",
            "ts": "2026-01-01T00:00:00Z",
            "context": {"ssh": False, "interactive": False},
            "seats": [
                {"seat": "claude", "status": "LIVE", "healthy": True, "latency_ms": 1, "evidence": "PONG", "required": True},
                {"seat": "codex", "status": "AUTH_DEAD", "healthy": False, "latency_ms": 1, "evidence": "401", "required": True},
            ],
            "transitions": [],
            "summary": {"live": 1, "dead_strict": 1, "context_limited": 0, "transient": 0},
        }
        _atomic_write_json(REPORT_DIR / "last.json", fixture)
        result = read_last()
        if result != {"findings": [{"seat": "codex", "status": "AUTH_DEAD"}]}:
            failures.append(f"--read-last fixture: got {result}")
    finally:
        REPORT_DIR = saved
    return failures


def selftest() -> int:
    failures: list[str] = []
    failures += _selftest_classifier()
    failures += _selftest_scrub()
    failures += _selftest_blind_scan()
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        failures += _selftest_read_last(Path(td))

    n_checks = len(_SELFTEST_CANNED) + 2 + 3 + 2  # canned + agy split + scrub cases + read-last cases
    if failures:
        print("SELFTEST FAIL:\n  " + "\n  ".join(failures))
        return 2
    print(f"SELFTEST OK — {n_checks} checks")
    return 0


# ---------------------------------------------------------------- exit semantics

def exit_code_for(report: dict, strict: bool, probed_count: int) -> int:
    if probed_count == 0:
        return 2  # blind-scan guard (W84) — 0 seats probed is never "clean"
    if not strict:
        return 0
    for s in report["seats"]:
        if s.get("required") and is_strict_fail(s["status"]):
            return 1
    return 0


# ---------------------------------------------------------------- main

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seats", default="", help="comma-set of seats to probe (default: all)")
    ap.add_argument("--json", action="store_true", help="print full report JSON to stdout")
    ap.add_argument("--table", action="store_true", help="human table (default when no other output flag)")
    ap.add_argument("--quiet", action="store_true", help="one summary line only")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a required seat strict-fails")
    ap.add_argument("--timeout", type=float, default=1.0, help="multiplier on all per-seat timeouts")
    ap.add_argument("--live-gen", action="store_true", help="ollama: real 1-token generate, not just `list`")
    ap.add_argument("--read-last", action="store_true", help="no probing — re-emit last.json findings")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    seats_filter = [s.strip() for s in args.seats.split(",") if s.strip()] or None

    if args.read_last:
        result = read_last(seats_filter)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    seats = seats_filter or list(ALL_SEATS)
    unknown = [s for s in seats if s not in ALL_SEATS]
    if unknown:
        sys.stderr.write(f"arsenal_probe: unknown seat(s): {', '.join(unknown)}\n")
        return 2

    machine = machine_label()
    # Fail-visible contract (2026-08-07 incident): print something, flushed, to stderr
    # BEFORE any probe fires — never stdout, so --json's stdout stays parseable. Before
    # this, the whole run printed nothing at all until every seat's future resolved
    # (agy alone could eat its full per-seat timeout — see DEFAULT_TIMEOUTS comment),
    # so a `timeout 60 ...` wrapper killing a hung/slow run looked exactly like "0
    # bytes, nothing happened" with zero way to tell a hang from a not-yet-started run.
    ts_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(
        f"arsenal_probe {ts_start} — probing {len(seats)} seat(s) on {machine}: {', '.join(seats)}",
        file=sys.stderr,
        flush=True,
    )
    report = run(seats, timeout_mult=args.timeout, live_gen=args.live_gen, machine=machine)

    try:
        write_report(report)
    except OSError as e:
        sys.stderr.write(f"arsenal_probe: report write FAILED: {e}\n")
        return 2

    required = set(REQUIRED_SEATS.get(machine, []))
    degraded = any(
        s["seat"] in required and is_strict_fail(s["status"]) for s in report["seats"]
    )
    try:
        write_heartbeat(machine, degraded, summary_line(report))
    except OSError as e:
        sys.stderr.write(f"arsenal_probe: heartbeat write FAILED: {e}\n")

    if args.quiet:
        print(summary_line(report))
    elif args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(render_table(report))

    return exit_code_for(report, strict=args.strict, probed_count=len(seats))


if __name__ == "__main__":
    sys.exit(main())
