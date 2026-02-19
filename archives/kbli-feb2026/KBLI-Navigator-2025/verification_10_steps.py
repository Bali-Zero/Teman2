#!/usr/bin/env python3
"""
10-Step Deep Verification: Backup JSON vs HTML Database
"""

import json
import re
import ast
from collections import Counter, defaultdict

print("="*80)
print("🔍 10-STEP VERIFICATION: BACKUP JSON vs KBLI-NAVIGATOR HTML")
print("="*80)

# Load backup JSON (TRUTH SOURCE)
backup_file = '/sessions/practical-inspiring-galileo/mnt/uploads/186fc707-a8fe-43d0-a0c9-7f6d2de7420e-1770771901719_KBLI_2025_FINAL_CLEAN.backup_final_20260204_165833.json'

print("\n📖 Loading TRUTH SOURCE (backup JSON)...")
with open(backup_file, 'r', encoding='utf-8') as f:
    backup = json.load(f)

print(f"✅ Loaded {len(backup['data'])} codes from backup")

# Extract expected data from backup
RISK_MAP = {
    'Rendah': 'L',
    'Menengah Rendah': 'ML',
    'Menengah Tinggi': 'MH',
    'Tinggi': 'H'
}

PMA_MAP = {
    'TERBUKA': 'O',
    'TERBATAS': 'R',
    'TERTUTUP': 'C'
}

expected = {}
for item in backup['data']:
    code = item.get('kode_kbli_2025')
    if not code:
        continue

    # Extract risk level
    risk = None
    if 'per_skala' in item and item['per_skala']:
        for scala in item['per_skala']:
            if 'Menengah' in scala.get('skala_usaha', []):
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria, 'H')
                break
        if not risk:
            for scala in item['per_skala']:
                categoria = scala.get('kategori_risiko', '')
                risk = RISK_MAP.get(categoria)
                if risk:
                    break

    expected[code] = {
        'title': item.get('judul', ''),
        'sector': item.get('sektor_id', ''),
        'pma': PMA_MAP.get(item.get('pma_status', ''), 'O'),
        'max_foreign': item.get('pma_max_asing', 100),
        'risk': risk if risk else 'H'
    }

print(f"✅ Extracted {len(expected)} expected codes")

# Load HTML database (ACTUAL)
print("\n📖 Loading ACTUAL HTML database...")
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
actual = {}
for entry in db_array:
    if len(entry) >= 6:
        code = entry[0]
        actual[code] = {
            'title': entry[1],
            'sector': entry[2],
            'pma': entry[3],
            'max_foreign': entry[4],
            'risk': entry[5]
        }

print(f"✅ Parsed {len(actual)} codes from HTML")

# ============================================================================
# 10 VERIFICATION STEPS
# ============================================================================

print("\n" + "="*80)
print("10 VERIFICATION STEPS")
print("="*80)

all_passed = True

# STEP 1: Total Number of Codes
print("\n[1/10] 📊 TOTAL NUMBER OF CODES")
print("-" * 60)
expected_total = len(expected)
actual_total = len(actual)
if expected_total == actual_total:
    print(f"✅ PASS: Both have {expected_total} codes")
else:
    print(f"❌ FAIL: Expected {expected_total}, got {actual_total}")
    all_passed = False

# STEP 2: Risk Level Distribution
print("\n[2/10] 📈 RISK LEVEL DISTRIBUTION (4 levels)")
print("-" * 60)
expected_risks = Counter([expected[c]['risk'] for c in expected])
actual_risks = Counter([actual[c]['risk'] for c in actual])

print(f"{'Level':<15} {'Expected':<15} {'Actual':<15} {'Status':<10}")
print("-" * 60)
risk_match = True
for level in ['L', 'ML', 'MH', 'H']:
    exp = expected_risks[level]
    act = actual_risks[level]
    status = '✅' if exp == act else '❌'
    if exp != act:
        risk_match = False
    print(f"{level:<15} {exp:<15} {act:<15} {status:<10}")

if risk_match:
    print("\n✅ PASS: All risk distributions match")
else:
    print("\n❌ FAIL: Risk distributions don't match")
    all_passed = False

# STEP 3: PMA Status Distribution
print("\n[3/10] 🌍 PMA STATUS DISTRIBUTION")
print("-" * 60)
expected_pma = Counter([expected[c]['pma'] for c in expected])
actual_pma = Counter([actual[c]['pma'] for c in actual])

print(f"{'Status':<15} {'Expected':<15} {'Actual':<15} {'Status':<10}")
print("-" * 60)
pma_match = True
for status in ['O', 'R', 'C']:
    exp = expected_pma[status]
    act = actual_pma[status]
    check = '✅' if exp == act else '❌'
    if exp != act:
        pma_match = False
    print(f"{status:<15} {exp:<15} {act:<15} {check:<10}")

if pma_match:
    print("\n✅ PASS: All PMA distributions match")
else:
    print("\n❌ FAIL: PMA distributions don't match")
    all_passed = False

# STEP 4: Sector Distribution
print("\n[4/10] 🏢 SECTOR DISTRIBUTION")
print("-" * 60)
expected_sectors = Counter([expected[c]['sector'] for c in expected if expected[c]['sector']])
actual_sectors = Counter([actual[c]['sector'] for c in actual if actual[c]['sector']])

sector_match = True
mismatched_sectors = []
for sector in sorted([s for s in expected_sectors.keys() if s]):
    exp = expected_sectors[sector]
    act = actual_sectors.get(sector, 0)
    if exp != act:
        sector_match = False
        mismatched_sectors.append((sector, exp, act))

if sector_match:
    print(f"✅ PASS: All {len(expected_sectors)} sectors match perfectly")
else:
    print(f"❌ FAIL: {len(mismatched_sectors)} sectors have mismatches:")
    for s, e, a in mismatched_sectors[:5]:
        print(f"   Sector {s}: Expected {e}, Got {a}")
    all_passed = False

# STEP 5: Specific High-Profile Codes
print("\n[5/10] 🎯 HIGH-PROFILE CODES VERIFICATION")
print("-" * 60)
test_codes = [
    ('01111', 'Agriculture - Corn'),
    ('56101', 'Restaurant Fixed'),
    ('62191', 'E-commerce IT'),
    ('10435', 'Palm Oil Processing'),
    ('01443', 'Goat Dairy Farming'),
    ('47911', 'E-commerce Retail'),
    ('63111', 'Data Processing'),
    ('72101', 'R&D Natural Sciences'),
]

high_profile_pass = True
for code, desc in test_codes:
    if code in expected and code in actual:
        exp = expected[code]
        act = actual[code]

        match = (exp['risk'] == act['risk'] and
                exp['pma'] == act['pma'] and
                exp['sector'] == act['sector'])

        status = '✅' if match else '❌'
        if not match:
            high_profile_pass = False
            print(f"{status} {code} ({desc})")
            if exp['risk'] != act['risk']:
                print(f"   Risk: Expected {exp['risk']}, Got {act['risk']}")
            if exp['pma'] != act['pma']:
                print(f"   PMA: Expected {exp['pma']}, Got {act['pma']}")
        else:
            print(f"{status} {code} ({desc}): Risk={act['risk']}, PMA={act['pma']}")

if high_profile_pass:
    print("\n✅ PASS: All high-profile codes correct")
else:
    print("\n❌ FAIL: Some high-profile codes have errors")
    all_passed = False

# STEP 6: Missing Codes
print("\n[6/10] 🔍 MISSING CODES CHECK")
print("-" * 60)
missing = set(expected.keys()) - set(actual.keys())
if not missing:
    print("✅ PASS: No codes missing from HTML")
else:
    print(f"❌ FAIL: {len(missing)} codes missing from HTML:")
    for code in sorted(list(missing)[:10]):
        print(f"   {code}: {expected[code]['title'][:50]}")
    if len(missing) > 10:
        print(f"   ... and {len(missing)-10} more")
    all_passed = False

# STEP 7: Extra Codes
print("\n[7/10] ➕ EXTRA CODES CHECK")
print("-" * 60)
extra = set(actual.keys()) - set(expected.keys())
if not extra:
    print("✅ PASS: No extra codes in HTML")
else:
    print(f"⚠️  WARNING: {len(extra)} codes in HTML not in backup:")
    for code in sorted(list(extra)[:10]):
        print(f"   {code}: {actual[code]['title'][:50]}")
    if len(extra) > 10:
        print(f"   ... and {len(extra)-10} more")
    # Don't fail for extra codes, just warn

# STEP 8: Risk Level Mismatches Detail
print("\n[8/10] 🚨 RISK LEVEL MISMATCHES (if any)")
print("-" * 60)
risk_mismatches = []
for code in expected:
    if code in actual:
        if expected[code]['risk'] != actual[code]['risk']:
            risk_mismatches.append({
                'code': code,
                'title': expected[code]['title'][:40],
                'expected': expected[code]['risk'],
                'actual': actual[code]['risk']
            })

if not risk_mismatches:
    print("✅ PASS: All risk levels match perfectly")
else:
    print(f"❌ FAIL: {len(risk_mismatches)} risk level mismatches found:")
    for m in risk_mismatches[:10]:
        print(f"   {m['code']}: {m['title']}")
        print(f"      Expected: {m['expected']} | Actual: {m['actual']}")
    if len(risk_mismatches) > 10:
        print(f"   ... and {len(risk_mismatches)-10} more")

    # Save detailed report
    with open('risk_mismatches_report.json', 'w', encoding='utf-8') as f:
        json.dump(risk_mismatches, f, indent=2, ensure_ascii=False)
    print("\n   💾 Full report saved: risk_mismatches_report.json")
    all_passed = False

# STEP 9: PMA Status Mismatches Detail
print("\n[9/10] 🌐 PMA STATUS MISMATCHES (if any)")
print("-" * 60)
pma_mismatches = []
for code in expected:
    if code in actual:
        if expected[code]['pma'] != actual[code]['pma']:
            pma_mismatches.append({
                'code': code,
                'title': expected[code]['title'][:40],
                'expected': expected[code]['pma'],
                'actual': actual[code]['pma']
            })

if not pma_mismatches:
    print("✅ PASS: All PMA statuses match perfectly")
else:
    print(f"❌ FAIL: {len(pma_mismatches)} PMA status mismatches found:")
    for m in pma_mismatches[:10]:
        print(f"   {m['code']}: {m['title']}")
        print(f"      Expected: {m['expected']} | Actual: {m['actual']}")
    if len(pma_mismatches) > 10:
        print(f"   ... and {len(pma_mismatches)-10} more")
    all_passed = False

# STEP 10: Max Foreign Investment Verification
print("\n[10/10] 💼 MAX FOREIGN INVESTMENT CHECK")
print("-" * 60)
max_foreign_mismatches = []
for code in expected:
    if code in actual:
        exp_max = expected[code]['max_foreign']
        act_max = actual[code]['max_foreign']

        # Only check for open/restricted (not closed)
        if expected[code]['pma'] in ['O', 'R']:
            if exp_max != act_max:
                max_foreign_mismatches.append({
                    'code': code,
                    'title': expected[code]['title'][:40],
                    'expected': exp_max,
                    'actual': act_max
                })

if not max_foreign_mismatches:
    print("✅ PASS: All max foreign investment values correct")
else:
    print(f"❌ FAIL: {len(max_foreign_mismatches)} max foreign mismatches:")
    for m in max_foreign_mismatches[:10]:
        print(f"   {m['code']}: {m['title']}")
        print(f"      Expected: {m['expected']}% | Actual: {m['actual']}%")
    if len(max_foreign_mismatches) > 10:
        print(f"   ... and {len(max_foreign_mismatches)-10} more")
    all_passed = False

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "="*80)
print("FINAL SUMMARY")
print("="*80)

if all_passed:
    print("\n🎉 ✅ ✅ ✅ ALL 10 VERIFICATION STEPS PASSED! ✅ ✅ ✅ 🎉")
    print("\nThe HTML database perfectly matches the backup JSON!")
    print("\n📊 Summary:")
    print(f"   • Total codes: {actual_total}")
    print(f"   • Risk levels: L={actual_risks['L']}, ML={actual_risks['ML']}, MH={actual_risks['MH']}, H={actual_risks['H']}")
    print(f"   • PMA status: Open={actual_pma['O']}, Restricted={actual_pma['R']}, Closed={actual_pma['C']}")
    print(f"   • All data matches backup perfectly!")
else:
    print("\n❌ VERIFICATION FAILED")
    print("\nSome checks did not pass. Review the details above.")
    print("\nIssues found:")
    if expected_total != actual_total:
        print("   - Total code count mismatch")
    if not risk_match:
        print("   - Risk distribution mismatch")
    if not pma_match:
        print("   - PMA distribution mismatch")
    if risk_mismatches:
        print(f"   - {len(risk_mismatches)} individual risk mismatches")
    if pma_mismatches:
        print(f"   - {len(pma_mismatches)} individual PMA mismatches")
    if max_foreign_mismatches:
        print(f"   - {len(max_foreign_mismatches)} max foreign investment mismatches")

print("\n" + "="*80)
