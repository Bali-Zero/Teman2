#!/usr/bin/env python3
"""Run a topic's journeys against PRODUCTION retrieval and report what came back.

MANDATE §2, fifth artifact. `kb/journeys/<topic>.yaml` declares, for each journey,
a `verbatim_phrase` that must appear in the RETRIEVED CONTEXT. Until this file
existed, a journey could record `probe_state: red` with nothing on earth producing
that verdict — the contract gate refuses an all-`untested` journey file precisely
because a record with no run behind it is a wish.

WHAT IT ASSERTS, AND WHY THAT AND NOT SOMETHING ELSE
The phrase is checked against the CHUNK TEXT returned by retrieval, never against
a generated answer. Asserting on the answer measures the model — it will paraphrase,
translate, hedge, and go green on a corpus that does not contain the fact. Asserting
on the retrieved context measures the knowledge base, which is the only thing this
campaign changes.

IT USES THE PRODUCTION PATH, DELIBERATELY
`SearchService.search()` is the same function the agentic `VectorSearchTool` calls
(`services/rag/agentic/tools.py:199`). It embeds with the same
`create_embeddings_generator()` factory the ingest side uses, and on this collection
it runs Qdrant's native hybrid query — named vectors `dense` + `bm25`, server-side
RRF fusion. A probe that reimplemented any of that could go green while production
went red, or the reverse.

Two production behaviours are pinned on purpose:
  * `collection_override="legal_unified"` (the `--collection` default, overridable
    PER JOURNEY — see below). Without it the legacy router sends any question
    containing "visa" / "kitas" / "imigrasi" to `visa_oracle` and the question never
    reaches this corpus at all — a red that means "routed elsewhere", not "not
    indexed". `collection_override` exists for exactly this ("Force specific
    collection (for testing)", its own docstring).
  * `.search()`, not `search_with_reranking()`. Reranking runs a cross-encoder and
    is not deterministic; a probe that flickers teaches people to rerun it.

THE CONTROL QUERY IS NOT OPTIONAL
A misconfigured probe — wrong URL, dead key, empty collection, an exception
swallowed somewhere — returns nothing for every journey and reports "all red",
which is indistinguishable from a knowledge base that is genuinely missing
everything. So a control query runs FIRST and must return results. If it does not,
this exits 3 (BROKEN) and reports no verdicts at all, because a probe that cannot
demonstrate it reached production has no business grading anything. It runs ONCE
PER DISTINCT COLLECTION a journey actually resolves to (2026-08-26 — see
`indiscriminate_phrases`'s docstring), memoized by name: any one of those failing
is enough to refuse the whole run, because a run that cannot prove EVERY collection
it is about to grade is reachable has no business grading any of them.

EXITS (same vocabulary as scripts/kb/kb_inventory_probe.py)
  0  AT TARGET   — every journey is SATISFIED (see "expectation" below), and the
                   file's recorded state agrees
  1  DRIFT       — the recorded probe_state disagrees with what production measured
  2  OUTSTANDING — at least one journey is not satisfied. For a plain "retrieves"
                   journey this is the ordinary "work undone" case (§3); it ALSO
                   fires for a "must_not_retrieve" canary that measures green — a
                   live regression, not routine coverage — and for a phrase found
                   in the WRONG instrument (see "instrument-checked grading" below)
  3  BROKEN      — the control query failed; nothing was graded

INSTRUMENT-CHECKED GRADING (2026-08-25, cross-family review finding — grading used
to be "is the phrase anywhere in the retrieved chunks", full stop, and that let a
journey go green off a citation inside a DIFFERENT document. Measured live in this
campaign: tax journey 8's HPP phrase appears verbatim as a citation inside
Permen_167_2022 and PP_44T_2022 ("...diubah terakhir dengan UU 7/2021 tentang HPP"),
while UU_7_2021 — the instrument that journey actually scoped — has ZERO points in
the corpus. The old grading called that green; it was never evidence about
UU_7_2021 at all. So a hit is now graded against the CHUNK'S OWN identity, read
from both payload generations (top-level `document_id` and nested
`metadata.document_id` — see `chunk_instrument()`), not just its text:
  - green         — the phrase is in a chunk that belongs to the journey's
                     `instrument_id`.
  - misattributed — the phrase came back, but every chunk carrying it belongs to a
                     DIFFERENT instrument. Not a weaker green (it is not evidence
                     for THIS instrument) and not folded into red (a red says the
                     phrase never came back at all — a different, better-understood
                     failure). A right-instrument hit wins over a wrong-instrument
                     hit regardless of rank: green at rank 7 beats misattributed at
                     rank 1, because rank measures retrieval quality and instrument
                     identity measures whether the hit is usable evidence at all.
  - red           — no chunk at any rank carries the phrase.

EXPECTATION AND SATISFACTION (2026-08-25, cross-family review finding — MANDATE §8's
"at_target sustained 48h" and a negative canary's permanent-red state contradicted
each other with no valid resolution: a canary can never legitimately go green, so a
topic with one could never reach the old definition of at_target). Each journey may
carry `expectation: retrieves` (the default, and what every journey meant before this
field existed) or `expectation: must_not_retrieve` (a canary: the phrase coming back,
correctly attributed, IS the failure — see kb/journeys/immigration.yaml journeys 2 and
8). `hit` is true only on a "green" grading; SATISFIED is `hit == (expectation ==
"retrieves")`. `probe_state` keeps recording the raw measured hit (green/red) exactly
as it always has — satisfaction is derived at report time, never stored, because two
fields that can disagree are two fields one of which is a lie.

There is deliberately NO --update flag. A probe that writes its own expected value
back into the file it grades is not a probe. Print the correction; let a human or a
lane put it in the file, where the contract gate can see it.

PER-JOURNEY COLLECTION OVERRIDE
A topic can span more than one live collection — e.g. lane A (immigration) reads
`legal_unified` for statutes/Permenkumham but production's own router sends a
"visa"/"kitas"/"imigrasi" question to `visa_oracle` first, with `immigration_circulars`
as a documented fallback (`surface_router.py:63`). A single `--collection` flag cannot
express that a canary journey deliberately targets a DIFFERENT collection than its
neighbours. So each journey entry MAY carry its own `collection:` key; when present it
wins over `--collection` for that journey only, and the run's table prints which
collection actually served each row so a reader never has to guess. Omitting it keeps
the previous behaviour (every journey uses `--collection`, default `legal_unified`)
exactly as before — this is additive, not a breaking change to journeys that don't need
it. See `test_probe_retrieval_collection_override.py` for the guilt/innocence proof.

--json (additive, 2026-08-25)
Emits ONE JSON object on stdout instead of the human-readable report, for a caller
(`kb/ops/probe_history.py`) that needs to record a verdict rather than read one.
Nothing about grading changes — this only serializes the same verdict the human
path already computes. Vocabulary is closed and mirrors the exit codes above, plus
one field the human report does not need: `reason`, set on a `broken` verdict to
distinguish "the journeys file declares nothing to run" (`no_journeys`) from "the
control query itself failed" (`control_failed`) — two different exit-3 causes that
a history recorder must not conflate (the first is "nothing was ever asked of
production", the second is "production could not be reached").
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

WS = re.compile(r"\s+")

# Closed vocabulary for --json's "verdict" field — one member per exit code above.
VERDICT_BY_EXIT = {0: "at_target", 1: "drift", 2: "outstanding", 3: "broken"}

# The control must be a phrase that is in this corpus regardless of any lane's work,
# and specific enough that a random chunk will not contain it by accident. This one
# is the standard Indonesian statutory closing formula.
CONTROL_QUERY = "ketentuan peraturan perundang-undangan"
CONTROL_PHRASE = "peraturan perundang-undangan"


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("repo root not found")


def load_env(root: Path) -> None:
    """Read apps/backend-rag/.env before importing settings.

    pydantic-settings resolves its `env_file=".env"` relative to the CWD at import
    time, so a script run from anywhere else silently gets an unconfigured client.
    Reading it here makes this cwd-independent — which is not a nicety: a gate that
    is green from one directory and red from another is not a gate.
    """
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize(text: str) -> str:
    return WS.sub(" ", text or "").strip().lower()


def detect_degraded(root: Path) -> str | None:
    """Return a one-line description of the degraded-path mismatch, or None if clean.

    Pure detection, no printing — split out of `warn_if_degraded` so `--json` can
    carry the same boolean the human banner is built from, without duplicating the
    version-comparison logic (see `warn_if_degraded`'s docstring for what this
    means and why it matters).
    """
    lock = root / "apps" / "backend-rag" / "requirements.lock.txt"
    pinned = None
    if lock.is_file():
        for line in lock.read_text(encoding="utf-8").splitlines():
            if line.startswith("google-genai=="):
                pinned = line.split("==", 1)[1].split()[0].strip("\\ ")
                break
    try:
        import importlib.metadata as _md

        installed = _md.version("google-genai")
    except Exception:  # noqa: BLE001
        installed = None

    if pinned and installed and pinned != installed:
        return "google-genai installed %s, repo pins %s" % (installed, pinned)
    return None


def warn_if_degraded(root: Path) -> bool:
    """Say out loud when this process is NOT running production's retrieval path.

    Measured 2026-08-25: a local venv carrying google-genai 1.75.0 against a lock
    that pins 2.18.1 makes every Gemini query-expansion call raise
    `TypeError: 'async for' requires an object with __aiter__ method` — which
    `QueryExpander` catches and returns None from, so retrieval proceeds WITHOUT
    multilingual expansion and logs a warning nobody reads. Search still works,
    the probe still produces verdicts, and every one of them is a measurement of a
    narrower retrieval than production performs.

    That is the dangerous shape: not a probe that breaks, but a probe that quietly
    grades a degraded path and reports the result as production's. A red measured
    here could be green in production, where expansion would have reached the
    chunk. So the divergence is printed as a banner rather than left in a log line,
    and the version is read from the SAME lock file CI installs from — never from a
    hardcoded expectation, which would rot the first time the pin moves.

    Returns whether the banner fired, so `--json` can carry the same fact.
    """
    mismatch = detect_degraded(root)
    if mismatch:
        print()
        print("  !! DEGRADED PATH — %s." % mismatch)
        print("     Gemini query expansion raises and is swallowed at this version, so")
        print("     retrieval below runs WITHOUT multilingual expansion. A red measured")
        print("     here may be green in production. Verdicts are still meaningful as a")
        print("     LOWER BOUND on what production retrieves — never as an upper one.")
    return mismatch is not None


async def retrieve(service, query: str, collection: str, limit: int) -> list[dict]:
    """One production retrieval. Returns the chunk dicts, or raises."""
    result = await service.search(
        query=query,
        user_level=3,  # LEVEL_TO_TIERS[3] = the full tier set; a lower level
        # silently narrows the corpus and the red would mean "tier-filtered".
        limit=limit,
        collection_override=collection,
    )
    return result.get("results") or []


def phrase_hit(chunks: list[dict], phrase: str) -> tuple[bool, int | None]:
    """Is the phrase in the retrieved text? Returns (hit, rank) — rank is 1-based.

    Reads `chunk["text"]`, which is where `format_search_results` puts it for both
    payload generations. Measured 2026-08-25 across all 84,283 points of
    legal_unified: 100% carry a top-level `text`, so production's
    `payload.get("text", "")` never serves an empty chunk here and this probe does
    not need a defensive fallback that production itself does not have. If that
    ever stops being true, the honest failure is a red probe, not a probe reading
    a field production ignores.
    """
    needle = normalize(phrase)
    for i, chunk in enumerate(chunks, start=1):
        if needle in normalize(chunk.get("text", "")):
            return True, i
    return False, None


def chunk_instrument(chunk: dict) -> str | None:
    """Which instrument this retrieved chunk's payload actually names, or None.

    Two payload generations coexist in legal_unified (kb_inventory_probe.py's
    PAYLOAD_SHAPES; MANDATE §4.1): a modern ingest writes `document_id` at the
    payload's top level; a legacy ingest nests it under
    `payload["metadata"]["document_id"]` instead. `_extract_point_metadata`
    (backend/core/qdrant_db.py:192) folds a flat payload's other keys —
    `document_id` included — into what reaches this probe as `chunk["metadata"]`,
    and passes a legacy payload's own nested `metadata` dict through unchanged.
    So by the time a chunk gets here, BOTH generations' identity lives at
    `chunk["metadata"]["document_id"]`. This also checks `chunk["document_id"]`
    directly rather than trusting that one normalisation layer never to change
    shape underneath it. Measured 2026-08-25: 78,486 of legal_unified's 84,283
    points (93%) carry identity ONLY in the nested form — a check that reads just
    the flat key is blind to the entire legacy generation, which is the exact
    failure this function exists not to repeat.
    """
    meta = chunk.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return chunk.get("document_id") or meta.get("document_id") or None


def journey_satisfaction(measured_state: str, expectation: str) -> bool:
    """Whether a journey's measurement meets what the journey asked for.

    The two expectations are NOT mirror images, and treating them as one was a
    real defect. `retrieves` asks a question about ATTRIBUTION: did the right
    instrument answer? A phrase found under some other document is not evidence
    for this instrument, so `misattributed` fails it.

    `must_not_retrieve` asks a question about REACHABILITY: can a user be shown
    this text at all? Immigration journey 2's poison is the body of a Tegal
    regency correspondence manual; if that text comes back attributed to some
    OTHER document, the reader still gets municipal letterhead rules in a Golden
    Visa answer. The harm is identical, and a poison phrase floating loose under
    someone else's identity is a MORE broken corpus, not a less broken one.

    So a canary is violated by any retrieval, `green` or `misattributed`. The
    earlier rule derived both from `hit == (expectation == "retrieves")`, which
    made `misattributed` SATISFY a canary — the guard went quiet in precisely
    the case where the corpus was worse.

    FAIL-CLOSED, not fail-open (PENDING-ARMS guard 1, cross-family completeness
    review 2026-08-26): `must_not_retrieve` used to be a DENY-list —
    `measured_state not in ("green", "misattributed")` — so ANYTHING else
    satisfied a canary: a case-mismatched `"GREEN"`, `None`, or any other value
    this function was never told to expect. `run()` only ever calls this with
    the three values `locate_phrase()` actually returns, so that specific chain
    is not reachable through this module's own code today — but this is a small
    pure function nothing stops another caller from misusing, and a canary is
    exactly the place a permissive default is the wrong direction: in doubt, a
    reachable poison must be declared a VIOLATION, not silently satisfied. Now
    an ALLOW-list — only the one state that has ever meant "the poison did not
    come back" satisfies a canary; every real caller's three legitimate values
    (`green`/`misattributed`/`red`) behave identically to before this change.
    """
    if expectation == "retrieves":
        return measured_state == "green"
    if expectation == "must_not_retrieve":
        return measured_state == "red"
    return False  # an unrecognised expectation satisfies nothing, ever


def canary_unverifiable_under_degradation(
    expectation: str, satisfied: bool, degraded: bool
) -> bool:
    """True when a SATISFIED canary's result is not trustworthy proof of safety.

    `warn_if_degraded`'s own docstring calls a degraded-path verdict "a LOWER
    BOUND on what production retrieves — never an upper one," because disabled
    query expansion can only NARROW what comes back. That direction is correct
    for `expectation: retrieves` (a red measured here may be green in
    production — the file already prints exactly that caveat). For
    `must_not_retrieve` it is inverted: a NARROWER search can only make a
    poisoned instrument HARDER to find, so a canary that stayed red under a
    degraded path is an UPPER bound on safety, not a lower one — production's
    wider search could still surface what this run could not. Refuter finding
    R2 (2026-08-26): the run's final verdict and its `AT TARGET ... canaries
    stayed red` banner did not carry this distinction at all, so a degraded run
    could declare a topic safe on evidence that, by this module's own stated
    logic, proves the opposite of what it is being read as.

    Only a SATISFIED canary is unverifiable this way — a VIOLATED canary
    (`satisfied=False`) under degradation is still real evidence: the poison
    came back despite a narrower search, which is if anything stronger proof of
    a live regression, and that branch already lands in `outstanding`
    regardless of `degraded`. A `retrieves` journey is never affected, at any
    value of `satisfied` or `degraded` — the lower-bound direction for it was
    always sound and is untouched by this predicate.
    """
    return expectation == "must_not_retrieve" and satisfied and degraded


def locate_phrase(chunks: list[dict], phrase: str, instrument_id: str) -> dict:
    """Where the phrase is, and — the point of this function — WHOSE it is.

    See the module docstring's "INSTRUMENT-CHECKED GRADING" section for why a
    text match alone is not enough (the tax-J8 defect: a phrase citation inside
    a DIFFERENT instrument used to grade green). Returns a dict with:
      "state"            — "green" | "misattributed" | "red"
      "rank"              — 1-based rank of the reported hit, or None for red
      "found_instrument" — the instrument actually holding the reported hit
                             (== instrument_id for green; the wrong one for
                             misattributed; None for red)

    A RIGHT-instrument hit wins over a WRONG-instrument hit regardless of rank
    — scanned in retrieval order, the first correct-instrument hit is returned
    immediately; a wrong-instrument hit is only ever a fallback, reported at
    ITS OWN first-seen rank so a reader can see how early the misattribution
    would mislead a real answer.
    """
    needle = normalize(phrase)
    wrong_rank: int | None = None
    wrong_instrument: str | None = None
    for i, chunk in enumerate(chunks, start=1):
        if needle not in normalize(chunk.get("text", "")):
            continue
        found = chunk_instrument(chunk)
        if found == instrument_id:
            return {"state": "green", "rank": i, "found_instrument": found}
        if wrong_rank is None:
            wrong_rank, wrong_instrument = i, found
    if wrong_rank is not None:
        return {
            "state": "misattributed",
            "rank": wrong_rank,
            "found_instrument": wrong_instrument,
        }
    return {"state": "red", "rank": None, "found_instrument": None}


def resolve_collection(journey: dict, default: str) -> str:
    """Which collection THIS journey's question is sent to.

    A journey's own `collection:` key wins; an absent/blank key falls back to the
    run's `--collection` default. Kept as a pure function (no I/O) so
    `test_probe_retrieval_collection_override.py` can prove both branches without a
    live Qdrant connection — the guilt case an inline `journey.get("collection") or
    args.collection` scattered at the call site could not be proven the same way.
    """
    override = journey.get("collection")
    return override if isinstance(override, str) and override.strip() else default


# The G3 contract already refuses a verbatim_phrase under 12 characters, but that
# is a DIFFERENT PROGRAM: it runs when someone runs the topic-contract test. A lane
# iterating with this probe by hand never touches it. Measured live 2026-08-25 by an
# adversarial pass: verbatim_phrase "" / "a" / "   " / "." / "dan" ALL reported GREEN
# at rank 1 — "" is a substring of every string in Python, so such a journey greens
# against any corpus, for any question. A probe that can be made to say green without
# reading anything is not a probe, so the floor lives here too.
MIN_PHRASE_CHARS = 12


def unusable_phrase(phrase: str) -> str | None:
    """Why this phrase can grade nothing — or None when it can."""
    norm = normalize(phrase)
    if not norm:
        return (
            "empty after normalisation. '' is a substring of every string, so this "
            "journey would report green against any corpus, for any question"
        )
    if len(norm) < MIN_PHRASE_CHARS:
        return (
            "%d characters after normalisation, floor is %d. A phrase this short "
            "matches by accident and measures nothing" % (len(norm), MIN_PHRASE_CHARS)
        )
    return None


# U+241F SYMBOL FOR UNIT SEPARATOR: a character no legal text contains, joined
# between chunks so a phrase cannot match by straddling the seam between two
# unrelated documents — a span that exists in nothing anyone ingested.
CHUNK_SEPARATOR = "\u241f"


def unserved_collections(names, lookup) -> list[str]:
    """Names the running collection manager cannot hand back, sorted.

    `lookup` is injected rather than reached for, and that is the whole point: this
    is the EXACT predicate search_service.py evaluates (`if not vector_db`) before
    silently substituting legal_unified, so it must have a test that can fail — and
    it cannot have one if exercising it requires a live Qdrant. A floor whose only
    proof needs production is a floor nobody checks.
    """
    return sorted({n for n in names if not lookup(n)})


def indiscriminate_phrases(
    journeys, controls: dict[str, list[dict]], default_collection: str
) -> list[tuple[int, str]]:
    """Phrases that also appear in THEIR OWN COLLECTION's control results.

    The control asks an unrelated, deliberately generic question — the standard
    Indonesian statutory closing formula — and whatever comes back is arbitrary legal
    text, chosen for a reason that has nothing to do with any journey. A journey's
    phrase turning up in THAT is not evidence about the journey's instrument; it is
    evidence the phrase is boilerplate, and a green from it would say only that the
    corpus contains legal prose.

    Measured 2026-08-25 in visa_oracle: one compliance paragraph is repeated across
    ~85 of its 90 points. Any phrase drawn from it is hundreds of characters long —
    it clears MIN_PHRASE_CHARS untouched — and matches nearly every document in the
    collection. Length was never the property that mattered; discrimination was.

    PER-COLLECTION (PENDING-ARMS finding opened 2026-08-26, refuter finding 10): a
    journey can override its own `collection:` (see `resolve_collection`), and
    checking it against a control fetched from a DIFFERENT collection proves
    nothing — a phrase that is boilerplate in visa_oracle but rare in legal_unified
    would sail past undetected if the only control fetched happened to be
    legal_unified's. `controls` maps collection name -> that collection's OWN
    control chunks (one retrieval per DISTINCT collection actually used by a run,
    memoized by the caller — see `run()`); each journey is checked against the
    haystack for the collection it resolves to, never a haystack shared across
    collections. The per-journey haystack is built lazily into a LOCAL dict — never
    module-level — so this function carries no state between calls: two calls in
    either order against the same inputs return the same answer.

    The check is ONE-DIRECTIONAL and the docstring says so on purpose: appearing in
    the control's results is damning, absence from five arbitrary chunks proves
    nothing. It is a cheap floor, not a certificate — the chunks are already fetched,
    so it costs no query at all.
    """
    haystacks: dict[str, str] = {}
    out = []
    for i, j in enumerate(journeys, start=1):
        phrase = normalize(j.get("verbatim_phrase", ""))
        if not phrase:
            continue
        collection = resolve_collection(j, default_collection)
        if collection not in haystacks:
            joiner = " %s " % CHUNK_SEPARATOR
            haystacks[collection] = joiner.join(
                normalize(c.get("text", "")) for c in controls.get(collection, [])
            )
        if phrase in haystacks[collection]:
            out.append((i, j.get("verbatim_phrase", "")))
    return out


def unknown_collections(names) -> list[str]:
    """Names this repo's registry does not define, sorted.

    Kept pure and I/O-free so its guilt case is provable without Qdrant. The reason
    it exists is NOT tidiness: `search_service.py:522-531` answers an unrecognised
    collection name by logging to stderr and silently searching `legal_unified`
    instead. Reproduced live — `--collection this_collection_does_not_exist_zzz999`
    exits 0 "AT TARGET" against a corpus the caller never asked for. A typo in a
    collection name must not be able to produce a green.
    """
    from backend.core.collection_registry import is_known_collection

    return sorted({n for n in names if not is_known_collection(n)})


def refuse(args, reason: str, detail: str, human: list[str]) -> int:
    """Emit a BROKEN verdict on whichever output path is active, and grade nothing."""
    if args.json:
        print(json.dumps({
            "journeys_file": str(args.journeys),
            "collection": args.collection,
            "verdict": VERDICT_BY_EXIT[3],
            "reason": reason,
            "detail": detail,
            "exit_code": 3,
            "degraded_path": False,
            "journeys": [],
        }))
    else:
        for line in human:
            print(line)
    return 3


async def run(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journeys", type=Path, help="kb/journeys/<topic>.yaml")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--collection", default="legal_unified")
    parser.add_argument(
        "--json", action="store_true",
        help="Emit one JSON object on stdout instead of the human report (additive; "
             "grading is identical either way — see module docstring).",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    load_env(root)
    sys.path.insert(0, str(root / "apps" / "backend-rag"))

    import yaml

    data = yaml.safe_load(args.journeys.read_text(encoding="utf-8")) or {}
    journeys = data.get("journeys") or []
    if not journeys:
        if args.json:
            print(json.dumps({
                "journeys_file": str(args.journeys),
                "collection": args.collection,
                "verdict": VERDICT_BY_EXIT[3],
                "reason": "no_journeys",
                "exit_code": 3,
                "degraded_path": False,
                "journeys": [],
            }))
        else:
            print("%s declares no journeys — nothing to run" % args.journeys.name)
        return 3

    # Both refusals happen BEFORE SearchService is constructed: neither needs
    # production, and a run that cannot be trusted should not spend a query.
    unusable = [
        (i, j.get("question", ""), why)
        for i, j in enumerate(journeys, start=1)
        if (why := unusable_phrase(j.get("verbatim_phrase", "")))
    ]
    if unusable:
        return refuse(
            args,
            "unusable_phrase",
            "; ".join("journey %d: %s" % (i, why) for i, _, why in unusable),
            ["BROKEN — %d journey(s) carry a phrase that cannot grade anything:"
             % len(unusable)]
            + ["  - journey %d (%s): %s" % (i, (q[:40] or "?"), why)
               for i, q, why in unusable]
            + ["",
               "Nothing was graded. A green from such a phrase would say only that "
               "some chunk came back,",
               "never that this instrument's text did."],
        )

    # Also BEFORE SearchService is constructed, and for the same reason: without
    # an instrument_id this probe cannot tell a phrase found in the RIGHT document
    # from one found in the WRONG one — which is exactly the defect it exists to
    # catch (tax-J8). The topic-contract test requires this field too, but a lane
    # iterating with this probe by hand never touches that gate.
    missing_instrument = [
        (i, j.get("question", ""))
        for i, j in enumerate(journeys, start=1)
        if not j.get("instrument_id")
    ]
    if missing_instrument:
        return refuse(
            args,
            "missing_instrument_id",
            "; ".join("journey %d has no instrument_id" % i for i, _ in missing_instrument),
            ["BROKEN — %d journey(s) carry no instrument_id:" % len(missing_instrument)]
            + ["  - journey %d (%s)" % (i, (q[:40] or "?")) for i, q in missing_instrument]
            + ["",
               "Nothing was graded. Without an instrument_id this probe cannot tell a "
               "phrase found",
               "in the RIGHT document from one found in the WRONG one (the tax-J8 "
               "shape) — grading",
               "anyway would silently fall back to the old, refuted, text-only check."],
        )

    asked = {resolve_collection(j, args.collection) for j in journeys}
    asked.add(args.collection)
    strangers = unknown_collections(asked)
    if strangers:
        return refuse(
            args,
            "unknown_collection",
            "not in LOGICAL_TO_PHYSICAL_COLLECTIONS: " + ", ".join(strangers),
            ["BROKEN — %d collection name(s) this repo's registry does not define:"
             % len(strangers)]
            + ["  - %r" % n for n in strangers]
            + ["",
               "Nothing was graded. search_service.py:522-531 answers an unknown "
               "collection by",
               "silently searching legal_unified instead, so a typo here does not "
               "error — it grades",
               "a corpus you did not ask for and can report AT TARGET. Check the "
               "spelling against",
               "backend/core/collection_registry.py."],
        )

    from backend.services.search.search_service import SearchService

    service = SearchService()

    # The registry check above catches a name nobody defined. This one catches the
    # other half: a name the registry knows but the running manager cannot hand back
    # — which is the EXACT predicate (`if not vector_db`) that triggers the silent
    # substitution downstream. Checking the same condition ourselves closes it by
    # construction rather than by hoping the two stay in agreement.
    absent = unserved_collections(asked, service.collection_manager.get_collection)
    if absent:
        return refuse(
            args,
            "unknown_collection",
            "registered but not served by this collection manager: " + ", ".join(absent),
            ["BROKEN — %d collection(s) the registry defines but this manager does "
             "not serve:" % len(absent)]
            + ["  - %r" % n for n in absent]
            + ["",
               "Nothing was graded. This is the condition search_service.py checks "
               "before silently",
               "falling back to legal_unified; refusing on it here is what keeps a "
               "green honest."],
        )

    # ── the control, before anything is graded ──────────────────────────────
    # One retrieval PER DISTINCT COLLECTION actually used by a journey (`asked`,
    # computed above), memoized by name — not just args.collection. PENDING-ARMS
    # finding opened 2026-08-26 (refuter finding 10): the discrimination floor
    # below used to check every journey's phrase against a SINGLE global control
    # fetched from args.collection alone. A journey overriding `collection:` (e.g.
    # to visa_oracle) was checked against the WRONG corpus's boilerplate — a
    # phrase generic in visa_oracle but rare in legal_unified would sail through
    # undetected. Today every real journeys file targets legal_unified alone, so
    # the refuter marked this UNDETERMINED rather than reproduced — but lane B is
    # writing company journeys against visa_oracle, so this is a failure waiting
    # for them, not a hypothetical.
    #
    # (Named function deliberately NOT written here as a call-shaped substring:
    # test_the_discrimination_floor_runs_after_the_control_and_before_any_grading
    # in test_probe_retrieval_refusals.py asserts on the raw source-text POSITION
    # of "CONTROL_PHRASE" vs the literal substring of this function's own call —
    # a comment naming it earlier in the text moves that substring's position
    # without moving any code. Reproduced live 2026-08-26 by an earlier draft of
    # this very comment; family #3, guard-over-match's own blind spot.)
    controls: dict[str, list[dict]] = {}
    control_ranks: dict[str, int] = {}
    for collection in sorted(asked):
        try:
            control_chunks = await retrieve(service, CONTROL_QUERY, collection, 5)
        except Exception as exc:  # noqa: BLE001 - the reason matters more than the type
            if args.json:
                print(json.dumps({
                    "journeys_file": str(args.journeys),
                    "collection": args.collection,
                    "verdict": VERDICT_BY_EXIT[3],
                    "reason": "control_failed",
                    "detail": "collection %r: %s: %s" % (collection, type(exc).__name__, exc),
                    "exit_code": 3,
                    "degraded_path": False,
                    "journeys": [],
                }))
            else:
                print("BROKEN — the control query on %r raised %s: %s"
                      % (collection, type(exc).__name__, exc))
                print("Nothing was graded. A probe that cannot reach production cannot")
                print("distinguish 'the knowledge base is missing this' from 'I am misconfigured'.")
            return 3

        hit, rank = phrase_hit(control_chunks, CONTROL_PHRASE)
        if not control_chunks or not hit:
            if args.json:
                print(json.dumps({
                    "journeys_file": str(args.journeys),
                    "collection": args.collection,
                    "verdict": VERDICT_BY_EXIT[3],
                    "reason": "control_failed",
                    "detail": "collection %r: control returned %d chunks, phrase %r was %s"
                              % (collection, len(control_chunks), CONTROL_PHRASE,
                                 "absent" if control_chunks else "unreachable"),
                    "exit_code": 3,
                    "degraded_path": False,
                    "journeys": [],
                }))
            else:
                print("BROKEN — the control query on %r returned %d chunks and the control"
                      % (collection, len(control_chunks)))
                print("         phrase %r was %s."
                      % (CONTROL_PHRASE, "absent" if control_chunks else "unreachable"))
                print("Nothing was graded. Check QDRANT_URL / QDRANT_API_KEY / OPENAI_API_KEY,")
                print("and that %r resolves to a populated collection." % collection)
            return 3

        controls[collection] = control_chunks
        control_ranks[collection] = rank

    # Every collection this run touches has just proved production is reachable.
    # Each collection's own chunks are also the cheapest boilerplate detector
    # available for the journeys that resolve to it: they were retrieved for a
    # question that has nothing to do with any journey.
    mirrors = indiscriminate_phrases(journeys, controls, args.collection)
    if mirrors:
        return refuse(
            args,
            "indiscriminate_phrase",
            "; ".join("journey %d: %r" % (i, ph[:60]) for i, ph in mirrors),
            ["BROKEN — %d phrase(s) also appear in their journey's own CONTROL query "
             "results:" % len(mirrors)]
            + ["  - journey %d: %r" % (i, ph[:70]) for i, ph in mirrors]
            + ["",
               "Nothing was graded. The control asks an unrelated generic question, so "
               "its results are",
               "arbitrary legal text. A phrase found there is boilerplate: a green from "
               "it would say the",
               "corpus contains legal prose, not that THIS instrument's text came back. "
               "Length is not the",
               "property that matters — pick a span only this instrument could have "
               "produced."],
        )

    if args.json:
        degraded = detect_degraded(root) is not None
    else:
        for collection in sorted(controls):
            print("[control:%s] %r found at rank %d of %d — production is reachable"
                  % (collection, CONTROL_PHRASE, control_ranks[collection],
                     len(controls[collection])))
        degraded = warn_if_degraded(root)
        print()

    # ── the journeys ────────────────────────────────────────────────────────
    # Display-only shrink for the table; JSON always carries the full word.
    MEASURED_DISPLAY = {"green": "green", "red": "red", "misattributed": "misattrib"}

    drift: list[str] = []
    outstanding: list[str] = []
    reported: list[dict] = []  # per-journey record, built regardless of --json
    if not args.json:
        header = "%-4s %-9s %-10s %-6s %-4s %-16s  %s" % (
            "#", "RECORDED", "MEASURED", "RANK", "SAT", "COLLECTION", "QUESTION")
        print(header)
        print("-" * max(len(header), 78))

    for i, journey in enumerate(journeys, start=1):
        question = journey.get("question", "")
        phrase = journey.get("verbatim_phrase", "")
        instrument_id = journey.get("instrument_id", "")
        expectation = journey.get("expectation", "retrieves")
        recorded = journey.get("probe_state", "untested")
        collection = resolve_collection(journey, args.collection)
        try:
            chunks = await retrieve(service, question, collection, args.limit)
        except Exception as exc:  # noqa: BLE001
            if not args.json:
                print("%-4d %-9s %-10s %-6s %-4s %-16s  %s"
                      % (i, recorded, "ERROR", "-", "-", collection, question[:44]))
            outstanding.append("journey %d raised %s: %s" % (i, type(exc).__name__, exc))
            reported.append({
                "index": i, "question": question, "recorded_state": recorded,
                "measured_state": "error", "rank": None, "collection": collection,
                "instrument_id": instrument_id, "expectation": expectation,
                "found_instrument": None, "satisfied": None,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })
            continue

        located = locate_phrase(chunks, phrase, instrument_id)
        measured_state = located["state"]  # "green" | "misattributed" | "red"
        rank = located["rank"]
        found_instrument = located["found_instrument"]
        hit = measured_state == "green"
        graded = "green" if hit else "red"  # what a human should write into probe_state
        satisfied = journey_satisfaction(measured_state, expectation)

        if not args.json:
            print("%-4d %-9s %-10s %-6s %-4s %-16s  %s"
                  % (i, recorded, MEASURED_DISPLAY[measured_state],
                     rank if rank else "-", "yes" if satisfied else "no",
                     collection, question[:44]))
        reported.append({
            "index": i, "question": question, "recorded_state": recorded,
            "measured_state": measured_state, "rank": rank, "collection": collection,
            "instrument_id": instrument_id, "expectation": expectation,
            "found_instrument": found_instrument, "satisfied": satisfied,
            "error": None,
        })

        # DRIFT compares the RECORDED probe_state against the raw measured HIT
        # (graded), never against satisfaction — probe_state means exactly what
        # it always meant ("did the phrase come back, correctly attributed"),
        # regardless of what a journey's expectation makes of that fact.
        if recorded == "untested":
            drift.append(
                "journey %d is recorded 'untested' but has now been run and measured "
                "%r — record it, an unrun verdict is not a verdict" % (i, measured_state)
            )
        elif recorded != graded:
            if expectation == "must_not_retrieve":
                note = (
                    "REGRESSION: this canary was safe and the poisoned instrument is "
                    "now retrieved" if graded == "green" else
                    "the file records a leak that production no longer reproduces — "
                    "re-verify before declaring it permanently safe"
                )
            else:
                note = (
                    "the work landed and the file is stale" if graded == "green"
                    else "REGRESSION: this used to be found and no longer is"
                )
            drift.append(
                "journey %d records %r, production measures %r — %s"
                % (i, recorded, measured_state, note)
            )

        if not satisfied:
            if measured_state == "misattributed":
                outstanding.append(
                    "journey %d: %r is retrieved (rank %d) but attributed to %r, "
                    "not %r — found, WRONG instrument (the tax-J8 shape)"
                    % (i, phrase[:48], rank, found_instrument, instrument_id)
                )
            elif expectation == "must_not_retrieve":
                outstanding.append(
                    "journey %d: CANARY VIOLATED — %r is retrieved (rank %d) from "
                    "the poisoned instrument %r: %s"
                    % (i, phrase[:48], rank, instrument_id,
                       journey.get("reason") or "no reason recorded")
                )
            else:
                outstanding.append(
                    "journey %d: %r is not in the retrieved context for %r"
                    % (i, phrase[:48], question[:48])
                )
        elif canary_unverifiable_under_degradation(expectation, satisfied, degraded):
            # R2 (refuter finding, 2026-08-26): a canary that measured 'safe' while
            # this run took the DEGRADED path (see warn_if_degraded's docstring) is
            # not proof of safety — a narrower search can only make a poisoned
            # instrument HARDER to find, so this is an upper bound, not a lower
            # one. Landing this in `outstanding` (not silently accepted) is what
            # stops the AT TARGET banner below from affirming a safety this run
            # did not actually measure.
            outstanding.append(
                "journey %d: CANARY UNVERIFIABLE — %r stayed red, but retrieval ran "
                "the DEGRADED path (see the banner above): a narrower search can only "
                "make a poisoned instrument HARDER to find, so this is an upper bound "
                "on safety, not proof of it. Re-verify on the production retrieval "
                "path before trusting this canary." % (i, phrase[:48])
            )

    exit_code = 0
    if drift:
        exit_code = 1
    elif outstanding:
        exit_code = 2

    # R3 (refuter finding, 2026-08-26): `drift` and `outstanding` are two
    # independent facts about this run, and collapsing them into one exit code
    # was already this campaign's own diagnosed mistake once — see
    # test_kb_probe_history_contract.py's rule (g), "build_record keeps the two
    # verdicts DISTINCT, never AND'd". Applying that same lesson here: the exit
    # code (and therefore VERDICT_BY_EXIT, which kb_inventory_probe.py's --json
    # mirrors string-for-string, and which probe_history.py's closed vocabulary
    # is built from) keeps DRIFT's historical priority over OUTSTANDING for
    # backward compatibility — no consumer's vocabulary changes. What changes is
    # that a live regression no longer goes INVISIBLE just because drift also
    # fired this run: both raw lists are reported, in the JSON and in the human
    # text, regardless of which one decided the exit code.
    if args.json:
        print(json.dumps({
            "journeys_file": str(args.journeys),
            "collection": args.collection,
            "verdict": VERDICT_BY_EXIT[exit_code],
            "exit_code": exit_code,
            "degraded_path": degraded,
            "drift": drift,
            "outstanding": outstanding,
            "journeys": reported,
        }))
        return exit_code

    print()
    if drift:
        print("DRIFT — the file disagrees with production (%d):" % len(drift))
        for item in drift:
            print("  ! %s" % item)
        print()
        print("The journey file is STALE. Update probe_state / probe_run_at by hand —")
        print("this tool deliberately will not write its own expected value back.")

    if outstanding:
        print("OUTSTANDING — %d of %d journeys are not satisfied:"
              % (len(outstanding), len(journeys)))
        for item in outstanding:
            print("  - %s" % item)
        print()
        print("For a plain 'retrieves' journey, red is the state it is SUPPOSED to be")
        print("in on the day it is written (§3) — work still to do, not a bug in this")
        print("run. A line above naming a CANARY VIOLATED, a WRONG instrument, or a")
        print("CANARY UNVERIFIABLE (degraded path), is not routine coverage — it is a")
        print("live regression, or an untrustworthy proof, the campaign exists to")
        print("catch. Read which kind each line is before treating it as expected.")

    if drift:
        return 1
    if outstanding:
        return 2

    print("AT TARGET — every journey is satisfied: 'retrieves' journeys found their")
    print("phrase in the right instrument, and 'must_not_retrieve' canaries stayed red.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
