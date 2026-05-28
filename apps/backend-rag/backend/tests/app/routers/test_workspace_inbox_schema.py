"""Schema regression guard for workspace_inbox.

Prior bug (2026-05-26): SQL used `cl.name` but `clients` table has
`full_name` (no `name` column). Produced `column cl.name does not exist`
silent 500 on /api/workspace/inbox, blocking redirect post-login for ALL
team users. Bug survived 39 days (2026-04-17 → 2026-05-26) because no
test exercised the real SQL string against the live schema.

This test inspects the router source as text and asserts only valid column
references against `clients` table — no DB needed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROUTER_PATH = (
    Path(__file__).resolve().parents[3]
    / "app"
    / "routers"
    / "workspace_inbox.py"
)

VALID_CLIENTS_COLUMNS = {
    "id",
    "uuid",
    "full_name",
    "email",
    "phone",
    "whatsapp",
    "nationality",
    "passport_number",
    "assigned_to",
    "status",
    "tags",
    "metadata",
    "created_at",
    "updated_at",
    "deleted_at",
    "client_type",
    "first_contact_date",
    "last_interaction_date",
    "address",
    "notes",
    "custom_fields",
    "avatar_url",
    "google_drive_folder_id",
    "date_of_birth",
    "passport_expiry",
    "company_name",
    "lead_source",
    "service_interest",
    "gender",
    "birthplace",
    "phone_normalized",
    "tax_id",
    "npwp",
    "nib",
    "current_visa_type",
    "current_visa_sponsor",
    "visa_expiry_date",
    "kitas_expiry_date",
    "ai_summary",
    "drive_folder_id",
    "drive_folder_url",
    "strategic_recap",
}


def test_workspace_inbox_uses_only_valid_clients_columns() -> None:
    """Every cl.<col> reference must match an actual clients column."""
    source = ROUTER_PATH.read_text()

    # Find every `cl.<identifier>` reference in the file (the JOINed clients alias)
    references = set(re.findall(r"\bcl\.([a-z_][a-z0-9_]*)", source))

    invalid = references - VALID_CLIENTS_COLUMNS
    assert not invalid, (
        f"workspace_inbox.py references invalid clients columns: {invalid}. "
        f"Valid set (excerpt): full_name, email, id, assigned_to. "
        f"This is the 2026-05-26 cl.name → cl.full_name class of bug."
    )


def test_workspace_inbox_does_not_reference_dropped_name_column() -> None:
    """Explicit regression guard for the 2026-05-26 bug."""
    source = ROUTER_PATH.read_text()
    assert "cl.name" not in source, (
        "workspace_inbox.py uses `cl.name` but clients table has `full_name`, "
        "not `name`. This was the 2026-04-17 → 2026-05-26 silent 500 bug."
    )


def test_workspace_inbox_selects_client_name_alias() -> None:
    """The client_name alias must be present in the SELECT (frontend uses it)."""
    source = ROUTER_PATH.read_text()
    assert "AS client_name" in source, (
        "workspace_inbox.py must SELECT client_name alias — frontend AiSummaryCard "
        "consumes this field. Removing it breaks the inbox UI silently."
    )
