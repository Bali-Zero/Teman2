from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "codex_config_health.py"


def load_module():
    spec = importlib.util.spec_from_file_location("codex_config_health", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def statuses(checks):
    return {check.name: check.status for check in checks}


def test_clean_profile_requires_quiet_plugins(tmp_path: Path) -> None:
    module = load_module()
    profile = tmp_path / "nuzantara-core.config.toml"
    profile.write_text(
        '\n'.join(
            [
                'model = "gpt-5.5"',
                'model_reasoning_effort = "xhigh"',
                'project_doc_max_bytes = 65536',
                '',
                '[features]',
                'plugins = false',
                'plugin_hooks = false',
                '',
            ]
        ),
        encoding="utf-8",
    )

    result = statuses(module.check_profile(profile, "nuzantara-core", require_quiet_plugins=True))

    assert result["profile:nuzantara-core:parse"] == "PASS"
    assert result["profile:nuzantara-core:model"] == "PASS"
    assert result["profile:nuzantara-core:reasoning"] == "PASS"
    assert result["profile:nuzantara-core:plugin_hooks"] == "PASS"
    assert result["profile:nuzantara-core:plugins"] == "PASS"


def test_noisy_profile_fails_clean_plugin_policy(tmp_path: Path) -> None:
    module = load_module()
    profile = tmp_path / "nuzantara-research.config.toml"
    profile.write_text(
        '\n'.join(
            [
                'model = "gpt-5.5"',
                'model_reasoning_effort = "xhigh"',
                'project_doc_max_bytes = 65536',
                '',
                '[features]',
                'plugins = true',
                'plugin_hooks = true',
                '',
            ]
        ),
        encoding="utf-8",
    )

    result = statuses(module.check_profile(profile, "nuzantara-research", require_quiet_plugins=True))

    assert result["profile:nuzantara-research:plugin_hooks"] == "FAIL"
    assert result["profile:nuzantara-research:plugins"] == "FAIL"


def test_hook_noise_is_reported(tmp_path: Path) -> None:
    module = load_module()
    hooks = tmp_path / "hooks.json"
    hooks.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [{"hooks": [{"command": "echo noisy"}]}],
                    "UserPromptSubmit": [],
                    "Stop": [{"hooks": [{"command": "echo blocked"}]}],
                }
            }
        ),
        encoding="utf-8",
    )

    result = statuses(module.check_hooks_file(hooks, "codex"))

    assert result["hooks:codex:SessionStart"] == "FAIL"
    assert result["hooks:codex:UserPromptSubmit"] == "PASS"
    assert result["hooks:codex:Stop"] == "FAIL"


def test_skill_frontmatter_accepts_block_scalar_description(tmp_path: Path) -> None:
    module = load_module()
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        """---
name: example
description: >-
  Use when a description needs colon: value text.
---

# Example
""",
        encoding="utf-8",
    )

    checks = module.check_skill_frontmatter(skill)

    assert statuses(checks)["skill:SKILL.md:frontmatter"] == "PASS"


def test_skill_frontmatter_rejects_unquoted_colon_description(tmp_path: Path) -> None:
    module = load_module()
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        """---
name: example
description: Use when this breaks: yaml scanners in Codex.
---

# Example
""",
        encoding="utf-8",
    )

    checks = module.check_skill_frontmatter(skill)

    assert statuses(checks)["skill:SKILL.md:frontmatter"] == "FAIL"


def test_agents_budget_warns_when_doc_exceeds_budget(tmp_path: Path) -> None:
    module = load_module()
    agents = tmp_path / "AGENTS.md"
    agents.write_text("x" * 12, encoding="utf-8")

    checks = module.check_agents_budget(agents, "repo", budget_bytes=10)

    assert statuses(checks)["agents:repo:budget"] == "WARN"


def test_optional_profile_missing_is_warning(tmp_path: Path) -> None:
    module = load_module()
    checks = module.check_profile(
        tmp_path / "missing.config.toml",
        "nuzantara-toolful",
        require_quiet_plugins=False,
        missing_status="WARN",
    )

    assert statuses(checks)["profile:nuzantara-toolful:parse"] == "WARN"
