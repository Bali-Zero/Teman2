"""roles.yaml is a POLICY document, and both of its readers now load it strictly.

THE DEFECT. `yaml.safe_load` lets a duplicate top-level key win, in silence — last
one wins, no warning. `roles:` in
`apps/team-agent/mcp-wrapper/config/roles.yaml` is a mapping keyed by role name, so
appending five lines that repeat an existing role replaces it. Measured 2026-09-05 on
a scratch copy of the shipped file:

    get_allowed_tools("tax_consultant")            11 named tools  ->  ["*"]
    is_allowed("tax_consultant", "publish_article")   False        ->  True
    is_allowed("tax_consultant", "anything_at_all")   False        ->  True

That is privilege escalation whose diff reads as an appended block. It is not a claim
that the repo is breached — anyone who can append to the file can edit it outright.
What the silence defeats is REVIEW, and review is the control this actually relies on.

WHY THIS FILE LIVES UNDER apps/nuzantara-mcp/tests/ AND NOT BESIDE THE WRAPPER.
`apps/team-agent/mcp-wrapper` is named by NO workflow in `.github/workflows/` — its
existing `tests/test_permissions.py` and `tests/test_server.py` are run by no CI job
(superscar #2, filed separately; arming that tree is a workflow edit and a different
concern). `apps/nuzantara-mcp/tests` IS collected wholesale by tests.yml's "MCP Server
Tests" job, so putting BOTH readers' cases here arms them today. The file under attack
is the same one for both readers, which is what makes one battery the honest shape.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ROLES = REPO_ROOT / "apps" / "team-agent" / "mcp-wrapper" / "config" / "roles.yaml"
WRAPPER = REPO_ROOT / "apps" / "team-agent" / "mcp-wrapper"


def _yaml_strict():
    """The shared loader, by path — so the guilt cases can name its exact type.

    Registered under the SAME canonical module name the two readers use. Loading the
    file twice under two names produces two distinct StrictYAMLError classes, and
    `pytest.raises` on the wrong one fails while the cure works perfectly — measured
    while writing this battery, which is why the readers cache it too.
    """
    cached = sys.modules.get("nuzantara_yaml_strict")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "nuzantara_yaml_strict", REPO_ROOT / "scripts" / "lib" / "yaml_strict.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["nuzantara_yaml_strict"] = module
    spec.loader.exec_module(module)
    return module


STRICT_ERROR = _yaml_strict().StrictYAMLError

#: Five appended lines. Written as the attack, not as a paraphrase of it.
POISON = '\n  tax_consultant:\n    description: "appended"\n    tools:\n      - "*"\n'


def _permission_checker_cls():
    """Load the wrapper's checker by path — it is not an installed package."""
    if str(WRAPPER) not in sys.path:
        sys.path.insert(0, str(WRAPPER))
    module = importlib.import_module("permissions")
    return importlib.reload(module).PermissionChecker


def _poisoned(tmp_path: Path, extra: str = POISON) -> Path:
    target = tmp_path / "roles.yaml"
    target.write_text(ROLES.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return target


def _taxonomy_for(path: Path, monkeypatch) -> dict[str, list[str]]:
    """`ROLE_TAXONOMY` is built at IMPORT time, so the module is reloaded per case."""
    monkeypatch.setenv("NUZANTARA_MCP_ROLES_YAML", str(path))
    import nuzantara_mcp.auth as auth

    return importlib.reload(auth).ROLE_TAXONOMY


# ------------------------------------------------------------------ the attack itself


def test_the_escalation_is_real_under_plain_safe_load(tmp_path):
    """Pins WHAT IS BEING PREVENTED, not just that the cure fires.

    Without this, the guilt cases below would still pass if the poison stopped being
    a poison — a guard proved only against a payload nobody checked is still standing
    guard over nothing.
    """
    document = yaml.safe_load(_poisoned(tmp_path).read_text(encoding="utf-8"))
    assert document["roles"]["tax_consultant"]["tools"] == ["*"]
    shipped = yaml.safe_load(ROLES.read_text(encoding="utf-8"))
    assert shipped["roles"]["tax_consultant"]["tools"] != ["*"]
    assert len(shipped["roles"]["tax_consultant"]["tools"]) == 11


# --------------------------------------------------------- guilt: the wrapper's reader


def test_guilt_the_permission_checker_refuses_a_duplicated_role(tmp_path):
    checker_cls = _permission_checker_cls()
    with pytest.raises(STRICT_ERROR) as exc:
        checker_cls(str(_poisoned(tmp_path)))
    assert "duplicate key" in str(exc.value)
    assert "tax_consultant" in str(exc.value)


def test_guilt_no_checker_can_be_built_on_a_poisoned_file(tmp_path):
    """Refusing at load is only useful if no caller can route around it."""
    checker_cls = _permission_checker_cls()
    poisoned = _poisoned(tmp_path)
    for _ in range(2):
        with pytest.raises(STRICT_ERROR):
            checker_cls(str(poisoned))


def test_guilt_an_empty_roles_mapping_is_refused(tmp_path):
    """Not an escalation — a disarmed control that denies uniformly and looks correct."""
    target = tmp_path / "roles.yaml"
    target.write_text("roles: {}\n", encoding="utf-8")
    checker_cls = _permission_checker_cls()
    with pytest.raises(STRICT_ERROR, match="roles") as exc:
        checker_cls(str(target))
    assert "denies everything" in str(exc.value)


def test_guilt_an_alias_is_refused(tmp_path):
    """An anchor defined far from its use puts the governing value out of the reader's eye."""
    target = tmp_path / "roles.yaml"
    target.write_text(
        'wildcard: &w ["*"]\nroles:\n  intern:\n    tools: *w\n', encoding="utf-8"
    )
    checker_cls = _permission_checker_cls()
    with pytest.raises(STRICT_ERROR, match="alias"):
        checker_cls(str(target))


# ------------------------------------------------------------ guilt: the MCP's reader


def test_guilt_the_mcp_taxonomy_is_EMPTY_on_a_poisoned_file(tmp_path, monkeypatch):
    """auth.py must never raise — its contract is degrade-to-empty, which fails closed.

    The two readers therefore fail DIFFERENTLY on the same poisoned file, on purpose:
    the wrapper raises at construction, the MCP server boots with no taxonomy and
    denies every decorated tool. Both refuse; neither escalates.
    """
    assert _taxonomy_for(_poisoned(tmp_path), monkeypatch) == {}


def test_guilt_the_poisoned_file_never_yields_a_wildcard_role(tmp_path, monkeypatch):
    taxonomy = _taxonomy_for(_poisoned(tmp_path), monkeypatch)
    assert all("*" not in tools for tools in taxonomy.values())


def test_guilt_the_refusal_is_logged_with_the_offending_key(tmp_path, monkeypatch, caplog):
    """A control that fails closed and leaves no legible trace is only half a control."""
    with caplog.at_level("WARNING"):
        _taxonomy_for(_poisoned(tmp_path), monkeypatch)
    assert any("duplicate key" in r.getMessage() for r in caplog.records)
    assert any("tax_consultant" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------------------- innocence


def test_innocence_the_shipped_file_still_builds_a_working_checker():
    """A loader strict enough to refuse the file actually shipped would be useless."""
    checker = _permission_checker_cls()(str(ROLES))
    assert checker.is_allowed("visa_specialist", "get_visa_details") is True
    assert checker.is_allowed("visa_specialist", "regenerate_invoice") is False
    assert checker.is_allowed("admin", "anything_at_all") is True
    assert checker.is_allowed("tax_consultant", "get_compliance_alerts") is True
    assert checker.is_allowed("tax_consultant", "compose_article") is False
    assert checker.is_allowed("hacker", "get_visa_details") is False


def test_innocence_the_shipped_file_still_builds_a_populated_taxonomy(monkeypatch):
    taxonomy = _taxonomy_for(ROLES, monkeypatch)
    assert len(taxonomy) >= 4
    assert "get_visa_details" in taxonomy["visa_specialist"]


def test_innocence_both_readers_agree_on_the_shipped_file(monkeypatch):
    """One writer, two readers: they may fail differently, they must not READ differently."""
    taxonomy = _taxonomy_for(ROLES, monkeypatch)
    checker = _permission_checker_cls()(str(ROLES))
    for role, tools in taxonomy.items():
        assert checker.get_allowed_tools(role) == tools


def test_innocence_a_role_repeated_in_DIFFERENT_mappings_is_not_a_duplicate(tmp_path):
    """The over-match direction: `tools:` appears once per role and that is legal."""
    target = tmp_path / "roles.yaml"
    target.write_text(
        "roles:\n  a:\n    tools: [\"x\"]\n  b:\n    tools: [\"y\"]\n", encoding="utf-8"
    )
    checker = _permission_checker_cls()(str(target))
    assert checker.get_allowed_tools("a") == ["x"]
    assert checker.get_allowed_tools("b") == ["y"]


def test_this_battery_is_collected_by_the_MCP_test_job():
    """A guard nobody runs is superscar #2. Asserts the wiring, not the intent."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "cd apps/nuzantara-mcp" in workflow
    assert "test-coverage.sh" in workflow
    script = (REPO_ROOT / "apps" / "nuzantara-mcp" / "scripts" / "test-coverage.sh").read_text(
        encoding="utf-8"
    )
    assert script.rstrip().endswith("tests"), "the job must still collect tests/ wholesale"
