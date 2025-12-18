#!/usr/bin/env python3
"""
Generate and analyze integration test coverage.
Runs integration tests with coverage and lists files with coverage < 80%
"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

def run_integration_tests_with_coverage() -> Path:
    """Run integration tests with coverage and return path to coverage.xml"""
    print("Running integration tests with coverage...")
    print("This may take several minutes...\n")
    
    coverage_file = Path(__file__).parent.parent / 'coverage-integration.xml'
    
    # Run pytest with integration marker and coverage
    cmd = [
        'pytest',
        '-m', 'integration',
        '--cov=backend',
        '--cov-report=xml:coverage-integration.xml',
        '--cov-report=term-missing',
        '-v'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )
        
        if result.returncode != 0:
            print("Warning: Some integration tests failed, but coverage data may still be available")
            print(f"Return code: {result.returncode}")
        
        if coverage_file.exists():
            print(f"\n✓ Coverage report generated: {coverage_file}")
            return coverage_file
        else:
            print(f"\n✗ Coverage file not found: {coverage_file}")
            print("Attempting to use existing coverage.xml...")
            existing = Path(__file__).parent.parent / 'coverage.xml'
            if existing.exists():
                return existing
            raise FileNotFoundError("No coverage file found")
            
    except subprocess.TimeoutExpired:
        print("\n⚠ Test execution timed out after 30 minutes")
        if coverage_file.exists():
            print(f"Using partial coverage data from: {coverage_file}")
            return coverage_file
        raise
    except Exception as e:
        print(f"\n✗ Error running tests: {e}")
        # Try to use existing coverage file if available
        if coverage_file.exists():
            print(f"Using existing coverage file: {coverage_file}")
            return coverage_file
        raise

def analyze_coverage(coverage_file: str, threshold: float = 0.80) -> List[Tuple[str, float, int, int]]:
    """
    Analyze coverage.xml and return files with coverage below threshold.
    
    Returns: List of tuples (filename, line_rate, lines_covered, lines_valid)
    """
    tree = ET.parse(coverage_file)
    root = tree.getroot()
    
    low_coverage_files = []
    
    # Iterate through all packages
    for package in root.findall('.//package'):
        # Iterate through all classes (files) in each package
        for class_elem in package.findall('.//class'):
            filename = class_elem.get('filename', '')
            line_rate = float(class_elem.get('line-rate', '0'))
            
            # Count lines
            lines = class_elem.findall('.//line')
            lines_covered = sum(1 for line in lines if int(line.get('hits', 0)) > 0)
            lines_valid = len(lines)
            
            # Only include Python files (skip __init__.py with 100% coverage)
            if filename.endswith('.py') and line_rate < threshold:
                # Convert relative path to absolute if needed
                if not filename.startswith('/'):
                    # Assume it's relative to backend directory
                    full_path = f"backend/{filename}"
                else:
                    full_path = filename
                
                low_coverage_files.append((
                    full_path,
                    line_rate,
                    lines_covered,
                    lines_valid
                ))
    
    # Sort by coverage (lowest first)
    low_coverage_files.sort(key=lambda x: x[1])
    
    return low_coverage_files

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze integration test coverage')
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip running tests, use existing coverage file'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.80,
        help='Coverage threshold (default: 0.80)'
    )
    parser.add_argument(
        '--coverage-file',
        type=str,
        help='Path to existing coverage file to analyze'
    )
    
    args = parser.parse_args()
    
    # Determine coverage file
    if args.coverage_file:
        coverage_file = Path(args.coverage_file)
        if not coverage_file.exists():
            print(f"Error: Coverage file not found: {coverage_file}")
            return 1
    elif args.skip_tests:
        coverage_file = Path(__file__).parent.parent / 'coverage-integration.xml'
        if not coverage_file.exists():
            print(f"Error: Coverage file not found: {coverage_file}")
            print("Run without --skip-tests to generate coverage first")
            return 1
    else:
        try:
            coverage_file = run_integration_tests_with_coverage()
        except Exception as e:
            print(f"Error: {e}")
            return 1
    
    threshold = args.threshold
    files = analyze_coverage(str(coverage_file), threshold)
    
    print(f"\n{'=' * 80}")
    print(f"INTEGRATION TEST COVERAGE - FILES WITH COVERAGE < {threshold*100:.0f}%")
    print(f"{'=' * 80}")
    print(f"\nTotal files with low coverage: {len(files)}\n")
    
    # Group by directory
    by_dir = {}
    for filename, rate, covered, valid in files:
        dir_path = '/'.join(filename.split('/')[:-1])
        if dir_path not in by_dir:
            by_dir[dir_path] = []
        by_dir[dir_path].append((filename, rate, covered, valid))
    
    # Print grouped by directory
    for dir_path in sorted(by_dir.keys()):
        print(f"\n{'─' * 80}")
        print(f"📁 {dir_path}/")
        print(f"{'─' * 80}")
        
        for filename, rate, covered, valid in sorted(by_dir[dir_path], key=lambda x: x[1]):
            coverage_pct = rate * 100
            print(f"  {filename:70s} {coverage_pct:6.2f}% ({covered:4d}/{valid:4d} lines)")
    
    # Summary statistics
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    
    total_files = len(files)
    zero_coverage = len([f for f in files if f[1] == 0.0])
    very_low = len([f for f in files if 0 < f[1] < 0.20])
    low = len([f for f in files if 0.20 <= f[1] < 0.50])
    medium = len([f for f in files if 0.50 <= f[1] < threshold])
    
    print(f"Total files with coverage < {threshold*100:.0f}%: {total_files}")
    print(f"  - 0% coverage:        {zero_coverage:4d} files")
    print(f"  - 1-19% coverage:     {very_low:4d} files")
    print(f"  - 20-49% coverage:    {low:4d} files")
    print(f"  - 50-{int(threshold*100)-1}% coverage:    {medium:4d} files")
    
    # Calculate overall coverage
    if files:
        total_lines_covered = sum(f[2] for f in files)
        total_lines_valid = sum(f[3] for f in files)
        if total_lines_valid > 0:
            overall_coverage = (total_lines_covered / total_lines_valid) * 100
            print(f"\nOverall coverage for low-coverage files: {overall_coverage:.2f}%")
    
    return 0

if __name__ == '__main__':
    exit(main())

