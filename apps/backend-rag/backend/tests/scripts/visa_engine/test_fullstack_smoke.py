from __future__ import annotations

from pathlib import Path

import pytest

from backend.scripts.visa_engine import fullstack_smoke


@pytest.mark.parametrize(
    "dsn",
    (
        "postgresql://nuzantara@127.0.0.1:5432/postgres",
        "postgres://test:test@localhost:5433/postgres",
        "postgresql://test@[::1]:5432/postgres?sslmode=disable",
    ),
)
def test_parse_safe_admin_dsn_accepts_only_explicit_loopback_admin_urls(dsn: str) -> None:
    parsed = fullstack_smoke._parse_safe_admin_dsn(dsn)
    assert parsed.path == "/postgres"


@pytest.mark.parametrize(
    "dsn",
    (
        "postgresql://readonly@db.internal/postgres",
        "postgresql://nuzantara@127.0.0.1:5432/nuzantara_test",
        "postgresql://127.0.0.1:5432/postgres",
        "https://nuzantara@127.0.0.1:5432/postgres",
        "postgresql://nuzantara@127.0.0.1:5432/postgres?target_session_attrs=read-write",
    ),
)
def test_parse_safe_admin_dsn_rejects_remote_existing_or_ambiguous_targets(dsn: str) -> None:
    with pytest.raises(ValueError):
        fullstack_smoke._parse_safe_admin_dsn(dsn)


def test_database_name_guard_refuses_existing_database_names() -> None:
    for unsafe_name in (
        "postgres",
        "nuzantara_test",
        "visa_oracle_smoke",
        "visa_oracle_smoke_bad-",
    ):
        with pytest.raises(ValueError):
            fullstack_smoke._assert_disposable_database_name(unsafe_name)


def test_migration_set_is_exact_and_forward_only() -> None:
    paths = fullstack_smoke._migration_paths(fullstack_smoke._backend_root())
    assert tuple(int(path.name.split("_", 1)[0]) for path in paths) == (
        250,
        251,
        252,
        253,
        254,
        255,
        256,
        257,
        261,
        262,
        263,
        264,
        265,
        266,
        267,
        268,
        276,
        281,
        289,
    )
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        forward, rollback = fullstack_smoke.split_migration_sql(text)
        assert forward.strip()
        assert rollback
        assert text.startswith(forward)
        assert len(forward) < len(text)
