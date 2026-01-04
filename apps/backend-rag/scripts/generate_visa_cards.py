#!/usr/bin/env python3
"""
Generate Professional Visa Cards for Bali Zero
Creates PDF cards and updates database via API
"""

import shutil
from pathlib import Path

import requests
from weasyprint import CSS, HTML

# Paths
DESKTOP = Path("/Users/antonellosiano/Desktop")
PUBLIC_FILES = Path("/Users/antonellosiano/Desktop/nuzantara/apps/mouth/public/files/visa")
LOGO_PATH = Path(
    "/Users/antonellosiano/Desktop/nuzantara/apps/mouth/public/images/balizero-logo.png"
)
API_BASE = "https://nuzantara-rag.fly.dev/api/knowledge/visa"

# Ensure directories exist
PUBLIC_FILES.mkdir(parents=True, exist_ok=True)

# Copy logo to desktop if not there
DESKTOP_LOGO = DESKTOP / "balizero-logo.png"
if not DESKTOP_LOGO.exists():
    shutil.copy(LOGO_PATH, DESKTOP_LOGO)


def generate_html(visa_data: dict) -> str:
    """Generate HTML for visa card"""

    # Format prices
    prices_html = ""
    if visa_data.get("cost_details"):
        details = visa_data["cost_details"]
        if details.get("offshore"):
            prices_html += f"""
                <div class="price-card featured">
                    <div class="price-type">Offshore</div>
                    <div class="price-amount">{int(details["offshore"]):,} <span>IDR</span></div>
                </div>"""
        if details.get("onshore"):
            prices_html += f"""
                <div class="price-card">
                    <div class="price-type">Onshore</div>
                    <div class="price-amount">{int(details["onshore"]):,} <span>IDR</span></div>
                </div>"""
        if details.get("extension"):
            prices_html += f"""
                <div class="price-card">
                    <div class="price-type">Extension</div>
                    <div class="price-amount">{int(details["extension"]):,} <span>IDR</span></div>
                </div>"""
        # For single price visas
        if details.get("price_1y"):
            prices_html += f"""
                <div class="price-card featured">
                    <div class="price-type">1 Year</div>
                    <div class="price-amount">{int(details["price_1y"]):,} <span>IDR</span></div>
                </div>"""
        if details.get("price_2y"):
            prices_html += f"""
                <div class="price-card">
                    <div class="price-type">2 Years</div>
                    <div class="price-amount">{int(details["price_2y"]):,} <span>IDR</span></div>
                </div>"""

    # Requirements list
    requirements_html = ""
    for req in visa_data.get("requirements", []):
        requirements_html += f'<div class="list-item">{req}</div>\n'

    # Benefits list
    benefits_html = ""
    for ben in visa_data.get("benefits", []):
        benefits_html += f'<div class="list-item">{ben}</div>\n'

    # Process steps
    steps_html = ""
    for i, step in enumerate(visa_data.get("process_steps", []), 1):
        step_name = step.split("(")[0].strip() if "(" in step else step
        step_time = step.split("(")[1].replace(")", "") if "(" in step else ""
        steps_html += f"""
            <div class="step">
                <div class="step-number">{i}</div>
                <div class="step-label">{step_name}</div>
                <div class="step-time">{step_time}</div>
            </div>"""

    # Dependent note
    dependent_note = ""
    if visa_data.get("metadata", {}).get("dependent_note"):
        note = visa_data["metadata"]["dependent_note"]
        dependent_note = f"""
            <div class="dependent-note">
                <strong>Note:</strong> {note}
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{visa_data["name"]} - Bali Zero</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(145deg, #1a1a1a 0%, #2d2d2d 50%, #1a1a1a 100%);
            min-height: 100vh;
            padding: 40px;
            color: #ffffff;
        }}
        .card {{
            max-width: 700px;
            margin: 0 auto;
            background: linear-gradient(145deg, #242424 0%, #1a1a1a 100%);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.08);
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            padding: 40px;
            display: flex;
            align-items: center;
            gap: 32px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .logo-container {{ width: 100px; height: 100px; flex-shrink: 0; }}
        .logo-container img {{ width: 100%; height: 100%; object-fit: contain; border-radius: 50%; }}
        .header-content {{ flex: 1; }}
        .visa-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 16px;
            border-radius: 100px;
            font-size: 12px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
            margin-bottom: 12px;
        }}
        .visa-title {{ font-size: 28px; font-weight: 800; color: #fff; letter-spacing: -1px; }}
        .visa-subtitle {{ font-size: 14px; color: rgba(255, 255, 255, 0.7); margin-top: 8px; }}
        .content {{ padding: 30px; }}
        .price-grid {{ display: flex; gap: 15px; margin-bottom: 30px; flex-wrap: wrap; }}
        .price-card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 16px 20px;
            text-align: center;
            flex: 1;
            min-width: 150px;
        }}
        .price-card.featured {{ background: rgba(229, 57, 53, 0.1); border-color: rgba(229, 57, 53, 0.3); }}
        .price-type {{ font-size: 11px; color: rgba(255, 255, 255, 0.5); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
        .price-amount {{ font-size: 20px; font-weight: 800; color: #fff; }}
        .price-amount span {{ font-size: 12px; font-weight: 500; color: rgba(255, 255, 255, 0.6); }}
        .stats-row {{ display: flex; gap: 12px; margin-bottom: 30px; flex-wrap: wrap; }}
        .stat {{ text-align: center; padding: 15px; background: rgba(255, 255, 255, 0.03); border-radius: 12px; flex: 1; min-width: 100px; }}
        .stat-value {{ font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
        .stat-label {{ font-size: 10px; color: rgba(255, 255, 255, 0.5); text-transform: uppercase; letter-spacing: 0.5px; }}
        .section {{ margin-bottom: 25px; }}
        .section-title {{
            font-size: 12px;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.4);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .list {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }}
        .list-item {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.85);
            line-height: 1.4;
        }}
        .list-item::before {{
            content: '';
            width: 5px;
            height: 5px;
            background: #e53935;
            border-radius: 50%;
            margin-top: 5px;
            flex-shrink: 0;
        }}
        .timeline {{ background: rgba(255, 255, 255, 0.03); border-radius: 16px; padding: 20px; }}
        .timeline-header {{ font-size: 12px; font-weight: 700; color: rgba(255, 255, 255, 0.4); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 15px; text-align: center; }}
        .timeline-steps {{ display: flex; justify-content: space-around; position: relative; }}
        .timeline-steps::before {{ content: ''; position: absolute; top: 14px; left: 60px; right: 60px; height: 2px; background: rgba(255, 255, 255, 0.2); }}
        .step {{ text-align: center; position: relative; z-index: 1; }}
        .step-number {{ width: 28px; height: 28px; background: #e53935; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; color: white; margin: 0 auto 6px; }}
        .step-label {{ font-size: 10px; color: rgba(255, 255, 255, 0.7); max-width: 80px; }}
        .step-time {{ font-size: 10px; color: #e53935; font-weight: 600; margin-top: 3px; }}
        .footer {{
            background: rgba(0, 0, 0, 0.3);
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .footer-left {{ font-size: 11px; color: rgba(255, 255, 255, 0.4); }}
        .footer-contact {{ display: flex; gap: 20px; font-size: 12px; color: rgba(255, 255, 255, 0.7); }}
        .footer-contact a {{ color: #e53935; text-decoration: none; }}
        .dependent-note {{
            background: rgba(229, 57, 53, 0.1);
            border: 1px solid rgba(229, 57, 53, 0.2);
            border-radius: 12px;
            padding: 14px 18px;
            margin-top: 20px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.8);
        }}
        .dependent-note strong {{ color: #e53935; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <div class="logo-container">
                <img src="balizero-logo.png" alt="Bali Zero">
            </div>
            <div class="header-content">
                <div class="visa-badge">
                    <span>{visa_data["category"]}</span>
                    <span>-</span>
                    <span>{visa_data.get("duration", "Multiple Entry")}</span>
                </div>
                <h1 class="visa-title">{visa_data["name"]}</h1>
                <p class="visa-subtitle">{visa_data.get("code", "")} - {visa_data.get("total_stay", "")}</p>
            </div>
        </div>

        <div class="content">
            <div class="price-grid">
                {prices_html}
            </div>

            <div class="stats-row">
                <div class="stat">
                    <div class="stat-value">{visa_data.get("duration", "Varies")}</div>
                    <div class="stat-label">Validity</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{visa_data.get("processing_time_normal", "~2-3 weeks")}</div>
                    <div class="stat-label">Processing</div>
                </div>
                <div class="stat">
                    <div class="stat-value">Multiple</div>
                    <div class="stat-label">Entry</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{"Yes" if visa_data.get("renewable") else "Extendable"}</div>
                    <div class="stat-label">Renewal</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">Requirements</div>
                <div class="list">
                    {requirements_html}
                </div>
            </div>

            <div class="section">
                <div class="section-title">Benefits</div>
                <div class="list">
                    {benefits_html}
                </div>
            </div>

            <div class="timeline">
                <div class="timeline-header">Processing Timeline ({visa_data.get("processing_time_normal", "~2-3 weeks")})</div>
                <div class="timeline-steps">
                    {steps_html}
                </div>
            </div>

            {dependent_note}
        </div>

        <div class="footer">
            <div class="footer-left">
                Official Bali Zero Prices 2025
            </div>
            <div class="footer-contact">
                <span><a href="mailto:info@balizero.com">info@balizero.com</a></span>
                <span>+62 813 3805 1876</span>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html


def create_pdf(visa_data: dict, filename: str):
    """Create PDF from visa data"""
    html_content = generate_html(visa_data)

    # Write HTML to desktop
    html_path = DESKTOP / f"{filename}.html"
    with open(html_path, "w") as f:
        f.write(html_content)

    # Generate PDF
    pdf_path = DESKTOP / f"{filename}.pdf"
    HTML(string=html_content, base_url=str(DESKTOP)).write_pdf(
        str(pdf_path), stylesheets=[CSS(string="@page { size: A4; margin: 1.5cm; }")]
    )

    # Copy to public folder
    shutil.copy(pdf_path, PUBLIC_FILES / f"{filename}.pdf")

    print(f"Created: {filename}.pdf")
    return f"/files/visa/{filename}.pdf"


def update_visa_api(visa_id: int, data: dict):
    """Update visa via API"""
    try:
        response = requests.put(f"{API_BASE}/{visa_id}", json=data)
        if response.status_code == 200:
            print(f"Updated visa ID {visa_id}: {data.get('name', 'Unknown')}")
            return True
        else:
            print(f"Failed to update visa ID {visa_id}: {response.text}")
            return False
    except Exception as e:
        print(f"Error updating visa ID {visa_id}: {e}")
        return False


# ============================================================================
# VISA DATA - From KB + Official Pricing
# ============================================================================

VISAS = [
    {
        "id": 24,  # E33G in database
        "code": "E33G",
        "name": "Digital Nomad KITAS",
        "category": "KITAS",
        "duration": "1 year",
        "total_stay": "1 year (extendable annually)",
        "processing_time_normal": "~2-3 weeks",
        "renewable": True,
        "cost_visa": "IDR 13,000,000 (offshore) / IDR 14,000,000 (onshore)",
        "cost_extension": "IDR 10,000,000",
        "cost_details": {"offshore": "13000000", "onshore": "14000000", "extension": "10000000"},
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Proof of remote work (employment letter/contract)",
            "Proof of income min USD 5,000/month (USD 60,000/year)",
            "Bank statement 3 months",
            "Travel/health insurance",
            "CV / Resume",
        ],
        "benefits": [
            "Work remotely for foreign companies",
            "Multiple entry/exit Indonesia",
            "No IMTA/RPTKA work permit needed",
            "No Indonesian sponsor required",
            "Path to KITAP after 4-5 years",
        ],
        "allowed_activities": [
            "Remote work for foreign employers",
            "Attend online meetings",
            "Work from cafes, coworking, home",
            "Travel around Indonesia",
        ],
        "restrictions": [
            "Cannot work for Indonesian companies",
            "Cannot receive salary from Indonesian sources",
            "Cannot open office/recruit local staff",
        ],
        "process_steps": [
            "Document Submission (Day 1-5)",
            "Evisa Processing (Day 6-14)",
            "KITAS Delivery (Day 15-21)",
        ],
        "tips": [
            "Maintain income proof of USD 5,000+/month (USD 60,000/year)",
            "SKTT reporting every 3 months required",
            "Keep insurance active throughout stay",
        ],
        "metadata": {
            "dependent_note": "No tax obligation if income from abroad + transferred to foreign account",
            "income_requirement": "USD 5,000/month (USD 60,000/year)",
        },
    },
    {
        "id": 20,  # D1 in database
        "code": "D1",
        "name": "Tourism Multiple Entry Visa",
        "category": "Visit",
        "duration": "5 years",
        "total_stay": "60 days per entry",
        "processing_time_normal": "~5-10 days",
        "renewable": False,
        "cost_visa": "IDR 5,000,000 - 7,000,000",
        "cost_details": {"government_fee": "USD 100", "total_estimate": "5000000-7000000"},
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "National ID from home country",
            "Bank statement 3 months (min USD 5,000)",
            "Round trip flight booking",
            "Hotel reservation",
            "Brief itinerary",
        ],
        "benefits": [
            "5-year validity",
            "Multiple entry unlimited",
            "All international entry points",
            "No need to reapply each trip",
            "Perfect for frequent travelers",
        ],
        "allowed_activities": [
            "Tourism and holidays",
            "Family visits",
            "Attend events",
            "Travel around Indonesia",
        ],
        "restrictions": [
            "60 days max per entry (no extension)",
            "Cannot work in Indonesia",
            "Must exit and re-enter for new 60 days",
            "Apply offshore only",
        ],
        "process_steps": [
            "Document Preparation (Day 1-3)",
            "Evisa Submission (Day 4-7)",
            "Approval & Collection (Day 8-10)",
        ],
        "tips": [
            "Cannot extend stay - must exit after 60 days",
            "Apply 1-2 months before travel",
            "Any currency acceptable for bank proof",
        ],
        "metadata": {"dependent_note": "Exit to Singapore 1 day to reset 60-day counter"},
    },
    {
        "id": 21,  # D12 in database
        "code": "D12",
        "name": "Business Investigation Visa",
        "category": "Visit",
        "duration": "1-2 years",
        "total_stay": "180 days per entry",
        "processing_time_normal": "~2-3 weeks",
        "renewable": False,
        "cost_visa": "IDR 7,500,000 (1Y) / IDR 10,000,000 (2Y)",
        "cost_details": {"price_1y": "7500000", "price_2y": "10000000"},
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "CV / Resume (business focus)",
            "Bank statement (min USD 2,000)",
            "Cover letter explaining visit purpose",
            "Sponsor/guarantor letter",
        ],
        "benefits": [
            "180 days per entry (not 60!)",
            "Multiple entry for 1-2 years",
            "Market research allowed",
            "Site visits and meetings",
            "Path to PT PMA setup",
        ],
        "allowed_activities": [
            "Meet potential partners/suppliers",
            "Visit locations for future offices",
            "Attend trade fairs/business events",
            "Consult lawyers, notaries, accountants",
            "Open bank account (some banks)",
        ],
        "restrictions": [
            "Cannot work or earn income",
            "Cannot sign contracts as employee",
            "Cannot manage company operations",
            "Apply offshore only",
        ],
        "process_steps": [
            "Document Preparation (Day 1-5)",
            "Sponsor Coordination (Day 6-10)",
            "Immigration Approval (Day 11-21)",
        ],
        "tips": [
            "Bali Zero can sponsor your D12",
            "Extendable +60 days (max 240/entry)",
            "Typical path: D12 -> PT PMA -> E28A",
        ],
        "metadata": {
            "dependent_note": "For pre-investment market research and feasibility studies"
        },
    },
    {
        "id": 25,  # E33E Retirement KITAS (55+, 5 years)
        "code": "E33E",
        "name": "Retirement KITAS (Lanjut Usia 55+, 5 Years)",
        "category": "KITAS",
        "duration": "5 years",
        "total_stay": "5 years (extendable to KITAP)",
        "extensions": "Can extend or convert to KITAP after 5 years",
        "processing_time_normal": "~2-3 weeks",
        "renewable": True,
        "cost_visa": "IDR 18,000,000 (5 years all-inclusive)",
        "cost_extension": "IDR 12,000,000",
        "cost_details": {
            "total_5_years": "18000000",
            "includes": "e-ITAS + Re-Entry Permit 5 years",
        },
        "requirements": [
            "Age 55+ years old",
            "Passport valid min 6 years (or until visa expires)",
            "Photo 4x6 red background",
            "Bank deposit USD 50,000 at Indonesian state bank",
            "Proof of monthly income USD 3,000+",
            "Health insurance valid in Indonesia",
            "No criminal record",
            "Medical fitness certificate",
        ],
        "benefits": [
            "5 years without annual renewals",
            "No local sponsor required",
            "Multiple entry/exit",
            "Path to KITAP (permanent residence)",
            "Lower total cost vs annual renewals",
        ],
        "allowed_activities": [
            "Retire and live in Indonesia",
            "Travel freely in/out of Indonesia",
            "Enjoy Indonesian lifestyle",
        ],
        "restrictions": [
            "Cannot work in Indonesia (formal or informal)",
            "Cannot conduct business activities",
            "Cannot receive Indonesian income",
        ],
        "process_steps": [
            "Document preparation (Day 1-3)",
            "Bank deposit at BNI/BRI/Mandiri/BTN (Day 4-7)",
            "Immigration review (Day 8-14)",
            "KITAS card delivery (Day 15-21)",
        ],
        "tips": [
            "USD 50,000 must be deposited in BNI, BRI, Mandiri, or BTN",
            "Income proof: pension statements, investment returns, rental income",
            "No annual renewal hassle - valid 5 full years",
            "Apply directly without Indonesian sponsor",
        ],
        "metadata": {
            "age_requirement": 55,
            "financial_requirement": 50000,
            "monthly_income": 3000,
            "sponsor_required": False,
            "dependent_note": "Spouse (55+) can apply separately with same requirements",
        },
    },
    {
        "id": 31,  # E33F Retirement KITAS (Pension 55+) in database
        "code": "E33F",
        "name": "Retirement KITAS (Pension 55+)",
        "category": "KITAS",
        "duration": "1 year",
        "total_stay": "1 year (extendable 5x, then KITAP)",
        "extensions": "Renewable annually up to 5 years, then eligible for KITAP",
        "processing_time_normal": "~2-3 weeks",
        "renewable": True,
        "cost_visa": "IDR 14,000,000 (first year) / IDR 11,000,000 (renewals)",
        "cost_extension": "IDR 11,000,000",
        "cost_details": {
            "first_year": "14000000",
            "renewal": "11000000",
            "government_fee": "2700000",
        },
        "requirements": [
            "Age 55+ years old",
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Proof of monthly income/pension USD 1,500+",
            "Local sponsor required (visa agent)",
            "Health insurance valid in Indonesia",
            "No criminal record",
            "Medical fitness certificate",
        ],
        "benefits": [
            "No large upfront deposit required",
            "Lower financial threshold (USD 1,500 vs USD 3,000)",
            "Multiple entry/exit",
            "Path to KITAP after 5 consecutive years",
            "Sponsor handles all paperwork",
        ],
        "allowed_activities": [
            "Retire and live in Indonesia",
            "Travel freely in/out of Indonesia",
            "Enjoy Indonesian lifestyle",
        ],
        "restrictions": [
            "Cannot work in Indonesia (formal or informal)",
            "Cannot conduct business activities",
            "Cannot receive Indonesian income",
            "Must renew annually",
        ],
        "process_steps": [
            "Document preparation (Day 1-3)",
            "Sponsor submission to Immigration (Day 4-7)",
            "Immigration review (Day 8-14)",
            "KITAS card delivery (Day 15-21)",
        ],
        "tips": [
            "Must have Indonesian sponsor (visa agent)",
            "Income proof: pension statements, investment returns, bank interest",
            "Renew 1-2 months before expiry to avoid gaps",
            "After 5 consecutive years, apply for KITAP",
        ],
        "metadata": {
            "age_requirement": 55,
            "monthly_income": 1500,
            "sponsor_required": True,
            "popularity": "high",
            "difficulty": "low",
            "bali_zero_recommended": True,
            "dependent_note": "Spouse eligible for Dependent KITAS at separate cost",
        },
    },
    {
        "id": None,  # Will create new - Working KITAS
        "code": "E23",
        "name": "Working KITAS (IMTA)",
        "category": "KITAS",
        "duration": "1 year",
        "total_stay": "1 year (renewable)",
        "processing_time_normal": "~4-6 weeks",
        "renewable": True,
        "cost_visa": "IDR 34,500,000 (offshore) / IDR 36,000,000 (onshore)",
        "cost_extension": "IDR 31,500,000",
        "cost_details": {"offshore": "34500000", "onshore": "36000000", "extension": "31500000"},
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "CV / Resume",
            "Degree certificate (legalized)",
            "Employment contract",
            "Sponsor company (PT) in Indonesia",
            "RPTKA approval from Ministry",
            "Company NIB and OSS",
        ],
        "benefits": [
            "Legal employment in Indonesia",
            "Work for Indonesian company",
            "IMTA work permit included",
            "Path to KITAP after 4 years",
            "Bring family on Dependent KITAS",
        ],
        "allowed_activities": [
            "Work for sponsoring company",
            "Attend business meetings",
            "Sign contracts as employee",
            "Receive Indonesian salary",
        ],
        "restrictions": [
            "Must work for sponsor only",
            "1:10 expat to local ratio",
            "Job must match RPTKA",
            "Cannot change employer easily",
        ],
        "process_steps": [
            "RPTKA Application (Day 1-14)",
            "IMTA Processing (Day 15-28)",
            "KITAS Issuance (Day 29-42)",
        ],
        "tips": [
            "Requires Indonesian company sponsor",
            "RPTKA must be approved first",
            "Most complex visa type",
        ],
        "metadata": {"dependent_note": "Family can apply Dependent KITAS 1Y at IDR 11M offshore"},
    },
    {
        "id": None,  # Will create new - Spouse KITAS
        "code": "E26",
        "name": "Spouse KITAS (Indonesian Marriage)",
        "category": "KITAS",
        "duration": "1-2 years",
        "total_stay": "Matches visa duration",
        "processing_time_normal": "~3-4 weeks",
        "renewable": True,
        "cost_visa": "IDR 11,000,000 (1Y offshore) / IDR 15,000,000 (2Y offshore)",
        "cost_extension": "IDR 9,000,000 (1Y) / IDR 15,000,000 (2Y)",
        "cost_details": {
            "offshore": "11000000",
            "onshore": "13500000",
            "extension": "9000000",
            "offshore_2y": "15000000",
            "onshore_2y": "18000000",
        },
        "requirements": [
            "Marriage certificate (legalized)",
            "Spouse's KTP and Kartu Keluarga",
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Sponsor letter from Indonesian spouse",
            "Proof of residence",
        ],
        "benefits": [
            "Live with Indonesian spouse",
            "Multiple entry/exit",
            "Path to KITAP after 2 years",
            "Can apply for work permit separately",
            "Children eligible for Dependent KITAS",
        ],
        "allowed_activities": [
            "Reside in Indonesia",
            "Travel freely",
            "Can apply for separate work permit",
            "Open bank account",
        ],
        "restrictions": [
            "Cannot work without IMTA",
            "Must maintain valid marriage",
            "Report to immigration quarterly",
        ],
        "process_steps": [
            "Document Preparation (Day 1-5)",
            "Marriage Verification (Day 6-14)",
            "KITAS Issuance (Day 15-28)",
        ],
        "tips": [
            "KITAP eligible after 2 years",
            "Marriage must be registered in Indonesia",
            "Faster path to permanent residency",
        ],
        "metadata": {"dependent_note": "For foreigners married to Indonesian citizens"},
    },
    {
        "id": None,  # Will create - Dependent KITAS
        "code": "E31",
        "name": "Dependent KITAS (Family of KITAS Holder)",
        "category": "KITAS",
        "duration": "1-2 years",
        "total_stay": "Matches sponsor",
        "processing_time_normal": "~2-3 weeks",
        "renewable": True,
        "cost_visa": "IDR 11,000,000 (1Y offshore) / IDR 15,000,000 (2Y offshore)",
        "cost_extension": "IDR 9,000,000 (1Y) / IDR 15,000,000 (2Y)",
        "cost_details": {
            "offshore": "11000000",
            "onshore": "13500000",
            "extension": "9000000",
            "offshore_2y": "15000000",
            "onshore_2y": "18000000",
        },
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Marriage cert (spouse) or Birth cert (children)",
            "Sponsor's KITAS copy",
            "Sponsor letter",
            "Family relationship proof",
        ],
        "benefits": [
            "Live with KITAS holder family member",
            "Multiple entry/exit",
            "Validity matches sponsor",
            "Children can attend school",
            "Path to KITAP with sponsor",
        ],
        "allowed_activities": [
            "Reside with sponsor",
            "Travel within Indonesia",
            "Children: attend school",
            "Open bank account",
        ],
        "restrictions": [
            "Cannot work without separate permit",
            "Validity tied to sponsor",
            "Must exit if sponsor's KITAS cancelled",
        ],
        "process_steps": [
            "Document Preparation (Day 1-3)",
            "Sponsor Verification (Day 4-10)",
            "KITAS Issuance (Day 11-21)",
        ],
        "tips": [
            "Apply together with main KITAS holder",
            "Children under 18 automatically eligible",
            "Spouse must prove marriage",
        ],
        "metadata": {
            "dependent_note": "For spouse and children of KITAS holders (not Indonesian spouse)"
        },
    },
]


def main():
    print("=" * 60)
    print("BALI ZERO VISA CARD GENERATOR")
    print("=" * 60)

    for visa in VISAS:
        visa_id = visa.pop("id", None)
        code = visa["code"]
        name = visa["name"]

        # Generate filename
        filename = f"{code}_{name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')}_BaliZero"

        # Create PDF
        pdf_url = create_pdf(visa, filename)
        visa["metadata"]["pdf_url"] = pdf_url

        # Update or create via API
        if visa_id:
            update_visa_api(visa_id, visa)
        else:
            # Create new visa
            try:
                response = requests.post(API_BASE, json=visa)
                if response.status_code == 200:
                    result = response.json()
                    print(f"Created new visa: {name} (ID: {result.get('id')})")
                else:
                    print(f"Failed to create {name}: {response.text}")
            except Exception as e:
                print(f"Error creating {name}: {e}")

    print("\n" + "=" * 60)
    print("COMPLETED!")
    print(f"PDFs saved to: {DESKTOP}")
    print(f"PDFs deployed to: {PUBLIC_FILES}")
    print("=" * 60)


if __name__ == "__main__":
    main()
