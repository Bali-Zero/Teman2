#!/usr/bin/env python3
"""Extract structured data from Profile Perseroan PDFs and save as JSON."""
import subprocess, json, os, glob, re, sys

BASE = "/Users/nuzantara/Library/CloudStorage/GoogleDrive-antonellosiano@gmail.com/Il mio Drive/BALI ZERO/CRM/Company_CRM"

def extract_text(pdf_path):
    """Extract text from PDF using pdftotext."""
    try:
        result = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except:
        pass
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except:
        return ""

def parse_profile(text, company_name):
    """Parse structured data from Profile Perseroan text."""
    data = {"company_name": company_name}
    
    # Company type
    if "PMA" in text:
        data["company_type"] = "PMA"
    elif "PMDN" in text:
        data["company_type"] = "PMDN"
    
    # SK Number
    m = re.search(r"AHU[-\s][\d]+\.AH\.[\d.]+\.Tahun\s*\d{4}", text)
    if m:
        data["sk_number"] = m.group(0)
    
    # NIB
    m = re.search(r"NIB[:\s]*(\d{13,})", text)
    if m:
        data["nib"] = m.group(1)
    
    # NPWP
    m = re.search(r"NPWP[:\s]*([\d.]+[-][\d.]+)", text)
    if m:
        data["npwp"] = m.group(1)
    
    # Address
    m = re.search(r"KEDUDUKAN PERSEROAN[:\s]*([^\n]+)", text)
    if m:
        data["address"] = m.group(1).strip()
    
    # KBLI codes
    kbli_codes = re.findall(r"\b(\d{5})\b\s+[A-Z]", text)
    if kbli_codes:
        data["kbli_codes"] = list(set(kbli_codes))
    
    # Modal Dasar (Authorized Capital)
    m = re.search(r"Modal Dasar[:\s]*(Rp[\s\d.,]+)", text, re.IGNORECASE)
    if m:
        data["authorized_capital"] = m.group(1).strip()
    
    # Modal Ditempatkan (Paid-up Capital)
    m = re.search(r"Modal Ditempatkan[:\s]*(Rp[\s\d.,]+)", text, re.IGNORECASE)
    if m:
        data["paid_up_capital"] = m.group(1).strip()
    
    # Directors/Shareholders - look for SUSUNAN PEMEGANG SAHAM or PENGURUS
    directors = []
    shareholders = []
    
    # Find person names with roles
    for m in re.finditer(r"(Direktur|Komisaris|Pemegang Saham)[:\s]*([A-Z][A-Z\s]+?)(?:\n|$)", text):
        role = m.group(1)
        name = m.group(2).strip()
        if len(name) > 2:
            if "Direktur" in role:
                directors.append(name)
            elif "Komisaris" in role:
                data.setdefault("commissioners", []).append(name)
            else:
                shareholders.append(name)
    
    if directors:
        data["directors"] = directors
    if shareholders:
        data["shareholders"] = shareholders
    
    # Notaris
    m = re.search(r"Notaris[:\s]*([A-Z][A-Za-z\s.,]+(?:S\.H\.|M\.Kn\.))", text)
    if m:
        data["notaris"] = m.group(1).strip()
    
    # Status
    if "TERTUTUP" in text:
        data["status"] = "TERTUTUP"
    elif "TERBUKA" in text:
        data["status"] = "TERBUKA"
    
    # Jangka Waktu
    if "TIDAK TERBATAS" in text:
        data["jangka_waktu"] = "TIDAK TERBATAS"
    
    return data

# Main
results = []
errors = []

for company_dir in sorted(glob.glob(os.path.join(BASE, "*/03_Profile_Perseroan"))):
    company_name = os.path.basename(os.path.dirname(company_dir))
    pdfs = glob.glob(os.path.join(company_dir, "*.pdf"))
    if not pdfs:
        continue
    
    # Pick best PDF (newest/baru/terbaru/2025)
    best = pdfs[0]
    for p in pdfs:
        bn = os.path.basename(p).lower()
        if "2025" in bn or "baru" in bn or "terbaru" in bn:
            best = p
            break
    
    text = extract_text(best)
    if not text:
        errors.append(company_name)
        continue
    
    parsed = parse_profile(text, company_name)
    results.append(parsed)

# Save results
output = {
    "total_parsed": len(results),
    "total_errors": len(errors),
    "errors": errors,
    "profiles": results
}

output_path = "/tmp/profile_perseroan_data.json"
with open(output_path, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Parsed: {len(results)}, Errors: {len(errors)}")
print(f"Saved to {output_path}")

# Quick stats
has_sk = sum(1 for r in results if r.get("sk_number"))
has_address = sum(1 for r in results if r.get("address"))
has_kbli = sum(1 for r in results if r.get("kbli_codes"))
has_directors = sum(1 for r in results if r.get("directors"))
has_type = sum(1 for r in results if r.get("company_type"))
has_capital = sum(1 for r in results if r.get("authorized_capital"))

print(f"\nField coverage:")
print(f"  company_type: {has_type}")
print(f"  sk_number: {has_sk}")
print(f"  address: {has_address}")
print(f"  kbli_codes: {has_kbli}")
print(f"  directors: {has_directors}")
print(f"  authorized_capital: {has_capital}")
