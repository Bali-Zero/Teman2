#!/usr/bin/env python3
"""
Script per pulire report coverage multipli, mantenendo solo l'ultimo.
"""

import sys
from pathlib import Path


def cleanup_coverage_reports(root: Path, dry_run: bool = False):
    """Pulisce report coverage multipli mantenendo solo l'ultimo."""

    # File da mantenere (escludi dalla pulizia)
    keep_patterns = [
        ".coverage_data/coverage*.json",  # Coverage ufficiale in cartella dedicata
        "coverage/coverage-final.json",  # Coverage frontend finale
    ]

    # Trova tutti i file coverage
    coverage_files = []
    for pattern in ["coverage*.json", "coverage.xml"]:
        coverage_files.extend(root.rglob(pattern))

    # Filtra i file da mantenere
    files_to_keep = []
    files_to_remove = []

    for coverage_file in coverage_files:
        # Controlla se è un file da mantenere (in .coverage_data o coverage finale frontend)
        should_keep = False

        # Mantieni tutti i file in .coverage_data
        if ".coverage_data" in str(coverage_file):
            should_keep = True
        # Mantieni coverage-final.json del frontend
        elif "apps/mouth/coverage/coverage-final.json" in str(coverage_file):
            should_keep = True
        # Mantieni coverage.xml solo in apps/backend-rag (non root)
        elif coverage_file.name == "coverage.xml":
            file_path_str = str(coverage_file)
            # Mantieni se è in apps/backend-rag (non nella root)
            if "apps/backend-rag" in file_path_str:
                # Escludi se è nella root del progetto (solo "coverage.xml")
                if coverage_file.parent != root:
                    should_keep = True

        if should_keep:
            files_to_keep.append(coverage_file)
        else:
            files_to_remove.append(coverage_file)

    # Per i file da rimuovere, mantieni solo l'ultimo modificato per directory
    if files_to_remove:
        # Raggruppa per directory
        by_dir = {}
        for f in files_to_remove:
            dir_key = str(f.parent)
            if dir_key not in by_dir:
                by_dir[dir_key] = []
            by_dir[dir_key].append(f)

        # Per ogni directory, mantieni solo l'ultimo file (più recente)
        final_remove = []
        for dir_path, files in by_dir.items():
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            if len(files) > 1:
                # Mantieni il primo (più recente), rimuovi gli altri
                files_to_keep.append(files[0])
                final_remove.extend(files[1:])
            else:
                # Se c'è solo un file, rimuovilo (non è in .coverage_data)
                final_remove.append(files[0])

        files_to_remove = final_remove

    if dry_run:
        print(f"[DRY RUN] File da mantenere: {len(files_to_keep)}")
        for f in files_to_keep[:5]:  # Mostra primi 5
            print(f"  ✓ {f.relative_to(root)}")
        if len(files_to_keep) > 5:
            print(f"  ... e altri {len(files_to_keep) - 5}")

        print(f"\n[DRY RUN] File da rimuovere: {len(files_to_remove)}")
        for f in files_to_remove:
            print(f"  ✗ {f.relative_to(root)}")
        return len(files_to_remove)

    # Rimuovi i file
    removed = 0
    for coverage_file in files_to_remove:
        try:
            coverage_file.unlink()
            print(f"✓ Rimosso: {coverage_file.relative_to(root)}")
            removed += 1
        except Exception as e:
            print(f"✗ Errore rimuovendo {coverage_file}: {e}")

    return removed


def main():
    root = Path(__file__).parent.parent
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Pulizia Report Coverage")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN MODE]\n")

    removed = cleanup_coverage_reports(root, dry_run=dry_run)

    if dry_run:
        print(f"\n[DRY RUN] {removed} file verrebbero rimossi.")
    else:
        print(f"\n✓ Rimossi {removed} file coverage.")


if __name__ == "__main__":
    main()
