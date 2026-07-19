"""Curated Q&A review-pack generator (curated-cache cantiere, Phase 1/2 support).

Zero's mandate: "prepara dei file semplici che distribuisco al team di tante
persone" — split a CHATKB dossier (E33-format markdown, same shape the
GARUDA visa corpus ships in) into simple per-reviewer files so non-technical
Bali Zero staff can vet each Q&A row before it is promoted to the bot's
verbatim FAQ cache.

Reuses `scripts.curated_qa_convert_e33.parse_e33_markdown_file` for the
actual CHATKB parsing contract (### Q<N>. / **FINAL (client-facing):** /
**CONFIDENCE:** / **LAW REFS (source-cited, unverified):**) — this module
does NOT re-implement a second parser dialect. In particular, the FINAL
block is the ONLY text that ever reaches a reviewer: **INTERNAL** reasoning,
banned-phrasing notes, and "confirm in writing" lists are parsed away by
the converter before this module ever sees the row.

Pure stdlib, no LLM calls, no network I/O.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/curated_qa_review_pack.py \\
        --input ~/Desktop/E33-SecondHome/E33-DEFINITIVE-CHATKB-2026-07-15.md \\
        --source \\
        --reviewers 6 --lang id \\
        --out-dir ~/Desktop/REVIEW-PACKS-2026-07-19/
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from scripts.curated_qa_convert_e33 import parse_e33_markdown_file

logger = logging.getLogger("curated_qa_review_pack")

# ── PII / provenance rail ────────────────────────────────────────────────────
# Only CHATKB files inside the repo's data/curated_qa/ tree may be read by
# default. Anything else (a Desktop dossier, a scratch export, ...) requires
# the operator to explicitly pass --source, acknowledging this is a
# non-repo path. This module never reads logs or DB dumps — it only ever
# opens the exact file paths given on the CLI.
REPO_CURATED_QA_DIR = Path(__file__).resolve().parents[1] / "data" / "curated_qa"


class ReviewPackSourceError(ValueError):
    """Raised when an input path fails the PII/provenance rail."""


def validate_input_path(
    path: Path, *, source_override: bool, allowed_dir: Path = REPO_CURATED_QA_DIR
) -> None:
    """Refuse to read `path` unless it is inside `allowed_dir` or the
    caller explicitly passed --source (source_override=True).

    Raises:
        ReviewPackSourceError: path is outside allowed_dir and no override.
        FileNotFoundError: path does not exist.
    """
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{path}: input file does not exist")
    try:
        resolved.relative_to(allowed_dir.resolve())
        return
    except ValueError:
        pass
    if not source_override:
        raise ReviewPackSourceError(
            f"{path}: refusing to read — outside repo {allowed_dir} and --source not given. "
            "Pass --source to explicitly allow a non-repo dossier path (e.g. a Desktop CHATKB file).",
        )


# ── Batch derivation from filename ──────────────────────────────────────────

_BATCH_SLUG_RE = re.compile(
    r"^(?P<prefix>.+?)-DEFINITIVE-CHATKB-(?P<date>\d{4}-\d{2}-\d{2})$",
    re.IGNORECASE,
)


def slugify(text: str) -> str:
    """Lowercase, ASCII-safe, hyphen-separated slug. Never empty for
    non-empty input (falls back to 'x' if everything gets stripped)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "x"


def derive_batch(path: Path) -> tuple[str, str]:
    """Derive (batch_slug, batch_title) from a CHATKB filename.

    Recognizes the "<PREFIX>-DEFINITIVE-CHATKB-<YYYY-MM-DD>" convention used
    by both real dossiers this build targets (E33-DEFINITIVE-CHATKB-... and
    GARUDA-VOA-DEFINITIVE-CHATKB-...); falls back to a plain slug of the
    filename stem for anything else so no input is ever rejected on naming.
    """
    stem = path.stem
    match = _BATCH_SLUG_RE.match(stem)
    if match:
        prefix = match.group("prefix")
        batch_date = match.group("date")
        return f"{slugify(prefix)}-{batch_date}", prefix.replace("-", " ")
    return slugify(stem), stem.replace("-", " ").replace("_", " ")


# ── Batch / review-item data model ──────────────────────────────────────────


@dataclass
class Batch:
    slug: str
    title: str
    source_path: Path
    rows: list[dict[str, Any]]
    confidence_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ReviewItem:
    number: str
    question: str
    answer: str
    confidence_class: str
    law_refs: list[str]
    source_ref: str


_SOURCE_REF_NUMBER_RE = re.compile(r"#Q(\d+)$")


def row_to_item(row: dict[str, Any]) -> ReviewItem:
    match = _SOURCE_REF_NUMBER_RE.search(row["source_ref"])
    number = match.group(1) if match else "?"
    return ReviewItem(
        number=number,
        question=row["question"],
        answer=row["answer"],
        confidence_class=row["confidence_class"],
        law_refs=list(row["law_refs"]),
        source_ref=row["source_ref"],
    )


def load_batches(
    input_paths: list[Path],
    *,
    lang: str,
    source_override: bool,
    allowed_dir: Path = REPO_CURATED_QA_DIR,
) -> list[Batch]:
    batches: list[Batch] = []
    for raw_path in input_paths:
        path = raw_path.expanduser()
        validate_input_path(path, source_override=source_override, allowed_dir=allowed_dir)
        batch_slug, batch_title = derive_batch(path)
        rows, counts = parse_e33_markdown_file(
            path.resolve(),
            domain=batch_slug,
            lang=lang,
            source_priority=0,
        )
        if not rows:
            raise ValueError(
                f"{path}: parsed zero questions — refusing to build an empty review pack"
            )
        batches.append(
            Batch(
                slug=batch_slug,
                title=batch_title,
                source_path=path,
                rows=rows,
                confidence_counts=counts,
            ),
        )
    return batches


# ── Round-robin assignment (with optional overlap) ──────────────────────────


def resolve_reviewer_names(*, reviewers: int | None, reviewers_file: Path | None) -> list[str]:
    if reviewers_file is not None:
        names = [
            line.strip()
            for line in reviewers_file.expanduser().read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not names:
            raise ValueError(f"{reviewers_file}: no reviewer names found")
        return names
    if reviewers is not None:
        if reviewers < 1:
            raise ValueError("--reviewers must be >= 1")
        return [f"Reviewer {i}" for i in range(1, reviewers + 1)]
    raise ValueError("either reviewers or reviewers_file is required")


def assign_round_robin(
    rows: list[dict[str, Any]],
    reviewer_names: list[str],
    *,
    overlap: int = 1,
) -> dict[str, list[dict[str, Any]]]:
    """Split `rows` round-robin across `reviewer_names`.

    With overlap=1 (default) every row goes to exactly one reviewer. With
    overlap=k>1, every row goes to k DISTINCT reviewers (independent
    double-review) — implemented as a sliding window over the reviewer
    cycle, which keeps per-reviewer load balanced to within 1 regardless of
    N or the overlap factor.
    """
    reviewer_count = len(reviewer_names)
    if reviewer_count == 0:
        raise ValueError("need at least one reviewer")
    if overlap < 1:
        raise ValueError("overlap must be >= 1")
    if overlap > reviewer_count:
        raise ValueError(f"overlap ({overlap}) cannot exceed reviewer count ({reviewer_count})")

    assignment: dict[str, list[dict[str, Any]]] = {name: [] for name in reviewer_names}
    for i, row in enumerate(rows):
        for k in range(overlap):
            reviewer = reviewer_names[(i + k) % reviewer_count]
            assignment[reviewer].append(row)
    return assignment


# ── Bahasa/IT/EN templates ───────────────────────────────────────────────────

_STRINGS: dict[str, dict[str, Any]] = {
    "id": {
        "title": "Paket Review",
        "reviewer_label": "Reviewer",
        "date_label": "Tanggal",
        "instructions_title": "Petunjuk",
        "instructions": [
            "Baca jawaban FINAL di bawah ini seolah-olah kamu adalah klien yang bertanya.",
            "Tandai setiap pertanyaan: ✅ BENAR, atau ❌ SALAH (tulis koreksinya), "
            "atau ⚠️ RAGU (tulis catatan).",
            "Cek juga: harga TIDAK boleh muncul di jawaban ini.",
            "Cek nomor WhatsApp / alamat kalau disebut — harus benar.",
        ],
        "send_back": "Kirim kembali file ini (atau foto halaman yang sudah ditandai) ke Zero.",
        "law_refs_label": "Dasar hukum",
        "law_refs_none": "Tidak ada referensi hukum tercatat",
        "confidence_label": "Tingkat kepastian",
        "answer_options": {
            "correct": "✅ BENAR",
            "wrong": "❌ SALAH — koreksi:",
            "unsure": "⚠️ RAGU — catatan:",
        },
        "summary_title": "Ringkasan",
        "summary_total": "Jumlah pertanyaan",
        "summary_deadline": "Target kembali",
    },
    "it": {
        "title": "Pacchetto di revisione",
        "reviewer_label": "Revisore",
        "date_label": "Data",
        "instructions_title": "Istruzioni",
        "instructions": [
            "Leggi la risposta FINALE qui sotto come se fossi il cliente che fa la domanda.",
            "Segna ogni domanda: ✅ CORRETTA, oppure ❌ SBAGLIATA (scrivi la correzione), "
            "oppure ⚠️ DUBBIO (scrivi una nota).",
            "Controlla anche: NON deve comparire nessun prezzo nella risposta.",
            "Controlla il numero WhatsApp / l'indirizzo se citati — devono essere corretti.",
        ],
        "send_back": "Rimanda questo file (o le foto delle pagine segnate) a Zero.",
        "law_refs_label": "Riferimenti normativi",
        "law_refs_none": "Nessun riferimento normativo registrato",
        "confidence_label": "Livello di certezza",
        "answer_options": {
            "correct": "✅ CORRETTA",
            "wrong": "❌ SBAGLIATA — correzione:",
            "unsure": "⚠️ DUBBIO — nota:",
        },
        "summary_title": "Riepilogo",
        "summary_total": "Numero di domande",
        "summary_deadline": "Scadenza per la restituzione",
    },
    "en": {
        "title": "Review Pack",
        "reviewer_label": "Reviewer",
        "date_label": "Date",
        "instructions_title": "Instructions",
        "instructions": [
            "Read the FINAL answer below as if you were the client asking the question.",
            "Mark each question: ✅ CORRECT, or ❌ WRONG (write the correction), "
            "or ⚠️ UNSURE (write a note).",
            "Also check: NO price should appear in this answer.",
            "Check the WhatsApp number / address if mentioned — it must be correct.",
        ],
        "send_back": "Send this file back (or photos of the marked-up pages) to Zero.",
        "law_refs_label": "Law references",
        "law_refs_none": "No law references recorded",
        "confidence_label": "Confidence",
        "answer_options": {
            "correct": "✅ CORRECT",
            "wrong": "❌ WRONG — correction:",
            "unsure": "⚠️ UNSURE — note:",
        },
        "summary_title": "Summary",
        "summary_total": "Total questions",
        "summary_deadline": "Target return date",
    },
}

_CONFIDENCE_LABELS: dict[str, dict[str, str]] = {
    "id": {
        "JELAS": "Pasti",
        "BERSYARAT": "Bersyarat",
        "DINAMIS": "Bisa berubah",
        "KEBIJAKAN_PENYEDIA": "Kebijakan kami",
        "BELUM_DIATUR_PUBLIK": "Belum ada aturan resmi",
    },
    "it": {
        "JELAS": "Certo",
        "BERSYARAT": "Condizionato",
        "DINAMIS": "Può cambiare",
        "KEBIJAKAN_PENYEDIA": "Nostra policy",
        "BELUM_DIATUR_PUBLIK": "Non ancora regolato pubblicamente",
    },
    "en": {
        "JELAS": "Settled",
        "BERSYARAT": "Conditional",
        "DINAMIS": "Can change",
        "KEBIJAKAN_PENYEDIA": "Our policy",
        "BELUM_DIATUR_PUBLIK": "Not yet publicly regulated",
    },
}


def _confidence_label(lang: str, confidence_class: str) -> str:
    return _CONFIDENCE_LABELS.get(lang, {}).get(confidence_class, confidence_class)


# ── Markdown pack ─────────────────────────────────────────────────────────


def render_markdown_pack(
    *,
    batch_title: str,
    reviewer_name: str,
    items: list[ReviewItem],
    lang: str,
    generated_date: str,
    deadline_date: str,
) -> str:
    s = _STRINGS[lang]
    lines: list[str] = []
    lines.append(f"# {s['title']} — {batch_title}")
    lines.append("")
    lines.append(f"**{s['reviewer_label']}:** {reviewer_name}  ")
    lines.append(f"**{s['date_label']}:** {generated_date}")
    lines.append("")
    lines.append(f"## {s['instructions_title']}")
    for i, instr in enumerate(s["instructions"], start=1):
        lines.append(f"{i}. {instr}")
    lines.append("")
    lines.append(s["send_back"])
    lines.append("")
    lines.append("---")
    lines.append("")

    opts = s["answer_options"]
    for item in items:
        lines.append(f"### Q{item.number}. {item.question}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        law_refs_text = "; ".join(item.law_refs) if item.law_refs else s["law_refs_none"]
        lines.append(f"**{s['law_refs_label']}:** {law_refs_text}")
        conf_label = _confidence_label(lang, item.confidence_class)
        lines.append(f"**{s['confidence_label']}:** {conf_label} ({item.confidence_class})")
        lines.append("")
        lines.append(f"- [ ] {opts['correct']}")
        lines.append(f"- [ ] {opts['wrong']} ________________________________")
        lines.append(f"- [ ] {opts['unsure']} ________________________________")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"## {s['summary_title']}")
    lines.append(f"{s['summary_total']}: {len(items)}")
    lines.append(f"{s['summary_deadline']}: {deadline_date}")
    lines.append("")
    return "\n".join(lines)


# ── HTML pack (print-ready, single self-contained file) ────────────────────


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=False)


def render_html_pack(
    *,
    batch_title: str,
    reviewer_name: str,
    items: list[ReviewItem],
    lang: str,
    generated_date: str,
    deadline_date: str,
) -> str:
    s = _STRINGS[lang]
    opts = s["answer_options"]

    instructions_html = "".join(f"<li>{_esc(text)}</li>" for text in s["instructions"])

    item_blocks: list[str] = []
    for item in items:
        law_refs_text = "; ".join(item.law_refs) if item.law_refs else s["law_refs_none"]
        conf_label = _confidence_label(lang, item.confidence_class)
        answer_html = _esc(item.answer).replace("\n", "<br>")
        item_blocks.append(
            f"""<section class="qa-card">
  <h2>Q{_esc(item.number)}. {_esc(item.question)}</h2>
  <p class="answer">{answer_html}</p>
  <p class="meta"><strong>{_esc(s["law_refs_label"])}:</strong> {_esc(law_refs_text)}</p>
  <p class="meta badge"><strong>{_esc(s["confidence_label"])}:</strong> {_esc(conf_label)} ({_esc(item.confidence_class)})</p>
  <div class="verdict">
    <label><input type="checkbox"> {_esc(opts["correct"])}</label>
    <label><input type="checkbox"> {_esc(opts["wrong"])} <span class="blank"></span></label>
    <label><input type="checkbox"> {_esc(opts["unsure"])} <span class="blank"></span></label>
  </div>
</section>""",
        )

    page_title = f"{s['title']} — {batch_title} — {reviewer_name}"

    return f"""<!doctype html>
<html lang="{_esc(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(page_title)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    font-size: 18px;
    line-height: 1.55;
    max-width: 820px;
    margin: 0 auto;
    padding: 24px;
    color: #111;
    background: #fff;
  }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  h2 {{ font-size: 22px; margin: 0 0 8px; }}
  .meta-block {{ font-size: 17px; margin-bottom: 16px; }}
  .qa-card {{
    border: 2px solid #333;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 26px;
    page-break-inside: avoid;
  }}
  .answer {{ font-size: 19px; margin: 8px 0 14px; }}
  .meta {{ font-size: 15px; color: #444; margin: 4px 0; }}
  .verdict {{ margin-top: 14px; }}
  .verdict label {{ display: block; font-size: 18px; margin: 10px 0; }}
  .verdict input[type=checkbox] {{
    width: 24px;
    height: 24px;
    margin-right: 10px;
    vertical-align: middle;
  }}
  .blank {{
    display: inline-block;
    border-bottom: 1px solid #333;
    width: 320px;
    height: 1.3em;
    vertical-align: middle;
  }}
  ol {{ font-size: 17px; }}
  hr {{ margin: 24px 0; border: none; border-top: 1px solid #ccc; }}
  @media print {{
    body {{ padding: 0; }}
    .qa-card {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<h1>{_esc(s["title"])} — {_esc(batch_title)}</h1>
<p class="meta-block">
  <strong>{_esc(s["reviewer_label"])}:</strong> {_esc(reviewer_name)}<br>
  <strong>{_esc(s["date_label"])}:</strong> {_esc(generated_date)}
</p>
<h2>{_esc(s["instructions_title"])}</h2>
<ol>{instructions_html}</ol>
<p>{_esc(s["send_back"])}</p>
<hr>
{"".join(item_blocks)}
<h2>{_esc(s["summary_title"])}</h2>
<p>
  {_esc(s["summary_total"])}: {len(items)}<br>
  {_esc(s["summary_deadline"])}: {_esc(deadline_date)}
</p>
</body>
</html>
"""


# ── Orchestration ────────────────────────────────────────────────────────


def build_review_packs(
    *,
    batches: list[Batch],
    reviewer_names: list[str],
    overlap: int,
    lang: str,
    out_dir: Path,
    generated_date: str,
    deadline_date: str,
) -> dict[str, Any]:
    """Write per-reviewer .md/.html packs for every batch and return the
    manifest dict (also written to disk by the caller)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "generated_at": generated_date,
        "lang": lang,
        "overlap": overlap,
        "reviewers": reviewer_names,
        "batches": [],
    }

    for batch in batches:
        assignment = assign_round_robin(batch.rows, reviewer_names, overlap=overlap)
        batch_entry: dict[str, Any] = {
            "batch_id": batch.slug,
            "batch_title": batch.title,
            "source_file": batch.source_path.name,
            "total_questions": len(batch.rows),
            "confidence_class_counts": batch.confidence_counts,
            "files": {},
            "assignments": {},
        }

        for reviewer_name in reviewer_names:
            rows_for_reviewer = assignment[reviewer_name]
            if not rows_for_reviewer:
                continue
            items = [row_to_item(row) for row in rows_for_reviewer]
            reviewer_slug = slugify(reviewer_name)
            md_name = f"review-pack-{batch.slug}-{reviewer_slug}.md"
            html_name = f"review-pack-{batch.slug}-{reviewer_slug}.html"

            md_text = render_markdown_pack(
                batch_title=batch.title,
                reviewer_name=reviewer_name,
                items=items,
                lang=lang,
                generated_date=generated_date,
                deadline_date=deadline_date,
            )
            html_text = render_html_pack(
                batch_title=batch.title,
                reviewer_name=reviewer_name,
                items=items,
                lang=lang,
                generated_date=generated_date,
                deadline_date=deadline_date,
            )

            (out_dir / md_name).write_text(md_text, encoding="utf-8")
            (out_dir / html_name).write_text(html_text, encoding="utf-8")

            batch_entry["files"][reviewer_name] = {"md": md_name, "html": html_name}
            batch_entry["assignments"][reviewer_name] = [
                row["source_ref"] for row in rows_for_reviewer
            ]

        manifest["batches"].append(batch_entry)

    return manifest


# ── CLI ──────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Split CHATKB Q&A dossiers into simple per-reviewer packs (.md + .html) "
            "for team review before curated-cache promotion."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        required=True,
        help="One or more CHATKB markdown source files (E33 format).",
    )
    reviewer_group = parser.add_mutually_exclusive_group(required=True)
    reviewer_group.add_argument(
        "--reviewers", type=int, default=None, help="Number of anonymous reviewers."
    )
    reviewer_group.add_argument(
        "--reviewers-file",
        type=Path,
        default=None,
        help="Path to a text file with one reviewer name per line.",
    )
    parser.add_argument(
        "--lang",
        choices=sorted(_STRINGS),
        default="id",
        help="Pack language (default: id — Bahasa Indonesia, the team language).",
    )
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="Directory to write packs + manifest into."
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=1,
        help="Number of independent reviewers per question (default: 1, no overlap).",
    )
    parser.add_argument(
        "--source",
        action="store_true",
        help=(
            "Explicitly allow reading --input files outside repo data/curated_qa/ "
            "(e.g. a Desktop dossier). PII/provenance rail — refused without this flag."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Override manifest output path (default: <out-dir>/review-packs-manifest.json).",
    )
    return parser.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    reviewer_names = resolve_reviewer_names(
        reviewers=args.reviewers, reviewers_file=args.reviewers_file
    )
    if args.overlap > len(reviewer_names):
        raise SystemExit(
            f"--overlap ({args.overlap}) cannot exceed reviewer count ({len(reviewer_names)})"
        )

    batches = load_batches(args.input, lang=args.lang, source_override=args.source)
    logger.info(
        "Loaded %d batch(es), %d total questions",
        len(batches),
        sum(len(b.rows) for b in batches),
    )

    generated_date = date.today().isoformat()
    deadline_date = (date.today() + timedelta(days=3)).isoformat()
    out_dir = args.out_dir.expanduser()

    manifest = build_review_packs(
        batches=batches,
        reviewer_names=reviewer_names,
        overlap=args.overlap,
        lang=args.lang,
        out_dir=out_dir,
        generated_date=generated_date,
        deadline_date=deadline_date,
    )

    manifest_path = (
        args.manifest.expanduser() if args.manifest else out_dir / "review-packs-manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    files_written = sum(len(entry["files"]) * 2 for entry in manifest["batches"])
    logger.info(
        "Wrote %d files (.md+.html) across %d batch(es); manifest at %s",
        files_written,
        len(batches),
        manifest_path,
    )


if __name__ == "__main__":
    main()
