"""Safety tests for the disposable portal QA seeder."""

import pytest

from backend.scripts.seed_portal_qa import (
    validate_qa_database_url,
    validate_synthetic_email,
    validate_synthetic_pin,
)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://portal_qa@localhost:55433/my_portal_qa",
        "postgresql://portal_qa@127.0.0.1:55433/my_portal_qa_run_1",
        "postgres://portal_qa@[::1]:55433/my_portal_qa_test",
    ],
)
def test_validate_qa_database_url_accepts_disposable_loopback_targets(
    database_url: str,
) -> None:
    assert validate_qa_database_url(database_url).startswith("my_portal_qa")


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://readonly@example.internal/nuzantara",
        "postgresql://portal_qa@127.0.0.1:55433/nuzantara_dev",
        "postgresql://portal_qa@127.0.0.1:55433/nuzantara_prod",
        "sqlite:///my_portal_qa",
    ],
)
def test_validate_qa_database_url_rejects_unsafe_targets(database_url: str) -> None:
    with pytest.raises(ValueError):
        validate_qa_database_url(database_url)


def test_validate_synthetic_email_accepts_reserved_example_domain() -> None:
    assert validate_synthetic_email("ACTIVE-CLIENT@example.com") == ("active-client@example.com")


@pytest.mark.parametrize(
    "email",
    [
        "active-client@my-portal-qa.example.test",
        "active-client@balizero.com",
        "active-client@qa.example.com",
        "missing-at-sign",
    ],
)
def test_validate_synthetic_email_rejects_non_fixture_domains(email: str) -> None:
    with pytest.raises(ValueError, match="example.com"):
        validate_synthetic_email(email)


@pytest.mark.parametrize("pin", ["1234", " 12345 ", "123456"])
def test_validate_synthetic_pin_accepts_registration_contract(pin: str) -> None:
    assert validate_synthetic_pin(pin) == pin.strip()


@pytest.mark.parametrize("pin", ["123", "1234567", "12ab", ""])
def test_validate_synthetic_pin_rejects_non_registration_values(pin: str) -> None:
    with pytest.raises(ValueError, match="4-6 digits"):
        validate_synthetic_pin(pin)
