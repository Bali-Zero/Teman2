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
    python3 scripts/arsenal_probe.py                       # probe all 7 seats, write report
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

ALL_SEATS = ["claude", "glm", "agy", "codex", "deepseek", "ollama", "nlm"]

REQUIRED_SEATS = {
    "mini": ["claude", "glm", "codex", "ollama"],
    "pro": ["claude", "codex", "deepseek", "ollama", "nlm"],
    "m5": ["claude", "glm", "agy", "codex"],
}

DEFAULT_TIMEOUTS = {
    "claude": 120,
    "glm": 45,
    "agy": 120,
    "codex": 180,
    "deepseek": 45,
    "ollama": 30,
    "nlm": 60,
}
OLLAMA_LIVE_GEN_TIMEOUT = 120

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
    scrubbed = scrub((text or "").strip().replace("\n", " "), extra_secrets)
    return scrubbed[:limit]


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
_AUTH_DEAD_PAT = re.compile(
    r"\b401\b|authentication failed|token_revoked|refresh_token_reused|oauth token", re.IGNORECASE
)
_QUOTA_DEAD_PAT = re.compile(
    r"out of extra usage|usage limit|quota|\b429\b|rate.?limit|exhausted", re.IGNORECASE
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
    cmd: list[str], timeout: float, env: Optional[dict] = None, stdin_devnull: bool = False
) -> ProbeResult:
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


def resolve_bin(name: str, extra_paths: Optional[list[str]] = None) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for p in extra_paths or []:
        expanded = os.path.expanduser(p)
        if Path(expanded).exists():
            return expanded
    return None


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


# ---------------------------------------------------------------- HTTP helper

def http_post_json(
    url: str, headers: dict, body: dict, timeout: float, secret_values: list[str]
) -> tuple[Optional[int], str]:
    """POST JSON, return (status_code_or_None, evidence_text). Never raises past this
    boundary, and the Authorization/x-api-key header value never appears in the
    returned evidence even on error (scar #4 — errors are the #1 leak vector)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, evidence_tail(raw, secret_values)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, evidence_tail(raw, secret_values)
    except urllib.error.URLError as e:
        # str(e.reason) could theoretically echo a header on some transports; scrub
        # unconditionally rather than trust the transport not to leak (defense-in-depth).
        return None, evidence_tail(f"{type(e).__name__}: {e.reason}", secret_values)
    except TimeoutError:
        return None, "timed out"
    except Exception as e:  # a probe must never crash the whole run
        return None, evidence_tail(f"{type(e).__name__}: {e}", secret_values)


# ---------------------------------------------------------------- per-seat probes

def probe_claude(timeout: float, env_overrides: Optional[dict] = None) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp = os.environ.get("ARSENAL_CLAUDE_BIN") or resolve_bin("claude", ["/opt/homebrew/bin/claude"])
    if not binp:
        return NOT_INSTALLED, "claude binary not found", 0
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # scar-load-bearing: never let the paid key leak in
    # A stray GLM-session env (AUTH_TOKEN + base URL) would silently probe z.ai
    # while reporting it as the MAX seat — strip both for a clean MAX-context probe.
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("ANTHROPIC_BASE_URL", None)
    # Headless/cron callers (launchd, sshd) often carry only the slotted
    # CLAUDE_CODE_OAUTH_TOKEN_{1,2,3} vars, never the bare one the `claude`
    # binary actually reads — same fallback already established in
    # organ_birth.py / regulatory-watcher-run.sh (CLAUDE.md's sanctioned
    # CLI-subprocess auth path). Without this the probe reports a false
    # UNKNOWN_ERR ("Not logged in") even when the MAX-plan session backing
    # slot 1 is perfectly alive.
    if not env.get("CLAUDE_CODE_OAUTH_TOKEN") and env.get("CLAUDE_CODE_OAUTH_TOKEN_1"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = env["CLAUDE_CODE_OAUTH_TOKEN_1"]
    if env_overrides:
        env.update(env_overrides)
    res = run_probe_cmd(
        [binp, "-p", PONG_PROMPT, "--model", "claude-sonnet-5"], timeout=timeout, env=env
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = evidence_tail(res.stdout + " " + res.stderr)
    if res.timed_out:
        return TIMEOUT, ev or "probe timed out", latency_ms
    live = "PONG" in res.stdout
    status = classify_generic(res.stdout + res.stderr, live, "claude", is_ssh_context())
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
    status_code, ev = http_post_json(
        "https://api.z.ai/api/anthropic/v1/messages", headers, body, timeout, [token]
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if status_code is None:
        return TIMEOUT if "timed out" in ev else UNKNOWN_ERR, ev, latency_ms
    live = status_code == 200 and '"model"' in ev
    status = classify_generic(f"HTTP {status_code} {ev}", live, "glm", is_ssh_context())
    return status, f"HTTP {status_code} {ev}", latency_ms


def probe_agy(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp = resolve_bin("agy", ["~/.local/bin/agy"])
    if not binp:
        return NOT_INSTALLED, "agy binary not found", 0
    res = run_probe_cmd([binp, "-p", PONG_PROMPT], timeout=timeout)
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = evidence_tail(res.stdout + " " + res.stderr)
    if res.timed_out:
        return TIMEOUT, ev or "probe timed out", latency_ms
    live = "PONG" in res.stdout
    status = classify_generic(res.stdout + res.stderr, live, "agy", is_ssh_context())
    return status, ev, latency_ms


def probe_codex(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp = resolve_bin("codex", ["/opt/homebrew/bin/codex"])
    if not binp:
        return NOT_INSTALLED, "codex binary not found", 0
    res = run_probe_cmd(
        [binp, "exec", "--sandbox", "read-only", "--skip-git-repo-check", PONG_PROMPT],
        timeout=timeout,
        stdin_devnull=True,  # codex blocks on an open stdin — must never inherit one
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = evidence_tail(res.stdout + " " + res.stderr)
    if res.timed_out:
        return TIMEOUT, ev or "probe timed out", latency_ms
    live = "PONG" in res.stdout
    status = classify_generic(res.stdout + res.stderr, live, "codex", is_ssh_context())
    return status, ev, latency_ms


def probe_deepseek(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    key, cred_note = load_env_master_key("DEEPSEEK_API_KEY")
    if key is None:
        return CRED_UNAVAILABLE, cred_note or "credential unavailable", int((time.monotonic() - t0) * 1000)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": "deepseek-v4-flash", "max_tokens": 1, "messages": [{"role": "user", "content": PONG_PROMPT}]}
    status_code, ev = http_post_json(
        "https://api.deepseek.com/chat/completions", headers, body, timeout, [key]
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if status_code is None:
        return TIMEOUT if "timed out" in ev else UNKNOWN_ERR, ev, latency_ms
    live = status_code == 200
    status = classify_generic(f"HTTP {status_code} {ev}", live, "deepseek", is_ssh_context())
    return status, f"HTTP {status_code} {ev}", latency_ms


def probe_ollama(timeout: float, live_gen: bool = False) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp = resolve_bin("ollama")
    if not binp:
        return NOT_INSTALLED, "ollama binary not found", 0
    res = run_probe_cmd([binp, "list"], timeout=timeout)
    latency_ms = int((time.monotonic() - t0) * 1000)
    if res.timed_out:
        return TIMEOUT, evidence_tail(res.stdout + res.stderr) or "probe timed out", latency_ms
    model_listed = "qwen3.5" in res.stdout
    if not model_listed:
        ev = evidence_tail(res.stdout + " " + res.stderr)
        status = classify_generic(res.stdout + res.stderr, False, "ollama", is_ssh_context())
        return status, ev or "qwen3.5 not listed", latency_ms
    if not live_gen:
        return LIVE, "qwen3.5 listed", latency_ms
    gen_res = run_probe_cmd(
        [binp, "run", "qwen3.5:9b"], timeout=OLLAMA_LIVE_GEN_TIMEOUT * timeout / DEFAULT_TIMEOUTS["ollama"],
        stdin_devnull=False,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if gen_res.timed_out:
        return TIMEOUT, "live-gen timed out", latency_ms
    live = bool(gen_res.stdout.strip())
    ev = evidence_tail(gen_res.stdout + " " + gen_res.stderr)
    status = classify_generic(gen_res.stdout + gen_res.stderr, live, "ollama", is_ssh_context())
    return status, ev or "live-gen produced no output", latency_ms


def probe_nlm(timeout: float) -> tuple[str, str, int]:
    t0 = time.monotonic()
    binp = resolve_bin("nlm")
    if not binp:
        return NOT_INSTALLED, "nlm binary not found", 0
    res = run_probe_cmd([binp, "list", "notebooks"], timeout=timeout)
    latency_ms = int((time.monotonic() - t0) * 1000)
    ev = evidence_tail(res.stdout + " " + res.stderr)
    if res.timed_out:
        return TIMEOUT, ev or "probe timed out", latency_ms
    live = False
    try:
        parsed = json.loads(res.stdout)
        live = isinstance(parsed, (list, dict))
    except (json.JSONDecodeError, ValueError):
        live = False
    status = classify_generic(res.stdout + res.stderr, live, "nlm", is_ssh_context())
    return status, ev, latency_ms


PROBE_FUNCS: dict[str, Callable[..., tuple[str, str, int]]] = {
    "claude": probe_claude,
    "glm": probe_glm,
    "agy": probe_agy,
    "codex": probe_codex,
    "deepseek": probe_deepseek,
    "ollama": probe_ollama,
    "nlm": probe_nlm,
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
    heartbeat = {
        "organ": f"{machine}.arsenal_probe",
        "status": "degraded" if degraded else "ok",
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
    return "\n".join(lines)


def summary_line(report: dict) -> str:
    summ = report["summary"]
    return (
        f"arsenal_probe {report['machine']}: {summ['live']} live, {summ['dead_strict']} dead_strict, "
        f"{summ['context_limited']} context_limited, {summ['transient']} transient"
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
