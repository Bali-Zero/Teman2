"""
Path validation utilities for secure file system operations.

Prevents path traversal attacks by validating paths against allowed base directories.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default allowed base directories
DEFAULT_ALLOWED_BASES = [
    "/app/data",
    "/app/uploads",
    "/tmp",
    "data",
    "uploads",
    "temp",
    "/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/data",
    "/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/uploads",
]


def validate_path(
    path: str | Path,
    allowed_bases: list[str] | None = None,
    must_exist: bool = False,
    allow_relative: bool = True,
) -> Path:
    """
    Validate a path to prevent path traversal attacks.

    Args:
        path: The path to validate
        allowed_bases: List of allowed base directories (defaults to DEFAULT_ALLOWED_BASES)
        must_exist: Whether the path must exist
        allow_relative: Whether to allow relative paths

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is outside allowed bases or contains traversal patterns
        FileNotFoundError: If must_exist=True and path doesn't exist
    """
    if allowed_bases is None:
        allowed_bases = DEFAULT_ALLOWED_BASES

    path_obj = Path(path).resolve()

    # Check for path traversal patterns in the original path
    path_str = str(path)
    if ".." in path_str or path_str.startswith("/") and ".." in path_str:
        # Additional check: resolve and verify it's within allowed bases
        pass  # Will be checked below against allowed bases

    # Check against allowed base directories
    allowed = False
    for base in allowed_bases:
        base_path = Path(base).resolve()
        try:
            # Check if path is within allowed base
            path_obj.relative_to(base_path)
            allowed = True
            break
        except ValueError:
            continue

    if not allowed:
        # Also check if it's a relative path within current working directory
        if allow_relative and not path_obj.is_absolute():
            cwd = Path.cwd()
            resolved = (cwd / path_obj).resolve()
            try:
                resolved.relative_to(cwd)
                allowed = True
                path_obj = resolved
            except ValueError:
                pass  # path not relative to cwd — will be blocked below

    if not allowed:
        logger.warning(f"Path traversal attempt blocked: {path}")
        raise ValueError(f"Access denied: path '{path}' is outside allowed directories")

    # Check if path must exist
    if must_exist and not path_obj.exists():
        raise FileNotFoundError(f"Path does not exist: {path_obj}")

    return path_obj


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal in file names.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for use
    """
    # Remove path separators and null bytes
    sanitized = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")

    # Remove parent directory references
    while ".." in sanitized:
        sanitized = sanitized.replace("..", "_")

    # Strip leading/trailing whitespace and dots
    sanitized = sanitized.strip(" .")

    # Limit length
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        sanitized = name[: 255 - len(ext)] + ext

    # Empty or only dots/underscores -> fallback
    if not sanitized or all(c in "._ " for c in sanitized):
        return "unnamed_file"
    return sanitized
