#!/usr/bin/env python3
"""
NUZANTARA - Script di Pulizia File Temporanei
Pulisce cache Python, log vuoti, e altri file temporanei.
"""

import shutil
import sys
from pathlib import Path
from typing import List, Tuple


def find_pycache_dirs(root: Path) -> List[Path]:
    """Trova tutte le cartelle __pycache__, escludendo virtualenv."""
    pycache_dirs = []
    exclude_dirs = {".venv", "venv", ".env", "env", "__pycache__"}
    for path in root.rglob("__pycache__"):
        if path.is_dir():
            # Escludi se è dentro una virtualenv
            parts = path.parts
            if not any(exclude in parts for exclude in exclude_dirs):
                pycache_dirs.append(path)
    return pycache_dirs


def find_pyc_files(root: Path) -> List[Path]:
    """Trova tutti i file .pyc, escludendo virtualenv."""
    pyc_files = []
    exclude_dirs = {".venv", "venv", ".env", "env"}
    for path in root.rglob("*.pyc"):
        if path.is_file():
            # Escludi se è dentro una virtualenv
            parts = path.parts
            if not any(exclude in parts for exclude in exclude_dirs):
                pyc_files.append(path)
    return pyc_files


def cleanup_pycache(root: Path, dry_run: bool = False) -> Tuple[int, int]:
    """Pulisce tutte le cartelle __pycache__ e file .pyc."""
    pycache_dirs = find_pycache_dirs(root)
    pyc_files = find_pyc_files(root)

    total_size = 0

    if dry_run:
        print(f"[DRY RUN] Trovate {len(pycache_dirs)} cartelle __pycache__")
        print(f"[DRY RUN] Trovati {len(pyc_files)} file .pyc")
        return len(pycache_dirs), len(pyc_files)

    # Rimuovi cartelle __pycache__
    for pycache_dir in pycache_dirs:
        try:
            # Calcola dimensione prima di eliminare
            dir_size = sum(
                f.stat().st_size for f in pycache_dir.rglob("*") if f.is_file()
            )
            total_size += dir_size
            shutil.rmtree(pycache_dir)
            print(f"✓ Rimossa: {pycache_dir.relative_to(root)}")
        except Exception as e:
            print(f"✗ Errore rimuovendo {pycache_dir}: {e}")

    # Rimuovi file .pyc
    for pyc_file in pyc_files:
        try:
            file_size = pyc_file.stat().st_size
            total_size += file_size
            pyc_file.unlink()
            print(f"✓ Rimosso: {pyc_file.relative_to(root)}")
        except Exception as e:
            print(f"✗ Errore rimuovendo {pyc_file}: {e}")

    size_mb = total_size / (1024 * 1024)
    print(
        f"\n✓ Pulizia completata: {len(pycache_dirs)} cartelle, {len(pyc_files)} file"
    )
    print(f"  Spazio liberato: {size_mb:.2f} MB")

    return len(pycache_dirs), len(pyc_files)


def cleanup_empty_logs(log_dir: Path, dry_run: bool = False) -> int:
    """Elimina file log vuoti."""
    log_files = list(log_dir.glob("*.log"))
    empty_logs = [f for f in log_files if f.stat().st_size == 0]

    if dry_run:
        print(f"[DRY RUN] Trovati {len(empty_logs)} log file vuoti")
        for log_file in empty_logs:
            print(f"  - {log_file.name}")
        return len(empty_logs)

    removed = 0
    for log_file in empty_logs:
        try:
            log_file.unlink()
            print(f"✓ Rimosso log vuoto: {log_file.name}")
            removed += 1
        except Exception as e:
            print(f"✗ Errore rimuovendo {log_file}: {e}")

    return removed


def cleanup_coverage_reports(
    root: Path, keep_latest: bool = True, dry_run: bool = False
) -> int:
    """Pulisce report coverage multipli, mantenendo solo l'ultimo se richiesto."""
    coverage_files = []

    # Trova tutti i file coverage
    for pattern in ["coverage*.json", "coverage.xml"]:
        coverage_files.extend(root.rglob(pattern))

    # Rimuovi duplicati e ordina per data di modifica
    coverage_files = list(set(coverage_files))
    coverage_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if dry_run:
        print(f"[DRY RUN] Trovati {len(coverage_files)} file coverage")
        if keep_latest and len(coverage_files) > 1:
            print(f"  Mantenere: {coverage_files[0].name}")
            print(f"  Eliminare: {len(coverage_files) - 1} file")
        return len(coverage_files) - 1 if keep_latest and len(coverage_files) > 1 else 0

    removed = 0
    if keep_latest and len(coverage_files) > 1:
        # Mantieni solo l'ultimo
        for coverage_file in coverage_files[1:]:
            try:
                coverage_file.unlink()
                print(f"✓ Rimosso coverage: {coverage_file.relative_to(root)}")
                removed += 1
            except Exception as e:
                print(f"✗ Errore rimuovendo {coverage_file}: {e}")

    return removed


def main():
    """Esegue la pulizia completa."""
    root = Path(__file__).parent.parent
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("NUZANTARA - Pulizia File Temporanei")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN MODE - Nessun file verrà eliminato]\n")

    # 1. Pulizia __pycache__ e .pyc
    print("\n1. Pulizia cache Python (__pycache__ e .pyc)...")
    print("-" * 60)
    dirs, files = cleanup_pycache(root, dry_run=dry_run)

    # 2. Pulizia log vuoti nel backend
    print("\n2. Pulizia log file vuoti...")
    print("-" * 60)
    backend_log_dir = root / "apps" / "backend-rag" / "backend"
    if backend_log_dir.exists():
        removed_logs = cleanup_empty_logs(backend_log_dir, dry_run=dry_run)
    else:
        print("✗ Directory backend non trovata")
        removed_logs = 0

    # 3. Pulizia coverage reports
    print("\n3. Pulizia report coverage multipli...")
    print("-" * 60)
    removed_coverage = cleanup_coverage_reports(root, keep_latest=True, dry_run=dry_run)

    # Riepilogo
    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    print(f"Cartelle __pycache__: {dirs}")
    print(f"File .pyc: {files}")
    print(f"Log vuoti rimossi: {removed_logs}")
    print(f"Coverage reports rimossi: {removed_coverage}")

    if dry_run:
        print("\n[DRY RUN] Nessun file è stato eliminato.")
        print("Esegui senza --dry-run per applicare le modifiche.")
    else:
        print("\n✓ Pulizia completata!")


if __name__ == "__main__":
    main()
