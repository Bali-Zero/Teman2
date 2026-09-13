"""test_startup_tax_budget.py — startup-tax budget guard for agent/skill descriptions.

Context (2026-09-02, Lane D of the startup-tax trim mandate): Zero's `/context` on M5
(Opus 5) measured custom agents (`.claude/agents/`, 45 files at the time — this repo's
`.claude/agents/` holds 20 actual agent definitions plus a README and 4 wr2-design-
architect resource docs that carry no `description:` frontmatter and are excluded here;
the remaining ~25 named in that count live outside this repo, e.g. user-level
`~/.claude/agents/`) at 10.5k tokens and skills (119 total across the session, of which
only 20 unique `SKILL.md` files live inside this repo's `.claude/skills/` +
`.agents/skills/` trees — the rest are user-level "corner" skills, plugin skills, and
document-skills outside repo scope) at 10k tokens — paid by EVERY session and EVERY
subagent before any work happens, because the harness loads every registered agent's and
skill's `name:` + `description:` frontmatter into context up front (body content loads
only when the agent/skill actually runs).

Only each `description:` field is measured here — not the whole file — because that is
the part the harness pre-loads for every agent/skill regardless of whether it is ever
used. This test guards the two mechanical levers this repo scope controls: a per-file
character ceiling (so no single description balloons back to pre-trim size) and a
total-bytes ceiling across each tree (so many small descriptions don't collectively
regress). It does NOT — and cannot — reduce the majority of Zero's measured 10k/10.5k
session totals, most of which comes from outside this repo's two trees; see the trim
PR body for the measured split.

Skills are deduplicated by `os.path.realpath()` before totalling: six `.claude/skills/*`
entries (`bot`, `design`, `kbli-navigator`, `secondhome`, `visaoracle`, `wr2`) are
symlinks into `.agents/skills/*` per `.agents/skills/README.md`'s Tier-A/Tier-B contract
(PR #3019) — counting both sides would double-count the same on-disk bytes and the same
context-window cost (the harness reads through the symlink once per registered name, but
the FILE the frontmatter lives in is the same file; editing it changes both surfaces at
once, so the budget must be measured once, not twice).

Extraction deliberately uses a permissive regex/continuation scan, NOT strict YAML
(`yaml.safe_load`), because a chunk of this repo's pre-existing agent frontmatter (the
7 GRUNT-tier defs enforced by test_agent_defs_model_pins.py's DESCRIPTION_GRUNT_RE) uses
an UNQUOTED `description: GRUNT (Haiku): ...` value whose embedded ": " sequence strict
PyYAML block-mapping parsing rejects with "mapping values are not allowed here" — a
pre-existing, unrelated condition on `origin/main` (verified via `git show
origin/main:<path> | python3 -c 'import yaml; yaml.safe_load(...)'` before this file was
written) this test must tolerate rather than "fix", since fixing it by force-quoting
those 7 descriptions was tried and reverted: it broke DESCRIPTION_GRUNT_RE, which matches
the literal unquoted string `description: GRUNT (Haiku):` with no quote character
between the colon and the word GRUNT.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
CLAUDE_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DOTAGENTS_SKILLS_DIR = REPO_ROOT / ".agents" / "skills"

AGENT_DESC_CHAR_LIMIT = 280
SKILL_DESC_CHAR_LIMIT = 200

# Measured 2026-09-02 after the trim: agents 4074 bytes, skills 3737 bytes (unique).
# Ceiling = measured + 10% headroom (rounded), per the mandate's instruction to set the
# ceiling from what was actually measured rather than an arbitrary round number.
AGENT_TOTAL_BYTES_CEILING = 4481
SKILL_TOTAL_BYTES_CEILING = 4110

_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:\s")
_DESC_START_RE = re.compile(r"^description:\s*(.*)$")


def _extract_frontmatter(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return text[3:end]


def _extract_description(fm: str) -> str:
    """Permissive extractor: handles unquoted, single/double-quoted, and folded ('>')
    description values. Mirrors the ad hoc measurement script used to size this trim
    (not committed) so the numbers in this test match what was actually measured."""
    lines = fm.split("\n")
    out: list[str] = []
    capturing = False
    for line in lines:
        m = _DESC_START_RE.match(line)
        if m:
            capturing = True
            first = m.group(1).strip()
            if first and not first.startswith("|") and not first.startswith(">"):
                out.append(first)
            continue
        if capturing:
            if _TOP_LEVEL_KEY_RE.match(line) or (line.strip() == "" and out):
                capturing = False
                continue
            if line.startswith(" ") or line.startswith("\t"):
                out.append(line.strip())
            else:
                capturing = False
    val = " ".join(out).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1]
    return val


def _agent_def_paths() -> list[Path]:
    assert AGENTS_DIR.is_dir(), f"{AGENTS_DIR} missing"
    paths = []
    for p in sorted(AGENTS_DIR.glob("*.md")):
        if p.name == "README.md":
            continue
        paths.append(p)
    assert paths, f"no agent .md files found under {AGENTS_DIR}"
    return paths


def _skill_def_paths() -> list[Path]:
    """Unique SKILL.md files across .claude/skills/*/ and .agents/skills/*/, deduped
    by realpath so a .claude/skills/<name> symlink into .agents/skills/<name> is
    counted once, matching what the harness actually loads once per skill name."""
    candidates = []
    if CLAUDE_SKILLS_DIR.is_dir():
        candidates.extend(sorted(CLAUDE_SKILLS_DIR.glob("*/SKILL.md")))
    if DOTAGENTS_SKILLS_DIR.is_dir():
        candidates.extend(sorted(DOTAGENTS_SKILLS_DIR.glob("*/SKILL.md")))
    assert candidates, "no SKILL.md files found under .claude/skills/ or .agents/skills/"
    seen_real: set[str] = set()
    unique: list[Path] = []
    for p in candidates:
        real = os.path.realpath(p)
        if real in seen_real:
            continue
        seen_real.add(real)
        unique.append(p)
    return unique


def _load_description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    assert fm is not None, f"{path}: missing --- frontmatter block"
    desc = _extract_description(fm)
    assert desc, f"{path}: empty or missing description field"
    return desc


# ---------------------------------------------------------------------------
# Per-file character-limit tests (innocence: real files must stay under budget)
# ---------------------------------------------------------------------------


def test_every_agent_description_is_within_char_limit():
    offenders = []
    for path in _agent_def_paths():
        desc = _load_description(path)
        if len(desc) > AGENT_DESC_CHAR_LIMIT:
            offenders.append((path, len(desc)))
    assert not offenders, (
        f"agent description(s) exceed {AGENT_DESC_CHAR_LIMIT} chars "
        f"(move detail into the agent body under '## Notes (moved from description)'): "
        + ", ".join(f"{p.relative_to(REPO_ROOT)}={n}ch" for p, n in offenders)
    )


def test_every_skill_description_is_within_char_limit():
    offenders = []
    for path in _skill_def_paths():
        desc = _load_description(path)
        if len(desc) > SKILL_DESC_CHAR_LIMIT:
            offenders.append((path, len(desc)))
    assert not offenders, (
        f"skill description(s) exceed {SKILL_DESC_CHAR_LIMIT} chars "
        f"(move detail into the SKILL.md body under '## Notes (moved from description)'): "
        + ", ".join(f"{p.relative_to(REPO_ROOT)}={n}ch" for p, n in offenders)
    )


# ---------------------------------------------------------------------------
# Total-bytes ceiling tests (catches "many small regressions" the per-file test misses)
# ---------------------------------------------------------------------------


def test_agent_descriptions_total_bytes_under_ceiling():
    total = sum(len(_load_description(p).encode("utf-8")) for p in _agent_def_paths())
    assert total <= AGENT_TOTAL_BYTES_CEILING, (
        f"agent description total grew to {total} bytes, ceiling is "
        f"{AGENT_TOTAL_BYTES_CEILING} (measured 4074B on 2026-09-02 + 10% headroom)"
    )


def test_skill_descriptions_total_bytes_under_ceiling():
    total = sum(len(_load_description(p).encode("utf-8")) for p in _skill_def_paths())
    assert total <= SKILL_TOTAL_BYTES_CEILING, (
        f"skill description total grew to {total} bytes, ceiling is "
        f"{SKILL_TOTAL_BYTES_CEILING} (measured 3737B on 2026-09-02 + 10% headroom)"
    )


# ---------------------------------------------------------------------------
# Guilt twins: the same char-limit assertion must actually fire on a synthetic
# oversized description, proving the check is load-bearing and not a tautology
# (cicatrix-superscar.md #3 antidote — guilt+innocence on the SAME helper).
# ---------------------------------------------------------------------------


def _assert_desc_within_limit(desc: str, limit: int, label: str) -> None:
    assert len(desc) <= limit, f"{label} description exceeds {limit} chars"


def test_guilt_oversized_agent_description_is_rejected():
    oversized = "x" * (AGENT_DESC_CHAR_LIMIT + 1)
    with pytest.raises(AssertionError):
        _assert_desc_within_limit(oversized, AGENT_DESC_CHAR_LIMIT, "synthetic-agent")


def test_guilt_oversized_skill_description_is_rejected():
    oversized = "x" * (SKILL_DESC_CHAR_LIMIT + 1)
    with pytest.raises(AssertionError):
        _assert_desc_within_limit(oversized, SKILL_DESC_CHAR_LIMIT, "synthetic-skill")


def test_innocence_boundary_description_at_exact_limit_passes():
    at_limit_agent = "x" * AGENT_DESC_CHAR_LIMIT
    _assert_desc_within_limit(at_limit_agent, AGENT_DESC_CHAR_LIMIT, "synthetic-agent")
    at_limit_skill = "x" * SKILL_DESC_CHAR_LIMIT
    _assert_desc_within_limit(at_limit_skill, SKILL_DESC_CHAR_LIMIT, "synthetic-skill")


def test_skill_dedup_actually_drops_symlink_duplicates():
    """Guilt/innocence for the dedup logic itself: .claude/skills/wr2 is a known
    symlink into .agents/skills/wr2 (per .agents/skills/README.md's Tier-A contract).
    If dedup silently stopped working, this repo's total-bytes ceiling test would
    pass while actually double-counting — this test catches that regression class
    directly rather than trusting the total alone."""
    claude_wr2 = CLAUDE_SKILLS_DIR / "wr2"
    dotagents_wr2 = DOTAGENTS_SKILLS_DIR / "wr2"
    if not (claude_wr2.is_symlink() and dotagents_wr2.is_dir()):
        pytest.skip("wr2 skill symlink topology not present on this checkout")
    assert os.path.realpath(claude_wr2 / "SKILL.md") == os.path.realpath(
        dotagents_wr2 / "SKILL.md"
    )
    paths = _skill_def_paths()
    reals = [os.path.realpath(p) for p in paths]
    assert len(reals) == len(set(reals)), "skill dedup let a duplicate real path through"
