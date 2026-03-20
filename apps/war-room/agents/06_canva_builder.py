#!/usr/bin/env python3
"""
FASE 4 — Canva Builder (replaces 06_keynote_builder.py)
========================================================
Crea/aggiorna un carosello Instagram su Canva usando le MCP Canva tools
via chiamata HTTP al gateway MCP locale (OpenClaw loopback:18789).

Workflow:
  1. Legge claude_slides.json (output di 04_claude_director.py)
  2. Apre una editing transaction sul design War_Room (DAHEME4mocU)
  3. Sceglie la prossima pagina vuota disponibile (pagine 2 o 3)
  4. Rimpiazza tutti gli elementi testo con il contenuto del carosello
  5. Commit + scrive output/canva/carousel_N.json con metadati

Note architetturali:
  - Il design War_Room ha 3 pagine: 1 = carosello esistente, 2-3 = vuote
  - Ogni pagina ha 2 righe di slide (upper y<400, lower y>500) = 2 caroselli per pagina
  - Upper row: elementi con prefix PBsLhMw2tzZTd6V7-LB (IDs mappati in TEMPLATE_MAP)
  - Il testo è un MOCKUP — lunghezza libera, nessun limite imposto
  - Le image_prompt vengono preservate nel JSON output per uso esterno (ComfyUI/Pollinations)
  - Il builder scrive anche FINISH_SLIDE con "FINISH FINISH FINISH..." quando esaurisci le slide

Dipendenze:
  - MCP Canva deve essere configurato e autenticato
  - CANVA_DESIGN_ID in .env o argomento --design-id
  - Richiede Python 3.11+ e httpx
"""

import json
import sys
import argparse
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ── Canva Design IDs ──────────────────────────────────────────────────────────
DEFAULT_DESIGN_ID = "DAHEME4mocU"   # War_Room template

# ── Template element map (War_Room page 1 upper row) ─────────────────────────
# Struttura: ogni "slot" = una slide del carosello Instagram
# upper_row: y < 400px (slide 0-4 = cover + 4 pannelli)
# lower_row: y > 500px (slide 5-9 = secondo carosello sulla stessa pagina Canva)
TEMPLATE_SLOTS = {
    "upper": [
        # (heading_element_id, body_element_id)
        # Slot 0 = Cover
        ("PBsLhMw2tzZTd6V7-LBNh3LV9Wpg3J3yh",  "PBsLhMw2tzZTd6V7-LBnxWRM9N3TnpjhD"),
        # Slot 1 = Panel 1
        ("PBsLhMw2tzZTd6V7-LBHHjHgS87kxWQtR",  "PBsLhMw2tzZTd6V7-LBdyFlLnfRvGlLFY"),
        # Slot 2 = Panel 2
        ("PBsLhMw2tzZTd6V7-LB41FkdMcJjvFVy6",  "PBsLhMw2tzZTd6V7-LBBGg07F7zXrT7wv"),
        # Slot 3 = Panel 3
        ("PBsLhMw2tzZTd6V7-LBZjVnkTKs8G3DmH",  "PBsLhMw2tzZTd6V7-LBNqRfkszx0hmt6K"),
        # Slot 4 = Panel 4
        ("PBsLhMw2tzZTd6V7-LBYYRwyhQKY0Rgsp",  "PBsLhMw2tzZTd6V7-LBvdBlbBdzkDQfJQ"),
        # Slot 5 = Panel 5 / CTA
        ("PBsLhMw2tzZTd6V7-LBPMtk8fRcwYm3jF",  "PBsLhMw2tzZTd6V7-LB7TgRGdpRKVsRLY"),
    ],
    "lower": [
        ("PBsLhMw2tzZTd6V7-LBpj4gW2zMQ6phJM",  "PBsLhMw2tzZTd6V7-LBFGYmXTfF9n1Jkn"),
        ("PBsLhMw2tzZTd6V7-LBtqPts7PGJ2kRqT",  "PBsLhMw2tzZTd6V7-LBvDCd7CP36nK9dG"),
        ("PBsLhMw2tzZTd6V7-LBlYBx8wF8NrVWNF",  "PBsLhMw2tzZTd6V7-LB1JKgk4QfKBpwVX"),
        ("PBsLhMw2tzZTd6V7-LBkddNpJPn8G8jzd",  "PBsLhMw2tzZTd6V7-LBmS0210M4PRnHdQ"),
    ],
}

FINISH_MARKER = "FINISH FINISH FINISH FINISH FINISH FINISH FINISH FINISH FINISH FINISH"


# ── MCP Gateway HTTP helper ───────────────────────────────────────────────────
MCP_GATEWAY = "http://localhost:18789"


def mcp_call(tool: str, args: dict, timeout: int = 60) -> dict:
    """
    Chiama un tool MCP via HTTP gateway OpenClaw.
    Endpoint: POST /mcp/call  body: {"tool": "...", "args": {...}}
    """
    payload = json.dumps({"tool": tool, "args": args}).encode()
    req = urllib.request.Request(
        f"{MCP_GATEWAY}/mcp/call",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MCP HTTP {e.code}: {body[:300]}")
    except Exception as e:
        raise RuntimeError(f"MCP call failed ({tool}): {e}")


def start_transaction(design_id: str) -> str:
    """Apre editing transaction, ritorna transaction_id."""
    print(f"  🔓 Opening Canva transaction on {design_id}...", file=sys.stderr)
    result = mcp_call("mcp__claude_ai_Canva__start-editing-transaction",
                      {"design_id": design_id, "user_intent": "War Room carousel generation"})
    tx_id = result.get("transaction_id") or result.get("result", {}).get("transaction_id")
    if not tx_id:
        raise RuntimeError(f"No transaction_id in response: {str(result)[:200]}")
    print(f"  ✅ Transaction: {tx_id}", file=sys.stderr)
    return tx_id


def perform_operations(tx_id: str, operations: list, page_index: int,
                       user_intent: str = "Replace carousel text") -> dict:
    """Esegue batch di operazioni edit su Canva."""
    return mcp_call("mcp__claude_ai_Canva__perform-editing-operations", {
        "transaction_id": tx_id,
        "operations": operations,
        "page_index": page_index,
        "user_intent": user_intent,
    }, timeout=120)


def commit_transaction(tx_id: str) -> bool:
    """Committa le modifiche."""
    print(f"  💾 Committing transaction {tx_id}...", file=sys.stderr)
    result = mcp_call("mcp__claude_ai_Canva__commit-editing-transaction", {
        "transaction_id": tx_id,
        "user_intent": "Commit War Room carousel",
    }, timeout=60)
    status = result.get("transaction", {}).get("status", "unknown")
    ok = status == "committed"
    print(f"  {'✅' if ok else '❌'} Status: {status}", file=sys.stderr)
    return ok


def cancel_transaction(tx_id: str) -> None:
    """Cancella transaction in caso di errore."""
    try:
        mcp_call("mcp__claude_ai_Canva__cancel-editing-transaction", {
            "transaction_id": tx_id,
            "user_intent": "Cancel on error",
        }, timeout=30)
        print(f"  ↩️  Transaction {tx_id} cancelled", file=sys.stderr)
    except Exception:
        pass


# ── Slide → Canva operations ──────────────────────────────────────────────────

def slides_to_operations(slides: list, slots: list) -> list:
    """
    Converte lista di slide JSON in operazioni Canva replace_text.

    Schema slide (da claude_director):
      slide_number, is_cover, headline, subhead, body,
      image_prompt, layout, notes, image_placement (opzionale)

    Ogni slot ha (heading_id, body_id).
    - heading riceve: HEADLINE (+ eventuale SUBHEAD su riga separata)
    - body riceve: body text + image prompts annotati tra parentesi
    - Se la slide è cover: heading = titolo grande, body = hook/subhead

    Se slides > slots disponibili: slot finale riceve marker FINISH.
    """
    operations = []
    n_slots = len(slots)

    for i, slide in enumerate(slides):
        if i >= n_slots:
            # Overflow: riempi slot rimanenti con FINISH marker
            for j in range(i, n_slots):
                heading_id, body_id = slots[j]
                operations.append({"type": "replace_text", "element_id": heading_id,
                                    "text": FINISH_MARKER})
                operations.append({"type": "replace_text", "element_id": body_id,
                                    "text": FINISH_MARKER})
            break

        heading_id, body_id = slots[i]
        headline = slide.get("headline", "").upper()
        subhead  = slide.get("subhead") or ""
        body     = slide.get("body") or ""
        image_prompt = slide.get("image_prompt", "")
        image_placement = slide.get("image_placement", "")
        is_cover = slide.get("is_cover", i == 0)

        # ── Build heading text ──
        if subhead and not is_cover:
            heading_text = f"{headline}\n{subhead.upper()}"
        else:
            heading_text = headline

        # ── Build body text (mockup free + image prompt annotato) ──
        body_parts = []
        if body:
            body_parts.append(body)
        if image_prompt:
            annotation = f"\n\n(IMAGE PROMPT: {image_prompt}"
            if image_placement:
                annotation += f" — PLACEMENT: {image_placement}"
            annotation += ")"
            body_parts.append(annotation)

        body_text = "\n".join(body_parts) if body_parts else FINISH_MARKER

        # Cover: heading = titolo, body = subhead/hook
        if is_cover and subhead:
            body_text_final = subhead
            if image_prompt:
                body_text_final += f"\n\n(COVER IMAGE PROMPT: {image_prompt}"
                if image_placement:
                    body_text_final += f" — {image_placement}"
                body_text_final += ")"
        else:
            body_text_final = body_text

        operations.append({"type": "replace_text", "element_id": heading_id,
                            "text": heading_text})
        operations.append({"type": "replace_text", "element_id": body_id,
                            "text": body_text_final})

    # Se ci sono più slot che slide, riempi i rimanenti con FINISH
    for j in range(len(slides), n_slots):
        heading_id, body_id = slots[j]
        operations.append({"type": "replace_text", "element_id": heading_id,
                            "text": FINISH_MARKER})
        operations.append({"type": "replace_text", "element_id": body_id,
                            "text": FINISH_MARKER})

    return operations


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="War Room — Canva Carousel Builder")
    ap.add_argument("--slides",    required=True,  help="Path a claude_slides.json")
    ap.add_argument("--output",    required=True,  help="Dir output (es. output/canva/)")
    ap.add_argument("--master",    required=True,  help="Dir master (es. output/master/)")
    ap.add_argument("--design-id", default=DEFAULT_DESIGN_ID,
                    help=f"Canva design ID (default: {DEFAULT_DESIGN_ID})")
    ap.add_argument("--row",       default="upper", choices=["upper", "lower"],
                    help="Riga template da popolare (upper=y<400, lower=y>500)")
    ap.add_argument("--page",      type=int, default=1,
                    help="Numero pagina Canva (1=page1 upper, default=1)")
    ap.add_argument("--dry-run",   action="store_true",
                    help="Mostra operazioni senza chiamare Canva")
    args = ap.parse_args()

    # ── Load slides ──
    slides_path = Path(args.slides)
    if not slides_path.exists():
        print(f"❌ Slides file not found: {slides_path}", file=sys.stderr)
        sys.exit(1)

    data   = json.loads(slides_path.read_text())
    slides = data.get("slides", data if isinstance(data, list) else [])

    print(f"\n🎨 Canva Carousel Builder", file=sys.stderr)
    print(f"   Design: {args.design_id}", file=sys.stderr)
    print(f"   Slides: {len(slides)}", file=sys.stderr)
    print(f"   Row: {args.row}  Page: {args.page}", file=sys.stderr)
    print(f"   Topic: {data.get('topic', 'N/A')}", file=sys.stderr)

    # ── Choose slot map ──
    slots = TEMPLATE_SLOTS[args.row]
    print(f"   Slots available: {len(slots)}", file=sys.stderr)

    # ── Build operations ──
    operations = slides_to_operations(slides, slots)
    print(f"   Operations: {len(operations)}", file=sys.stderr)

    if args.dry_run:
        print("\n[DRY RUN] Operations preview:", file=sys.stderr)
        for op in operations:
            eid = op["element_id"]
            txt = op["text"][:60].replace("\n", "↵")
            print(f"  replace_text {eid} → '{txt}'", file=sys.stderr)
        print("\n[DRY RUN] No Canva API calls made.", file=sys.stderr)
        # Write dry-run output
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        dry_out = {
            "design_id": args.design_id,
            "topic": data.get("topic"),
            "row": args.row,
            "page": args.page,
            "operations_count": len(operations),
            "dry_run": True,
            "slides": slides,
        }
        (out_dir / "canva_dryrun.json").write_text(
            json.dumps(dry_out, ensure_ascii=False, indent=2))
        print(f"✅ Dry-run output → {out_dir}/canva_dryrun.json", file=sys.stderr)
        return

    # ── Execute on Canva ──
    tx_id: Optional[str] = None
    try:
        tx_id = start_transaction(args.design_id)

        print(f"  📝 Applying {len(operations)} text operations...", file=sys.stderr)
        result = perform_operations(tx_id, operations, args.page,
                                    user_intent=f"War Room carousel: {data.get('topic', 'N/A')}")

        # Check results
        edit_results = result.get("edit_operation_results", [])
        success_count = sum(1 for r in edit_results if r.get("status") == "success")
        fail_count    = len(edit_results) - success_count
        print(f"  📊 Results: {success_count} success, {fail_count} failed", file=sys.stderr)

        if fail_count > 0:
            failures = [r for r in edit_results if r.get("status") != "success"]
            print(f"  ⚠️  Failures: {failures[:3]}", file=sys.stderr)

        # Commit
        committed = commit_transaction(tx_id)
        tx_id = None  # mark as done

        if not committed:
            print("❌ Commit failed", file=sys.stderr)
            sys.exit(1)

        # ── Write output metadata ──
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        master_dir = Path(args.master)
        master_dir.mkdir(parents=True, exist_ok=True)

        carousel_meta = {
            "design_id": args.design_id,
            "design_url": f"https://www.canva.com/design/{args.design_id}/edit",
            "topic": data.get("topic"),
            "tone": data.get("tone"),
            "row": args.row,
            "page": args.page,
            "slides_count": len(slides),
            "operations_applied": success_count,
            "committed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "instagram_caption": data.get("instagram_caption", ""),
            "slides": slides,  # full slide data including image_prompts
        }

        out_file = out_dir / "carousel_canva.json"
        out_file.write_text(json.dumps(carousel_meta, ensure_ascii=False, indent=2))
        print(f"  📁 Metadata → {out_file}", file=sys.stderr)

        # Master copy
        (master_dir / "carousel_canva.json").write_text(
            json.dumps(carousel_meta, ensure_ascii=False, indent=2))

        # Instagram caption
        if cap := data.get("instagram_caption"):
            (master_dir / "instagram_caption.txt").write_text(cap)

        # Image prompts summary for ComfyUI/Pollinations
        image_prompts = [
            {
                "slide": s.get("slide_number"),
                "is_cover": s.get("is_cover", False),
                "headline": s.get("headline", ""),
                "image_prompt": s.get("image_prompt", ""),
                "image_placement": s.get("image_placement", ""),
            }
            for s in slides if s.get("image_prompt")
        ]
        if image_prompts:
            ip_file = out_dir / "image_prompts.json"
            ip_file.write_text(json.dumps(image_prompts, ensure_ascii=False, indent=2))
            print(f"  🖼️  Image prompts ({len(image_prompts)}) → {ip_file}", file=sys.stderr)

        print(f"\n✅ Canva carousel ready!", file=sys.stderr)
        print(f"   🔗 {carousel_meta['design_url']}", file=sys.stderr)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if tx_id:
            cancel_transaction(tx_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
