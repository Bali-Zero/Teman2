#!/bin/bash
#
# Show Unified Test Force Results
# Mostra risultati in modo leggibile
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT_FILE="$PROJECT_ROOT/logs/unified_coverage_report.json"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}📊 UNIFIED TEST FORCE RESULTS${NC}"
echo "=================================="
echo ""

if [ ! -f "$REPORT_FILE" ]; then
    echo -e "${YELLOW}⏳ Report non ancora disponibile${NC}"
    echo "Il sistema sta ancora lavorando..."
    echo ""
    echo "Monitora progresso:"
    echo "  tail -f logs/unified_test_force.log"
    exit 0
fi

# Parse JSON and show results
python3 << 'PYTHON_SCRIPT'
import json
import sys
from pathlib import Path

report_file = Path("logs/unified_coverage_report.json")

try:
    with open(report_file) as f:
        data = json.load(f)
    
    # Summary
    summary = data.get('summary', {})
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"Duration: {summary.get('duration', 0):.1f}s")
    print(f"Components Analyzed: {summary.get('components_analyzed', 0)}")
    print(f"Overall Coverage: {summary.get('overall_coverage', 0):.1f}%")
    print(f"Tests Generated: {summary.get('tests_generated', 0)}")
    if summary.get('regressions', 0) > 0:
        print(f"⚠️  Regressions: {summary.get('regressions', 0)}")
    if summary.get('improvements', 0) > 0:
        print(f"✅ Improvements: {summary.get('improvements', 0)}")
    print()
    
    # Coverage Report
    cov_report = data.get('coverage_report', {})
    if cov_report:
        print("🌐 COVERAGE REPORT")
        print("=" * 50)
        print(f"Overall Coverage: {cov_report.get('overall_coverage', 0):.1f}%")
        print()
        
        print("📊 Coverage per Tipo:")
        for type_name, coverage in cov_report.get('coverage_by_type', {}).items():
            print(f"  {type_name}: {coverage:.1f}%")
        print()
        
        print("📦 Coverage per Componente:")
        for name, comp in cov_report.get('components', {}).items():
            print(f"  {name}: {comp.get('coverage', 0):.1f}% ({comp.get('files', 0)} files, {comp.get('gaps', 0)} gaps)")
        print()
        
        print(f"🎯 Critical Gaps: {cov_report.get('critical_gaps', 0)}")
        print()
    
    # Test Generation
    test_gen = data.get('test_generation', {})
    if test_gen:
        print("🤖 TEST GENERATION")
        print("=" * 50)
        print(f"Tests Generated: {test_gen.get('tests_generated', 0)}")
        print(f"Tests Passed: {test_gen.get('tests_passed', 0)}")
        print(f"Tests Failed: {test_gen.get('tests_failed', 0)}")
        if test_gen.get('tests_by_component'):
            print()
            print("📦 Tests per Componente:")
            for comp, count in test_gen.get('tests_by_component', {}).items():
                print(f"  {comp}: {count} tests")
        print()
    
    # Differential Report
    diff = data.get('differential_report')
    if diff:
        print("📈 COVERAGE DIFFERENTIAL")
        print("=" * 50)
        print(f"Overall Delta: {diff.get('overall_delta', 0):+.1f}%")
        print(f"Regressions: {diff.get('regressions', 0)}")
        print(f"Improvements: {diff.get('improvements', 0)}")
        print(f"Critical Regressions: {diff.get('critical_regressions', 0)}")
        print()
    else:
        print("⚠️  No baseline - save baseline first:")
        print("   cd apps/backend-rag")
        print("   python3 -m backend.agents.agents.unified_test_force_orchestrator \\")
        print("       --project-root=/Users/antonellosiano/Desktop/nuzantara \\")
        print("       --save-baseline --generate-tests=false")
        print()
    
    print("📄 Full report: logs/unified_coverage_report.json")
    
except Exception as e:
    print(f"❌ Error reading report: {e}")
    sys.exit(1)
PYTHON_SCRIPT
