#!/usr/bin/env python3
"""Pin the ~/.claude carve-outs in host_boundary.py — both halves.

Why this exists: the carve-outs (`UNPROTECTED_SUBPATHS`) lived ONLY in the live
copy at ~/.claude/hooks/ from 2026-06-16 until they were promoted to the repo on
2026-08-12 — seven weeks in which `install_phase_aware.sh`, the sanctioned way to
deploy these hooks, would have overwritten them with the repo's version and
silently re-blocked the agent's own memory directory. The installer was a mine on
the path it is documented as.

`test_host_boundary.py` passes with or without the carve-out — it never names it.
So the promotion alone would leave them unpinned, one tidy-up away from vanishing
again. This file asserts both directions, because a carve-out is a guard with the
sign inverted and wants its own guilt and innocence:

  innocence — the freed subpaths are writable. These are the agent's hands and
              notebook: ~/.claude/scripts, its memory under projects/, the WR2
              learning outputs. Blocking them does not protect anything; it just
              makes agents run and lose their work.
  guilt     — the control plane is STILL blocked. hooks/ and settings.json are
              the brain and the keys. If a future widening lets those through,
              the carve-out has eaten the guard it was carved out of.

Run directly, or under pytest.
"""
import json
import pathlib
import subprocess
import sys

HOOK = pathlib.Path(__file__).resolve().parent / "host_boundary.py"
HOME = pathlib.Path.home()

# (path, expected_rc, why). 0 = allowed through, 2 = blocked.
CASES = [
    # ── innocence: the agent's hands and notebook ───────────────────────────
    (HOME / ".claude" / "projects" / "-Users-x-y" / "memory" / "a-note.md", 0,
     "the agent's memory — every `mem save` writes here"),
    (HOME / ".claude" / "scripts" / "helper.sh", 0, "the agent's own tools"),
    (HOME / ".claude" / "venvs" / "x" / "pyvenv.cfg", 0, "agent venvs"),
    # The three WR2 entries below pass, but NOT because the carve-out frees
    # them: measured 2026-08-12, ~/.claude/skills/bali-zero-brand is a symlink
    # to ~/nuzantara/skills/bali-zero-brand, so these paths resolve OUTSIDE
    # ~/.claude and were never protected in the first place. They are inert
    # entries today and would only start doing work if that symlink went away.
    # Kept, and asserted, so the fact is recorded where the next reader looks.
    (HOME / ".claude" / "skills" / "bali-zero-brand" / "_lessons" / "l.md", 0,
     "WR2 Reflexion output (allowed via the repo symlink, not via the carve-out)"),
    (HOME / ".claude" / "skills" / "bali-zero-brand" / "_proposed-amendments" / "a.md", 0,
     "WR2 amendment proposals (same symlink)"),
    (HOME / ".claude" / "skills" / "bali-zero-brand" / "_observations" / "o.md", 0,
     "WR2 observations (same symlink)"),

    # ── guilt: the control plane and the keys stay shut ─────────────────────
    (HOME / ".claude" / "hooks" / "orchestrate_gate.py", 2,
     "a hook — writing it disarms guardrails"),
    (HOME / ".claude" / "settings.json", 2, "the control plane itself"),
    # NOT a guilt case, and the first draft of this file wrongly asserted it
    # was: a curated skill body under that symlink is repo content, not the
    # agent control plane, so host_boundary is right to pass it. What guards it
    # is the worktree-isolation hook, a different guard with a different job.
    # Recorded as an explicit 0 so nobody "fixes" host_boundary to block it.
    (HOME / ".claude" / "skills" / "bali-zero-brand" / "SKILL.md", 0,
     "repo content behind a symlink — guarded by worktree isolation, not this hook"),
    (HOME / ".claude" / "CLAUDE.md", 2, "global instructions"),
]


def _rc(path: pathlib.Path) -> int:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True).returncode


def test_carveouts_are_writable_and_control_plane_is_not():
    bad = []
    for path, expect, why in CASES:
        got = _rc(path)
        if got != expect:
            bad.append(f"{path} -> rc={got}, want {expect} ({why})")
    assert not bad, "host_boundary carve-out drifted:\n  " + "\n  ".join(bad)


if __name__ == "__main__":
    failures = 0
    for path, expect, why in CASES:
        got = _rc(path)
        ok = got == expect
        failures += 0 if ok else 1
        verdict = "allowed" if expect == 0 else "blocked"
        print(f"  [{'OK  ' if ok else 'FAIL'}] rc={got} want={expect} ({verdict}) — {why}")
    print()
    print("PASS — host_boundary carve-out pinned" if not failures else f"FAIL ({failures})")
    sys.exit(1 if failures else 0)
