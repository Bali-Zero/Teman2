"""Role-based permission checker for MCP tool access."""

import fnmatch
import importlib.util
import sys
from pathlib import Path
from typing import Any

# roles.yaml decides which tools a role may call, so it is a POLICY document and is
# loaded strictly: PyYAML's safe_load lets a duplicate top-level key win in silence,
# and `roles:` is a mapping keyed by role name. Measured 2026-09-05 on a scratch copy
# of the shipped file: appending five lines that repeat `tax_consultant:` with
# `tools: ["*"]` took get_allowed_tools("tax_consultant") from 11 named tools to
# ["*"], and is_allowed("tax_consultant", <anything>) from False to True. That is
# privilege escalation whose diff reads as an appended block, which is why the defect
# is in REVIEW rather than in the file's permissions.
#
# The loader is loaded by PATH rather than imported: scripts/lib is not an importable
# package. There is deliberately NO fallback to yaml.safe_load — a permission checker
# that quietly downgrades to the permissive loader when the strict one is missing would
# be the whole defect with an extra step.
#
# TWO CANDIDATE LOCATIONS, because this file is deployed by COPY and not by package.
# apps/team-agent/onboarding/mac-bootstrap.sh:90-93 does
# `cp -r .../mcp-wrapper/* $HOME/.nuzantara/mcp-wrapper/`, which ships this subtree and
# NOT the repo's top-level scripts/. Measured 2026-09-05 by reproducing that layout: a
# repo-relative-only lookup raised FileNotFoundError, and because server.py:45 builds
# the checker at MODULE IMPORT, the wrapper would not start at all on a team member's
# Mac. "Fail closed" is the right posture for an ambiguous policy file; it is the wrong
# posture for a loader that is merely somewhere else, because it converts a possible
# review-defeating edit into a certain outage. So: the repo path when running from the
# checkout, and a copy staged beside this file when running from the onboarded tree —
# one source of truth in the repo, deliberately shipped, never a second edited copy.
_YAML_STRICT_CANDIDATES = (
    Path(__file__).resolve().parents[3] / "scripts" / "lib" / "yaml_strict.py",
    Path(__file__).resolve().parent / "lib" / "yaml_strict.py",
)


_YAML_STRICT_MODULE = "nuzantara_yaml_strict"


def _load_yaml_strict():
    """Load the shared strict loader by path, once, under a canonical module name.

    The module is registered under ONE canonical name shared by every path-loader of it
    (apps/team-agent/mcp-wrapper/permissions.py, apps/nuzantara-mcp/nuzantara_mcp/auth.py,
    and the test battery). Loading the same file twice under two names produces two
    distinct StrictYAMLError CLASSES, so `except StrictYAMLError` in one caller does not
    catch the error raised through the other — measured while writing this battery.
    """
    cached = sys.modules.get(_YAML_STRICT_MODULE)
    if cached is not None:
        return cached
    for candidate in _YAML_STRICT_CANDIDATES:
        if candidate.is_file():
            break
    else:
        raise RuntimeError(
            "strict policy loader not found — looked in "
            + ", ".join(str(c) for c in _YAML_STRICT_CANDIDATES)
            + ". This wrapper will not start without it, by design: falling back to "
            "yaml.safe_load would silently restore the duplicate-key escalation."
        )
    spec = importlib.util.spec_from_file_location(_YAML_STRICT_MODULE, candidate)
    if spec is None or spec.loader is None:  # pragma: no cover - unreachable if the file exists
        raise RuntimeError(f"strict policy loader not importable at {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_YAML_STRICT_MODULE] = module
    spec.loader.exec_module(module)
    return module


class PermissionChecker:
    def __init__(self, config_path: str = "config/roles.yaml"):
        yaml_strict = _load_yaml_strict()
        data: dict[str, Any] = yaml_strict.load_policy(config_path)
        roles = data.get("roles")
        if not isinstance(roles, dict) or not roles:
            # An empty `roles:` grants nothing, so it is not an escalation — but it is
            # a disarmed control that looks like a working one, and every caller then
            # gets a uniform False that is indistinguishable from a correct denial.
            raise yaml_strict.StrictYAMLError(
                f"{config_path}: `roles:` is missing or empty — a permission checker "
                f"with no roles denies everything and cannot be told apart from one "
                f"that is working."
            )
        self.roles: dict[str, list[str]] = {
            role: info.get("tools", [])
            for role, info in roles.items()
            if isinstance(info, dict)
        }

    def is_allowed(self, role: str, tool_name: str) -> bool:
        if not role or not tool_name:
            return False
        allowed = self.roles.get(role, [])
        if not allowed:
            return False
        for pattern in allowed:
            if pattern == "*" or fnmatch.fnmatch(tool_name, pattern):
                return True
        return False

    def get_allowed_tools(self, role: str) -> list[str]:
        return self.roles.get(role, [])
