"""WR2 claims — the claim contract the WR2 brief never had.

WHY THIS EXISTS
---------------
WR3's companion mode inherits `primary_claim_ids` from the WR2 brief and
DELIBERATELY does not re-verify them (Law 2: NB source ids never re-enter the
room; the WR2 fact-checker already vetted them). That inheritance is only sound
if a claim id points at something WR2 actually verified.

Measured on disk 2026-07-26, across all 23 briefs in
`apps/war-room/output/carousel/*/brief.json`:

  * `primary_claim_ids` appears in **0** of them. The field is not empty — the
    CONCEPT does not exist in WR2.
  * The briefs carry ~90 distinct top-level keys, most appearing exactly once:
    the brief is LLM-authored free-form JSON with no schema.
  * `key_facts` is `list[str]` in 18 briefs and `list[dict]` in 3. The three
    structured ones are dated 2026-05-19, 2026-05-19 and 2026-07-15, while the
    two most recent briefs (07-20, 07-21) are back to plain strings — so the
    structure is **LLM variance, not a newer pipeline** that time would fix.

That rules out the tempting shortcut. Deriving ids from the free-text strings
would mint handles onto assertions whose grounding is a prose convention
followed intermittently: the companion would LOOK grounded, the dispatcher would
proceed, and Veo would spend real credits on it. A proxy that lies, with a bill.

So: a claim exists only where the brief carries a structured record with a
source AND a status drawn from a closed vocabulary. Everything else is not a
claim, is counted, and is reported — an honest zero, which makes the companion
skip rather than pretend.

WHY THE STATUS VOCABULARY IS CLOSED
-----------------------------------
`source_status` is free prose today. Observed values include `verified_web`,
`nb_verified`, `verified_web + nb_corroborated` — and this one:

    "verified_web (FAQ example) / operator_brief (Rp10m illustrative figure,
     consistent with the confirmed 0.5% rate)"

A `status.startswith("verified")` test accepts that string and promotes an
**illustrative** rupiah figure to a verified claim, which WR3 would then state
as fact in a video. That is cicatrix #3 (guard over-match) in its purest form:
matching the FORM of the status instead of the ENTITY it denotes. So the status
is parsed as tokens against a closed set, never searched as a substring, and
anything that does not parse cleanly is refused.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# Tokens that assert first-hand verification. A claim needs at least one.
PRIMARY_VERIFIED_TOKENS = frozenset({"verified_web", "nb_verified"})
# Tokens that only CORROBORATE — allowed alongside, never sufficient alone.
CORROBORATING_TOKENS = frozenset({"nb_corroborated", "web_corroborated"})
ALLOWED_STATUS_TOKENS = PRIMARY_VERIFIED_TOKENS | CORROBORATING_TOKENS

# The brief fields that can hold claims, and the claim kind each produces.
CLAIM_FIELDS: dict[str, str] = {"key_facts": "fact", "key_numbers": "num"}
# Per-field aliases for the claim text, in priority order.
_TEXT_KEYS = ("fact", "number", "text", "claim", "value", "statement")

_WS = re.compile(r"\s+")


class RejectReason:
    """Why an entry did not become a claim. Counted, never silently dropped."""

    UNSTRUCTURED = "unstructured"  # a bare string, not a record
    NO_TEXT = "no_text"
    NO_SOURCE = "no_source"
    NO_STATUS = "no_status"
    STATUS_NOT_IN_VOCABULARY = "status_not_in_vocabulary"
    STATUS_ONLY_CORROBORATING = "status_only_corroborating"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    kind: str
    text: str
    source: str
    status_tokens: tuple[str, ...]


@dataclass
class ClaimExtraction:
    claims: list[Claim] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)

    @property
    def claim_ids(self) -> list[str]:
        return [c.claim_id for c in self.claims]

    def reject_summary(self) -> str:
        if not self.rejected:
            return "none"
        return ", ".join(f"{k}={v}" for k, v in sorted(self.rejected.items()))


def _norm(value: Any) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def parse_status_tokens(raw: Any) -> list[str] | None:
    """Parse `source_status` into tokens, or None if it is not a clean status.

    Tokens are split on `+` and `/` (both appear as composers in the observed
    data) and must EACH be in the allowed set. Prose that merely contains an
    allowed word — e.g. `verified_web (FAQ example) / operator_brief (...)` —
    yields a token that is not in the set, so the whole status is refused.
    That refusal is the point: the entity, not the form.
    """
    text = _norm(raw)
    if not text:
        return None
    tokens = [t.strip() for t in re.split(r"[+/]", text)]
    if not all(tokens):
        return None
    if any(t not in ALLOWED_STATUS_TOKENS for t in tokens):
        return None
    return tokens


def make_claim_id(kind: str, text: str, source: str) -> str:
    """Deterministic id: same claim, same id, across reruns and machines.

    Stability matters because WR3 artifacts (script bindings, critic Lane 4
    cross-checks) reference these ids; a rerun that renumbers them would orphan
    every downstream reference. Whitespace is normalised so reflowing a brief
    does not mint a new id; nothing else is normalised, because a change to the
    wording or the source IS a different claim.
    """
    digest = hashlib.sha256(f"{_norm(text)}|{_norm(source)}".encode()).hexdigest()
    return f"{kind}-{digest[:12]}"


def extract_claims(brief: dict[str, Any]) -> ClaimExtraction:
    """Extract verified claims from a WR2 brief. Never invents one."""
    out = ClaimExtraction()
    seen: set[str] = set()

    def reject(reason: str) -> None:
        out.rejected[reason] = out.rejected.get(reason, 0) + 1

    for field_name, kind in CLAIM_FIELDS.items():
        entries = brief.get(field_name)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                reject(RejectReason.UNSTRUCTURED)
                continue
            text = next((_norm(entry[k]) for k in _TEXT_KEYS if entry.get(k)), "")
            if not text:
                reject(RejectReason.NO_TEXT)
                continue
            source = _norm(entry.get("source") or entry.get("source_verbatim"))
            if not source:
                reject(RejectReason.NO_SOURCE)
                continue
            raw_status = entry.get("source_status")
            if not _norm(raw_status):
                reject(RejectReason.NO_STATUS)
                continue
            tokens = parse_status_tokens(raw_status)
            if tokens is None:
                reject(RejectReason.STATUS_NOT_IN_VOCABULARY)
                continue
            if not any(t in PRIMARY_VERIFIED_TOKENS for t in tokens):
                reject(RejectReason.STATUS_ONLY_CORROBORATING)
                continue
            # An author-supplied id wins over the derived hash — but only HERE,
            # after the record has proved it has a source and a verified status.
            # That is the whole distinction: an id on a backed record is a
            # readable handle; an id on a bare assertion is a phantom.
            declared_id = _norm(entry.get("claim_id") or entry.get("id"))
            claim_id = (
                declared_id
                if declared_id and " " not in declared_id
                else make_claim_id(kind, text, source)
            )
            if claim_id in seen:
                continue
            seen.add(claim_id)
            out.claims.append(
                Claim(
                    claim_id=claim_id,
                    kind=kind,
                    text=text,
                    source=source,
                    status_tokens=tuple(tokens),
                )
            )
    return out


def resolve_primary_claim_ids(brief: dict[str, Any]) -> tuple[list[str], ClaimExtraction]:
    """The ids WR3 should inherit, plus the extraction that justifies them.

    A brief MAY narrow the set by declaring `primary_claim_ids` explicitly, but
    it may never invent one: an explicit list is honoured only when every id in
    it is also a derived id. An authored id traces to nothing, and WR3 does not
    re-verify what it inherits — so "the brief may narrow, never invent" is the
    only rule under which honouring it stays safe.
    """
    extraction = extract_claims(brief)
    derived = extraction.claim_ids
    declared = brief.get("primary_claim_ids") or brief.get("claim_ids")
    if isinstance(declared, list) and declared:
        wanted = [str(x) for x in declared]
        if set(wanted).issubset(set(derived)):
            return [cid for cid in derived if cid in set(wanted)], extraction
    return derived, extraction


def format_extraction(extraction: ClaimExtraction) -> str:
    """One log line an operator can act on — count AND why the rest failed."""
    return (
        f"{len(extraction.claims)} verified claim(s); "
        f"rejected: {extraction.reject_summary()}"
    )


def iter_claim_texts(claims: Iterable[Claim]) -> list[str]:
    return [c.text for c in claims]


def scan_corpus(root: Any) -> int:
    """Report how much of a carousel output tree satisfies the claim contract.

    This is an operator tool, not a test: the tree it reads is not tracked in
    git, so a test walking it would skip in CI and be coverage in name only.
    The number it prints is the one the WR2→WR3 ignition is waiting on — the
    day it stops being "1/23", the gap has closed.
    """
    from pathlib import Path

    # Skip dot-directories. `Path.glob("*/...")` matches them, the shell's `*`
    # does not — and the tree holds stale backups like
    # `.bali-pma-rental-crackdown.bak-pre-revise-20260714`, which would inflate
    # the denominator forever and, worse, could one day report progress that a
    # dead snapshot supplied. Two globs disagreeing means the SELECTOR is the
    # defect, not the count.
    briefs = sorted(
        p for p in Path(root).glob("*/brief.json") if not p.parent.name.startswith(".")
    )
    if not briefs:
        print(f"wr2-claims: no brief.json under {root}")
        return 1
    with_claims: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for path in briefs:
        try:
            data = __import__("json").loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # a broken brief is a finding, not a crash
            print(f"  UNREADABLE {path.parent.name}: {exc}")
            continue
        extraction = extract_claims(data)
        if extraction.claims:
            with_claims[path.parent.name] = len(extraction.claims)
        for reason, count in extraction.rejected.items():
            reasons[reason] = reasons.get(reason, 0) + count
    print(
        f"wr2-claims: {len(with_claims)}/{len(briefs)} brief(s) carry verified claims "
        f"({sum(with_claims.values())} claim(s) total)"
    )
    for slug, count in sorted(with_claims.items()):
        print(f"  {count:>3}  {slug}")
    print("  rejected across the corpus: " + (
        ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())) or "none"
    ))
    return 0


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="WR2 claim contract")
    parser.add_argument(
        "--scan",
        metavar="DIR",
        default="apps/war-room/output/carousel",
        help="carousel output root to report on (default: %(default)s)",
    )
    args = parser.parse_args()
    return scan_corpus(args.scan)


if __name__ == "__main__":
    raise SystemExit(_cli())
