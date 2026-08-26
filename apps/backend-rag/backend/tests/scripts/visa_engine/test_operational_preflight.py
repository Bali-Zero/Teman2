from __future__ import annotations

from typing import Any

import pytest

from backend.scripts.visa_engine import operational_preflight

RUNTIME_ROLE = "backend_rag_v2"

# Independent schema inventory: do not derive these from operational_preflight.
# A new governed table or SECURITY DEFINER capability requires a deliberate
# update here and in the preflight allowlists.
CANONICAL_SENSITIVE_FUNCTIONS = {
    "public.visa_activate_rule_pack(uuid,text,text)",
    "public.visa_replace_activation_set(uuid[],text,text)",
    "public.prepare_visa_evaluate_idempotency_reservation(bytea,integer,text)",
    "public.purge_visa_evaluate_idempotency(integer,text)",
    "public.purge_visa_decisions(integer,text)",
    "public.visa_idempotency_retention_evidence()",
    "public.visa_idempotency_key_usage_evidence()",
    "public.visa_decision_retention_evidence()",
    "public.erase_visa_decision_for_dsr(uuid,text,text)",
    "public.set_visa_decision_legal_hold(uuid,boolean,text,text,text,text,"
    "timestamp with time zone)",
    "public.bind_visa_evaluate_idempotency_retention_policy()",
    "public.bind_visa_decision_retention_policy()",
    "public.bind_visa_decision_payload_retention()",
}
CANONICAL_SENSITIVE_TABLES = {
    "visa_rule_packs",
    "visa_ruleset_activations",
    "visa_decisions",
    "visa_decision_payloads",
    "visa_source_records",
    "visa_evaluate_idempotency",
    "visa_decision_retention_policies",
    "visa_decision_legal_hold_events",
    "visa_decision_retention_batches",
    "visa_idempotency_retention_batches",
    "visa_decision_dsr_erasure_batches",
}


class FakePreflightConnection:
    """In-memory privilege catalog for exhaustive fail-closed preflight tests."""

    def __init__(self) -> None:
        role_names = {
            "visa_ledger_owner",
            *operational_preflight.CAPABILITY_ROLES,
            RUNTIME_ROLE,
        }
        self.roles = {
            role: {"rolname": role, "rolcanlogin": role == RUNTIME_ROLE, "rolsuper": False}
            for role in role_names
        }
        self.table_owners = dict.fromkeys(
            operational_preflight.SENSITIVE_TABLES, "visa_ledger_owner"
        )
        self.function_owners = dict.fromkeys(
            operational_preflight.SENSITIVE_FUNCTIONS, "visa_ledger_owner"
        )
        self.function_privileges = {
            (role, signature)
            for role, allowed in operational_preflight._function_allowlist(RUNTIME_ROLE).items()
            for signature in allowed
        }
        self.table_privileges = {
            (role, table, privilege)
            for role, allowed in operational_preflight._table_privilege_allowlist(
                RUNTIME_ROLE
            ).items()
            for table, privilege in allowed
        }
        self.memberships: set[tuple[str, str]] = set()
        self.dual_capability_login: str | None = None
        # Live bodies of the two binders migration 289 re-scopes. Default to
        # the POST-289 shape so the pre-existing least-privilege tests -- which
        # are about grants, not about 289 -- keep describing a healthy database.
        # The 289-specific tests below mutate this dict on purpose.
        # `fromkeys` shares one value across the keys, which is safe only
        # because the value is an immutable str and the tests below REBIND a
        # key rather than mutating what it points at.
        self.binder_bodies: dict[str, str] = dict.fromkeys(
            operational_preflight.SCOPE_BOUND_RETENTION_BINDERS,
            "BEGIN\n"
            "    SELECT id INTO STRICT policy\n"
            "      FROM public.visa_decision_retention_policies\n"
            "     WHERE environment = NEW.environment\n"
            "       AND policy_scope = 'VISA_DECISION'\n"
            "       AND effective_period @> NEW.evaluated_at\n"
            "     FOR SHARE;\n"
            "    RETURN NEW;\n"
            "END;",
        )

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if "FROM pg_catalog.pg_proc" in query and "prosrc" in query:
            requested = args[0]
            return [
                {"proname": name, "prosrc": self.binder_bodies[name]}
                for name in requested
                if name in self.binder_bodies
            ]
        if "FROM pg_roles WHERE rolname = ANY" not in query:
            raise AssertionError(f"unexpected fetch query: {query}")
        requested_roles = args[0]
        return [self.roles[role] for role in requested_roles if role in self.roles]

    async def fetchval(self, query: str, *args: Any) -> Any:
        if "current_setting('server_version_num')" in query:
            return 170000
        if "FROM pg_class AS class" in query:
            return self.table_owners.get(str(args[0]))
        if "FROM pg_proc" in query:
            return self.function_owners.get(str(args[0]))
        if "has_function_privilege" in query:
            return (str(args[0]), str(args[1])) in self.function_privileges
        if "has_table_privilege" in query:
            role = str(args[0])
            table = str(args[1]).removeprefix("public.")
            privilege = str(args[2]) if len(args) == 3 else "SELECT"
            return (role, table, privilege) in self.table_privileges
        if "SELECT pg_has_role" in query:
            return (str(args[0]), str(args[1])) in self.memberships
        if "string_agg" in query:
            return self.dual_capability_login
        raise AssertionError(f"unexpected fetchval query: {query}")


def _by_name(
    checks: tuple[operational_preflight.PreflightCheck, ...],
) -> dict[str, operational_preflight.PreflightCheck]:
    return {check.name: check for check in checks}


def test_preflight_inventory_matches_independently_frozen_schema_authority() -> None:
    assert set(operational_preflight.SENSITIVE_FUNCTIONS) == CANONICAL_SENSITIVE_FUNCTIONS
    assert set(operational_preflight.SENSITIVE_TABLES) == CANONICAL_SENSITIVE_TABLES
    assert set(operational_preflight.ALL_TABLE_PRIVILEGES) == {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "TRUNCATE",
        "REFERENCES",
        "TRIGGER",
        "MAINTAIN",
    }


@pytest.mark.asyncio
async def test_complete_least_privilege_catalog_passes() -> None:
    checks = await operational_preflight.collect_preflight_checks(
        FakePreflightConnection(),  # type: ignore[arg-type]
        runtime_role=RUNTIME_ROLE,
    )

    assert checks
    assert all(check.ok for check in checks), [check for check in checks if not check.ok]


@pytest.mark.asyncio
async def test_every_forbidden_sensitive_function_grant_fails_its_named_check() -> None:
    allowlist = operational_preflight._function_allowlist(RUNTIME_ROLE)
    for role, allowed in allowlist.items():
        for signature in operational_preflight.SENSITIVE_FUNCTIONS:
            if signature in allowed:
                continue
            connection = FakePreflightConnection()
            connection.function_privileges.add((role, signature))

            checks = _by_name(
                await operational_preflight.collect_preflight_checks(
                    connection,  # type: ignore[arg-type]
                    runtime_role=RUNTIME_ROLE,
                )
            )

            name = f"function:{role}:{signature}"
            assert checks[name].ok is False, (role, signature)


@pytest.mark.asyncio
async def test_missing_required_function_grant_fails_its_named_check() -> None:
    allowlist = operational_preflight._function_allowlist(RUNTIME_ROLE)
    for role, allowed in allowlist.items():
        for signature in allowed:
            connection = FakePreflightConnection()
            connection.function_privileges.remove((role, signature))

            checks = _by_name(
                await operational_preflight.collect_preflight_checks(
                    connection,  # type: ignore[arg-type]
                    runtime_role=RUNTIME_ROLE,
                )
            )

            name = f"function:{role}:{signature}"
            assert checks[name].ok is False, (role, signature)


@pytest.mark.asyncio
async def test_every_forbidden_sensitive_table_grant_fails_its_named_check() -> None:
    allowlist = operational_preflight._table_privilege_allowlist(RUNTIME_ROLE)
    for role in allowlist:
        for table in operational_preflight.SENSITIVE_TABLES:
            for privilege in operational_preflight.ALL_TABLE_PRIVILEGES:
                if (table, privilege) in allowlist[role]:
                    continue
                connection = FakePreflightConnection()
                connection.table_privileges.add((role, table, privilege))

                checks = _by_name(
                    await operational_preflight.collect_preflight_checks(
                        connection,  # type: ignore[arg-type]
                        runtime_role=RUNTIME_ROLE,
                    )
                )

                name = f"table:{role}:public.{table}:{privilege}"
                assert checks[name].ok is False, (role, table, privilege)


@pytest.mark.asyncio
async def test_every_required_sensitive_table_grant_is_enforced() -> None:
    allowlist = operational_preflight._table_privilege_allowlist(RUNTIME_ROLE)
    for role, required in allowlist.items():
        for table, privilege in required:
            connection = FakePreflightConnection()
            connection.table_privileges.remove((role, table, privilege))

            checks = _by_name(
                await operational_preflight.collect_preflight_checks(
                    connection,  # type: ignore[arg-type]
                    runtime_role=RUNTIME_ROLE,
                )
            )

            name = f"table:{role}:public.{table}:{privilege}"
            assert checks[name].ok is False, (role, table, privilege)


@pytest.mark.asyncio
async def test_runtime_membership_in_each_operational_capability_fails() -> None:
    for capability_role in operational_preflight.CAPABILITY_ROLES:
        connection = FakePreflightConnection()
        connection.memberships.add((RUNTIME_ROLE, capability_role))

        checks = _by_name(
            await operational_preflight.collect_preflight_checks(
                connection,  # type: ignore[arg-type]
                runtime_role=RUNTIME_ROLE,
            )
        )

        name = f"membership:{RUNTIME_ROLE}-not-{capability_role}"
        assert checks[name].ok is False, capability_role


@pytest.mark.asyncio
async def test_pack_writer_activation_combination_still_fails() -> None:
    connection = FakePreflightConnection()
    connection.dual_capability_login = "compromised_operator"

    checks = _by_name(
        await operational_preflight.collect_preflight_checks(
            connection,  # type: ignore[arg-type]
            runtime_role=RUNTIME_ROLE,
        )
    )

    assert checks["membership:no-pack-writer-activation-combination"].ok is False


async def _scoped_binder_check(connection: FakePreflightConnection):
    checks = _by_name(
        await operational_preflight.collect_preflight_checks(
            connection,  # type: ignore[arg-type]
            runtime_role=RUNTIME_ROLE,
        )
    )
    return checks["binder:retention-policy-scoped"]


@pytest.mark.asyncio
async def test_scoped_binder_check_passes_when_289_is_really_live() -> None:
    """INNOCENCE. The fake's default bodies carry the predicate 289 installs."""

    assert (await _scoped_binder_check(FakePreflightConnection())).ok is True


@pytest.mark.asyncio
@pytest.mark.parametrize("binder", operational_preflight.SCOPE_BOUND_RETENTION_BINDERS)
async def test_scoped_binder_check_fails_when_289_declined_for_either_binder(
    binder: str,
) -> None:
    """GUILT. Parameterised per binder: 289's catalog guard skips them one at a
    time, and a check that only noticed the FIRST unscoped binder would leave
    the second one silently broken -- which is the whole failure mode."""

    connection = FakePreflightConnection()
    # The pre-289 body: identical but for the missing scope predicate. This is
    # what the database really holds when the guard declines.
    connection.binder_bodies[binder] = (
        "BEGIN\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;"
    )

    check = await _scoped_binder_check(connection)
    assert check.ok is False
    assert binder in check.detail
    assert "visa_ledger_owner" in check.detail


@pytest.mark.asyncio
async def test_scoped_binder_check_fails_when_a_binder_is_absent_entirely() -> None:
    """A missing function must not read as a satisfied predicate. `.get()`
    returning None is exactly the shape that silently passes if unhandled."""

    connection = FakePreflightConnection()
    del connection.binder_bodies["bind_visa_decision_retention_policy"]

    check = await _scoped_binder_check(connection)
    assert check.ok is False
    assert "bind_visa_decision_retention_policy(absent)" in check.detail


@pytest.mark.asyncio
async def test_scoped_binder_check_is_not_satisfied_by_a_comment() -> None:
    """Scar #3, guard-over-match, in its UNDER-match twin: a body that merely
    MENTIONS the predicate in a comment is still scope-blind at runtime, and a
    bare-substring probe would call it healthy."""

    connection = FakePreflightConnection()
    connection.binder_bodies["bind_visa_decision_retention_policy"] = (
        "BEGIN\n"
        "    -- migration 289 would add: policy_scope = 'VISA_DECISION'\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;"
    )

    check = await _scoped_binder_check(connection)
    assert check.ok is False, (
        "a commented-out predicate satisfied the probe -- the check is matching "
        "the bare token, not the WHERE clause"
    )
