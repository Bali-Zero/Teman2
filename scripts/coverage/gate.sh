#!/bin/bash

# Enhanced Coverage Gate Script for Nuzantara
# Ensures minimum test coverage before allowing deployment

set -e

# Configuration
COVERAGE_THRESHOLD=${COVERAGE_THRESHOLD:-80}
REPORT_DIR="coverage_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "🚦 Running Enhanced Coverage Gate Analysis"
echo "📊 Threshold: ${COVERAGE_THRESHOLD}%"
echo "📁 Report Directory: ${REPORT_DIR}"
echo ""

# Create report directory
mkdir -p ${REPORT_DIR}

# Function to check frontend coverage
check_frontend_coverage() {
    echo "🔍 Checking Frontend coverage..."
    
    if [ ! -f "apps/mouth/coverage/lcov.info" ]; then
        echo "❌ Frontend coverage file not found: apps/mouth/coverage/lcov.info"
        return 1
    fi
    
    # Extract Line Coverage from lcov.info
    TOTAL_LINES=$(grep "LF:" apps/mouth/coverage/lcov.info | awk -F: '{sum+=$2} END {print sum}')
    HIT_LINES=$(grep "LH:" apps/mouth/coverage/lcov.info | awk -F: '{sum+=$2} END {print sum}')
    
    if [ -z "$TOTAL_LINES" ] || [ "$TOTAL_LINES" -eq 0 ]; then
        echo "⚠️  Frontend: Invalid coverage data (0 lines)."
        return 1
    fi

    COVERAGE_PCT=$(( 100 * HIT_LINES / TOTAL_LINES ))
    echo "📈 Frontend Coverage: ${COVERAGE_PCT}%"
    
    if [ "$COVERAGE_PCT" -lt $COVERAGE_THRESHOLD ]; then
        echo "❌ Frontend coverage FAILED (${COVERAGE_PCT}% < ${COVERAGE_THRESHOLD}%)"
        return 1
    else
        echo "✅ Frontend coverage PASSED (${COVERAGE_PCT}% >= ${COVERAGE_THRESHOLD}%)"
        return 0
    fi
}

# Function to check backend coverage
check_backend_coverage() {
    echo "🔍 Checking Backend coverage..."
    
    if [ ! -f "apps/backend-rag/coverage.json" ]; then
        echo "❌ Backend coverage file not found: apps/backend-rag/coverage.json"
        return 1
    fi
    
    # Extract coverage from JSON
    COVERAGE_PCT=$(python3 -c "
import json
try:
    with open('apps/backend-rag/coverage.json', 'r') as f:
        data = json.load(f)
        coverage = data.get('totals', {}).get('percent_covered', 0)
        print(f'{coverage:.1f}')
except Exception as e:
    print('0.0')
")
    
    echo "📈 Backend Coverage: ${COVERAGE_PCT}%"
    
    # Check against threshold (using bc for floating point)
    if command -v bc &> /dev/null; then
        if (( $(echo "$COVERAGE_PCT >= $COVERAGE_THRESHOLD" | bc -l) )); then
            echo "✅ Backend coverage PASSED (${COVERAGE_PCT}% >= ${COVERAGE_THRESHOLD}%)"
            return 0
        else
            echo "❌ Backend coverage FAILED (${COVERAGE_PCT}% < ${COVERAGE_THRESHOLD}%)"
            return 1
        fi
    else
        # Fallback to integer comparison
        COVERAGE_INT=${COVERAGE_PCT%.*}  # Remove decimal part
        if [ "$COVERAGE_INT" -ge $COVERAGE_THRESHOLD ]; then
            echo "✅ Backend coverage PASSED (${COVERAGE_PCT}% >= ${COVERAGE_THRESHOLD}%)"
            return 0
        else
            echo "❌ Backend coverage FAILED (${COVERAGE_PCT}% < ${COVERAGE_THRESHOLD}%)"
            return 1
        fi
    fi
}

# Function to generate coverage report
generate_report() {
    local report_file="${REPORT_DIR}/coverage_report_${TIMESTAMP}.md"
    
    # Get coverage values
    FRONTEND_COV="N/A"
    BACKEND_COV="N/A"
    
    if [ -f "apps/mouth/coverage/lcov.info" ]; then
        TOTAL_LINES=$(grep "LF:" apps/mouth/coverage/lcov.info | awk -F: '{sum+=$2} END {print sum}')
        HIT_LINES=$(grep "LH:" apps/mouth/coverage/lcov.info | awk -F: '{sum+=$2} END {print sum}')
        if [ "$TOTAL_LINES" -gt 0 ]; then
            FRONTEND_COV=$(( 100 * HIT_LINES / TOTAL_LINES ))
        fi
    fi
    
    if [ -f "apps/backend-rag/coverage.json" ]; then
        BACKEND_COV=$(python3 -c "
import json
try:
    with open('apps/backend-rag/coverage.json', 'r') as f:
        data = json.load(f)
        print(f\"{data.get('totals', {}).get('percent_covered', 0):.1f}\")
except:
    print('N/A')
" 2>/dev/null || echo "N/A")
    fi
    
    cat > "$report_file" << EOF
# 📊 Coverage Report - ${TIMESTAMP}

## 🎯 Threshold: ${COVERAGE_THRESHOLD}%

## 📈 Results

### Frontend (apps/mouth)
- Coverage: ${FRONTEND_COV}%
- Status: $([ "$FRONTEND_COV" != "N/A" ] && [ "$FRONTEND_COV" -ge $COVERAGE_THRESHOLD ] && echo "✅ PASSED" || echo "❌ FAILED")

### Backend (apps/backend-rag)
- Coverage: ${BACKEND_COV}%
- Status: $([ "$BACKEND_COV" != "N/A" ] && echo "$BACKEND_COV >= $COVERAGE_THRESHOLD" | bc -l 2>/dev/null | grep -q "1" && echo "✅ PASSED" || echo "❌ FAILED")

## 🚦 Overall Status
EOF

    # Determine overall status
    frontend_passed=false
    backend_passed=false
    
    if [ "$FRONTEND_COV" != "N/A" ] && [ "$FRONTEND_COV" -ge $COVERAGE_THRESHOLD ]; then
        frontend_passed=true
    fi
    
    if [ "$BACKEND_COV" != "N/A" ]; then
        if command -v bc &> /dev/null; then
            if (( $(echo "$BACKEND_COV >= $COVERAGE_THRESHOLD" | bc -l) )); then
                backend_passed=true
            fi
        else
            BACKEND_INT=${BACKEND_COV%.*}
            if [ "$BACKEND_INT" -ge $COVERAGE_THRESHOLD ]; then
                backend_passed=true
            fi
        fi
    fi
    
    if [ "$frontend_passed" = true ] && [ "$backend_passed" = true ]; then
        echo "✅ **ALL COVERAGE GATES PASSED**" >> "$report_file"
        echo "Ready for deployment! 🚀" >> "$report_file"
        overall_status=0
    else
        echo "❌ **COVERAGE GATES FAILED**" >> "$report_file"
        echo "Please improve test coverage before deployment." >> "$report_file"
        overall_status=1
    fi
    
    echo "📄 Report generated: $report_file"
    return $overall_status
}

# Main execution
main() {
    echo "🔄 Starting enhanced coverage analysis..."
    
    # Check prerequisites
    if ! command -v python3 &> /dev/null; then
        echo "❌ 'python3' command not found. Please install Python 3."
        exit 1
    fi
    
    # Run coverage checks
    frontend_status=0
    backend_status=0
    
    # Check frontend if coverage file exists
    if [ -f "apps/mouth/coverage/lcov.info" ]; then
        check_frontend_coverage || frontend_status=1
    else
        echo "⚠️ Frontend coverage file not found. Skipping..."
        frontend_status=1  # Fail if missing
    fi
    
    # Check backend if coverage file exists
    if [ -f "apps/backend-rag/coverage.json" ]; then
        check_backend_coverage || backend_status=1
    else
        echo "⚠️ Backend coverage file not found. Skipping..."
        backend_status=1  # Fail if missing
    fi
    
    # Generate overall report
    generate_report
    report_status=$?
    
    echo ""
    echo "🎯 Final Results:"
    echo "   Frontend: $([ $frontend_status -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
    echo "   Backend:  $([ $backend_status -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
    echo "   Overall:  $([ $report_status -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
    
    # Exit with overall status
    if [ $frontend_status -eq 0 ] && [ $backend_status -eq 0 ]; then
        echo ""
        echo "🎉 All coverage gates passed! Ready for deployment."
        exit 0
    else
        echo ""
        echo "🚫 Coverage gates failed. Please improve test coverage."
        exit 1
    fi
}

# Allow script to be called with specific functions
case "${1:-main}" in
    "frontend")
        check_frontend_coverage
        ;;
    "backend")
        check_backend_coverage
        ;;
    "report")
        generate_report
        ;;
    "main")
        main
        ;;
    *)
        echo "Usage: $0 [frontend|backend|report|main]"
        echo "Environment variables:"
        echo "  COVERAGE_THRESHOLD (default: 80)"
        exit 1
        ;;
esac
