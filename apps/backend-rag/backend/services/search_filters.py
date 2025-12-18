"""
Search filter utilities for tier-based access control and repealed law exclusion.

Extracted from SearchService to improve modularity and testability.
"""

from typing import Any


def build_search_filter(
    tier_filter: dict[str, Any] | None = None, exclude_repealed: bool = True
) -> dict[str, Any] | None:
    """Build combined search filter with tier access and repealed law exclusion.

    Constructs Qdrant/ChromaDB filter combining tier-based access control
    and automatic exclusion of repealed laws (status_vigensi: "dicabut").

    Filter Logic:
    1. Tier filter: Restricts results to allowed tiers (S/A/B/C/D)
    2. Repealed exclusion: Filters out laws with status_vigensi="dicabut"
    3. Conflict handling: Ensures exclusion takes precedence over inclusion

    Args:
        tier_filter: Optional tier constraint, format:
                     {"tier": {"$in": ["S", "A"]}} for inclusion
        exclude_repealed: If True, exclude status_vigensi="dicabut" (default: True)

    Returns:
        Combined filter dict or None if no filters apply

    Note:
        - Empty result: Returns None (no filter) if no constraints
        - Repealed laws: Indonesian legal term "dicabut" = repealed/revoked
        - Default behavior: Always excludes repealed unless explicitly disabled

    Example:
        >>> filter = build_search_filter(
        ...     tier_filter={"tier": {"$in": ["S", "A"]}},
        ...     exclude_repealed=True
        ... )
        >>> print(filter)
        {'tier': {'$in': ['S', 'A']}, 'status_vigensi': {'$ne': 'dicabut'}}
    """
    filters = {}

    # Add tier filter if provided
    if tier_filter:
        filters.update(tier_filter)

    # Default: Exclude repealed laws (status_vigensi: "dicabut")
    if exclude_repealed:
        if "status_vigensi" in filters:
            # If status_vigensi filter exists, ensure it doesn't include "dicabut"
            existing_filter = filters["status_vigensi"]
            if isinstance(existing_filter, dict) and "$in" in existing_filter:
                # Remove "dicabut" from allowed values
                allowed_values = [v for v in existing_filter["$in"] if v != "dicabut"]
                if allowed_values:
                    filters["status_vigensi"] = {"$in": allowed_values}
                else:
                    # All values were "dicabut", so exclude everything
                    filters["status_vigensi"] = {"$ne": "dicabut"}
            elif isinstance(existing_filter, str):
                if existing_filter == "dicabut":
                    # If explicitly filtering for "dicabut", remove the filter (exclude it)
                    filters.pop("status_vigensi")
                else:
                    # If it's a valid status string (e.g., "berlaku"), convert to $in format
                    # for consistency and to ensure exclusion can be applied
                    # Convert to dict format so exclusion logic can be handled uniformly
                    filters["status_vigensi"] = {"$in": [existing_filter]}
                    # Now remove "dicabut" from the list (if present) to ensure exclusion
                    # This ensures consistent behavior: all valid status filters exclude "dicabut"
                    allowed_values = [v for v in filters["status_vigensi"]["$in"] if v != "dicabut"]
                    if allowed_values:
                        filters["status_vigensi"] = {"$in": allowed_values}
                    else:
                        # Shouldn't happen since we just added the valid status, but handle it
                        filters["status_vigensi"] = {"$ne": "dicabut"}
        else:
            # No existing status_vigensi filter, add exclusion
            filters["status_vigensi"] = {"$ne": "dicabut"}

    return filters if filters else None

