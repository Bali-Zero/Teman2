#!/usr/bin/env python3
"""
FASE 4 — Canva Carousel Builder
================================
Popola il template War_Room (DAHEME4mocU) su Canva con il contenuto
generato da claude_director.py.

Architettura: claude -p come bridge MCP
  Il MCP Canva è un server remoto connesso SOLO alla sessione Claude Code
  (OAuth, non stdio, non HTTP locale). Non è raggiungibile da processi Python.
  Soluzione: genera un prompt strutturato e lo esegue via `claude -p`,
  identico al pattern Surgeon in Core Guardian.

Workflow:
  1. Legge claude_slides.json
  2. Costruisce un prompt preciso con le operazioni Canva da eseguire
  3. Lancia `claude -p "<prompt>"` — Claude Code esegue le MCP calls
  4. Parsa l'output JSON per verificare il successo
  5. Scrive carousel_canva.json + image_prompts.json in output/

TEMPLATE_SLOTS: element IDs pagina 1 del design DAHEME4mocU (War_Room)
  upper row (y < 400): slots 0-5 → cover + 5 pannelli
  lower row (y > 500): slots 0-3 → cover + 3 pannelli (seconda riga)

Per pagine 2-3: stesso design, stessi element ID — Canva li espone
  per pagina tramite page_index nel perform-editing-operations.
  Passare --page 2 usa page_index=2 ma gli element ID rimangono gli stessi
  (il design è un template: ogni pagina replica la struttura di pagina 1).
"""

import json
import sys
import os
import argparse
import subprocess
import time
from pathlib import Path
from typing import Optional

# ── Canva Design ──────────────────────────────────────────────────────────────
DEFAULT_DESIGN_ID = "DAHEME4mocU"

# ── Template element IDs (War_Room design, identici su tutte le pagine) ───────
# Struttura: (heading_element_id, body_element_id)
# upper row = riga superiore (y < 400px): cover + 5 pannelli
# lower row = riga inferiore (y > 500px): cover + 3 pannelli
TEMPLATE_SLOTS = {
    "upper": [
        ("PBsLhMw2tzZTd6V7-LBNh3LV9Wpg3J3yh", "PBsLhMw2tzZTd6V7-LBnxWRM9N3TnpjhD"),  # cover
        ("PBsLhMw2tzZTd6V7-LBHHjHgS87kxWQtR", "PBsLhMw2tzZTd6V7-LBdyFlLnfRvGlLFY"),  # panel 1
        ("PBsLhMw2tzZTd6V7-LB41FkdMcJjvFVy6", "PBsLhMw2tzZTd6V7-LBBGg07F7zXrT7wv"),  # panel 2
        ("PBsLhMw2tzZTd6V7-LBZjVnkTKs8G3DmH", "PBsLhMw2tzZTd6V7-LBNqRfkszx0hmt6K"),  # panel 3
        ("PBsLhMw2tzZTd6V7-LBYYRwyhQKY0Rgsp", "PBsLhMw2tzZTd6V7-LBvdBlbBdzkDQfJQ"),  # panel 4
        ("PBsLhMw2tzZTd6V7-LBPMtk8fRcwYm3jF", "PBsLhMw2tzZTd6V7-LB7TgRGdpRKVsRLY"),  # panel 5/CTA
    ],
    "lower": [
        ("PBsLhMw2tzZTd6V7-LBpj4gW2zMQ6phJM", "PBsLhMw2tzZTd6V7-LBFGYmXTfF9n1Jkn"),  # cover
        ("PBsLhMw2tzZTd6V7-LBtqPts7PGJ2kRqT", "PBsLhMw2tzZTd6V7-LBvDCd7CP36nK9dG"),  # panel 1
        ("PBsLhMw2tzZTd6V7-LBlYBx8wF8NrVWNF", "PBsLhMw2tzZTd6V7-LB1JKgk4QfKBpwVX"),  # panel 2
        ("PBsLhMw2tzZTd6V7-LBkddNpJPn8G8jzd", "PBsLhMw2tzZTd6V7-LBmS0210M4PRnHdQ"),  # panel 3
    ],
}

FINISH_MARKER = "FINISH FINISH FINISH FINISH FINISH FINISH"
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


# ── Slide → operations list ───────────────────────────────────────────────────

def slides_to_operations(slides: list, slots: list) -> list:
    """
    Converte slide JSON in lista di operazioni replace_text per Canva.
    - body è MOCKUP: nessun limite di lunghezza
    - image_prompt opzionale: aggiunto come annotazione tra parentesi nel body
    - Slot in eccesso rispetto alle slide → FINISH_MARKER
    """
    ops = []
    n_slots = len(slots)

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

        # Heading: headline + optional subhead (non-cover)
        heading_text = f"{headline}\n{subhead.upper()}" if (subhead and not is_cover) else headline

        # Body: testo + annotazione image prompt se presente
        body_parts = []
        if body:
            body_parts.append(body)
        if image_prompt:
            note = f"\n(IMAGE PROMPT: {image_prompt}"
            if image_placement:
                note += f" — PLACEMENT: {image_placement}"
            note += ")"
            body_parts.append(note)

        if is_cover and subhead:
            body_text = subhead
            if image_prompt:
                body_text += f"\n(COVER IMAGE PROMPT: {image_prompt}"
                if image_placement:
                    body_text += f" — {image_placement}"
                body_text += ")"
        else:
            body_text = "\n".join(body_parts) if body_parts else FINISH_MARKER

        ops.append({"type": "replace_text", "element_id": heading_id, "text": heading_text})
        ops.append({"type": "replace_text", "element_id": body_id,    "text": body_text})

    # Slot rimanenti → FINISH marker
    for j in range(len(slides), n_slots):
        heading_id, body_id = slots[j]
        ops.append({"type": "replace_text", "element_id": heading_id, "text": FINISH_MARKER})
        ops.append({"type": "replace_text", "element_id": body_id,    "text": FINISH_MARKER})

    return ops


# ── Claude -p bridge ──────────────────────────────────────────────────────────

def build_claude_prompt(design_id: str, page_index: int, operations: list,
                        topic: str) -> str:
    """
    Costruisce il prompt per `claude -p`.
    Claude Code ha accesso al MCP Canva — esegue le operazioni e ritorna JSON.
    """
    ops_json = json.dumps(operations, ensure_ascii=False, indent=2)
    return f"""You are executing a Canva carousel update for the War Room pipeline.

TASK: Update Canva design {design_id} with carousel content for topic: "{topic}"

STEPS (execute exactly in order, no confirmation needed):
1. Call mcp__claude_ai_Canva__start-editing-transaction with design_id="{design_id}"
2. Call mcp__claude_ai_Canva__perform-editing-operations with:
   - transaction_id: (from step 1)
   - page_index: {page_index}
   - user_intent: "War Room carousel: {topic}"
   - operations: {ops_json}
3. Check results — if any operation failed, note it but continue
4. Call mcp__claude_ai_Canva__commit-editing-transaction with the transaction_id

OUTPUT: After completing all steps, output ONLY this JSON (no other text):
{{
  "success": true/false,
  "transaction_id": "...",
  "operations_total": {len(operations)},
  "operations_success": <count of successful operations>,
  "design_url": "https://www.canva.com/design/{design_id}/edit",
  "committed": true/false,
  "error": null or "error message"
}}

IMPORTANT:
- Execute all MCP calls immediately, do not ask for confirmation
- If start-transaction fails, output success:false with error message
- If commit fails, still output what succeeded
- Output ONLY the JSON block, nothing else"""


def run_claude_bridge(prompt: str, timeout: int = 300) -> Optional[dict]:
    """
    Esegue `claude -p "<prompt>"` e parsa il JSON dall'output.
    Ritorna il dict risultato o None in caso di errore.
    """
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt,
             "--output-format", "json",
             "--model", "claude-haiku-4-5-20251001",
             "--no-session-persistence",   # avoid SessionEnd hook crash
             "--permission-mode", "bypassPermissions"],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "ANTHROPIC_MODEL": "claude-haiku-4-5-20251001"}
        )

        # rc=1 can come from SessionEnd hooks (claude-mem) crashing after output is written
        # Only fail if stdout is also empty
        if result.returncode != 0 and not result.stdout.strip():
            print(f"  ❌ claude -p failed (rc={result.returncode}): {result.stderr[:200]}",
                  file=sys.stderr)
            return None
        if result.returncode != 0:
            print(f"  ⚠️  claude -p rc={result.returncode} (hook error, ignoring — stdout present)",
                  file=sys.stderr)

        # Parse output: cerca JSON nell'output
        output = result.stdout.strip()
        # claude --output-format json wraps in {"result": "..."}
        try:
            outer = json.loads(output)
            # Claude JSON output format: {"type": "result", "result": "...", ...}
            inner_text = outer.get("result", output) if isinstance(outer, dict) else output
        except json.JSONDecodeError:
            inner_text = output

        # Cerca il blocco JSON nella risposta
        if isinstance(inner_text, str):
            # Trova l'ultimo { ... } nel testo
            start = inner_text.rfind("{")
            end   = inner_text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(inner_text[start:end])
                except json.JSONDecodeError:
                    pass
            print(f"  ⚠️  No JSON in claude output: {inner_text[:300]}", file=sys.stderr)
            return None
        elif isinstance(inner_text, dict):
            return inner_text

    except subprocess.TimeoutExpired:
        print(f"  ❌ claude -p timed out after {timeout}s", file=sys.stderr)
    except FileNotFoundError:
        print(f"  ❌ claude binary not found at: {CLAUDE_BIN}", file=sys.stderr)
    except Exception as e:
        print(f"  ❌ claude bridge error: {e}", file=sys.stderr)

    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="War Room — Canva Carousel Builder")
    ap.add_argument("--slides",    required=True,  help="Path a claude_slides.json")
    ap.add_argument("--output",    required=True,  help="Output dir (es. output/canva/)")
    ap.add_argument("--master",    required=True,  help="Master dir (es. output/master/)")
    ap.add_argument("--design-id", default=DEFAULT_DESIGN_ID)
    ap.add_argument("--row",       default="upper", choices=["upper", "lower"],
                    help="Riga template: upper (y<400) o lower (y>500)")
    ap.add_argument("--page",      type=int, default=1,
                    help="page_index Canva (1=prima pagina, default=1)")
    ap.add_argument("--dry-run",   action="store_true",
                    help="Mostra operazioni senza chiamare Canva")
    ap.add_argument("--timeout",   type=int, default=300,
                    help="Timeout in secondi per claude -p (default: 300)")
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

    print(f"\n🎨 Canva Carousel Builder", file=sys.stderr)
    print(f"   Design:  {args.design_id}", file=sys.stderr)
    print(f"   Topic:   {topic}", file=sys.stderr)
    print(f"   Slides:  {len(slides)}", file=sys.stderr)
    print(f"   Row:     {args.row}  Page: {args.page}", file=sys.stderr)

    # ── Build operations ──
    slots      = TEMPLATE_SLOTS[args.row]
    operations = slides_to_operations(slides, slots)
    print(f"   Ops:     {len(operations)} replace_text", file=sys.stderr)

    # ── Dry run ──
    if args.dry_run:
        print("\n[DRY RUN] Operations preview:", file=sys.stderr)
        for op in operations:
            txt = op["text"][:70].replace("\n", "↵")
            print(f"  {op['element_id'][-12:]} → '{txt}'", file=sys.stderr)
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

    # ── Execute via claude -p bridge ──
    prompt = build_claude_prompt(args.design_id, args.page, operations, topic)

    print(f"\n  🤖 Running claude -p bridge (timeout={args.timeout}s)...", file=sys.stderr)
    t0 = time.time()
    result = run_claude_bridge(prompt, timeout=args.timeout)
    elapsed = time.time() - t0
    print(f"  ⏱️  Elapsed: {elapsed:.1f}s", file=sys.stderr)

    if not result:
        print("⚠️  Canva bridge returned no result — skipping carousel update", file=sys.stderr)
        return

    if not result.get("success"):
        err = result.get("error", "unknown error")
        print(f"⚠️  Canva bridge reported failure: {err} — skipping carousel update", file=sys.stderr)
        return

    print(f"  ✅ {result.get('operations_success', '?')}/{result.get('operations_total', '?')} "
          f"ops — committed: {result.get('committed')}", file=sys.stderr)

    # ── Write output metadata ──
    meta = {
        "design_id":          args.design_id,
        "design_url":         result.get("design_url",
                                         f"https://www.canva.com/design/{args.design_id}/edit"),
        "topic":              topic,
        "tone":               data.get("tone"),
        "row":                args.row,
        "page":               args.page,
        "slides_count":       len(slides),
        "operations_applied": result.get("operations_success", len(operations)),
        "committed":          result.get("committed", True),
        "committed_at":       time.strftime("%Y-%m-%dT%H:%M:%S"),
        "instagram_caption":  data.get("instagram_caption", ""),
        "slides":             slides,
    }

    out_file = out_dir / "carousel_canva.json"
    out_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    (master_dir / "carousel_canva.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2))

    # Instagram caption
    if cap := data.get("instagram_caption"):
        (master_dir / "instagram_caption.txt").write_text(cap)

    # Image prompts per ComfyUI/Pollinations
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
        print(f"  🖼️  {len(image_prompts)} image prompts → {ip_file}", file=sys.stderr)

    print(f"\n✅ Canva carousel ready!", file=sys.stderr)
    print(f"   🔗 {meta['design_url']}", file=sys.stderr)


if __name__ == "__main__":
    main()
