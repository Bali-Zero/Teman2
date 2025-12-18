import os
import hashlib
import json
from pathlib import Path

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def classify_file(path):
    # Use the immediate parent directory name as the category
    # e.g., apps/kb/data/01_immigrazione/file.pdf -> 01_immigrazione
    parent_name = path.parent.name
    
    # If the parent is 'data' or 'raw_laws_local', it means it's at the root of the source
    if parent_name in ['data', 'raw_laws_local']:
        return "general"
    
    return parent_name

def create_catalog():
    roots = ["apps/kb/data", "nuzantara_laws"]
    catalog = {} # hash -> metadata
    
    print("🚀 Scanning directories for PDFs...")
    
    file_count = 0
    for root_dir in roots:
        root_path = Path(root_dir)
        if not root_path.exists():
            print(f"⚠️ Warning: {root_dir} not found.")
            continue
            
        for path in root_path.rglob("*.pdf"):
            file_count += 1
            try:
                file_hash = calculate_md5(path)
                category = classify_file(path)
                
                if file_hash in catalog:
                    catalog[file_hash]["duplicates"].append(str(path))
                else:
                    catalog[file_hash] = {
                        "primary_path": str(path),
                        "filename": path.name,
                        "category": category,
                        "size_kb": round(os.path.getsize(path) / 1024, 2),
                        "duplicates": []
                    }
            except Exception as e:
                print(f"❌ Error processing {path}: {e}")

    # Convert to list for easier viewing/processing
    final_list = list(catalog.values())
    
    # Stats
    stats = {
        "total_files_found": file_count,
        "unique_files": len(final_list),
        "duplicates_ignored": file_count - len(final_list),
        "by_category": {
            "legal": len([f for f in final_list if f["category"] == "legal"]),
            "pricing": len([f for f in final_list if f["category"] == "pricing"]),
            "knowledge": len([f for f in final_list if f["category"] == "knowledge"])
        }
    }
    
    output = {
        "stats": stats,
        "items": final_list
    }
    
    with open("master_ingestion_catalog.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        
    print("\n✅ Catalog created: master_ingestion_catalog.json")
    print(f"📊 Summary:")
    print(f"   - Total PDFs found: {stats['total_files_found']}")
    print(f"   - Unique PDFs: {stats['unique_files']}")
    print(f"   - Legal: {stats['by_category']['legal']}")
    print(f"   - Pricing: {stats['by_category']['pricing']}")
    print(f"   - Knowledge: {stats['by_category']['knowledge']}")

if __name__ == "__main__":
    create_catalog()
