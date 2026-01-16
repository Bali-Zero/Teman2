#!/usr/bin/env python3
"""Standalone test of categorization - copied from source"""
import re
from typing import Dict, Optional

# Comprehensive keyword mapping for document categorization
CATEGORIZATION_RULES = {
    "immigration": {
        "passport": ["passport", "paspor", "pp", "pport"],
        "kitas": ["kitas", "kitap", "stay permit", "limited stay", "itas"],
        "visa": ["visa", "voa", "b211", "c1", "c2", "e-visa"],
        "imta": ["imta", "work permit", "izin kerja", "working permit"],
        "merp": ["merp", "report", "pelaporan", "residence report"],
        "sktt": ["sktt", "temporary residence", "surat keterangan"],
        "sponsor_letter": ["sponsor", "sponsorship", "letter"],
    },
    "pma": {
        "akta": ["akta", "deed", "pendirian", "notarial", "akta pendirian"],
        "nib": ["nib", "oss", "business id", "nomor induk"],
        "tdp": ["tdp", "siup", "business license", "izin usaha"],
        "npwp_company": ["npwp", "tax id", "tin", "company tax"],
        "sk_kemenkumham": ["sk", "kemenkumham", "ministry approval", "ministry of law"],
        "domicile_letter": ["domicile", "domisili", "surat domisili"],
        "lkpm": ["lkpm", "investment report", "laporan kegiatan"],
    },
    "tax": {
        "spt": ["spt", "tax return", "annual report", "spt tahunan"],
        "tax_report": ["tax report", "laporan pajak", "monthly tax"],
        "bpjs": ["bpjs", "social insurance", "kesehatan", "ketenagakerjaan"],
        "invoice": ["invoice", "faktur", "receipt", "kwitansi"],
        "pph": ["pph", "income tax", "pajak penghasilan"],
        "ppn": ["ppn", "vat", "value added tax"],
        "bukti_potong": ["bukti potong", "withholding", "pemotongan"],
    },
    "personal": {
        "photo": ["photo", "foto", "picture", "jpg", "jpeg", "png", "image"],
        "cv": ["cv", "resume", "curriculum", "vitae"],
        "certificate": ["certificate", "sertifikat", "ijazah", "diploma"],
        "kk": ["kk", "family card", "kartu keluarga"],
        "ktp": ["ktp", "id card", "identity", "kartu tanda penduduk"],
        "birth_certificate": ["birth", "kelahiran", "akta kelahiran"],
        "marriage_certificate": ["marriage", "pernikahan", "akta nikah"],
    },
}

def auto_categorize_document(filename: str) -> Dict[str, any]:
    """Categorize document from filename"""
    if not filename:
        return {"document_type": "Other", "document_category": "other", "confidence": 0.5, "matched_keyword": None}
    
    filename_lower = filename.lower()
    
    for category, doc_types in CATEGORIZATION_RULES.items():
        for doc_type, keywords in doc_types.items():
            for keyword in keywords:
                if keyword in filename_lower:
                    return {
                        "document_type": doc_type.replace("_", " ").title(),
                        "document_category": category,
                        "confidence": 0.9 if filename_lower.startswith(keyword) else 0.7,
                        "matched_keyword": keyword,
                    }
    
    return {"document_type": "Other", "document_category": "other", "confidence": 0.5, "matched_keyword": None}

# Run tests
print("🧪 Testing Auto-Categorization Service...")
tests = [
    ('Passport_JOHN_DOE_2028-12-31.pdf', 'immigration', 'Passport'),
    ('KITAS_2025-06-15.jpg', 'immigration', 'Kitas'),
    ('Akta_PT_ABC.pdf', 'pma', 'Akta'),
    ('NPWP_Company.pdf', 'pma', 'Npwp Company'),
    ('SPT_2023.pdf', 'tax', 'Spt'),
    ('Invoice_Dec.pdf', 'tax', 'Invoice'),
    ('Photo_3x4.jpg', 'personal', 'Photo'),
    ('CV_Resume.pdf', 'personal', 'Cv'),
]

passed = 0
failed = 0

for filename, exp_cat, exp_type in tests:
    result = auto_categorize_document(filename)
    if result['document_category'] == exp_cat and result['document_type'] == exp_type:
        print(f"✓ {filename} → {result['document_category']}/{result['document_type']}")
        passed += 1
    else:
        print(f"✗ {filename} → Expected {exp_cat}/{exp_type}, got {result['document_category']}/{result['document_type']}")
        failed += 1

print(f"\n📊 Results: {passed}/{len(tests)} passed")
if failed == 0:
    print("🎉 AUTO-CATEGORIZATION SERVICE IS WORKING!")
else:
    print(f"⚠️  {failed} tests failed")
