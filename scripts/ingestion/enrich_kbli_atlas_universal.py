import json

# Paths
ATLAS_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_final.json"

GLOBAL_GEMS = [
    {
        "title": "Fiktif Positif / Silence is Consent",
        "ref": "Art. 225 PP 28/2025",
        "description": "Jika verifikasi tidak selesai dalam jangka waktu NSPK, sistem OSS menganggap permohonan disetujui secara otomatis.",
        "impact": "Tinggi - Mengurangi hambatan administratif.",
    },
    {
        "title": "Perlindungan dari Birokrasi Daerah",
        "ref": "Art. 6 PP 28/2025",
        "description": "Pemerintah Daerah dilarang menambah persyaratan perizinan di luar yang telah ditetapkan dalam PP 28/2025.",
        "impact": "Perlindungan Hukum - Melindungi pelaku usaha dari hambatan birokrasi tidak standar.",
    },
    {
        "title": "Keterbukaan Modal Asing (PMA)",
        "ref": "Investment Priority 2025",
        "description": "Berdasarkan kategori Skala Besar, KBLI ini diprioritaskan untuk Penanaman Modal Asing dengan kepemilikan mayoritas atau penuh.",
        "impact": "Investasi - Sangat cocok untuk pendirian PT PMA.",
    },
    {
        "title": "Fasilitas Pabean & Impor",
        "ref": "Art. 235 PP 28/2025",
        "description": "Pelaku usaha dapat mengajukan pembebasan bea masuk atas impor mesin dan barang modal melalui sistem OSS.",
        "impact": "Investasi - Pengurangan pajak signifikan perolehan aset industri.",
    },
    {
        "title": "Kewajiban Kemitraan",
        "ref": "Art. 188 PP 28/2025",
        "description": "Usaha Besar di sektor ini wajib melakukan kemitraan dengan Koperasi dan/atau Usaha Mikro, Kecil, dan Menengah lokal.",
        "impact": "Kepatuhan - Memerlukan struktur hukum yang melibatkan entitas lokal.",
    },
]

SECTOR_INTELLIGENCE = {
    "INDUSTRY": {
        "prefixes": [
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "20",
            "21",
            "22",
            "23",
            "24",
            "25",
            "26",
            "27",
            "28",
            "29",
            "30",
            "31",
            "32",
            "33",
        ],
        "extra_notices": [
            {
                "title": "Wajib SNI",
                "ref": "UU Perindustrian",
                "description": "Produk industri wajib memenuhi Standar Nasional Indonesia (SNI) yang berlaku secara wajib.",
                "impact": "Compliance",
            },
            {
                "title": "Penyampaian Data Industri (SIINas)",
                "ref": "PP 28/2021",
                "description": "Pelaku usaha industri wajib menyampaikan data industri melalui SIINas setiap semester.",
                "impact": "Reporting",
            },
        ],
        "sanksi_administratif": {
            "peringatan_tertulis": "Peringatan tertulis maksimal 3 kali.",
            "denda": "Denda administratif keterlambatan lapor SIINas.",
            "pembekuan": "Pembekuan IUI jika tidak mematuhi standar lingkungan (AMDAL/UKL-UPL).",
            "pencabutan": "Pencabutan izin usaha untuk pelanggaran berat atau pidana industri.",
        },
        "checklists_umku": [
            {
                "requirements": [
                    "Sertifikat Standar",
                    "Sertifikat Halal (jika Makanan/Minuman)",
                    "SPPL/UKL-UPL",
                ],
                "sla": "Tergantung Risiko",
            }
        ],
    },
    "CONSTRUCTION": {
        "prefixes": ["41", "42", "43"],
        "extra_notices": [
            {
                "title": "Sertifikat Badan Usaha (SBU)",
                "ref": "UU Jasa Konstruksi",
                "description": "Wajib memiliki SBU dan tenaga ahli bersertifikat (SKA/SKT).",
                "impact": "Licensing",
            },
            {
                "title": "K3 Konstruksi",
                "ref": "SMK3",
                "description": "Wajib menerapkan Sistem Manajemen Keselamatan dan Kesehatan Kerja.",
                "impact": "Safety",
            },
        ],
        "sanksi_administratif": {
            "peringatan": "Teguran tertulis.",
            "denda": "Denda keterlambatan proyek atau pelanggaran K3.",
            "blacklist": "Masuk daftar hitam tender pemerintah (Blacklist LPSE).",
        },
        "checklists_umku": [
            {
                "requirements": [
                    "SBU Konstruksi",
                    "Sertifikat K3",
                    "PBG (Persetujuan Bangunan Gedung)",
                ],
                "sla": "14-30 Hari",
            }
        ],
    },
    "TRADE": {
        "prefixes": ["45", "46", "47"],
        "extra_notices": [
            {
                "title": "Perlindungan Konsumen",
                "ref": "UU Perlindungan Konsumen",
                "description": "Wajib menjamin hak konsumen dan layanan purna jual.",
                "impact": "Compliance",
            },
            {
                "title": "Label Bahasa Indonesia",
                "ref": "Permendag",
                "description": "Barang beredar wajib mencantumkan label berbahasa Indonesia.",
                "impact": "Labeling",
            },
        ],
        "sanksi_administratif": {
            "peringatan": "Peringatan tertulis.",
            "penarikan_barang": "Perintah penarikan barang dari peredaran.",
            "pencabutan": "Pencabutan SIUP.",
        },
        "checklists_umku": [
            {
                "requirements": ["Sertifikat Distribusi", "Izin Edar (jika relevan)"],
                "sla": "Otomatis (Risiko Rendah)",
            }
        ],
    },
    "TRANSPORT": {
        "prefixes": ["49", "50", "51", "52", "53"],
        "extra_notices": [
            {
                "title": "Standar Keselamatan (SPM)",
                "ref": "PM Perhubungan",
                "description": "Wajib memenuhi Standar Pelayanan Minimal angkutan.",
                "impact": "Safety",
            },
            {
                "title": "Uji Kir",
                "ref": "UU LLAJ",
                "description": "Kendaraan angkutan wajib uji berkala (KIR).",
                "impact": "Operational",
            },
        ],
        "sanksi_administratif": {
            "pembekuan_operasi": "Pembekuan izin trayek/operasi.",
            "denda": "Sanksi denda pelanggaran ODOL (Over Dimension Over Load).",
        },
        "checklists_umku": [
            {
                "requirements": ["Izin Penyelenggaraan Angkutan", "Kartu Pengawasan"],
                "sla": "Variatif",
            }
        ],
    },
    "TOURISM": {
        "prefixes": ["55", "56"],
        "extra_notices": [
            {
                "title": "Sertifikasi CHSE",
                "ref": "Kemenparekraf",
                "description": "Disarankan memiliki sertifikasi Cleanliness, Health, Safety, and Environment.",
                "impact": "Quality",
            },
            {
                "title": "Standar Usaha Pariwisata",
                "ref": "Permenpar",
                "description": "Wajib memenuhi standar usaha pariwisata sesuai bintang/kelas.",
                "impact": "Licensing",
            },
        ],
        "sanksi_administratif": {
            "teguran": "Teguran tertulis 1-3.",
            "pembekuan": "Pembekuan sementara kegiatan usaha.",
            "pencabutan": "Pencabutan TDUP.",
        },
        "checklists_umku": [
            {
                "requirements": [
                    "Sertifikat Laik Sehat",
                    "Sertifikat Standar Usaha Pariwisata",
                ],
                "sla": "Verifikasi",
            }
        ],
    },
}


def enrich_universal_v2_gems():
    print("💎 INJECTING UNIVERSAL SECTOR INTELLIGENCE (V2 'THE 7 GEMS')...")

    atlas = json.load(open(ATLAS_PATH))
    universe = atlas["data"]

    stats = {k: 0 for k in SECTOR_INTELLIGENCE.keys()}
    global_enriched = 0

    for code, record in universe.items():
        # Inject Global Gems for everyone (Regulated Only?)
        # Actually Global Gems apply to all Business Activities in Indonesia under OSS RBA
        # So we inject them into ALL records in the Atlas

        current_notices = record.get("legal_notices", [])
        if not current_notices:
            current_notices = []

        # Check if Gems already exist to avoid dupe
        existing_titles = set(n["title"] for n in current_notices)

        # Add Global Gems
        for gem in GLOBAL_GEMS:
            if gem["title"] not in existing_titles:
                current_notices.append(gem)

        record["legal_notices"] = current_notices
        record["intelligence_version"] = "2.0 (The 7 Gems)"
        global_enriched += 1

        # Sector Specifics
        prefix = code[:2]
        target_sector = None
        for sec_name, rules in SECTOR_INTELLIGENCE.items():
            if prefix in rules["prefixes"]:
                target_sector = sec_name
                break

        if target_sector:
            rules = SECTOR_INTELLIGENCE[target_sector]

            # Inject Extra Notices
            for extra in rules.get("extra_notices", []):
                if extra["title"] not in existing_titles:
                    record["legal_notices"].append(extra)

            # Inject Sanksi (If missing)
            if (
                "sanksi_administratif" not in record
                or not record["sanksi_administratif"]
            ):
                record["sanksi_administratif"] = rules["sanksi_administratif"]

            # Inject Checklists (If missing)
            if "checklists_umku" not in record or not record["checklists_umku"]:
                record["checklists_umku"] = rules["checklists_umku"]

            # Tag as Enriched
            if "intelligence_tags" not in record:
                record["intelligence_tags"] = []
            tag = f"SECTOR_RULES_{target_sector}"
            if tag not in record["intelligence_tags"]:
                record["intelligence_tags"].append(tag)

            stats[target_sector] += 1

    # Save
    with open(ATLAS_PATH, "w") as f:
        json.dump(atlas, f, indent=2)

    print("💎 Gems Injection Complete.")
    print(f"   - Global Gems Applied to: {global_enriched} Codes")
    for sec, count in stats.items():
        print(f"   - {sec} Specifics: {count} Codes")
    print(f"💾 Updated: {ATLAS_PATH}")


if __name__ == "__main__":
    enrich_universal_v2_gems()
