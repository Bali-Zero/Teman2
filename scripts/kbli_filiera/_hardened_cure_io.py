"""Shared hardening primitives for one-shot canonical/gold cure compilers.

WHY THIS EXISTS
---------------
Item 6 of the 2026-08-08 sector-law brief (ledgered from #3749's Codex round):
`cure_canonical_47222_nota_kondisi.py` and `cure_gold_90200_whatchanged.py`
apply their old/new refusal correctly (double-apply idempotent, drift refused
loudly), but their specs carry no `old_sha256`, no atomic write (plain
`write_text`, non-atomic), and `untouched_fields` is declared in the
docstring but never checked against the actual diff. Retrofitting those two
is OPTIONAL and NOT done here — one ledger line, per the brief. Every NEW
cure compiler from this PR onward uses this module instead of re-deriving
the same three primitives a fourth time:

1. **old_sha256** — the spec pins `sha256_of(record)` computed against the
   exact state the adjudication was made against. A live record that no
   longer hashes to that pin is either already-cured (idempotent noop, if it
   already matches the patched state) or has drifted under the adjudication
   (a hard refusal — re-derive, never guess).
2. **atomic write** — tmp file + `os.replace`, so a crash mid-write can never
   leave a sibling session reading a half-written canonical/gold file
   (superscar #5's isolation discipline extended to filesystem atomicity).
3. **untouched_fields, enforced not just declared** — `verify_untouched()`
   fingerprints every record BEFORE and AFTER the patch: every code other
   than the one(s) named in the plan must be byte-identical, and the named
   code(s) may differ ONLY on the dotted-path field(s) the spec's `patch`
   block actually names. A stray change anywhere else aborts the write.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


def sha256_of(value: object) -> str:
    """Stable hash of any JSON-serialisable value (a whole record, a single
    field, a sub-dict) — order-independent (`sort_keys=True`) so key
    reordering by an earlier tool never produces a spurious drift refusal."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def has_field(rec: dict, path: str) -> bool:
    cur: object = rec
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    return True


def read_field(rec: dict, path: str) -> object:
    cur: object = rec
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            raise CureError(f"{path}: the record does not carry this field")
        cur = cur[key]
    return cur


def write_field(rec: dict, path: str, value: object) -> None:
    keys = path.split(".")
    cur = rec
    for key in keys[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[keys[-1]] = value


def load_dataset(path: Path) -> tuple[dict, list[dict], str]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    records = payload["data"] if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise CureError(f"{path}: expected a non-empty record list")
    return payload, records, text


def atomic_write_text(path: Path, text: str) -> None:
    """tmp-file + os.replace — the write is all-or-nothing at the filesystem
    level. `os.replace` is atomic on both POSIX and Windows within the same
    filesystem, so the tmp file is created as a SIBLING of the target."""
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        # If os.replace succeeded the tmp path no longer exists; if it
        # raised, clean up rather than leave a stray .tmp<pid> file behind.
        if tmp.exists():
            tmp.unlink()


def _diff_paths(before: dict, after: dict, prefix: str = "") -> set[str]:
    """Dotted-path leaves whose value differs between two dicts. Walks
    nested dicts; lists and scalars are compared as leaves (a list that
    changed shape is reported at the path holding the list, not per-index —
    good enough for the flat/1-level-nested KBLI record shape this serves)."""
    paths: set[str] = set()
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        path = f"{prefix}.{key}" if prefix else key
        bv = before.get(key)
        av = after.get(key)
        if isinstance(bv, dict) and isinstance(av, dict):
            paths |= _diff_paths(bv, av, path)
        elif bv != av:
            paths.add(path)
    return paths


def verify_untouched(
    before_records: list[dict],
    after_records: list[dict],
    code_field: str,
    touched_codes: set[str],
    touched_field_paths: dict[str, set[str]],
) -> None:
    """Raise CureError if anything moved outside the declared scope.

    `touched_field_paths` maps code -> the set of dotted paths that code's
    plan is allowed to have changed. Every record whose code is NOT in
    `touched_codes` must be byte-identical (fingerprinted whole, not
    field-by-field — a stray change to an undeclared field on an untouched
    code is exactly the failure mode this function exists to catch). Every
    record IN `touched_codes` may differ only on its own declared paths.
    """
    before_by_code = {str(r.get(code_field)): r for r in before_records}
    after_by_code = {str(r.get(code_field)): r for r in after_records}
    if set(before_by_code) != set(after_by_code):
        raise CureError(
            "untouched_fields: the code population itself changed (a record "
            "was added or removed) — refusing to write"
        )
    for code, before_rec in before_by_code.items():
        after_rec = after_by_code[code]
        if code not in touched_codes:
            if sha256_of(before_rec) != sha256_of(after_rec):
                raise CureError(
                    f"untouched_fields: {code!r} changed and was never named in "
                    "the plan — aborting before write"
                )
            continue
        changed = _diff_paths(before_rec, after_rec)
        allowed = touched_field_paths.get(code, set())
        extra = changed - allowed
        if extra:
            raise CureError(
                f"untouched_fields: {code!r} changed field(s) outside its "
                f"declared scope: {sorted(extra)} (declared: {sorted(allowed)})"
            )
