import json
import logging
import os
import sys

# Configure logging to match project standards
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("zantara.openapi_gen")

# Ensure we can import backend modules
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

try:
    from backend.app.main_cloud import app

    logger.info("✅ FastAPI app imported successfully")

    openapi_schema = app.openapi()

    # Define output path (project root/apps/backend-rag/openapi.json)
    output_path = os.path.join(os.getcwd(), "openapi.json")

    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    logger.info(f"✅ OpenAPI JSON exported to: {output_path}")

except Exception as e:
    logger.error(f"❌ Error exporting OpenAPI: {e}")
    sys.exit(1)
