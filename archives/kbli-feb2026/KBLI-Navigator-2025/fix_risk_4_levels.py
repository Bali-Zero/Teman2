#!/usr/bin/env python3
"""
Fix risk levels with CORRECT 4-level system:
L = Rendah (Low)
ML = Menengah Rendah (Medium Low)
MH = Menengah Tinggi (Medium High)
H = Tinggi (High)
"""

import json
import re
import ast
from collections import Counter

# CORRECT 4-LEVEL MAPPING
RISK_MAP = {
    'Rendah': 'L',              # Low
    'Menengah Rendah': 'ML',    # Medium Low
    'Menengah Tinggi': 'MH',    # Medium High
    'Tinggi': 'H'               # High
}

print("="*70)
print("KBLI Risk Levels Fix - 4 LEVELS (L, ML, MH, H)")
print("="*70)

# Load backup
print("\n📖 Loading backup JSON...")
backup_file = '/sessions/practical-inspiring-galileo/mnt/uploads/186fc707-a8fe-43d0-a0c9-7f6d2de7420e-1770771901719_KBLI_2025_FINAL_CLEAN.backup_final_20260204_165833.json'

with open(backup_file, 'r', encoding='utf-8') as f:
    backup = json.load(f)

print(f"✅ Loaded {len(backup['data'])} codes")

# Extract risk levels
risk_levels = {}
for item in backup['data']:
    code = item.get('kode_kbli_2025')
    if not code:
        continue

    risk = None
    if 'per_skala' in item and item['per_skala']:
        # Prefer Menengah scale
        for scala in item['per_skala']:
            if 'Menengah' in scala.get('skala_usaha', []):
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria)
                if risk:
                    break

        # Fallback to any scale
        if not risk:
            for scala in item['per_skala']:
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria)
                if risk:
                    break

    risk_levels[code] = risk if risk else 'H'

print(f"✅ Extracted risk levels for {len(risk_levels)} codes")

# Distribution
dist = Counter(risk_levels.values())
print(f"\n📊 Expected distribution (4 levels):")
print(f"   L  (Low):          {dist['L']:<4} ({dist['L']/len(risk_levels)*100:.1f}%)")
print(f"   ML (Medium Low):   {dist['ML']:<4} ({dist['ML']/len(risk_levels)*100:.1f}%)")
print(f"   MH (Medium High):  {dist['MH']:<4} ({dist['MH']/len(risk_levels)*100:.1f}%)")
print(f"   H  (High):         {dist['H']:<4} ({dist['H']/len(risk_levels)*100:.1f}%)")

# Load HTML
print("\n🔧 Updating HTML database...")
html_file = '/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/app/kbli-navigator-premium.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find database K
pattern = r'const K=(\[\s*\[[\s\S]*?\]\s*\]);'
match = re.search(pattern, content)

if not match:
    print("❌ Could not find database K")
    exit(1)

db_array = ast.literal_eval(match.group(1))
print(f"✅ Parsed {len(db_array)} entries")

# Update risk levels
updated = 0
examples = []

for entry in db_array:
    if len(entry) >= 6:
        code = entry[0]
        if code in risk_levels:
            old = entry[5]
            new = risk_levels[code]
            if old != new:
                entry[5] = new
                updated += 1
                if len(examples) < 15:
                    examples.append(f"  {code}: {old} → {new}")

print(f"\n✅ Updated {updated} codes")
if examples:
    print("\nExample changes:")
    for ex in examples:
        print(ex)

# Test specific codes
print("\n🧪 Verification:")
test_codes = ['01111', '56101', '62191']
for code in test_codes:
    for entry in db_array:
        if entry[0] == code:
            expected = risk_levels.get(code, '?')
            actual = entry[5]
            status = '✅' if expected == actual else '❌'
            print(f"  {status} {code}: {actual} (expected {expected})")
            break

# Reconstruct JavaScript
db_json = json.dumps(db_array, ensure_ascii=False, separators=(',', ':'))
new_declaration = f'const K={db_json};'

content_updated = re.sub(
    r'const K=\[\s*\[[\s\S]*?\]\s*\];',
    new_declaration,
    content
)

# Save
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(content_updated)

print(f"\n✅ Updated {html_file}")

# Update deployment
deploy_file = '/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deploy/ready-to-deploy/index.html'
with open(deploy_file, 'w', encoding='utf-8') as f:
    f.write(content_updated)

print(f"✅ Updated {deploy_file}")

print("\n" + "="*70)
print("✅ DONE! 4-level risk system:")
print("   L  = Rendah (Low)")
print("   ML = Menengah Rendah (Medium Low)")
print("   MH = Menengah Tinggi (Medium High)")
print("   H  = Tinggi (High)")
print("="*70)
print("\n⚠️  NEXT: Update UI to show 4 badges and 4 filters!")
