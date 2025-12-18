import os
import hashlib
import json
from pathlib import Path

# Load existing catalog
CATALOG_FILE = "master_ingestion_catalog.json"
try:
    with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
        existing_catalog = json.load(f)
        # Convert list back to dictionary for fast lookup: hash -> item
        known_hashes = {item['primary_path']: item for item in existing_catalog['items']}
        
        # Also need a hash set for quick membership check
        # Wait, the catalog structure in create_master_catalog.py was:
        # catalog[file_hash] = { ... }
        # But we saved output as { "items": [list_of_values] }
        # So we need to re-hash the items or rely on the fact that we can re-calculate hashes of new files.
        # Let's rebuild the hash set from the items list.
        
        # We need to re-calculate hash for items? No, that's slow.
        # Wait, the previous script didn't save the hash in the item value explicitly?
        # Let's check the structure again.
        pass
except FileNotFoundError:
    print("❌ Master catalog not found. Please run create_master_catalog.py first.")
    exit(1)

# Rebuild a set of known MD5s from the existing catalog
# Since the previous script calculated MD5s to deduplicate but didn't save the MD5 string in the item (my bad),
# we have a problem. The 'items' list contains deduplicated files.
# Ah, I need to know the MD5 of the files in the catalog to compare.
# Let's re-calculate MD5s for the 321 unique files in the catalog first. 
# It's safer than guessing.

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Error hashing {file_path}: {e}")
        return None

print("🔄 Re-indexing known files from catalog to get hashes...")
known_md5s = set()
for item in existing_catalog['items']:
    path = item['primary_path']
    md5 = calculate_md5(path)
    if md5:
        known_md5s.add(md5)

print(f"✅ Loaded {len(known_md5s)} unique hashes from catalog.")

# Now scan the new directories
NEW_DIRS = [
    "/Users/antonellosiano/Desktop/duplicati/_archive",
    "/Users/antonellosiano/Desktop/duplicati/general-laws"
]

print(f"🚀 Scanning external directories for duplicates...")

stats = {
    "total_scanned": 0,
    "duplicates_found": 0,
    "new_unique_files": 0,
    "errors": 0
}

new_files_list = []

for root_dir in NEW_DIRS:
    root_path = Path(root_dir)
    if not root_path.exists():
        print(f"⚠️ Warning: {root_dir} not found.")
        continue
        
    for path in root_path.rglob("*.pdf"):
        stats["total_scanned"] += 1
        md5 = calculate_md5(path)
        
        if not md5:
            stats["errors"] += 1
            continue
            
        if md5 in known_md5s:
            stats["duplicates_found"] += 1
            # Optional: print duplicate if needed
            # print(f"  ↳ Duplicate: {path.name}")
        else:
            stats["new_unique_files"] += 1
            print(f"🆕 NEW FILE FOUND: {path.name}")
            new_files_list.append(str(path))
            known_md5s.add(md5) # Add to known so we don't count it again if duplicated within the new dirs

print("\n" + "="*50)
print("📊 EXTERNAL DIRECTORY CHECK REPORT")
print("="*50)
print(f"Total PDF Scanned: {stats['total_scanned']}")
print(f"Duplicates (Already in Catalog): {stats['duplicates_found']}")
print(f"New Unique Files: {stats['new_unique_files']}")
print(f"Errors: {stats['errors']}")
print("="*50)

if new_files_list:
    print("\n📝 List of New Files:")
    for f in new_files_list[:20]:
        print(f" - {f}")
    if len(new_files_list) > 20:
        print(f" ... and {len(new_files_list)-20} more.")
