#!/usr/bin/env python3
"""pii_receipt.py — S6 R6.7/R6.8: PII-lane receipts are generated, never typed.

Spec: docs/specs/2026-09-27-evidence-pack-fixed-point.md, S6 R6.7 and R6.8.
Every countable claim a PII-removal/redaction evidence pack makes (R6.3 counts
and per-category split, the R6.5 redaction probe, the R6.6 `r66:` line, R6.8
descriptor counts) is the output of THIS script, pasted into pack.yml
verbatim. A gate re-runs the same invocation with `--check-in <pack.yml>`:
any byte of difference is a red, and so is a hand-typed number.

PII-SAFE BY CONSTRUCTION. Patterns, category maps and id lists come from
PRIVATE files named on the command line (never committed; R6.6 keeps them in
~/.agent/pii-quarantine/<lane>/, 0600 in a 0700 dir). Patterns reach
`git grep` on stdin, never in argv. The output carries counts and keyed
hashes only: never a matched string and never a private file's path; in
`tree` and `r66` never a tracked path either (not even a --path value).
`descriptor` echoes its --path/--not-path/--text/--not-text terms in clear,
by design: they ARE the public descriptor R6.8 measures, so they must stay at
class level and never name a file. argv is echoed with every private file and every
--path replaced by `@hmac:<16 hex>`, keyed by the lane salt SALT_NAME that
lives beside the private files (created 0600 on first use, refused if group-
or world-readable). A PLAIN hash would not do: a one-line category map, or a
one-line residual list, is reversed by hashing every tracked path or name, so
even the r66 line carries `hmac=` (R6.7 amends R6.6's `sha256=`). The salt is
lane state: it travels and is restored with the private files, every private
input of one invocation must sit in its directory, and rotating it invalidates
every earlier block, as a changed script does.

NO COMMIT SHA IN THE BLOCK. The block is pasted into pack.yml, and that commit
moves HEAD, so a sha in the block would make every re-run at the final head
differ (S1's fixed-point class). The block carries `tree_digest` instead:
sha256 over (mode, blob, path) of every tracked file at --rev OUTSIDE evidence/,
whatever --path scopes the count to. It does not change when the pack is
edited, and it changes when anything else does. The header's `blob=` is the
git blob of the script bytes that ran: a changed script invalidates every
block it produced before, by design.

WHAT `tree` COUNTS. files/hits/lines_any/occurrences count text blobs only;
a binary blob is counted in binary_files, yet a pattern found only inside a
binary still counts in patterns_present, so a name hidden in a binary shows.
The counts include files under evidence/ (a pack that carries a name shows
up), while scope_files and tree_digest exclude them: an evidence-only edit
leaves a block byte-identical only while evidence/ carries no pattern.

FAIL-CLOSED DESCRIPTOR (R6.8). --min-files never goes below 2 (exit 2). A run
without --categories cannot show covers_category n/n, so its verdict is
UNMEASURED and it exits 3 like ISOLATING and NOT-COVERING.

Modes (stdlib only, read-only on the repo):
  tree        pattern hits over tracked files at --rev
  r66         the R6.6 line over the brief, the pack and the body FILE
  descriptor  R6.8: how many tracked text files match a descriptor's predicate
  --selftest  synthetic repo assembled at runtime, guilt and innocence
Exit: 0 ok · 1 --check-in mismatch · 2 usage · 3 R6.8 violation · 4 no block.
"""
from __future__ import annotations

import argparse
import bisect
import difflib
import hashlib
import hmac
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_REL = "scripts/evidence/pii_receipt.py"
HEADER = "# pii_receipt v1"
FOOTER = "# end pii_receipt"
EVIDENCE_PREFIX = "evidence/"
BINARY_SNIFF = 8000
HEDGE_RE = re.compile(r"(?<!\w)(?:one of|some|a few|~[0-9]+)(?!\w)")
LABEL_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
SALT_NAME = ".pii-receipt-salt"


class UsageError(Exception):
    pass


def sha256_hex(data: bytes, n: int = 16) -> str:
    return hashlib.sha256(data).hexdigest()[:n]


def self_blob() -> str:
    data = Path(__file__).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def git(repo: Path, *args: str, stdin: bytes | None = None, ok: tuple[int, ...] = (0,)) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True)
    if proc.returncode not in ok:
        raise UsageError(f"git {args[0]} failed (exit {proc.returncode})")
    return proc.stdout


def read_private(path: str) -> tuple[bytes, list[bytes]]:
    raw = Path(path).expanduser().read_bytes()
    lines = [ln[:-1] if ln.endswith(b"\r") else ln for ln in raw.split(b"\n")]
    return raw, [ln for ln in lines if ln]


def ls_tree_rows(repo: Path, rev: str) -> list[tuple[str, str, str]]:
    out = git(repo, "ls-tree", "-r", "-z", "--full-tree", rev)
    rows = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, kind, obj = meta.split(b" ")
        if kind == b"blob":
            rows.append((mode.decode(), obj.decode(), path.decode("utf-8", "surrogateescape")))
    return rows


def ls_tree(repo: Path, rev: str) -> dict[str, str]:
    return {row[2]: row[1] for row in ls_tree_rows(repo, rev)}


def in_scope(path: str, prefixes: list[str]) -> bool:
    return not prefixes or any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def tree_digest(repo: Path, rev: str) -> str:
    h = hashlib.sha256()
    for mode, sha, path in sorted(ls_tree_rows(repo, rev), key=lambda r: r[2]):
        if not path.startswith(EVIDENCE_PREFIX):
            h.update(f"{mode} {sha}".encode() + b"\0" + path.encode("utf-8", "surrogateescape") + b"\n")
    return h.hexdigest()[:16]


def read_blobs(repo: Path, shas: list[str]):
    proc = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stdin, stdout = proc.stdin, proc.stdout
    if stdin is None or stdout is None:
        proc.kill()
        raise RuntimeError("git cat-file --batch opened without pipes")
    try:
        for sha in shas:
            stdin.write(sha.encode() + b"\n")
            stdin.flush()
            header = stdout.readline().split()
            size = int(header[2])
            data = stdout.read(size)
            stdout.read(1)
            yield sha, data
    finally:
        stdin.close()
        proc.wait()


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:BINARY_SNIFF]


def lane_salt(*private_files: str | None) -> bytes:
    dirs = {Path(f).expanduser().resolve().parent for f in private_files if f}
    if len(dirs) != 1:
        raise UsageError("every private input of one invocation must sit in the same lane directory")
    lane = dirs.pop()
    if lane.stat().st_mode & 0o077:
        raise UsageError("the lane directory holding the private inputs is group/world-accessible; chmod 700 it")
    salt = lane / SALT_NAME
    try:
        fd = os.open(salt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if salt.stat().st_mode & 0o077:
            raise UsageError(f"the lane salt {SALT_NAME} is group/world-readable; chmod 600 it")
        return salt.read_bytes()
    with os.fdopen(fd, "wb") as fh:
        fh.write(os.urandom(32).hex().encode())
    return salt.read_bytes()


def keyed(salt: bytes, raw: bytes) -> str:
    return hmac.new(salt, raw, hashlib.sha256).hexdigest()[:16]


def private_token(salt: bytes, raw: bytes) -> str:
    return "@hmac:" + keyed(salt, raw)


def render(argv: list[str], body: list[str]) -> str:
    head = [f"{HEADER} | script={SCRIPT_REL} | blob={self_blob()}",
            "# argv: " + " ".join(shlex.quote(a) for a in argv)]
    return "\n".join(head + body + [FOOTER]) + "\n"


def flow(nums: list[int]) -> str:
    return "[" + ", ".join(str(n) for n in nums) + "]"


def line_hits(data: bytes, pats: list[bytes]) -> tuple[int, int, int, set[int]]:
    starts = [0] + [m.end() for m in re.finditer(b"\n", data)]
    hits = occurrences = 0
    union: set[int] = set()
    present: set[int] = set()
    for idx, p in enumerate(pats):
        if p not in data:
            continue
        present.add(idx)
        occurrences += data.count(p)
        lines = {bisect.bisect_right(starts, m.start()) - 1 for m in re.finditer(re.escape(p), data)}
        hits += len(lines)
        union |= lines
    return hits, len(union), occurrences, present


def cmd_tree(a: argparse.Namespace) -> tuple[str, int]:
    repo = Path(a.repo)
    raw, pats = read_private(a.patterns)
    if not pats:
        raise UsageError("pattern file has no non-empty line")
    if a.ignore_case and not all(p.isascii() for p in pats):
        raise UsageError("--ignore-case folds ASCII only; a non-ASCII pattern would count differently from git -i")
    folded = [p.lower() for p in pats] if a.ignore_case else pats
    entries = {p: s for p, s in ls_tree(repo, a.rev).items() if in_scope(p, a.path)}
    grep = ["grep", "-z", "-l", "-F", "-f", "-"] + (["-i"] if a.ignore_case else []) + [a.rev, "--"]
    out = git(repo, *grep, stdin=b"\n".join(pats) + b"\n", ok=(0, 1))
    prefix = a.rev + ":"
    cands = sorted({r.decode("utf-8", "surrogateescape")[len(prefix):] for r in out.split(b"\0") if r})
    cands = [c for c in cands if c in entries]
    cat_raw, cat_map = b"", {}
    if a.categories:
        cat_raw, rows = read_private(a.categories)
        for row in rows:
            label, _, path = row.decode("utf-8", "surrogateescape").partition("\t")
            if not LABEL_RE.match(label) or not path:
                raise UsageError("categories file: each line is '<label>\\t<path>', label [a-z0-9_-]{1,32}")
            cat_map[path] = label
    per_file: dict[str, int] = {}
    totals = {"hits": 0, "lines_any": 0, "occurrences": 0, "binary_files": 0}
    present: set[int] = set()
    blobs = dict(read_blobs(repo, sorted({entries[c] for c in cands})))
    for path in cands:
        data = blobs[entries[path]]
        hits, union, occ, pres = line_hits(data.lower() if a.ignore_case else data, folded)
        if hits == 0:
            continue
        present |= pres
        if is_binary(data):
            totals["binary_files"] += 1
            continue
        per_file[path] = hits
        totals["hits"] += hits
        totals["lines_any"] += union
        totals["occurrences"] += occ
    salt = lane_salt(a.patterns, a.categories)
    argv = ["tree", "--patterns", private_token(salt, raw), "--rev", a.rev]
    if a.categories:
        argv += ["--categories", private_token(salt, cat_raw)]
    if a.ignore_case:
        argv.append("--ignore-case")
    for p in a.path:
        argv += ["--path", private_token(salt, p.encode("utf-8", "surrogateescape"))]
    body = ["mode: tree", f"tree_digest: {tree_digest(repo, a.rev)}",
            f"scope_files: {sum(1 for p in entries if not p.startswith(EVIDENCE_PREFIX))}",
            f"patterns: {{hmac: {keyed(salt, raw)}, lines: {len(pats)}}}",
            f"files: {len(per_file)}", f"hits: {totals['hits']}",
            f"lines_any: {totals['lines_any']}", f"occurrences: {totals['occurrences']}",
            f"patterns_present: {len(present)}", f"patterns_absent: {len(pats) - len(present)}",
            f"binary_files: {totals['binary_files']}"]
    if a.categories:
        labels = sorted(set(cat_map.values()))
        body.append(f"categories: {{hmac: {keyed(salt, cat_raw)}, entries: {len(cat_map)}, "
                    f"untracked: {sum(1 for p in cat_map if p not in entries)}, "
                    f"without_hits: {sum(1 for p in cat_map if p in entries and p not in per_file)}}}")
        body.append("by_category:")
        for label in labels + ["uncategorized"]:
            files = [p for p in per_file if cat_map.get(p, "uncategorized") == label]
            counts = sorted((per_file[p] for p in files), reverse=True)
            body.append(f"  {label}: {{files: {len(files)}, hits: {sum(counts)}, per_file: {flow(counts)}}}")
    return render(argv, body), 0


def count_lines(text: str, pred) -> tuple[int, list[int]]:
    hit_lines = [i for i, ln in enumerate(text.split("\n"), 1) if pred(ln)]
    return len(hit_lines), hit_lines


def text_digest(path: str) -> str:
    """sha256[:16] of a text file with CRLF and trailing newlines normalised, so a
    PR body read back from GitHub hashes like the file it was created from."""
    text = Path(path).read_bytes().replace(b"\r\n", b"\n").rstrip(b"\n") + b"\n"
    return sha256_hex(text)


def cmd_r66(a: argparse.Namespace) -> tuple[str, int]:
    raw, pats = read_private(a.patterns)
    if not pats:
        raise UsageError("pattern file has no non-empty line")
    spats = [p.decode("utf-8", "surrogateescape") for p in pats]
    residual = hedge = 0
    hedge_at: list[str] = []
    ids_raw, ids = (read_private(a.ids) if a.ids else (b"", []))
    id_res = [re.compile(r"(?<!\w)" + re.escape(i.decode("utf-8", "surrogateescape")) + r"(?!\w)") for i in ids]
    id_lines = id_occ = 0
    for role in ("brief", "pack", "body"):
        text = Path(getattr(a, role)).read_bytes().decode("utf-8", "surrogateescape")
        n, _ = count_lines(text, lambda ln: any(p in ln for p in spats))
        residual += n
        n, where = count_lines(text, lambda ln: HEDGE_RE.search(ln) is not None)
        hedge += n
        hedge_at += [f"{role}:{i}" for i in where]
        if id_res:
            n, _ = count_lines(text, lambda ln: any(r.search(ln) for r in id_res))
            id_lines += n
            id_occ += sum(len(r.findall(text)) for r in id_res)
    salt = lane_salt(a.patterns, a.ids)
    argv = ["r66", "--patterns", private_token(salt, raw)]
    if a.ids:
        argv += ["--ids", private_token(salt, ids_raw)]
    argv += ["--brief", "@text:" + text_digest(a.brief), "--pack", "PACK",
             "--body", "@text:" + text_digest(a.body)]
    body = ["mode: r66",
            f'r66_line: "r66: hmac={keyed(salt, raw)[:12]} lines={len(pats)} '
            f'residual_hits={residual} hedge_hits={hedge}"',
            f"hedge_hit_lines: [{', '.join(hedge_at)}]"]
    if a.ids:
        body.append(f"ids: {{hmac: {keyed(salt, ids_raw)}, lines: {len(ids)}, "
                    f"id_lines: {id_lines}, id_occurrences: {id_occ}}}")
    return render(argv, body), 0


def min_files_arg(value: str) -> int:
    n = int(value)
    if n < 2:
        raise argparse.ArgumentTypeError("never below 2 (S6 R6.8: one matching file is isolation)")
    return n


class TermAction(argparse.Action):
    def __call__(self, parser, ns, value, option_string=None):
        terms = list(getattr(ns, "terms", None) or [])
        try:
            re.compile(value)
        except re.error as exc:
            raise argparse.ArgumentError(self, f"bad regex: {exc}") from exc
        if option_string is None:
            raise argparse.ArgumentError(self, "a term is an option, never a positional")
        terms.append((option_string.lstrip("-"), value))
        ns.terms = terms


def term_ok(kind: str, rx: re.Pattern, path: str, text: str | None) -> bool:
    subject = path if kind.endswith("path") else text
    found = rx.search(subject) is not None
    return not found if kind.startswith("not-") else found


def cmd_descriptor(a: argparse.Namespace) -> tuple[str, int]:
    terms = getattr(a, "terms", None) or []
    if not terms:
        raise UsageError("descriptor needs at least one --path/--not-path/--text/--not-text term")
    if bool(a.categories) != bool(a.category):
        raise UsageError("--categories and --category go together")
    repo = Path(a.repo)
    compiled = [(k, re.compile(v, re.MULTILINE)) for k, v in terms]
    entries = ls_tree(repo, a.rev)
    universe = {p: s for p, s in entries.items() if not p.startswith(EVIDENCE_PREFIX)}
    depth: dict[str, int] = {}
    pending: dict[str, list[str]] = {}
    for path in sorted(universe):
        d = 0
        while d < len(compiled) and not compiled[d][0].endswith("text"):
            if not term_ok(compiled[d][0], compiled[d][1], path, None):
                break
            d += 1
        depth[path] = d
        if d > 0 or compiled[0][0].endswith("text"):
            pending.setdefault(universe[path], []).append(path)
    binary_skipped = 0
    for sha, data in read_blobs(repo, sorted(pending)):
        if is_binary(data):
            for path in pending[sha]:
                del depth[path]
                binary_skipped += 1
            continue
        text = data.decode("utf-8", "surrogateescape")
        for path in pending[sha]:
            d = depth[path]
            while d < len(compiled) and term_ok(compiled[d][0], compiled[d][1], path, text):
                d += 1
            depth[path] = d
    progressive = [sum(1 for v in depth.values() if v >= i) for i in range(1, len(compiled) + 1)]
    matched = {p for p, v in depth.items() if v == len(compiled)}
    verdict, covers, cat_raw = [], "n/a", b""
    if len(matched) < a.min_files:
        verdict.append("ISOLATING")
    if a.categories:
        cat_raw, rows = read_private(a.categories)
        described = [r.decode("utf-8", "surrogateescape").partition("\t")[2] for r in rows
                     if r.decode("utf-8", "surrogateescape").partition("\t")[0] == a.category]
        if not described:
            raise UsageError("--category names no line of the categories file")
        ok = sum(1 for p in described if p in matched)
        covers = f"{ok}/{len(described)}"
        if ok < len(described):
            verdict.append("NOT-COVERING")
    else:
        verdict.append("UNMEASURED")
    argv = ["descriptor", "--label", a.label, "--rev", a.rev, "--min-files", str(a.min_files)]
    if a.categories:
        argv += ["--categories", private_token(lane_salt(a.categories), cat_raw), "--category", a.category]
    for kind, value in terms:
        argv += ["--" + kind, value]
    body = ["mode: descriptor", f"label: {a.label}", f"tree_digest: {tree_digest(repo, a.rev)}",
            f"terms: {len(compiled)}", f"binary_skipped: {binary_skipped}",
            f"progressive_files: {flow(progressive)}",
            f"files: {len(matched)}", f"min_files: {a.min_files}", f"covers_category: {covers}",
            f"verdict: {'+'.join(verdict) or 'OK'}"]
    return render(argv, body), (3 if verdict else 0)


def pasted_blocks(text: str) -> list[str]:
    blocks, cur, indent = [], None, ""
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if cur is None and stripped.startswith(HEADER + " |"):
            indent, cur = line[: len(line) - len(stripped)], [stripped]
        elif cur is not None:
            cur.append(line[len(indent):] if line.startswith(indent) else line)
            if line.strip() == FOOTER:
                blocks.append("\n".join(cur) + "\n")
                cur = None
    return blocks


def check_in(fresh: str, where: str) -> int:
    argv_line = fresh.splitlines()[1]
    same = [b for b in pasted_blocks(Path(where).read_text("utf-8", "surrogateescape"))
            if b.splitlines()[1:2] == [argv_line]]
    if not same:
        print(f"pii_receipt: NO-BLOCK — {where} carries no pasted block for this argv", file=sys.stderr)
        return 4
    if fresh in same:
        print("pii_receipt: MATCH — the pasted block is byte-identical to this run", file=sys.stderr)
        return 0
    sys.stderr.writelines(difflib.unified_diff(same[0].splitlines(True), fresh.splitlines(True),
                                               "pasted", "re-run"))
    print("pii_receipt: MISMATCH — the pasted block differs from this run", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pii_receipt.py", description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true", help="run the synthetic guilt/innocence suite")
    sub = ap.add_subparsers(dest="mode")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=".", help="repository root (not echoed)")
    common.add_argument("--check-in", metavar="FILE", help="compare against the block pasted in FILE")
    t = sub.add_parser("tree", parents=[common], help="pattern hits over tracked files at --rev")
    t.add_argument("--patterns", required=True, help="PRIVATE fixed-string file, one per line")
    t.add_argument("--rev", default="HEAD")
    t.add_argument("--categories", help="PRIVATE '<label>\\t<path>' file for the per-category split")
    t.add_argument("--ignore-case", action="store_true", help="ASCII case folding")
    t.add_argument("--path", action="append", default=[], help="restrict to a tracked file/dir (repeatable)")
    r = sub.add_parser("r66", parents=[common], help="the S6 R6.6 line")
    r.add_argument("--patterns", required=True, help="PRIVATE residual-basename file (R6.6)")
    r.add_argument("--ids", help="PRIVATE id list for the companion id check")
    for role in ("brief", "pack", "body"):
        r.add_argument("--" + role, required=True)
    d = sub.add_parser("descriptor", parents=[common], help="S6 R6.8 descriptor measurement")
    d.add_argument("--label", required=True)
    d.add_argument("--rev", default="HEAD")
    d.add_argument("--min-files", type=min_files_arg, default=2, help="at least 2 (R6.8)")
    d.add_argument("--categories", help="PRIVATE '<label>\\t<path>' file")
    d.add_argument("--category", help="the label this descriptor describes")
    for kind in ("path", "not-path", "text", "not-text"):
        d.add_argument("--" + kind, action=TermAction, metavar="REGEX", help="ordered predicate term")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.mode:
        ap.error("a mode (tree | r66 | descriptor) or --selftest is required")
    if getattr(a, "label", None) is not None and not LABEL_RE.match(a.label):
        ap.error("--label must match [a-z0-9_-]{1,32}")
    if getattr(a, "category", None) is not None and not LABEL_RE.match(a.category):
        ap.error("--category must match [a-z0-9_-]{1,32}")
    try:
        out, rc = {"tree": cmd_tree, "r66": cmd_r66, "descriptor": cmd_descriptor}[a.mode](a)
    except UsageError as exc:
        print(f"pii_receipt: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"pii_receipt: cannot read an input file ({type(exc).__name__})", file=sys.stderr)
        return 2
    sys.stdout.write(out)
    if a.check_in:
        return check_in(out, a.check_in) or rc
    return rc


def _synthetic_repo(root: Path) -> tuple[Path, Path, list[str]]:
    """A throwaway repo whose 'names' are assembled at runtime from lowercase
    fragments, so no name-shaped literal exists in this file."""
    n1 = " ".join(w.title() for w in ("zq" + "vorn", "plax" + "ter"))
    n2 = " ".join(w.title() for w in ("ukk" + "elo", "brem" + "si"))
    n3 = " ".join(w.title() for w in ("yod" + "rin", "fasq" + "ue"))
    repo = root / "repo"
    files = {
        "src/one.py": f"# {n1} and {n1}\nx = '{n2}'\n",
        "src/two.py": f"y = '{n1}' + '{n2}'\n",
        "tests/fixtures/f.json": f'{{"a": "{n2}"}}\n',
        "docs/clean.md": "nothing to see\n",
        "evidence/x/pack.yml": "outcome: placeholder\n",
    }
    for rel, body in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
    _commit(repo, init=True)
    private = root / "private"
    private.mkdir(mode=0o700)
    pats = private / "names.txt"
    pats.write_text(f"{n1}\n\n{n2}\n{n3}\n")
    cats = private / "cats.txt"
    cats.write_text("code\tsrc/one.py\ncode\tsrc/two.py\n")
    return repo, private, [n1, n2, n3]


def _commit(repo: Path, init: bool = False) -> None:
    base = ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
            "-c", "user.name=selftest", "-c", "user.email=selftest@example.invalid"]
    if init:
        subprocess.run(["git", "-c", "init.templateDir=", "init", "-q", str(repo)], check=True)
    subprocess.run(base + ["add", "-A"], check=True)
    subprocess.run(base + ["commit", "-q", "-m", "fixture"], check=True)


def _run(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), *argv],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def selftest() -> int:
    fails: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            fails.append(what)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo, private, names = _synthetic_repo(root)
        tree = ["tree", "--repo", str(repo), "--patterns", str(private / "names.txt"),
                "--categories", str(private / "cats.txt")]
        rc1, out1 = _run(tree)
        rc2, out2 = _run(tree)
        expect(rc1 == 0 and out1 == out2, "innocence: a re-run reproduces the block byte-identically")
        expect("files: 3" in out1 and "hits: 5" in out1 and "lines_any: 4" in out1
               and "occurrences: 6" in out1 and "patterns_present: 2" in out1,
               "counts: 3 files, 5 hits, 4 lines, 6 occurrences, 2 of 3 patterns (empty line ignored)")
        expect("code: {files: 2, hits: 4, per_file: [2, 2]}" in out1
               and "uncategorized: {files: 1, hits: 1, per_file: [1]}" in out1,
               "per-category split with an uncategorized remainder")
        leaked = [s for s in names + ["src/one.py", "fixtures", str(private)] if s in out1]
        expect(not leaked, "no-leak: no pattern, matched path or private path in the block")
        rc, outp = _run(tree + ["--path", "src/two.py"])
        expect(rc == 0 and "src/two.py" not in outp and "--path @hmac:" in outp,
               "no-leak: a --path value is echoed as a keyed hash, never in clear")
        plain = hashlib.sha256((private / "cats.txt").read_bytes()).hexdigest()[:16]
        expect(plain not in out1 and (private / SALT_NAME).stat().st_mode & 0o777 == 0o600,
               "no-leak: private files are named by HMAC under a 0600 lane salt, not a plain sha256")
        pack = root / "pack.yml"
        pack.write_text("receipts:\n  - result: |\n" + "".join("      " + ln + "\n" for ln in out1.splitlines()))
        rc, _ = _run(tree + ["--check-in", str(pack)])
        expect(rc == 0, "innocence: --check-in on the verbatim paste exits 0")
        pack.write_text(pack.read_text().replace("hits: 5", "hits: 6"))
        rc, _ = _run(tree + ["--check-in", str(pack)])
        expect(rc == 1, "guilt: a hand-edited count in the pasted block exits 1")
        (repo / "evidence/x/pack.yml").write_text("outcome: edited\n" + out1)
        _commit(repo)
        expect(_run(tree)[1] == out1, "innocence: editing only evidence/ leaves the block unchanged")
        (repo / "docs/clean.md").write_text("changed\n")
        _commit(repo)
        expect(_run(tree)[1] != out1, "guilt: any non-evidence change moves tree_digest")
        brief, body = root / "brief.yml", root / "body.md"
        brief.write_text("a total of 3 files\n~30 lines\n")
        body.write_text("something else\nsome files\n")
        (private / "res.txt").write_text("one.py\n")
        pack.write_text("names one.py here\n")
        rc, out = _run(["r66", "--patterns", str(private / "res.txt"), "--brief", str(brief),
                        "--pack", str(pack), "--body", str(body)])
        expect(rc == 0 and "residual_hits=1 hedge_hits=2" in out and "[brief:2, body:2]" in out,
               "r66: word-bounded hedges ('some files', '~30' yes; 'something' no) and residual hits")
        desc = ["descriptor", "--repo", str(repo), "--label", "code", "--categories",
                str(private / "cats.txt"), "--category", "code", "--path", r"\.py$"]
        rc, out = _run(desc)
        expect(rc == 0 and "files: 2" in out and "verdict: OK" in out, "innocence: a descriptor matching 2 files passes")
        rc, out = _run(desc + ["--text", "and"])
        expect(rc == 3 and "ISOLATING" in out, "guilt: a descriptor that narrows to 1 file exits 3")
        pack.write_text("receipts:\n  - result: |\n" + "".join("      " + ln + "\n" for ln in out.splitlines()))
        rc, _ = _run(desc + ["--text", "and", "--check-in", str(pack)])
        expect(rc == 3, "guilt: a byte-identical paste of an ISOLATING block still exits 3 under --check-in")
        rc, out = _run(desc[:-2] + ["--not-path", "^src/"])
        expect(rc == 3 and "files: 2" in out and "covers_category: 0/2" in out
               and "verdict: NOT-COVERING\n" in out,
               "guilt: a 2-file descriptor its own category's files do not match exits 3")
        rc, out = _run(desc + ["--min-files", "1"])
        expect(rc == 2 and out == "", "guilt: --min-files below 2 is refused (exit 2), no block printed")
        rc, out = _run(desc[:5] + desc[-2:])
        expect(rc == 3 and "covers_category: n/a" in out and "verdict: UNMEASURED\n" in out,
               "guilt: a descriptor run without --categories is UNMEASURED and exits 3")
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failing)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
