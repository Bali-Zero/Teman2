#!/usr/bin/env python3
"""Re-derive the `**PMA:**` sentence in `apps/mouth/data/kbli-gold-all.json`
from the canonical record's adjudicated cap.

WHY THIS EXISTS
---------------
`kbli-gold-all.json` OVERRIDES canonical on every field it carries, on every
rendered page (`kbli-data.server.ts::getGoldContent` feeds `/kbli/[code]` and
`/api/kbli/gold/[code]` directly, bypassing `transformCode`'s merged intel).
428 of the 1,559 codes have a gold entry.

Gold's `whatYouNeed` carries a `**PMA:**` sentence — a RESTATEMENT of a fact
gold does not own. On 2026-08-07 that restatement disagreed with the canonical
cap on **21** codes. Sixteen of them promised MORE foreign ownership than the
record allows, and they were live: `/kbli/51101` (scheduled airlines, cap 49)
rendered `**PMA:** Fully open — 100% foreign ownership allowed.` in the same
page that, two sections above, correctly said the ceiling is 49% — the page
stated the fact twice and the second occurrence contradicted the cure.

HOW IT SURVIVED THE CURE LANE
-----------------------------
`cure_prose_national_openness.py`'s own docstring asserts, in terms, that gold
"is already clean — measured, zero openness assertions across all 428 gold
codes". That measurement was real but it was taken with
`editorial_record_conformance.classify`, whose predicate needs an openness
claim AND a national-scope word IN THE SAME SENTENCE. `**PMA:** Fully open —
100% foreign ownership allowed.` has the claim and no scope word, so the
detector acquits it. A result true OF THAT PREDICATE was written down as a
property OF THE FILE, and every later session read that sentence and did not
look. The docstring is corrected in the same commit as this compiler: a false
"already clean" is worse than no note at all, because it aims the next reader
away.

WHAT IT PATCHES, AND WHAT IT REFUSES
------------------------------------
Patches ONLY where gold carries the *default* sentence emitted by the
enrichment scripts (`kbli_enrich_deterministic.py:125`,
`kbli_enrichment_pipeline.py:245`, `kbli_silver_parallel.py:202`) —
"Fully open — N% foreign ownership[ allowed]." — AND gold states a HIGHER
figure than canonical. Those are codes where gold froze the pre-adjudication
default while canonical was later adjudicated against a cited instrument
(Perpres 10/2021 as replaced by 49/2021, or the UMKM reservation). Rewriting
them asserts nothing new: it propagates an adjudication that already happened.

REFUSES, and names, everything else:
  * gold MORE RESTRICTIVE than canonical — a rewrite there would assert that
    canonical is right, which is a per-code adjudication and not a deduction;
  * hand-authored sentences carrying conditions (`86101`, `47222`) — a
    mechanical swap would leave a "closed" line above a step-by-step guide for
    the PT PMA that cannot exist, which reads worse than the contradiction;
  * canonical caps that are not a number (`special`).

FOUR REFUSALS BEFORE IT WRITES
------------------------------
1. Canonical cap must be an int (never `special`, never absent).
2. Gold's live sentence must hash to the pinned `old_sha256` for that field.
3. The rewritten sentence may state no percentage other than canonical's cap —
   the one machine-checkable property of the sentence.
4. After patching IN MEMORY, a re-scan must report zero more-open divergences
   on the cured codes AND an unchanged verdict on every other gold code.

Dry-run is the default; nothing is written without --apply.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANON_PATH = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"

log = logging.getLogger("cure_gold_pma_line")

# The sentence the enrichment scripts emit for an open record. Anchored to the
# marker and stopped at the sentence's own full stop so the rest of the field —
# which is authored content — is never in the replacement's reach.
DEFAULT_OPEN_RE = re.compile(
    r"\*\*PMA:\*\*\s*Fully open\s*—\s*(\d{1,3})%\s*foreign ownership(?: allowed)?\."
)
# Any PMA sentence, for the divergence scan. The optional inner `**` is not
# cosmetic: `41020` writes `**PMA: TERBUKA 100% — fully open to foreign
# ownership.**` — colon INSIDE the bold — and the first version of this pattern,
# written from the shape I had already found, was blind to it on a cap-0 code.
# A pattern derived from the instance you found catches the instance you found.
PMA_SENTENCE_RE = re.compile(r"\*\*PMA:?(?:\*\*)?[^\n]*")
PERCENT_RE = re.compile(r"(\d{1,3})\s*%")

# Openness asserted in WORDS, anywhere in gold, outside a PMA sentence. This is
# the class a percentage check cannot reach: `53200` states its cap correctly
# and then says "Since this is fully open to foreign investment" three fields
# away. Reported by --report; the two live instances are cured below.
PROSE_OPEN_RE = re.compile(
    r"(100%\s*(?:foreign|owned|foreign-owned|PMA)|fully open|wholly foreign|"
    r"open to 100%|foreign investors can (?:fully )?own)",
    re.I,
)

# Gold passages that assert 100% openness on a capped code and are RIGHT,
# because the figure belongs to a DIFFERENT, NAMED code. Never "corrected".
PROSE_ACQUITTED = {
    "47111": (
        "the '100% PMA' is 47191's, named in the same paragraph as the PMA "
        "alternative; the passage itself says 'foreigners cannot own 47111' and "
        "calls the segment UMKM-reserved. The number belongs to another entity."
    ),
}

# Sentence-level replacements that had to be WRITTEN, not derived — each pinned
# to the exact sentence it was authored against, so it can never land on a
# paragraph it was not graded on. Kept here rather than in the mechanical path
# because a compiler that starts authoring is a compiler nobody can audit.
AUTHORED_SENTENCES = {
    "41020": {
        "field": "whatYouNeed",
        "old": "**PMA: TERBUKA 100% — fully open to foreign ownership.**",
        "new": (
            "**PMA: 0% — closed to foreign shareholding.** Prefabricated-building "
            "construction is reserved to cooperatives and Indonesian MSMEs by "
            "Perpres 49/2021, so a PT PMA cannot register this code anywhere in "
            "Indonesia."
        ),
        "why": "cap 0, UMKM-reserved; the line asserted the exact opposite",
    },
    "53200": {
        "field": "baliContext",
        "old": (
            "Since this is fully open to foreign investment, expect a minimum "
            "paid-up capital of IDR 10 billion."
        ),
        # The paid-up figure here was IDR 10 billion when this sentence was
        # first authored — inherited unexamined from the clause I was replacing,
        # and wrong since Permen BKPM 5/2025 (art. 26(10): 2.5 billion). Caught
        # by `cure_gold_paidup_capital.py` an hour later. The lesson is not the
        # figure: it is that a cure reads the clause it came for and copies the
        # one beside it.
        "new": (
            "Foreign shareholding in courier activity is capped at 49%, so an "
            "Indonesian partner holds the majority; expect a minimum paid-up "
            "capital of IDR 2.5 billion. Total investment must still exceed IDR "
            "10 billion per 5-digit KBLI per location — a separate threshold "
            "from the paid-up minimum (Permen BKPM 5/2025 art. 26(2) and "
            "art. 26(10))."
        ),
        "why": "cap 49; the sentence made the capital figure follow FROM an openness that is not the case",
    },
}


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


def resolve_cap(rec: dict) -> int | str | None:
    """Mirror of apps/mouth/src/lib/kbli-pma-cap.ts::resolvePmaCap.

    Deliberately a mirror and not a re-invention: two modules that must agree
    about one fact do not get to invent two answers (W105). Kept in step by
    test_gold_pma_line_matches_canonical.py, which asserts the ladder.
    """
    raw = rec.get("pma_max_asing")
    if isinstance(raw, bool):
        raw = None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        t = raw.strip()
        if t == "special":
            return "special"
        if t.isdigit():
            return int(t)
    status = rec.get("pma_status")
    if status == "TERBUKA":
        return 100
    if status == "TERTUTUP":
        return 0
    return "special"


def derived_sentence(cap: int) -> str:
    """The enrichment scripts' own three forms — same vocabulary, so a reader
    who has seen one gold page is not asked to learn a second dialect."""
    if cap == 0:
        return "**PMA:** Closed to foreign investment — domestic entities only."
    if cap >= 100:
        return "**PMA:** Fully open — 100% foreign ownership allowed."
    return f"**PMA:** Restricted — max {cap}% foreign ownership."


def stated_figure(sentence: str) -> int | None:
    if "closed to foreign" in sentence.lower():
        return 0
    m = PERCENT_RE.search(sentence)
    return int(m.group(1)) if m else None


def scan(gold: dict, by_code: dict, incomparable: list | None = None) -> dict[str, dict]:
    """Every gold code whose PMA sentence states a figure ≠ the canonical cap.

    Returns {code: {field, sentence, stated, cap, more_open, is_default}}.

    A code whose canonical cap is not a number (`special`) can carry a gold
    figure that no comparison can judge — `47221` states 49% against a cap of
    `special`. Excluding it is correct; excluding it SILENTLY is not, because
    the count then reads as the whole population. Those codes are appended to
    `incomparable` and printed by main(), so "20 divergences" never quietly
    means "20, plus one I could not look at" (no silent caps).
    """
    out: dict[str, dict] = {}
    for code, rec in gold.items():
        field = sentence = None
        for k, v in rec.items():
            if isinstance(v, str):
                m = PMA_SENTENCE_RE.search(v)
                if m:
                    field, sentence = k, m.group(0)
                    break
        if sentence is None:
            continue
        canon = by_code.get(code)
        if canon is None:
            continue
        cap = resolve_cap(canon)
        stated = stated_figure(sentence)
        if stated is not None and not isinstance(cap, int):
            if incomparable is not None:
                incomparable.append((code, stated, cap, sentence))
            continue
        if stated is None or stated == cap:
            continue
        out[code] = {
            "field": field,
            "sentence": sentence,
            "stated": stated,
            "cap": cap,
            "status": canon.get("pma_status"),
            "more_open": stated > cap,
            "is_default": bool(DEFAULT_OPEN_RE.fullmatch(sentence.strip())),
        }
    return out


def prose_scan(gold: dict, by_code: dict) -> dict[str, list]:
    """Openness asserted in words, on a code whose cap is below 100.

    DECLARED LIMIT: this reads for a vocabulary, so it is blind to a
    reformulation and to the other four languages the site serves. It is a
    second net under the percentage check, not a proof of cleanliness — and
    saying so here is the point, because the last thing this file's sibling
    claimed was that a narrower net had found nothing.
    """
    out: dict[str, list] = {}
    for code, rec in gold.items():
        canon = by_code.get(code)
        if canon is None:
            continue
        cap = resolve_cap(canon)
        if not isinstance(cap, int) or cap >= 100:
            continue
        for k, v in rec.items():
            if not isinstance(v, str):
                continue
            stripped = PMA_SENTENCE_RE.sub("", v)  # the PMA sentence has its own check
            for m in PROSE_OPEN_RE.finditer(stripped):
                s = max(0, m.start() - 90)
                out.setdefault(code, []).append(
                    (cap, k, stripped[s : m.end() + 90].replace("\n", " "))
                )
    return out


def plan(findings: dict[str, dict], gold: dict) -> tuple[dict, dict]:
    """Split the findings into what a compiler may do and what it must not."""
    patch: dict[str, dict] = {}
    refused: dict[str, str] = {}
    for code, f in sorted(findings.items()):
        if code in AUTHORED_SENTENCES:
            continue  # handled by the authored path, not by derivation
        if not f["more_open"]:
            refused[code] = (
                f"gold is MORE RESTRICTIVE ({f['stated']}% vs cap {f['cap']}); "
                "rewriting would assert canonical is right — per-code adjudication"
            )
            continue
        if not f["is_default"]:
            refused[code] = (
                "the PMA sentence carries text beyond the figure — a condition, a "
                "note, or authored prose. Replacing the sentence would drop that "
                "text, or leave it standing above a paragraph written for an "
                "entity the record is not"
            )
            continue
        old_text = gold[code][f["field"]]
        new_text = DEFAULT_OPEN_RE.sub(
            lambda _m: derived_sentence(f["cap"]), old_text, count=1
        )
        if new_text == old_text:
            raise CureError(f"{code}: replacement was a no-op — refusing to claim a cure")
        for got in PERCENT_RE.findall(derived_sentence(f["cap"])):
            if int(got) != f["cap"]:
                raise CureError(
                    f"{code}: replacement states {got}% but the record's cap is "
                    f"{f['cap']}"
                )
        patch[code] = {
            "field": f["field"],
            "old_sha256": hashlib.sha256(old_text.encode("utf-8")).hexdigest(),
            "new": new_text,
            "was": f["sentence"],
            "now": derived_sentence(f["cap"]),
            "cap": f["cap"],
        }
    return patch, refused


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--report", action="store_true", help="print the full scan")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    canon = json.loads(CANON_PATH.read_text(encoding="utf-8"))
    by_code = {r["kode_kbli_2025"]: r for r in canon["data"]}
    gold_raw = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)

    incomparable: list = []
    findings = scan(gold, by_code, incomparable)
    patch, refused = plan(findings, gold)

    # Authored sentences — pinned, never pattern-matched into place.
    authored: dict[str, dict] = {}
    for code, a in sorted(AUTHORED_SENTENCES.items()):
        live = gold.get(code, {}).get(a["field"])
        if live is None:
            raise CureError(f"{code}.{a['field']}: field is gone — the pin is stale")
        if a["old"] not in live:
            if a["new"] in live:
                continue  # already applied; idempotent, not a failure
            raise CureError(
                f"{code}.{a['field']}: the pinned sentence is not in the live text. "
                "It was authored against a paragraph that has since moved; re-read "
                "it before re-pinning."
            )
        authored[code] = {"field": a["field"], "new": live.replace(a["old"], a["new"], 1)}

    prose = prose_scan(gold, by_code)
    unacquitted = {c: v for c, v in prose.items()
                   if c not in PROSE_ACQUITTED and c not in AUTHORED_SENTENCES
                   and c not in refused}
    log.info("prose openness on capped codes: %d found | %d acquitted | %d to author",
             len(prose), len(PROSE_ACQUITTED), len(unacquitted))
    for code, hits in sorted(unacquitted.items()):
        cap, field, frag = hits[0]
        log.info("    PROSE %s cap=%s [%s] …%s…", code, cap, field, frag.strip()[:110])

    log.info("gold codes: %d | divergences: %d", len(gold), len(findings))
    for code, stated, cap, _s in sorted(incomparable):
        log.info("  NOT COMPARABLE %s  gold=%s%% canonical=%r — no figure to compare",
                 code, stated, cap)
    log.info("  patchable (default sentence, gold more open): %d", len(patch))
    log.info("  refused and named: %d", len(refused))
    for code, why in sorted(refused.items()):
        f = findings[code]
        log.info("    REFUSE %s  gold=%s%% canonical=%s%% — %s",
                 code, f["stated"], f["cap"], why)
    if args.report or not args.apply:
        for code, p in sorted(patch.items()):
            log.info("    %s  «%s»  ->  «%s»", code, p["was"], p["now"])

    if not patch and not authored:
        log.info("nothing to patch")
        return 0

    # Refusal 4: patch in memory, then re-scan. The second half — every other
    # gold code unchanged — matters more than the first.
    before = {c: f["stated"] for c, f in findings.items()}
    staged = copy.deepcopy(gold)
    for code, p in patch.items():
        live = staged[code][p["field"]]
        got = hashlib.sha256(live.encode("utf-8")).hexdigest()
        if got != p["old_sha256"]:
            raise CureError(f"{code}.{p['field']}: live text moved under the plan")
        staged[code][p["field"]] = p["new"]
    for code, a in authored.items():
        staged[code][a["field"]] = a["new"]

    # The authored sentences must silence the prose scan on their own codes,
    # and must not wake it anywhere else.
    prose_after = prose_scan(staged, by_code)
    for code in authored:
        if code in prose_after:
            raise CureError(f"{code}: authored sentence did not silence the prose scan")
    for code in prose_after:
        if code not in prose:
            raise CureError(f"{code}: prose finding appeared on a code never touched")

    after = scan(staged, by_code)
    for code in patch:
        if code in after:
            raise CureError(f"{code}: still divergent after the patch")
    for code, f in after.items():
        if code not in before or before[code] != f["stated"]:
            raise CureError(f"{code}: verdict changed on a code this cure never touched")

    if not args.apply:
        log.info("DRY-RUN — nothing written. Re-run with --apply.")
        return 0

    if "data" in gold_raw and isinstance(gold_raw["data"], dict):
        gold_raw["data"] = staged
    else:
        gold_raw = staged
    GOLD_PATH.write_text(
        json.dumps(gold_raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("WROTE %s — %d re-derived, %d authored", GOLD_PATH.name,
             len(patch), len(authored))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CureError as exc:
        log.error("REFUSED: %s", exc)
        sys.exit(2)
