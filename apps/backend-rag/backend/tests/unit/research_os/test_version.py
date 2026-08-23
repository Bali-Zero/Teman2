from __future__ import annotations

from research_os.version import (
    CompatibilityLevel,
    SemanticVersion,
    check_compatibility,
    compare_semantic_versions,
)


def test_semantic_version_helpers_parse_and_compare_versions() -> None:
    assert SemanticVersion.parse("1.2.3") == SemanticVersion(1, 2, 3)
    assert compare_semantic_versions("1.2.3", "1.3.0") == -1
    assert compare_semantic_versions("2.0.0", "1.9.9") == 1
    assert compare_semantic_versions("1.2.3", "1.2.3") == 0


def test_optional_field_addition_requires_minor_compatibility_level() -> None:
    old = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    new = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "note": {"type": "string"}},
        "required": ["name"],
    }

    report = check_compatibility(old, new)

    assert report.compatible is True
    assert report.level is CompatibilityLevel.MINOR
    assert report.breaking_reasons == ()


def test_enum_addition_is_breaking_even_when_old_values_remain() -> None:
    old = {"type": "string", "enum": ["green", "amber"]}
    new = {"type": "string", "enum": ["green", "amber", "red"]}

    report = check_compatibility(old, new)

    assert report.compatible is False
    assert report.level is CompatibilityLevel.MAJOR
    assert "enum addition at $: red" in report.breaking_reasons


def test_removal_and_required_field_change_are_breaking() -> None:
    old = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "note": {"type": "string"}},
        "required": ["name"],
    }
    new = {"type": "object", "properties": {"name": {"type": "string"}}, "required": []}

    report = check_compatibility(old, new)

    assert report.compatible is False
    assert "field removal at $.note" in report.breaking_reasons
    assert "required-field change at $: removed name" in report.breaking_reasons


def test_description_meaning_change_is_breaking() -> None:
    report = check_compatibility(
        {"type": "string", "description": "old meaning"},
        {"type": "string", "description": "new meaning"},
    )
    assert report.compatible is False
    assert "meaning change at $: schema keyword description changed" in report.breaking_reasons


def test_optional_nested_field_with_new_definition_remains_minor() -> None:
    old = {"type": "object", "properties": {}, "$defs": {}}
    new = {
        "type": "object",
        "properties": {"detail": {"anyOf": [{"$ref": "#/$defs/Detail"}, {"type": "null"}]}},
        "$defs": {"Detail": {"type": "object", "properties": {"value": {"type": "string"}}}},
    }
    report = check_compatibility(old, new)
    assert report.compatible is True
    assert report.level is CompatibilityLevel.MINOR
