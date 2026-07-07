#!/usr/bin/env python3
"""scar_test for the WR2 reflexion W74-cure (superscar #2 Esiste≠Armato).

DISEASE: the running Pro copy `~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py`
had NO Delta Gate — an empty week was a SILENT `print(...); return 0`. Green cron, zero
state-delta, no audit trail: the canonical W74 "green != working". An operator could not
tell "12 weeks all empty" from "12 weeks of healthy learning".

ANTIBODY (this gate verifies it stays dead): scripts/wr2_reflexion_synthesis.py now records
every run via reflexion_core.record_run at ALL THREE main() exits —
  - no-data week     -> NO_INPUT  (canonical NO_SIGNAL), exit 0
  - synthesis failed -> LLM_FAILED (canonical LLM_FAILED), exit 1
  - synthesized      -> SYNTHESIZED/THIN_SIGNAL (canonical LEARNED/NO_SIGNAL), exit 0
so there is an auditable _reflexion-state.json record on every path, and is_tautological can
fire the Omeostasi alarm.

This test ARMS the gate: it exits 0 only if the disease is still dead. Registered in
verify_the_verifiers_gates.yaml as scar_A_wr2_reflexion. Runnable both as a bare script
(scar_test contract: `[sys.executable, this_file]`) and under pytest.

NO real claude -p, NO real DB writes outside a tmp dir: paths are env-overridden
(WR2_DB_PATH / WR2_SKILL_DIR / WR2_QUEUE_PATH), claude is stubbed via PATH shim.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "wr2_reflexion_synthesis.py"
CORE = HERE / "lib" / "reflexion.py"


def _load_target(env_overrides):
    """Import the target module fresh with env paths applied (module reads env at import)."""
    for k, v in env_overrides.items():
        os.environ[k] = str(v)
    # force a fresh import so module-level path constants pick up the env
    sys.modules.pop("wr2_reflexion_synthesis", None)
    spec = importlib.util.spec_from_file_location("wr2_reflexion_synthesis", str(TARGET))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_core():
    spec = importlib.util.spec_from_file_location("reflexion_core_t", str(CORE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_state(skill_dir):
    p = Path(skill_dir) / "_reflexion-state.json"
    if not p.exists():
        return []
    return json.loads(p.read_text())


def test_no_data_records_no_input_not_silent_return0():
    """THE W74 REGRESSION: an empty week must record NO_INPUT, NOT silently return 0."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        db = Path(td) / "nonexistent.db"      # no DB -> no runs
        queue = Path(td) / "nonexistent.json"  # no queue -> no rejections
        mod = _load_target({"WR2_DB_PATH": db, "WR2_SKILL_DIR": skill, "WR2_QUEUE_PATH": queue})
        rc = mod.main()
        assert rc == 0, f"empty week should exit 0, got {rc}"
        state = _read_state(skill)
        assert len(state) == 1, f"empty week MUST leave exactly one audit record, got {state!r}"
        rec = state[0]
        # native operator vocabulary on disk
        assert rec["status"] == "NO_INPUT", f"native status should be NO_INPUT, got {rec['status']!r}"
        # canonical machine vocabulary drives is_tautological
        assert rec["canonical_status"] == "NO_SIGNAL", \
            f"canonical should be NO_SIGNAL, got {rec.get('canonical_status')!r}"
        assert rec["loop"] == "wr2"
        assert rec["signals_found"] == 0
        assert rec["lessons_written"] == 0
    print("PASS no-data records NO_INPUT (W74 silent-return-0 is dead)")


def test_status_map_is_well_formed_and_canonical():
    """The WR2->core status map must only target real core enum values (anti-typo)."""
    mod = _load_target({})
    core = _load_core()
    valid = {core.LEARNED, core.NO_SIGNAL, core.NOOP, core.LLM_FAILED}
    assert mod._WR2_STATUS_TO_CORE, "status map must be non-empty"
    for native, canonical in mod._WR2_STATUS_TO_CORE.items():
        assert canonical in valid, f"{native!r} maps to non-enum {canonical!r}"
    # the three exits must each have a status
    for required in ("NO_INPUT", "LLM_FAILED", "SYNTHESIZED", "THIN_SIGNAL"):
        assert required in mod._WR2_STATUS_TO_CORE, f"missing native status {required!r}"
    print("PASS status map well-formed (NO_INPUT/LLM_FAILED/SYNTHESIZED/THIN_SIGNAL -> enum)")


def test_record_rejects_unknown_status():
    """_record must refuse an unknown native status — anti-typo gate, not silent."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        mod = _load_target({"WR2_SKILL_DIR": skill})
        raised = False
        try:
            mod._record("TOTALLY_BOGUS", signals_found=1, lessons_written=0)
        except ValueError:
            raised = True
        assert raised, "_record should raise ValueError on unknown status"
    print("PASS unknown status rejected (anti-typo)")


def test_synthesis_failed_records_llm_failed_exit1():
    """Data present + claude -p fails -> LLM_FAILED record + exit 1 (alert-worthy, not green)."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        db = Path(td) / "nonexistent.db"
        queue = Path(td) / "nonexistent.json"
        mod = _load_target({"WR2_DB_PATH": db, "WR2_SKILL_DIR": skill, "WR2_QUEUE_PATH": queue})
        # Inject data + force synthesis failure without touching real claude/DB.
        mod.fetch_last_7_days = lambda: {"runs": [{"id": 1, "topic_slug": "t", "domain": "tax"}],
                                         "critic_failures": []}
        mod.fetch_rejections_from_queue = lambda: []
        mod.call_claude_synthesis = lambda prompt: None  # synthesis fails
        rc = mod.main()
        assert rc == 1, f"synthesis-failed-with-data should exit 1 (alert), got {rc}"
        state = _read_state(skill)
        assert len(state) == 1, f"failure path MUST leave one audit record, got {state!r}"
        rec = state[0]
        assert rec["status"] == "LLM_FAILED"
        assert rec["canonical_status"] == "LLM_FAILED"
        assert rec["signals_found"] == 1
    print("PASS synthesis-failed records LLM_FAILED + exit 1 (not silent green)")


def test_is_tautological_fires_after_three_empty_weeks():
    """Three consecutive empty weeks -> is_tautological True (Omeostasi alarm wired)."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        db = Path(td) / "nonexistent.db"
        queue = Path(td) / "nonexistent.json"
        mod = _load_target({"WR2_DB_PATH": db, "WR2_SKILL_DIR": skill, "WR2_QUEUE_PATH": queue})
        for _ in range(3):
            mod.main()
        core = _load_core()
        assert core.is_tautological(skill) is True, \
            "three empty weeks should trip the tautology alarm"
    print("PASS tautology alarm fires after 3 empty weeks")


def main():
    tests = [
        test_no_data_records_no_input_not_silent_return0,
        test_status_map_is_well_formed_and_canonical,
        test_record_rejects_unknown_status,
        test_synthesis_failed_records_llm_failed_exit1,
        test_is_tautological_fires_after_three_empty_weeks,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            failed += 1
        except Exception as e:  # noqa: BLE001 — a crash is a failed scar gate
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
            failed += 1
    total = len(tests)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
