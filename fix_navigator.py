#!/usr/bin/env python3
"""Remove duplicate Browse Sectors section from Navigator HTML"""

input_file = '/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/kbli-navigator/index.html'
output_file = '/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/kbli-navigator/index_fixed.html'

with open(input_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find markers
browse_markers = []
about_marker = None

for i, line in enumerate(lines):
    if '<!-- SECTION: BROWSE SECTORS -->' in line:
        browse_markers.append(i)
    elif '<!-- SECTION: ABOUT -->' in line:
        about_marker = i

print(f"Total lines: {len(lines)}")
print(f"Browse Sectors at lines: {[m+1 for m in browse_markers]}")  # +1 for human-readable
print(f"About at line: {about_marker+1 if about_marker else None}")

if len(browse_markers) == 2 and about_marker:
    # Remove duplicate (second browse section through line before About)
    start_remove = browse_markers[1]
    end_remove = about_marker  # Don't include About marker itself

    print(f"\nRemoving lines {start_remove+1} to {end_remove} (duplicate Browse Sectors)")
    print(f"Lines to remove: {end_remove - start_remove}")

    # Write fixed file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write everything except the duplicate section
        f.writelines(lines[:start_remove])
        f.writelines(lines[end_remove:])

    print(f"\n✅ Fixed file written to: {output_file}")
    print(f"Original: {len(lines)} lines")
    print(f"Fixed: {len(lines) - (end_remove - start_remove)} lines")
    print(f"\nReplace original with: mv {output_file} {input_file}")
else:
    print(f"\n❌ Unexpected structure. Browse markers: {len(browse_markers)}, About: {about_marker is not None}")
