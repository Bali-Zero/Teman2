# CRM Company Data Automation — Definitive Guideline for AI Models

> **Version:** 1.0
> **Author:** Bali Zero AI Team
> **Date:** 2026-03-01
> **Target Audience:** Kimi 2.5, Claude (Opus/Sonnet/Haiku), any LLM with tool-use capability
> **Prerequisite:** Access to Nuzantara MCP server OR direct HTTP access to `https://nuzantara-rag.fly.dev`

---

## PURPOSE

You are automating the CRM data pipeline for Bali Zero. For each client company stored in Google Drive, you must:

1. **Explore** — List all files in the company's Drive folder
2. **Extract** — Read PDFs (AKTA, NIB, NPWP, Profil Perseroan) and extract 18 structured fields
3. **Organize** — Restructure the Drive folder into 5 standard subfolders
4. **Update Sheet** — Write the 18 extracted fields to the Master Google Sheet

Each company takes 2-5 minutes. There are ~1,700 companies to process.

---

## AUTHENTICATION

### Option A: Nuzantara MCP Server (Recommended)

If you have access to the Nuzantara MCP server, all tools are pre-authenticated. Use the tool names directly:

- `list_drive_files` — list files in a folder
- `search_drive` — search by filename
- `create_drive_folder` — create a new folder
- `create_client_drive_folder` — create standard 5-folder structure
- `read_sheet` — read spreadsheet range
- `write_sheet` — write to spreadsheet range
- `update_sheet_row` — update a specific row starting at a column
- `find_sheet_row` — find a row by column value

### Option B: Direct HTTP API

Base URL: `https://nuzantara-rag.fly.dev`

Authentication: Bearer JWT token in `Authorization` header.

```
Authorization: Bearer <JWT_TOKEN>
```

The JWT is set as `NUZANTARA_API_KEY` in MCP config, or obtained from the backend auth system.

### Option C: Fly.io SSH (for scripts)

For running Python scripts directly on the production server:

```bash
fly ssh console -a nuzantara-rag -C "python3 -c '<code>'"
```

Or for longer scripts:

```bash
cat script.py | fly ssh console -a nuzantara-rag -C "python3 -"
```

The server has `GOOGLE_SERVICE_ACCOUNT_JSON` available as an environment variable. The Service Account email is `nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com`.

---

## CONSTANTS

```
MASTER_SHEET_ID    = "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY"
SHEET_NAME         = "Company"
HEADER_ROW         = 9
DATA_START_ROW     = 10

# Google Drive folder IDs (CRITICAL — you need these to navigate)
BALI_ZERO_FOLDER   = "1hkOeV03YM5-sHbQhswYz809jsrnwC0At"
CRM_FOLDER         = "1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl"
COMPANY_CRM_FOLDER = "1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW"   # ← START HERE

SA_EMAIL           = "nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com"

STANDARD_FOLDERS   = ["AKTA", "NIB", "NPWP", "Profile Perseroan", "Other"]
```

**To list all company folders**, call:

```
GET /api/drive/files?folder_id=1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW
```

This returns all ~1,700 company folders with their IDs and names.

**IMPORTANT — CURL WITH "!" IN JSON:**
The `!` character in sheet ranges (e.g. `Company!A9:U`) causes JSON parse errors in bash/zsh.
You MUST always write the JSON body with Python first:

```bash
python3 -c "
import json
data = {'spreadsheet_id': '1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY', 'range': 'Company!B10:U30'}
with open('/tmp/req.json', 'w') as f: json.dump(data, f)
"
curl -s -H "X-API-Key: zantara-secret-2024" -H "Content-Type: application/json" \
  https://nuzantara-rag.fly.dev/api/sheets/read -X POST -d @/tmp/req.json
```

This workaround is MANDATORY for every curl that contains `!` in the JSON body.

---

## PHASE 1: EXPLORATION

**Goal:** Get the full file tree of a company folder.

### Using MCP Tool

```
Tool: list_drive_files
Parameters:
  folder_id: "<company_folder_id>"
```

This returns a list of files and subfolders with their IDs, names, and MIME types.

### Using HTTP API

```
GET /api/drive/files?folder_id=<company_folder_id>
```

### Using Drive API directly (Python on Fly SSH)

```python
import json, os, tempfile
from google.oauth2 import service_account
from googleapiclient.discovery import build

sa_json = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
tf = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
json.dump(sa_json, tf); tf.close()

creds = service_account.Credentials.from_service_account_file(
    tf.name,
    scopes=['https://www.googleapis.com/auth/drive'],
    subject='zero@balizero.com'
)
svc = build('drive', 'v3', credentials=creds)

def list_folder(folder_id, indent=0):
    results = svc.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields='files(id,name,mimeType)',
        orderBy='name',
        pageSize=100
    ).execute()
    for f in results.get('files', []):
        is_folder = f['mimeType'] == 'application/vnd.google-apps.folder'
        print(f"{'  '*indent}[{'DIR' if is_folder else 'FILE'}] {f['name']}  {f['id']}")
        if is_folder:
            list_folder(f['id'], indent + 1)

list_folder("<COMPANY_FOLDER_ID>")
os.unlink(tf.name)
```

### What to look for

Identify:

- Which documents exist (AKTA, NIB, NPWP, Profil Perseroan)
- Which files are loose in the root (need moving to subfolders)
- Which subfolders already exist
- Any non-standard folders or files

---

## PHASE 2: EXTRACTION

**Goal:** Read document contents and extract 18 structured fields.

### Target Fields (Columns D through U)

| #   | Column | Field Name                 | Source Document             | Example                                                                 |
| --- | ------ | -------------------------- | --------------------------- | ----------------------------------------------------------------------- |
| 1   | D      | Legal Address              | AKTA or Profil Perseroan    | Jl. Raya Tangeb No. 59, Abianbase, Kec. Mengwi, Kab. Badung, Bali 80351 |
| 2   | E      | NIB                        | NIB.pdf                     | 2308240057585                                                           |
| 3   | F      | NPWP                       | NPWP.pdf                    | 07.621.242.2-906.000                                                    |
| 4   | G      | KBLI (comma-separated)     | NIB.pdf or Profil Perseroan | 68111, 70209                                                            |
| 5   | H      | Director 1                 | AKTA                        | Ivan Shamrai                                                            |
| 6   | I      | Ownership % (Director)     | AKTA                        | 50%                                                                     |
| 7   | J      | Commissioner 1             | AKTA                        | Oleksandr Huliaiev                                                      |
| 8   | K      | Ownership % (Commissioner) | AKTA                        | 30%                                                                     |
| 9   | L      | Investor (optional)        | AKTA                        | PT Predmet Construction Group                                           |
| 10  | M      | Ownership % (Investor)     | AKTA                        | 50%                                                                     |
| 11  | N      | Authorized Capital         | AKTA                        | Rp 10.100.000.000                                                       |
| 12  | O      | Incorporation Date         | AKTA or SK                  | 20 Agustus 2024                                                         |
| 13  | P      | Official Email             | Profil Perseroan or AKTA    | backtobackdevelopmentgroup@gmail.com                                    |
| 14  | Q      | Official Phone             | Profil Perseroan or AKTA    | 082144087549                                                            |
| 15  | R      | SK Number                  | AKTA                        | AHU-0064467.AH.01.01.TAHUN 2024                                         |
| 16  | S      | Tax Office (KPP)           | NPWP                        | KPP Pratama Badung Utara                                                |
| 17  | T      | Company Status             | AKTA                        | TERTUTUP                                                                |
| 18  | U      | Office Type                | NIB or general knowledge    | PMA                                                                     |

### Extraction Priority

1. **AKTA (Akta Pendirian)** — Primary source. Contains: company name, directors, commissioners, shareholders, ownership percentages, authorized capital, SK number, incorporation date, legal address, company status.
2. **NIB.pdf** — Contains: NIB number, KBLI codes.
3. **NPWP.pdf** — Contains: NPWP number, KPP (tax office).
4. **Profil Perseroan** — If available, contains a summary of all fields. Use as cross-reference or primary source if AKTA is unreadable.

### PDF Reading Strategy

**For text-based PDFs** (most common):

```bash
pdftotext -layout "file.pdf" -
```

**For scanned PDFs** (images):

```bash
pdftoppm -jpeg -r 150 -f 1 -l 2 "file.pdf" "output_prefix"
# Then use OCR or vision model on the images
```

**How to tell them apart:**

```bash
pdfinfo "file.pdf"
# If "Tagged: no" and "Pages: X" with very small file size per page → likely scanned
# If pdftotext returns empty/garbled text → scanned
```

### Extraction Rules

1. **If a field is not found in any document, leave it as empty string `""`**. Never guess or invent data.
2. **KBLI codes** must be comma-separated, codes only (no descriptions). Example: `"68111, 70209"`, NOT `"68111 - Real Estat"`.
3. **Ownership percentages** must include the `%` symbol. Example: `"50%"`, NOT `"50"`.
4. **Capital amounts** must include `Rp` prefix. Example: `"Rp 10.100.000.000"`.
5. **Dates** should be in the format found in the document (Indonesian format preferred). Example: `"20 Agustus 2024"`.
6. **SK Number** always starts with `AHU-` followed by digits and year.
7. **Company Status** is either `TERTUTUP` (closed/private) or `TERBUKA` (open/public). Most are `TERTUTUP`.
8. **Office Type** is either `PMA` (foreign investment) or `PMDN` (domestic). If company has foreign shareholders → `PMA`.

### Handling Missing Documents

If the AKTA is missing or unreadable:

- Check for `Profil Perseroan.pdf` — it often has a summary
- Check for `Rincian PT.pdf` or similar documents in Other/DOKUMEN
- If no data source exists, leave fields empty — do NOT guess

If only NIB exists:

- Extract NIB number and KBLI codes
- Mark all other fields as empty
- Flag the company for manual review

---

## PHASE 3: ORGANIZATION

**Goal:** Restructure the company folder so root contains exactly 5 subfolders.

### Standard Structure

```
📁 [Company Name] PT/
├── 📁 AKTA/              → Akta Pendirian, SK Pendirian, related images
├── 📁 NIB/               → NIB.pdf and related
├── 📁 NPWP/              → NPWP.pdf and related
├── 📁 Profile Perseroan/ → Profil Perseroan.pdf (original or generated)
└── 📁 Other/             → EVERYTHING else (bank statements, KTP, certificates, personal folders, DOKUMEN, etc.)
```

### Rules

1. **Root must contain ONLY these 5 folders.** No loose files, no extra folders.
2. **Move, don't delete.** Everything that isn't AKTA/NIB/NPWP/Profile Perseroan goes to `Other/`.
3. **Preserve internal structure.** If a subfolder like `DOKUMEN/` exists with its own tree, move the entire folder to `Other/` — don't flatten it.
4. **Create missing folders.** If `AKTA/`, `NIB/`, `NPWP/`, `Profile Perseroan/`, or `Other/` don't exist, create them.

### Using MCP Tool

```
Tool: create_client_drive_folder
Parameters:
  client_name: "<Company Name>"
  parent_folder_id: "<CRM_company_crm_folder_id>"
```

This creates the standard 5-folder structure automatically. Use this for new companies.

For existing companies, move files manually:

### Moving Files via API

```
PATCH /api/drive/files/<file_id>/move
Body: {
  "new_parent_id": "<OTHER_FOLDER_ID>",
  "current_parent_id": "<ROOT_FOLDER_ID>"
}
```

### Moving Files via Python (Fly SSH)

```python
def move_to_other(svc, file_id, root_folder_id, other_folder_id):
    svc.files().update(
        fileId=file_id,
        addParents=other_folder_id,
        removeParents=root_folder_id,
        fields='id,parents'
    ).execute()
```

### Profile Perseroan Generation

If no Profil Perseroan document exists for the company, **generate one** as a PDF using the extracted data:

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

def generate_profil_perseroan(data: dict, output_path: str):
    """
    data = {
        "company_name": "PT BACKTOBACK DEVELOPMENT GROUP",
        "company_type": "Perseroan Terbatas (PT) - PMA",
        "status": "TERTUTUP",
        "sk_number": "AHU-0064467.AH.01.01.TAHUN 2024",
        "incorporation_date": "20 Agustus 2024",
        "notaris": "Notaris di Kab. Badung",
        "address": "Jl. Raya Tangeb No. 59, ...",
        "email": "company@gmail.com",
        "phone": "082144087549",
        "nib": "2308240057585",
        "npwp": "07.621.242.2-906.000",
        "kpp": "KPP Pratama Badung Utara",
        "kbli": "68111, 70209",
        "authorized_capital": "Rp 10.100.000.000",
        "shareholders": [
            {"name": "PT Predmet Construction Group", "pct": "50%", "role": "Pemegang Saham Mayoritas"},
            {"name": "Oleksandr Huliaiev", "pct": "30%"},
        ],
        "director": "Ivan Shamrai",
        "commissioner": "Oleksandr Huliaiev",
    }
    """
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm, leftMargin=2.5*cm, rightMargin=2.5*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title2', parent=styles['Title'],
        fontSize=16, spaceAfter=6, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('Subtitle2', parent=styles['Normal'],
        fontSize=10, spaceAfter=12, alignment=TA_CENTER, textColor=colors.grey)

    rows = [
        ("Nama Perseroan", data["company_name"]),
        ("Jenis Perseroan", data.get("company_type", "PT - PMA")),
        ("Status Perseroan", data.get("status", "")),
        ("SK Kemenkumham", data.get("sk_number", "")),
        ("Tanggal Pendirian", data.get("incorporation_date", "")),
        ("", ""),
        ("ALAMAT", ""),
        ("Alamat Lengkap", data.get("address", "")),
        ("Email", data.get("email", "")),
        ("Telepon", data.get("phone", "")),
        ("", ""),
        ("PERIZINAN", ""),
        ("NIB", data.get("nib", "")),
        ("NPWP", data.get("npwp", "")),
        ("KPP Terdaftar", data.get("kpp", "")),
        ("KBLI", data.get("kbli", "")),
        ("", ""),
        ("PERMODALAN", ""),
        ("Modal Dasar", data.get("authorized_capital", "")),
    ]

    for i, sh in enumerate(data.get("shareholders", []), 1):
        role = f" — {sh['role']}" if 'role' in sh else ""
        rows.append((f"{i}. {sh['name']}", f"{sh['pct']}{role}"))

    rows += [("", ""), ("SUSUNAN PENGURUS", ""),
             ("Direktur", data.get("director", "")),
             ("Komisaris", data.get("commissioner", ""))]

    elements = [
        Paragraph("PROFIL PERSEROAN", title_style),
        Paragraph(data["company_name"], subtitle_style),
        Paragraph("Disusun oleh Bali Zero — Redatto", subtitle_style),
        Spacer(1, 0.5*cm),
    ]

    table_data = []
    for label, value in rows:
        if label == "" and value == "":
            table_data.append(["", ""])
        elif value == "":
            table_data.append([Paragraph(f"<b>{label}</b>", styles['Normal']), ""])
        else:
            table_data.append([
                Paragraph(f"<b>{label}</b>", styles['Normal']),
                Paragraph(value, styles['Normal']),
            ])

    table = Table(table_data, colWidths=[6*cm, 10*cm])
    table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(table)
    doc.build(elements)
```

Then upload the generated PDF to the `Profile Perseroan` folder via Drive API.

---

## PHASE 4: UPDATE MASTER SHEET

**Goal:** Write the 18 extracted fields to the correct row in the Master Google Sheet.

### Sheet Structure

- **Sheet ID:** `1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY`
- **Sheet name:** `Company`
- **Column A:** Row number (auto)
- **Column B:** Company folder name (already populated)
- **Column C:** Company short name (already populated)
- **Columns D through U:** The 18 data fields (this is what you write)
- **Header row:** 9
- **Data starts:** Row 10

### Step 1: Find the company row

```
Tool: find_sheet_row
Parameters:
  spreadsheet_id: "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY"
  range: "Company!B10:B"
  search_column: 0
  search_value: "<Company Folder Name>"
```

Or via HTTP:

```
POST /api/sheets/find
Body: {
  "spreadsheet_id": "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY",
  "range": "Company!B10:B",
  "search_column": 0,
  "search_value": "Backtoback Development Group PT"
}
```

Response: `{"status": "found", "row": 1701}` or `{"status": "not_found", "row": null}`

### Step 2: Write the 18 values

If `row` was found:

```
Tool: update_sheet_row
Parameters:
  spreadsheet_id: "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY"
  sheet_name: "Company"
  row_number: <found_row>
  column_start: "D"
  values: [
    "<legal_address>",
    "<nib>",
    "<npwp>",
    "<kbli_codes>",
    "<director_1>",
    "<ownership_pct_1>",
    "<commissioner_1>",
    "<ownership_pct_2>",
    "<investor>",
    "<investor_ownership_pct>",
    "<authorized_capital>",
    "<incorporation_date>",
    "<email>",
    "<phone>",
    "<sk_number>",
    "<kpp>",
    "<company_status>",
    "<office_type>"
  ]
```

Or via HTTP:

```
POST /api/sheets/update-row
Body: {
  "spreadsheet_id": "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY",
  "sheet_name": "Company",
  "row_number": 1701,
  "column_start": "D",
  "values": ["Jl. Raya Tangeb No. 59, ...", "2308240057585", ...]
}
```

### If company NOT found in sheet

If `find_sheet_row` returns `not_found`, the company may not be listed yet. In that case, use `append`:

```
POST /api/sheets/append
Body: {
  "spreadsheet_id": "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY",
  "range": "Company!A:U",
  "values": [["", "<folder_name>", "<short_name>", "<legal_address>", ...18 fields...]]
}
```

### Column Mapping Reference (D-U)

```
D  = values[0]  = Legal Address
E  = values[1]  = NIB
F  = values[2]  = NPWP
G  = values[3]  = KBLI (comma-separated codes)
H  = values[4]  = Director 1
I  = values[5]  = Ownership % (Director)
J  = values[6]  = Commissioner 1
K  = values[7]  = Ownership % (Commissioner)
L  = values[8]  = Investor (optional, empty string if none)
M  = values[9]  = Ownership % (Investor)
N  = values[10] = Authorized Capital
O  = values[11] = Incorporation Date
P  = values[12] = Official Email
Q  = values[13] = Official Phone
R  = values[14] = SK Number (AHU-...)
S  = values[15] = Tax Office (KPP)
T  = values[16] = Company Status (TERTUTUP/TERBUKA)
U  = values[17] = Office Type (PMA/PMDN)
```

---

## BULK PROCESSING

When processing all ~1,700 companies sequentially:

### Algorithm

```
for each company_folder in CRM/Company_CRM/:
    1. list files in company_folder
    2. identify which documents exist (AKTA, NIB, NPWP, Profil Perseroan)
    3. download and extract text from each document
    4. parse the 18 fields from extracted text
    5. create missing standard folders (AKTA, NIB, NPWP, Profile Perseroan, Other)
    6. move non-standard items to Other/
    7. if no Profil Perseroan exists → generate PDF and upload
    8. find company row in Master Sheet
    9. write 18 fields to row
    10. log result (success/partial/error)
    11. wait 0.5s (rate limiting)
```

### Progress Logging

Maintain a JSON log file:

```json
{
  "total": 1700,
  "processed": 142,
  "successful": 135,
  "partial": 5,
  "errors": 2,
  "companies": [
    {
      "name": "Backtoback Development Group PT",
      "status": "success",
      "fields_extracted": 18,
      "fields_empty": 2,
      "folder_organized": true,
      "profile_generated": true,
      "sheet_updated": true,
      "timestamp": "2026-03-01T18:30:00Z"
    }
  ]
}
```

### Rate Limiting

- Google Drive API: 10 requests/second per user → 0.5s pause between companies
- Google Sheets API: 60 writes/minute → batch writes when possible
- If rate-limited (HTTP 429), exponential backoff: wait 2s, 4s, 8s, max 60s

### Error Handling

| Error               | Action                               |
| ------------------- | ------------------------------------ |
| Folder not found    | Skip, log as error                   |
| PDF unreadable      | Mark fields as empty, log as partial |
| Sheet row not found | Use append instead of update         |
| Rate limited (429)  | Exponential backoff, retry 3 times   |
| Auth expired        | Re-authenticate and retry            |
| Network timeout     | Retry once after 5s                  |

### Partial Success

A company is `partial` if:

- Some fields were extracted but not all
- Folder was organized but sheet not updated
- Sheet was updated but folder not organized

Always write whatever data you have — partial data is better than no data.

---

## COMMON PATTERNS

### Indonesian Document Terms

| Indonesian                      | English                        | Where Found |
| ------------------------------- | ------------------------------ | ----------- |
| Akta Pendirian                  | Deed of Establishment          | AKTA folder |
| SK Pendirian                    | Decree of Establishment        | AKTA folder |
| Nomor Induk Berusaha            | Business Identification Number | NIB.pdf     |
| Nomor Pokok Wajib Pajak         | Taxpayer ID                    | NPWP.pdf    |
| Klasifikasi Baku Lapangan Usaha | Business Field Classification  | NIB/Profil  |
| Modal Dasar                     | Authorized Capital             | AKTA        |
| Modal Ditempatkan               | Paid-up Capital                | AKTA        |
| Pemegang Saham                  | Shareholder                    | AKTA        |
| Direktur                        | Director                       | AKTA        |
| Komisaris                       | Commissioner                   | AKTA        |
| Perseroan Terbatas              | Limited Liability Company      | AKTA        |
| Tertutup                        | Private/Closed                 | AKTA        |
| Terbuka                         | Public/Open                    | AKTA        |
| Penanaman Modal Asing           | Foreign Investment (PMA)       | NIB         |
| Penanaman Modal Dalam Negeri    | Domestic Investment (PMDN)     | NIB         |

### Regex Patterns for Extraction

```python
import re

# NIB (13 digits)
nib = re.search(r'\b(\d{13})\b', text)

# NPWP (XX.XXX.XXX.X-XXX.XXX)
npwp = re.search(r'(\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})', text)

# SK Number (AHU-XXXXXXX.AH.01.01.TAHUN YYYY)
sk = re.search(r'(AHU-\d+\.AH\.\d+\.\d+\.TAHUN\s*\d{4})', text)

# Capital amount (Rp followed by digits and dots)
capital = re.search(r'Rp\.?\s*([\d.]+)', text)

# KBLI codes (5-digit numbers)
kbli_codes = re.findall(r'\b(\d{5})\b', text)

# Phone numbers (Indonesian format)
phone = re.search(r'(0\d{9,12}|\+62\d{9,12})', text)

# Email
email = re.search(r'([\w.+-]+@[\w.-]+\.\w+)', text)
```

---

## IMPORTANT NOTES

1. **Never delete files.** Only move them. If something looks wrong, leave it and flag for manual review.
2. **Never overwrite existing Sheet data** without first reading what's already there. If a cell already has data, skip it unless the existing data is clearly wrong.
3. **The Service Account uses Domain-Wide Delegation for Drive** but **Direct SA mode for Sheets** (Sheets shared with SA as Editor). This is because DWD doesn't have Sheets scope configured.
4. **Profile Perseroan PDFs you generate** should be clearly marked as "Disusun oleh Bali Zero — Redatto" (not official OSS documents).
5. **KBLI codes** — write only the 5-digit code, not the description. Multiple codes separated by commas with spaces: `"68111, 70209"`.
6. **If you encounter a company with no readable documents at all**, skip it entirely and log it for manual processing.
7. **Columns L and M (Investor)** — Many companies don't have a separate investor. If the shareholders are only individuals, leave L and M empty.

---

## WORKED EXAMPLE: BACKTOBACK DEVELOPMENT GROUP PT

### Phase 1: Exploration

Listed folder `1V1BcajeME-mZqhwtT93q9eMsFW6RrJkh`:

```
[DIR] AKTA/                    1YP1XCXc82_l6gJoxEGOxb2NvDmvYUPWE
[DIR] DOKUMEN/                 1v4c_fkk78zcqRoi4eMEKFR9hhXOZGLFz
[DIR] KHASAN KHATER/           ...
[DIR] NIB/                     14xqNMIjgfYmYxfMe_kR5CKlKeQqPlzwY
[DIR] NPWP/                    1uIqj3O2JdpljJUax-Gff9CBM3Rb9LLwS
[DIR] WAJIB LAPOR/             ...
[FILE] various loose files...
```

### Phase 2: Extraction

Read AKTA documents. Extracted:

```
company_name: PT BACKTOBACK DEVELOPMENT GROUP
company_type: Perseroan Terbatas (PT) - PMA
status: TERTUTUP
sk_number: AHU-0064467.AH.01.01.TAHUN 2024
incorporation_date: 20 Agustus 2024
address: Jl. Raya Tangeb No. 59, Abianbase, Kec. Mengwi, Kab. Badung, Bali 80351
email: backtobackdevelopmentgroup@gmail.com
phone: 082144087549
nib: 2308240057585
npwp: 07.621.242.2-906.000
kpp: KPP Pratama Badung Utara
kbli: 68111, 70209
authorized_capital: Rp 10.100.000.000
shareholders:
  - PT Predmet Construction Group: 50% (Pemegang Saham Mayoritas)
  - Oleksandr Huliaiev: 30%
  - Roman Beznosiuk: 15%
  - Taras Levchyk: 5%
director: Ivan Shamrai
commissioner: Oleksandr Huliaiev
```

### Phase 3: Organization

Created `Other/` and `Profile Perseroan/` folders. Moved 12 non-standard items (DOKUMEN, KHASAN KHATER, WAJIB LAPOR, loose files) to `Other/`.

Root now contains exactly: AKTA, NIB, NPWP, Profile Perseroan, Other.

Generated Profil Perseroan PDF and uploaded to Profile Perseroan folder.

### Phase 4: Sheet Update

Found row via append (company wasn't in sheet yet). Wrote 18 values:

```python
values = [
    "Jl. Raya Tangeb No. 59, Abianbase, Kec. Mengwi, Kab. Badung, Bali 80351",  # D
    "2308240057585",                    # E
    "07.621.242.2-906.000",             # F
    "68111, 70209",                     # G
    "Ivan Shamrai",                     # H
    "",                                 # I - Director ownership not specified separately
    "Oleksandr Huliaiev",               # J
    "30%",                              # K
    "PT Predmet Construction Group",    # L - Investor/majority shareholder
    "50%",                              # M
    "Rp 10.100.000.000",               # N
    "20 Agustus 2024",                  # O
    "backtobackdevelopmentgroup@gmail.com",  # P
    "082144087549",                     # Q
    "AHU-0064467.AH.01.01.TAHUN 2024", # R
    "KPP Pratama Badung Utara",         # S
    "TERTUTUP",                         # T
    "PMA",                              # U
]
```

Result: Row 1701 updated successfully, 18 cells written.

---

## TROUBLESHOOTING

| Problem                             | Solution                                                              |
| ----------------------------------- | --------------------------------------------------------------------- |
| `unauthorized_client` on Sheets API | Use Direct SA, not DWD. Sheet must be shared with SA email as Editor. |
| `!` in range causes parse error     | Use POST endpoint instead of GET, or escape as `\!`                   |
| `Invalid \escape` in curl JSON      | Write JSON to file, use `curl -d @file.json`                          |
| PDF returns empty text              | Scanned PDF — use `pdftoppm` + OCR or vision model                    |
| Company not found in Sheet          | Use `append` instead of `update-row`                                  |
| Rate limited (429)                  | Wait with exponential backoff, retry                                  |
| Service Account can't access folder | Ensure folder is shared with SA email or use DWD with Drive scope     |

---

## SUMMARY CHECKLIST PER COMPANY

- [ ] List all files in company folder
- [ ] Download and read AKTA, NIB, NPWP, Profil Perseroan
- [ ] Extract 18 fields into structured data
- [ ] Create missing standard folders (AKTA, NIB, NPWP, Profile Perseroan, Other)
- [ ] Move all non-standard items to Other/
- [ ] If no Profil Perseroan exists → generate PDF and upload
- [ ] Find company row in Master Sheet (or append new row)
- [ ] Write 18 fields to columns D-U
- [ ] Verify: root has exactly 5 folders
- [ ] Log result

---

_End of guideline. This document is the single source of truth for CRM automation. Follow it exactly._
