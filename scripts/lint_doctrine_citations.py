from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Doctrine surface scanned by default. Kept as a module constant so CI and humans
# can audit the lint's scope in one place without reading the whole extractor.
# NOT a subject, and the reason is the same one that governs the audit trees in
# `test_injected_surface_budget.py`: `.claude/skills/modus/PENDING-ARMS.md` is an
# append-only DATED ledger whose rows are byte-immutable by CI
# (`check-ledger-no-silent-loss` compares them to origin/main line-for-line). A
# row citing a file that was later deleted is a record of what was true when the
# row was written, not a live claim that the file backs an argument — and it
# cannot be corrected even if one wanted to. Measured 2026-08-31: it accounts for
# 6 of the 6 remaining findings, all of that shape.
_EXCLUDED_SUBJECTS: frozenset[str] = frozenset({".claude/skills/modus/PENDING-ARMS.md"})

DEFAULT_SUBJECTS: tuple[str, ...] = (
    ".claude/skills/**/*.md",
    ".claude/commands/*.md",
    "CLAUDE.md",
    "SYMBIOSIS.md",
    "VADEMECUM.md",
    "INDEX.md",
    "AUTONOMOUS_OPS.md",
)

# Citations are research/... or docs/... tokens ending in a file extension.
# `(?<![\w/.~-])` and NOT `\b`: `\b` matches immediately after a slash, so
# `apps/mata-garuda/docs/X.md` yielded a citation to `docs/X.md` — a path that
# does not exist while the real one, three segments to the left, does. Measured
# on SYMBIOSIS.md: all four of its "phantom" citations were this artifact, two
# of them pointing at files that exist under apps/, and two at another project
# entirely (`~/Desktop/OSINT-Nexus/docs/...`). A lint that reddens correct
# doctrine is a lint someone disables, and it would have been red on this
# repo's most load-bearing document (superscar #3, guard-over-match).
# `\.?/?` lets a `./`-prefixed path match in prose; the lookbehind still refuses
# a path that is merely a SUFFIX of a longer one (`apps/x/docs/y.md`), which is
# the over-match this anchor exists for.
_PATH_RE = re.compile(r"(?<![\w/~-])\.?/?(research|docs)/[\w./-]+\.\w+\b")
# Markdown link URLs: we only care about the parenthesised path.
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Inline code spans delimited by a single backtick.
_BACKTICK_RE = re.compile(r"`([^`]+)`")
# A ':line' suffix (e.g. docs/x.md:42) or '#anchor' suffix.
_ANCHOR_OR_LINE_RE = re.compile(r"[#:].*$")

# Shell words that, when they appear before a path inside the same backtick span,
# turn that span into a command example rather than a citation.
_SHELL_WORDS: frozenset[str] = frozenset({
    "bash", "cat", "cd", "chmod", "cp", "cargo", "find", "go", "grep", "head",
    "less", "ls", "make", "mkdir", "more", "mv", "nano", "node", "npm", "npx",
    "pip", "python", "python3", "pytest", "rm", "rustc", "sed", "sh", "tail",
    "touch", "vim",
})


# A citation names a FILE. `docs/` and `research/operations/` are directories, and
# a bare directory in prose is a location, not a source — the reader is not being
# told "this claim is backed by that". Requiring an extension is what separates
# the two, and without it this lint reported 47 findings of which the large
# majority were bare prefixes: a lint that cries 47 times to be right 17 gets
# switched off, which is the failure mode it exists to prevent.
# No arbitrary length cap: `.markdown` is 8 and real. What the pattern must
# exclude is a trailing version-ish number (`docs/v1.2`), not a long suffix.
_HAS_EXTENSION_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9]*$")


def _normalise_relative(token: str) -> str:
    """`./docs/x.md` and `docs/x.md` are the same citation. Markdown links are
    routinely written with the `./` prefix, and dropping them made every such
    citation invisible (Codex sol, 2026-08-31)."""
    while token.startswith("./"):
        token = token[2:]
    return token


def _starts_a_repo_path(token: str) -> bool:
    """A citation is repo-relative. A token that merely CONTAINS `docs/` deeper
    in an absolute or foreign path is not one — see the note on _PATH_RE."""
    return token.startswith(("research/", "docs/"))


def _is_file_citation(path: str) -> bool:
    return bool(_HAS_EXTENSION_RE.search(path)) and not _looks_like_template(path)


# The only capitalised tokens that mean "fill this in". Everything else that
# happens to be uppercase is a real name until proven otherwise.
_PLACEHOLDER_TOKENS: frozenset[str] = frozenset(
    {"YYYY", "MM", "DD", "HH", "NN", "N", "X", "SLUG", "TOPIC", "DOMAIN", "NAME", "ID"}
)


def _looks_like_template(path: str) -> bool:
    """Exclude paths that are clearly templates, not real references.

    WHY: a glob, or a bracketed/named placeholder, means the author is describing
    a PATTERN rather than pointing at one concrete file.

    NOT "any capitalised segment", which an earlier version used and which made
    `docs/API/x.md` and `docs/RESEARCH_LANDSCAPE_2026.md` — a real filename shape
    here — silently unscannable. That was an under-match hiding exactly the
    phantoms this lint looks for, and this docstring argued for it after the code
    had stopped doing it (Kimi K3, 2026-08-31: prose outliving the rule it
    describes is how the next reader re-adds a defect).
    """
    if any(ch in path for ch in "*?{}<>[]"):
        return True
    # ONLY date/id placeholders, not "any uppercase segment". The earlier rule
    # treated every capitalised part as a template, so `docs/API/x.md` and
    # `docs/RESEARCH_LANDSCAPE_2026.md` — a real filename shape in this repo —
    # were silently unscannable: an under-match that hid exactly the phantoms
    # this lint exists to find (Codex sol, 2026-08-31).
    parts = path.replace("/", " ").replace("-", " ").replace("_", " ").split()
    return any(part in _PLACEHOLDER_TOKENS for part in parts)


def _strip_suffixes_and_punctuation(raw: str) -> str:
    """Remove trailing punctuation and any #anchor or :line suffix."""
    # Drop trailing punctuation that sentence structure adds.
    while raw and raw[-1] in ". , ; )":
        raw = raw[:-1]
    # Drop #anchor or :line (kept after punctuation so docs/x.md:42,) works.
    raw = _ANCHOR_OR_LINE_RE.sub("", raw)
    return raw


def _candidates_from_link(url: str) -> list[str]:
    """Return citation candidates from a markdown link URL."""
    # A markdown link target is URL-encoded: a real file with a space in its name
    # is written `%20`, and comparing the encoded form against the filesystem
    # reported an existing file as missing.
    from urllib.parse import unquote

    # `[x](path "title")` — markdown allows a title after the target. Leaving it
    # attached made the extension test fail and the citation invisible.
    url = url.strip().split(None, 1)[0] if url.strip() else url
    url = _normalise_relative(_strip_suffixes_and_punctuation(unquote(url)))
    if _starts_a_repo_path(url) and _is_file_citation(url):
        return [url]
    return []


def _candidates_from_backtick_span(span: str) -> list[str]:
    """Return citation candidates from an inline code span.

    WHY exclude command spans: `cat docs/x.md` is a shell example, not a claim
    that docs/x.md backs an argument. A bare `docs/x.md` with no shell word is
    the canonical way doctrine files cite a source, so it counts.
    """
    tokens = span.split()
    # The span is a COMMAND if it BEGINS with a shell word — not merely if a shell
    # word happens to sit immediately before the path. `grep -n foo research/x.md`
    # has `foo` before the path, so the adjacency test passed it through as a
    # citation; the whole span is one command and none of it is a reference.
    # Drop a leading prompt token so `$ grep x docs/y.md` is still recognised as
    # a command; the prompt is punctuation, not a word.
    if tokens and tokens[0] in ("$", "#", ">"):
        tokens = tokens[1:]
    if tokens and tokens[0].lower() in _SHELL_WORDS:
        return []
    for i, token in enumerate(tokens):
        if i > 0 and _starts_a_repo_path(_normalise_relative(token)):
            if tokens[i - 1].lower() in _SHELL_WORDS:
                return []
    found: list[str] = []
    for token in tokens:
        # Normalise BEFORE the repo-path test: `./research/x.md` does not start
        # with `research/`, so checking first made every `./`-prefixed span
        # invisible while the same path resolved fine as a link — the three
        # recognisers disagreeing about the same string (Kimi K3, 2026-08-31).
        candidate = _normalise_relative(_strip_suffixes_and_punctuation(token))
        if _starts_a_repo_path(candidate):
            if _is_file_citation(candidate):
                found.append(candidate)
    return found


def _candidates_from_bare_text(text: str) -> list[str]:
    """Return citation candidates found loose in prose."""
    found: list[str] = []
    for match in _PATH_RE.finditer(text):
        candidate = _normalise_relative(_strip_suffixes_and_punctuation(match.group(0)))
        if _starts_a_repo_path(candidate) and _is_file_citation(candidate):
            found.append(candidate)
    return found


def _inside_fenced_code_block(lines: list[str]) -> list[bool]:
    """Return a parallel list: True when the line is inside a fenced code block.

    WHY: Shell examples inside ``` fences commonly reference paths (grep, cat,
    python scripts). Those are usage instructions, not evidentiary citations.
    Counting them would drown real findings in noise.
    """
    inside: list[bool] = []
    in_fence = False
    fence_char: str | None = None
    for line in lines:
        # Markdown permits fences indented up to three spaces.
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent <= 3:
            if not in_fence:
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_fence = True
                    fence_char = stripped[0]
            else:
                # End fence must use the same character class that opened it.
                if stripped.startswith(fence_char * 3):
                    in_fence = False
                    fence_char = None
        inside.append(in_fence)
    return inside


# A line that marks its own path as withdrawn is quoting a dead reference, not
# making one. This is what lets a retraction note name the path it is retracting
# without the note itself becoming a finding — and it is more durable than
# relying on a code fence, which a reformat can turn into an indented block or a
# blockquote (Codex sol, 2026-08-31, whose input was precisely this file's own
# cure). The token is deliberately loud and bilingual: nobody types it by
# accident, and it reads as an assertion in the text a human sees.
_RETRACTION_RE = re.compile(r"\b(RETRACTED|RITIRATA|RITIRATO)\b")

# NOT IMPLEMENTED, deliberately: excluding 4-space-INDENTED code blocks the way
# fenced ones are excluded. Markdown gives the same indentation to a list
# continuation, and no heuristic separated the two — the attempt made a citation
# inside a nested bullet invisible, which is an UNDER-match, and this guard's
# whole posture is that an under-match hides a phantom while an over-match costs
# a finding nobody needed. The concrete worry that prompted it (a retraction note
# reformatted from a fence into an indented block) is answered better by
# _RETRACTION_RE above, which survives any reformat because it is semantic.
# An indented example naming a non-existent path is therefore still a finding;
# fence it, or mark it retracted.


def _extract_citations(text: str) -> list[tuple[int, str]]:
    """Extract (1-based line number, cited path) pairs from a file's content."""
    lines = text.splitlines()
    in_fence = _inside_fenced_code_block(lines)
    citations: list[tuple[int, str]] = []

    in_list = False
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "+ ")) or (stripped[:2].rstrip(".").isdigit() and ". " in stripped[:4]):
            in_list = True
        elif not stripped:
            in_list = False
        if in_fence[line_no - 1]:
            continue
        if _RETRACTION_RE.search(line):
            # LINE-scoped, deliberately. A block-scoped marker — "the paragraph
            # after RETRACTED is exempt" — excused every OTHER citation sharing
            # that paragraph, including live ones: `Old rule RETRACTED; the live
            # source is research/x.md` passed with x.md missing (Kimi K3,
            # 2026-08-31), and the test written for it pinned only the blank-line
            # boundary, so the hole was locked in by its own guard. The narrow
            # rule costs one thing — a retraction must NAME its dead path on the
            # marker's own line — and that is a better sentence anyway.
            continue

        # Mask out link spans and backtick spans so bare-text scanning does not
        # double-count the same path. We still scan them separately below.
        mask = [""] * len(line)

        for match in _LINK_RE.finditer(line):
            for idx in range(match.start(1), match.end(1)):
                mask[idx] = "_"
            for candidate in _candidates_from_link(match.group(1)):
                citations.append((line_no, candidate))

        for match in _BACKTICK_RE.finditer(line):
            for idx in range(match.start(), match.end()):
                mask[idx] = "_"
            for candidate in _candidates_from_backtick_span(match.group(1)):
                citations.append((line_no, candidate))

        # A no-op until 2026-08-31: this read `ch if mask[i] else line[i]` over
        # `enumerate(line)`, where `ch` IS `line[i]` — both branches returned the
        # same character, so the mask was computed, looked like masking, and
        # masked nothing. The visible symptom was a shell example counted as a
        # citation by the bare-text pass after the span pass had correctly
        # rejected it; the invisible one was every backticked citation reported
        # twice. The three recognisers must cover DISJOINT regions of the line.
        masked = "".join(" " if mask[i] else line[i] for i in range(len(line)))
        for candidate in _candidates_from_bare_text(masked):
            citations.append((line_no, candidate))

    return citations


def _resolves_through_symlink(cwd: Path, cited: str) -> bool:
    """Last-resort existence check for a path that reaches THROUGH a symlink.

    `docs/design-palettes/kbli-images` is a tracked symlink to a directory under
    `apps/`. `git ls-tree` lists the LINK, not what is behind it, and `rglob` does
    not descend into directory symlinks — so a citation to a real file under it
    was reported missing by BOTH resolvers, reddening CI on correct doctrine
    (Kimi K3, 2026-08-31, verified on two interpreters).

    Confined to the repo: a citation is repo-relative by definition, so anything
    resolving outside `cwd` is refused rather than trusted — `..` in a citation
    must not become a way to point at the filesystem at large.
    """
    try:
        target = (cwd / cited).resolve()
        cwd_resolved = cwd.resolve()
        if cwd_resolved not in (target, *target.parents):
            return False
        return target.is_file()
    except (OSError, RuntimeError):
        return False


def _load_resolver(ref: str, cwd: Path) -> tuple[set[str], bool]:
    """Return (resolvable relative paths, whether git supplied them).

    THE WORKING TREE IS THE DEFAULT, and that is the correction that matters.
    This resolved against `HEAD` while the SUBJECT files were read from disk — a
    hybrid comparison in which deleting a cited file and running the lint before
    committing reads GREEN, because HEAD still has it (Codex sol, 2026-08-31).
    The single most natural way to create a phantom is to delete the thing being
    cited, so a resolver blind to exactly that is a resolver blind to the disease.

    `--ref` still exists for asking the question about another commit, and when
    it is given the answer is honestly ref-shaped: git supplies the set, and both
    sides of the comparison are that ref only if the caller also checked it out.
    """
    if ref:
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", ref],
                cwd=cwd, capture_output=True, text=True, check=True,
            )
            return set(result.stdout.splitlines()), True
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            # A named ref that cannot be read is a usage error, not a reason to
            # quietly answer a different question against the working tree. The
            # earlier version fell through to the filesystem with a warning on
            # stderr, which nobody reads in CI, and produced a green run whose
            # meaning had silently changed.
            raise SystemExit(
                f"error: --ref {ref!r} could not be read ({type(exc).__name__}); "
                "refusing to answer against a different tree instead"
            )

    # Relative POSIX paths, because that is the shape a citation is written in.
    # The earlier fallback stored `str(p)` for absolute `p`, so nothing ever
    # matched and every real citation read as missing.
    paths: set[str] = set()
    skip = {".git", "node_modules", ".venv", "__pycache__"}
    for path in cwd.rglob("*"):
        if path.is_file() and not any(part in skip for part in path.parts):
            paths.add(path.relative_to(cwd).as_posix())
    return paths, False


def _collect_subjects(cwd: Path, overrides: list[str] | None) -> list[Path]:
    """Expand glob patterns into concrete subject paths."""
    patterns = overrides if overrides else list(DEFAULT_SUBJECTS)
    subjects: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in cwd.glob(pattern):
            # Applied to the DISCOVERED set, not to the pattern list, so a glob
            # that happens to sweep the ledger in still cannot smuggle it back.
            # An explicit --subject naming it is honoured, because that is a
            # human deliberately asking (and the tests need it).
            if not overrides and path.relative_to(cwd).as_posix() in _EXCLUDED_SUBJECTS:
                continue
            if path.is_file() and path not in seen:
                subjects.append(path)
                seen.add(path)
    subjects.sort()
    return subjects


def _relative_to_cwd(path: Path, cwd: Path) -> str:
    """Return a forward-slash path relative to cwd for stable output."""
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint doctrine files for citations to non-existent research/docs paths.",
    )
    parser.add_argument(
        "--subject",
        action="append",
        metavar="PATH",
        help="Override the default subject set (repeatable; glob patterns accepted).",
    )
    parser.add_argument(
        "--ref",
        default="",
        help="git ref to resolve citations against; default is the WORKING TREE, because deleting a cited file is the commonest way to create a phantom",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text lines.",
    )
    args = parser.parse_args(argv)

    cwd = Path.cwd()
    subjects = _collect_subjects(cwd, args.subject)
    # An explicit --subject that resolves to NO file is a usage error, never a
    # clean run. Distinct from a subject that resolves and cites nothing, which
    # is a legitimate answer — conflating the two is how "I scanned the wrong
    # path" comes back as a green tick.
    if args.subject and not subjects:
        print(f"error: --subject matched no file: {', '.join(args.subject)}", file=sys.stderr)
        return 2
    resolver, _ = _load_resolver(args.ref, cwd)

    findings: list[dict[str, object]] = []
    total_citations = 0
    # Deduped on (subject, line, citation). The extractor deliberately runs three
    # recognisers over the same line — link, backtick span, bare prose — because a
    # citation may be written any of those ways; a path written as a backticked
    # markdown link is legitimately seen by two of them. Reporting it twice does
    # not make it truer, and a finding list padded with repeats is one a reader
    # skims (measured 2026-08-31: 47 printed lines for 12 distinct findings).
    seen_findings: set[tuple[str, int, str]] = set()

    for subject in subjects:
        rel = _relative_to_cwd(subject, cwd)
        text = subject.read_text(encoding="utf-8")
        for line_no, cited in _extract_citations(text):
            total_citations += 1
            if cited in resolver or _resolves_through_symlink(cwd, cited):
                continue
            key = (rel, line_no, cited)
            if key in seen_findings:
                continue
            seen_findings.add(key)
            findings.append({
                "subject": rel,
                "line": line_no,
                "citation": cited,
            })

    # The empty-extraction guard exists because a lint that silently scans nothing
    # reports clean forever. That reasoning holds for the DEFAULT corpus — where
    # zero citations can only mean the extractor broke — and not for an explicit
    # `--subject`, where a caller may legitimately point at one file that cites
    # nothing (every innocence fixture does exactly that). Same principle as the
    # ledger exclusion above: an explicit override is a human asking on purpose.
    if total_citations == 0 and not args.subject:
        msg = "error: extractor found zero citations across the subject set"
        if args.json:
            print(json.dumps({"error": msg}, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for finding in findings:
            print(f"{finding['subject']}:{finding['line']}: cited path does not exist: {finding['citation']}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
