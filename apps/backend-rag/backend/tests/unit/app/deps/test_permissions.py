"""Tests for permission-based auth dependencies — S03 Sprint 3."""

import pytest
from unittest.mock import MagicMock


class TestCheckPermission:

    def test_wildcard_grants_all(self):
        from backend.app.deps.permissions import check_permission
        assert check_permission({"permissions": ["*"], "role": "user"}, "crm:write") is True

    def test_exact_match(self):
        from backend.app.deps.permissions import check_permission
        assert check_permission({"permissions": ["crm:read", "crm:write"], "role": "user"}, "crm:write") is True

    def test_missing_denied(self):
        from backend.app.deps.permissions import check_permission
        assert check_permission({"permissions": ["crm:read"], "role": "user"}, "crm:write") is False

    def test_admin_grants_all(self):
        from backend.app.deps.permissions import check_permission
        assert check_permission({"permissions": [], "role": "admin"}, "anything") is True

    def test_empty_denied(self):
        from backend.app.deps.permissions import check_permission
        assert check_permission({"permissions": [], "role": "user"}, "crm:read") is False

    def test_no_permissions_key_denied(self):
        from backend.app.deps.permissions import check_permission
        assert check_permission({"role": "user"}, "crm:read") is False
