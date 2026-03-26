import os
import httpx
import asyncio

DOWNLOAD_DIR = "data/kb_sources/2026_updates"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Target Laws 2026 — verified URLs (2026-03-23)
# Note: JDIH Kemenkeu blocks curl (SSL timeout), use browser fetch + presigned S3 for Bali
# PP 9/2026 (THR/Gaji 13) does NOT exist on any JDIH portal as of 2026-03-23
TARGETS = {
    "PMK_1_2026_Coretax_System.pdf": "https://jdih.kemenkeu.go.id/api/download/b5f99bff-f689-4e4f-ae3a-7c6a9a4cfe8a/2026pmkeuangan001.pdf",
    "PP_9_2026_THR_Gaji_13.pdf": "MANUAL_DOWNLOAD",  # Source: jdih.setneg.go.id (not indexed when checked, file provided manually)
    "Pergub_Bali_14_2023_RPD_2024_2026.pdf": "REQUIRES_PRESIGNED_S3",  # jdih.baliprov.go.id → S3 presigned URL (expires 600s)
    "SE_Gubernur_Bali_09_2025_Bali_Bersih_Sampah.pdf": "REQUIRES_PRESIGNED_S3",  # jdih.baliprov.go.id → S3 presigned URL
    "UU_1_2023_KUHP_Baru.pdf": "https://peraturan.bpk.go.id/Download/287456/UU%20Nomor%201%20Tahun%202023.pdf",
}
# JDIH detail pages (for browser-based download):
#   PMK 1/2026:  https://jdih.kemenkeu.go.id/dok/pmk-1-tahun-2026
#   Pergub Bali: https://jdih.baliprov.go.id/dokumen-hukum/21bc7914-82a3-4ca6-945f-2cb71293e5d7
#   SE Gub Bali: https://jdih.baliprov.go.id/dokumen-hukum/a1405712-5758-440d-8b15-ec80226192f5
#   UU 1/2023:   https://peraturan.bpk.go.id/Details/234935/uu-no-1-tahun-2023

async def download_file(filename, url):
    print(f"[*] Searching for {filename}...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"[+] Downloaded: {filename}")
            else:
                print(f"[-] JDIH Shield/404 for {filename}. Requires manual CAPTCHA bypass or portal login.")
    except Exception as e:
        print(f"[!] Error fetching {filename}: {str(e)}")

async def main():
    print("=== Nuzantara 2026 Law Hunter ===")
    tasks = [download_file(name, url) for name, url in TARGETS.items()]
    await asyncio.gather(*tasks)
    print("=== Hunt Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
