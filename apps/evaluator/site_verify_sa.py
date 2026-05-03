"""
Site Verification — completa la verifica del service account come siteOwner.

Prerequisiti:
1. Il meta tag è già in layout.tsx e deployato su balizero.com
2. Il SA ha già il token via getToken() (già usato per layout.tsx)

Usage:
    python apps/evaluator/site_verify_sa.py --check   # verifica se meta tag è live
    python apps/evaluator/site_verify_sa.py --insert  # esegue la verifica (diventa siteOwner)
    python apps/evaluator/site_verify_sa.py --list    # lista risorse verificate
"""

import argparse
import sys
import urllib.request
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"
SITE_URL = "https://balizero.com/"
VERIFICATION_TOKEN = "tuGW8kCBjRE-ycNaFdotBkKfOIaunurqnj-XDAVlPWw"


def build_service():
    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/siteverification"],
    )
    return build("siteVerification", "v1", credentials=creds)


def check_meta_tag_live() -> bool:
    """Controlla se il meta tag è già presente su balizero.com."""
    try:
        req = urllib.request.Request(
            "https://balizero.com/",
            headers={"User-Agent": "Mozilla/5.0 NuzantaraSEO/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            if VERIFICATION_TOKEN in html:
                print(f"✅ Meta tag trovato su balizero.com")
                return True
            else:
                print(f"❌ Meta tag NON trovato su balizero.com (deploy non ancora live?)")
                print(f"   Cerco: {VERIFICATION_TOKEN}")
                # Show <head> snippet for debug
                head_start = html.find("<head")
                head_end = html.find("</head>")
                if head_start != -1 and head_end != -1:
                    head = html[head_start:head_end]
                    if "google-site-verification" in head:
                        print("   (trovato google-site-verification ma token diverso)")
                return False
    except Exception as e:
        print(f"❌ Errore fetch: {e}")
        return False


def insert_verification() -> None:
    """Chiama l'API per completare la verifica del SA come siteOwner."""
    service = build_service()
    try:
        result = service.webResource().insert(
            verificationMethod="META",
            body={
                "site": {"type": "SITE", "identifier": SITE_URL},
            },
        ).execute()
        print(f"✅ Verifica completata! Il SA è ora siteOwner di {SITE_URL}")
        print(f"   Owners: {result.get('owners', [])}")
    except Exception as e:
        print(f"❌ Errore insert: {e}")
        sys.exit(1)


def list_verified() -> None:
    """Lista le risorse verificate dal SA."""
    service = build_service()
    try:
        result = service.webResource().list().execute()
        items = result.get("items", [])
        if not items:
            print("Nessuna risorsa verificata per questo SA.")
        for item in items:
            site = item.get("site", {})
            print(f"  - {site.get('type')}: {site.get('identifier')} | owners: {item.get('owners', [])}")
    except Exception as e:
        print(f"❌ Errore list: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Site Verification per SA balizero.com")
    parser.add_argument("--check", action="store_true", help="Controlla se meta tag è live")
    parser.add_argument("--insert", action="store_true", help="Esegui verifica (diventa siteOwner)")
    parser.add_argument("--list", action="store_true", help="Lista risorse verificate")
    args = parser.parse_args()

    if args.check:
        check_meta_tag_live()
    elif args.insert:
        if not check_meta_tag_live():
            print("⚠️  Il meta tag non è live. Deploy prima su Vercel, poi riprova.")
            sys.exit(1)
        insert_verification()
    elif args.list:
        list_verified()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
