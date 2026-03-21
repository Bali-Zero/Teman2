"""
CRM Utilities - RBAC and Shared Business Logic
"""

import json
import logging
import re

# Hardcoded admin emails for CRM access
# TODO: Move to database or environment variables in the future
CRM_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    "admin@balizero.com",
    "admin@zantara.io",
    "damar@balizero.com",
}

# Super admins (by username prefix/email)
SUPER_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    "antonellosiano@gmail.com",
}

# Users who can see ALL practices (admins + accounting)
# Everyone else sees only practices assigned to them
PRACTICES_FULL_VIEW_EMAILS: set[str] = {
    "zero@balizero.com",
    "antonellosiano@gmail.com",
    "asya@balizero.com",
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

    # All team members have full CRM access (only portal "client" users are excluded)
    result = role != "client"

    if result:
        logger.debug(f"RBAC: User {email} granted CRM access (role={role})")

    return result


def can_view_all_practices(user: dict) -> bool:
    """
    Check if a user can see ALL practices (admin, super admin, accounting).

    Users not in PRACTICES_FULL_VIEW_EMAILS and not role=admin see only
    practices where the client is assigned to them.
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    role = user.get("role", "").lower()

    # Explicit full-view list (admin + accounting)
    if email in PRACTICES_FULL_VIEW_EMAILS:
        return True

    # Role-based: admin role always sees everything
    if role == "admin":
        return True

    return False


def is_super_admin(user: dict) -> bool:
    """
    Check if a user is a super admin (e.g. Zero).
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    return email in SUPER_ADMIN_EMAILS


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
        allow_assigned: If True, allows access to assigned team members (not just admins)

    Returns:
        tuple: (has_access, assigned_to_email or None)
               has_access is True if user is admin OR (allow_assigned AND is the assigned user)

    Raises:
        HTTPException: 403 if access denied, 404 if client not found
    """
    from fastapi import HTTPException

    user_email = current_user.get("email", "").lower()

    # Admins always have access
    if is_crm_admin(current_user):
        # Still fetch assigned_to for audit purposes
        row = await conn.fetchrow(
            "SELECT assigned_to FROM clients WHERE id = $1",
            client_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")
        return True, row["assigned_to"]

    # Non-admins: fetch client and check assignment
    row = await conn.fetchrow(
        "SELECT id, assigned_to FROM clients WHERE id = $1",
        client_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Client not found")

    assigned_to = row["assigned_to"]

    # If allowing assigned access, check if user is the assigned team member
    if allow_assigned and assigned_to and assigned_to.lower() == user_email:
        return True, assigned_to

    # Access denied
    logger.warning(
        f"RBAC: User {user_email} denied access to client {client_id} (assigned_to: {assigned_to})"
    )
    raise HTTPException(
        status_code=403,
        detail="You don't have permission to access this client. Only admins or the assigned team member can access it.",
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
        except json.JSONDecodeError:
            pass  # Fall through to brace balancing

    # Method 1b: Handle truncated code fence (no closing ```)
    # This happens when Gemini's response is cut off
    truncated_fence_match = re.search(r"```json?\s*([\s\S]+)", text, re.IGNORECASE)
    if truncated_fence_match:
        content = truncated_fence_match.group(1).strip()
        # Remove trailing ``` if partially present
        content = re.sub(r"`+$", "", content)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass  # Fall through to brace balancing

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
                    except json.JSONDecodeError:
                        # Not valid JSON, try next { in text
                        break

        # Move to next { occurrence
        start_idx = text.find("{", start_idx + 1)

    return None
