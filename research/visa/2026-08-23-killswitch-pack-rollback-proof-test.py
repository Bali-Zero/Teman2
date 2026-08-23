"""TEMPORARY, uncommitted proof script for the Visa Oracle ENFORCE-GATE
kill-switch rollback proof (research/visa/2026-08-23-killswitch-rollback-proof.md).

Not part of the suite; not committed; delete after use. Reuses this
directory's own ``repo``/``visa_schema``/``db_pool`` fixtures (conftest.py)
and ``test_repository.py``'s pure builder helpers exactly as the sibling
test files (``test_activation_writer.py``, ``test_replace_activation_set.py``)
already do — no new mechanism invented, only a new SCENARIO: the full
"emergency rollback" ceremony end to end (guilt: literal old-sequence
reactivation rejected; innocence: re-signed forward-chained content restore
succeeds with exactly one open activation and no temporal gap).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from backend.services.visa_engine.repository import VisaEngineRepository

from .test_repository import _ENV, _insert_pack, _open_range, _pack_hash


@pytest.mark.asyncio
async def test_emergency_rollback_ceremony_end_to_end(repo: VisaEngineRepository) -> None:
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))

    # --- Step 1: bootstrap pack A (sequence 1), the ruleset we will later
    # need to "roll back" to. ------------------------------------------------
    pack_a = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_a,
        sequence=1,
        legal_period=legal,
        kid="key-a",
        signed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        note="RULES_V1_GOOD",
        payload_sha256=_pack_hash(1),
    )
    activation_a = await repo.activate_rule_pack(
        rule_pack_id=pack_a, activated_by="ops.ceremony", activation_reason="bootstrap"
    )

    # --- Step 2: pack B (sequence 2) supersedes A -- this is the "bad
    # deploy" the operator will need to walk back. --------------------------
    pack_b = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_b,
        sequence=2,
        legal_period=legal,
        kid="key-b",
        signed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        note="RULES_V2_BAD",
        payload_sha256=_pack_hash(2),
        previous_payload_sha256=_pack_hash(1),
    )
    activation_b = await repo.activate_rule_pack(
        rule_pack_id=pack_b, activated_by="ops.ceremony", activation_reason="deploy-v2"
    )
    assert activation_b != activation_a

    async with repo.db_pool.acquire() as conn:
        row_a = await conn.fetchrow(
            "SELECT upper(system_period) AS hi FROM visa_ruleset_activations WHERE id = $1",
            activation_a,
        )
        row_b = await conn.fetchrow(
            "SELECT lower(system_period) AS lo, upper(system_period) AS hi "
            "FROM visa_ruleset_activations WHERE id = $1",
            activation_b,
        )
    assert row_a["hi"] is not None  # A closed
    assert row_b["hi"] is None  # B open
    assert row_a["hi"] == row_b["lo"]  # adjacent, no gap

    # --- Step 3 (GUILT): the naive "rollback" -- reactivate pack A
    # verbatim -- MUST be rejected. Sequence 1 <= current head sequence 2. --
    with pytest.raises(asyncpg.exceptions.RaiseError, match="rollback rejected"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_a,
            activated_by="ops.ceremony",
            activation_reason="naive-rollback-attempt",
        )

    # B's activation must be completely untouched by the rejected attempt
    # (the whole call -- including the writer function's own close-step --
    # rolled back atomically).
    async with repo.db_pool.acquire() as conn:
        row_b_after = await conn.fetchrow(
            "SELECT upper(system_period) AS hi FROM visa_ruleset_activations WHERE id = $1",
            activation_b,
        )
        open_count_after_guilt = await conn.fetchval(
            "SELECT count(*) FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
    assert row_b_after["hi"] is None  # still open, untouched
    assert open_count_after_guilt == 1

    # --- Step 4 (INNOCENCE): the LEGITIMATE emergency rollback. The
    # operator re-signs pack A's RULE CONTENT as a NEW pack C, sequence 3,
    # chained forward from B's own payload_sha256 (the real current head --
    # never from A's hash, which is stale the instant B activated). ---------
    pack_c = uuid.uuid4()
    await _insert_pack(
        repo,
        pack_id=pack_c,
        sequence=3,
        legal_period=legal,
        kid="key-c-resigned-rollback",
        signed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        note="RULES_V1_GOOD",  # <-- content-identical to pack A: this IS the rollback
        payload_sha256=_pack_hash(3),
        previous_payload_sha256=_pack_hash(2),  # chains from B, the true current head
    )
    activation_c = await repo.activate_rule_pack(
        rule_pack_id=pack_c,
        activated_by="ops.ceremony",
        activation_reason="emergency-rollback-to-v1-content",
    )

    async with repo.db_pool.acquire() as conn:
        row_b_final = await conn.fetchrow(
            "SELECT upper(system_period) AS hi FROM visa_ruleset_activations WHERE id = $1",
            activation_b,
        )
        row_c = await conn.fetchrow(
            "SELECT lower(system_period) AS lo, upper(system_period) AS hi "
            "FROM visa_ruleset_activations WHERE id = $1",
            activation_c,
        )
        open_count_final = await conn.fetchval(
            "SELECT count(*) FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
        all_open_rows = await conn.fetch(
            "SELECT rule_pack_id FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )

    assert row_b_final["hi"] is not None  # B closed
    assert row_c["hi"] is None  # C open
    assert row_b_final["hi"] == row_c["lo"]  # adjacent close/open, no temporal gap
    assert open_count_final == 1  # exactly one open activation for the triple
    assert [r["rule_pack_id"] for r in all_open_rows] == [pack_c]

    # The engine's real read path resolves to C's content, and that content
    # is byte-identical to what pack A originally carried -- i.e. the
    # applicant-facing ruleset has genuinely been restored, even though the
    # ledger itself only ever moved FORWARD (sequence 1 -> 2 -> 3, never
    # backward).
    loaded = await repo.load_active_rule_pack(
        environment=_ENV,
        effective_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        observed_at=datetime.now(timezone.utc),
    )
    assert loaded is not None
    assert loaded["payload"]["note"] == "RULES_V1_GOOD"
    assert loaded["payload"]["sequence"] == 3  # NOT 1 -- the chain never goes backward

    print(
        "\nROLLBACK CEREMONY PROOF HOLDS: "
        f"activation_a={activation_a} activation_b={activation_b} activation_c={activation_c} "
        "-- naive reactivation of pack A (seq 1) was rejected while B (seq 2) was head; "
        "re-signing A's CONTENT as pack C (seq 3, chained from B's hash) was accepted; "
        "final state: exactly 1 open activation (C), B/C system_period adjacent with no gap, "
        "engine reads sequence 3 whose payload content equals the original sequence-1 ruleset."
    )
