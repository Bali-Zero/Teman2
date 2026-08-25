"""Legacy row shapes for `apps/bali-zero-magazine`'s ops-action tables.

Field-level ground truth for both TypedDicts below was read directly from
`apps/bali-zero-magazine/db/schema.ts` (`opsIntents` / `opsReceipts`) in this
session -- not carried over from the D3 compatibility matrix without
re-checking. Column names are the snake_case DB names (Drizzle maps its
camelCase field names to these); no transport layer exists yet between
Magazine's Cloudflare D1 and this backend, so an adapter caller supplies a
plain mapping shaped like the DB row however it eventually reads one.

Note (verified this session, not carried from the matrix): `ops_intents` has
no `updated_at` column at all -- only `created_at`. The row is mutated in
place (`status`, `attempt_count`, ...) with no last-modified timestamp
anywhere on it; `ActionItem.recorded_at` has to be approximated from other
timestamp columns (see `action_item_adapter.py`).
"""

from __future__ import annotations

from typing import TypedDict


class OpsIntentRow(TypedDict, total=False):
    intent_id: str
    actor_key: str
    effective_role: str  # CHECK constant, always 'operator'
    policy_version: str
    idempotency_key: str
    intent_kind: str  # closed 5-value enum, see ACTION_TYPES below
    params_json: str
    request_hash: str  # sha256 over {schema_version,intent_kind,reason_code,expires_at,params}
    reason_code: str
    status: str  # queued|claimed|running|succeeded|failed|cancelled_revoked|outcome_unknown
    attempt_limit: int
    attempt_count: int
    worker_id: str | None
    claim_token: str | None
    fencing_token: int
    heartbeat_at: str | None
    lease_deadline: str | None
    effect_token: str | None
    pre_effect_attested_at: str | None
    attested_policy_version: str | None
    attestation_expires_at: str | None
    effect_consumed_at: str | None
    expires_at: str
    started_at: str | None
    completed_at: str | None
    failure_code: str | None
    created_at: str


class OpsReceiptRow(TypedDict, total=False):
    receipt_id: str
    intent_id: str  # UNIQUE FK -- one receipt per intent, ever (matrix §1.5 item 9)
    status: str
    receipt_json: str  # opaque, shape varies by intent_kind
    receipt_hash: str  # sha256
    request_hash: str  # sha256, duplicated from the parent ops_intents row
    key_id: str
    body_hash: str  # sha256
    fencing_token: int
    attested_policy_version: str | None
    created_at: str


ACTION_TYPES: frozenset[str] = frozenset(
    {
        "rerun_collector",
        "rebuild_edition",
        "quarantine_story",
        "release_story",
        "refresh_research_job",
    }
)

OPS_INTENT_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"succeeded", "failed", "cancelled_revoked", "outcome_unknown"}
)
