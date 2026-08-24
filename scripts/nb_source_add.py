#!/usr/bin/env python3
"""nb_source_add.py — verifying loader for NotebookLM sources.

WHY THIS EXISTS
---------------
NotebookLM can accept a source and store it without usable extracted text. A
scanned PDF with no OCR appears normal in the source list, shows a sane title,
and contains only the rendered page images / a title fragment. A wrong-document
upload (file named for one law, body of another) is equally silent. This tool
replaces the raw ``nlm source add`` call in our workflows with an add-read-assert
triple:

  1. add the source and wait for processing;
  2. read the live content back from NotebookLM;
  3. enforce an emptiness floor AND an identity gate.

On any failure the tool deletes the source it just added. It never leaves a
failed source behind.

EMPTINESS FLOOR DERIVATION (PDF)
--------------------------------
Measured 2026-08-24 on Kepmen M.IP-19.GR.01.01/2025 (3 pages) in NB-2:

  - raw NotebookLM extraction of the scanned PDF: 721 characters total
    -> ~240 characters / page.
  - local tesseract OCR at 300 dpi on the same PDF: 6 963 characters total
    -> ~2 321 characters / page.

The default floor of 500 characters / page is roughly double the measured shell
density and about one fifth of the measured real-text density. That rejects an
un-OCR'd scan while giving margin for degraded scans or marginal OCR. It is
configurable via ``--floor-chars-per-page``.

For non-PDF source types the floor is a single absolute number (default 50
characters), configurable via ``--floor-chars``.

IDENTITY GATE
-------------
The caller passes one or more ``--required-phrase`` values. The live extracted
content must contain every phrase, case-insensitive and ignoring whitespace
runs. This catches the wrong-document class (e.g. a file titled UU_6_2011 but
whose body is a Sumenep regional by-law).

OCR FALLBACK
------------
If ``--ocr-fallback`` is set, the emptiness gate fails, and the input is a local
PDF, the tool runs ``pdftoppm -r 300`` + ``tesseract -l eng`` locally, prepends a
provenance header, and uploads the OCR text as a second source. The original PDF
source is kept as evidence. If the OCR text also fails a gate, both sources are
deleted.

Exit codes:
  0  source added and both gates passed
  2  usage error
  3  nlm / subprocess failure
  4  emptiness gate failed
  5  identity gate failed
  6  phantom source (content unreadable / NOT_FOUND)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nb-source-add")

NLM_CLI = str(Path.home() / ".local" / "bin" / "nlm")

# Timeouts. NotebookLM scans can take >120s; use generous defaults.
NLM_ADD_TIMEOUT = 600.0
NLM_CONTENT_TIMEOUT = 90.0
CONTENT_POLL_INTERVAL = 3.0
CONTENT_POLL_TIMEOUT = 120.0

# Default floors. See module docstring for derivation.
DEFAULT_PDF_FLOOR_CHARS_PER_PAGE = 500
DEFAULT_OTHER_FLOOR_CHARS = 50

# Exit codes
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NLM_ERROR = 3
EXIT_EMPTINESS = 4
EXIT_IDENTITY = 5
EXIT_PHANTOM = 6

RunNlm = Callable[[list[str], float], subprocess.CompletedProcess[str]]


class GateError(Exception):
    """A verification gate failed."""

    def __init__(self, gate: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.gate = gate
        self.message = message
        self.exit_code = exit_code


class NlmError(Exception):
    """nlm CLI returned a non-zero exit or unreadable output."""

    def __init__(self, message: str, is_phantom: bool = False) -> None:
        super().__init__(message)
        self.is_phantom = is_phantom


def default_run_nlm(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Default subprocess runner for the nlm CLI."""
    return subprocess.run(
        [NLM_CLI, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _nlm_with_profile(base_args: list[str], profile: str) -> list[str]:
    if profile and profile != "default":
        return [*base_args, "--profile", profile]
    return base_args


def add_source(
    notebook_id: str,
    *,
    url: Optional[str] = None,
    file_path: Optional[Path] = None,
    text: Optional[str] = None,
    title: Optional[str] = None,
    profile: str = "default",
    wait_timeout: float = NLM_ADD_TIMEOUT,
    run_nlm: RunNlm = default_run_nlm,
) -> str:
    """Add a source to ``notebook_id`` and return the new source_id.

    Exactly one of ``url``, ``file_path``, or ``text`` must be provided.
    Waits for NotebookLM processing to complete.
    """
    provided = [x for x in (url, file_path, text) if x is not None]
    if len(provided) != 1:
        raise ValueError("exactly one of --url, --file, or --text must be provided")

    base = ["source", "add", notebook_id, "--wait", "--json", "--wait-timeout", str(wait_timeout)]
    if title:
        base.extend(["--title", title])
    if url:
        base.extend(["--url", url])
    elif file_path:
        base.extend(["--file", str(file_path)])
    elif text:
        base.extend(["--text", text])

    args = _nlm_with_profile(base, profile)
    result = run_nlm(args, timeout=wait_timeout + 30.0)
    if result.returncode != 0:
        raise NlmError(
            f"nlm source add failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise NlmError(f"nlm source add returned invalid JSON: {exc}") from exc

    source_id = payload.get("source_id")
    if not source_id:
        raise NlmError(f"nlm source add response missing source_id: {payload}")
    return source_id


def get_source_content(
    source_id: str,
    *,
    profile: str = "default",
    run_nlm: RunNlm = default_run_nlm,
) -> dict:
    """Fetch live content for ``source_id`` via ``nlm source content --json``."""
    args = _nlm_with_profile(["source", "content", source_id, "--json"], profile)
    result = run_nlm(args, timeout=NLM_CONTENT_TIMEOUT)
    if result.returncode != 0:
        err = result.stderr.strip()
        is_phantom = "NOT_FOUND" in err or "not found" in err.lower()
        raise NlmError(f"nlm source content failed for {source_id} (exit {result.returncode}): {err}", is_phantom=is_phantom)
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise NlmError(f"nlm source content returned invalid JSON for {source_id}: {exc}") from exc


def poll_source_content(
    source_id: str,
    *,
    profile: str = "default",
    poll_timeout: float = CONTENT_POLL_TIMEOUT,
    run_nlm: RunNlm = default_run_nlm,
) -> dict:
    """Poll ``nlm source content`` until it succeeds or ``poll_timeout`` expires.

    A small number of transient failures (including NOT_FOUND immediately after
    add) are retried. A persistent NOT_FOUND is treated as a phantom source.
    """
    deadline = time.monotonic() + poll_timeout
    last_error: Optional[NlmError] = None
    while True:
        try:
            return get_source_content(source_id, profile=profile, run_nlm=run_nlm)
        except NlmError as exc:
            last_error = exc
            if not exc.is_phantom:
                # Non-NOT_FOUND errors are not retried.
                raise
            if time.monotonic() >= deadline:
                break
            logger.warning(
                "Source %s content not yet available (%s); retrying in %.0fs",
                source_id,
                exc,
                CONTENT_POLL_INTERVAL,
            )
            time.sleep(CONTENT_POLL_INTERVAL)
    assert last_error is not None
    raise last_error


def delete_sources(
    source_ids: Iterable[str],
    *,
    profile: str = "default",
    run_nlm: RunNlm = default_run_nlm,
) -> None:
    """Delete the given source IDs, logging any failure but never raising."""
    ids = list(source_ids)
    if not ids:
        return
    args = _nlm_with_profile(["source", "delete", *ids, "--confirm", "--json"], profile)
    try:
        result = run_nlm(args, timeout=NLM_CONTENT_TIMEOUT)
        if result.returncode != 0:
            logger.error("Failed to delete sources %s: %s", ids, result.stderr.strip())
        else:
            logger.info("Cleaned up sources: %s", ids)
    except Exception as exc:  # noqa: BLE001 — cleanup must not mask the original error
        logger.error("Exception while deleting sources %s: %s", ids, exc)


def pdf_page_count(file_path: Path) -> int:
    """Return the number of pages in a PDF using ``pdfinfo``.

    Falls back to 1 if ``pdfinfo`` is missing or cannot parse the file.
    """
    if not shutil.which("pdfinfo"):
        logger.warning("pdfinfo not found; assuming 1 page for %s", file_path)
        return 1
    try:
        result = subprocess.run(
            ["pdfinfo", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30.0,
        )
        if result.returncode != 0:
            logger.warning("pdfinfo failed for %s: %s", file_path, result.stderr.strip())
            return 1
        match = re.search(r"^Pages:\s*(\d+)", result.stdout, re.MULTILINE)
        if match:
            return int(match.group(1))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not determine page count for %s: %s", file_path, exc)
    return 1


def ocr_pdf_to_text(file_path: Path, lang: str = "eng") -> str:
    """OCR a local PDF with pdftoppm (300 dpi) + tesseract.

    Raises RuntimeError if a required tool is missing or the OCR fails.
    Degrades gracefully if the requested tesseract language pack is absent:
    if ``lang`` is not installed, falls back to the first installed language
    (usually ``eng``) and logs a warning.
    """
    if not shutil.which("pdftoppm"):
        raise RuntimeError("pdftoppm not installed; cannot OCR fallback")
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract not installed; cannot OCR fallback")

    installed_langs = _installed_tesseract_langs()
    effective_lang = lang
    if lang not in installed_langs:
        fallback = installed_langs[0] if installed_langs else None
        if fallback:
            logger.warning(
                "Tesseract language '%s' not installed (have %s); falling back to '%s'",
                lang,
                installed_langs,
                fallback,
            )
            effective_lang = fallback
        else:
            raise RuntimeError(f"no tesseract language packs installed (requested {lang})")

    pages: list[str] = []
    with tempfile.TemporaryDirectory(prefix="nb_source_ocr_") as tmpdir:
        prefix = Path(tmpdir) / "page"
        convert = subprocess.run(
            ["pdftoppm", "-png", "-r", "300", str(file_path), str(prefix)],
            capture_output=True,
            text=True,
            timeout=300.0,
        )
        if convert.returncode != 0:
            raise RuntimeError(f"pdftoppm failed: {convert.stderr.strip()}")

        images = sorted(prefix.parent.glob(f"{prefix.name}-*.png"))
        if not images:
            raise RuntimeError("pdftoppm produced no images")

        for img in images:
            ocr = subprocess.run(
                ["tesseract", str(img), "stdout", "-l", effective_lang],
                capture_output=True,
                text=True,
                timeout=120.0,
            )
            if ocr.returncode != 0:
                raise RuntimeError(f"tesseract failed on {img.name}: {ocr.stderr.strip()}")
            pages.append(ocr.stdout)

    return "\n\n".join(pages)


def _installed_tesseract_langs() -> list[str]:
    """Return the tesseract language packs reported by ``tesseract --list-langs``."""
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            timeout=30.0,
        )
        if result.returncode != 0:
            return []
        # First line is "List of available languages in ..."; subsequent lines are codes.
        return [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
    except Exception:  # noqa: BLE001
        return []


def build_ocr_provenance(instrument: str, char_count: int, dpi: int = 300, tool: str = "tesseract") -> str:
    """Return the header prepended to OCR fallback text."""
    return (
        f"[PROVENANCE — LOCAL OCR FALLBACK]\n"
        f"Source instrument: {instrument}\n"
        f"Extraction: local OCR via {tool} (pdftoppm at {dpi} dpi)\n"
        f"Character count: {char_count}\n"
        f"WARNING: binding legal quotation must be re-checked against the original PDF.\n\n"
    )


def normalize_text(text: str) -> str:
    """Lower-case and collapse whitespace runs for tolerant matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


def identity_gate(content: str, required_phrases: list[str]) -> Optional[str]:
    """Return the first required phrase not found in ``content``, or None if all present."""
    normalized_content = normalize_text(content)
    for phrase in required_phrases:
        if normalize_text(phrase) not in normalized_content:
            return phrase
    return None


def emptiness_floor(source_type: str, *, page_count: int = 1, pdf_floor_per_page: int, other_floor: int) -> int:
    """Compute the character-count floor for a source type."""
    if source_type == "pdf":
        return max(1, page_count) * pdf_floor_per_page
    return other_floor


def verify_source(
    content_payload: dict,
    *,
    required_phrases: list[str],
    pdf_floor_per_page: int,
    other_floor: int,
    page_count: int = 1,
) -> None:
    """Assert emptiness and identity gates on a live content payload.

    Raises ``GateError`` on failure.
    """
    source_type = content_payload.get("source_type", "")
    char_count = content_payload.get("char_count", 0) or 0
    floor = emptiness_floor(
        source_type,
        page_count=page_count,
        pdf_floor_per_page=pdf_floor_per_page,
        other_floor=other_floor,
    )

    if char_count < floor:
        raise GateError(
            gate="emptiness",
            message=(
                f"EMPTINESS gate failed: char_count={char_count}, floor={floor}, "
                f"source_type={source_type}, page_count={page_count}"
            ),
            exit_code=EXIT_EMPTINESS,
        )

    content_text = content_payload.get("content", "") or ""
    missing = identity_gate(content_text, required_phrases)
    if missing is not None:
        raise GateError(
            gate="identity",
            message=(
                f"IDENTITY gate failed: required phrase not found: {missing!r} "
                f"(checked {len(required_phrases)} phrase(s))"
            ),
            exit_code=EXIT_IDENTITY,
        )


def run_add_verify(
    notebook_id: str,
    *,
    url: Optional[str] = None,
    file_path: Optional[Path] = None,
    text: Optional[str] = None,
    title: Optional[str] = None,
    required_phrases: list[str],
    profile: str = "default",
    pdf_floor_per_page: int = DEFAULT_PDF_FLOOR_CHARS_PER_PAGE,
    other_floor: int = DEFAULT_OTHER_FLOOR_CHARS,
    ocr_fallback: bool = False,
    ocr_lang: str = "eng",
    wait_timeout: float = NLM_ADD_TIMEOUT,
    poll_timeout: float = CONTENT_POLL_TIMEOUT,
    run_nlm: RunNlm = default_run_nlm,
) -> int:
    """Core orchestration: add, verify, optionally OCR fallback, cleanup on failure.

    Returns an exit code (0 on success).
    """
    source_ids_added: list[str] = []
    try:
        source_id = add_source(
            notebook_id,
            url=url,
            file_path=file_path,
            text=text,
            title=title,
            profile=profile,
            wait_timeout=wait_timeout,
            run_nlm=run_nlm,
        )
        source_ids_added.append(source_id)
        logger.info("Added source %s to notebook %s", source_id, notebook_id)

        content_payload = poll_source_content(
            source_id, profile=profile, poll_timeout=poll_timeout, run_nlm=run_nlm
        )

        page_count = 1
        if file_path and file_path.suffix.lower() == ".pdf":
            page_count = pdf_page_count(file_path)

        try:
            verify_source(
                content_payload,
                required_phrases=required_phrases,
                pdf_floor_per_page=pdf_floor_per_page,
                other_floor=other_floor,
                page_count=page_count,
            )
        except GateError as gate_err:
            if (
                ocr_fallback
                and gate_err.gate == "emptiness"
                and file_path
                and file_path.suffix.lower() == ".pdf"
            ):
                logger.warning("Emptiness gate failed on PDF; attempting local OCR fallback")
                return _run_ocr_fallback(
                    notebook_id=notebook_id,
                    original_source_id=source_id,
                    file_path=file_path,
                    title=title,
                    required_phrases=required_phrases,
                    profile=profile,
                    pdf_floor_per_page=pdf_floor_per_page,
                    other_floor=other_floor,
                    ocr_lang=ocr_lang,
                    wait_timeout=wait_timeout,
                    poll_timeout=poll_timeout,
                    run_nlm=run_nlm,
                )
            raise

        logger.info(
            "Source %s verified: char_count=%s, gates passed",
            source_id,
            content_payload.get("char_count"),
        )
        return EXIT_OK

    except GateError as exc:
        logger.error("%s", exc.message)
        delete_sources(source_ids_added, profile=profile, run_nlm=run_nlm)
        return exc.exit_code
    except NlmError as exc:
        if exc.is_phantom:
            logger.error("Phantom source detected: %s", exc)
            delete_sources(source_ids_added, profile=profile, run_nlm=run_nlm)
            return EXIT_PHANTOM
        logger.error("nlm error: %s", exc)
        delete_sources(source_ids_added, profile=profile, run_nlm=run_nlm)
        return EXIT_NLM_ERROR
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error: %s", exc, exc_info=True)
        delete_sources(source_ids_added, profile=profile, run_nlm=run_nlm)
        return EXIT_NLM_ERROR


def _run_ocr_fallback(
    notebook_id: str,
    *,
    original_source_id: str,
    file_path: Path,
    title: Optional[str],
    required_phrases: list[str],
    profile: str,
    pdf_floor_per_page: int,
    other_floor: int,
    ocr_lang: str,
    wait_timeout: float,
    poll_timeout: float,
    run_nlm: RunNlm,
) -> int:
    """Run OCR on the local PDF, upload the text, verify it, keep the original PDF."""
    instrument = title or file_path.name
    try:
        ocr_text = ocr_pdf_to_text(file_path, lang=ocr_lang)
    except RuntimeError as exc:
        logger.error("OCR fallback failed: %s", exc)
        delete_sources([original_source_id], profile=profile, run_nlm=run_nlm)
        return EXIT_NLM_ERROR

    provenance = build_ocr_provenance(
        instrument=instrument,
        char_count=len(ocr_text),
        dpi=300,
        tool="tesseract",
    )
    full_text = provenance + ocr_text

    ocr_title = f"{instrument} (OCR text)" if instrument else "OCR text"
    try:
        ocr_source_id = add_source(
            notebook_id,
            text=full_text,
            title=ocr_title,
            profile=profile,
            wait_timeout=wait_timeout,
            run_nlm=run_nlm,
        )
    except NlmError as exc:
        logger.error("Failed to upload OCR fallback text: %s", exc)
        delete_sources([original_source_id], profile=profile, run_nlm=run_nlm)
        return EXIT_NLM_ERROR

    try:
        ocr_content = poll_source_content(
            ocr_source_id, profile=profile, poll_timeout=poll_timeout, run_nlm=run_nlm
        )
        verify_source(
            ocr_content,
            required_phrases=required_phrases,
            pdf_floor_per_page=pdf_floor_per_page,
            other_floor=other_floor,
            page_count=1,  # OCR text is one virtual "page" for floor purposes
        )
    except GateError as exc:
        logger.error("OCR fallback failed verification: %s", exc.message)
        delete_sources([original_source_id, ocr_source_id], profile=profile, run_nlm=run_nlm)
        return exc.exit_code
    except NlmError as exc:
        logger.error("OCR fallback source unreadable: %s", exc)
        delete_sources([original_source_id, ocr_source_id], profile=profile, run_nlm=run_nlm)
        return EXIT_PHANTOM if exc.is_phantom else EXIT_NLM_ERROR

    logger.info(
        "OCR fallback succeeded: kept original PDF %s and added OCR text source %s "
        "(%s characters)",
        original_source_id,
        ocr_source_id,
        len(ocr_text),
    )
    return EXIT_OK


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Verifying loader for NotebookLM sources.")
    p.add_argument("notebook_id", help="Notebook UUID")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", "-u", help="URL source")
    src.add_argument("--file", "-f", type=Path, help="Local file source (PDF, etc.)")
    src.add_argument("--text", "-t", help="Inline text source")
    p.add_argument("--title", help="Source title")
    p.add_argument(
        "--required-phrase",
        "-r",
        action="append",
        required=True,
        help="Phrase that must appear in the live extracted content (repeatable)",
    )
    p.add_argument("--profile", "-p", default="default", help="nlm profile (default: default)")
    p.add_argument(
        "--floor-chars-per-page",
        type=int,
        default=DEFAULT_PDF_FLOOR_CHARS_PER_PAGE,
        help=f"PDF emptiness floor per page (default: {DEFAULT_PDF_FLOOR_CHARS_PER_PAGE})",
    )
    p.add_argument(
        "--floor-chars",
        type=int,
        default=DEFAULT_OTHER_FLOOR_CHARS,
        help=f"Absolute emptiness floor for non-PDF sources (default: {DEFAULT_OTHER_FLOOR_CHARS})",
    )
    p.add_argument(
        "--ocr-fallback",
        action="store_true",
        help="If a local PDF fails the emptiness gate, run local OCR and upload the text",
    )
    p.add_argument("--ocr-lang", default="eng", help="Tesseract language pack (default: eng)")
    p.add_argument(
        "--wait-timeout",
        type=float,
        default=NLM_ADD_TIMEOUT,
        help=f"Seconds to wait for nlm source add processing (default: {NLM_ADD_TIMEOUT})",
    )
    p.add_argument(
        "--poll-timeout",
        type=float,
        default=CONTENT_POLL_TIMEOUT,
        help=f"Seconds to poll nlm source content after add (default: {CONTENT_POLL_TIMEOUT})",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_add_verify(
        args.notebook_id,
        url=args.url,
        file_path=args.file,
        text=args.text,
        title=args.title,
        required_phrases=args.required_phrase,
        profile=args.profile,
        pdf_floor_per_page=args.floor_chars_per_page,
        other_floor=args.floor_chars,
        ocr_fallback=args.ocr_fallback,
        ocr_lang=args.ocr_lang,
        wait_timeout=args.wait_timeout,
        poll_timeout=args.poll_timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
