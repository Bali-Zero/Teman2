#!/usr/bin/env python3
"""
Script per analizzare il report di coverage e generare una lista dettagliata
dei file con coverage < 80%
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def calculate_coverage_percentage(coverage_dict: Dict) -> float:
    """Calcola la percentuale di coverage da un dizionario di coverage"""
    if not coverage_dict:
        return 0.0
    
    covered = 0
    total = 0
    
    for value in coverage_dict.values():
        if isinstance(value, list):
            # Per branches: array di [covered, total] o [0, 0]
            for branch_coverage in value:
                if isinstance(branch_coverage, list) and len(branch_coverage) >= 2:
                    total += 1
                    if branch_coverage[0] > 0:  # covered > 0
                        covered += 1
                elif isinstance(branch_coverage, (int, float)):
                    total += 1
                    if branch_coverage > 0:
                        covered += 1
        elif isinstance(value, (int, float)):
            # Per statements/functions: valore numerico
            total += 1
            if value > 0:
                covered += 1
    
    return (covered / total * 100) if total > 0 else 0.0


def calculate_lines_coverage(statement_map: Dict, statements: Dict) -> Tuple[float, Dict]:
    """Calcola la coverage delle linee dagli statementMap"""
    if not statement_map:
        return 0.0, {}
    
    lines_coverage = {}  # line_num -> covered (0 or 1)
    
    for stmt_id, stmt_info in statement_map.items():
        line_num = stmt_info.get('start', {}).get('line', 0)
        if line_num > 0:
            # Se lo statement è coperto, la linea è coperta
            stmt_covered = statements.get(stmt_id, 0) > 0
            if line_num not in lines_coverage:
                lines_coverage[line_num] = 0
            if stmt_covered:
                lines_coverage[line_num] = 1
    
    covered_lines = sum(1 for v in lines_coverage.values() if v > 0)
    total_lines = len(lines_coverage)
    percentage = (covered_lines / total_lines * 100) if total_lines > 0 else 0.0
    
    return percentage, lines_coverage


def analyze_file_coverage(file_path: str, file_data: Dict) -> Dict:
    """Analizza la coverage di un singolo file"""
    statements_dict = file_data.get('s', {})
    branches_dict = file_data.get('b', {})
    functions_dict = file_data.get('f', {})
    statement_map = file_data.get('statementMap', {})
    
    statements = calculate_coverage_percentage(statements_dict)
    branches = calculate_coverage_percentage(branches_dict)
    functions = calculate_coverage_percentage(functions_dict)
    lines, lines_data = calculate_lines_coverage(statement_map, statements_dict)
    
    # Converti path assoluto in relativo
    rel_path = file_path
    if '/apps/mouth/' in file_path:
        rel_path = file_path.split('/apps/mouth/')[-1]
    
    return {
        'path': rel_path,
        'statements': statements,
        'branches': branches,
        'functions': functions,
        'lines': lines,
        'statements_data': statements_dict,
        'branches_data': branches_dict,
        'functions_data': functions_dict,
        'lines_data': lines_data,
    }


def get_uncovered_lines(lines_data: Dict) -> List[int]:
    """Estrae le linee non coperte"""
    uncovered = []
    for line_num, coverage in lines_data.items():
        if isinstance(line_num, str):
            line_num = int(line_num)
        if coverage == 0:
            uncovered.append(line_num)
    return sorted(uncovered)


def filter_low_coverage_files(coverage_data: Dict, threshold: float = 80.0) -> List[Dict]:
    """Filtra i file con almeno una metrica < threshold"""
    low_coverage_files = []
    
    for file_path, file_data in coverage_data.items():
        if file_path == 'total':
            continue
        
        # Filtra solo file sorgente in src/ (gestisce path assoluti e relativi)
        if '/src/' not in file_path and not file_path.startswith('src/'):
            continue
        
        # Escludi file di test e setup
        if '.test.' in file_path or '.spec.' in file_path:
            continue
        if 'test/setup' in file_path:
            continue
        if file_path.endswith('.d.ts'):
            continue
        
        analysis = analyze_file_coverage(file_path, file_data)
        
        # Controlla se almeno una metrica è < threshold
        if (analysis['statements'] < threshold or
            analysis['branches'] < threshold or
            analysis['functions'] < threshold or
            analysis['lines'] < threshold):
            low_coverage_files.append(analysis)
    
    # Ordina per coverage media (più bassa prima)
    low_coverage_files.sort(
        key=lambda x: (x['statements'] + x['branches'] + x['functions'] + x['lines']) / 4
    )
    
    return low_coverage_files


def generate_markdown_report(low_coverage_files: List[Dict], output_path: Path):
    """Genera il report markdown"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Report Coverage Frontend - File con Coverage < 80%\n\n")
        f.write(f"**Generato:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Threshold:** 80%\n")
        f.write(f"**File analizzati:** {len(low_coverage_files)}\n\n")
        f.write("---\n\n")
        
        # Nota sui file di tipo
        type_files = [f for f in low_coverage_files if f['path'].endswith('.ts') and 'types' in f['path']]
        if type_files:
            f.write("> **Nota:** I file di tipo TypeScript (`.d.ts` o in `types/`) tipicamente non necessitano di test unitari poiché contengono solo definizioni di tipo.\n\n")
            f.write("---\n\n")
        
        if not low_coverage_files:
            f.write("✅ **Nessun file con coverage < 80% trovato!**\n\n")
            return
        
        # Tabella riepilogativa
        f.write("## 📊 Riepilogo\n\n")
        f.write("| File | Statements | Branches | Functions | Lines | Media |\n")
        f.write("|------|------------|----------|-----------|-------|-------|\n")
        
        for file_info in low_coverage_files:
            avg = (file_info['statements'] + file_info['branches'] + 
                   file_info['functions'] + file_info['lines']) / 4
            f.write(f"| `{file_info['path']}` | "
                   f"{file_info['statements']:.1f}% | "
                   f"{file_info['branches']:.1f}% | "
                   f"{file_info['functions']:.1f}% | "
                   f"{file_info['lines']:.1f}% | "
                   f"{avg:.1f}% |\n")
        
        f.write("\n---\n\n")
        
        # Dettagli per ogni file
        f.write("## 📁 Dettagli per File\n\n")
        
        for file_info in low_coverage_files:
            f.write(f"### `{file_info['path']}`\n\n")
            
            # Metriche
            f.write("**Coverage:**\n")
            f.write(f"- Statements: {file_info['statements']:.1f}%\n")
            f.write(f"- Branches: {file_info['branches']:.1f}%\n")
            f.write(f"- Functions: {file_info['functions']:.1f}%\n")
            f.write(f"- Lines: {file_info['lines']:.1f}%\n\n")
            
            # Linee non coperte
            uncovered_lines = get_uncovered_lines(file_info['lines_data'])
            if uncovered_lines:
                # Raggruppa linee consecutive
                ranges = []
                start = uncovered_lines[0]
                end = uncovered_lines[0]
                
                for line in uncovered_lines[1:]:
                    if line == end + 1:
                        end = line
                    else:
                        if start == end:
                            ranges.append(str(start))
                        else:
                            ranges.append(f"{start}-{end}")
                        start = line
                        end = line
                
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
                
                f.write(f"**Linee non coperte:** {', '.join(ranges[:20])}")
                if len(ranges) > 20:
                    f.write(f" ... (e altre {len(ranges) - 20})")
                f.write("\n\n")
            
            # Suggerimenti
            f.write("**Suggerimenti:**\n")
            suggestions = []
            if file_info['statements'] < 80:
                suggestions.append(f"- Aggiungere test per aumentare la coverage delle statements (attualmente {file_info['statements']:.1f}%)")
            if file_info['branches'] < 80:
                suggestions.append(f"- Testare più branch/condizioni per aumentare la coverage dei branch (attualmente {file_info['branches']:.1f}%)")
            if file_info['functions'] < 80:
                suggestions.append(f"- Aggiungere test per tutte le funzioni (attualmente {file_info['functions']:.1f}%)")
            if file_info['lines'] < 80:
                suggestions.append(f"- Aggiungere test per coprire più linee di codice (attualmente {file_info['lines']:.1f}%)")
            
            if suggestions:
                f.write("\n".join(suggestions) + "\n")
            else:
                f.write("- Nessun suggerimento specifico\n")
            
            f.write("\n---\n\n")


def main():
    coverage_file = Path(__file__).parent.parent / 'coverage' / 'coverage-final.json'
    output_file = Path(__file__).parent.parent / 'COVERAGE_LOW_FILES.md'
    
    if not coverage_file.exists():
        print(f"❌ File di coverage non trovato: {coverage_file}")
        sys.exit(1)
    
    print(f"📖 Leggendo {coverage_file}...")
    with open(coverage_file, 'r', encoding='utf-8') as f:
        coverage_data = json.load(f)
    
    print("🔍 Analizzando coverage...")
    low_coverage_files = filter_low_coverage_files(coverage_data, threshold=80.0)
    
    print(f"📝 Generando report...")
    generate_markdown_report(low_coverage_files, output_file)
    
    print(f"✅ Report generato: {output_file}")
    print(f"📊 File con coverage < 80%: {len(low_coverage_files)}")
    
    if low_coverage_files:
        print("\nTop 5 file con coverage più bassa:")
        for i, file_info in enumerate(low_coverage_files[:5], 1):
            avg = (file_info['statements'] + file_info['branches'] + 
                   file_info['functions'] + file_info['lines']) / 4
            print(f"  {i}. {file_info['path']} - Media: {avg:.1f}%")


if __name__ == '__main__':
    main()

