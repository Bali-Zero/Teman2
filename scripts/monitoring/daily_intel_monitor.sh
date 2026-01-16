#!/bin/bash
# Daily Intel Router monitoring script
# Run via cron: 0 9 * * * /path/to/daily_intel_monitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$SCRIPT_DIR/../monitoring/reports"
DATE=$(date +%Y%m%d)

mkdir -p "$REPORT_DIR"

echo "=========================================="
echo "Daily Intel Router Monitoring"
echo "Date: $(date)"
echo "=========================================="
echo ""

# 1. Monitor logs
echo "1. Checking logs for errors..."
python3 "$SCRIPT_DIR/monitor_intel_logs.py" 200 > "$REPORT_DIR/logs_$DATE.txt" 2>&1
LOGS_EXIT=$?

# 2. Monitor metrics
echo "2. Checking Prometheus metrics..."
python3 "$SCRIPT_DIR/monitor_intel_metrics.py" > "$REPORT_DIR/metrics_$DATE.txt" 2>&1
METRICS_EXIT=$?

# 3. Monitor performance
echo "3. Measuring performance..."
python3 "$SCRIPT_DIR/monitor_intel_performance.py" 5 > "$REPORT_DIR/performance_$DATE.txt" 2>&1
PERF_EXIT=$?

# 4. Run production tests
echo "4. Running production tests..."
python3 "$SCRIPT_DIR/../testing/test_intel_production.py" > "$REPORT_DIR/production_test_$DATE.txt" 2>&1
TEST_EXIT=$?

# Summary
echo ""
echo "=========================================="
echo "Monitoring Summary"
echo "=========================================="
echo "Logs check: $([ $LOGS_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Metrics check: $([ $METRICS_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Performance check: $([ $PERF_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Production tests: $([ $TEST_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo ""

# Overall status
if [ $LOGS_EXIT -eq 0 ] && [ $METRICS_EXIT -eq 0 ] && [ $PERF_EXIT -eq 0 ] && [ $TEST_EXIT -eq 0 ]; then
    echo "✅ All checks passed"
    exit 0
else
    echo "⚠️  Some checks failed - review reports in $REPORT_DIR"
    exit 1
fi
