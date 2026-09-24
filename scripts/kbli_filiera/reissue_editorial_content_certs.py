#!/usr/bin/env python3
"""reissue_editorial_content_certs.py — re-issue `contentSha256` in the PMA
editorial certification registry for the canonicalIntel codes a sha256-pinned
prose cure has just rewritten, and only when that rewrite is the WHOLE
difference.

WHY THIS EXISTS (2026-09-24, the inverted 49% PT PMA formula)
-------------------------------------------------------------
`contentSha256` binds publication to the exact reviewed bytes of a code's
`intel_2026` (`backend/services/kbli_editorial_certification.py::
matches_editorial_certification`, mirrored by
`apps/mouth/src/lib/kbli-editorial-certification.ts`). A prose cure on a
certified code therefore withdraws that code's whole Intelligence section from
the website, the KG and Qdrant — fail-closed, and the corrected sentence never
reaches a reader. `decertify_editorial_entries.py` can only remove an entry and
`recert_pma_editorial_registry.py` only re-stamps the dataset pin. #6598
re-issued 29 hashes with a hand edit, which the data-plane guard refuses; this
is that step as a compiler.

WHAT MAKES A RE-ISSUE SAFE — four refusals, checked per code
-------------------------------------------------------------
For every code the spec names that is certified in `canonicalIntel`:
1. the registry's `contentSha256` must be the hash of the code's `intel_2026`
   at `--base`: the certified bytes are exactly the pre-cure bytes;
2. every spec field at `--base` must hash to its `old_sha256`;
3. the live `intel_2026` must HASH identically to the base one with exactly
   the spec's replacements applied, so the new hash certifies nothing beyond
   the reviewed bytes plus the spec's graded replacements. The comparison is
   the certification hash itself, never `==`: Python equality calls
   `1 == True == 1.0`, and the hash tells them apart;
4. `pmaFingerprint` recomputed on the live record must equal the registry's.
Any refusal aborts the run (exit 2) before anything is written, and so does a
spec that repeats a JSON key (the reviewer may have graded the other copy). A
code whose entry already hashes the live bytes is a no-op only after 3 and 4
hold, so a second run is idempotent without skipping the chain.

It never certifies a new code, never touches `mouthGold`/`standaloneGold`,
`sourceDatasetSha256` or `reviewedAt` (the recert compiler owns the pin), and
never touches an entry the spec does not name.

Usage (dry-run is the default):
    PYTHONPATH=apps/backend-rag python3 scripts/kbli_filiera/reissue_editorial_content_certs.py \\
        --spec scripts/kbli_filiera/cure_specs/<spec>.json --base origin/main [--apply]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
_FILIERA = str(Path(__file__).resolve().parent)
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import cure_prose_national_openness as C  # noqa: E402

CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
REGISTRY = REPO_ROOT / "data" / "kbli-filiera" / "pma-editorial-certifications.json"
SECTION = "canonicalIntel"
CODE_FIELD = "kode_kbli_2025"
EXIT_OK, EXIT_REFUSED = 0, 2

Hasher = Callable[[Any], str]


class ReissueError(RuntimeError):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ReissueError(f"spec repeats the key {key!r} — a reviewer may have graded the other copy")
        out[key] = value
    return out


def plan(
    spec: dict[str, Any],
    base_records: list[dict[str, Any]],
    live_records: list[dict[str, Any]],
    registry: dict[str, Any],
    content_sha: Hasher,
    pma_fingerprint: Hasher,
) -> list[tuple[str, str, str]]:
    """(code, old contentSha256, new contentSha256) for every entry to move."""
    if spec.get("compiler") != C.LANE:
        raise ReissueError(f"spec is not a {C.LANE} spec — its field paths are that compiler's")
    certs = registry.get(SECTION) or {}
    base_by = {r.get(CODE_FIELD): r for r in base_records}
    live_by = {r.get(CODE_FIELD): r for r in live_records}

    moves: list[tuple[str, str, str]] = []
    for code, entry in spec["codes"].items():
        cert = certs.get(code)
        if cert is None:
            continue
        base, live = base_by.get(code), live_by.get(code)
        if base is None or live is None:
            raise ReissueError(f"{code}: absent from the base or the live canonical")

        expected = copy.deepcopy(base)
        for path, patch in entry["fields"].items():
            was = C.read_field(expected, path)
            if not isinstance(was, str) or _sha256(was) != patch["old_sha256"]:
                raise ReissueError(f"{code}.{path}: base text is not the text the spec was graded against")
            C.write_field(expected, path, patch["new"])
        live_hash = content_sha(live.get("intel_2026"))
        if content_sha(expected.get("intel_2026")) != live_hash:
            raise ReissueError(
                f"{code}: live intel_2026 differs from base + the spec's replacements — "
                "the new hash would certify unreviewed bytes"
            )
        if pma_fingerprint(live) != cert["pmaFingerprint"]:
            raise ReissueError(f"{code}: pmaFingerprint moved — that is a re-review, not a re-issue")

        if cert["contentSha256"] == live_hash:
            continue
        if cert["contentSha256"] != content_sha(base.get("intel_2026")):
            raise ReissueError(
                f"{code}: the registry certifies bytes that are not the base intel_2026 — "
                "something besides this cure moved the certified content"
            )
        moves.append((code, cert["contentSha256"], live_hash))
    return moves


def run(
    spec_path: Path,
    base_records: list[dict[str, Any]],
    canonical_path: Path,
    registry_path: Path,
    apply: bool,
    content_sha: Hasher,
    pma_fingerprint: Hasher,
) -> int:
    live_records = json.loads(canonical_path.read_text(encoding="utf-8"))["data"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
        moves = plan(spec, base_records, live_records, registry, content_sha, pma_fingerprint)
    except ReissueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    certified = sorted(set(spec["codes"]) & set(registry.get(SECTION) or {}))
    print(f"{len(spec['codes'])} code(s) in spec, {len(certified)} certified in {SECTION}, {len(moves)} to re-issue")
    for code, old, new in moves:
        print(f"  {code}  {old[:12]} -> {new[:12]}")
    if not apply:
        print("dry-run — rerun with --apply to write")
        return EXIT_OK
    if not moves:
        return EXIT_OK

    for code, _old, new in moves:
        registry[SECTION][code]["contentSha256"] = new
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {registry_path}")
    return EXIT_OK


def _base_records(base: str) -> list[dict[str, Any]]:
    rel = CANONICAL.relative_to(REPO_ROOT)
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{base}:{rel}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReissueError(f"cannot read canonical at {base}")
    return json.loads(result.stdout)["data"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--base", required=True, help="git ref holding the pre-cure canonical")
    ap.add_argument("--apply", action="store_true", help="write the registry (default: dry-run)")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))
    try:
        from backend.services.kbli_editorial_certification import (  # noqa: E402
            pma_editorial_fingerprint,
            stable_editorial_sha256,
        )
    except ImportError as exc:
        print(f"CANNOT-VERIFY: {exc} — run with PYTHONPATH=apps/backend-rag", file=sys.stderr)
        return EXIT_REFUSED

    try:
        base_records = _base_records(args.base)
    except ReissueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    return run(
        args.spec,
        base_records,
        CANONICAL,
        REGISTRY,
        args.apply,
        stable_editorial_sha256,
        pma_editorial_fingerprint,
    )


if __name__ == "__main__":
    sys.exit(main())
