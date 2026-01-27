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
    # TRADE (47) - Focus on RETAIL & INGUB 6/2025 (Bali Moratorium)
    "TRADE": {
        "prefixes": ["47"],
        "extra_notices": [
             {
                "title": "Moratorium Toko Modern Berjejaring (Bali)",
                "ref": "INGUB Bali No. 6 Tahun 2025",
                "description": "Penghentian sementara pemberian izin baru untuk Toko Modern Berjejaring (Minimarket, Supermarket waralaba) di seluruh Kabupaten/Kota se-Bali. Berlaku untuk: Alfamart, Indomaret, Circle K, dan brand franchise global.",
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
                "title": "Larangan Pembukaan Lahan Gambut",
                "ref": "PP 57/2016 jo PP 28/2025 Art 45",
                "description": "Dilarang keras melakukan pembukaan lahan baru di area ekosistem gambut dengan fungsi lindung.",
                "impact": "Criminal Sanction (Pidana)"
            },
            {
                "title": "Dana Jaminan Pemulihan (Reklamasi)",
                "ref": "Art. 99 PP 28/2025",
                "description": "Pelaku usaha wajib menempatkan Dana Jaminan Reklamasi Hutan sebelum operasi produksi dimulai.",
                "impact": "Financial Requirement (High Cost)"
            }
        ],
        # ... (sanksi defaults kept below)
            {
                "title": "Sanksi Blokir Layanan Pemerintah",
                "ref": "Art. 367 PP 28/2025",
                "description": "Pelanggaran administrasi di sektor kehutanan dapat mengakibatkan penghentian layanan pemerintah secara digital (OSS/SIPSPLH).",
                "impact": "Kritikal (Operasional Berhenti)"
            },
            {
                "title": "Kewajiban SVLK",
                "ref": "Permen LHK No. 8/2021",
                "description": "Seluruh produk kayu wajib memiliki Sertifikat Verifikasi Legalitas dan Kelestarian.",
                "impact": "Ekspor & Perdagangan"
            }
        ],
        "sanksi_administratif": {
            "peringatan_tertulis": "Teguran tertulis via OSS (Maksimal 3 kali).",
            "denda_administratif": "Pembayaran PNBP denda administrasi sesuai tingkat kerusakan/pelanggaran.",
            "penghentian_layanan": "Penghentian layanan pemerintah (SIPSPLH/OSS) secara sementara.",
            "pencabutan": "Pencabutan Izin (PBPH/Persetujuan Lingkungan)."
        },
        "checklists_umku": [
            {
              "group": "PENGELOLAAN SATWA & TUMBUHAN (TSL/CITES)",
              "requirements": [
                "Legalitas Asal Usul Induk/Benih",
                "Rencana Pengelolaan Satwa (RPS)",
                "Prasarana Kandang/Fasilitas Medik Veteriner",
                "Sertifikat Kompetensi Tenaga Ahli"
              ],
              "sla": "14-20 Hari Kerja",
              "kewajiban": [
                "Laporan Studbook/Logbook Satwa",
                "Penandaan (Tagging/Microchip) Satwa",
                "Health Certificate dari Karantina/BKSDA"
              ]
            }
        ],
        "intelligence_tags": [
            "WILDLIFE_CITES_COMPLIANCE", "FORESTRY_CRITICAL_RISK", "MINISTERIAL_DIRECT_AUTHORITY"
        ]
    },
    # AGRICULTURE (01)
    "AGRICULTURE": {
        "prefixes": ["01"],
        "sanksi_administratif": {"peringatan": "Teguran tertulis."},
        "checklists_umku": [],
        "intelligence_tags": ["AGRO_BUSINESS"],
    },
    # INDUSTRY (10-33)
    "INDUSTRY": {
        "prefixes": [str(x) for x in range(10, 34)], # 10-33
        "sanksi_administratif": {
            "peringatan_tertulis": "Peringatan tertulis maksimal 3 kali.",
            "denda": "Denda administratif keterlambatan lapor SIINas.",
            "pencabutan": "Pencabutan izin usaha untuk pelanggaran berat.",
        },
        "checklists_umku": [
            {"requirements": ["Sertifikat Standar", "SPPL/UKL-UPL"], "sla": "Tergantung Risiko"}
        ],
        "intelligence_tags": ["INDUSTRIAL_MANUFACTURING", "SIINAS_REPORTING"],
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
                
        if matched_sector:
            rec["intelligence_enrichment"] = f"Sector: {matched_sector}"
            enriched_count += 1
            
    content["intelligence_level"] = "Vision Factory V1 + Enrichment (Masterpiece)"
    
    with open(output_path, 'w') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Enriched {enriched_count}/{len(records)} records. Saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 enrich_masterpiece.py <input.json> <output.json>")
    else:
        enrich_data(sys.argv[1], sys.argv[2])
