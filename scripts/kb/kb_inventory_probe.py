#!/usr/bin/env python3
"""kb_inventory_probe — measure a kb/inventory/*.yaml against LIVE production.

The CI gate (`test_kb_inventory_contract.py` / `test_kb_topic_contract.py`) proves
an inventory is internally sound — consistent with itself, the registry, the ingest
entrypoints. It cannot prove the inventory still describes the world: CI has no
Qdrant credentials, and a probe that ran there would be flaky theatre. Measured
2026-08-26: four `kind: topic` inventories (kb/inventory/{company,immigration,
property,tax}.yaml) declared point counts and payload-shape mixes "measured
against production" on 2026-08-25, and nothing has re-measured any of them since
— this module dispatches on `kind` for exactly that reason; before this dispatch
existed, handing it a topic file raised KeyError on `compared_with`, a key only
the retired-collection schema carries.

This is the half that touches production. Dispatches on `data["kind"]`:

  kind: retired_collection  (`_run_retired_collection`) — a triage of documents
    queued for promotion/discard/blocking against a READ collection. Answers two
    questions, kept apart because their cures are opposite:
      DRIFT        production no longer matches what the inventory recorded.
                   The inventory is STALE. Re-measure before acting on any of it.
                   -> exit 1
      OUTSTANDING  production matches the recorded baseline, and the dispositions
                   have not been carried out yet. Honest state of a campaign
                   mid-flight, RED on purpose: undone work must not read as success.
                   -> exit 2
      exit 0 only when every document has reached the state its disposition declares.

  kind: topic  (`_run_topic`) — a lane's own scoped instruments inside ONE
    collection. No disposition to reach, so the verdict is binary:
      DRIFT        production has moved since `measured_at` (point count, payload
                   shape mix, or a named instrument's count). -> exit 1
      exit 0 only when every recorded number still matches production.

  Any other `kind` (or none) -> exit 3, BROKEN, nothing measured — same vocabulary
  as the missing-`.env` case below and as `kb/ops/probe_retrieval.py`.

Run it: PYTHONPATH unnecessary; it reads apps/backend-rag/.env for credentials.
    python3 scripts/kb/kb_inventory_probe.py kb/inventory/legal_unified_2026.yaml
    python3 scripts/kb/kb_inventory_probe.py kb/inventory/immigration.yaml
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import os
import re
import sys
from pathlib import Path

WS = re.compile(r"\s+")
CTX = re.compile(r"^\[CONTEXT:[^\]]*\]\s*", re.S)
MIN_FRAGMENT_CHARS = 40  # must match the inventory's containment-proof method


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("kb_inventory_probe: repo root not found")


def resolve_physical(name: str) -> str:
    """Map a LOGICAL collection name (what every kb/inventory/*.yaml records) to
    the live PHYSICAL Qdrant collection.

    MEASURED 2026-08-26, against real production: no literal Qdrant collection
    is named `legal_unified` — `client.get_collections()` lists 14 names, and
    the live one is `legal_unified_hybrid_hybrid`
    (`collection_registry.py::LOGICAL_TO_PHYSICAL_COLLECTIONS`). Before this
    resolution existed, running THIS module's own topic probe against real
    production for all four `kind: topic` inventories printed `[live]
    legal_unified: ABSENT from Qdrant` and reported every instrument at 100%
    DRIFT — true of the STRING, false of the CONTENT: the collection is there,
    holding 84,361 points, under a different literal name. The same bug was
    already latent in `_run_retired_collection`'s `read_name` lookup, which
    this module inherited unchanged and which had never been run against real
    production under test before this fix (`_run_retired_collection` itself
    had zero coverage). A probe that does not resolve is not measuring drift,
    it is measuring its own naming bug — which is exactly the false-positive
    shape this campaign exists to refuse (a red for the wrong reason is as
    untrustworthy as a green for the wrong reason).

    Falls through unchanged for any name the registry does not know (e.g.
    `legal_unified_2026`, itself a literal collection) — `.get(name, name)`,
    the same fallback `collection_registry.resolve_collection_name` itself
    uses, so a name outside the logical registry is passed through rather than
    mangled.
    """
    root = repo_root()
    backend_path = str(root / "apps" / "backend-rag")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from backend.core.collection_registry import resolve_collection_name

    return resolve_collection_name(name)


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        # Exit 3, NOT 1. `SystemExit("...")` with a string exits 1, which is this
        # probe's code for DRIFT — "production has moved and the inventory is
        # stale". Those two states demand opposite actions: DRIFT is cured by
        # re-measuring, a missing .env is cured by configuring, and an operator
        # who reads the wrong one re-measures nothing against nothing. Measured
        # 2026-08-25 in a throwaway worktree, where .env is gitignored and absent:
        # the probe reported the same code as a genuine drift. Same vocabulary as
        # kb/ops/probe_retrieval.py — 3 means BROKEN, and nothing was graded.
        print("BROKEN — %s not found, so there are no credentials to reach Qdrant "
              "with.\nNothing was measured. This is NOT drift: the inventory has "
              "not been checked at all." % env, file=sys.stderr)
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize(text: str) -> str:
    return WS.sub(" ", CTX.sub("", text or "")).strip().lower()


def fragment_hash(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()


PAYLOAD_SHAPES: tuple[str, ...] = (
    "legacy_metadata_text",
    "orphan_no_identity",
    "modern_id_only",
    "modern_id_chunk",
    "modern_full",
)


def payload_shape(payload: dict) -> str:
    """Name which of the modern payload fields this point actually carries.

    Mandate §4.1 calls the modern shape a triple — top-level `document_id`,
    `chunk_key` and `section`. Measured on 2026-08-25, that triple is not one
    shape but three: of the 5,797 points in legal_unified carrying a top-level
    `document_id`, only 792 carry all three; 4,992 carry `document_id` alone and
    13 stop at `chunk_key`. A binary modern/legacy test hides that split, so a
    probe written as `if "document_id" in payload: <read section>` is wrong for
    86% of the points it calls modern. This function names the real shape, and
    the caller compares the census to the inventory so a re-ingest that changes
    the mix goes RED instead of passing unnoticed.
    """
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    if not payload.get("document_id"):
        return "legacy_metadata_text" if meta.get("document_id") else "orphan_no_identity"
    if not payload.get("chunk_key"):
        return "modern_id_only"
    return "modern_full" if payload.get("section") else "modern_id_chunk"


def census(client, collection: str):
    """Per-document point counts, per-document fragment hashes, payload shapes.

    Reads BOTH payload shapes every time (mandate §3.1). A probe that filtered
    only `document_id` reported "0 damaged" for a document with 118 damaged
    points; this one is not allowed to make that mistake.

    Returns `(points, by_doc, hashes_by_doc, all_hashes, shapes, shapes_by_doc)`
    — six values. `shapes_by_doc` (added alongside the topic-drift dispatch) is
    the SAME per-document breakdown `shapes` already aggregates, just not
    collapsed across documents: `shapes_by_doc[doc_id][shape_name]`. A topic
    inventory's `measured_against.points`/`payload_shapes` describe only ITS
    OWN scoped instruments inside a collection SHARED across every lane (§4.1
    — `legal_unified` alone holds 84,283 points across 388 documents; no single
    topic owns more than a few dozen of them), so comparing those fields
    against the WHOLE collection's totals is a false positive by construction,
    every time, for every topic but the one that happens to own the entire
    collection. `shapes_by_doc` is what lets the caller sum only the shapes of
    the documents a topic actually scoped.
    """
    points = 0
    by_doc = collections.Counter()
    hashes_by_doc = collections.defaultdict(set)
    all_hashes = set()
    shapes = collections.Counter()
    shapes_by_doc = collections.defaultdict(collections.Counter)
    offset = None
    while True:
        batch, offset = client.scroll(
            collection, limit=2000, offset=offset, with_payload=True, with_vectors=False
        )
        if not batch:
            break
        for point in batch:
            points += 1
            payload = point.payload or {}
            meta = payload.get("metadata")
            meta = meta if isinstance(meta, dict) else {}
            top = payload.get("document_id")
            nested = meta.get("document_id")
            shape = payload_shape(payload)
            shapes[shape] += 1
            doc = top or nested or "<none>"
            by_doc[doc] += 1
            shapes_by_doc[doc][shape] += 1
            text = payload.get("text") or payload.get("content") or meta.get("text") or ""
            if len(normalize(text)) >= MIN_FRAGMENT_CHARS:
                digest = fragment_hash(text)
                hashes_by_doc[doc].add(digest)
                all_hashes.add(digest)
        if offset is None:
            break
    return points, by_doc, hashes_by_doc, all_hashes, shapes, shapes_by_doc


def shape_drift(collection: str, measured, recorded) -> list[str]:
    """Report every shape whose live count differs from the recorded one.

    Reports absent keys as 0 rather than skipping them: a shape that vanishes
    from production is exactly the drift worth catching, and a loop over only
    the live keys would stay silent about it.
    """
    findings = []
    for shape in PAYLOAD_SHAPES:
        live = measured.get(shape, 0)
        want = recorded.get(shape, 0)
        if live != want:
            findings.append(
                "%s payload shape %s is %d, inventory recorded %d"
                % (collection, shape, live, want)
            )
    unknown = set(recorded) - set(PAYLOAD_SHAPES)
    if unknown:
        findings.append(
            "%s inventory names payload shapes this probe cannot measure: %s"
            % (collection, ", ".join(sorted(unknown)))
        )
    return findings


def topic_drift(data: dict, by_doc, shapes_by_doc) -> list[str]:
    """DRIFT findings for a `kind: topic` inventory (MANDATE.md §2/§4.1).

    Pure function over already-measured census output — no Qdrant object is
    touched here, only `by_doc`/`shapes_by_doc`, two of the six values
    `census()` returns. That is deliberate: the retired-collection gate this
    module already has (`shape_drift`) is tested this way, and a topic inventory
    with a `kind: topic` schema had NO production check at all before this
    function existed — `main()` unconditionally read `data["compared_with"]`,
    a key that only the retired-collection schema carries, and raised KeyError
    on the first topic file handed to it.

    SCOPED TO THE TOPIC'S OWN INSTRUMENTS, not the whole collection. MEASURED
    2026-08-25/26 against all four real `kind: topic` inventories: every one
    of them satisfies `sum(instrument.points) == measured_against.points` and
    the matching identity for `payload_shapes` (also enforced statically by
    `test_kb_topic_contract.py::check_topic_inventory`) — because
    `measured_against` describes what THIS topic's lane scoped and measured,
    inside a `legal_unified` collection SHARED across every other lane (84,283
    points / 388 documents total, measured 2026-08-25; no single topic scopes
    more than a few dozen). An earlier version of this function compared
    `measured_against.points`/`payload_shapes` against the WHOLE collection's
    live totals and reported every topic as 100% DRIFT, on every run, forever
    — a false positive baked into the comparison itself, not a real
    divergence: run against real production, it reported "legal_unified point
    count is 84283, inventory recorded 1868" for the immigration topic, which
    is arithmetically true and means nothing (1868 is what THIS topic scoped;
    84283 is everyone's).

    So both point count and shape mix are summed here ONLY over the
    instrument ids this topic's own `instruments:` list names, before
    comparison — a probe that checked the whole collection would be unable to
    ever pass for a shared collection with more than one lane in it, which is
    every topic collection this campaign has.

    Per-instrument point counts are still read straight from `by_doc` — the
    already-scrolled per-document tally, keyed by `top or nested` (§4.1: a
    document's identity can live at the top level or under
    `metadata.document_id`, and a reader that only checks one is wrong on the
    majority of this corpus's points) — so an instrument counted under either
    payload shape is found here without this function ever issuing a second,
    filtered query of its own. A server-side filter on an unindexed key
    returns HTTP 400, not zero results (MANDATE.md §4.1); reusing the
    already-scrolled tally sidesteps that failure mode entirely rather than
    working around it.
    """
    findings: list[str] = []
    measured = data["measured_against"]
    collection = measured["collection"]
    instrument_ids = [inst.get("id") for inst in data.get("instruments") or []]

    topic_points = sum(by_doc.get(iid, 0) for iid in instrument_ids)
    if topic_points != measured["points"]:
        findings.append(
            "%s (this topic's own instruments) point count is %d, inventory "
            "recorded %d — the collection has moved since %s"
            % (collection, topic_points, measured["points"], data.get("measured_at"))
        )

    topic_shapes = collections.Counter()
    for iid in instrument_ids:
        topic_shapes.update(shapes_by_doc.get(iid, {}))
    findings.extend(shape_drift(collection, topic_shapes, measured["payload_shapes"]))

    for inst in data.get("instruments") or []:
        iid = inst.get("id")
        declared = inst.get("points", 0)
        live = by_doc.get(iid, 0)
        if live != declared:
            findings.append(
                "%s: %d points in %s, inventory recorded %d"
                % (iid, live, collection, declared)
            )
    return findings


def _run_retired_collection(client, data: dict) -> int:
    """The original `main()` body — `kind: retired_collection` — plus ONE fix.

    Extracted so `main()` can dispatch on `data["kind"]` instead of assuming
    this schema for every file handed to it. Exit codes and printed output are
    unchanged from before the dispatch was added, EXCEPT: `topic_name` /
    `read_name` are now resolved through `resolve_physical()` before either
    is checked for membership in `live` or handed to `census()`. They were
    previously used as literal Qdrant collection names — correct for
    `legal_unified_2026` (a literal collection) but wrong for `legal_unified`
    (a logical alias for `legal_unified_hybrid_hybrid`), which this function's
    own `read_name` has always been. That bug was never caught because this
    function had zero test coverage before today; see `resolve_physical`'s
    docstring for how it was found. Display strings keep the LOGICAL name
    throughout (what the inventory itself records), so nothing downstream of
    the resolution — the DOCUMENT table, the drift text — changes shape.
    """
    topic_name = data["measured_against"]["collection"]
    read_name = data["compared_with"]["collection"]
    topic_physical = resolve_physical(topic_name)
    read_physical = resolve_physical(read_name)

    live = {c.name for c in client.get_collections().collections}

    drift: list[str] = []
    outstanding: list[str] = []

    topic_exists = topic_physical in live
    if not topic_exists:
        print("[live] %s: ABSENT from Qdrant" % topic_name)
        topic_points, topic_docs, topic_hashes = 0, collections.Counter(), {}
    else:
        topic_points, topic_docs, topic_hashes, _, topic_shapes, _ = census(client, topic_physical)
        print("[live] %-28s %6d points  %3d docs  shapes=%s"
              % (topic_name, topic_points, len(topic_docs), dict(topic_shapes)))
        drift.extend(shape_drift(topic_name, topic_shapes,
                                 data["measured_against"]["payload_shapes"]))
        if topic_points != data["measured_against"]["points"]:
            drift.append(
                "%s point count is %d, inventory recorded %d — the collection has "
                "moved since %s" % (topic_name, topic_points,
                                    data["measured_against"]["points"], data["measured_at"])
            )

    read_points, read_docs, read_hashes, read_all_hashes, read_shapes, _ = census(client, read_physical)
    print("[live] %-28s %6d points  %3d docs  shapes=%s"
          % (read_name, read_points, len(read_docs), dict(read_shapes)))
    drift.extend(shape_drift(read_name, read_shapes, data["compared_with"]["payload_shapes"]))
    if read_points != data["compared_with"]["points"]:
        drift.append(
            "%s point count is %d, inventory recorded %d" % (read_name, read_points,
                                                             data["compared_with"]["points"])
        )

    print()
    header = "%-24s %-20s %8s %8s %9s  %s" % (
        "DOCUMENT", "DISPOSITION", "in_2026", "in_read", "unshared", "STATE")
    print(header)
    print("-" * len(header))

    for doc in data["documents"]:
        did = doc["document_id"]
        disposition = doc["disposition"]
        in_topic = topic_docs.get(did, 0)
        in_read = read_docs.get(did, 0)
        unshared = len(topic_hashes.get(did, set()) - read_all_hashes) if topic_exists else 0

        recorded = doc["presence_in_legal_unified"]
        if topic_exists and in_topic != doc["points"]:
            drift.append("%s: %d points in %s, inventory recorded %d"
                         % (did, in_topic, topic_name, doc["points"]))
        if in_read != recorded["by_document_id"]:
            drift.append("%s: %d points in %s, inventory recorded %d"
                         % (did, in_read, read_name, recorded["by_document_id"]))

        # target state per disposition
        if disposition == "promote_after_repair":
            reached = unshared == 0 and in_read > 0
            want = "every fragment present in %s" % read_name
        elif disposition in ("discard_duplicate", "catalogue_only"):
            reached = in_topic == 0
            want = "removed from %s" % topic_name
        elif disposition == "blocked_identity":
            reached = in_topic == 0 and not (doc.get("leaked_to_production") and in_read > 0)
            want = "removed from %s (and from %s where it leaked)" % (topic_name, read_name)
        else:
            reached = False
            want = "unknown disposition"

        state = "AT TARGET" if reached else "OUTSTANDING"
        if not reached:
            outstanding.append("%s [%s] — want: %s" % (did, disposition, want))
        print("%-24s %-20s %8d %8d %9d  %s"
              % (did, disposition, in_topic, in_read, unshared, state))

    print()
    if drift:
        print("DRIFT — production no longer matches the recorded measurement (%d):" % len(drift))
        for item in drift:
            print("  ! %s" % item)
        print()
        print("The inventory is STALE. Re-measure before acting on any disposition in it.")
        return 1

    if outstanding:
        print("OUTSTANDING — %d of %d documents have not reached their declared state:"
              % (len(outstanding), len(data["documents"])))
        for item in outstanding:
            print("  - %s" % item)
        print()
        print("Production matches the baseline exactly, so the inventory is sound; the")
        print("WORK is undone. This is red on purpose — see decision.deletions_authorized")
        print("in the inventory for why nothing has been removed yet.")
        return 2

    print("AT TARGET — every document has reached the state its disposition declares.")
    return 0


def _run_topic(client, data: dict) -> int:
    """`kind: topic` — measure ONE collection against the instruments a lane scoped.

    No `documents`/`disposition` machinery here: a topic inventory has no target
    state to reach beyond "the numbers this file recorded are still true" (a
    topic's outstanding REPAIR work — `complete: false` instruments, blocked
    identities — is recorded honestly in the file itself, per MANDATE.md §4.5/§4.2,
    and is not this probe's job to re-litigate). So the verdict is binary: DRIFT
    (exit 1) when production has moved since `measured_at`, AT TARGET (exit 0)
    otherwise — the same two states `shape_drift` already reports for, reused via
    `topic_drift` rather than reimplemented.
    """
    collection = data["measured_against"]["collection"]
    physical = resolve_physical(collection)
    live = {c.name for c in client.get_collections().collections}

    if physical not in live:
        print("[live] %s: ABSENT from Qdrant" % collection)
        by_doc, shapes_by_doc = collections.Counter(), collections.defaultdict(collections.Counter)
    else:
        points, by_doc, _hashes_by_doc, _all_hashes, shapes, shapes_by_doc = census(client, physical)
        # Whole-collection totals, printed for context ONLY — `legal_unified` is
        # SHARED across every lane, so these numbers are never compared against
        # this topic's own `measured_against` (see `topic_drift`'s docstring).
        print("[live] %-28s %6d points total  %3d docs total  shapes=%s"
              % (collection, points, len(by_doc), dict(shapes)))

    findings = topic_drift(data, by_doc, shapes_by_doc)

    print()
    header = "%-28s %10s %10s  %s" % ("INSTRUMENT", "declared", "live", "STATE")
    print(header)
    print("-" * len(header))
    for inst in data.get("instruments") or []:
        iid = inst.get("id")
        declared = inst.get("points", 0)
        live_n = by_doc.get(iid, 0)
        state = "AT TARGET" if live_n == declared else "DRIFT"
        print("%-28s %10d %10d  %s" % (iid, declared, live_n, state))

    print()
    if findings:
        print("DRIFT — production no longer matches the recorded measurement (%d):" % len(findings))
        for item in findings:
            print("  ! %s" % item)
        print()
        print("The inventory is STALE. Re-measure before trusting any number in it —")
        print("MANDATE.md §1: 'measured against production' is the whole claim a topic")
        print("inventory makes, and this is what checks it stayed true.")
        return 1

    print("AT TARGET — every number this inventory recorded still matches production.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    import yaml

    root = repo_root()
    load_env(root)
    from qdrant_client import QdrantClient

    data = yaml.safe_load(args.inventory.read_text(encoding="utf-8"))
    kind = data.get("kind")

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )

    if kind == "topic":
        return _run_topic(client, data)
    if kind == "retired_collection":
        return _run_retired_collection(client, data)

    # Same vocabulary as the missing-.env case above and as kb/ops/probe_retrieval.py:
    # 3 means BROKEN, nothing was measured. An inventory whose `kind` this probe does
    # not recognise must not silently fall through to either schema's KeyErrors, and
    # must not be read as DRIFT (1) or AT TARGET (0) — both would claim a measurement
    # that never happened.
    print(
        "BROKEN — kind=%r is neither 'topic' nor 'retired_collection'; this probe "
        "has no schema for it. Nothing was measured." % kind,
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
