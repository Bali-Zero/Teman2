"""
CRM Access Control Dependencies.

RBAC filter functions for CRM routers. Admin/full-view users see everything;
team members see only their assigned clients/practices.
"""

from backend.app.utils.crm_utils import (
    can_view_all_clients as _can_view_all_clients,
    can_view_all_practices,
)


def can_view_all_clients(user: dict) -> bool:
    """Check if user can see ALL clients (admin, board, full-view list)."""
    return _can_view_all_clients(user)


def get_crm_user_filter(current_user: dict) -> str | None:
    """
    Return the assigned_to filter for CRM client queries.

    Returns None for admins (no filter = see all), or the user's email
    for team members (filter to assigned_to = email).
    """
    if can_view_all_clients(current_user):
        return None
    return (current_user.get("email") or "").lower().strip() or None


def get_practices_user_filter(current_user: dict) -> str | None:
    """
    Return the assigned_to filter for CRM practice queries.

    Returns None for full-view users (no filter), or the user's email
    for team members.
    """
    if can_view_all_practices(current_user):
        return None
    return (current_user.get("email") or "").lower().strip() or None
