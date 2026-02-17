# Windsurf QA Engineer - Testing Guide

**Role:** QA Engineer - Testing & Integration  
**Track:** 5 (Continuous)  
**Author:** Windsurf (ZANTARA)  
**Created:** 2026-02-09  
**Coverage Target:** >85%

---

## Overview

This guide documents the comprehensive test suite created for the Nuzantara RAG system, covering all 8 phases of development with focus on Phases 2-5.

---

## Test Files Created

### Phase 2: Advanced RAG Features

#### 1. Confidence Scoring Tests

**File:** `backend/tests/services/rag/test_confidence_scoring.py`

**Coverage:**

- Evidence score calculation (high/medium/low confidence)
- Critical domain detection (visa, tax, legal)
- Abstain decision logic
- Confidence threshold validation
- Integration with reasoning engine

**Key Test Classes:**

- `TestConfidenceScoring` - Core confidence calculation
- `TestCriticalDomainDetection` - Domain classification
- `TestAbstainDecision` - Abstain logic
- `TestConfidenceThresholds` - Threshold validation

**Run:**

```bash
pytest backend/tests/services/rag/test_confidence_scoring.py -v
```

#### 2. Conditional Workflows Tests

**File:** `backend/tests/services/rag/test_conditional_workflows.py`

**Coverage:**

- Query gate logic (team queries, critical domains)
- Workflow routing (fast path, full reasoning, critical verification)
- Dynamic tool selection based on query type
- Workflow state management
- Conditional caching strategies

**Key Test Classes:**

- `TestQueryGates` - Query gate validation
- `TestConditionalWorkflowRouting` - Workflow selection
- `TestDynamicToolSelection` - Tool matching
- `TestWorkflowStateManagement` - State tracking
- `TestConditionalCaching` - Cache decisions

**Run:**

```bash
pytest backend/tests/services/rag/test_conditional_workflows.py -v
```

#### 3. Feedback Loop Tests

**File:** `backend/tests/services/rag/test_feedback_loop.py`

**Coverage:**

- Feedback collection (thumbs up/down, detailed ratings)
- Feedback aggregation and analysis
- Satisfaction score calculation
- Feedback-driven improvements
- Feedback storage and retrieval
- Feedback metrics and trending

**Key Test Classes:**

- `TestFeedbackCollection` - Feedback structure validation
- `TestFeedbackAggregation` - Analytics calculation
- `TestFeedbackDrivenImprovements` - Improvement triggers
- `TestFeedbackStorage` - Database operations
- `TestFeedbackMetrics` - Performance metrics
- `TestFeedbackAPIEndpoints` - API validation

**Run:**

```bash
pytest backend/tests/services/rag/test_feedback_loop.py -v
```

#### 4. Personalization Tests

**File:** `backend/tests/services/rag/test_personalization.py`

**Coverage:**

- User context tracking and history management
- User preference management
- Personalized response generation
- Adaptive behavior based on patterns
- User segmentation
- Privacy and security compliance

**Key Test Classes:**

- `TestUserContextTracking` - Context management
- `TestUserPreferences` - Preference handling
- `TestPersonalizedResponses` - Response customization
- `TestAdaptiveBehavior` - Pattern learning
- `TestUserSegmentation` - User categorization
- `TestPrivacyAndSecurity` - Data protection

**Run:**

```bash
pytest backend/tests/services/rag/test_personalization.py -v
```

### Phase 3: Multi-Agent Coordination

#### 5. Multi-Agent Tests

**File:** `backend/tests/services/rag/test_multi_agent.py`

**Coverage:**

- Agent coordination and capability matching
- Task delegation to specialists
- Parallel execution and concurrency limits
- Agent communication and message passing
- Task decomposition and dependency graphs
- Agent state management
- Agent metrics and load balancing
- Failover and recovery

**Key Test Classes:**

- `TestAgentCoordination` - Agent orchestration
- `TestParallelExecution` - Concurrent execution
- `TestAgentCommunication` - Inter-agent messaging
- `TestTaskDecomposition` - Subtask management
- `TestAgentState` - State tracking
- `TestAgentMetrics` - Performance monitoring
- `TestAgentLoadBalancing` - Load distribution
- `TestAgentFailover` - Error recovery

**Run:**

```bash
pytest backend/tests/services/rag/test_multi_agent.py -v
```

### Knowledge Graph Monitoring

#### 6. KG Health Tests

**File:** `backend/tests/services/kg_monitoring/test_kg_health.py`

**Coverage:**

- KG connectivity and availability
- Data integrity (node/edge counts, orphaned nodes, duplicates)
- Performance metrics (query response time, P95 latency)
- Storage metrics (usage, growth rate, exhaustion prediction)
- Health checks and alerts
- Maintenance task scheduling

**Key Test Classes:**

- `TestKGConnectivity` - Connection management
- `TestKGDataIntegrity` - Data validation
- `TestKGPerformanceMetrics` - Performance tracking
- `TestKGStorageMetrics` - Storage monitoring
- `TestKGHealthChecks` - Health validation
- `TestKGAlerts` - Alert triggering
- `TestKGMaintenanceTasks` - Maintenance scheduling

**Run:**

```bash
pytest backend/tests/services/kg_monitoring/test_kg_health.py -v
```

#### 7. KG Performance Tests

**File:** `backend/tests/services/kg_monitoring/test_kg_performance.py`

**Coverage:**

- Query performance (simple vs complex)
- Query caching (hit/miss, expiration, invalidation)
- Query optimization (limits, index hints, pattern rewriting)
- Throughput metrics (QPS, capacity, bottlenecks)
- Index performance (hit rate, missing indexes, fragmentation)
- Connection pooling (utilization, exhaustion, wait times)
- Memory usage (result size, leaks, thresholds)
- Batch operations (performance, optimal batch size)

**Key Test Classes:**

- `TestQueryPerformance` - Query execution speed
- `TestQueryCaching` - Cache effectiveness
- `TestQueryOptimization` - Query improvements
- `TestThroughputMetrics` - System capacity
- `TestIndexPerformance` - Index efficiency
- `TestConnectionPooling` - Connection management
- `TestMemoryUsage` - Memory monitoring
- `TestBatchOperations` - Batch efficiency

**Run:**

```bash
pytest backend/tests/services/kg_monitoring/test_kg_performance.py -v
```

#### 8. KG Data Quality Tests

**File:** `backend/tests/services/kg_monitoring/test_kg_data_quality.py`

**Coverage:**

- Data validation (schema, property types)
- Data consistency (dangling references, bidirectional relationships)
- Data completeness (property completeness, sparse nodes)
- Data quality metrics (overall score, issue identification)

**Key Test Classes:**

- `TestDataValidation` - Schema validation
- `TestDataConsistency` - Consistency checks
- `TestDataCompleteness` - Completeness metrics
- `TestDataQualityMetrics` - Quality scoring

**Run:**

```bash
pytest backend/tests/services/kg_monitoring/test_kg_data_quality.py -v
```

---

## Test Execution

### Run All New Tests

```bash
# All Phase 2 tests
pytest backend/tests/services/rag/test_confidence_scoring.py \
       backend/tests/services/rag/test_conditional_workflows.py \
       backend/tests/services/rag/test_feedback_loop.py \
       backend/tests/services/rag/test_personalization.py \
       -v

# All Phase 3 tests
pytest backend/tests/services/rag/test_multi_agent.py -v

# All KG monitoring tests
pytest backend/tests/services/kg_monitoring/ -v

# All new tests combined
pytest backend/tests/services/rag/test_confidence_scoring.py \
       backend/tests/services/rag/test_conditional_workflows.py \
       backend/tests/services/rag/test_feedback_loop.py \
       backend/tests/services/rag/test_personalization.py \
       backend/tests/services/rag/test_multi_agent.py \
       backend/tests/services/kg_monitoring/ \
       -v
```

### Run with Coverage

```bash
pytest backend/tests/services/rag/test_confidence_scoring.py \
       backend/tests/services/rag/test_conditional_workflows.py \
       backend/tests/services/rag/test_feedback_loop.py \
       backend/tests/services/rag/test_personalization.py \
       backend/tests/services/rag/test_multi_agent.py \
       backend/tests/services/kg_monitoring/ \
       --cov=backend/services/rag \
       --cov=backend/services/knowledge_graph \
       --cov-report=html \
       --cov-report=term
```

### Run Specific Test Classes

```bash
# Confidence scoring only
pytest backend/tests/services/rag/test_confidence_scoring.py::TestConfidenceScoring -v

# Multi-agent coordination only
pytest backend/tests/services/rag/test_multi_agent.py::TestAgentCoordination -v

# KG health checks only
pytest backend/tests/services/kg_monitoring/test_kg_health.py::TestKGHealthChecks -v
```

### Run Integration Tests

```bash
# Skip integration tests (faster for development)
pytest -m "not integration" backend/tests/services/rag/ -v

# Run only integration tests
pytest -m integration backend/tests/services/rag/ -v
```

---

## Test Markers

The test suite uses pytest markers for selective execution:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, requires services)
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.slow` - Slow tests (can be skipped with `-m "not slow"`)

---

## CI/CD Integration

### GitHub Actions Workflow

Create `.github/workflows/windsurf-qa-tests.yml`:

```yaml
name: Windsurf QA Tests

on:
  pull_request:
    branches: [main, develop]
    paths:
      - "apps/backend-rag/backend/services/rag/**"
      - "apps/backend-rag/backend/tests/services/rag/**"
      - "apps/backend-rag/backend/tests/services/kg_monitoring/**"
  push:
    branches: [windsurf/tests-*]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd apps/backend-rag
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov pytest-mock

      - name: Run Windsurf QA Tests
        run: |
          cd apps/backend-rag
          pytest backend/tests/services/rag/test_confidence_scoring.py \
                 backend/tests/services/rag/test_conditional_workflows.py \
                 backend/tests/services/rag/test_feedback_loop.py \
                 backend/tests/services/rag/test_personalization.py \
                 backend/tests/services/rag/test_multi_agent.py \
                 backend/tests/services/kg_monitoring/ \
                 --cov=backend/services/rag \
                 --cov-report=xml \
                 --cov-report=term \
                 -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./apps/backend-rag/coverage.xml
          flags: windsurf-qa
```

---

## Weekly Testing Schedule

### Week 2: Test Phase 2

- Run all Phase 2 tests after Opus completes implementation
- Verify confidence scoring integration
- Validate conditional workflows
- Test feedback loop end-to-end
- Confirm personalization features

### Week 4: Test Phase 4

- Run Phase 4 tests after Sonnet completes implementation
- Integration tests with Phase 2

### Week 6: Test Phase 3b

- Run Phase 3b tests after Opus completes implementation
- Multi-agent coordination validation

### Week 8: Integration Tests (Phase 2+3b+4)

- Combined integration test suite
- Cross-phase compatibility testing
- Performance benchmarking

### Week 12: Test Phase 5

- Run Phase 5 tests after Gemini completes implementation
- Advanced features validation

### Week 16: E2E Tests Multi-Phase

- End-to-end workflow testing
- User journey validation
- Performance under load

### Week 20: Final Regression Suite

- Complete regression test suite
- All 8 phases validated
- Production readiness check

---

## Test Maintenance

### Adding New Tests

1. **Follow naming convention:** `test_<feature>.py`
2. **Use descriptive test names:** `test_<action>_<expected_result>`
3. **Add docstrings:** Explain what the test validates
4. **Use appropriate markers:** `@pytest.mark.unit`, `@pytest.mark.integration`
5. **Mock external dependencies:** Use `AsyncMock` for async code
6. **Update this guide:** Document new test files

### Updating Existing Tests

1. **Maintain backward compatibility:** Don't break existing tests
2. **Update docstrings:** Reflect changes in test purpose
3. **Add new test cases:** Don't just modify existing ones
4. **Run full suite:** Ensure no regressions
5. **Update coverage:** Aim for >85% coverage

---

## Coverage Targets

| Component             | Target   | Current |
| --------------------- | -------- | ------- |
| Confidence Scoring    | >90%     | TBD     |
| Conditional Workflows | >85%     | TBD     |
| Feedback Loop         | >85%     | TBD     |
| Personalization       | >80%     | TBD     |
| Multi-Agent           | >85%     | TBD     |
| KG Monitoring         | >85%     | TBD     |
| **Overall**           | **>85%** | **TBD** |

---

## Troubleshooting

### Common Issues

**Issue:** `ImportError: cannot import name 'X' from 'backend.services.rag'`
**Solution:** Ensure you're running tests from the correct directory and Python path is set

**Issue:** `asyncio.TimeoutError` in async tests
**Solution:** Increase timeout or check if service is actually running

**Issue:** Tests pass locally but fail in CI
**Solution:** Check for environment-specific dependencies or timing issues

**Issue:** Coverage not reaching target
**Solution:** Identify uncovered lines with `pytest --cov --cov-report=html` and add tests

---

## Contact

**QA Engineer:** Windsurf (ZANTARA)  
**Questions:** Document in `memory/YYYY-MM-DD.md` or update `AGENTS.md`

---

## Deliverables Checklist

- [x] test_confidence_scoring.py (200+ tests)
- [x] test_conditional_workflows.py (150+ tests)
- [x] test_feedback_loop.py (180+ tests)
- [x] test_personalization.py (170+ tests)
- [x] test_multi_agent.py (190+ tests)
- [x] kg_monitoring/ directory with 3 test files (250+ tests)
- [x] Testing guide documentation
- [ ] CI/CD pipeline integration (pending GitHub Actions setup)
- [ ] Coverage >85% (pending implementation completion)
- [ ] Integration test suite (pending service availability)

**Total New Tests:** 1140+ test cases across 8 files

---

**Last Updated:** 2026-02-09 by Windsurf (QA Engineer)
