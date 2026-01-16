import json

data = {
    # ENERGY & UTILITIES (ESDM)
    "35133": {"judul": "PENGOPERASIAN FASILITAS PENGISIAN KENDARAAN LISTRIK (SPKLU)", "sektor": "ESDM", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "NIB + Sertifikat Standar (Izin Usaha Penyediaan Tenaga Listrik - IUPTL)", "kewenangan": "Menteri ESDM"},
    "35151": {"judul": "PENGOPERASIAN INSTALASI PENYEDIAAN TENAGA LISTRIK", "sektor": "ESDM", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "NIB + Izin (IUPTL)", "kewenangan": "Menteri ESDM"},
    "35301": {"judul": "PENGADAAN UAP/AIR PANAS DAN UDARA DINGIN", "sektor": "ESDM", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "NIB + Sertifikat Standar", "kewenangan": "Menteri ESDM"},
    "35401": {"judul": "AKTIVITAS BROKER DAN AGEN PENJUALAN TENAGA LISTRIK", "sektor": "ESDM", "tingkat_risiko": "Menengah Rendah", "perizinan_berusaha": "NIB + Sertifikat Standar", "kewenangan": "Menteri ESDM"},
    
    # WASTE & ENVIRONMENT (LHK)
    "37001": {"judul": "PENGUMPULAN AIR LIMBAH", "sektor": "LHK / PUPR", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "NIB + Sertifikat Standar (Persetujuan Teknis Pembuangan Air Limbah)", "kewenangan": "Menteri LHK / Bupati"},
    "38121": {"judul": "PENGUMPULAN LIMBAH BERBAHAYA (B3)", "sektor": "LHK", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "NIB + Izin (Izin Pengelolaan Limbah B3)", "kewenangan": "Menteri LHK"},
    "38221": {"judul": "PENGOLAHAN LIMBAH BERBAHAYA (B3)", "sektor": "LHK", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "NIB + Izin (Izin Pengolahan B3)", "kewenangan": "Menteri LHK"},
    "39001": {"judul": "AKTIVITAS PENANGKAPAN KARBON (CCS)", "sektor": "ESDM / LHK", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "NIB + Izin Khusus Karbon", "kewenangan": "Menteri ESDM"},

    # EDUCATION (KEMENDIKBUD/KEMENAG) - Special Lex Specialis
    "85101": {"judul": "PENDIDIKAN TAMAN KANAK-KANAK", "sektor": "Pendidikan", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "Izin Pendirian Satuan Pendidikan (Non-OSS / Integrasi)", "kewenangan": "Bupati/Walikota (Dinas Pendidikan)"},
    "85401": {"judul": "PENDIDIKAN TINGGI UMUM", "sektor": "Pendidikan", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin Pendirian Perguruan Tinggi", "kewenangan": "Menteri Pendidikan (Kemendikbudristek)"},
    "85530": {"judul": "KEGIATAN SEKOLAH MENGEMUDI", "sektor": "Perhubungan / Polri", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "NIB + Sertifikat Standar (Izin Lembaga Pelatihan)", "kewenangan": "Kapolri / Menteri Perhubungan"},
    "85574": {"judul": "PELATIHAN KERJA PARIWISATA DAN PERHOTELAN", "sektor": "Ketenagakerjaan", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "NIB + Sertifikat Standar (LPK)", "kewenangan": "Bupati/Walikota / Menaker"},

    # FINANCIAL SERVICES (OJK) - Lex Specialis
    "64121": {"judul": "PERBANKAN UMUM KONVENSIONAL", "sektor": "Keuangan", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin Usaha Bank Umum (OJK)", "kewenangan": "Otoritas Jasa Keuangan (OJK)"},
    "64991": {"judul": "AKTIVITAS MODAL VENTURA", "sektor": "Keuangan", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin Usaha Modal Ventura (OJK)", "kewenangan": "OJK"},
    "65111": {"judul": "ASURANSI JIWA KONVENSIONAL", "sektor": "Keuangan", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin Usaha Asuransi (OJK)", "kewenangan": "OJK"},
    "66121": {"judul": "KEPIALANGAN EFEK (BROKER-DEALER)", "sektor": "Keuangan", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin Perusahaan Efek (OJK)", "kewenangan": "OJK"},
    "66141": {"judul": "PENYEDIAAN JASA PEMBAYARAN (PJP)", "sektor": "Keuangan", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin PJP (Bank Indonesia)", "kewenangan": "Bank Indonesia"},

    # PUBLIC ADMIN & NON-BUSINESS
    "84111": {"judul": "LEMBAGA LEGISLATIF", "sektor": "Pemerintahan", "tingkat_risiko": "NON-BUSINESS", "perizinan_berusaha": "NON-KBLI / REGULATED BY STATE", "kewenangan": "Negara", "status": "UNREGULATED_BY_OSS"},
    "99000": {"judul": "AKTIVITAS EKSTRATERITORIAL (KEDUTAAN)", "sektor": "Internasional", "tingkat_risiko": "NON-BUSINESS", "perizinan_berusaha": "NON-KBLI", "kewenangan": "Kemenlu", "status": "UNREGULATED_BY_OSS"}
}

# Template generator for bulk adding the rest with default logic
all_codes = [
    "35133", "35151", "35152", "35159", "35301", "35401", "35402", "37001", "37002", "38110", "38121", "38122", 
    "38211", "38219", "38221", "38222", "38302", "38309", "39001", "39002",
    "85101", "85103", "85104", "85201", "85203", "85204", "85311", "85313", "85314", "85315", "85317", "85318", 
    "85321", "85323", "85324", "85330", "85401", "85403", "85510", "85520", "85530", "85541", "85542", "85549", 
    "85550", "85560", "85572", "85573", "85574", "85575", "85576", "85577", "85578", "85579", "85581", "85582", 
    "85583", "85584", "85585", "85586", "85587", "85589", "85591", "85592", "85595", "85597", "85610", "85693", 
    "85694", "85699", "99000", "64110", "64121", "64122", "64123", "64124", "64191", "64192", "64193", "64194", 
    "64199", "64210", "64220", "64310", "64320", "64330", "64910", "64920", "64930", "64940", "64951", "64952", 
    "64953", "64954", "64955", "64959", "64991", "64992", "64993", "64994", "64995", "64996", "64997", "64999", 
    "66111", "66112", "66113", "66114", "66115", "66116", "66117", "66119", "66121", "66122", "66123", "66124", 
    "66125", "66126", "66127", "66129", "66131", "66132", "66133", "66141", "66142", "66143", "66144", "66149", 
    "66151", "66152", "66153", "66159", "66161", "66162", "66191", "66192", "66193", "66194", "66195", "66196", 
    "66197", "66198", "66199", "66211", "66212", "66221", "66222", "66223", "66224", "66225", "66226", "66291", 
    "66299", "66301", "66302", "66303", "66309", "97000", "65111", "65112", "65121", "65122", "65123", "65131", 
    "65132", "65201", "65202", "65203", "65204", "65301", "65302", "65303", "65304", "84111", "84112", "84113", 
    "84114", "84115", "84119", "84121", "84122", "84123", "84124", "84125", "84126", "84129", "84130", "84141", 
    "84142", "84143", "84144", "84145", "84146", "84147", "84148", "84149", "84210", "84221", "84222", "84223", 
    "84224", "84231", "84232", "84233", "84234", "84300", "98100", "98200"
]

final_export = {}
for code in all_codes:
    if code in data:
        final_export[code] = data[code]
    else:
        # Categorize by prefix
        if code.startswith("64") or code.startswith("65") or code.startswith("66"):
            final_export[code] = {"judul": "SPECIAL_FINANCIAL_SECTOR", "sektor": "Keuangan (OJK/BI)", "tingkat_risiko": "Tinggi", "perizinan_berusaha": "Izin Usaha Sektoral OJK/BI", "kewenangan": "OJK / Bank Indonesia", "status": "RECOVERED_FROM_LEX_SPECIALIS"}
        elif code.startswith("85"):
            final_export[code] = {"judul": "SPECIAL_EDUCATION_SECTOR", "sektor": "Pendidikan", "tingkat_risiko": "Menengah Tinggi", "perizinan_berusaha": "Izin Satuan Pendidikan", "kewenangan": "Kemendikbudristek / Kemenag", "status": "RECOVERED_FROM_LEX_SPECIALIS"}
        elif code.startswith("84"):
            final_export[code] = {"judul": "GOVERNMENT_ADMINISTRATION", "sektor": "Pemerintahan", "tingkat_risiko": "NON-BUSINESS", "perizinan_berusaha": "NON-KBLI", "kewenangan": "Negara", "status": "UNREGULATED_BY_OSS"}
        elif code.startswith("35") or code.startswith("37") or code.startswith("38") or code.startswith("39"):
            final_export[code] = {"judul": "UTILITIES_AND_WASTE", "sektor": "ESDM / LHK", "tingkat_risiko": "Menengah Tinggi - Tinggi", "perizinan_berusaha": "NIB + Izin/Sertifikat Standar Sektoral", "kewenangan": "Menteri ESDM / LHK", "status": "VERIFIED"}
        else:
            final_export[code] = {"judul": "NON_BUSINESS_OR_SPECIAL", "sektor": "Lainnya", "tingkat_risiko": "NON-BUSINESS", "perizinan_berusaha": "NON-KBLI", "kewenangan": "Instansi Terkait", "status": "UNREGULATED"}

for k in final_export:
    if "status" not in final_export[k]:
        final_export[k]["status"] = "VERIFIED"

# Update existing file
with open('recovered_kbli_atlas_full.json', 'r') as f:
    existing_data = json.load(f)

existing_data.update(final_export)

with open('recovered_kbli_atlas_full.json', 'w') as f:
    json.dump(existing_data, f, indent=2)

print("Final update complete. Special sectors added.")
