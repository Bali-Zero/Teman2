#!/usr/bin/env python3
"""
NUZANTARA - Monitor Spazio Disco
Monitora lo spazio disco utilizzato dal progetto e identifica cartelle grandi.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def get_dir_size(path: Path) -> int:
    """Calcola la dimensione totale di una directory."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def format_size(size_bytes: int) -> str:
    """Formatta la dimensione in formato leggibile."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def analyze_project_structure(root: Path, exclude_dirs: set = None) -> Dict[str, int]:
    """Analizza la struttura del progetto e calcola le dimensioni delle cartelle principali."""
    if exclude_dirs is None:
        exclude_dirs = {
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            ".pytest_cache", "htmlcov", ".coverage", "dist", "build"
        }
    
    dir_sizes = {}
    
    # Analizza solo le cartelle principali
    main_dirs = ["apps", "docs", "scripts", "tests", "config", "assets"]
    
    for main_dir in main_dirs:
        dir_path = root / main_dir
        if dir_path.exists() and dir_path.is_dir():
            size = get_dir_size(dir_path)
            if size > 0:
                dir_sizes[main_dir] = size
    
    # Analizza anche le cartelle nella root (escludendo quelle già analizzate)
    for item in root.iterdir():
        if item.is_dir() and item.name not in main_dirs:
            # Escludi cartelle da ignorare
            if item.name not in exclude_dirs and not item.name.startswith("."):
                size = get_dir_size(item)
                if size > 0:
                    dir_sizes[item.name] = size
    
    return dir_sizes


def find_large_files(root: Path, min_size_mb: int = 10) -> List[Tuple[Path, int]]:
    """Trova file grandi nel progetto."""
    large_files = []
    min_size_bytes = min_size_mb * 1024 * 1024
    
    exclude_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    
    for path in root.rglob("*"):
        if path.is_file():
            # Escludi se è dentro una directory da ignorare
            parts = path.parts
            if any(exclude in parts for exclude in exclude_dirs):
                continue
            
            try:
                size = path.stat().st_size
                if size >= min_size_bytes:
                    large_files.append((path, size))
            except (OSError, PermissionError):
                pass
    
    # Ordina per dimensione (decrescente)
    large_files.sort(key=lambda x: x[1], reverse=True)
    return large_files


def main():
    """Esegue l'analisi dello spazio disco."""
    root = Path(__file__).parent.parent
    
    print("=" * 70)
    print("NUZANTARA - Monitor Spazio Disco")
    print("=" * 70)
    print(f"\nDirectory analizzata: {root.absolute()}\n")
    
    # Analizza struttura progetto
    print("1. Analisi dimensioni cartelle principali:")
    print("-" * 70)
    dir_sizes = analyze_project_structure(root)
    
    if not dir_sizes:
        print("Nessuna cartella trovata.")
    else:
        # Ordina per dimensione
        sorted_dirs = sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True)
        total_size = sum(dir_sizes.values())
        
        for dir_name, size in sorted_dirs:
            percentage = (size / total_size * 100) if total_size > 0 else 0
            print(f"  {dir_name:20s} {format_size(size):>12s} ({percentage:5.1f}%)")
        
        print(f"\n  {'TOTALE':20s} {format_size(total_size):>12s}")
    
    # Trova file grandi
    print("\n2. File grandi (>10MB):")
    print("-" * 70)
    large_files = find_large_files(root, min_size_mb=10)
    
    if not large_files:
        print("Nessun file grande trovato.")
    else:
        for file_path, size in large_files[:20]:  # Mostra primi 20
            rel_path = file_path.relative_to(root)
            print(f"  {format_size(size):>12s}  {rel_path}")
        
        if len(large_files) > 20:
            print(f"\n  ... e altri {len(large_files) - 20} file")
    
    # Statistiche cache Python
    print("\n3. Cache Python (__pycache__ e .pyc):")
    print("-" * 70)
    pycache_dirs = []
    pyc_files = []
    
    exclude_dirs = {".venv", "venv", ".env", "env"}
    for path in root.rglob("__pycache__"):
        if path.is_dir():
            parts = path.parts
            if not any(exclude in parts for exclude in exclude_dirs):
                pycache_dirs.append(path)
    
    for path in root.rglob("*.pyc"):
        if path.is_file():
            parts = path.parts
            if not any(exclude in parts for exclude in exclude_dirs):
                pyc_files.append(path)
    
    if pycache_dirs or pyc_files:
        cache_size = 0
        for pycache_dir in pycache_dirs:
            cache_size += get_dir_size(pycache_dir)
        for pyc_file in pyc_files:
            try:
                cache_size += pyc_file.stat().st_size
            except (OSError, PermissionError):
                pass
        
        print(f"  Cartelle __pycache__: {len(pycache_dirs)}")
        print(f"  File .pyc: {len(pyc_files)}")
        print(f"  Spazio totale: {format_size(cache_size)}")
    else:
        print("  Nessuna cache Python trovata.")
    
    print("\n" + "=" * 70)
    print("Analisi completata!")
    print("=" * 70)
    
    # Suggerimenti
    if pycache_dirs or pyc_files:
        print("\n💡 Suggerimento: Esegui 'python3 scripts/cleanup_temp_files.py' per pulire la cache Python")


if __name__ == "__main__":
    main()

