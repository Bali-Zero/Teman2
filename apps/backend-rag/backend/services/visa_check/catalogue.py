"""Visa catalogue — the finite set of visa types our app knows about.

Kept as a module-level constant so pydantic enums, the decision tree,
the Clock form, and the PricingTool bridge all agree.
"""

from __future__ import annotations

from enum import Enum


class VisaType(str, Enum):
    # Single-entry & tourism
    B211A = "B211A"            # Tourism single entry (extendable to 180d)
    C1 = "C1"                  # Tourism (60d, 2 extensions × 60d)
    C2 = "C2"                  # Business visit
    C7 = "C7"                  # Job training
    C7A = "C7A"                # Music/art (single)
    C7B = "C7B"                # Sport
    # Digital nomad
    E33G = "E33G"              # Digital nomad (Remote Worker KITAS)
    # Investor / company
    E28A = "E28A"              # Investor 2yr KITAS
    E23 = "E23"                # Work KITAS (employer-sponsored)
    # Family / long-term
    E33F = "E33F"              # Retirement KITAS (55+)
    E31 = "E31"                # Family KITAS (spouse/dependent)
    E30A = "E30A"              # Student KITAS


# Visa types whose Clock timeline assumes a specific duration. These
# drive the D-60/30/14/7/1 checkpoint math on the result page.
DEFAULT_DURATION_DAYS: dict[VisaType, int] = {
    VisaType.B211A: 60,
    VisaType.C1: 60,
    VisaType.C2: 60,
    VisaType.C7: 60,
    VisaType.C7A: 30,
    VisaType.C7B: 30,
    VisaType.E33G: 365,
    VisaType.E28A: 365 * 2,
    VisaType.E23: 365,
    VisaType.E33F: 365,
    VisaType.E31: 365,
    VisaType.E30A: 365,
}


# Some visas allow N extensions of M days each.
# (source: docs/VISA_TYPES_REFERENCE.md — confirmed 2026-04-19 memory entry
# "Visa C-series duration rules": C1/C2/C7 = 60 + 2×60 = 180 max.)
EXTENSION_POLICY: dict[VisaType, tuple[int, int]] = {
    # (count, days_each)
    VisaType.B211A: (1, 60),
    VisaType.C1: (2, 60),
    VisaType.C2: (2, 60),
    VisaType.C7: (2, 60),
    VisaType.C7A: (0, 0),  # non-extendable
    VisaType.C7B: (0, 0),
    VisaType.E33G: (1, 365),
    VisaType.E28A: (1, 365 * 2),
    VisaType.E23: (1, 365),
    VisaType.E33F: (1, 365),
    VisaType.E31: (1, 365),
    VisaType.E30A: (1, 365),
}
