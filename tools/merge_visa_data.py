import re
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# [TRANSLATIONS and ZANTARA_PRICES remain identical]
TRANSLATIONS = {
    "Bebas Visa": "Visa Free", "Visa Kunjungan": "Visit Visa", "Visa Kerja": "Working Visa",
    "Visa Investor": "Investor Visa", "Visa Pendidikan": "Education Visa", "Visa Keluarga": "Family Visa",
    "Visa Repatriasi": "Repatriation Visa", "Keturunan EX-WNI": "Former Indonesian Citizen Descendant",
    "Visa Rumah Kedua": "Second Home Visa", "Visa Kemudahan Bekerja Saat Berlibur": "Working Holiday Visa",
    "Wisata": "Tourism", "Bisnis": "Business", "Perawatan Kesehatan": "Medical Treatment",
    "Penugasan Pemerintah": "Government Assignment", "Kru Kapal dan Pesawat": "Ship and Aircraft Crew",
    "Kru Kapal di Perairan Indonesia": "Ship Crew in Indonesian Waters", "Konten Kreator": "Content Creator",
    "Kegiatan Sosial": "Social Activity", "Penampilan Seni e Budaya": "Arts and Culture Performance",
    "Penampilan Musik": "Music Performance", "Kru Penampilan Musik": "Music Performance Crew",
    "Penampilan Bakat e Seni": "Talent and Arts Performance", "Kegiatan Olahraga": "Sports Activity",
    "Atlet Olahraga": "Athlete", "Ofisial Olahraga": "Sports Official", "Studi Singkat": "Short Study",
    "Pelatihan Singkat Keagamaan": "Short Religious Training", "Pelatihan Singkat Bahasa Indonesia": "Short Indonesian Language Training",
    "Narasumber Kegiatan Bisnis": "Business Speaker", "Penceramah Agama": "Religious Lecturer",
    "Promosi Produk e Jasa": "Product and Service Promotion", "Pra-Investasi": "Pre-Investment",
    "Awak Bergabung con Alat Angkut": "Crew Joining a Transport Vehicle", "Pembuatan e Produksi Film": "Film Production",
    "Penanganan Keadaan Darurat": "Emergency Handling", "Instruktur Pengembangan Industri": "Industrial Development Instructor",
    "Audit, Kendali Mutu, e Inspeksi Perusahaan": "Audit, Quality Control, and Company Inspection",
    "Uji Kemampuan Tenaga Kerja Asing": "Foreign Worker Competency Test", "Layanan Purna Jual": "After-Sales Service",
    "Pemasangan e Perbaikan Mesin": "Machinery Installation and Repair", "Menghadiri Process Peradilan": "Attending Judicial Proceedings",
    "Pemagangan": "Internship", "Pemagangan Akademik": "Academic Internship", "Pemagangan Kompetensi": "Competency Internship",
    "Kawasan Ekonomi Khusus": "Special Economic Zone", "Asisten Rumah Tangga Diplomat Asing": "Foreign Diplomat House Assistant",
    "Kantor Dagang e Ekonomi": "Trade and Economic Office", "Tenaga Ahli Pemerintah Indonesia": "Indonesian Government Expert",
    "Tenaga Ahli Bidang Digital": "Digital Field Expert", "Komisaris e Eksekutif Perusahaan": "Company Commissioner and Executive",
    "Komisaris Perusahaan": "Company Commissioner", "Direktur Perusahaan": "Company Director",
    "Wakil Direktur Perusahaan": "Company Deputy Director", "Manajer Umum Perusahaan": "Company General Manager",
    "Manajer Perusahaan": "Company Manager", "Supervisor Perusahaan": "Company Supervisor",
    "Awak Kapal, Alat Apung, e Instalasi Lepas Pantai": "Ship Crew, Floating Equipment, and Offshore Installation",
    "Rohaniwan": "Cleric", "Peneliti": "Researcher", "Pendirian Perusahaan": "Company Establishment",
    "Pasar Modal": "Capital Market", "Pendirian Cabang o Anak Perusahaan": "Branch or Subsidiary Establishment",
    "Ibu Kota Nusantara": "Indonesian New Capital (IKN)", "Perwakilan Perusahaan Induk": "Parent Company Representative",
    "Pendidikan Dasar e Menengah": "Primary and Secondary Education", "Pendidikan Tinggi": "Higher Education",
    "Pertukaran Pelajar": "Student Exchange", "Suami/Istri WNI": "Spouse of Indonesian Citizen",
    "Suami/Istri Pemegang ITAS/ITAP": "Spouse of ITAS/ITAP Holder", "Anak Hasil Perkawinan Sah WNA-WNI": "Child of Legal Mixed Marriage",
    "Anak Bawaan WNA Perkawinan Sah WNA-WNI": "Stepchild of Foreigner in Legal Mixed Marriage",
    "Anak Pemegang ITAS/ITAP": "Child of ITAS/ITAP Holder", "Anak con Orang Tua WNI": "Child with Indonesian Parent",
    "Orang Tua dari Anak WNI": "Parent of Indonesian Child", "Orang Tua dari Anak Pemegang ITAS/ITAP": "Parent of ITAS/ITAP Holder Child",
    "Anak yang Bergabung con Saudara Kandung Pemegang ITAS/ITAP": "Child Joining Sibling ITAS/ITAP Holder",
    "Tinggal Tetap": "Permanent Residence", "Keahlian Khusus": "Special Expertise", "Tokoh Dunia": "World Figure",
    "Undangan Pemerintah": "Government Invitation", "Lansia Untuk 5 Tahun": "Elderly for 5 Years",
    "Lansia Untuk 1 Tahun": "Elderly for 1 Year", "Pekerja Jarak Jauh": "Remote Worker / Digital Nomad",
}

def translate_name(name):
    translated = name
    for indo, eng in TRANSLATIONS.items():
        translated = re.sub(indo, eng, translated, flags=re.IGNORECASE)
    return translated

ZANTARA_PRICES = {
    "C1": "2.300.000", "C2": "3.600.000", "C7": "4.500.000", "C7AB": "4.500.000",
    "C18": "5.500.000", "C22A": "4.800.000", "C22B": "4.800.000", "D12": "7.500.000",
    "E23": "34.500.000 (Offshore) / 36.000.000 (Onshore)", "E23-FREELANCE": "25.800.000 (Offshore) / 27.500.000 (Onshore)",
    "E33G": "13.000.000 (Offshore) / 14.000.000 (Onshore)", "E28A": "17.000.000 (Offshore) / 19.000.000 (Onshore)",
    "E31A": "11.000.000 (1 Year) / 15.000.000 (2 Years)", "E31B": "11.000.000 (1 Year) / 15.000.000 (2 Years)",
    "E31F": "11.000.000 (1 Year) / 15.000.000 (2 Years)", "E33E": "14.000.000 (Offshore) / 16.000.000 (Onshore)",
    "E33F": "14.000.000 (Offshore) / 16.000.000 (Onshore)", "E35": "Contact for Quote",
    "KITAP-INVESTOR": "55.000.000", "KITAP-FAMILY": "33.000.000", "KITAP-RETIREMENT": "45.000.000",
    "EPO": "700.000", "ERP": "800.000", "SKTT": "1.500.000", "DOMICILE": "800.000",
}

def translate_name(name):
    translated = name
    for indo, eng in TRANSLATIONS.items():
        translated = re.sub(indo, eng, translated, flags=re.IGNORECASE)
    return translated

ZANTARA_PRICES = {
    "C1": "2.300.000", "C2": "3.600.000", "C7": "4.500.000", "C7AB": "4.500.000",
    "C18": "5.500.000", "C22A": "4.800.000", "C22B": "4.800.000", "D12": "7.500.000",
    "E23": "34.500.000 (Offshore) / 36.000.000 (Onshore)", "E23-FREELANCE": "25.800.000 (Offshore) / 27.500.000 (Onshore)",
    "E33G": "13.000.000 (Offshore) / 14.000.000 (Onshore)", "E28A": "17.000.000 (Offshore) / 19.000.000 (Onshore)",
    "E31A": "11.000.000 (1 Year) / 15.000.000 (2 Years)", "E31B": "11.000.000 (1 Year) / 15.000.000 (2 Years)",
    "E31F": "11.000.000 (1 Year) / 15.000.000 (2 Years)", "E33E": "14.000.000 (Offshore) / 16.000.000 (Onshore)",
    "E33F": "14.000.000 (Offshore) / 16.000.000 (Onshore)", "E35": "Contact for Quote",
    "KITAP-INVESTOR": "55.000.000", "KITAP-FAMILY": "33.000.000", "KITAP-RETIREMENT": "45.000.000",
    "EPO": "700.000", "ERP": "800.000", "SKTT": "1.500.000", "DOMICILE": "800.000",
}

def parse_detailed_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    sections = re.split(r'##\s+([A-Z0-9]+)\s+-\s+(.+)', content)
    visa_types = {}
    for i in range(1, len(sections), 3):
        code = sections[i].strip()
        visa_types[code] = {"code": code, "name": sections[i+1].strip(), "body": sections[i+2].strip()}
    return visa_types

def parse_list_file(file_path):
    with open(file_path, 'r') as f:
        return [{"code": l.split(' ', 1)[0], "name": l.split(' ', 1)[1].strip()} for l in f.readlines() if ' ' in l]

def determine_category(code):
    if code.startswith("A") or code.startswith("F"): return "Visa Free/VOA"
    if code.startswith("B"): return "VOA"
    if code.startswith("C"): return "Visit Visa"
    if code.startswith("D"): return "Multiple Entry"
    if code.startswith("E"): return "KITAS/Limited Stay"
    return "Immigration Service"

def merge_data(detailed, simple_list):
    merged = []
    extra_items = [
        {"code": "E23-FREELANCE", "name": "Freelance KITAS (E23)"},
        {"code": "EPO", "name": "EPO (Exit Permit Only)"},
        {"code": "ERP", "name": "ERP (Exit Re-entry Permit)"},
        {"code": "SKTT", "name": "SKTT Registration"},
    ]
    all_codes = simple_list + extra_items
    for item in all_codes:
        code = item["code"]
        name = translate_name(item["name"])
        obj = {
            "code": code, "name": name, "category": determine_category(code),
            "duration": "See details", "cost_visa": "Contact for Quote",
            "requirements": [], "description": f"Official title: {name}",
            "metadata": {
                "source": "zantara_curated_2026", 
                "is_agency_product": False,
                "name_id": item["name"] # Store original name
            }
        }
        gov_fee = None
        lookup_code = "E23" if code == "E23-FREELANCE" else code
        if lookup_code in detailed:
            d = detailed[lookup_code]
            cost_match = re.search(r'\*\*(?:Cost|Fee|Fees):\*\*\s*(.*?)(?=\**|$)', d["body"], re.DOTALL)
            gov_fee = cost_match.group(1).strip().replace('\n', ' ') if cost_match else None
            purpose_match = re.search(r'\*\*(?:Purpose|Description):\*\*\s*(.*?)(?=\**|$)', d["body"], re.DOTALL)
            if purpose_match: obj["description"] = purpose_match.group(1).strip()
            req_match = re.search(r'\*\*Requirements:\*\*\s*(.*?)(?=\**|$)', d["body"], re.DOTALL)
            if req_match:
                obj["requirements"] = [l.strip().lstrip('*').strip() for l in req_match.group(1).strip().split('\n') if l.strip().startswith('*')]
        price = ZANTARA_PRICES.get(code)
        if not price and code.startswith("E23") and code != "E23-FREELANCE":
            price = ZANTARA_PRICES.get("E23")
            obj["metadata"]["inherited_from"] = "E23"
        if price:
            obj["cost_visa"] = f"IDR {price}" if "IDR" not in price and "Contact" not in price else price
            obj["metadata"]["is_agency_product"] = True
            if code in ["C1", "C2"]:
                obj["cost_visa"] += " (All-inclusive pricing)"
        if gov_fee: obj["metadata"]["government_fee_internal"] = gov_fee
        merged.append(obj)
    return merged

if __name__ == "__main__":
    detailed = parse_detailed_file("visa_indonesia_corrected_EN.txt")
    simple_list = parse_list_file("visa_imigrasi_list.txt")
    merged = merge_data(detailed, simple_list)
    
    with open("apps/backend-rag/backend/migrations/seed_visa_types_complete_2026.py", "w") as f:
        f.write("import asyncio\nimport json\nimport os\nimport asyncpg\nimport logging\n\nlogging.basicConfig(level=logging.INFO)\nlogger = logging.getLogger(__name__)\n\nVISA_TYPES = [\n")
        for v in merged:
            f.write(f"    {repr(v)},\n")
        f.write("]\n\n")
        f.write("\nasync def seed_visa_types():\n    db_url = os.environ.get(\"DATABASE_URL\")\n    if not db_url: return\n    conn = await asyncpg.connect(db_url)\n    try:\n        logger.info(f\"Seeding {len(VISA_TYPES)} Curated Visa Types...\")\n        await conn.execute(\"CREATE TABLE IF NOT EXISTS visa_types (code TEXT PRIMARY KEY, name TEXT, category TEXT, description TEXT, duration TEXT, cost_visa TEXT, requirements TEXT[], metadata JSONB, created_at TIMESTAMP DEFAULT NOW(), last_updated TIMESTAMP DEFAULT NOW());\")\n        try: await conn.execute(\"ALTER TABLE visa_types ADD COLUMN IF NOT EXISTS description TEXT;\")\n        except: pass\n        for visa in VISA_TYPES:\n            exists = await conn.fetchval(\"SELECT 1 FROM visa_types WHERE code = $1\", visa[\"code\"])\n            if exists:\n                await conn.execute(\"UPDATE visa_types SET name=$2, category=$3, description=$4, duration=$5, cost_visa=$6, requirements=$7, metadata=$8, last_updated=NOW() WHERE code=$1\", \n                    visa[\"code\"], visa[\"name\"], visa[\"category\"], visa[\"description\"], visa[\"duration\"], visa[\"cost_visa\"], visa[\"requirements\"], json.dumps(visa[\"metadata\"])\n                )\n            else:\n                await conn.execute(\"INSERT INTO visa_types (code, name, category, description, duration, cost_visa, requirements, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)\", \n                    visa[\"code\"], visa[\"name\"], visa[\"category\"], visa[\"description\"], visa[\"duration\"], visa[\"cost_visa\"], visa[\"requirements\"], json.dumps(visa[\"metadata\"])\n                )\n        logger.info(\"Done.\")\n    finally: await conn.close()\n\nif __name__ == \"__main__\":\n    asyncio.run(seed_visa_types())\n")
    logger.info("Migration file updated with English + ID names + No print().")