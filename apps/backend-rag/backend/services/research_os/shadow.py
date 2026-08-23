"""Feature-flagged shadow dual-write for the Magazine action-chain adapters.

Packet's own "Shadow and rollback" section: "All domain dual-write flags
default off ... canonical write failures must be observable but must not
corrupt legacy truth." And, from this deliverable's own scoping note: "the
canonical models currently have zero non-test consumers anywhere in the
repo. So there is no live legacy write path to shadow yet." This module
therefore proves the flag-off no-op and the failure-isolation contract at
the code level -- there is no canonical persistence layer to write INTO yet
(that is Work Packet 04 Deliverable 5, the `research_os_contract_core`
migration, a different deliverable). Once that repository exists, its
writer slots in where the `# TODO` below is; nothing about the flag
contract changes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from research_os.models.action_intent import ActionIntent
from research_os.models.action_item import ActionItem
from research_os.models.operational_receipt import OperationalReceipt

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.action_intent_adapter import adapt_ops_intent_to_action_intent
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.legacy_magazine import OpsIntentRow, OpsReceiptRow
from backend.services.research_os.loss_report import AdapterResult
from backend.services.research_os.operational_receipt_adapter import (
    adapt_ops_receipt_to_operational_receipt,
)

logger = logging.getLogger(__name__)

SHADOW_FLAG_ENV_VAR = "RESEARCH_OS_SHADOW_MAGAZINE_ACTIONS"


def shadow_dual_write_enabled() -> bool:
    """Defaults OFF: any value other than an explicit truthy string leaves
    the shadow path fully dark.
    """

    return os.environ.get(SHADOW_FLAG_ENV_VAR, "false").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ShadowRunResult:
    enabled: bool
    action_item: AdapterResult[ActionItem] | None
    action_intent: AdapterResult[ActionIntent] | None
    operational_receipt: AdapterResult[OperationalReceipt] | None
    error: str | None


_NOOP_RESULT = ShadowRunResult(
    enabled=False, action_item=None, action_intent=None, operational_receipt=None, error=None
)


def shadow_adapt_magazine_action_chain(
    intent_row: OpsIntentRow, receipt_row: OpsReceiptRow | None = None
) -> ShadowRunResult:
    """Flag OFF (default): returns the shared no-op result WITHOUT calling
    any adapter -- this is the acceptance test itself, enforced at the code
    level (see `test_shadow_flag_off_is_noop.py`, which asserts the
    adapters are never invoked), not just documented as an aspiration.

    Flag ON: runs all three adapters and returns their results. Any
    exception is caught, logged (`logger.error`, observable), and reported
    back via `error` -- it never propagates, so it can never corrupt or
    block whatever legacy write path the caller is also doing alongside it.
    """

    if not shadow_dual_write_enabled():
        return _NOOP_RESULT

    try:
        item_result = adapt_ops_intent_to_action_item(intent_row)
        intent_result = adapt_ops_intent_to_action_intent(intent_row)
        receipt_result = (
            adapt_ops_receipt_to_operational_receipt(receipt_row, intent_row)
            if receipt_row is not None
            else None
        )
    except Exception as exc:
        logger.error(
            "research_os shadow dual-write failed for ops_intent %s: %s",
            intent_row.get("intent_id"),
            exc,
            exc_info=True,
        )
        return ShadowRunResult(
            enabled=True, action_item=None, action_intent=None, operational_receipt=None, error=str(exc)
        )

    # TODO(research_os_contract_core, Deliverable 5): once the canonical
    # repository lands, persist item_result/intent_result/receipt_result
    # here (additively, never touching Magazine's own tables) and surface
    # persistence failures through `error` the same way the adapter
    # exception path above already does.
    return ShadowRunResult(
        enabled=True,
        action_item=item_result,
        action_intent=intent_result,
        operational_receipt=receipt_result,
        error=None,
    )
