#!/usr/bin/env python3
"""kimi_client.py — hardened headless wrapper around the ``kimi`` CLI (v2).

Cascade tier-Kimi wrapper: mirrors the claude-CLI-subprocess doctrine used
elsewhere in this repo (shell out to a local OAuth-authenticated CLI, never
touch a per-token API key). Kimi (Moonshot) is a flat-subscription seat
(Allegro plan, OAuth device-code login) added to the arsenal 2026-07-19 as
the replacement for the retired DeepSeek V4 Pro API (owner order, pre-auth
revoked — never top up). See CLAUDE.md §5 "Kimi seat".

v2 (2026-08-12, lane ops/kimi-seat-hardening): raises the wrapper from
prompt-level discipline to enforced controls, per the Qwen-seat red-team
standard "a prompt instruction is NOT a control"
(research/operations/2026-08-08-qwen-code-seat-integration-and-system-review.md
§5, mirrored from scripts/qwen-cloud-code.sh v3):

v2.1 (2026-08-12, REWORK-BUILD cure after the Opus-5 Gear-2 verdict on
182c82d069 — three CONFIRMED blockers):

0. NO-TOOLS CHILD (C1+C2, the headline fix) — every invocation binds
   scripts/kimi_client_agent.md via --agent-file: `tools: []` disables ALL
   tools in the child (enforced at execution, not just hidden from the
   model). kimi -p is an agent with tools live BY DEFAULT and can read any
   file under cwd and echo it to the cloud — a digit-free prompt sails
   through the prompt gate while the filesystem leaks around it (proven
   with a canary by the Opus-5 grader). With tools disabled the wrapper is
   prompt-in/prompt-out; tasks that genuinely need repo reads belong to an
   interactive kimi session in a worktree, not to this wrapper. This also
   subsume-fixes the missing approval-mode injection (C2): with no tools
   there is nothing to approve, yolo or otherwise.

1. ENV SCRUB (zero-trust, kimi.md §1) — the child process never inherits
   infrastructure credentials. Any inherited variable whose name carries a
   credential marker (API_KEY/TOKEN/SECRET/PASSWORD/DATABASE_URL/…) is
   dropped, except kimi-code's own non-secret KIMI_CODE_*/KIMI_BIN knobs.
   Kimi authenticates via its own OAuth store under ~/.kimi-code and needs
   nothing else.
2. DURABLE PERMS — 0600 re-asserted on ~/.kimi-code/credentials|oauth files
   (0700 on the dirs themselves) before every subprocess run, refused paths
   included (mirrors qwen-cloud-code.sh v3 §0).
3. PII GATE (SYMBIOSIS Law 2) — structural identity-number detector: plain
   digit runs >= 15, or separator-grouped runs of 15-19 digits with identity
   structure (a >= 4-digit group, or mixed separator types like NPWP's
   dot+dash), refused BEFORE any network call. Whitespace is a group
   separator only between >= 3-digit groups, so the seat's sanctioned
   payloads pass: KBLI code lists, port lists, date lists, sample series.
   Declared residual boundary (W113): separated chains of 20+ digits are
   list territory; keywords are intentionally NOT matched (legitimate
   non-PII visa work mentions KTP/NPWP constantly).
   Raises PiiRefusalError (a ValueError, NOT RuntimeError) so future cascade
   callers fail loudly instead of falling through to another cloud seat with
   the same PII prompt (forward-looking: as of v2.1 no production caller
   imports this module — the taxonomy is pre-registered doctrine).
4. MODEL ARG GUARD — model slugs starting with "-" are refused (no flag
   smuggling through -m).

DECLARED RESIDUAL (parity with qwen-cloud-code.sh v3 §3): kimi -p persists a
resumable session transcript under ~/.kimi-code/sessions/; retention control
is harness state, not wrapper state.

HARD RULE — Chinese cloud (SYMBIOSIS Law 2, non-negotiable): NEVER pass
client PII (KTP, passport, NPWP, akta, CRM rows, any UU PDP-regulated field)
in a prompt to this client. Kimi is for non-PII work only (research,
code review, cascade fallback, aggregate/health/intel synthesis) — same
posture as the DeepSeek client it replaces.

Stdlib-only (subprocess, argparse, os, re, sys, shutil) — no new dependencies.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("kimi_client")

DEFAULT_MODEL = "kimi-code/k3"

_KIMI_BIN_DEFAULT = str(Path.home() / ".kimi-code" / "bin" / "kimi")

PONG_PROMPT = "Reply with exactly: PONG"

#: State dirs whose files hold OAuth material — 0600 re-asserted every run.
_KIMI_STATE_DIRS: tuple[Path, ...] = (
    Path.home() / ".kimi-code" / "credentials",
    Path.home() / ".kimi-code" / "oauth",
)

#: Name markers that mark an env var as credential-like. Any inherited var
#: matching one of these is stripped from the child environment.
_CRED_ENV_MARKERS: tuple[str, ...] = (
    "API_KEY",
    "APIKEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT",
    "PRIVATE_KEY",
)

#: Env vars that survive the scrub even if a marker matches (non-secret
#: kimi-code runtime knobs + the binary override used by _resolve_kimi_bin).
_CRED_ENV_ALLOWLIST_PREFIXES: tuple[str, ...] = ("KIMI_CODE_",)
_CRED_ENV_ALLOWLIST_EXACT: frozenset[str] = frozenset({"KIMI_BIN"})

#: PII gate (Law 2) — structural identity-number detector, not a flat regex.
#: A flat "digits + optional separators" pattern is provably both over- and
#: under-matched (Opus-5 verdict on 87f315f185, superscar #3 twin-born):
#: the space is BOTH a group separator in written KTP/NPWP AND the ordinary
#: word separator, so "KBLI 68111 68112 68120 ..." lists were refused while
#: NBSP/tab/slash/comma-grouped or letter-adjacent numbers passed.
#:
#: The detector below parses each maximal digit/separator run and refuses
#: only when the run has IDENTITY structure:
#:   - plain run (no separators): >= 15 digits — a long bare digit string is
#:     never prose;
#:   - separated run: 15-19 total digits AND (a group of >= 4 digits OR mixed
#:     separator types, e.g. NPWP's dot+dash) — AND whitespace is accepted as
#:     a group separator only between groups of >= 3 digits (a chain broken
#:     by prose-like small numbers is a LIST: KBLI codes, ports, dates,
#:     samples — the seat's sanctioned payload — and passes);
#:   - separated runs of 20+ digits are declared list territory (residual
#:     boundary, documented per W113).
#: Shorter totals (< 15) always pass: dates, ports, short ids, phone numbers.
_CANDIDATE_RUN_RE = re.compile(r"\d(?:[\d\s.,/\-\u00a0]*\d)?")
_WHITESPACE_ONLY_RE = re.compile(r"^\s+$")

#: Pinned no-tools agent profile bound to every child invocation via
#: --agent-file (the C1/C2 cure: kimi -p has tools live by default, and a
#: reading child is an exfil channel around the prompt gate).
_AGENT_FILE = Path(__file__).resolve().parent / "kimi_client_agent.md"

#: The one operative line in the pinned profile (proven by the Opus-5
#: inverted-prose control: tools: [] is the control, the prose is decoration).
#: run()/probe() re-verify it on every call — a profile edit that drops or
#: fills the tools list turns the seat dead instead of letting the guard
#: silently lapse (the "pin not armed" finding on 87f315f185).
_NO_TOOLS_MARKER_RE = re.compile(r"^tools:\s*\[\s*\]\s*$", re.MULTILINE)


class PiiRefusalError(ValueError):
    """Prompt refused by the Law-2 PII gate.

    A ValueError (not RuntimeError) on purpose: cascade callers treat
    RuntimeError as "dead seat → try next tier", and a PII prompt must
    never fall through to another cloud seat.
    """


def _resolve_kimi_bin() -> str | None:
    """Resolve the ``kimi`` CLI binary: env override -> known install path ->
    PATH lookup. Never raises."""
    env_override = os.environ.get("KIMI_BIN")
    if env_override:
        # A dangling override must fall through, not shadow a working install
        # (semantics aligned with codex_tri_llm_review._resolve_kimi_bin).
        if Path(env_override).exists():
            return env_override
    if Path(_KIMI_BIN_DEFAULT).exists():
        return _KIMI_BIN_DEFAULT
    return shutil.which("kimi")


def _assert_credential_perms() -> None:
    """Re-assert 0600 on Kimi OAuth state files, 0700 on the dirs. Never raises.

    Mirrors qwen-cloud-code.sh v3 §0: durable perms are re-asserted on every
    invocation, including runs that will be refused later, so a refusal never
    leaves the state dir exposed.
    """
    for state_dir in _KIMI_STATE_DIRS:
        try:
            if not state_dir.is_dir():
                continue
            state_dir.chmod(0o700)
            for entry in state_dir.iterdir():
                if entry.is_file():
                    entry.chmod(0o600)
        except OSError as exc:
            logger.warning("kimi_client: perms re-assert failed on %s: %s", state_dir, exc)


def _scrubbed_env() -> dict[str, str]:
    """Child environment with credential-like variables removed (zero-trust).

    kimi.md §1: no Fly/Vercel/GitHub/DB tokens and no .env material in the
    Kimi seat's environment. The CLI authenticates from ~/.kimi-code and is
    documented to NOT fall back to shell env for provider keys, so scrubbing
    cannot break its own auth.
    """
    env = {}
    dropped = []
    for key, value in os.environ.items():
        upper = key.upper()
        if key in _CRED_ENV_ALLOWLIST_EXACT or any(
            upper.startswith(p) for p in _CRED_ENV_ALLOWLIST_PREFIXES
        ):
            env[key] = value
            continue
        if any(marker in upper for marker in _CRED_ENV_MARKERS):
            dropped.append(key)
            continue
        env[key] = value
    if dropped:
        logger.info("kimi_client: scrubbed credential env vars: %s", ", ".join(sorted(dropped)))
    return env


def _is_identity_shape(candidate: str) -> bool:
    """True iff a digit/separator run has identity-number structure."""
    parts = re.split(r"(\D+)", candidate)  # [group, sep, group, ...]
    groups = parts[0::2]
    seps = parts[1::2]
    total = sum(len(g) for g in groups)
    if total < 15:
        return False
    if not seps:
        return True  # plain bare run of >= 15 digits is never prose
    if total > 19:
        return False  # long separated chains are lists (KBLI/port/date enums)
    # whitespace counts as a group separator only between substantial groups;
    # a chain linked through 1-2 digit groups is prose enumeration, not one number
    for i, sep in enumerate(seps):
        if _WHITESPACE_ONLY_RE.match(sep) and (len(groups[i]) < 3 or len(groups[i + 1]) < 3):
            return False
    distinct_seps = {"" if _WHITESPACE_ONLY_RE.match(s) else s for s in seps}
    return max(len(g) for g in groups) >= 4 or len(distinct_seps) > 1


def _check_prompt(prompt: str) -> None:
    """Law-2 PII gate. Raises PiiRefusalError on identity-number shapes."""
    for match in _CANDIDATE_RUN_RE.finditer(prompt):
        if _is_identity_shape(match.group(0)):
            raise PiiRefusalError(
                "prompt refused by the Law-2 PII gate: identity-number shape "
                "detected (15-19 digits, plain or grouped — KTP/NPWP/card). "
                "Kimi is a Chinese-cloud, non-PII seat — route this work to a "
                "local model (pii_intake chain) instead."
            )


def _assert_no_tools_profile() -> None:
    """Verify the pinned agent profile still disables all tools. Fail closed.

    The C1/C2 cure rests entirely on `tools: []` in _AGENT_FILE (the Opus-5
    inverted-prose control proved the frontmatter is the operative control,
    not the prose). A profile edit that drops or fills the tools list must
    turn the seat DEAD, not silently re-arm the exfil channel.
    """
    if not _AGENT_FILE.is_file():
        raise RuntimeError(f"pinned no-tools agent file missing: {_AGENT_FILE}")
    try:
        text = _AGENT_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"pinned no-tools agent file unreadable: {exc}") from exc
    if not _NO_TOOLS_MARKER_RE.search(text):
        raise RuntimeError(
            f"pinned agent profile {_AGENT_FILE} no longer disables all tools "
            "(`tools: []` absent from frontmatter) — seat dead by construction"
        )


def _check_model(model: str) -> None:
    """Refuse model slugs that could smuggle a CLI flag through ``-m``."""
    if model.startswith("-"):
        raise ValueError(f"model slug {model!r} refused: must not start with '-'")


def probe(timeout: float = 60.0) -> bool:
    """One-shot liveness probe. Returns True iff the CLI answered PONG.

    Never raises — a missing binary, a timeout, or any subprocess error all
    resolve to False (dead seat), matching the "signaler, never actuator"
    doctrine of scripts/arsenal_probe.py.
    """
    _assert_credential_perms()
    binp = _resolve_kimi_bin()
    if not binp:
        logger.warning("kimi_client.probe: kimi binary not found")
        return False
    try:
        _assert_no_tools_profile()
    except RuntimeError as exc:
        logger.warning("kimi_client.probe: %s", exc)
        return False
    try:
        result = subprocess.run(
            [binp, "-m", DEFAULT_MODEL, "-p", PONG_PROMPT, "--agent-file", str(_AGENT_FILE)],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=_scrubbed_env(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("kimi_client.probe: subprocess failed: %s", exc)
        return False
    return "PONG" in result.stdout


def run(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout: float = 300.0,
    cwd: str | None = None,
) -> str:
    """Run ``prompt`` through the ``kimi`` CLI, return stdout.

    Raises PiiRefusalError (ValueError) when the Law-2 gate refuses the
    prompt — loudly, so cascades do NOT fall through to another cloud seat
    with the same prompt. Raises RuntimeError (with a stderr excerpt) on a
    missing binary, a missing pinned agent file, a non-zero exit, or a
    timeout — the caller decides how to degrade (e.g. a cascade fallback
    treats this as a dead seat, never a crash of the whole run).

    The child is always bound to scripts/kimi_client_agent.md (tools: [] —
    no filesystem, no shell, no network beyond the model call), so ``cwd``
    is only the session's nominal directory, never a data channel.
    """
    _assert_credential_perms()
    _check_model(model)
    _check_prompt(prompt)
    binp = _resolve_kimi_bin()
    if not binp:
        raise RuntimeError("kimi binary not found (KIMI_BIN unset, ~/.kimi-code/bin/kimi absent, not on PATH)")
    _assert_no_tools_profile()
    try:
        result = subprocess.run(
            [binp, "-m", model, "-p", prompt, "--agent-file", str(_AGENT_FILE)],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            env=_scrubbed_env(),
        )
    except subprocess.TimeoutExpired as exc:
        stderr_excerpt = (exc.stderr or b"")
        if isinstance(stderr_excerpt, bytes):
            stderr_excerpt = stderr_excerpt.decode(errors="replace")
        raise RuntimeError(f"kimi run timed out after {timeout}s: {stderr_excerpt[:500]}") from exc
    except OSError as exc:
        raise RuntimeError(f"kimi run failed to start: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"kimi run exited {result.returncode}: {result.stderr.strip()[:500]}"
        )
    return result.stdout


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2] if __doc__ else "kimi_client")
    ap.add_argument("--probe", action="store_true", help="one-shot PONG liveness probe")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"model slug (default: {DEFAULT_MODEL})")
    ap.add_argument("prompt", nargs="?", help="prompt to send (required unless --probe)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    _assert_credential_perms()  # refused paths re-assert too (qwen v3 §0)
    args = _parse_args(argv)

    if args.probe:
        ok = probe()
        print("LIVE" if ok else "DEAD")
        return 0 if ok else 1

    if not args.prompt:
        print("kimi_client: error: prompt is required unless --probe", file=sys.stderr)
        return 2

    try:
        output = run(args.prompt, model=args.model)
    except (PiiRefusalError, ValueError) as exc:
        # refusals (Law-2 gate, model guard) are exit 3 — distinct from usage
        # errors (2) and runtime failures (1)
        print(f"kimi_client: REFUSED: {exc}", file=sys.stderr)
        return 3
    except RuntimeError as exc:
        print(f"kimi_client: error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
