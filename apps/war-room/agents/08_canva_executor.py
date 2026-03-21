#!/usr/bin/env python3
"""
FASE 4b — Canva Executor
========================
Legge canva_pending.json e applica le operazioni su Canva via MCP.

Questo script viene chiamato da Claude Code (sessione interattiva) che ha
accesso ai remote MCP tools di claude.ai, incluso Canva.

NON può essere eseguito headless (subprocess) perché il Canva MCP richiede
autenticazione OAuth browser-bound alla sessione Claude Code interattiva.

Utilizzo:
    # Claude Code lo chiama internamente leggendo canva_pending.json
    python3 agents/08_canva_executor.py --pending output/canva/canva_pending.json

Output:
    - output/canva/canva_applied.json  (status: applied)
    - output/canva/carousel_canva.json (con design_url)
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def load_pending(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"❌ File non trovato: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(p.read_text())
    if data.get("status") == "applied":
        print(f"✅ Già applicato: {path}", file=sys.stderr)
        sys.exit(0)
    return data


def print_operations_summary(pending: dict) -> None:
    """Stampa un summary leggibile delle operazioni da applicare."""
    ops = pending.get("operations", [])
    slides = pending.get("slides", [])
    print(f"\n🎨 Canva Executor — {pending.get('topic', 'N/A')}")
    print(f"   Design: {pending.get('design_url', 'N/A')}")
    print(f"   Slides: {pending.get('slides_count', 0)}")
    print(f"   Ops:    {len(ops)} replace_text")
    print(f"   Tone:   {pending.get('tone', 'N/A')}\n")

    print("📋 Preview slides:")
    for s in slides[:3]:
        print(f"   [{s.get('slide_number', '?')}] {s.get('headline', '')[:60]}")
    if len(slides) > 3:
        print(f"   ... +{len(slides)-3} slides")


def mark_applied(pending_path: str, design_url: str) -> None:
    """Aggiorna status a 'applied' e scrive carousel_canva.json."""
    p = Path(pending_path)
    data = json.loads(p.read_text())
    data["status"] = "applied"
    data["applied_at"] = datetime.now().isoformat()
    data["design_url"] = design_url
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Scrivi anche carousel_canva.json (usato da 07_delivery.sh)
    canva_out = p.parent / "carousel_canva.json"
    canva_out.write_text(json.dumps({
        "design_id": data.get("design_id"),
        "design_url": design_url,
        "topic": data.get("topic"),
        "slides_count": data.get("slides_count"),
        "applied_at": data["applied_at"],
        "status": "applied",
    }, ensure_ascii=False, indent=2))

    print(f"✅ Canva applicato → {canva_out}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", required=True, help="Path a canva_pending.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pending = load_pending(args.pending)
    print_operations_summary(pending)

    if args.dry_run:
        print("🔍 [DRY RUN] Operazioni non applicate.")
        return

    print("\n⚡ Questo script deve essere eseguito da Claude Code con accesso MCP Canva.")
    print("   Claude Code applicherà le operazioni via mcp__claude_ai_Canva__*")
    print(f"\n   File pending: {args.pending}")
    print(f"   Design ID:   {pending.get('design_id')}")
    print(f"   Operations:  {pending.get('operations_count')}")


if __name__ == "__main__":
    main()
