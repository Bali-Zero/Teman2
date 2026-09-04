"""The cover visual director must find the `claude` CLI under launchd's PATH.

Measured on Pro 2026-09-04: the post-publish poller runs with
PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin while `claude` lives in
~/.local/bin, so every cover prompt logged "claude CLI: not found in PATH" and
fell back to the canned visual (388 times). The child PATH must include the
user-local bin, and the binary must be resolved against THAT path.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module() -> ModuleType:
    path = REPO_ROOT / "apps/bali-intel-scraper/scripts/bz_image_style.py"
    spec = importlib.util.spec_from_file_location("cli_path_bz_image_style", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cli_path_bz_image_style"] = module
    spec.loader.exec_module(module)
    return module


def test_cli_search_path_prepends_user_local_bin_and_keeps_the_current_path(
    monkeypatch: Any, tmp_path: Path
) -> None:
    module = _load_module()
    monkeypatch.setenv("HOME", str(tmp_path))

    path = module._cli_search_path("/usr/bin:/bin")

    assert path.startswith(f"/opt/homebrew/bin:{tmp_path}/.local/bin:")
    assert path.endswith(":/usr/bin:/bin")
    # No current PATH at all (launchd minimal env): still a usable search path.
    assert module._cli_search_path("") == module._CLI_STANDARD_PATH.format(home=tmp_path)


def test_prompt_via_claude_resolves_the_binary_from_the_child_path(
    monkeypatch: Any, tmp_path: Path
) -> None:
    module = _load_module()
    fake_bin = tmp_path / ".local" / "bin"
    fake_bin.mkdir(parents=True)
    fake_claude = fake_bin / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IXUSR)

    # The parent's PATH is launchd's: it cannot see ~/.local/bin.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    for slot in range(1, 7):
        monkeypatch.delenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", raising=False)
    module._IMG_EXHAUSTED_TOKENS.clear()

    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], *, timeout: float, env: dict[str, str]) -> Any:
        seen["argv0"] = argv[0]
        seen["path"] = env["PATH"]
        return SimpleNamespace(
            returncode=0, stdout="A grounded visual concept with enough detail.", stderr=""
        )

    monkeypatch.setattr(module, "_run_process_group", fake_run)

    output = module._prompt_via_claude("Title", "tax", "Summary", "crisis")

    assert output == "A grounded visual concept with enough detail."
    assert seen["argv0"] == str(fake_claude)
    assert seen["path"].split(os.pathsep)[1] == str(fake_bin)
