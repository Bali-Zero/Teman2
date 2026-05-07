"""OpenLLMetry SDK initialization helper.

Discovered in R1 SOTA 2026-05-08. OpenLLMetry (Traceloop) is OTel-native;
pair with Langfuse + Phoenix backend (Phase 1 deferred).

Dormant mode pattern (Nuzantara PR #312 cicatrix): when env vars unset,
init returns False and SDK is not loaded. Zero overhead.

Activation: set OPENLLMETRY_ENDPOINT (e.g. http://mini-pro2.local:4318)
plus optional Langfuse keys to forward to Langfuse self-host.
"""
from __future__ import annotations

import os


def is_openllmetry_enabled() -> bool:
    if os.environ.get("LANGFUSE_ENABLED", "").lower() == "false":
        return False
    return bool(os.environ.get("OPENLLMETRY_ENDPOINT"))


def init_openllmetry(service_name: str) -> bool:
    """Initialize OpenLLMetry SDK if env-enabled. Returns True if active."""
    if not is_openllmetry_enabled():
        return False
    try:
        from traceloop.sdk import Traceloop
    except ImportError:
        # SDK not installed — dormant mode.
        return False
    Traceloop.init(
        app_name=service_name,
        api_endpoint=os.environ["OPENLLMETRY_ENDPOINT"],
        disable_batch=False,
    )
    return True
