# Nuzantara RAG - A/B Testing Framework

## Overview

The A/B Testing Framework enables comparing different retrieval strategies in production to optimize RAG performance. It supports sticky user assignment, automatic metric recording, and statistical significance testing.

## Experiments Supported

### 1. `hybrid_vs_dense`

Compares hybrid search (BM25 + vector) vs dense-only search.

- **Variant A**: `dense_only` - Pure vector similarity search
- **Variant B**: `hybrid` - BM25 + vector with RRF fusion

### 2. `reranking_on_off`

Compares results with and without cross-encoder reranking.

- **Variant A**: `no_rerank` - No reranking applied
- **Variant B**: `with_rerank` - Cross-encoder reranking enabled

### 3. `query_expansion`

Compares query expansion enabled vs disabled.

- **Variant A**: `no_expansion` - Original query only
- **Variant B**: `with_expansion` - Query expanded with synonyms

## Metrics Tracked

- **CTR (Click-Through Rate)**: User clicked on a source document
- **Satisfaction**: Thumbs up/down feedback
- **Response Time**: Query processing time in seconds
- **Evidence Score**: Confidence score from retrieval

## Configuration

### Default Settings

- **Traffic Split**: 50/50 (configurable per experiment)
- **Minimum Sample Size**: 100 queries per variant
- **Confidence Level**: 95%

### Enabling/Disabling Experiments

```python
from backend.services.rag.evaluation import ABTestManager

ab_manager = ABTestManager()

# Enable experiment
ab_manager.enable_experiment("hybrid_vs_dense")

# Disable experiment
ab_manager.disable_experiment("hybrid_vs_dense")
```

## API Endpoints

### Query Endpoints (A/B Testing Integrated)

- `POST /api/agentic-rag/query` - Synchronous query with A/B test assignment
- `POST /api/agentic-rag/stream` - Streaming query with A/B test assignment

### A/B Testing Dashboard

- `GET /api/agentic-rag/ab-test/dashboard` - Full dashboard with all experiments
- `GET /api/agentic-rag/ab-test/experiments` - List available experiments
- `GET /api/agentic-rag/ab-test/results/{experiment}` - Results for specific experiment

### Feedback & Control

- `POST /api/agentic-rag/ab-test/feedback` - Record user feedback (thumbs up/down)
- `POST /api/agentic-rag/ab-test/experiments/{experiment}/control` - Enable/disable experiment
- `GET /api/agentic-rag/ab-test/user/{user_id}/exposure` - View user's experiment history

## Usage Example

### Assign Variant and Use Configuration

```python
from backend.services.rag.evaluation import ABTestManager

ab_manager = ABTestManager()

# Assign user to variant
variant = ab_manager.assign_variant("user123", "hybrid_vs_dense")

# Get variant configuration
config = ab_manager.get_variant_config("hybrid_vs_dense", variant)
# Returns: {"use_hybrid_search": True, "alpha": 0.5}

# Apply configuration to search
if config.get("use_hybrid_search"):
    results = await hybrid_search_service.search_hybrid(
        query=query,
        alpha=config.get("alpha", 0.5)
    )
else:
    results = await hybrid_search_service.search_dense_only(query=query)
```

### Record Metrics

```python
# Record a single metric
await ab_manager.record_metric(
    experiment="hybrid_vs_dense",
    variant="hybrid",
    metric="ctr",
    value=1.0,  # User clicked
    user_id="user123",
    query_id="query456",
)

# Record multiple metrics at once
await ab_manager.metrics_tracker.record_query_metrics(
    query_id="query456",
    user_id="user123",
    experiment="hybrid_vs_dense",
    variant="hybrid",
    metrics={
        "response_time": 1.25,
        "evidence_score": 0.85,
        "ctr": 1.0,
    },
)
```

### Check Statistical Significance

```python
# Get full experiment results
results = await ab_manager.get_experiment_results("hybrid_vs_dense")

# Check if results are significant
is_significant = await ab_manager.is_significant("hybrid_vs_dense", metric="ctr")

# Results include:
# - Variant counts and means
# - P-values and t-statistics
# - Uplift percentages
# - Statistical significance flag
```

## Database Schema

### Main Table: `ab_test_metrics`

```sql
CREATE TABLE ab_test_metrics (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    experiment VARCHAR(100) NOT NULL,
    variant VARCHAR(50) NOT NULL,
    metric VARCHAR(50) NOT NULL,
    value FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Summary Table: `ab_test_summaries`

Pre-aggregated metrics for fast dashboard queries.

## Statistical Methods

### Variant Assignment

- **Method**: Consistent hashing with MD5
- **Sticky Assignment**: Same user always gets same variant
- **Hash Input**: `{user_id}:{experiment}`

### Significance Testing

- **Method**: Welch's t-test for unequal variances
- **Confidence Level**: 95% (configurable)
- **Minimum Sample**: 100 per variant (configurable)
- **Output**: P-value, t-statistic, degrees of freedom, uplift %

## Testing

Run the test suite:

```bash
source .venv/bin/activate
python -m pytest backend/tests/services/rag/evaluation/test_ab_testing.py -v
```

45+ tests covering:

- Variant assignment and caching
- Metric recording and aggregation
- Statistical significance calculations
- Database operations
- Edge cases and error handling

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agentic RAG Router                       │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ /query       │  │ /stream      │  │ /ab-test/*      │   │
│  └──────┬───────┘  └──────┬───────┘  └─────────────────┘   │
│         │                 │                                 │
│         └─────────────────┘                                 │
│                   │                                         │
│         ┌─────────▼─────────┐                              │
│         │ ABTestManager     │                              │
│         │ - assign_variant()│                              │
│         │ - record_metric() │                              │
│         └─────────┬─────────┘                              │
│                   │                                         │
│         ┌─────────▼─────────┐                              │
│         │ MetricsTracker    │                              │
│         │ - PostgreSQL      │                              │
│         │ - Aggregations    │                              │
│         └───────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

## Monitoring & Alerts

The framework automatically logs:

- Variant assignments
- Metric recordings
- Statistical significance milestones
- Experiment status changes

Monitor via:

```python
# Get active experiments
active = await tracker.get_active_experiments(hours=24)

# Export data for analysis
raw_data = await tracker.export_experiment_data("hybrid_vs_dense")
```

## Future Enhancements

- Multi-variant experiments (A/B/C/D)
- Bandit algorithms for dynamic allocation
- Integration with MLflow for experiment tracking
- Automatic experiment stopping based on significance
- Real-time dashboard with WebSocket updates
