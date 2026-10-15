#!/usr/bin/env python3
"""Payload-only cure of the E28 points in the Qdrant ``visa_oracle`` collection.

Why: the E28A/B/C/D/F points and the KITAP-conversion concept note carried claims
the official Imigrasi pages do not make (E28F as "Real Estate ... Rp 5 billion+",
E28B "direct KITAP after 5y", E28A "KITAP threshold Rp 15 billion", ...), and an
E28G point exists for a visa that is not a current product. The corrected source is
``scripts/enrich_visa_oracle_stay_rules.py`` (RULES / CONCEPT_DOCS); this script
derives every new value from THAT module, so source and fixer cannot diverge.

What it does NOT do: it never embeds anything and never calls an LLM/embedding API
(the old enrich script re-embeds with a paid per-token API; this one only sets
payload fields and deletes one point), and it never changes a vector.

Modes
  default       dry-run: read the points, print per point id the before/after of
                every changed payload field, change nothing.
  --backup P    write the full current points (payload + vector) to P (mode 0600,
                refuses to overwrite) BEFORE any write.
  --apply       perform the writes. Refuses to run without --backup.

  --restore P   put every payload back from the backup file P EXACTLY (overwrite_payload) and
                re-upsert a point that no longer exists (the deleted E28G) with its saved vector.
                Dry-run unless --apply is given.

Idempotent: a second run finds nothing to change (and no E28G point to delete).

Stops at the FIRST error of a write run and prints the exact restore command.

DO NOT use ``scripts/enrich_visa_oracle_stay_rules.py`` as an alternative: it calls the OpenAI
embeddings API (a paid per-token endpoint that needs separate owner authorization) and re-embeds
every point. This fixer never embeds anything.

Environment: QDRANT_URL, QDRANT_API_KEY (never printed).

    cd apps/backend-rag && set -a && . ./.env && set +a && cd ../..
    python3 scripts/fix_visa_oracle_e28_points.py                       # dry-run
    python3 scripts/fix_visa_oracle_e28_points.py --backup ~/visa_oracle_e28_backup.json --apply
    python3 scripts/fix_visa_oracle_e28_points.py --restore ~/visa_oracle_e28_backup.json --apply   # undo
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import logging
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

COLLECTION = "visa_oracle"

# code -> point id, read from PROD on 2026-10-15 (audit F40-F44).
CODE_POINTS: dict[str, str] = {
    "E28A": "762c2f04-031f-5bfc-b86f-1ed8433544a9",
    "E28B": "b5213b2e-aebc-5cc2-bdb1-67ed15d0a5ca",
    "E28C": "1283b444-d5cd-5a67-9259-14d7e2bb8844",
    "E28D": "a2bc3a9d-e8e1-5ded-a4fa-6054379eff26",
    "E28F": "6ecc8c5b-ff30-517c-901c-fc87a896ae68",
}
E28G_POINT_ID = "225aed53-6663-5df6-97fe-bfb49d999800"
CONCEPT_ID = "nb2-kitap-conversion"
CONCEPT_POINT_ID = "b50440ec-a48a-54b5-95b4-2ffe9695dbf5"
CONCEPT_CODE = CONCEPT_ID.upper()

# A target text must contain the OLD sentence this PR replaces, or already the NEW notes
# (idempotent re-run). Anything else is not the point we audited: refuse.
OLD_ANCHORS: dict[str, str] = {
    "E28A": "KITAP threshold INCREASED to Rp 15 billion",
    "E28B": "Direct KITAP-INV after 5y",
    "E28C": "Golden Visa Portfolio Investor",
    "E28D": "Investor Branch/Representative Office",
    "E28F": "Investor Real Estate (IKN Nusantara or property-based)",
}
OLD_CONCEPT_ANCHORS = ("Rp 15 billion", "E28 series, all variants")


def _load_source() -> Any:
    path = Path(__file__).resolve().parent / "enrich_visa_oracle_stay_rules.py"
    name = "_enrich_visa_oracle_stay_rules_src"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses needs the module registered
    spec.loader.exec_module(mod)
    return mod


class RefusedError(Exception):
    """A point does not look like what we expect: nothing is written."""


@dataclass
class Change:
    kind: str  # "set_payload" | "delete"
    point_id: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)  # set_payload body
    before: dict[str, Any] = field(default_factory=dict)  # current payload


def _expect_code(point_id: str, payload: dict[str, Any], code: str) -> None:
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        raise RefusedError(f"point {point_id}: payload.text is missing or not a string")
    if not isinstance(payload.get("metadata"), dict):
        raise RefusedError(f"point {point_id}: payload.metadata is missing or not an object")
    got = payload["metadata"].get("code")
    if got != code:
        raise RefusedError(f"point {point_id}: metadata.code is {got!r}, expected {code!r}")


def concept_text(src: Any) -> str:
    for doc in src.CONCEPT_DOCS:
        if doc["concept_id"] == CONCEPT_ID:
            return doc["text"].strip()
    raise RefusedError(f"concept {CONCEPT_ID} missing from the enrichment source")


def plan_changes(src: Any, current: dict[str, dict[str, Any] | None]) -> list[Change]:
    """Pure: current payloads (None = point absent) -> the writes still needed."""
    changes: list[Change] = []

    for code, pid in CODE_POINTS.items():
        payload = current.get(pid)
        if payload is None:
            raise RefusedError(f"point {pid} ({code}) not found")
        _expect_code(pid, payload, code)
        rule = src.RULES[code]
        text = payload["text"]
        if OLD_ANCHORS[code] not in text and rule.notes not in text:
            raise RefusedError(
                f"point {pid} ({code}): text holds neither the expected old sentence nor the new notes"
            )
        meta = payload.get("metadata") or {}
        new_text = src.replace_stay_block(text, rule)
        if OLD_ANCHORS[code] in new_text:
            # The old claim survives OUTSIDE the stay block this fixer replaces: writing would
            # leave it served, and the post-apply verify would still say "0 pending". Refuse.
            raise RefusedError(
                f"point {pid} ({code}): the old sentence {OLD_ANCHORS[code]!r} survives outside the stay block"
            )
        new_meta = src.build_metadata(meta, rule)
        if new_text != text or new_meta != meta:
            changes.append(
                Change("set_payload", pid, code, {"text": new_text, "metadata": new_meta}, payload)
            )

    concept = current.get(CONCEPT_POINT_ID)
    if concept is None:
        raise RefusedError(f"concept point {CONCEPT_POINT_ID} not found")
    _expect_code(CONCEPT_POINT_ID, concept, CONCEPT_CODE)
    if str(uuid.uuid5(uuid.NAMESPACE_URL, f"nb2-concept:{CONCEPT_ID}")) != CONCEPT_POINT_ID:
        raise RefusedError("concept point id does not match its deterministic uuid5")
    old_text = concept["text"]
    new_text = concept_text(src)
    if new_text != old_text:
        missing = [a for a in OLD_CONCEPT_ANCHORS if a not in old_text]
        if missing:
            raise RefusedError(f"concept point {CONCEPT_POINT_ID}: old anchor(s) not found: {missing}")
        for line in difflib.ndiff(old_text.splitlines(), new_text.splitlines()):
            if line[:2] in ("+ ", "- ") and line[2:].strip() and "E28" not in line:
                raise RefusedError(
                    f"concept point {CONCEPT_POINT_ID}: unexpected drift outside the E28 lines: {line[:80]!r}"
                )
        changes.append(
            Change("set_payload", CONCEPT_POINT_ID, "concept", {"text": new_text}, concept)
        )

    ghost = current.get(E28G_POINT_ID)
    if ghost is not None:
        _expect_code(E28G_POINT_ID, ghost, "E28G")
        changes.append(Change("delete", E28G_POINT_ID, "E28G", {}, ghost))

    return changes


def describe(change: Change) -> str:
    out = [f"--- {change.label}  id={change.point_id}  action={change.kind}"]
    if change.kind == "delete":
        out.append("  point deleted (vector and payload); the visa is not a current product")
        return "\n".join(out)
    for key, new in change.payload.items():
        old = change.before.get(key)
        if key == "metadata":
            old = old or {}
            for k in sorted(set(old) | set(new)):
                if old.get(k, "<absent>") != new.get(k, "<absent>"):
                    out.append(f"  metadata.{k}: {old.get(k, '<absent>')!r} -> {new.get(k, '<absent>')!r}")
        else:
            diff = difflib.unified_diff(
                (old or "").splitlines(), (new or "").splitlines(), "before", "after", lineterm="", n=0
            )
            out.append(f"  {key}:")
            out.extend("    " + d for d in diff)
    return "\n".join(out)


# ---- Qdrant I/O (httpx, injectable client) ---------------------------------------


def fetch_points(client: httpx.Client, ids: list[str], with_vector: bool) -> dict[str, dict[str, Any]]:
    r = client.post(
        f"/collections/{COLLECTION}/points",
        json={"ids": ids, "with_payload": True, "with_vector": with_vector},
    )
    r.raise_for_status()
    return {str(p["id"]): p for p in r.json()["result"]}


def write_backup(path: str, points: dict[str, dict[str, Any]]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"collection": COLLECTION, "points": list(points.values())}, fh)


def apply_change(client: httpx.Client, change: Change) -> None:
    if change.kind == "set_payload":
        r = client.post(
            f"/collections/{COLLECTION}/points/payload",
            params={"wait": "true"},
            json={"payload": change.payload, "points": [change.point_id]},
        )
    else:
        r = client.post(
            f"/collections/{COLLECTION}/points/delete",
            params={"wait": "true"},
            json={"points": [change.point_id]},
        )
    r.raise_for_status()


def all_ids() -> list[str]:
    return [*CODE_POINTS.values(), CONCEPT_POINT_ID, E28G_POINT_ID]


def restore_from_backup(client: httpx.Client, path: str, apply: bool) -> int:
    saved = json.loads(Path(path).read_text())["points"]
    ids = [str(p["id"]) for p in saved]
    present = fetch_points(client, ids, with_vector=False)
    for p in saved:
        pid = str(p["id"])
        action = "overwrite_payload" if pid in present else "upsert (point is missing: re-created with its saved vector)"
        print(f"restore {pid}: {action}")
        if not apply:
            continue
        if pid in present:
            r = client.put(
                f"/collections/{COLLECTION}/points/payload",
                params={"wait": "true"},
                json={"payload": p["payload"], "points": [pid]},
            )
        else:
            r = client.put(
                f"/collections/{COLLECTION}/points",
                params={"wait": "true"},
                json={"points": [{"id": pid, "vector": p["vector"], "payload": p["payload"]}]},
            )
        r.raise_for_status()
    if not apply:
        print(f"{len(saved)} point(s) would be restored (dry-run; add --apply)")
        return 0
    after = fetch_points(client, ids, with_vector=False)
    bad = [str(p["id"]) for p in saved if after.get(str(p["id"]), {}).get("payload") != p["payload"]]
    if bad:
        print(f"RESTORE VERIFY FAILED for {bad}", file=sys.stderr)
        return 4
    print(f"restored {len(saved)} point(s); re-read matches the backup exactly")
    return 0


def main(
    argv: list[str] | None = None,
    client_factory: Callable[[str, str], httpx.Client] | None = None,
    env: dict[str, str] | None = None,
) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="perform the writes (needs --backup, or --restore)")
    ap.add_argument("--backup", metavar="PATH", help="write the full current points here (0600) first")
    ap.add_argument("--restore", metavar="PATH", help="put the payloads (and the deleted point) back from a backup")
    args = ap.parse_args(argv)
    env = os.environ if env is None else env

    if args.apply and not args.backup and not args.restore:
        print("REFUSED: --apply requires --backup <path>", file=sys.stderr)
        return 2
    url, key = env.get("QDRANT_URL"), env.get("QDRANT_API_KEY")
    if not url or not key:
        print("REFUSED: QDRANT_URL and QDRANT_API_KEY must be set in the environment", file=sys.stderr)
        return 2

    factory = client_factory or (
        lambda u, k: httpx.Client(base_url=u, headers={"api-key": k}, timeout=60.0)
    )
    # the enrichment module configures INFO logging; httpx would then log every request URL
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.restore:
        with factory(url, key) as client:
            try:
                return restore_from_backup(client, args.restore, args.apply)
            except Exception as exc:  # stop at once, say what failed
                print(f"RESTORE STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 5
    src = _load_source()
    with factory(url, key) as client:
        points = fetch_points(client, all_ids(), with_vector=True)
        current = {pid: (points[pid]["payload"] if pid in points else None) for pid in all_ids()}
        try:
            changes = plan_changes(src, current)
        except RefusedError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 3

        for change in changes:
            print(describe(change))
        print(f"{len(changes)} change(s) planned ({'APPLY' if args.apply else 'dry-run'})")

        if args.backup:
            write_backup(args.backup, points)
            print(f"backup written: {args.backup} ({len(points)} point(s), mode 0600)")
        if not args.apply or not changes:
            return 0

        for change in changes:
            try:
                apply_change(client, change)
            except Exception as exc:  # stop at the first error; the backup is complete
                print(
                    f"STOPPED at {change.kind} {change.label} {change.point_id}: {type(exc).__name__}: {exc}\n"
                    f"Restore with: python3 scripts/fix_visa_oracle_e28_points.py --restore {args.backup} --apply",
                    file=sys.stderr,
                )
                return 5
            print(f"applied {change.kind} {change.label} {change.point_id}")

        after = fetch_points(client, all_ids(), with_vector=False)
        verify = plan_changes(src, {pid: (after[pid]["payload"] if pid in after else None) for pid in all_ids()})
        if verify:
            print(
                f"VERIFY FAILED: {len(verify)} change(s) still pending after apply\n"
                f"Restore with: python3 scripts/fix_visa_oracle_e28_points.py --restore {args.backup} --apply",
                file=sys.stderr,
            )
            return 4
        print("verified: re-read shows 0 pending changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
