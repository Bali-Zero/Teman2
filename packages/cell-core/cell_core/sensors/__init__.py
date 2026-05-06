"""Concrete sensors for cell-core PulseLoop.

Sensors must implement the ``cell_core.protocols.Sensor`` Protocol:
they expose a ``name`` attribute and an async ``read(**context)`` method
returning a ``SensorReading``.

All sensors here degrade gracefully (Symbiosis Law 4) — when their
upstream dependency is unreachable they return a yellow/red reading
with metadata, never raise.
"""
from __future__ import annotations

from cell_core.sensors.outbox_sensor import OutboxSensor

__all__ = ["OutboxSensor"]
