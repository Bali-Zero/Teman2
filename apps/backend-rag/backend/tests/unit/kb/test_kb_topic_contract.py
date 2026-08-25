"""The G3 contract for topic artifacts: kb/topics, kb/journeys, kb/inventory(kind=topic).

`test_kb_inventory_contract.py` owns `kind: retired_collection` and SKIPS every
`kind: topic` file with the message "owned by another gate (MANDATE §2)". Measured
2026-08-25, that gate did not exist: a three-line topic inventory containing the
word `nonsense` passed the whole suite with rc=0, judged by nobody. A defensive
skip that names an owner which does not exist is worse than no skip at all,
because it reads as coverage. This module is that owner, and the interlock test
at the bottom of the other module now fails if this file goes missing.

Anti-vacuity, which is the hard part here. No lane has landed a topic artifact
yet, so a gate parametrised only over real files would collect zero cases and
exit 0 — green because it looked at nothing (MANDATE §4.9). Every rule below is
therefore proven twice: once against a SYNTHETIC tree built in `tmp_path`, where
guilt and innocence are both exercised on every run regardless of what exists on
disk, and once against whatever real files are present. The synthetic half is
what keeps this honest before the lanes open; the real half is what keeps it
honest after.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Hard import, NOT importorskip: pyyaml==6.0.3 is pinned in requirements.lock.txt.
# importorskip here would convert a missing dependency into a silently green gate.
import yaml


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()
TOPICS_DIR = ROOT / "kb" / "topics"
JOURNEYS_DIR = ROOT / "kb" / "journeys"
INVENTORY_DIR = ROOT / "kb" / "inventory"

# MANDATE §4.3 — the label is never the thing. An instrument carries a DECLARED
# identity (what the filename and metadata say) and a VERIFIED identity (what the
# text of the instrument says about itself), and the two are recorded separately
# so that a disagreement is a fact in the file rather than a judgement call made
# once and forgotten. Measured on the legal corpus: 11 of 18 documents in one
# collection had identities that contradicted their own text.
IDENTITY_VERDICTS = frozenset({"consistent", "mistyped", "contradictory", "lost"})

# An instrument's standing in Indonesian law. `unknown` is deliberately a member:
# a topic file that cannot establish standing must SAY so, because omitting the
# field would read as "in force" to every consumer downstream.
STATUSES = frozenset({"in_force", "superseded", "revoked", "amended", "unknown"})

# MANDATE §5 — the seven lanes. Every artifact is owned by one, so a finding
# cannot be recorded with nobody on the hook for it.
LANES = frozenset("ABCDEFP")

# A journey probe's outcome against production. `red` is the expected state on
# the day a journey is written (MANDATE §3: the suite must fail red against
# production today); `untested` means the probe has never been run, which is NOT
# the same thing and must not be allowed to masquerade as red.
PROBE_STATES = frozenset({"red", "green", "untested"})

# How the question is worded. Measured 2026-08-25 over 10,929 question-bearing
# client messages in the Pro-bound WhatsApp mirror: NOT ONE named an instrument.
# Clients write index codes ("C5", "D12", "E33G") and colloquial handles
# ("investor KITAS", "hak pakai", "coretax"). A suite phrased entirely in statute
# language proves the corpus is indexed; it does not prove a client can reach it.
PHRASINGS = frozenset({"client", "statute"})

# The same measurement found four languages in one corpus, frequently mixed inside
# a single message. An English-only suite certifies a path most traffic never takes.
LANGUAGES = frozenset({"en", "id", "it", "es"})

# A citation, not a mention: "22/2023", "Nomor 22 Tahun 2023", "No. 6 of 2011".
# Deliberately narrow — the cost of a false positive is one rephrased journey,
# and the cost of a loose rule is a check that objects to honest questions.
_CITATION = re.compile(
    r"\b\d{1,3}\s*/\s*(?:19|20)\d{2}\b"
    r"|\b(?:no\.?|nomor|n[.\u00ba\u00b0])\s*\d{1,3}\s+(?:tahun|of|year|del)\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)


def cites_an_instrument(question: str) -> bool:
    """True when the question carries a statute citation rather than a mention."""
    return bool(_CITATION.search(question or ""))

OWNED_KIND = "topic"


def _probe():
    """Load kb_inventory_probe.py (it lives outside any package)."""
    import importlib.util

    cached = sys.modules.get("kb_inventory_probe")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "kb_inventory_probe", ROOT / "scripts" / "kb" / "kb_inventory_probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_inventory_probe"] = module
    spec.loader.exec_module(module)
    return module


# IMPORTED from the probe, never restated. The sibling gate does the same, for the
# same reason: a tripwire that compares two restatements of one idea is blind, and
# these two must read the SAME tuple the probe measures production with.
PAYLOAD_SHAPES = frozenset(_probe().PAYLOAD_SHAPES)


# ── the rules, as pure functions over already-parsed data ────────────────────
# Written as functions rather than inline asserts so the SAME rule can be run
# against the synthetic tree and against real files. A gate whose guilt proof
# exercises a reimplementation of its rule proves nothing about the rule.


def check_topic(data: dict) -> list[str]:
    """Rules for kb/topics/<t>.yaml — the instruments in scope for a topic."""
    problems: list[str] = []
    if data.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if data.get("lane") not in LANES:
        problems.append(f"lane must be one of {sorted(LANES)}, got {data.get('lane')!r}")
    if not data.get("topic"):
        problems.append("topic is required")

    instruments = data.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        problems.append(
            "instruments must be a non-empty list — a topic in scope with no "
            "instruments named is a topic nobody has actually scoped"
        )
        return problems

    seen: set[str] = set()
    for i, inst in enumerate(instruments):
        where = f"instruments[{i}]"
        ident = inst.get("id")
        if not ident:
            problems.append(f"{where}: id is required")
        elif ident in seen:
            problems.append(f"{where}: duplicate id {ident!r}")
        else:
            seen.add(ident)

        status = inst.get("status")
        if status not in STATUSES:
            problems.append(f"{where}: status must be one of {sorted(STATUSES)}, got {status!r}")

        # §4.3: the label is never the thing. Both identities, always, plus a
        # verdict on whether they agree. Every Indonesian ministry restarts its
        # numbering each year, so a filename is never sufficient evidence.
        if "declared_identity" not in inst:
            problems.append(f"{where}: declared_identity is required (what the label says)")
        if "verified_identity" not in inst:
            problems.append(
                f"{where}: verified_identity is required (what the instrument's own "
                f"text says) — record null if it could not be established, never omit"
            )
        verdict = inst.get("identity_verdict")
        if verdict not in IDENTITY_VERDICTS:
            problems.append(
                f"{where}: identity_verdict must be one of {sorted(IDENTITY_VERDICTS)}, "
                f"got {verdict!r}"
            )
        if verdict == "consistent" and inst.get("declared_identity") != inst.get(
            "verified_identity"
        ):
            problems.append(
                f"{where}: identity_verdict says 'consistent' but declared_identity "
                f"and verified_identity differ — the verdict contradicts its own evidence"
            )

        # A superseded instrument that does not say what replaced it sends every
        # reader back to the superseded text.
        if status == "superseded" and not inst.get("superseded_by"):
            problems.append(f"{where}: status is 'superseded' but superseded_by is empty")

        # §4.8: a source is only checkable if the check can be repeated.
        # peraturan.go.id answers HTTP 200 with a 74KB HTML error page, so a URL
        # alone is not evidence — the retrieval must record what it actually got.
        if not inst.get("source_url"):
            problems.append(f"{where}: source_url is required")
        fetched = inst.get("source_verified")
        if fetched not in (True, False):
            problems.append(
                f"{where}: source_verified must be an explicit true/false — whether the "
                f"URL was fetched AND the bytes looked like the instrument (first four "
                f"bytes %PDF, or a parsed title), never assumed from the URL alone"
            )
    return problems


def check_journey(data: dict) -> list[str]:
    """Rules for kb/journeys/<t>.yaml — what a real user asks, and what must come back."""
    problems: list[str] = []
    if data.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if data.get("lane") not in LANES:
        problems.append(f"lane must be one of {sorted(LANES)}, got {data.get('lane')!r}")

    journeys = data.get("journeys")
    if not isinstance(journeys, list) or not journeys:
        problems.append("journeys must be a non-empty list")
        return problems

    for i, j in enumerate(journeys):
        where = f"journeys[{i}]"
        if not j.get("question"):
            problems.append(f"{where}: question is required, in the user's own words")

        # The assertion target is the RETRIEVED CONTEXT, not the generated answer.
        # Asserting on the answer measures the model; asserting on the context
        # measures the knowledge base, which is the thing this campaign changes.
        phrase = j.get("verbatim_phrase")
        if not phrase or len(str(phrase).strip()) < 12:
            problems.append(
                f"{where}: verbatim_phrase must be a substantive span (>=12 chars) that "
                f"has to appear in the RETRIEVED CONTEXT — a short phrase matches by "
                f"accident and measures nothing"
            )
        if not j.get("instrument_id"):
            problems.append(
                f"{where}: instrument_id is required — the phrase must be traceable to "
                f"an instrument in this topic's kb/topics file"
            )
        state = j.get("probe_state")
        if state not in PROBE_STATES:
            problems.append(
                f"{where}: probe_state must be one of {sorted(PROBE_STATES)}, got {state!r}"
            )
        if state in ("red", "green") and not j.get("probe_run_at"):
            problems.append(
                f"{where}: probe_state is {state!r} but probe_run_at is missing — a "
                f"verdict with no run behind it is 'untested' wearing a costume"
            )

        phrasing = j.get("phrasing")
        if phrasing not in PHRASINGS:
            problems.append(
                f"{where}: phrasing must be one of {sorted(PHRASINGS)}, got {phrasing!r}"
            )
        # Declaring 'client' is cheap; the check is behavioural, not a promise.
        if phrasing == "client" and cites_an_instrument(j.get("question") or ""):
            problems.append(
                f"{where}: phrasing is 'client' but the question carries a statute "
                f"citation. Measured over 10,929 real client questions, not one "
                f"named an instrument — this is statute phrasing wearing a label"
            )

        lang = j.get("language")
        if lang not in LANGUAGES:
            problems.append(
                f"{where}: language must be one of {sorted(LANGUAGES)}, got {lang!r}"
            )

        cross = j.get("cross_topic")
        if cross not in (True, False, None):
            problems.append(f"{where}: cross_topic must be true or false, got {cross!r}")
        if cross is True:
            other = j.get("cross_topic_lane")
            if other not in LANES:
                problems.append(
                    f"{where}: cross_topic is true but cross_topic_lane is {other!r} — "
                    f"name the lane that owns the other instrument"
                )
            elif other == data.get("lane"):
                problems.append(
                    f"{where}: cross_topic_lane names its own lane {other!r} — that is "
                    f"not a boundary crossing"
                )

    # ── set-level rules ──────────────────────────────────────────────────────
    # Each of these was bought with a measurement, not an opinion. A per-journey
    # rule cannot express them: the defect is in the SHAPE of the whole suite.
    client_phrased = sum(1 for j in journeys if j.get("phrasing") == "client")
    if client_phrased < 3:
        problems.append(
            f"only {client_phrased} journey(s) are phrased the way a client phrases "
            f"it; at least 3 are required. A suite written in statute language "
            f"measures indexing, not reachability"
        )

    if not any(j.get("cross_topic") is True for j in journeys):
        problems.append(
            "no journey is marked cross_topic. Real client questions cross lane "
            "boundaries — a secondary-home KITAS asked against hak pakai, an "
            "investor KITAS whose sponsor is the client's own PMA — and a per-topic "
            "suite misses exactly those unless it is made to carry one"
        )

    non_english = sum(
        1 for j in journeys
        if j.get("language") in LANGUAGES and j.get("language") != "en"
    )
    if non_english < 2:
        problems.append(
            f"only {non_english} journey(s) are in a language other than English; at "
            f"least 2 are required. The traffic is English, Indonesian, Italian and "
            f"Spanish, often mixed inside one message"
        )
    return problems


def check_topic_inventory(data: dict) -> list[str]:
    """Rules for kb/inventory/<t>.yaml with kind: topic — what is ACTUALLY in the store."""
    problems: list[str] = []
    if data.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if data.get("lane") not in LANES:
        problems.append(f"lane must be one of {sorted(LANES)}, got {data.get('lane')!r}")
    if not data.get("measured_at"):
        problems.append("measured_at is required — an unmeasured inventory is a wish")

    measured = data.get("measured_against")
    if not isinstance(measured, dict):
        problems.append("measured_against is required")
        return problems

    if not measured.get("collection"):
        problems.append("measured_against.collection is required")
    points = measured.get("points")
    if not isinstance(points, int):
        problems.append("measured_against.points must be an integer")

    # §4.1 — the payload shape mix, in the vocabulary the probe measures. A topic
    # inventory that does not record it cannot be drift-checked, and the shape
    # mix is exactly what a re-ingest silently changes.
    shapes = measured.get("payload_shapes")
    if not isinstance(shapes, dict) or not shapes:
        problems.append(
            "measured_against.payload_shapes is required — §4.1, and the probe "
            "compares it against production"
        )
    else:
        # The vocabulary must be CLOSED, not merely non-empty. An arithmetically
        # balanced dict of invented shape names passed every check in the first
        # draft of this gate — which is precisely the defect the sibling gate had
        # just been fixed for, reproduced here. A shape spelled some other way is
        # not a stricter record: it is a row the probe scores as 0 and the drift
        # comparison can never reach.
        unknown = set(shapes) - PAYLOAD_SHAPES
        if unknown:
            problems.append(
                f"payload_shapes names {sorted(unknown)}, which kb_inventory_probe.py "
                f"cannot measure — known shapes are {sorted(PAYLOAD_SHAPES)}"
            )
        missing = PAYLOAD_SHAPES - set(shapes)
        if missing:
            problems.append(
                f"payload_shapes omits {sorted(missing)}. Omission reads as 'absent', and "
                f"'absent' is indistinguishable from 'never looked' — record a 0"
            )
        if isinstance(points, int) and sum(shapes.values()) != points:
            problems.append(
                f"payload_shapes sums to {sum(shapes.values())} but points is {points} — "
                f"every point has exactly one shape, so these must be equal"
            )

    instruments = data.get("instruments")
    if not isinstance(instruments, list):
        problems.append("instruments must be a list (empty is legal: 'nothing is indexed yet')")
        return problems

    total = 0
    for i, inst in enumerate(instruments):
        where = f"instruments[{i}]"
        if not inst.get("id"):
            problems.append(f"{where}: id is required")
        n = inst.get("points")
        if not isinstance(n, int) or n < 0:
            problems.append(f"{where}: points must be a non-negative integer")
        else:
            total += n
        # §4.5 — whole or nothing. `present` must be stated, never inferred from
        # a non-zero count: this repo has already stored a half-read law as if it
        # were whole, and a partial document is worse than an absent one because
        # it answers confidently from the half it has.
        present = inst.get("present")
        if present not in (True, False):
            problems.append(
                f"{where}: present must be an explicit true/false (§4.5) — inferring it "
                f"from a point count cannot distinguish 'fully indexed' from 'the first "
                f"three chunks landed and the ingest died'"
            )
        if present is True:
            if isinstance(n, int) and n == 0:
                problems.append(
                    f"{where}: present=true with points=0 — a document that is 'there' "
                    f"with nothing indexed is not there"
                )
            complete = inst.get("complete")
            if complete not in (True, False):
                problems.append(
                    f"{where}: present=true requires an explicit complete true/false "
                    f"(§4.5) — whether the WHOLE instrument is indexed, not merely some "
                    f"of it"
                )
            elif complete is False and not inst.get("incomplete_because"):
                problems.append(
                    f"{where}: complete=false requires incomplete_because — a known-partial "
                    f"document with no stated gap is indistinguishable from a whole one to "
                    f"every reader downstream"
                )
        if present is False and isinstance(n, int) and n > 0:
            problems.append(
                f"{where}: present=false but points={n} — the store disagrees with the claim"
            )

        # §4.2 — three misses before saying "missing". A claim of absence made
        # from one lookup is the single most repeated error in this corpus.
        if present is False:
            attempts = inst.get("lookup_attempts")
            if not isinstance(attempts, list) or len(attempts) < 3:
                problems.append(
                    f"{where}: present=false requires lookup_attempts with at least THREE "
                    f"distinct methods (§4.2) — one lookup that found nothing is evidence "
                    f"about the lookup, not about the store"
                )

    if isinstance(points, int) and instruments and total != points:
        problems.append(
            f"instruments sum to {total} points but measured_against.points is {points} — "
            f"the inventory does not cover the collection it claims to"
        )
    return problems


# ── the synthetic tree: guilt and innocence, on every run, with zero real files ──


def _good_topic() -> dict:
    return {
        "schema_version": 1,
        "lane": "A",
        "topic": "immigration",
        "instruments": [
            {
                "id": "Permenkumham_22_2023",
                "declared_identity": "Permenkumham 22/2023",
                "verified_identity": "Permenkumham 22/2023",
                "identity_verdict": "consistent",
                "status": "in_force",
                "source_url": "https://peraturan.go.id/id/permenkumham-no-22-tahun-2023",
                "source_verified": True,
            }
        ],
    }


def _good_journey() -> dict:
    """A suite shaped like the measured traffic: mostly client-phrased, multilingual,
    carrying one boundary crossing, and red on the day it was written."""
    return {
        "schema_version": 1,
        "lane": "A",
        "journeys": [
            {
                "question": "Berapa lama izin tinggal terbatas berlaku?",
                "verbatim_phrase": "izin tinggal terbatas berlaku paling lama",
                "instrument_id": "Permenkumham_22_2023",
                "phrasing": "client",
                "language": "id",
                "cross_topic": False,
                "probe_state": "red",
                "probe_run_at": "2026-08-25",
            },
            {
                "question": "What is the C5 visa for, and what does it cost?",
                "verbatim_phrase": "izin tinggal terbatas berlaku paling lama",
                "instrument_id": "Permenkumham_22_2023",
                "phrasing": "client",
                "language": "en",
                "cross_topic": False,
                "probe_state": "red",
                "probe_run_at": "2026-08-25",
            },
            {
                "question": "Quanto dura un KITAS investor e si rinnova?",
                "verbatim_phrase": "izin tinggal terbatas berlaku paling lama",
                "instrument_id": "Permenkumham_22_2023",
                "phrasing": "client",
                "language": "it",
                "cross_topic": False,
                "probe_state": "red",
                "probe_run_at": "2026-08-25",
            },
            {
                "question": (
                    "Does Permenkumham 22/2023 allow hak pakai and the value of the "
                    "house in place of a bank deposit?"
                ),
                "verbatim_phrase": "izin tinggal terbatas berlaku paling lama",
                "instrument_id": "Permenkumham_22_2023",
                "phrasing": "statute",
                "language": "en",
                "cross_topic": True,
                "cross_topic_lane": "D",
                "probe_state": "red",
                "probe_run_at": "2026-08-25",
            },
        ],
    }


def _good_inventory() -> dict:
    return {
        "schema_version": 1,
        "kind": "topic",
        "lane": "A",
        "topic": "immigration",
        "measured_at": "2026-08-25",
        "measured_against": {
            "collection": "legal_unified",
            "points": 10,
            "payload_shapes": {
                "legacy_metadata_text": 7,
                "orphan_no_identity": 0,
                "modern_id_only": 3,
                "modern_id_chunk": 0,
                "modern_full": 0,
            },
        },
        "instruments": [
            {
                "id": "Permenkumham_22_2023",
                "points": 10,
                "present": True,
                "complete": True,
            }
        ],
    }


def test_innocence_the_well_formed_synthetic_artifacts_pass():
    """If the happy path did not pass, every guilt case below would be vacuous."""
    assert check_topic(_good_topic()) == []
    assert check_journey(_good_journey()) == []
    assert check_topic_inventory(_good_inventory()) == []


TOPIC_GUILT = [
    ("lane missing", lambda d: d.pop("lane"), "lane must be one of"),
    ("lane not a real lane", lambda d: d.update(lane="Z"), "lane must be one of"),
    ("no instruments", lambda d: d.update(instruments=[]), "non-empty list"),
    ("status outside vocabulary",
     lambda d: d["instruments"][0].update(status="probably_fine"), "status must be one of"),
    ("verified_identity omitted",
     lambda d: d["instruments"][0].pop("verified_identity"), "verified_identity is required"),
    ("declared_identity omitted",
     lambda d: d["instruments"][0].pop("declared_identity"), "declared_identity is required"),
    ("verdict contradicts its own evidence",
     lambda d: d["instruments"][0].update(verified_identity="Permenkumham 40/2023"),
     "contradicts its own evidence"),
    ("superseded with no successor",
     lambda d: d["instruments"][0].update(status="superseded"), "superseded_by is empty"),
    ("source_url missing",
     lambda d: d["instruments"][0].pop("source_url"), "source_url is required"),
    ("source_verified assumed rather than stated",
     lambda d: d["instruments"][0].pop("source_verified"), "explicit true/false"),
    ("duplicate instrument id",
     lambda d: d["instruments"].append(dict(d["instruments"][0])), "duplicate id"),
]


@pytest.mark.parametrize("name,mutate,expected", TOPIC_GUILT, ids=[c[0] for c in TOPIC_GUILT])
def test_guilt_topic(name, mutate, expected):
    data = _good_topic()
    mutate(data)
    problems = check_topic(data)
    assert any(expected in p for p in problems), (
        f"{name}: check_topic did not object. Problems returned: {problems}"
    )


JOURNEY_GUILT = [
    ("no journeys", lambda d: d.update(journeys=[]), "non-empty list"),
    ("question missing", lambda d: d["journeys"][0].pop("question"), "question is required"),
    ("phrase too short to mean anything",
     lambda d: d["journeys"][0].update(verbatim_phrase="visa"), "substantive span"),
    ("phrase missing entirely",
     lambda d: d["journeys"][0].pop("verbatim_phrase"), "substantive span"),
    ("phrase not traceable to an instrument",
     lambda d: d["journeys"][0].pop("instrument_id"), "instrument_id is required"),
    ("probe verdict outside vocabulary",
     lambda d: d["journeys"][0].update(probe_state="probably red"), "probe_state must be one of"),
    ("verdict with no run behind it",
     lambda d: d["journeys"][0].pop("probe_run_at"), "wearing a costume"),
    ("phrasing outside the closed vocabulary",
     lambda d: d["journeys"][0].update(phrasing="colloquial-ish"),
     "phrasing must be one of"),
    ("phrasing missing entirely",
     lambda d: d["journeys"][0].pop("phrasing"), "phrasing must be one of"),
    ("a statute citation wearing the 'client' label",
     lambda d: d["journeys"][0].update(question="Apa isi Permenkumham 22/2023?"),
     "wearing a label"),
    ("the same trick in the No.-Tahun form",
     lambda d: d["journeys"][0].update(question="Apa isi Permenkumham Nomor 22 Tahun 2023?"),
     "wearing a label"),
    ("language outside the closed vocabulary",
     lambda d: d["journeys"][0].update(language="bahasa"), "language must be one of"),
    ("language missing entirely",
     lambda d: d["journeys"][0].pop("language"), "language must be one of"),
    ("cross_topic is neither true nor false",
     lambda d: d["journeys"][0].update(cross_topic="maybe"), "must be true or false"),
    ("cross_topic true with no lane named",
     lambda d: d["journeys"][3].pop("cross_topic_lane"), "name the lane that owns"),
    ("cross_topic pointing at its own lane",
     lambda d: d["journeys"][3].update(cross_topic_lane="A"),
     "not a boundary crossing"),
    ("suite written entirely in statute language",
     lambda d: [x.update(phrasing="statute") for x in d["journeys"]],
     "measures indexing, not reachability"),
    ("one client-phrased journey short",
     lambda d: d["journeys"][0].update(phrasing="statute"),
     "measures indexing, not reachability"),
    ("no journey crosses a lane boundary",
     lambda d: d["journeys"][3].update(cross_topic=False),
     "a per-topic suite misses exactly those"),
    ("suite written entirely in English",
     lambda d: [x.update(language="en") for x in d["journeys"]],
     "often mixed inside one message"),
    ("one non-English journey short",
     lambda d: d["journeys"][0].update(language="en"),
     "often mixed inside one message"),
]


@pytest.mark.parametrize("name,mutate,expected", JOURNEY_GUILT, ids=[c[0] for c in JOURNEY_GUILT])
def test_guilt_journey(name, mutate, expected):
    data = _good_journey()
    mutate(data)
    problems = check_journey(data)
    assert any(expected in p for p in problems), (
        f"{name}: check_journey did not object. Problems returned: {problems}"
    )


INVENTORY_GUILT = [
    ("no measurement at all",
     lambda d: d.pop("measured_against"), "measured_against is required"),
    ("measured_at missing", lambda d: d.pop("measured_at"), "an unmeasured inventory is a wish"),
    ("payload shape mix not recorded",
     lambda d: d["measured_against"].pop("payload_shapes"), "payload_shapes is required"),
    ("shape mix does not add up",
     lambda d: d["measured_against"]["payload_shapes"].update(modern_id_only=99),
     "every point has exactly one shape"),
    ("instrument points do not cover the collection",
     lambda d: d["instruments"][0].update(points=4), "does not cover the collection"),
    ("absence claimed from a single lookup",
     lambda d: d["instruments"][0].update(present=False, points=0, lookup_attempts=["by id"])
     or d["measured_against"].update(points=0, payload_shapes={"legacy_metadata_text": 0}),
     "at least THREE distinct methods"),
    # F.1 — the closed payload-shape vocabulary (found by a cross-family refuter:
    # an arithmetically balanced dict of invented names passed the first draft)
    ("payload shape name invented, arithmetic balanced",
     lambda d: d["measured_against"].update(payload_shapes={"i_made_this_shape_up": 10}),
     "cannot measure"),
    ("payload shape omitted rather than recorded as zero",
     lambda d: d["measured_against"]["payload_shapes"].pop("modern_full"),
     "indistinguishable from 'never looked'"),
    # F.2 — whole or nothing (§4.5)
    ("present neither true nor false",
     lambda d: d["instruments"][0].pop("present"), "explicit true/false"),
    ("present true with nothing indexed",
     lambda d: d["instruments"][0].update(points=0)
     or d["measured_against"].update(points=0, payload_shapes={
         "legacy_metadata_text": 0, "orphan_no_identity": 0, "modern_id_only": 0,
         "modern_id_chunk": 0, "modern_full": 0}),
     "is not there"),
    ("present true but completeness never stated",
     lambda d: d["instruments"][0].pop("complete"), "requires an explicit complete"),
    ("known-partial document with no stated gap",
     lambda d: d["instruments"][0].update(complete=False), "requires incomplete_because"),
    ("absent according to the file, present in the store",
     lambda d: d["instruments"][0].update(
         present=False, complete=None,
         lookup_attempts=["by id", "by phrase", "by scroll"]),
     "the store disagrees with the claim"),
    ("absence claimed with no lookups recorded",
     lambda d: d["instruments"][0].update(present=False, points=0)
     or d["measured_against"].update(points=0, payload_shapes={"legacy_metadata_text": 0}),
     "at least THREE distinct methods"),
]


@pytest.mark.parametrize("name,mutate,expected", INVENTORY_GUILT,
                         ids=[c[0] for c in INVENTORY_GUILT])
def test_guilt_topic_inventory(name, mutate, expected):
    data = _good_inventory()
    mutate(data)
    problems = check_topic_inventory(data)
    assert any(expected in p for p in problems), (
        f"{name}: check_topic_inventory did not object. Problems returned: {problems}"
    )


def test_the_guilt_matrix_is_not_empty():
    """Anti-vacuity on the anti-vacuity: an emptied parametrisation collects zero
    cases and pytest exits 0. Assert the COUNT, so deleting the cases is loud."""
    assert len(TOPIC_GUILT) >= 11, len(TOPIC_GUILT)
    assert len(JOURNEY_GUILT) >= 7, len(JOURNEY_GUILT)
    assert len(INVENTORY_GUILT) >= 14, len(INVENTORY_GUILT)


# ── cross-source rules: three files that must agree, or one of them is fiction ──


def check_agreement(topic: dict, journey: dict, inventory: dict) -> list[str]:
    """The three artifacts for one topic must name the same instruments.

    Each file is internally consistent on its own; the interesting failure is
    between them. A journey asserting a phrase from an instrument the topic file
    never scoped is a probe measuring something nobody decided was in scope, and
    an inventory counting points for an instrument the topic file does not list
    is a measurement of the wrong corpus.
    """
    problems: list[str] = []
    scoped = {i.get("id") for i in (topic.get("instruments") or [])}

    for i, j in enumerate(journey.get("journeys") or []):
        ref = j.get("instrument_id")
        if ref and ref not in scoped:
            problems.append(
                f"journeys[{i}]: instrument_id {ref!r} is not in this topic's "
                f"kb/topics file (scoped: {sorted(scoped)}) — the probe asserts a "
                f"phrase from an instrument nobody put in scope"
            )

    for i, inst in enumerate(inventory.get("instruments") or []):
        ref = inst.get("id")
        if ref and ref not in scoped:
            problems.append(
                f"inventory instruments[{i}]: {ref!r} is not in this topic's kb/topics "
                f"file — the inventory measured a corpus the topic never claimed"
            )

    # MANDATE §3: the journey suite must fail RED against production on the day it
    # is written. A journey file whose probes are ALL green on creation day is
    # either measuring something that already worked — in which case there was no
    # work to do — or the probe is not reaching production at all. Both are worth
    # refusing, and the second is the one that actually happens.
    states = [j.get("probe_state") for j in (journey.get("journeys") or [])]
    if states and all(s == "green" for s in states):
        problems.append(
            "every journey probe is green on a freshly written file — either this "
            "topic needed no work, or the probe is not reaching production (§3). "
            "Record the red state first, then cure it"
        )
    if states and all(s == "untested" for s in states):
        problems.append(
            "every journey probe is 'untested' — an unrun probe suite is not a red "
            "suite, it is no suite. Run it against production and record what happened"
        )
    return problems


def test_innocence_the_synthetic_trio_agrees():
    assert check_agreement(_good_topic(), _good_journey(), _good_inventory()) == []


AGREEMENT_GUILT = [
    ("journey cites an unscoped instrument",
     lambda t, j, v: j["journeys"][0].update(instrument_id="UU_Invented_99_2099"),
     "nobody put in scope"),
    ("inventory measures an unscoped instrument",
     lambda t, j, v: v["instruments"][0].update(id="UU_Invented_99_2099"),
     "a corpus the topic never claimed"),
    ("all probes green on day one",
     lambda t, j, v: [x.update(probe_state="green") for x in j["journeys"]],
     "not reaching production"),
    ("all probes never run",
     lambda t, j, v: [x.update(probe_state="untested") for x in j["journeys"]],
     "it is no suite"),
]


@pytest.mark.parametrize("name,mutate,expected", AGREEMENT_GUILT,
                         ids=[c[0] for c in AGREEMENT_GUILT])
def test_guilt_agreement(name, mutate, expected):
    t, j, v = _good_topic(), _good_journey(), _good_inventory()
    mutate(t, j, v)
    problems = check_agreement(t, j, v)
    assert any(expected in p for p in problems), (
        f"{name}: check_agreement did not object. Problems returned: {problems}"
    )


# ── the same rules, against whatever real files exist ────────────────────────
# Empty until the lanes land. That is legal and it is why the synthetic half
# above exists — but "empty" must be OBSERVABLE, not silent, so the reporter
# below prints the count on every run.


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _real(directory: Path) -> list[Path]:
    """Every .yaml in the directory. No prefix escape hatch, deliberately.

    An earlier draft skipped names starting with `_`, meaning to allow scratch
    files. That is precisely the defect this module exists to prevent: a file
    sitting in a gated directory that no gate looks at. It also rigged this
    module's own vacuity proof — the nonsense fixture written to demonstrate the
    hole was named `_vacuity_probe.yaml` and was therefore excluded by the very
    filter under test, so the proof came back green having tested nothing.
    Scratch work belongs in a scratchpad, not in a directory a gate owns.
    """
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.yaml"))


def _real_topic_inventories() -> list[Path]:
    return [p for p in _real(INVENTORY_DIR) if _load(p).get("kind") == OWNED_KIND]


@pytest.mark.parametrize("path", _real(TOPICS_DIR), ids=lambda p: p.stem)
def test_real_topic_files_obey_the_contract(path):
    assert check_topic(_load(path)) == [], path.name


@pytest.mark.parametrize("path", _real(JOURNEYS_DIR), ids=lambda p: p.stem)
def test_real_journey_files_obey_the_contract(path):
    assert check_journey(_load(path)) == [], path.name


@pytest.mark.parametrize("path", _real_topic_inventories(), ids=lambda p: p.stem)
def test_real_topic_inventories_obey_the_contract(path):
    assert check_topic_inventory(_load(path)) == [], path.name


@pytest.mark.parametrize("path", _real(TOPICS_DIR), ids=lambda p: p.stem)
def test_every_real_topic_has_its_journey_and_inventory_and_they_agree(path):
    """A topic file alone is a scope with nothing measuring it (§2's five-artifact set)."""
    topic = _load(path)
    stem = path.stem
    journey_path = JOURNEYS_DIR / f"{stem}.yaml"
    inventory_path = INVENTORY_DIR / f"{stem}.yaml"
    assert journey_path.is_file(), (
        f"kb/topics/{stem}.yaml exists but kb/journeys/{stem}.yaml does not — a scope "
        f"with no journey is a scope nothing probes"
    )
    assert inventory_path.is_file(), (
        f"kb/topics/{stem}.yaml exists but kb/inventory/{stem}.yaml does not — a scope "
        f"with no inventory is a scope nobody measured"
    )
    assert check_agreement(topic, _load(journey_path), _load(inventory_path)) == [], stem


def test_the_real_file_count_is_reported_not_assumed(capsys):
    """Zero real topic artifacts is legal before the lanes land — but it must be SAID.

    Every parametrisation above collects zero cases while the directories are
    empty, and pytest reports that as passing. This test cannot fail on the count
    (that would block the contract from landing before its lanes), so it does the
    one thing that keeps 'empty' from reading as 'covered': it prints.
    """
    counts = (len(_real(TOPICS_DIR)), len(_real(JOURNEYS_DIR)), len(_real_topic_inventories()))
    print(f"\n[kb-topic-contract] real artifacts — topics={counts[0]} "
          f"journeys={counts[1]} inventories={counts[2]} "
          f"(synthetic guilt matrix runs regardless: "
          f"{len(TOPIC_GUILT) + len(JOURNEY_GUILT) + len(INVENTORY_GUILT) + len(AGREEMENT_GUILT)} cases)")
    assert isinstance(counts[0], int)


def test_the_other_gate_still_defers_topic_inventories_to_this_one():
    """The reverse interlock, exercised as BEHAVIOUR rather than read as text.

    The first version of this test string-grepped the sibling's source for
    `OWNED_KIND = "retired_collection"` and for the word "topic". A cross-family
    refuter showed that both assertions survive the exact regression the test
    exists to prevent: delete the `pytest.skip` from the sibling's `inventory`
    fixture and topic files start being judged by the retired-collection schema,
    while the constant line and the word "topic" both sit elsewhere in the file,
    untouched. The test was green over the defect — the same guard-over-text
    failure this whole module is built to refuse, committed inside the module
    that refuses it.

    So this now CALLS the sibling's fixture function with a synthetic
    kind='topic' entry and asserts it raises Skipped. Remove the deferral and the
    function returns a value instead of raising, and this goes red. The fixture's
    undecorated body is reached through `__wrapped__`, which pytest sets when it
    wraps a fixture function — asserted below, so a pytest change that removes it
    fails loudly here instead of silently disarming the check.
    """
    import importlib.util

    from _pytest.outcomes import Skipped

    other_path = Path(__file__).with_name("test_kb_inventory_contract.py")
    assert other_path.is_file(), (
        f"{other_path.name} is missing — the retired-collection gate is gone"
    )
    spec = importlib.util.spec_from_file_location("_sibling_gate_probe", other_path)
    sibling = importlib.util.module_from_spec(spec)
    sys.modules["_sibling_gate_probe"] = sibling
    spec.loader.exec_module(sibling)

    assert sibling.OWNED_KIND == "retired_collection", (
        f"{other_path.name} no longer claims kind='retired_collection'"
    )
    assert OWNED_KIND in sibling.KINDS, (
        f"{other_path.name} dropped kind={OWNED_KIND!r} from its KINDS vocabulary — a "
        f"file with an unknown kind is validated by nobody, which is the hole this "
        f"pair of gates exists to close"
    )

    body = getattr(sibling.inventory, "__wrapped__", None)
    assert body is not None, (
        "sibling.inventory has no __wrapped__ — pytest no longer exposes the "
        "undecorated fixture body, so this interlock can no longer exercise the "
        "deferral. Rewrite it rather than letting it pass on a missing attribute"
    )

    topic_entry = (Path("synthetic_topic.yaml"), {"schema_version": 1, "kind": OWNED_KIND})
    with pytest.raises(Skipped):
        body(topic_entry)

    # Innocence: the same fixture must NOT skip what it does own, or the guilt
    # assertion above would pass against a fixture that skips everything.
    #
    # The `except Skipped -> pytest.fail` is load-bearing and was written the wrong
    # way round first. A bare `assert body(owned_entry) == owned_entry` lets the
    # Skipped propagate, and pytest reads a Skipped raised inside a test body as
    # "skip this test" — so mutating the sibling's condition to `if True:` (defer
    # EVERYTHING, including what it owns) left this test green by silencing it.
    # The condition the probe exists to detect was the condition that muted the
    # probe. Catch it explicitly, or do not claim to check it.
    owned_entry = (
        Path("synthetic_retired.yaml"),
        {"schema_version": 1, "kind": sibling.OWNED_KIND},
    )
    try:
        returned = body(owned_entry)
    except Skipped as exc:  # pragma: no cover - only reachable under the mutation
        pytest.fail(
            f"the sibling fixture skipped an inventory of its OWN kind "
            f"({sibling.OWNED_KIND!r}) — the deferral has stopped discriminating and "
            f"now defers everything, so nothing is validated by anyone. Skip reason: {exc}"
        )
    assert returned == owned_entry, (
        f"the sibling fixture returned {returned!r} for an inventory of its own kind"
    )
