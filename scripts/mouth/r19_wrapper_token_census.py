#!/usr/bin/env python3
"""READ-ONLY census of every token read inside the /kbli* wrapper (apps/mouth).

Rule (docs/specs/2026-10-08-kbli-r19-wrapper-token-contract.md): no token may be
read inside the wrapper and left undefined by the wrapper. This probe walks the
RENDERED DOM of a local `next dev --webpack` — 5 pages x the 6 states of
.claude/skills/design/strumenti/measure.py — matching every stylesheet rule
(nesting, @media, @supports, @layer) and inline style against each element, and
follows every var() chain where the browser resolves it (at the declaring
element). It prints, as its LAST lines, `read-but-undefined: N` (one line per
token the contract lacks), `colors-outside-direction-a: M` and, from the
state contract (section 7), `state-rows-unseen: U` then `state-colors-off-contract: K`, and the
ground under every text run at rest, `page-grounds-off-contract: G`. Then it opens the surfaces a
click or a query reveals (section 8.4, the search and inspect APIs stubbed from a fixture) and
prints `opened-surfaces: N ok, F failed`, `opened-outside-wrapper: P`, `opened-grounds-off-contract: K`,
`ground-resolver-disagree: R`, then, for the shared components outside /kbli* (section 8.5),
`shared-touched-unpinned: N` and `shared-component-drift: D`, and, last, `opened-text-below-4.5: M`.
A ground is read twice: by the pixels of a screenshot with the text made transparent (they decide)
and by the painter stack under the text (it names the painter); R counts where they disagree.
The verdict is the printed line, never the exit code.

The census runs whole, or in the parts CI runs side by side (`--part`, section 9): each part dumps what it
walked, and `--replay` over the dumps concatenated judges them as one census, first printing
`scenarios-off-manifest: S`, what was received against the one scenario list the parts are cut from.

  python3 scripts/mouth/r19_wrapper_token_census.py [--base-url URL] [--part PART] [--json OUT] [--diff-base REF]
  python3 scripts/mouth/r19_wrapper_token_census.py --replay CENSUS.jsonl
  python3 scripts/mouth/r19_wrapper_token_census.py --export
"""
from __future__ import annotations

import argparse
import ast
import collections
import importlib.util
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/specs/2026-10-08-kbli-r19-wrapper-token-contract.md"
MEASURE = ROOT / ".claude/skills/design/strumenti/measure.py"
PAGES = ["/kbli", "/kbli/55203", "/kbli/51101", "/kbli/56101", "/kbli-explorer"]
DIRECTION_A = {"paper": "#F7F4EE", "elevated": "#FFFCF7", "wash": "#EAE3D8",
               "ink": "#1D2C3B", "muted": "#58626B", "structure": "#233D52",
               "copper": "#A44B36", "line": "#DAD8D1", "line-strong": "#A8ACA9"}
# The PMA verdict triad keeps its semantic hues (each >= 4.5:1 on paper).
SEMANTIC = {"open": "#2E5E4E", "restricted": "#7A5A1E", "closed": "#8E2F2A"}
TYPE = {"Fraunces 450 display", "Manrope 400 15px/1.75"}
NOT_PAINTED = "not painted on this surface"
KINDS = ("var", "class", "rule", "component")
HEADER = ["kind", "token", "value", "reason"]
BEGIN, END = "<!-- contract:begin -->", "<!-- contract:end -->"
SBEGIN, SEND = "<!-- states:begin -->", "<!-- states:end -->"
SHEADER = ["token", "state", "property", "value", "against", "contrast", "reason"]
STATES = {"hover", "group-hover", "focus", "focus-visible", "focus-within", "group-focus-within",
          "group-focus-visible", "selection", "placeholder", "prose-a", "prose-p", "prose-strong", "scrollbar"}
PROPS = {"color", "background", "border", "ring", "shadow", "scrollbar"}
# A state-variant colour class: the variants of section 7 on a colour utility, plus the two
# bare utilities (placeholder-*, scrollbar-*). Sizes, alignment and border styles paint no colour.
STATE_TOKEN = (r"^(?:(?:group-hover|group-focus-within|group-focus-visible|hover|focus-visible|focus-within"
               r"|focus|selection|prose-a|prose-p|prose-strong):(?:shadow-.+|(?:bg|text|border|ring|outline|fill"
               r"|stroke|from|via|to|decoration|caret|accent|divide)-(?!(?:xs|sm|base|lg|xl|[2-9]xl|left|center"
               r"|right|justify|start|end|balance|pretty|wrap|nowrap|ellipsis|clip|solid|dashed|dotted|none)$).+)"
               r"|placeholder-.+|scrollbar-(?!(?:thin|none|auto|hide|gutter-.+)$).+)$")
WALK = [("desktop", "light"), ("mobile", "system-dark")]
UBEGIN, UEND = "<!-- surfaces:begin -->", "<!-- surfaces:end -->"
CBEGIN, CEND = "<!-- surface-classes:begin -->", "<!-- surface-classes:end -->"
UHEADER = ["token", "surface", "ground", "value", "text", "contrast", "reason"]
# opaque: a text-bearing ground (copper only as the action fill); scrim: a backdrop, ink at any alpha;
# mark: a dot, caret or handle with no text, any role at alpha 1.
GROUNDS = {"opaque": {"paper", "elevated", "wash", "copper"}, "scrim": {"ink"},
           "mark": set(DIRECTION_A) | set(SEMANTIC)}
RANK ={None: -1, "wrapper": 0, "above": 1, "nowhere": 2}  # where a var resolves, worst wins


class ContractError(ValueError):
    """The contract table is malformed: refused, never read as empty."""


def _lum(hex6: str) -> float:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _cells(line: str) -> list[str]:
    if not (line.startswith("|") and line.endswith("|")):
        raise ContractError(f"not a table row: {line!r}")
    cells = re.split(r"(?<!\\)\|", line[1:-1])
    return [c.strip().replace("\\|", "|") for c in cells]


def _value(value: str, reason: str, where: str) -> str | None:
    """Returns the hex a row paints (None for type / not painted)."""
    if value == NOT_PAINTED:
        if not reason:
            raise ContractError(f"{where}: '{NOT_PAINTED}' needs a reason")
        return None
    if value.startswith("type "):
        if value[5:] not in TYPE:
            raise ContractError(f"{where}: unknown type value {value!r}")
        return None
    m = re.fullmatch(r"([a-z-]+) (#[0-9A-F]{6})", value)
    if not m:
        raise ContractError(f"{where}: value {value!r} is not '<role> #HEX'")
    role, hx = m.groups()
    if role == "semantic":
        if hx not in SEMANTIC.values() or contrast(hx, DIRECTION_A["paper"]) < 4.5:
            raise ContractError(f"{where}: semantic {hx} is not a PMA triad hue >= 4.5:1 on paper")
        return hx
    if DIRECTION_A.get(role) != hx:
        raise ContractError(f"{where}: {role} is not {hx} in Direction A")
    return hx


def parse_contract(text: str, begin: str = BEGIN, end: str = END) -> dict[tuple[str, str], dict]:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ContractError(f"expected exactly one {begin} ... {end} block")
    lines = [ln.strip() for ln in text.split(begin)[1].split(end)[0].splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) < 3:
        raise ContractError("contract table has no rows")
    if [c.lower() for c in _cells(lines[0])] != HEADER:
        raise ContractError(f"header must be {HEADER}, got {_cells(lines[0])}")
    if not all(re.fullmatch(r":?-{3,}:?", c) for c in _cells(lines[1])) or len(_cells(lines[1])) != 4:
        raise ContractError("second line must be the 4-column separator")
    rows: dict[tuple[str, str], dict] = {}
    for n, line in enumerate(lines[2:], start=3):
        cells = _cells(line)
        if len(cells) != 4:
            raise ContractError(f"row {n}: {len(cells)} cells, expected 4")
        kind, token, value, reason = cells
        token = token.strip("`")
        if kind not in KINDS or not token:
            raise ContractError(f"row {n}: bad kind/token {kind!r} {token!r}")
        if (kind, token) in rows:
            raise ContractError(f"row {n}: duplicate {kind} {token}")
        rows[(kind, token)] = {"value": value, "hex": _value(value, reason, f"row {n}"), "reason": reason}
    return rows


def load_contract(text: str) -> dict[tuple[str, str], dict]:
    """Section 5 and the classes of section 8.2, one authority per token."""
    rows = parse_contract(text)
    extra = parse_contract(text, CBEGIN, CEND)
    both = sorted(f"{k} {t}" for k, t in rows.keys() & extra.keys())
    if both:
        raise ContractError(f"section 8.2 repeats section 5 rows: {', '.join(both)}")
    return {**rows, **extra}


def parse_states(text: str, contract: dict | None = None) -> dict[str, dict]:
    """The state table of section 7: token -> row. Refused, never read as empty."""
    if text.count(SBEGIN) != 1 or text.count(SEND) != 1:
        raise ContractError("expected exactly one states:begin/end block")
    lines = [ln.strip() for ln in text.split(SBEGIN)[1].split(SEND)[0].splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) < 3:
        raise ContractError("state table has no rows")
    if [c.lower() for c in _cells(lines[0])] != SHEADER:
        raise ContractError(f"state header must be {SHEADER}, got {_cells(lines[0])}")
    if not all(re.fullmatch(r":?-{3,}:?", c) for c in _cells(lines[1])) or len(_cells(lines[1])) != len(SHEADER):
        raise ContractError("state table: second line must be the 7-column separator")
    rows: dict[str, dict] = {}
    for n, line in enumerate(lines[2:], start=3):
        cells = _cells(line)
        if len(cells) != len(SHEADER):
            raise ContractError(f"state row {n}: {len(cells)} cells, expected {len(SHEADER)}")
        token, state, prop, value, against, ratio, reason = cells
        token, where = token.strip("`"), f"state row {n}"
        if not token or token in rows:
            raise ContractError(f"{where}: empty or duplicate token {token!r}")
        if state not in STATES or prop not in PROPS:
            raise ContractError(f"{where}: bad state/property {state!r} {prop!r}")
        hx = _value(value, reason, where)
        row = {"state": state, "prop": prop, "value": value, "hex": hx, "reason": reason}
        if hx is None:
            if against != "-" or ratio != "-":
                raise ContractError(f"{where}: a row that paints nothing has no against / contrast")
        else:
            m = re.fullmatch(r"([a-z-]+) (#[0-9A-F]{6})", against)
            if not m or DIRECTION_A.get(m.group(1)) != m.group(2):
                raise ContractError(f"{where}: against {against!r} is not '<role> #HEX' of Direction A")
            got = contrast(hx, m.group(2))
            if ratio != f"{got:.2f}":
                raise ContractError(f"{where}: contrast {ratio} is not {got:.2f}")
            floor = 4.5 if prop in ("color", "background") else 3.0 if prop == "ring" or (
                prop == "border" and state.startswith(("focus", "group-focus"))) else 0.0
            if got < floor:
                raise ContractError(f"{where}: {token} is {got:.2f}:1, below {floor}:1")
            row["against"], row["ratio"] = against, got
        rows[token] = row
    for token, row in rows.items():
        main = (contract or {}).get(("class", token))
        if main and main["hex"] != row["hex"]:
            raise ContractError(f"{token}: state row {row['value']!r} contradicts section 5 {main['value']!r}")
    return rows


def split_variant(token: str) -> tuple[str, str]:
    """(variant, utility), split at the last colon outside brackets, as STATE_JS does."""
    depth, last = 0, -1
    for i, ch in enumerate(token):
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        elif ch == ":" and depth == 0:
            last = i
    return ("", token) if last < 0 else (token[:last], token[last + 1:])


def parse_surfaces(text: str, contract: dict | None = None, states: dict | None = None) -> dict[str, dict]:
    """The surfaces table of section 8: token -> row. Refused, never read as empty."""
    if text.count(UBEGIN) != 1 or text.count(UEND) != 1:
        raise ContractError("expected exactly one surfaces:begin/end block")
    lines = [ln.strip() for ln in text.split(UBEGIN)[1].split(UEND)[0].splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) < 3:
        raise ContractError("surfaces table has no rows")
    if [c.lower() for c in _cells(lines[0])] != UHEADER:
        raise ContractError(f"surfaces header must be {UHEADER}, got {_cells(lines[0])}")
    if not all(re.fullmatch(r":?-{3,}:?", c) for c in _cells(lines[1])) or len(_cells(lines[1])) != len(UHEADER):
        raise ContractError("surfaces table: second line must be the 7-column separator")
    roles = {**DIRECTION_A, **SEMANTIC}
    rows: dict[str, dict] = {}
    for n, line in enumerate(lines[2:], start=3):
        cells = _cells(line)
        if len(cells) != len(UHEADER):
            raise ContractError(f"surface row {n}: {len(cells)} cells, expected {len(UHEADER)}")
        token, surface, ground, value, text_roles, ratio, reason = cells
        token, where = token.strip("`"), f"surface row {n}"
        if not token or token in rows or not surface or not reason:
            raise ContractError(f"{where}: empty or duplicate token {token!r}, or no surface / reason")
        if split_variant(token)[0]:
            raise ContractError(f"{where}: {token} carries a state variant; section 7 owns it")
        if ("class", token) in (contract or {}) or token in (states or {}):
            raise ContractError(f"{where}: {token} already has a section 5 or 7 row")
        hx = _value(value, reason, where)
        row = {"surface": surface, "ground": ground, "value": value, "hex": hx, "text": [], "reason": reason}
        if hx is None:
            if (ground, text_roles, ratio) != ("-", "-", "-"):
                raise ContractError(f"{where}: a row that paints nothing has no ground, text or contrast")
        else:
            role = next((k for k, v in SEMANTIC.items() if v == hx), None) or value.split()[0]
            if role not in GROUNDS.get(ground, ()):
                raise ContractError(f"{where}: {value!r} is not a {ground!r} ground ({GROUNDS})")
            if ground in ("scrim", "mark") or text_roles == "-":
                if (text_roles, ratio) != ("-", "-"):
                    raise ContractError(f"{where}: a scrim, a mark, or a ground with no text has no text / contrast")
            else:
                names = [r.strip() for r in text_roles.split(",")]
                if not all(r in roles for r in names):
                    raise ContractError(f"{where}: text roles {names} are not roles of section 3")
                got = min(contrast(roles[r], hx) for r in names)
                if ratio != f"{got:.2f}":
                    raise ContractError(f"{where}: contrast {ratio} is not {got:.2f}")
                if got < 4.5:
                    raise ContractError(f"{where}: {token} carries text at {got:.2f}:1, below 4.5:1")
                row["text"], row["ratio"] = names, got
        rows[token] = row
    return rows


def judge_states(census: dict, states: dict) -> tuple[list[str], int]:
    """Lines naming each state class whose observed paint is off its row, and their count."""
    allowed = set(DIRECTION_A.values()) | set(SEMANTIC.values())
    off = []
    for token, ob in sorted(census.get("state_obs", {}).items()):
        row, seen = states.get(token), sorted(set(ob["observed"]))
        if row is None:
            off.append(f"  {token}  undeclared state class, e.g. {ob['selector']} on {ob['page']} {ob['walk']}")
        elif row["hex"] and seen:
            wrong = [h for h in seen if h[:7] != row["hex"]]
            bad = row["hex"] not in {h[:7] for h in seen} if row["prop"] == "ring" else bool(wrong)
            if bad or (row["prop"] != "ring" and any(h[:7] not in allowed for h in seen)):
                off.append(f"  {token}  expected {row['hex']}, painted {', '.join(seen)} ({ob['state']} {ob['prop']}), "
                           f"e.g. {ob['selector']} on {ob['page']} {ob['walk']}")
    return off, len(off)


def unseen_rows(census: dict, states: dict) -> list[str]:
    """Painted state rows whose class is in the DOM but was never observed: a 0 must not hide them."""
    return [f"  {t}  ({states[t]['state']} {states[t]['prop']}), e.g. {ob['selector']} on {ob['page']} {ob['walk']}"
            for t, ob in sorted(census.get("state_obs", {}).items())
            if t in states and states[t]["hex"] and not ob["observed"]]


def verdict(census: dict, contract: dict, states: dict | None = None) -> list[str]:
    reads, colors = census["reads"], census["colors"]
    failed = census.get("failed", [])
    by_kind = {k: sum(1 for r in reads.values() if r["kind"] == k) for k in KINDS}
    out = [f"captures: {len(census['captures'])} ok, {len(failed)} failed"]
    for page in census["pages"]:
        caps = [c for c in census["captures"] if c["page"] == page]
        roots = sorted({c["root"] for c in caps}) or ["-"]
        out.append(f"  {page}: {len(caps)}/{len(census['states'])} states, root {' | '.join(roots)}, "
                   f"elements {sorted({c['elements'] for c in caps})}")
    out += [f"  capture-failed: {f}" for f in failed]
    out.append(f"reads: {len(reads)} tokens (" + ", ".join(f"{k} {v}" for k, v in by_kind.items()) + ")")
    above = sorted(k for k, r in reads.items() if r["kind"] == "var" and r["defined"] != "wrapper")
    out.append(f"defined-above-wrapper: {len(above)} (informational; resolved outside the wrapper today)")
    allowed = {r["hex"] for r in contract.values() if r["hex"]} | set(DIRECTION_A.values())
    outside = sorted((h for h in colors if h[:7] not in allowed), key=lambda h: -colors[h]["count"])
    for h in outside:
        c = colors[h]
        out.append(f"  colour {h} x{c['count']} {c['prop']} e.g. {c['selector']} on {c['page']} {c['state']}")
    missing = sorted(k for k, r in reads.items() if (r["kind"], r["token"]) not in contract
                     and not (r["kind"] == "class" and r["token"] in (states or {})))
    tail = f" (INCOMPLETE: {len(failed)} captures failed, not a verdict)" if failed or not census["captures"] else ""
    out.append(f"read-but-undefined: {len(missing)}{tail}")
    for k in missing:
        r = reads[k]
        out.append(f"  {r['kind']} {r['token']}  e.g. {r['selector']} on {r['page']} {r['state']}")
    out.append(f"colors-outside-direction-a: {len(outside)}")
    walk_failed = census.get("walk_failed", [])
    if states is None:
        out.append("state-colors-off-contract: REFUSED (no state table)")
    elif not census.get("walks") or walk_failed:
        out += [f"  walk-failed: {f}" for f in walk_failed]
        out.append("state-rows-unseen: INCOMPLETE (no judged walk)")
        out.append(f"state-colors-off-contract: INCOMPLETE ({len(walk_failed)} walks failed, "
                   f"{len(census.get('walks', []))} ok, not a verdict)")
    else:
        unseen = unseen_rows(census, states)
        out.append(f"state-rows-unseen: {len(unseen)}")
        out += unseen
        lines, count = judge_states(census, states)
        out += lines
        out.append(f"state-colors-off-contract: {count}")
    return out


def dump(census: dict, path: Path) -> None:
    """JSON Lines: a header, then one read / colour per line, sorted by token."""
    head = {k: census[k] for k in ("schema", "pages", "states", "captures", "failed", "walks", "walk_failed",
                                   "parts", "seconds") if k in census}
    lines = [json.dumps(head, sort_keys=True)]
    lines += [json.dumps({"read": k, **census["reads"][k]}, sort_keys=True) for k in sorted(census["reads"])]
    lines += [json.dumps({"color": k, **census["colors"][k]}, sort_keys=True) for k in sorted(census["colors"])]
    lines += [json.dumps({"state_ob": k, **census["state_obs"][k]}, sort_keys=True) for k in sorted(census["state_obs"])]
    if "opened" in census:
        lines[0] = json.dumps({**head, "opened_walked": True, "shared_failed": census.get("shared_failed", [])},
                              sort_keys=True)
        lines += [json.dumps({"opened": f"{o['name']} {o['walk']}", **o}, sort_keys=True) for o in census["opened"]]
        lines += [json.dumps({"shared": f"{o['name']} {o['walk']}", **o}, sort_keys=True)
                  for o in census.get("shared", [])]
    path.write_text("\n".join(lines) + "\n")


def load(path: Path) -> dict:
    """One dump, or the dumps of the CI parts concatenated in any order (section 9). The parts are folded in
    the order of PARTS, a token two parts read as one run folds it; against_scenarios() then puts every
    scenario back where one full run takes it. No dump at all is a census of the parts, every scenario missing."""
    docs: list[list[dict]] = []
    for ln in path.read_text().splitlines():
        if ln.strip():
            row = json.loads(ln)
            if "schema" in row:
                docs.append([row])
            elif not docs:
                raise ValueError(f"{path}: a row before any header")
            else:
                docs[-1].append(row)
    if not docs:
        viewports, themes = measure_literals()
        docs = [[{"schema": 1, "pages": PAGES, "states": [f"{v}/{t}" for v in viewports for t in themes],
                  "captures": [], "failed": [], "walks": [], "walk_failed": [], "parts": []}]]
    rank = {p: i for i, p in enumerate(("full",) + PARTS)}
    docs.sort(key=lambda d: min((rank.get(p, len(rank)) for p in d[0].get("parts", [])), default=-1))
    census: dict = {"reads": {}, "colors": {}, "state_obs": {}}
    for head, *rows in docs:
        for k, v in head.items():
            if k in ("captures", "failed", "walks", "walk_failed", "shared_failed", "parts"):
                census.setdefault(k, []).extend(v)
            elif k == "seconds":
                census.setdefault(k, {}).update(v)
            elif census.setdefault(k, v) != v:
                raise ValueError(f"{path}: the dumps disagree on {k}")
        if head.get("opened_walked"):
            census.setdefault("opened", [])
            census.setdefault("shared", [])
        for row in rows:
            if "opened" in row or "shared" in row:
                key = "opened" if "opened" in row else "shared"
                row.pop(key)
                census[key].append(row)
                continue
            key = next(k for k in ("read", "color", "state_ob") if k in row)
            name = row.pop(key)
            prev = census[key + "s"].get(name)
            if prev is None:
                census[key + "s"][name] = row
                continue
            prev["count"] += row["count"]
            if key == "read" and RANK[row["defined"]] > RANK[prev["defined"]]:
                prev.update({k: row[k] for k in ("defined", "selector", "page", "state")})
            if key == "state_ob":
                prev["observed"] += [v for v in row["observed"] if v not in prev["observed"]]
    return census


# In-page half: evaluated by Playwright with the packages/core component names.
PROBE_JS = r"""
(core) => {
  const CORE = new Set(core);
  // The colour-bearing property families of src/test/r19-colour-guard.ts
  // (COLOUR_BEARING), minus geometry, plus the face and its weight: Direction A
  // fixes one weight per face (refuter finding, 2026-10-08).
  const BEARING = /background|border|outline|shadow|fill|stroke|caret|accent|decoration|column-rule|scrollbar|stop-color|flood-color|lighting-color|filter|text-emphasis|tap-highlight|text-stroke/;
  const GEOMETRY = /radius|width|style|collapse|spacing|offset|size|position|repeat|origin|clip|attachment|blend|slice|outset|mode|type|opacity|fill-rule|dash|linecap|linejoin|miterlimit|thickness|decoration-line|gutter|shape|composite/;
  const PAINT = { test: (p) => /^(color|-webkit-text-fill-color|font|font-family|font-weight)$/.test(p) || (BEARING.test(p) && !GEOMETRY.test(p)) };
  const family = (p) => p.startsWith("font") ? "font" : p.includes("shadow") ? "shadow"
    : /^(color|-webkit-text-fill-color)$/.test(p) ? "color" : p.match(BEARING)[0].replace(/-color$/, "");
  const INHERITED = new Set(["color", "font", "fill", "stroke", "caret"]);
  const DYNAMIC = /:(hover|focus-visible|focus-within|focus|active|visited|target)(?![\w-])/g;
  const PSEUDO = /::?(before|after|placeholder|selection|marker|first-line|first-letter|backdrop|file-selector-button|-webkit-[\w-]+|-moz-[\w-]+)(?![\w-])/g;
  // A pseudo-element that exists only on some elements is tested on those.
  const ONLY = { placeholder: ":is(input, textarea)", "file-selector-button": 'input[type="file"]', marker: ":is(li, summary)" };
  const KEYWORD = new Set(["transparent", "currentcolor", "inherit", "initial", "unset", "revert", "revert-layer", "none"]);
  const isColour = new Map();

  const splitTop = (s, sep) => {
    const out = []; let depth = 0, quote = "", cur = "";
    for (const ch of s) {
      if (quote) { if (ch === quote) quote = ""; }
      else if (ch === '"' || ch === "'") quote = ch;
      else if (ch === "(" || ch === "[") depth++;
      else if (ch === ")" || ch === "]") depth = Math.max(0, depth - 1);
      if (ch === sep && !depth && !quote) { out.push(cur); cur = ""; } else cur += ch;
    }
    out.push(cur);
    return out.map((x) => x.trim()).filter(Boolean);
  };
  const decls = (text) => splitTop(text || "", ";").map((d) => {
    const i = d.indexOf(":");
    if (i <= 0) return null;
    const p = d.slice(0, i).trim();
    return [p.startsWith("--") ? p : p.toLowerCase(), d.slice(i + 1).replace(/!important\s*$/i, "").trim()];
  }).filter(Boolean);
  const vars = (v) => [...v.matchAll(/var\(\s*(--[\w-]+)/g)].map((m) => m[1]);
  const literal = (v) => /#[0-9a-f]{3,8}\b|\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix|light-dark)\(|gradient\(/i.test(v)
    || v.split(/[^a-zA-Z-]+/).some((w) => {
      if (!w || w.startsWith("-") || KEYWORD.has(w.toLowerCase())) return false;
      if (!isColour.has(w)) isColour.set(w, CSS.supports("color", w));
      return isColour.get(w);
    });
  const keywordOnly = (v) => v.split(/\s+/).every((w) => KEYWORD.has(w.toLowerCase()));
  const paints = (p, v) => !p.startsWith("--") && PAINT.test(p)
    && (vars(v).length > 0 || (family(p) === "font" ? !keywordOnly(v) : literal(v)));
  const valid = (s) => { try { document.documentElement.matches(s); return true; } catch (e) { return false; } };
  const testable = (part) => {
    let t = part.replace(DYNAMIC, "")
      .replace(new RegExp("(^|[\\s>+~])" + PSEUDO.source, "g"), (m, pre, name) => pre + (ONLY[name] || "*"))
      .replace(PSEUDO, (m, name) => ONLY[name] || "").trim();
    if (!t || /[>+~(,]$/.test(t)) t += "*";
    return valid(t) ? t : valid(part) ? part : null;
  };

  const RULES = [], skipped = [];
  const add = (sel, style) => {
    const ds = decls(style.cssText);
    const paint = ds.filter(([p, v]) => paints(p, v));
    const defs = ds.filter(([p]) => p.startsWith("--"));
    if (!paint.length && !defs.length) return;
    for (const part of splitTop(sel, ",")) {
      const t = testable(part);
      if (t) RULES.push({ part: part.replace(/\s+/g, " "), t, paint, defs, cond: t !== part });
    }
  };
  const nest = (parent, sel) => {
    if (!parent) return sel;
    const p = splitTop(parent, ",").length > 1 ? `:is(${parent})` : parent;
    return splitTop(sel, ",").map((s) => (s.includes("&") ? s.replaceAll("&", p) : `${p} ${s}`)).join(", ");
  };
  const mediaOk = (t) => /hover|pointer/.test(t) || matchMedia(t).matches;
  const walk = (list, parent) => {
    for (const r of list) {
      const T = r.constructor.name;
      if (T === "CSSStyleRule") {
        const sel = nest(parent, r.selectorText);
        add(sel, r.style);
        if (r.cssRules && r.cssRules.length) walk(r.cssRules, sel);
      } else if (T === "CSSNestedDeclarations") { if (parent) add(parent, r.style); }
      else if (T === "CSSMediaRule") { if (mediaOk(r.media.mediaText)) walk(r.cssRules, parent); }
      else if (T === "CSSSupportsRule") { if (CSS.supports(r.conditionText)) walk(r.cssRules, parent); }
      else if (T === "CSSImportRule") { try { walk(r.styleSheet.cssRules, parent); } catch (e) { skipped.push(r.href); } }
      else if (T === "CSSKeyframesRule" || T === "CSSFontFaceRule" || T === "CSSPropertyRule") continue;
      else if (r.cssRules) walk(r.cssRules, parent);
    }
  };
  for (const s of [...document.styleSheets, ...(document.adoptedStyleSheets || [])]) {
    try { walk(s.cssRules, null); } catch (e) { skipped.push(s.href || "inline"); }
  }

  const root = document.querySelector('[data-presentation="r19"]') || document.querySelector(".r19-direction-a")
    || [...document.querySelectorAll("[style]")].find((e) => /--font-montserrat/.test(e.getAttribute("style")))
    || (document.getElementById("kbli-explorer-jsonld") || {}).parentElement;
  if (!root) return { root: null };
  const how = root.matches('[data-presentation="r19"]') ? "[data-presentation=r19]"
    : root.matches(".r19-direction-a") ? ".r19-direction-a"
    : root.querySelector(":scope > #kbli-explorer-jsonld") ? "parent of #kbli-explorer-jsonld" : "[style*=--font-montserrat]";

  const info = new Map();
  const get = (el) => {
    if (info.has(el)) return info.get(el);
    const rules = RULES.filter((r) => el.matches(r.t));
    const defs = new Map();
    const def = (p, v) => (defs.get(p) || defs.set(p, []).get(p)).push(v);
    for (const r of rules) for (const [p, v] of r.defs) def(p, { v, part: r.part });
    const inline = decls(el.getAttribute("style"));
    for (const [p, v] of inline) if (p.startsWith("--")) def(p, { v, part: null });
    const x = { rules, defs, inline };
    info.set(el, x);
    return x;
  };
  const definer = (el, tok) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const d = get(n).defs.get(tok);
      if (d) return [n, d];
    }
    return [null, []];
  };
  const paintOf = (el) => {
    const out = [];
    for (const r of get(el).rules) for (const [p, v] of r.paint) out.push({ p, fam: family(p), v, part: r.part, cond: r.cond });
    for (const [p, v] of get(el).inline) if (paints(p, v)) out.push({ p, fam: family(p), v, part: null });
    if (el instanceof SVGElement) {
      for (const a of ["fill", "stroke", "stop-color"]) {
        const v = el.getAttribute(a);
        if (v && (vars(v).length || literal(v))) out.push({ fam: family(a), v, part: null });
      }
    }
    // A filter paints colour only through drop-shadow(); blur and grayscale do not.
    const cs = getComputedStyle(el);
    return out.filter((x) => x.fam !== "filter" || cs.getPropertyValue(x.p).includes("drop-shadow"));
  };
  const path = (el) => {
    const bits = [];
    for (let n = el; n && n.nodeType === 1 && bits.length < 3; n = n.parentElement) {
      const cls = typeof n.className === "string" ? n.className.trim().split(/\s+/).filter(Boolean).slice(0, 2) : [];
      bits.unshift(n.tagName.toLowerCase() + cls.map((c) => "." + c).join(""));
      if (n === root) break;
    }
    return bits.join(">");
  };
  const owner = (el) => {
    const k = Object.keys(el).find((x) => x.startsWith("__reactFiber$"));
    const o = k && el[k] && el[k]._debugOwner;
    return o ? o.name || (o.type && (o.type.displayName || o.type.name)) || null : null;
  };
  const classOf = (el, part) => {
    for (const c of el.classList) {
      const e = "." + CSS.escape(c);
      let rest = part.slice(e.length);
      if (!part.startsWith(e) || /^[\w\\-]/.test(rest)) continue;
      while (/\([^()]*\)/.test(rest)) rest = rest.replace(/\([^()]*\)/g, "");
      if (!/[\s>+~]/.test(rest)) return c; // the class sits on the subject compound
    }
    return null;
  };

  const reads = new Map();
  const note = (kind, token, selector, defined) => {
    const key = kind + " " + token;
    const prev = reads.get(key);
    if (!prev) reads.set(key, { kind, token, selector, defined, count: 1 });
    else {
      prev.count++;
      const rank = { wrapper: 0, above: 1, nowhere: 2 };
      if (defined && rank[defined] > rank[prev.defined]) Object.assign(prev, { defined, selector });
    }
  };
  const follow = (el, value, selector, seen) => {
    for (const tok of vars(value)) {
      if (seen.has(tok)) continue;
      seen.add(tok);
      const [n, defs] = definer(el, tok);
      if (!tok.startsWith("--tw-")) note("var", tok, selector, !n ? "nowhere" : root.contains(n) ? "wrapper" : "above");
      for (const d of defs) {
        // A colour that reaches the paint through Tailwind plumbing (from-*,
        // ring-*, shadow-<colour>) is decided by the class that sets --tw-*.
        const c = tok.startsWith("--tw-") && d.part && classOf(n, d.part);
        if (c) note("class", c, selector, null);
        follow(n, d.v, selector, seen);
      }
    }
  };
  const record = (src, p, selector, who) => {
    if (p.part) {
      const c = classOf(src, p.part);
      if (c) note("class", c, selector, null);
      else note("rule", `${p.part} { ${p.fam} }`, selector, null);
    }
    if (who && CORE.has(who)) note("component", `${who} { ${p.fam} }`, selector, null);
    follow(src, p.v, selector, new Set());
  };

  const elements = [root, ...root.querySelectorAll("*")];
  for (const el of elements) {
    const selector = path(el);
    const own = paintOf(el);
    const who = owner(el);
    for (const p of own) record(el, p, selector, who);
    if (el !== root) continue;
    // The wrapper inherits what it does not paint itself, and shows the
    // backdrop of the nearest painted ancestor when its own is transparent.
    // A :hover or ::pseudo paint is not the element's own resting paint.
    const have = new Set(own.filter((p) => !p.cond).map((p) => p.fam));
    if (getComputedStyle(root).backgroundColor !== "rgba(0, 0, 0, 0)") have.add("background");
    for (let n = root.parentElement; n; n = n.parentElement) {
      const got = new Set();
      for (const p of paintOf(n)) {
        if (have.has(p.fam) || !(INHERITED.has(p.fam) || p.fam === "background")) continue;
        record(n, p, `${path(n)} (inherited by the wrapper)`, owner(n));
        if (!p.cond) got.add(p.fam);
      }
      got.forEach((f) => have.add(f));
    }
  }

  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const rgba = (c) => {
    const m = c.match(/^rgba?\(([^)]+)\)$/);
    if (m) {
      const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
      return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    }
    ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = "#000"; ctx.fillStyle = c; ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const hex = ([r, g, b, a]) => "#" + [r, g, b].map((x) => Math.round(x).toString(16).padStart(2, "0")).join("").toUpperCase()
    + (a < 1 ? "/" + a.toFixed(2) : "");
  const colors = new Map();
  const seeColour = (value, prop, el) => {
    const c = rgba(value);
    if (c[3] === 0) return;
    const h = hex(c);
    const prev = colors.get(h);
    if (prev) prev.count++;
    else colors.set(h, { hex: h, prop, selector: path(el), count: 1 });
  };
  for (const el of elements) {
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    if (cs.display === "none" || cs.visibility === "hidden" || box.width < 1 || box.height < 1) continue;
    if ([...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) seeColour(cs.color, "color", el);
    seeColour(cs.backgroundColor, "background-color", el);
    for (const side of ["top", "right", "bottom", "left"]) {
      const b = (k) => cs.getPropertyValue(`border-${side}-${k}`);
      if (parseFloat(b("width")) > 0 && !["none", "hidden"].includes(b("style"))) {
        seeColour(b("color"), "border-color", el);
      }
    }
  }
  return { root: how, elements: elements.length, rules: RULES.length, skipped, reads: [...reads.values()], colors: [...colors.values()] };
}
"""


# In-page half of the state walk (section 7.5): installs window.__r19s on the wrapper.
STATE_JS = r"""
(pattern) => {
  const TOKEN = new RegExp(pattern);
  const root = document.querySelector('[data-presentation="r19"]') || document.querySelector(".r19-direction-a")
    || [...document.querySelectorAll("[style]")].find((e) => /--font-montserrat/.test(e.getAttribute("style")))
    || (document.getElementById("kbli-explorer-jsonld") || {}).parentElement;
  if (!root) return { root: null };
  const style = document.createElement("style");
  style.textContent = "*,*::before,*::after{transition:none!important;animation:none!important}";
  document.head.append(style);
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  // The rgb channels of the computed colour with the alpha DROPPED, for every syntax Chrome computes
  // (rgb, color(srgb), oklab, oklch, lab, lch): Tailwind writes `/NN` as color-mix(in oklab, ...),
  // which computes to oklab(L a b / A). The canvas un-premultiplies and drifts (copper at 30% read
  // #A64C35), so the alpha is cut off the string first and the canvas only ever sees an opaque colour.
  const hex = (c) => {
    const am = c.match(/\/\s*([\d.]+)(%?)\s*\)$/);
    if (am && parseFloat(am[1]) === 0) return "transparent";
    let p, m;
    const opaque = c.replace(/\s*\/\s*[\d.]+%?\s*\)$/, ")");
    if ((m = opaque.match(/^rgba?\(([^)]+)\)$/))) p = m[1].split(/[\s,]+/).filter(Boolean).map(Number);
    else if ((m = opaque.match(/^color\(srgb ([^)]+)\)$/))) { p = m[1].split(/\s+/).filter(Boolean).map(Number).map((x) => x * 255); }
    else {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = "#000"; ctx.fillStyle = opaque; ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      if (d[3] === 0) return "transparent";
      p = [d[0], d[1], d[2]];
    }
    if (m && m[1].split(/[\s,]+/).filter(Boolean).length > 3 && !am) { const a = parseFloat(m[1].split(/[\s,]+/).filter(Boolean)[3]); if (a === 0) return "transparent"; }
    return "#" + p.slice(0, 3).map((x) => Math.round(x).toString(16).padStart(2, "0")).join("").toUpperCase();
  };
  // The variant is everything before the last colon OUTSIDE brackets: `[color:var(--x)]` is a utility.
  const split = (t) => {
    let depth = 0, last = -1;
    for (let i = 0; i < t.length; i++) {
      const ch = t[i];
      if (ch === "[" || ch === "(") depth++;
      else if (ch === "]" || ch === ")") depth--;
      else if (ch === ":" && depth === 0) last = i;
    }
    return last < 0 ? ["", t] : [t.slice(0, last), t.slice(last + 1)];
  };
  const group = (el) => el.closest(".group");
  const COND = {
    "hover": (el) => el.matches(":hover"),
    "group-hover": (el) => !!group(el) && group(el).matches(":hover"),
    "focus": (el) => el.matches(":focus"),
    "focus-visible": (el) => el.matches(":focus-visible"),
    "focus-within": (el) => el.matches(":focus-within"),
    "group-focus-within": (el) => !!group(el) && group(el).matches(":focus-within"),
    "group-focus-visible": (el) => !!group(el) && group(el).matches(":focus-visible"),
  };
  const textOf = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    ? el : [...el.querySelectorAll("*")].find((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) || el;
  const read = (el, state, util) => {
    const [kind] = util.split("-");
    if (state === "selection") {
      const t = textOf(el), r = document.createRange();
      r.selectNodeContents(t); getSelection().removeAllRanges(); getSelection().addRange(r);
      const pick = (e) => hex(getComputedStyle(e, "::selection")[kind === "bg" ? "backgroundColor" : "color"]);
      return [pick(el), pick(t)];
    }
    if (state === "placeholder") return [hex(getComputedStyle(el, "::placeholder").color)];
    if (state.startsWith("prose-")) {
      const t = el.querySelector(state.slice(6)); return t ? [hex(getComputedStyle(t).color)] : [];
    }
    const cs = getComputedStyle(el);
    if (kind === "bg") return [hex(cs.backgroundColor)];
    if (kind === "text") return [hex(cs.color)];
    if (kind === "border") {
      const side = (util.match(/^border-([trbl])(?:-|$)/) || [, "t"])[1];
      return [hex(cs.getPropertyValue("border-" + { t: "top", r: "right", b: "bottom", l: "left" }[side] + "-color"))];
    }
    if (kind === "ring") return [...cs.boxShadow.matchAll(/rgba?\([^)]+\)|color\([^)]+\)/g)].map((m) => hex(m[0])).filter((h) => h !== "transparent");
    if (kind === "outline") return [hex(cs.outlineColor)];
    return [];
  };
  const obs = new Map();
  const tokens = (el) => [...el.classList].filter((c) => TOKEN.test(c));
  const els = [root, ...root.querySelectorAll("*")].filter((el) => el.classList && el.classList.length);
  const path = (el) => el.tagName.toLowerCase() + [...el.classList].slice(0, 2).map((c) => "." + c).join("");
  const seen = (token, state, prop, el, values) => {
    let o = obs.get(token);
    if (!o) obs.set(token, o = { token, state, prop, observed: [], selector: path(el), count: 0 });
    o.count++;
    for (const v of values) if (!o.observed.includes(v)) o.observed.push(v);
  };
  const PROP = { bg: "background", text: "color", border: "border", ring: "ring", outline: "ring" };
  const observe = () => {
    for (const el of els) for (const token of tokens(el)) {
      const [variant, util] = split(token);
      const state = variant || (util.startsWith("placeholder-") ? "placeholder" : "scrollbar");
      const prop = state === "placeholder" ? "color" : state === "scrollbar" ? "scrollbar" : PROP[util.split("-")[0]] || "shadow";
      const live = state in COND ? COND[state](el) : state === "selection" || state === "placeholder" || state.startsWith("prose-");
      if (prop === "scrollbar") {
        const parts = [...getComputedStyle(el).scrollbarColor.matchAll(/rgba?\([^)]+\)|color\([^)]+\)/g)].map((m) => hex(m[0]));
        seen(token, state, prop, el, util.startsWith("scrollbar-thumb") && parts[0] ? [parts[0]] : []);
        continue;
      }
      if (!live || prop === "shadow") { seen(token, state, prop, el, []); continue; }
      seen(token, state, prop, el, read(el, state, util));
    }
  };
  const targets = () => {
    const out = new Set();
    for (const el of els) for (const token of tokens(el)) {
      const v = split(token)[0];
      if (v === "hover") out.add(el); else if (v === "group-hover" && group(el)) out.add(group(el));
    }
    const shown = [...out].filter((e) => { const b = e.getBoundingClientRect(); return b.width > 1 && b.height > 1 && getComputedStyle(e).visibility !== "hidden"; });
    shown.forEach((e, i) => e.setAttribute("data-r19-hover", String(i)));
    return shown.length;
  };
  window.__r19s = { observe, targets, hex, collect: () => [...obs.values()], blur: () => { document.activeElement && document.activeElement.blur(); getSelection().removeAllRanges(); } };
  return { root: "ok", tokens: els.reduce((n, e) => n + tokens(e).length, 0) };
}
"""


def _load_measure():
    spec = importlib.util.spec_from_file_location("measure", MEASURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def core_components() -> list[str]:
    names = set()
    for f in (ROOT / "packages/core/components").glob("*.tsx"):
        if ".test." not in f.name:
            names.add(f.stem)
            names |= set(re.findall(r"export (?:const|function) ([A-Z]\w+)", f.read_text()))
    return sorted(names)


def measure_literals() -> tuple[dict, dict]:
    """measure.py's VIEWPORTS and THEMES, read without importing it (it imports Playwright)."""
    found = {}
    for node in ast.parse(MEASURE.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("VIEWPORTS", "THEMES"):
                    found[target.id] = ast.literal_eval(node.value)
    for name in ("VIEWPORTS", "THEMES"):
        if name not in found:
            raise SystemExit(f"{MEASURE}: top-level {name} literal not found")
    return found["VIEWPORTS"], found["THEMES"]


def export() -> dict:
    """The probe, pages, six states and palette, for the armed apps/mouth test."""
    viewports, themes = measure_literals()
    states = [{"name": f"{v}/{t}", "width": w, "height": h, "scheme": scheme, "forced": forced}
              for v, (w, h) in viewports.items()
              for t, (scheme, forced) in themes.items()]
    return {"probe": PROBE_JS, "pages": PAGES, "core": core_components(), "states": states,
            "direction_a": DIRECTION_A, "semantic": SEMANTIC,
            "semantic_on_paper": {k: round(contrast(h, DIRECTION_A["paper"]), 2) for k, h in SEMANTIC.items()}}


def _wait(url: str, seconds: int) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                if r.status < 400:
                    return
        except Exception:
            time.sleep(2)
    raise SystemExit(f"dev server never answered {url}")


def live(base: str, part: str | None = None) -> dict:
    """One full census, or the scenarios of one part (section 9): either way the scenarios run in the order
    of the one list, scenarios()."""
    from playwright.sync_api import sync_playwright
    m = _load_measure()
    units = [u for u in scenarios(m.VIEWPORTS, m.THEMES) if part in (None, u[0])]
    census: dict = {"schema": 1, "pages": PAGES, "captures": [], "failed": [], "reads": {}, "colors": {},
                    "state_obs": {}, "walks": [], "walk_failed": [], "parts": [part or "full"],
                    "states": [f"{v}/{t}" for v in m.VIEWPORTS for t in m.THEMES]}
    loads = {how[0] if kind in ("capture", "walk") else how[0][1].split("?")[0] for _, kind, _, how in units}
    for p in PAGES:
        if p in loads:
            _wait(base + p, 300)
    seconds = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        for kind, run in (("capture", capture_pages), ("walk", walk_states), ("opened", walk_opened),
                          ("shared", walk_opened)):
            todo = [u for u in units if u[1] == kind]
            if todo:
                clock = time.monotonic()
                run(browser, m, base, census, todo)
                seconds[kind] = round(time.monotonic() - clock)
        browser.close()
    census["seconds"] = {part or "full": seconds}
    return census


def capture_pages(browser, m, base: str, census: dict, units: list | None = None) -> None:
    """Each page in each of the six states: the tokens read, the colours painted, the grounds at rest."""
    core = core_components()
    for _, kind, _, (page_path, vname, tname) in scenarios(m.VIEWPORTS, m.THEMES) if units is None else units:
        if kind != "capture":
            continue
        w, h = m.VIEWPORTS[vname]
        scheme, forced = m.THEMES[tname]
        state = f"{vname}/{tname}"
        ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
        ctx.add_init_script(FREEZE_JS)
        page = ctx.new_page()
        try:
            resp = page.goto(base + page_path, wait_until="load", timeout=180000)
            if resp is None or resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status if resp else 'none'}")
            page.wait_for_timeout(250)
            if forced:
                page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", forced)
            page.wait_for_function("() => document.readyState === 'complete'", timeout=60000)
            quiet(page)
            page.wait_for_timeout(1500)
            force_theme(page, forced)
            res = page.evaluate(PROBE_JS, core)
            if not res.get("root"):
                raise RuntimeError("wrapper root not found")
        except Exception as exc:  # a failed capture must never read as clean
            census["failed"].append(f"{page_path} {state}: {exc}".splitlines()[0][:200])
            ctx.close()
            continue
        census["captures"].append({"page": page_path, "state": state, "root": res["root"],
                                   "elements": res["elements"], "rules": res["rules"],
                                   "skipped_sheets": res["skipped"]})
        try:
            census["captures"][-1].update(page_grounds(page, f"{page_path} {state}"))
        except Exception as exc:  # a page that was not read through is never clean
            census["captures"][-1].update(page_incomplete=True,
                                          page_error=str(exc).splitlines()[0][:160])
        for r in res["reads"]:
            key = f"{r['kind']} {r['token']}"
            prev = census["reads"].get(key)
            if prev is None:
                census["reads"][key] = {**r, "page": page_path, "state": state}
            else:
                prev["count"] += r["count"]
                if RANK[r["defined"]] > RANK[prev["defined"]]:
                    prev.update(defined=r["defined"], selector=r["selector"], page=page_path, state=state)
        for c in res["colors"]:
            prev = census["colors"].get(c["hex"])
            if prev is None:
                census["colors"][c["hex"]] = {**{k: c[k] for k in ("count", "prop", "selector")},
                                              "page": page_path, "state": state}
            else:
                prev["count"] += c["count"]
        ctx.close()


def walk_states(browser, m, base: str, census: dict, units: list | None = None) -> None:
    """Hover through page.hover, focus through Tab, selection through a range: section 7.5."""
    for _, kind, _, (page_path, vname, tname) in scenarios(m.VIEWPORTS, m.THEMES) if units is None else units:
        if kind != "walk":
            continue
        w, h = m.VIEWPORTS[vname]
        scheme, forced = m.THEMES[tname]
        name = f"{page_path} {vname}/{tname}"
        ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
        page = ctx.new_page()
        try:
            resp = page.goto(base + page_path, wait_until="load", timeout=180000)
            if resp is None or resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status if resp else 'none'}")
            page.wait_for_timeout(250)
            if forced:
                page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", forced)
            page.wait_for_function("() => document.readyState === 'complete'", timeout=60000)
            page.wait_for_timeout(1500)
            if not page.evaluate(STATE_JS, STATE_TOKEN).get("root"):
                raise RuntimeError("wrapper root not found")
            page.evaluate("() => window.__r19s.observe()")  # presence, placeholder, selection
            for i in range(min(page.evaluate("() => window.__r19s.targets()"), 150)):
                try:
                    page.hover(f'[data-r19-hover="{i}"]', timeout=2000)
                except Exception:  # covered or off-screen: that target is skipped, never faked
                    continue
                page.evaluate("() => window.__r19s.observe()")
            page.mouse.move(0, 0)
            page.evaluate("() => window.__r19s.blur()")
            for _ in range(80):
                page.keyboard.press("Tab")
                page.evaluate("() => window.__r19s.observe()")
            found = page.evaluate("() => window.__r19s.collect()")
        except Exception as exc:  # a failed walk must never read as clean
            census["walk_failed"].append(f"{name}: {exc}".splitlines()[0][:200])
            ctx.close()
            continue
        census["walks"].append(name)
        for ob in found:
            prev = census["state_obs"].get(ob["token"])
            if prev is None:
                census["state_obs"][ob["token"]] = {**ob, "page": page_path, "walk": f"{vname}/{tname}"}
            else:
                prev["count"] += ob["count"]
                prev["observed"] += [v for v in ob["observed"] if v not in prev["observed"]]
        ctx.close()


# The opened-surface half (section 8.4): text contrast with opacity composited, and every
# background class on the surface or its scrim, read where it paints.
# Section 8.4 (W0d-2, SPEC-W0d section 2): the ground under each text run, found by two resolvers. A, the
# pixel oracle, reads a screenshot taken with the text made transparent; B, the painter stack, walks
# elementsFromPoint down to the first opaque layer and names who paints. A decides; B names the painter.
RESOLVE_JS = r"""
(args) => {
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const parse = (c) => {
    if (!c || c === "none" || c === "transparent") return null;
    const am = c.match(/\/\s*([\d.]+)(%?)\s*\)$/);
    let a = am ? parseFloat(am[1]) / (am[2] ? 100 : 1) : 1, m, p;
    const opaque = c.replace(/\s*\/\s*[\d.]+%?\s*\)$/, ")");
    if ((m = opaque.match(/^rgba?\(([^)]+)\)$/))) {
      const q = m[1].split(/[\s,]+/).filter(Boolean).map(Number);
      p = q.slice(0, 3); if (q.length > 3) a = q[3];
    } else if ((m = opaque.match(/^color\(srgb ([^)]+)\)$/))) {
      p = m[1].split(/\s+/).filter(Boolean).slice(0, 3).map((x) => Number(x) * 255);
    } else {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = "#000"; ctx.fillStyle = opaque; ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      p = [d[0], d[1], d[2]];
    }
    return a === 0 ? null : { rgb: p.map((x) => Math.max(0, Math.min(255, x))), a };
  };
  const hex = (rgb) => "#" + rgb.map((x) => Math.round(x).toString(16).padStart(2, "0")).join("").toUpperCase();
  const over = (fg, bg, a) => fg.map((c, i) => c * a + bg[i] * (1 - a));
  const classes = (el) => (el.getAttribute("class") || "").split(/\s+/).filter(Boolean);
  const path = (el) => {
    const bits = [];
    for (let n = el; n && n.nodeType === 1 && bits.length < 4; n = n.parentElement)
      bits.unshift(n.tagName.toLowerCase() + classes(n).slice(0, 2).map((c) => "." + c).join(""));
    return bits.join(">");
  };
  const styles = new Map();
  const cs = (el, pseudo = "") => {
    let m = styles.get(el);
    if (!m) styles.set(el, (m = {}));
    return m[pseudo] || (m[pseudo] = getComputedStyle(el, pseudo || null));
  };
  const opacities = new Map();
  const opacity = (el) => {
    if (!el || el.nodeType !== 1) return 1;
    if (!opacities.has(el)) opacities.set(el, parseFloat(cs(el).opacity) * opacity(el.parentElement));
    return opacities.get(el);
  };
  // The layers one element paints at a point, top first: ::after, ::before, replaced content, its
  // background image, its background colour. Alpha is the layer's times every opacity above it. A pseudo-
  // element is a layer only when its box covers its host's, or the viewport's when it is fixed (90% each
  // way): B cannot see where a smaller one sits, and A will disagree if it is under the text. An image
  // whose alpha moves no channel by 6 (the page's 1.5% noise texture), or that blends into what lies
  // below it (the page's colour-dodge glow), is faint: it names no ground and only makes B approximate.
  const REPLACED = new Set(["IMG", "VIDEO", "CANVAS", "IFRAME", "OBJECT", "EMBED"]);
  const layers = new Map();
  const layersOf = (el) => {
    if (layers.has(el)) return layers.get(el);
    const out = [], s = cs(el), op = opacity(el);
    const approx = s.mixBlendMode !== "normal" || (s.backdropFilter || "none") !== "none" || s.filter !== "none";
    for (const pseudo of ["::after", "::before"]) {
      const p = cs(el, pseudo);
      if (!p.content || p.content === "none" || p.content === "normal") continue;
      const host = el.getBoundingClientRect();
      const [w, h] = p.position === "fixed" ? [innerWidth, innerHeight] : [host.width, host.height];
      if (!(parseFloat(p.width) >= w * 0.9 && parseFloat(p.height) >= h * 0.9)) continue;
      const blend = p.mixBlendMode !== "normal";
      const own = approx || blend || p.filter !== "none" || (p.backdropFilter || "none") !== "none";
      if (p.backgroundImage !== "none")
        out.push({ el, pseudo, kind: p.backgroundImage.includes("gradient") ? "gradient" : "image", a: op * parseFloat(p.opacity),
                   approx: own, blend });
      const c = parse(p.backgroundColor);
      if (c) out.push({ el, pseudo, kind: "color", rgb: c.rgb, a: c.a * op * parseFloat(p.opacity), approx: own });
    }
    if (REPLACED.has(el.tagName)) out.push({ el, kind: el.tagName.toLowerCase(), a: op, approx });
    else if (el instanceof SVGElement && el.tagName.toLowerCase() !== "svg" && (parse(s.fill) || parse(s.stroke)))
      out.push({ el, kind: "svg", a: op, approx });
    if (s.backgroundImage !== "none")
      out.push({ el, kind: s.backgroundImage.includes("gradient") ? "gradient" : "image", a: op, approx,
                 blend: s.mixBlendMode !== "normal" });
    const c = parse(s.backgroundColor);
    if (c) out.push({ el, kind: "color", rgb: c.rgb, a: c.a * op, approx });
    for (const l of out) if (l.kind !== "color" && (l.a * 255 < 6 || l.blend)) l.faint = true;
    layers.set(el, out);
    return out;
  };
  const position = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement)
      if (["fixed", "sticky"].includes(cs(n).position)) return true;
    return false;
  };
  // Resolver B at one point. An element above the run's own that paints is an occluder: the point is dropped.
  // So is a fixed or sticky element outside the roots that paints anything at all, a faint layer or a filter
  // included (a floating button's blurred glow): the run is then read again in the middle of the viewport.
  const overlay = (el) => position(el) && !roots.some((r) => r.contains(el)) && opacity(el) > 0
    && (layersOf(el).some((l) => l.a > 0) || cs(el).filter !== "none" || (cs(el).backdropFilter || "none") !== "none");
  const canvasRgb = () => {
    for (const el of [document.documentElement, document.body]) {
      const c = el && parse(cs(el).backgroundColor);
      if (c && c.a >= 0.999) return c.rgb;
    }
    return [255, 255, 255];
  };
  const pointB = (x, y, runEl) => {
    const st = document.elementsFromPoint(x, y);
    let i = -1;
    for (let a = runEl; a && i < 0; a = a.parentElement) i = st.indexOf(a);
    if (i < 0) return { missed: true };
    for (let k = 0; k < i; k++)
      if (!runEl.contains(st[k]) && (layersOf(st[k]).some((l) => !l.faint) || overlay(st[k])))
        return { occluded: path(st[k]), fixed: position(st[k]) };
    const ls = st.slice(i).flatMap(layersOf);
    let k = ls.findIndex((l) => l.kind === "color" && l.a >= 0.999);
    const base = k >= 0 ? ls[k].rgb : canvasRgb();
    if (k < 0) k = ls.length;
    const above = ls.slice(0, k);
    let acc = base;
    for (const l of above.slice().reverse()) if (l.kind === "color") acc = over(l.rgb, acc, l.a);
    // Over an image when the text sits on an image, gradient or replaced painter. An image seen only through
    // translucent colour makes B approximate: A's spread then says whether it shows.
    const top = ls.find((l) => !l.faint), direct = top && top.kind !== "color" ? top.kind : null;
    const seen = above.some((l) => l.kind !== "color");
    return { rgb: acc, image: direct, approx: above.some((l) => l.approx) || (k < ls.length && ls[k].approx) || (seen && !direct),
             painter: top ? path(top.el) + (top.pseudo || "") : "canvas", painterEl: top ? top.el : null };
  };
  // Copper is a ground only for its own action: the painter is or sits inside a, button or [role=button],
  // the run is inside that same action, and the painter's border box lies within the action's (+-1px).
  const actionOf = (painterEl, runEl) => {
    const a = painterEl && painterEl.closest("a,button,[role=button]");
    if (!a || !a.contains(runEl)) return "off";
    const p = painterEl.getBoundingClientRect(), q = a.getBoundingClientRect();
    return p.left >= q.left - 1 && p.top >= q.top - 1 && p.right <= q.right + 1 && p.bottom <= q.bottom + 1 ? "ok" : "box";
  };
  const wrapper = document.querySelector('[data-presentation="r19"]') || document.querySelector(".r19-direction-a")
    || [...document.querySelectorAll("[style]")].find((e) => /--font-montserrat/.test(e.getAttribute("style")))
    || (document.getElementById("kbli-explorer-jsonld") || {}).parentElement;
  const roots = (args.mode === "page" ? [wrapper].filter(Boolean)
    : [...new Set(args.selectors.flatMap((s) => [...document.querySelectorAll(s)]))])
    .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1; });
  const outside = roots.filter((r) => !(wrapper && wrapper.contains(r)) && !r.closest(".kbli-r19")).map(path);
  const vw = innerWidth, vh = innerHeight;
  // A scrim: no text, covering 95% of the viewport, behind a surface root, painting any colour.
  const scrims = args.mode !== "opened" ? [] : [...document.querySelectorAll("body *")].filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width >= vw * 0.95 && r.height >= vh * 0.95 && parse(cs(el).backgroundColor)
      && !roots.some((x) => el.contains(x) || x.contains(el)) && !el.textContent.trim();
  });
  const grounds = [];
  for (const el of [...scrims, ...roots.flatMap((r) => [r, ...r.querySelectorAll("*")])])
    for (const t of classes(el)) {
      if (!/^(bg|from|via|to)-/.test(t)) continue;
      const c = parse(cs(el).backgroundColor);
      grounds.push({ token: t, hex: c ? hex(c.rgb) : "transparent", a: c ? Math.round(c.a * 1000) / 1000 : 0,
                     image: cs(el).backgroundImage !== "none", scrim: scrims.includes(el) });
    }
  const scrimPaint = scrims.map((el) => { const c = parse(cs(el).backgroundColor);
    return { path: path(el), hex: hex(c.rgb), a: Math.round(c.a * opacity(el) * 1000) / 1000 }; });
  // The runs: every non-empty own text node of a visible element (opacity product >= 0.1), read before
  // the text is made transparent.
  const runs = [], seen = new Set();
  for (const root of roots) {
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let t = tw.nextNode(); t; t = tw.nextNode()) {
      const el = t.parentElement, text = t.textContent.trim();
      if (!text || !el || seen.has(t)) continue;
      seen.add(t);
      const s = cs(el), box = el.getBoundingClientRect();
      if (s.visibility === "hidden" || box.width <= 1 || box.height <= 1 || opacity(el) < 0.1) continue;
      const fg = parse(s.color);
      const clip = s.backgroundClip === "text" && !parse(s.webkitTextFillColor);
      if (!fg && !clip) continue;
      runs.push({ node: t, el, text: text.slice(0, 40), path: path(el), fg: fg ? hex(fg.rgb) : null,
                  fa: fg ? Math.round(fg.a * opacity(el) * 100) / 100 : 0, clip, state: "pending" });
    }
  }
  roots.forEach((r) => r.setAttribute("data-census-root", ""));
  const st = document.createElement("style");
  st.textContent = "nextjs-portal{display:none!important}"
    + "*{pointer-events:auto!important;scroll-behavior:auto!important}[data-census-root],[data-census-root] *,"
    + "[data-census-root] *::before,[data-census-root] *::after{color:transparent!important;"
    + "-webkit-text-fill-color:transparent!important;text-decoration-color:transparent!important;"
    + "caret-color:transparent!important;text-shadow:none!important}";
  document.head.appendChild(st);
  if (!args.focus && document.activeElement && document.activeElement.blur) document.activeElement.blur();
  const median = (xs) => { const s = xs.slice().sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
  const box = (rect, el) => {
    const e = el.getBoundingClientRect();
    const l = Math.max(rect.left, e.left), t = Math.max(rect.top, e.top), r = Math.min(rect.right, e.right),
          b = Math.min(rect.bottom, e.bottom);
    return r - l > 1 && b - t > 1 ? { l, t, r, b } : null;
  };
  const points = ({ l, t, r, b }) => {
    const dx = Math.min(2, (r - l) * 0.25), dy = Math.min(2, (b - t) * 0.25);
    return [[(l + r) / 2, (t + b) / 2], [l + dx, t + dy], [r - dx, t + dy], [l + dx, b - dy], [r - dx, b - dy]];
  };
  const inView = ([x, y]) => x >= 0 && y >= 0 && x < innerWidth && y < innerHeight;
  window.__census = {
    runs, pending: runs.map((_, i) => i), target: -1, current: [], root: args.mode === "shared" ? roots[0] : null,
    rootGround: null, rootPts: null,
    step() {
      this.current = [];
      for (const i of this.pending) {
        const r = runs[i];
        const g = document.createRange();
        g.selectNodeContents(r.node);
        const boxes = [...g.getClientRects()].map((q) => box(q, r.el)).filter(Boolean);
        const inside = boxes.length && boxes.every((q) => q.t >= 0 && q.l >= 0 && q.b <= innerHeight && q.r <= innerWidth);
        if (!inside && this.target !== i) continue;
        const pts = boxes.flatMap(points).filter(inView);
        if (!pts.length) continue;
        r.trial = { pts, bs: pts.map(([x, y]) => pointB(x, y, r.el)) };
        this.current.push(i);
      }
      this.rootPts = null;
      if (this.root && !this.rootGround) {
        const q = this.root.getBoundingClientRect();
        const v = box({ left: 0, top: 0, right: innerWidth, bottom: innerHeight }, this.root);
        if (v && q.width > 1) this.rootPts = points(v).filter(inView);
      }
      return { selected: this.current.length, root: !!(this.rootPts && this.rootPts.length) };
    },
    async decode(b64) {
      const bin = atob(b64), bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const bmp = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
      const cv = document.createElement("canvas");
      cv.width = bmp.width; cv.height = bmp.height;
      const g = cv.getContext("2d", { willReadFrequently: true });
      g.drawImage(bmp, 0, 0);
      const data = g.getImageData(0, 0, cv.width, cv.height).data;
      const px = ([x, y]) => { const o = (Math.floor(y) * cv.width + Math.floor(x)) * 4; return [data[o], data[o + 1], data[o + 2]]; };
      const sample = (pts) => {
        const rgb = pts.map(px), ch = [0, 1, 2].map((c) => rgb.map((p) => p[c]));
        return { rgb: ch.map(median), spread: Math.max(...ch.map((xs) => Math.max(...xs) - Math.min(...xs))) };
      };
      for (const i of this.current) {
        const r = runs[i], { pts, bs } = r.trial;
        const keep = pts.map((p, k) => [p, bs[k]]).filter(([, b]) => !b.occluded && !b.missed);
        const occ = bs.find((b) => b.occluded);
        // Under a fixed overlay, even at one point, the run waits to be read in the middle of the viewport:
        // a blur or a shadow reaches past the overlay's box onto the points that are left.
        if (occ && occ.fixed && this.target !== i) continue;
        if (!keep.length) {
          if (occ) { r.state = "occluded"; r.occludedBy = occ.occluded; }
          continue;
        }
        const A = sample(keep.map(([p]) => p)), B = keep.map(([, b]) => b);
        const ch = [0, 1, 2].map((c) => median(B.map((b) => b.rgb[c])));
        const lead = B[0];
        Object.assign(r, { state: "ok", a: hex(A.rgb), spread: A.spread, b: hex(ch), image: (B.find((b) => b.image) || {}).image || null,
                           approx: B.some((b) => b.approx), painter: lead.painter, action: actionOf(lead.painterEl, r.el) });
      }
      if (this.rootPts && this.rootPts.length) {
        const R = sample(this.rootPts);
        this.rootGround = R.spread > 6 ? "over-image" : hex(R.rgb);
      }
      this.pending = this.pending.filter((i) => runs[i].state === "pending");
    },
    // Brings the first pending run to the middle of the viewport. A run already brought once that is
    // still pending cannot be measured: it is occluded, or unreached (clipped out of view).
    bring() {
      while (this.pending.length) {
        const i = this.pending[0], r = runs[i];
        if (this.target === i) {
          r.state = r.trial && r.trial.bs.some((b) => b.occluded) ? "occluded" : "unreached";
          this.pending.shift();
          continue;
        }
        this.target = i;
        (r.el.nodeType === 1 ? r.el : r.node.parentElement).scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" });
        return true;
      }
      return false;
    },
    result() {
      return {
        runs: runs.map(({ text, path: p, fg, fa, clip, state: s, a, spread, b, image, approx, painter, action, occludedBy }) =>
          ({ text, path: p, fg, fa, clip, state: s === "pending" ? "unreached" : s, a: a || null, spread: spread ?? null,
             b: b || null, image: image || null, approx: !!approx, painter: painter || p, action: action || null,
             occludedBy: occludedBy || null })),
        rootGround: this.rootGround,
      };
    },
  };
  return { roots: roots.length, outside, scrims: scrims.length, grounds, scrimPaint, runs: runs.length };
}
"""
SETTLE = {"load": 250, "ready": 1500, "open": 2500, "scroll": 150}
# Scroll positions a walk may take before it is INCOMPLETE. The spec says 8; the sector drawer needs 77 on
# mobile (contract section 8.4, a declared deviation), so every walk gets room for the longest code page.
CAPS = {"opened": 250, "shared": 250, "page": 250}
# A position is read once two captures 100 ms apart are identical: a section a script reveals or animates
# in on scroll has finished. After 10 tries the last capture is read as it paints.
STILL = (100, 10)
IMAGES_JS = ("() => [...document.images].every((i) => { const r = i.getBoundingClientRect();"
             " return i.complete || r.bottom < 0 || r.top > innerHeight; })")


ROOTS_JS = """(sels) => [...new Set(sels.flatMap((s) => [...document.querySelectorAll(s)]))]
  .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1; }).length"""
THEME_JS = "() => document.documentElement.getAttribute('data-theme')"


def force_theme(page, forced: str | None) -> None:
    """A forced theme holds after hydration: a page that hydrated its own theme over it is forced again, and a
    page that keeps its own is never read under the wrong one."""
    if not forced or page.evaluate(THEME_JS) == forced:
        return
    page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", forced)
    page.wait_for_timeout(SETTLE["ready"])
    got = page.evaluate(THEME_JS)
    if got != forced:
        raise RuntimeError(f"theme: the page hydrated data-theme={got!r} over {forced!r}")


def open_page(page, url: str, forced: str | None, opener, selectors: list[str]) -> bool:
    """Loads the page under its theme and opens the surface; True when a root is there to read."""
    resp = page.goto(url, wait_until="load", timeout=180000)
    if resp is None or resp.status >= 400:
        raise RuntimeError(f"load: HTTP {resp.status if resp else 'none'}")
    page.wait_for_timeout(SETTLE["load"])
    if forced:
        page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", forced)
    page.wait_for_function("() => document.readyState === 'complete'", timeout=60000)
    quiet(page)
    page.wait_for_timeout(SETTLE["ready"])
    force_theme(page, forced)
    if opener:
        try:
            opener(page)
        except Exception as exc:  # the reason names the opener, never "never opened" bare
            raise RuntimeError(f"opener: {exc}".splitlines()[0][:160]) from exc
    page.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
    page.wait_for_timeout(SETTLE["open"])
    force_theme(page, forced)
    return bool(page.evaluate(ROOTS_JS, selectors))


def quiet(page) -> None:
    """No request for 500 ms after the load: a section a client fetch renders is in the page before it is read."""
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:  # a page that keeps polling is read as it stands
        pass


def still(page, cdp) -> str:
    """The viewport, captured until two captures in a row are the same (STILL)."""
    shot = cdp.send("Page.captureScreenshot", {"format": "png"})["data"]
    for _ in range(STILL[1]):
        page.wait_for_timeout(STILL[0])
        last, shot = shot, cdp.send("Page.captureScreenshot", {"format": "png"})["data"]
        if shot == last:
            break
    return shot


def resolve(page, mode: str, selectors: list[str] | None = None, focus: bool = False) -> dict:
    """Both resolvers over every text run of the surface roots (mode opened or shared) or of the wrapper
    (mode page), scrolling run by run: SPEC-W0d section 2."""
    page.evaluate("() => document.fonts.ready.then(() => true)")  # a late webfont moves every box
    meta = page.evaluate(RESOLVE_JS, {"mode": mode, "selectors": selectors or [], "focus": focus})
    cdp = page.context.new_cdp_session(page)
    positions, incomplete = 0, False
    try:
        while True:
            step = page.evaluate("() => window.__census.step()")
            if step["selected"] or step["root"]:
                if positions == CAPS[mode]:
                    incomplete = True
                    break
                positions += 1
                page.evaluate("b => window.__census.decode(b)", still(page, cdp))
            if not page.evaluate("() => window.__census.bring()"):
                break
            page.wait_for_timeout(SETTLE["scroll"])
            try:
                page.wait_for_function(IMAGES_JS, timeout=3000)
            except Exception:  # an image that never loads is read as it paints
                pass
    finally:
        cdp.detach()
    return {**meta, **page.evaluate("() => window.__census.result()"), "positions": positions,
            "incomplete": incomplete}


def near(a: str, b: str, tol: int = 2) -> bool:
    """Each 8-bit sRGB channel within tol (section 8.4, SPEC-W0d section 2.5)."""
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tol for i in (1, 3, 5))


def text_colour(r: dict) -> str:
    """The run's colour times its opacity, composited over A's ground."""
    if not r["fg"]:
        return r["a"]
    f, g = (tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in (r["fg"], r["a"]))
    return "#" + "".join(f"{round(x * r['fa'] + y * (1 - r['fa'])):02X}" for x, y in zip(f, g))


def over_image(r: dict) -> str | None:
    if r["clip"]:
        return "text clipped to a background"
    return r["image"] or ("non-uniform" if r["spread"] > 6 else None)


def run_verdict(r: dict, page_level: bool = False) -> str | None:
    """None when a measured run's ground is on contract, else why not (SPEC-W0d sections 2.5 and 2.6)."""
    if over_image(r):
        return "over-image"
    if any(near(r["a"], DIRECTION_A[x]) for x in ("paper", "elevated", "wash")):
        return None
    if near(r["a"], DIRECTION_A["copper"]):
        return {"ok": None, "box": "copper off an action (outside the action box)"}.get(r["action"],
                                                                                       "copper off an action")
    if page_level and near(r["a"], DIRECTION_A["ink"]) and any(near(text_colour(r), DIRECTION_A[x])
                                                             for x in ("elevated", "paper")):
        return None
    return "off"


def judge_runs(runs: list[dict], where: str, page_level: bool = False) -> tuple[dict, dict]:
    """The off-contract grounds and the resolver disagreements of measured runs, keyed by painter and hex."""
    off, disagree = {}, {}
    for r in runs:
        if r["state"] != "ok":
            continue
        why = run_verdict(r, page_level)
        if why:
            img = f" over-image ({over_image(r)})" if why == "over-image" else ""
            tail = f" ({why})" if why.startswith("copper") else ""
            off.setdefault(f"ground {r['a']} {r['painter']} {why}",
                           f"  ground {r['a']}{img} under {r['text']!r} at {r['painter']}{tail}, on {where}")
        if r["b"] and not r["approx"] and not r["image"] and not near(r["a"], r["b"]):
            disagree.setdefault(f"{r['a']} {r['b']} {r['painter']}",
                                f"  disagree {r['a']} (pixels) vs {r['b']} (DOM) under {r['text']!r} "
                                f"at {r['painter']}, on {where}")
    return off, disagree


def walk_state(row: dict) -> tuple[str, str]:
    """One verdict state per scenario-walk (SPEC-W0d section 2.7); the reason names which."""
    runs = row.get("runs", [])
    ok = [r for r in runs if r["state"] == "ok"]
    measured = [r for r in ok if not over_image(r)]
    occluded = sum(r["state"] == "occluded" for r in runs)
    if row.get("error"):
        return "failed:never-opened", row["error"]
    if not row.get("roots"):
        return "failed:never-opened", "0 roots"
    if not runs:
        return "failed:never-opened", "0 text runs"
    if measured:
        return "ok", ""
    if ok:
        return "failed:over-image-only", f"{len(ok)} runs"
    return "failed:never-opened", f"0 measurable, {occluded} occluded"


OPENED_FIXTURE = Path(__file__).resolve().parent / "tests/fixtures/r19_opened_surfaces.json"
EXPLORER_SURFACES = ["main", "main ~ aside", '[class*="h-[70vh]"]']


def _stub(ctx, fixture: dict, search_status: int = 200) -> None:
    """Search and inspect answer from the fixture: the walk never needs the backend."""
    def reply(route, body, status=200):
        origin = route.request.headers.get("origin", "*")
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body),
                      headers={"access-control-allow-origin": origin, "access-control-allow-credentials": "true"})
    ctx.route("**/api/v1/kbli-notebook/search**",
              lambda route: reply(route, fixture["search"]) if search_status == 200
              else reply(route, {"detail": f"HTTP {search_status}"}, search_status))
    ctx.route("**/api/v1/kbli-notebook/inspect/**",
              lambda route: reply(route, {**fixture["inspect"], "code": route.request.url.rstrip("/").split("/")[-1]}))


def _seed(ctx, fixture: dict) -> None:
    msgs = [{**m, "results": fixture["search"]} if m.get("results") == "search" else m for m in fixture["messages"]]
    ctx.add_init_script(f"sessionStorage.setItem('kbli-messages', {json.dumps(json.dumps(msgs))})")


def _type_query(page) -> None:
    box = page.locator('input[role="combobox"]').first
    box.click()
    box.fill("restaurant")
    page.wait_for_selector('[role="listbox"]', state="attached", timeout=15000)
    page.mouse.move(0, 0)


def _active_row(page) -> None:
    _type_query(page)
    page.locator('input[role="combobox"]').first.press("ArrowDown")


def _open_sector(page) -> None:
    page.locator('a[href^="/kbli/sectors/"]').first.click()
    page.wait_for_selector('[role="dialog"]', timeout=60000)


def _open_compare(page) -> None:
    page.locator('button[title="Compare codes"]').click()
    for code in ("56101", "55130"):
        page.locator("main button", has_text=code).first.click()
    page.locator("button", has_text="Compare 2 codes").click()
    page.wait_for_selector('[role="dialog"]', timeout=30000)


def _open_black_book(page) -> None:
    page.locator("button:visible", has_text="Ask about your codes").first.click()
    page.wait_for_selector('[aria-labelledby="kbli-transition-title"]', timeout=30000)


def _open_sidebar(page) -> None:
    page.locator("main button:has(svg.lucide-menu)").first.click()


def _open_mobile_nav(page) -> None:
    page.locator('button[aria-label="Open menu"]:visible').first.click()
    page.wait_for_selector('[role="dialog"]', timeout=30000)


# name, page, walks ("all" = the six states), stub (search status or None), seed, opener, surface selectors
SCENARIOS = [
    ("search-dropdown", "/kbli", "all", 200, False, _type_query, ['div:has(> [role="listbox"])']),
    ("search-active-row", "/kbli", "walk", 200, False, _active_row, ['div:has(> [role="listbox"])']),
    ("search-error", "/kbli", "walk", 503, False, _type_query, ['div:has(> [role="listbox"])']),
    ("sector-drawer", "/kbli", "walk", None, False, _open_sector, ['[role="dialog"]']),
    ("explorer-answer-inspector", "/kbli-explorer?inspect=56101", "walk", 200, True, None, EXPLORER_SURFACES),
    ("explorer-compare", "/kbli-explorer", "walk", 200, True, _open_compare, ['[role="dialog"]']),
    ("explorer-black-book", "/kbli-explorer", "walk", 200, False, _open_black_book,
     ['[aria-labelledby="kbli-transition-title"] > :last-child']),
    ("explorer-mobile-sidebar", "/kbli-explorer", "mobile", 200, True, _open_sidebar, ["aside:has(h3)"]),
    ("kbli-mobile-nav", "/kbli", "mobile-all", None, False, _open_mobile_nav, ['[role="dialog"]']),
    ("kbli-code-mobile-nav", "/kbli/55203", "mobile-all", None, False, _open_mobile_nav, ['[role="dialog"]']),
]
# Section 8.5: the shared components /kbli* mounts, keyed by file. Each (component, branch) pair names the
# routes outside /kbli* that pin it, fingerprinted on origin/main and never judged by the wrapper's rows. A
# file with no pair has no pin: an edit to it is unpinned by construction.
MOBILE_NAV = {"MobileNav non-R19": ("/v2", "/visa/second-home", "/v2/news"),
              "MobileNav R19": ("/tax-calendar", "/property/eligibility", "/news")}
NAV_SHELL = {"NavShell default": ("/v2",), "NavShell paper": ("/tax-calendar",)}
SHARED_MATRIX = {
    "apps/mouth/src/app/v2/_components/MobileNav.tsx": MOBILE_NAV,
    "packages/core/components/NavShell.tsx": NAV_SHELL,
    "packages/core/components/NavShell.module.css": NAV_SHELL,
    "apps/mouth/src/app/v2/_components/Footer.tsx": {"Footer editorial": ("/v2",), "Footer R19 blog": ("/news",)},
    "packages/core/components/BZLogo.tsx": {},
    "apps/mouth/src/components/lead/WhatsAppLeadButton.tsx": {},
    "packages/core/components/FunnelFrame.tsx": {},
    "apps/mouth/src/components/ui/button.tsx": {},
    "apps/mouth/src/components/ui/skeleton.tsx": {},
    "apps/mouth/src/components/providers/LazyToaster.tsx": {},
    # The R19 drawer's own styles also paint every other R19 surface, far beyond the drawer pins.
    "apps/mouth/src/components/r19/R19Presentation.module.css": {},
    "apps/mouth/src/components/r19/presentation.ts": {},
}
# The branch a pair claims, read at run time on the hydrated surface, never from the server HTML.
BRANCH_OF = {"MobileNav non-R19": "non-R19", "MobileNav R19": "R19", "NavShell default": "default",
             "NavShell paper": "paper"}
BRANCH_JS = """(component) => {
  if (component === "MobileNav") {
    const d = document.querySelector('[role="dialog"]');
    return d ? (d.getAttribute("data-presentation") === "r19-drawer" ? "R19" : "non-R19") : "closed";
  }
  if (component === "NavShell") {
    const n = document.querySelector("nav:has(> [data-nav-logo])");
    return n ? ([...n.classList].some((c) => /(^|_)paper(_|$)/.test(c)) ? "paper" : "default") : "absent";
  }
  return null;
}"""
# How each component is reached: opener, surface selectors, walks. NavShell is pinned on desktop, where its
# links show, and at 390px, where the bar holds no text of its own and the pin is its root ground alone.
SHARED_SURFACE = {"MobileNav": (_open_mobile_nav, ['[role="dialog"]'], "shared"),
                  "NavShell": (None, ["nav:has(> [data-nav-logo])"], "shared-nav"),
                  "Footer": (None, ["footer:has(.footer-grid)"], "shared")}
SHARED_WALKS = {"shared": [("mobile", "light"), ("mobile", "system-dark")],
                "shared-nav": [("desktop", "light"), ("desktop", "system-dark"), ("mobile", "light"),
                               ("mobile", "system-dark")]}
SHARED_PAIRS = {pair: routes for pairs in SHARED_MATRIX.values() for pair, routes in pairs.items()}
SHARED = [(f"{pair} {route}", route, SHARED_SURFACE[pair.split()[0]][2], None, False,
           *SHARED_SURFACE[pair.split()[0]][:2]) for pair, routes in SHARED_PAIRS.items() for route in routes]
SHARED_PIN = Path(__file__).resolve().parent / "tests/fixtures/r19_shared_component_pins.json"


def pin_keys(pair: str, route: str) -> list[str]:
    """The pin entries one (pair, route) needs: one per walk of its component."""
    which = SHARED_SURFACE[pair.split()[0]][2]
    return [f"{pair} {route} {v}/{t}" for v, t in SHARED_WALKS[which]]


# Section 9 (W0d-3a): the parts CI runs side by side. `rest` reads the pages at rest (captures and state walks),
# `kbli` and `explorer` open the surfaces of their pages, `shared` walks the shared components.
PARTS = ("rest", "kbli", "explorer", "shared")


def scenarios(viewports: dict, themes: dict) -> list[tuple[str, str, str, tuple]]:
    """The one list: every scenario of a full census as (part, kind, name, how), in the order a full run takes
    them. Each part runs its own scenarios and nothing else; the aggregate is checked against this list."""
    out = [("rest", "capture", f"{p} {v}/{t}", (p, v, t)) for p in PAGES for v in viewports for t in themes]
    out += [("rest", "walk", f"{p} {v}/{t}", (p, v, t)) for p in PAGES for v, t in WALK]
    walks = {"all": [(v, t) for v in viewports for t in themes], "walk": WALK,
             "mobile": [("mobile", "system-dark")], "mobile-all": [("mobile", t) for t in themes], **SHARED_WALKS}
    for sc in SCENARIOS + SHARED:
        name, path, which = sc[:3]
        part = "shared" if which in SHARED_WALKS else "explorer" if path.startswith("/kbli-explorer") else "kbli"
        out += [(part, "shared" if part == "shared" else "opened", f"{name} {v}/{t}", (sc, v, t))
                for v, t in walks[which]]
    return out


# The scenario each entry of a census reports, done or failed: "<kind> <name>" as scenarios() names it.
SCENARIO_OF = {"captures": lambda c: f"capture {c['page']} {c['state']}",
               "failed": lambda f: "capture " + f.split(": ", 1)[0],
               "walks": lambda w: f"walk {w}",
               "walk_failed": lambda f: "walk " + f.split(": ", 1)[0],
               "opened": lambda o: f"opened {o['name']} {o['walk']}",
               "shared": lambda s: f"shared {s['name']} {s['walk']}",
               "shared_failed": lambda f: "shared " + f.split(": ", 1)[0]}
NOT_RECEIVED = "not received from any part"


def against_scenarios(census: dict, units: list) -> list[str]:
    """`scenarios-off-manifest: S`: the scenarios the census received against the one list, and the lines naming
    each one missing, received twice or not on the list. A missing scenario is entered as failed, so every count
    it feeds reads INCOMPLETE and never 0; then every entry goes back to where a full run takes it. A dump from
    before the parts has no list to be checked against."""
    if "parts" not in census:
        return []
    want = {f"{kind} {name}": i for i, (_, kind, name, _) in enumerate(units)}
    got = collections.Counter(see(x) for k, see in SCENARIO_OF.items() for x in census.get(k, []))
    missing = [k for k in want if k not in got]
    for key in missing:
        kind, name = key.split(" ", 1)
        if kind == "opened":
            surface, walk = name.rsplit(" ", 1)
            row = {"name": surface, "walk": walk, "roots": 0, "runs": [], "error": NOT_RECEIVED}
            row["state"], row["reason"] = walk_state(row)
            census.setdefault("opened", []).append(row)
            continue
        if kind == "shared":
            census.setdefault("shared", [])
        where = {"capture": "failed", "walk": "walk_failed", "shared": "shared_failed"}[kind]
        census.setdefault(where, []).append(f"{name}: {NOT_RECEIVED}")
    for k, see in SCENARIO_OF.items():
        if k in census:
            census[k].sort(key=lambda x: want.get(see(x), len(want)))
    lines = ([f"  missing: {k}" for k in missing] + [f"  twice: {k}" for k, n in sorted(got.items()) if n > 1]
             + [f"  unexpected: {k}" for k in sorted(got) if k not in want])
    tail = f" (INCOMPLETE: {len(missing)} scenarios not received, not a verdict)" if missing else ""
    return [f"scenarios-off-manifest: {len(lines)}{tail}"] + lines
# Background utilities that paint no colour: never a ground of their own.
NON_COLOUR_BG = ("bg-gradient-", "bg-linear-", "bg-radial", "bg-conic", "bg-clip-", "bg-cover", "bg-contain",
                 "bg-center", "bg-no-repeat", "bg-fixed", "bg-none", "bg-repeat", "bg-blend-", "bg-origin-",
                 "bg-top", "bg-bottom", "bg-left", "bg-right", "bg-auto")
# A rotating placeholder or carousel holds its first state, so the count does not depend on when it is read.
FREEZE_JS = ("(() => { const si = window.setInterval;"
             " window.setInterval = (fn, ms, ...a) => (Number(ms) >= 2000 ? 0 : si(fn, ms, ...a)); })()")


def walk_opened(browser, m, base: str, census: dict, units: list | None = None) -> None:
    """Opens each surface a click or a query reveals and resolves the ground of every text run on it:
    section 8.4. A shared component outside /kbli* is fingerprinted instead (section 8.5)."""
    fixture = json.loads(OPENED_FIXTURE.read_text())
    census.setdefault("opened", [])
    census.setdefault("shared", [])
    census.setdefault("shared_failed", [])
    for _, kind, _, (sc, vname, tname) in scenarios(m.VIEWPORTS, m.THEMES) if units is None else units:
        if kind not in ("opened", "shared"):
            continue
        name, path, which, status, seed, opener, selectors = sc
        shared = which in SHARED_WALKS
        w, h = m.VIEWPORTS[vname]
        scheme, forced = m.THEMES[tname]
        ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
        ctx.add_init_script(FREEZE_JS)
        if status is not None:
            _stub(ctx, fixture, status)
        if seed:
            _seed(ctx, fixture)
        page = ctx.new_page()
        row: dict = {"name": name, "walk": f"{vname}/{tname}", "roots": 0, "runs": []}
        branch = None
        try:
            # Under load a click can land before hydration: the surface never opens, closes again, or a link
            # navigates away. The page is loaded and opened once more before the walk fails.
            try:
                opened = open_page(page, base + path, forced, opener, selectors)
            except Exception:
                if not opener:
                    raise
                opened = False
            if opener and not opened:
                open_page(page, base + path, forced, opener, selectors)
            branch = page.evaluate(BRANCH_JS, name.split()[0]) if shared else None
            row.update(resolve(page, "shared" if shared else "opened", selectors))
        except Exception as exc:  # a surface that did not open must never read as clean
            row["error"] = str(exc).splitlines()[0][:200]
        ctx.close()
        row["state"], row["reason"] = walk_state(row)
        if shared:
            if row["state"] != "ok" and not row.get("rootGround"):
                census["shared_failed"].append(f"{name} {row['walk']}: {row['state']} ({row['reason']})")
                continue
            census["shared"].append({"name": name, "walk": row["walk"], "fingerprint": fingerprint(row, branch)})
            continue
        census["opened"].append(row)


def fingerprint(row: dict, branch: str | None) -> list[str]:
    """What a shared pin holds: each measured run as its colour on A's ground (or its own colour over an
    image), the ground of the surface root itself, and the branch."""
    prints = set()
    for r in row.get("runs", []):
        if r["state"] != "ok":
            continue
        if over_image(r):
            prints.add(f"{r['fg']} at alpha {r['fa']} over an image {r['text']!r}")
        else:
            prints.add(f"{text_colour(r)} on {r['a']} {r['text']!r}")
    if row.get("rootGround"):
        prints.add(f"root {row['rootGround']}")
    if branch:
        prints.add(f"branch {branch}")
    return sorted(prints)


def judge_grounds(census: dict, surfaces: dict, contract: dict) -> list[str]:
    """Every run's ground by its pixels, every scrim by its hue, then each background class by its row
    (section 8.4)."""
    off: dict[str, str] = {}
    for o in census.get("opened", []):
        on = f"{o['name']} {o['walk']}"
        off.update({k: v for k, v in judge_runs(o.get("runs", []), on)[0].items() if k not in off})
        for c in o.get("scrimPaint", []):
            key = f"scrim {c['hex']} {c['path']}"
            if (not near(c["hex"], DIRECTION_A["ink"]) or c["a"] >= 1) and key not in off:
                off[key] = f"  scrim {c['hex']} alpha {c['a']} at {c['path']} (a scrim is ink, translucent), on {on}"
        for g in o.get("grounds", []):
            t = g["token"]
            if t.startswith(NON_COLOUR_BG) or t in off:
                continue
            row = surfaces.get(t)
            if row is None:
                if ("class", t) not in contract:
                    off[t] = f"  {t}  has no section 5 or 8.1 row, painted {g['hex']} alpha {g['a']}, on {on}"
                continue
            if row["hex"] is None:
                bad = g["image"] if t.startswith(("from-", "via-", "to-")) else g["a"] > 0 or g["image"]
            else:
                bad = g["hex"] != row["hex"] or (row["ground"] != "scrim" and g["a"] < 1) or g["image"]
            if bad:
                off[t] = (f"  {t}  expected {row['value']} ({row['ground']}), painted {g['hex']} alpha {g['a']}"
                          f"{' over an image' if g['image'] else ''}, on {on}")
    return [off[k] for k in sorted(off)]


def disagreements(census: dict) -> list[str]:
    """Runs whose pixel ground and DOM ground differ by more than the tolerance: the instrument's self-check."""
    out: dict[str, str] = {}
    for o in census.get("opened", []):
        for k, v in judge_runs(o.get("runs", []), f"{o['name']} {o['walk']}")[1].items():
            out.setdefault(k, v)
    for c in census.get("captures", []):
        for k, v in c.get("page_disagree", {}).items():
            out.setdefault(k, v)
    return [out[k] for k in sorted(out)]


def page_grounds(page, where: str) -> dict:
    """The resolvers on every text run of the wrapper at rest (SPEC-W0d section 2.6)."""
    page.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
    page.wait_for_timeout(SETTLE["scroll"])
    res = resolve(page, "page")
    off, disagree = judge_runs(res["runs"], where, page_level=True)
    return {"page_off": off, "page_disagree": disagree, "page_runs": len(res["runs"]),
            "page_positions": res["positions"],
            "page_incomplete": res["incomplete"] or not res["roots"],
            "page_unreached": sum(r["state"] == "unreached" for r in res["runs"])}


def page_verdict(census: dict) -> list[str]:
    """`page-grounds-off-contract: G`: each distinct painter and hex, or over-image, under wrapper text at rest."""
    caps, failed = census.get("captures", []), census.get("failed", [])
    off: dict[str, str] = {}
    for c in caps:
        for k, v in c.get("page_off", {}).items():
            off.setdefault(k, v)
    short = [c for c in caps if "page_off" not in c or c.get("page_incomplete")]
    tail = (f" (INCOMPLETE: {len(failed)} captures failed, {len(short)} not read through, not a verdict)"
            if failed or short or not caps else "")
    lines = [off[k] for k in sorted(off)]
    return lines[:80] + ([f"  ... and {len(lines) - 80} more"] if len(lines) > 80 else []) + [
        f"page-grounds-off-contract: {len(off)}{tail}"]


PRINT = re.compile(r"^(#[0-9A-F]{6}) on (#[0-9A-F]{6}) (.*)$|^root (#[0-9A-F]{6})$")


def same_print(a: str, b: str) -> bool:
    """Two fingerprint entries are one within section 8.4's tolerance, 2 per channel: a ground the pixels read
    moves a level when the page behind a translucent surface, or the page texture over it, shifts."""
    ma, mb = PRINT.match(a), PRINT.match(b)
    if a == b or not (ma and mb):
        return a == b
    if ma.group(4) or mb.group(4):
        return bool(ma.group(4) and mb.group(4)) and near(ma.group(4), mb.group(4))
    return ma.group(3) == mb.group(3) and near(ma.group(1), mb.group(1)) and near(ma.group(2), mb.group(2))


def shared_drift(census: dict, pin: dict | None) -> tuple[list[str], str]:
    """Every shared component outside /kbli* against its origin/main pin: lines, and the count or why there
    is none. A text pair (foreground on the ground the pixels read, label), a text over an image (its own
    colour and alpha, label), the root's ground or a branch that appeared or vanished is one line; an entry
    whose colours moved by 2 or less per channel is the same entry."""
    shared, failed = census.get("shared"), census.get("shared_failed", [])
    if shared is None or pin is None:
        return [], "INCOMPLETE (no shared walk in this census)" if shared is None else "UNPINNED"
    lines = [f"  shared-failed: {f}" for f in failed]
    if failed:
        return lines, f"INCOMPLETE ({len(failed)} shared walks failed, not a verdict)"
    walked = {f"{s['name']} {s['walk']}": s["fingerprint"] for s in shared}
    for where, want in sorted(pin.items()):
        got = walked.get(where)
        if got is None:
            return [], f"INCOMPLETE ({where} not walked)"
        gone, left = sorted(set(want) - set(got)), sorted(set(got) - set(want))
        for x in list(gone):
            hit = next((y for y in left if same_print(x, y)), None)
            if hit is not None:
                gone.remove(x)
                left.remove(hit)
        lines += [f"  - {x}  ({where})" for x in gone]
        lines += [f"  + {x}  ({where})" for x in left]
    lines += [f"  ? {where}  walked, not in the pin" for where in sorted(set(walked) - set(pin))]
    return lines, str(len(lines))


def touched_files(base: str = "origin/main", root: Path = ROOT) -> list[str] | str:
    """The files this tree changed since its merge base with `base`, committed or not; a reason if git cannot say."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout
    try:
        merge_base = git("merge-base", base, "HEAD").strip()
        names = git("diff", "--name-only", f"{merge_base}...HEAD") + git("diff", "--name-only", "HEAD")
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"cannot diff against {base}: {str(getattr(exc, 'stderr', '') or exc).strip()[:120]}"
    return sorted({n for n in names.splitlines() if n})


def shared_unpinned(touched: list[str] | str | None, pin: dict | None) -> tuple[list[str], str]:
    """Each touched shared file must have a pin for every (component, branch) pair it serves, taken on the
    branch the pair claims (section 8.5): one line per file and pair that lacks one."""
    if touched is None or isinstance(touched, str):
        return [], f"INCOMPLETE ({touched or 'no diff against the base'}, not a verdict)"
    pin, lines = pin or {}, []
    for f in sorted(set(touched) & set(SHARED_MATRIX)):
        if not SHARED_MATRIX[f]:
            lines.append(f"  {f}  has no pinned pair: an edit to it is unpinned by construction")
        for pair, routes in SHARED_MATRIX[f].items():
            want = BRANCH_OF.get(pair)
            missing = [k for r in routes for k in pin_keys(pair, r)
                       if k not in pin or (want and f"branch {want}" not in pin[k])]
            if missing:
                lines.append(f"  {f}  {pair}: no pin for {', '.join(missing)}")
    return lines, str(len(lines))


def opened_verdict(census: dict, surfaces: dict, contract: dict, pin: dict | None = None,
                   touched: list[str] | str | None = None) -> list[str]:
    opened = census.get("opened")
    unpinned, unpinned_count = shared_unpinned(touched, pin)
    if opened is None:
        return ["opened-surfaces: 0 ok, 0 failed (no opened walk in this census)",
                "opened-outside-wrapper: INCOMPLETE (no opened walk)",
                "opened-grounds-off-contract: INCOMPLETE (no opened walk)",
                "ground-resolver-disagree: INCOMPLETE (no opened walk)",
                *unpinned, f"shared-touched-unpinned: {unpinned_count}",
                "shared-component-drift: INCOMPLETE (no shared walk in this census)",
                "opened-text-below-4.5: INCOMPLETE (no opened walk, not a verdict)"]
    ok = [o for o in opened if o["state"] == "ok"]
    failed = [o for o in opened if o["state"] != "ok"]
    short = [o for o in opened if o.get("incomplete")]
    out = [f"opened-surfaces: {len(ok)} ok, {len(failed)} failed"]
    below = []
    for o in opened:
        runs = o.get("runs", [])
        measured = [r for r in runs if r["state"] == "ok"]
        pairs = [(contrast(text_colour(r), r["a"]), r) for r in measured if r["fg"]]
        below += [(ratio, r, o) for ratio, r in pairs if ratio < 4.5]
        out.append(f"  {o['name']} {o['walk']}: {o['state']}" + (f" ({o['reason']})" if o["reason"] else "")
                   + f", {o['roots']} root(s), {o.get('scrims', 0)} scrim(s), {len(measured)} runs"
                   + (f", min {min(p for p, _ in pairs):.2f}" if pairs else "")
                   + "".join(f", {n} {what}" for n, what in (
                       (sum(bool(over_image(r)) for r in measured), "over an image"),
                       (sum(r["state"] == "occluded" for r in runs), "occluded"),
                       (sum(r["state"] == "unreached" for r in runs), "unreached")) if n)
                   + f", {o.get('positions', 0)} position(s)" + (", INCOMPLETE" if o.get("incomplete") else ""))
    tail = (f" (INCOMPLETE: {len(failed)} walks failed, {len(short)} over the scroll cap, not a verdict)"
            if failed or short or not opened else "")
    outside = [(o, r) for o in opened for r in o.get("outside", [])]
    out += [f"  {r}  renders outside the wrapper ({o['name']} {o['walk']})" for o, r in outside]
    out.append(f"opened-outside-wrapper: {len(outside)}{tail}")
    off = judge_grounds(census, surfaces, contract)
    out += off[:80] + ([f"  ... and {len(off) - 80} more"] if len(off) > 80 else [])
    out.append(f"opened-grounds-off-contract: {len(off)}{tail}")
    disagree = disagreements(census)
    out += disagree[:40] + ([f"  ... and {len(disagree) - 40} more"] if len(disagree) > 40 else [])
    out.append(f"ground-resolver-disagree: {len(disagree)}{tail}")
    out += unpinned
    out.append(f"shared-touched-unpinned: {unpinned_count}")
    drift, count = shared_drift(census, pin)
    out += drift
    out.append(f"shared-component-drift: {count}")
    out += [f"  {ratio:.2f}  {text_colour(r)} on {r['a']}  {r['text']!r}  {r['path']}  ({o['name']} {o['walk']})"
            for ratio, r, o in below[:60]]
    if len(below) > 60:
        out.append(f"  ... and {len(below) - 60} more")
    out.append(f"opened-text-below-4.5: {len(below)}{tail}")
    return out


def start_server(port: int) -> subprocess.Popen:
    with socket.socket() as probe:  # never census some other checkout's server
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"port {port} already serves: pass --base-url to reuse it or --port")
    log = open(os.environ.get("CENSUS_DEV_LOG", os.devnull), "w")
    return subprocess.Popen([str(ROOT / "node_modules/.bin/next"), "dev", "--webpack", "-p", str(port)],
                            cwd=ROOT / "apps/mouth", stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True, env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"})


def stop_server(proc: subprocess.Popen) -> None:
    for sig, wait in ((signal.SIGTERM, 15), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
            proc.wait(timeout=wait)
            return
        except (ProcessLookupError, subprocess.TimeoutExpired):
            continue


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", help="reuse a running dev server (default: start one)")
    ap.add_argument("--port", type=int, default=3419)
    ap.add_argument("--json", type=Path, help="dump the census (JSON Lines) for offline replay")
    ap.add_argument("--replay", type=Path, help="judge a dumped census, or the parts' dumps concatenated, no browser")
    ap.add_argument("--part", choices=PARTS, help="run the scenarios of one part only (section 9); default: all")
    ap.add_argument("--export", action="store_true",
                    help="print the probe, pages, six states and palette as JSON for the armed apps/mouth test")
    ap.add_argument("--contract", type=Path, default=CONTRACT)
    ap.add_argument("--diff-base", default="origin/main",
                    help="the ref whose merge base with HEAD shared-touched-unpinned diffs against")
    a = ap.parse_args(argv)
    if a.part and a.replay:
        ap.error("--part runs a live part; --replay judges what the parts dumped")
    if a.export:
        print(json.dumps(export()))
        return 0
    try:
        contract = load_contract(a.contract.read_text())
    except ContractError as exc:
        print(f"contract: REFUSED — {exc}")
        print("read-but-undefined: REFUSED (contract unreadable)")
        return 2
    try:
        states = parse_states(a.contract.read_text(), contract)
    except ContractError as exc:
        print(f"states: REFUSED — {exc}")
        print("state-colors-off-contract: REFUSED (state table unreadable)")
        return 2
    try:
        surfaces = parse_surfaces(a.contract.read_text(), contract, states)
    except ContractError as exc:
        print(f"surfaces: REFUSED — {exc}")
        print("opened-text-below-4.5: REFUSED (surfaces table unreadable)")
        return 2
    if a.replay:
        census = load(a.replay)
    else:
        proc = None if a.base_url else start_server(a.port)
        try:
            census = live((a.base_url or f"http://localhost:{a.port}").rstrip("/"), a.part)
        finally:
            if proc:
                stop_server(proc)
    if a.json:
        dump(census, a.json)
    # The CI budget: how long each part took, on stderr, never in the verdict text.
    for part, seconds in census.get("seconds", {}).items():
        print(f"phase-seconds: {part} " + ", ".join(f"{k} {v}" for k, v in seconds.items()), file=sys.stderr)
    # A live part answers for its own scenarios; a replay, whatever it holds, for the whole list.
    received = against_scenarios(census, [u for u in scenarios(*measure_literals()) if a.part in (None, u[0])])
    pin = json.loads(SHARED_PIN.read_text()) if SHARED_PIN.exists() else None
    touched = touched_files(a.diff_base)
    print("\n".join(received + verdict(census, contract, states) + page_verdict(census)
                    + opened_verdict(census, surfaces, contract, pin, touched)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
