"""Score and diff two A/B dossier batches by model.

Reads:
- timing JSON: ~/Desktop/nuzantara/research/crm/<date>-timing-<model>.json
- dossier txt: ~/Desktop/nuzantara/research/crm/<date>-wa-dossier-<model>-batch-*.txt

Emits markdown scorecard comparing two models on:
- latency per client + total
- JSON validity (all clients vs failures)
- attribution preservation: count "@balizero.com" mentions per dossier
- semantic richness: count Hard/Soft/Human facts extracted
- numeric integrity: regex `\\d{4}-\\d{2}-\\d{2}` valid ISO dates, no "2im..." glitches
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RESEARCH_DIR = Path.home() / "Desktop" / "nuzantara" / "research" / "crm"

EMAIL_RE = re.compile(r"@balizero\.com")
ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
BAD_DATE_RE = re.compile(r"\b\d?[a-z]+\d+-\d{2}-\d{2}\b|\b\d{4}-\d?[a-z]+-\d{2}\b")


def slug(model: str) -> str:
    return model.replace(":", "_")


def load_timing(model: str, date: str) -> dict[str, Any] | None:
    path = RESEARCH_DIR / f"{date}-timing-{slug(model)}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_dossier_text(model: str, date: str) -> str:
    files = sorted(RESEARCH_DIR.glob(f"{date}-wa-dossier-{slug(model)}-batch-*.txt"))
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def section_counts(text: str) -> dict[str, int]:
    """Count semantic richness markers in dossier text."""
    return {
        "clients": text.count("## Client:"),
        "decisions": text.count("#### Decisions"),
        "documents": text.count("#### Documents delivered"),
        "deadlines": text.count("#### Declared deadlines"),
        "quotes": text.count("#### Quotes approved"),
        "business_goals": text.count("#### Client business goals"),
        "warnings": text.count("#### Warnings"),
        "promises": text.count("#### Promises"),
        "frustration": text.count("#### Frustration episodes"),
        "handoffs": text.count("#### Operator handoffs"),
        "team_attributions": len(EMAIL_RE.findall(text)),
        "iso_dates": len(ISO_DATE_RE.findall(text)),
        "bad_dates": len(BAD_DATE_RE.findall(text)),
        "none_extracted": text.count("(none extracted)"),
        "total_words": len(text.split()),
    }


def sentiment_distribution(text: str) -> Counter[str]:
    """Count sentiment_trend values."""
    sentiments = re.findall(r"\*\*Sentiment trend\*\*:\s*(\w+)", text)
    return Counter(sentiments)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="Date prefix YYYY-MM-DD")
    p.add_argument("--model-a", required=True, help="Baseline model, e.g. qwen3.5:9b")
    p.add_argument("--model-b", required=True, help="Candidate model, e.g. qwen3.6:27b")
    p.add_argument("--out", type=str, default=None, help="Output markdown path")
    args = p.parse_args()

    ta = load_timing(args.model_a, args.date)
    tb = load_timing(args.model_b, args.date)
    da = load_dossier_text(args.model_a, args.date)
    db = load_dossier_text(args.model_b, args.date)

    if ta is None or not da:
        print(f"Missing data for model A ({args.model_a})", file=sys.stderr)
        return 1
    if tb is None or not db:
        print(f"Missing data for model B ({args.model_b})", file=sys.stderr)
        return 1

    elapsed_a = [r["elapsed_s"] for r in ta["results"] if r["ok"]]
    elapsed_b = [r["elapsed_s"] for r in tb["results"] if r["ok"]]
    ok_a = sum(1 for r in ta["results"] if r["ok"])
    ok_b = sum(1 for r in tb["results"] if r["ok"])
    total_a = len(ta["results"])
    total_b = len(tb["results"])

    sa = section_counts(da)
    sb = section_counts(db)
    senta = sentiment_distribution(da)
    sentb = sentiment_distribution(db)

    md: list[str] = []
    md.append(f"# A/B Scorecard — {args.model_a} vs {args.model_b}")
    md.append(f"Date: {args.date}\n")
    md.append("## Latency\n")
    md.append(f"| Metric | A: {args.model_a} | B: {args.model_b} |")
    md.append("|---|---|---|")
    md.append(f"| Clients OK | {ok_a}/{total_a} | {ok_b}/{total_b} |")
    if elapsed_a and elapsed_b:
        md.append(f"| Mean elapsed (s) | {sum(elapsed_a)/len(elapsed_a):.1f} | {sum(elapsed_b)/len(elapsed_b):.1f} |")
        md.append(f"| Total wall (s) | {sum(elapsed_a):.1f} | {sum(elapsed_b):.1f} |")
        md.append(f"| Min/Max (s) | {min(elapsed_a):.1f}/{max(elapsed_a):.1f} | {min(elapsed_b):.1f}/{max(elapsed_b):.1f} |")

    md.append("\n## Semantic richness (counts across all clients)\n")
    md.append("| Marker | A | B | Δ B−A |")
    md.append("|---|---|---|---|")
    richness_keys = [
        "clients", "decisions", "documents", "deadlines", "quotes",
        "business_goals", "warnings", "promises", "frustration", "handoffs",
    ]
    for k in richness_keys:
        md.append(f"| {k} | {sa[k]} | {sb[k]} | {sb[k]-sa[k]:+d} |")

    md.append("\n## Attribution & integrity\n")
    md.append("| Metric | A | B | Notes |")
    md.append("|---|---|---|---|")
    md.append(f"| @balizero.com mentions | {sa['team_attributions']} | {sb['team_attributions']} | Higher = better attribution |")
    md.append(f"| ISO dates extracted | {sa['iso_dates']} | {sb['iso_dates']} | Higher = more temporal facts |")
    md.append(f"| Malformed dates | {sa['bad_dates']} | {sb['bad_dates']} | Lower = better (0 ideal) |")
    md.append(f"| '(none extracted)' empty sections | {sa['none_extracted']} | {sb['none_extracted']} | Lower = denser extraction |")
    md.append(f"| Total words in dossiers | {sa['total_words']} | {sb['total_words']} | Higher = more detail |")

    md.append("\n## Sentiment distribution\n")
    md.append("| Sentiment | A | B |")
    md.append("|---|---|---|")
    all_sentiments = sorted(set(senta) | set(sentb))
    for s in all_sentiments:
        md.append(f"| {s} | {senta.get(s, 0)} | {sentb.get(s, 0)} |")

    md.append("\n## Verdict heuristic\n")
    score_a = sa["team_attributions"] * 2 - sa["bad_dates"] * 5 - sa["none_extracted"]
    score_b = sb["team_attributions"] * 2 - sb["bad_dates"] * 5 - sb["none_extracted"]
    md.append(f"- Score A: {score_a}")
    md.append(f"- Score B: {score_b}")
    if score_b > score_a:
        md.append(f"- **Candidate B ({args.model_b}) wins by {score_b-score_a} pts**")
    elif score_a > score_b:
        md.append(f"- **Baseline A ({args.model_a}) wins by {score_a-score_b} pts** — keep current default")
    else:
        md.append("- **Tie** — fall back to latency tiebreaker")

    output = "\n".join(md) + "\n"
    out_path = Path(args.out) if args.out else (RESEARCH_DIR / f"{args.date}-scorecard-{slug(args.model_a)}-vs-{slug(args.model_b)}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(output)
    print(f"\nWritten to: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
