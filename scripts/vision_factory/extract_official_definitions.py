import json
import re
import logging
from pdfminer.high_level import extract_text

logger = logging.getLogger(__name__)


def extract_official_definitions(pdf_path, output_path):
    logger.info(f"📄 Extracting text from {pdf_path}...")

    # Extract full text
    try:
        text = extract_text(pdf_path)
    except Exception as e:
        logger.error(f"❌ Error reading PDF: {e}")
        return

    logger.info(f"✅ Text extracted ({len(text)} chars). Parsing content...")

    # Pre-processing to clean up page numbers and heavy artifacts
    # Removing lines like "- 8 -" or "Page 8" if common, but specifically "- \d+ -"
    # Also removing form feed characters
    clean_lines = []
    lines = text.split("\n")

    page_num_pattern = re.compile(r"^\s*-\s*\d+\s*-\s*$")

    for line in lines:
        # Skip page numbers
        if page_num_pattern.match(line):
            continue
        # Skip header/footer noise if detected (heuristic)
        if "KLASIFIKASI BAKU LAPANGAN USAHA INDONESIA" in line and len(line) < 60:
            continue

        clean_lines.append(line)

    full_clean_text = "\n".join(clean_lines)

    # Regex to find KBLI Codes (5 digits)
    # Pattern: start of line, 5 digits, spaces, Title
    # We capture 5 digits, then title
    # Note: Sometimes title wraps? Usually title is on same line.
    # Looking at preview: "01111  PERTANIAN JAGUNG"

    # We will split the text by the code pattern to get the chunks
    # Pattern: ^(\d{5})\s+(.*)$ (multiline flag needed if we search, but let's iterate)

    kbli_pattern = re.compile(r"\n(\d{5})\s+(.*?)(?=\n\d{5}|\Z)", re.DOTALL)

    # Wait, splitting by code might be safer.
    # Let's find all starts.
    matches = list(re.finditer(r"\n(\d{5})\s+", full_clean_text))

    results = {}

    logger.info(f"🔍 Found {len(matches)} potential 5-digit KBLI codes.")

    for i, match in enumerate(matches):
        code = match.group(1)
        start_idx = match.end()  # Start of title + desc

        # End is start of next match or end of text
        end_idx = (
            matches[i + 1].start() if i + 1 < len(matches) else len(full_clean_text)
        )

        content_block = full_clean_text[start_idx:end_idx].strip()

        # The title is usually the first line of the content block
        lines_in_block = content_block.split("\n")
        title = lines_in_block[0].strip()

        # The description is the rest
        if len(lines_in_block) > 1:
            description_raw = "\n".join(lines_in_block[1:]).strip()
            # Clean up newlines in description (merge paragraphs)
            # Rejoin by space, but respect double newlines as paragraphs?
            # PDF extraction often breaks lines mid-sentence.
            # Simple heuristic: join with space if line doesn't end with period?
            # For now, let's just join with space to get a single block of text,
            # as Masterpiece "uraian" is usually a block.
            description = re.sub(r"\s+", " ", description_raw).strip()
        else:
            description = ""

        # Validation: Code must be 4 or 5 digits
        results[code] = {
            "kode": code,
            "judul": title,
            "uraian": description,
            "source": "Perban BPS No. 7 Tahun 2025",
        }

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"💾 Saved {len(results)} definitions to {output_path}")


if __name__ == "__main__":
    pdf_file = (
        "/Users/antonellosiano/Desktop/nuzantara/peraturan-bps-no-7-tahun-2025.pdf"
    )
    output_json = "/Users/antonellosiano/Desktop/nuzantara/source_documents/official_kbli_definitions.json"

    extract_official_definitions(pdf_file, output_json)