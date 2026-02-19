#!/usr/bin/env python3
"""
Fix risk levels in KBLI Navigator database - FINAL VERSION
Corrects the mapping: BOTH 'Menengah Rendah' AND 'Menengah Tinggi' → M
"""

import json
import re
import ast

# CORRECT MAPPING
RISK_MAP = {
    'Rendah': 'L',                # Low → L
    'Menengah Rendah': 'M',       # Medium-Low → M
    'Menengah Tinggi': 'M',       # Medium-High → M (NOT H!)
    'Tinggi': 'H'                 # High → H
}

print("="*60)
print("KBLI Risk Levels Fix - FINAL VERSION")
print("="*60)

# Step 1: Extract correct risk levels from backup
print("\n📖 Step 1: Extracting risk levels from backup...")

backup_file = '/sessions/practical-inspiring-galileo/mnt/uploads/186fc707-a8fe-43d0-a0c9-7f6d2de7420e-1770771901719_KBLI_2025_FINAL_CLEAN.backup_final_20260204_165833.json'

with open(backup_file, 'r', encoding='utf-8') as f:
    backup = json.load(f)

risk_levels = {}
for item in backup['data']:
    code = item.get('kode_kbli_2025')
    if not code:
        continue

    risk = None
    if 'per_skala' in item and item['per_skala']:
        # Prefer "Menengah" (medium enterprise) scale
        for scala in item['per_skala']:
            if 'Menengah' in scala.get('skala_usaha', []):
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria, 'H')
                break

        # Fallback to any available scale
        if not risk:
            for scala in item['per_skala']:
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria)
                if risk:
                    break

    risk_levels[code] = risk if risk else 'H'

print(f"✅ Extracted risk levels for {len(risk_levels)} codes")

# Count distribution
from collections import Counter
dist = Counter(risk_levels.values())
print(f"\n📊 Expected distribution:")
print(f"   Low (L):    {dist['L']} ({dist['L']/len(risk_levels)*100:.1f}%)")
print(f"   Medium (M): {dist['M']} ({dist['M']/len(risk_levels)*100:.1f}%)")
print(f"   High (H):   {dist['H']} ({dist['H']/len(risk_levels)*100:.1f}%)")

# Step 2: Update database
print("\n🔧 Step 2: Updating database...")

html_file = '/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/app/kbli-navigator-premium.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find database K array
pattern = r'const K=(\[\s*\[[\s\S]*?\]\s*\]);'
match = re.search(pattern, content)

if not match:
    print("❌ Could not find database K array")
    exit(1)

db_json = match.group(1)

# Parse as Python list
try:
    db_array = ast.literal_eval(db_json)
except Exception as e:
    print(f"❌ Error parsing database: {e}")
    exit(1)

print(f"✅ Parsed {len(db_array)} entries from database")

# Update risk levels (index 5)
updated_count = 0
changes = []

for entry in db_array:
    if len(entry) >= 6:
        code = entry[0]
        if code in risk_levels:
            old_risk = entry[5]
            new_risk = risk_levels[code]

            if old_risk != new_risk:
                entry[5] = new_risk
                updated_count += 1

                # Track some example changes
                if len(changes) < 10:
                    changes.append(f"  {code}: {old_risk} → {new_risk}")

print(f"\n✅ Updated {updated_count} codes")
print("\nExample changes:")
for change in changes[:10]:
    print(change)

# Verify specific codes
print("\n🧪 Verification of specific codes:")
test_codes = ['01111', '56101', '62191', '56102']
for code in test_codes:
    for entry in db_array:
        if entry[0] == code:
            expected = risk_levels.get(code, '?')
            actual = entry[5]
            status = '✅' if expected == actual else '❌'
            print(f"  {status} {code}: Expected {expected}, Got {actual}")
            break

# Reconstruct JavaScript
db_json_updated = json.dumps(db_array, ensure_ascii=False, separators=(',', ':'))
new_db_declaration = f'const K={db_json_updated};'

# Replace in content
content_updated = re.sub(
    r'const K=\[\s*\[[\s\S]*?\]\s*\];',
    new_db_declaration,
    content
)

# Save
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(content_updated)

print(f"\n✅ Updated {html_file}")

# Step 3: Update deployment file
print("\n📦 Step 3: Updating deployment file...")

deploy_file = '/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deploy/ready-to-deploy/index.html'

with open(deploy_file, 'w', encoding='utf-8') as f:
    f.write(content_updated)

print(f"✅ Updated {deploy_file}")

print("\n" + "="*60)
print("✅ DONE! Risk levels corrected with proper mapping:")
print("   Rendah → L")
print("   Menengah Rendah → M")
print("   Menengah Tinggi → M  ← FIXED!")
print("   Tinggi → H")
print("="*60)
print("\n⚠️  IMPORTANT: Hard refresh browser (Cmd+Shift+R / Ctrl+Shift+R)")
