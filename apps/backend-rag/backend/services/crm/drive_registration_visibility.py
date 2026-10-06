"""Default client visibility for a Google Drive file registered with no human decision.

Notes-type text files (WhatsApp exports, scratch notes) are staff working material;
everything else keeps the column default (visible). One predicate, shared by every
Drive-registration writer so the rule cannot drift per site.
"""

NOTES_EXTENSIONS = (".txt", ".md")


def drive_default_client_visible(file_name: str | None) -> bool:
    """False for a notes-type text file (.txt/.md, any case); True for anything else."""
    name = (file_name or "").strip().lower()
    return not name.endswith(NOTES_EXTENSIONS)
