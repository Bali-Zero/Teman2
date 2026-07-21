#!/usr/bin/env python3
"""kimi_client.py — thin headless wrapper around the ``kimi`` CLI.

Cascade tier-Kimi wrapper: mirrors the claude-CLI-subprocess doctrine used
elsewhere in this repo (shell out to a local OAuth-authenticated CLI, never
touch a per-token API key). Kimi (Moonshot) is a flat-subscription seat
(Allegro plan, OAuth device-code login) added to the arsenal 2026-07-19 as
the replacement for the retired DeepSeek V4 Pro API (owner order, pre-auth
revoked — never top up). See CLAUDE.md §5 "Kimi seat".

HARD RULE — Chinese cloud (SYMBIOSIS Law 2, non-negotiable): NEVER pass
client PII (KTP, passport, NPWP, akta, CRM rows, any UU PDP-regulated field)
in a prompt to this client. Kimi is for non-PII work only (research,
code review, cascade fallback, aggregate/health/intel synthesis) — same
posture as the DeepSeek client it replaces.

Stdlib-only (subprocess, argparse, os, sys, shutil) — no new dependencies.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("kimi_client")

DEFAULT_MODEL = "kimi-code/k3"

_KIMI_BIN_DEFAULT = str(Path.home() / ".kimi-code" / "bin" / "kimi")

PONG_PROMPT = "Reply with exactly: PONG"


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


def probe(timeout: float = 60.0) -> bool:
    """One-shot liveness probe. Returns True iff the CLI answered PONG.

    Never raises — a missing binary, a timeout, or any subprocess error all
    resolve to False (dead seat), matching the "signaler, never actuator"
    doctrine of scripts/arsenal_probe.py.
    """
    binp = _resolve_kimi_bin()
    if not binp:
        logger.warning("kimi_client.probe: kimi binary not found")
        return False
    try:
        result = subprocess.run(
            [binp, "-m", DEFAULT_MODEL, "-p", PONG_PROMPT],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
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

    Raises RuntimeError (with a stderr excerpt) on a missing binary, a
    non-zero exit, or a timeout — the caller decides how to degrade (e.g. a
    cascade fallback treats this as a dead seat, never a crash of the whole
    run).
    """
    binp = _resolve_kimi_bin()
    if not binp:
        raise RuntimeError("kimi binary not found (KIMI_BIN unset, ~/.kimi-code/bin/kimi absent, not on PATH)")
    try:
        result = subprocess.run(
            [binp, "-m", model, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
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
    except RuntimeError as exc:
        print(f"kimi_client: error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
