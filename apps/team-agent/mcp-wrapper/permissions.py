"""Role-based permission checker for MCP tool access."""

import fnmatch
from typing import Any

import yaml


class PermissionChecker:
    def __init__(self, config_path: str = "config/roles.yaml"):
        with open(config_path) as f:
            data: dict[str, Any] = yaml.safe_load(f)
        self.roles: dict[str, list[str]] = {
            role: info.get("tools", [])
            for role, info in data.get("roles", {}).items()
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
