#!/usr/bin/env python3
"""
Auto Catalog - Sistema Automatico di Catalogazione KB
======================================================
Scansiona la Knowledge Base e genera:
1. CATALOG.json - Catalogo strutturato con metadata
2. STATS.md - Statistiche e report
3. CHANGELOG.md - Log delle modifiche

Eseguire periodicamente o dopo ogni ingestione.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configurazione
KB_ROOT = Path(__file__).parent.parent / "data"
CATALOG_FILE = KB_ROOT / "CATALOG.json"
STATS_FILE = KB_ROOT / "STATS.md"

# Mapping categorie
CATEGORY_MAP = {
    "immigration": {
        "name": "Immigrazione",
        "description": "Visa, KITAS, KITAP, Surat Edaran",
        "qdrant_collection": "visa_oracle",
    },
    "training-conversations": {
        "name": "Training Conversations",
        "description": "Conversazioni Q&A per training RAG",
        "qdrant_collection": "training_conversations",
    },
    "general-laws": {
        "name": "Leggi Generali",
        "description": "UU, PP, PMK, Permen",
        "qdrant_collection": "legal_unified",
    },
    "court-decisions": {
        "name": "Sentenze",
        "description": "Putusan MA, PN",
        "qdrant_collection": "litigation_oracle",
    },
    "business": {
        "name": "Business",
        "description": "KBLI, Investimenti, PT",
        "qdrant_collection": "kbli_unified",
    },
}

# Regex per estrazione metadata
DOCUMENT_PATTERNS = {
    "surat_edaran": r"SE_IMI-(\d+).*_(\d{4})_",
    "visa_type": r"visa_([a-z0-9]+)-",
    "uu": r"UU.*?(\d+).*?(\d{4})",
    "pp": r"PP.*?(\d+).*?(\d{4})",
    "pmk": r"PMK.*?(\d+).*?(\d{4})",
}


def get_file_hash(filepath: Path) -> str:
    """Calcola hash MD5 del file per detect modifiche"""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def extract_metadata_from_txt(filepath: Path) -> dict:
    """Estrae metadata da file .txt con header standard"""
    metadata = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("==="):
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    metadata[key] = value.strip()
    except Exception:
        pass
    return metadata


def classify_document(filepath: Path) -> dict:
    """Classifica documento basandosi su nome e contenuto"""
    filename = filepath.name.lower()

    doc_info = {
        "filename": filepath.name,
        "path": str(filepath.relative_to(KB_ROOT)),
        "size_bytes": filepath.stat().st_size,
        "modified": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
        "hash": get_file_hash(filepath),
        "extension": filepath.suffix,
        "type": "unknown",
        "metadata": {},
    }

    # Classifica per tipo
    if "se_imi" in filename or "surat_edaran" in filename:
        doc_info["type"] = "surat_edaran"
    elif filename.startswith("visa_"):
        doc_info["type"] = "visa_type"
        # Estrai codice visa
        code = filename.replace("visa_", "").split("-")[0].upper()
        doc_info["metadata"]["visa_code"] = code
    elif "uu_" in filename or "undang" in filename:
        doc_info["type"] = "undang_undang"
    elif "pp_" in filename or "peraturan_pemerintah" in filename:
        doc_info["type"] = "peraturan_pemerintah"
    elif "pmk" in filename:
        doc_info["type"] = "peraturan_menteri_keuangan"
    elif "permen" in filename:
        doc_info["type"] = "peraturan_menteri"
    elif "putusan" in filename:
        doc_info["type"] = "putusan"
    elif filepath.suffix == ".md":
        doc_info["type"] = "training_conversation"

    # Estrai metadata da .txt
    if filepath.suffix == ".txt":
        txt_metadata = extract_metadata_from_txt(filepath)
        doc_info["metadata"].update(txt_metadata)

    return doc_info


def scan_directory(directory: Path) -> list:
    """Scansiona directory e cataloga tutti i file"""
    documents = []

    for filepath in directory.rglob("*"):
        if filepath.is_file() and not filepath.name.startswith("."):
            if filepath.suffix in [".pdf", ".txt", ".md", ".json"]:
                doc_info = classify_document(filepath)
                documents.append(doc_info)

    return documents


def generate_catalog() -> dict:
    """Genera catalogo completo della KB"""
    catalog = {
        "generated_at": datetime.now().isoformat(),
        "kb_root": str(KB_ROOT),
        "categories": {},
        "statistics": {
            "total_files": 0,
            "total_size_mb": 0,
            "by_type": {},
            "by_extension": {},
        },
    }

    # Scansiona ogni categoria
    for cat_dir in KB_ROOT.iterdir():
        if cat_dir.is_dir() and not cat_dir.name.startswith("_"):
            cat_name = cat_dir.name
            cat_info = CATEGORY_MAP.get(
                cat_name,
                {"name": cat_name, "description": "", "qdrant_collection": None},
            )

            documents = scan_directory(cat_dir)

            catalog["categories"][cat_name] = {
                **cat_info,
                "file_count": len(documents),
                "documents": documents,
            }

            # Aggiorna statistiche
            for doc in documents:
                catalog["statistics"]["total_files"] += 1
                catalog["statistics"]["total_size_mb"] += doc["size_bytes"] / (
                    1024 * 1024
                )

                doc_type = doc["type"]
                catalog["statistics"]["by_type"][doc_type] = (
                    catalog["statistics"]["by_type"].get(doc_type, 0) + 1
                )

                ext = doc["extension"]
                catalog["statistics"]["by_extension"][ext] = (
                    catalog["statistics"]["by_extension"].get(ext, 0) + 1
                )

    catalog["statistics"]["total_size_mb"] = round(
        catalog["statistics"]["total_size_mb"], 2
    )

    return catalog


def generate_stats_report(catalog: dict) -> str:
    """Genera report statistiche in Markdown"""
    stats = catalog["statistics"]

    report = f"""# Knowledge Base Statistics

> Auto-generated: {catalog["generated_at"]}

## Overview

| Metric | Value |
|--------|-------|
| Total Files | {stats["total_files"]} |
| Total Size | {stats["total_size_mb"]:.2f} MB |

## Files by Category

| Category | Files | Description |
|----------|-------|-------------|
"""

    for cat_name, cat_info in catalog["categories"].items():
        report += f"| {cat_name} | {cat_info['file_count']} | {cat_info.get('description', '')} |\n"

    report += "\n## Files by Type\n\n| Type | Count |\n|------|-------|\n"
    for doc_type, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        report += f"| {doc_type} | {count} |\n"

    report += (
        "\n## Files by Extension\n\n| Extension | Count |\n|-----------|-------|\n"
    )
    for ext, count in sorted(stats["by_extension"].items(), key=lambda x: -x[1]):
        report += f"| {ext} | {count} |\n"

    # Visa coverage
    visa_codes = set()
    for cat_info in catalog["categories"].values():
        for doc in cat_info.get("documents", []):
            if doc["type"] == "visa_type":
                code = doc["metadata"].get("visa_code", "")
                if code:
                    visa_codes.add(code)

    report += (
        f"\n## Visa Coverage\n\nTotal visa types documented: **{len(visa_codes)}**\n\n"
    )
    report += "Codes: " + ", ".join(sorted(visa_codes)) + "\n"

    return report


def detect_changes(old_catalog: Optional[dict], new_catalog: dict) -> list:
    """Rileva modifiche tra due versioni del catalogo"""
    changes = []

    if not old_catalog:
        changes.append({"type": "initial", "message": "Initial catalog created"})
        return changes

    # Costruisci indice file vecchio
    old_files = {}
    for cat_info in old_catalog.get("categories", {}).values():
        for doc in cat_info.get("documents", []):
            old_files[doc["path"]] = doc

    # Costruisci indice file nuovo
    new_files = {}
    for cat_info in new_catalog.get("categories", {}).values():
        for doc in cat_info.get("documents", []):
            new_files[doc["path"]] = doc

    # Trova aggiunte
    for path, doc in new_files.items():
        if path not in old_files:
            changes.append(
                {"type": "added", "path": path, "message": f"Added: {doc['filename']}"}
            )

    # Trova rimozioni
    for path, doc in old_files.items():
        if path not in new_files:
            changes.append(
                {
                    "type": "removed",
                    "path": path,
                    "message": f"Removed: {doc['filename']}",
                }
            )

    # Trova modifiche
    for path, new_doc in new_files.items():
        if path in old_files:
            old_doc = old_files[path]
            if old_doc.get("hash") != new_doc.get("hash"):
                changes.append(
                    {
                        "type": "modified",
                        "path": path,
                        "message": f"Modified: {new_doc['filename']}",
                    }
                )

    return changes


def main():
    """Main function"""
    print("=" * 60)
    print("AUTO CATALOG - Knowledge Base Scanner")
    print("=" * 60)

    # Carica catalogo esistente (se presente)
    old_catalog = None
    if CATALOG_FILE.exists():
        try:
            with open(CATALOG_FILE, "r") as f:
                old_catalog = json.load(f)
            print(f"Loaded existing catalog from {CATALOG_FILE}")
        except Exception as e:
            print(f"Could not load existing catalog: {e}")

    # Genera nuovo catalogo
    print(f"\nScanning KB at: {KB_ROOT}")
    catalog = generate_catalog()

    # Rileva modifiche
    changes = detect_changes(old_catalog, catalog)

    # Salva catalogo
    with open(CATALOG_FILE, "w") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"\nCatalog saved to: {CATALOG_FILE}")

    # Genera e salva stats
    stats_report = generate_stats_report(catalog)
    with open(STATS_FILE, "w") as f:
        f.write(stats_report)
    print(f"Stats saved to: {STATS_FILE}")

    # Report
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files: {catalog['statistics']['total_files']}")
    print(f"Total size: {catalog['statistics']['total_size_mb']:.2f} MB")

    if changes:
        print(f"\nChanges detected: {len(changes)}")
        for change in changes[:10]:  # Mostra max 10
            print(f"  - [{change['type']}] {change['message']}")
        if len(changes) > 10:
            print(f"  ... and {len(changes) - 10} more")
    else:
        print("\nNo changes detected")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

    return catalog


if __name__ == "__main__":
    main()
