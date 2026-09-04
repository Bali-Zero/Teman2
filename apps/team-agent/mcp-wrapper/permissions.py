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
# package, and this file already assumes the repo layout (see the sibling reader in
# apps/nuzantara-mcp/nuzantara_mcp/auth.py, which reaches across app trees for the very
# roles.yaml this class reads). There is deliberately NO fallback to yaml.safe_load: a
# permission checker that quietly downgrades to the permissive loader when the strict
# one is missing would be the whole defect with an extra step.
_YAML_STRICT = Path(__file__).resolve().parents[3] / "scripts" / "lib" / "yaml_strict.py"


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
    spec = importlib.util.spec_from_file_location(_YAML_STRICT_MODULE, _YAML_STRICT)
    if spec is None or spec.loader is None:  # pragma: no cover - unreachable if the file exists
        raise RuntimeError(f"strict policy loader not importable at {_YAML_STRICT}")
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
