#!/usr/bin/env python3
"""
Generatore automatico di caroselli Canva per Bali Zero.

Struttura carosello (6 slide):
  1. Chi è colpito  — segmentazione per tipo di business
  2. La deadline    — data e urgenza
  3. Cosa succede   — conseguenze se ignori
  4. Piano in 4 step — azioni concrete
  5. Slow Paralysis  — testo centrale + immagine
  6. CTA Audit       — call to action Bali Zero

Usage:
    python3 canva_carousel.py --template DAHBtCC2-9A --topic kbli_2025
    python3 canva_carousel.py --template DAHBtCC2-9A --json content.json
    python3 canva_carousel.py --list-templates
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from canva_client import CanvaClient

OUTPUT_DIR = Path(__file__).parent / "output"

# ------------------------------------------------------------------ #
# Content Schemas                                                      #
# ------------------------------------------------------------------ #

@dataclass
class SlideContent:
    """Content for one carousel slide."""
    title: str
    body: str
    highlight: str = ""        # bold/colored text
    cta: str = ""              # call-to-action line
    image_query: str = ""      # optional image hint


@dataclass
class CarouselContent:
    topic: str
    slides: list[SlideContent]
    output_name: str = ""

    def __post_init__(self):
        if not self.output_name:
            self.output_name = self.topic.lower().replace(" ", "_")


# ------------------------------------------------------------------ #
# Pre-built content library                                            #
# ------------------------------------------------------------------ #

CONTENT_LIBRARY: dict[str, CarouselContent] = {
    "kbli_2025": CarouselContent(
        topic="KBLI 2025 Compliance",
        slides=[
            SlideContent(
                title="WHO'S MOST AFFECTED IN BALI?",
                body=(
                    "VILLA OWNERS: Accommodation codes restructured. "
                    "OTA platforms must verify your license by MARCH 2026.\n\n"
                    "RESTAURANTS: Open to PMA but under high investment scrutiny.\n\n"
                    "CAFÉS: Open to PMA but classified as large enterprise. "
                    "IDR 10B investment plan required — EVEN FOR A SMALL COFFEE SHOP.\n\n"
                    "DIGITAL AGENCIES: 63122 gone. You need sector-specific codes now.\n\n"
                    "CONTENT CREATORS: New dedicated codes finally exist. "
                    "This could be your legal pathway."
                ),
                highlight="EVEN FOR A SMALL COFFEE SHOP",
            ),
            SlideContent(
                title="THE DEADLINE:\nJUNE 18, 2026",
                body=(
                    "That's exactly 4 months away.\n"
                    "All businesses must align their codes by then.\n\n"
                    "BUT HERE'S THE CATCH:\n"
                    "[BKPM] The OSS system HASN'T BEEN UPDATED YET.\n\n"
                    "When it goes live, every PT PMA in Indonesia will rush "
                    "to migrate at the same time.\n\n"
                    "PREPARE NOW, NOT IN MAY."
                ),
                highlight="HASN'T BEEN UPDATED YET",
            ),
            SlideContent(
                title="WHAT HAPPENS IF\nYOU IGNORE THIS?",
                body=(
                    "Your license won't expire overnight.\n"
                    "BKPM confirmed existing permits stay valid.\n\n"
                    "BUT THE OPERATIONAL BLOCKS STACK UP:\n"
                    "→ NIB flagged as 'INCOMPATIBLE' with new system.\n"
                    "→ License renewals: BLOCKED.\n"
                    "→ New KITAS work permits: STUCK.\n"
                    "→ Import licenses? FROZEN.\n"
                    "→ LKPM reports with wrong codes: AUTOMATIC SANCTIONS.\n\n"
                    "It's not a single event. It's a slow paralysis."
                ),
                highlight="AUTOMATIC SANCTIONS",
            ),
            SlideContent(
                title="YOUR 4-STEP ACTION PLAN",
                body=(
                    "1. AUDIT — Map every code in your NIB against the KBLI 2025 "
                    "concordance table. Check: split merged? Deleted?\n\n"
                    "2. AMEND — If codes affect your AKTA (articles of association), "
                    "convene a shareholder meeting. New rules make this slower than before.\n\n"
                    "3. SYNC — Update NIB, licenses, and permits in "
                    "OSS-RBA when the system goes live.\n\n"
                    "4. CHECK DOWNSTREAM — Verify LKPM reporting, tax classification, "
                    "and any visa/import license tied to your codes.\n\n"
                    "DON'T WAIT FOR THE SYSTEM UPDATE. STEPS 1 AND 2 CAN START TODAY."
                ),
                highlight="DON'T WAIT FOR THE SYSTEM UPDATE",
            ),
            SlideContent(
                title="IT'S NOT A SINGLE EVENT.\nIT'S A SLOW PARALYSIS.",
                body=(
                    "Your license won't expire overnight.\n"
                    "BKPM confirmed existing permits stay valid.\n\n"
                    "BUT THE OPERATIONAL BLOCKS STACK UP:\n"
                    "→ NIB flagged as 'INCOMPATIBLE' [BIANCO] with new system.\n"
                    "→ License renewals: BLOCKED.\n"
                    "→ New KITAS work permits: STUCK.\n"
                    "→ Import licenses? FROZEN.\n"
                    "→ LKPM reports with wrong codes: AUTOMATIC SANCTIONS.\n\n"
                    "IT'S NOT A SINGLE EVENT. IT'S A SLOW PARALYSIS."
                ),
                image_query="bali business compliance",
            ),
            SlideContent(
                title="WE AUDIT YOUR CODES\nYOU RUN YOUR BUSINESS",
                body=(
                    "BALI ZERO HANDLES THE FULL KBLI MIGRATION:\n"
                    "CODE AUDIT + AKTA AMENDMENT + OSS SYNC + COMPLIANCE CHECK.\n\n"
                    "💾 SAVE THIS POST FOR YOUR NEXT COMPLIANCE REVIEW.\n"
                    "📩 SEND IT TO SOMEONE WITH A PT PMA IN BALI."
                ),
                cta="DM 'KBLI' OR WHATSAPP US",
                highlight="DM 'KBLI' OR WHATSAPP US",
            ),
        ],
    ),
}


# ------------------------------------------------------------------ #
# Carousel Generator                                                   #
# ------------------------------------------------------------------ #

class CarouselGenerator:
    def __init__(self, template_id: str):
        self.template_id = template_id
        self.client = CanvaClient()
        OUTPUT_DIR.mkdir(exist_ok=True)

    def generate(self, content: CarouselContent) -> Path:
        print(f"\n🎨 Generazione carosello: {content.topic}")
        print(f"   Template: {self.template_id}")
        print(f"   Slides: {len(content.slides)}")

        # Step 1: Get template info
        print("\n1/4 Lettura template...")
        design_info = self.client.get_design(self.template_id)
        design_title = design_info.get("design", {}).get("title", "Carousel")
        print(f"   Trovato: {design_title}")

        # Step 2: Inspect pages structure
        print("2/4 Analisi pagine...")
        pages = self.client.get_design_pages(self.template_id)
        page_list = pages.get("pages", {}).get("items", [])
        print(f"   Pagine trovate: {len(page_list)}")

        if not page_list:
            print("⚠️  Nessuna pagina trovata nel template. Verifica i permessi.")
            print("   Continuo con export diretto del template...")
            return self._export_template(content)

        # Step 3: Build page updates
        print("3/4 Preparazione aggiornamenti testo...")
        page_updates = self._build_page_updates(page_list, content.slides)

        if page_updates:
            # Apply text updates
            print(f"   Applicazione updates a {len(page_updates)} pagine...")
            self.client.update_design_pages(self.template_id, page_updates)
            time.sleep(1)  # let Canva process

        # Step 4: Export as PNG
        print("4/4 Export PNG...")
        return self._export_and_download(self.template_id, content.output_name)

    def _build_page_updates(
        self,
        page_list: list[dict],
        slides: list[SlideContent],
    ) -> list[dict]:
        """Map slide content to Canva page element updates."""
        updates = []
        for i, page in enumerate(page_list):
            if i >= len(slides):
                break
            slide = slides[i]
            page_id = page.get("id") or page.get("index", str(i + 1))

            # Find text elements in the page
            elements = page.get("elements", [])
            text_elements = [e for e in elements if e.get("type") == "text"]

            if not text_elements:
                # Page structure not accessible — skip text replacement
                continue

            element_updates = []
            # Map by position: first text block = title, rest = body
            for j, elem in enumerate(text_elements):
                elem_id = elem.get("id")
                if not elem_id:
                    continue
                if j == 0:
                    new_text = slide.title
                elif j == 1:
                    new_text = slide.body
                elif j == 2 and slide.cta:
                    new_text = slide.cta
                else:
                    continue

                element_updates.append({
                    "id": elem_id,
                    "type": "text",
                    "text": new_text,
                })

            if element_updates:
                updates.append({
                    "id": page_id,
                    "elements": element_updates,
                })

        return updates

    def _export_template(self, content: CarouselContent) -> Path:
        """Export template as-is (without text changes)."""
        return self._export_and_download(self.template_id, content.output_name + "_template")

    def _export_and_download(self, design_id: str, name: str) -> Path:
        """Export design and download all pages as PNGs."""
        export_job = self.client.export_design(design_id, format="png")
        export_id = export_job.get("job", {}).get("id")

        if not export_id:
            raise RuntimeError(f"Export job non avviato: {export_job}")

        print(f"   Export job: {export_id} — attendo completamento...")
        urls = self.client.wait_for_export(export_id)
        print(f"   {len(urls)} immagini pronte.")

        output_folder = OUTPUT_DIR / name
        output_folder.mkdir(exist_ok=True)

        for i, url in enumerate(urls, 1):
            dest = output_folder / f"slide_{i:02d}.png"
            self.client.download_file(url, dest)
            print(f"   ✅ {dest}")

        print(f"\n✅ Carosello salvato in: {output_folder}")
        return output_folder


# ------------------------------------------------------------------ #
# CLI                                                                  #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Genera caroselli Canva automaticamente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Genera carosello KBLI 2025 dal template
  python3 canva_carousel.py --template DAHBtCC2-9A --topic kbli_2025

  # Usa un file JSON con contenuto custom
  python3 canva_carousel.py --template DAHBtCC2-9A --json my_content.json

  # Lista topic disponibili
  python3 canva_carousel.py --list-topics

  # Mostra struttura del template
  python3 canva_carousel.py --template DAHBtCC2-9A --inspect
        """,
    )
    parser.add_argument("--template", help="Canva design ID del template")
    parser.add_argument("--topic", choices=list(CONTENT_LIBRARY.keys()), help="Topic predefinito")
    parser.add_argument("--json", dest="json_file", help="File JSON con contenuto custom")
    parser.add_argument("--list-topics", action="store_true", help="Lista topic disponibili")
    parser.add_argument("--inspect", action="store_true", help="Mostra struttura del template")

    args = parser.parse_args()

    if args.list_topics:
        print("\nTopic disponibili:")
        for key, content in CONTENT_LIBRARY.items():
            print(f"  {key:20s} — {content.topic} ({len(content.slides)} slides)")
        return

    if not args.template:
        parser.error("--template è obbligatorio")

    client = CanvaClient()

    if args.inspect:
        print(f"\nIspezione template: {args.template}")
        design = client.get_design(args.template)
        print(json.dumps(design, indent=2))
        pages = client.get_design_pages(args.template)
        print(json.dumps(pages, indent=2))
        return

    # Load content
    if args.json_file:
        with open(args.json_file) as f:
            raw = json.load(f)
        content = CarouselContent(
            topic=raw["topic"],
            output_name=raw.get("output_name", ""),
            slides=[SlideContent(**s) for s in raw["slides"]],
        )
    elif args.topic:
        content = CONTENT_LIBRARY[args.topic]
    else:
        parser.error("Specifica --topic o --json")

    gen = CarouselGenerator(args.template)
    output_path = gen.generate(content)
    print(f"\n🎉 Fatto! Files: {output_path}")


if __name__ == "__main__":
    main()
