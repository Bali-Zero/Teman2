"""Helpers to read git state without touching the working tree.

Everything here is a thin wrapper over `git` subprocess calls scoped to a given
repo path. We never `git checkout`. We stream blobs with `git show SHA:path` and
list trees with `git ls-tree -r SHA -- path`. Binary detection uses a null-byte
sniff on the first 8 KiB of a blob, matching what git itself does.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


class GitError(RuntimeError):
    """Raised when a git command fails for a reason we can't paper over."""


def _run(args: list[str], cwd: str, check: bool = True) -> str:
    """Run a git command, return stdout as text (UTF-8, errors replaced)."""
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    if check and res.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed: {res.stderr.decode('utf-8', 'replace').strip()}"
        )
    return res.stdout.decode("utf-8", "replace")


def _run_bytes(args: list[str], cwd: str, check: bool = True) -> bytes:
    """Run a git command, return stdout as raw bytes."""
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    if check and res.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed: {res.stderr.decode('utf-8', 'replace').strip()}"
        )
    return res.stdout


def resolve_range(range_expr: str, repo: str, path_filter: str | None = None) -> list[str]:
    """Return the list of SHAs in the given range, oldest-first."""
    args = ["rev-list", "--reverse", range_expr]
    if path_filter:
        args += ["--", path_filter]
    out = _run(args, repo)
    return [line.strip() for line in out.splitlines() if line.strip()]


def commit_meta(sha: str, repo: str) -> dict:
    """Return subject, parent sha, and short sha for `sha`."""
    fmt = "%H%x1f%h%x1f%P%x1f%s"
    out = _run(["log", "-n1", f"--pretty=format:{fmt}", sha], repo).rstrip("\n")
    if not out:
        raise GitError(f"empty commit meta for {sha}")
    full, short, parents, subject = out.split("\x1f", 3)
    parent = parents.split(" ")[0] if parents.strip() else None
    return {
        "sha": full,
        "short_sha": short,
        "parent_sha": parent,
        "subject": subject,
    }


def changed_paths(sha: str, repo: str, path_filter: str | None = None) -> list[dict]:
    """Return [{path, status}] for files changed between `sha` and its parent.

    Status is the raw git letter (A/M/D/R/C/T), untouched.
    """
    args = ["show", "--name-status", "--pretty=format:", sha]
    if path_filter:
        args += ["--", path_filter]
    out = _run(args, repo)
    items: list[dict] = []
    for line in out.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        items.append({"path": path, "status": status[0]})
    return items


def show_blob(sha: str, path: str, repo: str) -> bytes | None:
    """Return the blob bytes for `path` at `sha`, or None if the path is absent."""
    res = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        return None
    return res.stdout


def is_binary(blob: bytes) -> bool:
    """True if `blob` looks binary (null byte in first 8 KiB)."""
    return b"\x00" in blob[:8192]


def ls_tree(sha: str, repo: str, path: str) -> list[dict]:
    """List regular files under `path` at `sha`.

    Returns [{path, blob_sha, size_bytes}]. Directories and symlinks are filtered.
    """
    # -r = recurse, -l = include size, format "mode type blob size\tpath"
    out = _run(["ls-tree", "-r", "-l", sha, "--", path], repo, check=False)
    items: list[dict] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # "100644 blob <sha> <size>\t<path>"
        head, _, fpath = line.partition("\t")
        parts = head.split()
        if len(parts) < 4:
            continue
        mode, typ, blob_sha, size = parts[0], parts[1], parts[2], parts[3]
        if typ != "blob":
            continue
        # Skip symlinks (mode 120000)
        if mode == "120000":
            continue
        try:
            size_int = int(size)
        except ValueError:
            size_int = 0
        items.append({"path": fpath, "blob_sha": blob_sha, "size_bytes": size_int})
    return items


@dataclass
class RepoView:
    """Convenience struct to bind repo path + range once."""

    repo: str
    range_expr: str

    def shas(self, path_filter: str | None = None) -> list[str]:
        return resolve_range(self.range_expr, self.repo, path_filter)
