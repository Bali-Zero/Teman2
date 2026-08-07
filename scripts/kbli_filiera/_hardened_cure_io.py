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
import re
from pathlib import Path


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


# A path SEGMENT that addresses one element of a list nested inside a dict —
# `editorial.byTheNumbers[2].value` needs this for the stat-card cells; every
# other path in this codebase is plain dict traversal and never matches this.
_INDEXED = re.compile(r"^(?P<name>[^\[\]]+)\[(?P<idx>\d+)\]$")


def sha256_of(value: object) -> str:
    """Stable hash of any JSON-serialisable value (a whole record, a single
    field, a sub-dict) — order-independent (`sort_keys=True`) so key
    reordering by an earlier tool never produces a spurious drift refusal."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _step_into(cur: object, seg: str) -> tuple[object, bool]:
    """One path segment, dict key or `name[idx]` list index. Returns
    (value, ok) — `ok` is False when the segment cannot be resolved, so
    callers decide whether that means "missing" (has_field/read_field) or
    "create it" (write_field's intermediate segments)."""
    m = _INDEXED.match(seg)
    if m:
        name, idx = m.group("name"), int(m.group("idx"))
        if not isinstance(cur, dict) or name not in cur:
            return None, False
        seq = cur[name]
        if not isinstance(seq, list) or idx >= len(seq):
            return None, False
        return seq[idx], True
    if not isinstance(cur, dict) or seg not in cur:
        return None, False
    return cur[seg], True


def has_field(rec: dict, path: str) -> bool:
    cur: object = rec
    for key in path.split("."):
        cur, ok = _step_into(cur, key)
        if not ok:
            return False
    return True


def read_field(rec: dict, path: str) -> object:
    cur: object = rec
    for key in path.split("."):
        cur, ok = _step_into(cur, key)
        if not ok:
            raise CureError(f"{path}: the record does not carry this field")
    return cur


def diff_leaf_for_patch_path(path: str) -> str:
    """The dotted-path leaf `_diff_paths` will report for a given patch path.

    `_diff_paths` (below) treats a list as an opaque leaf — it never descends
    into one — so a patch path like `editorial.byTheNumbers[2].value` shows
    up in the untouched-fields diff as `editorial.byTheNumbers` (the whole
    list), never as the indexed sub-path. `verify_untouched`'s declared scope
    must be built from THIS, not from the raw patch keys, or a legitimate
    list-cell edit reads as an undeclared field change and refuses itself.
    """
    out: list[str] = []
    for seg in path.split("."):
        m = _INDEXED.match(seg)
        if m:
            out.append(m.group("name"))
            return ".".join(out)
        out.append(seg)
    return ".".join(out)


def write_field(rec: dict, path: str, value: object) -> None:
    keys = path.split(".")
    cur = rec
    for key in keys[:-1]:
        m = _INDEXED.match(key)
        if m:
            name, idx = m.group("name"), int(m.group("idx"))
            seq = cur.get(name) if isinstance(cur, dict) else None
            if not isinstance(seq, list) or idx >= len(seq):
                raise CureError(f"{path}: cannot traverse into {key!r}")
            cur = seq[idx]
            continue
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    last = keys[-1]
    m = _INDEXED.match(last)
    if m:
        name, idx = m.group("name"), int(m.group("idx"))
        seq = cur.get(name) if isinstance(cur, dict) else None
        if not isinstance(seq, list) or idx >= len(seq):
            raise CureError(f"{path}: cannot write into {last!r} — index out of range")
        seq[idx] = value
    else:
        cur[last] = value


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


def judge_patch(
    rec: dict, old_sha256: str, new_sha256: str | None, code: str = ""
) -> str:
    """Classify one code's plan: "patch" or "noop" — never a value-by-value
    guess (2026-08-08 sector-law fix-pack, item J).

    THE BLIND SPOT THIS CLOSES
    ---------------------------
    Every hardened compiler up to this point resumed with:

        already_patched = all(rec.get(k) == v for k, v in patch.items())
        ...
        if already_patched:
            return {"action": "noop", "reason": "already cured"}

    That check only reads the KEYS NAMED IN THE PATCH. A record whose patched
    fields already carry the target values, but whose UNRELATED fields have
    drifted since this cure's `old_sha256` was pinned (a later cure touched
    the same record, or a hand-edit), passes it and is certified "already
    cured" — the drift is real and it is never reported, because the check
    never looks anywhere else.

    THE FIX
    -------
    `new_sha256` pins the WHOLE record's hash at the fully-cured state this
    spec was authored against (computed AFTER every cure that touches the
    same record has landed — ordering matters, see the fix-pack item J
    docstring in the compiler that calls this). The noop path now requires
    the live record to hash to EXACTLY that pin, not to "coincidentally carry
    the same values on the keys I bothered to check". Anything else —
    including a record that still carries every patched value but has moved
    elsewhere — is a refusal, named, never a silent success.

    `new_sha256=None` means the pin has not been backfilled yet (the normal
    state on a spec's first application): only "patch" or "refuse" are
    possible, matching the original hardened compilers' first-run behaviour.
    """
    current_hash = sha256_of(rec)
    if current_hash == old_sha256:
        return "patch"
    if new_sha256 is not None and current_hash == new_sha256:
        return "noop"
    raise CureError(
        f"{code}: live record hashes to {current_hash!r}, matching neither "
        f"the pinned old_sha256 {old_sha256!r} nor the pinned new_sha256 "
        f"{new_sha256!r} — the record drifted under this adjudication "
        "(re-adjudicated elsewhere, or hand-edited outside the declared "
        "patch); re-derive before writing, do not overwrite blind"
    )
