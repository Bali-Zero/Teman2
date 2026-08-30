#!/usr/bin/env python3
"""probe_amendment_invariant — a self-contained, no-domain-knowledge check on `legal_status`.

Every other measurement of `legal_status` in this campaign (kb/inventory/legal_status.yaml,
scripts/kb/audit_legal_status.py, scripts/kb/propose_legal_status_repair.py) needs a human
who already knows which Indonesian instruments are actually in force to say the field is
wrong. This probe needs none of that. It checks one thing the corpus asserts about ITSELF:

    If document A's own title reads "PERUBAHAN ... ATAS B" (an amendment TO B), B cannot
    be `dicabut` (revoked) -- amending a revoked instrument is not a thing a legislature
    does. If A is in force (`berlaku`) and B is marked `dicabut`, that is not a disputed
    reading of Indonesian law -- it is the corpus contradicting its own citations.

Two forms, kept separate because their evidentiary weight differs:

  STRICT   amender is uniformly `berlaku`, amended is uniformly `dicabut`.
           An outright logical impossibility. -> the RED this probe exists to report.
  WEAK     amended is uniformly `dicabut`, regardless of the amender's own status.
           Weaker (an amender that is itself `dicabut` proves less), kept as
           corroborating evidence, never merged into the STRICT count.

Resolution method (title-text only, no metadata, no filename):
  1. A document's own `[CONTEXT: <TYPE> - NO <N> - TAHUN <Y> - TENTANG <topic>]` header
     is built once per document by LegalChunker._build_context() and repeated on every
     chunk (apps/backend-rag/backend/core/legal/chunker.py:343) -- so any ONE header
     found on ANY of a document's points names that document's own (type, number, year)
     unambiguously.
  2. If "PERUBAHAN [ordinal] ATAS" appears as the FIRST thing after "TENTANG" in that
     header (not merely somewhere in the text -- a citation-history sentence three
     clauses later saying "as amended by X" would otherwise scavenge a match, exactly
     the failure mode the shared LEGAL_TITLE_PATTERN comment warns about), the amended
     instrument's (type, number, year) is extracted from the text immediately following
     with the SAME `LEGAL_TITLE_PATTERN` production ingestion uses for its own title
     block (apps/backend-rag/backend/core/legal/constants.py) -- not a reimplementation.
  3. The (type, number, year) triple is turned into a candidate document_id with the
     SAME abbreviation table (LEGAL_TYPE_ABBREV) and number normalization
     (normalize_document_number) production ingestion uses to build every OTHER
     document_id in this corpus, so a resolved id either matches a real document_id
     in the corpus or it does not -- never a parallel naming scheme.
  4. One disclosed, scoped normalization is applied to the searched text only (never
     to anything written back or reported as if from the payload): whitespace touching
     a hyphen is collapsed ("UNDANG -UNDANG" -> "UNDANG-UNDANG") before matching. This
     is a common OCR line-wrap artifact in this corpus (confirmed on PP_1_2014's own
     citation of UU 27/2007) and collapsing it cannot manufacture a false type-name
     match: none of LEGAL_TYPE_NAMES contains a hyphen-adjacent character this touches
     in a way that changes which name matches.

What this probe does NOT attempt: a title whose year is OCR-corrupted (a literal
capital "O" for the digit "0", e.g. "TAHUN 2OO8") is reported as UNRESOLVED, not
guessed at. The same is true of a resolved id that does not exist in this corpus
(indexed elsewhere, or not indexed at all) -- absence is reported, never silently
treated as compliance. Both are floors on this probe's coverage, stated in its own
output, not folded into the violation count either direction.

READ-ONLY: this script never writes to Qdrant.

Run:
    apps/backend-rag/.venv/bin/python kb/ops/probe_amendment_invariant.py
    apps/backend-rag/.venv/bin/python kb/ops/probe_amendment_invariant.py --json
    apps/backend-rag/.venv/bin/python kb/ops/probe_amendment_invariant.py --collection legal_unified_2026

Exit codes (closed vocabulary, shared with scripts/kb/kb_inventory_probe.py and
kb/ops/probe_retrieval.py -- 2/"outstanding" does not apply to this probe and is
never emitted):
    0  CLEAN        no strict violation found, and at least one amendment relationship
                     was genuinely resolved into this corpus (so "clean" is not silence).
    1  VIOLATION    at least one STRICT violation found -- the corpus contradicts itself.
    3  BROKEN       could not measure: no `.env` / Qdrant unreachable, OR (anti-vacuity)
                     the probe resolved ZERO amendment relationships into the corpus,
                     which given the corpus's own size is itself a probe failure, not
                     evidence of a clean corpus.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

VERDICT_BY_EXIT = {0: "clean", 1: "violation", 3: "broken"}

_MISSING = "<missing:no legal_status field anywhere>"

# The document's own title/CONTEXT header must open with this immediately after
# "TENTANG" for the amendment reference to be trusted as the document's OWN nature,
# rather than a citation-history sentence elsewhere in the same chunk's text quoting
# a DIFFERENT amendment. Ordinals are optional and bounded to the ones actually seen
# in this corpus's own vocabulary (Indonesian ordinal words up to "KEDELAPAN").
_ORDINALS = r"(?:KEDUA|KETIGA|KEEMPAT|KELIMA|KEENAM|KETUJUH|KEDELAPAN)"
AMEND_AT_TITLE_START = re.compile(
    rf"^\s*PERUBAHAN\b(?:\s+{_ORDINALS})?\s*\bATAS\b", re.IGNORECASE
)
TENTANG = re.compile(r"TENTANG", re.IGNORECASE)
CTX = re.compile(r"^\[CONTEXT:\s*(.*?)\]", re.S)

# The searched-slice-only OCR normalization documented in the module docstring §4.
_HYPHEN_OCR = re.compile(r"\s*-\s*")


def _closehyphen(s: str) -> str:
    return _HYPHEN_OCR.sub("-", s)


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("probe_amendment_invariant: repo root not found")


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        print(
            f"BROKEN — {env} not found, no credentials to reach Qdrant with. "
            "Nothing was measured.",
            file=sys.stderr,
        )
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_legal_status(payload: dict) -> str:
    """Same read-only, both-shapes extraction as scripts/kb/audit_legal_status.py's
    extract_legal_status, collapsed to just the effective value (this probe does not
    care WHERE the field lives, only what it says)."""
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    top = payload.get("legal_status")  # legal-status-lint: allow — probe tool, inspects the broken field, does not decide with it
    nested = meta.get("legal_status")  # legal-status-lint: allow — probe tool, inspects the broken field, does not decide with it
    top_present = "legal_status" in payload and top is not None  # legal-status-lint: allow — probe tool, inspects the broken field, does not decide with it
    nested_present = "legal_status" in meta and nested is not None  # legal-status-lint: allow — probe tool, inspects the broken field, does not decide with it
    if top_present and nested_present:
        return str(top) if top == nested else f"CONFLICT[top={top!r} vs metadata={nested!r}]"
    if top_present:
        return str(top)
    if nested_present:
        return str(nested)
    return _MISSING


def extract_document_id(payload: dict) -> str:
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return payload.get("document_id") or meta.get("document_id") or "<none>"


def extract_title(text: str) -> str | None:
    """The document's own `[CONTEXT: ...]` header content, or None if this chunk
    carries no header (30.6% of points in legal_unified do not -- see
    kb/inventory/legal_status.yaml's CONTEXT-header coverage caveat)."""
    if not isinstance(text, str):
        return None
    m = CTX.match(text)
    return m.group(1) if m else None


def resolve_amendment_target(
    title: str,
    legal_title_pattern: "re.Pattern[str]",
    legal_type_abbrev: dict,
    normalize_document_number,
) -> str | None:
    """Pure function: does this document's OWN title open (right after TENTANG) with
    an amendment referencing another instrument, and if so, what document_id would
    that instrument have under this corpus's own id-construction convention?

    Returns None if: no TENTANG found, no amendment opens right after it, the
    referenced type/number/year cannot be co-located by legal_title_pattern within
    its own bounded window (see that pattern's own docstring for why the window is
    bounded), the type name has no abbreviation, or the number token carries no digit
    at all. A None here is UNRESOLVED, not a claim of non-amendment -- see the module
    docstring's stated limits.
    """
    tmatch = TENTANG.search(title)
    if not tmatch:
        return None
    window = title[tmatch.end():tmatch.end() + 40]
    amend = AMEND_AT_TITLE_START.match(window)
    if not amend:
        return None
    rest = _closehyphen(title[tmatch.end() + amend.end():])
    tm = legal_title_pattern.search(rest)
    if not tm:
        return None
    type_name = tm.group("type").upper()
    abbrev = legal_type_abbrev.get(type_name)
    if not abbrev:
        return None
    number = normalize_document_number(tm.group("number"))
    if not number:
        return None
    year = tm.group("year")
    return f"{abbrev}_{number}_{year}"


def doc_status(status_counter: dict) -> str:
    """A document's OWN legal_status: the single value every one of its points
    agrees on, or 'mixed' if they disagree. Absence-only documents (every point
    _MISSING) resolve to _MISSING itself, distinct from 'mixed'."""
    present = {k: v for k, v in status_counter.items() if v > 0}
    if len(present) == 1:
        return next(iter(present))
    return "mixed"


def classify_violations(
    resolved_pairs: list[tuple[str, str]],
    by_doc_status: dict[str, str],
) -> dict:
    """Pure function, independent of Qdrant: given resolved (amending, amended) id
    pairs restricted to ids present in `by_doc_status`, split into STRICT and WEAK
    violations. Kept pure and separate from the scroll so it is directly unit-testable
    with synthetic guilt/innocence fixtures (test_legal_status_field_integrity_contract.py)."""
    strict, weak = [], []
    for amending, amended in resolved_pairs:
        if amending not in by_doc_status or amended not in by_doc_status:
            continue
        a_status = by_doc_status[amending]
        t_status = by_doc_status[amended]
        if t_status != "dicabut":
            continue
        weak.append({"amending": amending, "amended": amended,
                     "amending_status": a_status, "amended_status": t_status})
        if a_status == "berlaku":
            strict.append({"amending": amending, "amended": amended,
                           "amending_status": a_status, "amended_status": t_status})
    return {"strict": strict, "weak": weak}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--collection", default="legal_unified_hybrid_hybrid")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args(argv)

    root = repo_root()
    load_env(root)
    sys.path.insert(0, str(root / "apps" / "backend-rag"))
    from backend.core.legal.constants import LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV
    from backend.core.legal.metadata_extractor import normalize_document_number
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )
    live = {c.name for c in client.get_collections().collections}
    if args.collection not in live:
        result = {
            "verdict": "broken", "reason": "collection_missing",
            "collection": args.collection, "exit_code": 3,
        }
        print(json.dumps(result)) if args.json_mode else print(
            f"BROKEN — {args.collection!r} does not exist. Live collections: {sorted(live)}"
        )
        return 3

    by_doc_status: dict[str, dict[str, int]] = {}
    by_doc_titles: dict[str, set[str]] = {}
    total_points = 0
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=args.collection, offset=offset, limit=1000,
            with_payload=True, with_vectors=False,
        )
        for point in points:
            total_points += 1
            payload = point.payload or {}
            doc_id = extract_document_id(payload)
            status = extract_legal_status(payload)
            by_doc_status.setdefault(doc_id, {}).setdefault(status, 0)
            by_doc_status[doc_id][status] += 1
            title = extract_title(payload.get("text", ""))
            if title:
                by_doc_titles.setdefault(doc_id, set()).add(title)
        if offset is None:
            break

    resolved_status = {doc_id: doc_status(counts) for doc_id, counts in by_doc_status.items()}

    resolved_pairs: list[tuple[str, str]] = []
    unresolved_own_amendment = []
    for doc_id, titles in by_doc_titles.items():
        # A document can amend MORE THAN ONE instrument (distinct chunks / distinct
        # provisions each carrying their own CONTEXT header) -- collect every distinct
        # target resolved from every title, never just the first one found. Iterating
        # a `set` of title strings is hash-order-dependent (PYTHONHASHSEED is randomized
        # per process by default), so "take the first that resolves, then break" silently
        # dropped a genuine second reference on some runs and not others -- caught live
        # on Permen_1_2026, which amends both Permen_81_2024 and an unrelated instrument.
        targets = {
            resolve_amendment_target(
                title, LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV, normalize_document_number
            )
            for title in titles
        }
        targets.discard(None)
        for target in sorted(targets):
            resolved_pairs.append((doc_id, target))
        if not targets and any(
            (m := TENTANG.search(t))
            and AMEND_AT_TITLE_START.match(t[m.end():m.end() + 40])
            for t in titles
        ):
            unresolved_own_amendment.append(doc_id)

    in_corpus = [(a, t) for a, t in resolved_pairs if t in resolved_status]
    not_in_corpus = sorted({t for a, t in resolved_pairs if t not in resolved_status})

    violations = classify_violations(in_corpus, resolved_status)

    broken = len(in_corpus) == 0
    verdict_exit = 3 if broken else (1 if violations["strict"] else 0)

    if args.json_mode:
        result = {
            "collection": args.collection,
            "verdict": VERDICT_BY_EXIT[verdict_exit],
            "exit_code": verdict_exit,
            "total_points": total_points,
            "total_documents": len(by_doc_status),
            "amendment_titles_found": len(by_doc_titles) and sum(
                1 for titles in by_doc_titles.values()
                for t in titles
                if (m := TENTANG.search(t)) and AMEND_AT_TITLE_START.match(t[m.end():m.end() + 40])
            ),
            "resolved_relationships": len(resolved_pairs),
            "resolved_targets_in_corpus": len(in_corpus),
            "resolved_targets_not_in_corpus": not_in_corpus,
            "unresolved_own_amendment_titles": sorted(unresolved_own_amendment),
            "strict_violations": violations["strict"],
            "weak_violations": violations["weak"],
        }
        print(json.dumps(result))
        return verdict_exit

    print(f"probe_amendment_invariant — {args.collection}")
    print(f"  {total_points} points / {len(by_doc_status)} documents scanned")
    print(f"  {len(resolved_pairs)} own-title amendment relationships resolved "
          f"({len(in_corpus)} with the amended instrument present in this corpus, "
          f"{len(not_in_corpus)} pointing outside it, {len(unresolved_own_amendment)} "
          f"found an amendment opening but could not resolve type/number/year)")
    if not_in_corpus:
        print(f"  outside-corpus targets (not a violation — just unmeasurable here): "
              f"{', '.join(not_in_corpus)}")
    if unresolved_own_amendment:
        print(f"  unresolved (OCR noise or unmapped type name): "
              f"{', '.join(sorted(unresolved_own_amendment))}")
    print()
    if broken:
        print("BROKEN — zero amendment relationships resolved into this corpus. Given "
              "the corpus's size that is itself a probe failure (anti-vacuity), not "
              "evidence the corpus is clean.")
        return 3

    print(f"STRICT violations (amender uniformly berlaku, amended uniformly dicabut): "
          f"{len(violations['strict'])}")
    for v in violations["strict"]:
        print(f"    {v['amending']} (berlaku) --amends--> {v['amended']} (dicabut)")
    print(f"WEAK violations (amended uniformly dicabut, any amender status): "
          f"{len(violations['weak'])}")
    for v in violations["weak"]:
        print(f"    {v['amending']} ({v['amending_status']}) --amends--> "
              f"{v['amended']} ({v['amended_status']})")
    print()
    if violations["strict"]:
        print("VIOLATION — the corpus contradicts its own citations. This requires no "
              "domain knowledge to trust: an instrument cannot amend a revoked target "
              "while itself remaining in force.")
        return 1
    print("CLEAN — no strict amendment-invariant violation found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
