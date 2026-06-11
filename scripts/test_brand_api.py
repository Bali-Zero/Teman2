#!/usr/bin/env python3
"""test_brand_api.py — falsifiable gate tests for the P8 brand-api slice.

Covers the two binary gates the safe slice promises:
  G6 — fonte generata non scritta: components.json is a build-artifact, carries
       a GENERATED header, and regenerating is idempotent (no hand-edit drift).
  G2 — token-compliance: brand_token_lint catches hardcoded color literals and
       passes brand-token usage.

Plus structural invariants: every parsed component has a name + import + source,
the artifact on disk is in sync (CI-gating: a stale checked-in artifact fails),
and the generator is deterministic across two runs.

Run: PYTHONPATH=scripts pytest scripts/test_brand_api.py -q
(stdlib + pytest only; no network, no PII, no DB).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import brand_api_gen as gen
import brand_token_lint as lint

REPO_ROOT = gen.REPO_ROOT


# ---------------------------------------------------------------- generation --
def test_generator_finds_components():
    arts = gen.build_components()
    assert len(arts) >= 12, "expected at least the 12 top-level components"
    # disk-state truth: the real tree has 24 (13 top-level incl. Money + 11 under apps/)
    assert len(arts) == 24, f"expected 24 components on disk, got {len(arts)}"


def test_every_component_has_required_fields():
    for c in gen.build_components():
        assert c["name"], c
        assert c["import"].startswith(gen.IMPORT_PREFIX), c
        assert c["source"].endswith(".tsx"), c
        assert isinstance(c["props"], dict), c
        assert isinstance(c["useWhen"], list), c
        assert c["example"].startswith("<"), c


def test_known_component_props_parsed():
    by_name = {c["name"]: c for c in gen.build_components()}
    # DeadlineBadge is the spec's canonical example — verify we read it right.
    assert "DeadlineBadge" in by_name
    props = by_name["DeadlineBadge"]["props"]
    assert "date" in props
    # windowDays is optional in source -> must be flagged undefined-able
    assert "windowDays" in props
    assert "| undefined" in props["windowDays"]


def test_artifact_has_generated_header():
    art = gen.build_artifact()
    assert art["_generated"] is True
    assert "do not edit" in art["_header"].lower()
    assert art["component_count"] == len(art["components"])


def test_generation_is_deterministic():
    a = gen.render_json(gen.build_artifact())
    b = gen.render_json(gen.build_artifact())
    assert a == b, "two generations differ — non-deterministic output"


def test_components_sorted_stable():
    comps = gen.build_artifact()["components"]
    keys = [(c["name"], c["source"]) for c in comps]
    assert keys == sorted(keys), "components not in stable sorted order"


# ----------------------------------------------------------- G6 idempotence --
def test_checked_in_artifact_is_in_sync():
    """If someone hand-edits components.json or forgets to regenerate after a
    .tsx change, --check must fail. Here it must PASS (artifact committed)."""
    rc = gen.check_artifacts(gen.build_artifact())
    assert rc == 0, "checked-in brand-api artifact is stale — run bz:brand:api"


def test_check_detects_handedit(tmp_path, monkeypatch):
    """Falsify G6: a tampered artifact must be detected as stale."""
    art = gen.build_artifact()
    fake_json = tmp_path / "components.json"
    fake_cat = tmp_path / "catalog.md"
    fake_json.write_text(
        gen.render_json(art).replace('"schema_version": 1', '"schema_version": 999')
    )
    fake_cat.write_text(gen.render_catalog(art))
    monkeypatch.setattr(gen, "OUT_JSON", fake_json)
    monkeypatch.setattr(gen, "OUT_CATALOG", fake_cat)
    rc = gen.check_artifacts(art)
    assert rc == 1, "tampered artifact NOT detected — G6 broken"


# --------------------------------------------------------------- G2 token --
def test_token_lint_self_test_passes():
    assert lint._self_test() == 0


def test_token_lint_catches_hex():
    assert lint._HEX.search("color: #ff0000;") is not None
    assert lint._HEX.search("background:#FFF;") is not None


def test_token_lint_catches_rgb_hsl():
    assert lint._FUNC.search("rgba(0,0,0,0.5)") is not None
    assert lint._FUNC.search("hsl(120, 50%, 50%)") is not None


def test_token_lint_allows_brand_tokens():
    assert lint._HEX.search("var(--bz-color-accent)") is None
    assert lint._FUNC.search("var(--bz-color-accent)") is None


def test_token_lint_respects_allow_escape(tmp_path, monkeypatch):
    bad = tmp_path / "x.css"
    bad.write_text(".a{color:#fff; /* brand-token-lint: allow legacy */}\n")
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    v = lint.scan([tmp_path])
    assert v == [], "allow-escape not honored"


def test_token_lint_flags_unescaped(tmp_path):
    bad = tmp_path / "y.tsx"
    bad.write_text("const s = { color: '#abcdef' };\n")
    v = lint.scan([tmp_path])
    assert len(v) == 1
    assert v[0][2].startswith("#")


# --------------------------------------------------------- CLI smoke (G6) --
def test_generator_check_cli_exit_zero():
    """The committed artifact + --check must exit 0 via the real CLI."""
    rc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "brand_api_gen.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0


def test_token_lint_cli_exit_zero():
    rc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "brand_token_lint.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
