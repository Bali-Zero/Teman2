"""
guardrail_liveness — behavioral liveness checks for the guardrail stack.

Born from the Anthropic "When AI builds itself" reflection (2026-06-06): the
named bottleneck of the likely future is "verify can't keep up with generate".
We had scars of guardrails alive-on-paper / dead-in-fact (cascade silently
2-deep; stop_verify WIRED-BUT-DISABLED via STOP_VERIFY_ALLOW_DIRTY=1;
verify_mcp_integrity.sh claimed-shipped but absent on disk). This module makes
that decay OBSERVABLE.

Design (spec 2026-06-06-guardrail-liveness-sentinel.md) + 4-LLM CODE panel
hardening (Codex + Gemini, 2026-06-06 — ~11 real defects fixed pre-merge):
  - "present + wired" is NOT liveness. A guardrail can be wired in settings.json
    yet disabled by an env override IN THE COMMAND **or in the daemon env**
    (the stop_verify counterexample). We check both.
  - Wired hooks must also resolve to an EXISTING, NON-EMPTY file on disk — a
    hook pointing at a deleted/zero-byte script is dead-in-fact (panel C#3/#4).
  - Hook detection matches the script path as a real token, not a loose
    substring (`stop_verify.py.bak` / `echo stop_verify.py` must NOT pass).
  - Disable-env regex is word-boundary-anchored, case-insensitive, exact-value
    (panel C#6/G#2); "0/false/no" is NOT a disable.
  - Host matching normalizes FQDN/.local/case and rejects str-as-hosts (G#8/9).
  - Regression key = per-guardrail status vector. Duplicate registry names are a
    config error (loud), never a silently-overwritten OK (G#7).
  - First-run / any-dead alerts (born-dead not silently baselined).
  - settings.json corruption fails LOUD, redacted (no file content in alert),
    catching JSONDecodeError + OSError + UnicodeDecodeError (panel C#7/G#4/#6).
  - Missing registry keys → loud per-guardrail DEAD, never abort the whole run.

No side effects on import; does NOT send alerts itself — returns a structured
report the caller (run_sentinel) folds into status_obj and routes via send_alert.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import socket
from dataclasses import dataclass, field
from typing import Callable

# ---- status constants -------------------------------------------------------

OK = "ok"
DEAD = "dead"
DISABLED = "disabled"  # present + wired but neutralized (command or env)
ABSENT = "absent"  # expected on this host, not found / empty
SKIP = "skip"  # not applicable on this host (wrong host) — not a failure


# ---- registry ---------------------------------------------------------------

DEFAULT_REGISTRY: list[dict] = [
    {
        "name": "stop_verify",
        "hosts": ["*"],
        "probe": "hook_not_env_disabled",
        "settings_key": "stop_verify.py",
        "disable_env": "STOP_VERIFY_ALLOW_DIRTY",
    },
    {
        "name": "dispatch_nudge",
        "hosts": ["*"],
        "probe": "hook_wired",
        "settings_key": "dispatch_nudge.py",
    },
    {
        "name": "guardrails_destructive_mcp",
        "hosts": ["*"],
        "probe": "hook_wired",
        "settings_key": "guardrails-client.sh",
    },
    # verify_mcp_integrity.sh deliberately NOT seeded — phantom (scar 2026-06-06).
]


# ---- result types -----------------------------------------------------------


@dataclass
class GuardrailResult:
    name: str
    status: str
    detail: str = ""


@dataclass
class LivenessReport:
    host: str
    results: list[GuardrailResult] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)
    alert_needed: bool = False
    alert_reason: str = ""

    def vector(self) -> dict[str, str]:
        # Duplicate names are a config error, not a silent overwrite (G#7):
        # surface the WORST status for any duplicated name.
        order = [SKIP, OK, DISABLED, ABSENT, DEAD]  # increasing severity
        sev = {s: i for i, s in enumerate(order)}
        out: dict[str, str] = {}
        for r in self.results:
            if r.name not in out or sev.get(r.status, 99) > sev.get(out[r.name], -1):
                out[r.name] = r.status
        return out

    def to_status_obj(self) -> dict:
        return {
            "host": self.host,
            "vector": self.vector(),
            "regressed": self.regressed,
            "alert_needed": self.alert_needed,  # C#9: do not drop
            "alert_reason": self.alert_reason,
            "details": {r.name: r.detail for r in self.results if r.detail},
        }


# ---- helpers ----------------------------------------------------------------

# truthy env values that DISABLE a guardrail (case-insensitive, exact)
_TRUTHY = {"1", "true", "yes", "on"}


def _settings_command_strings(settings: dict | None) -> list[str]:
    """Flatten every hook command string. Defensive against malformed shapes
    (G#3: a non-list 'hooks' must not raise)."""
    if not isinstance(settings, dict):
        return []
    out: list[str] = []
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return out
    for _event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            hook_list = group.get("hooks")
            if not isinstance(hook_list, list):
                continue
            for hook in hook_list:
                if isinstance(hook, dict):
                    cmd = hook.get("command")
                    if isinstance(cmd, str):
                        out.append(cmd)
    return out


def _command_runs_script(cmd: str, key: str) -> bool:
    """True iff `cmd` actually invokes the script named by `key`, as a token
    (not a loose substring, not a .bak, not an echo arg). (panel C#2)."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()
    base = os.path.basename(key)
    for t in tokens:
        # strip leading env-assignments handled separately; match path tokens
        tb = os.path.basename(t)
        if tb == base:
            return True
    return False


def _resolve_hook_path(cmd: str, key: str) -> str | None:
    """Return the on-disk path token matching key, expanded, or None."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()
    base = os.path.basename(key)
    for t in tokens:
        if os.path.basename(t) == base:
            return os.path.expanduser(t)
    return None


def _file_is_live(path: str | None) -> bool:
    """Existing AND non-empty (zero-byte script is dead-in-fact, panel C#4)."""
    return bool(path) and os.path.isfile(path) and os.path.getsize(path) > 0


def _env_disables(cmd: str, env: dict, disable_env: str) -> bool:
    """Disable if the env var is truthy EITHER inline in the command OR exported
    in the daemon environment (panel C#1/G#1). Word-boundary, case-insensitive,
    exact value (panel C#6/G#2)."""
    # inline: VAR=val as its own assignment token in the command
    pat = re.compile(rf"(^|\s){re.escape(disable_env)}=(\S+)")
    for m in pat.finditer(cmd):
        if m.group(2).strip("'\"").lower() in _TRUTHY:
            return True
    # exported in daemon env
    val = env.get(disable_env)
    if isinstance(val, str) and val.strip("'\"").lower() in _TRUTHY:
        return True
    return False


# ---- probes -----------------------------------------------------------------


def probe_hook_wired(entry: dict, ctx: dict) -> GuardrailResult:
    name = entry["name"]
    key = entry["settings_key"]
    cmds = _settings_command_strings(ctx.get("settings"))
    wiring = [c for c in cmds if _command_runs_script(c, key)]
    if not wiring:
        return GuardrailResult(name, DEAD, f"not wired in settings.json ({key})")
    # wired — but does the referenced file actually exist + non-empty? (C#3/#4)
    for c in wiring:
        if _file_is_live(_resolve_hook_path(c, key)):
            return GuardrailResult(name, OK, f"wired + file live ({key})")
    return GuardrailResult(name, DEAD, f"wired but file missing/empty ({key})")


def probe_hook_not_env_disabled(entry: dict, ctx: dict) -> GuardrailResult:
    name = entry["name"]
    key = entry["settings_key"]
    disable_env = entry["disable_env"]
    env = ctx.get("env", {})
    cmds = _settings_command_strings(ctx.get("settings"))
    wiring = [c for c in cmds if _command_runs_script(c, key)]
    if not wiring:
        return GuardrailResult(name, DEAD, f"not wired ({key})")
    # neutralized by env override (inline in any wiring cmd, or daemon env)?
    if any(_env_disables(c, env, disable_env) for c in wiring):
        return GuardrailResult(
            name, DISABLED, f"wired but neutralized by {disable_env}"
        )
    # also require the file to be live
    for c in wiring:
        if _file_is_live(_resolve_hook_path(c, key)):
            return GuardrailResult(name, OK, f"wired, enabled, file live ({key})")
    return GuardrailResult(name, DEAD, f"wired+enabled but file missing/empty ({key})")


def probe_script_exists(entry: dict, ctx: dict) -> GuardrailResult:
    name = entry["name"]
    path = os.path.expanduser(entry["path"])
    if _file_is_live(path):
        return GuardrailResult(name, OK, path)
    if os.path.isfile(path):
        return GuardrailResult(name, ABSENT, f"present but EMPTY: {path}")
    return GuardrailResult(name, ABSENT, f"expected at {path}")


PROBES: dict[str, Callable[[dict, dict], GuardrailResult]] = {
    "hook_wired": probe_hook_wired,
    "hook_not_env_disabled": probe_hook_not_env_disabled,
    "script_exists": probe_script_exists,
}

# required keys per probe (missing → loud per-guardrail DEAD, never abort, C#8)
_REQUIRED_KEYS = {
    "hook_wired": ["settings_key"],
    "hook_not_env_disabled": ["settings_key", "disable_env"],
    "script_exists": ["path"],
}


# ---- host matching ----------------------------------------------------------


def _norm_host(h: str) -> str:
    """Normalize for comparison: lowercase, strip .local / first FQDN label
    keeps the short name (G#8/#9)."""
    h = (h or "").strip().lower()
    if h.endswith(".local"):
        h = h[: -len(".local")]
    # take short hostname (before first dot) for FQDN
    return h.split(".")[0]


def _host_applies(entry: dict, host: str) -> bool:
    hosts = entry.get("hosts", ["*"])
    if not isinstance(hosts, list):  # str-as-hosts is a config error → don't apply loosely
        return False
    if "*" in hosts:
        return True
    nh = _norm_host(host)
    return any(_norm_host(h) == nh for h in hosts)


# ---- main entry -------------------------------------------------------------


def _load_settings(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)  # may raise JSONDecodeError / UnicodeDecodeError


def run_check(
    *,
    registry: list[dict] | None = None,
    host: str | None = None,
    settings_path: str | None = None,
    prior_vector: dict[str, str] | None = None,
    env: dict | None = None,
) -> LivenessReport:
    # Copy so a caller/test mutating the result can't corrupt the module-level
    # DEFAULT_REGISTRY across runs (DeepSeek panel #7).
    registry = list(registry if registry is not None else DEFAULT_REGISTRY)
    host = host or socket.gethostname()
    env = env if env is not None else dict(os.environ)
    if settings_path is None:
        settings_path = os.path.expanduser("~/.claude/settings.json")

    settings_error: str | None = None
    settings: dict | None = None
    try:
        settings = _load_settings(settings_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        # redact: do NOT echo file content (G#6); just the error TYPE
        settings_error = f"settings.json corrupt ({type(exc).__name__})"
    except OSError as exc:
        settings_error = f"settings.json unreadable ({type(exc).__name__})"

    ctx = {"settings": settings, "env": env}
    report = LivenessReport(host=host)

    if settings_error is not None:
        report.results.append(GuardrailResult("settings_json", DEAD, settings_error))

    # detect duplicate names up front (G#7) — loud config error
    names = [e.get("name", "?") for e in registry]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        report.results.append(
            GuardrailResult(
                "registry_config", DEAD, f"duplicate guardrail names: {sorted(dupes)}"
            )
        )

    for entry in registry:
        name = entry.get("name", "?")
        probe_key = entry.get("probe")
        if not _host_applies(entry, host):
            report.results.append(GuardrailResult(name, SKIP, f"not on {host}"))
            continue
        probe = PROBES.get(probe_key)
        if probe is None:
            report.results.append(GuardrailResult(name, DEAD, f"unknown probe {probe_key!r}"))
            continue
        missing = [k for k in _REQUIRED_KEYS.get(probe_key, []) if k not in entry]
        if missing:
            report.results.append(
                GuardrailResult(name, DEAD, f"registry entry missing keys {missing}")
            )
            continue
        try:
            report.results.append(probe(entry, ctx))
        except Exception as exc:  # a buggy probe must not kill the whole sweep
            report.results.append(
                GuardrailResult(name, DEAD, f"probe error: {type(exc).__name__}")
            )

    _decide_alert(report, prior_vector)
    return report


_FAILED_STATES = {DEAD, DISABLED, ABSENT}


def _decide_alert(report: LivenessReport, prior_vector: dict[str, str] | None) -> None:
    cur = report.vector()
    failed_now = {n for n, s in cur.items() if s in _FAILED_STATES}

    if prior_vector:
        for name, status in cur.items():
            prev = prior_vector.get(name)
            # A guardrail UNKNOWN in prior (prev is None) that is born-dead is
            # NOT a regression — it was never seen OK (DeepSeek panel #5). Only
            # a transition from a known-good prior state counts as regression.
            if (
                status in _FAILED_STATES
                and prev is not None
                and prev not in _FAILED_STATES
            ):
                report.regressed.append(name)

    if failed_now:
        report.alert_needed = True
        if report.regressed:
            report.alert_reason = (
                f"guardrail regression: {', '.join(sorted(report.regressed))} "
                f"(all currently failed: {', '.join(sorted(failed_now))})"
            )
        else:
            report.alert_reason = (
                f"guardrail(s) not protecting: {', '.join(sorted(failed_now))}"
            )
    else:
        report.alert_needed = False
        report.alert_reason = ""


__all__ = [
    "run_check", "LivenessReport", "GuardrailResult", "DEFAULT_REGISTRY",
    "OK", "DEAD", "DISABLED", "ABSENT", "SKIP",
]
