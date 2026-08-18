"""Parser for the Visa Oracle doctrine-factory claim ledgers.

E5 increment 1 (claim-compiler + VERIFIED-only lint, see
``research/visa/doctrine-factory/claims/*.md`` and
``research/visa/doctrine-factory/cards/*.md``). This module reads the
markdown claim ledgers produced by the E2a/E2b/E3a research passes and
extracts a machine-checkable ``dict[claim_id, ClaimRecord]`` — the SSOT the
compiler (``backend.scripts.visa_engine.compile_claims``) uses to enforce
the VERIFIED-only lint.

Format observed across every ledger file (``e2a-claim-ledger.md``,
``e2b-batch1-claim-ledger.md``, ``e2b-batch2-claim-ledger.md``,
``e2b-batch2-conflict-report.md``, ``e3a-cf1-resolution.md``), verified by
grep before writing this parser — do not "improve" the regex without
re-grepping, the ledgers are hand-authored prose and drift is real:

    **CL-<ID> — <short name>.** <prose...>
    - Source: ...
    - **State: <TOKEN>[.]** [free text — "as a mechanical/structural
      finding", "(gap, not a negative finding)", etc. — never re-parsed]
    - Backs: `rule.a`, `rule.b` (...).

Only the FIRST ``- **State: ...`` line following a ``**CL-<ID> —`` header
(and preceding the next such header) is authoritative for that claim — a
card or ledger may restate/discuss a claim's state in prose elsewhere
(e.g. D2.md's superseded ``<details>`` block), but this parser only reads
the ledger files it is pointed at, in file order, header-block by
header-block, so restated states never race with the authoritative one
inside a single well-formed ledger.

Known ``State:`` tokens (grepped 2026-08-18 across all four claim-ledger-
shaped files): ``VERIFIED``, ``VERIFIED-WITH-CAVEAT``, ``CONFLICTING``,
``UNVERIFIED``, ``STALE``, ``SUPERSEDED`` (last two not observed live yet
but named in ``source-hierarchy-draft.md``'s five-state vocabulary — kept
here so a future ledger entry using them parses instead of silently
matching nothing).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: The five-state vocabulary (``source-hierarchy-draft.md`` §3.2). Longest
#: alternative first so the regex alternation doesn't stop at the
#: "VERIFIED" prefix of "VERIFIED-WITH-CAVEAT" (mirrors the repo-wide
#: longest-alternative-first regex convention, see Bash tool guidance).
CLAIM_STATES: tuple[str, ...] = (
    "VERIFIED-WITH-CAVEAT",
    "VERIFIED",
    "CONFLICTING",
    "UNVERIFIED",
    "STALE",
    "SUPERSEDED",
)

#: States a rule is permitted to depend on at all (E5 VERIFIED-only lint).
#: CONFLICTING/UNVERIFIED/STALE/SUPERSEDED are hard-blocked by construction
#: — see ``compile_claims.py``'s ``lint_verified_only``.
COMPILABLE_STATES: frozenset[str] = frozenset({"VERIFIED", "VERIFIED-WITH-CAVEAT"})

#: Sentinel for a claim header with no resolvable ``**State: ...**`` line in
#: its block — real, grepped example: ``CL-E30A-03`` in
#: ``e2b-batch1-claim-ledger.md`` is a cross-reference alias ("See
#: CL-E30B-01 above"), not a claim with its own evidentiary state. These are
#: legitimately out of any given compiler slice's scope; hard-failing the
#: WHOLE ledger load on one alias would make the compiler unable to consume
#: a ledger file that has any out-of-scope alias claims in it at all — so
#: they parse as this never-compilable sentinel instead. Any rule that DOES
#: try to depend on one fails the VERIFIED-only lint exactly like a claim
#: with a real bad state would (``UNSTATED not in COMPILABLE_STATES``).
UNSTATED = "UNSTATED"

#: Both real header shapes are covered: bare ``**CL-<id> — <name>.**`` at
#: column 0 (``e2a-claim-ledger.md``, ``e2b-batch1-claim-ledger.md``) AND
#: bullet-prefixed ``- **CL-<id> — <name>.**`` (``e2b-batch2-claim-ledger.md``).
#: ``^`` + ``re.MULTILINE`` + the optional bullet prefix is load-bearing —
#: a kimi-k3 adversarial review (2026-08-18) caught the unanchored version
#: matching an inline bold reference mid-prose (e.g. "as discussed in
#: **CL-D2-01 — the passport claim**...") as a spurious SECOND header for
#: an already-open claim, corrupting its block boundary. Verified the
#: anchored version still matches all 90 real headers across the four
#: loaded ledger files (identical count to the unanchored version) before
#: landing this fix — a real header is always the first thing on its line.
_HEADER_RE = re.compile(
    r"^[ \t]*(?:-[ \t]+)?\*\*(CL-[A-Za-z0-9][A-Za-z0-9-]*)\s*[—-]\s*([^*]*)\*\*",
    re.MULTILINE,
)
#: Same anchoring rationale as ``_HEADER_RE``: a bare ``**State: ...**``
#: match anywhere in a block's prose (e.g. "Previously marked
#: **State: CONFLICTING** before resolution.") could otherwise out-race the
#: real ``- **State: ...**`` bullet the ledger format actually uses.
#: Verified against all four loaded ledger files: identical match count to
#: the unanchored version.
_STATE_RE = re.compile(
    r"^[ \t]*-[ \t]*\*\*State:\s*(" + "|".join(CLAIM_STATES) + r")\b[^*]*\*\*",
    re.MULTILINE,
)
#: ``Backs:`` lines routinely wrap onto an indented continuation line in
#: these ledgers (grepped example: ``CL-D12-02`` lists 5 rule ids across two
#: physical lines) — capture up to the next unindented ``- `` bullet, a
#: blank line, or end of block, not just to end-of-line.
_BACKS_RE = re.compile(r"^-\s*Backs:\s*(.*?)(?=\n-\s|\n\n|\Z)", re.MULTILINE | re.DOTALL)
_RULE_ID_RE = re.compile(r"`([a-z][a-z0-9_.-]*)`")

#: The full ``- **State: ...`` bullet, wrapping-tolerant (same lookahead
#: shape as ``_BACKS_RE``) — captured separately from ``_STATE_RE`` so a
#: kimi-k3 adversarial review (2026-08-18) live-data finding can be
#: detected: a PRODUCT-CONDITIONAL state line. Real example,
#: ``CL-D-FUNDS`` in ``e2a-claim-ledger.md``:
#:
#:     - **State: VERIFIED** for D1/D12 (numeric, primary-adjacent
#:       sourcing); **VERIFIED-WITH-CAVEAT** for D2 (no hardcoded
#:       national figure ...).
#:
#: ``_STATE_RE`` alone picks the FIRST token match (``VERIFIED``) and
#: applies it claim-wide — a D2 rule citing this claim would then compile
#: with NO caveat requirement, silently bypassing the caveat-propagation
#: guarantee lint 1 exists to enforce. Verified this is the ONLY claim
#: across all four loaded ledger files with this shape (grepped
#: 2026-08-18: `grep -n "for D1/D12" claims/*.md` and a broader
#: multi-state-per-line sweep both return exactly one hit) — a raised
#: `ClaimLedgerError` here would therefore deadlock the D1/D12 rules that
#: legitimately need the plain-VERIFIED resolution, so per-product state
#: parsing (not a hard fail) is the correct scope for this one real shape.
_STATE_BULLET_SPAN_RE = re.compile(
    r"^[ \t]*-[ \t]*\*\*State:.*?(?=\n[ \t]*-[ \t]|\n\n|\Z)",
    re.MULTILINE | re.DOTALL,
)
#: Matches every ``**TOKEN** for PRODUCTLIST`` clause inside a state
#: bullet — ``PRODUCTLIST`` is a ``/``-joined list like ``D1/D12``.
_PRODUCT_STATE_CLAUSE_RE = re.compile(r"\*\*(" + "|".join(CLAIM_STATES) + r")\*\*\s+for\s+([A-Za-z0-9/]+)")


def _parse_product_conditional_states(bullet_text: str) -> dict[str, str] | None:
    """Return ``{product_code: state}`` if the bullet expresses 2+ distinct
    ``**TOKEN** for PRODUCTS`` clauses (a product-conditional state line),
    else ``None`` for the ordinary single-state case."""

    clauses = _PRODUCT_STATE_CLAUSE_RE.findall(bullet_text)
    if len(clauses) < 2:
        return None
    product_states: dict[str, str] = {}
    for token, product_list in clauses:
        for product in product_list.split("/"):
            product = product.strip()
            if product:
                product_states[product] = token
    return product_states or None


class ClaimLedgerError(ValueError):
    """A claim ledger file could not be parsed into records."""


@dataclass(frozen=True)
class ClaimRecord:
    """One claim as recorded in a doctrine-factory ledger.

    ``source_file``/``header`` are provenance for compiler error messages
    (so a lint failure can point a human straight at the ledger line that
    caused it, not just the bare claim_id).
    """

    claim_id: str
    state: str
    header: str
    backs: tuple[str, ...]
    source_file: str
    #: Non-``None`` only for the rare product-conditional shape (see
    #: ``_STATE_BULLET_SPAN_RE``) — maps a product code (e.g. ``"D2"``) to
    #: its OWN state, distinct from the claim-wide ``state`` above (which
    #: for a product-conditional claim is just the first token found, kept
    #: for backward-compatible display/UNSTATED-detection only — callers
    #: that care about a specific product must consult this map, not
    #: ``state``, when it is populated).
    product_states: dict[str, str] | None = None

    @property
    def compilable(self) -> bool:
        return self.state in COMPILABLE_STATES

    def state_for_product(self, product_code: str) -> str:
        """The state to apply for ``product_code`` — the per-product entry
        if this is a product-conditional claim and the product is named,
        else the claim-wide ``state``."""

        if self.product_states is not None:
            return self.product_states.get(product_code, self.state)
        return self.state

    def compilable_for_product(self, product_code: str) -> bool:
        return self.state_for_product(product_code) in COMPILABLE_STATES


def parse_claim_ledger_text(text: str, *, source_name: str) -> dict[str, ClaimRecord]:
    """Parse one ledger file's already-read text into ``{claim_id: ClaimRecord}``.

    Splits the document into header-block chunks at every ``**CL-<id> —``
    occurrence, then looks for the first ``**State: ...**`` line inside that
    chunk (i.e. before the next header). A header with no resolvable state
    line inside its block raises ``ClaimLedgerError`` — a claim with a
    header but no state is exactly the kind of drift this parser exists to
    catch, not silently skip (a rule referencing that claim_id would
    otherwise fail with a confusing "unknown claim_id" instead of the real
    "malformed ledger entry").
    """

    headers = list(_HEADER_RE.finditer(text))
    records: dict[str, ClaimRecord] = {}
    for i, m in enumerate(headers):
        claim_id = m.group(1)
        header = m.group(2).strip()
        block_start = m.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[block_start:block_end]

        state_m = _STATE_RE.search(block)
        state = state_m.group(1) if state_m is not None else UNSTATED

        product_states: dict[str, str] | None = None
        bullet_m = _STATE_BULLET_SPAN_RE.search(block)
        if bullet_m is not None:
            product_states = _parse_product_conditional_states(bullet_m.group(0))

        backs: tuple[str, ...] = ()
        backs_m = _BACKS_RE.search(block)
        if backs_m is not None:
            backs = tuple(_RULE_ID_RE.findall(backs_m.group(1)))

        if claim_id in records:
            # Same claim_id re-declared — WITHIN this file or across files —
            # with a DIFFERENT state is a real ledger inconsistency the
            # compiler must not silently pick a side on. This covers both
            # legitimate cross-file restatements (a resolution fast-follow
            # file that reprints an unchanged claim for context) AND the
            # sharper in-file case a kimi-k3 adversarial review caught live
            # (2026-08-18): `_HEADER_RE` is not anchored to the start of a
            # line, so an inline bold restatement mid-prose that happens to
            # match the exact `**CL-<id> — <name>.**` shape (e.g. a card's
            # `<details>` block quoting a claim header for context) would
            # otherwise open a SECOND block for the same claim_id and
            # silently overwrite the authoritative record with whatever
            # that second block's own (possibly UNSTATED) state resolves
            # to — no error, wrong answer. Never observed live in the four
            # ledger files this module currently loads (verified: 90
            # headers, 90 unique claim_ids, zero within-file duplicates),
            # but the docstring's claim of header-block immunity only held
            # by accident of what these specific files happen to contain,
            # not by construction — so duplicate detection is now
            # unconditional, not source_file-gated.
            prior = records[claim_id]
            if prior.state != state:
                raise ClaimLedgerError(
                    f"claim {claim_id!r} is declared with state "
                    f"{prior.state!r} ({prior.source_file!r}) and state "
                    f"{state!r} ({source_name!r}) — ledger inconsistency, "
                    "not resolvable by the compiler. If this is an in-file "
                    "restatement (a details block quoting a claim header), "
                    "the restatement must not use the literal "
                    "'**CL-<id> — <name>.**' bold-header shape."
                )
            # Identical restatement (same claim_id, same state) — keep the
            # first block's record, harmless.
            continue

        records[claim_id] = ClaimRecord(
            claim_id=claim_id,
            state=state,
            header=header,
            backs=backs,
            source_file=source_name,
            product_states=product_states,
        )

    return records


def load_claim_ledgers(paths: list[Path]) -> dict[str, ClaimRecord]:
    """Read and merge every claim ledger file in ``paths``, in order.

    Raises ``ClaimLedgerError`` on any inter-file state inconsistency (see
    ``parse_claim_ledger_text``) or ``OSError`` if a path is unreadable.
    """

    merged: dict[str, ClaimRecord] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        records = parse_claim_ledger_text(text, source_name=str(path))
        for claim_id, record in records.items():
            if claim_id in merged and merged[claim_id].state != record.state:
                raise ClaimLedgerError(
                    f"claim {claim_id!r} is declared with state "
                    f"{merged[claim_id].state!r} in {merged[claim_id].source_file!r} "
                    f"and state {record.state!r} in {record.source_file!r} — "
                    "ledger inconsistency, not resolvable by the compiler"
                )
            merged.setdefault(claim_id, record)
    return merged
