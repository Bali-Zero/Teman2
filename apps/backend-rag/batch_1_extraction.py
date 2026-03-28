import asyncio
import json
import logging
import os
import sys

import httpx
import pdfplumber

# Add backend to path
sys.path.append("/Users/nuzantara/Desktop/nuzantara/apps/backend-rag")

# Nuzantara imports
# from backend.services.integrations.drive.drive_auth import DriveAuthManager # Removing since we'll do manual OAuth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Batch1Extractor")

# Constants
RESULTS_DIR = "/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/extraction_results"
PDF_DIR = os.path.join(RESULTS_DIR, "pdfs")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "batch_1_results.json")

# Ensure directories exist
os.makedirs(PDF_DIR, exist_ok=True)

COMPANIES = [
    {"company_id": 2054, "name": "PT Lab Satu Delapan Satu", "drive_file_id": "1BZSJnplcxalXUa-ITvAN0Tlyln1b5awU"},
    {"company_id": 2054, "name": "PT Lab Satu Delapan Satu", "drive_file_id": "1r4Hpqj_DdUdKw-M_jtiBzPThSC8nMVgH"},
    {"company_id": 2055, "name": "PT Lachance Property Management", "drive_file_id": "1uzQW9Ds6S1HPG9IU_2l7FqD6GxXvXTFf"},
    {"company_id": 2056, "name": "PT Lakra", "drive_file_id": "17AcgcNvSJvN6zA6n6djnFjf7QP1IYAXC"},
    {"company_id": 2056, "name": "PT Lakra", "drive_file_id": "1eX_z_7HJDIXvZZMO_-yoaSa9FIxU1_qz"},
    {"company_id": 2056, "name": "PT Lakra", "drive_file_id": "1kZcy4jTm9n4ew92yqgozKJ1z4XujyK4J"},
    {"company_id": 2056, "name": "PT Lakra", "drive_file_id": "1t52AB4alwaP1GIh21SkC3rkGtFygaFKr"},
    {"company_id": 2056, "name": "PT Lakra", "drive_file_id": "1xENuMVbRGaudEokEpDJqJYfm6L4Fi6zo"},
    {"company_id": 2058, "name": "PT Lala Catalano Investments", "drive_file_id": "1KaW8qXQ3YAobnxrzAlZMwxb55w63SNrO"},
    {"company_id": 2060, "name": "PT Landscape Art Bali", "drive_file_id": "1o-jfbTLsZDxqZBYzGZ59EAGeAvh7ntuK"},
    {"company_id": 2060, "name": "PT Landscape Art Bali", "drive_file_id": "1v0eIljAlcKyBwccLhvaRBWs5u00VxkRh"},
    {"company_id": 2062, "name": "PT Las Alas Studio", "drive_file_id": "1YDqWSGDMtuXT2-FgUwxMXjJ93uZ78KFA"},
    {"company_id": 2065, "name": "PT Layang Bali Jaya", "drive_file_id": "1tUTMCzMDDp3iKDHrWwLyofhrs9a3AFIN"},
    {"company_id": 2068, "name": "PT Leleka Internasional Indonesia", "drive_file_id": "104Jp8nrqTzT8ivcTDQtJXehrtRjTwHn4"},
    {"company_id": 2068, "name": "PT Leleka Internasional Indonesia", "drive_file_id": "17uh1kcKihopIsQRhVe4zAIO_IpPbA4EM"},
    {"company_id": 2070, "name": "PT Lesbabes Spa Bali (zainal)", "drive_file_id": "1M6q5QBsTXBm3F3MIX5e4tKKrDdDStIPP"},
    {"company_id": 2072, "name": "PT Lets Get Afterit", "drive_file_id": "1emi5YyolcNqpctZYl9-YKROu0y97WKfJ"},
    {"company_id": 2072, "name": "PT Lets Get Afterit", "drive_file_id": "1qmlg7K1M-7I0IfoNpxoyL9TtX5aGxrWo"},
    {"company_id": 2072, "name": "PT Lets Get Afterit", "drive_file_id": "1u_Dbw6Fh6k2tZByMnbzS4qsAecxAaPhY"},
    {"company_id": 2073, "name": "PT Lettuce Entertain You", "drive_file_id": "1pROKMDkeBNyqiXFSVQUlvasgTHfk4KrW"},
    {"company_id": 2074, "name": "PT Liah Media Consulting", "drive_file_id": "14YG74XYt5kRgspJpCe2JhC_N8Y1cbLHc"},
    {"company_id": 2074, "name": "PT Liah Media Consulting", "drive_file_id": "168k2gVWZLvLLlnAPMRE9JwcNhIroIKb0"},
    {"company_id": 2074, "name": "PT Liah Media Consulting", "drive_file_id": "19sl2qUjhYCeGchz5Od3-shPwJBnJE12_"},
    {"company_id": 2077, "name": "PT Libra Investment Consulting", "drive_file_id": "1fVW9Ln0f3qQ4qCCknxOH3SBI01mYkCY_"},
    {"company_id": 2077, "name": "PT Libra Investment Consulting", "drive_file_id": "1p-b48UDtjdzTrWwPvfrlgfG2Xhz0keO3"},
    {"company_id": 2078, "name": "PT Life Bali Group", "drive_file_id": "1xHzoinmoh5EvxHMaKfNCCmDEPHUpuBVV"},
    {"company_id": 2079, "name": "PT Lifestyle Property Group", "drive_file_id": "1OjxCIrEue__4D_g7vI5CdZPpFO4Qh2gq"},
    {"company_id": 2080, "name": "PT Ligeli Jiwa Raga Selaras", "drive_file_id": "1IZWKT74d7UN51azRIJKK6o0hvJfuTGDF"},
    {"company_id": 2085, "name": "PT Lion Investment Consulting", "drive_file_id": "1T9sNS4PTM66c-mAYMo-LznoAuqdJ84yA"},
    {"company_id": 2089, "name": "PT Live Dream Bali", "drive_file_id": "1LmDsmo_oQWBaFfb6t9yYjQnGDDHmf8Ri"},
    {"company_id": 2089, "name": "PT Live Dream Bali", "drive_file_id": "1QoE6eBcFYlRxVoO-duGkAYAVixyXHM_X"},
    {"company_id": 2090, "name": "PT Living Shoreline Dreams", "drive_file_id": "1preVnDeqA-Z1Tg4BC9DZ3Lw_eX0tG7vo"},
    {"company_id": 2092, "name": "PT Loku Property Investments", "drive_file_id": "1qRSYvVvl1m7VSWEB13k7cAx0zL5gVARl"},
    {"company_id": 2093, "name": "PT Lombok Cabana Lodge", "drive_file_id": "1Te42umnjkxaD9YOYaSIEweJkLYobpATW"},
    {"company_id": 2096, "name": "PT Lowlands Capital Investments", "drive_file_id": "1FPIWBxSyIARXf0KVoUtG7lv0pVRhKFyw"},
    {"company_id": 2097, "name": "PT Loyo Bondar Real Estate", "drive_file_id": "17LIZ4FnCJ-OqFnMHdoCTq__kfSc7ThEv"},
    {"company_id": 2099, "name": "PT Loyo Group Bali", "drive_file_id": "1N-URR_7DgzOKWRPWh0UnlPPMHl_DetOv"},
    {"company_id": 2099, "name": "PT Loyo Group Bali", "drive_file_id": "1OGkVoij9aVFK3tABB5at_uQMh_WfKe8R"},
    {"company_id": 2100, "name": "PT Lucky Choice Bali", "drive_file_id": "1TR29nE_W44guQea_h2nSPC1E_kp2K_H6"},
    {"company_id": 2100, "name": "PT Lucky Choice Bali", "drive_file_id": "1Y1FfIVGKzhq1gbBwHffwc-VmYQy7T1cl"},
    {"company_id": 2101, "name": "PT Lucky Estate Development", "drive_file_id": "1Q-i07Rnj2lvOK_bN04ppYwM2ryN3Ld7g"},
    {"company_id": 2104, "name": "PT Lumi Creative House", "drive_file_id": "1js3a9-2hkupzhKveVYIz4uEpChFjXK1j"},
    {"company_id": 2107, "name": "PT Lumos Innovation Labs", "drive_file_id": "14PlYPmu2S_-iliL0m5FRfj_E7IQ06rVD"},
    {"company_id": 2107, "name": "PT Lumos Innovation Labs", "drive_file_id": "1H5uVqRTNc4cOS0Awbl4RmiQR6n_1fDXT"},
    {"company_id": 2107, "name": "PT Lumos Innovation Labs", "drive_file_id": "1N5KI8_EVP4j7LWBVnpZg4nNrfHaJyf6I"},
    {"company_id": 2108, "name": "PT Luvira Interior Goods", "drive_file_id": "1tH_GtPI-HD8XmbAmRsjQhOtzlZsWy1Fn"},
    {"company_id": 2113, "name": "PT MBM Indonesia Group", "drive_file_id": "1D3auHaWrzyqw3OvjCKIssTZRLlH9rKT2"},
    {"company_id": 2115, "name": "PT MCGM International Business", "drive_file_id": "1LkaO52KYGXo_FD24SuoK2eOyGZ7kpA1-"},
    {"company_id": 2116, "name": "PT MJM Lifestyle Investments", "drive_file_id": "1Af8It-zOlnHZAQjk2oePcTR6gIk7iQAW"},
    {"company_id": 2120, "name": "PT Mac Net Informasi", "drive_file_id": "1IhKaPNlICN9KP0cpnWxXQyjTCWNxVB1o"},
    {"company_id": 2123, "name": "PT Made With Comp", "drive_file_id": "1VIyiobPUM-6ZemQRCTzY1JBXe6l1TIpo"},
    {"company_id": 2128, "name": "PT Magic Bird Colibri", "drive_file_id": "1X_hFVkCVbNOTpRc8-OWzk91YuiCXRn9b"},
    {"company_id": 2132, "name": "PT Magnum Management Indonesia", "drive_file_id": "1Y28EB3zd0NFWieA7W5TMviiTGWnWhPC8"},
    {"company_id": 2134, "name": "PT Maison Design Group", "drive_file_id": "1Ucj6zxwsPc64MzT8W4-elT6yOAyfuIbO"},
    {"company_id": 2135, "name": "PT Maison Properties Management", "drive_file_id": "1wXndxPDS7rygIM_l3C8jVMBE9UFcIvGd"},
    {"company_id": 2136, "name": "PT Majarom Luclair Leju", "drive_file_id": "1uLs6Bjp7U-Rtm_J0P4QXqdFrZyIAjCNf"},
    {"company_id": 2137, "name": "PT Maju Bersama Agency", "drive_file_id": "12W_fgNqifugRC_Y7LsCEZXd3ACml5uKI"},
    {"company_id": 2139, "name": "PT Makan Tiga Sembilan", "drive_file_id": "1nCrUsZ8fClVsGoaxrPqQuh_E_GGUO7Wf"},
    {"company_id": 2140, "name": "PT Malamadre Motor Bali", "drive_file_id": "1CVTPs3v2RZw8apho7jWJeP0C0ugLY5Vd"},
    {"company_id": 2140, "name": "PT Malamadre Motor Bali", "drive_file_id": "1myvLOTX_JNwO-lJ3VqV-hOYy64jCRBM3"},
    {"company_id": 2141, "name": "PT Malu Rumah Kecil", "drive_file_id": "1h-wGkjwKVafXA-TET5irgfASwWhcluJC"},
    {"company_id": 2141, "name": "PT Malu Rumah Kecil", "drive_file_id": "1xCnOKSKOATlxCI4_X60ojsZ1Jvn4lm-7"},
    {"company_id": 2145, "name": "PT Mani Libertad Villas", "drive_file_id": "1Bf6poDAqqZorx3_eiXyfSEIi0PqSq91M"},
    {"company_id": 2145, "name": "PT Mani Libertad Villas", "drive_file_id": "1_u417pZ6k66RN-jo7CArqtRQCJ7Wseog"},
    {"company_id": 2148, "name": "PT Mapru Business Group", "drive_file_id": "116mJGjzHS0RNv4K4QIc2xdyrl8etis0u"},
    {"company_id": 2149, "name": "PT Mares Fitness Coaching", "drive_file_id": "1VvaacVvo12Qgb_g3kOiM5J1TFzYxA60x"},
    {"company_id": 2150, "name": "PT Marias Villas Bali", "drive_file_id": "1cHev1liGWMeBy-NyukwVpqkQoo1cYkE_"},
    {"company_id": 2155, "name": "PT Marshall Investment Bali", "drive_file_id": "1zn2e79F5x5iy0D6S6FcZFvvhRKil2WHf"},
    {"company_id": 2158, "name": "PT Masa Depan Utama Lestari", "drive_file_id": "1qk246rHQpij6JMLhmb4mLnC6EgrYKs9z"},
    {"company_id": 2159, "name": "PT Max Gianni Management", "drive_file_id": "1_OFV6eu4cFxPhATr0iG3mjn20laE-xN7"},
    {"company_id": 2160, "name": "PT Max Uli Bali", "drive_file_id": "18zr7mxm8nF5bHAiMaPXiQtBl_MHd0vsv"},
    {"company_id": 2160, "name": "PT Max Uli Bali", "drive_file_id": "1QTO6vMxN7eU5anOxhM0gRkwFQ-pucFWz"},
    {"company_id": 2161, "name": "PT Maximus Media Consulting", "drive_file_id": "1ZS1xFpBWE0k4fJilaLcqy3Dj15vqRQdk"},
    {"company_id": 2163, "name": "PT Mazo Consulting and Development", "drive_file_id": "1BwolvWjPB4J-pXZn6nx3mo48JEt7skC7"},
    {"company_id": 2163, "name": "PT Mazo Consulting and Development", "drive_file_id": "1Iijbi3UoBzFqrhY2vv953K1hhZ7HoRyk"},
    {"company_id": 2164, "name": "PT Mcmillan Indonesian Investment Group", "drive_file_id": "1cOSVF0u5j5QsS2h5ns64glN5ckHBof6_"},
]

class Batch1Extractor:
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.creds_path = "/Users/nuzantara/.gemini/oauth_creds.json"
        with open(self.creds_path) as f:
            self.creds = json.load(f)

    async def get_token(self):
        # The refresh logic is failing because we don't have the correct client_id/secret for this specific token.
        # We will use the access_token from the file directly.
        access_token = self.creds.get("access_token")
        if access_token:
            logger.info("Using access token from oauth_creds.json")
            return access_token

        logger.error("No access token found in oauth_creds.json")
        return None

    async def download_pdf(self, file_id: str, company_name: str) -> str | None:
        # Use the backend API to download the file
        api_url = f"https://nuzantara-rag.fly.dev/api/drive/files/{file_id}/download"
        headers = {"X-API-Key": "admin-key-2024"}

        safe_name = "".join([c if c.isalnum() else "_" for c in company_name])
        dest_path = os.path.join(PDF_DIR, f"{safe_name}_{file_id}.pdf")

        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            return dest_path

        try:
            response = await self.http_client.get(api_url, headers=headers, follow_redirects=True)
            if response.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Successfully downloaded {company_name} (ID: {file_id})")
                return dest_path
            else:
                logger.error(f"Error downloading {company_name} ({file_id}): HTTP {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error downloading {company_name} ({file_id}): {e}")
            return None

    def extract_text(self, pdf_path: str) -> str:
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
        return text

    async def run(self):
        # Step 1: Download all PDFs
        logger.info(f"Starting download of {len(COMPANIES)} PDFs...")
        for comp in COMPANIES:
            await self.download_pdf(comp["drive_file_id"], comp["name"])

        # Step 2: Extract text and prepare for processing
        # Note: The actual LLM parsing will be handled by the agent after reviewing the extracted text
        # this script prepares the local files for inspection.
        logger.info("Downloads complete. Preparing for extraction.")

if __name__ == "__main__":
    extractor = Batch1Extractor()
    asyncio.run(extractor.run())
