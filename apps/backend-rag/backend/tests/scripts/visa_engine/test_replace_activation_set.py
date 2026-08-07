from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import asyncpg
import pytest

from backend.scripts.visa_engine import replace_activation_set as cli


def _replacement(
    lower: datetime, upper: datetime | None, *, sequence: int
) -> cli.ReplacementBundle:
    return cli.ReplacementBundle(
        raw={"payload": {}},
        verified=cast(Any, object()),
        insert_kwargs={
            "id": uuid.uuid4(),
            "environment": "TEST",
            "sequence": sequence,
            "legal_period": asyncpg.Range(lower, upper, lower_inc=True, upper_inc=False),
        },
    )


def test_normalize_coverage_merges_adjacency_and_preserves_explicit_gap() -> None:
    jan = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jun = datetime(2026, 6, 1, tzinfo=timezone.utc)
    jul = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert cli._normalize_disjoint_coverage([(jun, end), (jan, jun)], label="replacement") == (
        (jan, end),
    )
    assert cli._normalize_disjoint_coverage([(jan, jun), (jul, end)], label="replacement") == (
        (jan, jun),
        (jul, end),
    )


def test_normalize_coverage_rejects_overlap() -> None:
    jan = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jun = datetime(2026, 6, 1, tzinfo=timezone.utc)
    jul = datetime(2026, 7, 1, tzinfo=timezone.utc)
    with pytest.raises(SystemExit, match="overlap"):
        cli._normalize_disjoint_coverage(
            [(jan, jul), (jun, None)],
            label="replacement",
        )


@pytest.mark.parametrize(
    "content",
    [
        '{"protected": {}, "protected": {}}',
        '{"payload": {"sequence": 2, "sequence": 3}}',
        '{"payload": {"sequence": NaN}}',
    ],
)
def test_strict_bundle_json_rejects_duplicate_keys_and_non_finite_numbers(
    tmp_path: Path,
    content: str,
) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key|non-finite JSON number"):
        cli._load_strict_json(bundle)


def test_strict_bundle_json_enforces_size_and_set_count_limits(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (cli.MAX_SIGNED_BUNDLE_BYTES + 1))
    with pytest.raises(ValueError, match="2 MiB"):
        cli._load_strict_json(oversized)

    with pytest.raises(SystemExit, match="exceeds 64"):
        cli._load_and_verify_bundles(
            ["unused.json"] * (cli.MAX_REPLACEMENT_PACKS + 1),
            trust_store=cast(Any, object()),
            observed_at=datetime.now(timezone.utc),
        )


def test_parse_args_is_dry_run_and_uses_canonical_split_identity_envs() -> None:
    args = cli._parse_args(
        [
            "carry.json",
            "correction.json",
            "--actor",
            "ops.zero",
            "--reason",
            "legal-narrowing",
            "--current-sequence",
            "10",
            "--current-payload-sha256",
            "ab" * 32,
        ]
    )
    assert args.yes is False
    assert args.pack_database_url_env == "VISA_ENGINE_PACK_WRITER_DATABASE_URL"
    assert args.activation_database_url_env == "VISA_ENGINE_ACTIVATION_DATABASE_URL"


@pytest.mark.asyncio
async def test_dry_run_verifies_crypto_shape_without_opening_a_database_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jan = datetime(2026, 1, 1, tzinfo=timezone.utc)
    replacement = _replacement(jan, None, sequence=11)
    args = cli._parse_args(
        [
            "replacement.json",
            "--actor",
            "ops.zero",
            "--reason",
            "legal-narrowing",
            "--current-sequence",
            "10",
            "--current-payload-sha256",
            "ab" * 32,
        ]
    )
    validation_calls: list[tuple[int, bytes, str]] = []

    monkeypatch.setattr(cli.StaticTrustStore, "from_env", lambda: cast(Any, object()))
    monkeypatch.setattr(
        cli,
        "_load_and_verify_bundles",
        lambda *_args, **_kwargs: [replacement],
    )
    monkeypatch.setattr(
        cli,
        "_validate_chain",
        lambda _replacements, *, current_sequence, current_payload_sha256, engine_version: (
            validation_calls.append((current_sequence, current_payload_sha256, engine_version))
        ),
    )

    async def unexpected_create_pool(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry-run must not connect to a database")

    monkeypatch.setattr(cli.asyncpg, "create_pool", unexpected_create_pool)

    assert await cli.run(args) == 0
    assert validation_calls == [(10, bytes.fromhex("ab" * 32), "1.0.0")]


class _CapabilityPool:
    def __init__(
        self,
        *,
        principal: str,
        superuser: bool = False,
        server_version_num: int = 150000,
        table_privileges: set[tuple[str, str]] | None = None,
        function_privileges: set[str] | None = None,
    ) -> None:
        self.principal = principal
        self.superuser = superuser
        self.server_version_num = server_version_num
        self.table_privileges = table_privileges or set()
        self.function_privileges = function_privileges or set()

    async def fetchval(self, query: str, *args: object) -> object:
        if "session_user" in query and "rolsuper" not in query:
            return self.principal
        if "rolsuper" in query:
            return self.superuser
        if "current_setting('server_version_num')" in query:
            return self.server_version_num
        if "has_function_privilege" in query:
            return str(args[0]) in self.function_privileges
        if "has_table_privilege" in query:
            return (str(args[0]), str(args[1])) in self.table_privileges
        raise AssertionError(f"unexpected capability query: {query}")


@pytest.mark.asyncio
async def test_capability_preflight_accepts_separated_least_privilege_identities() -> None:
    pack_pool = cast(
        asyncpg.Pool,
        _CapabilityPool(
            principal="visa_pack_writer",
            table_privileges={
                ("public.visa_rule_packs", "SELECT"),
                ("public.visa_rule_packs", "INSERT"),
            },
        ),
    )
    activation_pool = cast(
        asyncpg.Pool,
        _CapabilityPool(
            principal="visa_activation_executor",
            function_privileges={cli.ACTIVATION_SET_FUNCTION},
        ),
    )
    pack_principal = await cli._assert_pack_writer_capability(pack_pool)
    activation_principal = await cli._assert_activation_capability(
        activation_pool,
        pack_writer_principal=pack_principal,
    )
    assert pack_principal == "visa_pack_writer"
    assert activation_principal == "visa_activation_executor"


@pytest.mark.asyncio
async def test_capability_preflight_rejects_combined_or_direct_table_identity() -> None:
    for activation_function in (cli.ACTIVATION_FUNCTION, cli.ACTIVATION_SET_FUNCTION):
        combined = cast(
            asyncpg.Pool,
            _CapabilityPool(
                principal="combined",
                table_privileges={
                    ("public.visa_rule_packs", "SELECT"),
                    ("public.visa_rule_packs", "INSERT"),
                },
                function_privileges={activation_function},
            ),
        )
        with pytest.raises(SystemExit, match="pack-writer identity"):
            await cli._assert_pack_writer_capability(combined)

    direct = cast(
        asyncpg.Pool,
        _CapabilityPool(
            principal="visa_activation_executor",
            table_privileges={("public.visa_ruleset_activations", "SELECT")},
            function_privileges={cli.ACTIVATION_SET_FUNCTION},
        ),
    )
    with pytest.raises(SystemExit, match="forbidden direct table"):
        await cli._assert_activation_capability(
            direct,
            pack_writer_principal="visa_pack_writer",
        )

    pg17_maintainer = cast(
        asyncpg.Pool,
        _CapabilityPool(
            principal="visa_activation_executor",
            server_version_num=170000,
            table_privileges={("public.visa_rule_packs", "MAINTAIN")},
            function_privileges={cli.ACTIVATION_SET_FUNCTION},
        ),
    )
    with pytest.raises(SystemExit, match="forbidden direct table"):
        await cli._assert_activation_capability(
            pg17_maintainer,
            pack_writer_principal="visa_pack_writer",
        )
