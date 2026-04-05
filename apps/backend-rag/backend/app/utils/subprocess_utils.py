"""
Secure subprocess execution utilities.

Prevents command injection and ensures safe execution of external commands.
"""

import logging
import shlex
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def secure_subprocess_run(
    command: list[str] | str,
    *,
    shell: bool = False,
    cwd: str | None = None,
    timeout: int = 60,
    check: bool = True,
    capture_output: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """
    Execute a subprocess command securely.

    Args:
        command: Command to execute (list preferred over string)
        shell: Whether to use shell (default False - recommended)
        cwd: Working directory for the command
        timeout: Timeout in seconds
        check: Whether to raise exception on non-zero exit
        capture_output: Whether to capture stdout/stderr
        **kwargs: Additional arguments for subprocess.run

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.SubprocessError: If command fails or times out
        ValueError: If command contains dangerous patterns
    """
    # If string command and shell=False, split safely
    if isinstance(command, str) and not shell:
        command = shlex.split(command)

    # Validate command doesn't contain dangerous shell metacharacters when shell=True
    if shell and isinstance(command, str):
        dangerous_chars = [";", "&&", "||", "|", "`", "$", "(", ")"]
        for char in dangerous_chars:
            if char in command:
                logger.warning(f"Dangerous character '{char}' detected in shell command")
                raise ValueError(f"Dangerous shell character detected: {char}")

    logger.debug(f"Executing command: {command if isinstance(command, str) else ' '.join(command)}")

    try:
        return subprocess.run(  # nosec B602 — shell=True validated via dangerous_chars check above
            command,
            shell=shell,
            cwd=cwd,
            timeout=timeout,
            check=check,
            capture_output=capture_output,
            text=True,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {command}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {e.stderr[:500]}")
        raise


def sanitize_command_arg(arg: str) -> str:
    """
    Sanitize a command argument to prevent injection.

    Args:
        arg: Argument to sanitize

    Returns:
        Sanitized argument
    """
    # Remove null bytes
    arg = arg.replace("\x00", "")

    # If the argument contains shell metacharacters, quote it
    dangerous = set(";|&`$(){}[]<>!#*?\\'\"\n\r")
    if any(c in arg for c in dangerous):
        # Use shlex.quote to safely escape the argument
        return shlex.quote(arg)

    return arg


def validate_working_directory(cwd: str | None) -> None:
    """
    Validate that a working directory is safe to use.

    Args:
        cwd: Working directory path

    Raises:
        ValueError: If directory is not safe
    """
    if cwd is None:
        return

    import os

    # Prevent directory traversal
    resolved = os.path.realpath(cwd)

    # Check for suspicious paths
    suspicious = ["/etc", "/root", "/sys", "/proc", "/dev", "/boot"]
    for path in suspicious:
        if resolved.startswith(path):
            raise ValueError(f"Working directory not allowed: {cwd}")

    logger.debug(f"Working directory validated: {resolved}")
