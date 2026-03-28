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

TEMPLATE_SLOTS: element IDs design DAHE6lx1lf8 (CLAUDE IN CANVA)
  1 slide per pagina, 11 pagine totali
  Element IDs recuperati via start-editing-transaction il 2026-03-26

Numero slide: range decisionale 6-11
  - Director può generare qualsiasi numero nel range
  - Slide in eccesso rispetto agli slot → troncate (con warning)
  - Slot in eccesso rispetto alle slide → lasciati intatti
"""

import json
import sys
import os
import argparse
import time
from pathlib import Path
from typing import Optional


# ── Canva Design ──────────────────────────────────────────────────────────────
DEFAULT_DESIGN_ID = "DAHE6lx1lf8"

# ── Template element IDs (CLAUDE IN CANVA — design DAHE6lx1lf8) ───────────────
# Struttura: 1 slide per pagina, ogni pagina ha heading + body distinti
# Recuperati via start-editing-transaction il 2026-03-26
# (page_index, heading_element_id, body_element_id)
TEMPLATE_SLOTS = [
    (1,  "PB6Rxs8n5DZkNS9Z-LB7Ms2Np5mWMHmSS", "PB6Rxs8n5DZkNS9Z-LBKpxy8Y8VM8g5sm"),  # cover
    (2,  "PBRnkF5C2FHvWPPp-LBwYVgC9yVwkqB5w",  "PBRnkF5C2FHvWPPp-LBSxs84s03skX2bJ"),   # slide 2
    (3,  "PBswT8p6LMg6vyX4-LBZ0XDG56kG2Vclt",  "PBswT8p6LMg6vyX4-LBR7pfgBKZYHQxLJ"),   # slide 3
    (4,  "PB9rgJ5tQj1yNJrD-LBtDrMM3Bp4nJ4v9",  "PB9rgJ5tQj1yNJrD-LBGHjSsS3lj7VY3Z"),   # slide 4
    (5,  "PBZjXPTPh9tnvx82-LBSZHpqHtJfq43QC",  "PBZjXPTPh9tnvx82-LB9q34XMJhYmJcVV"),   # slide 5
    (6,  "PBgr2GbZD3DJkPP0-LB0cZMDY3BRdprNk",  "PBgr2GbZD3DJkPP0-LB1kPFcPYqsqQYfQ"),   # slide 6
    (7,  "PBk1XphW0PnpKMh2-LBbh37qB3S4DrdrD",  "PBk1XphW0PnpKMh2-LB2XL6f0tjmwhgk8"),   # slide 7
    (8,  "PBNffcgkNpZKTtmM-LBFg8s6hy6DF3HvB",  "PBNffcgkNpZKTtmM-LBY2F75l9NJp4bpf"),   # slide 8
    (9,  "PBqdbS4QcwHgGN0F-LBFxtRbKJBx5qKch",  None),                                    # slide 9 (heading only)
    (10, "PBz4hjP71RbnjKhb-LBbCpkK9wH5C1KQX",  "PBz4hjP71RbnjKhb-LBTVJsF8WVLZBx8L"),   # slide 10
    (11, "PBxns7m6jJJm3BKT-LBtXZ6mvNj5TH3n0",  None),                                    # slide 11 (heading only)
]

# ── Image element IDs per le slide che hanno immagini (slot Canva) ───────────
# Recuperare tramite start-editing-transaction se non noti — per ora marcati come None
# Format: slide_index (0-based) → image_element_id
IMAGE_ELEMENT_IDS: dict = {
    0: None,  # cover (slide 1) — image element ID da recuperare da Canva
    3: None,  # slide 4 — image element ID da recuperare
    8: None,  # slide 9 — image element ID da recuperare
}

MIN_SLIDES = 6
MAX_SLIDES = 11


# ── Slide → operations list ───────────────────────────────────────────────────

def slides_to_operations(slides: list, page: int = 1) -> list:
    """
    Converte slide JSON in lista di operazioni replace_text per Canva.

    Design DAHE6lx1lf8: 1 slide per pagina (11 pagine totali).
    - Ogni slot in TEMPLATE_SLOTS corrisponde a una pagina specifica
    - page_index viene preso dallo slot, non dal parametro `page` (ignorato)
    - Slide in eccesso (>MAX_SLIDES): troncate con warning
    - Slot in eccesso rispetto alle slide: saltati (non si toccano)
    - image_prompt: annotazione testuale nel body, non generazione immagini
    """
    if len(slides) > MAX_SLIDES:
        print(f"  ⚠️  {len(slides)} slide > MAX {MAX_SLIDES} — troncate",
              file=sys.stderr)
        slides = slides[:MAX_SLIDES]

    if len(slides) < MIN_SLIDES:
        print(f"  ⚠️  Solo {len(slides)} slide (min consigliato: {MIN_SLIDES})",
              file=sys.stderr)

    ops = []

    for i, slide in enumerate(slides):
        if i >= len(TEMPLATE_SLOTS):
            break

        page_index, heading_id, body_id = TEMPLATE_SLOTS[i]
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

        ops.append({
            "type": "replace_text",
            "element_id": heading_id,
            "text": heading_text,
            "page_index": page_index,
        })

        # Body: solo se l'elemento esiste per questa pagina
        if body_id is None:
            continue

        body_parts = []
        if is_cover and subhead:
            body_parts.append(subhead)
        elif body:
            body_parts.append(body)

        # Annotazione image prompt (solo testo per designer)
        if image_prompt:
            note = f"\n(IMAGE PROMPT: {image_prompt}"
            if image_placement:
                note += f" — PLACEMENT: {image_placement}"
            note += ")"
            body_parts.append(note)

        body_text = "\n".join(body_parts) if body_parts else ""
        if body_text:
            ops.append({
                "type": "replace_text",
                "element_id": body_id,
                "text": body_text,
                "page_index": page_index,
            })

    # ── Aggiungi operazioni upload_image per slide con immagini generate ──
    for i, slide in enumerate(slides):
        if i >= len(TEMPLATE_SLOTS):
            break
        img_path = slide.get("generated_image_path", "")
        if not img_path:
            continue
        img_elem_id = IMAGE_ELEMENT_IDS.get(i)
        page_index = TEMPLATE_SLOTS[i][0]
        if img_elem_id:
            # Element ID noto → operazione upload_image diretta
            ops.append({
                "type": "upload_image",
                "element_id": img_elem_id,
                "file_path": img_path,
                "page_index": page_index,
            })
        else:
            # Element ID non noto → annotazione per applicazione manuale
            ops.append({
                "type": "pending_image",
                "file_path": img_path,
                "page_index": page_index,
                "note": f"Image generated: {img_path} — aggiungere manualmente alla slide {page_index}",
            })

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
    ap.add_argument("--page",      type=int, default=0, help="Pagina iniziale (default: 0)")
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

    # ── Build operations ──
    operations = slides_to_operations(slides)

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
