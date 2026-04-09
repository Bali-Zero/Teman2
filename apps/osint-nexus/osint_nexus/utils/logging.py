"""OPSEC-safe logging — never logs PII at INFO, redacts at DEBUG."""

from __future__ import annotations

import logging
import re
import sys

from osint_nexus.config import LOG_LEVEL

_NIP_PATTERN = re.compile(r"\b\d{18}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+62|62|08)\d{8,12}\b")


class RedactingFormatter(logging.Formatter):
    """Redacts NIP and phone numbers from log output."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if record.levelno <= logging.DEBUG:
            msg = _NIP_PATTERN.sub("[NIP-REDACTED]", msg)
            msg = _PHONE_PATTERN.sub("[PHONE-REDACTED]", msg)
        return msg


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"osint.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            RedactingFormatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return logger
