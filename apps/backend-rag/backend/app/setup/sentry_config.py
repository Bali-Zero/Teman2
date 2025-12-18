"""
Sentry Configuration Module

Handles Sentry initialization for error monitoring.
Avoids initializing during tests unless explicitly desired.
"""

import os

import sentry_sdk


def init_sentry() -> None:
    """
    Initialize Sentry only when configured.

    Notes:
    - Avoids initializing during tests unless explicitly desired.
    - Default behavior is opt-in via SENTRY_DSN.
    """
    if os.getenv("SKIP_SENTRY_INIT"):
        return

    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return

    send_pii = os.getenv("SENTRY_SEND_DEFAULT_PII", "").strip().lower() in {"1", "true", "yes"}
    env = os.getenv("ENVIRONMENT", "development")
    traces_sample_rate = (
        float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")) if env == "production" else 1.0
    )
    profiles_sample_rate = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        send_default_pii=send_pii,
        environment=env,
        release=os.getenv("SENTRY_RELEASE", "nuzantara-backend@1.0.0"),
    )

