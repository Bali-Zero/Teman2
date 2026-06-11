"""OCR round-trip readability check — the deterministic anti-hallucination oracle.

The designer loop's vision critic + brand verifier (claude_vision.py) are VLMs:
they SEE the slide well enough to judge composition, but they HALLUCINATE text
specifics (E2E 2026-06-07: reported "5 RULES CHANGED." when the slide says
"3 RULES", and a garbled "...keewkuhan" that wasn't there). Because the brand
verifier is fail-closed, a hallucinated "headline garbled/clipped" can block a
GOOD change.

This module closes that gap with the SOTA dimension #1 (design-critic-loop-sota
research): OCR the RENDERED png and check the title comes back verbatim. A pure
OCR model READS text, it does not GENERATE it — so it can't hallucinate the way
a VLM does. If OCR can read the headline, "garbled/clipped" is false; if OCR
can't, the slide really is broken.

Engine: EasyOCR (MIT, vendored — see OCR_PROVENANCE.md). Chosen over the existing
tesseract→qwen2.5vl cascade (crm_guardian/ocr.py) because: (a) qwen is itself a
VLM that hallucinates — wrong tool for an anti-hallucination check; (b) torch is
already installed in the backend venv on all 3 machines, so EasyOCR runs
identically on M5/Pro/Mini with no per-host system binary (tesseract is Pro-only);
(c) EasyOCR is stronger on large display type over a photo (our exact case) than
tesseract (built for A4 scans).

Reuse: the verbatim comparison uses difflib.SequenceMatcher with the same
normalization idiom as knowledge_graph/quality_filter.py:358.

Graceful degradation: if EasyOCR can't import/init, the verdict is `degraded`
and `legible=True` — we NEVER block the pipeline on an OCR-engine outage (same
philosophy as the QA-outage pass-through in the production layout loop).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

logger = logging.getLogger("wr2.ocr_check")

# Default verbatim floor. A perfect read is 1.0; uppercase display type over a
# photo realistically lands ~0.80-0.95 when truly legible. 0.75 leaves margin
# for OCR quirks while still catching a clipped/garbled title (which scores far
# lower because whole glyphs are missing).
DEFAULT_FLOOR = 0.75

# module-level cached reader — easyocr.Reader construction is expensive (loads
# the model), so we build it once per process.
_READER = None
_READER_FAILED = False


def _get_reader():
    """Lazily build a cached EasyOCR reader (English, CPU for determinism+parity).

    Returns None if EasyOCR is unavailable (mid-install / missing) — callers must
    degrade gracefully.
    """
    global _READER, _READER_FAILED
    if _READER is not None:
        return _READER
    if _READER_FAILED:
        return None
    try:
        import easyocr  # noqa: PLC0415 (lazy: package may be installing)

        # gpu=False → deterministic + identical across M5/Pro/Mini (no CUDA/MPS
        # nondeterminism). English only (brand copy is EN; ID terms are short).
        _READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        return _READER
    except Exception as exc:  # import error, model download failure, etc.
        logger.warning("EasyOCR unavailable (%s) — OCR check will degrade to pass", exc)
        _READER_FAILED = True
        return None


@dataclass
class OcrVerdict:
    """Result of an OCR round-trip headline check."""

    legible: bool          # score >= floor (or degraded → True, don't block)
    score: float           # best verbatim alignment 0..1 (-1.0 if degraded)
    ocr_text: str          # the joined text EasyOCR actually read
    expected: str          # the headline we expected to find
    mean_confidence: float # EasyOCR's own mean per-line confidence (0..1)
    degraded: bool = False # True if the OCR engine was unavailable


def _normalize(s: str) -> str:
    """Uppercase, strip punctuation to spaces, collapse whitespace.

    Mirrors quality_filter._similarity normalization (upper+strip) but also
    neutralizes punctuation so 'VALID. 3 RULES' and 'VALID 3 RULES' compare
    equal — OCR is unreliable on periods/commas, and we care about the WORDS.
    """
    s = s.upper()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)  # punctuation → space
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _token_coverage(expected_norm: str, ocr_norm: str) -> float:
    """Fraction of expected tokens present in the OCR text (order-independent).

    A headline can be split across several OCR detection lines in any order; a
    pure sequence ratio under-rewards that. Token coverage catches "every word
    of the headline is somewhere in the read" even if the line order differs.
    """
    exp_tokens = expected_norm.split()
    if not exp_tokens:
        return 0.0
    ocr_tokens = set(ocr_norm.split())
    hit = sum(1 for t in exp_tokens if t in ocr_tokens)
    return hit / len(exp_tokens)


def ocr_read(png_path: Path) -> list[tuple[str, float]]:
    """OCR a PNG → list of (text_line, confidence). Empty list if degraded."""
    reader = _get_reader()
    if reader is None:
        return []
    try:
        # detail=1 → (bbox, text, confidence); we keep text+conf.
        results = reader.readtext(str(png_path), detail=1, paragraph=False)
    except Exception as exc:
        logger.warning("EasyOCR readtext failed on %s: %s", png_path, exc)
        return []
    out: list[tuple[str, float]] = []
    for item in results:
        # item = [bbox, text, conf]
        if len(item) >= 3:
            out.append((str(item[1]), float(item[2])))
        elif len(item) == 2:
            out.append((str(item[1]), 1.0))
    return out


def headline_legible(
    png_path: Path,
    expected_headline: str,
    *,
    floor: float = DEFAULT_FLOOR,
) -> OcrVerdict:
    """Is the expected headline actually readable in the rendered PNG?

    Computes the best of two signals on normalized text:
      - SequenceMatcher ratio of the expected headline vs the full OCR text
        (rewards verbatim contiguous presence)
      - token coverage (rewards all words present even if split/reordered)
    score = max(ratio, coverage). legible = score >= floor.

    Degrades to legible=True (never block) if the OCR engine is unavailable.
    """
    expected = (expected_headline or "").strip()
    if not expected:
        # nothing to check → not a failure
        return OcrVerdict(legible=True, score=1.0, ocr_text="", expected="", mean_confidence=0.0)

    lines = ocr_read(Path(png_path))
    reader_present = _get_reader() is not None
    if not lines and not reader_present:
        # engine unavailable → degrade to pass (don't block pipeline)
        return OcrVerdict(
            legible=True, score=-1.0, ocr_text="", expected=expected,
            mean_confidence=0.0, degraded=True,
        )

    ocr_text = " ".join(t for t, _ in lines)
    mean_conf = (sum(c for _, c in lines) / len(lines)) if lines else 0.0

    exp_n = _normalize(expected)
    ocr_n = _normalize(ocr_text)

    ratio = SequenceMatcher(None, exp_n, ocr_n).ratio() if ocr_n else 0.0
    coverage = _token_coverage(exp_n, ocr_n)
    score = max(ratio, coverage)

    return OcrVerdict(
        legible=score >= floor,
        score=round(score, 3),
        ocr_text=ocr_text,
        expected=expected,
        mean_confidence=round(mean_conf, 3),
        degraded=False,
    )


# Keywords in a brand-verifier issue that indicate a TEXT-LEGIBILITY claim (the
# only kind OCR can adjudicate). Used by the designer loop to decide whether to
# OCR-check a verifier rejection. Bilingual (the verifier sometimes replies IT).
TEXT_CLAIM_KEYWORDS = (
    "headline", "title", "titolo", "garbled", "garbl", "clipped", "clip",
    "cut off", "cut-off", "tagliat", "illegible", "illeggibil", "unreadable",
    "non leggibil", "occlud", "occlus", "troncat", "truncat",
)


def is_text_legibility_claim(issue: str) -> bool:
    """Does this brand-verifier issue assert the headline text is broken?

    OCR can only override THIS class of claim (it adjudicates text legibility,
    not palette/font/logo). Palette/font claims stay non-overridable.
    """
    low = issue.lower()
    return any(k in low for k in TEXT_CLAIM_KEYWORDS)
