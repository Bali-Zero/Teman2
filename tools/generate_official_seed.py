import re
import json

def parse_visa_text(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Split by headers like "## A1 - ..."
    sections = re.split(r'##\s+([A-Z0-9]+)\s+-\s+(.+)', content)
    
    visa_types = []
    
    # Skip preamble (index 0)
    for i in range(1, len(sections), 3):
        code = sections[i].strip()
        name = sections[i+1].strip()
        body = sections[i+2].strip()
        
        # Helper to extract section content
        def extract_section(header_pattern, text):
            # Find start of header
            match = re.search(header_pattern, text, re.IGNORECASE)
            if not match:
                return None
            start_idx = match.end()
            
            # Find start of NEXT header (any known header)
            # We look for a newline followed by **Header**:
            next_match = re.search(r'\n\s*\*\*[A-Za-z0-9 &/\(\)-]+:\*\*', text[start_idx:])
            
            if next_match:
                content = text[start_idx : start_idx + next_match.start()]
            else:
                content = text[start_idx:]
            
            return content.strip()

        purpose = extract_section(r'\*\*Purpose:\*\*', body) or ""
        type_info = extract_section(r'\*\*Visa Type(?: & Duration)?:\*\*', body) or ""
        # Handle Type alias
        if not type_info:
             type_info = extract_section(r'\*\*Type:\*\*', body) or ""

        cost = extract_section(r'\*\*(?:Cost|Fee|Fees):\*\*', body) or "See description"
        requirements_raw = extract_section(r'\*\*Requirements:\*\*', body) or ""
        
        # Clean up cost newlines
        cost = cost.replace('\n', ' ')
        
        # Parse list items for requirements
        requirements = [line.strip().lstrip('*').strip() for line in requirements_raw.split('\n') if line.strip().startswith('*')]
        
        # Determine Category
        category = "Visit"
        if code.startswith("A") or code.startswith("F"): category = "Visa Free/VOA"
        if code.startswith("B"): category = "VOA"
        if code.startswith("D"): category = "Multiple Entry"
        if code.startswith("E"): category = "KITAS"
        
        visa_data = {
            "code": code,
            "name": name,
            "category": category,
            "description": purpose,
            "duration": "See details", # Placeholder, logic needed for extraction
            "cost_visa": cost,
            "requirements": requirements,
            "raw_type_info": type_info
        }
        
        # refine duration from type_info
        if "30 days" in type_info: visa_data["duration"] = "30 days"
        if "60 days" in type_info: visa_data["duration"] = "60 days"
        if "1 Year" in type_info: visa_data["duration"] = "1 Year"
        if "5 Years" in type_info: visa_data["duration"] = "5 Years"
        
        visa_types.append(visa_data)

    return visa_types

def generate_seed_file(visa_types):
    header = '''"""
Official Visa Types Seed 2026 - Series A-F
Based on verified text file: visa_indonesia_corrected_EN.txt
"""

import asyncio
import json
import os
import asyncpg

VISA_TYPES = [
'''
    
    body = ""
    for v in visa_types:
        # Use simple string concatenation to avoid f-string complexity issues
        body += "    {\n"
        body += f'        "code": "{v["code"]}",\n'
        body += f'        "name": "{v["name"]}",\n'
        body += f'        "category": "{v["category"]}",\n'
        body += f'        "duration": "{v["duration"]}",\n'
        body += f'        "cost_visa": "{v["cost_visa"]}",\n'
        body += f'        "requirements": {json.dumps(v["requirements"])},\n'
        body += f'        "description": {json.dumps(v["description"])},\n'
        body += f'        "benefits": [],\n'
        
        # Safe metadata construction
        meta = {"source": "official_pdf_2026", "raw_type_info": v["raw_type_info"]}
        body += f'        "metadata": {json.dumps(meta)},\n'
        
        body += "    },\n"

    footer = '''
]

async def seed_visa_types():
    """Seed all visa types into database"""
    # Connect to database - handle missing env var for local testing
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set. Printing logic only.")
        return

    conn = await asyncpg.connect(db_url)

    try:
        print("Seeding Official 2026 Visa Types...")

        for visa in VISA_TYPES:
            # Check if exists
            exists = await conn.fetchval("SELECT 1 FROM visa_types WHERE code = $1", visa["code"])
            
            if exists:
                print(f"  ~ Updating {visa['code']}")
                await conn.execute(
                    """
                    UPDATE visa_types SET
                        name = $2,
                        category = $3,
                        duration = $4,
                        cost_visa = $5,
                        requirements = $6,
                        description = $7,
                        metadata = $8,
                        last_updated = NOW()
                    WHERE code = $1
                    """,
                    visa["code"], visa["name"], visa["category"], visa["duration"],
                    visa["cost_visa"], visa["requirements"], visa["description"],
                    json.dumps(visa["metadata"])
                )
            else:
                print(f"  + Inserting {visa['code']}")
                await conn.execute(
                    """
                    INSERT INTO visa_types (
                        code, name, category, duration, cost_visa, requirements, description, metadata, created_at, last_updated
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                    """,
                    visa["code"], visa["name"], visa["category"], visa["duration"],
                    visa["cost_visa"], visa["requirements"], visa["description"],
                    json.dumps(visa["metadata"])
                )

        print("Done.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_visa_types())
'''
    return header + body + footer

if __name__ == "__main__":
    data = parse_visa_text("visa_indonesia_corrected_EN.txt")
    seed_content = generate_seed_file(data)
    with open("apps/backend-rag/backend/migrations/seed_visa_types_official_2026.py", "w") as f:
        f.write(seed_content)
    print("Migration file created: apps/backend-rag/backend/migrations/seed_visa_types_official_2026.py")
