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
_FINAL_RE = re.compile(
    r"\*\*FINAL \(client-facing\):\*\*\s*\n(.*?)\n\s*\*\*CONFIDENCE:\*\*",
    re.DOTALL,
)
_CONFIDENCE_RE = re.compile(r"\*\*CONFIDENCE:\*\*\s*(\S+)")
_LAW_REFS_BLOCK_RE = re.compile(
    r"\*\*LAW REFS \(source-cited, unverified\):\*\*\s*\n(.*?)(?=\n### Q\d+\.|\n## Section|\Z)",
    re.DOTALL,
)


def _extract_law_refs(block: str) -> list[str]:
    match = _LAW_REFS_BLOCK_RE.search(block)
    if not match:
        return []
    refs = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            refs.append(stripped[2:].strip())
        elif stripped.startswith("-"):
            refs.append(stripped[1:].strip())
    return [r for r in refs if r]


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
