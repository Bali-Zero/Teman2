"""GARUDA VOA pilot — Safe Clock + intake constants (single source of truth).

Every number here is traceable to a governance document, NOT invented:

- ``PILOT_INTAKE_THRESHOLD_DAYS`` (D-10): SOP-v0-GARUDA-B1 §1 "Pilot intake
  threshold — D-10 (set 2026-07-24, Zero-delegated)". A pilot-conservatism
  parameter, NOT a legal limit — Zero/Surya may retune it. NEVER quoted to a
  client as an official rule.
- ``PUBLISHED_FILING_DEADLINE_DAYS`` (D-7): the published Ngurah Rai filing
  deadline ("paling lambat 7 hari sebelum masa izin tinggal berakhir",
  verified verbatim on ngurahrai.imigrasi.go.id 2026-07-24). The one number
  that IS client-facing. "verify per office" — offices may differ.
- ``EXTENSION_WINDOW_OPENS_DAYS`` (D-14): earliest the extension window opens
  ("paling cepat ... 14 hari sebelum masa berlaku ... habis", same source).
- ``INTERNAL_ESCALATION_DAYS`` (D-3) / ``FINAL_CHECK_DAYS`` (D-1): internal
  Bali Zero checkpoints only (SOP §6) — never quoted to clients.
- ``MIN_PASSPORT_VALIDITY_DAYS`` (≥6 months from entry): SOP §1 + §4 checklist.

These are the enforceable form of what the Gate-1 role-play validated by hand.
"""

from __future__ import annotations

# ── Safe Clock (days before the VOA/extension expiry) ────────────────
EXTENSION_WINDOW_OPENS_DAYS: int = 14  # D-14 — earliest the window opens
PUBLISHED_FILING_DEADLINE_DAYS: int = 7  # D-7 — published Ngurah Rai deadline (client-facing)
PILOT_INTAKE_THRESHOLD_DAYS: int = 10  # D-10 — pilot accepts only with >= this runway
INTERNAL_ESCALATION_DAYS: int = 3  # D-3 — internal escalation checkpoint
FINAL_CHECK_DAYS: int = 1  # D-1 — internal final-check checkpoint

# ── Intake ───────────────────────────────────────────────────────────
MIN_PASSPORT_VALIDITY_DAYS: int = 180  # >= 6 months from entry (SOP §1/§4)

__all__ = [
    "EXTENSION_WINDOW_OPENS_DAYS",
    "FINAL_CHECK_DAYS",
    "INTERNAL_ESCALATION_DAYS",
    "MIN_PASSPORT_VALIDITY_DAYS",
    "PILOT_INTAKE_THRESHOLD_DAYS",
    "PUBLISHED_FILING_DEADLINE_DAYS",
]
