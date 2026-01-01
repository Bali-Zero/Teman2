# Check if coverage file exists (proof that tests ran)
if [ -f "apps/mouth/coverage/lcov.info" ]; then
    echo "✅ Coverage Gate: Report found."
    
    # Extract Line Coverage from lcov.info summary (simple approximation)
    # LCOV doesn't simple summary in the file, but we can check the text summary output if we piped it.
    # Alternatively, use coverage-percentage if available.
    # For now, let's keep it simple: existence is the first gate. 
    # To satisfy "Pignolo", we need actual metrics. 
    # Let's rely on the fact that standard Vitest text reporter prints to stdout.
    # But CI runs this script AFTER tests.
    
    # Let's use a simple awk script to calculate percentage from lcov.info
    # LF = total lines found, LH = total lines hit
    
    TOTAL_LINES=$(grep "LF:" apps/mouth/coverage/lcov.info | awk -F: '{sum+=$2} END {print sum}')
    HIT_LINES=$(grep "LH:" apps/mouth/coverage/lcov.info | awk -F: '{sum+=$2} END {print sum}')
    
    if [ -z "$TOTAL_LINES" ] || [ "$TOTAL_LINES" -eq 0 ]; then
        echo "⚠️  Coverage Gate: Invalid coverage data (0 lines)."
        exit 1
    fi

    COVERAGE_PCT=$(( 100 * HIT_LINES / TOTAL_LINES ))
    
    echo "📊 Calculated Coverage: $COVERAGE_PCT%"
    
    if [ "$COVERAGE_PCT" -lt 15 ]; then
        echo "❌ Coverage Gate Failed: $COVERAGE_PCT% < 15%"
        exit 1
    else
        echo "✅ Coverage Gate Passed: $COVERAGE_PCT% >= 15%"
        exit 0
    fi
else
    echo "⚠️  Coverage Gate: Report NOT found!"
    # Fail CI if report is missing? For "Pignolo", yes.
    echo "   Ensure 'npm run test:ci -w apps/mouth' ran successfully."
    exit 1
fi
