"""Deterministic, session-local Universal Conductor runtime primitives.

This package intentionally contains no process launcher, network client, probe, or
daemon loop.  Those boundaries are handled by later adapters; this layer turns
already-observed MIR data into an explainable routing plan.
"""

from __future__ import annotations
