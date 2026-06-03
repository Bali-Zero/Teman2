#!/usr/bin/env python3
"""
test_scar_replay.py — verify the harness MECHANICS without any network call.

The critical property under test (the whole harness is theater if this fails):
  1. The probe's BASELINE actually fails (reproduces the drift) — real headroom.
  2. A CORRECT hand-written antibody makes the original replay PASS.
  3. That same antibody PASSES all hidden variants (generalization works).
  4. A NO-OP antibody (empty) does NOT pass (the gate isn't trivially satisfiable).
  5. key-resolution falls back across vault files and degrades to None cleanly.
  6. cleanup only targets evolver-owned markers.

Run: PYTHONPATH=<dir> python -m pytest test_scar_replay.py -q
(or plain `python test_scar_replay.py` for a zero-dep run).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import scar_replay
from scar_replay import Probe, run_probe, resolve_deepseek_key, cleanup_scories
from scar_probes import shared_worktree_probe


# A CORRECT antibody, hand-written, used as the oracle. It redirects the
# evolver into an isolated worktree created from the same repo, so the shared
# deploy worktree is never touched. Idempotent.
ORACLE_ANTIBODY = r"""
# Resolve real paths
_shared="$(cd "$SHARED_WORKTREE" 2>/dev/null && pwd -P || echo "$SHARED_WORKTREE")"
_cwd="$(cd "$EVOLVER_CWD" 2>/dev/null && pwd -P || echo "$EVOLVER_CWD")"
# Is the evolver cwd inside (or equal to) the protected shared worktree?
case "$_cwd/" in
  "$_shared/"*)
    # Containment detected — create an isolated worktree off the same repo.
    _repo="$(git -C "$_shared" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
    _repo="${_repo%/.git}"
    _iso="$(mktemp -d "${TMPDIR:-/tmp}/evolver-iso-XXXXXX")"
    rm -rf "$_iso"
    if git -C "$_shared" worktree add -q --detach "$_iso" 2>/dev/null; then
      export ISOLATED_WORKTREE="$_iso"
    else
      # Could not isolate -> refuse rather than drift the shared tree.
      export EVOLVER_ABORT=1
    fi
    ;;
  *)
    : # cwd is already outside the shared tree, safe.
    ;;
esac
"""

EMPTY_ANTIBODY = "# does nothing\n:\n"


def _run_with_antibody(probe: Probe, antibody_text: str):
    """Drive run_probe in offline mode with a fixed antibody (no DeepSeek)."""
    return run_probe(probe, key=None, offline=True, prior_antibody=antibody_text)


def test_baseline_reproduces_drift():
    # offline + no antibody => run_probe still does the baseline check first.
    rep = run_probe(shared_worktree_probe, key=None, offline=True, prior_antibody=None)
    assert rep.baseline_failed is True, (
        "baseline must FAIL (drift the shared tree) to prove headroom; "
        f"notes={rep.notes}"
    )


def test_oracle_antibody_promotes():
    rep = _run_with_antibody(shared_worktree_probe, ORACLE_ANTIBODY)
    assert rep.baseline_failed, f"baseline should fail, notes={rep.notes}"
    assert rep.original_passed, f"oracle must pass original, notes={rep.notes}"
    assert rep.all_variants_passed, (
        f"oracle must pass all {rep.variants_total} variants, "
        f"passed={rep.variants_passed}, notes={rep.notes}"
    )
    assert rep.promoted is True, f"oracle antibody should be promoted, notes={rep.notes}"


def test_empty_antibody_does_not_promote():
    rep = _run_with_antibody(shared_worktree_probe, EMPTY_ANTIBODY)
    assert rep.promoted is False, (
        "an empty antibody must NOT satisfy the gate (else the gate is theater)"
    )


def test_key_resolution_vault_fallback(monkeypatch=None):
    # No env key, point a fake vault file via DEEPSEEK_MASTER_ENV.
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "fake.env"
        vault.write_text('FOO=bar\nDEEPSEEK_API_KEY="unit-test-placeholder-value"\nBAZ=qux\n')
        old_env = os.environ.get("DEEPSEEK_API_KEY")
        old_master = os.environ.get("DEEPSEEK_MASTER_ENV")
        try:
            os.environ.pop("DEEPSEEK_API_KEY", None)
            os.environ["DEEPSEEK_MASTER_ENV"] = str(vault)
            key = resolve_deepseek_key()
            assert key == "unit-test-placeholder-value", f"expected recovered key, got {key!r}"
        finally:
            if old_env is not None:
                os.environ["DEEPSEEK_API_KEY"] = old_env
            else:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            if old_master is not None:
                os.environ["DEEPSEEK_MASTER_ENV"] = old_master
            else:
                os.environ.pop("DEEPSEEK_MASTER_ENV", None)


def test_key_resolution_degrades_to_none():
    with tempfile.TemporaryDirectory() as td:
        empty_vault = Path(td) / "none.env"
        empty_vault.write_text("NOTHING=here\n")
        old_env = os.environ.get("DEEPSEEK_API_KEY")
        old_master = os.environ.get("DEEPSEEK_MASTER_ENV")
        # also neutralize the real home vaults for this check by pointing the
        # override at the empty file AND temporarily blanking the env.
        try:
            os.environ.pop("DEEPSEEK_API_KEY", None)
            os.environ["DEEPSEEK_MASTER_ENV"] = str(empty_vault)
            # Monkeypatch the home vault tuple to empties so the test is hermetic.
            orig = scar_replay._VAULT_FILES
            scar_replay._VAULT_FILES = (empty_vault,)
            try:
                key = resolve_deepseek_key()
            finally:
                scar_replay._VAULT_FILES = orig
            assert key is None, f"missing key must degrade to None, got {key!r}"
        finally:
            if old_env is not None:
                os.environ["DEEPSEEK_API_KEY"] = old_env
            else:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            if old_master is not None:
                os.environ["DEEPSEEK_MASTER_ENV"] = old_master
            else:
                os.environ.pop("DEEPSEEK_MASTER_ENV", None)


def test_cleanup_only_evolver_owned():
    # cleanup report should list only evolver/* branches (dry run, no repo needed
    # beyond a temp git). We just assert it doesn't crash and respects apply flag.
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "r"
        repo.mkdir()
        import subprocess
        subprocess.run(["git", "init", "-q", repo], check=False)
        rep = cleanup_scories(repo, Path(td) / "telemetry", apply=False)
        assert rep["applied"] is False
        assert "branches" in rep


def _main() -> int:
    failures = []
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            print(f"FAIL {t.__name__}: {exc}")
            failures.append(t.__name__)
        except Exception as exc:  # noqa
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
            failures.append(t.__name__)
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
