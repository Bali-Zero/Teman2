#!/usr/bin/env python3
"""
Script per sostituire print() con logger nei file di codice.
Esclude script utility e file di test che possono avere print() per debug.
"""

import ast
import logging
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Pattern per identificare print() reali (non nei commenti/docstring)
PRINT_PATTERN = re.compile(r'^\s*print\s*\(', re.MULTILINE)

# Directory da processare
CODE_DIRS = [
    "backend/app",
    "backend/services",
    "backend/middleware",
    "backend/core",
    "backend/utils",
    "backend/cli",
]

# Directory da escludere (script utility, test, etc.)
EXCLUDE_DIRS = [
    "scripts",
    "tests",
    "migrations",
    "verify_",
    "check_",
    "test_",
    "evaluate_",
]

# File da escludere
EXCLUDE_FILES = [
    "__init__.py",
    "conftest.py",
]


def has_print_statements(file_path: Path) -> bool:
    """Verifica se un file contiene print() statements."""
    try:
        content = file_path.read_text(encoding="utf-8")
        # Cerca print() non nei commenti/docstring
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("print(") and not stripped.startswith("#"):
                return True
        return False
    except Exception as e:
        print(f"⚠️  Errore leggendo {file_path}: {e}")
        return False


def get_logger_import_line(file_path: Path) -> Tuple[str, bool]:
    """
    Determina se il file ha già logger importato e restituisce la linea corretta.
    Returns: (import_line, already_imported)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        
        # Verifica se logging è già importato
        has_logging_import = "import logging" in content or "from logging import" in content
        has_logger = "logger = logging.getLogger" in content
        
        if has_logger:
            return "", True
        
        # Determina dove inserire l'import (dopo gli altri import standard)
        lines = content.split("\n")
        import_end_idx = 0
        
        for i, line in enumerate(lines):
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                import_end_idx = i + 1
            elif line.strip() and not line.strip().startswith("#") and import_end_idx > 0:
                break
        
        if has_logging_import:
            logger_line = "logger = logging.getLogger(__name__)"
        else:
            logger_line = "import logging\n\nlogger = logging.getLogger(__name__)"
        
        return logger_line, False
    except Exception as e:
        print(f"⚠️  Errore analizzando imports in {file_path}: {e}")
        return "import logging\n\nlogger = logging.getLogger(__name__)", False


def replace_prints_in_file(file_path: Path) -> Tuple[int, bool]:
    """
    Sostituisce print() con logger.info() in un file.
    Returns: (num_replacements, file_modified)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        
        # Pattern per catturare print() statements
        # Cattura: print("text") o print(variable) o print("text", variable)
        print_pattern = re.compile(
            r'(\s*)print\s*\((.*?)\)',
            re.MULTILINE | re.DOTALL
        )
        
        replacements = 0
        
        def replace_print(match):
            nonlocal replacements
            indent = match.group(1)
            args = match.group(2).strip()
            
            # Determina il livello di log appropriato
            # Se contiene "error", "fail", "exception" -> logger.error
            # Se contiene "warn", "warning" -> logger.warning
            # Altrimenti logger.info
            args_lower = args.lower()
            if any(keyword in args_lower for keyword in ["error", "fail", "exception", "critical"]):
                log_level = "error"
            elif any(keyword in args_lower for keyword in ["warn", "warning"]):
                log_level = "warning"
            elif any(keyword in args_lower for keyword in ["debug", "trace"]):
                log_level = "debug"
            else:
                log_level = "info"
            
            replacements += 1
            return f'{indent}logger.{log_level}({args})'
        
        new_content = print_pattern.sub(replace_print, content)
        
        # Aggiungi logger import se necessario
        if replacements > 0 and "logger = logging.getLogger" not in new_content:
            logger_line, already_imported = get_logger_import_line(file_path)
            if logger_line:
                # Trova dove inserire l'import
                lines = new_content.split("\n")
                insert_idx = 0
                
                # Trova la fine degli import standard
                for i, line in enumerate(lines):
                    if line.strip().startswith("import ") or line.strip().startswith("from "):
                        insert_idx = i + 1
                    elif line.strip() and not line.strip().startswith("#") and insert_idx > 0:
                        break
                
                if already_imported:
                    lines.insert(insert_idx, logger_line)
                else:
                    lines.insert(insert_idx, logger_line.split("\n")[0])
                    if "\n" in logger_line:
                        lines.insert(insert_idx + 1, logger_line.split("\n")[1])
                
                new_content = "\n".join(lines)
        
        # Scrivi solo se ci sono modifiche
        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            return replacements, True
        
        return 0, False
        
    except Exception as e:
        print(f"❌ Errore processando {file_path}: {e}")
        return 0, False


def should_process_file(file_path: Path) -> bool:
    """Verifica se un file dovrebbe essere processato."""
    # Escludi file non Python
    if file_path.suffix != ".py":
        return False
    
    # Escludi file specifici
    if file_path.name in EXCLUDE_FILES:
        return False
    
    # Escludi directory specifiche
    path_str = str(file_path)
    for exclude_dir in EXCLUDE_DIRS:
        if f"/{exclude_dir}/" in path_str or path_str.endswith(f"/{exclude_dir}"):
            return False
    
    return True


def main():
    """Main function."""
    base_path = Path(__file__).parent.parent
    
    files_with_prints: List[Path] = []
    total_replacements = 0
    files_modified = 0
    
    print("🔍 Cercando file con print() statements...")
    
    # Cerca file con print()
    for code_dir in CODE_DIRS:
        dir_path = base_path / code_dir
        if not dir_path.exists():
            continue
        
        for py_file in dir_path.rglob("*.py"):
            if should_process_file(py_file) and has_print_statements(py_file):
                files_with_prints.append(py_file)
    
    print(f"📋 Trovati {len(files_with_prints)} file con print() statements")
    
    if not files_with_prints:
        print("✅ Nessun file da processare!")
        return 0
    
    # Chiedi conferma
    print("\nFile da processare:")
    for f in files_with_prints[:10]:
        print(f"  - {f.relative_to(base_path)}")
    if len(files_with_prints) > 10:
        print(f"  ... e altri {len(files_with_prints) - 10} file")
    
    # Supporta flag --yes per esecuzione non interattiva
    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    
    if not auto_yes:
        response = input("\n⚠️  Procedere con la sostituzione? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Operazione annullata.")
            return 1
    
    # Processa file
    print("\n🔄 Processando file...")
    for file_path in files_with_prints:
        rel_path = file_path.relative_to(base_path)
        replacements, modified = replace_prints_in_file(file_path)
        
        if modified:
            files_modified += 1
            total_replacements += replacements
            print(f"  ✅ {rel_path}: {replacements} sostituzioni")
        else:
            print(f"  ⚠️  {rel_path}: nessuna modifica (print() solo in commenti?)")
    
    print(f"\n✅ Completato!")
    print(f"   File modificati: {files_modified}")
    print(f"   Totale sostituzioni: {total_replacements}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

