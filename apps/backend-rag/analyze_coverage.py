#!/usr/bin/env python3
"""Analyze coverage.xml and generate detailed report"""

import xml.etree.ElementTree as ET
from collections import defaultdict

tree = ET.parse('coverage.xml')
root = tree.getroot()

files = []
for pkg in root.findall('.//package'):
    for cls in pkg.findall('class'):
        filename = cls.get('filename')
        line_rate = float(cls.get('line-rate', 0))
        branch_rate = float(cls.get('branch-rate', 0))

        # Calculate overall coverage
        coverage = line_rate * 100

        files.append({
            'file': filename,
            'coverage': coverage,
            'line_rate': line_rate,
            'branch_rate': branch_rate
        })

# Sort by coverage ascending
files.sort(key=lambda x: x['coverage'])

print('📊 COVERAGE ANALYSIS BY MODULE\n')
print('=' * 100)
print(f"{'File':<70} {'Coverage':>15}")
print('=' * 100)

# Show worst 30 files
print('\n🔴 LOWEST COVERAGE (Bottom 30):')
for f in files[:30]:
    print(f"{f['file']:<70} {f['coverage']:>14.2f}%")

print('\n\n✅ HIGHEST COVERAGE (Top 20):')
for f in files[-20:]:
    print(f"{f['file']:<70} {f['coverage']:>14.2f}%")

# Module breakdown
modules = defaultdict(list)
for f in files:
    if 'backend/' in f['file']:
        parts = f['file'].replace('backend/', '').split('/')
        module = parts[0] if len(parts) > 0 else 'root'
        modules[module].append(f['coverage'])

print('\n\n📦 AVERAGE COVERAGE BY MODULE:')
print('=' * 60)
for module in sorted(modules.keys()):
    avg = sum(modules[module]) / len(modules[module])
    count = len(modules[module])
    print(f"{module:<35} {avg:>10.2f}% ({count} files)")

# Summary statistics
total_files = len(files)
zero_cov = len([f for f in files if f['coverage'] == 0])
low_cov = len([f for f in files if 0 < f['coverage'] < 50])
medium_cov = len([f for f in files if 50 <= f['coverage'] < 80])
high_cov = len([f for f in files if f['coverage'] >= 80])
full_cov = len([f for f in files if f['coverage'] == 100])

print('\n\n📈 SUMMARY STATISTICS:')
print('=' * 60)
print(f"Total files:            {total_files}")
print(f"  🔴 0% coverage:        {zero_cov} ({zero_cov/total_files*100:.1f}%)")
print(f"  🟠 1-49% coverage:     {low_cov} ({low_cov/total_files*100:.1f}%)")
print(f"  🟡 50-79% coverage:    {medium_cov} ({medium_cov/total_files*100:.1f}%)")
print(f"  🟢 80-99% coverage:    {high_cov} ({high_cov/total_files*100:.1f}%)")
print(f"  ✅ 100% coverage:      {full_cov} ({full_cov/total_files*100:.1f}%)")

avg_coverage = sum(f['coverage'] for f in files) / len(files)
print(f"\nAverage coverage:       {avg_coverage:.2f}%")
