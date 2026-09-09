"""
Byte-budget + link-integrity tripwire for `CLAUDE.md` (root) and every
per-folder `CLAUDE.md`.

Context-diet (2026-09-04, plan `goofy-purring-pillow`, mandate "root CLAUDE.md
becomes an index — specialist content moves to lazy per-folder files"): the
repo-root `CLAUDE.md` was 51,270 bytes and injected in full at every session
start. Specialist content (Code Golden Rules, Data Invariants, Postgres MCP,
Deploy Lifecycle, Operational Channels; Research Capture Convention; the
Claude-5 routing ruling chains; behavior/PR-mechanics/anti-hallucination/
hooks/critical-ops content) was MOVED verbatim (never rewritten, never
deleted) into `apps/backend-rag/CLAUDE.md`, `research/CLAUDE.md`,
`.claude/rules/RULINGS.md` and `.claude/rules/operations.md`. Claude Code
loads a folder's `CLAUDE.md` natively and lazily when working there, so the
same content now costs tokens only when it is actually relevant — this
guard is what keeps the root file from quietly regrowing back into the same
disease (superscar family #2, "Esiste ≠ Armato": a document that claims to
be a thin index but is secretly carrying the full corpus again).

This guard is three things, deliberately kept together:

1. A byte-budget assertion on the root `CLAUDE.md` (<=16KB).
2. A byte-budget assertion on every OTHER `CLAUDE.md` in the repo (<=12KB
   each) — this also covers the four per-app files that already existed
   before this diet (`apps/bali-intel-scraper`, `apps/mata-garuda`,
   `apps/mouth`, `apps/nuzantara-mcp-browser`), not just the two new ones.
3. A completeness assertion: the root CANON block
   (`<!-- CANON:builder-contract -->` ... `<!-- /CANON:builder-contract -->`)
   is present and non-empty, and every file path cited in the root's
   "## INDICE — dove sta cosa" section resolves to a real file on disk — a
   dangling pointer in an index file is worse than no index at all.
4. An anti-regression guard on `.claude/rules/`: a file dropped into that
   directory WITHOUT `paths:` frontmatter is auto-injected into every session
   and every subagent, no scoping — that is exactly what `RULINGS.md` and
   `operations.md` were doing until 2026-09-04, when they were moved to
   `docs/rules/` for that reason (see their own file headers). The one
   deliberate exception is `cicatrix-superscar.md`, which is meant to be
   always-injected. This guard fails if a second paths-less file appears.

Deliberately excluded from the per-folder scan: anything under
`scripts/tests/fixtures/` — that tree holds fixture CLAUDE.md files used by
OTHER tests (e.g. `scripts/tests/fixtures/docs_audit/repo/CLAUDE.md`), not
real project documentation, and is not part of the boot-tax surface this
guard exists to protect.

One named exception to the 12KB subfolder budget: `apps/backend-rag/CLAUDE.md`
already existed (403 lines / 20,566 bytes of backend-specific "non-inferable
knowledge" — Sentry PII redaction, migration-runner gotchas, Drive OAuth,
Ollama vision model, ...) *before* this diet's mandate named that same path
as the destination for the root's §8-§12 (Code Golden Rules / Data
Invariants / Postgres MCP / Deploy Lifecycle / Operational Channels). The
mandate's hard rule is "move verbatim, never delete" — shrinking the
pre-existing content was out of scope, so the two bodies were concatenated
rather than one overwriting the other, and the merged file is 28,113 bytes.
Shrinking either body back under 12KB is a separate, deliberate editorial
pass this guard does not force.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ROOT_CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
RULES_DIR = REPO_ROOT / ".claude" / "rules"

# The one file in .claude/rules/ that is DELIBERATELY always-injected (no
# `paths:` frontmatter) — the superscar bridge, by design. Every other file
# in that directory must be scoped, or it is auto-loaded into every session
# regardless of relevance (the exact bug that sent RULINGS.md/operations.md
# to docs/rules/ instead).
ALWAYS_INJECTED_RULES_EXCEPTION = "cicatrix-superscar.md"

ROOT_BYTE_BUDGET = 16 * 1024  # 16KB
SUBFOLDER_BYTE_BUDGET = 12 * 1024  # 12KB

# apps/backend-rag/CLAUDE.md pre-dates this diet with its own 20,566-byte
# body of backend-specific gotchas; the diet's mandate appended §8-§12 from
# root rather than overwrite it (see module docstring). Named, not silent —
# any OTHER file over budget still fails.
SUBFOLDER_BUDGET_EXCEPTIONS = {"apps/backend-rag/CLAUDE.md"}

CANON_START = "<!-- CANON:builder-contract -->"
CANON_END = "<!-- /CANON:builder-contract -->"

# Markdown inline-code pointer, e.g. `apps/backend-rag/CLAUDE.md` or
# `.claude/rules/RULINGS.md` — the INDICE section cites every destination
# this way.
_BACKTICK_PATH_RE = re.compile(r"`([\w./-]+\.[\w-]+)`")

_FIXTURES_PREFIX = "scripts/tests/fixtures/"


def discover_claude_md_files() -> list[Path]:
    """Every CLAUDE.md in the repo except the root one and fixture copies."""
    found = []
    for p in REPO_ROOT.rglob("CLAUDE.md"):
        if p == ROOT_CLAUDE_MD:
            continue
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(_FIXTURES_PREFIX):
            continue
        if "/.worktrees/" in f"/{rel}" or rel.startswith(".worktrees/"):
            continue
        if "/node_modules/" in f"/{rel}" or "/.venv/" in f"/{rel}":
            continue
        found.append(p)
    return found


def extract_canon_block(text: str) -> str | None:
    start = text.find(CANON_START)
    end = text.find(CANON_END)
    if start == -1 or end == -1 or end < start:
        return None
    return text[start : end + len(CANON_END)]


def extract_indice_section(text: str) -> str | None:
    """The '## INDICE — dove sta cosa' section body, up to the next H2."""
    lines = text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## INDICE"):
            start_idx = i
            break
    if start_idx is None:
        return None
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            end_idx = i
            break
    return "\n".join(lines[start_idx:end_idx])


def has_paths_frontmatter(text: str) -> bool:
    """True if `text` opens with a YAML frontmatter block (starts with a `---`
    line) that contains a `paths:` key before the closing `---`."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False  # closed the frontmatter without ever seeing paths:
        if line.strip().startswith("paths:"):
            return True
    return False


def pointer_paths_in(text: str) -> set[str]:
    """Every backtick-quoted path-shaped token in the given text that looks
    like a repo-relative file reference (contains a '/' and an extension)."""
    paths = set()
    for m in _BACKTICK_PATH_RE.findall(text):
        if "/" in m:
            paths.add(m)
    return paths


class TestGuiltACanonBlockDrift:
    def test_a_missing_canon_start_marker_is_flagged(self) -> None:
        assert extract_canon_block("no markers here") is None

    def test_a_reversed_marker_order_is_flagged(self) -> None:
        text = f"{CANON_END}\nsome text\n{CANON_START}"
        assert extract_canon_block(text) is None


class TestGuiltADanglingPointer:
    def test_an_indice_row_naming_a_nonexistent_file_is_a_real_gap(
        self, tmp_path: Path
    ) -> None:
        fake_root = tmp_path
        (fake_root / "CLAUDE.md").write_text(
            "## INDICE — dove sta cosa\n\n"
            "| X | Y | `nonexistent/file.md` |\n\n"
            "## Next section\n",
            encoding="utf-8",
        )
        text = (fake_root / "CLAUDE.md").read_text(encoding="utf-8")
        indice = extract_indice_section(text)
        assert indice is not None
        paths = pointer_paths_in(indice)
        assert "nonexistent/file.md" in paths
        assert not (fake_root / "nonexistent/file.md").exists()


class TestGuiltAPathslessRulesFile:
    def test_a_rules_file_with_no_frontmatter_at_all_is_flagged(self) -> None:
        assert has_paths_frontmatter("# just a heading\n\nsome prose\n") is False

    def test_a_frontmatter_block_missing_the_paths_key_is_flagged(self) -> None:
        text = "---\ntitle: something else entirely\n---\n\nbody\n"
        assert has_paths_frontmatter(text) is False


class TestInnocenceOfTheGuardItself:
    def test_the_indice_section_stops_at_the_next_h2_not_the_end_of_file(
        self,
    ) -> None:
        text = (
            "## INDICE — dove sta cosa\n\n"
            "row one\n\n"
            "## Regole sempre-applicabili\n\n"
            "unrelated content that must not count as an indice pointer\n"
        )
        indice = extract_indice_section(text)
        assert indice is not None
        assert "unrelated content" not in indice

    def test_pointer_extraction_ignores_bare_identifiers_without_a_slash(
        self,
    ) -> None:
        # `AGENT_BROKER_ENABLED` and similar env-var-shaped backtick spans
        # must not be misread as file paths.
        assert pointer_paths_in("see `AGENT_BROKER_ENABLED=false` for the kill switch") == set()

    def test_single_line_paths_frontmatter_is_recognized(self) -> None:
        text = '---\npaths: ["scripts/generate_*.py"]\n---\n\nbody\n'
        assert has_paths_frontmatter(text) is True

    def test_multiline_paths_frontmatter_is_recognized(self) -> None:
        text = '---\npaths:\n  [\n    "apps/mouth/**/*.ts",\n  ]\n---\n\nbody\n'
        assert has_paths_frontmatter(text) is True


class TestTheRealFilesAreClean:
    """The actual guard run — pins the corrected state, catches the next relapse."""

    def test_root_claude_md_stays_under_the_byte_budget(self) -> None:
        size = ROOT_CLAUDE_MD.stat().st_size
        assert size <= ROOT_BYTE_BUDGET, (
            f"CLAUDE.md (root) is {size} bytes, over the {ROOT_BYTE_BUDGET}-byte "
            "boot-tax budget. Move any specialist content verbatim into the "
            "matching per-folder CLAUDE.md or .claude/rules/ file and leave only "
            "an INDICE pointer here."
        )

    def test_every_subfolder_claude_md_stays_under_its_byte_budget(self) -> None:
        offenders = []
        for p in discover_claude_md_files():
            rel = p.relative_to(REPO_ROOT).as_posix()
            if rel in SUBFOLDER_BUDGET_EXCEPTIONS:
                continue
            size = p.stat().st_size
            if size > SUBFOLDER_BYTE_BUDGET:
                offenders.append((rel, size))
        assert offenders == [], (
            f"{len(offenders)} per-folder CLAUDE.md file(s) over the "
            f"{SUBFOLDER_BYTE_BUDGET}-byte budget: {offenders}"
        )

    def test_every_named_exception_still_exists_and_is_still_over_budget(self) -> None:
        """A stale exception (file shrunk back under budget, or deleted) is a
        silently-widening allowlist — catch it so the exception set stays honest."""
        for rel in SUBFOLDER_BUDGET_EXCEPTIONS:
            p = REPO_ROOT / rel
            assert p.exists(), f"budget exception {rel!r} no longer exists — remove it"
            assert p.stat().st_size > SUBFOLDER_BYTE_BUDGET, (
                f"{rel} is now back under the {SUBFOLDER_BYTE_BUDGET}-byte budget — "
                "remove it from SUBFOLDER_BUDGET_EXCEPTIONS."
            )

    def test_root_canon_block_is_present_and_non_empty(self) -> None:
        text = ROOT_CLAUDE_MD.read_text(encoding="utf-8")
        block = extract_canon_block(text)
        assert block is not None, (
            "CLAUDE.md (root) is missing the CANON:builder-contract block — "
            "scripts/proprioception.py's door_canon_parity probe depends on it "
            "being present and byte-identical to AGENTS.md/GEMINI.md/QWEN.md."
        )
        inner = block[len(CANON_START) : -len(CANON_END)].strip()
        assert inner, "CANON block is present but empty in CLAUDE.md (root)."

    def test_every_pointer_in_the_root_indice_resolves_to_a_real_file(self) -> None:
        text = ROOT_CLAUDE_MD.read_text(encoding="utf-8")
        indice = extract_indice_section(text)
        assert indice is not None, (
            "CLAUDE.md (root) has no '## INDICE — dove sta cosa' section — "
            "the context-diet mandate requires one."
        )
        paths = pointer_paths_in(indice)
        assert paths, "INDICE section has no file-shaped pointers to check."
        missing = sorted(p for p in paths if not (REPO_ROOT / p).exists())
        assert missing == [], (
            f"{len(missing)} pointer(s) in the root INDICE section do not resolve "
            f"to a real file: {missing}"
        )

    def test_every_claude_rules_file_except_the_named_exception_has_paths_frontmatter(
        self,
    ) -> None:
        offenders = []
        for p in sorted(RULES_DIR.glob("*.md")):
            if p.name == ALWAYS_INJECTED_RULES_EXCEPTION:
                continue
            text = p.read_text(encoding="utf-8")
            if not has_paths_frontmatter(text):
                offenders.append(p.relative_to(REPO_ROOT).as_posix())
        assert offenders == [], (
            f"{len(offenders)} file(s) in .claude/rules/ have no `paths:` frontmatter, "
            f"which means they are auto-injected into EVERY session and subagent: "
            f"{offenders}. Either add scoping `paths:` frontmatter, or move the file "
            "out of .claude/rules/ (e.g. to docs/rules/) if it should be loaded "
            "on demand instead of always."
        )
