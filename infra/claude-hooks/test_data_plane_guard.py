#!/usr/bin/env python3
"""data_plane_guard guilt+innocence corpus (superscar #3 antidote).

Runs the REAL on-disk hook (infra/claude-hooks/data_plane_guard.py) as a
subprocess with a crafted stdin JSON payload — the exact contract Claude Code
uses (see test_hook_innocence.py / test_w85_stash_readonly.py for the sibling
pattern this mirrors). GUILT cases must BLOCK (exit 2); INNOCENCE cases must
ALLOW (exit 0).

Path resolution is proven against a SYNTHETIC git tree (a temp dir carrying
both a main-checkout `.git` DIR and a nested `.worktrees/lane-x/` dir with
its own `.git` FILE — exactly how a real worktree looks) so the corpus is
deterministic and independent of whatever worktree this test happens to run
inside. The REAL `infra/claude-hooks/data-plane-registry.json` is used
unmodified (no CLAUDE_PROJECT_DIR override) except for the one case that
specifically proves missing-registry pass-through.

Run:  python3 infra/claude-hooks/test_data_plane_guard.py
      (exit 0 = all clean, 1 = a guilt case went blind or an innocent got bit)
Also a pytest target: pytest infra/claude-hooks/test_data_plane_guard.py -q
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent  # infra/claude-hooks
HOOK = HERE / "data_plane_guard.py"

# --- synthetic git tree: main checkout + a nested worktree, both carrying a
# real `.git` marker so _git_root_for() resolves exactly as it would live.
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="data_plane_guard_test_"))
MAIN = _TMP / "main-checkout"
WT = MAIN / ".worktrees" / "infra-data-plane-guard-fake"
(MAIN / ".git").mkdir(parents=True, exist_ok=True)          # main checkout: .git DIR
WT.mkdir(parents=True, exist_ok=True)
(WT / ".git").write_text("gitdir: /fake/common/git/dir\n")  # worktree: .git FILE

# a dir with NO infra/claude-hooks/data-plane-registry.json under it, for the
# missing-registry pass-through case.
_NO_REGISTRY_DIR = _TMP / "no-registry-project"
_NO_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def run_hook(payload: dict, env_extra: dict | None = None) -> tuple[int, str]:
    """Invoke the real hook file as Claude Code does: JSON on stdin. Returns
    (exit_code, stderr)."""
    env = dict(os.environ)
    env.pop("DATA_PLANE_GUARD_OFF", None)  # ensure kill switch not leaked from caller shell
    env.pop("CLAUDE_PROJECT_DIR", None)    # default: let the hook use its own repo root (real registry)
    if env_extra:
        env.update(env_extra)
    try:
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=15, env=env,
        )
        return (proc.returncode, proc.stderr)
    except subprocess.TimeoutExpired:
        return (-2, "TIMEOUT")


def edit(path: str, cwd: str = str(MAIN)) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": path,
            "old_string": "a", "new_string": "b"}, "cwd": cwd}


def write(path: str, cwd: str = str(MAIN)) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path,
            "content": "x"}, "cwd": cwd}


def bash(cmd: str, cwd: str = str(MAIN)) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}


# (payload, expect, desc) — expect in {"BLOCK", "ALLOW"}
CASES: list[tuple[dict, str, str, dict | None]] = [
    # ------------------------------------------------------------------ GUILT
    (edit("data/kbli-filiera/dossiers/68112.jsonl"), "BLOCK",
     "Edit hand-touches a kbli-filiera dossier (main checkout)", None),
    (write("data/source_documents/KBLI_2025_FINAL_CLEAN.json"), "BLOCK",
     "Write hand-touches the KBLI gold file (main checkout)", None),
    (edit(str(WT / "data/kbli-filiera/dossiers/68112.jsonl"), cwd=str(WT)), "BLOCK",
     "same dossier path, but resolved inside a .worktrees/<lane> prefix — "
     "protection must follow the dataset into worktrees", None),
    (bash("echo x > data/kbli-filiera/quarantine.md"), "BLOCK",
     "Bash redirect writes into the protected dir", None),
    (bash("cp /tmp/a data/source_documents/KBLI_2025_FINAL_CLEAN.json"), "BLOCK",
     "Bash cp overwrites the KBLI gold file", None),
    (bash("sed -i '' 's/a/b/' data/kbli-filiera/manifest/m.json"), "BLOCK",
     "Bash sed -i (BSD two-arg form) edits a manifest in place", None),

    # --------------------------------------------------------------- INNOCENCE
    (edit("data/kbli-filiera-README.md"), "ALLOW",
     "adjacent prefix (hyphen, not a path separator) must not match "
     "data/kbli-filiera/** ", None),
    (edit("research/operations/x.md"), "ALLOW",
     "unrelated repo path", None),
    (bash("cat data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "read-only cat, no write operator", None),
    (bash("python3 scripts/kbli_filiera/build_canonical.py"), "ALLOW",
     "compiler invocation itself — no shell-level write operator", None),
    (bash("grep -r foo data/kbli-filiera/"), "ALLOW",
     "read-only grep over the protected dir", None),
    (bash("git add data/kbli-filiera/manifest.json && git commit"), "ALLOW",
     "git object writes are not hand-edits", None),
    (edit("data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "same GUILTY path, but registry unreachable from this project dir "
     "→ pass-through with WARN", {"CLAUDE_PROJECT_DIR": str(_NO_REGISTRY_DIR)}),
    (edit("data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "same GUILTY path, but kill switch DATA_PLANE_GUARD_OFF=1",
     {"DATA_PLANE_GUARD_OFF": "1"}),
]


def evaluate() -> list[str]:
    failures: list[str] = []
    for payload, expect, desc, env_extra in CASES:
        code, err = run_hook(payload, env_extra)
        if code < 0:
            failures.append(f"{desc}: hook error ({err.strip()[:200]})")
            continue
        blocked = code == 2
        if expect == "BLOCK":
            if not blocked:
                failures.append(
                    f"WENT-BLIND on guilt → {desc}: expected BLOCK, got exit {code}\n"
                    f"        payload={json.dumps(payload)[:200]}"
                )
        else:  # ALLOW
            if blocked:
                failures.append(
                    f"BIT-AN-INNOCENT → {desc}: expected ALLOW, got BLOCK\n"
                    f"        payload={json.dumps(payload)[:200]}\n"
                    f"        stderr={err.strip()[:300]}"
                )
    return failures


def test_data_plane_guard():
    failures = evaluate()
    assert not failures, "data_plane_guard GUILT/INNOCENCE regressions:\n" + "\n".join(failures)


def test_data_plane_guard_block_message_names_file_and_owner():
    """The block message must name the file, the matched registry entry, and
    point at the compiler-script resolution — not just a bare 'blocked'."""
    code, err = run_hook(edit("data/source_documents/KBLI_2025_FINAL_CLEAN.json"))
    assert code == 2, f"expected BLOCK, got exit {code}: {err}"
    assert "KBLI_2025_FINAL_CLEAN.json" in err, err
    assert "kbli-filiera" in err, err
    assert "scripts/kbli_filiera" in err, err


def test_data_plane_guard_missing_registry_warns_on_stderr():
    code, err = run_hook(
        edit("data/kbli-filiera/dossiers/68112.jsonl"),
        {"CLAUDE_PROJECT_DIR": str(_NO_REGISTRY_DIR)},
    )
    assert code == 0, f"expected ALLOW (pass-through), got exit {code}: {err}"
    assert "WARN" in err, f"expected a WARN line on missing-registry pass-through, got: {err!r}"


def _cleanup():
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    try:
        failures = evaluate()
    finally:
        pass
    if failures:
        print("data_plane_guard FAILED:")
        for f in failures:
            print(f"  - {f}")
        _cleanup()
        sys.exit(1)
    print(f"OK (data_plane_guard) — {len(CASES)} guilt+innocence cases clean.")
    _cleanup()
    sys.exit(0)
