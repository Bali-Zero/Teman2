#!/usr/bin/env python3
"""KBLI dataset lint — the anti-presunzione vaccine (blueprint 2026-06-19, built 2026-07-07).

Deterministic, zero-LLM checks over apps/mouth/data/KBLI_2025_FINAL_CLEAN.json:
  L1  italian-prose        Italian text in investor-facing fields (l4_bali.reason, intel_2026.*)
  L2  en-title-coverage    codes lacking a curated English title (kbli-english.ts)
  L3  phantom-codes        5-digit KBLI-looking references in prose that do not exist in the dataset
  L4  date-format          non-canonical date renderings in prose (canon: "13 May 2026")
  L5  pma-coherence        nationally-closed code whose l4 status/prose claims Bali registrability
  L6  risk-coherence       prose risk level contradicting per_skala kategori_risiko (reuses kbli_enrich_validate)
  L7  per-skala-empty      codes with no per_skala rows (report-only; special-regime sectors expected)
  L8  reason-english       l4_bali.reason must read as English (structural fix for the FAQ injection)
  L10 ownership-contradiction  foreign-ownership % in prose contradicting the record's own
                           pma_max_asing (65111 class, quality-sampler find 2026-07-07).
                           Innocence guards: "N% closed" idiom, "not N%" negation, KSO
                           work-share percentages, documented sector-law overrides.
  L11 editorial-boilerplate  corpus-level: a sentence ≥60 chars appearing verbatim in ≥5
                           editorials (headline/standfirst/body) — the anti-template gate
                           for the LOOP-2 magazine layer (census 2026-07-08 found the old
                           intel prose had 995× / 258× / 88× stock sentences).

Exit 0 = clean (L7 informational only). Exit 1 = findings. --json for machine output.
Usage: python3 scripts/kbli_dataset_lint.py [--json] [--only L1,L3] [--repo ROOT]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------

ITALIAN_MARKERS = re.compile(
    r"\b(riservat[oaie]|chius[oaie]|apert[oaie]|vietat[oaie]|bloccat[oaie]|"
    r"società|attività|sanit[aà]|agricoltur[a]|pesca|commercio|edilizi[oa]|"
    r"consulenza|servizi|stranier[oi]|iscritt[oi]|avvocat[oi]|dipende|richiede|"
    r"gestion[ei]|impres[ae]|settore|primo dei|dal \d{1,2}/)",
    re.IGNORECASE,
)
ENGLISH_MARKERS = re.compile(
    r"\b(the|of|for|and|with|not|is|are|no|scale|risk|foreign|reserved|closed|"
    r"open|under|has|this|to|in Bali|business|license)\b",
    re.IGNORECASE,
)

# Canonical prose date: "13 May 2026". Flag numeric slash forms and ISO-in-prose.
BAD_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")

CODE_REF = re.compile(r"\b(\d{5})\b")
# 5-digit numbers that are usually NOT KBLI references in our prose
NON_CODE_5DIGIT = {"10000", "50000", "20000", "25000", "30000", "40000", "60000"}

# --- L3 / G3 dead-reference machinery (ONE SSOT, shared with the applier) -----
# A 5-digit code outside the 2025 catalogue is a LEGITIMATE reference when the prose
# labels it as a superseded (2020) code. The editorial register uses a wider idiom set
# than the terse enriched fields, so this list is deliberately broad — but every entry
# is a phrase that unambiguously means "this is an OLD code", never a live-code mention.
LABELED_2020_MARKERS = (
    "kbli 2020", "2020 code", "kbli2020", "formerly", "previous code",
    "from kbli 2020", "under kbli 2020", "2020 codes", "2020 origin",
    "predecessor code", "predecessor", "split from", "split from code",
    "used to live under", "used to fall under", "used to sit under",
    "ex-generic", "ex-code", "absorbed", "collapsed", "consolidat",  # consolidat(es/ion)
    "superseded", "replaced code", "old code",
)
# a section-block reference like "the 68000 real-estate block" / "into the 41000 group"
# — NN000 where NN is a real 2-digit KBLI division, framed as a block/group/category.
SECTION_BLOCK_REF = re.compile(
    r"\b(?:into|under|in|the|its?)\s+(?:the\s+)?\d{2}000\b"
    r"[^.]{0,30}?\b(?:block|group|category|division|section|bucket)\b",
    re.IGNORECASE,
)


def l3_dead_ref(text, code, codes):
    """The ONE SSOT for the L3/G3 unlabeled-dead-code guard.

    Returns (ref, ctx) for the FIRST 5-digit reference in `text` that is NOT in the 2025
    catalogue AND not covered by an innocence class, or None. Innocence classes:
      * the subject code itself, or any live 2025 code, or a known non-code constant
      * money / quantity contexts (Rp, m2, …)
      * technical-standard numbers (ISO/IEC/SNI/DIN/EN …)
      * explicitly labeled as a superseded 2020 code (broad idiom set)
      * a comma-list continuation whose head carried a 2020 label ("2020 codes X, Y … Z")
      * a section-block reference ("the 68000 real-estate block")
    """
    for m in CODE_REF.finditer(text):
        ref = m.group(1)
        if ref == code or ref in codes or ref in NON_CODE_5DIGIT:
            continue
        idx = m.start()
        ctx = text[max(0, idx - 24) : idx + 36]
        low_ctx = ctx.lower()
        if any(w in low_ctx for w in ("rp", "idr", "usd", "$", "m2", "sqm", "meter")):
            continue
        std_ctx = text[max(0, idx - 70) : idx].lower()
        if re.search(r"\b(iso(/iec)?|iec|sni|din|en)\b[^.]{0,60}$", std_ctx):
            continue
        # widened label lookbehind (90 chars) — editorial idioms like
        # "kbli 2020 origin: split from code 46421" push the label further back
        before = text[max(0, idx - 90) : idx].lower()
        if any(w in before for w in LABELED_2020_MARKERS):
            continue
        # comma-list continuation: "KBLI 2020 codes 02111, 02112, … 02121 and 02122"
        # — the label sits before the FIRST item; later items inherit it. Detect a run
        # of "<5digits>[,·] " (optionally "and ") immediately preceding this ref, then
        # look for a 2020 label before the whole run.
        run = re.search(r"((?:\d{5}\s*[,·]\s*(?:and\s+|dan\s+)?)+)$", text[max(0, idx - 120) : idx])
        if run:
            run_start = idx - (len(text[max(0, idx - 120) : idx]) - run.start())
            head = text[max(0, run_start - 40) : run_start].lower()
            if any(w in head for w in LABELED_2020_MARKERS):
                continue
        # section-block reference ("the 68000 real-estate block")
        block_win = text[max(0, idx - 20) : idx + 40]
        if re.fullmatch(r"\d{2}000", ref) and SECTION_BLOCK_REF.search(block_win):
            continue
        return ref, ctx.strip()
    return None
# -----------------------------------------------------------------------------

PROSE_FIELDS_INTEL = (
    "whatItMeans",
    "whatYouNeed",
    "whatChanged",
    "zantaraOpener",
    "baliContext",
    "whoThisIsFor",
    "youllAlsoNeed",
    "tkaInfo",
)

L4_OK_TONES = {"OK_or_HIGHER_RISK", "APERTO_BALI_RISCHIO_ALTO"}

# --- L10 ownership-contradiction machinery -----------------------------------
L10_PCT = re.compile(r"\b(\d{1,3})\s?%")
# a % counts as a foreign-OWNERSHIP claim only when ownership intent sits nearby
L10_FOREIGN_CTX = re.compile(
    r"foreign\s+(?:ownership|owner|equity|shareholding|capital|investors?|stake|life\s+insurers?)"
    r"|own(?:ed|s)?\s+up\s+to|can\s+own|max\w*\s+foreign|capped\s+at|\basing\b"
    r"|pma\s+cap|%\s*pma\b|pma\s+\d{1,3}\s?%",
    re.IGNORECASE,
)
# innocence: "100% closed" idiom (the % modifies closed-ness, consistent with TERTUTUP)
L10_CLOSED_IDIOM = re.compile(r"^\s*(?:closed|tertutup)", re.IGNORECASE)
# innocence: "not 100% open" negation
L10_NEG = re.compile(r"\bnot\s*$", re.IGNORECASE)
# innocence: an explicit CAP-DENIAL enumeration in the editorial register — the prose
# lists percentages only to say NONE of them applies ("the record does not impose a
# 67%, 49%, or minority ceiling", "there is no 67% cap here"). A negation verb sits
# before the figure and a cap-noun (ceiling/cap/limit/minority) bounds the clause, so
# the % is being denied, not asserted. Guilt is preserved: "capped at 67%" / "limited
# to 49%" carry NO negation and still flag. Matched against the ~60-char window BEFORE
# the figure (negation) combined with a cap-noun anywhere in the local window.
L10_NEG_CAP_BEFORE = re.compile(
    r"\b(?:no|not|does\s+not|do\s+not|doesn't|don't|isn't|is\s+not|are\s+not|"
    r"never|without|there\s+is\s+no|there's\s+no|free\s+of|absent)\b"
    r"[^.]{0,50}$",
    re.IGNORECASE,
)
L10_CAP_NOUN = re.compile(
    r"\b(?:ceiling|cap(?:ped|s)?|limit(?:ed|s)?|minority|ownership\s+ceiling|"
    r"equity\s+ceiling|restriction)\b",
    re.IGNORECASE,
)
# innocence: KSO construction work-share percentages ("min 50% domestic work",
# "min 30% by national partner") are volume-of-work quotas, not equity (41019 class)
L10_WORK_SHARE = re.compile(r"\b(?:kso|domestic work|construction work|work volume)\b", re.IGNORECASE)
# innocence: historical reference to a superseded cap ("the old 49% cap is gone",
# "no longer capped at 49%") — the prose is explicitly saying the % does NOT apply.
# Checked BOTH sides of the number: the marker may sit before ("the old 49%") OR
# after ("a 49% cap ... old briefing / hangover / that ceiling closed") in the
# longer editorial register.
L10_HISTORICAL = re.compile(
    r"\b(?:old|former(?:ly)?|no longer|pre-\d{4}|previous(?:ly)?|used to be)\b", re.IGNORECASE
)
# same intent, phrased as a myth being debunked AFTER the figure — editorial voice
# ("still hear about a 49% cap … working from an old briefing", "the 49% … hangover",
# "that ceiling closed"). Scanned in the window that follows the %.
L10_HISTORICAL_AFTER = re.compile(
    r"\b(?:old\s+briefing|hangover|ceiling\s+closed|no\s+longer\s+applies|"
    r"is\s+gone|was\s+lifted|has\s+been\s+lifted|scrapped|superseded|"
    r"still\s+hear\s+about|myth|outdated)\b",
    re.IGNORECASE,
)
# innocence: the % is a BALI / regional cap (the l4_bali layer), measured against
# l4_bali.reason — NOT the national pma_max_asing. The Navigator's whole point is to
# state a regional restriction on top of a nationally-open code ("Bali caps foreign
# equity at 67%", "on the ground in Bali … capped at 49%"). Without this, every
# documented L4 cap reads as a national-ownership contradiction (scar family #3).
L10_REGIONAL_CAP = re.compile(
    r"\b(?:bali|island|islandwide|island-wide|province|provincial|regional|regency|"
    r"regensi|local\s+regime|on\s+the\s+ground|l4)\b"
    # a regional regime phrased as "layered on top of the national OSS system" is the
    # same L4-cap fact without the word "Bali" in the immediate window
    r"|regime\b[^.]{0,60}?\blayered\s+on\s+top\b"
    r"|\blayered\s+on\s+top\s+of\s+the\s+national\b",
    re.IGNORECASE,
)
# innocence: an "in practice" / no-tier-to-register figure is a lived operational
# reality distinct from the national OSS ceiling ("100% on paper, but 0% in practice —
# no Usaha Besar tier for a PT PMA to register against"). The record itself carries the
# same note (pma_nota / l4 reason), so this is a documented divergence, not a mis-statement.
L10_IN_PRACTICE = re.compile(
    r"\bin\s+practice\b|\bno\s+(?:usaha\s+)?besar\s+(?:scale\s+)?(?:tier|row|scale)\b"
    r"|\bno\s+tier\s+(?:for\s+a\s+pt\s+pma\s+)?to\s+register\b",
    re.IGNORECASE,
)
# innocence: the % is scoped to a DIFFERENT, adjacent code referenced by word/pronoun
# rather than a 5-digit number ("a code fully open to 100%", "that code is fully open,
# 100%", "the route … uses"). The subject-code claim ("this code/activity is open to
# 100%") is deliberately NOT matched here, so a genuine self-contradiction still flags.
L10_ADJACENT_STEER = re.compile(
    r"\b(?:a|an|another|whichever|its\s+own)\s+code\b[^.]{0,40}$"
    r"|\bthat\s+code\b[^.]{0,40}$"
    r"|\bopen\s+code\b[^.]{0,40}$"
    r"|\bthe\s+route\b[^.]{0,40}$",
    re.IGNORECASE,
)
# Documented sector-law overrides: prose legitimately states a % that diverges from
# the OSS catalogue because a SECTOR law outside OSS caps ownership, and the prose
# explains that divergence explicitly (same pattern as L9 69101 Advocates).
#   65111 Life insurance — PP 14/2018 (amended PP 3/2020) caps foreign ownership at
#   80% for non-listed insurers; catalogue records 100 at the risk-based layer.
L10_SECTOR_LAW_OVERRIDE = {"65111"}


def l10_ownership_contradiction(text, code, maxa, maxa_by_code):
    """The ONE SSOT for the L10 ownership-vs-pma_max_asing guard.

    Returns (val, window) for the FIRST genuine contradiction in `text`, or None if
    every foreign-ownership % in the prose is either consistent with `maxa` or covered
    by a documented innocence class. Both the lint's L10 rule and the applier's G4 gate
    call this so guilt/innocence can never drift between them (scar family #3: a guard
    with two copies hardens one and forgets the other).

    Innocence classes (each a real, verified pattern in the KBLI editorials):
      * value equals the national ceiling                    (not a contradiction)
      * "100% closed / tertutup" idiom                        (% modifies closed-ness)
      * "not <n>% open" negation
      * historical marker before OR after the figure          (old cap, now gone)
      * KSO construction work-share quota                      (volume, not equity)
      * BALI / regional cap                                    (l4_bali layer, not national)
      * % scoped to a named/deictic OTHER code                 (adjacent-code steering)
      * cross-ref to another code whose own pma_max_asing == val
    Guilt is preserved: a subject-code self-claim ("this code is fully open to 100%")
    that diverges from `maxa` is NOT exonerated by any class above.
    """
    if maxa is None or code in L10_SECTOR_LAW_OVERRIDE:
        return None
    for m in L10_PCT.finditer(text):
        val = int(m.group(1))
        if val == maxa:
            continue
        after = text[m.end() : m.end() + 12]
        if L10_CLOSED_IDIOM.match(after):
            continue
        if L10_NEG.search(text[max(0, m.start() - 6) : m.start()]):
            continue
        # cap-denial enumeration: negation verb before the figure AND a cap-noun in the
        # local window ("does not impose a 67%, 49%, or minority ceiling")
        before_neg = text[max(0, m.start() - 60) : m.start()]
        neg_cap_win = text[max(0, m.start() - 60) : m.end() + 40]
        if L10_NEG_CAP_BEFORE.search(before_neg) and L10_CAP_NOUN.search(neg_cap_win):
            continue
        if L10_HISTORICAL.search(text[max(0, m.start() - 40) : m.start()]):
            continue
        after_win = text[m.end() : m.end() + 80]
        if L10_HISTORICAL_AFTER.search(after_win) or L10_HISTORICAL_AFTER.search(
            text[max(0, m.start() - 40) : m.start()]
        ):
            continue
        win = text[max(0, m.start() - 80) : m.end() + 80]
        if L10_WORK_SHARE.search(win):
            continue
        # BALI / regional cap: the figure is the l4_bali restriction, not national max
        if L10_REGIONAL_CAP.search(win):
            continue
        # "in practice" / no-Besar-tier operational figure — documented divergence
        # from the national OSS ceiling, not a contradiction of it
        if L10_IN_PRACTICE.search(win):
            continue
        before_clause = text[max(0, m.start() - 50) : m.start()]
        # adjacent-code steering by word/pronoun ("a code … open to 100%")
        if L10_ADJACENT_STEER.search(before_clause):
            continue
        # cross-ref: the % describes ANOTHER named code and matches THAT code's max.
        # Window is a full recent sentence (~140 chars) so a pronoun subject whose
        # antecedent is a named sibling one sentence back is exonerated
        # ("That separate code is 85312 … It is fully open to 100%"), while a BARE
        # self-claim with no nearby named sibling ("It is fully open to 100%") is not.
        ref_window = text[max(0, m.start() - 140) : m.start()]
        ref_codes = re.findall(r"\b(\d{5})\b", ref_window)
        if any(rc != code and maxa_by_code.get(rc) == val for rc in ref_codes):
            continue
        if L10_FOREIGN_CTX.search(win):
            return (val, win)
    return None


# -----------------------------------------------------------------------------


def looks_italian(text: str) -> bool:
    if not text:
        return False
    it = len(ITALIAN_MARKERS.findall(text))
    en = len(ENGLISH_MARKERS.findall(text))
    return it > 0 and it >= en


def iter_prose(rec: dict):
    l4 = rec.get("l4_bali") or {}
    if isinstance(l4, dict) and l4.get("reason"):
        yield "l4_bali.reason", str(l4["reason"])
    intel = rec.get("intel_2026") or {}
    if isinstance(intel, dict):
        for f in PROSE_FIELDS_INTEL:
            v = intel.get(f)
            if isinstance(v, str) and v.strip():
                yield f"intel_2026.{f}", v
        # LOOP-2 editorial layer — same rules apply (L1/L3/L4/L10)
        ed = intel.get("editorial")
        if isinstance(ed, dict):
            for f in ("headline", "standfirst", "body", "pullQuote"):
                v = ed.get(f)
                if isinstance(v, str) and v.strip():
                    yield f"intel_2026.editorial.{f}", v
            for i, n in enumerate(ed.get("byTheNumbers") or []):
                if isinstance(n, dict):
                    # label+value joined so context guards (L3 labeled-2020, L10
                    # cross-ref) can see the label the value belongs to
                    yield (
                        f"intel_2026.editorial.byTheNumbers[{i}]",
                        f"{n.get('label', '')}: {n.get('value', '')}",
                    )
    if rec.get("pma_nota"):
        yield "pma_nota", str(rec["pma_nota"])


def parse_english_titles(ts_path: Path) -> set[str]:
    """Extract code keys from kbli-english.ts ENGLISH_TITLES map."""
    text = ts_path.read_text(encoding="utf-8")
    return set(re.findall(r'^\s*"(\d{5})":', text, re.MULTILINE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument(
        "--repo", default=str(Path(__file__).resolve().parents[1]), help="repo root"
    )
    args = ap.parse_args()
    root = Path(args.repo)
    only = {s.strip().upper() for s in args.only.split(",") if s.strip()}

    def enabled(rule: str) -> bool:
        return not only or rule in only

    dataset_path = root / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    english_path = root / "apps/mouth/src/lib/kbli-english.ts"
    english_gen_path = root / "apps/mouth/src/lib/kbli-english-generated.ts"

    data = json.loads(dataset_path.read_text(encoding="utf-8"))["data"]
    codes = {r["kode_kbli_2025"] for r in data}
    # L10 cross-ref guard: prose may state ANOTHER code's ownership ("47192 is 100% open")
    maxa_by_code = {
        r["kode_kbli_2025"]: r.get("pma_max_asing")
        for r in data
        if isinstance(r.get("pma_max_asing"), int)
    }
    en_titles = parse_english_titles(english_path) if english_path.exists() else set()
    if english_gen_path.exists():
        en_titles |= parse_english_titles(english_gen_path)

    findings: list[dict] = []

    def add(rule: str, code: str, field: str, detail: str):
        findings.append({"rule": rule, "code": code, "field": field, "detail": detail})

    sys.path.insert(0, str(root / "scripts"))
    try:
        from kbli_enrich_validate import validate_risk_consistency  # type: ignore
    except Exception:
        validate_risk_consistency = None
    try:
        from kbli_enrich_validate import validate_pma_consistency  # type: ignore
    except Exception:
        validate_pma_consistency = None

    for rec in data:
        code = rec["kode_kbli_2025"]
        l4 = rec.get("l4_bali") or {}

        for field, text in iter_prose(rec):
            if enabled("L1") and looks_italian(text):
                add("L1", code, field, text[:90])
            if enabled("L4"):
                for m in BAD_DATE.findall(text):
                    add("L4", code, field, m)
            if enabled("L3"):
                hit = l3_dead_ref(text, code, codes)
                if hit:
                    ref, ctx = hit
                    add("L3", code, field, f"{ref} :: …{ctx}…")

        if enabled("L8"):
            reason = str(l4.get("reason") or "")
            if reason and looks_italian(reason):
                add("L8", code, "l4_bali.reason", reason[:90])

        if enabled("L2") and code not in en_titles:
            add("L2", code, "kbli-english.ts", "no curated English title")

        if enabled("L5"):
            pma = str(rec.get("pma_status") or "").upper()
            if pma == "TERTUTUP" and str(l4.get("status")) in L4_OK_TONES:
                add("L5", code, "l4_bali.status", f"national TERTUTUP but l4={l4.get('status')}")

        if enabled("L6") and validate_risk_consistency is not None:
            intel = rec.get("intel_2026") or {}
            if isinstance(intel, dict) and intel:
                for err in validate_risk_consistency(intel, rec):
                    add("L6", code, "intel_2026", err[:120])

        if enabled("L9") and validate_pma_consistency is not None:
            # Documented profession-law overrides: the catalogue says TERBUKA but a
            # sector law closes the PROFESSION to foreigners, and the prose says so
            # explicitly and correctly. These are features, not contradictions.
            #   69101 Advocates — UU 18/2003 (PERADI membership, WNI-only)
            L9_PROFESSION_OVERRIDE = {"69101"}
            intel = rec.get("intel_2026") or {}
            if isinstance(intel, dict) and intel and code not in L9_PROFESSION_OVERRIDE:
                for err in validate_pma_consistency(intel, rec):
                    add("L9", code, "intel_2026", err[:120])

        if enabled("L10") and code not in L10_SECTOR_LAW_OVERRIDE:
            maxa = rec.get("pma_max_asing")
            if isinstance(maxa, int):
                for field, text in iter_prose(rec):
                    hit = l10_ownership_contradiction(text, code, maxa, maxa_by_code)
                    if hit:
                        val, win = hit
                        add(
                            "L10", code, field,
                            f"prose says {val}% but pma_max_asing={maxa} :: …{win.strip()[:100]}…",
                        )

        if enabled("L7") and not rec.get("per_skala"):
            add("L7", code, "per_skala", "no scale rows (special regime?)")

    # L11 — corpus-level boilerplate across editorial fields (needs the whole
    # corpus, so it runs after the per-record loop)
    if enabled("L11"):
        sent_owners: dict[str, list[str]] = {}
        for rec in data:
            ed = (rec.get("intel_2026") or {}).get("editorial")
            if not isinstance(ed, dict):
                continue
            seen_in_rec: set[str] = set()
            for f in ("headline", "standfirst", "body"):
                t = ed.get(f) or ""
                for s in re.split(r"(?<=[.!?])\s+", t):
                    s = s.strip()
                    if len(s) >= 60 and s not in seen_in_rec:
                        seen_in_rec.add(s)
                        sent_owners.setdefault(s, []).append(rec["kode_kbli_2025"])
        for s, owners in sent_owners.items():
            if len(owners) >= 5:
                add(
                    "L11", ",".join(owners[:8]) + ("…" if len(owners) > 8 else ""),
                    "intel_2026.editorial", f"{len(owners)}× :: {s[:90]}",
                )

    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1

    if args.json:
        print(json.dumps({"counts": by_rule, "findings": findings}, ensure_ascii=False))
    else:
        print(f"KBLI dataset lint — {len(data)} codes")
        for rule in sorted(by_rule):
            print(f"  {rule}: {by_rule[rule]}")
        blocking = [f for f in findings if f["rule"] not in ("L7", "L2")]
        print(f"\nblocking findings (non-L2/L7): {len(blocking)}")
        for f in blocking[:40]:
            print(f"  [{f['rule']}] {f['code']} {f['field']}: {f['detail']}")

    return 1 if any(r not in ("L7",) for r in by_rule) else 0


if __name__ == "__main__":
    sys.exit(main())
