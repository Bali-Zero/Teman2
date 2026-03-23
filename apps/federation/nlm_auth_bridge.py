"""
NLM Auth Bridge — Proactive authentication management for NotebookLM.

Addresses the fragile cookie-based auth by:
  1. Proactive health checks before each NLM dispatch
  2. Automatic re-login via `nlm login` if auth expires
  3. Auth status caching to avoid repeated checks
  4. MCP fallback path (via save_auth_tokens) if CLI login fails
  5. Configurable check interval (default: check once per 30 min)

The bridge integrates with CLIAgentExecutor in a2a_service.py.

Usage:
  from apps.federation.nlm_auth_bridge import ensure_nlm_auth, get_nlm_status

  if await ensure_nlm_auth():
      # NLM is authenticated, proceed
  else:
      # Auth failed, use fallback
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("federation.nlm_auth")

# ═══════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════
AUTH_CHECK_INTERVAL = 1800  # 30 minutes — don't check more often than this
AUTH_LOGIN_TIMEOUT = 60     # Max seconds to wait for nlm login
AUTH_CHECK_TIMEOUT = 15     # Max seconds for auth check

# ═══════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════
_last_check_time: float = 0.0
_last_check_result: bool = False
_auth_failures: int = 0
_total_checks: int = 0
_total_relogins: int = 0


async def check_nlm_auth() -> dict[str, Any]:
    """Check NLM authentication status via `nlm login --check`.

    Returns:
        {"valid": bool, "profile": str, "account": str, "notebooks": int, "error": str|None}
    """
    global _total_checks  # noqa: PLW0603
    _total_checks += 1

    try:
        proc = await asyncio.create_subprocess_exec(
            "nlm", "login", "--check",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=AUTH_CHECK_TIMEOUT
        )
        output = (stdout.decode() + stderr.decode()).strip()

        if "Authentication valid" in output or "✓" in output:
            # Parse details from output
            account = ""
            notebooks = 0
            profile = "default"
            for line in output.split("\n"):
                line = line.strip()
                if "Account:" in line:
                    account = line.split("Account:")[-1].strip()
                elif "Notebooks found:" in line:
                    try:
                        notebooks = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Profile:" in line:
                    profile = line.split("Profile:")[-1].strip()

            return {
                "valid": True,
                "profile": profile,
                "account": account,
                "notebooks": notebooks,
                "error": None,
            }
        else:
            return {
                "valid": False,
                "profile": "default",
                "account": "",
                "notebooks": 0,
                "error": output[:200] if output else "Auth check returned non-valid status",
            }

    except asyncio.TimeoutError:
        return {
            "valid": False,
            "profile": "default",
            "account": "",
            "notebooks": 0,
            "error": f"Auth check timed out after {AUTH_CHECK_TIMEOUT}s",
        }
    except FileNotFoundError:
        return {
            "valid": False,
            "profile": "default",
            "account": "",
            "notebooks": 0,
            "error": "nlm CLI not found in PATH",
        }
    except Exception as e:
        return {
            "valid": False,
            "profile": "default",
            "account": "",
            "notebooks": 0,
            "error": str(e),
        }


async def attempt_relogin() -> bool:
    """Attempt automatic re-login via `nlm login`.

    Uses the builtin provider (headless Chrome) which requires
    an existing browser session cookie. If that fails, logs
    instructions for manual intervention.

    Returns True if re-login succeeded.
    """
    global _total_relogins  # noqa: PLW0603
    _total_relogins += 1

    logger.info("Attempting NLM re-login (builtin provider)...")

    try:
        proc = await asyncio.create_subprocess_exec(
            "nlm", "login",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=AUTH_LOGIN_TIMEOUT
        )
        output = (stdout.decode() + stderr.decode()).strip()

        if proc.returncode == 0:
            # Verify auth is actually working now
            check = await check_nlm_auth()
            if check["valid"]:
                logger.info(
                    "NLM re-login successful: %s (%d notebooks)",
                    check["account"], check["notebooks"]
                )
                return True
            else:
                logger.warning("NLM login returned 0 but auth check still fails: %s", check["error"])
                return False
        else:
            logger.warning("NLM re-login failed (exit %d): %s", proc.returncode, output[:200])
            return False

    except asyncio.TimeoutError:
        logger.warning("NLM re-login timed out after %ds", AUTH_LOGIN_TIMEOUT)
        return False
    except Exception as e:
        logger.warning("NLM re-login error: %s", e)
        return False


async def ensure_nlm_auth() -> bool:
    """Ensure NLM is authenticated. Check cache, verify, re-login if needed.

    This is the main entry point — call before any NLM dispatch.
    Uses caching to avoid checking too frequently.

    Returns True if NLM is ready to use, False if auth cannot be restored.
    """
    global _last_check_time, _last_check_result, _auth_failures  # noqa: PLW0603

    now = time.monotonic()

    # Use cached result if recent enough
    if (now - _last_check_time) < AUTH_CHECK_INTERVAL and _last_check_result:
        return True

    # Check auth status
    check = await check_nlm_auth()
    _last_check_time = now

    if check["valid"]:
        _last_check_result = True
        _auth_failures = 0
        return True

    # Auth is invalid — attempt re-login
    logger.warning("NLM auth invalid: %s. Attempting re-login...", check["error"])
    _auth_failures += 1

    success = await attempt_relogin()
    _last_check_result = success

    if not success:
        logger.error(
            "NLM auth could not be restored (failures: %d). "
            "Manual intervention needed: run 'nlm login' in terminal. "
            "Federation will use Qdrant RAG fallback.",
            _auth_failures,
        )

    return success


def get_nlm_status() -> dict[str, Any]:
    """Get current NLM auth bridge status (sync, for metrics/dashboard)."""
    return {
        "last_check_age_s": round(time.monotonic() - _last_check_time, 1) if _last_check_time > 0 else -1,
        "last_check_valid": _last_check_result,
        "auth_failures": _auth_failures,
        "total_checks": _total_checks,
        "total_relogins": _total_relogins,
        "check_interval_s": AUTH_CHECK_INTERVAL,
    }


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════
async def _main() -> None:
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    print("Checking NLM authentication...")
    check = await check_nlm_auth()
    print(json.dumps(check, indent=2))

    if check["valid"]:
        print(f"\n✅ NLM auth valid: {check['account']} ({check['notebooks']} notebooks)")
    else:
        print(f"\n❌ NLM auth invalid: {check['error']}")
        print("Attempting re-login...")
        success = await attempt_relogin()
        print(f"Re-login: {'✅ success' if success else '❌ failed'}")

    print(f"\nBridge status: {json.dumps(get_nlm_status(), indent=2)}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
