"""
Fix PDF Encoding - Extract clean UTF-8 text from PDFs

This script:
1. Finds all PDF files in kb/ directory
2. Extracts text using PyMuPDF (handles binary encoding issues)
3. Saves clean UTF-8 text as .txt files
4. Ready for re-ingestion into Qdrant

Usage:
    cd /path/to/backend
    source venv/bin/activate
    python scripts/fix_pdf_encoding.py
"""

import sys
from pathlib import Path

import pymupdf  # pip install pymupdf


def fix_pdf_encoding():
    """Extract clean text from PDFs and save as .txt for re-ingestion"""

    # Determine KB directory path
    kb_dir = Path(__file__).parent.parent / "kb"

    # Create kb/ directory if it doesn't exist
    if not kb_dir.exists():
        print(f"⚠️  Directory KB non trovata: {kb_dir}")
        print("🔧 Creazione directory...")
        kb_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Directory creata: {kb_dir}")
        print(f"\n📌 Copia i tuoi PDF in: {kb_dir}")
        print("   Poi riesegui questo script.\n")
        return

    # Find PDF files
    pdf_files = list(kb_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ Nessun PDF trovato in {kb_dir}")
        print(f"\n📌 Copia i tuoi PDF in: {kb_dir}")
        print("   Poi riesegui questo script.\n")
        return

    print(f"📄 Trovati {len(pdf_files)} PDF da processare\n")
    print(f"Directory: {kb_dir}\n")

    success_count = 0
    error_count = 0
    total_chars = 0

    for pdf_path in pdf_files:
        print(f"Processing: {pdf_path.name}...")

        try:
            # Open PDF with PyMuPDF
            doc = pymupdf.open(pdf_path)
            text = ""

            # Extract text from each page
            for page_num, page in enumerate(doc, 1):
                page_text = page.get_text()
                text += f"\n--- Page {page_num} ---\n{page_text}"

            doc.close()

            # Save as .txt with UTF-8 encoding
            txt_path = pdf_path.with_suffix(".txt")
            txt_path.write_text(text, encoding="utf-8")

            chars = len(text)
            total_chars += chars
            success_count += 1

            print(f"  ✅ Estratto → {txt_path.name} ({chars:,} chars, {len(doc)} pages)")

        except Exception as e:
            error_count += 1
            print(f"  ❌ Errore: {e}")
            continue

    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY:")
    print(f"{'='*60}")
    print(f"  ✅ Successi:     {success_count}/{len(pdf_files)}")
    print(f"  ❌ Errori:       {error_count}/{len(pdf_files)}")
    print(f"  📝 Totale testo: {total_chars:,} caratteri")
    print(f"  📁 Output dir:   {kb_dir}")
    print(f"{'='*60}\n")

    if success_count > 0:
        print("✅ PDF processati con successo!")
        print("\n📋 PROSSIMI STEP:")
        print("1. Verifica i file .txt generati:")
        print(f"   ls -lh {kb_dir}/*.txt")
        print("\n2. (Opzionale) Backup Qdrant esistente:")
        print("   cp -r chroma_db chroma_db.backup_$(date +%Y%m%d_%H%M%S)")
        print("\n3. Re-ingest la knowledge base:")
        print("   python scripts/run_ingestion.py")
        print("\n4. Riavvia il backend:")
        print("   uvicorn app.main:app --reload --port 8000")
        print()
    else:
        print("⚠️  Nessun PDF processato con successo.")
        print("   Verifica che i PDF siano validi e leggibili.\n")


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 PDF Encoding Fix Tool")
    print("=" * 60)
    print("Questo script estrae testo pulito da PDF per risolvere")
    print("problemi di encoding nella knowledge base.\n")

    try:
        fix_pdf_encoding()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione interrotta dall'utente.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRORE FATALE: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
