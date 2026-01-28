#!/usr/bin/env python3
"""
enrich_masterpiece.py - The "Vision Factory" Enrichment Layer
-------------------------------------------------------------
Takes the raw JSON from `excel_to_masterpiece.py` and injects:
1. GLOBAL_GEMS (Legal Notices for all KBLI)
2. SECTOR_INTELLIGENCE (Sanctions, Checklists based on 2-digit Code Prefix)

Usage:
    python3 scripts/vision_factory/enrich_masterpiece.py [input_json] [output_json]
"""

import sys
import json
import copy

# --- LOGIC SYNTHESIZED FROM:
# 1. PP Nomor 28 Tahun 2025 (Risk-Based Licensing / OSS RBA High Level Rules)
# 2. Peraturan BPS No 7 Tahun 2025 (KBLI Structure & Descriptions)
# 3. INGUB 6 Tahun 2025 (Bali Moratorium on Modern Retail/Minimarkets)

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
        "title": "Kewajiban Kemitraan (Usaha Besar)",
        "ref": "Art. 188 PP 28/2025",
        "description": "Usaha Besar di sektor ini wajib melakukan kemitraan dengan Koperasi dan/atau Usaha Mikro, Kecil, dan Menengah lokal.",
        "impact": "Kepatuhan",
    },
]

SECTOR_INTELLIGENCE = {

    # AUTOMOTIVE & REPAIR (45)
    "AUTOMOTIVE_SERVICES": {
        "prefixes": ["45"],
        "extra_notices": [
            {
                "title": "Pengelolaan Limbah B3",
                "ref": "PP 22/2021",
                "description": "Bengkel/Service Station wajib memiliki tempat penyimpanan sementara limbah B3 (Oli bekas, aki bekas) dan bekerjasama dengan pengolah limbah berizin.",
                "impact": "Environmental Audit Risk"
            }
        ],
        "sanksi_administratif": {
            "paksaan_pemerintah": "Penghentian sementara kegiatan jika membuang limbah sembarangan.",
            "denda": "Denda administratif lingkungan hidup."
        },
        "intelligence_tags": ["AUTOMOTIVE", "HAZARDOUS_WASTE_POTENTIAL"],
        "checklists_umku": [
            {"requirements": ["SPPL (Surat Pernyataan Kesanggupan Pengelolaan Lingkungan)", "Izin Lokasi"], "sla": "Automated via OSS"}
        ]
    },

    # WHOLESALE TRADE (46)
    "WHOLESALE_TRADE": {
        "prefixes": ["46"],
        "sanksi_administratif": {
            "pencabutan_izin": "Pencabutan izin jika menjual eceran (Breaking Bulk improperly).",
        },
        "intelligence_tags": ["B2B_ONLY", "DISTRIBUTION_NETWORK"],
        "checklists_umku": [
            {"requirements": ["Izin Gudang (TDG)", "Kontrak Distributor/Keagenan"], "sla": "5 Hari"}
        ]
    },
    
    # RETAIL TRADE (47) - Focus on RETAIL & INGUB 6/2025 (Bali Moratorium)
    "RETAIL_TRADE": {
        "prefixes": ["47"],
        "extra_notices": [
             {
                "title": "Moratorium Toko Modern Berjejaring (Bali)",
                "ref": "INGUB Bali No. 6 Tahun 2025",
                "description": "Penghentian sementara pemberian izin baru untuk Toko Modern Berjejaring (Minimarket, Supermarket waralaba) di seluruh Kabupaten/Kota se-Bali.",
                "impact": "CRITICAL - STOP (Zona Merah untuk Izin Baru)"
            },
            {
                "title": "Zonasi Pasar Tradisional",
                "ref": "Perda Bali No. 5 Tahun 2024",
                "description": "Toko modern dilarang beroperasi dalam radius 500m dari Pasar Tradisional/Desa Adat.",
                "impact": "Location Restriction"
            }
        ],
        "sanksi_administratif": {
             "penutupan_paksa": "Penutupan/Penyegelan kegiatan usaha bagi yang melanggar moratorium.",
             "pencabutan_nib": "Pencabutan NIB oleh DPMPTSP atas rekomendasi Satpol PP.",
             "pidana_lingkungan": "Jika melanggar pengelolaan sampah (Pergub Bali 47/2019)."
        },
        "intelligence_tags": ["BALI_MORATORIUM_ACTIVE", "RETAIL_RESTRICTIONS", "FRANCHISE_LIMITATION"],
        "checklists_umku": [
            {
                "requirements": ["PBG (Persetujuan Bangunan Gedung)", "SLF (Sertifikat Laik Fungsi)", "Izin Reklame"],
                "sla": "45 Hari Kerja"
            }
        ]
    },

    # FORESTRY (02) - PP 28/2025 Deep Dive
    "FORESTRY": {
        "prefixes": ["02"],
        "extra_notices": [
            {
                "title": "Kewajiban Reboisasi 1:100",
                "ref": "PP 28/2025 Art 45 (Obligations)",
                "description": "Setiap penebangan pohon (jika terpaksa) wajib diganti dengan menanam 100 anakan pohon lokal/endemik dan dipelihara s.d. 5 tahun.",
                "impact": "High Operational Cost (Hidden)"
            },
            {
                "title": "Dana Jaminan Pemulihan & Bank Garansi",
                "ref": "Art. 99 PP 28/2025",
                "description": "Wajib menempatkan Jaminan Reklamasi Hutan dan Bank Garansi untuk pengangkutan TSL (Tumbuhan Satwa Liar).",
                "impact": "Financial Lock (Cashflow)"
            }
        ],
        "sanksi_administratif": {
            "peringatan_tertulis": "Teguran tertulis via OSS (Maksimal 3 kali).",
            "denda_administratif": "Pembayaran PNBP denda administrasi (Progresif).",
            "penghentian_layanan": "Blokir akses SIPNBP/SIPUHH (Sistem Penatausahaan Hasil Hutan).",
            "pencabutan": "Pencabutan PBPH (Perizinan Berusaha Pemanfaatan Hutan)."
        },
        "checklists_umku": [
            {
              "group": "PENGELOLAAN HUTAN & SATWA",
              "requirements": [
                "Rencana Kerja Usaha (RKU) 10 Tahun",
                "Rencana Kerja Tahunan (RKT)",
                "Sertifikat Standar PHPL (Pengelolaan Hutan Produksi Lestari)",
                "Tenaga Ganis (Tenaga Teknis) Bersertifikat"
              ],
              "sla": "14-45 Hari Kerja",
              "kewajiban": [
                "Laporan Produksi Kayu Bulat",
                "Pembayaran PSDH/DR (Provisi Sumber Daya Hutan)"
              ]
            }
        ],
        "intelligence_tags": [
            "FORESTRY_REFORESTATION_1_100", "HIGH_CAPITAL_INTENSIVE", "MINISTRY_FORESTRY_DIRECT"
        ]
    },
    
    # WOOD & RATTAN INDUSTRY (16) - SPECIALIZED MANUFACTURING
    "WOOD_INDUSTRY": {
        "prefixes": ["16"],
        "extra_notices": [
             {
                "title": "Kewajiban SVLK (Sistem Verifikasi Legalitas Kelestarian)",
                "ref": "Permen LHK No. 8/2021",
                "description": "Wajib memiliki sertifikasi SVLK (V-Legal) untuk memastikan legalitas bahan baku kayu/rotan. Tanpa ini, EKSPOR DILARANG.",
                "impact": "CRITICAL - Export Barrier"
            },
            {
                "title": "Pelaporan RPBBI (Bahan Baku)",
                "ref": "Sistem SIINas / RPBBH",
                "description": "Wajib lapor Rencana Pemenuhan Bahan Baku Industri secara digital. Ketidakcocokan stok fisik vs digital memicu audit.",
                "impact": "High Compliance Risk"
            }
        ],
        "sanksi_administratif": {
             "pembekuan_svlk": "Pembekuan sertifikat legalitas kayu (Operasional Ekspor Stop).",
             "denda": "Denda administratif pelanggaran kapasitas produksi.",
             "pencabutan_nib": "Pencabutan NIB."
        },
        "intelligence_tags": ["SVLK_MANDATORY", "EXPORT_ORIENTED", "RAW_MATERIAL_TRACING"],
        "checklists_umku": [
            {
                "requirements": ["Sertifikat Standar Verifikasi Legalitas (SVLK)", "Izin Gudang (Tanda Daftar Gudang)"],
                "sla": "14 Hari (SVLK via LS Independent)"
            }
        ]
    },

    # AGRICULTURE (01)
    "AGRICULTURE": {
        "prefixes": ["01"],
        "sanksi_administratif": {"peringatan": "Teguran tertulis."},
        "checklists_umku": [],
        "intelligence_tags": ["AGRO_BUSINESS"],
    },
    # INDUSTRY (10-33, excluding 16)
    "INDUSTRY": {
        "prefixes": [str(x) for x in range(10, 34) if x != 16], # 10-33 excluding Wood (16)
        "sanksi_administratif": {
            "peringatan_tertulis": "Peringatan tertulis maksimal 3 kali.",
            "denda": "Denda administratif keterlambatan lapor SIINas.",
            "pencabutan": "Pencabutan izin usaha untuk pelanggaran berat.",
        },
        "checklists_umku": [
            {"requirements": ["Sertifikat Standar", "SPPL/UKL-UPL"], "sla": "Tergantung Risiko"}
        ],
        "intelligence_tags": ["INDUSTRIAL_MANUFACTURING", "SIINAS_REPORTING"],
    },

    # REAL ESTATE (68)
    "REAL_ESTATE": {
        "prefixes": ["68"],
        "extra_notices": [
            {
                "title": "Kewajiban Lapor PPTAT (PPATK)",
                "ref": "UU TPPU (Anti Money Laundering)",
                "description": "Agen Real Estate wajib lapor Transaksi Mencurigakan ke PPATK (GoAML) sebagai Pihak Pelapor.",
                "impact": "High Compliance Risk"
            }
        ],
        "sanksi_administratif": {
            "peringatan": "Peringatan tertulis.",
            "denda": "Denda administratif pelanggaran pelaporan.",
            "pencabutan": "Pencabutan NIB/Sertifikat Standar."
        },
        "checklists_umku": [
             {
                 "group": "BROKERAGE & PROPERTY",
                 "requirements": [
                     "Sertifikat Kompetensi Tenaga Ahli (Broker)",
                     "Keanggotaan Asosiasi (AREBI)",
                     "Sertifikat Standar (OSS)"
                 ],
                 "sla": "14-30 Hari Kerja"
             }
        ],
        "intelligence_tags": ["PROPERTY_MANAGEMENT", "AML_REPORTING_OBLIGATION", "HIGH_VALUE_ASSET"]
    }
}

# --- SPECIAL HIGH RISK CODES (Granular Control) ---
SPECIAL_CODES = {
    # Alcohol Distribution
    "46333": {
        "extra_notices": [
            {"title": "Wajib SKMB (Distributor)", "ref": "Permendag Minol", "description": "Wajib memiliki Surat Keterangan Minuman Beralkohol (SKMB) sebagai Distributor. Gudang harus terpisah dari barang lain.", "impact": "High Compliance"}
        ],
        "intelligence_tags": ["ALCOHOL_CONTROLLED", "HIGH_RISK_DISTRIBUTION"]
    },
    # Alcohol Retail
    "47221": {
        "extra_notices": [
            {"title": "Larangan Konsumsi di Tempat", "ref": "Regulasi Minol Eceran", "description": "Dilarang minum di tempat (kecuali Bar/Resto). Penjualan hanya boleh untuk take-away. Pembeli wajib 21+ tahun.", "impact": "Operational Restriction"},
            {"title": "Separasi Display", "ref": "Aturan Ritel Modern", "description": "Minuman beralkohol tidak boleh dipajang bercampur dengan produk lain. Rak harus khusus/terpisah.", "impact": "Audit Risk"}
        ],
        "intelligence_tags": ["ALCOHOL_RETAIL_RESTRICTED", "STRICT_AGE_VERIFICATION"]
    }
}

def enrich_data(input_path, output_path):
    print(f"💎 Enriching: {input_path}")
    
    with open(input_path, 'r') as f:
        content = json.load(f)
        
    # Handle both list (from mineru_to_masterpiece) and dict (legacy)
    if isinstance(content, list):
        records = content
        is_list_root = True
    else:
        records = content.get("data", [])
        is_list_root = False
        
    enriched_count = 0
    
    for rec in records:
        # Try 'kbli_code' first (mineru format), fall back to 'kode'
        code = rec.get("kbli_code") or rec.get("kode", "")
        # Clean code to find prefix (e.g. "02209" -> "02")
        # Handle cases like " - " or empty
        clean_code = code.replace("-", "").strip()
        if not clean_code or not clean_code[0].isdigit():
            continue
            
        prefix = clean_code[:2]
        # Specific sub-code check (first 5 digits)
        full_code_5 = clean_code[:5]
        
        # 1. Inject Global Gems
        current_legal = rec.get("legal_notices", [])
        existing_titles = set(n["title"] for n in current_legal)
        
        for gem in GLOBAL_GEMS:
            if gem["title"] not in existing_titles:
                current_legal.append(gem)
        rec["legal_notices"] = current_legal
        
        # 2. Inject Sector Intelligence
        matched_sector = None
        for sector, rule in SECTOR_INTELLIGENCE.items():
            if prefix in rule["prefixes"]:
                matched_sector = sector
                
                # Sanksi
                if not rec.get("sanksi_administratif"):
                    rec["sanksi_administratif"] = rule.get("sanksi_administratif", {})
                
                # Checklists (Append/Merge)
                # If vision factory extracted nothing, take the Sector Default
                if not rec.get("checklists_umku"):
                    rec["checklists_umku"] = copy.deepcopy(rule.get("checklists_umku", []))
                    
                # Tags
                tags = rec.get("intelligence_tags", [])
                for tag in rule.get("intelligence_tags", []):
                    if tag not in tags:
                        tags.append(tag)
                rec["intelligence_tags"] = tags
                
                # Extra Notices
                for notice in rule.get("extra_notices", []):
                    if notice["title"] not in [x["title"] for x in rec["legal_notices"]]:
                        rec["legal_notices"].append(notice)
                        
                break
        
        # 3. Inject Special Code Intelligence (Overlay)
        if full_code_5 in SPECIAL_CODES:
            special = SPECIAL_CODES[full_code_5]
            # Add Special Notices
            for notice in special.get("extra_notices", []):
                if notice["title"] not in [x["title"] for x in rec["legal_notices"]]:
                    rec["legal_notices"].insert(0, notice) # High priority
            
            # Add Special Tags
            tags = rec.get("intelligence_tags", [])
            for tag in special.get("intelligence_tags", []):
                if tag not in tags:
                    tags.append(tag)
            rec["intelligence_tags"] = tags
            
            matched_sector = f"{matched_sector} + SPECIAL({full_code_5})"

        if matched_sector:
            rec["intelligence_enrichment"] = f"Sector: {matched_sector}"
            enriched_count += 1
            
    # Wrap list in object if needed to support metadata
    if isinstance(content, list):
        content = {"data": content}
    
    # --- MASTERPIECE V5 SCHEMA NORMALIZATION (INDONESIAN KEYS) ---
    print(f"🔄 Normalizing to Masterpiece V5 (Indonesian Schema)...")
    normalized_records = []
    
    for rec in records:
        norm_rec = {
            "kode": rec.get("kbli_code") or rec.get("kode", "UNKNOWN"),
            "judul": rec.get("title") or rec.get("judul", "No Title"),
            "uraian": rec.get("description") or rec.get("uraian", ""),
            "kategori_resiko": rec.get("risk_level") or rec.get("kategori_resiko", ""),
            "skala_usaha": rec.get("business_scale") or rec.get("skala_usaha", ""),
            "kewenangan": rec.get("authority") or rec.get("kewenangan", ""),
            "perizinan_berusaha": rec.get("licensing_requirements") or rec.get("perizinan_berusaha", ""),
            "persyaratan": rec.get("requirements") or rec.get("persyaratan", ""),
            "kewajiban": rec.get("obligations") or rec.get("kewajiban", ""),
            "jangka_waktu": rec.get("issuance_period") or rec.get("jangka_waktu", ""),
            "sanksi_administratif": rec.get("sanksi_administratif", {}),
            "checklist_umku": rec.get("checklists_umku", []),
            "tags_intel": rec.get("intelligence_tags", []),
            "catatan_hukum": rec.get("legal_notices", []),
            "metadata_sumber": {
                "file_asal": rec.get("source_file", ""),
                "mode_ekstraksi": rec.get("extraction_mode", "")
            },
            "enrichment_info": rec.get("intelligence_enrichment", "")
        }
        
        # Preserve original raw text fields if they exist and aren't mapped
        # (Optional, but good for debugging. For strict schema, maybe exclude?)
        # strict schema = exclude unknown fields.
        
        normalized_records.append(norm_rec)

    content["data"] = normalized_records
    content["schema_version"] = "Masterpiece V5 (Indonesian)"
    content["intelligence_level"] = "Vision Factory V1 + Enrichment (Masterpiece)"
    
    with open(output_path, 'w') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Enriched & Normalized {enriched_count}/{len(records)} records. Saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 enrich_masterpiece.py <input.json> <output.json>")
    else:
        enrich_data(sys.argv[1], sys.argv[2])
