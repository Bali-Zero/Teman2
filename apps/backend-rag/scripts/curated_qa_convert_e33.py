"""Curated Q&A corpus converter (SPEC v2 D3, F1b).

Converts three source formats into the shared curated_qa JSONL schema
(apps/backend-rag/data/curated_qa/README.md):
{question, answer, domain, lang, source_ref, source_date, confidence_class,
law_refs, source_priority}.

Modes (mutually exclusive):

1. Default (E33 markdown): parses the "E33 DEFINITIVE CHATKB" per-question
   format:

       ### Q<N>. <question text>

       **FINAL (client-facing):**
       <client-facing answer — this, and ONLY this, becomes `answer`;
       INTERNAL reasoning/banned-phrasing/confirm-in-writing notes are
       deliberately NOT copied into the answer — they are editorial/legal
       reasoning, not the vetted client answer>

       **CONFIDENCE:** <CLASS>

       **INTERNAL:**
       ...

       **CONFIRM IN WRITING:**
       - ...

       **LAW REFS (source-cited, unverified):**
       - ref
       - ref

   observed CONFIDENCE classes in the real corpus: BERSYARAT,
   BELUM_DIATUR_PUBLIK, KEBIJAKAN_PENYEDIA, JELAS, DINAMIS. Any OTHER token
   is kept verbatim (never silently dropped) and counted under its own key
   in the summary — "map confidence classes; skip nothing silently."

2. --golden-yaml: converts scripts/golden_answers_questions.yaml.
   QUESTION-ONLY (that file has no answer field — the actual golden answer
   is generated live against NLM and stored in Postgres by
   scripts/golden_answers_refresh.py, out of scope here). Every row gets
   answer=null, confidence_class="UNSCORED".

3. --prewarm: converts the PREWARM_QUESTIONS dict imported from
   scripts/nlm_cache_prewarm.py. Also QUESTION-ONLY — those answers come
   from a live NLM bridge query at prewarm time, not a static corpus.
   answer=null, confidence_class="UNSCORED".

Question-only rows (answer=null) are valid per the shared schema but MUST
be skipped by curated_qa_harvest.py for both sinks (see that script's
docstring) — they exist here only for later coverage analysis (which
curated/prewarm/golden questions still have no vetted answer).

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/curated_qa_convert_e33.py \\
        --input ~/Desktop/E33-SecondHome/E33-DEFINITIVE-CHATKB-2026-07-15.md \\
        --output data/curated_qa/e33-second-home.jsonl --domain visa
    PYTHONPATH=. python scripts/curated_qa_convert_e33.py --golden-yaml \\
        --output data/curated_qa/golden-questions.jsonl
    PYTHONPATH=. python scripts/curated_qa_convert_e33.py --prewarm \\
        --output data/curated_qa/prewarm-questions.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("curated_qa_convert_e33")

# Question-only seeds (prewarm/golden) are functionally inert for both sinks
# (harvester skips answer-less rows) — a low, fixed source_priority documents
# that intent without needing a CLI knob nobody will ever tune.
_QUESTION_ONLY_SOURCE_PRIORITY = 5
_QUESTION_ONLY_CONFIDENCE_CLASS = "UNSCORED"

# scripts/nlm_cache_prewarm.py domain keys -> curated_qa schema domain values.
# The prewarm bank predates this schema and uses a slightly different
# vocabulary (immigration/company/lifestyle) than the rest of the codebase
# (visa/kbli/tax/property/default per the abstain-policy domain set).
_PREWARM_DOMAIN_MAP: dict[str, str] = {
    "immigration": "visa",
    "company": "kbli",
    "tax": "tax",
    "property": "property",
    "lifestyle": "default",
}

_SHARED_SCHEMA_KEYS = (
    "question",
    "answer",
    "domain",
    "lang",
    "source_ref",
    "source_date",
    "confidence_class",
    "law_refs",
    "source_priority",
)

# ── E33 markdown parsing ─────────────────────────────────────────────────────

_GENERATED_DATE_RE = re.compile(r"generated\s+(\d{4}-\d{2}-\d{2})")
_QUESTION_HEADER_RE = re.compile(r"^### Q(\d+)\.\s*(.+?)\s*$", re.MULTILINE)
# NOTE (2026-07-19, curated-cache cantiere Wave 1/2 postmortem): the answer
# body has been observed in TWO physical layouts across real dossiers, both
# equally valid per the spec's own prose (which never mandated a line break)
# — (a) the label on its own line, answer starting on the next line (the
# original E33/GARUDA convention the fixture below models), and (b) the
# answer starting INLINE on the same line as the label ("**FINAL
# (client-facing):** The standard..."), used by 8 of the 14 Wave 1/2
# dossiers (company-compliance, company-ptpma-process, property-ownership,
# property-villa-rental, tax-corporate, tax-personal, visa-kitap,
# visa-medical-crew). The old `\s*\n` right after the label required a
# literal newline before the answer could start, so it silently failed to
# match (and thus silently emitted answer="") on every INLINE-style row —
# not a crash, a quiet data-loss bug (162/272 rows empty when first
# discovered via curated_qa_review_pack.py packs). `\s*` (no mandatory
# `\n`) accepts either layout; `.strip()` on the caller side already
# normalizes the leading whitespace/newline either way.
_FINAL_RE = re.compile(
    r"\*\*FINAL \(client-facing\):\*\*\s*(.*?)\n\s*\*\*CONFIDENCE:\*\*",
    re.DOTALL,
)
_CONFIDENCE_RE = re.compile(r"\*\*CONFIDENCE:\*\*\s*(\S+)")
# Same postmortem, two more real-world variants beyond the header text:
# (a) the "(source-cited, unverified)" qualifier is dropped in 9 of the 14
#     Wave 1/2 dossiers ("**LAW REFS:**" bare) — the `(?: ...)?` makes it
#     optional so both match;
# (b) 6 of those 9 write the citations as INLINE PROSE (one or two
#     semicolon-separated sentences right after the label, sometimes
#     hard-wrapped across physical lines — e.g. visa-kitap), not a
#     "- " bulleted list — the old mandatory `\s*\n` before the capture
#     group required a literal newline before content could start, so it
#     silently returned law_refs=[] for every such row (same data-loss
#     shape as the FINAL_RE bug above). `\s*` (no mandatory `\n`) fixes it;
#     `_extract_law_refs` below now falls back to semicolon-splitting the
#     prose when no "- " bullet lines are present.
# (c) THIRD real bug, independent of the two above and pre-existing in the
#     original regex (not something the inline/prose fix introduced): the
#     per-question `block` a caller hands in runs from this question's
#     header to the NEXT "### Q" header, or — for the LAST question in a
#     file — all the way to EOF (see `parse_e33_markdown_file` below). Real
#     dossiers append document-level trailing sections after the last
#     question ("## Self-check pass", "## Arbiter verification pass",
#     "## Sanity checks", ...) — arbitrary text, not just "## Section...".
#     The old boundary lookahead only recognized the literal "## Section"
#     spelling, so on 7 of the 14 Wave 1/2 dossiers the last question's LAW
#     REFS capture ran straight through those trailing sections to EOF,
#     and any "- " bulleted line inside them (e.g. a "## Self-check pass"
#     bullet list) got mis-read as one of the LAST QUESTION's own law refs
#     — confirmed live: company-compliance Q20's rendered "Dasar hukum"
#     line contained the dossier's ENTIRE postgate commentary, INTERNAL
#     reasoning included, in a reviewer-facing pack. `\n## ` (ANY level-2
#     heading, not just ones literally spelled "Section") is the correct,
#     strictly tighter boundary — every "## Section ..." heading is also
#     just "## " followed by more text, so this can only stop capture
#     EARLIER/more-correctly, never later.
_LAW_REFS_BLOCK_RE = re.compile(
    r"\*\*LAW REFS(?: \(source-cited, unverified\))?:\*\*\s*(.*?)(?=\n### Q\d+\.|\n## |\Z)",
    re.DOTALL,
)
# A markdown horizontal rule ("---", "***", "___") used as the visual
# separator between question blocks. Real dossiers place one right after
# the LAW REFS content and before the next "### Q" header/EOF, so it lands
# INSIDE the captured group above. Without filtering it out, the old
# per-line bullet scan below (`elif stripped.startswith("-")`) mis-reads a
# lone "---" line as a dash-bulleted ref and appends a bogus "--" entry —
# confirmed live on every one of the 5 dossiers that otherwise parsed
# cleanly (visa-golden-investor, visa-business-multientry, visa-student,
# company-kbli-signed-lots: near-100% of rows; tax-pmk37: 0, no "---"
# convention in that file). Filtered out unconditionally, both in the
# bullet path and the prose-fallback path.
_HR_LINE_RE = re.compile(r"^[-*_]{3,}\s*$")


def _extract_law_refs(block: str) -> list[str]:
    match = _LAW_REFS_BLOCK_RE.search(block)
    if not match:
        return []

    bullet_refs: list[str] = []
    prose_lines: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or _HR_LINE_RE.match(stripped):
            continue
        if stripped.startswith("- "):
            bullet_refs.append(stripped[2:].strip())
        elif stripped.startswith("-"):
            bullet_refs.append(stripped[1:].strip())
        else:
            prose_lines.append(stripped)

    if bullet_refs:
        return [r for r in bullet_refs if r]
    if prose_lines:
        # Re-join hard-wrapped physical lines into one logical paragraph,
        # then split on the "; " convention real dossiers use to separate
        # discrete citations within a single inline LAW REFS sentence —
        # matches the per-citation granularity the bulleted format gives.
        prose = " ".join(prose_lines)
        return [part.strip() for part in prose.split("; ") if part.strip()]
    return []


def parse_e33_markdown_file(
    path: Path,
    *,
    domain: str,
    lang: str,
    source_priority: int,
    source_date_override: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Parse one E33-format markdown file into curated_qa schema rows.

    Returns (rows, confidence_class_counts) — the per-class summary is
    mandatory per spec ("skip nothing silently — emit a per-class count
    summary").

    Raises:
        ValueError: if no source_date can be determined (no "generated
            YYYY-MM-DD" header found in the file AND no
            source_date_override given) — fail loud rather than guess a date.
    """
    text = path.read_text(encoding="utf-8")

    source_date = source_date_override
    if not source_date:
        date_match = _GENERATED_DATE_RE.search(text)
        if not date_match:
            raise ValueError(
                f"{path}: could not determine source_date — no 'generated "
                "YYYY-MM-DD' header found and no source_date_override given.",
            )
        source_date = date_match.group(1)

    headers = list(_QUESTION_HEADER_RE.finditer(text))
    rows: list[dict[str, Any]] = []
    confidence_class_counts: dict[str, int] = {}

    for i, header in enumerate(headers):
        question_number = header.group(1)
        question_text = header.group(2).strip()
        block_start = header.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[block_start:block_end]

        final_match = _FINAL_RE.search(block)
        answer = final_match.group(1).strip() if final_match else ""

        confidence_match = _CONFIDENCE_RE.search(block)
        confidence_class = confidence_match.group(1).strip() if confidence_match else "UNKNOWN"
        confidence_class_counts[confidence_class] = (
            confidence_class_counts.get(confidence_class, 0) + 1
        )

        law_refs = _extract_law_refs(block)

        rows.append(
            {
                "question": question_text,
                "answer": answer,
                "domain": domain,
                "lang": lang,
                "source_ref": f"{path.name}#Q{question_number}",
                "source_date": source_date,
                "confidence_class": confidence_class,
                "law_refs": law_refs,
                "source_priority": source_priority,
            },
        )

    return rows, confidence_class_counts


# ── golden_answers_questions.yaml mode ───────────────────────────────────────


def convert_golden_yaml(yaml_path: Path) -> list[dict[str, Any]]:
    """Convert scripts/golden_answers_questions.yaml into question-only rows.

    That file carries no answer — golden answers are generated live against
    NLM by scripts/golden_answers_refresh.py and stored in Postgres. Rows
    here are QUESTION-ONLY seeds (answer=null); the harvester skips them for
    both sinks, keeping them useful only for coverage analysis.
    """
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    source_date = str(data.get("generated", "unknown"))
    questions = data.get("questions", [])

    rows: list[dict[str, Any]] = []
    for q in questions:
        rows.append(
            {
                "question": q["question"],
                "answer": None,
                "domain": q.get("domain", "default"),
                "lang": "en",
                "source_ref": f"{yaml_path.name}#{q.get('nb_id', '')}",
                "source_date": source_date,
                "confidence_class": _QUESTION_ONLY_CONFIDENCE_CLASS,
                "law_refs": [],
                "source_priority": _QUESTION_ONLY_SOURCE_PRIORITY,
            },
        )
    return rows


# ── nlm_cache_prewarm.py PREWARM_QUESTIONS mode ──────────────────────────────


def convert_prewarm(prewarm_questions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the PREWARM_QUESTIONS dict (scripts/nlm_cache_prewarm.py) into
    question-only rows. Answers come from a live NLM bridge query at prewarm
    time (not a static corpus), so answer=null here too.
    """
    rows: list[dict[str, Any]] = []
    for prewarm_domain, config in prewarm_questions.items():
        schema_domain = _PREWARM_DOMAIN_MAP.get(prewarm_domain, prewarm_domain)
        notebook_id = config.get("notebook_id", "")
        for idx, question in enumerate(config.get("questions", [])):
            rows.append(
                {
                    "question": question,
                    "answer": None,
                    "domain": schema_domain,
                    "lang": "en",
                    "source_ref": f"nlm_cache_prewarm.py#{prewarm_domain}:{idx}:{notebook_id}",
                    "source_date": "unknown",
                    "confidence_class": _QUESTION_ONLY_CONFIDENCE_CLASS,
                    "law_refs": [],
                    "source_priority": _QUESTION_ONLY_SOURCE_PRIORITY,
                },
            )
    return rows


# ── Output ───────────────────────────────────────────────────────────────────


def write_jsonl_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a curated Q&A source into the shared curated_qa JSONL schema.",
    )
    parser.add_argument("--input", type=Path, default=None, help="E33 markdown source file")
    parser.add_argument("--output", type=Path, required=True, help="Output .jsonl path")
    parser.add_argument(
        "--golden-yaml",
        action="store_true",
        help="Convert scripts/golden_answers_questions.yaml instead of --input",
    )
    parser.add_argument(
        "--prewarm",
        action="store_true",
        help="Convert PREWARM_QUESTIONS from scripts/nlm_cache_prewarm.py instead of --input",
    )
    parser.add_argument("--domain", default="visa", help="Domain tag for E33 mode (default: visa)")
    parser.add_argument("--lang", default="en", help="Language tag for E33 mode (default: en)")
    parser.add_argument(
        "--source-priority",
        type=int,
        default=80,
        help="FAQ-cache collision-policy rank for E33 mode rows (default: 80)",
    )
    parser.add_argument(
        "--source-date",
        default=None,
        help="Override source_date for E33 mode if the file has no 'generated YYYY-MM-DD' header",
    )
    return parser.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    if args.golden_yaml:
        _script_dir = Path(__file__).resolve().parent
        rows = convert_golden_yaml(_script_dir / "golden_answers_questions.yaml")
        logger.info("Converted %d question-only rows from golden_answers_questions.yaml", len(rows))
    elif args.prewarm:
        from scripts.nlm_cache_prewarm import PREWARM_QUESTIONS

        rows = convert_prewarm(PREWARM_QUESTIONS)
        logger.info("Converted %d question-only rows from PREWARM_QUESTIONS", len(rows))
    else:
        if not args.input:
            raise SystemExit("--input is required unless --golden-yaml or --prewarm is given")
        rows, counts = parse_e33_markdown_file(
            args.input,
            domain=args.domain,
            lang=args.lang,
            source_priority=args.source_priority,
            source_date_override=args.source_date,
        )
        logger.info("Converted %d rows from %s", len(rows), args.input)
        logger.info("Confidence class counts: %s", counts)

    write_jsonl_rows(rows, args.output)
    logger.info("Wrote %d rows to %s", len(rows), args.output)


if __name__ == "__main__":
    main()
