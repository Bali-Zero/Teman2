import sys
import os
import logging

logger = logging.getLogger(__name__)

# Add the script directory to path so we can import if needed,
# but here we might just duplicate the import or rely on existing file being there.
sys.path.append(os.path.dirname(__file__))

from mineru_to_masterpiece import convert_csv_to_masterpiece

input_csv = "/Users/antonellosiano/riri/azure_full_output/lampiran_IC_part2.csv"
output_json = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_extraction_lampiran_ic_part2_v2.json"

logger.info(f"Starting conversion from {input_csv} to {output_json}")
convert_csv_to_masterpiece(input_csv, output_json)
logger.info("Conversion finished.")
