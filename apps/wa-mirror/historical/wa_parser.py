"""Deterministic WhatsApp _chat.txt parser. NO LLM, NO PII redaction (structure only).

Medallion F1 (spec 2026-05-23-chat-data-intelligence-nuzantara.md). Parses the standard
WhatsApp export format into normalized JSON per conversation. Multi-line message bodies are
folded into the preceding message. Attachment refs (<terlampir:>/<attached:>/...) are extracted.

Observed corpus format (2026-05-23):
    \\u200e?[D/M/YY(YY), H.MM.SS] Sender: body
    attachment: ... <terlampir: 00000011-FILE.pdf>  (LRM-prefixed, CRLF line endings)

Usage:
    python3 wa_parser.py --roots <dir>... --out-dir chat_parsed/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

# [D/M/YY or YYYY, H.MM.SS] or [..., H:MM:SS]  — leading LRM (‎) stripped first
_HEADER = re.compile(
    r"^\[(\d{1,2})/(\d{1,2})/(\d{2,4}),\s*(\d{1,2})[.:](\d{2})(?:[.:](\d{2}))?\]\s*(.*?):\s?(.*)$"
)
_ATTACH = re.compile(r"<(?:terlampir|attached|allegato|adjunto|bijgevoegd):\s*([^>]+)>", re.I)
_LRM = "‎"
_SYSTEM_MARKERS = (
    "Messages and calls are end-to-end encrypted",
    "created group",
    "added you",
    "Disappearing messages",
    "turned off disappearing",
    "tidak disertakan",  # sticker not included
    "stiker tidak disertakan",
)


def _parse_ts(d: str, mo: str, y: str, h: str, mi: str, s: str | None) -> str | None:
    year = int(y)
    if year < 100:
        year += 2000
    try:
        return datetime(year, int(mo), int(d), int(h), int(mi), int(s or 0)).isoformat()
    except ValueError:
        # ambiguous D/M vs M/D — corpus is D/M (Indonesian/EU); if month>12 it's already D/M
        return None


def parse_chat(path: str) -> dict:
    messages: list[dict] = []
    senders: set[str] = set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw_lines = fh.read().splitlines()

    cur: dict | None = None
    for raw in raw_lines:
        line = raw.replace(_LRM, "").rstrip("\r")
        m = _HEADER.match(line)
        if m:
            d, mo, y, h, mi, s, sender, body = m.groups()
            cur = {
                "ts": _parse_ts(d, mo, y, h, mi, s),
                "sender": sender.strip(),
                "body": body,
                "attachments": _ATTACH.findall(body),
                "is_system": any(mk in body for mk in _SYSTEM_MARKERS) and not body.strip(),
            }
            senders.add(sender.strip())
            messages.append(cur)
        elif cur is not None:
            # continuation of previous message (multi-line body)
            cur["body"] += "\n" + line
            cur["attachments"].extend(_ATTACH.findall(line))

    ts_list = [m["ts"] for m in messages if m["ts"]]
    return {
        "conversation": os.path.basename(os.path.dirname(path)).replace("WhatsApp Chat - ", ""),
        "source_file": path,
        "message_count": len(messages),
        "senders": sorted(senders),
        "date_first": min(ts_list) if ts_list else None,
        "date_last": max(ts_list) if ts_list else None,
        "attachment_count": sum(len(m["attachments"]) for m in messages),
        "messages": messages,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    chats = []
    for root in args.roots:
        root = os.path.expanduser(root)
        for dp, _, fns in os.walk(root):
            if "_chat.txt" in fns:
                chats.append(os.path.join(dp, "_chat.txt"))

    stats = {"conversations": 0, "messages": 0, "attachments": 0, "parse_errors": 0, "unparsed_ts": 0}
    for i, path in enumerate(chats):
        try:
            parsed = parse_chat(path)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: parse failed {path}: {exc}", file=sys.stderr)
            stats["parse_errors"] += 1
            continue
        out = os.path.join(args.out_dir, f"conv_{i:03d}.json")
        with open(out, "w", encoding="utf-8") as ofh:
            json.dump(parsed, ofh, ensure_ascii=False, indent=1)
        stats["conversations"] += 1
        stats["messages"] += parsed["message_count"]
        stats["attachments"] += parsed["attachment_count"]
        stats["unparsed_ts"] += sum(1 for m in parsed["messages"] if not m["ts"])

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
