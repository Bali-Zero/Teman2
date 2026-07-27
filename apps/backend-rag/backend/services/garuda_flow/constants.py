"""GARUDA VOA pilot — Safe Clock + intake constants (single source of truth).

Every number here is traceable to a governance document, NOT invented:

- ``PILOT_INTAKE_THRESHOLD_DAYS`` (D-10): set 2026-07-24 (Zero-delegated) as
  SOP-v0-GARUDA-B1 §1 "Pilot intake threshold". Owner ruling 2026-07-27
  RETIRED that role: the gate was declining cases (e.g. 8 days of runway)
  that are still legally filable under the published deadline below, and
  it added margin nobody asked for — our threshold and the office's
  published deadline should be the same line. This constant survives
  ONLY as the SOP §6 internal staff-escalation checkpoint inside
  ``safe_clock.compute_stay`` — it is NEVER again an ACCEPT/DECLINE gate,
  and, as before, NEVER quoted to a client.
- ``PUBLISHED_FILING_DEADLINE_DAYS`` (D-7): the published Ngurah Rai filing
  deadline ("paling lambat 7 hari sebelum masa izin tinggal berakhir",
  verified verbatim on ngurahrai.imigrasi.go.id 2026-07-24). The one number
  that IS client-facing, AND (owner ruling 2026-07-27) the single source
  of truth `eligibility.screen()` derives the extension-intake runway
  gate from — no separately-tuned pilot margin anymore. "verify per
  office" — offices may differ.
- ``EXTENSION_WINDOW_OPENS_DAYS`` (D-14): INTERNAL-ONLY staff estimate of the
  earliest the extension window opens. The source states this two
  incompatible ways on the same page — "paling cepat ... 14 hari sebelum
  masa berlaku ... habis" (14 days before expiry) vs. "paling cepat 14
  hari setelah kedatangan" (14 days after arrival) — different dates on a
  30-day B1. This constant implements the BEFORE-EXPIRY reading because it
  is the conservative one (never earlier than an office might accept), not
  because the source confirms it. Never client-facing — see
  `safe_clock.filing_window_opens_for` docstring and
  `app/routers/garuda_voa.py` for the boundary this backs.
- ``INTERNAL_ESCALATION_DAYS`` (D-3) / ``FINAL_CHECK_DAYS`` (D-1): internal
  Bali Zero checkpoints only (SOP §6) — never quoted to clients.
- ``MIN_PASSPORT_VALIDITY_DAYS`` (≥6 months from entry): SOP §1 + §4 checklist.

These are the enforceable form of what the Gate-1 role-play validated by hand.
"""

from __future__ import annotations

# ── Safe Clock (days before the VOA/extension expiry) ────────────────
EXTENSION_WINDOW_OPENS_DAYS: int = 14  # D-14 — earliest the window opens
PUBLISHED_FILING_DEADLINE_DAYS: int = 7  # D-7 — published Ngurah Rai deadline (client-facing)
PILOT_INTAKE_THRESHOLD_DAYS: int = 10  # D-10 — internal SOP §6 staff-escalation checkpoint only
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
