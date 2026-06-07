"""Deterministic summaries for non-green pulse drivers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


_SEVERITY = {
    "green": 0,
    "ok": 0,
    "yellow": 1,
    "unknown": 1,
    "failed": 2,
    "red": 2,
    "critical": 2,
}


@dataclass(frozen=True)
class RedSummary:
    driver_sensors: list[str] = field(default_factory=list)
    headline: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def summarize_pulse(
    status: str,
    sensor_statuses: Mapping[str, str],
    sensor_metadata: Mapping[str, Any] | None = None,
) -> RedSummary:
    """Return the named sensors that explain a non-green aggregate pulse.

    The pulse loop already computes the worst status. This function only makes
    that decision legible and deterministic for DB logs, observability payloads,
    and future operator views.
    """
    target_severity = _severity(status)
    if target_severity <= 0:
        return RedSummary()

    metadata = sensor_metadata or {}
    drivers = [
        name for name, sensor_status in sensor_statuses.items()
        if _severity(sensor_status) == target_severity
    ]
    if not drivers:
        drivers = [
            name for name, sensor_status in sensor_statuses.items()
            if _severity(sensor_status) > 0
        ]

    details = {
        name: {
            "status": sensor_statuses.get(name, ""),
            "metadata": metadata.get(name, {}),
        }
        for name in drivers
    }
    lines = [
        _format_driver(name, sensor_statuses.get(name, ""), metadata.get(name, {}))
        for name in drivers
    ]
    lines = [line for line in lines if line]
    if not lines and drivers:
        lines = [f"{name}={sensor_statuses.get(name, '')}" for name in drivers]

    visible = lines[:2]
    if len(lines) > 2:
        visible.append(f"+{len(lines) - 2} more")

    return RedSummary(
        driver_sensors=drivers,
        headline="; ".join(visible),
        details=details,
    )


def _severity(status: Any) -> int:
    return _SEVERITY.get(str(status).strip().lower(), 0)


def _format_driver(name: str, status: str, metadata: Any) -> str:
    meta = metadata if isinstance(metadata, Mapping) else {}
    if name == "backup":
        return _format_backup(status, meta)
    if name == "cron":
        return _format_cron(status, meta)
    if name == "outbox":
        return _format_outbox(status, meta)
    if name == "http":
        return _format_http(status, meta)

    reason = _first_text(meta, ("reason", "error", "message", "detail"))
    if reason:
        return f"{name} {status}: {_truncate(reason)}"
    if meta:
        return f"{name}={status} ({_compact_metadata(meta)})"
    return f"{name}={status}"


def _format_backup(status: str, metadata: Mapping[str, Any]) -> str:
    reason = _first_text(metadata, ("reason", "error", "message"))
    age = metadata.get("age_hours")
    if age is not None:
        age_label = _format_hours(age)
        path = _first_text(metadata, ("path", "last_backup_path"))
        suffix = f" ({path})" if path else ""
        verb = "stale" if status == "red" else "aging"
        return f"backup {verb} {age_label}{suffix}"
    if reason:
        return f"backup {status}: {_truncate(reason)}"
    return f"backup={status}"


def _format_cron(status: str, metadata: Mapping[str, Any]) -> str:
    failed = _list_label(metadata.get("failed_jobs"))
    stale = _list_label(metadata.get("stale_jobs"))
    parts = []
    if failed:
        parts.append(f"failed={failed}")
    if stale:
        parts.append(f"stale={stale}")
    total = metadata.get("total")
    if total is not None:
        parts.append(f"total={total}")
    if parts:
        label = "blocked" if status == "red" else "degraded"
        return f"cron {label}: {'; '.join(parts)}"
    return f"cron={status}"


def _format_outbox(status: str, metadata: Mapping[str, Any]) -> str:
    count = metadata.get("unconsumed_count")
    if count is not None:
        channel = _first_text(metadata, ("channel",))
        suffix = f" on {channel}" if channel else ""
        return f"outbox lag {count} events{suffix}"
    return _format_generic("outbox", status, metadata)


def _format_http(status: str, metadata: Mapping[str, Any]) -> str:
    reachable = metadata.get("reachable")
    code = metadata.get("status_code")
    body_status = _first_text(metadata, ("body_status",))
    if reachable is False:
        return "http unreachable"
    if code is not None:
        suffix = f", body={body_status}" if body_status else ""
        return f"http {status}: status_code={code}{suffix}"
    return f"http={status}"


def _format_generic(name: str, status: str, metadata: Mapping[str, Any]) -> str:
    reason = _first_text(metadata, ("reason", "error", "message", "detail"))
    if reason:
        return f"{name} {status}: {_truncate(reason)}"
    if metadata:
        return f"{name}={status} ({_compact_metadata(metadata)})"
    return f"{name}={status}"


def _first_text(metadata: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and value != "":
            return str(value)
    return ""


def _format_hours(value: Any) -> str:
    try:
        return f"{float(value):.0f}h"
    except (TypeError, ValueError):
        return f"{value}h"


def _list_label(value: Any, limit: int = 3) -> str:
    if not isinstance(value, list) or not value:
        return ""
    labels = [str(item) for item in value[:limit]]
    if len(value) > limit:
        labels.append(f"+{len(value) - limit}")
    return ",".join(labels)


def _compact_metadata(metadata: Mapping[str, Any], limit: int = 3) -> str:
    parts = []
    for key, value in list(metadata.items())[:limit]:
        if isinstance(value, list):
            value = _list_label(value)
        parts.append(f"{key}={value}")
    return _truncate(", ".join(parts))


def _truncate(value: str, limit: int = 160) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "..."
