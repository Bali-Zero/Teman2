"""Guilt + innocence for scripts/hooks/check_protected_files.sh.

Owner ruling 2026-10-12: zantara_core.py (and only it) may be committed when
ZANTARA_CORE_EDIT carries a real reason; fly.toml and alembic/env.py keep no
override. Expectations here are written from the ruling, not read off the hook.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "check_protected_files.sh"
CORE = "apps/backend-rag/backend/zantara_core.py"


def _repo(tmp_path: Path, staged: list[str]) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel in staged:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x = 1\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", rel], check=True)
    return tmp_path


def _run(repo: Path, reason: str | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "ZANTARA_CORE_EDIT"}
    if reason is not None:
        env["ZANTARA_CORE_EDIT"] = reason
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, env=env, capture_output=True, text=True
    )


def test_unprotected_change_passes(tmp_path: Path) -> None:
    assert _run(_repo(tmp_path, ["apps/x.py"]), None).returncode == 0


def test_core_edit_without_reason_is_blocked(tmp_path: Path) -> None:
    assert _run(_repo(tmp_path, [CORE]), None).returncode == 1


@pytest.mark.parametrize("reason", ["", "   ", "short", "<reason>", "<motivo reale lungo>"])
def test_core_edit_with_hollow_reason_is_blocked(tmp_path: Path, reason: str) -> None:
    assert _run(_repo(tmp_path, [CORE]), reason).returncode == 1


def test_core_edit_with_real_reason_passes_and_is_audited(tmp_path: Path) -> None:
    res = _run(_repo(tmp_path, [CORE]), "PT PMA price 20M to 25M, owner ruling 2026-10-12")
    assert res.returncode == 0
    assert "owner ruling 2026-10-12" in res.stdout


@pytest.mark.parametrize("other", ["fly.toml", "apps/svc/fly.toml", "db/alembic/env.py"])
def test_reason_never_unlocks_other_protected_files(tmp_path: Path, other: str) -> None:
    reason = "a perfectly real and long reason"
    assert _run(_repo(tmp_path, [other]), reason).returncode == 1
    assert _run(_repo(tmp_path / "mixed", [CORE, other]), reason).returncode == 1
