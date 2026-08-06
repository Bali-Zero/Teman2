"""Read-only Visa Oracle production privilege and privacy preflight."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger("visa_engine.operational_preflight")

PREFLIGHT_DSN_ENV = "VISA_ENGINE_PREFLIGHT_DATABASE_URL"

ACTIVATION_FUNCTION = "public.visa_activate_rule_pack(uuid,text,text)"
PREPARE_IDEMPOTENCY_FUNCTION = (
    "public.prepare_visa_evaluate_idempotency_reservation(bytea,integer,text)"
)
RETENTION_FUNCTIONS = (
    "public.purge_visa_evaluate_idempotency(integer,text)",
    "public.purge_visa_decisions(integer,text)",
    "public.visa_idempotency_retention_evidence()",
    "public.visa_decision_retention_evidence()",
)
PRIVACY_FUNCTIONS = (
    "public.erase_visa_decision_for_dsr(uuid,text,text)",
    "public.set_visa_decision_legal_hold(uuid,boolean,text,text,text,text,"
    "timestamp with time zone)",
)
SENSITIVE_FUNCTIONS = (
    ACTIVATION_FUNCTION,
    PREPARE_IDEMPOTENCY_FUNCTION,
    *RETENTION_FUNCTIONS,
    *PRIVACY_FUNCTIONS,
)

SENSITIVE_TABLES = (
    "visa_rule_packs",
    "visa_ruleset_activations",
    "visa_decisions",
    "visa_decision_payloads",
    "visa_evaluate_idempotency",
    "visa_decision_retention_policies",
    "visa_decision_retention_batches",
    "visa_idempotency_retention_batches",
    "visa_decision_dsr_erasure_batches",
)
DIRECT_DML_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE")
CAPABILITY_ROLES = (
    "visa_pack_writer",
    "visa_activation_executor",
    "visa_policy_writer",
    "visa_retention_executor",
    "visa_privacy_operator",
)


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


def _function_allowlist(runtime_role: str) -> dict[str, frozenset[str]]:
    return {
        runtime_role: frozenset({PREPARE_IDEMPOTENCY_FUNCTION}),
        "visa_pack_writer": frozenset(),
        "visa_activation_executor": frozenset({ACTIVATION_FUNCTION}),
        "visa_policy_writer": frozenset(),
        "visa_retention_executor": frozenset(RETENTION_FUNCTIONS),
        "visa_privacy_operator": frozenset(PRIVACY_FUNCTIONS),
    }


def _direct_dml_allowlist(
    runtime_role: str,
) -> dict[str, frozenset[tuple[str, str]]]:
    return {
        runtime_role: frozenset(
            {
                ("visa_decisions", "INSERT"),
                ("visa_decision_payloads", "INSERT"),
                ("visa_evaluate_idempotency", "INSERT"),
                ("visa_evaluate_idempotency", "UPDATE"),
            }
        ),
        "visa_pack_writer": frozenset({("visa_rule_packs", "INSERT")}),
        "visa_activation_executor": frozenset(),
        "visa_policy_writer": frozenset(
            {
                ("visa_decision_retention_policies", "INSERT"),
                ("visa_decision_retention_policies", "UPDATE"),
            }
        ),
        "visa_retention_executor": frozenset(),
        "visa_privacy_operator": frozenset(),
    }


async def collect_preflight_checks(
    connection: asyncpg.Connection,
    *,
    runtime_role: str,
) -> tuple[PreflightCheck, ...]:
    """Collect read-only structural and least-privilege assertions."""

    checks: list[PreflightCheck] = []
    expected_roles = {
        "visa_ledger_owner": False,
        "visa_pack_writer": False,
        "visa_activation_executor": False,
        "visa_policy_writer": False,
        "visa_retention_executor": False,
        "visa_privacy_operator": False,
        runtime_role: True,
    }
    role_rows = await connection.fetch(
        "SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname = ANY($1::text[])",
        list(expected_roles),
    )
    roles = {str(row["rolname"]): row for row in role_rows}
    for role, login_expected in expected_roles.items():
        row = roles.get(role)
        ok = (
            row is not None
            and bool(row["rolcanlogin"]) is login_expected
            and not bool(row["rolsuper"])
        )
        checks.append(
            PreflightCheck(
                name=f"role:{role}",
                ok=ok,
                detail="present with expected LOGIN/superuser posture"
                if ok
                else "missing or unsafe",
            )
        )

    table_exists: dict[str, bool] = {}
    for table in SENSITIVE_TABLES:
        owner = await connection.fetchval(
            """
            SELECT pg_get_userbyid(class.relowner)
              FROM pg_class AS class
              JOIN pg_namespace AS namespace ON namespace.oid = class.relnamespace
             WHERE namespace.nspname = 'public' AND class.relname = $1
            """,
            table,
        )
        table_exists[table] = owner is not None
        checks.append(
            PreflightCheck(
                name=f"owner:public.{table}",
                ok=owner == "visa_ledger_owner",
                detail="owned by visa_ledger_owner"
                if owner == "visa_ledger_owner"
                else "wrong/missing owner",
            )
        )

    function_exists: dict[str, bool] = {}
    for signature in SENSITIVE_FUNCTIONS:
        owner = await connection.fetchval(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = to_regprocedure($1)",
            signature,
        )
        function_exists[signature] = owner is not None
        checks.append(
            PreflightCheck(
                name=f"owner:{signature}",
                ok=owner == "visa_ledger_owner",
                detail="owned by visa_ledger_owner"
                if owner == "visa_ledger_owner"
                else "wrong/missing owner",
            )
        )

    function_allowlist = _function_allowlist(runtime_role)
    for role, allowed_signatures in function_allowlist.items():
        for signature in SENSITIVE_FUNCTIONS:
            expected = signature in allowed_signatures
            actual = False
            if role in roles and function_exists.get(signature, False):
                actual = bool(
                    await connection.fetchval(
                        "SELECT has_function_privilege($1, $2, 'EXECUTE')",
                        role,
                        signature,
                    )
                )
            checks.append(
                PreflightCheck(
                    name=f"function:{role}:{signature}",
                    ok=actual is expected,
                    detail=f"EXECUTE={actual} expected={expected}",
                )
            )

    direct_dml_allowlist = _direct_dml_allowlist(runtime_role)
    for role, allowed_privileges in direct_dml_allowlist.items():
        for table in SENSITIVE_TABLES:
            for privilege in DIRECT_DML_PRIVILEGES:
                expected = (table, privilege) in allowed_privileges
                actual = False
                if role in roles and table_exists.get(table, False):
                    actual = bool(
                        await connection.fetchval(
                            "SELECT has_table_privilege($1, $2, $3)",
                            role,
                            f"public.{table}",
                            privilege,
                        )
                    )
                checks.append(
                    PreflightCheck(
                        name=f"table:{role}:public.{table}:{privilege}",
                        ok=actual is expected,
                        detail=f"{privilege}={actual} expected={expected}",
                    )
                )

    required_select_privileges = (
        (runtime_role, "visa_rule_packs"),
        (runtime_role, "visa_ruleset_activations"),
        (runtime_role, "visa_decisions"),
        (runtime_role, "visa_decision_payloads"),
        (runtime_role, "visa_evaluate_idempotency"),
        (runtime_role, "visa_decision_retention_policies"),
        ("visa_pack_writer", "visa_rule_packs"),
        ("visa_policy_writer", "visa_decision_retention_policies"),
    )
    for role, table in required_select_privileges:
        actual = False
        if role in roles and table_exists.get(table, False):
            actual = bool(
                await connection.fetchval(
                    "SELECT has_table_privilege($1, $2, 'SELECT')",
                    role,
                    f"public.{table}",
                )
            )
        checks.append(
            PreflightCheck(
                name=f"table:{role}:public.{table}:SELECT",
                ok=actual,
                detail=f"SELECT={actual} expected=True",
            )
        )

    for capability_role in CAPABILITY_ROLES:
        runtime_is_member = False
        if runtime_role in roles and capability_role in roles:
            runtime_is_member = bool(
                await connection.fetchval(
                    "SELECT pg_has_role($1, $2, 'MEMBER')",
                    runtime_role,
                    capability_role,
                )
            )
        checks.append(
            PreflightCheck(
                name=f"membership:{runtime_role}-not-{capability_role}",
                ok=not runtime_is_member,
                detail=f"runtime_member={runtime_is_member} expected=False",
            )
        )

    dual_capability_login = "roles-missing"
    if "visa_pack_writer" in roles and "visa_activation_executor" in roles:
        dual_capability_login = await connection.fetchval(
            """
            SELECT string_agg(role.rolname, ', ' ORDER BY role.rolname)
              FROM pg_roles AS role
             WHERE role.rolcanlogin
               AND pg_has_role(role.oid, 'visa_pack_writer', 'MEMBER')
               AND pg_has_role(role.oid, 'visa_activation_executor', 'MEMBER')
            """
        )
    checks.append(
        PreflightCheck(
            name="membership:no-pack-writer-activation-combination",
            ok=dual_capability_login is None,
            detail="no login combines both capabilities"
            if dual_capability_login is None
            else "one or more logins combine pack-write and activation",
        )
    )
    return tuple(checks)


async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get(args.database_url_env, "").strip()
    if not database_url:
        raise RuntimeError(f"${args.database_url_env} is required")
    connection = await asyncpg.connect(database_url)
    try:
        checks = await collect_preflight_checks(connection, runtime_role=args.runtime_role)
    finally:
        await connection.close()
    for check in checks:
        logger.info("preflight check=%s ok=%s detail=%s", check.name, check.ok, check.detail)
    failed = sum(not check.ok for check in checks)
    logger.info("preflight_summary total=%d failed=%d", len(checks), failed)
    return 0 if failed == 0 else 2


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url-env", default=PREFLIGHT_DSN_ENV)
    parser.add_argument("--runtime-role", default="backend_rag_v2")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
