"""
Skills canonicity: `.claude/skills/` vs `.agents/skills/` must never drift
the wrong way.

CORRECTION (2026-08-26/27, this file's own authoring turn): the mandate that
requested this file ("Q0") was dispatched on a premise this turn falsified
by direct, repeated measurement — `git status`/`ls -la`/`find -type d`/
`git log`, not inference. It claimed `.agents/skills/` held 21 dirs with 11
`SKILL.md` files "DIVERGENT" from `.claude/skills/` counterparts (naming
`modus`/`workflow` as two of them), and that
`.agents/skills/modus/SKILL.md:149` still routed the Gear-3 harness verdict
gate to "Fable 5 first", contradicting the 2026-08-20 Fable-out ruling.

None of that holds. Measured instead:
  - `.agents/skills/` has 8 top-level skill dirs total (bot,
    bz-video-production, google-flow-video, kbli-navigator, secondhome,
    subhi, visaoracle, wr2) plus README.md — not 21.
  - `.agents/skills/modus/` does not exist AT ALL (no file, no line 149).
  - `.claude/skills/modus/SKILL.md` (the file that DOES exist) already
    correctly reflects the 2026-08-20 ruling — every "Fable 5 first"
    occurrence there is explicitly historical ("RULED 2026-08-20 — was
    'Fable 5 first, degrade to Opus on exhaustion' ... now moot").
  - The 11 skills that exist only under `.claude/skills/` are not
    "diverged" from an `.agents/skills/` counterpart — no such counterpart
    exists, or ever did (`git log --diff-filter=D` on
    `.agents/skills/modus*` and `.agents/skills/workflow*` returns nothing).

`.agents/skills/README.md` (established 2026-07-23, PR #3019 "chore(skills):
unify cross-agent skill stores") states why, and it is the actual contract
this file enforces: `.agents/skills/` is the canonical CROSS-AGENT (Tier-A)
store; a shared skill's `.claude/skills/<name>` is a SYMLINK into it (never
a copy — "if you find a real file where a symlink should be, it is
drift"); Claude-Code-specific orchestration skills ("Tier-B" — the README
names `workflow` itself as the paradigm example) stay real directories
under `.claude/skills/` ONLY and must NEVER be mirrored into
`.agents/skills/` ("stays in the owning tool's directory ... and is NOT
shared"). Mirroring `modus`/`workflow`/etc. into `.agents/skills/` — the
fix Q0 originally asked for — would have BEEN the regression, not the cure:
Kimi/Codex/Gemini CLIs that treat `.agents/skills/` as tool-agnostic ground
truth (per that same README) would start reading Claude-Code-only
orchestration prose as if it were shared doctrine.

This guard therefore protects the real invariant in both directions with
one structural rule that needs no hardcoded Tier-A/Tier-B allowlist for
the COPY case: whenever a name exists under BOTH trees,
`.claude/skills/<name>` must be a symlink whose target resolves to exactly
`.agents/skills/<name>`. A small pinned regression list (today's
known-good state) additionally asserts the specific drift/leak this
turn's investigation was dispatched to prevent stays fixed.

DISCLOSED GAP (Kimi K3 refuter round, 2026-08-27): the structural rule
only fires when a name exists on both sides, so it cannot see a Tier-B
skill that gets MOVED — not copied — into `.agents/skills/` (deleted from
`.claude/skills/` in the same change that adds it under
`.agents/skills/`). For skills that exist today, `KNOWN_CLAUDE_ONLY_NAMES`
closes that gap by pinning their names to stay real `.claude`-only
directories; for a Tier-B skill authored AFTER this file, nothing here
catches a move into the canonical store. Closing that fully would require
judging whether new content is tool-agnostic, which a directory-shape
check cannot do — a known, disclosed limit, not a claim of complete
coverage.
"""
from __future__ import annotations

import os
from pathlib import Path

# NUZ_SKILLS_ROOT (added 2026-08-27, team-lead finding): the real-repo tests
# below only ever inspected the checkout THIS file lives in — a clean git
# worktree/checkout never has untracked cruft, so it could never reproduce
# the actual failure mode. Measured independently on the Pro MAIN checkout
# (~/nuzantara, not a worktree): `git status --porcelain -- .agents/skills`
# shows 12 UNTRACKED dirs (11 exact Tier-B names + `source-command-resume`),
# all mtime 2026-08-19 00:26 — a one-shot manual/tool copy that git never
# saw. `.agents/skills/modus/SKILL.md` there is a genuinely stale 271-line
# copy (271 vs the tracked file's 280) whose Gear-3 row still reads "Fable 5
# first, rotating AZ->A2->A3->A1" — the exact text the original Q0 mandate
# described, just on the untracked file, not the tracked one this test
# suite was built against. No CI check can ever see this class of drift
# (CI only ever clones a specific commit; untracked files by construction
# never travel with it) — the override below lets this same suite be
# pointed at an arbitrary on-disk tree, so a LOCAL pre-push hook can run it
# against the real working directory instead.
_root_override = os.environ.get("NUZ_SKILLS_ROOT")
REPO_ROOT = Path(_root_override).resolve() if _root_override else Path(__file__).resolve().parents[2]
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
AGENTS_SKILLS = REPO_ROOT / ".agents" / "skills"

# Pinned regression state, measured on disk 2026-08-27 — not a completeness
# claim about every skill in either tree, just the specific names this
# turn's investigation is responsible for.
KNOWN_SHARED_NAMES = {"bot", "kbli-navigator", "secondhome", "visaoracle", "wr2"}
KNOWN_CLAUDE_ONLY_NAMES = {
    "agent-session-discipline",
    "final-gate-discipline",
    "intake",
    "karpathy-discipline",
    "modus",
    "pipeline-ship",
    "reuse-first",
    "skill-catalog",
    "slhs",
    "sota-architecture-loop",
    "workflow",
}


def find_canonicity_violations(claude_skills: Path, agents_skills: Path) -> list[str]:
    """Structural rule: name in BOTH trees => `.claude` side is a symlink
    resolving to the `.agents` side.

    Fires on either drift direction:
      - a shared skill's `.claude/skills/<name>` stops being a symlink
        (replaced by a real copy that can silently go stale), or
      - a Claude-Code-specific skill gets copied/mirrored into
        `.agents/skills/<name>` (it now exists on both sides, but the
        `.claude` side was never a symlink to begin with).
    A name present on only one side is not a violation by itself — that is
    the normal, intended shape for both Tier-A-not-yet-linked and
    Tier-B-never-shared skills.
    """
    violations: list[str] = []
    if not claude_skills.is_dir() or not agents_skills.is_dir():
        return violations

    agents_names = {p.name for p in agents_skills.iterdir()}

    for entry in sorted(claude_skills.iterdir()):
        name = entry.name
        if name not in agents_names:
            continue  # only in .claude — fine, nothing to compare against
        expected_target = (agents_skills / name).resolve()
        if not entry.is_symlink():
            violations.append(
                f"LEAK/DRIFT: '{name}' exists under both trees but "
                f".claude/skills/{name} is a real {'dir' if entry.is_dir() else 'file'}, "
                f"not a symlink to .agents/skills/{name}"
            )
            continue
        actual_target = Path(entry).resolve()
        if actual_target != expected_target:
            violations.append(
                f"DRIFT: .claude/skills/{name} is a symlink but resolves to "
                f"{actual_target}, not {expected_target}"
            )
    return violations


def _make_symlinked_pair(tmp_path: Path, name: str, content: str = "# ok\n") -> tuple[Path, Path]:
    """Build a minimal innocent `.claude/skills` + `.agents/skills` pair
    with one correctly-symlinked shared skill `name`."""
    claude_skills = tmp_path / "claude_skills"
    agents_skills = tmp_path / "agents_skills"
    claude_skills.mkdir()
    agents_skills.mkdir()
    real_dir = agents_skills / name
    real_dir.mkdir()
    (real_dir / "SKILL.md").write_text(content)
    # claude_skills/ and agents_skills/ are DIRECT siblings under tmp_path
    # here (unlike the real repo's `.claude/skills/` -> `.agents/skills/`,
    # which is two directories deep on each side) — one `..` reaches
    # tmp_path from inside claude_skills/, same as the real repo's two `..`
    # reach repo root from inside `.claude/skills/`.
    (claude_skills / name).symlink_to(Path("..") / "agents_skills" / name, target_is_directory=True)
    return claude_skills, agents_skills


# --------------------------------------------------------------- innocence


def test_innocence_correctly_symlinked_pair_has_no_violations(tmp_path: Path) -> None:
    claude_skills, agents_skills = _make_symlinked_pair(tmp_path, "shared-skill")
    assert find_canonicity_violations(claude_skills, agents_skills) == []


def test_innocence_claude_only_skill_is_not_a_violation(tmp_path: Path) -> None:
    """A Tier-B skill that exists ONLY under .claude/skills (never shared)
    is the normal, intended shape — not flagged."""
    claude_skills = tmp_path / "claude_skills"
    agents_skills = tmp_path / "agents_skills"
    claude_skills.mkdir()
    agents_skills.mkdir()
    (claude_skills / "modus-like").mkdir()
    (claude_skills / "modus-like" / "SKILL.md").write_text("# tool-specific\n")
    assert find_canonicity_violations(claude_skills, agents_skills) == []


def test_innocence_agents_only_skill_is_not_a_violation(tmp_path: Path) -> None:
    """A Tier-A skill not yet linked into .claude/skills is not itself a
    violation of THIS rule (a separate concern from what this guard checks)."""
    claude_skills = tmp_path / "claude_skills"
    agents_skills = tmp_path / "agents_skills"
    claude_skills.mkdir()
    agents_skills.mkdir()
    (agents_skills / "unlinked-skill").mkdir()
    (agents_skills / "unlinked-skill" / "SKILL.md").write_text("# shared, not yet linked\n")
    assert find_canonicity_violations(claude_skills, agents_skills) == []


# -------------------------------------------------------------------- guilt


def test_guilt_leaked_tool_specific_skill_copied_into_agents(tmp_path: Path) -> None:
    """The exact mistake Q0 originally asked for: a Claude-Code-specific
    skill (real dir, not a symlink) gets mirrored into `.agents/skills`."""
    claude_skills = tmp_path / "claude_skills"
    agents_skills = tmp_path / "agents_skills"
    claude_skills.mkdir()
    agents_skills.mkdir()
    (claude_skills / "modus-like").mkdir()
    (claude_skills / "modus-like" / "SKILL.md").write_text("# tool-specific\n")
    # Leaked copy — same name now exists as a REAL dir on the .agents side.
    (agents_skills / "modus-like").mkdir()
    (agents_skills / "modus-like" / "SKILL.md").write_text("# tool-specific\n")

    violations = find_canonicity_violations(claude_skills, agents_skills)
    assert len(violations) == 1
    assert "modus-like" in violations[0]
    assert "not a symlink" in violations[0]


def test_guilt_symlink_replaced_by_real_copy_is_drift(tmp_path: Path) -> None:
    """A shared skill's `.claude/skills/<name>` symlink gets replaced by an
    independent real copy — the copy can silently go stale."""
    claude_skills, agents_skills = _make_symlinked_pair(tmp_path, "shared-skill")
    (claude_skills / "shared-skill").unlink()
    (claude_skills / "shared-skill").mkdir()
    (claude_skills / "shared-skill" / "SKILL.md").write_text("# stale independent copy\n")

    violations = find_canonicity_violations(claude_skills, agents_skills)
    assert len(violations) == 1
    assert "shared-skill" in violations[0]
    assert "not a symlink" in violations[0]


def test_guilt_symlink_pointing_at_wrong_target_is_drift(tmp_path: Path) -> None:
    """Must resolve to a REAL, different directory inside the same store —
    not merely dangle — or this proves nothing beyond the dangling case
    `test_guilt_symlink_replaced_by_real_copy_is_drift` already covers via
    a different mechanism (Kimi K3 refuter round, 2026-08-27: the first
    version of this fixture used `../..`, which — since claude_skills/ and
    agents_skills/ are direct siblings under tmp_path, same as the
    innocence fixture's own `..` — escapes tmp_path entirely and points at
    a nonexistent path, so the violation it caught was "dangling symlink",
    not "resolves to the wrong real target" as the test name claims)."""
    claude_skills, agents_skills = _make_symlinked_pair(tmp_path, "shared-skill")
    (agents_skills / "decoy").mkdir()
    (agents_skills / "decoy" / "SKILL.md").write_text("# decoy\n")
    (claude_skills / "shared-skill").unlink()
    (claude_skills / "shared-skill").symlink_to(Path("..") / "agents_skills" / "decoy", target_is_directory=True)
    assert (claude_skills / "shared-skill").resolve() == (agents_skills / "decoy").resolve(), (
        "fixture bug: symlink must resolve to the real decoy dir, not dangle"
    )

    violations = find_canonicity_violations(claude_skills, agents_skills)
    assert len(violations) == 1
    assert "resolves to" in violations[0]


# ------------------------------------------------------------- real repo


def test_real_repo_both_skill_trees_exist() -> None:
    """`find_canonicity_violations` silently returns `[]` when either tree
    is missing (Kimi K3 refuter round, 2026-08-27) — a whole-architecture
    disappearance would otherwise pass `test_real_repo_has_zero_canonicity_violations`
    vacuously. Make the precondition explicit instead of relying on the
    pinned-name tests to catch it as a side effect."""
    assert CLAUDE_SKILLS.is_dir(), f"{CLAUDE_SKILLS} missing"
    assert AGENTS_SKILLS.is_dir(), f"{AGENTS_SKILLS} missing"


def test_real_repo_has_zero_canonicity_violations() -> None:
    violations = find_canonicity_violations(CLAUDE_SKILLS, AGENTS_SKILLS)
    assert violations == [], "\n".join(violations)


def test_real_repo_known_shared_names_are_symlinked_into_agents_skills() -> None:
    for name in sorted(KNOWN_SHARED_NAMES):
        link = CLAUDE_SKILLS / name
        assert link.is_symlink(), f".claude/skills/{name} should be a symlink"
        assert link.resolve() == (AGENTS_SKILLS / name).resolve()
        assert (link / "SKILL.md").exists(), f"{name} symlink target has no SKILL.md"


def test_real_repo_claude_only_names_never_leak_into_agents_skills() -> None:
    """Pins the exact set Q0 would have copied into `.agents/skills/` had
    its original (false) premise been executed unchecked."""
    agents_names = {p.name for p in AGENTS_SKILLS.iterdir()} if AGENTS_SKILLS.is_dir() else set()
    leaked = KNOWN_CLAUDE_ONLY_NAMES & agents_names
    assert leaked == set(), f"Tier-B skill(s) leaked into .agents/skills: {sorted(leaked)}"
    for name in sorted(KNOWN_CLAUDE_ONLY_NAMES):
        entry = CLAUDE_SKILLS / name
        assert entry.is_dir() and not entry.is_symlink(), (
            f".claude/skills/{name} expected to be a real (Tier-B) directory"
        )


def test_modus_skill_reflects_the_2026_08_20_fable_out_ruling() -> None:
    """Positive assertion, not a fragile substring-absence check: the
    historical '...was \"Fable 5 first...\"' quote is expected to stay in
    this file's changelog-style prose forever. What must never regress is
    the ruling itself being documented as current."""
    text = (CLAUDE_SKILLS / "modus" / "SKILL.md").read_text()
    assert "RULED 2026-08-20" in text
    assert "Fable" in text and "out of the workflow" in text
