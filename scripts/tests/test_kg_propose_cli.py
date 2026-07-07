"""Unit tests for the kg-propose operator CLI (scripts/kg_propose.py).

These tests mock KGProposalStore entirely — no DB, no network. They lock down
the two things that matter for safety: (1) command routing reaches the right
store method, and (2) `apply`/`apply-all` are dry-run UNLESS `--yes` is passed
(the production-KG-mutation boundary). The KG-write logic itself lives in the
already-tested KGProposalStore.apply_approved and is not re-tested here.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock


# Load the CLI module by path (scripts/ is not a package).
_CLI_PATH = Path(__file__).resolve().parents[1] / "kg_propose.py"
_spec = importlib.util.spec_from_file_location("kg_propose", _CLI_PATH)
assert _spec and _spec.loader
kg_propose = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kg_propose)


def _store(**overrides) -> AsyncMock:
    store = AsyncMock()
    store.list_proposals.return_value = overrides.get("list", [])
    store.get_proposal.return_value = overrides.get("get", None)
    store.approve.return_value = overrides.get("approve", True)
    store.reject.return_value = overrides.get("reject", True)
    store.apply_approved.return_value = overrides.get("apply", True)
    return store


def _run(store: AsyncMock, args: list[str]) -> int:
    parsed = kg_propose._build_parser().parse_args(args)
    return asyncio.run(parsed.func(store, parsed))


_APPROVED = {
    "proposal_id": "abc12345-0000-0000-0000-000000000000",
    "status": "approved",
    "proposal_type": "node",
    "domain": "company",
    "node_label": "NIB registration",
    "self_rag_score": 0.99,
}
_PENDING = {**_APPROVED, "status": "pending"}


def test_list_routes_to_store() -> None:
    store = _store(list=[_PENDING])
    assert _run(store, ["list", "--status", "pending"]) == 0
    store.list_proposals.assert_awaited_once()


def test_approve_routes_with_by() -> None:
    store = _store(approve=True)
    assert _run(store, ["approve", _APPROVED["proposal_id"], "--by", "zero"]) == 0
    store.approve.assert_awaited_once_with(_APPROVED["proposal_id"], approved_by="zero")


def test_apply_without_yes_is_dry_run() -> None:
    """The safety contract: no --yes => apply_approved is NEVER called."""
    store = _store(get=_APPROVED)
    rc = _run(store, ["apply", _APPROVED["proposal_id"]])
    assert rc == 0
    store.apply_approved.assert_not_awaited()


def test_apply_with_yes_mutates() -> None:
    store = _store(get=_APPROVED, apply=True)
    rc = _run(store, ["apply", _APPROVED["proposal_id"], "--yes"])
    assert rc == 0
    store.apply_approved.assert_awaited_once_with(_APPROVED["proposal_id"])


def test_apply_refuses_non_approved() -> None:
    """apply on a 'pending' proposal must fail loudly and never mutate."""
    store = _store(get=_PENDING)
    rc = _run(store, ["apply", _PENDING["proposal_id"], "--yes"])
    assert rc == 1
    store.apply_approved.assert_not_awaited()


def test_apply_all_without_yes_is_dry_run() -> None:
    store = _store(list=[_APPROVED, _APPROVED])
    rc = _run(store, ["apply-all"])
    assert rc == 0
    store.apply_approved.assert_not_awaited()


def test_apply_all_with_yes_applies_each() -> None:
    store = _store(list=[_APPROVED, _APPROVED], apply=True)
    rc = _run(store, ["apply-all", "--yes"])
    assert rc == 0
    assert store.apply_approved.await_count == 2


def test_reject_routes_with_reason() -> None:
    store = _store(reject=True)
    assert _run(store, ["reject", _PENDING["proposal_id"], "--reason", "dup"]) == 0
    store.reject.assert_awaited_once_with(_PENDING["proposal_id"], reason="dup")
