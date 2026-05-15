#!/usr/bin/env python3
"""WR2 Canva PDF renderer — production multi-page.

Architecture:
  slides.json  →  ReportLab PDF (text-layered, editable in Canva)  →  Tigris S3
  upload  →  Canva import-design-from-url (MCP)  →  layer-editable design.

Slide types supported (auto-routed via `slide.layout_family`):
  - cover-photo                  → cover with hero + yellow subhead + heading
                                   + regulation badge (Article 14.4, yellow AAA)
  - photo-headline-yellow-sub    → inner hero + body
  - dark-status-list             → 3-6 status items neutral/critical/positive
  - evidence-carved              → "Hammurabi" code+evidence+ledger structure
  - qa-dialogue                  → 2-3 voice exchanges
  - timeline-pinboard            → date+event list
  - three-verdicts               → decision-tree three columns
  - statement-bomb               → closing single-statement
  - elegant-close                → soft CTA (email + WA + IF/WHEN)
  - stat-card-hero               → big number center (ADOPT pattern 1)
  - thin-red-rule-divider        → red rule + body + mono footer (ADOPT 2)
  - swiss-grid-asymmetry         → numerals + steps (ADOPT 3)
  - monospace-evidence-block     → system output as evidence (ADOPT 4)

Inputs:
  Either:
    --slides-json /path/to/slides.json   (file mode, smoke tests)
  Or:
    --draft-id <uuid>                    (PG mode, production cron)

Outputs (when --apply set):
  - PDF at /tmp/wr2_<draft_id>.pdf
  - Tigris upload to s3://nuzantara-warroom-images/wr2-pdf/<draft_id>.pdf
  - Canva design created via MCP import-design-from-url
  - PG update: war_room_drafts.canva_design_id, .status='rendered'

Without --apply: only writes PDF to /tmp for visual review.

Design tokens — SOURCE OF TRUTH: ~/.claude/skills/bali-zero-brand/tokens.json
This renderer mirrors those values for offline use; if tokens.json changes,
update RGB constants below. Yellow badge migration applied 2026-05-13
(commit 940fc77 in ~/.claude).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from reportlab.lib.colors import Color, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ---------- Constants (mirror of tokens.json) ----------
W, H = 1080, 1350

COLOR_BG_ANTRACITE = "#2C2F38"
COLOR_BG_BLACK = "#000000"
COLOR_TEXT_WHITE = "#FFFFFF"
COLOR_TEXT_MUTED = "#9CA3AF"
COLOR_ACCENT_YELLOW = "#F4C430"
COLOR_STATUS_RED = "#C8102E"

LOGO_PATH = Path.home() / ".claude/skills/bali-zero-brand/assets/logo.png"

# ---------- Yellow highlight regex (Article 6.9 anchor family) ----------
# These patterns identify "verifiable facts" tokens that get yellow color
# in body text (numbers, regulations, verdicts). Mirrors split_for_yellow().
YELLOW_TOKEN_PATTERNS = [
    # Numbers + currency + percentages + units
    r"\b\d+([,.\d]+)*[KMB]?(?:\s+(?:DAYS|YEARS|MONTHS|HECTARES|VILLAS|"
    r"BILLION|MILLION|RIBU|JUTA|MILIAR|TRILYUN))?\b",
    r"\b(?:RP|IDR|USD|EUR|\$)\s?\d+([,.\d]+)*[KMB]?\b",
    r"\b\d+%\b",
    # Indonesian regulations (verbatim — Article 6.4)
    r"\b(?:PP|PERMENKUMHAM|PERMEN\w+|UU|KEP-\d+|PERPRES|PERMENDAGRI|"
    r"PERMENKES|PMK|PER-?BKPM|PERDA)[\s-]?\d+/\d{4}\b",
    # Verdict / state-change verbs (Article 6.9 anchor 4)
    r"\b(?:WON|LOST|BANS|BANNED|RESCINDED|WAIVED|"
    r"SHUTS\s+DOWN|BLOCKED|RESTORED|EXPIRES|KILLED|"
    r"MUST|CANNOT|FORBIDDEN|ABOLISHED|SUSPENDED|REVOKED|"
    r"REJECTED|APPROVED|EXTENDED|DEFERRED|"
    r"SIGNAL|WIN|LOSS|END|START|STOP|CHANGE|RESET|"
    r"RECRUITING|COMPETING|FILTERING|"
    r"NAMED|APPOINTED|PROMOTED|DEMOTED|REPLACED|"
    r"DROPPED|RAISED|CUT)\b",
]
YELLOW_COMPILED = [re.compile(p, re.IGNORECASE) for p in YELLOW_TOKEN_PATTERNS]


# ---------- Font registry ----------

def register_fonts() -> None:
    """Register Montserrat/Arial/Menlo into ReportLab. Idempotent."""
    candidates = [
        ("/Users/nuzantara/Library/Fonts/Montserrat-ExtraBold.ttf",
         "Montserrat-ExtraBold"),
        ("/Users/nuzantara/Library/Fonts/Montserrat-Bold.ttf",
         "Montserrat-Bold"),
        ("/Users/nuzantara/Library/Fonts/Montserrat-Regular.ttf",
         "Montserrat-Regular"),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "ArialBold"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "Arial"),
        ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
         "CourierNewBold"),
        ("/System/Library/Fonts/Supplemental/Courier New.ttf", "CourierNew"),
        ("/System/Library/Fonts/Menlo.ttc", "Menlo"),
    ]
    for path, name in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass


def pick_font(prefer: list[str]) -> str:
    for f in prefer:
        try:
            pdfmetrics.getFont(f)
            return f
        except Exception:
            continue
    return "Helvetica"


# ---------- Text utilities ----------

# Fix 2026-05-15: previously every number/regulation/verb was highlighted →
# slides like "165 DEPORTED 1 JAN– 12 APR. 62 DETAINED. 210 ARRESTED…" had
# 10+ yellow tokens, destroying visual hierarchy. Cap is enforced inside
# split_for_yellow: keep only the FIRST N highlights, rest revert to white.
MAX_HIGHLIGHTS_PER_TEXT = 3


def split_for_yellow(text: str,
                     max_highlights: int = MAX_HIGHLIGHTS_PER_TEXT) -> list[tuple[str, bool]]:
    """Return [(segment, is_yellow), ...] covering the input text.

    The first ``max_highlights`` regex matches keep is_yellow=True; subsequent
    matches are collapsed to is_yellow=False. This enforces editorial discipline:
    typography hierarchy is destroyed when every fact is highlighted.
    """
    matches: list[tuple[int, int]] = []
    for pat in YELLOW_COMPILED:
        for m in pat.finditer(text):
            matches.append((m.start(), m.end()))
    matches.sort()
    merged: list[tuple[int, int]] = []
    for s, e in matches:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    # Enforce cap: only the first N merged ranges remain "yellow".
    capped = merged[:max_highlights]
    segments: list[tuple[str, bool]] = []
    last = 0
    for s, e in capped:
        if s > last:
            segments.append((text[last:s], False))
        segments.append((text[s:e], True))
        last = e
    if last < len(text):
        segments.append((text[last:], False))
    return segments if segments else [(text, False)]


_TRAILING_PUNCT = ".,;:!?)»\"'"
_LEADING_PUNCT = ".,;:!?)»\"'"


def wrap_segments(text: str, font: str, size: int,
                  max_w: int) -> list[list[tuple[str, bool]]]:
    """Wrap text into lines, preserving (segment, is_yellow) tuples.

    Fix 2 (2026-05-13): punctuation glue. Previously every token was emitted
    with a trailing space, so "DAYS" + "." became "DAYS ." (orphan punctuation
    after a yellow-highlight token). Now: if a word begins with punctuation
    AND the previous emitted token in the same line ends with a trailing space,
    strip that trailing space before appending the punctuation. This collapses
    "31 DAYS ." → "31 DAYS." while preserving normal word spacing.
    """
    full_segs = split_for_yellow(text)
    lines: list[list[tuple[str, bool]]] = []
    cur_line: list[tuple[str, bool]] = []
    cur_width = 0.0
    for seg_text, is_y in full_segs:
        for word in seg_text.split(" "):
            if not word:
                continue
            # If word starts with punctuation AND previous token in this line
            # ended with space, strip that space.
            if cur_line and word[0] in _LEADING_PUNCT:
                prev_word, prev_y = cur_line[-1]
                if prev_word.endswith(" "):
                    stripped = prev_word.rstrip(" ")
                    width_delta = (
                        stringWidth(prev_word, font, size)
                        - stringWidth(stripped, font, size)
                    )
                    cur_line[-1] = (stripped, prev_y)
                    cur_width -= width_delta
            word_w = stringWidth(word + " ", font, size)
            if cur_width + word_w > max_w and cur_line:
                lines.append(cur_line)
                cur_line = []
                cur_width = 0.0
            cur_line.append((word + " ", is_y))
            cur_width += word_w
    if cur_line:
        lines.append(cur_line)
    return lines


def smart_wrap_heading(text: str, font: str, size: int,
                       max_w: int) -> list[str]:
    """Wrap heading, keeping N+adjacent-noun atoms (e.g. '31 EXTRA DAYS') together."""
    nbsp = " "
    protected = text
    # Detect "<number> <word>" or "<number> <word> <word>" patterns
    matches = list(re.finditer(
        r"\b(\d+([,.\d]+)*[KMB]?)\s+(\w+(?:\s+\w+){0,1})\b", text))
    for m in reversed(matches):
        atom = m.group(0)
        if stringWidth(atom, font, size) <= max_w:
            protected = protected[:m.start()] + atom.replace(
                " ", nbsp) + protected[m.end():]
    words = protected.split(" ")
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        cand = " ".join(cur + [word])
        cand_disp = cand.replace(nbsp, " ")
        if stringWidth(cand_disp, font, size) <= max_w or not cur:
            cur.append(word)
        else:
            lines.append(" ".join(cur).replace(nbsp, " "))
            cur = [word]
    if cur:
        lines.append(" ".join(cur).replace(nbsp, " "))
    return lines


def adaptive_heading(text: str, font: str, max_w: int, max_size: int = 64,
                     min_size: int = 40, max_lines: int = 3) -> tuple[int, list[str]]:
    """Find largest font size where heading fits ≤max_lines."""
    for size in range(max_size, min_size - 1, -4):
        lines = smart_wrap_heading(text, font, size, max_w)
        if len(lines) <= max_lines:
            return size, lines
    return min_size, smart_wrap_heading(text, font, min_size, max_w)[:max_lines]


def wrap_simple(text: str, font: str, size: int, max_w: int) -> list[str]:
    """Plain word-wrap without yellow segmentation."""
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        cand = " ".join(cur + [w])
        if stringWidth(cand, font, size) <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def draw_text_shadow(c: canvas.Canvas, x: float, y: float, text: str,
                     font: str, size: int, fill_hex: str,
                     shadow_off: int = 3, shadow_a: float = 0.75) -> None:
    c.saveState()
    c.setFillColor(Color(0, 0, 0, alpha=shadow_a))
    c.setFont(font, size)
    c.drawString(x + shadow_off, y - shadow_off, text)
    c.restoreState()
    c.setFillColor(HexColor(fill_hex))
    c.setFont(font, size)
    c.drawString(x, y, text)


def draw_highlighted_line(c: canvas.Canvas, x: float, y: float,
                          line: list[tuple[str, bool]], font: str, size: int,
                          shadow: bool = False) -> None:
    cur_x = x
    for seg, is_y in line:
        if shadow:
            c.saveState()
            c.setFillColor(Color(0, 0, 0, alpha=0.6))
            c.setFont(font, size)
            c.drawString(cur_x + 2, y - 2, seg)
            c.restoreState()
        c.setFillColor(HexColor(COLOR_ACCENT_YELLOW if is_y else COLOR_TEXT_WHITE))
        c.setFont(font, size)
        c.drawString(cur_x, y, seg)
        cur_x += stringWidth(seg, font, size)


def draw_wrapped_highlights(c: canvas.Canvas, x: float, y: float, text: str,
                            font: str, size: int, max_w: int, line_h: int,
                            max_lines: int | None = None,
                            shadow: bool = True) -> float:
    lines = wrap_segments(text, font, size, max_w)
    if max_lines:
        lines = lines[:max_lines]
    cur_y = y
    for line in lines:
        draw_highlighted_line(c, x, cur_y, line, font, size, shadow=shadow)
        cur_y -= line_h
    return cur_y


def draw_centered_highlights(c: canvas.Canvas, center_x: float, y: float,
                             text: str, font: str, size: int, max_w: int,
                             line_h: int, max_lines: int | None = None,
                             shadow: bool = False) -> float:
    lines = wrap_segments(text, font, size, max_w)
    if max_lines:
        lines = lines[:max_lines]
    cur_y = y
    for line in lines:
        total_w = sum(stringWidth(seg, font, size) for seg, _ in line)
        cur_x = center_x - total_w / 2
        draw_highlighted_line(c, cur_x, cur_y, line, font, size, shadow=shadow)
        cur_y -= line_h
    return cur_y


# ---------- Image / hero helpers ----------

def _gradient_png(w: int, h: int, top_a: float, bot_a: float,
                  out_path: str) -> str:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        a = top_a + (bot_a - top_a) * (y / max(1, h - 1))
        for x in range(w):
            px[x, y] = (0, 0, 0, int(a * 255))
    img.save(out_path, format="PNG")
    return out_path


def _crop_hero_to_canvas(hero_path: str, out_path: str) -> str | None:
    if not Path(hero_path).exists():
        return None
    try:
        img = Image.open(hero_path).convert("RGB")
    except Exception:
        return None
    sw, sh = img.size
    target_ratio = W / H
    src_ratio = sw / sh
    if src_ratio > target_ratio:
        nw = int(sh * target_ratio)
        l = (sw - nw) // 2
        img = img.crop((l, 0, l + nw, sh))
    else:
        nh = int(sw / target_ratio)
        t = max(0, (sh - nh) // 2)
        img = img.crop((0, t, sw, t + nh))
    img = img.resize((W, H), Image.LANCZOS)
    img.save(out_path, quality=92)
    return out_path


def draw_logo(c: canvas.Canvas, x_center: float = W / 2,
              y_bottom: float = 80, size: float = 90) -> None:
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), x_center - size / 2, y_bottom,
                    width=size, height=size, mask="auto")


def draw_swipe_indicator(c: canvas.Canvas) -> None:
    """SOTA Pattern #10 (Article 14.1) — yellow dot bottom-right on inner slides."""
    c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
    c.circle(W - 32, 32, 6, fill=1, stroke=0)


def draw_regulation_badge(c: canvas.Canvas, code: str, font_mono: str) -> None:
    """SOTA Pattern #3 (Article 14.4 revised 2026-05-13) — yellow rounded badge
    top-right with regulation code in IBM Plex Mono / Menlo fallback.

    WCAG: yellow #F4C430 vs antracite #2C2F38 = 8.14:1 AAA;
          black text on yellow = 12.79:1 AAA inside.
    """
    if not code:
        return
    text_w = stringWidth(code, font_mono, 16)
    pad_x, pad_y = 12, 6
    badge_w = text_w + pad_x * 2
    badge_h = 16 + pad_y * 2
    x = W - 32 - badge_w
    y = H - 32 - badge_h
    c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
    c.roundRect(x, y, badge_w, badge_h, 4, fill=1, stroke=0)
    c.setFillColor(HexColor(COLOR_BG_BLACK))
    c.setFont(font_mono, 16)
    c.drawString(x + pad_x, y + pad_y + 3, code)


# ---------- Layout renderers ----------

@dataclass
class RenderContext:
    font_bold: str
    font_reg: str
    font_mono: str
    slide_count: int
    is_inner: bool  # slides 2..N-1
    primary_regulation_code: str | None


def render_cover_photo(c: canvas.Canvas, s: dict[str, Any],
                       ctx: RenderContext) -> None:
    """Cover slide — hero + yellow subhead + heading + optional badge."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    hero = s.get("hero_image_path") or s.get("image_path")
    if hero:
        cropped = _crop_hero_to_canvas(hero, "/tmp/_wr2_cover_hero.jpg")
        if cropped:
            c.drawImage(cropped, 0, 0, width=W, height=H)
            grad = _gradient_png(W, H // 2, 0.0, 0.92,
                                 "/tmp/_wr2_cover_grad.png")
            c.drawImage(grad, 0, 0, width=W, height=H // 2, mask="auto")

    # Regulation badge top-right (Article 14.4)
    if ctx.primary_regulation_code:
        draw_regulation_badge(c, ctx.primary_regulation_code, ctx.font_mono)

    max_w = W - 120

    # Heading + subhead with dynamic gap (fix #1)
    heading_text = s.get("heading", "") or ""
    sub_text = s.get("subheading") or s.get("sub_heading") or ""

    head_size, head_lines = adaptive_heading(
        heading_text.upper(), ctx.font_bold, max_w,
        max_size=72, min_size=48, max_lines=3)
    head_line_h = head_size + 14

    sub_size = 36
    sub_lines = smart_wrap_heading(
        sub_text.upper(), ctx.font_bold, sub_size, max_w)[:2] if sub_text else []
    sub_line_h = 50

    y_head_bottom_line = 240
    y_head_top_line = y_head_bottom_line + (len(head_lines) - 1) * head_line_h
    head_top_edge = y_head_top_line + head_size
    y_sub_bottom_line = head_top_edge + 60
    y_sub_top_line = y_sub_bottom_line + (len(sub_lines) - 1) * sub_line_h

    cur_y = y_sub_top_line
    for line in sub_lines:
        draw_text_shadow(c, 60, cur_y, line, ctx.font_bold, sub_size,
                         COLOR_ACCENT_YELLOW, shadow_off=2, shadow_a=0.75)
        cur_y -= sub_line_h

    cur_y = y_head_top_line
    for line_text in head_lines:
        line_segs = split_for_yellow(line_text)
        cur_x = 60
        for seg, is_y in line_segs:
            c.saveState()
            c.setFillColor(Color(0, 0, 0, alpha=0.75))
            c.setFont(ctx.font_bold, head_size)
            c.drawString(cur_x + 3, cur_y - 3, seg)
            c.restoreState()
            c.setFillColor(HexColor(COLOR_ACCENT_YELLOW if is_y else COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, head_size)
            c.drawString(cur_x, cur_y, seg)
            cur_x += stringWidth(seg, ctx.font_bold, head_size)
        cur_y -= head_line_h

    draw_logo(c, y_bottom=80, size=110)


def render_photo_headline_yellow_sub(c: canvas.Canvas, s: dict[str, Any],
                                     ctx: RenderContext) -> None:
    """Inner hero slide — top heading + body + (optional) hero photo."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    hero = s.get("hero_image_path") or s.get("image_path")
    has_hero = False
    if hero:
        cropped = _crop_hero_to_canvas(hero, "/tmp/_wr2_inner_hero.jpg")
        if cropped:
            c.drawImage(cropped, 0, 0, width=W, height=H)
            grad = _gradient_png(W, H, 0.55, 0.85, "/tmp/_wr2_inner_grad.png")
            c.drawImage(grad, 0, 0, width=W, height=H, mask="auto")
            has_hero = True

    if not has_hero:
        c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
        c.rect(0, 0, W, H, fill=1, stroke=0)

    max_w = W - 120

    # Fix 2026-05-15: previously yellow sub at y=H-110 (font 28) and heading
    # at y=H-170 (font up to 56) → only 60pt vertical gap. With heading 56pt
    # ascender top, the heading visually overlapped the sub. New: enforce
    # SUB_BELOW_HEADING ordering — sub is the eyebrow (smaller, ABOVE heading)
    # OR moved down with proper gap; here we keep sub at top but with explicit
    # bottom-of-sub clearance before heading top.
    SUB_SIZE = 22                     # smaller eyebrow to leave room
    SUB_TO_HEADING_GAP = 38           # explicit gap (font_size + breathing room)
    SUB_Y = H - 100                   # eyebrow baseline

    # Yellow sub (eyebrow)
    sub_text = (s.get("subheading") or s.get("yellow_accent") or "").upper()
    if sub_text:
        c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
        c.setFont(ctx.font_bold, SUB_SIZE)
        c.drawString(60, SUB_Y, sub_text[:60])

    # Heading — anchored below sub with explicit gap (avoid vertical overlap)
    heading = (s.get("heading") or "").upper()
    head_size, head_lines = adaptive_heading(
        heading, ctx.font_bold, max_w, max_size=56, min_size=40, max_lines=3)
    head_line_h = head_size + 12
    # Heading top baseline = SUB_Y - SUB_SIZE (sub block bottom) - GAP - head_size (heading first-line ascender)
    y_head = SUB_Y - SUB_SIZE - SUB_TO_HEADING_GAP - head_size
    for line in head_lines:
        segs = split_for_yellow(line)
        cur_x = 60
        for seg, is_y in segs:
            c.setFillColor(HexColor(COLOR_ACCENT_YELLOW if is_y else COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, head_size)
            c.drawString(cur_x, y_head, seg)
            cur_x += stringWidth(seg, ctx.font_bold, head_size)
        y_head -= head_line_h

    # Body (UPPERCASE) — vcentered in space between heading bottom and logo top.
    # Fix 1 (2026-05-13): previously body anchored just below heading, leaving
    # 50-70% of canvas as empty antracite. Now compute body block height and
    # center it vertically within [logo_top + 60pt, heading_bottom - 30pt].
    body = (s.get("body") or "").upper()
    if body:
        body_size = 30
        body_line_h = body_size + 12
        # Pre-wrap to know the line count
        body_lines_segs = wrap_segments(body, ctx.font_bold, body_size, max_w)
        body_lines_segs = body_lines_segs[:8]
        body_total_h = len(body_lines_segs) * body_line_h

        # Available zone: top = just below last heading baseline; bottom = logo top edge + safety
        zone_top = y_head + head_line_h - 30
        logo_top_edge = 80 + 90 + 60  # logo y=80, h=90, safety 60
        zone_bottom = logo_top_edge

        # Center body block in [zone_bottom, zone_top]
        vcenter = (zone_top + zone_bottom) / 2
        body_start_y = vcenter + body_total_h / 2 - body_size / 2
        # Clamp: never push above zone_top, never below zone_bottom
        body_start_y = min(body_start_y, zone_top - body_size)
        body_start_y = max(body_start_y, zone_bottom + body_total_h - body_size)

        cur_y = body_start_y
        for line in body_lines_segs:
            draw_highlighted_line(c, 60, cur_y, line, ctx.font_bold,
                                  body_size, shadow=has_hero)
            cur_y -= body_line_h

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_dark_status_list(c: canvas.Canvas, s: dict[str, Any],
                            ctx: RenderContext) -> None:
    """3-6 items label:value, status colors neutral/critical/positive."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    max_w = W - 120
    head_size, head_lines = adaptive_heading(
        heading, ctx.font_bold, max_w, max_size=48, min_size=36, max_lines=2)
    y_head = H - 130
    for line in head_lines:
        c.setFillColor(HexColor(COLOR_TEXT_WHITE))
        c.setFont(ctx.font_bold, head_size)
        c.drawString(60, y_head, line)
        y_head -= head_size + 12

    # Red rule
    c.setStrokeColor(HexColor(COLOR_STATUS_RED))
    c.setLineWidth(4)
    c.line(60, y_head - 10, 220, y_head - 10)

    # Fix 2026-05-15: previous version had (a) label at cur_y and value at
    # cur_y-40 with no wrap → value font 32pt collides with label 18pt of
    # NEXT row because cur_y -= 110 isn't enough when value is multi-line;
    # (b) status="critical" mapped to red, violating brand constitution
    # (white+yellow only — red reserved for logo + thin rule). Both fixed.
    items = s.get("list_items") or []
    LABEL_TO_VALUE_GAP = 32           # vertical gap between label baseline and value baseline (label ~18pt, gap accommodates descenders + leading)
    VALUE_LINE_HEIGHT = 38            # for value at 28pt with leading
    INTER_ITEM_GAP = 40               # gap between bottom of one value block and top of next label
    LABEL_SIZE = 16
    VALUE_SIZE = 28
    cur_y = y_head - 80
    for it in items[:6]:
        label = (it.get("label") or "").upper()
        value_full = (it.get("value") or "").upper()
        status = it.get("status") or "neutral"
        # Constitution: white + yellow only. critical→white+bold (intensity via weight, not red).
        color = {
            "critical": COLOR_TEXT_WHITE,
            "positive": COLOR_ACCENT_YELLOW,
            "neutral": COLOR_TEXT_WHITE,
        }.get(status, COLOR_TEXT_WHITE)

        # Label (small caps, muted)
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_mono, LABEL_SIZE)
        c.drawString(60, cur_y, label[:48])

        # Value: wrap to fit, max 2 lines, drawn below label with gap
        c.setFillColor(HexColor(color))
        c.setFont(ctx.font_bold, VALUE_SIZE)
        value_lines = wrap_simple(value_full, ctx.font_bold, VALUE_SIZE, W - 120)[:2]
        line_y = cur_y - LABEL_TO_VALUE_GAP
        for vl in value_lines:
            c.drawString(60, line_y, vl)
            line_y -= VALUE_LINE_HEIGHT
        # Next item position: after this value block plus inter-item gap
        cur_y = line_y - INTER_ITEM_GAP + VALUE_LINE_HEIGHT  # line_y is "below last line", add back one LH to get bottom of last line

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_evidence_carved(c: canvas.Canvas, s: dict[str, Any],
                           ctx: RenderContext) -> None:
    """Hammurabi — heading carved + body + small mono code below."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    body = (s.get("body") or "").upper()
    code_line = s.get("evidence_code") or s.get("yellow_accent") or ""

    max_w = W - 120

    # Carved heading (large, embossed shadow)
    head_size, head_lines = adaptive_heading(
        heading, ctx.font_bold, max_w, max_size=60, min_size=44, max_lines=3)
    head_line_h = head_size + 14
    y_head = H - 150
    for line in head_lines:
        # Engraved effect: dark shadow above, light below
        c.saveState()
        c.setFillColor(Color(0, 0, 0, alpha=0.6))
        c.setFont(ctx.font_bold, head_size)
        c.drawString(62, y_head - 3, line)
        c.restoreState()
        c.setFillColor(HexColor(COLOR_TEXT_WHITE))
        c.setFont(ctx.font_bold, head_size)
        c.drawString(60, y_head, line)
        y_head -= head_line_h

    # Yellow rule
    rule_y = y_head - 10
    c.setStrokeColor(HexColor(COLOR_ACCENT_YELLOW))
    c.setLineWidth(3)
    c.line(60, rule_y, 280, rule_y)

    # Body
    if body:
        body_y_top = rule_y - 50
        draw_wrapped_highlights(c, 60, body_y_top, body, ctx.font_bold,
                                28, max_w, 40, max_lines=10, shadow=False)

    # Code/source line (mono bottom)
    if code_line:
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_mono, 18)
        c.drawString(60, 210, code_line.upper())

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_qa_dialogue(c: canvas.Canvas, s: dict[str, Any],
                       ctx: RenderContext) -> None:
    """2-3 voice exchanges (founder/Bali Zero/etc)."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    if heading:
        c.setFillColor(HexColor(COLOR_TEXT_WHITE))
        c.setFont(ctx.font_bold, 32)
        c.drawString(60, H - 110, heading[:50])

    pairs = s.get("qa_pairs") or []
    cur_y = H - 220
    max_w = W - 160
    for p in pairs[:3]:
        voice = (p.get("voice") or "").upper()
        line = p.get("line") or ""
        # Voice label yellow
        c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
        c.setFont(ctx.font_mono, 18)
        c.drawString(60, cur_y, voice)
        cur_y -= 30
        # Line body white
        body_lines = wrap_simple(line, ctx.font_bold, 26, max_w)
        for bl in body_lines:
            c.setFillColor(HexColor(COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, 26)
            c.drawString(60, cur_y, bl)
            cur_y -= 36
        cur_y -= 30

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_timeline_pinboard(c: canvas.Canvas, s: dict[str, Any],
                             ctx: RenderContext) -> None:
    """date+event vertical timeline with red rule."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    c.setFillColor(HexColor(COLOR_TEXT_WHITE))
    c.setFont(ctx.font_bold, 36)
    c.drawString(60, H - 110, heading[:40])

    # Vertical red rule
    c.setStrokeColor(HexColor(COLOR_STATUS_RED))
    c.setLineWidth(3)
    c.line(80, H - 200, 80, 240)

    # Fix 2026-05-15: previous version drew date at (110, cur_y+8) and event
    # at (110, cur_y-8) — only 16pt vertical separation but font 18 vs 24,
    # so glyphs interleaved producing the "Q01²⁶A⁻⁰R¹R⁻⁰IVALS" garbage.
    # Plus event used same X=110 as date — they collided horizontally.
    # New layout: date as separated pill ABOVE event, both starting at x=110,
    # date at cur_y, event starting cur_y - 26 (font 18 + 8 padding).
    events = s.get("timeline") or []
    DATE_TO_EVENT_GAP = 28
    EVENT_LINE_H = 30
    INTER_EVENT_GAP = 36
    cur_y = H - 220
    for ev in events[:6]:
        date = ev.get("date") or ""
        event = (ev.get("event") or "").upper()
        # Dot on rule, aligned vertically with date row
        c.setFillColor(HexColor(COLOR_STATUS_RED))
        c.circle(80, cur_y - 4, 6, fill=1, stroke=0)
        # Date — yellow mono, single line, no overlap
        c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
        c.setFont(ctx.font_mono, 16)
        c.drawString(110, cur_y, date)
        # Event — below date with proper gap
        evt_lines = wrap_simple(event, ctx.font_bold, 22, W - 180)[:2]
        evt_y = cur_y - DATE_TO_EVENT_GAP
        for el in evt_lines:
            c.setFillColor(HexColor(COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, 22)
            c.drawString(110, evt_y, el)
            evt_y -= EVENT_LINE_H
        # Move to next event: bottom of last event line + inter-event gap
        cur_y = evt_y - INTER_EVENT_GAP + EVENT_LINE_H

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_three_verdicts(c: canvas.Canvas, s: dict[str, Any],
                          ctx: RenderContext) -> None:
    """3 columns side-by-side (GO/CAUTION/STOP color-coded)."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    c.setFillColor(HexColor(COLOR_TEXT_WHITE))
    c.setFont(ctx.font_bold, 32)
    c.drawString(60, H - 110, heading[:40])

    verdicts = s.get("verdicts") or []
    col_w = (W - 200) / max(1, min(3, len(verdicts)))
    color_map = {
        "go": COLOR_ACCENT_YELLOW,
        "positive": COLOR_ACCENT_YELLOW,
        "caution": COLOR_TEXT_WHITE,
        "neutral": COLOR_TEXT_WHITE,
        "stop": COLOR_STATUS_RED,
        "critical": COLOR_STATUS_RED,
    }
    for i, v in enumerate(verdicts[:3]):
        x = 80 + i * (col_w + 40)
        verdict_kind = (v.get("kind") or "neutral").lower()
        color = color_map.get(verdict_kind, COLOR_TEXT_WHITE)
        label = (v.get("label") or "").upper()
        body = (v.get("body") or "")

        # Label (large color)
        c.setFillColor(HexColor(color))
        c.setFont(ctx.font_bold, 44)
        c.drawString(x, H - 280, label[:8])
        # Body wrapped
        body_lines = wrap_simple(body, ctx.font_bold, 22, col_w)[:8]
        body_y = H - 340
        for bl in body_lines:
            c.setFillColor(HexColor(COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, 22)
            c.drawString(x, body_y, bl)
            body_y -= 30

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_statement_bomb(c: canvas.Canvas, s: dict[str, Any],
                          ctx: RenderContext) -> None:
    """Closing slide — single statement centered, adaptive shrink."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    statement = (s.get("statement") or s.get("heading") or "").upper().strip()
    if not statement:
        return

    # If statement has 2 sentences, render as 2 stanzas
    sentences = [t.strip() for t in re.split(r"(?<=[.!?])\s+", statement) if t.strip()]
    if not sentences:
        sentences = [statement]

    max_w = W - 120
    # Adaptive shrink: find size where each sentence fits ≤2 lines
    size = 80
    while size >= 48:
        ok = all(len(smart_wrap_heading(snt, ctx.font_bold, size, max_w)) <= 2
                 for snt in sentences)
        if ok:
            break
        size -= 4
    line_h = size + 18
    sentence_gap = 30

    total_lines = sum(len(smart_wrap_heading(snt, ctx.font_bold, size, max_w))
                      for snt in sentences)
    total_h = total_lines * line_h + sentence_gap * max(0, len(sentences) - 1)
    center_y_top = (H + total_h) / 2 - size

    cur_y = center_y_top
    for snt in sentences:
        lines = smart_wrap_heading(snt, ctx.font_bold, size, max_w)
        for line in lines:
            draw_centered_highlights(c, W / 2, cur_y, line, ctx.font_bold,
                                     size, max_w, line_h, max_lines=1)
            cur_y -= line_h
        cur_y -= sentence_gap

    draw_logo(c, y_bottom=80, size=110)


def render_elegant_close(c: canvas.Canvas, s: dict[str, Any],
                         ctx: RenderContext) -> None:
    """Optional last slide — soft CTA (Article 6.6.1)."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    body = s.get("body") or ""
    email = s.get("email") or "zantara@balizero.com"
    whatsapp = s.get("whatsapp") or "wa.me/6285954680980"

    c.setFillColor(HexColor(COLOR_TEXT_WHITE))
    c.setFont(ctx.font_bold, 40)
    c.drawString(60, H - 200, heading[:38])

    if body:
        lines = wrap_simple(body, ctx.font_bold, 26, W - 120)[:5]
        cur_y = H - 280
        for ln in lines:
            c.setFillColor(HexColor(COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, 26)
            c.drawString(60, cur_y, ln)
            cur_y -= 36

    # Soft CTA mono
    c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
    c.setFont(ctx.font_mono, 20)
    c.drawString(60, 380, email.upper())
    c.setFillColor(HexColor(COLOR_TEXT_MUTED))
    c.setFont(ctx.font_mono, 18)
    c.drawString(60, 350, whatsapp.upper())

    draw_logo(c, y_bottom=80, size=90)


# ---------- 4 ADOPT type-as-design patterns (research 2026-05-12) ----------

def render_stat_card_hero(c: canvas.Canvas, s: dict[str, Any],
                          ctx: RenderContext) -> None:
    """ADOPT pattern 1 — Quartz/ProPublica big-number stat card.

    Fix 3 (2026-05-13): canonical Quartz layout — kicker mute TOP, giant
    number vertically centered, caption block BELOW number, source mono
    footer above logo. Previously caption was above number (wrong direction).
    """
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    stat = s.get("stat") or s.get("heading") or ""
    caption = s.get("caption") or s.get("body") or ""
    source = s.get("source") or s.get("yellow_accent") or ""
    # Optional kicker (small label top — Quartz convention).
    # Falls back to source-like field if no explicit kicker.
    kicker = (s.get("kicker") or s.get("subheading") or "").upper()

    # 1. Kicker (small mute label top)
    if kicker:
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_mono, 20)
        kw = stringWidth(kicker[:60], ctx.font_mono, 20)
        c.drawString((W - kw) / 2, H - 180, kicker[:60])

    # 2. Giant number (vertically centered, ~middle of canvas)
    stat_size = 380 if len(stat) <= 4 else (280 if len(stat) <= 6 else 200)
    c.setFillColor(HexColor(COLOR_ACCENT_YELLOW))
    c.setFont(ctx.font_bold, stat_size)
    stat_w = stringWidth(stat, ctx.font_bold, stat_size)
    # Anchor stat so its center sits near vertical middle of canvas
    # (canvas vertical center = 675, stat baseline ~ center + stat_size*0.35)
    stat_baseline = H / 2 - stat_size * 0.35
    c.drawString((W - stat_w) / 2, stat_baseline, stat)

    # 3. Caption (BELOW the number — Quartz readout)
    if caption:
        cap_size = 32
        lines = wrap_simple(caption.upper(), ctx.font_bold, cap_size, W - 200)[:3]
        # Anchor caption block top just below the stat baseline minus
        # some safety (stat_baseline - 60 is "below the number's bottom")
        cap_top = stat_baseline - 90
        cur_y = cap_top
        for ln in lines:
            lw = stringWidth(ln, ctx.font_bold, cap_size)
            c.setFillColor(HexColor(COLOR_TEXT_WHITE))
            c.setFont(ctx.font_bold, cap_size)
            c.drawString((W - lw) / 2, cur_y, ln)
            cur_y -= 46

    # 4. Source mono footer (above logo)
    if source:
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_mono, 20)
        meta = f"SOURCE: {source.upper()}"
        mw = stringWidth(meta, ctx.font_mono, 20)
        c.drawString((W - mw) / 2, 230, meta)

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_thin_red_rule_divider(c: canvas.Canvas, s: dict[str, Any],
                                 ctx: RenderContext) -> None:
    """ADOPT pattern 2 — FT-style red rule + body + mono footer."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    rule_y = H - 480
    c.setStrokeColor(HexColor(COLOR_STATUS_RED))
    c.setLineWidth(3)
    c.line(60, rule_y, 380, rule_y)

    body = (s.get("body") or s.get("heading") or "").upper()
    body_lines = wrap_segments(body, ctx.font_bold, 38, W - 120)[:5]
    cur_y = rule_y - 70
    for line in body_lines:
        draw_highlighted_line(c, 60, cur_y, line, ctx.font_bold, 38)
        cur_y -= 52

    code = s.get("regulation_code") or ctx.primary_regulation_code or ""
    source = s.get("source") or ""
    effective = s.get("effective") or ""

    c.setStrokeColor(HexColor(COLOR_STATUS_RED))
    c.setLineWidth(1)
    c.line(60, 260, W - 60, 260)

    c.setFillColor(HexColor(COLOR_TEXT_MUTED))
    c.setFont(ctx.font_mono, 20)
    footer = "  ·  ".join(x for x in [code, source] if x)
    if footer:
        c.drawString(60, 220, footer)
    if effective:
        c.setFont(ctx.font_mono, 18)
        c.drawString(60, 195, effective)

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_swiss_grid_asymmetry(c: canvas.Canvas, s: dict[str, Any],
                                ctx: RenderContext) -> None:
    """ADOPT pattern 3 — Pentagram-style numerals + steps."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    title_meta = (s.get("yellow_accent") or s.get("subheading") or "").upper()
    if title_meta:
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_mono, 20)
        c.drawString(60, H - 100, title_meta[:60])

    steps = s.get("steps") or []
    cur_y = H - 220
    for i, st in enumerate(steps[:4]):
        num = st.get("num") or f"{i + 1:02d}"
        head = (st.get("head") or "").upper()
        body = (st.get("body") or "")
        emphasis = i == 0

        c.setFillColor(HexColor(COLOR_STATUS_RED if emphasis else COLOR_TEXT_WHITE))
        c.setFont(ctx.font_bold, 110)
        c.drawString(60, cur_y - 90, num)

        c.setFillColor(HexColor(COLOR_TEXT_WHITE))
        c.setFont(ctx.font_bold, 40)
        c.drawString(220, cur_y - 30, head)
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_reg, 26)
        c.drawString(220, cur_y - 65, body)

        cur_y -= 230

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


def render_monospace_evidence_block(c: canvas.Canvas, s: dict[str, Any],
                                    ctx: RenderContext) -> None:
    """ADOPT pattern 4 — The Markup-style system output as evidence."""
    c.setFillColor(HexColor(COLOR_BG_ANTRACITE))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    heading = (s.get("heading") or "").upper()
    c.setFillColor(HexColor(COLOR_TEXT_WHITE))
    c.setFont(ctx.font_bold, 28)
    c.drawString(60, H - 130, heading[:50])

    c.setStrokeColor(HexColor(COLOR_ACCENT_YELLOW))
    c.setLineWidth(3)
    c.line(60, H - 155, 300, H - 155)

    evidence = s.get("evidence_lines") or []
    cur_y = H - 270
    for ln_obj in evidence[:14]:
        if isinstance(ln_obj, str):
            text = ln_obj
            color = COLOR_TEXT_WHITE
        else:
            text = ln_obj.get("text") or ""
            color_kind = (ln_obj.get("color") or "white").lower()
            color = {
                "white": COLOR_TEXT_WHITE,
                "yellow": COLOR_ACCENT_YELLOW,
                "red": COLOR_STATUS_RED,
                "muted": COLOR_TEXT_MUTED,
            }.get(color_kind, COLOR_TEXT_WHITE)

        c.setFillColor(HexColor(color))
        c.setFont(ctx.font_mono, 28)
        c.drawString(80, cur_y, text)
        cur_y -= 38

    source = s.get("source") or ""
    captured = s.get("captured") or ""
    if source or captured:
        c.setFillColor(HexColor(COLOR_TEXT_MUTED))
        c.setFont(ctx.font_mono, 18)
        footer = "  ·  ".join(x for x in [source, captured] if x).upper()
        c.drawString(60, 220, footer)

    draw_logo(c)
    if ctx.is_inner:
        draw_swipe_indicator(c)


# ---------- Router ----------

LAYOUT_DISPATCH = {
    "cover-photo": render_cover_photo,
    "cover": render_cover_photo,
    "photo-headline-yellow-sub": render_photo_headline_yellow_sub,
    "dark-status-list": render_dark_status_list,
    "evidence-carved": render_evidence_carved,
    "qa-dialogue": render_qa_dialogue,
    "timeline-pinboard": render_timeline_pinboard,
    "three-verdicts": render_three_verdicts,
    "statement-bomb": render_statement_bomb,
    "elegant-close": render_elegant_close,
    "stat-card-hero": render_stat_card_hero,
    "thin-red-rule-divider": render_thin_red_rule_divider,
    "swiss-grid-asymmetry": render_swiss_grid_asymmetry,
    "monospace-evidence-block": render_monospace_evidence_block,
}


def render_slide(c: canvas.Canvas, slide: dict[str, Any],
                 ctx: RenderContext) -> None:
    family = (slide.get("layout_family") or "photo-headline-yellow-sub").strip()
    fn = LAYOUT_DISPATCH.get(family)
    if fn is None:
        sys.stderr.write(
            f"[wr2-render] unknown layout_family={family!r} on slide "
            f"{slide.get('index')!r} — falling back to "
            f"photo-headline-yellow-sub\n")
        fn = render_photo_headline_yellow_sub
    fn(c, slide, ctx)


# ---------- PDF assembly ----------

def render_carousel(slides_json: dict[str, Any], out_pdf: str) -> int:
    register_fonts()
    font_bold = pick_font(["Montserrat-ExtraBold", "Montserrat-Bold",
                           "ArialBold", "Helvetica-Bold"])
    font_reg = pick_font(["Montserrat-Regular", "Arial", "Helvetica"])
    font_mono = pick_font(["Menlo", "CourierNewBold", "CourierNew", "Courier"])

    slides = slides_json.get("slides") or []
    n = len(slides)
    primary_regulation_code = (slides_json.get("primary_regulation_code")
                               or slides_json.get("brief", {}).get(
                                   "primary_regulation_code"))

    c = canvas.Canvas(out_pdf, pagesize=(W, H))
    for i, s in enumerate(slides):
        is_inner = (i > 0) and (i < n - 1)
        ctx = RenderContext(
            font_bold=font_bold,
            font_reg=font_reg,
            font_mono=font_mono,
            slide_count=n,
            is_inner=is_inner,
            primary_regulation_code=primary_regulation_code,
        )
        render_slide(c, s, ctx)
        c.showPage()
    c.save()
    return n


# ---------- CLI ----------

def load_slides_from_pg(draft_id: str) -> dict[str, Any]:
    import psycopg

    dsn = os.environ.get(
        "WR2_PG_DSN",
        "postgresql://postgres@127.0.0.1:15432/postgres")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT topic, slides_json FROM war_room_drafts WHERE id = %s",
                (draft_id,))
            row = cur.fetchone()
            if not row:
                raise SystemExit(f"draft {draft_id} not found")
            topic, slides_json = row
    if isinstance(slides_json, str):
        slides_json = json.loads(slides_json)
    slides_json.setdefault("topic", topic)
    return slides_json


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--slides-json", type=str,
                     help="Local slides.json file (smoke test)")
    src.add_argument("--draft-id", type=str,
                     help="war_room_drafts.id (PG mode)")
    p.add_argument("--out", type=str, default=None,
                   help="Output PDF path (default /tmp/wr2_<id>.pdf)")
    p.add_argument("--apply", action="store_true",
                   help="Upload to Tigris + import into Canva via MCP "
                        "(otherwise only writes local PDF)")
    args = p.parse_args()

    if args.slides_json:
        with open(args.slides_json) as f:
            slides_json = json.load(f)
        slug = Path(args.slides_json).stem
    else:
        slides_json = load_slides_from_pg(args.draft_id)
        slug = args.draft_id

    out_pdf = args.out or f"/tmp/wr2_{slug}.pdf"
    n = render_carousel(slides_json, out_pdf)
    size = Path(out_pdf).stat().st_size
    print(f"[wr2-render] wrote {out_pdf} — {n} pages, {size} bytes")

    if args.apply:
        print("[wr2-render] --apply is a TODO at this stage. The Tigris upload + "
              "Canva import-design-from-url MCP call is driven by the orchestrator "
              "(canva-renderer wrapper) — this script only produces the PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
