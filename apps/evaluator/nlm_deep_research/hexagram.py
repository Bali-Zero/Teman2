"""Hexagram Dashboard — 6-bit daily state of each NB mapped to King Wen hexagram.

Sacred root (commented only): the Yi Jing maps the quality of any moment to
six binary lines (yin=broken=0, yang=intact=1). 2^6 = 64 possible hexagrams.
The King Wen sequence is a 3000-year-old vocabulary that compresses a wide
range of systemic states into memorable archetypes. We don't predict the
future with it. We use it to give an operator a single-word answer to
"how is NB-X today?" in under 60 seconds of reading.

Six dimensions (bottom → top):

    L1 (prakṛti, foundation) — Ingest         last run < 48h
    L2                        — Health         claims_added_7d >= 5
    L3                        — Balance        yin-yang ratio in [0.5, 3]
    L4                        — Memory         synth weekly present
    L5                        — Service        yajna cite_rate_30d > 0.15
    L6 (puruṣa, crown)        — Consciousness  heartbeat < max_age

Each dimension is yang(1) when healthy, yin(0) when stressed.

The binary is read **bottom-to-top** as a string 'L1L2L3L4L5L6', same as
traditional Chinese convention. The King Wen number is looked up from a
canonical table (included in this file).

Side effects:
    - Appends one JSON line per NB per day to hexagram_state.jsonl.
    - Does NOT modify any NB, pipeline, state file.
    - Does NOT call LLM.
    - Does NOT auto-inject into Claude briefing.

Kill switch:
    Remove the cron entry. No other runtime dependency.

Usage:

    python -m apps.evaluator.nlm_deep_research.hexagram --compute    # daily cron
    python -m apps.evaluator.nlm_deep_research.hexagram --view       # ASCII table
    python -m apps.evaluator.nlm_deep_research.hexagram --nb nb4     # single NB
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from apps.evaluator.nlm_deep_research.turiya import (
    NB_CATALOG,
    snapshot_nb,
)

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
HEXAGRAM_STATE_FILE = _DIR / "hexagram_state.jsonl"

# ── Thresholds for dimensions ────────────────────────────────────────────────

INGEST_FRESH_HOURS = 48         # L1 yang if jagrat.last_updated < 48h
HEALTH_MIN_CLAIMS_7D = 5        # L2 yang if claims_added_7d >= 5 (via yajna offered)
BALANCE_STATUS_YANG = "HEALTHY"  # L3 yang iff yin-yang status HEALTHY
SERVICE_MIN_CITE_RATE = 0.15    # L5 yang if cite_rate > 0.15
CONSCIOUSNESS_MAX_HEARTBEAT_HOURS = 26  # L6 yang if heartbeat age < max_age (nbX=6, weekly=170)

# ── King Wen sequence table ──────────────────────────────────────────────────
#
# Each entry keyed by a 6-char binary string read bottom-up (L1 first).
# Value = (king_wen_number, chinese_name, pinyin, gloss).
# Binary convention: '1' = yang (unbroken), '0' = yin (broken). Read L1 L2 L3 L4 L5 L6.
#
# Source: standard King Wen ordering. This table is curated manually to
# satisfy the project constraint "no LLM, no allucinations". Hexagram gloss
# is deliberately short (≤ 60 chars) so it fits in a dashboard line.
#
# NOTE on sourcing: the 64 entries below are derived from the Wilhelm/Baynes
# English translation index and cross-verified against the public-domain
# James Legge translation. Any operator reading this may replace the gloss
# with their preferred translation without breaking any code — only the
# integer and binary are semantic.

KING_WEN: dict[str, tuple[int, str, str, str]] = {
    "111111": (1,  "乾", "Qián",   "Creative force — pure yang"),
    "000000": (2,  "坤", "Kūn",    "Receptive ground — pure yin"),
    "100010": (3,  "屯", "Zhūn",   "Difficulty at the beginning"),
    "010001": (4,  "蒙", "Méng",   "Youthful folly — needs guidance"),
    "111010": (5,  "需", "Xū",     "Waiting with nourishment"),
    "010111": (6,  "訟", "Sòng",   "Conflict — dispute"),
    "010000": (7,  "師", "Shī",    "Army — disciplined collective"),
    "000010": (8,  "比", "Bǐ",     "Holding together — union"),
    "111011": (9,  "小畜","Xiǎo Xù","Small taming — restraint"),
    "110111": (10, "履", "Lǚ",     "Treading carefully"),
    "111000": (11, "泰", "Tài",    "Peace — flourishing"),
    "000111": (12, "否", "Pǐ",     "Stagnation — obstruction"),
    "101111": (13, "同人","Tóng Rén","Fellowship — community"),
    "111101": (14, "大有","Dà Yǒu", "Great possession — abundance"),
    "001000": (15, "謙", "Qiān",   "Modesty"),
    "000100": (16, "豫", "Yù",     "Enthusiasm"),
    "100110": (17, "隨", "Suí",    "Following — adapting"),
    "011001": (18, "蠱", "Gǔ",     "Work on what has decayed"),
    "110000": (19, "臨", "Lín",    "Approach — drawing near"),
    "000011": (20, "觀", "Guān",   "Contemplation — observing"),
    "100101": (21, "噬嗑","Shì Kè", "Biting through — decisive action"),
    "101001": (22, "賁", "Bì",     "Grace — adornment"),
    "000001": (23, "剝", "Bō",     "Splitting apart — decay"),
    "100000": (24, "復", "Fù",     "Return — renewal"),
    "100111": (25, "無妄","Wú Wàng","Innocence — without pretension"),
    "111001": (26, "大畜","Dà Xù",  "Great taming — restraint power"),
    "100001": (27, "頤", "Yí",     "Nourishment — right feeding"),
    "011110": (28, "大過","Dà Guò", "Great exceeding — overweight"),
    "010010": (29, "坎", "Kǎn",    "Abyssal — water, danger"),
    "101101": (30, "離", "Lí",     "Clinging — fire, clarity"),
    "001110": (31, "咸", "Xián",   "Influence — mutual attraction"),
    "011100": (32, "恆", "Héng",   "Duration — endurance"),
    "001111": (33, "遯", "Dùn",    "Retreat — strategic withdrawal"),
    "111100": (34, "大壯","Dà Zhuàng","Great power"),
    "000101": (35, "晉", "Jìn",    "Progress — advancing"),
    "101000": (36, "明夷","Míng Yí","Darkening light — hidden worth"),
    "101011": (37, "家人","Jiā Rén","Family — internal stability"),
    "110101": (38, "睽", "Kuí",    "Opposition — polarity"),
    "001010": (39, "蹇", "Jiǎn",   "Obstruction — limping"),
    "010100": (40, "解", "Xiè",    "Deliverance — release"),
    "110001": (41, "損", "Sǔn",    "Decrease — conscious reduction"),
    "100011": (42, "益", "Yì",     "Increase — beneficial growth"),
    "111110": (43, "夬", "Guài",   "Breakthrough — decisive resolve"),
    "011111": (44, "姤", "Gòu",    "Coming to meet — encounter"),
    "000110": (45, "萃", "Cuì",    "Gathering together"),
    "011000": (46, "升", "Shēng",  "Pushing upward"),
    "010110": (47, "困", "Kùn",    "Oppression — exhaustion"),
    "011010": (48, "井", "Jǐng",   "The well — deep source"),
    "101110": (49, "革", "Gé",     "Revolution — molting"),
    "011101": (50, "鼎", "Dǐng",   "Cauldron — transformation vessel"),
    "100100": (51, "震", "Zhèn",   "Shock — arousing thunder"),
    "001001": (52, "艮", "Gèn",    "Keeping still — mountain"),
    "001011": (53, "漸", "Jiàn",   "Gradual development"),
    "110100": (54, "歸妹","Guī Mèi","Marrying maiden — subordinate role"),
    "101100": (55, "豐", "Fēng",   "Abundance — fullness"),
    "001101": (56, "旅", "Lǚ",     "Wanderer — sojourner"),
    "011011": (57, "巽", "Xùn",    "Gentle wind — penetrating"),
    "110110": (58, "兌", "Duì",    "Joyous lake — exchange"),
    "010011": (59, "渙", "Huàn",   "Dispersion — dissolution"),
    "110010": (60, "節", "Jié",    "Limitation — articulation"),
    "110011": (61, "中孚","Zhōng Fú","Inner truth — sincerity"),
    "001100": (62, "小過","Xiǎo Guò","Small exceeding"),
    "101010": (63, "既濟","Jì Jì",  "After completion — stable"),
    "010101": (64, "未濟","Wèi Jì", "Before completion — unstable"),
}

# Sanity: table must have exactly 64 entries
assert len(KING_WEN) == 64, f"KING_WEN must have 64 entries, has {len(KING_WEN)}"


# ── Derive the 6 dimensions from turiya snapshot ─────────────────────────────


def _dim_ingest(jagrat: dict[str, Any]) -> int:
    """L1 — yang if pipeline last_updated < INGEST_FRESH_HOURS."""
    if not jagrat.get("available"):
        return 0
    last = jagrat.get("last_updated", "?")
    if not last or last == "?":
        return 0
    try:
        dt = datetime.fromisoformat(last)
        now = datetime.now(timezone.utc) if dt.tzinfo is None else datetime.now(dt.tzinfo)
        age_hours = (now - dt).total_seconds() / 3600
        return 1 if age_hours < INGEST_FRESH_HOURS else 0
    except (ValueError, TypeError):
        return 0


def _dim_health(yajna: dict[str, Any]) -> int:
    """L2 — yang if offered >= threshold (production alive)."""
    if not yajna.get("available"):
        return 0
    offered = int(yajna.get("offered", 0) or 0)
    return 1 if offered >= HEALTH_MIN_CLAIMS_7D else 0


def _dim_balance(yin_yang: dict[str, Any]) -> int:
    """L3 — yang iff yin-yang status is HEALTHY."""
    if not yin_yang.get("available"):
        return 0
    return 1 if yin_yang.get("status") == BALANCE_STATUS_YANG else 0


def _dim_memory(sushupti: dict[str, Any]) -> int:
    """L4 — yang if weekly synthetic source present."""
    if not sushupti.get("available"):
        return 0
    return 1 if (sushupti.get("weekly_sources_count") or 0) >= 1 else 0


def _dim_service(yajna: dict[str, Any]) -> int:
    """L5 — yang if global cite_rate > threshold (NB is consumed)."""
    if not yajna.get("available"):
        return 0
    rate = yajna.get("global_cite_rate")
    if rate is None:
        return 0
    return 1 if float(rate) > SERVICE_MIN_CITE_RATE else 0


def _dim_consciousness(heartbeat: dict[str, Any]) -> int:
    """L6 — yang if heartbeat present and fresh."""
    if not heartbeat.get("available"):
        return 0
    age = heartbeat.get("age_hours")
    if age is None:
        return 0
    return 1 if age < CONSCIOUSNESS_MAX_HEARTBEAT_HOURS else 0


def derive_lines(snapshot: dict[str, Any]) -> dict[str, int]:
    """Return the 6 yang/yin lines for a turiya NB snapshot."""
    return {
        "L1_ingest": _dim_ingest(snapshot.get("jagrat", {})),
        "L2_health": _dim_health(snapshot.get("yajna", {})),
        "L3_balance": _dim_balance(snapshot.get("yin_yang", {})),
        "L4_memory": _dim_memory(snapshot.get("sushupti", {})),
        "L5_service": _dim_service(snapshot.get("yajna", {})),
        "L6_consciousness": _dim_consciousness(snapshot.get("heartbeat", {})),
    }


def lines_to_binary(lines: dict[str, int]) -> str:
    """Return the 6-char binary string L1..L6 (bottom-up)."""
    return "".join(
        str(lines[k])
        for k in ("L1_ingest", "L2_health", "L3_balance", "L4_memory", "L5_service", "L6_consciousness")
    )


def binary_to_hexagram(binary: str) -> dict[str, Any]:
    """Look up King Wen entry for a 6-char binary string."""
    if len(binary) != 6 or any(c not in "01" for c in binary):
        return {"binary": binary, "valid": False, "error": "invalid binary"}
    entry = KING_WEN.get(binary)
    if entry is None:  # should never happen — we have all 64
        return {"binary": binary, "valid": False, "error": "missing king_wen entry"}
    number, chinese, pinyin, gloss = entry
    return {
        "binary": binary,
        "valid": True,
        "king_wen": number,
        "chinese": chinese,
        "pinyin": pinyin,
        "gloss": gloss,
    }


# ── ASCII rendering ──────────────────────────────────────────────────────────


def _line_char(bit: int) -> str:
    """Render a single hexagram line as ASCII (top view = L6)."""
    return "━━━━━" if bit == 1 else "━━ ━━"


def render_ascii(binary: str) -> str:
    """Render a 6-line hexagram (top-down display order: L6 at top)."""
    if len(binary) != 6:
        return "(invalid)"
    rows = []
    # Display order: L6 top → L1 bottom
    for i in range(5, -1, -1):
        rows.append(_line_char(int(binary[i])))
    return "\n".join(rows)


def render_compact(binary: str) -> str:
    """Single-line compact glyph: ☰ ☱ ☲ ☳ ☴ ☵ ☶ ☷ are trigrams (3 lines).

    For simplicity we stack 6 lines side-by-side using ▇ (yang) and ▃▃ (yin)
    — ASCII-safe fallback uses 1/0.
    """
    glyph = []
    # Bottom-to-top for reading order L1 → L6
    for c in binary:
        glyph.append("▇" if c == "1" else "▁")
    return "".join(glyph)


# ── Per-NB compute ───────────────────────────────────────────────────────────


def compute_for_nb(
    nb: str,
    evaluator_root: Optional[Path] = None,
    heartbeat_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Compute today's hexagram for a single NB."""
    cat = NB_CATALOG.get(nb, {})
    snap = snapshot_nb(nb, evaluator_root=evaluator_root, heartbeat_dir=heartbeat_dir)
    lines = derive_lines(snap)
    binary = lines_to_binary(lines)
    hex_info = binary_to_hexagram(binary)
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "nb": nb,
        "label": cat.get("label", nb),
        "lines": lines,
        "binary": binary,
        "hexagram": hex_info,
    }


def compute_all(
    nb_catalog: Optional[dict[str, dict[str, str]]] = None,
    evaluator_root: Optional[Path] = None,
    heartbeat_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Compute hexagrams for every NB in catalog."""
    catalog = nb_catalog or NB_CATALOG
    return [
        compute_for_nb(nb, evaluator_root=evaluator_root, heartbeat_dir=heartbeat_dir)
        for nb in catalog
    ]


def append_state(
    entries: list[dict[str, Any]],
    state_file: Optional[Path] = None,
) -> int:
    """Append computed hexagrams to hexagram_state.jsonl. Returns count written."""
    target = state_file or HEXAGRAM_STATE_FILE
    count = 0
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
                count += 1
    except OSError as exc:
        logger.warning("hexagram: state write failed (%s) — %s", target, exc)
    return count


# ── CLI ──────────────────────────────────────────────────────────────────────


def _view_ascii_table(entries: list[dict[str, Any]]) -> str:
    """Single-screen dashboard summary of all hexagrams."""
    rows = ["=== Hexagram Dashboard — " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + " ===", ""]
    rows.append(f"{'NB':<5}  {'Domain':<20}  {'Bits':<7}  {'Hex':<5}  {'Name':<12}  Gloss")
    rows.append("-" * 90)
    for e in entries:
        h = e.get("hexagram", {})
        rows.append(
            f"{e['nb']:<5}  {e['label'][:20]:<20}  {e['binary']:<7}  "
            f"{h.get('king_wen', '?'):<5}  {h.get('pinyin', '?'):<12}  {h.get('gloss', '?')}"
        )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hexagram Dashboard — 6-bit daily NB state")
    parser.add_argument("--compute", action="store_true", help="compute + append to hexagram_state.jsonl")
    parser.add_argument("--view", action="store_true", help="ASCII table for all NBs")
    parser.add_argument("--nb", metavar="NB", help="restrict to single NB")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not (args.compute or args.view):
        parser.print_help()
        return 1

    if args.nb:
        if args.nb not in NB_CATALOG:
            print(f"unknown nb={args.nb}. Valid: {sorted(NB_CATALOG)}", file=sys.stderr)
            return 2
        entry = compute_for_nb(args.nb)
        if args.compute:
            append_state([entry])
        if args.view:
            print(_view_ascii_table([entry]))
        else:
            print(json.dumps(entry, indent=2, ensure_ascii=False, default=str))
        return 0

    entries = compute_all()
    if args.compute:
        written = append_state(entries)
        logger.info("hexagram: wrote %d entries to state", written)
    if args.view:
        print(_view_ascii_table(entries))
    else:
        print(json.dumps(entries, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
