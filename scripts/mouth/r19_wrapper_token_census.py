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
state contract (section 7), `state-rows-unseen: U` then `state-colors-off-contract: K`. The verdict is the
printed line, never the exit code.

  python3 scripts/mouth/r19_wrapper_token_census.py [--base-url URL] [--json OUT]
  python3 scripts/mouth/r19_wrapper_token_census.py --replay CENSUS.jsonl
  python3 scripts/mouth/r19_wrapper_token_census.py --export
"""
from __future__ import annotations

import argparse
import ast
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
RANK = {None: -1, "wrapper": 0, "above": 1, "nowhere": 2}  # where a var resolves, worst wins


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


def parse_contract(text: str) -> dict[tuple[str, str], dict]:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ContractError("expected exactly one contract:begin/end block")
    lines = [ln.strip() for ln in text.split(BEGIN)[1].split(END)[0].splitlines()]
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
    head = {k: census[k] for k in ("schema", "pages", "states", "captures", "failed", "walks", "walk_failed")}
    lines = [json.dumps(head, sort_keys=True)]
    lines += [json.dumps({"read": k, **census["reads"][k]}, sort_keys=True) for k in sorted(census["reads"])]
    lines += [json.dumps({"color": k, **census["colors"][k]}, sort_keys=True) for k in sorted(census["colors"])]
    lines += [json.dumps({"state_ob": k, **census["state_obs"][k]}, sort_keys=True) for k in sorted(census["state_obs"])]
    path.write_text("\n".join(lines) + "\n")


def load(path: Path) -> dict:
    head, *rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    census = {**head, "reads": {}, "colors": {}, "state_obs": {}}
    for row in rows:
        key = next(k for k in ("read", "color", "state_ob") if k in row)
        census[key + "s"][row.pop(key)] = row
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
  // The rgb channels of the computed colour, unblended and unrounded of alpha: copper at 30% reads
  // #A44B36 exactly as W1's slice(0,7) does. A canvas round-trip un-premultiplies and drifts.
  const hex = (c) => {
    let p, m;
    if ((m = c.match(/^rgba?\(([^)]+)\)$/))) p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    else if ((m = c.match(/^color\(srgb ([^)]+)\)$/))) { p = m[1].split(/[\s/]+/).filter(Boolean).map(Number); p = [p[0] * 255, p[1] * 255, p[2] * 255, p[3]]; }
    else {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = "#000"; ctx.fillStyle = c; ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      p = [d[0], d[1], d[2], d[3] / 255];
    }
    return p.length > 3 && p[3] === 0 ? "transparent"
      : "#" + p.slice(0, 3).map((x) => Math.round(x).toString(16).padStart(2, "0")).join("").toUpperCase();
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
  window.__r19s = { observe, targets, collect: () => [...obs.values()], blur: () => { document.activeElement && document.activeElement.blur(); getSelection().removeAllRanges(); } };
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


def export() -> dict:
    """The probe, pages, six states and palette, for the armed apps/mouth test."""
    found = {}
    for node in ast.parse(MEASURE.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("VIEWPORTS", "THEMES"):
                    found[target.id] = ast.literal_eval(node.value)
    for name in ("VIEWPORTS", "THEMES"):
        if name not in found:
            raise SystemExit(f"{MEASURE}: top-level {name} literal not found")
    states = [{"name": f"{v}/{t}", "width": w, "height": h, "scheme": scheme, "forced": forced}
              for v, (w, h) in found["VIEWPORTS"].items()
              for t, (scheme, forced) in found["THEMES"].items()]
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


def live(base: str) -> dict:
    from playwright.sync_api import sync_playwright
    m = _load_measure()
    census: dict = {"schema": 1, "pages": PAGES, "captures": [], "failed": [], "reads": {}, "colors": {},
                    "state_obs": {}, "walks": [], "walk_failed": [],
                    "states": [f"{v}/{t}" for v in m.VIEWPORTS for t in m.THEMES]}
    core = core_components()
    for p in PAGES:
        _wait(base + p, 300)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        for page_path in PAGES:
            for vname, (w, h) in m.VIEWPORTS.items():
                for tname, (scheme, forced) in m.THEMES.items():
                    state = f"{vname}/{tname}"
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
        walk_states(browser, m, base, census)
        browser.close()
    return census


def walk_states(browser, m, base: str, census: dict) -> None:
    """Hover through page.hover, focus through Tab, selection through a range: section 7.5."""
    for page_path in PAGES:
        for vname, tname in WALK:
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
    ap.add_argument("--replay", type=Path, help="judge a dumped census, no browser")
    ap.add_argument("--export", action="store_true",
                    help="print the probe, pages, six states and palette as JSON for the armed apps/mouth test")
    ap.add_argument("--contract", type=Path, default=CONTRACT)
    a = ap.parse_args(argv)
    if a.export:
        print(json.dumps(export()))
        return 0
    try:
        contract = parse_contract(a.contract.read_text())
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
    if a.replay:
        census = load(a.replay)
    else:
        proc = None if a.base_url else start_server(a.port)
        try:
            census = live((a.base_url or f"http://localhost:{a.port}").rstrip("/"))
        finally:
            if proc:
                stop_server(proc)
    if a.json:
        dump(census, a.json)
    print("\n".join(verdict(census, contract, states)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
