import asyncio
import json
import logging
import os
from typing import Any

import httpx
import pdfplumber
from google import genai
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataExtractor")

# Constants
RESULTS_DIR = "/Users/nuzantara/Desktop/nuzantara/.gemini/tmp/results"
PDF_DIR = os.path.join(RESULTS_DIR, "pdfs")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "batch_0_results.json")

# Service Account provided by user
SA_JSON = {
  "type": "service_account",
  "project_id": "nuzantara",
  "private_key_id": "28e6087e450988b12db1efa74404b5177676569a",
  "private_key": os.environ.get("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC/5o8b3UHrNDCk\n2UGEq0Q6ikLRigxaolTq9qaajCjZosNex2JpFnTmQGP+BIBcKrroOfxQscAwKBdB\nNol3ui2bSKjUtyRX19nR3PUfudrn8P0gKG1IslLUjXfh/8WwPTavg96+Q7zgb4Ti\ndjlvN/DXH21nxIWVDSgu1LNgrNYgj0hDKOB/1ZABHrvkzD7JC0k9VR3k4GBUokKa\ndwzHfXIuRTU4kyhhrFLrKzB8FpWUsQfnBAGltBKdIZx8h7u6O4HDdHZNwxE5gAGP\nVw9NHU0zYN0p9t7hWBqRmffvPhBfy4Pvga6p8uNIyLaSCLSCTXIRJT+VEdczKgdQ\nOP4hQZSTAgMBAAECggEACy15ddIJc5MdUjzQCCjsVyHpNR3+t44aYXqZxwlq8mJR\n/ESjgs4quPlUhF3sFseWY3hyg0YXP7bWGUJSojACAA2CEqx9ksWhNmF8awCps4uM\nnZbn5q1xuFe/0ot8uatByC9nhgWZYX6dauN1V6PBL4abxMjkTwOZLOvOwaQk73h5\n0PbRvRDsERRo7ilonfB2pVFrk8r6sUpLfxDylItJHVjVJ7GNtCSODqj8KmonFHU6\n7oGcw/QCKxGKG/QktWC+AXjaFSmsNw5hY/yPtVmRFd7Bz4fq9LKPmWO/sQ3KhmAe\nl+CGxSKoqj2lXmjdl3Ipt+82oNMx0TKhNlAL2vU/wQKBgQDyvHRofsT+NVUKExHs\nD6d7TnigoMawAYNv5Z4kdQ104i9tO19uVDch0Nlygp5jzZpYAEhdACLyWPy6Zw2R\nU8A5+osHQkLiZIdIu5GfDKrJ1IoRqSsGIPI4QLpG15ioUxYYrNIioyKE+Brv//1F\nFga6lfMDglHUjSWVBL6SVLK0OQKBgQDKYvwttOHRanh1eCd+UFeawbOQ2zjRZAsZ\nQRzA99KYH98/gP/cXT6tzWVQTOssapxn8EOa+WNKtiuCqmI/OMghdJQ/4GsT3l12\n8n010upvvI7s4YTFwQL4Iwv4TbuzDx/ZbA4msgpeWB/O4ew6jooPDvCFNqmoZpdJ\nMHq5CE3HKwKBgEdpvFG14hzr8d3p6F7r6Bk15/VR98J2X4X/JvyQ12mo1c0sJ5Jd\nAm9Xc3HmDdVM+vii9Kcv0Bg+p/PrN6mm2ynzlQ2IqAbVDpwOWvRRFLoWZpx1iave\n64QzPtpyuX3kG98ckSIRnqlCGSK8zHWT2lzwmrNQluSSthjWcX65nm25AoGBAMJX\nkvkA/OdvagTDQIlW9QiygI/VMxY/DzlNASN71komMOZ2JTuifpG+7k7RzfJ03YQh\nf4nNeL9Bdz6eBoHXMLaPj9xWz/vgR7f02q9Yva5WTpjBZhHPad6FKPVjD56+I0NR\nM7WMudAmp0SuRX1lasVS/zusZfZDrXqmhvIvOyDJAoGBAMOqNcUiKKTpms287HFi\n7Y+5PllroA8iZwo/VO9O7jX1UPDQ7B53An3hsmhHWeqrMu/urJRA7VCeZWebZVCw\nb0eeV5XoxYI4GWH6N6nq8mFtBsA9bHsB8QFvYLbH/qAbrT4swNmF5JbEr1T2LSKg\nLgsJ9cx3DEgrE4M6iJ+7T4i7\n-----END PRIVATE KEY-----\n"),
  "client_email": "nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com",
  "client_id": "107304438107245099867",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/nuzantara-google-drive-sa%40nuzantara.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

COMPANIES = [
    {"company_id": 11, "name": "PT Backtoback Development Group", "drive_file_id": "1hH1olkS9c6s91KhXnxulDUKdL3k3uqFf"},
    {"company_id": 13, "name": "PT Baik dan Bagus Management", "drive_file_id": "1gOujWLEIXSLpocewYBjRB-VIvPA6snED"},
    {"company_id": 18, "name": "PT Bali Akusara Jaya (Adi Ubud)", "drive_file_id": "1KUISCUEATcdF07-jvn5vE0HpNC32t6FR"},
    {"company_id": 300, "name": "PT Elite Interior Project", "drive_file_id": "1nlnlzi9OAigiMc0V6sXyM7VaX2aBz4Gh"},
    {"company_id": 301, "name": "PT Elogic Venture Capital", "drive_file_id": "1-Mgh9fVi6XZTDfyGR5kCwpZXvd5j8t5v"},
    {"company_id": 899, "name": "PT Real Quality Construction", "drive_file_id": "1S1VnQGciWSjx6kh_ic4Btuw8nXJjUEX0"},
    {"company_id": 899, "name": "PT Real Quality Construction", "drive_file_id": "1UHWMkkZ_XDPXZG1gij_dIrIf4DM_VMt6"},
    {"company_id": 996, "name": "PT Shardana West Sumbawa", "drive_file_id": "1VZq4ZrdrFPYUtD-6VjRtAGCFBqNIFqMT"},
    {"company_id": 997, "name": "PT Sheikh Mansur Academy", "drive_file_id": "1DreKntP-pIPhQ8oS08Q2a4R_nvNKtJgx"},
    {"company_id": 1310, "name": "PT Zorrin Video Production", "drive_file_id": "15mGigEHZcJ6TUfy3fs7rIIeCHhH7-HJr"},
    {"company_id": 1310, "name": "PT Zorrin Video Production", "drive_file_id": "1JfS0aiOBd0QKyE-Rt4eYy5l3LStmwNKq"},
    {"company_id": 1360, "name": "PT Bali Invest Group", "drive_file_id": "1AIYIu-BwmHe1TzqdqsicQydkQkAxrfov"},
    {"company_id": 1360, "name": "PT Bali Invest Group", "drive_file_id": "1Fsrh6HNjFqmHyzYjE7qkfUBtj4l6HKn4"},
    {"company_id": 1361, "name": "PT Bali Investment Group", "drive_file_id": "1SE3epjKKTs2Prb6EwLOr3m3zbySTLQp-"},
    {"company_id": 1362, "name": "PT Bali Investment Protocolls", "drive_file_id": "1A86ATmn0TUn1EqfUllSv6JNl81VGW9eF"},
    {"company_id": 1370, "name": "PT Bali Luxury Management", "drive_file_id": "1krp79cI5vbxPwQVZ9-S5SzNbD85fIu1Q"},
    {"company_id": 1371, "name": "PT Bali Mama Food", "drive_file_id": "14WxMJezPDJGTH4IsLhs0MOzy_ynQwid0"},
    {"company_id": 1378, "name": "PT Bali Moon Estate", "drive_file_id": "1SsYrqZnmzupqpoYwe2xhalfL8V1KhoTk"},
    {"company_id": 1381, "name": "PT Bali Nash Group", "drive_file_id": "1Hv821MHOaT2V2e74NoZv1HwQ4JHhVZW3"},
    {"company_id": 1385, "name": "PT Bali Nol Impresariat", "drive_file_id": "1PIbI5_S1TIKH73x-YuW2NaPGd1NrsdCr"},
    {"company_id": 1393, "name": "PT Bali Privilege Ducat", "drive_file_id": "1SdNKCEhBCKSdb4Zaaqjj0Jj4wKip8naI"},
    {"company_id": 1394, "name": "PT Bali Property Consulting", "drive_file_id": "1KbRshwOHN38M5oQBIM7QRK25tvO-Wp8n"},
    {"company_id": 1439, "name": "PT Bao Architecture Collective", "drive_file_id": "12ysJSta7TwVR8Mjv80yBrHCMlYEy75hY"},
    {"company_id": 1439, "name": "PT Bao Architecture Collective", "drive_file_id": "1nLkomDfpzIRYy-tFagxQVq8M2be7vBPM"},
    {"company_id": 1477, "name": "PT Black Mountain Adventures", "drive_file_id": "12vI2Uz5uFv9YmljJRSJiYt1Ua-wi7Fp3"},
    {"company_id": 1483, "name": "PT Bloodmoon Ritual Services", "drive_file_id": "1juCYr-9RGSGknAX0QxzAdMm-O3VfvYkX"},
    {"company_id": 1607, "name": "PT Damao Shine Indonesia", "drive_file_id": "1oK-Ao98StDOYc0Cb5Rf-aqS1zFnoludX"},
    {"company_id": 1612, "name": "PT David Georges Property", "drive_file_id": "17HbYUEfmkqtVxBYdDjPawOuTIx37JKy9"},
    {"company_id": 1613, "name": "PT Davidson Villas Investment", "drive_file_id": "1gDAyOg_3x4jHhOVHfwgZa0jbTGnm88nW"},
    {"company_id": 1629, "name": "PT Dewata Flavor Journey", "drive_file_id": "1H_vHuLe62XcwNnya9kpHLFKkgn9yNI4S"},
    {"company_id": 1638, "name": "PT Disruptives Idea Indonesia", "drive_file_id": "1A0nzHMOja3r5Yt3nzuUKizs6Vlj53uH9"},
    {"company_id": 1645, "name": "PT Domus Dei Amare", "drive_file_id": "1m21Ajp472nGoaH-kcMBO89WG9xokQkWk"},
    {"company_id": 1712, "name": "PT Ettore Gelato Bali", "drive_file_id": "16058cdn80JnLVnVuaJK6l_Ky8fHb_lOZ"},
    {"company_id": 1716, "name": "PT Everis Investment Group", "drive_file_id": "1a75lkYyvbrPnrLmRbc9s6UdffZPYe24n"},
    {"company_id": 1728, "name": "PT Fak Team Apparel", "drive_file_id": "1plhhb6guGzogm6J9g-mTYAa5BHuJKi2p"},
    {"company_id": 1736, "name": "PT Fave Jaya Residences", "drive_file_id": "1ZGUpQ4lK5-uwszlmzGKsYdPASad2OVDI"},
    {"company_id": 1739, "name": "PT Fillup Today Bali", "drive_file_id": "1EyIYCmeW1o37N8dHOIUHXlCmQTY_bbZW"},
    {"company_id": 1739, "name": "PT Fillup Today Bali", "drive_file_id": "1M-ifHOz0gROz98FQYBO78VdCRS2LtVJB"},
    {"company_id": 1745, "name": "PT Five Elements Hospitality", "drive_file_id": "1phZ469q-W77CDfLDcMzjPV0bXpIL8fbo"},
    {"company_id": 1745, "name": "PT Five Elements Hospitality", "drive_file_id": "1T7Jtsz7NHF9MleKjRADN-73cPIh3C9_w"},
    {"company_id": 1755, "name": "PT Forever Ink Tattoo Studio", "drive_file_id": "1AW3cjUQd-lHSQDWc_JPSUCq5OT8qe2f6"},
    {"company_id": 1759, "name": "PT Foundry Brands Collective", "drive_file_id": "1458F9H-65kor6tHwxxYehSv03mxGIKss"},
    {"company_id": 1760, "name": "PT Fouram Active Wear", "drive_file_id": "1POrev1sllRmdt3CJxXeKYmmxqoWdhVxh"},
    {"company_id": 1761, "name": "PT Fov Investment Solution", "drive_file_id": "1RGKChW6jjC_Mi3bQP_n383U81O0k-Xee"},
    {"company_id": 1764, "name": "PT Friends and Family", "drive_file_id": "1_wZCtiKsTgjCDGgKUIgGRZjtM9rHUykD"},
    {"company_id": 1890, "name": "PT INDICO NATURAL LIVING", "drive_file_id": "19H9sKry1GhdjZvF0K9raI0k2eiXMXzMi"},
    {"company_id": 1890, "name": "PT INDICO NATURAL LIVING", "drive_file_id": "1chMcDhQWm3PMY5mBsYLrLWDdAvQyP78Y"},
    {"company_id": 1904, "name": "PT Indo Investments Bali", "drive_file_id": "1BRlGdsXPYcwYOwYC3syqubF14pobEng0"},
    {"company_id": 1976, "name": "PT Jro Kayun Consulting", "drive_file_id": "1xqeZEclg6BrMdRV4eht9Zh4jZCC4YCv_"},
    {"company_id": 1978, "name": "PT Jungle Dream House", "drive_file_id": "10cCP1NVnQgEXSVx0Ictg32WbGj7kiTEF"},
    {"company_id": 1978, "name": "PT Jungle Dream House", "drive_file_id": "1535_JarebihhmzLIK1OiybrkSJSjNnfI"},
    {"company_id": 1978, "name": "PT Jungle Dream House", "drive_file_id": "1CZWFn3_xzDycWXMru_B0v4piBOF-H6bh"},
    {"company_id": 1978, "name": "PT Jungle Dream House", "drive_file_id": "1PiDR9K4WPKkscM-h_50LFYySG8Sw63No"},
    {"company_id": 2004, "name": "PT Karya Mandiri Explorers", "drive_file_id": "138eIB8Egc1nqWCp2YxJhtnSTfK5ZpkxO"},
    {"company_id": 2004, "name": "PT Karya Mandiri Explorers", "drive_file_id": "1iCKxkhTZ6kgH6I1agHOn1rC3BVZOgFXC"},
    {"company_id": 2004, "name": "PT Karya Mandiri Explorers", "drive_file_id": "1r3c3WmS0pTpGDI-pncPP70NZj3hdZ99U"},
    {"company_id": 2009, "name": "PT Kavo Maison Bali", "drive_file_id": "129FrcHIwEdOyeDsmBOvczXnKMPlgy9H8"},
    {"company_id": 2010, "name": "PT Kaya Spa Grup", "drive_file_id": "1aShcSMKv8114qYzH0rgmfLpY4sT2VeF2"},
    {"company_id": 2016, "name": "PT Kembar Digital Indonesia", "drive_file_id": "1dPIrRVPxjQRL7Sgccj0y07ia1ci6B51U"},
    {"company_id": 2031, "name": "PT Koi Gold Fish", "drive_file_id": "1T4P0QrK2hL4ukdsUNSaUY1jbAFK5OeSg"},
    {"company_id": 2033, "name": "PT Kole International Trader", "drive_file_id": "1_4GR-CZ8rut7IHYMxmKVeD8F0-55YUxe"},
    {"company_id": 2033, "name": "PT Kole International Trader", "drive_file_id": "1Kn7TVFvBI7XssfgMzc1MeS8Sbr5OMxBH"},
    {"company_id": 2033, "name": "PT Kole International Trader", "drive_file_id": "1N7zOr11t-3vjRKIZm1M3tO_S9I8V_U_i"},
    {"company_id": 2037, "name": "PT Konsultasi Modal Sehat", "drive_file_id": "1-qEiD5eRynZLylVqUSOT6r7DnsxVGTtz"},
    {"company_id": 2041, "name": "PT Kris Investment And Trade", "drive_file_id": "1qG6Zh3DB7JqFv7jkNdtt7JokJNacgEDR"},
    {"company_id": 2042, "name": "PT Kuat Investment Consulting", "drive_file_id": "14wJm6YwZYxwwrqB_On0PovGbQk5gYwpw"},
    {"company_id": 2042, "name": "PT Kuat Investment Consulting", "drive_file_id": "1QM93jO71kgYwzLBgmb0x_VUT4jP2PuXu"},
    {"company_id": 2043, "name": "PT Kuat Solution Bali", "drive_file_id": "1atx-Xg5yd0gKFbJvAptj8vV1QuiKtcUz"},
    {"company_id": 2043, "name": "PT Kuat Solution Bali", "drive_file_id": "1mMM_1WylPqO8L6RBm3LuWYKaNchtEYUc"},
    {"company_id": 2043, "name": "PT Kuat Solution Bali", "drive_file_id": "1uwjX_3eAUyZkJFALHyI6BUdXRIOGSxGY"},
    {"company_id": 2048, "name": "PT Kuta Mandalika Group", "drive_file_id": "1fCirpeD2bpQzIDYcfvirmJaZrh79MFjk"},
    {"company_id": 2048, "name": "PT Kuta Mandalika Group", "drive_file_id": "1rkhz7kMCrs7sWXX7cEzXyUn_QEKllop7"},
    {"company_id": 2048, "name": "PT Kuta Mandalika Group", "drive_file_id": "1WX8WRNGgTouhjUxgIfR6lVZYT_sh8ciR"},
    {"company_id": 2048, "name": "PT Kuta Mandalika Group", "drive_file_id": "1ZED0svMKPIcp0qZgBaADlRhbGyqxk-jD"},
    {"company_id": 2053, "name": "PT LYKIN", "drive_file_id": "1j-euIfx1zzRBlvKyRmvtYyM94Ty_u1GM"},
    {"company_id": 2053, "name": "PT LYKIN", "drive_file_id": "1lyT6QrxokWTOnkK7UbPhzDDp4Ms7mjS-"},
]

class PDFExtractor:
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("Missing GOOGLE_API_KEY in environment")

        # Use Gemini via new Google GenAI SDK
        self.client = genai.Client(api_key=self.google_api_key)
        self.scopes = ["https://www.googleapis.com/auth/drive"]

    async def get_token(self) -> str | None:
        """Direct Service Account token retrieval."""
        try:
            from google.auth.transport.requests import Request as GoogleAuthRequest
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_info(
                SA_JSON, scopes=self.scopes
            )
            credentials.refresh(GoogleAuthRequest())
            return credentials.token
        except Exception as e:
            logger.error(f"Failed to get Google Token: {e}")
            return None

    async def download_pdf(self, file_id: str, company_name: str) -> str | None:
        token = await self.get_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        safe_name = "".join([c if c.isalnum() else "_" for c in company_name])
        dest_path = os.path.join(PDF_DIR, f"{safe_name}_{file_id}.pdf")

        if os.path.exists(dest_path):
            return dest_path

        try:
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            logger.info(f"Downloaded PDF for {company_name}")
            return dest_path
        except Exception as e:
            logger.error(f"Error downloading {company_name} ({file_id}): {e}")
            return None

    def extract_text(self, pdf_path: str) -> str:
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
        return text

    async def parse_with_gemini(self, text: str, company_id: int) -> dict[str, Any]:
        prompt = f"""
Extract structured data from this Indonesian "Profil Perseroan" PDF text.
Constraint: Indonesian numbers: "10.001.000.000" = 10001000000.
Constraint: ownership_percentage MUST BE 0-100.
Constraint: Return ONLY valid JSON.

TEXT:
{text}
"""
        try:
            # Define schema as a dict for Gemini structured output
            schema = {
                "type": "OBJECT",
                "properties": {
                    "company_id": {"type": "INTEGER"},
                    "total_authorized_capital": {"type": "NUMBER"},
                    "share_nominal_value": {"type": "NUMBER"},
                    "kbli_codes": {"type": "STRING"},
                    "shareholders": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING"},
                                "role": {"type": "STRING"},
                                "shares_count": {"type": "NUMBER"},
                                "ownership_percentage": {"type": "NUMBER"}
                            },
                            "required": ["name", "role", "shares_count", "ownership_percentage"]
                        }
                    }
                },
                "required": ["company_id", "total_authorized_capital", "share_nominal_value", "kbli_codes", "shareholders"]
            }

            response = self.client.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=schema
                )
            )

            data = json.loads(response.text)
            data["company_id"] = company_id # Ensure it's the correct ID
            return data
        except Exception as e:
            logger.error(f"Error parsing with Gemini for company {company_id}: {e}")
            return {"company_id": company_id, "error": str(e)}

    async def process_company(self, company: dict[str, Any]) -> dict[str, Any]:
        pdf_path = await self.download_pdf(company["drive_file_id"], company["name"])
        if not pdf_path:
            return {"company_id": company["company_id"], "name": company["name"], "error": "Download failed"}

        text = self.extract_text(pdf_path)
        if not text:
            return {"company_id": company["company_id"], "name": company["name"], "error": "Text extraction failed"}

        data = await self.parse_with_gemini(text[:15000], company["company_id"])
        return data

    async def run(self):
        results = []
        for i in range(0, len(COMPANIES), 5):
            batch = COMPANIES[i:i+5]
            tasks = [self.process_company(c) for c in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            logger.info(f"Processed batch {i//5 + 1}/{(len(COMPANIES)-1)//5 + 1}")
            await asyncio.sleep(0.5)

        with open(OUTPUT_FILE, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved total {len(results)} results to {OUTPUT_FILE}")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Missing GOOGLE_API_KEY")
        exit(1)
    extractor = PDFExtractor()
    asyncio.run(extractor.run())
