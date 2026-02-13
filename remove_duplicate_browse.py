#!/usr/bin/env python3
"""Remove duplicate Browse Sectors fragment from Navigator HTML (lines 3431-3518)"""

input_file = '/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/kbli-navigator/index.html'
output_file = '/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/kbli-navigator/index_cleaned.html'

with open(input_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Removing lines 3431-3518 (88 lines - duplicate Browse Sectors fragment)")

# Remove lines 3431-3518 (0-indexed: 3430-3517)
start_remove = 3430  # Line 3431 (0-indexed)
end_remove = 3518     # Line 3519 (0-indexed, exclusive)

# Write cleaned file
with open(output_file, 'w', encoding='utf-8') as f:
    f.writelines(lines[:start_remove])
    f.writelines(lines[end_remove:])

new_line_count = len(lines) - (end_remove - start_remove)
print(f"\n✅ Cleaned file written to: {output_file}")
print(f"Original: {len(lines)} lines")
print(f"Cleaned: {new_line_count} lines")
print(f"Removed: {end_remove - start_remove} lines")
print(f"\nReplace original with: mv {output_file} {input_file}")
