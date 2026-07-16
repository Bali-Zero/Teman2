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

    result = statuses(
        module.check_profile(
            profile,
            "nuzantara-core",
            require_quiet_plugins=True,
            required_model="gpt-5.5",
            required_reasoning="xhigh",
        )
    )

    assert result["profile:nuzantara-core:parse"] == "PASS"
    assert result["profile:nuzantara-core:model"] == "PASS"
    assert result["profile:nuzantara-core:reasoning"] == "PASS"
    assert result["profile:nuzantara-core:plugin_hooks"] == "PASS"
    assert result["profile:nuzantara-core:plugins"] == "PASS"


def test_profile_requirements_are_per_profile_not_global(tmp_path: Path) -> None:
    """2026-07-16: model/reasoning requirements diverge by profile (core vs
    research) — the check must key off PROFILE_REQUIREMENTS per label, not a
    single global constant, and must FAIL a profile that doesn't match ITS
    OWN required model even if it would match another profile's."""
    module = load_module()
    profile = tmp_path / "nuzantara-core.config.toml"
    profile.write_text(
        '\n'.join(
            [
                'model = "gpt-5.6-sol"',
                'model_reasoning_effort = "high"',
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

    required_model, required_reasoning = module.PROFILE_REQUIREMENTS["nuzantara-core"]
    result = statuses(
        module.check_profile(
            profile,
            "nuzantara-core",
            require_quiet_plugins=True,
            required_model=required_model,
            required_reasoning=required_reasoning,
        )
    )
    assert result["profile:nuzantara-core:model"] == "PASS"
    assert result["profile:nuzantara-core:reasoning"] == "PASS"

    # Same file checked against research's requirement must FAIL — proves the
    # gate is per-profile, not a single shared constant.
    research_model, research_reasoning = module.PROFILE_REQUIREMENTS["nuzantara-research"]
    mismatched = statuses(
        module.check_profile(
            profile,
            "nuzantara-core",
            require_quiet_plugins=True,
            required_model=research_model,
            required_reasoning=research_reasoning,
        )
    )
    assert mismatched["profile:nuzantara-core:model"] == "FAIL" or mismatched["profile:nuzantara-core:reasoning"] == "FAIL"


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


def test_missing_requirement_on_mandatory_profile_fails_visibly(tmp_path: Path) -> None:
    """2026-07-16 red-team finding (Codex gpt-5.6-terra, MEDIUM): a typo'd or
    deleted PROFILE_REQUIREMENTS key for a MANDATORY profile (missing_status=
    "FAIL") must NOT silently default to (None, None) — that would skip the
    model/reasoning checks entirely, letting a drifted gpt-5.5 profile read
    green (scar-W82 class fail-open). GUILT: simulate the deleted/renamed key."""
    module = load_module()
    path = tmp_path / "nuzantara-core.config.toml"

    (requirement, checks) = module.resolve_profile_requirement(
        "nuzantara-core-TYPO", "FAIL", path
    )
    assert requirement == (None, None)
    result = statuses(checks)
    assert result["profile:nuzantara-core-TYPO:requirements_missing"] == "FAIL"


def test_missing_requirement_on_optional_profile_is_not_a_failure(tmp_path: Path) -> None:
    """INNOCENCE counterpart: an OPTIONAL profile (missing_status="WARN", e.g.
    nuzantara-toolful — not armed yet) legitimately has no PROFILE_REQUIREMENTS
    entry. That must NOT trip the new fail-visible gate — only mandatory
    profiles are held to having a requirement."""
    module = load_module()
    path = tmp_path / "nuzantara-toolful.config.toml"

    (requirement, checks) = module.resolve_profile_requirement(
        "nuzantara-toolful", "WARN", path
    )
    assert requirement == (None, None)
    assert checks == []


def test_real_profiles_keep_their_requirements_after_the_fail_visible_fix(tmp_path: Path) -> None:
    """INNOCENCE: the real, present PROFILE_REQUIREMENTS entries for
    nuzantara-core/nuzantara-research must be returned unchanged (no spurious
    requirements_missing check) after the fail-visible fix."""
    module = load_module()
    for label in ("nuzantara-core", "nuzantara-research"):
        expected = module.PROFILE_REQUIREMENTS[label]
        (requirement, checks) = module.resolve_profile_requirement(
            label, "FAIL", tmp_path / f"{label}.config.toml"
        )
        assert requirement == expected
        assert checks == []
