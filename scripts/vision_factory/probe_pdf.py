from pdfminer.high_level import extract_text
import logging

logger = logging.getLogger(__name__)

pdf_path = "/Users/antonellosiano/Desktop/nuzantara/peraturan-bps-no-7-tahun-2025.pdf"

# Extract first 10 pages roughly (pdfminer extracts all by default, we'll just print start)
# To limit pages, we use maxpages (if using specialized classes) but extract_text is simple.
# Let's just extract all and slice string for preview, or use PDFResourceManager for better control if efficient.
# For now, simple extract_text is enough to see layout.

text = extract_text(pdf_path, maxpages=10)

logger.info("--- START PDF TEXT PREVIEW ---")
logger.info(text[:5000])  # Print first 5000 chars
logger.info("--- END PDF TEXT PREVIEW ---")

with open("pdf_preview_extract.txt", "w") as f:
    f.write(text)
