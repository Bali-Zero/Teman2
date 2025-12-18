#!/bin/bash
# Script per calcolare coverage per tutti e 3 i tipi di test
# Usage: ./run_coverage_all_types.sh

set -e

BACKEND_DIR="apps/backend-rag"
COVERAGE_DIR="$BACKEND_DIR/.coverage_data"
mkdir -p "$COVERAGE_DIR"

echo "🚀 Starting Coverage Calculation for All Test Types"
echo "=================================================="

cd "$BACKEND_DIR"

# Function to run coverage for a test type
run_coverage() {
    local test_type=$1
    local test_dir="tests/$test_type"
    
    if [ ! -d "$test_dir" ]; then
        echo "⚠️  Test directory not found: $test_dir"
        return 1
    fi
    
    echo ""
    echo "🧪 Running $test_type tests with coverage..."
    echo "--------------------------------------------"
    
    export COVERAGE_FILE="$COVERAGE_DIR/.coverage.$test_type"
    
    # Run coverage
    coverage run --source=backend --rcfile=.coveragerc -m pytest "$test_dir" -v --tb=short --continue-on-collection-errors || true
    
    # Generate JSON report
    coverage json -o "$COVERAGE_DIR/coverage_${test_type}.json" || echo "⚠️  Failed to generate JSON for $test_type"
    
    # Generate HTML report
    coverage html -d "$COVERAGE_DIR/htmlcov_${test_type}" || echo "⚠️  Failed to generate HTML for $test_type"
    
    # Show summary
    if [ -f "$COVERAGE_DIR/coverage_${test_type}.json" ]; then
        echo ""
        echo "✅ $test_type coverage completed"
        python3 -c "
import json
with open('$COVERAGE_DIR/coverage_${test_type}.json') as f:
    data = json.load(f)
    totals = data.get('totals', {})
    print(f\"  Coverage: {totals.get('percent_covered', 0):.2f}%\")
    print(f\"  Statements: {totals.get('num_statements', 0):,}\")
    print(f\"  Covered: {totals.get('covered_lines', 0):,}\")
    print(f\"  Missing: {totals.get('missing_lines', 0):,}\")
" || echo "  Could not parse coverage data"
    fi
}

# Run coverage for each type
run_coverage "unit"
run_coverage "integration"  
run_coverage "api"

# Combine coverage
echo ""
echo "🔄 Combining coverage from all test types..."
echo "--------------------------------------------"

# Combine all .coverage files
export COVERAGE_FILE="$COVERAGE_DIR/.coverage.combined"
coverage combine "$COVERAGE_DIR"/.coverage.* 2>/dev/null || echo "⚠️  Some coverage files may be missing"

# Generate combined report
if [ -f "$COVERAGE_DIR/.coverage.combined" ]; then
    coverage json -o "$COVERAGE_DIR/coverage_combined.json"
    coverage html -d "$COVERAGE_DIR/htmlcov_combined"
    
    echo ""
    echo "✅ Combined coverage report generated"
    python3 -c "
import json
with open('$COVERAGE_DIR/coverage_combined.json') as f:
    data = json.load(f)
    totals = data.get('totals', {})
    print(f\"  Overall Coverage: {totals.get('percent_covered', 0):.2f}%\")
    print(f\"  Total Statements: {totals.get('num_statements', 0):,}\")
    print(f\"  Covered Lines: {totals.get('covered_lines', 0):,}\")
    print(f\"  Missing Lines: {totals.get('missing_lines', 0):,}\")
"
fi

echo ""
echo "📊 Coverage reports saved to:"
echo "  - Unit: $COVERAGE_DIR/htmlcov_unit/index.html"
echo "  - Integration: $COVERAGE_DIR/htmlcov_integration/index.html"
echo "  - API: $COVERAGE_DIR/htmlcov_api/index.html"
echo "  - Combined: $COVERAGE_DIR/htmlcov_combined/index.html"
echo ""
echo "✅ Coverage calculation complete!"

