"""Agentic reconciliation: decide what to do with each counterpart's Doc on
every pass, by comparing the DESIRED state (computed now from the DB) against the
RECORDED state (what we did last time, stored in wa_corpus_docs).

This is the flow Antonello asked for: it is NOT enough to create a Doc once.
Every run we must handle the state transitions:
  - new counterpart                          -> CREATE
  - title changed (prospect→client, CRM name updated, category changed) -> RENAME
  - chat grew (new messages since last pass)  -> UPDATE (re-render + sync + recap)
  - nothing changed                           -> SKIP
  - no longer loadable (became team/group/multi-client) -> ARCHIVE (rename only)

The decision function is PURE (no DB, no NLM) so the whole transition matrix is
unit-tested. The Reconciler (separate, I/O) executes the chosen Action.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


class Action(enum.Enum):
    CREATE = "create"    # never seen -> render + add source + recap (+ CRM if client)
    RENAME = "rename"    # title must change (identity/category transition)
    UPDATE = "update"    # chat grew -> re-render + sync + recap (+ CRM if client)
    SKIP = "skip"        # nothing changed
    ARCHIVE = "archive"  # no longer loadable -> rename to an archived title


@dataclass(frozen=True)
class DesiredState:
    """What the counterpart should look like right now (computed from the DB)."""
    loadable: bool          # CLIENT or PROSPECT
    title: str              # doc_title() output for current CRM/phone state
    latest_msg_at: datetime | None  # MAX(message_date) for this chat


@dataclass(frozen=True)
class RecordedState:
    """What we did last time (row in wa_corpus_docs), or None if never seen."""
    file_id: str
    source_id: str
    last_title: str
    last_msg_at: datetime | None


ARCHIVED_PREFIX = "ARCHIVED · "


def archived_title(title: str) -> str:
    """Title used when a Doc is archived (kept, not deleted — Antonello: rename)."""
    if title.startswith(ARCHIVED_PREFIX):
        return title
    return ARCHIVED_PREFIX + title


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str
    new_title: str | None = None  # for RENAME / ARCHIVE


def decide_action(desired: DesiredState, recorded: RecordedState | None) -> Decision:
    """Pure decision: given desired vs recorded state, what to do this pass."""
    # 1. Never seen before.
    if recorded is None:
        if not desired.loadable:
            return Decision(Action.SKIP, "new but not loadable (team/group/multi-client)")
        return Decision(Action.CREATE, "new loadable counterpart")

    # 2. Seen before but no longer loadable -> archive (rename, keep the Doc).
    if not desired.loadable:
        target = archived_title(recorded.last_title)
        if recorded.last_title == target:
            return Decision(Action.SKIP, "already archived")
        return Decision(
            Action.ARCHIVE,
            "no longer loadable -> archive (rename)",
            new_title=target,
        )

    # 3. Loadable: title changed (prospect→client, CRM name added/updated,
    #    category change that still leaves it loadable) -> rename.
    if desired.title != recorded.last_title:
        return Decision(
            Action.RENAME,
            f"title changed: {recorded.last_title!r} -> {desired.title!r}",
            new_title=desired.title,
        )

    # 4. Chat grew since last pass -> update content + recap.
    if _is_newer(desired.latest_msg_at, recorded.last_msg_at):
        return Decision(Action.UPDATE, "new messages since last pass")

    # 5. Nothing changed.
    return Decision(Action.SKIP, "no change since last pass")


def _is_newer(desired_at: datetime | None, recorded_at: datetime | None) -> bool:
    if desired_at is None:
        return False
    if recorded_at is None:
        return True
    return desired_at > recorded_at
