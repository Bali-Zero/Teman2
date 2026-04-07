"""Constants for owner weekly cashout sync.

TAB_TO_WEEK is the source of truth for which sheet tabs map to which
weeks. New tabs must be added here manually (alert via Telegram on unknown
tabs during sync).
"""
from __future__ import annotations

from datetime import date

SHEET_ID: str = "1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE"

# Verified against sheet 2026-04-07
TAB_TO_WEEK: dict[str, date] = {
    "BZ 22 AUG":          date(2025, 8, 22),
    "BS 22 AUG":          date(2025, 8, 22),
    "BZ 29 AUG":          date(2025, 8, 29),
    "BS 29 AUG":          date(2025, 8, 29),
    "BZ 05 SEPT":         date(2025, 9, 5),
    "BS 05 SEPT":         date(2025, 9, 5),
    "BZ 12 SEPT":         date(2025, 9, 12),
    "BS 12 SEPT":         date(2025, 9, 12),
    "BZ 19 SEPT":         date(2025, 9, 19),
    "BS 19 SEPT":         date(2025, 9, 19),
    "BZ 26 SEPT":         date(2025, 9, 26),
    "BS 26 SEPT":         date(2025, 9, 26),
    "BZ 03 OCT":          date(2025, 10, 3),
    "BS 03 OCT":          date(2025, 10, 3),
    "BZ 10 OCT":          date(2025, 10, 10),
    "BS 10 OCT":          date(2025, 10, 10),
    "BZ 17 OCT":          date(2025, 10, 17),
    "BS 17 OCT":          date(2025, 10, 17),
    "BZ 24 OCT":          date(2025, 10, 24),
    "BS 24 OCT":          date(2025, 10, 24),
    "BZ 31 OCT":          date(2025, 10, 31),
    "BS 31 OCT":          date(2025, 10, 31),
    "BZ 07 NOV":          date(2025, 11, 7),
    "BS 07 NOV":          date(2025, 11, 7),
    "BZ 14 NOV":          date(2025, 11, 14),
    "BS 14 NOV":          date(2025, 11, 14),
    "BZ 21 NOV":          date(2025, 11, 21),
    "BS 21 NOV":          date(2025, 11, 21),
    "BZ 28 NOV":          date(2025, 11, 28),
    "BS 28 NOV":          date(2025, 11, 28),
    "BZ 05 DEC":          date(2025, 12, 5),
    "BS 05 DEC":          date(2025, 12, 5),
    "BZ 12 DEC":          date(2025, 12, 12),
    "BS 12 DEC":          date(2025, 12, 12),
    "BZ 19 DEC":          date(2025, 12, 19),
    "BS 19 DEC":          date(2025, 12, 19),
    "BZ 26 DES & 2 JAN":  date(2025, 12, 26),  # combo 2-week tab
    "BS 26 DES & 2 JAN":  date(2025, 12, 26),
    "BZ 09 JAN 26":       date(2026, 1, 9),
    "BS 09 JAN 26":       date(2026, 1, 9),
    "BZ 16-23 JAN 26":    date(2026, 1, 16),   # combo 2-week tab
    "BS 16-23 JAN 26":    date(2026, 1, 16),
    "BZ 30 JAN":          date(2026, 1, 30),
}

# Tabs that must be skipped (junk, duplicates, backups).
JUNK_TABS: frozenset[str] = frozenset({
    "Sheet18",
    "Copy of BZ 31 OCT",
    "BS 19 DEC 25 - 09 JAN 26",
})
