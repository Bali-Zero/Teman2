import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
RAW_LAWS_DIR = Path(
    "/Users/antonellosiano/Desktop/nuzantara/apps/scraper/data/raw_laws_targeted"
)
PRICING_KEYWORDS = ["Rp.", "Rp ", "IDR", "Biaya", "Harga", "Tarif", "PNBP"]


def clean_file(file_path: Path):
    """
    Remove lines containing pricing keywords from a file.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        cleaned_lines = []
        removed_count = 0

        for line in lines:
            # Check if line contains any pricing keyword (case insensitive)
            if any(keyword.lower() in line.lower() for keyword in PRICING_KEYWORDS):
                removed_count += 1
                continue
            cleaned_lines.append(line)

        if removed_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(cleaned_lines)
            logger.info(f"✅ Cleaned {file_path.name}: Removed {removed_count} lines")
        else:
            logger.info(f"⚪ No pricing info found in {file_path.name}")

    except Exception as e:
        logger.error(f"❌ Error processing {file_path.name}: {e}")


def main():
    if not RAW_LAWS_DIR.exists():
        logger.error(f"❌ Directory not found: {RAW_LAWS_DIR}")
        return

    logger.info(f"🧹 Starting cleanup of pricing info in {RAW_LAWS_DIR}...")

    files = list(RAW_LAWS_DIR.glob("*.txt"))
    logger.info(f"Found {len(files)} files to process.")

    for file_path in files:
        clean_file(file_path)

    logger.info("✨ Cleanup complete!")


if __name__ == "__main__":
    main()
