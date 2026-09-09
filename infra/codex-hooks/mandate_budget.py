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

# The supervisor waits this long for a destination to claim its source. It is the
# SAME window that decides whether a still-reserved row is mid-handshake or
# abandoned, so the two must be derived from one another and not merely agree:
# context_bridge.py imports this name. Until 2026-09-10 the sweep below defaulted
# to 60 s against this 240 s handshake, so any concurrent reserve() under a shared
# NUZANTARA_MANDATE_ID swept a HEALTHY mid-handshake row to expired_unstarted —
# leaving the max_active count (cap drift) and orphaning the later accept, which
# then found no reserved row to bind and recorded "observed without a dispatch
# reservation".
ACKNOWLEDGE_SECONDS = 240

# How long an ACTIVE row may go silent before the sweep may call it a suspect
# zombie. The Claude adapter has always passed this explicitly (child_workflow.py
# active_ttl=1800); install.py's Codex default carried no such key, and the sweep
# below was gated on `limits.get("active_ttl")` — so on the Codex side the sweep
# never ran at all and a SIGKILLed supervisor pinned its slot until max_attempts.
# A default here cures the policies already on disk, which an install-time-only
# fix would not: none of the three live seats has the key.
ACTIVE_TTL_SECONDS = 1800


def _attend(state: dict[str, Any], reason: str, key: str) -> None:
    """Raise the live attention flag AND keep the history.

    Every writer went through `state["status"] = "needs_attention"` directly and
    nothing ever cleared it, so a child that later returned cleanly left its alarm
    standing and the attention report accumulated resolved alarms — the same
    signal pollution R1 was written to stop, one level up. The live flag is now
    derived from a KEY that a later contradicting observation can supersede; the
    ledger keeps every raise in `attention_history` regardless.
    """
    state["status"] = "needs_attention"
    state["reason"] = reason
    state["attention_key"] = key
    state.setdefault("attention_history", []).append(
        {"reason": reason, "key": key, "at": time.time()}
    )


def _resolve(state: dict[str, Any], *keys: str) -> None:
    """Supersede the live flag when an observation contradicts the raise.

    Only the named keys are cleared: an alarm this observation says nothing about
    must survive. The history is never rewritten — the alarm happened.
    """
    if state.get("status") == "needs_attention" and state.get("attention_key") in keys:
        state.pop("status", None)
        state.pop("reason", None)
        resolved = state.pop("attention_key", None)
        state.setdefault("attention_history", []).append(
            {"resolved": resolved, "at": time.time()}
        )


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
    """Reserve before dispatch; expiration never refunds a spent attempt.

    Transcript liveness checks are opt-in. A silent child remains in the ledger
    as suspect_zombie, never as a claim that its process was killed.
    """
    if os.environ.get("MANDATE_BUDGET_OFF") == "1":
        return None
    with ledger(root, mandate) as state:
        state.setdefault("created", time.time())
        state.setdefault("deadline", state["created"] + limits.get("max_seconds", 3600))
        reservations = state.setdefault("reservations", {})
        state["budget_mode"] = (
            "enforced" if limits.get("strict", True) else "interactive_observation"
        )
        state["max_active"] = limits.get("max_active", 3)
        if not tool_id:
            _attend(
                state,
                "Native dispatch identity is UNKNOWN; return to the coordinator.",
                "dispatch_identity_unknown",
            )
            return "Native dispatch identity is UNKNOWN; return to the coordinator."
        key = hashlib.sha256(tool_id.encode()).hexdigest()
        if key in reservations:
            return None
        for row in reservations.values():
            if row["status"] == "reserved" and time.time() - row[
                "created"
            ] > limits.get("unstarted_ttl", ACKNOWLEDGE_SECONDS):
                row["status"] = "expired_unstarted"
            elif row["status"] == "active":
                active_ttl = limits.get("active_ttl", ACTIVE_TTL_SECONDS)
                heartbeat = max(row.get("heartbeat", row["created"]), row["created"])
                if time.time() - heartbeat < active_ttl:
                    # A row heartbeating inside its TTL contradicts an earlier
                    # "liveness UNKNOWN" on this ledger: the slot is demonstrably
                    # alive, so the alarm must not outlive the doubt.
                    _resolve(state, "liveness_unknown")
                    continue
                child_row = state.get("children", {}).get(row.get("child"), {})
                try:
                    transcript = Path(child_row["transcript_path"])
                    modified = transcript.stat().st_mtime
                except (KeyError, OSError):
                    # Missing evidence cannot establish transcript silence.
                    _attend(
                        state,
                        "Child transcript liveness UNKNOWN; slot retained",
                        "liveness_unknown",
                    )
                    continue
                last_activity = max(modified, heartbeat)
                if time.time() - last_activity >= active_ttl:
                    row.update(status="suspect_zombie", suspected_at=time.time())
                    _attend(
                        state,
                        "Child transcript silent; suspect_zombie slot requires reconciliation",
                        "suspect_zombie",
                    )
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
                _attend(state, "Resume target UNKNOWN", "resume_target_unknown")
        active = {
            r.get("child", key)
            for key, r in reservations.items()
            if r["status"] in ("reserved", "active")
        }
        reason = None
        strict = limits.get("strict", True)
        if time.time() >= state["deadline"] and strict:
            reason = "Mandate deadline reached"
        elif depth > limits.get("max_depth", 1) and strict:
            # Gated like its four siblings. It was the only limit in this chain
            # enforced under interactive_observation too — an asymmetry nobody
            # chose: the structural depth rule is already enforced by the adapter
            # ABOVE this ledger, so an ungated copy here duplicated a decision it
            # does not own and would have denied an interactive caller that the
            # other four limits let through.
            reason = "Mandate child depth reached"
        elif len(reservations) >= limits.get("max_attempts", 24) and strict:
            reason = "Mandate total dispatch attempts reached"
        elif (
            strict
            and len(active) >= limits.get("max_active", 3)
            and child not in active
        ):
            reason = "Mandate concurrent dispatch limit reached"
        if reason:
            _attend(state, reason, "mandate_limit")
            return (
                reason
                + "; return the remaining work. Do not reset the budget with a replacement."
            )
        reservations[key] = {
            "status": "active" if child else "reserved",
            "created": time.time(),
            "heartbeat": time.time(),
            "depth": depth,
        }
        if child:
            reservations[key]["child"] = child
        state["budget_mode"] = "enforced" if strict else "interactive_observation"
        if not strict and (
            time.time() >= state["deadline"]
            or len(reservations) > limits.get("max_attempts", 24)
            or (len(active) >= limits.get("max_active", 3) and child not in active)
        ):
            _attend(
                state,
                "Interactive session counters exceed one mandate budget; declare an "
                "explicit autonomous mandate for enforced total limits.",
                "interactive_counters",
            )
    return None


def observe(
    root: Path,
    mandate: str,
    child: str,
    stopped: bool = False,
    alias: str | None = None,
    nickname: str | None = None,
    transcript: str | None = None,
) -> str | None:
    with ledger(root, mandate) as state:
        children = state.setdefault("children", {})
        children.setdefault(child, {}).update(
            {
                "transport": "stopped" if stopped else "started",
                "acceptance": "unverified",
                "heartbeat": time.time(),
            }
        )
        if transcript:
            children[child]["transcript_path"] = transcript
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
        if bound is None:
            # Claim the pending reservation whether this is a start OR a stop. Under
            # reordered or missing hook delivery a SubagentStop can arrive first; when
            # the claim was gated on `not stopped` the row stayed `reserved` while the
            # child was recorded stopped, so the slot leaked until unstarted_ttl swept
            # it and the ledger reported attention for a child that had returned fine.
            bound = next(
                (r for r in reservations.values() if r["status"] == "reserved"), None
            )
            if bound is not None:
                bound["child"] = child
        if bound is not None:
            if not stopped and bound["status"] not in ("active", "reserved"):
                active = {
                    r.get("child", key)
                    for key, r in reservations.items()
                    if r["status"] in ("active", "reserved")
                }
                if (
                    state.get("budget_mode") == "enforced"
                    and child not in active
                    and len(active) >= state.get("max_active", 3)
                ):
                    _attend(
                        state,
                        "Child lease cannot resume: concurrent dispatch limit reached",
                        "lease_cannot_resume",
                    )
                    return state["reason"]
            bound["status"] = "returned_unverified" if stopped else "active"
            bound["heartbeat"] = time.time()
            # This child DID have a reservation and its lease DID resume, which is
            # exactly what those two alarms claimed was untrue. Any other alarm
            # (a mandate limit, an unknown resume target) is untouched.
            _resolve(state, "observed_without_reservation", "lease_cannot_resume")
            # One child may have multiple resume reservations. Refresh them all.
            for row in reservations.values():
                if row.get("child") == child:
                    row["heartbeat"] = time.time()
            if stopped:
                for row in reservations.values():
                    if row.get("child") == child:
                        row["status"] = "returned_unverified"
        else:
            _attend(
                state,
                "Child observed without a dispatch reservation",
                "observed_without_reservation",
            )
    return None
