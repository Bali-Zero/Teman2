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
        # Independent census for `definer:public-security-definer-ledger-owned`.
        # Deliberately NOT derived from SENSITIVE_FUNCTIONS: the whole point of
        # that check is that it reads the catalog and consults no list, so a
        # fixture built from the module's own list would quietly re-introduce
        # the coupling the check exists to remove. These three signatures were
        # copied from the production census of 2026-08-30 (21 rows, all
        # ledger-owned), in the `proname(identity args)` shape the shipped
        # query really returns.
        self.security_definer_functions: dict[str, str] = {
            "bind_garuda_magic_link_token_retention_policy()": "visa_ledger_owner",
            "purge_garuda_voa_checks(p_limit integer, p_requested_by text)": (
                "visa_ledger_owner"
            ),
            "visa_activate_rule_pack(p_rule_pack_id uuid, p_activated_by text, "
            "p_activation_reason text)": "visa_ledger_owner",
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
        if "prosecdef" in query:
            return [
                {"signature": signature, "owner": owner}
                for signature, owner in sorted(self.security_definer_functions.items())
            ]
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


# ---------------------------------------------------------------------------
# Adversarial coverage of the two pure helpers behind `binder:retention-policy-scoped`.
#
# NOTE (2026-08-27): as of this file's writing the live implementation exposes
# `operational_preflight._noise_mask(body) -> list[bool]` (a per-character noise
# mask covering `--`/`/* */` comments and `'...'`/`$tag$...$tag$` string
# literals) plus `operational_preflight._active_lookups_are_scoped(body) -> bool`
# built on top of it. An EARLIER shape of this same guard, seen mid-session
# while these tests were being written, instead exposed a
# `_strip_sql_noise(body) -> str` that BLANKED string literals into spaces
# before regex-matching `policy_scope = 'VISA_DECISION'` against the blanked
# copy -- which is self-defeating (the predicate's own `'VISA_DECISION'` is a
# string literal, so blanking it made every genuinely-scoped body register as
# unscoped: reproduced live, `_active_lookups_are_scoped` returned False on the
# exact healthy default body in `FakePreflightConnection.binder_bodies`). That
# function no longer exists in this file. These tests exercise the CURRENT
# mask-based pair; if `_strip_sql_noise` reappears, its false-red-by-design
# defect needs its own case, not a silent revert of this file.
def _lookup_and_predicate_share_a_line() -> str:
    return (
        "BEGIN\n"
        "    SELECT id INTO STRICT policy FROM public.visa_decision_retention_policies"
        " WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION' AND"
        " effective_period @> NEW.evaluated_at FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;"
    )


def _predicate_exactly_at_window_boundary(distance: int) -> str:
    """Predicate `distance` lines above the lookup. `distance == _SCOPE_WINDOW_LINES`
    (10) must still count (`<=`); `distance == 11` must not."""

    lines = ["BEGIN", "    IF policy_scope = 'VISA_DECISION' THEN NULL; END IF;"]
    for i in range(distance - 1):
        lines.append(f"    PERFORM pg_sleep(0); -- pad {i}")
    lines.append(
        "    SELECT id INTO STRICT policy FROM public.visa_decision_retention_policies"
        " WHERE environment = NEW.environment AND effective_period @> NEW.evaluated_at"
        " FOR SHARE;"
    )
    lines.append("    RETURN NEW;")
    lines.append("END;")
    return "\n".join(lines)


def _count_satisfied_but_second_lookup_isolated() -> str:
    """2 lookups, 2 predicates (satisfies the COUNT rule: predicates >= lookups),
    but BOTH predicates sit next to the FIRST lookup and neither is within
    `_SCOPE_WINDOW_LINES` of the second. If the guard only checked the total
    count it would wrongly call this scoped; it must also check per-lookup
    proximity (Rule 2 in `_active_lookups_are_scoped`)."""

    lines = [
        "BEGIN",
        "    SELECT id INTO STRICT policy",
        "      FROM public.visa_decision_retention_policies",
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'",
        "       AND effective_period @> NEW.evaluated_at",
        "     FOR SHARE;",
        "    IF policy_scope = 'VISA_DECISION' THEN NULL; END IF;",
    ]
    lines.extend(f"    PERFORM pg_sleep(0); -- pad {i}" for i in range(15))
    lines.extend(
        [
            "    SELECT id INTO STRICT other",
            "      FROM public.visa_decision_retention_policies",
            "     WHERE environment = NEW.environment",
            "       AND effective_period @> NEW.evaluated_at",
            "     FOR SHARE;",
            "    RETURN NEW;",
            "END;",
        ]
    )
    return "\n".join(lines)


_ADVERSARIAL_SCOPE_CASES: tuple[tuple[str, str, bool], ...] = (
    (
        "false_green_predicate_inside_dollar_quoted_raise_notice",
        "BEGIN\n"
        "    RAISE NOTICE $msg$policy_scope = 'VISA_DECISION'$msg$;\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "false_red_dashdash_in_string_literal_before_real_predicate",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy, 'range x--y' AS debug_note\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND policy_scope = 'VISA_DECISION'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "false_red_dashdash_string_and_predicate_share_a_line",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'"
        " AND notes = 'range x--y'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "escaped_doubled_single_quote_then_dashdash_then_real_predicate",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy, 'it''s -- not a comment' AS note\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "dollar_quote_nested_different_tags_hides_predicate",
        "BEGIN\n"
        "    RAISE NOTICE $outer$ inner text $inner$ policy_scope = 'VISA_DECISION'"
        " $inner$ still outer $outer$;\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "anonymous_dollar_quote_hides_predicate",
        "BEGIN\n"
        "    RAISE NOTICE $$policy_scope = 'VISA_DECISION'$$;\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "multiline_block_comment_hides_predicate",
        "BEGIN\n"
        "    /* TODO: eventually add\n"
        "       policy_scope = 'VISA_DECISION'\n"
        "       here */\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "dashdash_inside_dollar_quoted_string_does_not_start_a_comment",
        "BEGIN\n"
        "    RAISE NOTICE $msg$ this -- looks like a comment $msg$;\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "unclosed_dollar_quote_tail_still_scoped",
        "BEGIN\n"
        "    RAISE NOTICE $unterminated$ this never closes\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "unclosed_dollar_quote_tail_still_genuinely_unscoped",
        "BEGIN\n"
        "    RAISE NOTICE $unterminated$ whoops forgot to close\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "two_lookups_only_one_carries_the_predicate",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    SELECT id INTO STRICT other_policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    ("zero_lookups_is_vacuously_scoped", "BEGIN\n    RETURN NEW;\nEND;", True),
    ("empty_body_is_vacuously_scoped", "", True),
    (
        "predicate_exactly_at_window_boundary_ten_lines_still_counts",
        _predicate_exactly_at_window_boundary(10),
        True,
    ),
    (
        "predicate_one_line_past_window_boundary_does_not_count",
        _predicate_exactly_at_window_boundary(11),
        False,
    ),
    (
        "new_dot_effective_period_alone_is_not_a_lookup",
        "BEGIN\n"
        "    IF NEW.effective_period @> NEW.evaluated_at THEN\n"
        "        RETURN NEW;\n"
        "    END IF;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "word_boundary_excludes_suffixed_identifier",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE old_effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        True,
    ),
    (
        "predicate_faked_inside_escaped_string_literal_does_not_count",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy, 'debug: policy_scope = ''VISA_DECISION''"
        " fake' AS note\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "one_predicate_cannot_scope_two_close_lookups",
        "BEGIN\n"
        "    SELECT id INTO STRICT policy\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment AND policy_scope = 'VISA_DECISION'\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    SELECT id INTO STRICT other\n"
        "      FROM public.visa_decision_retention_policies\n"
        "     WHERE environment = NEW.environment\n"
        "       AND effective_period @> NEW.evaluated_at\n"
        "     FOR SHARE;\n"
        "    RETURN NEW;\n"
        "END;",
        False,
    ),
    (
        "count_satisfied_but_second_lookup_isolated_beyond_window",
        _count_satisfied_but_second_lookup_isolated(),
        False,
    ),
    (
        "predicate_and_lookup_share_the_same_line",
        _lookup_and_predicate_share_a_line(),
        True,
    ),
)


@pytest.mark.parametrize(
    "body, expected",
    [(body, expected) for _, body, expected in _ADVERSARIAL_SCOPE_CASES],
    ids=[case_id for case_id, _, _ in _ADVERSARIAL_SCOPE_CASES],
)
def test_active_lookups_are_scoped_resists_adversarial_bodies(
    body: str, expected: bool
) -> None:
    assert operational_preflight._active_lookups_are_scoped(body) is expected


def test_noise_mask_covers_line_comment_but_not_the_newline_or_surrounding_code() -> None:
    body = "SELECT 1; -- a comment\nSELECT 2;"
    mask = operational_preflight._noise_mask(body)
    assert len(mask) == len(body)
    dash_dash = body.index("--")
    newline = body.index("\n")
    assert all(mask[dash_dash:newline])  # the whole comment body is masked
    assert mask[newline] is False  # the newline itself ends the comment
    assert not any(mask[: dash_dash - 1])  # "SELECT 1;" before it is real code
    assert not any(mask[newline + 1 :])  # "SELECT 2;" after it is real code


def test_noise_mask_covers_a_single_quoted_string_including_its_quotes() -> None:
    body = "before 'a literal' after"
    mask = operational_preflight._noise_mask(body)
    start = body.index("'")
    end = body.rindex("'")
    assert all(mask[start : end + 1])
    assert not any(mask[:start])
    assert not any(mask[end + 1 :])


# ---------------------------------------------------------------------------
# definer:public-security-definer-ledger-owned — the list-free floor.
#
# The check next to it, `owner:{signature}`, reads `SENSITIVE_FUNCTIONS`. That
# list is why migration 285 shipped a SECURITY DEFINER trigger owned by the
# runtime role and no preflight went red: nobody added the new function to it.
# These cases assert the replacement is genuinely list-free — the fixture below
# introduces a function that appears in NO module constant, and the check must
# still catch it.
CHECK_NAME = "definer:public-security-definer-ledger-owned"


async def _definer_check(connection: FakePreflightConnection):
    checks = _by_name(
        await operational_preflight.collect_preflight_checks(
            connection,  # type: ignore[arg-type]
            runtime_role=RUNTIME_ROLE,
        )
    )
    return checks[CHECK_NAME]


@pytest.mark.asyncio
async def test_definer_owner_check_passes_when_every_definer_is_ledger_owned() -> None:
    """INNOCENCE. The fake's census is the healthy production shape."""

    check = await _definer_check(FakePreflightConnection())
    assert check.ok is True, check.detail
    assert "3" in check.detail, check.detail


@pytest.mark.asyncio
async def test_definer_owner_check_catches_a_function_named_in_no_list() -> None:
    """GUILT, and the whole reason this check exists.

    `garuda_new_thing_nobody_listed` is in no module constant — not
    `SENSITIVE_FUNCTIONS`, not `RETENTION_BINDING_TRIGGER_FUNCTIONS`, not
    `CANONICAL_SENSITIVE_FUNCTIONS` in this file. It is migration 285's
    situation reproduced: a brand-new SECURITY DEFINER function left owned by
    the runtime role. A list-driven check cannot see it; this one must.
    """

    connection = FakePreflightConnection()
    connection.security_definer_functions[
        "garuda_new_thing_nobody_listed(p_limit integer)"
    ] = RUNTIME_ROLE

    check = await _definer_check(connection)
    assert check.ok is False, (
        "a SECURITY DEFINER function owned by the runtime role passed the floor "
        "— the check is still reading a list, not the catalog"
    )
    assert "garuda_new_thing_nobody_listed(p_limit integer)" in check.detail
    assert RUNTIME_ROLE in check.detail


@pytest.mark.asyncio
async def test_definer_owner_check_catches_the_exact_285_regression() -> None:
    """The concrete incident, by name: `bind_garuda_magic_link_token_retention_
    policy` owned by `backend_rag_v2` is the state in which
    `POST /api/visa/voa/auth/magic-links` answered 500 to every call."""

    connection = FakePreflightConnection()
    connection.security_definer_functions[
        "bind_garuda_magic_link_token_retention_policy()"
    ] = RUNTIME_ROLE

    check = await _definer_check(connection)
    assert check.ok is False
    assert "bind_garuda_magic_link_token_retention_policy()" in check.detail


@pytest.mark.asyncio
async def test_definer_owner_check_reports_every_offender_not_only_the_first() -> None:
    """Migration 281/286 left FIVE functions behind at once. A check that named
    only the first would send an operator round the loop five times, and a
    reviewer reading the log would think one ALTER closed it."""

    connection = FakePreflightConnection()
    for signature in (
        "purge_garuda_voa_checks(p_limit integer, p_requested_by text)",
        "purge_garuda_voa_check_results(p_limit integer, p_requested_by text)",
        "garuda_voa_check_retention_evidence()",
    ):
        connection.security_definer_functions[signature] = RUNTIME_ROLE

    check = await _definer_check(connection)
    assert check.ok is False
    for signature in (
        "purge_garuda_voa_checks(p_limit integer, p_requested_by text)",
        "purge_garuda_voa_check_results(p_limit integer, p_requested_by text)",
        "garuda_voa_check_retention_evidence()",
    ):
        assert signature in check.detail, signature
    # 3 of 5: the fixture seeds three healthy functions, of which
    # `purge_garuda_voa_checks` is one of the three re-owned above.
    assert "3 of 5" in check.detail, check.detail


@pytest.mark.asyncio
async def test_definer_owner_check_survives_an_empty_census_without_lying() -> None:
    """An empty catalog read must be legible, not a silent green.

    It is deliberately NOT a failure: a legitimately fresh database has no
    governed functions yet, and inventing a second alarm there would make this
    check the boy who cried wolf. But the count has to reach the log, because
    "0 functions, all correctly owned" and "21 functions, all correctly owned"
    must not print the same sentence.
    """

    connection = FakePreflightConnection()
    connection.security_definer_functions.clear()

    check = await _definer_check(connection)
    assert check.ok is True
    assert "0 SECURITY DEFINER function(s)" in check.detail


def test_definer_violations_helper_is_indifferent_to_every_module_list() -> None:
    """The helper's verdict must depend on the OWNER column alone.

    A row whose signature happens to sit in `SENSITIVE_FUNCTIONS` gets no
    amnesty, and one that sits in no list gets no free pass — otherwise the
    floor has quietly grown a list again.
    """

    rows = [
        {"signature": "visa_activate_rule_pack(p_id uuid)", "owner": RUNTIME_ROLE},
        {"signature": "something_entirely_new()", "owner": "visa_ledger_owner"},
    ]
    violations = operational_preflight._security_definer_violations(rows)

    assert violations == [f"visa_activate_rule_pack(p_id uuid) owned by {RUNTIME_ROLE}"]


def test_definer_census_sql_selects_on_prosecdef_and_scopes_to_public() -> None:
    """The three properties the shipped query may not lose.

    Read off the constant rather than re-derived: a census that dropped
    `prosecdef` would flag every ordinary function in the schema (a permanent
    false red), and one that dropped the namespace filter would reach into
    `pg_catalog` and flag Postgres's own definer functions, which no migration
    of ours may ever own.
    """

    sql = operational_preflight.SECURITY_DEFINER_CENSUS_SQL
    assert "proc.prosecdef" in sql
    assert "namespace.nspname = 'public'" in sql
    assert "pg_get_userbyid(proc.proowner)" in sql
