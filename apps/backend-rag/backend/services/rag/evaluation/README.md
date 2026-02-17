# RAGAS Evaluation Pipeline

Automated RAG evaluation using RAGAS metrics for the Nuzantara RAG system.

## Overview

This module provides comprehensive evaluation capabilities for measuring RAG system quality using the RAGAS (Retrieval-Augmented Generation Assessment) framework.

## Features

- **5 RAGAS Metrics**: Faithfulness, Answer Relevance, Context Precision, Context Recall, Context Entity Recall
- **Multilingual Support**: Evaluation prompts in Indonesian (ID) and English (EN)
- **Caching**: Result caching to reduce LLM costs
- **Benchmarking**: Compare multiple retrieval methods (dense, hybrid, hybrid+reranking)
- **Historical Tracking**: Store and compare results over time in PostgreSQL

## Quick Start

### Basic Evaluation

```python
from backend.services.rag.evaluation import get_ragas_evaluator

# Get evaluator instance
evaluator = get_ragas_evaluator()

# Evaluate a single query-answer pair
result = await evaluator.evaluate(
    query="Apa itu KITAS?",
    context=["KITAS adalah izin tinggal untuk WNA..."],
    answer="KITAS adalah izin tinggal.",
    ground_truth="KITAS (Kartu Izin Tinggal Terbatas)..."
)

print(result.metrics)
# {
#     "faithfulness": 0.95,
#     "answer_relevance": 0.90,
#     "context_precision": 0.85,
#     "context_recall": 0.80,
#     "context_entity_recall": 0.88
# }
```

### Individual Metrics

```python
# Evaluate specific metrics
faithfulness = await evaluator.evaluate_faithfulness(answer, context)
relevance = await evaluator.evaluate_answer_relevance(query, answer)
precision = await evaluator.evaluate_context_precision(query, context, ground_truth)
recall = await evaluator.evaluate_context_recall(query, context, ground_truth)
entity_recall = await evaluator.evaluate_context_entity_recall(answer, context)
```

### Build Evaluation Dataset

```python
from backend.services.rag.evaluation import DatasetBuilder

builder = DatasetBuilder()

# Build dataset from multiple sources
dataset = await builder.build_dataset(
    target_size=50,
    expert_ratio=0.3,      # 30% expert-curated
    user_ratio=0.2,        # 20% real user queries
    synthetic_ratio=0.5,   # 50% synthetic questions
)

# Save dataset
builder.save_dataset(dataset, "eval_dataset.json")

# Load dataset
loaded = builder.load_dataset("eval_dataset.json")
```

### Run Benchmark

```python
from backend.services.rag.evaluation import RAGBenchmark, BenchmarkConfig

# Configure benchmark
config = BenchmarkConfig(
    name="weekly_eval",
    description="Weekly RAG evaluation",
    collection="legal_unified_hybrid",
    search_methods=["dense", "hybrid", "hybrid_rerank"],
    limit=5,
    alpha=0.5,
)

# Run benchmark
benchmark = RAGBenchmark()
result = await benchmark.run_benchmark(dataset, config)

# Save results to database
await benchmark.save_results(result)

# Generate report
print(benchmark.generate_report(result))
```

### Weekly Automated Benchmark

```python
from backend.services.rag.evaluation import run_weekly_benchmark

# Run weekly benchmark with auto-generated dataset
result = await run_weekly_benchmark(
    collection="legal_unified_hybrid"
)

print(f"Best method: {result.comparison['best_method']}")
print(f"Best score: {result.comparison['best_overall_score']:.3f}")
```

## RAGAS Metrics

### 1. Faithfulness (0.0 - 1.0)

Measures whether the answer is grounded in the retrieved context.

- **High score**: Answer contains only facts from context
- **Low score**: Answer contains hallucinations or unsupported claims

### 2. Answer Relevance (0.0 - 1.0)

Measures whether the answer addresses the question.

- **High score**: Answer directly addresses the query
- **Low score**: Answer is off-topic or incomplete

### 3. Context Precision (0.0 - 1.0)

Measures whether retrieved context is relevant to the question.

- **High score**: All retrieved chunks are relevant
- **Low score**: Many retrieved chunks are irrelevant

### 4. Context Recall (0.0 - 1.0)

Measures whether all relevant context was retrieved.

- **High score**: All information needed is in context
- **Low score**: Important information is missing from context

### 5. Context Entity Recall (0.0 - 1.0)

Measures whether entities in the answer appear in the context.

- **High score**: All entities are found in context
- **Low score**: Entities in answer not supported by context

## Database Schema

### rag_evaluation_runs

```sql
CREATE TABLE rag_evaluation_runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    dataset_size INTEGER,
    config JSONB,
    results JSONB,
    comparison JSONB
);
```

## API Endpoints

### Run Evaluation

```python
# Example API usage
from backend.services.rag.evaluation import get_ragas_evaluator

@router.post("/evaluate")
async def evaluate_rag(request: EvaluationRequest):
    evaluator = get_ragas_evaluator()

    result = await evaluator.evaluate(
        query=request.query,
        context=request.context,
        answer=request.answer,
        ground_truth=request.ground_truth,
    )

    return {
        "metrics": result.metrics,
        "overall_score": result.overall_score,
    }
```

### Run Benchmark

```python
@router.post("/benchmark")
async def run_benchmark(config: BenchmarkConfig):
    benchmark = RAGBenchmark()

    # Load or build dataset
    builder = DatasetBuilder()
    dataset = await builder.build_dataset(target_size=50)

    # Run benchmark
    result = await benchmark.run_benchmark(dataset, config)

    # Save results
    await benchmark.save_results(result)

    return result.to_dict()
```

## Testing

Run the test suite:

```bash
# Run all evaluation tests
cd apps/backend-rag
pytest backend/tests/services/rag/evaluation/ -v

# Run with coverage
pytest backend/tests/services/rag/evaluation/ --cov=backend.services.rag.evaluation

# Run specific test file
pytest backend/tests/services/rag/evaluation/test_ragas_evaluator.py -v
```

## Configuration

### Environment Variables

```bash
# Evaluation settings
RAGAS_CACHE_TTL=86400  # Cache TTL in seconds (default: 24 hours)
RAGAS_ENABLE_CACHE=true

# LLM for evaluation (uses default LLM client)
GOOGLE_API_KEY=xxx
OPENAI_API_KEY=xxx
```

### Benchmark Settings

```python
BenchmarkConfig(
    name="my_benchmark",           # Benchmark run name
    description="Description",     # Description
    collection="my_collection",    # Qdrant collection
    search_methods=[               # Methods to compare
        "dense",                   # Dense vector only
        "hybrid",                  # BM25 + Dense
        "hybrid_rerank",          # Hybrid + Reranking
    ],
    limit=5,                      # Number of results per query
    alpha=0.5,                    # Hybrid weight (0.0=BM25, 1.0=Dense)
    rerank_top_k=10,              # Top k to rerank
)
```

## Directory Structure

```
backend/services/rag/evaluation/
├── __init__.py              # Public API exports
├── README.md                # This file
├── ragas_evaluator.py       # Core evaluator
├── dataset_builder.py       # Dataset construction
└── benchmark.py             # Benchmark runner

backend/tests/services/rag/evaluation/
├── __init__.py
├── test_ragas_evaluator.py  # Evaluator tests (35+ tests)
├── test_dataset_builder.py  # Dataset builder tests (35+ tests)
└── test_benchmark.py        # Benchmark tests (35+ tests)
```

## Performance Considerations

1. **Caching**: Enable result caching to reduce LLM costs
2. **Batch Size**: Process dataset in batches for large evaluations
3. **Parallel Execution**: Use asyncio for concurrent evaluation
4. **Database**: Store results in PostgreSQL for historical analysis

## Best Practices

1. **Ground Truth**: Always provide ground truth for precision/recall metrics
2. **Sample Size**: Use 50-100 samples for reliable benchmark results
3. **Diversity**: Include diverse query types (visa, business, tax, legal)
4. **Regular Runs**: Run weekly benchmarks to track performance trends
5. **Comparison**: Always compare against baseline (dense-only search)

## Troubleshooting

### Common Issues

**LLM Response Parsing Error**

```
Solution: Lower temperature (0.1) for more consistent JSON output
```

**Cache Not Working**

```
Check: Ensure enable_cache=True and cache_ttl is set correctly
```

**Database Connection Error**

```
Solution: Verify DATABASE_URL and ensure PostgreSQL is running
```

### Debug Mode

```python
# Enable verbose logging
import logging
logging.getLogger("backend.services.rag.evaluation").setLevel(logging.DEBUG)

# Get evaluator stats
stats = evaluator.get_stats()
print(f"Evaluations: {stats['total_evaluations']}")
print(f"Cache hits: {stats['cache_hits']}")
```
