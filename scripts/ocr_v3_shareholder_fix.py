#!/usr/bin/env python3
"""OCR Pipeline v3 — Fix pass for missing addresses + extract shareholders.
Targets: companies with NPWP but no address, and all companies for shareholder data.
Runs on Fly.io with DATABASE_URL, OPENAI_API_KEY, GOOGLE_SERVICE_ACCOUNT_JSON.
"""
import asyncio, asyncpg, os, json, io, base64, re, datetime, sys
import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
DB_URL = os.environ["DATABASE_URL"]
SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT")

try:
    sa_data = json.loads(SA_JSON)
except:
    sa_data = json.loads(base64.b64decode(SA_JSON))
creds = service_account.Credentials.from_service_account_info(sa_data, scopes=["https://www.googleapis.com/auth/drive.readonly"])
drive = build("drive", "v3", credentials=creds)

def to_date(s):
    if not s: return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %B %Y", "%d %b %Y"):
        try: return datetime.datetime.strptime(s.strip(), fmt).date()
        except: continue
    try:
        from dateutil.parser import parse as dp
        return dp(s.strip()).date()
    except: return None

def classify_file(name):
    n = name.lower()
    if any(k in n for k in ["profil perseroan", "profile perseroan", "company_profile", "profil_perseroan"]): return "company_profile"
    if any(k in n for k in ["sk ", "sk_", "keputusan", "menhumkam", "menkumham", "kemenkumham"]): return "sk_decree"
    if any(k in n for k in ["akta pendirian", "akta_pendirian", "deed", "notari"]): return "akta_pendirian"
    if any(k in n for k in ["akta perubahan", "akta_perubahan"]): return "akta_perubahan"
    if any(k in n for k in ["npwp"]): return "npwp"
    if any(k in n for k in ["nib", "oss"]): return "nib"
    return "other"

def list_drive_files(folder_id):
    files = []
    try:
        results = drive.files().list(q=f"'{folder_id}' in parents and trashed=false", fields="files(id,name,mimeType,size)", pageSize=100).execute()
        for f in results.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                files.extend(list_drive_files(f["id"]))
            else:
                files.append(f)
    except Exception as e:
        print(f"  [WARN] Drive error: {e}")
    return files

def download_file(file_id, max_bytes=3_000_000):
    try:
        meta = drive.files().get(fileId=file_id, fields="size").execute()
        if int(meta.get("size", 0)) > max_bytes: return None
        req = drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        dl = MediaIoBaseDownload(fh, req)
        done = False
        while not done: _, done = dl.next_chunk()
        fh.seek(0)
        return fh.read()
    except: return None

def extract_text_pdf(data):
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = ""
        for p in reader.pages[:6]:
            t = p.extract_text()
            if t: text += t + "\n"
        return text.strip() if len(text.strip()) > 50 else None
    except: return None

async def llm_extract_all(text, company_name):
    """Extract ALL data including shareholders with roles and percentages."""
    prompt = f"""Extract ALL company data from this Indonesian legal/corporate document.
Company: {company_name}

CRITICAL RULES:
- Extract ALL shareholders (pemegang saham) with their EXACT ownership percentage and share count
- Extract ALL directors (direktur) and commissioners (komisaris) with their roles
- Only REAL PERSON names, NOT government officials
- Extract the registered address (alamat) even from NPWP documents
- Return JSON only, no markdown
- Dates in YYYY-MM-DD format
- If a field is not found, use null

Return this JSON:
{{
  "company_name_extracted": "...",
  "company_type": "PT/CV/etc",
  "registered_address": "full address from document",
  "office_address": "if different from registered",
  "city": "...",
  "province": "...",
  "postal_code": "...",
  "npwp": "...",
  "nib": "...",
  "akta_pendirian_no": "...",
  "akta_pendirian_date": "YYYY-MM-DD",
  "akta_perubahan_no": "...",
  "akta_perubahan_date": "YYYY-MM-DD",
  "sk_menhumkam_no": "...",
  "sk_menhumkam_date": "YYYY-MM-DD",
  "notary_name": "...",
  "kbli_codes": ["12345"],
  "kbli_descriptions": ["..."],
  "people": [
    {{
      "name": "FULL NAME",
      "role": "direktur_utama|direktur|komisaris_utama|komisaris|pemegang_saham",
      "nationality": "Indonesia|etc",
      "shares_count": 500,
      "ownership_percentage": 50.0,
      "share_nominal_value": 1000000
    }}
  ]
}}

Document text:
{text[:8000]}"""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-4o-mini", "max_tokens": 3000,
                  "messages": [{"role": "user", "content": prompt}]}
        )
        r = resp.json()
        if "choices" not in r: return None
        content = r["choices"][0]["message"]["content"]
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        return json.loads(content)

def check_contamination(ext, exp):
    if not ext: return True
    e1 = ext.lower().replace("pt ", "").replace("pt. ", "").replace("cv ", "").strip()
    e2 = exp.lower().replace("pt ", "").replace("pt. ", "").replace("cv ", "").strip()
    w1 = [w for w in e1.split() if len(w) > 2]
    w2 = [w for w in e2.split() if len(w) > 2]
    if w1 and w2:
        if w1[0] == w2[0]: return True
        if set(w1) & set(w2): return True
    return False

async def process_company(conn, company_id, company_name, folder_id, needs_address):
    """Process company: try multiple docs, merge data, save shareholders."""
    print(f"\n{'='*60}")
    print(f"Processing: {company_name} (id={company_id})")
    print(f"  needs_address={needs_address}")

    if not folder_id:
        return "NO_FOLDER"

    files = list_drive_files(folder_id)
    if not files:
        return "EMPTY"

    # Classify
    classified = []
    for f in files:
        if f.get("mimeType") == "application/pdf" or f["name"].lower().endswith(".pdf"):
            doc_type = classify_file(f["name"])
            classified.append((doc_type, f))

    if not classified:
        return "NO_PDFS"

    # Strategy: try multiple documents and MERGE results
    # Priority for shareholders: company_profile > sk_decree > akta_pendirian
    # Priority for address if missing: npwp > company_profile > sk_decree
    merged = {}
    people_all = []
    docs_tried = 0

    # If needs_address, prioritize NPWP files
    if needs_address:
        order = ["npwp", "company_profile", "sk_decree", "akta_pendirian"]
    else:
        order = ["company_profile", "sk_decree", "akta_pendirian", "npwp"]

    # Group by type
    by_type = {}
    for dtype, f in classified:
        by_type.setdefault(dtype, []).append(f)

    for dtype in order:
        if dtype not in by_type or docs_tried >= 3:
            continue
        for f in by_type[dtype][:1]:  # Try first file of each type
            print(f"  Trying: {f['name']} ({dtype})")
            data = download_file(f["id"])
            if not data:
                print(f"    [SKIP] Too large or failed")
                continue

            text = extract_text_pdf(data)
            if not text:
                print(f"    [SKIP] No text")
                continue

            docs_tried += 1
            print(f"    Extracted {len(text)} chars")

            try:
                parsed = await llm_extract_all(text, company_name)
            except Exception as e:
                print(f"    [WARN] Parse failed: {e}")
                continue

            if not parsed:
                continue

            # Contamination check
            if not check_contamination(parsed.get("company_name_extracted"), company_name):
                print(f"    [WARN] CONTAMINATION")
                continue

            # Merge: only fill empty fields
            for k, v in parsed.items():
                if k == "people":
                    continue
                if v and not merged.get(k):
                    merged[k] = v

            # Collect people
            for p in parsed.get("people", []):
                if p.get("name") and len(p["name"]) > 2:
                    people_all.append(p)

            print(f"    OK from {dtype}")

    if not merged and not people_all:
        print("  [FAIL] No data extracted")
        return "FAIL"

    # === Update company fields ===
    updates = []
    params = []
    idx = 1

    # Only update address if it was missing
    field_map = {}
    if needs_address:
        field_map["registered_address"] = "registered_address"
        field_map["office_address"] = "office_address"
        field_map["city"] = "city"
        field_map["province"] = "province"
        field_map["postal_code"] = "postal_code"

    for src, dst in field_map.items():
        val = merged.get(src)
        if val:
            updates.append(f"{dst} = ${idx}")
            params.append(str(val))
            idx += 1

    if updates:
        updates.append(f"updated_at = ${idx}")
        params.append(datetime.datetime.now(datetime.timezone.utc))
        idx += 1
        params.append(company_id)
        sql = f"UPDATE companies SET {', '.join(updates)} WHERE id = ${idx}"
        await conn.execute(sql, *params)
        print(f"  [OK] Updated {len(updates)-1} address fields")

    # === Save shareholders/directors ===
    if people_all:
        # Deduplicate by name
        seen = set()
        unique_people = []
        for p in people_all:
            name = p["name"].strip().upper()
            if name not in seen:
                seen.add(name)
                unique_people.append(p)

        # Store in custom_fields JSON (since client_company_links needs client_id which we may not have)
        people_json = json.dumps(unique_people, ensure_ascii=False)
        await conn.execute(
            "UPDATE companies SET custom_fields = $1, updated_at = $2 WHERE id = $3",
            people_json,
            datetime.datetime.now(datetime.timezone.utc),
            company_id
        )
        roles = [f"{p['name']} ({p.get('role','?')}, {p.get('ownership_percentage','')}%)" for p in unique_people[:5]]
        print(f"  [OK] Saved {len(unique_people)} people: {'; '.join(roles)}")

    return "OK"

async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "address"  # "address" or "all"
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    batch = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    conn = await asyncpg.connect(DB_URL)

    if mode == "address":
        # Only companies with NPWP but no address
        rows = await conn.fetch("""
            SELECT id, company_name, google_drive_folder_id FROM companies
            WHERE (registered_address IS NULL OR registered_address = '')
            AND google_drive_folder_id IS NOT NULL AND google_drive_folder_id != ''
            ORDER BY company_name
            OFFSET $1 LIMIT $2
        """, offset, batch)
        needs_address = True
    else:
        # All companies for shareholder extraction
        rows = await conn.fetch("""
            SELECT id, company_name, google_drive_folder_id FROM companies
            WHERE google_drive_folder_id IS NOT NULL AND google_drive_folder_id != ''
            AND (custom_fields IS NULL OR custom_fields::text = '' OR custom_fields::text = 'null'
                 OR custom_fields::text NOT LIKE '%ownership_percentage%')
            ORDER BY company_name
            OFFSET $1 LIMIT $2
        """, offset, batch)
        needs_address = False

    print(f"Mode: {mode}, offset={offset}, batch={batch}, got {len(rows)} companies")

    results = {"OK": 0, "FAIL": 0, "EMPTY": 0, "NO_PDFS": 0, "NO_FOLDER": 0}
    for row in rows:
        try:
            status = await process_company(conn, row["id"], row["company_name"],
                                          row["google_drive_folder_id"], needs_address)
            results[status] = results.get(status, 0) + 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            results["ERROR"] = results.get("ERROR", 0) + 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {json.dumps(results)}")
    await conn.close()

asyncio.run(main())
