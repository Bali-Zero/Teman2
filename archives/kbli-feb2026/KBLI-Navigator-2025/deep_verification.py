#!/usr/bin/env python3
"""
Deep verification: Compare HTML database with backup JSON (truth source)
"""

import json
import re
import ast
from collections import Counter, defaultdict

print("="*70)
print("DEEP VERIFICATION: HTML vs BACKUP JSON (Truth Source)")
print("="*70)

# Correct mapping
RISK_MAP = {
    'Rendah': 'L',
    'Menengah Rendah': 'M',
    'Menengah Tinggi': 'M',
    'Tinggi': 'H'
}

# Load backup JSON (TRUTH SOURCE)
print("\n📖 Loading TRUTH SOURCE (backup JSON)...")
backup_file = '/sessions/practical-inspiring-galileo/mnt/uploads/186fc707-a8fe-43d0-a0c9-7f6d2de7420e-1770771901719_KBLI_2025_FINAL_CLEAN.backup_final_20260204_165833.json'

with open(backup_file, 'r', encoding='utf-8') as f:
    backup = json.load(f)

print(f"✅ Loaded backup with {len(backup['data'])} codes")

# Extract truth data
truth = {}
for item in backup['data']:
    code = item.get('kode_kbli_2025')
    if not code:
        continue

    # Store all available info
    truth[code] = {
        'title': item.get('judul', ''),
        'sector': item.get('sektor_id', ''),
        'pma_status': item.get('pma_status', ''),
        'pma_max': item.get('pma_max_asing', 100),
        'per_skala': item.get('per_skala', [])
    }

    # Extract risk level using Menengah scale preference
    risk = None
    if 'per_skala' in item and item['per_skala']:
        # First priority: Menengah scale
        for scala in item['per_skala']:
            if 'Menengah' in scala.get('skala_usaha', []):
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria, 'H')
                break

        # Second priority: any available scale
        if not risk:
            for scala in item['per_skala']:
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria)
                if risk:
                    break

    truth[code]['risk'] = risk if risk else 'H'

print(f"✅ Extracted {len(truth)} codes from backup")

# Load HTML database (CURRENT)
print("\n📖 Loading CURRENT HTML database...")
html_file = '/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/app/kbli-navigator-premium.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'const K=(\[\s*\[[\s\S]*?\]\s*\]);'
match = re.search(pattern, content)

if not match:
    print("❌ Could not find database K in HTML")
    exit(1)

db_array = ast.literal_eval(match.group(1))
print(f"✅ Loaded {len(db_array)} codes from HTML")

# Parse HTML database
html_db = {}
for entry in db_array:
    if len(entry) >= 6:
        code = entry[0]
        html_db[code] = {
            'title': entry[1],
            'sector': entry[2],
            'pma': entry[3],
            'max_foreign': entry[4],
            'risk': entry[5],
            'kondisi': entry[6] if len(entry) > 6 else '',
            'keywords': entry[7] if len(entry) > 7 else ''
        }

print(f"✅ Parsed {len(html_db)} codes from HTML")

# DEEP COMPARISON
print("\n" + "="*70)
print("DEEP COMPARISON")
print("="*70)

# Check 1: Codes in backup but missing in HTML
missing_in_html = set(truth.keys()) - set(html_db.keys())
if missing_in_html:
    print(f"\n❌ {len(missing_in_html)} codes in backup but MISSING in HTML:")
    for code in sorted(list(missing_in_html)[:10]):
        print(f"   {code}: {truth[code]['title'][:50]}")
    if len(missing_in_html) > 10:
        print(f"   ... and {len(missing_in_html)-10} more")
else:
    print("\n✅ All backup codes present in HTML")

# Check 2: Codes in HTML but not in backup
extra_in_html = set(html_db.keys()) - set(truth.keys())
if extra_in_html:
    print(f"\n⚠️  {len(extra_in_html)} codes in HTML but NOT in backup:")
    for code in sorted(list(extra_in_html)[:10]):
        print(f"   {code}: {html_db[code]['title'][:50]}")
    if len(extra_in_html) > 10:
        print(f"   ... and {len(extra_in_html)-10} more")
else:
    print("\n✅ No extra codes in HTML")

# Check 3: Risk level mismatches
print("\n🔍 Checking RISK LEVELS...")
risk_mismatches = []
for code in truth:
    if code in html_db:
        expected_risk = truth[code]['risk']
        actual_risk = html_db[code]['risk']

        if expected_risk != actual_risk:
            risk_mismatches.append({
                'code': code,
                'title': truth[code]['title'][:60],
                'expected': expected_risk,
                'actual': actual_risk,
                'scala_info': truth[code]['per_skala']
            })

if risk_mismatches:
    print(f"\n❌ Found {len(risk_mismatches)} RISK LEVEL MISMATCHES:")
    print("\nFirst 20 mismatches:")
    for i, m in enumerate(risk_mismatches[:20], 1):
        print(f"\n{i}. Code {m['code']}: {m['title']}")
        print(f"   Expected: {m['expected']} | Actual in HTML: {m['actual']}")
        print(f"   Available scales in backup:")
        for scala in m['scala_info']:
            skala_usaha = ', '.join(scala.get('skala_usaha', []))
            risk_cat = scala.get('kategori_risiko', 'N/A')
            print(f"      - {skala_usaha}: {risk_cat}")

    if len(risk_mismatches) > 20:
        print(f"\n   ... and {len(risk_mismatches)-20} more mismatches")

    # Save full mismatch report
    with open('risk_mismatches_detailed.json', 'w', encoding='utf-8') as f:
        json.dump(risk_mismatches, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Full mismatch report saved to: risk_mismatches_detailed.json")
else:
    print("\n✅ ALL RISK LEVELS MATCH!")

# Check 4: PMA status mismatches
print("\n🔍 Checking PMA STATUS...")
pma_mismatches = []
for code in truth:
    if code in html_db:
        # Map PMA status
        backup_pma = truth[code]['pma_status']
        html_pma = html_db[code]['pma']

        # TERBUKA → O, TERBATAS → R, TERTUTUP → C
        expected_pma = 'O' if backup_pma == 'TERBUKA' else 'R' if backup_pma == 'TERBATAS' else 'C'

        if expected_pma != html_pma:
            pma_mismatches.append({
                'code': code,
                'title': truth[code]['title'][:60],
                'expected': expected_pma,
                'actual': html_pma,
                'backup_status': backup_pma
            })

if pma_mismatches:
    print(f"\n❌ Found {len(pma_mismatches)} PMA STATUS MISMATCHES:")
    for m in pma_mismatches[:10]:
        print(f"   {m['code']}: Expected {m['expected']} ({m['backup_status']}), Got {m['actual']}")
    if len(pma_mismatches) > 10:
        print(f"   ... and {len(pma_mismatches)-10} more")
else:
    print("✅ All PMA statuses match")

# FINAL STATISTICS
print("\n" + "="*70)
print("FINAL STATISTICS")
print("="*70)

# Risk distribution comparison
truth_risks = Counter([truth[c]['risk'] for c in truth])
html_risks = Counter([html_db[c]['risk'] for c in html_db if c in truth])

print("\nRisk Distribution Comparison:")
print(f"{'Level':<10} {'Backup':<15} {'HTML':<15} {'Status':<10}")
print("-"*50)
for level in ['L', 'M', 'H']:
    backup_count = truth_risks[level]
    html_count = html_risks[level]
    status = '✅' if backup_count == html_count else '❌'
    print(f"{level:<10} {backup_count:<15} {html_count:<15} {status:<10}")

# Test specific codes
print("\n🧪 Specific Code Tests:")
test_codes = [
    ('01111', 'Agriculture corn'),
    ('56101', 'Restaurant fixed'),
    ('62191', 'E-commerce IT'),
    ('01443', 'Goat farming'),
    ('10435', 'Processed meat'),
]

for code, desc in test_codes:
    if code in truth and code in html_db:
        expected = truth[code]['risk']
        actual = html_db[code]['risk']
        status = '✅' if expected == actual else '❌'
        print(f"  {status} {code} ({desc}): Expected {expected}, Got {actual}")

# SUMMARY
print("\n" + "="*70)
print("SUMMARY")
print("="*70)

issues = []
if missing_in_html:
    issues.append(f"{len(missing_in_html)} codes missing in HTML")
if extra_in_html:
    issues.append(f"{len(extra_in_html)} extra codes in HTML")
if risk_mismatches:
    issues.append(f"{len(risk_mismatches)} risk level mismatches")
if pma_mismatches:
    issues.append(f"{len(pma_mismatches)} PMA status mismatches")

if issues:
    print("\n❌ ISSUES FOUND:")
    for issue in issues:
        print(f"   - {issue}")
    print("\n🔧 Action needed: Review mismatches and fix")
else:
    print("\n✅ ✅ ✅ DATABASE PERFECTLY MATCHES BACKUP! ✅ ✅ ✅")
    print("\nAll codes, risk levels, and PMA statuses are correct!")

print("="*70)
