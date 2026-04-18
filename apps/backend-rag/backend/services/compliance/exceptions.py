"""
Compliance subsystem exceptions.

Four domain-specific exception classes — one per failure boundary:
  AlertGenerationError  — alert build/persist pipeline failed
  AlertDispatchError    — delivery to a channel failed
  IntelValidationError  — Intel validator non-recoverable error
  LkpmValidationError   — LKPM data fails completeness validation

All are subclasses of ComplianceError for easy broad-catch.
"""
from __future__ import annotations


class ComplianceError(Exception):
    """Base for all compliance-subsystem exceptions."""


class AlertGenerationError(ComplianceError):
    """Raised when the alert generation pipeline fails non-recoverably."""


class AlertDispatchError(ComplianceError):
    """Raised when a channel dispatcher cannot deliver an alert."""


class IntelValidationError(ComplianceError):
    """Raised when an Intel validator encounters a non-recoverable error."""


class LkpmValidationError(ComplianceError):
    """Raised when LKPM data fails completeness validation."""


__all__ = [
    "ComplianceError",
    "AlertGenerationError",
    "AlertDispatchError",
    "IntelValidationError",
    "LkpmValidationError",
]
