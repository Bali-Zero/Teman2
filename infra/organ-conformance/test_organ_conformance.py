"""Guilt AND innocence tests for check_organ_conformance.py (#3 discipline:
the gate itself ships with proof it catches the guilty and spares the innocent).

Run:  python3 -m pytest infra/organ-conformance/test_organ_conformance.py -q
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_organ_conformance", HERE / "check_organ_conformance.py"
)
coc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coc)


PLIST_TMPL = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string>{wrapper}</string></array>
    <key>StartInterval</key><integer>3600</integer>
</dict>
</plist>
"""

GOOD_WRAPPER = """#!/bin/bash
set -u
PIDFILE=/tmp/test-good.pid
[ "${GOOD_ORGAN_ENABLED:-true}" = "false" ] && organism_heartbeat good disabled && exit 0
source ~/nuzantara/scripts/lib/heartbeat.sh
organism_heartbeat "test.good" "ok"
"""

BAD_WRAPPER = """#!/bin/bash
echo "no genes at all"
"""

LLM_HARDENED = """#!/bin/bash
set -u
PIDFILE=/tmp/test-llm.pid
[ "${LLM_ORGAN_ENABLED:-true}" = "false" ] && exit 0
[ -n "${SSH_CONNECTION:-}" ] || exit 78
organism_heartbeat "test.llm" "ok"
claude -p "mandate" --strict-mcp-config --mcp-config '{"mcpServers":{}}' </dev/null > /tmp/out.log 2>&1
"""

LLM_NAKED = """#!/bin/bash
set -u
[ "${LLM2_ORGAN_ENABLED:-true}" = "false" ] && exit 0
organism_heartbeat "test.llm2" "ok"
claude -p "mandate" > /tmp/out.log 2>&1
"""


def make_repo(tmp_path: Path) -> Path:
    """Minimal git repo with the files the checker grounds on."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts/lint_plist_keepalive.py", repo / "scripts/")
    reg = repo / "apps/organism/organism"
    reg.mkdir(parents=True)
    (reg / "organs_registry.yaml").write_text(
        "version: 1\norgans:\n- id: test.good\n  recovery_params:\n"
        "    label: com.test.good\n- id: test.llm\n  recovery_params:\n"
        "    label: com.test.llm\n- id: test.llm2\n  recovery_params:\n"
        "    label: com.test.llm2\n",
        encoding="utf-8",
    )
    hf = repo / "infra/home-fork"
    hf.mkdir(parents=True)
    (hf / "declared-pairs.json").write_text('{"pairs": []}', encoding="utf-8")
    (repo / "infra/launchagents/wrappers").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def add_organ(repo: Path, label: str, wrapper_name: str, wrapper_body: str) -> str:
    wrapper = repo / "infra/launchagents/wrappers" / wrapper_name
    wrapper.write_text(wrapper_body, encoding="utf-8")
    plist = repo / "infra/launchagents" / f"{label}.plist"
    plist.write_text(
        PLIST_TMPL.format(label=label, wrapper=f"/Users/x/nuzantara/infra/launchagents/wrappers/{wrapper_name}"),
        encoding="utf-8",
    )
    return str(plist.relative_to(repo))


def run_gate(repo: Path, monkeypatch, grandfathered: dict | None = None) -> dict:
    genes = json.loads((HERE / "genes.json").read_text(encoding="utf-8"))
    genes["grandfathered"] = grandfathered or {}
    genes_path = repo / "genes.json"
    genes_path.write_text(json.dumps(genes), encoding="utf-8")
    monkeypatch.setattr(coc, "GENES_PATH", genes_path)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    return coc.run(repo)


# ---------------------------------------------------------------- innocence
def test_innocence_conformant_new_organ_passes(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    add_organ(repo, "com.test.good", "good.sh", GOOD_WRAPPER)
    report = run_gate(repo, monkeypatch)
    assert report["exit"] == 0, report
    assert report["failures"] == []


def test_innocence_grandfathered_unchanged_is_report_only(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    rel = add_organ(repo, "com.test.bad", "bad.sh", BAD_WRAPPER)
    # bad organ is fully recorded in the baseline -> report-only, gate green
    baseline = {rel: ["G1_registry", "G2_heartbeat", "G5_kill_switch", "G9_fail_visible"]}
    report = run_gate(repo, monkeypatch, grandfathered=baseline)
    assert report["exit"] == 0, report
    assert report["regressions"] == []
    assert report["grandfathered_count"] == 1


def test_innocence_hardened_llm_wrapper_passes(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    add_organ(repo, "com.test.llm", "llm.sh", LLM_HARDENED)
    report = run_gate(repo, monkeypatch)
    organ = next(o for o in report["organs"] if o["label"] == "com.test.llm")
    assert "G6_spawn_hardened" not in organ["missing"], organ
    assert "G10_single_instance" not in organ["missing"], organ
    assert report["exit"] == 0, report


def test_innocence_app_bundle_info_plist_is_not_scanned_as_organ(tmp_path, monkeypatch):
    """A macOS app-bundle Info.plist (CFBundleIdentifier/CFBundleExecutable/...)
    can live under a scan root (e.g. apps/<app>/Info.plist) but structurally can
    never carry ProgramArguments/Program — the one launchd.plist(5)-mandatory
    directive this gate checks. It must never be flagged as a "new organ without
    genes", and must never be silently grandfathered (the ratchet forbids new
    grandfather entries) — it must be recognized as not-an-organ and skipped."""
    repo = make_repo(tmp_path)
    bundle_dir = repo / "apps/some-app"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "Info.plist").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\"><dict>\n"
        "  <key>CFBundleIdentifier</key><string>com.test.someapp</string>\n"
        "  <key>CFBundleExecutable</key><string>SomeApp</string>\n"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    add_organ(repo, "com.test.good", "good.sh", GOOD_WRAPPER)  # keep scan non-blind
    report = run_gate(repo, monkeypatch)
    assert report["exit"] == 0, report
    assert not any("Info.plist" in f for f in report["failures"])
    assert not any("Info.plist" in m for m in report.get("malformed", []))
    bundle_organ = next(o for o in report["organs"] if o["path"].endswith("Info.plist"))
    assert bundle_organ.get("not_an_organ") is True, bundle_organ


# ------------------------------------------------------------------- guilt
def test_guilt_new_organ_without_genes_fails(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    add_organ(repo, "com.test.bad", "bad.sh", BAD_WRAPPER)
    report = run_gate(repo, monkeypatch)
    assert report["exit"] == 1
    assert any("com.test.bad" in f for f in report["failures"])
    missing = next(o for o in report["organs"] if o["label"] == "com.test.bad")["missing"]
    assert "G1_registry" in missing and "G2_heartbeat" in missing
    assert "G5_kill_switch" in missing and "G9_fail_visible" in missing


def test_guilt_regression_beyond_baseline_fails(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    rel = add_organ(repo, "com.test.bad", "bad.sh", BAD_WRAPPER)
    # baseline only forgave the registry gap -> everything else is a regression
    report = run_gate(repo, monkeypatch, grandfathered={rel: ["G1_registry"]})
    assert report["exit"] == 1
    assert any("REGRESSION" in r and "com.test.bad" in r for r in report["regressions"])


def test_guilt_naked_llm_spawn_fails(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    add_organ(repo, "com.test.llm2", "llm2.sh", LLM_NAKED)
    report = run_gate(repo, monkeypatch)
    organ = next(o for o in report["organs"] if o["label"] == "com.test.llm2")
    assert "G6_spawn_hardened" in organ["missing"]
    assert "G10_single_instance" in organ["missing"]
    assert report["exit"] == 1


def test_guilt_plist_with_program_arguments_is_still_an_organ(tmp_path, monkeypatch):
    """The not-an-organ classifier only skips plists lacking BOTH ProgramArguments
    and Program — it must never over-match into skipping a genuine (if oddly
    shaped, e.g. no Label) launchd job description."""
    repo = make_repo(tmp_path)
    plist = repo / "infra/launchagents/com.test.nolabel.plist"
    plist.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\"><dict>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array><string>/bin/bash</string><string>/tmp/nolabel.sh</string></array>\n"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    report = run_gate(repo, monkeypatch)
    organ = next(o for o in report["organs"] if o["path"].endswith("com.test.nolabel.plist"))
    assert not organ.get("not_an_organ")
    assert "G1_registry" in organ["missing"]
    assert report["exit"] == 1


def test_guilt_blind_scan_exits_2(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)  # no plists at all
    report = run_gate(repo, monkeypatch)
    assert report["exit"] == 2


def test_guilt_malformed_plist_flagged(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    add_organ(repo, "com.test.good", "good.sh", GOOD_WRAPPER)
    (repo / "infra/launchagents/com.test.broken.plist").write_text(
        "<plist>not really", encoding="utf-8"
    )
    report = run_gate(repo, monkeypatch)
    assert report["exit"] & 4
    assert any("com.test.broken" in m for m in report["malformed"])


# ------------------------------------------------- gate-applies-to-itself
def test_real_repo_gate_is_green_and_healer_conformant():
    """The actual repo must pass its own gate, and the healer (first organ
    born after the genome) must be fully conformant — not grandfathered."""
    report = coc.run(REPO_ROOT)
    assert report["exit"] == 0, {
        "failures": report.get("failures"), "regressions": report.get("regressions"),
        "malformed": report.get("malformed"), "errors": report.get("errors"),
    }
    healer = next(
        o for o in report["organs"]
        if o["path"] == "infra/launchagents/com.nuzantara.healer.4h.plist"
    )
    assert healer["missing"] == [], healer
    assert not healer.get("grandfathered"), healer


def test_e2e_born_organ_passes_the_gate(tmp_path, monkeypatch):
    """The circle: an organ delivered by organ_birth.py must pass the gate
    with ZERO missing genes — vertical inheritance, verified end-to-end."""
    repo = make_repo(tmp_path)
    # give the fixture repo the files organ_birth grounds on
    (repo / "infra/organ-conformance").mkdir(parents=True)
    shutil.copy(HERE / "genes.json", repo / "infra/organ-conformance/genes.json")
    validator_src = REPO_ROOT / "apps/organism/organism/tools/validate_organs_registry.py"
    vdst = repo / "apps/organism/organism/tools"
    vdst.mkdir(parents=True)
    (vdst / "__init__.py").write_text("", encoding="utf-8")
    (repo / "apps/organism/organism/__init__.py").write_text("", encoding="utf-8")
    (repo / "apps/organism/__init__.py").write_text("", encoding="utf-8")
    shutil.copy(validator_src, vdst / "validate_organs_registry.py")

    spec = importlib.util.spec_from_file_location(
        "organ_birth", REPO_ROOT / "scripts/organ_birth.py")
    ob = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ob)
    for attr, val in {
        "REPO": repo,
        "GENES_PATH": repo / "infra/organ-conformance/genes.json",
        "REGISTRY_PATH": repo / "apps/organism/organism/organs_registry.yaml",
        "PAIRS_PATH": repo / "infra/home-fork/declared-pairs.json",
        "WRAPPER_DIR": repo / "infra/launchagents/wrappers",
        "PLIST_DIR": repo / "infra/launchagents",
    }.items():
        monkeypatch.setattr(ob, attr, val)

    rc = ob.main([
        "--id", "mini.newborn_probe", "--node", "mini", "--kind", "llm-cron",
        "--schedule", "14400", "--description", "e2e fixture organ", "--apply",
    ])
    assert rc == 0

    report = run_gate(repo, monkeypatch)
    organ = next(
        o for o in report["organs"] if o["label"] == "com.nuzantara.newborn-probe")
    assert organ["missing"] == [], organ
    assert report["failures"] == [], report["failures"]


def test_generator_and_gate_share_gene_contract():
    """genes.json is the single source: every gene the generator's templates
    claim to imprint must exist in genes.json (anti-divergence tripwire)."""
    genes = json.loads((HERE / "genes.json").read_text(encoding="utf-8"))
    gene_ids = set(genes["genes"].keys())
    birth = (REPO_ROOT / "scripts/organ_birth.py").read_text(encoding="utf-8")
    referenced = {g for g in gene_ids if g in birth}
    # the generator must reference every gene (imprint or document why not)
    assert referenced == gene_ids, f"organ_birth.py missing genes: {gene_ids - referenced}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
