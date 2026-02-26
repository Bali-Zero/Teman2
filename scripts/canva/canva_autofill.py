#!/usr/bin/env python3
"""
Canva Brand Template Autofill — Opzione B

Crea una copia editabile del brand template EAG6SZ7KgI0 con il testo
KBLI 2025 pre-compilato, poi restituisce il link per aprire in Canva
e modificare liberamente gli elementi.

Usage:
    python3 canva_autofill.py --topic kbli_2025
    python3 canva_autofill.py --json content.json
    python3 canva_autofill.py --check-fields   # verifica i Data Fields configurati
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from canva_client import CanvaClient

BRAND_TEMPLATE_ID = "EAG6SZ7KgI0"

# ------------------------------------------------------------------ #
# KBLI 2025 Content                                                   #
# ------------------------------------------------------------------ #

KBLI_2025_FIELDS = {
    "s1_title": "WHO'S MOST AFFECTED IN BALI?",
    "s1_body": (
        "VILLA OWNERS: Accommodation codes restructured. "
        "OTA platforms must verify your license by MARCH 2026.\n\n"
        "RESTAURANTS: Open to PMA but under high investment scrutiny.\n\n"
        "CAFÉS: Open to PMA but classified as large enterprise. "
        "IDR 10B investment plan required — EVEN FOR A SMALL COFFEE SHOP.\n\n"
        "DIGITAL AGENCIES: 63122 gone. You need sector-specific codes now.\n\n"
        "CONTENT CREATORS: New dedicated codes finally exist. "
        "This could be your legal pathway."
    ),
    "s2_title": "THE DEADLINE:\nJUNE 18, 2026",
    "s2_body": (
        "That's exactly 4 months away.\n"
        "All businesses must align their codes by then.\n\n"
        "BUT HERE'S THE CATCH:\n"
        "The OSS system HASN'T BEEN UPDATED YET.\n\n"
        "When it goes live, every PT PMA in Indonesia will rush "
        "to migrate at the same time.\n\n"
        "PREPARE NOW, NOT IN MAY."
    ),
    "s3_title": "WHAT HAPPENS IF\nYOU IGNORE THIS?",
    "s3_body": (
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
    "s4_title": "YOUR 4-STEP ACTION PLAN",
    "s4_body": (
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
    "s5_title": "IT'S NOT A SINGLE EVENT.\nIT'S A SLOW PARALYSIS.",
    "s5_body": (
        "Your license won't expire overnight.\n"
        "BKPM confirmed existing permits stay valid.\n\n"
        "BUT THE OPERATIONAL BLOCKS STACK UP:\n"
        "→ NIB flagged as 'INCOMPATIBLE' with new system.\n"
        "→ License renewals: BLOCKED.\n"
        "→ New KITAS work permits: STUCK.\n"
        "→ Import licenses? FROZEN.\n"
        "→ LKPM reports with wrong codes: AUTOMATIC SANCTIONS.\n\n"
        "IT'S NOT A SINGLE EVENT. IT'S A SLOW PARALYSIS."
    ),
    "s6_title": "WE AUDIT YOUR CODES\nYOU RUN YOUR BUSINESS",
    "s6_body": (
        "BALI ZERO HANDLES THE FULL KBLI MIGRATION:\n"
        "CODE AUDIT + AKTA AMENDMENT + OSS SYNC + COMPLIANCE CHECK.\n\n"
        "SAVE THIS POST FOR YOUR NEXT COMPLIANCE REVIEW.\n"
        "SEND IT TO SOMEONE WITH A PT PMA IN BALI."
    ),
    "s6_cta": "DM 'KBLI' OR WHATSAPP US",
}

TOPICS = {
    "kbli_2025": KBLI_2025_FIELDS,
}


# ------------------------------------------------------------------ #
# Autofill                                                            #
# ------------------------------------------------------------------ #

def check_fields(client: CanvaClient) -> None:
    """Check which Data Fields are configured on the brand template."""
    print(f"\nVerifica Data Fields — brand template: {BRAND_TEMPLATE_ID}")
    result = client._request("GET", f"/brand-templates/{BRAND_TEMPLATE_ID}/dataset")
    dataset = result.get("dataset", result)

    if not dataset:
        print("\n⚠️  Nessun Data Field configurato.")
        print("   Devi aprire il Brand Hub e assegnare i nomi ai campi testo.")
        print(f"   URL: https://www.canva.com/brand/brand-templates/{BRAND_TEMPLATE_ID}")
        print("\n   Campi richiesti:")
        for key in KBLI_2025_FIELDS:
            print(f"     • {key}")
        return

    print(f"\n✅ Data Fields trovati: {len(dataset)}")
    for key, info in dataset.items():
        print(f"   • {key}: {info}")

    # Check missing
    expected = set(KBLI_2025_FIELDS.keys())
    found = set(dataset.keys())
    missing = expected - found
    if missing:
        print(f"\n⚠️  Campi mancanti ({len(missing)}):")
        for k in sorted(missing):
            print(f"     • {k}")
    else:
        print("\n✅ Tutti i campi sono configurati — pronto per autofill!")


def run_autofill(client: CanvaClient, fields: dict, title: str) -> str:
    """
    Call POST /autofills to create a copy of the brand template
    with the given fields pre-filled. Returns the edit_url.
    """
    print(f"\n🎨 Avvio autofill — template: {BRAND_TEMPLATE_ID}")
    print(f"   Titolo design: {title}")
    print(f"   Campi da compilare: {len(fields)}")

    # Build autofill data
    data_fields = {}
    for field_name, value in fields.items():
        data_fields[field_name] = {
            "type": "text",
            "text": value,
        }

    payload = {
        "brand_template_id": BRAND_TEMPLATE_ID,
        "title": title,
        "data": data_fields,
    }

    result = client._request("POST", "/autofills", body=payload)
    print(f"\nRisposta autofill: {json.dumps(result, indent=2)}")

    # The API returns a job — poll until complete
    job = result.get("job", {})
    job_id = job.get("id")

    if not job_id:
        # Direct response with design info
        design = result.get("design", {})
        edit_url = design.get("urls", {}).get("edit_url") or design.get("edit_url", "")
        if edit_url:
            return edit_url
        raise RuntimeError(f"Autofill non ha restituito job_id né edit_url: {result}")

    print(f"   Job ID: {job_id} — polling...")
    return _poll_autofill_job(client, job_id)


def _poll_autofill_job(client: CanvaClient, job_id: str, timeout: int = 120) -> str:
    """Poll the autofill job until complete, return edit_url."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = client._request("GET", f"/autofills/{job_id}")
        job = result.get("job", {})
        status = job.get("status")

        if status == "success":
            design = job.get("design", {})
            edit_url = (
                design.get("urls", {}).get("edit_url")
                or design.get("edit_url")
                or ""
            )
            if not edit_url:
                # Try alternate path
                edit_url = job.get("result", {}).get("design", {}).get("urls", {}).get("edit_url", "")
            print(f"\nJob completato. Design: {json.dumps(design, indent=2)}")
            return edit_url

        if status == "failed":
            raise RuntimeError(f"Autofill job failed: {job}")

        print(f"   Status: {status} — attendo...")
        time.sleep(3)

    raise TimeoutError(f"Autofill job {job_id} timed out after {timeout}s")


# ------------------------------------------------------------------ #
# CLI                                                                 #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea carosello Canva via Brand Template autofill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Verifica Data Fields configurati
  python3 canva_autofill.py --check-fields

  # Autofill con contenuto KBLI 2025
  python3 canva_autofill.py --topic kbli_2025

  # Autofill con JSON custom
  python3 canva_autofill.py --json my_fields.json
        """,
    )
    parser.add_argument("--check-fields", action="store_true",
                        help="Verifica i Data Fields configurati nel brand template")
    parser.add_argument("--topic", choices=list(TOPICS.keys()),
                        help="Topic predefinito")
    parser.add_argument("--json", dest="json_file",
                        help="File JSON con i campi {field_name: text}")
    parser.add_argument("--title", default="",
                        help="Titolo del design generato (default: topic name + timestamp)")

    args = parser.parse_args()
    client = CanvaClient()

    if args.check_fields:
        check_fields(client)
        return

    # Load fields
    if args.json_file:
        with open(args.json_file) as f:
            fields = json.load(f)
        topic_label = Path(args.json_file).stem
    elif args.topic:
        fields = TOPICS[args.topic]
        topic_label = args.topic
    else:
        parser.error("Specifica --check-fields, --topic, o --json")

    title = args.title or f"KBLI Carousel — {topic_label} — {time.strftime('%Y%m%d-%H%M')}"

    try:
        edit_url = run_autofill(client, fields, title)
    except RuntimeError as e:
        print(f"\n❌ Errore: {e}")
        print("\nSe il dataset è vuoto, prima esegui:")
        print("  python3 canva_autofill.py --check-fields")
        sys.exit(1)

    if edit_url:
        print(f"\n✅ Design pronto!")
        print(f"   Apri in Canva per modificare liberamente:")
        print(f"\n   {edit_url}\n")
    else:
        print("\n⚠️  Autofill completato ma edit_url non trovato.")
        print(f"   Controlla manualmente: https://www.canva.com/brand/brand-templates/{BRAND_TEMPLATE_ID}")


if __name__ == "__main__":
    main()
