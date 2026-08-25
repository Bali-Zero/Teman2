#!/usr/bin/env python3
"""kb_inventory_probe — measure a kb/inventory/*.yaml against LIVE production.

The CI gate (`test_kb_inventory_contract.py`) proves an inventory is internally
sound and consistent with the registry and the ingest entrypoints. It cannot
prove the inventory still describes the world: CI has no Qdrant credentials, and
a probe that ran there would be flaky theatre.

This is the half that touches production. It answers two different questions, and
keeps them apart because their cures are opposite:

  DRIFT       production no longer matches what the inventory recorded.
              The inventory is STALE. Re-measure before acting on any of it.
              -> exit 1

  OUTSTANDING production matches the recorded baseline, and the dispositions have
              not been carried out yet. This is the honest state of a campaign
              mid-flight, and it is RED on purpose: an inventory whose work is
              undone must not read as success.
              -> exit 2

  exit 0 only when every document has reached the state its disposition declares.

Run it: PYTHONPATH unnecessary; it reads apps/backend-rag/.env for credentials.
    python3 scripts/kb/kb_inventory_probe.py kb/inventory/legal_unified_2026.yaml
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import os
import re
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


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        raise SystemExit("kb_inventory_probe: %s not found — no credentials" % env)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize(text: str) -> str:
    return WS.sub(" ", CTX.sub("", text or "")).strip().lower()


def fragment_hash(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()


def census(client, collection: str):
    """Per-document point counts, per-document fragment hashes, payload shapes.

    Reads BOTH payload shapes every time (mandate §3.1). A probe that filtered
    only `document_id` reported "0 damaged" for a document with 118 damaged
    points; this one is not allowed to make that mistake.
    """
    points = 0
    by_doc = collections.Counter()
    hashes_by_doc = collections.defaultdict(set)
    all_hashes = set()
    shapes = collections.Counter()
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
            shapes["modern" if top else ("legacy" if nested else "neither")] += 1
            doc = top or nested or "<none>"
            by_doc[doc] += 1
            text = payload.get("text") or payload.get("content") or meta.get("text") or ""
            if len(normalize(text)) >= MIN_FRAGMENT_CHARS:
                digest = fragment_hash(text)
                hashes_by_doc[doc].add(digest)
                all_hashes.add(digest)
        if offset is None:
            break
    return points, by_doc, hashes_by_doc, all_hashes, shapes


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
    topic_name = data["measured_against"]["collection"]
    read_name = data["compared_with"]["collection"]

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )
    live = {c.name for c in client.get_collections().collections}

    drift: list[str] = []
    outstanding: list[str] = []

    topic_exists = topic_name in live
    if not topic_exists:
        print("[live] %s: ABSENT from Qdrant" % topic_name)
        topic_points, topic_docs, topic_hashes = 0, collections.Counter(), {}
    else:
        topic_points, topic_docs, topic_hashes, _, topic_shapes = census(client, topic_name)
        print("[live] %-28s %6d points  %3d docs  shapes=%s"
              % (topic_name, topic_points, len(topic_docs), dict(topic_shapes)))
        if topic_points != data["measured_against"]["points"]:
            drift.append(
                "%s point count is %d, inventory recorded %d — the collection has "
                "moved since %s" % (topic_name, topic_points,
                                    data["measured_against"]["points"], data["measured_at"])
            )

    read_points, read_docs, read_hashes, read_all_hashes, read_shapes = census(client, read_name)
    print("[live] %-28s %6d points  %3d docs  shapes=%s"
          % (read_name, read_points, len(read_docs), dict(read_shapes)))
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


if __name__ == "__main__":
    raise SystemExit(main())
