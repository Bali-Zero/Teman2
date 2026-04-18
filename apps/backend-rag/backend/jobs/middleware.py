"""Safety middleware stack for the jobs runner.

Three default-on middleware, applied outer-to-inner in this order:
 1. OAuthGuard     — fails fast if ANTHROPIC_API_KEY is set (hard rule).
 2. CostCap        — budget per run, defaults to $1.00 (100 cents).
 3. ClaudeCliFallback — sets ctx.claude_cli_available based on env.

Each middleware supports opt-out via JobDeclaration.skip_middleware; the
registry enforces that opt-out requires a non-empty reason string.
"""
from __future__ import annotations

import os
import sys

from backend.jobs.context import JobContext
from backend.jobs.retry import CostExceeded, OAuthViolation


class OAuthGuard:
    NAME = "oauth_guard"

    async def check(self, ctx: JobContext) -> None:
        if os.environ.get("ANTHROPIC_API_KEY"):
            ctx.logger.error(
                "job.violation",
                extra={
                    "event": "job.violation",
                    "middleware": self.NAME,
                    "detail": "ANTHROPIC_API_KEY present in env",
                    "job_name": ctx.job_name,
                },
            )
            raise OAuthViolation(
                f"ANTHROPIC_API_KEY must not be set in job {ctx.job_name!r} "
                "(OAuth-only policy). Use OAuth token instead."
            )


class CostCap:
    NAME = "cost_cap"

    def __init__(self, limit_cents: int = 100) -> None:
        self.limit_cents = limit_cents

    def check(self, ctx: JobContext) -> None:
        if ctx.meter.total_cents > self.limit_cents:
            raise CostExceeded(
                f"job {ctx.job_name!r} spent {ctx.meter.total_cents} cents, "
                f"cap is {self.limit_cents}"
            )


def detect_claude_cli_available() -> bool:
    """Claude CLI hangs on Linux non-TTY (feedback_claude_cli_linux_hang.md).

    On macOS OR on a TTY, assume the CLI works. On Linux non-TTY
    (Fly.io container), report False so handlers route around it.
    """
    is_linux = sys.platform.startswith("linux")
    try:
        is_tty = sys.stdout.isatty()
    except Exception:
        is_tty = False
    if is_linux and not is_tty:
        return False
    return True
