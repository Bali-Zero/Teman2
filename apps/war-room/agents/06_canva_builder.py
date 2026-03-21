#!/usr/bin/env python3
"""
FASE 4 — Canva Carousel Builder
================================
Prepara le operazioni Canva e le scrive in canva_pending.json.

Il MCP Canva è accessibile SOLO dalla sessione interattiva Claude Code
(OAuth bound al browser). Non è raggiungibile da subprocess/claude -p.

Soluzione: questo script scrive canva_pending.json con tutte le operazioni
pronte. La sessione Claude Code legge il file e applica su Canva via MCP.

Workflow:
  1. Legge claude_slides.json
  2. Converte slide → lista operazioni replace_text
  3. Scrive output/canva/canva_pending.json  ← il file che Claude Code legge
  4. Scrive output/master/canva_pending.json (copia master)
  5. Notifica via Telegram (se disponibile)

TEMPLATE_SLOTS: element IDs pagina 1 del design DAHEME4mocU
  upper row (y < 400): slots 0-5 → cover + 5 pannelli
  lower row (y > 500): slots 0-3 → 4 pannelli seconda riga
  Totale: 10 slot disponibili per 6-10 slide

Numero slide: range decisionale 6-10
  - Director può generare qualsiasi numero nel range
  - Slot in eccesso → FINISH marker (slot vuoto pulito)
  - Slide in eccesso rispetto agli slot → troncate (con warning)
"""

import json
import sys
import os
import argparse
import time
from pathlib import Path
from typing import Optional


# ── Canva Design ──────────────────────────────────────────────────────────────
DEFAULT_DESIGN_ID = "DAHEME4mocU"

# ── Template element IDs (War_Room design, identici su tutte le pagine) ───────
# Struttura: (heading_element_id, body_element_id)
# upper row = riga superiore (y < 400px): cover + 5 pannelli
# lower row = riga inferiore (y > 500px): 4 pannelli
TEMPLATE_SLOTS = {
    "upper": [
        ("PBsLhMw2tzZTd6V7-LBNh3LV9Wpg3J3yh", "PBsLhMw2tzZTd6V7-LBnxWRM9N3TnpjhD"),  # cover/slide 1
        ("PBsLhMw2tzZTd6V7-LBHHjHgS87kxWQtR", "PBsLhMw2tzZTd6V7-LBdyFlLnfRvGlLFY"),  # slide 2
        ("PBsLhMw2tzZTd6V7-LB41FkdMcJjvFVy6", "PBsLhMw2tzZTd6V7-LBBGg07F7zXrT7wv"),  # slide 3
        ("PBsLhMw2tzZTd6V7-LBZjVnkTKs8G3DmH", "PBsLhMw2tzZTd6V7-LBNqRfkszx0hmt6K"),  # slide 4
        ("PBsLhMw2tzZTd6V7-LBYYRwyhQKY0Rgsp", "PBsLhMw2tzZTd6V7-LBvdBlbBdzkDQfJQ"),  # slide 5
        ("PBsLhMw2tzZTd6V7-LBPMtk8fRcwYm3jF", "PBsLhMw2tzZTd6V7-LB7TgRGdpRKVsRLY"),  # slide 6
    ],
    "lower": [
        ("PBsLhMw2tzZTd6V7-LBpj4gW2zMQ6phJM", "PBsLhMw2tzZTd6V7-LBFGYmXTfF9n1Jkn"),  # slide 7
        ("PBsLhMw2tzZTd6V7-LBtqPts7PGJ2kRqT", "PBsLhMw2tzZTd6V7-LBvDCd7CP36nK9dG"),  # slide 8
        ("PBsLhMw2tzZTd6V7-LBlYBx8wF8NrVWNF", "PBsLhMw2tzZTd6V7-LB1JKgk4QfKBpwVX"),  # slide 9
        ("PBsLhMw2tzZTd6V7-LBkddNpJPn8G8jzd", "PBsLhMw2tzZTd6V7-LBmS0210M4PRnHdQ"),  # slide 10
    ],
    "all": [],  # populated below
}
TEMPLATE_SLOTS["all"] = TEMPLATE_SLOTS["upper"] + TEMPLATE_SLOTS["lower"]

FINISH_MARKER = "FINISH"
MIN_SLIDES = 6
MAX_SLIDES = 10


# ── Slide → operations list ───────────────────────────────────────────────────

def slides_to_operations(slides: list, page: int = 1) -> list:
    """
    Converte slide JSON in lista di operazioni replace_text per Canva.

    Range decisionale: 6-10 slide.
    - Slide in eccesso (>10): troncate con warning
    - Slot in eccesso (slide < slot): FINISH_MARKER (slot vuoto)
    - image_prompt: annotazione testuale nel body, non generazione immagini
    """
    slots = TEMPLATE_SLOTS["all"]
    n_slots = len(slots)  # 10

    if len(slides) > MAX_SLIDES:
        print(f"  ⚠️  {len(slides)} slide > MAX {MAX_SLIDES} — troncate",
              file=sys.stderr)
        slides = slides[:MAX_SLIDES]

    if len(slides) < MIN_SLIDES:
        print(f"  ⚠️  Solo {len(slides)} slide (min consigliato: {MIN_SLIDES})",
              file=sys.stderr)

    ops = []

    for i, slide in enumerate(slides):
        if i >= n_slots:
            break

        heading_id, body_id = slots[i]
        headline = slide.get("headline", "").upper()
        subhead  = (slide.get("subhead") or "").strip()
        body     = (slide.get("body") or "").strip()
        image_prompt    = slide.get("image_prompt") or ""
        image_placement = slide.get("image_placement") or ""
        is_cover = slide.get("is_cover", i == 0)

        # Heading: solo headline (cover) o headline + subhead uppercase
        heading_text = headline
        if subhead and not is_cover:
            heading_text = f"{headline}\n{subhead.upper()}"

        # Body: testo principale
        body_parts = []
        if is_cover and subhead:
            # Cover: subhead come body (es. "It's in the hands of an algorithm.")
            body_parts.append(subhead)
        elif body:
            body_parts.append(body)

        # Annotazione image prompt (non generazione — solo testo per designer)
        if image_prompt:
            note = f"\n(IMAGE PROMPT: {image_prompt}"
            if image_placement:
                note += f" — PLACEMENT: {image_placement}"
            note += ")"
            body_parts.append(note)

        body_text = "\n".join(body_parts) if body_parts else FINISH_MARKER

        ops.append({
            "type": "replace_text",
            "element_id": heading_id,
            "text": heading_text,
            "page_index": page,
        })
        ops.append({
            "type": "replace_text",
            "element_id": body_id,
            "text": body_text,
            "page_index": page,
        })

    # Slot rimanenti → FINISH marker (slot puliti)
    for j in range(len(slides), n_slots):
        heading_id, body_id = slots[j]
        ops.append({"type": "replace_text", "element_id": heading_id,
                    "text": FINISH_MARKER, "page_index": page})
        ops.append({"type": "replace_text", "element_id": body_id,
                    "text": FINISH_MARKER, "page_index": page})

    return ops


def notify_telegram(token: str, chat_id: str, message: str) -> bool:
    """Invia notifica Telegram. Non bloccante."""
    import urllib.request
    import urllib.parse
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode()
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️  Telegram notify failed: {e}", file=sys.stderr)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="War Room — Canva Pending Writer")
    ap.add_argument("--slides",    required=True,  help="Path a claude_slides.json")
    ap.add_argument("--output",    required=True,  help="Output dir (es. output/canva/)")
    ap.add_argument("--master",    required=True,  help="Master dir (es. output/master/)")
    ap.add_argument("--design-id", default=DEFAULT_DESIGN_ID)
    ap.add_argument("--row",       default="all",
                    choices=["upper", "lower", "all"],
                    help="Slot da usare (default: all = tutte e 10)")
    ap.add_argument("--page",      type=int, default=1,
                    help="page_index Canva (default: 1)")
    ap.add_argument("--dry-run",   action="store_true",
                    help="Mostra operazioni senza scrivere file")
    args = ap.parse_args()

    # ── Validate inputs ──
    slides_path = Path(args.slides)
    if not slides_path.exists():
        print(f"❌ Slides file not found: {slides_path}", file=sys.stderr)
        sys.exit(1)

    data   = json.loads(slides_path.read_text())
    slides = data.get("slides", data if isinstance(data, list) else [])
    topic  = data.get("topic", "Unknown")

    if not slides:
        print("❌ No slides found in input JSON", file=sys.stderr)
        sys.exit(1)

    out_dir    = Path(args.output)
    master_dir = Path(args.master)
    out_dir.mkdir(parents=True, exist_ok=True)
    master_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🎨 Canva Pending Writer", file=sys.stderr)
    print(f"   Design:  {args.design_id}", file=sys.stderr)
    print(f"   Topic:   {topic}", file=sys.stderr)
    print(f"   Slides:  {len(slides)} (range: {MIN_SLIDES}-{MAX_SLIDES})", file=sys.stderr)
    print(f"   Row:     {args.row}  Page: {args.page}", file=sys.stderr)

    # ── Build operations ──
    # Override slots if specific row requested
    if args.row != "all":
        # Monkey-patch per compatibilità
        original_all = TEMPLATE_SLOTS["all"]
        TEMPLATE_SLOTS["all"] = TEMPLATE_SLOTS[args.row]

    operations = slides_to_operations(slides, page=args.page)

    if args.row != "all":
        TEMPLATE_SLOTS["all"] = original_all

    print(f"   Ops:     {len(operations)} replace_text", file=sys.stderr)

    # ── Dry run ──
    if args.dry_run:
        print("\n[DRY RUN] Operations preview:", file=sys.stderr)
        for op in operations:
            txt = op["text"][:70].replace("\n", "↵")
            print(f"  [{op['page_index']}] {op['element_id'][-12:]} → '{txt}'",
                  file=sys.stderr)
        dry = {
            "design_id": args.design_id,
            "topic": topic,
            "row": args.row,
            "page": args.page,
            "operations_count": len(operations),
            "dry_run": True,
            "slides": slides,
        }
        (out_dir / "canva_dryrun.json").write_text(
            json.dumps(dry, ensure_ascii=False, indent=2))
        print(f"\n✅ Dry-run → {out_dir}/canva_dryrun.json", file=sys.stderr)
        return

    # ── Write canva_pending.json ──
    pending = {
        "design_id":         args.design_id,
        "design_url":        f"https://www.canva.com/design/{args.design_id}/edit",
        "topic":             topic,
        "tone":              data.get("tone", ""),
        "page_index":        args.page,
        "slides_count":      len(slides),
        "operations_count":  len(operations),
        "operations":        operations,
        "instagram_caption": data.get("instagram_caption", ""),
        "slides":            slides,
        "created_at":        time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status":            "pending",  # → "applied" dopo MCP commit
    }

    pending_file = out_dir / "canva_pending.json"
    pending_file.write_text(json.dumps(pending, ensure_ascii=False, indent=2))
    (master_dir / "canva_pending.json").write_text(
        json.dumps(pending, ensure_ascii=False, indent=2))

    print(f"\n✅ canva_pending.json scritto → {pending_file}", file=sys.stderr)
    print(f"   {len(operations)} operazioni pronte per Claude Code → MCP Canva",
          file=sys.stderr)
    print(f"   Design: {pending['design_url']}", file=sys.stderr)

    # Instagram caption
    if cap := data.get("instagram_caption"):
        (master_dir / "instagram_caption.txt").write_text(cap)
        print(f"   📸 Instagram caption salvata", file=sys.stderr)

    # Image prompts (solo annotazioni testuali)
    image_prompts = [
        {
            "slide":           s.get("slide_number"),
            "is_cover":        s.get("is_cover", False),
            "headline":        s.get("headline", ""),
            "image_prompt":    s.get("image_prompt", ""),
            "image_placement": s.get("image_placement", ""),
        }
        for s in slides if s.get("image_prompt")
    ]
    if image_prompts:
        ip_file = out_dir / "image_prompts.json"
        ip_file.write_text(json.dumps(image_prompts, ensure_ascii=False, indent=2))
        print(f"   🖼️  {len(image_prompts)} image prompts → {ip_file}", file=sys.stderr)

    # ── Notifica Telegram ──
    tg_token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id = os.environ.get("TELEGRAM_GROUP_ID", "")
    if tg_token and tg_chat_id:
        msg = (
            f"🎨 <b>War Room — Canva pronto</b>\n"
            f"Topic: <i>{topic}</i>\n"
            f"{len(slides)} slide → {len(operations)} operazioni\n\n"
            f"Apri Claude Code e scrivi:\n"
            f"<code>applica canva_pending</code>"
        )
        if notify_telegram(tg_token, tg_chat_id, msg):
            print(f"   📱 Telegram notifica inviata", file=sys.stderr)


if __name__ == "__main__":
    main()
