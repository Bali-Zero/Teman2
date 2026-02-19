#!/usr/bin/env python3
"""
Verify corrected risk levels match backup database
"""

import json
import re
import ast
from collections import Counter

print("="*60)
print("VERIFYING CORRECTED RISK LEVELS")
print("="*60)

# Correct mapping
RISK_MAP = {
    'Rendah': 'L',
    'Menengah Rendah': 'M',
    'Menengah Tinggi': 'M',  # Both Menengah → M
    'Tinggi': 'H'
}

# Extract expected from backup
print("\n📖 Loading backup database...")
backup_file = '/sessions/practical-inspiring-galileo/mnt/uploads/186fc707-a8fe-43d0-a0c9-7f6d2de7420e-1770771901719_KBLI_2025_FINAL_CLEAN.backup_final_20260204_165833.json'

with open(backup_file, 'r', encoding='utf-8') as f:
    backup = json.load(f)

expected_risks = {}
for item in backup['data']:
    code = item.get('kode_kbli_2025')
    if not code:
        continue

    risk = None
    if 'per_skala' in item and item['per_skala']:
        for scala in item['per_skala']:
            if 'Menengah' in scala.get('skala_usaha', []):
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria, 'H')
                break
        if not risk:
            for scala in item['per_skala']:
                categoria = scala.get('categoria_risiko', '')
                risk = RISK_MAP.get(categoria)
                if risk:
                    break

    expected_risks[code] = risk if risk else 'H'

print(f"✅ Extracted {len(expected_risks)} expected risk levels")

# Load current database
print("\n📖 Loading current database...")
html_file = '/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/app/kbli-navigator-premium.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'const K=(\[\s*\[[\s\S]*?\]\s*\]);'
match = re.search(pattern, content)
db_array = ast.literal_eval(match.group(1))

print(f"✅ Loaded {len(db_array)} codes from database")

# Build actual risks dict
actual_risks = {}
for entry in db_array:
    if len(entry) >= 6:
        actual_risks[entry[0]] = entry[5]

# Compare
print("\n🔍 Comparing expected vs actual...")
mismatches = []
for code in expected_risks:
    expected = expected_risks[code]
    actual = actual_risks.get(code, '?')
    if expected != actual:
        mismatches.append(f"  {code}: Expected {expected}, Got {actual}")

if mismatches:
    print(f"\n❌ Found {len(mismatches)} mismatches:")
    for m in mismatches[:20]:
        print(m)
    if len(mismatches) > 20:
        print(f"  ... and {len(mismatches)-20} more")
else:
    print("✅ ALL CODES MATCH!")

# Distribution
print("\n📊 Distribution:")
expected_dist = Counter(expected_risks.values())
actual_dist = Counter(actual_risks.values())

for level in ['L', 'M', 'H']:
    exp = expected_dist[level]
    act = actual_dist[level]
    status = '✅' if exp == act else '❌'
    print(f"  {status} {level}: Expected {exp}, Actual {act}")

# Test specific codes
print("\n🧪 Specific code tests:")
test_cases = [
    ('01111', 'M', 'Agriculture corn'),
    ('56101', 'M', 'Restaurant (was wrongly H)'),
    ('62191', 'M', 'E-commerce IT'),
    ('56102', 'M', 'Mobile food'),
]

for code, expected_risk, description in test_cases:
    actual = actual_risks.get(code, '?')
    status = '✅' if actual == expected_risk else '❌'
    print(f"  {status} {code} ({description}): Expected {expected_risk}, Got {actual}")

print("\n" + "="*60)
if not mismatches and all(expected_dist[l] == actual_dist[l] for l in ['L','M','H']):
    print("✅ ✅ ✅ ALL VERIFICATIONS PASSED! ✅ ✅ ✅")
    print("\n📊 FINAL DISTRIBUTION:")
    print(f"   Low (L):    {actual_dist['L']} codes ({actual_dist['L']/len(actual_risks)*100:.1f}%)")
    print(f"   Medium (M): {actual_dist['M']} codes ({actual_dist['M']/len(actual_risks)*100:.1f}%)")
    print(f"   High (H):   {actual_dist['H']} codes ({actual_dist['H']/len(actual_risks)*100:.1f}%)")
    print("\n⚠️  Remember to HARD REFRESH your browser!")
else:
    print("❌ VERIFICATION FAILED - Check mismatches above")
print("="*60)
