#!/usr/bin/env python3
"""dossier_pull.py — GARUDA-FILIERA per-code D0 evidence pull (deterministic).

Given a code list, pulls every applicable vault layer for each code into
<out>/<code>/: canonical.json (repo dataset row), oss/ (RBA snapshot or a
recorded ABSENT/NOT_APPLICABLE verdict), crosswalk/ (BPS Vol.2 Lampiran 5/10
rendered page hits) and pp28/ (PP 28/2025 lampiran rendered page hits),
plus evidence-index.json — the flat manifest of everything pulled, each
item carrying {rel_path, sha256, source, locator, created_at}.

Runs against the LOCAL vault (Mini, ~/nuzantara-vault/ by default per
vault_common.DEFAULT_VAULT_ROOT) — no network calls of its own; every byte
here was already fetched by the batch-0 vault_fetch_* compilers. This is
the D0 stage of research/operations/2026-07-16-kbli-garuda-filiera-workflow.md
§3: "ABSENT is earned, not defaulted" — every applicable layer either cites
a vault item or writes an explicit ABSENT verdict; nothing is silently
skipped (P3, kbli-navigator SKILL.md §4.3).

OCR TRAP (kbli-navigator SKILL.md §3, grounded 2026-07-16): pdftotext on
these BPK/BPS scans renders digit `1` as `t`/`l`/`I` ("68112"->"681t2").
Every digit-string search in this file goes through `fuzzy_code_pattern`,
never a literal `code in text` substring check — and every hit is anchored
to the WHOLE code token (never a floating substring inside a longer digit
run; superscar #3, "guard-over-match" applies to evidence-hunting regexes
just as much as to command guards).

PP28 scoping (per-code, documented here because there is no static
KBLI-sector -> PP28-lampiran-letter table anywhere in the repo to import):
canonical records already carry `sektor_id` in the SAME letter alphabet as
PP28 lampiran filenames (`sektor_id="I.H"` for code 43216, whose PP28 hit
IS in Lampiran I.H — verified live 2026-07-16). `sektor_id_to_lampiran_letters`
parses that field (including a `"I.J-P"` compound-range form, alphabetically
expanded) into a candidate letter set. Candidates are: that set, UNION the
two known collision surfaces (Lampiran I.L, I.H — 68112-class), and widened
to a FULL 21-file scan whenever canonical has `_l2_source: null` (the
highest-risk "no OSS scope" class, kbli-navigator SKILL.md §2.3). Every
scan logs N-of-M files/pages actually walked (W97: a cap must say so).

Usage:
    python scripts/kbli_filiera/dossier_pull.py --codes 68112,51103,65121 \\
        --vault-root ~/nuzantara-vault --out /tmp/pilot-a1-evidence
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

LOG = common.setup_logger("dossier_pull")

DEFAULT_CANONICAL_PATH = Path("data/source_documents/KBLI_2025_FINAL_CLEAN.json")

OSS_ENDPOINTS: tuple[str, ...] = ("detail", "ruang_lingkup", "relasi", "umku")

# Known PP28/BPS collision surfaces (kbli-navigator SKILL.md §2.1/§2.8) —
# always scanned regardless of a code's own sektor_id, because a compound
# sektor_id range (e.g. "I.J-P" for 68112) does not pin down the exact
# letter a code actually landed in.
COLLISION_LETTERS: frozenset[str] = frozenset({"I.L", "I.H"})

# BPS Vol.2 lampiran windows (research/operations/2026-07-17-kbli-pilot-a1-
# preregistration.md "Vault snapshot pinned for this pilot" — 444pp total,
# Lampiran 5 (2020->2025) from p.117, Lampiran 10 (2025->2020) from ~p.233).
# These are FIXED windows, not discovered from the PDF's own structure (no
# bookmark/outline is assumed present) — override via CLI if a future vault
# refresh reflows the page numbers.
BPS_LAMPIRAN5_WINDOW = (117, 232)
BPS_LAMPIRAN10_WINDOW = (233, 444)

PP28_PAGE_CAP = 10  # per-code cap across ALL candidate PP28 files (W97)


# ---------------------------------------------------------------------------
# Fuzzy digit matching (OCR digit-confusion tolerant, whole-token anchored)
# ---------------------------------------------------------------------------

# Per-digit OCR confusion classes. "1"->"tlLiI" and "0"->"oOQ" are the
# grounded, explicitly-documented confusions (kbli-navigator SKILL.md §3,
# "681t2" live-verified). The rest follow the same well-known OCR
# digit/letter confusion pairs (0/O, 1/l/I, 2/Z, 5/S, 6/G, 8/B, 9/g/q) —
# applied uniformly rather than singled out, since an un-covered digit
# would just silently under-match on a page that misrendered THAT digit.
_DIGIT_FUZZ: dict[str, str] = {
    "0": "0oOQ",
    "1": "1tlLiI",
    "2": "2zZ",
    "3": "3",
    "4": "4",
    "5": "5sS",
    "6": "6gG",
    "7": "7",
    "8": "8bB",
    "9": "9gq",
}
_FUZZY_UNIVERSE = "".join(sorted(set("".join(_DIGIT_FUZZ.values()))))


def fuzzy_code_pattern(code: str) -> re.Pattern[str]:
    """Compiles a whole-token, OCR-confusion-tolerant regex for a digit
    string like "68112". Anchored on BOTH sides with a negative lookaround
    against the full fuzzy-char universe (not just \\d) so the match can
    never be a floating substring of a LONGER digit-or-lookalike run
    (superscar #3 — "168112" must never register as a hit for "68112").

    Raises ValueError on a non-digit input — never silently degrades to a
    literal-substring search (the whole point of this function)."""
    if not code or not code.isdigit():
        raise ValueError(f"fuzzy_code_pattern requires a plain digit string, got {code!r}")
    body = "".join(f"[{_DIGIT_FUZZ[d]}]" for d in code)
    boundary_class = re.escape(_FUZZY_UNIVERSE)
    pattern = rf"(?<![{boundary_class}]){body}(?![{boundary_class}])"
    return re.compile(pattern)


def find_code_hits(text: str, code: str) -> list[int]:
    """0-based character offsets of every whole-token fuzzy hit of `code`
    in `text`. Pure, no I/O — the unit under test for the digit-fuzzing
    guilt/innocence corpus."""
    pattern = fuzzy_code_pattern(code)
    return [m.start() for m in pattern.finditer(text)]


# ---------------------------------------------------------------------------
# sektor_id -> PP28 lampiran letter candidates
# ---------------------------------------------------------------------------

_SEKTOR_ID_RE = re.compile(r"^(?P<num>[IVXLCDM]+)\.(?P<a>[A-Z])(?:-(?P<b>[A-Z]))?")


def sektor_id_to_lampiran_letters(sektor_id: str | None) -> set[str]:
    """Parses a canonical `sektor_id` value into candidate PP28 lampiran
    letters. Handles the compound-range form ("I.J-P" -> I.J..I.P) and
    ignores any third-level sub-classification ("I.F.c" -> {"I.F"}).
    Returns an empty set (never raises) on an unparseable/missing value —
    callers always UNION this with COLLISION_LETTERS, so an empty parse
    degrades to "scan the known collision surfaces only", not zero scan."""
    if not sektor_id:
        return set()
    m = _SEKTOR_ID_RE.match(sektor_id)
    if not m:
        return set()
    num, a, b = m.group("num"), m.group("a"), m.group("b")
    if not b:
        return {f"{num}.{a}"}
    start, end = ord(a), ord(b)
    if end < start:  # malformed range — degrade to the single anchor letter
        return {f"{num}.{a}"}
    return {f"{num}.{chr(c)}" for c in range(start, end + 1)}


def pp28_scan_scope(record: dict) -> tuple[set[str], bool]:
    """(candidate_letters, full_scan). full_scan=True means every lampiran
    id is a candidate regardless of letter (the "_l2_source is null" —
    no-OSS-scope — highest-risk class, kbli-navigator SKILL.md §2.3)."""
    full_scan = record.get("_l2_source") is None
    letters = sektor_id_to_lampiran_letters(record.get("sektor_id")) | set(COLLISION_LETTERS)
    return letters, full_scan


# ---------------------------------------------------------------------------
# Canonical extraction (1a)
# ---------------------------------------------------------------------------

def load_canonical_index(canonical_path: Path) -> dict[str, dict]:
    data = json.loads(canonical_path.read_text(encoding="utf-8"))
    return {str(r.get("kode_kbli_2025")): r for r in data.get("data", [])}


def pull_canonical(code: str, record: dict, canonical_path: Path, out_dir: Path, *, fetched_at: str) -> dict:
    """Writes <out_dir>/canonical.json and returns its evidence-index item."""
    dest = out_dir / "canonical.json"
    payload = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    dest.write_text(payload, encoding="utf-8")
    return evidence_item(
        rel_path="canonical.json",
        sha256=common.sha256_bytes(payload.encode("utf-8")),
        source=f"{canonical_path.as_posix()}#{code}",
        locator={"kode_kbli_2025": code},
        created_at=fetched_at,
    )


# ---------------------------------------------------------------------------
# OSS pull (1b)
# ---------------------------------------------------------------------------

def load_oss_absences(vault_root: Path) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for rec in common.read_jsonl(vault_root / "oss" / "absences.jsonl"):
        key = (rec.get("code"), rec.get("endpoint"))
        out[key] = rec
    return out


def pull_oss(code: str, vault_root: Path, out_dir: Path, *, fetched_at: str) -> list[dict]:
    """Copies every present <vault_root>/oss/<code>/<endpoint>.json into
    <out_dir>/oss/, and for every endpoint NOT found on disk writes a
    quoted absence record (from absences.jsonl if one was recorded there,
    else an honest "no data, no absence record" verdict — a fetch GAP is
    never silently conflated with a corroborated ABSENT) into
    <out_dir>/oss/ABSENT.json. Never leaves oss/ empty (P3)."""
    src_dir = vault_root / "oss" / code
    oss_out = out_dir / "oss"
    absences = load_oss_absences(vault_root)
    items: list[dict] = []
    missing: list[dict] = []

    for endpoint in OSS_ENDPOINTS:
        src = src_dir / f"{endpoint}.json"
        if src.exists():
            oss_out.mkdir(parents=True, exist_ok=True)
            data = src.read_bytes()
            dest = oss_out / f"{endpoint}.json"
            dest.write_bytes(data)
            items.append(evidence_item(
                rel_path=f"oss/{endpoint}.json",
                sha256=common.sha256_bytes(data),
                source=(src.relative_to(vault_root)).as_posix(),
                locator={"endpoint": endpoint},
                created_at=fetched_at,
            ))
            continue

        absence = absences.get((code, endpoint))
        if absence is not None:
            missing.append({"endpoint": endpoint, "verdict": "absent", "record": absence})
        else:
            missing.append({"endpoint": endpoint, "verdict": "no_data_no_absence_record"})

    if missing:
        oss_out.mkdir(parents=True, exist_ok=True)
        absent_path = oss_out / "ABSENT.json"
        payload = json.dumps({"code": code, "missing_endpoints": missing}, ensure_ascii=False, indent=2) + "\n"
        absent_path.write_text(payload, encoding="utf-8")
        items.append(evidence_item(
            rel_path="oss/ABSENT.json",
            sha256=common.sha256_bytes(payload.encode("utf-8")),
            source=(vault_root / "oss" / "absences.jsonl").relative_to(vault_root).as_posix(),
            locator={"missing_endpoints": [m["endpoint"] for m in missing]},
            created_at=fetched_at,
        ))
        LOG.info("code=%s oss: %s of %s endpoints present, %s recorded missing",
                  code, len(OSS_ENDPOINTS) - len(missing), len(OSS_ENDPOINTS), len(missing))
    return items


# ---------------------------------------------------------------------------
# PDF tooling (thin subprocess wrappers — fail-visible if the binaries are
# absent; the page-matching LOGIC above/below is pure and unit-testable
# without ever invoking these)
# ---------------------------------------------------------------------------

def require_pdf_tools() -> None:
    missing = [t for t in ("pdftotext", "pdftoppm") if shutil.which(t) is None]
    if missing:
        raise RuntimeError(
            f"required PDF tool(s) not on PATH: {', '.join(missing)} "
            "(poppler-utils — this script does not install it; see kbli-navigator SKILL.md §3)"
        )


def extract_pages_text(pdf_path: Path, first: int, last: int) -> dict[int, str]:
    """Runs `pdftotext -f first -l last <pdf> -` ONCE and splits the result
    on poppler's per-page form-feed separator, mapping back to real page
    numbers by offset from `first`. One subprocess call per window instead
    of one per page — the 444pp BPS file makes per-page invocation
    needlessly expensive."""
    result = subprocess.run(
        ["pdftotext", "-f", str(first), "-l", str(last), str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    pages = result.stdout.split("\f")
    # poppler emits one \f-terminated chunk per page in range, plus a
    # trailing empty chunk after the final \f — drop it if present.
    if pages and pages[-1] == "":
        pages = pages[:-1]
    return {first + i: text for i, text in enumerate(pages)}


def render_page_png(pdf_path: Path, page: int, out_prefix: Path, *, dpi: int = 300) -> Path:
    """Renders exactly one page to <out_prefix>-<page>.png at `dpi` and
    returns the resulting path. Raises CalledProcessError (never silently
    no-ops) if pdftoppm fails."""
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-png",
         str(pdf_path), str(out_prefix)],
        check=True, capture_output=True,
    )
    candidates = sorted(out_prefix.parent.glob(f"{out_prefix.name}-*{page}.png"))
    if not candidates:
        # poppler pads page numbers with zeros once the doc has >=100/1000
        # pages — glob for any file with this prefix as a fallback.
        candidates = sorted(out_prefix.parent.glob(f"{out_prefix.name}*.png"))
    if not candidates:
        raise RuntimeError(f"pdftoppm produced no output for page {page} of {pdf_path}")
    return candidates[-1]


# ---------------------------------------------------------------------------
# Crosswalk pull (1c) — BPS Vol.2 Lampiran 5 / Lampiran 10
# ---------------------------------------------------------------------------

def find_candidate_pages(pages_text: dict[int, str], code: str) -> list[int]:
    """Sorted page numbers where a whole-token fuzzy hit of `code` occurs.
    Pure — the matching logic under test independent of any subprocess."""
    return sorted(p for p, text in pages_text.items() if find_code_hits(text, code))


def pull_crosswalk(code: str, vault_root: Path, out_dir: Path, *, bps_pdf: Path | None,
                    fetched_at: str) -> list[dict]:
    xwalk_out = out_dir / "crosswalk"
    if bps_pdf is None or not bps_pdf.exists():
        xwalk_out.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "code": code, "verdict": "absent",
            "reason": "BPS Vol.2 not found in vault at pull time",
            "pages_scanned": [],
        }, ensure_ascii=False, indent=2) + "\n"
        (xwalk_out / "ABSENT.json").write_text(payload, encoding="utf-8")
        return [evidence_item(
            rel_path="crosswalk/ABSENT.json", sha256=common.sha256_bytes(payload.encode("utf-8")),
            source="vault:bps (not found)", locator=None, created_at=fetched_at,
        )]

    items: list[dict] = []
    pages_scanned: list[int] = []
    hits: list[tuple[str, int]] = []  # (lampiran, page)

    for lampiran, window in (("5", BPS_LAMPIRAN5_WINDOW), ("10", BPS_LAMPIRAN10_WINDOW)):
        pages_text = extract_pages_text(bps_pdf, *window)
        pages_scanned.extend(pages_text.keys())
        for page in find_candidate_pages(pages_text, code):
            hits.append((lampiran, page))

    for lampiran, page in hits:
        prefix = xwalk_out / f"lampiran{lampiran}_p{page}"
        png_path = render_page_png(bps_pdf, page, prefix)
        rel_name = f"crosswalk/{png_path.name}"
        (xwalk_out).mkdir(parents=True, exist_ok=True)
        final_path = xwalk_out / png_path.name
        if png_path != final_path:
            png_path.replace(final_path)
        data = final_path.read_bytes()
        items.append(evidence_item(
            rel_path=rel_name, sha256=common.sha256_bytes(data),
            source=bps_pdf.relative_to(vault_root).as_posix() if _is_relative_to(bps_pdf, vault_root) else str(bps_pdf),
            locator={"lampiran": lampiran, "page": page}, created_at=fetched_at,
        ))

    if not hits:
        xwalk_out.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "code": code, "verdict": "absent",
            "pages_scanned": sorted(set(pages_scanned)),
        }, ensure_ascii=False, indent=2) + "\n"
        (xwalk_out / "ABSENT.json").write_text(payload, encoding="utf-8")
        items.append(evidence_item(
            rel_path="crosswalk/ABSENT.json", sha256=common.sha256_bytes(payload.encode("utf-8")),
            source=bps_pdf.relative_to(vault_root).as_posix() if _is_relative_to(bps_pdf, vault_root) else str(bps_pdf),
            locator={"pages_scanned": sorted(set(pages_scanned))}, created_at=fetched_at,
        ))
    LOG.info("code=%s crosswalk: %s page(s) scanned, %s hit(s)", code, len(set(pages_scanned)), len(hits))
    return items


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# PP28 pull (1d)
# ---------------------------------------------------------------------------

def load_pp28_fetch_log(vault_root: Path) -> list[dict]:
    """Latest (by id) clean-200 fetch-log records only — the id->letter map
    this compiler needs, per vault_fetch_pp28.py's own {fragment, letter,
    range} parse."""
    latest: dict[int, dict] = {}
    for rec in common.read_jsonl(vault_root / "pp28" / "fetch-log.jsonl"):
        if rec.get("http_status") == 200 and rec.get("id") is not None:
            latest[rec["id"]] = rec
    return list(latest.values())


def select_pp28_candidates(record: dict, fetch_log: list[dict]) -> tuple[list[dict], bool]:
    """Returns (candidate fetch-log records, full_scan). Pure — the
    scoping decision under test independent of any filesystem/vault."""
    letters, full_scan = pp28_scan_scope(record)
    if full_scan:
        return list(fetch_log), True
    return [r for r in fetch_log if r.get("letter") in letters], False


def pull_pp28(code: str, vault_root: Path, out_dir: Path, record: dict, *, fetched_at: str) -> list[dict]:
    sources: list[str] = [s for s in (record.get("pp28_sources") or []) if s]
    pp28_out = out_dir / "pp28"

    if not sources:
        pp28_out.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "code": code, "verdict": "not_applicable",
            "reason": "canonical pp28_sources is empty — PP28 layer does not apply to this code",
        }, ensure_ascii=False, indent=2) + "\n"
        (pp28_out / "NOT_APPLICABLE.json").write_text(payload, encoding="utf-8")
        return [evidence_item(
            rel_path="pp28/NOT_APPLICABLE.json", sha256=common.sha256_bytes(payload.encode("utf-8")),
            source="canonical.json#pp28_sources", locator=None, created_at=fetched_at,
        )]

    fetch_log = load_pp28_fetch_log(vault_root)
    candidates, full_scan = select_pp28_candidates(record, fetch_log)
    LOG.info("code=%s pp28: %s of %s lampiran file(s) scanned (full_scan=%s)",
              code, len(candidates), len(fetch_log), full_scan)

    items: list[dict] = []
    hits: list[tuple[dict, str, int]] = []  # (fetch_log_rec, source_code, page)
    pages_scanned_total = 0
    capped = False

    for rec in sorted(candidates, key=lambda r: r.get("id", 0)):
        rel_path = rec.get("rel_path")
        if not rel_path:
            continue
        pdf_path = vault_root / rel_path
        if not pdf_path.exists():
            continue
        pages_text = extract_pages_text(pdf_path, 1, _pdf_page_count(pdf_path))
        pages_scanned_total += len(pages_text)
        for source_code in sources:
            for page in find_candidate_pages(pages_text, source_code):
                if len(hits) >= PP28_PAGE_CAP:
                    capped = True
                    break
                hits.append((rec, source_code, page))
            if capped:
                break
        if capped:
            break

    for rec, source_code, page in hits:
        pdf_path = vault_root / rec["rel_path"]
        prefix = pp28_out / f"{rec['id']}_p{page}"
        png_path = render_page_png(pdf_path, page, prefix)
        pp28_out.mkdir(parents=True, exist_ok=True)
        final_path = pp28_out / png_path.name
        if png_path != final_path:
            png_path.replace(final_path)
        data = final_path.read_bytes()
        items.append(evidence_item(
            rel_path=f"pp28/{final_path.name}", sha256=common.sha256_bytes(data),
            source=rec["rel_path"], locator={"lampiran_id": rec["id"], "page": page, "code_hunted": source_code},
            created_at=fetched_at,
        ))

    if not hits:
        pp28_out.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "code": code, "verdict": "absent",
            "sources_hunted": sources,
            "files_scanned": [r.get("id") for r in candidates],
            "pages_scanned_total": pages_scanned_total,
        }, ensure_ascii=False, indent=2) + "\n"
        (pp28_out / "ABSENT.json").write_text(payload, encoding="utf-8")
        items.append(evidence_item(
            rel_path="pp28/ABSENT.json", sha256=common.sha256_bytes(payload.encode("utf-8")),
            source="vault:pp28/fetch-log.jsonl",
            locator={"files_scanned": [r.get("id") for r in candidates]}, created_at=fetched_at,
        ))

    if capped:
        LOG.info("code=%s pp28: page-render CAPPED at %s (more matches may exist, not rendered)",
                  code, PP28_PAGE_CAP)
    return items


def _pdf_page_count(pdf_path: Path) -> int:
    """`pdfinfo -f` is not always present alongside poppler-utils'
    pdftotext/pdftoppm on every install, so this shells to pdftotext with
    an intentionally-huge -l and counts form feeds instead of adding a
    third binary dependency — one extra subprocess call per PP28 file,
    acceptable at pilot scale (<=21 files)."""
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    pages = result.stdout.split("\f")
    if pages and pages[-1] == "":
        pages = pages[:-1]
    return max(len(pages), 1)


# ---------------------------------------------------------------------------
# evidence-index.json
# ---------------------------------------------------------------------------

def evidence_item(*, rel_path: str, sha256: str, source: str, locator, created_at: str) -> dict:
    return {"rel_path": rel_path, "sha256": sha256, "source": source, "locator": locator, "created_at": created_at}


def write_evidence_index(out_dir: Path, items: list[dict]) -> Path:
    dest = out_dir / "evidence-index.json"
    dest.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Per-code orchestration + CLI
# ---------------------------------------------------------------------------

def pull_one(code: str, canonical_index: dict[str, dict], vault_root: Path, out_root: Path,
             canonical_path: Path, bps_pdf: Path | None) -> int:
    """Returns 0 on a complete pull, 1 if the code is missing from
    canonical entirely (a compiler exception per §3 D0 — the caller
    quarantines and continues, this never raises)."""
    record = canonical_index.get(code)
    if record is None:
        LOG.error("code=%s NOT FOUND in canonical dataset — skipped (quarantine candidate)", code)
        return 1

    out_dir = out_root / code
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = common.now_iso()

    items: list[dict] = []
    items += [pull_canonical(code, record, canonical_path, out_dir, fetched_at=fetched_at)]
    items += pull_oss(code, vault_root, out_dir, fetched_at=fetched_at)
    items += pull_crosswalk(code, vault_root, out_dir, bps_pdf=bps_pdf, fetched_at=fetched_at)
    items += pull_pp28(code, vault_root, out_dir, record, fetched_at=fetched_at)
    write_evidence_index(out_dir, items)
    LOG.info("code=%s DONE — %s evidence item(s)", code, len(items))
    return 0


def run(codes: list[str], *, vault_root: Path, out_root: Path, canonical_path: Path,
        bps_pdf: Path | None) -> int:
    require_pdf_tools()
    canonical_index = load_canonical_index(canonical_path)
    out_root.mkdir(parents=True, exist_ok=True)
    failures = [c for c in codes if pull_one(c, canonical_index, vault_root, out_root, canonical_path, bps_pdf) != 0]
    if failures:
        LOG.error("PULL COMPLETE with %s of %s codes failed: %s", len(failures), len(codes), failures)
        return 1
    LOG.info("PULL COMPLETE %s of %s codes ok", len(codes), len(codes))
    return 0


def default_bps_pdf(vault_root: Path) -> Path | None:
    matches = sorted((vault_root / "bps").glob("*.pdf")) if (vault_root / "bps").exists() else []
    return matches[0] if matches else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--codes", required=True, help="comma-separated KBLI-2025 codes")
    ap.add_argument("--vault-root", type=Path, default=common.DEFAULT_VAULT_ROOT)
    ap.add_argument("--out", type=Path, required=True, help="output directory (one subdir per code)")
    ap.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    ap.add_argument("--bps-pdf", type=Path, default=None,
                     help="explicit BPS Vol.2 PDF path (default: first *.pdf found under <vault-root>/bps/)")
    args = ap.parse_args(argv)

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        LOG.error("--codes produced an empty list")
        return 2
    if not args.canonical.exists():
        LOG.error("canonical dataset not found: %s", args.canonical)
        return 2

    vault_root = args.vault_root.expanduser()
    bps_pdf = args.bps_pdf.expanduser() if args.bps_pdf else default_bps_pdf(vault_root)

    try:
        return run(codes, vault_root=vault_root, out_root=args.out, canonical_path=args.canonical, bps_pdf=bps_pdf)
    except RuntimeError as exc:
        LOG.error(str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main())
