# Nuzantara RAG Evaluator

Security and quality evaluation tools for the Nuzantara RAG system.

## Tools

### 1. Red Team Evaluator (`red_team_evaluator.py`)

Adversarial security testing framework with 50 test cases across 5 categories:

| Category | Tests | Description |
|----------|-------|-------------|
| `router_confusion` | 10 | Tests to confuse `detect_team_query()` routing |
| `infinite_loop` | 10 | Tests to force recursive/infinite tool calls |
| `prompt_injection` | 15 | Tests to bypass security filters |
| `evidence_manipulation` | 5 | Tests to manipulate evidence scoring |
| `policy_bypass` | 10 | Tests to circumvent safety policies |

**Usage:**
```bash
# Against production
export JUDGEMENT_DAY_API_KEY="your-api-key"
export RAG_API_URL="https://nuzantara-rag.fly.dev"
python red_team_evaluator.py

# Against local
export RAG_API_URL="http://localhost:8000"
python red_team_evaluator.py

# With options
MAX_CONCURRENT=5 TEST_TIMEOUT=60 python red_team_evaluator.py
```

**Output:**
- `red_team_report.md` - Human-readable report with recommendations
- `red_team_report.json` - Structured data for CI/CD integration

**CI/CD Integration:**
- Exit code 0 if survival rate >= 70%
- Exit code 1 if survival rate < 70%

**Latest Results (2025-12-28):**
- Survival Rate: **90.00%**
- Status: GOOD
- Vulnerabilities found: 5 (see report for details)

### 2. RAGAS Evaluation (`judgement_day.py`)

Quality evaluation using RAGAS metrics with Google Gemini as judge.

**Metrics:**
- `faithfulness` - Is the answer grounded in retrieved contexts?
- `answer_relevancy` - Is the answer relevant to the question?

**Usage:**
```bash
export GOOGLE_API_KEY="your-google-api-key"
export RAG_API_URL="https://nuzantara-rag.fly.dev"
python judgement_day.py
```

### 3. Mock RAG Server (`mock_rag_server.py`)

Lightweight mock server for testing the evaluation framework without full backend setup.

```bash
python mock_rag_server.py  # Runs on port 8000
```

## Test Cases

Test cases are defined in `adversarial_tests.json`. Each test includes:
- `id` - Unique identifier (e.g., "RC-001", "PI-009")
- `category` - Test category
- `name` - Human-readable name
- `query` - The adversarial query to send
- `expected_behavior` - What the system should do
- `attack_vector` - How the test attempts to exploit the system

## Reports

Reports are generated in both Markdown and JSON formats:
- Summary statistics
- Results by category
- Detailed failure analysis
- Recommendations for fixes

## Security Thresholds

| Survival Rate | Status | CI Exit Code |
|---------------|--------|--------------|
| >= 95% | EXCELLENT | 0 |
| 85-94% | GOOD | 0 |
| 70-84% | MODERATE | 0 |
| < 70% | POOR | 1 |
