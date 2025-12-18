#!/bin/bash

# DEEP ANALYSIS ENGINE for Nuzantara
# Uses SonarQube, CodeQL, and Semgrep for comprehensive security & quality analysis

set -e

echo "🔬 Nuzantara Deep Analysis Engine"
echo "================================="
echo "Time: $(date)"
echo "Root: $(pwd)"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Results directory
RESULTS_DIR="deep-analysis-results"
mkdir -p "$RESULTS_DIR"
echo -e "${BLUE}📁 Results directory: $RESULTS_DIR${NC}"
echo

# 1. SEMGREP SECURITY ANALYSIS
echo -e "${YELLOW}🔍 Phase 1: Semgrep Security Analysis${NC}"
echo "-----------------------------------------"

# Run multiple semgrep scans with different rule sets
echo "Running OWASP Top 10 scan..."
semgrep --config=owasp-top-ten \
        --config=security \
        --config=secrets \
        --severity=ERROR \
        --severity=WARNING \
        --json \
        --output="$RESULTS_DIR/semgrep-security.json" \
        apps/ 2>"$RESULTS_DIR/semgrep-errors.log" || true

echo "Running Performance scan..."
semgrep --config=performance \
        --json \
        --output="$RESULTS_DIR/semgrep-performance.json" \
        apps/ 2>/dev/null || true

echo "Running Python Best Practices scan..."
semgrep --config=p.lang.best-practice \
        --json \
        --output="$RESULTS_DIR/semgrep-bestpractices.json" \
        apps/ 2>/dev/null || true

# Count findings
SEMGREP_FINDINGS=$(cat "$RESULTS_DIR/semgrep-security.json" 2>/dev/null | jq '.results | length' 2>/dev/null || echo "0")
echo -e "${GREEN}✅ Semgrep completed with $SEMGREP_FINDINGS findings${NC}"
echo

# 2. CODEQL ANALYSIS
echo -e "${YELLOW}🔬 Phase 2: CodeQL Security Analysis${NC}"
echo "----------------------------------------"

# Create CodeQL database
echo "Creating CodeQL database..."
codeql database create "$RESULTS_DIR/codeql-db" \
    --language=python \
    --source-root=apps/backend-rag \
    --command="pip install -r requirements.txt" \
    2>"$RESULTS_DIR/codeql-create.log" || echo "⚠️ CodeQL DB creation had warnings"

# Run security analysis
echo "Running CodeQL security analysis..."
codeql database analyze "$RESULTS_DIR/codeql-db" \
    --format=csv \
    --output="$RESULTS_DIR/codeql-security.csv" \
    python-security-and-quality \
    2>"$RESULTS_DIR/codeql-analyze.log" || true

# Count CodeQL findings
CODEQL_FINDINGS=$(cat "$RESULTS_DIR/codeql-security.csv" 2>/dev/null | wc -l || echo "0")
echo -e "${GREEN}✅ CodeQL completed with $CODEQL_FINDINGS findings${NC}"
echo

# 3. SONARQUBE STATIC ANALYSIS
echo -e "${YELLOW}📊 Phase 3: SonarQube Quality Analysis${NC}"
echo "------------------------------------------"

# Create sonar-project.properties
cat > sonar-project.properties << EOF
sonar.projectKey=nuzantara-backend
sonar.projectName=Nuzantara Backend
sonar.projectVersion=1.0

# Source configuration
sonar.sources=apps/backend-rag/backend,apps/backend-rag/api
sonar.tests=apps/backend-rag/tests
sonar.inclusions=**/*.py
sonar.exclusions=**/__pycache__/**,**/node_modules/**,**/.next/**

# Language properties
sonar.python.coverage.reportPaths=apps/backend-rag/coverage.xml
sonar.python.xunit.reportPath=apps/backend-rag/test-results.xml

# Quality profile
sonar.qualityProfile.wait=true

# Encoding
sonar.sourceEncoding=UTF-8
EOF

# Run SonarQube scan (without server for now)
echo "Running SonarQube scan..."
sonar-scanner \
    -Dsonar.project.settings=sonar-project.properties \
    -Dsonar.working.directory="$RESULTS_DIR/.sonar" \
    2>"$RESULTS_DIR/sonar.log" || echo "⚠️ SonarQube scan completed with warnings"

echo -e "${GREEN}✅ SonarQube scan completed${NC}"
echo

# 4. FINDINGS SUMMARY
echo -e "${BLUE}📋 ANALYSIS SUMMARY${NC}"
echo "===================="
echo "Results saved in: $RESULTS_DIR"
echo
echo "Files generated:"
echo "🔴 semgrep-security.json - Security vulnerabilities"
echo "🔴 semgrep-performance.json - Performance issues"
echo "🔴 semgrep-bestpractices.json - Code best practices"
echo "🔴 codeql-security.csv - Advanced security analysis"
echo "🔴 sonar.log - Quality analysis log"
echo

# Show critical findings
if [ "$SEMGREP_FINDINGS" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL SEMGREP FINDINGS:${NC}"
    cat "$RESULTS_DIR/semgrep-security.json" | jq -r '.results[] | "  \(.metadata.severity): \(.message) in \(.path):\(.start.line)"' 2>/dev/null | head -10 || echo "  (Parse error)"
    echo
fi

if [ "$CODEQL_FINDINGS" -gt 1 ]; then
    echo -e "${RED}🚨 CRITICAL CODEQL FINDINGS:${NC}"
    cat "$RESULTS_DIR/codeql-security.csv" | tail -n +2 | cut -d',' -f1-3 | head -10 || echo "  (Parse error)"
    echo
fi

echo -e "${GREEN}✨ Deep Analysis Complete! ✨${NC}"
echo "Next steps:"
echo "1. Review JSON/CSV files for detailed findings"
echo "2. Prioritize critical security issues"
echo "3. Create tickets for remediation"
echo "4. Integrate into CI/CD pipeline"
