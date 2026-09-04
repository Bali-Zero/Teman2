"""Guilt + innocence for the strict policy-YAML loader, and for the PII redactor on it.

THE DEFECT. `yaml.safe_load` lets a DUPLICATE top-level key win, in silence — no warning,
no error, last one wins. Measured 2026-09-04 on a copy of the real rules file: appending
two lines (`pass1: []`) at the end took the redactor from 18 NPWP / KTP / passport /
bank-account / OSINT patterns to zero, while passes 2-4 kept running, so the redactor
emitted output that looked entirely normal and redacted nothing. That is the Legge 2 /
UU PDP output boundary, defeated by a diff that reads as one added line.

WHAT THESE TESTS PIN, in the two directions superscar #3 requires:

  guilt      a duplicate key, an alias, a merge key, an empty or non-mapping document,
             and unparseable YAML are each REFUSED — and the redactor then fails CLOSED,
             raising instead of returning a redactor that redacts nothing.
  innocence  the REAL rules file still loads, still carries all 18 pass1 rules, and still
             redacts a sample; nested mappings and lists still construct normally.

The innocence half is not decoration: a loader strict enough to refuse the real file would
be trivially "safe" and completely useless, and the same over-match is why this loader is
pointed only at policy documents rather than at all 76 YAML call sites in this repo.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES = REPO_ROOT / "agent-library" / "config" / "redaction-rules.yaml"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "yaml_strict_under_test", str(REPO_ROOT / "scripts" / "lib" / "yaml_strict.py")
)
assert _spec is not None and _spec.loader is not None
ys = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ys)

from scripts._redact_pii import RedactionError, Redactor, load_config  # noqa: E402


def _poisoned(tmp_path: Path, extra: str) -> Path:
    """The real rules file with `extra` appended — the exact shape of the attack."""
    target = tmp_path / "redaction-rules.yaml"
    target.write_text(RULES.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return target


# --------------------------------------------------------------------- loader, guilt


def test_guilt_a_duplicate_top_level_key_is_refused(tmp_path):
    """The defect itself: PyYAML would take the appended one and say nothing."""
    with pytest.raises(ys.StrictYAMLError) as exc:
        ys.load_policy(_poisoned(tmp_path, "\npass1: []\n"))
    assert "duplicate key" in str(exc.value)
    assert "pass1" in str(exc.value)


def test_guilt_an_alias_is_refused():
    """An anchor defined far from its use puts the governing value out of the reader's eye."""
    with pytest.raises(ys.StrictYAMLError):
        ys.load_policy_text("anchor: &a [1]\nrules: *a\n")


def test_guilt_a_merge_key_is_refused():
    """Written with an INLINE mapping, so it reaches the merge-key branch and not the alias one."""
    with pytest.raises(ys.StrictYAMLError) as exc:
        ys.load_policy_text("child:\n  <<: {k: 1}\n  j: 2\n")
    assert "merge key" in str(exc.value)


def test_guilt_an_empty_or_non_mapping_document_is_refused():
    """`{}` is the shape that flows on looking normal; it must not be a success."""
    for text in ("", "- a\n- b\n", "just a string\n"):
        with pytest.raises(ys.StrictYAMLError):
            ys.load_policy_text(text)


def test_guilt_unparseable_yaml_raises_the_named_error_not_a_yaml_error():
    """Callers catch one error type; a leaked `yaml.YAMLError` would slip past them."""
    with pytest.raises(ys.StrictYAMLError):
        ys.load_policy_text("a: [\n")


def test_guilt_an_unreadable_path_is_refused_not_defaulted(tmp_path):
    with pytest.raises(ys.StrictYAMLError):
        ys.load_policy(tmp_path / "does-not-exist.yaml")


# ----------------------------------------------------------------- loader, innocence


def test_innocence_the_real_rules_file_loads_unchanged():
    """A loader that refused the file actually shipped would be safe and useless."""
    document = ys.load_policy(RULES)
    assert len(document["pass1"]) == 18
    assert {"pass1", "pass2_team_first", "pass3_generic", "pass4_dynamic", "gate"} <= set(document)


def test_innocence_ordinary_nesting_and_lists_still_construct():
    """Overriding the mapping constructor must not break recursive construction."""
    assert ys.load_policy_text("a:\n  b:\n    c: [1, 2]\n  d: {e: f}\n") == {
        "a": {"b": {"c": [1, 2]}, "d": {"e": "f"}}
    }


def test_innocence_a_repeated_key_in_DIFFERENT_mappings_is_not_a_duplicate():
    """The over-match direction: `pattern:` appears once per rule and that is legal."""
    assert ys.load_policy_text("rules:\n  - {id: a, pattern: x}\n  - {id: b, pattern: y}\n") == {
        "rules": [{"id": "a", "pattern": "x"}, {"id": "b", "pattern": "y"}]
    }


# ------------------------------------------------------------------ redactor, guilt


def test_guilt_the_redactor_fails_CLOSED_on_poisoned_rules(tmp_path):
    """The whole point: not "redacts nothing and looks normal" but "refuses and says so"."""
    with pytest.raises(RedactionError) as exc:
        load_config(_poisoned(tmp_path, "\npass1: []\n"))
    assert "ambiguous" in str(exc.value)


def test_guilt_no_redactor_can_be_built_on_poisoned_rules(tmp_path):
    """`load_config` raising is only useful if no caller can route around it."""
    poisoned = _poisoned(tmp_path, "\npass1: []\n")
    with pytest.raises(RedactionError):
        Redactor(load_config(poisoned), {})


def test_guilt_an_empty_pass1_is_a_disarmed_control_not_a_permissive_one(tmp_path):
    """A rules file that is UNAMBIGUOUS and still carries no PII patterns.

    Strict loading closes the append; it does not close a file edited in place to have an
    empty `pass1`. That edit reads as a real diff, but the failure mode is the same one —
    passes 2-4 keep running and the output looks normal — so it is refused too.
    """
    target = tmp_path / "redaction-rules.yaml"
    target.write_text(
        "pass1: []\npass2_team_first: []\npass3_generic: []\npass4_dynamic: []\ngate: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(RedactionError) as exc:
        load_config(target)
    assert "disarmed control" in str(exc.value)


# --------------------------------------------------------------- redactor, innocence


def test_innocence_the_shipped_rules_still_build_a_working_redactor():
    config = load_config()
    assert len(config.pass1) == 18
    redactor = Redactor(config, {})
    # A SYNTHETIC NPWP-shaped number, never a real one: a test fixture is an artifact
    # that gets committed, and Legge 2 binds it exactly like any other output. The
    # padding is required rather than decorative — the redactor's own `gate` refuses to
    # emit fewer than min_remaining_chars, so a short sample fails closed and would
    # prove nothing about the rules.
    fake_npwp = "09.254.294.5-403.000"
    sample = (
        "Catatan internal untuk berkas klien: nomor pajak tercatat "
        f"{fake_npwp} dan berkas pendukung sudah diterima lengkap oleh tim, "
        "menunggu verifikasi akhir sebelum pengajuan diteruskan."
    )
    out = redactor.redact(sample)
    assert isinstance(out, str)
    assert fake_npwp not in out, "the shipped rules must still redact an NPWP-shaped number"


def test_this_test_file_is_listed_in_the_immune_enforcement_battery():
    """A guard nobody runs is superscar #2. This asserts the wiring, not the intent."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "immune-enforcement.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/tests/test_yaml_strict_policy_loader.py" in workflow
