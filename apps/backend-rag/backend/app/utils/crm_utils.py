"""
CRM Utilities - RBAC and Shared Business Logic
"""

import json
import logging
import re

from backend.app.core.config import settings

# CRM-specific admin additions on top of the global allowlist
# (`settings.admin_emails_set`). The global set covers zero/asya/antonellosiano;
# these are CRM-domain roles that are NOT global admins. HIGH-7 (audit 2026-04-18).
CRM_EXTRA_ADMIN_EMAILS: frozenset[str] = frozenset(
    {
        "admin@balizero.com",
        "admin@zantara.io",
        "damar@balizero.com",
    },
)

# Practices accounting role — sees full practice history for audit/reconciliation.
# Separate from admin because accounting users are not admins for everything else.
PRACTICES_EXTRA_VIEW_EMAILS: frozenset[str] = frozenset({"ruslana@balizero.com"})


def _crm_admin_emails() -> frozenset[str]:
    """Effective CRM admin allowlist — union of global admins and CRM extras."""
    return settings.admin_emails_set | CRM_EXTRA_ADMIN_EMAILS


def _practices_full_view_emails() -> frozenset[str]:
    """Effective practices-full-view allowlist — global admins + accounting."""
    return settings.admin_emails_set | PRACTICES_EXTRA_VIEW_EMAILS


# Backwards-compatibility aliases — some call sites still expect the old names.
# These are intentionally thin wrappers: point future code at the helpers above
# so that a config change propagates without redefining the set.
def _crm_admin_emails_compat() -> frozenset[str]:
    return _crm_admin_emails()


logger = logging.getLogger(__name__)


def is_crm_admin(user: dict) -> bool:
    """Check if user is a CRM admin (email in admin list or admin-level role)."""
    if not user:
        return False
    email = (user.get("email") or "").lower().strip()
    if email in _crm_admin_emails():
        return True
    if email in _practices_full_view_emails():
        return True
    role = (user.get("role") or "").lower().strip()
    return role in ("admin", "board member", "ceo", "founder")


def can_view_all_practices(user: dict) -> bool:
    """
    Check if a user can see ALL practices (admin, super admin, accounting).

    Users not in the practices-full-view allowlist and not role=admin see only
    practices where the client is assigned to them.
    """
    if not user:
        return False

    email = (user.get("email") or "").lower()
    role = (user.get("role") or "").lower()

    # Explicit full-view list (admin + accounting)
    if email in _practices_full_view_emails():
        return True

    # Role-based: admin and board/management roles see everything
    return role in ("admin", "board member", "ceo", "founder")


def can_view_all_clients(user: dict) -> bool:
    """All authenticated team members can see the full client list.

    Client visibility is separated from ownership (assigned_to).
    Everyone sees all clients; assigned_to determines responsibility,
    notifications, and write permissions — not read access.
    """
    if not user:
        return False
    return True


def is_super_admin(user: dict) -> bool:
    """
    Check if a user is a super admin (e.g. Zero, Antonello).

    Super admin is the global admin set (`settings.admin_emails_set`) minus
    the CRM-specific additions. We accept the global set as the super-admin
    boundary — if a user is a global admin they can always impersonate.
    """
    if not user:
        return False

    email = (user.get("email") or "").lower()
    return email in settings.admin_emails_set


async def verify_client_access(
    client_id: int,
    current_user: dict,
    conn,
    allow_assigned: bool = True,
) -> tuple[bool, str | None]:
    """
    Verify if a user has access to a specific client.

    Args:
        client_id: The client ID to check
        current_user: User dictionary from authentication
        conn: Database connection
        allow_assigned: If True, all authenticated users can access the client
                        (consistent with can_view_all_clients policy).
                        If False, only admins can access.

    Returns:
        tuple: (has_access, assigned_to_email or None)

    Raises:
        HTTPException: 403 if access denied, 404 if client not found
    """
    from fastapi import HTTPException

    user_email = current_user.get("email", "").lower()

    # Admins always have access
    if is_crm_admin(current_user):
        # Still fetch assigned_to for audit purposes
        row = await conn.fetchrow(
            "SELECT assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")
        return True, row["assigned_to"]

    # Non-admins: fetch client and check access
    row = await conn.fetchrow(
        "SELECT id, assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Client not found")

    assigned_to = row["assigned_to"]

    # All authenticated team members can view any client (consistent with
    # can_view_all_clients policy). Unassigned clients must be accessible
    # so team members can self-assign.
    if allow_assigned:
        return True, assigned_to

    # Access denied (only reachable if allow_assigned=False)
    logger.warning(
        f"RBAC: User {user_email} denied access to client {client_id} (assigned_to: {assigned_to})",
    )
    raise HTTPException(
        status_code=403,
        detail="You don't have permission to access this client.",
    )


def extract_json_from_llm_response(text: str) -> dict | None:
    """
    Extract JSON from LLM response, handling code fences and chain-of-thought reasoning.

    Gemini sometimes returns responses like:
    - ```json\n{...}\n```
    - "Let me think... wait, need to count carefully. {json here}"
    - Just raw JSON

    This function handles all these cases by:
    1. First trying to find JSON in markdown code fence
    2. Then using brace balancing to find valid JSON objects

    Args:
        text: Raw LLM response text

    Returns:
        Parsed JSON dict or None if no valid JSON found
    """
    if not text:
        return None

    # Method 1: Try to find JSON in code fence first (most common)
    code_fence_match = re.search(r"```json?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if code_fence_match:
        try:
            return json.loads(code_fence_match.group(1).strip())
        except json.JSONDecodeError as exc:
            logger.debug(
                "crm_utils.extract_json.fence_parse_failed",
                extra={"reason": str(exc)[:80]},
            )
            # Fall through to truncated-fence and then brace balancing

    # Method 1b: Handle truncated code fence (no closing ```)
    # This happens when Gemini's response is cut off
    truncated_fence_match = re.search(r"```json?\s*([\s\S]+)", text, re.IGNORECASE)
    if truncated_fence_match:
        content = truncated_fence_match.group(1).strip()
        # Remove trailing ``` if partially present
        content = re.sub(r"`+$", "", content)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.debug(
                "crm_utils.extract_json.truncated_fence_parse_failed",
                extra={"reason": str(exc)[:80]},
            )
            # Fall through to brace balancing

    # Method 2: Find JSON by matching balanced braces
    # This handles chain-of-thought text before/after the JSON
    start_idx = text.find("{")
    while start_idx != -1:
        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start_idx:], start_idx):
            if escape_next:
                escape_next = False
                continue

            if char == "\\" and in_string:
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    # Found a complete JSON object
                    try:
                        candidate = text[start_idx : i + 1]
                        return json.loads(candidate)
                    except json.JSONDecodeError as exc:
                        logger.debug(
                            "crm_utils.extract_json.brace_candidate_invalid",
                            extra={"start": start_idx, "reason": str(exc)[:80]},
                        )
                        # Not valid JSON, try next { in text
                        break

        # Move to next { occurrence
        start_idx = text.find("{", start_idx + 1)

    return None
