from types import SimpleNamespace

from backend.services.response.validator import ZantaraResponseValidator


def _context(mode: str = "short") -> SimpleNamespace:
    return SimpleNamespace(mode=mode)


def test_validate_dry_run_reports_violations_without_changing_text() -> None:
    validator = ZantaraResponseValidator(
        mode_config={"modes": {"short": {"max_sentences": 1}}},
        dry_run=True,
    )
    original = "Certainly, First answer. Second answer."

    result = validator.validate(original, _context())

    assert result.original == original
    assert result.validated == original
    assert result.was_modified is False
    assert any("Filler detected" in violation for violation in result.violations)
    assert any("Length exceeded" in violation for violation in result.violations)


def test_validate_applies_filler_removal_and_length_limit() -> None:
    validator = ZantaraResponseValidator(
        mode_config={"modes": {"short": {"max_sentences": 2}}},
        dry_run=False,
    )

    result = validator.validate("Of course, First answer. Second answer. Third answer.", _context())

    assert result.validated == "First answer. Second answer."
    assert result.was_modified is True
    assert any("Filler detected" in violation for violation in result.violations)
    assert any("Length exceeded" in violation for violation in result.violations)


def test_validate_removes_source_artifacts_and_excess_newlines() -> None:
    validator = ZantaraResponseValidator(mode_config={"modes": {"short": {}}}, dry_run=False)

    result = validator.validate("Answer. [Source: draft]\n\n\nNext line. ****", _context())

    assert "[Source:" not in result.validated
    assert "\n\n\n" not in result.validated
    assert "****" not in result.validated
    assert any("Artifact detected" in violation for violation in result.violations)


def test_validate_reports_missing_hook_when_mode_requires_it() -> None:
    validator = ZantaraResponseValidator(
        mode_config={"modes": {"chat": {"include_hook": True}}},
        dry_run=False,
    )

    result = validator.validate("This is ready.", _context("chat"))

    assert result.validated == "This is ready."
    assert "Missing hook" in result.violations


def test_validate_accepts_question_as_hook() -> None:
    validator = ZantaraResponseValidator(
        mode_config={"modes": {"chat": {"include_hook": True}}},
        dry_run=False,
    )

    result = validator.validate("Want me to prepare the next step?", _context("chat"))

    assert result.validated == "Want me to prepare the next step?"
    assert "Missing hook" not in result.violations
