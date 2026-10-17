"""#8646 added a step to guard-conformance.yml with no matrix row, so ctx.guard-guilt-innocence went BLOCKED on every PR: the BASE workflow job must be fully accounted for by the BASE matrix."""
from __future__ import annotations

import yaml

from .fixture_repo import REAL_REPO as ROOT, runner

CTX = "Every guard proves guilt AND innocence"
STEP = "harness/fable-gate zsh preflight regression"


def _resolve():
    doc = yaml.safe_load((ROOT / ".github/workflows/guard-conformance.yml").read_text())
    entry = next(c for c in yaml.safe_load((ROOT / "scripts/localci/contexts_matrix.yaml").read_text())["contexts"] if c["name"] == CTX)
    return runner.resolve_steps(doc["jobs"][entry["job_id"]], entry["local"], "b" * 40, ((doc.get("defaults") or {}).get("run")) or {}, doc.get("env") or {})


def test_the_guard_job_is_fully_mapped_by_the_matrix():
    steps, why = _resolve()
    assert why is None, why
    assert steps


def test_the_zsh_preflight_step_runs_its_real_assertions_without_the_install():
    steps, _ = _resolve()
    step = next(s for s in steps if s["name"] == STEP)
    script = step["argv"][-1]
    assert step["argv"][:2] == ["bash", "-c"]
    assert "apt-get" not in script and "sudo" not in script
    assert "command -v zsh" in script
    assert "REQUIRE_ZSH=1 python3 -m pytest tests/scripts/test_harness_fable_gate_preflight_zsh_1017.py -q" in script


def test_the_override_keeps_every_non_install_line_of_the_hosted_body():
    doc = yaml.safe_load((ROOT / ".github/workflows/guard-conformance.yml").read_text())
    hosted = next(s for s in doc["jobs"]["conformance"]["steps"] if s.get("name") == STEP)["run"]
    steps, _ = _resolve()
    local = next(s for s in steps if s["name"] == STEP)["argv"][-1]
    kept = [ln.strip() for ln in hosted.splitlines() if ln.strip() and "apt-get" not in ln]
    assert kept == [ln.strip() for ln in local.splitlines() if ln.strip()]
