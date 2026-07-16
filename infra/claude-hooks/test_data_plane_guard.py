#!/usr/bin/env python3
"""data_plane_guard guilt+innocence corpus (superscar #3 antidote).

Runs the REAL on-disk hook (infra/claude-hooks/data_plane_guard.py) as a
subprocess with a crafted stdin JSON payload — the exact contract Claude Code
uses (see test_hook_innocence.py / test_w85_stash_readonly.py for the sibling
pattern this mirrors). GUILT cases must BLOCK (exit 2); INNOCENCE cases must
ALLOW (exit 0).

Path resolution is proven against a SYNTHETIC git tree (a temp dir carrying
both a main-checkout `.git` DIR and a nested `.worktrees/lane-x/` dir with
its own `.git` FILE, EACH also carrying its own copy of the registry marker
file so the A4 foreign-repo guard trusts them) so the corpus is deterministic
and independent of whatever worktree this test happens to run inside. The
REAL `infra/claude-hooks/data-plane-registry.json` is used unmodified (no
CLAUDE_PROJECT_DIR override) except for the cases that specifically prove
missing/malformed-registry pass-through and the foreign-repo case.

Run:  python3 infra/claude-hooks/test_data_plane_guard.py
      (exit 0 = all clean, 1 = a guilt case went blind, an innocent got bit,
      or a non-corpus test function failed — B3: this standalone runner
      executes EVERY test_* function in the module, not just the corpus, so
      CI invoking this file directly sees the same coverage as pytest.)
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
REPO_ROOT = HERE.parent.parent
HOOK = HERE / "data_plane_guard.py"
SETTINGS_JSON = REPO_ROOT / ".claude" / "settings.json"

# --- synthetic git tree: main checkout + a nested worktree, both carrying a
# real `.git` marker AND our own registry marker file (A4: the foreign-repo
# guard only trusts a git root that also carries this file) so
# _git_root_for()/_is_nuzantara_checkout() resolve exactly as they would live.
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="data_plane_guard_test_"))
MAIN = _TMP / "main-checkout"
WT = MAIN / ".worktrees" / "infra-data-plane-guard-fake"


def _plant_registry_marker(root: pathlib.Path) -> None:
    marker = root / "infra" / "claude-hooks" / "data-plane-registry.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}")  # presence is all A4 checks — content irrelevant here


(MAIN / ".git").mkdir(parents=True, exist_ok=True)          # main checkout: .git DIR
_plant_registry_marker(MAIN)
WT.mkdir(parents=True, exist_ok=True)
(WT / ".git").write_text("gitdir: /fake/common/git/dir\n")  # worktree: .git FILE
_plant_registry_marker(WT)

# a real on-disk file under MAIN for the glob-expansion guilt case (C4) —
# glob.glob only matches things that actually exist.
(MAIN / "data" / "kbli-filiera" / "dossiers").mkdir(parents=True, exist_ok=True)
(MAIN / "data" / "kbli-filiera" / "dossiers" / "68112.jsonl").write_text("{}")

# a dir with NO infra/claude-hooks/data-plane-registry.json under it, for the
# missing-registry pass-through case.
_NO_REGISTRY_DIR = _TMP / "no-registry-project"
_NO_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

# a foreign git repository (A4): has its OWN .git, but does NOT carry our
# registry marker — must never be trusted as a Nuzantara checkout/worktree.
FOREIGN = _TMP / "foreign-repo"
(FOREIGN / ".git").mkdir(parents=True, exist_ok=True)
(FOREIGN / "data" / "kbli-filiera").mkdir(parents=True, exist_ok=True)

# malformed-registry project dirs (B1) — each carries a deliberately broken
# infra/claude-hooks/data-plane-registry.json to prove the loader degrades
# gracefully instead of crashing or over-blocking.
_MALFORMED_STRING_PROTECTED_DIR = _TMP / "malformed-string-protected"
(_MALFORMED_STRING_PROTECTED_DIR / "infra" / "claude-hooks").mkdir(parents=True, exist_ok=True)
(_MALFORMED_STRING_PROTECTED_DIR / "infra" / "claude-hooks" / "data-plane-registry.json").write_text(
    json.dumps({"entries": [{"id": "bad", "owner": "x", "compilers": "x",
                              "protected": "data/kbli-filiera/**"}]})
)

_MALFORMED_TOPLEVEL_LIST_DIR = _TMP / "malformed-toplevel-list"
(_MALFORMED_TOPLEVEL_LIST_DIR / "infra" / "claude-hooks").mkdir(parents=True, exist_ok=True)
(_MALFORMED_TOPLEVEL_LIST_DIR / "infra" / "claude-hooks" / "data-plane-registry.json").write_text("[]")

_MALFORMED_NULL_ENTRY_DIR = _TMP / "malformed-null-entry"
(_MALFORMED_NULL_ENTRY_DIR / "infra" / "claude-hooks").mkdir(parents=True, exist_ok=True)
(_MALFORMED_NULL_ENTRY_DIR / "infra" / "claude-hooks" / "data-plane-registry.json").write_text(
    json.dumps({"entries": [None]})
)


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


def monitor(cmd: str, cwd: str = str(MAIN)) -> dict:
    return {"tool_name": "Monitor", "tool_input": {
        "command": cmd, "description": "test", "timeout_ms": 5000,
        "persistent": False}, "cwd": cwd}


# (payload, expect, desc, env_extra) — expect in {"BLOCK", "ALLOW"}
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
    (bash("rm -rf data/kbli-filiera"), "BLOCK",
     "rm -rf on the BARE protected dir (no glob suffix) — the /** glob alone "
     "does not match the directory itself, needs the exact entry too", None),
    (bash("rm -rf data/kbli-filiera/"), "BLOCK",
     "same, with a trailing slash", None),
    (bash("mv data/source_documents/KBLI_2025_FINAL_CLEAN.json /tmp/x.json"), "BLOCK",
     "mv of a protected SOURCE — mv destroys its source, unlike cp/install/rsync", None),

    # -------------------------------------------------- GUILT (wave-2, A1/A3)
    (bash("true && rm data/kbli-filiera/dossiers/68112.jsonl"), "BLOCK",
     "A1 re-proof: a verb after && is still a real command, must still block", None),
    (bash("ssh mini hostname && cp /tmp/a data/source_documents/KBLI_2025_FINAL_CLEAN.json"),
     "BLOCK",
     "A3: the ssh prelude is remote, but the cp lives in a LATER, LOCAL "
     "segment — must still block (never a whole-command exemption)", None),

    # -------------------------------------------------------- GUILT (C1 case)
    (edit("data/source_documents/kbli_2025_final_clean.json"), "BLOCK",
     "C1: APFS is case-insensitive — a lowercase edit of the SAME real file "
     "must still block", None),
    (edit("data/KBLI-FILIERA/dossiers/x.json"), "BLOCK",
     "C1: uppercase directory variant of the protected dir must still block", None),

    # ------------------------------------------------------- GUILT (C2 Monitor)
    (monitor("printf x > data/source_documents/KBLI_2025_FINAL_CLEAN.json"), "BLOCK",
     "C2: Monitor executes the same shell channel as Bash, must be covered", None),

    # ------------------------------------------------------- GUILT (C3 quoted)
    (bash('echo x > "data/source_documents/KBLI_2025_FINAL_CLEAN.json"'), "BLOCK",
     "C3: a double-quoted redirect target must not become invisible", None),
    (bash("cp /tmp/a 'data/source_documents/KBLI_2025_FINAL_CLEAN.json'"), "BLOCK",
     "C3: a single-quoted cp destination must not become invisible", None),

    # --------------------------------------------------------- GUILT (C4 glob)
    (bash("rm data/kbli-filiera/dossiers/*.jsonl"), "BLOCK",
     "C4: glob expansion must resolve against the real file on disk", None),

    # ------------------------------------------------------ GUILT (C5 multi-file)
    (bash("sed -i '' 's/a/b/' data/source_documents/KBLI_2025_FINAL_CLEAN.json "
          "/tmp/control.json"), "BLOCK",
     "C5: sed -i mutates EVERY file argument, not just the last one", None),
    (bash("truncate -s 0 data/kbli-filiera/a.json /tmp/control.json"), "BLOCK",
     "C5: truncate mutates every file argument too", None),

    # ---------------------------------------------------- GUILT (C6 new verbs)
    (bash("dd if=/tmp/bad.json of=data/source_documents/KBLI_2025_FINAL_CLEAN.json"),
     "BLOCK", "C6: dd of= was entirely unrecognized before", None),
    (bash("touch data/kbli-filiera/newfile.json"), "BLOCK",
     "C6: touch was entirely unrecognized before", None),
    (bash("perl -pi -e 's/a/b/' data/kbli-filiera/manifest.json"), "BLOCK",
     "C6: perl -i was entirely unrecognized before", None),

    # --------------------------------------------------------- GUILT (C7 cd)
    (bash("cd data/source_documents && rm KBLI_2025_FINAL_CLEAN.json"), "BLOCK",
     "C7: a preceding cd changes the effective base for a relative rm target", None),

    # --------------------------------------------------------- GUILT (C8 bare)
    (bash("rm manifest", cwd=str(MAIN / "data" / "kbli-filiera")), "BLOCK",
     "C8: a bare filename (no separator/extension) with cwd already inside "
     "the protected dir must not escape via the plausibility filter", None),

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
    (bash("mv /tmp/a /tmp/b"), "ALLOW",
     "mv entirely outside the repo — neither source nor dest is protected", None),
    (bash("mv data/kbli-filiera-README.md /tmp/"), "ALLOW",
     "mv source has the adjacent (non-matching) prefix, not the protected dir", None),
    (bash("cp data/kbli-filiera/dossiers/x.json /tmp/"), "ALLOW",
     "cp FROM a protected path is a read of the source, not a write — must "
     "stay allowed (only cp's DEST is checked)", None),
    (edit("data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "same GUILTY path, but registry unreachable from this project dir "
     "→ pass-through with WARN", {"CLAUDE_PROJECT_DIR": str(_NO_REGISTRY_DIR)}),
    (edit("data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "same GUILTY path, but kill switch DATA_PLANE_GUARD_OFF=1",
     {"DATA_PLANE_GUARD_OFF": "1"}),

    # ----------------------------------------------------- INNOCENCE (A1/A2)
    (bash("grep rm data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "A1: 'rm' is grep's PATTERN argument, not a command — must not block", None),
    (bash("echo rm\ncat data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "A1: 'rm' as echo's argument on line 1 must not bleed into line 2's "
     "unrelated cat as a phantom arg (arg-separator must not cross \\n)", None),
    (bash("brew install jq"), "ALLOW",
     "A1: 'install' is brew's subcommand, not brew itself — anchored to "
     "command position, brew never matches our verb list either", None),
    (bash("true # rm data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "A2: an unquoted shell comment must never leak its content as a command", None),

    # --------------------------------------------------------- INNOCENCE (A3)
    (bash("ssh mini cp /tmp/a data/source_documents/KBLI_2025_FINAL_CLEAN.json"), "ALLOW",
     "A3: the whole payload is one remote-dispatched segment — the cp runs "
     "on Mini, never touches this checkout", None),

    # --------------------------------------------------------- INNOCENCE (A4)
    (write(str(FOREIGN / "data" / "kbli-filiera" / "mock.json")), "ALLOW",
     "A4: /tmp/foreign-repo has its own .git but is not a Nuzantara "
     "checkout (no registry marker) — must never be trusted", None),

    # --------------------------------------------------------- INNOCENCE (B1)
    (edit("README.md"), "ALLOW",
     "B1: a registry entry with a bare-STRING 'protected' field must be "
     "skipped, not iterated as characters (a lone '*' would else match "
     "everything)", {"CLAUDE_PROJECT_DIR": str(_MALFORMED_STRING_PROTECTED_DIR)}),
    (edit("data/kbli-filiera/dossiers/x.json"), "ALLOW",
     "B1: a top-level JSON array (not object) must degrade to pass-through, "
     "not crash on .get()", {"CLAUDE_PROJECT_DIR": str(_MALFORMED_TOPLEVEL_LIST_DIR)}),
    (edit("data/kbli-filiera/dossiers/x.json"), "ALLOW",
     "B1: a null entry in 'entries' must be skipped, not crash on .get()",
     {"CLAUDE_PROJECT_DIR": str(_MALFORMED_NULL_ENTRY_DIR)}),

    # --------------------------------------------------------- INNOCENCE (C1)
    (edit("data/kbli-filiera-README.MD"), "ALLOW",
     "C1: case-folding must not OVER-match — an already-unrelated adjacent "
     "file stays unrelated regardless of extension casing", None),

    # ----------------------------------------------------- INNOCENCE (C2)
    (monitor("cat data/kbli-filiera/dossiers/68112.jsonl"), "ALLOW",
     "C2: a read-only Monitor command must stay allowed", None),

    # ----------------------------------------------------- INNOCENCE (C3)
    (bash("git commit -m 'rm data/kbli-filiera/x.json'"), "ALLOW",
     "C3: quoted content WITH whitespace (a commit message) stays blanked, "
     "not unwrapped — only bare-path-shaped quoted content is preserved", None),

    # ----------------------------------------------------- INNOCENCE (C4)
    (bash("rm /tmp/nowhere-*.json"), "ALLOW",
     "C4: a glob pattern matching nothing on disk yields no candidates", None),

    # ----------------------------------------------------- INNOCENCE (C6)
    (bash("touch /tmp/scratch.json"), "ALLOW",
     "C6: touch of an unrelated file stays allowed", None),
    (bash("perl -e 'print 1'"), "ALLOW",
     "C6: perl WITHOUT -i never writes a file", None),

    # ----------------------------------------------------- INNOCENCE (C7)
    (bash("cd /tmp && rm x.json"), "ALLOW",
     "C7: cd to an unrelated dir, target resolves outside the repo entirely", None),
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
                    f"        payload={json.dumps(payload)[:200]}\n"
                    f"        stderr={err.strip()[:300]}"
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


def test_settings_json_wires_the_hook_correctly():
    """B2: CI must independently verify the .claude/settings.json wiring, not
    just the hook's own logic — a settings-only regression (wrong matcher,
    wrong filename) must fail this test even though it never touches
    data_plane_guard.py itself."""
    assert HOOK.exists(), f"hook file missing on disk: {HOOK}"
    assert SETTINGS_JSON.exists(), f"settings.json missing: {SETTINGS_JSON}"
    data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    pre_blocks = data.get("hooks", {}).get("PreToolUse", [])
    required_tools = {"Edit", "Write", "NotebookEdit", "Bash", "Monitor"}
    found = False
    for block in pre_blocks:
        matcher_tools = set(block.get("matcher", "").split("|"))
        if not required_tools <= matcher_tools:
            continue
        for h in block.get("hooks", []):
            if "infra/claude-hooks/data_plane_guard.py" in h.get("command", ""):
                found = True
    assert found, (
        "No PreToolUse block in .claude/settings.json has BOTH a matcher "
        f"covering {sorted(required_tools)} AND a command referencing "
        "infra/claude-hooks/data_plane_guard.py"
    )


def _run_all_module_tests() -> list[str]:
    """B3: execute every top-level test_* function in this module (skipping
    test_data_plane_guard itself, which __main__ already runs via evaluate()
    directly — avoids running the whole subprocess corpus twice). Used by
    BOTH pytest (implicitly, via its own collection) and the standalone
    __main__ runner below, so CI invoking this file directly (as
    hook-innocence-gate.yml does) sees the SAME coverage pytest would."""
    mod = sys.modules[__name__]
    failures: list[str] = []
    for name in sorted(dir(mod)):
        if not name.startswith("test_") or name == "test_data_plane_guard":
            continue
        fn = getattr(mod, name)
        if not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report, don't hide
            failures.append(f"{name}: unexpected error: {exc!r}")
    return failures


def _cleanup():
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    corpus_failures = evaluate()
    module_failures = _run_all_module_tests()
    all_failures = corpus_failures + module_failures
    if all_failures:
        print("data_plane_guard FAILED:")
        for f in all_failures:
            print(f"  - {f}")
        _cleanup()
        sys.exit(1)
    print(
        f"OK (data_plane_guard) — {len(CASES)} guilt+innocence cases + "
        f"{len([n for n in dir(sys.modules[__name__]) if n.startswith('test_') and n != 'test_data_plane_guard'])} "
        "module tests clean."
    )
    _cleanup()
    sys.exit(0)
