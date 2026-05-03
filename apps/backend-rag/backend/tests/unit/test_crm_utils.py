import pytest
from backend.app.utils.crm_utils import is_crm_admin, can_view_all_clients

class TestIsCrmAdmin:
    def test_admin_email_is_admin(self):
        user = {"email": "zero@balizero.com", "role": "admin"}
        assert is_crm_admin(user) is True

    def test_team_member_is_not_admin(self):
        user = {"email": "surya@balizero.com", "role": "user"}
        assert is_crm_admin(user) is False

    def test_client_is_not_admin(self):
        user = {"email": "client@example.com", "role": "client"}
        assert is_crm_admin(user) is False

    def test_asya_is_admin(self):
        user = {"email": "asya@balizero.com", "role": "user"}
        assert is_crm_admin(user) is True

    def test_founder_role_is_admin(self):
        user = {"email": "someone@balizero.com", "role": "founder"}
        assert is_crm_admin(user) is True

    def test_none_user_is_not_admin(self):
        assert is_crm_admin(None) is False

class TestCanViewAllClients:
    def test_admin_can_view_all(self):
        user = {"email": "zero@balizero.com", "role": "admin"}
        assert can_view_all_clients(user) is True

    def test_asya_can_view_all(self):
        user = {"email": "asya@balizero.com", "role": "user"}
        assert can_view_all_clients(user) is True

    def test_team_member_can_view_all(self):
        user = {"email": "surya@balizero.com", "role": "user"}
        assert can_view_all_clients(user) is True

    def test_founder_role_can_view_all(self):
        user = {"email": "someone@balizero.com", "role": "founder"}
        assert can_view_all_clients(user) is True

    def test_none_user_cannot_view_all(self):
        assert can_view_all_clients(None) is False
