"""Small locked mandate ledger shared by both hook adapters; no worker launcher."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def ledger(root: Path, mandate: str) -> Iterator[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (hashlib.sha256(mandate.encode()).hexdigest() + ".json")
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            state = {}
        state.setdefault("mandate_id", mandate)
        yield state
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        with open(tmp, "w", opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
            json.dump(state, out)
        tmp.replace(path)


def reserve(
    root: Path,
    mandate: str,
    tool_id: str,
    limits: dict[str, Any],
    depth: int = 1,
    target: str | None = None,
) -> str | None:
    """Reserve before dispatch. Failed/unknown dispatches retain their reservation.

    This deliberately needs coordinator attention rather than silently spending
    another attempt or releasing an unobserved worker. A repeat of the same
    native tool id is idempotent. No prompts, tool arguments or PII are stored.
    """
    if os.environ.get("MANDATE_BUDGET_OFF") == "1":
        return None
    with ledger(root, mandate) as state:
        state.setdefault("created", time.time())
        state.setdefault("deadline", state["created"] + limits.get("max_seconds", 3600))
        reservations = state.setdefault("reservations", {})
        if not tool_id:
            state["status"] = "needs_attention"
            return "Native dispatch identity is UNKNOWN; return to the coordinator."
        key = hashlib.sha256(tool_id.encode()).hexdigest()
        if key in reservations:
            return None
        for row in reservations.values():
            if row["status"] == "reserved" and time.time() - row[
                "created"
            ] > limits.get("unstarted_ttl", 60):
                row["status"] = "expired_unstarted"
        child = None
        if target:
            alias = target if target.startswith("/") else "/root/" + target
            children = state.get("children", {})
            child = (
                target
                if target in children
                else next(
                    (
                        cid
                        for cid, row in children.items()
                        if set(
                            row.get("aliases_sha256", []) + [row.get("alias_sha256")]
                        )
                        & {
                            hashlib.sha256(alias.encode()).hexdigest(),
                            hashlib.sha256(target.encode()).hexdigest(),
                        }
                    ),
                    None,
                )
            )
            if child is None:
                state.update(status="needs_attention", reason="Resume target UNKNOWN")
        active = {
            r.get("child", key)
            for key, r in reservations.items()
            if r["status"] in ("reserved", "active")
        }
        reason = None
        strict = limits.get("strict", True)
        if time.time() >= state["deadline"] and strict:
            reason = "Mandate deadline reached"
        elif depth > limits.get("max_depth", 1):
            reason = "Mandate child depth reached"
        elif len(reservations) >= limits.get("max_attempts", 24) and strict:
            reason = "Mandate total dispatch attempts reached"
        elif len(active) >= limits.get("max_active", 3) and child not in active:
            reason = "Mandate concurrent dispatch limit reached"
        if reason:
            state.update(status="needs_attention", reason=reason)
            return (
                reason
                + "; return the remaining work. Do not reset the budget with a replacement."
            )
        reservations[key] = {
            "status": "active" if child else "reserved",
            "created": time.time(),
            "depth": depth,
        }
        if child:
            reservations[key]["child"] = child
        state["budget_mode"] = "enforced" if strict else "interactive_observation"
        if not strict and (
            time.time() >= state["deadline"]
            or len(reservations) > limits.get("max_attempts", 24)
        ):
            state.update(
                status="needs_attention",
                reason="Interactive session counters exceed one mandate budget; declare an explicit autonomous mandate for enforced total limits.",
            )
    return None


def observe(
    root: Path,
    mandate: str,
    child: str,
    stopped: bool = False,
    alias: str | None = None,
    nickname: str | None = None,
) -> None:
    with ledger(root, mandate) as state:
        children = state.setdefault("children", {})
        children.setdefault(child, {}).update(
            {
                "transport": "stopped" if stopped else "started",
                "acceptance": "unverified",
            }
        )
        if alias:
            children[child]["alias_sha256"] = hashlib.sha256(alias.encode()).hexdigest()
        children[child]["aliases_sha256"] = list(
            set(
                children[child].get("aliases_sha256", [])
                + [
                    hashlib.sha256(value.encode()).hexdigest()
                    for value in (child, alias, nickname)
                    if value
                ]
            )
        )
        reservations = state.get("reservations", {})
        bound = next(
            (
                r
                for r in reversed(list(reservations.values()))
                if r.get("child") == child
            ),
            None,
        )
        if bound is None and not stopped:
            bound = next(
                (r for r in reservations.values() if r["status"] == "reserved"), None
            )
            if bound is not None:
                bound["child"] = child
        if bound is not None:
            bound["status"] = "returned_unverified" if stopped else "active"
            if stopped:
                for row in reservations.values():
                    if row.get("child") == child:
                        row["status"] = "returned_unverified"
        else:
            state["status"] = "needs_attention"
            state["reason"] = "Child observed without a dispatch reservation"
