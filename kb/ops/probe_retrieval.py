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
  * `collection_override="legal_unified"`. Without it the legacy router sends any
    question containing "visa" / "kitas" / "imigrasi" to `visa_oracle` and the
    question never reaches this corpus at all — a red that means "routed elsewhere",
    not "not indexed". `collection_override` exists for exactly this ("Force
    specific collection (for testing)", its own docstring).
  * `.search()`, not `search_with_reranking()`. Reranking runs a cross-encoder and
    is not deterministic; a probe that flickers teaches people to rerun it.

THE CONTROL QUERY IS NOT OPTIONAL
A misconfigured probe — wrong URL, dead key, empty collection, an exception
swallowed somewhere — returns nothing for every journey and reports "all red",
which is indistinguishable from a knowledge base that is genuinely missing
everything. So a control query runs FIRST and must return results. If it does not,
this exits 3 (BROKEN) and reports no verdicts at all, because a probe that cannot
demonstrate it reached production has no business grading anything.

EXITS (same vocabulary as scripts/kb/kb_inventory_probe.py)
  0  AT TARGET   — every journey measured green, and the file says green
  1  DRIFT       — the measurement disagrees with the recorded probe_state
  2  OUTSTANDING — the file says red and the measurement agrees: work undone
  3  BROKEN      — the control query failed; nothing was graded

There is deliberately NO --update flag. A probe that writes its own expected value
back into the file it grades is not a probe. Print the correction; let a human or a
lane put it in the file, where the contract gate can see it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

WS = re.compile(r"\s+")

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


def warn_if_degraded(root: Path) -> None:
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
        print()
        print("  !! DEGRADED PATH — google-genai installed %s, this repo pins %s."
              % (installed, pinned))
        print("     Gemini query expansion raises and is swallowed at this version, so")
        print("     retrieval below runs WITHOUT multilingual expansion. A red measured")
        print("     here may be green in production. Verdicts are still meaningful as a")
        print("     LOWER BOUND on what production retrieves — never as an upper one.")


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


async def run(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journeys", type=Path, help="kb/journeys/<topic>.yaml")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--collection", default="legal_unified")
    args = parser.parse_args(argv)

    root = repo_root()
    load_env(root)
    sys.path.insert(0, str(root / "apps" / "backend-rag"))

    import yaml

    data = yaml.safe_load(args.journeys.read_text(encoding="utf-8")) or {}
    journeys = data.get("journeys") or []
    if not journeys:
        print("%s declares no journeys — nothing to run" % args.journeys.name)
        return 3

    from backend.services.search.search_service import SearchService

    service = SearchService()

    # ── the control, before anything is graded ──────────────────────────────
    try:
        control = await retrieve(service, CONTROL_QUERY, args.collection, 5)
    except Exception as exc:  # noqa: BLE001 - the reason matters more than the type
        print("BROKEN — the control query raised %s: %s" % (type(exc).__name__, exc))
        print("Nothing was graded. A probe that cannot reach production cannot")
        print("distinguish 'the knowledge base is missing this' from 'I am misconfigured'.")
        return 3

    hit, rank = phrase_hit(control, CONTROL_PHRASE)
    if not control or not hit:
        print("BROKEN — the control query returned %d chunks and the control phrase"
              % len(control))
        print("         %r was %s." % (CONTROL_PHRASE, "absent" if control else "unreachable"))
        print("Nothing was graded. Check QDRANT_URL / QDRANT_API_KEY / OPENAI_API_KEY,")
        print("and that %r resolves to a populated collection." % args.collection)
        return 3
    print("[control] %r found at rank %d of %d — production is reachable"
          % (CONTROL_PHRASE, rank, len(control)))
    warn_if_degraded(root)
    print()

    # ── the journeys ────────────────────────────────────────────────────────
    drift: list[str] = []
    outstanding: list[str] = []
    header = "%-4s %-9s %-9s %-6s  %s" % ("#", "RECORDED", "MEASURED", "RANK", "QUESTION")
    print(header)
    print("-" * max(len(header), 78))

    for i, journey in enumerate(journeys, start=1):
        question = journey.get("question", "")
        phrase = journey.get("verbatim_phrase", "")
        recorded = journey.get("probe_state", "untested")
        try:
            chunks = await retrieve(service, question, args.collection, args.limit)
        except Exception as exc:  # noqa: BLE001
            print("%-4d %-9s %-9s %-6s  %s" % (i, recorded, "ERROR", "-", question[:44]))
            outstanding.append("journey %d raised %s: %s" % (i, type(exc).__name__, exc))
            continue

        hit, rank = phrase_hit(chunks, phrase)
        measured = "green" if hit else "red"
        print("%-4d %-9s %-9s %-6s  %s"
              % (i, recorded, measured, rank if rank else "-", question[:44]))

        if recorded == "untested":
            drift.append(
                "journey %d is recorded 'untested' but has now been run and measured "
                "%r — record it, an unrun verdict is not a verdict" % (i, measured)
            )
        elif recorded != measured:
            drift.append(
                "journey %d records %r, production measures %r — %s"
                % (i, recorded, measured,
                   "the work landed and the file is stale" if measured == "green"
                   else "REGRESSION: this used to be found and no longer is")
            )
        if measured == "red":
            outstanding.append(
                "journey %d: %r is not in the retrieved context for %r"
                % (i, phrase[:48], question[:48])
            )

    print()
    if drift:
        print("DRIFT — the file disagrees with production (%d):" % len(drift))
        for item in drift:
            print("  ! %s" % item)
        print()
        print("The journey file is STALE. Update probe_state / probe_run_at by hand —")
        print("this tool deliberately will not write its own expected value back.")
        return 1

    if outstanding:
        print("OUTSTANDING — %d of %d journeys do not retrieve their phrase:"
              % (len(outstanding), len(journeys)))
        for item in outstanding:
            print("  - %s" % item)
        print()
        print("Red on purpose: the file says red and production agrees. This is the")
        print("state a journey is SUPPOSED to be in on the day it is written (§3).")
        return 2

    print("AT TARGET — every journey retrieves its verbatim phrase.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
