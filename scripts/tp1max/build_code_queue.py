#!/usr/bin/env python3
"""Build the L-CODE queue (TP1MAX-20261005) from a repo snapshot: one job per source file/chunk.

Every queued job is sent to an external provider (the Alibaba Token Plan), so the input screen is
fail-closed: a file is queued only when it was read, is UTF-8 text under MAX_BYTES, is not a
symlink, sits on a printable-ASCII path, and carries no secret shape, phone number or e-mail address
but a role mailbox or a documentation domain. Anything else is SKIPPED and counted by reason, never sent; a screen that
raises counts as screen_error. Test/fixture/data/content paths are never even read.

Usage: build_code_queue.py <repo> <out queue.jsonl>
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Optional

EXT = (".py", ".sh", ".ts", ".tsx", ".js", ".mjs")
ROOTS = ("scripts/", "apps/backend-rag/backend/", "apps/nuzantara-mcp/", ".claude/hooks/", "infra/",
         "apps/mouth/src/", "apps/kbli-navigator/src/", "apps/")
SKIP_PATH = re.compile(r"(^|/)(\.env|tests?/|__tests__|fixtures?|testdata|test_|.*\.test\.|.*\.spec\.|data/|content/|"
                       r"node_modules|dist/|build/|migrations?/|vendor/|.*secret|.*credential|.*\.min\.)", re.I)
EMAIL = re.compile(r"([A-Za-z0-9._%+!#$&'*?^~-]{1,64})@([\w.-]{1,253}\.(?:[^\W\d_]{2,63}|xn--[\w-]{2,59}))")
# Any address at a domain reserved for documentation (RFC 2606/6761); at the project's own domains only
# a role mailbox. A person's address, on any domain, is PII.
EMAIL_RESERVED = re.compile(r"(?:[a-z0-9-]+\.)*example\.(?:com|net|org)|(?:[a-z0-9-]+\.)+(?:example|test|invalid|localhost)", re.I)
EMAIL_OWN = re.compile(r"(?:[a-z0-9-]+\.)*(?:balizero\.com|zantara\.io|nuzantara\.com)", re.I)
EMAIL_ROLE = re.compile(r"zantara|noreply|no-reply|info|admin|test|support|hello|contact|team|ops|dev|bot|"
                        r"notifications?|alerts?", re.I)
# A run of digits joined by any separator a human puts in a phone number (NBSP, unicode dashes too).
PHONE_RUN = re.compile(r"(?<![A-Za-z0-9])(?:\+[ \t]?)?\(?\d(?:[\d \t  -​  　./()\-‐-―−]*\d)?"
                       r"(?![A-Za-z0-9])")
PHONE_DIGITS = re.compile(r"00[1-9]\d{7,13}|628\d{8,11}|08\d{8,11}|0[2-7]\d{7,10}|62[2-7]\d{7,10}")
FAMILY = re.compile(
    r"xkeysib-[A-Za-z0-9_-]{16,}|\d{8,10}:[A-Za-z0-9_-]{35}|(?:FlyV1\s+|fo1_|fm[12]_)[A-Za-z0-9_+/=-]{16,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}|npm_[A-Za-z0-9]{36}|whsec_[A-Za-z0-9+/=]{16,}|github_pat_[A-Za-z0-9_]{20,}|[sr]k_(?:live|test)_[A-Za-z0-9]{16,}|"
    r"GOCSPX-[A-Za-z0-9_-]{16,}|ya29\.[A-Za-z0-9_-]{20,}|(?:AKIA|ASIA)[0-9A-Z]{16}|AGE-SECRET-KEY-1[0-9A-Z]{50,}|hooks\.slack\.com/services/T[A-Za-z0-9_/]{16,}|xox[a-z]-[A-Za-z0-9-]{16,}|"
    r"sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}|eyJ[\w-]{8,}\.[\w-]{2,}\.[\w-]{10,}|AIza[0-9A-Za-z_-]{30,}")
PEM = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY")  # the header alone: a body may follow as "\n"-escaped text
DSN = re.compile(r"(?<![a-z0-9+.-])[a-z][a-z0-9+.-]{0,20}://[^\s/:@'\"]*:([^\s/@'\"]{2,})@", re.I)
# A key-like NAME (compound too: DB_PASSWORD, client_secret, "api_key":) assigned a literal.
KEYWORD = re.compile(r"(?<![\w.-])[\w.-]{0,40}?(?:passw(?:or)?d|secret|api[_-]?key|access[_-]?key|token)\w{0,40}\\?['\"]?"  # \" too: JSON
                     r"\s*[:=]\s*(?:\\?['\"]{1,3}(?P<q>(?:[^'\"\n\\]|\\.){6,})\\?['\"]|(?P<b>[^\s'\"$`{}()<\[\],;:]{8,}))", re.I)
CHUNK = 700
MIN_CHARS = 300
MAX_BYTES = 512 * 1024

PROMPT = """Adversarial code audit of ONE file (or one chunk of it) from a public repository: ops tooling, a FastAPI/RAG backend and Next.js frontends of a small Indonesian consultancy.
Report ONLY concrete defects you can pin to a line: fail-open guards (an error path that lets a check pass or a monitor stay green), unhandled error paths, races/TOCTOU that can actually happen, dead code that a test or caller still relies on, wrong exit codes, shell pitfalls (missing pipefail, SIGPIPE under pipefail, unquoted expansions, `set -e` traps), wrong regex/off-by-one, timezone bugs, resource leaks, security holes (injection, path traversal, auth bypass). No style remarks, no "could be improved", no speculation about code you cannot see. If you find nothing concrete, return an empty list — that is a good answer.
Reply with ONLY a JSON object: {{"defects":[{{"line":<int>,"severity":"high|medium|low","class":"...","defect":"...","evidence":"<the exact code on that line>"}}]}}

FILE: {path}{part}
-----
{text}
-----"""


def files(repo: Path):
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    for raw in out.split(b"\0"):
        if not raw:
            continue
        try:
            f = raw.decode("utf-8")
        except UnicodeDecodeError:
            yield None, "unsafe_path"
            continue
        if not (f.endswith(EXT) and f.startswith(ROOTS)):
            continue
        if SKIP_PATH.search(f):
            yield f, "excluded_path"
            continue
        yield f, None  # screen() refuses a unicode/control-character path under its own reason


def _placeholder(value: str) -> bool:
    return bool(re.search(r"example|changeme|dummy|fake|sample|placeholder|redacted|your[_-]|<|x{4,}|\*{2}|\.{3}|\u2026",
                          value, re.I))


def _template(value: str) -> bool:
    return bool(re.match(r"\$\{[^}]+\}|\$[A-Z_][A-Z0-9_]*(?![\w])", value))  # ${PG_PASSWORD}, $DB_PASS


def _literal(value: str, quoted: bool, shell: bool = False) -> bool:
    """True when the value assigned to a key-like name looks like a credential, not a name or a reference."""
    lead = ("%", "{", "~", "/") if quoted else ("$", "%", "{", "~", "/", "?", "-", "+", ".", "!")
    if _placeholder(value) or _template(value) or "://" in value or value.startswith(lead):
        return False  # a template, a path, a URL; unquoted also a shell expansion (${X:?msg}) or !!flag
    if re.fullmatch(r"[\d_.]+|(?:[A-Z][A-Za-z]*|x)(?:-[A-Z][A-Za-z]*|-[a-z]+)+|(?i:pass(?:word|wd)?|secret)", value):
        return False  # a number (1_000_000), an X-Header-Name, the placeholder word itself (user:password@host)
    if quoted or shell:  # NAME=value in a shell script is a literal; quoted: only snake_case/CONSTANT_NAME
        return not re.fullmatch(r"[a-z]+(?:[_.][a-z]+)+|[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", value)
    return not re.fullmatch(r"[A-Za-z_]+|[A-Za-z_]\w*(?:\??\.[A-Za-z_]\w*)+!?", value)  # a name, a?.b.c reference


def _has_secret(text: str) -> bool:
    if PEM.search(text) or any(not re.search(r"x{4,}|example|<", m.group(), re.I) for m in FAMILY.finditer(text)):
        return True
    if any(not (_placeholder(v) or _template(v) or re.fullmatch(r"(?i:pass(?:word|wd)?|secret)", v))
           for v in (m.group(1) for m in DSN.finditer(text))):  # a URL password is never a variable name
        return True
    return any(_literal(m.group("q") or m.group("b"), m.group("q") is not None, bool(re.match(r"[A-Z0-9_]+=\S", m.group())))
               for m in KEYWORD.finditer(text))


def _has_phone(text: str) -> bool:
    for run in PHONE_RUN.finditer(text):
        ascii_run = re.sub(r"\d", lambda d: str(unicodedata.decimal(d.group())), run.group())  # fullwidth too
        parts = re.split(r"(\+?\d+)", re.sub(r"^\+[\s(]+", "+", ascii_run).replace("(0)", " "))
        seps, groups = parts[0::2], parts[1::2]  # seps[i] precedes groups[i]
        whole = "".join(groups)  # a spaced-out number whose trunk stands alone: 0 812 3456 7890
        if any(re.search(r"\s", sep) for sep in seps) and len(whole) <= 17 and PHONE_DIGITS.fullmatch(whole.lstrip("+")) \
                and not whole.startswith("00"):
            return True
        for i, first in enumerate(groups):  # group-aligned windows: a phone glued to a neighbouring number counts
            if (i and not re.search(r"\s", seps[i])) or len(first) < 2 or first.startswith("+0"):
                continue  # mid-date (2026-10-06), mid-float (0.0812...), a +0700 offset
            w = ""
            for group in groups[i:i + 16]:  # 16 digits is the longest number any shape below accepts
                w += group
                if len(w) > 17:
                    break
                if w.startswith("+"):
                    if 8 <= len(w) - 1 <= 15:
                        return True
                elif PHONE_DIGITS.fullmatch(w) and (not w.startswith("00") or first.startswith("00")):
                    return True
    return False


def classify(text: str) -> Optional[str]:
    if _has_secret(text):
        return "secret"
    if _has_phone(text):
        return "phone"
    if any(not (EMAIL_RESERVED.fullmatch(domain) or EMAIL_OWN.fullmatch(domain) and EMAIL_ROLE.fullmatch(local.strip("'").split("+")[0]))
           for local, domain in EMAIL.findall(text)):
        return "email"
    return None


def clean(text: str) -> bool:
    return classify(text) is None


def screen(path: Path, root: Optional[Path] = None) -> "tuple[Optional[str], str]":
    """(text, "ok") when the file may leave the machine, else (None, reason). Never raises."""
    try:
        rel = path.relative_to(root).parts if root else ()
        if any(any(ord(c) > 126 or unicodedata.category(c).startswith("C") for c in part) for part in rel):
            return None, "unsafe_path"
        hops = [root.joinpath(*rel[:i]) for i in range(1, len(rel))] if root else []  # a linked DIRECTORY too
        if path.is_symlink() or any(hop.is_symlink() for hop in hops):
            return None, "symlink"  # it would send whatever the link points at, inside the repo or not
        if path.stat().st_size > MAX_BYTES:
            return None, "oversized"
        data = path.read_bytes()
    except (OSError, ValueError):  # ValueError: a path outside root
        return None, "unreadable"
    if len(data) > MAX_BYTES:
        return None, "oversized"
    if not data:
        return None, "empty"
    if b"\0" in data:
        return None, "binary"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "binary"
    if len(text) < MIN_CHARS:
        return None, "short"
    reason = classify("/".join(rel) + "\n" + text)  # the path goes into the job id and the prompt too
    if reason:
        return None, reason
    return text, "ok"


def build(repo: Path) -> "tuple[list[dict], collections.Counter]":
    jobs, skipped, seen = [], collections.Counter(), set()
    prio = lambda f: next(i for i, r in enumerate(ROOTS) if f.startswith(r))  # noqa: E731
    for f, path_reason in sorted(files(repo), key=lambda item: prio(item[0]) if item[0] else len(ROOTS)):
        if path_reason:
            skipped[path_reason] += 1
            continue
        if f in seen:
            continue
        seen.add(f)
        try:
            text, reason = screen(repo / f, repo)
        except Exception:
            text, reason = None, "screen_error"
        if text is None:
            skipped[reason] += 1
            continue
        lines = text.splitlines()
        parts = [(i, lines[i:i + CHUNK]) for i in range(0, len(lines), CHUNK)]
        for k, (start, chunk) in enumerate(parts):
            numbered = "\n".join(f"{start + j + 1:5d}| {line}" for j, line in enumerate(chunk))
            part = f" (lines {start + 1}-{start + len(chunk)} of {len(lines)})" if len(parts) > 1 else ""
            jid = f"code:{f}" + (f"#{k}" if len(parts) > 1 else "")
            jobs.append({"id": jid, "lane": "L-CODE", "prompt": PROMPT.format(path=f, part=part, text=numbered),
                         "sha": hashlib.sha256(text.encode()).hexdigest()[:12]})
    return jobs, skipped


def main(argv: "list[str]") -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    jobs, skipped = build(Path(argv[0]))
    out = Path(argv[1])
    tmp = out.with_suffix(".tmp")  # a live runner may be reading the queue: never leave it half-written
    tmp.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"jobs": len(jobs), "skipped": dict(sorted(skipped.items())),
                      "prompt_chars": sum(len(j["prompt"]) for j in jobs)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
