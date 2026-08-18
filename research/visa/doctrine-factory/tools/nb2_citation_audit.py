#!/usr/bin/env python3
"""QW-1 citation validator — mechanical, generator != grader.

This tool is deliberately dumb: it does not judge legal merit, doctrine correctness, or
whether an answer is "good". It only checks whether every pointer an NB-2 answer makes to a
source RESOLVES against the frozen 131-source snapshot (`nb2_query.py snapshot-sources`).
That separation is the point — the interrogator (nb2_query.py) and the auditor
(this file) are different code paths run by different invocations, so a hallucinated
citation cannot be self-graded away.

SCOPE (declared, not implied — cicatrix W109: an exemption/assertion a tool makes about its
own coverage must be explicit): this auditor resolves BRACKET pointers of two forms —
`[Source N]` and bare `[N]` — against the structured `citations` (citation_number ->
source_id) or `references` (list of {citation_number, source_id, ...}) fields the nlm payload
already carries, then checks that source_id is a member of the frozen snapshot. It ALSO
validates every source_id the STRUCTURED payload itself asserts (citations values,
references[].source_id, sources_used entries) against the snapshot, regardless of whether a
prose pointer ever referenced it — a fabricated structured citation the model never quoted in
prose is still a hallucinated claim about what NB-2 said (GLM grader finding P1, 2026-08-15:
the first cut of this tool only membership-checked pointers actually extracted from prose,
so a fabricated `citations["2"]` entry that the answer text never referenced in a `[Source 2]`
or `[2]` bracket slipped through as VERIFIED). It also detects verbatim SOURCE-TITLE mentions
in the prose as a secondary evidence signal. It does NOT run free-text entity extraction to
invent a title the answer paraphrased — that would require an LLM judge, which would make the
grader the same class of thing as the generator. A title match is corroborating evidence,
never the sole basis for a NOT_COMPILABLE verdict.

BARE-BRACKET FIX (GLM grader finding P0, 2026-08-15): the first cut of this tool only matched
`[Source N]`. Measured live against the actual B0 canary answers this session, NB-2 emits
bare `[N]` almost exclusively (27 in VO-NB2-001, 43 in VO-NB2-002, 4 in VO-NB2-005; ZERO
`[Source N]` anywhere in the batch) — so the first cut was checking a citation FORM the model
essentially never uses. Both forms are now extracted and resolved through the same
citations/references map. Declared over-match risk (family #3 discipline): a bare `[N]` COULD
in principle appear in non-citation prose (a footnote marker, a table row label, an ordered
list). This tool does not attempt to disambiguate context — it resolves every bare `[N]` it
finds against the citations map exactly like `[Source N]`. This is judged acceptable because
(a) empirically every bare-bracket count observed live tracks the `references` count for that
answer (27 vs 45 refs, 43 vs 65 refs, 4 vs 8 refs — consistent with genuine citation markers,
not noise), and (b) a bare `[N]` that legitimately resolves against the map costs nothing
(VERIFIED, not flagged) — the only failure mode is a FALSE hallucination flag on a bare number
that happens to coincide with an unrelated citation index, which is testable and, if it ever
recurs empirically, should be narrowed with more context rather than guarded against
speculatively now.

Verdicts (per-answer):
  - SKIPPED_TRANSPORT_ERROR — the response-log record itself was not status=="OK" (isolation
    mismatch / CLI error / unparseable JSON): nothing to audit, the transport failed first.
  - NOT_COMPILABLE — at least one extracted prose pointer OR at least one source_id the
    structured payload itself asserts (citations/references/sources_used) does not resolve
    against the frozen snapshot (hallucinated citation number, or a source_id — pointed-to or
    merely asserted — the snapshot does not contain).
  - PROSE_ONLY — no structured citations/references/sources_used at all, but every prose
    pointer found DOES resolve. Usable, flagged as weaker grounding.
  - VERIFIED — structured citations/references/sources_used are present, every extracted
    prose pointer resolves, AND every source_id the structured payload itself asserts also
    resolves.
  - UNSUPPORTED — no structured citations and no resolvable prose pointer found: the claim
    carries no traceable grounding at all.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

_SOURCE_BRACKET_RE = re.compile(r"\[\s*Source\s+(\d+)\s*\]", re.IGNORECASE)
_BARE_BRACKET_RE = re.compile(r"\[\s*(\d+)\s*\]")

VERDICT_NOT_COMPILABLE = "NOT_COMPILABLE"
VERDICT_PROSE_ONLY = "PROSE_ONLY"
VERDICT_VERIFIED = "VERIFIED"
VERDICT_UNSUPPORTED = "UNSUPPORTED"
VERDICT_SKIPPED = "SKIPPED_TRANSPORT_ERROR"


def load_source_index(snapshot_path: Path) -> dict[str, dict[str, Any]]:
    """snapshot file -> {source_id: {"title": ..., "type": ..., ...}}."""
    data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    sources = data["sources"] if isinstance(data, dict) else data
    index: dict[str, dict[str, Any]] = {}
    for entry in sources:
        sid = entry.get("id") or entry.get("source_id")
        if sid is None:
            continue
        index[sid] = entry
    return index


def load_response_log(log_path: Path) -> list[dict[str, Any]]:
    records = []
    with Path(log_path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def extract_bracket_pointers(answer: str) -> list[dict[str, Any]]:
    """Extract both `[Source N]` and bare `[N]` pointers, in order of appearance.

    Returns a list of {"n": int, "form": str} — "form" is the exact bracket text so audit
    output can show the reader what the model actually wrote, not a normalized guess.
    """
    pointers: list[dict[str, Any]] = []
    for m in _SOURCE_BRACKET_RE.finditer(answer or ""):
        pointers.append({"n": int(m.group(1)), "form": f"[Source {m.group(1)}]"})
    for m in _BARE_BRACKET_RE.finditer(answer or ""):
        pointers.append({"n": int(m.group(1)), "form": f"[{m.group(1)}]"})
    return pointers


def extract_title_mentions(answer: str, source_index: dict[str, dict[str, Any]]) -> list[str]:
    """Verbatim (casefolded) mentions of a KNOWN snapshot title inside the prose.

    Secondary evidence only (see module docstring SCOPE) — titles under 8 chars are skipped
    to avoid noise-matching short generic titles.
    """
    if not answer:
        return []
    haystack = answer.casefold()
    hits = []
    seen_titles: set[str] = set()
    for entry in source_index.values():
        title = entry.get("title")
        if not title or len(title) < 8 or title in seen_titles:
            continue
        if title.casefold() in haystack:
            hits.append(title)
            seen_titles.add(title)
    return hits


def _lookup_citation_source_id(
    n: int, citations: Any, references: Iterable[dict[str, Any]] | None
) -> str | None:
    if isinstance(citations, dict):
        for key in (n, str(n)):
            if key in citations:
                return citations[key]
    for ref in references or []:
        if isinstance(ref, dict) and ref.get("citation_number") == n:
            return ref.get("source_id")
    return None


def _all_structured_source_ids(
    citations: Any, references: Any, sources_used: Any
) -> list[tuple[str, Any]]:
    """Every (channel, source_id) pair the STRUCTURED payload itself asserts exists —
    independent of whether any prose pointer ever referenced it. A fabricated entry here is a
    hallucinated claim about NB-2's own citation data, not just an unresolved prose pointer.
    """
    pairs: list[tuple[str, Any]] = []
    if isinstance(citations, dict):
        for sid in citations.values():
            pairs.append(("citations", sid))
    for ref in references or []:
        if isinstance(ref, dict) and "source_id" in ref:
            pairs.append(("references", ref.get("source_id")))
    for sid in sources_used or []:
        pairs.append(("sources_used", sid))
    return pairs


def audit_record(record: dict[str, Any], source_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "query_id": record.get("query_id"),
        "conversation_id_sent": record.get("conversation_id_sent"),
    }

    if record.get("status") != "OK":
        result["verdict"] = VERDICT_SKIPPED
        result["reason"] = record.get("anomaly") or record.get("status") or "no status field"
        return result

    answer = record.get("answer") or ""
    citations = record.get("citations")
    references = record.get("references")
    sources_used = record.get("sources_used")
    structured_present = bool(citations) or bool(references) or bool(sources_used)

    # --- prose pointers: [Source N] and bare [N], resolved through citations/references ---
    bracket_pointers = extract_bracket_pointers(answer)
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for ptr in bracket_pointers:
        n = ptr["n"]
        form = ptr["form"]
        source_id = _lookup_citation_source_id(n, citations, references)
        if source_id is None:
            unresolved.append(
                {
                    "pointer": form,
                    "reason": "no citations/references entry maps this citation number to a source_id",
                }
            )
            continue
        if source_id not in source_index:
            unresolved.append(
                {
                    "pointer": form,
                    "source_id": source_id,
                    "reason": "source_id not present in the frozen snapshot",
                }
            )
            continue
        resolved.append({"pointer": form, "source_id": source_id, "title": source_index[source_id].get("title")})

    # --- structured payload's OWN asserted source_ids, membership-checked independently of ---
    # --- whether prose ever pointed at them (fix for GLM grader finding P1) ---
    unresolved_structured: list[dict[str, Any]] = []
    for channel, sid in _all_structured_source_ids(citations, references, sources_used):
        if sid is None:
            unresolved_structured.append(
                {"channel": channel, "source_id": sid, "reason": "null source_id in structured payload"}
            )
        elif sid not in source_index:
            unresolved_structured.append(
                {"channel": channel, "source_id": sid, "reason": "source_id not present in the frozen snapshot"}
            )

    title_mentions = extract_title_mentions(answer, source_index)

    result["bracket_pointers_found"] = len(bracket_pointers)
    result["resolved_pointers"] = resolved
    result["unresolved_pointers"] = unresolved
    result["unresolved_structured_source_ids"] = unresolved_structured
    result["title_mentions"] = title_mentions
    result["structured_citations_present"] = structured_present

    if unresolved or unresolved_structured:
        result["verdict"] = VERDICT_NOT_COMPILABLE
        reasons = []
        if unresolved:
            reasons.append(f"{len(unresolved)} prose pointer(s) do not resolve against the frozen source snapshot")
        if unresolved_structured:
            reasons.append(
                f"{len(unresolved_structured)} structured source_id(s) (citations/references/sources_used) "
                "do not resolve against the frozen source snapshot"
            )
        result["reason"] = "; ".join(reasons)
    elif not structured_present and (bracket_pointers or title_mentions):
        result["verdict"] = VERDICT_PROSE_ONLY
        result["reason"] = (
            "structured citations/references/sources_used are empty; grounding relies on "
            "resolvable prose pointers/title mentions only"
        )
    elif structured_present:
        result["verdict"] = VERDICT_VERIFIED
        result["reason"] = (
            "structured citations present, every extracted prose pointer resolves, and every "
            "structured source_id the payload asserts also resolves"
        )
    else:
        result["verdict"] = VERDICT_UNSUPPORTED
        result["reason"] = "no structured citations and no resolvable prose pointer/title mention found"

    return result


def audit_log(log_path: Path, snapshot_path: Path) -> list[dict[str, Any]]:
    source_index = load_source_index(snapshot_path)
    records = load_response_log(log_path)
    return [audit_record(r, source_index) for r in records]


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True, help="response-log.jsonl to audit")
    p.add_argument("--snapshot", type=Path, required=True, help="frozen source snapshot JSON")
    p.add_argument("--out", type=Path, default=None, help="write verdicts JSON here (default: stdout)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    verdicts = audit_log(args.log, args.snapshot)
    payload = json.dumps(verdicts, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(payload)
    not_compilable = sum(1 for v in verdicts if v["verdict"] == VERDICT_NOT_COMPILABLE)
    return 1 if not_compilable else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
