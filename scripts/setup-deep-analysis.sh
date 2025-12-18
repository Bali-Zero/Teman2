#!/bin/bash

# SETUP DEEP ANALYSIS ENVIRONMENT
# Installs and configures all deep analysis tools

echo "🚀 Setting up Deep Analysis Environment for Nuzantara"
echo "======================================================"

# Check if tools are installed
echo "Checking tool installation..."

# Check semgrep
if command -v semgrep &> /dev/null; then
    echo -e "✅ Semgrep: $(semgrep --version | head -1)"
else
    echo -e "❌ Semgrep not found. Installing..."
    brew install semgrep
fi

# Check codeql
if command -v codeql &> /dev/null; then
    echo -e "✅ CodeQL: $(codeql --version | head -1)"
else
    echo -e "❌ CodeQL not found. Installing..."
    brew install --cask codeql
fi

# Check sonar-scanner
if command -v sonar-scanner &> /dev/null; then
    echo -e "✅ SonarScanner: $(sonar-scanner --version | head -1)"
else
    echo -e "❌ SonarScanner not found. Installing..."
    brew install sonar-scanner
fi

# Check jq for JSON parsing
if command -v jq &> /dev/null; then
    echo -e "✅ jq: $(jq --version)"
else
    echo -e "❌ jq not found. Installing..."
    brew install jq
fi

echo
echo "Creating configuration files..."

# Create .semgrepignore
cat > .semgrepignore << EOF
# Ignore common non-source directories
.git
.vscode
.idea
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.egg-info
build
dist
node_modules
.next
.venv
env
venv
.coverage
htmlcov
.pytest_cache
.mypy_cache
.tox

# Ignore generated files
*.generated.*
**/generated/**
lib/api/generated/

# Ignore test files temporarily
tests/
test_*
*_test.py
EOF

# Create CodeQL custom queries directory
mkdir -p .codeql/queries

# Create custom CodeQL query for hardcoded secrets
cat > .codeql/queries/hardcoded-secrets.ql << 'EOF'
/**
 * @name Hardcoded secret in code
 * @description Finds hardcoded secrets and API keys
 * @kind problem
 * @problem.severity error
 * @id py/hardcoded-secret
 * @tags security
 */

import python

from string value, string name
where
  exists(string s |
    s = "password" or
    s = "secret" or
    s = "token" or
    s = "key" or
    s = "api_key"
  ) and
  (
    // Variable assignment with string literal
    exists(Assignment a |
      a.getTarget().getName() = name and
      name.matches("%" + s + "%") and
      a.getValue().(StrConst).getText() = value and
      value.length() > 10 and
      not value.matches("%localhost%") and
      not value.matches("%example%")
    ) or

    // Function parameter with default value
    exists(Parameter p |
      p.getName().matches("%" + s + "%") and
      p.getDefault().(StrConst).getText() = value and
      value.length() > 10
    )
  )
select value, "Hardcoded secret detected: " + value
EOF

# Create Semgrep custom rules
mkdir -p .semgrep/rules

cat > .semgrep/rules/nuzantara-security.yaml << 'EOF'
rules:
  - id: hardcoded-jwt-secret
    pattern: |
      JWT_SECRET = "..."
    message: Hardcoded JWT secret detected
    severity: ERROR
    languages: [python]
    metadata:
      category: security
      technology: [jwt]
      cwe: "CWE-798: Use of Hard-coded Credentials"

  - id: hardcoded-api-key
    pattern: |
      $VAR = "sk-proj-..." or
      $VAR = "zantara-secret-..."
    message: Hardcoded API key detected
    severity: ERROR
    languages: [python]
    metadata:
      category: security
      technology: [api]
      cwe: "CWE-798"

  - id: sql-injection-f-string
    pattern: |
      f"SELECT ... {$VAR} ..."
    message: Potential SQL injection with f-string
    severity: ERROR
    languages: [python]
    metadata:
      category: security
      technology: [sql]
      cwe: "CWE-89: SQL Injection"

  - id: dangerous-eval
    pattern: eval($INPUT)
    message: Use of eval() with user input
    severity: ERROR
    languages: [python]
    metadata:
      category: security
      technology: [python]
      cwe: "CWE-94: Improper Control of Generation of Code"

  - id: weak-crypto
    pattern: |
      hashlib.md5(...) or
      hashlib.sha1(...)
    message: Weak cryptographic algorithm detected
    severity: WARNING
    languages: [python]
    metadata:
      category: security
      technology: [crypto]
      cwe: "CWE-327: Use of a Broken or Risky Cryptographic Algorithm"
EOF

echo "✅ Configuration files created"
echo

# Install Python dependencies for analysis
echo "Installing Python dependencies..."
pip install jq 2>/dev/null || echo "jq not available via pip"

echo
echo "🎉 Setup complete!"
echo
echo "Usage:"
echo "  ./scripts/deep-analysis.sh    # Run complete analysis"
echo "  semgrep --config=.semgrep/rules apps/    # Run custom rules only"
echo "  codeql database analyze --format=sarif --output=results.sarif codeql-db python-security-and-quality"
echo
echo "📊 For full SonarQube dashboard:"
echo "  1. Start SonarQube server: docker run -d -p 9000:9000 sonarqube:community"
echo "  2. Visit: http://localhost:9000"
echo "  3. Configure project and run scan"
