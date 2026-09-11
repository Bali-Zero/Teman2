"""Child usage and expiring, seat-local CLI capacity calibration; no API calls.

Reuses tokenaudit's latest-request accounting pattern, with strict missing-data
handling and output allowance. Never sums usage over the child's lifetime.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
from pathlib import Path
from typing import Any

TTL = 7 * 86400
FALLBACK_TOKENS = 400000
MAX_TOOL_CALLS = 120
MAX_SECONDS = 3600


def seat() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def snapshot(tail: str) -> dict[str, Any]:
    """Latest assistant request only; streaming duplicates are not added together."""
    for line in reversed(tail.splitlines()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("type") != "assistant":
            continue
        message = row.get("message") or {}
        usage = message.get("usage") or {}
        counts = [usage.get("input_tokens")] + [
            usage.get(k, 0)
            for k in (
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            )
        ]
        return {
            "model": message.get("model"),
            "version": row.get("version"),
            "used": sum(counts)
            if all(type(n) is int and n >= 0 for n in counts)
            else None,
        }
    return {"model": None, "version": None, "used": None}


def scope(cwd: str) -> str:
    """Hash routing/settings without retaining their contents or credential values.

    Hook definitions are excluded so installation does not invalidate calibration.
    Project model/env overrides do invalidate it. Capacity is never shared by seats.
    """
    paths = [seat() / "settings.json", seat() / "settings.local.json"]
    location = Path(cwd).resolve()
    paths += [
        p / ".claude" / name
        for p in (location, *location.parents)
        for name in ("settings.json", "settings.local.json")
    ]
    settings = []
    seen = set()
    for path in paths:
        if not path.is_file() or path.resolve() in seen:
            continue
        seen.add(path.resolve())
        value = json.loads(path.read_text())
        selected = {k: v for k, v in value.items() if k in ("model", "env")}
        if selected:
            settings.append(selected)
    # Presence/values of routing flags matter; OAuth/API credentials are excluded.
    env = {
        k: v
        for k, v in os.environ.items()
        if (
            k.startswith("CLAUDE_CODE_USE_")
            or k.startswith("ANTHROPIC_DEFAULT_")
            or k
            in (
                "ANTHROPIC_BASE_URL",
                "ANTHROPIC_MODEL",
                "CLAUDE_CODE_DISABLE_1M_CONTEXT",
                "ANTHROPIC_CUSTOM_HEADERS",
                "CLAUDE_CODE_BETAS",
            )
        )
    }
    return hashlib.sha256(
        json.dumps(
            [platform.node(), str(seat().resolve()), settings, env], sort_keys=True
        ).encode()
    ).hexdigest()


def calibration_path(model: str, version: str, cwd: str) -> Path:
    return scoped_path(model, version, scope(cwd))


def scoped_path(model: str, version: str, fingerprint: str) -> Path:
    key = hashlib.sha256(json.dumps([model, version, fingerprint]).encode()).hexdigest()
    return seat() / "state" / "child-context-capacities" / (key + ".json")


def capacity(model: str | None, version: str | None, cwd: str) -> int | None:
    if not model or not version:
        return None
    try:
        record = json.loads(calibration_path(model, version, cwd).read_text())
        age = time.time() - record["observed_at"]
        window = record["window"]
        if (
            0 <= age <= TTL
            and record["model"] == model
            and record["version"] == version
            and record["scope"] == scope(cwd)
            and type(window) is int
            and 16000 <= window <= 2000000
        ):
            return window
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def calibrate(
    result: dict[str, Any], observations: list[dict[str, Any]], cwd: str
) -> list[dict[str, Any]]:
    """Called only by the owned native probe after a successful CLI result.

    Metadata-only entries bind native transcript identity/version to modelUsage.
    The probe must complete before capacity can guide a subsequent child.
    """
    if result.get("type") != "result" or result.get("is_error", True):
        return []
    records = []
    for observed in observations:
        model, version = observed.get("model"), observed.get("version")
        # CLI can key this map by a routing spelling (e.g. opus-5[1m]) while
        # the native transcript uses opus-5. Only explicit canonicalModel binds
        # those identities; never guess by removing an arbitrary suffix.
        windows = [
            entry.get("contextWindow")
            for key, entry in result.get("modelUsage", {}).items()
            if key == model or entry.get("canonicalModel") == model
        ]
        window = (
            windows[0] if windows and all(w == windows[0] for w in windows) else None
        )
        used = observed.get("used")
        if not (
            model
            and version
            and type(window) is int
            and 16000 <= window <= 2000000
            and type(used) is int
            and 0 < used <= window
        ):
            continue
        fingerprint = observed.get("capacity_scope") or scope(cwd)
        if not isinstance(fingerprint, str) or not re.fullmatch(
            r"[a-f0-9]{64}", fingerprint
        ):
            continue
        path = scoped_path(model, version, fingerprint)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {
            "model": model,
            "version": version,
            "window": window,
            "scope": fingerprint,
            "observed_at": time.time(),
            "source": "owned_cli_probe.modelUsage.contextWindow",
            "session_id": result.get("session_id"),
        }
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        with open(temporary, "w", opener=lambda p, f: os.open(p, f, 0o600)) as out:
            json.dump(record, out)
        temporary.replace(path)
        records.append(record)
    return records
