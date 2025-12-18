# Load Tests

Load testing harness using Locust for critical backend endpoints.

## Prerequisites

```bash
pip install locust
```

## Usage

### Local Testing

```bash
# Basic smoke test
locust -f tests/load/locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 2 --run-time 60s

# Production testing
locust -f tests/load/locustfile.py --host=https://nuzantara-rag.fly.dev --users 50 --spawn-rate 5 --run-time 300s
```

### Headless Mode (CI)

```bash
locust -f tests/load/locustfile.py \
  --host=https://nuzantara-rag.fly.dev \
  --users 100 \
  --spawn-rate 10 \
  --run-time 300s \
  --headless \
  --html reports/load_test_report.html \
  --csv reports/load_test
```

### Web UI Mode

```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000
# Then open http://localhost:8089
```

## Test Scenarios

### Health Endpoints (30% of load)
- `/health` - Basic health check
- `/health/ready` - Readiness check
- `/health/detailed` - Detailed health

### Search Endpoints (30% of load)
- `/api/search/?query=...` - Basic search
- `/api/search/?query=...&tier=A` - Tier filtering
- `/api/search/?query=...&limit=20` - Custom limits

### Oracle Endpoints (20% of load)
- `/api/oracle/query` - Oracle queries

### Agentic RAG SSE (10% of load)
- `/api/agentic-rag/stream` - Streaming responses

### Auth Endpoints (10% of load)
- `/api/auth/login` - Login attempts (success + fail)

## Metrics

Locust reports:
- **p50/p95/p99**: Response time percentiles
- **RPS**: Requests per second
- **Error rate**: Percentage of failed requests
- **Timeouts**: Requests exceeding timeout threshold

## Automated Testing Integration

Add load tests to your automated testing configuration:

```yaml
# Example CI/CD configuration
load-tests:
  stage: test
  image: python:3.11-slim
  script:
    - pip install locust
    - locust -f tests/load/locustfile.py \
        --host=https://nuzantara-rag.fly.dev \
        --users 50 \
        --spawn-rate 5 \
        --run-time 300s \
        --headless \
        --html reports/load_test.html
  artifacts:
    when: always
    paths:
      - reports/load_test.html
```

## Thresholds

Expected performance (smoke test):
- `/health`: p95 < 100ms
- `/api/search/`: p95 < 500ms
- `/api/oracle/query`: p95 < 2000ms
- `/api/agentic-rag/stream`: p95 < 5000ms (first chunk)
- Error rate < 1%

