"""Tests for scripts/lint_avatar_url_validators.py — the avatar_url data:-URI
model guard (a NEW static CI guard so a fifth unguarded Pydantic model can
never be born silently, cicatrix-superscar.md #2/#3).

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package — same pattern as test_pending_arms_report.py / test_secrets_permissions_audit.py.

Guilt+innocence discipline (superscar #3 "Guard-over-match"): every accepted
"guarded" shape gets an INNOCENCE test proving it is NOT flagged, and the bare
unguarded shape gets a GUILT test proving it IS. The cross-file type-alias
case gets its own dedicated test because it is the actual live shape this
repo's shared `AvatarUrl` guard took (crm_utils.py) — a same-file-only alias
resolver would silently pass right over it (verified live during this task:
the first draft of this scanner false-flagged all four real guarded models
as unguarded until cross-file alias resolution was added).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "lint_avatar_url_validators.py"
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend-rag" / "backend"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_avatar_url_validators", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_module()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _keys(result) -> set[str]:
    return {f.key for f in result.findings}


def _finding(result, class_name: str):
    matches = [f for f in result.findings if f.class_name == class_name]
    assert len(matches) == 1, f"expected exactly one {class_name}, got {matches}"
    return matches[0]


# ---------------------------------------------------------------------------
# 1. GUILT — bare avatar_url field, no validator at all
# ---------------------------------------------------------------------------


def test_guilt_bare_field_is_unguarded(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "bad_model.py",
        "from pydantic import BaseModel\n\n"
        "class LeakyModel(BaseModel):\n"
        "    avatar_url: str | None = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "LeakyModel")
    assert not finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_UNGUARDED

    guarded, allowlisted, unguarded = lint.classify(result.findings, {})
    assert len(unguarded) == 1
    assert unguarded[0].class_name == "LeakyModel"


def test_guilt_main_strict_exits_1_on_unguarded(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "bad_model.py",
        "from pydantic import BaseModel\n\n"
        "class LeakyModel(BaseModel):\n"
        "    avatar_url: str | None = None\n",
    )

    assert lint.main(["--root", str(tmp_path)]) == 0  # no --strict: report-only
    assert lint.main(["--root", str(tmp_path), "--strict"]) == 1


# ---------------------------------------------------------------------------
# 2. INNOCENCE — each accepted "guarded" shape
# ---------------------------------------------------------------------------


def test_innocence_field_validator_decorator(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "good_decorator.py",
        "from pydantic import BaseModel, field_validator\n\n"
        "class GoodModel(BaseModel):\n"
        "    avatar_url: str | None = None\n\n"
        "    @field_validator('avatar_url')\n"
        "    @classmethod\n"
        "    def reject(cls, v):\n"
        "        if v and v.startswith('data:'):\n"
        "            raise ValueError('no')\n"
        "        return v\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "GoodModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_DECORATOR


def test_innocence_legacy_validator_decorator(tmp_path: Path) -> None:
    """Legacy pydantic-v1-style `@validator(...)` name is also accepted."""
    _write(
        tmp_path,
        "good_legacy.py",
        "from pydantic import BaseModel, validator\n\n"
        "class LegacyModel(BaseModel):\n"
        "    avatar_url: str | None = None\n\n"
        "    @validator('avatar_url')\n"
        "    def reject(cls, v):\n"
        "        return v\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "LegacyModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_DECORATOR


def test_innocence_shared_validator_attach(tmp_path: Path) -> None:
    """The documented pydantic v2 'reuse across models' pattern:
    `_check = field_validator("avatar_url")(checker_fn)` in the class body."""
    _write(
        tmp_path,
        "good_attach.py",
        "from pydantic import BaseModel, field_validator\n\n"
        "def reject_data_uri_avatar(v):\n"
        "    return v\n\n"
        "class AttachModel(BaseModel):\n"
        "    avatar_url: str | None = None\n"
        "    _avatar_check = field_validator('avatar_url')(reject_data_uri_avatar)\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "AttachModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_SHARED_ASSIGN


def test_innocence_shared_validator_attach_classmethod_wrapped(tmp_path: Path) -> None:
    """Same attach pattern, explicitly wrapped in classmethod(...)."""
    _write(
        tmp_path,
        "good_attach_cm.py",
        "from pydantic import BaseModel, field_validator\n\n"
        "def reject_data_uri_avatar(v):\n"
        "    return v\n\n"
        "class AttachCmModel(BaseModel):\n"
        "    avatar_url: str | None = None\n"
        "    _avatar_check = classmethod(field_validator('avatar_url')(reject_data_uri_avatar))\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "AttachCmModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_SHARED_ASSIGN


def test_innocence_inline_annotated_after_validator(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "good_inline_annotated.py",
        "from typing import Annotated\n"
        "from pydantic import AfterValidator, BaseModel\n\n"
        "def reject_data_uri_avatar(v):\n"
        "    return v\n\n"
        "class InlineAnnotatedModel(BaseModel):\n"
        "    avatar_url: Annotated[str | None, AfterValidator(reject_data_uri_avatar)] = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "InlineAnnotatedModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_ANNOTATED


def test_innocence_same_file_type_alias(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "good_same_file_alias.py",
        "from typing import Annotated\n"
        "from pydantic import AfterValidator, BaseModel\n\n"
        "def reject_data_uri_avatar(v):\n"
        "    return v\n\n"
        "AvatarUrl = Annotated[str | None, AfterValidator(reject_data_uri_avatar)]\n\n"
        "class SameFileAliasModel(BaseModel):\n"
        "    avatar_url: AvatarUrl = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "SameFileAliasModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_ANNOTATED


def test_innocence_cross_file_type_alias(tmp_path: Path) -> None:
    """THE live shape: `AvatarUrl` is defined once in crm_utils.py and
    imported bare into crm_clients.py / crm_enhanced.py / client_core.py.
    A same-file-only alias resolver passes right over this — this is the
    exact bug caught and fixed live while building this scanner: the first
    draft false-flagged all four real guarded models as unguarded until
    scan_tree's two-pass global alias registry was added.
    """
    _write(
        tmp_path,
        "shared_utils.py",
        "from typing import Annotated\n"
        "from pydantic import AfterValidator\n\n"
        "def reject_data_uri_avatar(v):\n"
        "    return v\n\n"
        "AvatarUrl = Annotated[str | None, AfterValidator(reject_data_uri_avatar)]\n",
    )
    _write(
        tmp_path,
        "consumer_model.py",
        "from pydantic import BaseModel\n"
        "from shared_utils import AvatarUrl\n\n"
        "class CrossFileAliasModel(BaseModel):\n"
        "    avatar_url: AvatarUrl = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    finding = _finding(result, "CrossFileAliasModel")
    assert finding.guarded
    assert finding.guard_kind == lint._GUARD_KIND_ANNOTATED

    # Would-be regression guard: importlib re-check that scan_file() alone
    # (single-file, no cross-file registry) does NOT resolve it — proves the
    # cross-file case is genuinely exercised by scan_tree, not accidentally
    # passing some other way.
    single_file_result = lint.scan_file(
        tmp_path / "consumer_model.py", tmp_path, extra_type_aliases={}
    )
    assert single_file_result[0].guard_kind == lint._GUARD_KIND_UNGUARDED


# ---------------------------------------------------------------------------
# 3. INNOCENCE — no avatar_url field at all; allowlisted model
# ---------------------------------------------------------------------------


def test_innocence_no_avatar_url_field_not_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "unrelated.py",
        "from pydantic import BaseModel\n\n"
        "class TotallyUnrelated(BaseModel):\n"
        "    full_name: str\n"
        "    email: str | None = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    assert "unrelated.py::TotallyUnrelated" not in _keys(result)
    assert len(result.findings) == 0


def test_innocence_non_pydantic_class_not_flagged(tmp_path: Path) -> None:
    """A plain class (not a BaseModel subclass) with an avatar_url attribute
    is not a Pydantic model and must not be flagged — e.g. a dataclass or a
    plain dict-shaped helper."""
    _write(
        tmp_path,
        "not_pydantic.py",
        "class NotAModel:\n"
        "    avatar_url: str | None = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)

    assert len(result.findings) == 0


def test_innocence_allowlisted_model_not_flagged_as_unguarded(tmp_path: Path) -> None:
    """A model exempted via ALLOWLIST (team_members-style / response-model-style)
    is unguarded by construction but must not fail the build."""
    _write(
        tmp_path,
        "team_avatar.py",
        "from pydantic import BaseModel\n\n"
        "class TeamMemberProfile(BaseModel):\n"
        "    avatar_url: str | None = None\n",
    )

    result = lint.scan_tree(tmp_path, tmp_path)
    allowlist = {
        "team_avatar.py::TeamMemberProfile": (
            "bound to team_members, not clients — own avatar semantics, out of scope."
        )
    }

    guarded, allowlisted, unguarded = lint.classify(result.findings, allowlist)

    assert len(unguarded) == 0
    assert len(allowlisted) == 1
    assert allowlisted[0][0].class_name == "TeamMemberProfile"

    # And via main(): a request pointed at a root whose only model is
    # allowlisted-in-the-module-constant must never fail --strict. We
    # monkeypatch the module ALLOWLIST for the duration of this check since
    # main() always consults the real module-level constant.
    original_allowlist = dict(lint.ALLOWLIST)
    try:
        lint.ALLOWLIST.clear()
        lint.ALLOWLIST.update(allowlist)
        # --repo-root pins relative-key computation to tmp_path (matching how
        # scan_tree() above resolved "team_avatar.py::TeamMemberProfile")
        # instead of falling back to an absolute-path key under the real repo
        # root, which would never match the ALLOWLIST entry above.
        assert (
            lint.main(["--root", str(tmp_path), "--repo-root", str(tmp_path), "--strict"]) == 0
        )
    finally:
        lint.ALLOWLIST.clear()
        lint.ALLOWLIST.update(original_allowlist)


# ---------------------------------------------------------------------------
# 4. BLIND-SCAN guard (W84): looked nowhere != clean
# ---------------------------------------------------------------------------


def test_blind_scan_empty_dir_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    empty_root = tmp_path / "empty"
    empty_root.mkdir()

    rc = lint.main(["--root", str(empty_root), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 2
    assert payload["blind"] is True
    assert payload["files_scanned"] == 0
    assert payload["models_found"] == 0


def test_blind_scan_files_present_but_no_avatar_url_models_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Files ARE walked, but none of them declare avatar_url anywhere — this
    is the mis-pathed-scanner case (e.g. --root pointed at the wrong repo
    subtree) and must still be treated as blind, not silently 'clean'."""
    _write(tmp_path, "irrelevant.py", "x = 1\n")

    rc = lint.main(["--root", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 2
    assert payload["blind"] is True
    assert payload["files_scanned"] == 1
    assert payload["models_found"] == 0


def test_nonexistent_root_exits_2(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert lint.main(["--root", str(missing)]) == 2


# ---------------------------------------------------------------------------
# 5. REAL-TREE — the scanner must find the real client models, not nothing
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not BACKEND_ROOT.exists(), reason="apps/backend-rag/backend not present")
def test_real_tree_finds_known_client_models() -> None:
    result = lint.scan_tree(BACKEND_ROOT, REPO_ROOT)

    # Never silently-matching-nothing: the walk must see a substantial slice
    # of the real backend and must find at least the historically-known
    # avatar_url-bearing client models.
    assert result.files_scanned > 500
    assert len(result.findings) >= 4

    keys = _keys(result)
    expected_substrings = [
        "crm_clients.py::ClientCreate",
        "crm_clients.py::ClientUpdate",
        "crm_enhanced.py::ClientProfileUpdate",
        "client_core.py::ClientValidator",
    ]
    for expected in expected_substrings:
        assert any(expected in key for key in keys), (
            f"expected a finding matching {expected!r}, got {sorted(keys)}"
        )


@pytest.mark.skipif(not BACKEND_ROOT.exists(), reason="apps/backend-rag/backend not present")
def test_real_tree_main_strict_matches_current_repo_state() -> None:
    """Regression gate: run exactly what CI runs. If this starts failing, a
    real avatar_url model in the live tree is genuinely unguarded and not
    allowlisted — the guard is doing its job, this is not a flaky test."""
    rc = lint.main(["--strict"])
    assert rc in (0, 1)  # never 2 (blind) against the real tree
    if rc == 1:
        pytest.fail(
            "lint_avatar_url_validators --strict found an unguarded avatar_url "
            "model in the real repo tree — see stdout report above for which one."
        )


# ---------------------------------------------------------------------------
# 6. JSON output shape
# ---------------------------------------------------------------------------


def test_json_output_shape(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _write(
        tmp_path,
        "bad_model.py",
        "from pydantic import BaseModel\n\n"
        "class LeakyModel(BaseModel):\n"
        "    avatar_url: str | None = None\n",
    )

    rc = lint.main(["--root", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0  # no --strict
    assert payload["schema"] == 1
    assert payload["models_found"] == 1
    assert payload["blind"] is False
    assert len(payload["unguarded"]) == 1
    assert payload["unguarded"][0]["class_name"] == "LeakyModel"
    assert payload["guarded"] == []
    assert payload["allowlisted"] == []
