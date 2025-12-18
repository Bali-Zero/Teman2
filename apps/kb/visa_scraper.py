import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger

# Configuration
VISA_URL = "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia"
OUTPUT_DIR = Path("data/immigration")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "visa_imigrasi_info.txt"


# List of Visa URLs found in the page source
VISA_LINKS = [
    # Group A (Bebas Visa)
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/a1-bebas-visa-wisata?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/a36-bebas-visa-kru-alat-angkut-yang-sedang-bertugas?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/a37-bebas-visa-kru-alat-angkut-di-perairan-nusantara?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/a4-bebas-visa-tugas-pemerintahan?golden_visa=0&all=1",
    # Group B (Visa Saat Kedatangan)
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/b1-visa-saat-kedatangan-wisata?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/b4-visa-saat-kedatangan-tugas-pemerintahan?golden_visa=0&all=1",
    # Group C (Visa Kunjungan)
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c1-visa-wisata?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c10-visa-pertemuan-bisnis?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c10a-visa-pemuka-agama?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c11-visa-bisnis-pameran?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c11a-visa-bisnis-pameran-untuk-warga-negara-dari-negara-calling-visa?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c12-visa-pra-investasi?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c13-visa-kru-alat-angkut?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c14-visa-aktivitas-pembuatan-dan-produksi-film?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c15-visa-pekerjaan-darurat?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c16-visa-pelatihan-pelatih-dan-instruktur?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c17-visa-bisnis-audit-dan-inspeksi?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c18-visa-ujicoba-kerja?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c19-visa-bisnis-pelayanan-purnajual?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c2-visa-bisnis?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c20-visa-bisnis-pemasangan-dan-perbaikan-mesin?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c21-visa-proses-peradilan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c22-visa-program-magang?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c22a-visa-program-magang-akademik?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c22b-visa-program-magang-industri-dan-perusahaan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c3-visa-perawatan-kesehatan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c4-visa-tugas-pemerintahan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c5-visa-media-dan-pers?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c6-visa-kegiatan-sosial?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c7-visa-kegiatan-seni-dan-budaya?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c7a-visa-pertunjukan-musik?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c7b-visa-kru-pertunjukan-musik?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c7c-visa-pertunjukan-seni?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c8a-visa-olahraga-atlet?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c8b-visa-olahraga-ofisial?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c9-visa-studi-banding-kursus-dan-pelatihan-singkat?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c9a-visa-studi-kursus-dan-pelatihan-singkat-bidang-keagamaan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/c9b-visa-studi-kursus-dan-pelatihan-singkat-bidang-keagamaan?golden_visa=0&all=1",
    # Group D (Visa Tinggal Terbatas)
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d1-visa-wisata?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d12-visa-pra-investasi?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d14-visa-aktivitas-pembuatan-dan-produksi-film?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d17-visa-bisnis-audit-dan-inspeksi?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d2-visa-bisnis?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d3-visa-perawatan-kesehatan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d7-visa-kegiatan-seni-dan-budaya?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d7a-visa-pertunjukan-musik?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d7b-visa-kru-pertunjukan-musik?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d8a-visa-olahraga-atlet?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d8b-visa-olahraga-ofisial?golden_visa=0&all=1",
    # Group E (Visa Tinggal Terbatas - Investor/Pekerja/Lainnya)
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28a-visa-investor?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28b-visa-investor-pendirian-perusahaan?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28c-visa-investor-tanpa-mendirikan-perusahaan?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28d-visa-investor-pendirian-kantor-cabanganak-perusahaan?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28f-visa-investor-ibukota-negara?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e28g-visa-investor-representatif-perusahaan-induk?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e29-visa-penelitian?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e30a-visa-pelajar?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e30b-visa-pendidikan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31a-visa-keluarga?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31b-visa-keluarga-istrisuami-dari-pemegang-itasitap?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31c-visa-keluarga-anak-dari-ibuayah-wni?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31d-visa-keluarga-anak?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31e-visa-keluarga-anak?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31f-visa-keluarga-anak?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31g-visa-keluarga-orangtua?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31h-visa-keluarga-orangtua?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e31j-visa-keluarga-saudara?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e32a-visa-eks-warga-negara-indonesia?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e32b-visa-eks-warga-negara-indonesia-derajat-1-dan-2?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e32c-visa-eks-warga-negara-indonesia-tinggal-maksimal-2-tahun?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e32d-visa-eks-warga-negara-indonesia-tinggal-maksimal-1-tahun?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33-visa-rumah-kedua?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33a-visa-keahlian-khusus?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33b-visa-keahlian-khusus-tanpa-penjamin?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33c-visa-tokoh-dunia-orang-asing-yang-diundang-oleh-pemerintah-karena-ketokohannya?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33e-visa-lanjut-usia?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33f-visa-lanjut-usia?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33g-visa-pekerja-jarak-jauh?golden_visa=1&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e33g-visa-pengobatan?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/e35-visa-bekerja-dan-berwisata?golden_visa=0&all=1",
    # Group F (Visa Saat Kedatangan)
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/f1-visa-saat-kedatangan-wisata?golden_visa=0&all=1",
    "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/f4-visa-saat-kedatangan-tugas-pemerintahan?golden_visa=0&all=1",
]


async def scrape_visa_page():
    logger.info(f"🚀 Starting Visa Scraper for {len(VISA_LINKS)} pages...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for url in VISA_LINKS:
            try:
                # Generate filename from URL slug
                slug = url.split("/")[-1].split("?")[0]
                filename = f"visa_{slug}.txt"
                file_path = OUTPUT_DIR / filename

                # SKIP IF EXISTS
                if file_path.exists():
                    logger.info(f"⏭️  Skipping {filename} (already exists)")
                    continue

                logger.info(f"📄 Scraping: {url}")
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")

                # Wait for content to settle
                await asyncio.sleep(3)

                # Extract Title
                title = "Unknown Visa"
                try:
                    title_elem = page.locator("h1").first
                    if await title_elem.count() > 0:
                        title = await title_elem.inner_text()
                except:
                    pass

                # Extract Content
                content = await page.inner_text("body")

                # Save to file
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"TITLE: {title}\n")
                    f.write(f"SOURCE: {url}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(content)

                logger.info(f"   ✅ Saved to {filename}")

                # Polite delay only if we actually scraped
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"   ❌ Error scraping {url}: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_visa_page())
