#!/usr/bin/env python3
"""Rebuild or check the committed B03 test fixtures from the frozen .agent-receipts inputs.

stdlib-only. Needs the gitignored .agent-receipts/ tree, so it is a maintenance tool:
the adapter and its tests never run it. `--check` re-derives every fixture and
PROVENANCE.json in memory and fails on any byte difference; without it the files are
(re)written. Fixture names and the pins to compare come from b03_census_adapter.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import b03_census_adapter as adapter  # noqa: E402

MATRIX_REL = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
# Columns the adapter reads (consumer_type is NOT a source column and is not invented).
MATRIX_COLUMNS = ("consumer_id", "entry_point", "disposition", "blocker", "identity_relationships")
HOME_PREFIX_RE = re.compile(r"/Users/[^/\s;]+")
HOME_PLACEHOLDER = "<HOME>"

FORBIDDEN_PATTERNS = {
    "absolute_user_home": re.compile(r"/Users/"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(
        r"(?<![0-9A-Za-z])\+\d[\d\s().-]{7,}\d|(?<![0-9A-Za-z])(?:\+62|62|0)8\d{8,11}(?![0-9A-Za-z])"
    ),
    "credential_value": re.compile(
        r"sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{12,}|-----BEGIN [A-Z ]*KEY|"
        r"gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|"
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
        r"(?i:bearer)\s+[A-Za-z0-9._~+/=-]{16,}|"
        r"(?i:(?:password|passwd|secret|api[_-]?key|token))[\"']?\s*[:=]\s*[\"']?[^\s\"',;]{6,}"
    ),
}


def forbidden_matches(text: str) -> dict[str, int]:
    """Per-pattern match counts for client PII / path / credential shapes (all must be 0)."""
    return {name: len(pat.findall(text)) for name, pat in FORBIDDEN_PATTERNS.items()}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stored_bytes(name: str, content: bytes) -> bytes:
    """Bytes written to disk. '.gz' fixtures are pinned on their DECOMPRESSED content."""
    if name.endswith(".gz"):
        return gzip.compress(content, compresslevel=9, mtime=0)
    return content


def stored_content(name: str, path: Path) -> bytes | None:
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return gzip.decompress(raw) if name.endswith(".gz") else raw


def _compact_json(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def project_matrix(src: bytes) -> tuple[bytes, dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(src.decode("utf-8"), newline=""))
    missing = [col for col in MATRIX_COLUMNS if col not in (reader.fieldnames or ())]
    if missing:
        raise SystemExit(f"matrix is missing required columns: {missing}")
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(MATRIX_COLUMNS)
    rows = redacted = 0
    for row in reader:
        values = []
        for col in MATRIX_COLUMNS:
            value, count = HOME_PREFIX_RE.subn(HOME_PLACEHOLDER, row[col])
            redacted += 1 if count else 0
            values.append(value)
        writer.writerow(values)
        rows += 1
    projection = {
        "format": "csv",
        "columns_kept": list(MATRIX_COLUMNS),
        "columns_dropped": len(reader.fieldnames or ()) - len(MATRIX_COLUMNS),
        "row_order": "preserved",
        "transform": {
            "op": "replace_regex",
            "pattern": "absolute user-home prefix: the Users root plus one path component",
            "replacement": HOME_PLACEHOLDER,
            "cells_changed": redacted,
        },
    }
    return out.getvalue().encode("utf-8"), {"rows": rows, "projection": projection}


def project_source_index(src: bytes) -> tuple[bytes, dict[str, Any]]:
    data = json.loads(src)
    nodes = []
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            raise SystemExit("source index node is not an object")
        nodes.append({"source_id": node["source_id"]} if "source_id" in node else {})
    projection = {"format": "json", "keeps": ["nodes[].source_id"], "row_order": "preserved"}
    return _compact_json({"nodes": nodes}), {"rows": len(nodes), "projection": projection}


def project_jobs(src: bytes) -> tuple[bytes, dict[str, Any]]:
    data = json.loads(src)
    if not isinstance(data, dict) or not data.get("observed_at"):
        raise SystemExit("jobs input has no observed_at")
    jobs = []
    for job in data.get("jobs", []):
        if not isinstance(job, dict):
            raise SystemExit("job is not an object")
        jobs.append({"label_hash": job["label_hash"]} if "label_hash" in job else {})
    projection = {"format": "json", "keeps": ["observed_at", "jobs[].label_hash"], "row_order": "preserved"}
    return _compact_json({"jobs": jobs, "observed_at": data["observed_at"]}), {
        "rows": len(jobs),
        "projection": projection,
    }


def project_observed_at(src: bytes) -> tuple[bytes, dict[str, Any]]:
    data = json.loads(src)
    if not isinstance(data, dict) or not data.get("observed_at"):
        raise SystemExit("input has no observed_at")
    projection = {"format": "json", "keeps": ["observed_at"], "row_order": "n/a"}
    return _compact_json({"observed_at": data["observed_at"]}), {
        "rows": None,
        "projection": projection,
    }


PROJECTORS: dict[str, Callable[[bytes], tuple[bytes, dict[str, Any]]]] = {
    MATRIX_REL: project_matrix,
    adapter.SUPPLEMENTARY_PRIOR_PATHS["source_index"]: project_source_index,
    adapter.SUPPLEMENTARY_PRIOR_PATHS["jobs_pro"]: project_jobs,
    adapter.SUPPLEMENTARY_PRIOR_PATHS["gh_workflows"]: project_observed_at,
}


def derive(repo_root: Path) -> dict[str, bytes]:
    """Return {fixture file name: bytes}, PROVENANCE.json included, from the originals."""
    pins = {**adapter.PINNED_FROZEN_INPUTS, **adapter.PINNED_PRIOR_INPUTS}
    files: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []

    for rel, name in adapter.BYTE_IDENTICAL_FIXTURES.items():
        data = (repo_root / rel).read_bytes()
        source_sha = sha256_bytes(data)
        expected = (
            adapter.INPUT_MANIFEST_SHA256
            if rel.endswith("/INPUT-MANIFEST.json")
            else pins[rel]
        )
        if source_sha != expected:
            raise SystemExit(f"original {rel} does not match its pin")
        files[name] = data
        entries.append(
            {
                "fixture": name,
                "kind": "byte_identical",
                "source_rel_path": rel,
                "source_sha256": source_sha,
                "output_sha256": source_sha,
                "bytes": len(data),
                "stored_encoding": "identity",
                "rows": None,
                "projection": None,
            }
        )

    for rel, (name, _pin) in adapter.PROJECTED_FIXTURES.items():
        src = (repo_root / rel).read_bytes()
        source_sha = sha256_bytes(src)
        if source_sha != pins[rel]:
            raise SystemExit(f"original {rel} does not match its pin")
        data, meta = PROJECTORS[rel](src)
        files[name] = data
        entries.append(
            {
                "fixture": name,
                "kind": "projection",
                "source_rel_path": rel,
                "source_sha256": source_sha,
                "output_sha256": sha256_bytes(data),
                "bytes": len(data),
                "stored_encoding": "gzip" if name.endswith(".gz") else "identity",
                "rows": meta["rows"],
                "projection": meta["projection"],
            }
        )

    for name, data in files.items():
        hits = {k: v for k, v in forbidden_matches(data.decode("utf-8")).items() if v}
        if hits:
            raise SystemExit(f"fixture {name} carries forbidden shapes: {hits}")

    entries.sort(key=lambda entry: entry["fixture"])
    provenance = {
        "kind": adapter.FIXTURE_KIND,
        "campaign_id": "universal-db-wave8-20261015",
        "block_id": "B03",
        "purpose": (
            "Make the B03 adapter tests reproducible from committed files only; "
            "frozen metadata already pinned by the adapter, no new native observation."
        ),
        "manifest_attested_not_copied": sorted(adapter.MANIFEST_ATTESTED_INPUTS),
        "fixtures": entries,
    }
    files[adapter.FIXTURE_PROVENANCE_NAME] = (
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    hits = forbidden_matches(files[adapter.FIXTURE_PROVENANCE_NAME].decode("utf-8"))
    if any(hits.values()):
        raise SystemExit(f"provenance carries forbidden shapes: {hits}")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=HERE.parents[4])
    parser.add_argument("--check", action="store_true", help="compare, never write")
    args = parser.parse_args(argv)

    derived = derive(args.repo_root)
    target = args.repo_root / adapter.FIXTURES_DIR_REL
    status = 0
    for name, data in sorted(derived.items()):
        path = target / name
        digest = sha256_bytes(data)
        if args.check:
            same = stored_content(name, path) == data
            status |= 0 if same else 1
            print(f"{'OK  ' if same else 'DIFF'} {name} {digest}")
        else:
            target.mkdir(parents=True, exist_ok=True)
            path.write_bytes(stored_bytes(name, data))
            print(f"WROTE {name} {digest} {len(data)}")
    if args.check:
        pins_ok = all(
            sha256_bytes(derived[name]) == pin
            for name, pin in adapter.PROJECTED_FIXTURES.values()
        )
        print(f"projected pins in adapter match: {pins_ok}")
        status |= 0 if pins_ok else 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
