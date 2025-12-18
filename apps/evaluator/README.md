# Nuzantara RAG Evaluator

RAGAS-based evaluation system for Nuzantara RAG quality assessment.

## Setup

1. Install dependencies:
```bash
pip install -r ../backend-rag/requirements.txt
```

2. Set environment variables:
```bash
export GOOGLE_API_KEY="your-google-api-key"
export RAG_API_URL="http://localhost:8080"  # Optional, defaults to localhost
export API_KEY="REDACTED-ROTATED-KEY"  # Optional, uses default if not set
```

## Usage

Run the evaluation:
```bash
python apps/evaluator/judgement_day.py
```

This will:
1. Query the Nuzantara RAG API with 3 test questions about Indonesian Law
2. Collect answers and contexts
3. Evaluate using Ragas with Google Gemini as judge
4. Save results to `apps/evaluator/report.csv`

## Metrics

- **faithfulness**: Checks if the answer is grounded in the retrieved contexts
- **answer_relevancy**: Checks if the answer is relevant to the question

Both metrics return scores between 0.0 and 1.0.

## Testing

Run tests with coverage:
```bash
cd apps/evaluator
pip install pytest pytest-asyncio pytest-cov
pytest --cov=. --cov-report=term-missing
```

Run specific test class:
```bash
pytest test_judgement_day.py::TestQueryNuzantaraApi -v
```

## Output

The script generates `report.csv` with columns:
- `question`: The test question
- `answer`: The RAG system's answer
- `contexts`: List of retrieved contexts
- `faithfulness`: Faithfulness score (0.0-1.0)
- `answer_relevancy`: Answer relevancy score (0.0-1.0)
