"""Smoke test: Claude Max OAuth via subprocess (claude -p).

Run inside container with:
    fly ssh console -a nuzantara-rag --process-group api \
      -C "su nuzantara -c 'cd /app && python3 scripts/smoke_claude_oauth.py'"
"""
import asyncio
import sys
import time


async def main() -> int:
    from backend.llm.claude_oauth_client import (
        ClaudeOAuthError,
        ClaudeOAuthNotAvailable,
        _collect_tokens,
        complete_async,
    )

    tokens = _collect_tokens()
    print(f"[enum] labels: {[lab for _, lab in tokens]}")
    print(f"[enum] non-empty tokens: {sum(1 for t, _ in tokens if t)}")

    t0 = time.monotonic()
    try:
        resp = await complete_async(
            "Reply with exactly: SMOKE_OK",
            model="claude-haiku-4-5",
            timeout_s=30,
        )
        print(f"[live] text={resp.text[:120]!r}")
        print(f"[live] token={resp.token_label} attempts={resp.attempts}")
        print(f"[live] elapsed={resp.elapsed_s:.1f}s (wrapper), "
              f"{time.monotonic()-t0:.1f}s (wall)")
        return 0
    except ClaudeOAuthNotAvailable as exc:
        print(f"[fail] CLI missing: {exc}", file=sys.stderr)
        return 10
    except ClaudeOAuthError as exc:
        print(f"[fail] every token failed: {exc}", file=sys.stderr)
        return 20
    except Exception as exc:  # noqa: BLE001
        print(f"[fail] unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 30


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
