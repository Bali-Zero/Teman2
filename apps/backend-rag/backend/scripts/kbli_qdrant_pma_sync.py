"""
kbli_qdrant_pma_sync.py — sync a named LAYER of the KBLI Qdrant payload from the
canonical dataset. `--layer pma` (default) owns the complete PMA evidence tuple
(`pma_status`, `pma_max_asing`, verification status, official basis, vintage);
`--layer bali` owns `bali_status` / `bali_blocked` /
`bali_needs_review` / `bali_reason` / `has_bali_l4`.

WHY THE BALI LAYER LIVES HERE AND NOT IN ITS OWN TOOL (2026-08-03): there WAS a
second tool, `apps/backend-rag/scripts/patch_qdrant_bali_l4.py`, and it is
deleted in the same commit that adds this layer. It did not read the canonical
verdict — it RE-DERIVED one from `l4_bali.verdict`, a parallel field that has
drifted away from `l4_bali.status`, the field every rendering surface actually
reads. Measured on the canonical the day it was removed:

  * 237 records carry NO `l4_bali.verdict` at all, and **118 of those are
    currently blocked**. The tool's `verdicts.get(kode, "OPEN")` default would
    have written `OK_or_HIGHER_RISK` + "not blocked by moratorium" onto all
    118 — publishing 118 blocked activities as registrable, on the store
    `inspect_kbli` reads FIRST.
  * 15 more carry a `verdict` that disagrees with their `status`.

Two tools deciding the same client-facing fact will disagree exactly when it
matters (W105). So the rule is one tool, and the tool COPIES the canonical
verdict — it never recomputes one. `l4_bali.status` is what the website, the
LLM corpus and the macOS app render; anything else is a second opinion nobody
asked for.

WHY THIS EXISTS, AND WHY THE KG-SIDE CURE WAS NOT ENOUGH (2026-08-02, found
during the prove-live of the Perpres 49/2021 Lampiran III cure, #3515):
`inspect_kbli` resolves the PMA verdict with Qdrant FIRST and the KG node only
as a fallback (`backend/app/routers/kbli_notebook.py`):

    pma_status = (
        (_payload_value(qdrant_payload, "pma_status") if qdrant_payload else None)
        or props.get("pma_status")      # <- the kg_nodes property
        ...
    )

So `kg_kbli_resync.py` — whose own docstring exists *because* `inspect_kbli`
served a stale `pma_status` — cannot move that field on this endpoint while
Qdrant carries any value at all. Measured live: after the cure, `kg_nodes` said
TERBATAS on all twenty codes and `inspect_kbli 51101` still answered TERBUKA,
because the Qdrant payload still read `TERBUKA / 100`. A cure that stops at the
KG is a cure the channel never sees.

WHAT IT WRITES: exactly the keys of the SELECTED layer, via `set_payload` — a
payload MERGE that touches nothing else. Never `overwrite_payload`, never
`delete_payload`, never a vector. **The embedding model is FROZEN**
(`text-embedding-3-small`, 93k+ vectors — CLAUDE.md §9); a re-index to change a
few scalars would put that invariant at risk for no reason.

The layers are deliberately separate runs. National ownership (`pma_*`) and the
Bali provincial verdict (`bali_*`) answer different questions from different
instruments, and the one confusion this lane keeps paying for is treating them
as one answer. A run that could move both at once would make "did this cure
touch the national fields?" unanswerable from the command line.

SCOPE DISCIPLINE (mirrors `kbli_qdrant_risk_clear.py` and
`kg_kbli_license_fix.py`): `--codes` is MANDATORY. No code is ever
auto-discovered or swept.

`--collection` IS ALSO MANDATORY, and that is deliberate. The physical name is
`kbli_2025_final_hybrid`; the logical name `kbli_2025_final` **does not exist**
as a collection, and `kbli_2025_final_oss` (10,825 points) answers to none of
the code keys the router tries. Writing a default here would freeze a measure of
the world into a constant — the exact shape that took production down for 27h in
W106 — so the caller states it and the guard below checks it.

THE WRONG-COLLECTION GUARD: if not one of the requested codes matches a single
point, the run exits 2 instead of reporting a tidy "0 updated". A probe pointed
at a collection that does not carry `kode_kbli` returns a clean, believable zero
for every code you ask about, including codes you know exist — that is how this
defect was nearly mis-diagnosed on the day this script was written.

USAGE (dry-run is the default; nothing is written without --apply):
    cd /app && python backend/scripts/kbli_qdrant_pma_sync.py \\
        --collection kbli_2025_final_hybrid --codes 51101,25200

    cd /app && python backend/scripts/kbli_qdrant_pma_sync.py \\
        --collection kbli_2025_final_hybrid --codes 51101,25200 --apply

    cd /app && python backend/scripts/kbli_qdrant_pma_sync.py --layer bali \\
        --collection kbli_2025_final_hybrid --codes 86995,96220 --apply

The script bootstraps the application root before importing the shared
disclosure gate.  Direct Fly execution therefore keeps working without a
``PYTHONPATH`` override, while every writer uses the exact same PMA/Bali
allowlist and boolean validation.

AFTER APPLYING, EVICT THE CACHE: `inspect_kbli` caches its assembled payload
under `kbli_inspect_v6_<code>` for up to 30 days, so a cured Qdrant payload is
invisible on the channel until `kbli_inspect_cache_bust.py --only <codes>
--apply` has run.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

_APP_ROOT = Path(__file__).resolve().parents[2]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from backend.services.kbli_pma_disclosure import (
    disclose_bali,
    disclose_pma,
    pma_claims_verified,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_qdrant_pma_sync")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

# The flat KBLI payload invariant (CLAUDE.md §9) — the code lives in
# `kode_kbli`, never nested. Points are always resolved through this filter,
# never through a point-id assumption.
CODE_KEY = "kode_kbli"

_SCROLL_PAGE_LIMIT = 256


LAYERS = ("pma", "bali", "whatchanged")

# The blob the RETRIEVER hands to the LLM. Stored under two keys that
# `reindex_kbli_2025_final.py::build_payload` fills with the SAME string, so both
# are rewritten from the same source and neither is left behind.
PROSE_KEYS = ("content", "text")


@dataclass(frozen=True)
class Target:
    """What the canonical says this code's payload should be, for one layer.

    `fields` maps a Qdrant payload key to the canonical value. Keeping it a
    mapping rather than named attributes is what lets one comparison, one
    diff-log and one `set_payload` body serve both layers — a second copy of
    that logic is a second place for the two to drift apart.
    """

    code: str
    layer: str
    fields: dict[str, Any]
    # The canonical record itself, carried so the prose repair reads the SAME
    # source as the flat fields. Two lookups of one record is how the two
    # representations end up disagreeing.
    record: dict = field(default_factory=dict)


@dataclass
class CodePlan:
    """Pure decision record for one code — no I/O, so it unit-tests directly."""

    code: str
    target: Target
    point_ids: list[Any]
    current: dict[Any, dict[str, Any]]
    # pid -> {payload key -> repaired blob}. Empty for layers that own no prose,
    # and empty for a point already carrying the truthful prose.
    prose: dict[Any, dict[str, str]] = field(default_factory=dict)
    # Points whose blob is not shaped the way the repair assumes. Reported and
    # NEVER written: a blob we cannot locate the block in is a blob we do not
    # understand, and overwriting it would be a guess (W84 — a refusal is not
    # an empty finding).
    unshaped: list[Any] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.point_ids)

    def stale_points(self) -> list[Any]:
        """Point ids whose payload disagrees with the canonical on ANY field of
        the layer, OR whose prose still carries the old wording. Judging on one
        field would leave the others uncured — that is how a point ends up
        reading TERBATAS at 100%, and how a point ends up reading TERBATAS in
        its flat field while its blob still says TERBUKA / 100."""
        out = []
        for pid in self.point_ids:
            if pid in self.unshaped:
                continue
            cur = self.current.get(pid, {})
            if any(cur.get(key) != value for key, value in self.target.fields.items()):
                out.append(pid)
            elif self.prose.get(pid):
                out.append(pid)
        return out

    def payload_for(self, pid: Any) -> dict[str, Any]:
        """What to `set_payload` on ONE point: the layer's flat fields plus, when
        this point needed it, the repaired blob. Per-point because the blob is
        per-point — a single shared body would copy one point's prose onto every
        other point of the code."""
        return {**self.target.fields, **self.prose.get(pid, {})}


def _pma_fields(rec: dict) -> tuple[dict[str, Any] | None, str | None]:
    public = disclose_pma(rec)
    keys = (
        "pma_status",
        "pma_max_asing",
        "pma_verification_status",
        "pma_official_basis",
        "pma_source_vintage",
        "pma_cap_special",
        "pma_cap_verified",
    )
    return {key: public[key] for key in keys}, None


def _bali_fields(rec: dict) -> tuple[dict[str, Any] | None, str | None]:
    """The Bali layer, copied from `l4_bali.status` — never recomputed.

    Mirrors `reindex_kbli_2025_final.py::build_payload` key for key, so a payload
    written here and a payload written by a full re-index say the same thing.
    `l4_bali.verdict` is deliberately NOT read: see the module docstring for the
    118-code measurement that removed the tool which did.
    """
    return disclose_bali(rec), None


def _whatchanged_fields(rec: dict) -> tuple[dict[str, Any] | None, str | None]:
    """A PROSE-ONLY layer: `whatChanged` has no flat payload key at all.

    Measured 2026-08-05 on `kbli_2025_final_hybrid`: the payload carries 29 flat
    keys and `whatChanged` is not among them — the sentence exists only inside
    the `content`/`text` blob, under `## Intelligence 2026`. So this layer owns
    no flat field and returns an empty mapping; everything it repairs is prose.
    """
    intel = rec.get("intel_2026")
    if not isinstance(intel, dict) or not intel.get("whatChanged"):
        return (
            None,
            "canonical record carries no intel_2026.whatChanged — nothing authoritative to sync",
        )
    return {}, None


_LAYER_READERS = {
    "pma": _pma_fields,
    "bali": _bali_fields,
    "whatchanged": _whatchanged_fields,
}


# ---------------------------------------------------------------------------
# PROSE REPAIR — the same fact, in the other representation
#
# WHY THIS EXISTS (measured on prod 2026-08-05, during the prove-live of the
# whatChanged cure):
#
#   `--layer pma` synced the FLAT keys and stopped there. But the payload also
#   holds `content`/`text` — `build_embedding_text(record)`, the blob the
#   retriever hands to the LLM verbatim — and that blob still opened with
#
#       ## Status PMA: TERBUKA
#       - Kepemilikan asing maksimal: 100
#
#   on all 20 codes the Perpres 49/2021 cure had capped. Among them `25200`
#   (arms and ammunition, real cap 49%) and `79122` (Umrah/Hajj travel, real cap
#   **0%**). `inspect_kbli` reads the flat field and was cured; the RAG channel
#   reads the blob and was not. TWO REPRESENTATIONS OF ONE FACT, and the cure
#   reached one of them — the same shape as every other scar in this lane.
#
#   So the fact's owner repairs BOTH. Putting the blob repair in a second tool
#   is exactly the two-writers arrangement the module docstring above forbids:
#   they would disagree precisely when it matters.
#
# FIDELITY TO THE GENERATOR: these renderers must emit what a full re-index
# would emit, character for character, or the next re-index silently reverts the
# cure and the two disagree again. That is asserted, not asserted-by-comment:
# `test_prose_repair_matches_the_real_generator` runs the REAL
# `build_embedding_text` over canonical records and requires the repair to be a
# no-op on its fresh output, including the zero-cap and special non-percentage
# forms.
#
# WHAT IS NOT CLAIMED: the VECTOR is not re-computed (the embedding model is
# FROZEN). The old sentence still shapes retrieval RANKING; what changes is the
# text the model is given once the point is retrieved. Ranking drift is a
# re-index question, ledgered separately — but a wrong sentence in the context
# window is what reaches a client, and that is what this removes.
# ---------------------------------------------------------------------------

_PMA_HEADING = "## Status PMA:"
_INTEL_HEADING = "## Intelligence 2026"
_BALI_HEADING = "## Status PMA di Bali (L4 — moratorium provinsi)"
_WHATCHANGED_PREFIX = "- whatChanged: "
_TRUNCATION_MARKER = "(... dipotong untuk batas panjang.)"


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def render_pma_block(rec: dict) -> list[str]:
    """The `## Status PMA:` block exactly as `build_embedding_text` writes it.

    FIVE lines, not two. The first draft rendered only status + cap and the
    generator-fidelity organ failed on the very first record (`01131`): the real
    block also carries `- Kondisi:`, `- Prioritas:` and `- Nota:`, so a repair
    that knew about two of them would have DELETED a priority-sector note from
    every point it touched — silent data loss dressed as a cure. Any field added
    to the generator's block must be added here, and that test is what says so.
    """
    fields, _ = _pma_fields(rec)
    assert fields is not None
    if fields["pma_verification_status"] != "located":
        return [
            f"{_PMA_HEADING} NOT_VERIFIED",
            "- Whole-code foreign ownership is withheld: no located official basis and source vintage are recorded.",
        ]

    lines = [f"{_PMA_HEADING} {fields['pma_status']}"]
    cap = fields["pma_max_asing"]
    if fields["pma_cap_verified"]:
        if cap == "special":
            lines.append("- Kepemilikan asing: kondisi khusus non-persentase")
        elif cap is not None:
            lines.append(f"- Kepemilikan asing maksimal: {cap}%")
    else:
        lines.append("- Kepemilikan asing: belum terverifikasi")
    condition = _clean_text(rec.get("pma_kondisi"))
    if condition:
        lines.append(f"- Kondisi: {condition}")
    if rec.get("pma_prioritas") is True:
        lines.append("- Prioritas: Ya")
    note = _clean_text(rec.get("pma_nota"))
    if note:
        lines.append(f"- Nota: {note}")
    return lines


def render_bali_block(rec: dict) -> list[str]:
    """Mirror ``reindex_kbli_2025_final.render_bali_embedding_block`` exactly."""
    fields, _ = _bali_fields(rec)
    assert fields is not None
    if not fields["has_bali_l4"]:
        return []

    lines = [_BALI_HEADING]
    if fields["bali_blocked"] is True:
        lines.append(
            "- DIBLOKIR untuk PMA di Bali: kegiatan risiko Rendah/Menengah-Rendah "
            "tidak dapat didaftarkan PT PMA di Provinsi Bali (moratorium 2026-05-13)."
        )
    lines.append(f"- Status Bali: {fields['bali_status']}")
    if fields["bali_reason"]:
        lines.append(f"- Alasan: {fields['bali_reason']}")
    lines.append(
        "- Note: national status (Perpres 10/2021) can differ from the "
        "provincial block; read both verdicts."
    )
    return lines


def _replace_block(blob: str, start_pred, stop_pred, new_lines: list[str]) -> str | None:
    """Swap one contiguous run of lines. Returns None when the block is absent —
    a caller must treat that as "this point is not shaped the way I assume" and
    refuse, never as "nothing to do"."""
    lines = blob.split("\n")
    try:
        i = next(n for n, ln in enumerate(lines) if start_pred(ln))
    except StopIteration:
        return None
    j = i + 1
    while j < len(lines) and not stop_pred(lines[j]):
        j += 1
    return "\n".join(lines[:i] + new_lines + lines[j:])


def _replace_heading_section(blob: str, heading: str, new_lines: list[str]) -> str:
    """Replace an optional generated ``##`` section while preserving spacing."""
    lines = blob.split("\n")
    try:
        start = lines.index(heading)
    except ValueError:
        return blob
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1

    before = lines[:start]
    after = lines[end:]
    replacement = list(new_lines)
    if replacement:
        # Generated sections are separated from the next section (or EOF) by
        # one empty line. Preserve that byte shape for generator fidelity.
        replacement.append("")
    return "\n".join(before + replacement + after)


def rewrite_pma_prose(rec: dict, blob: str) -> str | None:
    rewritten = _replace_block(
        blob,
        lambda ln: ln.startswith(_PMA_HEADING),
        lambda ln: not ln.startswith("- "),
        render_pma_block(rec),
    )
    if rewritten is None or pma_claims_verified(rec):
        return rewritten

    # A declared gap owns the entire generated/editorial disclosure boundary,
    # not only the two PMA lines. Old points can still carry an Intelligence
    # section or a Bali verdict that asserts PT PMA registrability. Remove both
    # atomically.
    # The generator can truncate in the middle of the Bali or Intelligence
    # section.  Expanding a partial section would write content *after* the
    # marker that explicitly says the document ended.  A fresh declared-gap
    # blob is already safe once its PMA block is replaced, so leave that byte
    # shape alone.  A legacy truncated blob that still carries editorial prose
    # cannot be repaired losslessly and is refused instead.
    if _TRUNCATION_MARKER in rewritten:
        if _INTEL_HEADING in rewritten or _BALI_HEADING in rewritten:
            return None
        return rewritten

    rewritten = _replace_heading_section(rewritten, _INTEL_HEADING, [])
    if _BALI_HEADING in rewritten:
        rewritten = _replace_heading_section(rewritten, _BALI_HEADING, render_bali_block(rec))
    return rewritten


def rewrite_whatchanged_prose(rec: dict, blob: str) -> str | None:
    """Replace EXACTLY ONE line.

    `build_embedding_text` emits each intel entry as a single `- {k}: {v}` part,
    and measured on canonical 2026-08-05 **zero** of the 1,559 `whatChanged`
    values contain a newline (longest 665 chars) — so the block is one line and
    a multi-line span rule is not just unnecessary, it is wrong: the first draft
    consumed lines until the next `- `/`## `, which on `20112` swallowed the
    generator's own truncation marker `(... dipotong untuk batas panjang.)`.

    A value that DID contain a newline would silently break the round trip, so
    it is refused rather than written.

    Refusing when the line is absent matters just as much: for 101 of 1,559
    records the generator truncates before `## Intelligence 2026` ever appears,
    and appending a line there would put content AFTER a marker that tells the
    reader the document stopped.
    """
    text = (rec.get("intel_2026") or {}).get("whatChanged")
    if not text or "\n" in text:
        return None
    lines = blob.split("\n")
    for n, ln in enumerate(lines):
        if ln.startswith(_WHATCHANGED_PREFIX):
            lines[n] = f"{_WHATCHANGED_PREFIX}{text}"
            return "\n".join(lines)
    return None


_LAYER_PROSE = {
    "pma": rewrite_pma_prose,
    "bali": None,  # the Bali block is not repaired here — see the ledger line
    "whatchanged": rewrite_whatchanged_prose,
}


def build_targets(
    records: list[dict], codes: list[str], layer: str = "pma"
) -> tuple[dict[str, Target], list[str]]:
    """Read the canonical verdict for each requested code.

    A code the canonical does not carry is a REFUSAL, not a skip: writing a
    guessed or inherited verdict onto a client-facing store is the whole class of
    defect this lane exists to remove.
    """
    if layer not in _LAYER_READERS:
        raise ValueError(f"unknown layer {layer!r} — expected one of {LAYERS}")
    read = _LAYER_READERS[layer]
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    targets: dict[str, Target] = {}
    refusals: list[str] = []
    for code in codes:
        rec = by_code.get(code)
        if rec is None:
            refusals.append(
                f"{code}: absent from the canonical dataset — refusing to write a {layer} verdict for it"
            )
            continue
        fields, why = read(rec)
        if fields is None:
            refusals.append(f"{code}: {why}")
            continue
        targets[code] = Target(code=code, layer=layer, fields=fields, record=rec)
    return targets, refusals


def load_dataset(source: str) -> list[dict]:
    """Local path or URL — the same two-mode source the sibling cure tools take."""
    if source.startswith(("http://", "https://")):
        logger.info("dataset: fetching %s", source)
        with httpx.Client(timeout=120) as http:
            resp = http.get(source)
            resp.raise_for_status()
            payload = resp.json()
    else:
        logger.info("dataset: reading %s", source)
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    return payload["data"]


def qdrant_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def find_points_for_code(
    http: httpx.Client, url_base: str, headers: dict[str, str], collection: str, code: str
) -> list[dict]:
    """Scroll every point in `collection` whose flat `kode_kbli` equals `code`."""
    records: list[dict] = []
    offset = None
    while True:
        body: dict[str, Any] = {
            "filter": {"must": [{"key": CODE_KEY, "match": {"value": code}}]},
            "limit": _SCROLL_PAGE_LIMIT,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            body["offset"] = offset
        resp = http.post(
            f"{url_base}/collections/{collection}/points/scroll", headers=headers, json=body
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        records.extend(result.get("points", []))
        offset = result.get("next_page_offset")
        if offset is None:
            break
    return records


def build_plan(code: str, target: Target, points: list[dict]) -> CodePlan:
    """Turn scrolled points into a plan — pure, no I/O.

    Only the layer's own keys are read off the existing payload, so the plan can
    never carry — and therefore never re-write — a field this run does not own.
    """
    ids = [p["id"] for p in points]
    current = {
        p["id"]: {key: (p.get("payload") or {}).get(key) for key in target.fields} for p in points
    }
    rewrite = _LAYER_PROSE.get(target.layer)
    prose: dict[Any, dict[str, str]] = {}
    unshaped: list[Any] = []
    if rewrite is not None:
        for p in points:
            payload = p.get("payload") or {}
            repaired: dict[str, str] = {}
            for key in PROSE_KEYS:
                blob = payload.get(key)
                if not isinstance(blob, str) or not blob:
                    continue
                new = rewrite(target.record, blob)
                if new is None:
                    # The block this layer owns is not in the blob. Not "already
                    # correct" — unknown. Recorded so the run says so out loud.
                    unshaped.append(p["id"])
                    repaired = {}
                    break
                if new != blob:
                    repaired[key] = new
            if repaired:
                prose[p["id"]] = repaired
    return CodePlan(
        code=code,
        target=target,
        point_ids=ids,
        current=current,
        prose=prose,
        unshaped=unshaped,
    )


def _describe(values: dict[str, Any]) -> str:
    return " / ".join(f"{v!r}" for v in values.values())


def apply_plan(
    http: httpx.Client,
    url_base: str,
    headers: dict[str, str],
    collection: str,
    plan: CodePlan,
    apply: bool,
) -> int:
    """Report (always) and write (only when `apply`). Returns points written."""
    if not plan.found:
        logger.info("  %s: NOT FOUND — no point matches %s=%s", plan.code, CODE_KEY, plan.code)
        return 0

    for pid in plan.unshaped:
        logger.warning(
            "  %s: point %s carries no %r block in its blob — REFUSING to rewrite prose "
            "we cannot locate (the point is left exactly as found)",
            plan.code,
            pid,
            plan.target.layer,
        )

    stale = plan.stale_points()
    if not stale:
        logger.info(
            "  %s: already agrees with canonical (%s)",
            plan.code,
            _describe(plan.target.fields) or f"{plan.target.layer} prose",
        )
        return 0

    cap = plan.target.fields.get("pma_max_asing")
    if cap is not None and not isinstance(cap, (int, float)):
        # 47221 carries the string "special" — a non-percentage regime. Passed
        # through verbatim rather than coerced, but said out loud: a payload
        # field that changes type is exactly what a downstream reader does not
        # expect, and a silent coercion here would invent a number.
        logger.warning(
            "  %s: canonical cap is %r (%s), not an int — writing it verbatim",
            plan.code,
            cap,
            type(cap).__name__,
        )

    for pid in stale:
        cur = plan.current.get(pid, {})
        repaired = plan.prose.get(pid, {})
        logger.info(
            "  %s: point %s  %s -> %s%s%s",
            plan.code,
            pid,
            _describe({k: cur.get(k) for k in plan.target.fields}),
            _describe(plan.target.fields),
            f"  [+prose: {', '.join(sorted(repaired))}]" if repaired else "",
            "" if apply else "  (dry-run, not written)",
        )

    if not apply:
        return 0

    # One request per point when prose is involved — the blob is per-point, and a
    # single shared body would stamp one point's repaired text onto every other
    # point of the same code.
    if plan.prose:
        for pid in stale:
            resp = http.post(
                f"{url_base}/collections/{collection}/points/payload",
                headers=headers,
                json={"payload": plan.payload_for(pid), "points": [pid]},
            )
            resp.raise_for_status()
        return len(stale)

    resp = http.post(
        f"{url_base}/collections/{collection}/points/payload",
        headers=headers,
        json={"payload": dict(plan.target.fields), "points": stale},
    )
    resp.raise_for_status()
    return len(stale)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--codes",
        required=True,
        help="comma-separated KBLI codes to sync (never auto-discovered or swept)",
    )
    ap.add_argument(
        "--collection",
        required=True,
        help="physical Qdrant collection, e.g. kbli_2025_final_hybrid. Mandatory on "
        "purpose: a default here would freeze a measure of the world into a constant.",
    )
    ap.add_argument("--dataset", default=DATASET_URL, help="canonical dataset: local path or URL")
    ap.add_argument(
        "--layer",
        choices=LAYERS,
        default="pma",
        help="which payload layer to sync: 'pma' (national ownership: pma_status, "
        "pma_max_asing, AND the '## Status PMA:' block inside the content/text blob), "
        "'bali' (provincial verdict: bali_status, bali_blocked, bali_needs_review, "
        "bali_reason, has_bali_l4) or 'whatchanged' (prose-only: the '- whatChanged:' line inside "
        "the blob, which has no flat payload key). One layer per run, on purpose — "
        "they answer different questions from different instruments.",
    )
    args = ap.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        logger.error("--codes produced an empty list, nothing to do")
        return 2

    logger.info("layer: %s", args.layer)
    targets, refusals = build_targets(load_dataset(args.dataset), codes, args.layer)
    if refusals:
        for r in refusals:
            logger.error("REFUSED %s", r)
        logger.error("refusing the whole run — nothing written")
        return 2

    url_base = os.environ["QDRANT_URL"].rstrip("/")
    headers = qdrant_headers(os.environ.get("QDRANT_API_KEY"))

    written = 0
    found = 0
    agreed = 0
    with httpx.Client(timeout=60) as http:
        plans = []
        for code in codes:
            points = find_points_for_code(http, url_base, headers, args.collection, code)
            plans.append(build_plan(code, targets[code], points))

        if not any(p.found for p in plans):
            # A collection that does not carry `kode_kbli` returns a clean zero
            # for every code, including ones you know exist. Never report that
            # as "nothing to do".
            logger.error(
                "not one of the %d requested codes matched a point in %r on key %r — "
                "wrong collection? (the KBLI points live in kbli_2025_final_hybrid)",
                len(codes),
                args.collection,
                CODE_KEY,
            )
            return 2

        for plan in plans:
            if plan.found:
                found += 1
                if not plan.stale_points():
                    agreed += 1
            written += apply_plan(http, url_base, headers, args.collection, plan, args.apply)

    verb = f"{'APPLIED' if args.apply else 'DRY-RUN'} [{args.layer}]"
    logger.info(
        "%s: %d/%d code(s) found | %d already agreed | %d point(s) %s",
        verb,
        found,
        len(codes),
        agreed,
        written if args.apply else sum(len(p.stale_points()) for p in plans if p.found),
        "written" if args.apply else "would be written",
    )
    if not args.apply:
        logger.info("dry-run complete — rerun with --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
