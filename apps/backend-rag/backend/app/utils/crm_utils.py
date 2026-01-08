"""
CRM Utilities - RBAC and Shared Business Logic
"""

import logging

# Hardcoded admin emails for CRM access
# TODO: Move to database or environment variables in the future
CRM_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    "admin@balizero.com",
    "admin@zantara.io",
}

# Super admins (by username prefix/email)
SUPER_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    "antonellosiano@gmail.com",
}

logger = logging.getLogger(__name__)


def is_crm_admin(user: dict) -> bool:
    """
    Check if a user has administrative access to the CRM.

    Admins can see all clients, all practices, and perform bulk actions.

    Args:
        user: User dictionary from authentication (get_current_user)

    Returns:
        bool: True if user is admin
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    role = user.get("role", "").lower()

    # Check by email or role
    result = email in CRM_ADMIN_EMAILS or role == "admin"

    if result:
        logger.debug(f"RBAC: User {email} granted CRM admin access (role={role})")

    return result


def is_super_admin(user: dict) -> bool:
    """
    Check if a user is a super admin (e.g. Zero).
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    return email in SUPER_ADMIN_EMAILS
