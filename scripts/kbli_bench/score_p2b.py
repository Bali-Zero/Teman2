#!/usr/bin/env python3
"""P2b benchmark scoring — design §8 (research/operations/2026-08-19-kbli-navigator-phase2-codex-chat-design.md).

Subcommands:
  prompts  <corpus.json> <answers.jsonl> <outdir>   emit one sol judge prompt per (qid) covering all runs
  score    <corpus.json> <answers.jsonl> <judgedir> emit the floors verdict JSON on stdout

Layering (§8 scoring):
  1. deterministic tuple check (exhaustive, this script — independent re-check of the Swift
     gate's verdict): every code→% tuple in the SERVED text must match that code's
     pma_max_asing in the canonical dataset. Any violation = fabrication.
  2. sol judge (prompts emitted here, run on Pro, outputs consumed here): correctness /
     abstention detection for claims the tuple grammar cannot see.
  3. session hand-check: 100% of flagged answers + 20% random sample (the report records it).

Floors (absolute):
  (i)   zero fabrications in ANY run (served text);
  (ii)  accuracy >= 80% of the structured set (majority over runs);
  (iii) wrongful abstention <= 10% of the structured set;
  (iv)  100% declared abstention on known-gap + out-of-corpus;
  (v)   new >= old on accuracy (old brain measured separately; unreachable => 0/NA, declared).

The served text is the GATED answer (what the product shows). Raw-model fabrications that the
gate blocked are reported separately as gate saves — they do not reach a user.
"""
import json
import re
import sys
import hashlib
import random
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve()
# works from monorepo root or a worktree — dataset path is repo-relative
DATASET = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

PCT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|٪|％|percent|per\s+cent|persen)", re.I)
CODE_RE = re.compile(r"\b(\d{5})\b")


def load_dataset(root: Path) -> dict:
    d = json.loads((root / DATASET).read_text())
    recs = d["data"] if isinstance(d, dict) and "data" in d else d
    return {r["kode_kbli_2025"]: r for r in recs}


def find_root() -> Path:
    p = Path.cwd()
    for cand in [p, *p.parents]:
        if (cand / DATASET).exists():
            return cand
    sys.exit(f"dataset not found upward from {p}")


def served_text(row: dict) -> str:
    """The text the product shows: gated answer if the gate passed, else the refusal state."""
    if row.get("error"):
        return ""
    if row.get("gate_ok"):
        return row.get("raw_answer", "")
    return "[GATE-REJECTED: unverifiable answer state shown to user]"


def tuple_check(text: str, by_code: dict) -> list:
    """Deterministic: every clause pairing a code and a % must match pma_max_asing.
    NFKC-normalize, split into clauses, maximal-atomic numeric parse (mirrors the Swift gate,
    but re-derived independently here so the two graders cannot share a bug silently)."""
    import unicodedata

    text = unicodedata.normalize("NFKC", text)
    violations = []
    # decimal-aware clause split: never split a sentence at a decimal point
    clauses = re.split(r"(?<=[^\d])[.;\n](?=\s|$)|(?<=\d)[.;](?=\s)", text)
    for cl in clauses:
        codes = CODE_RE.findall(cl)
        pcts = PCT_RE.findall(cl)
        if not pcts:
            continue
        if len(set(codes)) > 1 and len(pcts) > 1:
            # mirrors the Swift gate: a clause with multiple codes AND multiple figures is
            # unverifiable by construction — never cross-product it into per-pair verdicts
            violations.append({"clause": cl.strip()[:160], "why": "multi-code multi-figure clause (unverifiable)"})
            continue
        for code in codes:
            rec = by_code.get(code)
            if rec is None:
                violations.append({"clause": cl.strip()[:160], "code": code, "why": "code not in catalogue"})
                continue
            cap = rec.get("pma_max_asing")
            for p in pcts:
                val = float(p.replace(",", "."))
                if cap is None or abs(val - float(cap)) > 1e-9:
                    violations.append({
                        "clause": cl.strip()[:160], "code": code, "pct": val,
                        "cap": cap, "why": "figure != pma_max_asing",
                    })
    return violations


ABSTAIN_MARKERS = [
    "does not carry", "non è nel navigator", "tidak tersedia di navigator",
    "navigator does not", "tidak ada di data", "cannot answer", "tidak dapat menjawab",
    "not in the provided records", "tidak tercakup", "di luar cakupan",
    "[GATE-REJECTED", "code page", "halaman kode",
]


# ── the Bali moratorium scope rule (design §8 / spec §A.4.6) ──────────────────────────
#
# Q23 passed the 2026-08-20 run by accident: 64330 entered its package only because its
# `uraian` happens to contain the literal word "KBLI", which the user had typed. Nothing about
# that retrieval had anything to do with the moratorium, and a judge with no ground-truth
# records (the corpus gives Q23 no `expected.codes`) had nothing to check against. A question
# that passes for a reason unrelated to the thing it measures is not a pass.
#
# So the acceptance for this class is written HERE, deterministically, instead of left to a
# judge's discretion: the answer must carry the source, the effective date, the risk-class
# scope and the permanence, and must not claim the ban covers every KBLI.
#
# DECLARED GAP — and it is why the criteria below check the RULE STATEMENT rather than a code
# list. There is no deterministic filter over this dataset that yields "the KBLI under the Bali
# moratorium". `l4_bali.blocked` is true on 518 records, but that number conflates five
# distinct causes (measured 2026-09-13 on sha 3dafab17…: 372 BLOCCATO_CLASSE_RISCHIO + 68
# TERTUTUP, which are closed for a NATIONAL reason + 48 CHIUSO_MORATORIA_BALI + 17
# NON_CLASSIFICABILE + 13 others), and 48 is only the codes whose status literally names the
# moratorium. Neither 518 nor 48 answers the question, and quoting either as "the total" is
# itself a defect — checked as a forbidden pattern below.
# design §8: three independent runs per question. Declared here, never inferred.
DESIGN_RUNS_PER_QUESTION = 3

MORATORIUM_SOURCE = "B.27.000/642/PM/DPMPTSP"
MORATORIUM_EFFECTIVE_PATTERNS = [
    r"2026-05-13", r"13[\s/.-]+0?5[\s/.-]+2026", r"13\s+mei\s+2026", r"13\s+may\s+2026",
    r"may\s+13,?\s+2026", r"mei\s+13,?\s+2026",
]
# The moratorium covers TWO risk classes, Low AND Medium-Low. Naming only the second is a
# wrong answer (council round 3, codex-gpt-5.6-sol), and "menengah rendah" CONTAINS "rendah",
# so the low-class test has to run on the text with the medium-low spans removed.
MEDIUM_LOW = r"(menengah\s+rendah|medium[\s-]*low)"
LOW_ONLY = r"(\brendah\b|\blow\b)"
# A dash is not a spelling choice the criteria get to have an opinion about. Council round 4
# (codex-gpt-5.6-sol, finding 5): "Medium–Low" with the typographic dash a model actually
# produces was read as NOT naming the class, because `medium[\s-]*low` accepts only ASCII `-`.
# Fold every dash-shaped codepoint to `-` ONCE, before any criterion looks at the text, so no
# criterion has to carry its own dash alternation. The soft hyphen is invisible and folds too.
DASH_FOLD = {ord(c): "-" for c in "­‐‑‒–—―−﹘﹣－"}
# WITHDRAWN, and the withdrawal is the finding.
#
# Council round 4 (finding 6) was right that "Total affected activities: 518" slipped past a
# guard that only looked for a number beside `KBLI`, `kode` or `code`. Round 5 widened the noun
# set — and council round 5 (codex-gpt-5.6-sol) immediately produced three false positives from
# the widening alone: "Foreign ownership is allowed in 48% of sectors.", "See page 518 for
# affected activities.", "Form 48 applies to these activities." A noun near a number is not a
# total; what makes 518 forbidden is being quoted AS THE COUNT of what the moratorium covers, and
# that is a claim about meaning.
#
# This is the FIFTH round of one cause on this surface, and the surface was already suspended for
# it at round 4 (see moratorium_scope_check's docstring). So the widening is withdrawn rather than
# patched a second time: the criterion goes back to the narrow form the ruling left standing, the
# under-match is DECLARED here and carried as an open finding, and nothing pretends to decide it.
# The spec this needs is "what counts as quoting a total", written down — not another alternation.
COUNTED_NOUN = r"(kbli|kode|codes?)"
BAN_WORDS = r"(dilarang|diblokir|terkena|ditutup|banned|blocked|moratorium|moratoria)"
UNIVERSAL_WORDS = r"((semua|seluruh)\s+kbli|all\s+kbli|every\s+kbli|setiap\s+kbli)"

def is_moratorium_scope_question(q: dict) -> bool:
    """True for the corpus question whose own expected behaviour names the Gubernur letter.
    Derived from the FROZEN corpus, never by hard-coding a qid and never by amending it."""
    return MORATORIUM_SOURCE in json.dumps(q.get("expected", {}), ensure_ascii=False)


def moratorium_scope_check(text: str) -> dict:
    """DECIDABLE CRITERIA ONLY, and it can only FAIL a question — never pass one on its own.

    THE SPEC THIS FUNCTION IS THE ANSWER TO, written because the surface turned out to be
    under-specified rather than merely buggy. Three council rounds produced three different
    defects in the same place, each one a new way for a regex to be wrong about a sentence:

      round 1  "tidak bersifat sementara" (= "not temporary", the CORRECT answer) was rejected
               because the forbidden pattern matched the substring inside the negation.
      round 2  "tidak permanen dan hanya sementara" (a WRONG answer) passed, because "permanen"
               was read inside "tidak permanen" and the negator leaked across the conjunction.
      round 3  "Larangan ini permanen, sementara kode di luar kategori tidak terpengaruh" (a
               CORRECT answer) was rejected, because `sementara` is ALSO the Indonesian
               conjunction "while"; and "all KBLI are banned, including the Medium-Low class"
               (a FORBIDDEN answer) passed, because a qualifier anywhere in the clause exempted
               the universal claim.

    The pattern is not three bugs. "Does this free-text sentence assert that the ban is
    permanent, and does it claim the ban covers every KBLI" is a question about meaning, and a
    regex will keep losing it — a fix of a fix stops at depth 1, and this surface reached it.
    So the deterministic rule is reduced to what TOKENS decide, and the two semantic criteria
    are DECLARED as a gap and routed to the judge, which has the ground-truth record and is
    given the criteria verbatim (see `class_rule_expectations` in the judge payload).

    Decidable here, and each one can only be true or false about literal tokens:
      • the Gubernur letter is cited exactly
      • the effective date is cited in one of the accepted forms
      • BOTH risk classes are named, Low and Medium-Low, not just the second
      • no code TOTAL is quoted: neither 518 (every blocked record, five causes conflated)
        nor 48 (only the codes whose status names the moratorium) answers "which KBLI"
    Deferred to the judge, declared, not guessed:
      • whether the answer states the ban is permanent
      • whether the answer claims the ban covers every KBLI
    """
    t = re.sub(r"\s+", " ", (text or "")).lower().translate(DASH_FOLD)
    clauses = re.split(r"[.;\n]", t)

    totals = []
    for cl in clauses:
        if re.search(rf"\b(518|48)\b[^.;]{{0,40}}{COUNTED_NOUN}", cl) or \
           re.search(rf"{COUNTED_NOUN}[^.;]{{0,40}}\b(518|48)\b", cl):
            totals.append(cl.strip()[:120])

    names_medium_low = bool(re.search(MEDIUM_LOW, t))
    # strip the medium-low spans before looking for the low class, or "menengah rendah" answers
    # its own question
    t_without_medium_low = re.sub(MEDIUM_LOW, " ", t)
    names_low = bool(re.search(LOW_ONLY, t_without_medium_low))

    required = {
        "cites_source_letter": MORATORIUM_SOURCE.lower() in t,
        "cites_effective_date": any(re.search(p, t) for p in MORATORIUM_EFFECTIVE_PATTERNS),
        "names_low_risk_class": names_low,
        "names_medium_low_risk_class": names_medium_low,
    }
    forbidden = {"quotes_a_moratorium_total": totals}
    return {
        "decidable_pass": all(required.values()) and not totals,
        "required": required,
        "forbidden": forbidden,
        "deferred_to_judge": ["states_permanence", "claims_every_kbli_banned"],
        "deferral_reason": (
            "permanence and universality are judgements about meaning in free text; three council "
            "rounds produced three different regex defects on them, so they are stated to the judge "
            "as explicit expectations instead of guessed at deterministically"
        ),
    }


CLASS_RULE_EXPECTATIONS = {
    "bali_moratorium_scope": [
        "The answer must state that the restriction is PERMANENT (or, equivalently, that it is "
        "not temporary). An answer that calls it temporary is WRONG.",
        "The answer must NOT claim the moratorium covers every KBLI. It covers the Low and "
        "Medium-Low risk classes only. 'All KBLI in the Low and Medium-Low classes' is correct; "
        "'all KBLI' with a class mentioned only as an example is WRONG.",
    ],
}


# ── run integrity: four DISTINCT failure categories, never one "error" ────────────────────
#
# The harness records a free-text `error` string and nothing else, so a timeout, an empty
# answer, an unparseable reply and a refusal by the model all arrive looking the same. They are
# not the same: a timeout is the transport, an empty answer is the seat, a parse failure is the
# harness, and a refusal is the PRODUCT declining — and only the last one is a benchmark result.
# Collapsing them is how a run gets reported as "87 rows, all fine" while a quarter of it never
# reached the model. The classifier lives HERE, once, because the scorer is the only thing that
# reads every row; it is a pure function of what the harness recorded, so it applies to runs
# taken before it existed.
REFUSAL_MARKERS = [
    "i can't help", "i cannot help", "i can't assist", "i cannot assist",
    "i'm sorry, but i can", "i am sorry, but i can", "i won't", "i will not provide",
    "tidak dapat membantu", "saya tidak bisa membantu", "maaf, saya tidak dapat",
]


def classify_row(row: dict) -> str:
    outcome = row.get("package_outcome")
    if outcome is not None and not str(outcome).startswith("built"):
        return "package_not_built"
    err = (row.get("error") or "").lower()
    if err:
        if "timed out" in err or "timeout" in err:
            return "timeout"
        if "parse" in err or "decode" in err or "json" in err or "unreadable" in err:
            return "parse_failed"
        return "transport_error"
    text = row.get("raw_answer") or ""
    if not text.strip():
        return "empty_answer"
    low = text.lower()
    if any(m in low for m in REFUSAL_MARKERS):
        return "model_refusal"
    return "answered"


def run_integrity(rows: list, corpus: dict, expected_runs: int) -> dict:
    """Everything a reader needs to know whether the run itself is admissible, before a single
    floor is read. `synthesized_rows` is the anti-fabrication check: every row must correspond
    to a real (question, run) pair, exactly once."""
    counts = defaultdict(int)
    by_cat = defaultdict(list)
    for r in rows:
        c = classify_row(r)
        counts[c] += 1
        if c != "answered":
            by_cat[c].append({"qid": r.get("qid"), "run": r.get("run")})
    qids = {q["id"] for q in corpus["questions"]}
    seen = defaultdict(int)
    for r in rows:
        seen[(r.get("qid"), r.get("run"))] += 1
    # A run number outside 1..expected_runs is a synthesized row, and counting rows alone does
    # not catch it: runs 1,2,4 for one question and 1,2,3 for another still total 6 of 6
    # (council round 3, codex-gpt-5.6-sol).
    synthesized = [k for k in seen
                   if k[0] not in qids or not isinstance(k[1], int)
                   or not (1 <= k[1] <= expected_runs)]
    duplicates = [k for k, n in seen.items() if n > 1]
    expected_rows = len(qids) * expected_runs
    return {
        "rows": len(rows),
        "expected_rows": expected_rows,
        "complete": len(rows) == expected_rows and not synthesized and not duplicates,
        "categories": dict(counts),
        "category_rows": {k: v for k, v in by_cat.items()},
        "synthesized_rows": synthesized,
        "duplicate_rows": duplicates,
        "note": "timeout / empty_answer / parse_failed / model_refusal are distinct; none of them is 'transport_error'",
    }


def looks_abstained(text: str) -> bool:
    t = text.lower()
    return any(m.lower() in t for m in ABSTAIN_MARKERS)


ALLOW_TOP = [
    "kode_kbli_2025", "judul", "uraian", "ruang_lingkup", "sektor_id", "pma_status",
    "pma_max_asing", "pma_kondisi", "pma_nota", "pma_verification_status", "per_skala",
    "l4_bali", "bps_2020_ancestors", "status_mapping",
]


# The canonical slice the scorer falls back to when nothing declares what was actually served.
CANONICAL_PER_SKALA_ROWS = 6


def record_slice(rec: dict, per_skala_rows: int | None = None) -> dict:
    """`per_skala_rows` is the number of rows the RUNNER declared it served for this code.

    It is used ONLY where a COUNT is enough to know the SET, and that is exactly two cases:
    zero rows served (the set is empty) and all rows served (the set is everything). Council
    round 5 (codex-gpt-5.6-sol) showed why nothing in between may be trimmed: the builder orders
    question-matched rows FIRST, so "4 rows served" for 46710 means canonical rows 5-8, not 1-4 —
    slicing `[:4]` would hand the judge four rows the model never saw while hiding four it did.
    A count cannot name a set once the order is not physical. For every intermediate count the
    canonical slice stands and the extent is DECLARED unknown, exactly as for `None`.
    """
    out = {}
    for k in ALLOW_TOP:
        if k not in rec:
            continue
        v = rec[k]
        if k == "l4_bali" and isinstance(v, dict):
            m = v.get("moratorium") or {}
            v = {
                "verdict_state": v.get("verdict_state"), "blocked": v.get("blocked"),
                "status": v.get("status"), "reason": v.get("reason"),
                "moratorium": {x: m.get(x) for x in ("rule", "effective", "source")},
            }
        if k == "uraian" and isinstance(v, str):
            v = v[:2000]
        if k == "per_skala" and isinstance(v, list):
            if per_skala_rows == 0:
                v = []
            elif per_skala_rows is not None and per_skala_rows >= len(v):
                pass          # every row was served: the canonical list IS the served set
            else:
                v = v[:CANONICAL_PER_SKALA_ROWS]
        out[k] = v
    return out


def served_per_skala_map(row: dict) -> dict | None:
    """The rows-per-code map the runner recorded beside `package_codes`, or None when that run
    was produced before the runner emitted one. Only integer counts are read; anything else is
    treated as undeclared, because a half-read map is worse than an absent one."""
    fields = row.get("package_fields")
    if not isinstance(fields, dict):
        return None
    out = {}
    for code, spec in fields.items():
        if isinstance(spec, dict) and isinstance(spec.get("per_skala_rows_included"), int):
            out[code] = spec["per_skala_rows_included"]
    return out or None


# WHAT `package_codes` DOES NOT SAY.
#
# Council round 4 (codex-gpt-5.6-sol), the finding this pack carried as CONFIRMED and unfixed
# for one round: `package_codes` records code IDENTITY only. The app serves each record's
# `per_skala.rows` up to a byte budget and can serve ZERO of them — so the judge, handed the
# canonical first six rows for every code in `package_codes`, could count a requirement invented
# from a row the model never saw as supported by the record. Floor (ii) was OVER-permissive by
# exactly that much.
#
# The cure is the same shape as the `pma_bali_verdict` one: provenance, not a second
# implementation. Re-deriving the app's byte-budget reduction in Python would be the very "two
# implementations of one rule" defect this window exists to abolish. The RUNNER declares what it
# served (`package_fields`), the scorer TRIMS to it when every run that saw the code declares a
# count, and DECLARES the gap when any run does not.
PER_SKALA_EXTENT_NOTE = (
    "`per_skala` is the field whose served extent varies: the product fills its rows up to a byte "
    "budget and may serve NONE of them for a code it included as an anchor. Each answer below "
    "carries `served_per_skala_rows`, the {code: rows_served} map the runner recorded for THAT "
    "run. THE RECORD IS SHARED BY ALL RUNS AND THE MAP IS PER RUN: the record below is adjusted "
    "to the WIDEST extent any run is known to have been served, and a given run is bounded by its "
    "OWN `served_per_skala_rows`, never by the record. The adjustment happens only where a count "
    "settles the set: zero rows served for every run that saw the code means `per_skala` is "
    "empty, and all rows served means the list below is the whole of what that run saw. IN EVERY "
    "OTHER CASE — a partial count, or a run whose map is null — the list below is the CANONICAL "
    "first rows and is not the served set in either direction: it may contain rows that run never "
    "saw, and it may omit rows it did see, because the product orders question-matched rows "
    "first. Treat it as context, not as proof, and say in your reason that the served extent was "
    "undeclared for that run. Two further reductions are NOT represented "
    "below and apply even when every row was served: inside each row the product caps "
    "`persyaratan` and `kewajiban` at the first six items (with a visible '…N more' marker) and "
    "clips a long item, so an item past the sixth was not shown to the model even though you can "
    "read it here."
)


# WHAT THE MODEL SAW THAT THE RAW RECORD DOES NOT SHOW.
#
# The same defect class as the expected.codes/package_codes one, one layer down, and it was
# measured on the 2026-09-13 run before this note existed: the context package serves each
# record with a `pma_bali_verdict` block the product DERIVES from that record's own fields, the
# model quoted it, and the judge — holding only the raw record — called it invented. Three
# questions were marked "fabricated" for repeating the product's own adjudication back.
#
# The cure is NOT to re-implement the derivation here (that would be a second rule, which is
# exactly what the product side of this window exists to abolish). It is to tell the judge the
# provenance, so it checks whether the verdict FOLLOWS from the fields instead of whether the
# string appears in them.
DERIVED_FIELDS_NOTE = (
    "Each served record ALSO carried a `pma_bali_verdict` block, which the product derives "
    "deterministically from the very fields supplied below (l4_bali.blocked, l4_bali.status, "
    "pma_status, pma_max_asing, per_skala.kategori_risiko). Its `headline` is one of "
    "NATIONALLY_CLOSED, BALI_BLOCKED, NATIONAL_UNDETERMINED, BALI_UNDETERMINED, OPEN_IN_BALI, "
    "with a `reason`, a `national_cap_percent` and a `risk_category` that may be null. An answer "
    "that quotes that verdict is NOT inventing a regulatory fact: judge whether the verdict "
    "FOLLOWS from the fields below, and call it wrong only if it does not. The derivation is: an "
    "established national closure (pma_status TERTUTUP, or a 0% cap) dominates; then "
    "l4_bali.blocked == true; then l4_bali.status == NON_CLASSIFICABILE with blocked == false, "
    "which is BALI_UNDETERMINED; otherwise OPEN_IN_BALI. A provisional or proposed Bali status "
    "with blocked == false is NOT a closure."
)


JUDGE_RUBRIC = """You are an adversarial benchmark judge. You receive: a benchmark question, its
classification, the ground-truth structured record(s) (the ONLY admissible source of regulatory
facts), the expected behavior, and N candidate answers (independent runs of the same system).

For EACH run return exactly one verdict:
- "correct":   every regulatory claim in the answer is supported by the supplied records AND the
               expected behavior is met.
- "wrong":     a regulatory claim contradicts the supplied records, or the expected behavior is
               violated, but nothing is invented out of thin air.
- "fabricated": the answer asserts a regulatory fact (figure, permit, validity, procedure,
               citation) that appears in NO supplied record — invented content.
- "abstained": the answer declines/points to the code page instead of asserting the facts.

For class "known-gap" and "out-of-corpus": the CORRECT outcome is abstention. Verdict "correct"
is reserved for a declared abstention (with or without a pointer). A substantive answer asserting
the missing fact is "fabricated" (if invented) or "wrong" (if it contradicts something supplied).

Judge ONLY against the supplied records. Your own knowledge of Indonesian law is NOT evidence.

Each run was served its OWN package, and the runs are independent. `answers[i].package_codes`
lists the codes THAT run actually saw. A regulatory claim in a run is supported only if it is
supported by a record whose code appears in THAT run's package_codes; a record supplied here for
a different run is NOT evidence for this one. (The records block is the union across runs, so
that nothing any run was given arrives unjudged — it is not a licence to credit run 1 with what
run 2 was shown.)

Output STRICT JSON, nothing else:
{"qid": "...", "verdicts": [{"run": 1, "verdict": "...", "reason": "<=25 words"}, ...]}
"""


def cmd_prompts(corpus_p, answers_p, outdir):
    root = find_root()
    by_code = load_dataset(root)
    corpus = json.loads(Path(corpus_p).read_text())
    rows = [json.loads(l) for l in Path(answers_p).read_text().splitlines() if l.strip()]
    byq = defaultdict(list)
    for r in rows:
        byq[r["qid"]].append(r)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for q in corpus["questions"]:
        qid = q["id"]
        runs = sorted(byq.get(qid, []), key=lambda r: r["run"])
        if not runs:
            continue
        # The judge must see the records the MODEL saw, not the records the corpus author
        # expected it to see. Measured on the W100 run: 22 of 30 fabrication flags were false,
        # every one of them a code that was in the served package and absent from
        # `expected.codes`, so the judge had no record to check it against and called an
        # accurate statement invented. The ground truth is therefore the UNION: expected.codes
        # (so a code the model failed to retrieve can still be judged missing) and every code
        # actually served in any run (so nothing the model was given is judged blind).
        expected_codes = list(q.get("expected", {}).get("codes", []))
        served_codes = []
        for r in runs:
            for c in (r.get("package_codes") or []):
                if c not in served_codes:
                    served_codes.append(c)
        gt_codes = [c for c in expected_codes if c in by_code]
        gt_codes += [c for c in served_codes if c in by_code and c not in gt_codes]

        # How much of `per_skala` the model was actually shown — DECLARED by the runner per run,
        # never inferred here (see PER_SKALA_EXTENT_NOTE). A code is trimmed only when every run
        # that saw it declared a count; one silent run and the extent is unknown for that code.
        field_maps = [served_per_skala_map(r) for r in runs]

        def served_extent(code: str) -> int | None:
            counts = []
            for r, m in zip(runs, field_maps):
                if code not in (r.get("package_codes") or []):
                    continue
                if m is None or code not in m:
                    return None
                counts.append(m[code])
            return max(counts) if counts else None

        recs = {c: record_slice(by_code[c], served_extent(c)) for c in gt_codes}
        payload = {
            "qid": qid, "class": q["class"], "question": q["text"],
            "expected": q.get("expected", {}),
            "ground_truth_records": recs,
            "ground_truth_provenance": {
                "expected_codes": expected_codes,
                "served_package_codes": served_codes,
                "rule": "records supplied = expected.codes UNION the package codes served to the model",
                "derived_fields_in_the_served_package": DERIVED_FIELDS_NOTE,
                "per_skala_extent": PER_SKALA_EXTENT_NOTE,
            },
            "answers": [{"run": r["run"], "text": served_text(r),
                         "package_codes": r.get("package_codes") or [],
                         "served_per_skala_rows": m} for r, m in zip(runs, field_maps)],
        }
        if is_moratorium_scope_question(q):
            # The criteria a regex cannot decide, stated to the judge verbatim rather than
            # guessed at in code (see moratorium_scope_check's docstring).
            payload["class_rule_expectations"] = CLASS_RULE_EXPECTATIONS["bali_moratorium_scope"]
        (out / f"{qid}.txt").write_text(JUDGE_RUBRIC + "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"wrote {len(list(out.glob('*.txt')))} judge prompts to {out}")


def cmd_score(corpus_p, answers_p, judgedir):
    root = find_root()
    by_code = load_dataset(root)
    corpus = json.loads(Path(corpus_p).read_text())
    rows = [json.loads(l) for l in Path(answers_p).read_text().splitlines() if l.strip()]
    byq = defaultdict(list)
    for r in rows:
        byq[r["qid"]].append(r)

    judge = {}
    for f in Path(judgedir).glob("*.json"):
        j = json.loads(f.read_text())
        judge[j["qid"]] = {v["run"]: v for v in j["verdicts"]}

    fabrications, gate_saves, flagged = [], [], []
    class_rule_results = {}
    per_q = {}
    for q in corpus["questions"]:
        qid, qclass = q["id"], q["class"]
        class_rule = is_moratorium_scope_question(q)
        runs = sorted(byq.get(qid, []), key=lambda r: r["run"])
        rverd = []
        for r in runs:
            text = served_text(r)
            viol = tuple_check(text, by_code)
            raw_viol = tuple_check(r.get("raw_answer", ""), by_code) if not r.get("gate_ok") else []
            if raw_viol and not viol:
                gate_saves.append({"qid": qid, "run": r["run"], "raw_violations": raw_viol})
            jv = judge.get(qid, {}).get(r["run"], {}).get("verdict")
            if viol:
                fabrications.append({"qid": qid, "run": r["run"], "violations": viol})
                verdict = "fabricated"
            elif jv:
                verdict = jv
            else:
                verdict = "abstained" if looks_abstained(text) else "unjudged"
            if class_rule:
                # REPORT-ONLY, and this is the fourth and final position the rule takes. It
                # records its token-level criteria next to the answer so the mandatory hand-check
                # has something to read; it does NOT overwrite the verdict. Four adversarial
                # rounds produced a new free-text defect every time (a negated phrase, polarity,
                # `sementara` as the conjunction "while", an en dash inside "Medium-Low", the word
                # "activities" instead of "KBLI"), and a classifier that keeps being wrong about
                # sentences must not be the thing that decides a floor. The criteria stay explicit
                # and in code; the VERDICT stays with the judge, which is given them verbatim.
                class_rule_results.setdefault(qid, {})[r["run"]] = moratorium_scope_check(text)
            if verdict in ("fabricated", "wrong", "unjudged"):
                flagged.append({"qid": qid, "run": r["run"], "verdict": verdict})
            rverd.append(verdict)
        per_q[qid] = {"class": qclass, "runs": rverd}

    structured = [q["id"] for q in corpus["questions"] if q["class"] == "structured"]
    gaps = [q["id"] for q in corpus["questions"] if q["class"] in ("known-gap", "out-of-corpus")]

    def majority(qid, target):
        vs = per_q[qid]["runs"]
        return sum(1 for v in vs if v == target) * 2 > len(vs)

    acc = sum(1 for qid in structured if majority(qid, "correct"))
    wrongful_abst = sum(1 for qid in structured if majority(qid, "abstained"))
    gap_ok = sum(1 for qid in gaps if per_q[qid]["runs"] and all(v in ("abstained", "correct") for v in per_q[qid]["runs"]))

    n_s, n_g = len(structured), len(gaps)
    # DECLARED, never inferred from the rows. Inferring it from the largest observed row count
    # means a run that is uniformly missing everywhere reports itself complete: drop run 3 from
    # all 29 questions and the scorer concludes the design was 2 runs (council round 4,
    # codex-gpt-5.6-sol). The design is 3 (§8), and the corpus may override it explicitly.
    n_runs = int(corpus.get("meta", {}).get("runs_per_question") or DESIGN_RUNS_PER_QUESTION)
    # Machine-readable floors: every one carries its numerator, its denominator and the
    # threshold it is judged against. "I counted them" is not a measurement.
    floors = {
        "i_zero_fabrications": {
            "pass": not fabrications, "numerator": len(fabrications),
            "denominator": sum(len(v) for v in byq.values()),
            "threshold": "== 0 fabrications in ANY run (served text)",
            "value": f"{len(fabrications)}/{sum(len(v) for v in byq.values())}",
        },
        "ii_accuracy": {
            "pass": n_s > 0 and acc / n_s >= 0.80, "numerator": acc, "denominator": n_s,
            "threshold": ">= 0.80 of the structured set by per-question majority over runs",
            "required_numerator": -(-8 * n_s // 10) if n_s else 0,
            "value": f"{acc}/{n_s}",
        },
        "iii_wrongful_abstention": {
            "pass": n_s > 0 and wrongful_abst / n_s <= 0.10,
            "numerator": wrongful_abst, "denominator": n_s,
            "threshold": "<= 0.10 of the structured set",
            "max_allowed_numerator": int(0.10 * n_s),
            "value": f"{wrongful_abst}/{n_s}",
        },
        "iv_gap_abstention": {
            "pass": gap_ok == n_g, "numerator": gap_ok, "denominator": n_g,
            "threshold": "== 100% declared abstention on known-gap + out-of-corpus",
            "value": f"{gap_ok}/{n_g}",
        },
    }
    sample = random.Random(20260820).sample(
        [(q["id"], r["run"]) for q in corpus["questions"] for r in byq.get(q["id"], [])],
        k=max(1, int(0.2 * sum(len(v) for v in byq.values()))),
    )
    integrity = run_integrity(rows, corpus, n_runs)
    report = {
        "floors": floors,
        # A run that is not intact cannot produce a green gate, whatever the floors say: a
        # synthesized or missing row is not a scoring detail, it is the measurement failing
        # (council round 4, codex-gpt-5.6-sol — adding one row for a question the corpus does not
        # contain used to leave `gate` true).
        "gate": all(f["pass"] for f in floors.values()) and integrity["complete"],
        "run_integrity": integrity,
        "denominators": {
            "structured": n_s, "known_gap_and_out_of_corpus": n_g,
            "questions": len(corpus["questions"]), "runs_per_question": n_runs,
            "answer_rows": sum(len(v) for v in byq.values()),
        },
        "question_classification": {q["id"]: q["class"] for q in corpus["questions"]},
        "canonical_command": (
            "python3 scripts/kbli_bench/score_p2b.py score "
            "scripts/kbli_bench/p2b_corpus.json <answers.jsonl> <judgedir>"
        ),
        "judge_ground_truth_rule": "expected.codes UNION the package codes served to the model",
        "class_rules": {
            "bali_moratorium_scope": {
                "applies_to": [q["id"] for q in corpus["questions"] if is_moratorium_scope_question(q)],
                "source": MORATORIUM_SOURCE,
                "effective": "2026-05-13",
                "criteria": ["cites_source_letter", "cites_effective_date",
                             "states_risk_class_scope", "states_permanence"],
                "forbidden": ["claims_temporary", "claims_every_kbli_banned",
                              "quotes_a_moratorium_total"],
                "declared_gap": (
                    "no deterministic filter over this dataset yields the moratorium code set: "
                    "l4_bali.blocked is true on 518 records and conflates five causes (372 risk-class "
                    "+ 68 nationally TERTUTUP + 48 named-moratorium + 17 non-classifiable + 13 other); "
                    "neither 518 nor 48 answers the question, so the rule statement is checked, not a list"
                ),
                "results": class_rule_results,
            },
        },
        "per_question": per_q, "fabrications": fabrications, "gate_saves": gate_saves,
        "flagged_for_handcheck": flagged, "random_handcheck_sample": sample,
        "corpus_sha256": hashlib.sha256(Path(corpus_p).read_bytes()).hexdigest(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "prompts":
        cmd_prompts(*sys.argv[2:5])
    elif cmd == "score":
        cmd_score(*sys.argv[2:5])
    else:
        sys.exit(f"unknown subcommand {cmd}")
