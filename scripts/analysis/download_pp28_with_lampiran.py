#!/usr/bin/env python3
"""
Scarica PP 28/2025 completo con Lampiran da siti ufficiali JDIH
"""

import os
import requests
from pathlib import Path

# URL ufficiali trovati
JDIH_KEMENKEU = "https://jdih.kemenkeu.go.id/dok/pp-28-tahun-2025"
JDIH_MENLHK = "https://jdih.menlhk.go.id/new2/home/portfolioDetails2/PP_28_2025.pdf/28/2025/7"
DPMPTSP_PURBALINGGA = "https://dpmptsp.purbalinggakab.go.id/wp-content/uploads/2025/06/Bahan-Sosialisasi-PP-28-Tahun-2025.pdf"

DOWNLOAD_DIR = "/Users/antonellosiano/Desktop"


def download_pdf(url: str, filename: str) -> bool:
    """Scarica un PDF da un URL"""
    try:
        print(f"📥 Scaricando da: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        
        if response.status_code == 200:
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            size_mb = len(response.content) / (1024 * 1024)
            print(f"  ✅ Salvato: {filename} ({size_mb:.2f} MB)")
            return True
        else:
            print(f"  ❌ Errore HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Errore: {e}")
        return False


def extract_pdf_link_from_jdih(url: str) -> str | None:
    """Estrae il link diretto al PDF dalla pagina JDIH"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            html = response.text
            # Cerca link PDF nella pagina
            import re
            pdf_links = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.IGNORECASE)
            if pdf_links:
                # Prendi il primo link PDF trovato
                pdf_link = pdf_links[0]
                # Se è un link relativo, convertilo in assoluto
                if pdf_link.startswith("/"):
                    from urllib.parse import urlparse
                    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    pdf_link = base_url + pdf_link
                elif not pdf_link.startswith("http"):
                    from urllib.parse import urljoin
                    pdf_link = urljoin(url, pdf_link)
                return pdf_link
    except Exception as e:
        print(f"  ⚠️  Errore estrazione link: {e}")
    return None


def main():
    """Main download function"""
    print("=" * 60)
    print("DOWNLOAD PP 28/2025 CON LAMPIRAN DA SITI UFFICIALI")
    print("=" * 60)
    
    # 1. Prova a scaricare dalla pagina JDIH Kemenkeu
    print("\n1️⃣ Tentativo da JDIH Kemenkeu...")
    pdf_link = extract_pdf_link_from_jdih(JDIH_KEMENKEU)
    if pdf_link:
        print(f"   Link PDF trovato: {pdf_link}")
        download_pdf(pdf_link, "PP_28_2025_JDIH_Kemenkeu.pdf")
    else:
        print("   ⚠️  Link PDF non trovato nella pagina")
    
    # 2. Prova link diretto DPMPTSP (presentazione con Lampiran)
    print("\n2️⃣ Tentativo da DPMPTSP Purbalingga (presentazione)...")
    download_pdf(DPMPTSP_PURBALINGGA, "Bahan_Sosialisasi_PP_28_2025.pdf")
    
    # 3. Verifica file esistenti
    print("\n3️⃣ Verifica file esistenti sul Desktop...")
    existing_files = [
        "PP Nomor 28 Tahun 2025 (1).pdf",
        "PP_28_2025_JDIH_Kemenkeu.pdf",
        "Bahan_Sosialisasi_PP_28_2025.pdf",
    ]
    
    for filename in existing_files:
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"  ✅ {filename} ({size_mb:.2f} MB)")
        else:
            print(f"  ❌ {filename} (non trovato)")
    
    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETATO")
    print("=" * 60)
    print("\n💡 Prossimi passi:")
    print("  1. Verifica se i file scaricati contengono i Lampiran")
    print("  2. Se il PDF principale ha i Lampiran inclusi, usa Vision per estrarli")
    print("  3. Se i Lampiran sono in file separati, analizzali con Vision")


if __name__ == "__main__":
    main()
