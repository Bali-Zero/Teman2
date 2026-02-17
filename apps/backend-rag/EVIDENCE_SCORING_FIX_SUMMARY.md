# Evidence Scoring and ABSTAIN Logic Fix Summary

## Problems Fixed

### Problem 1: Wrong Scores

- Query "KITAS" was returning KBLI results with score 0.8 (high confidence)
- Results were completely wrong but scores didn't reflect this
- Score should be low (< 0.15) for irrelevant/mismatched results

### Problem 2: No ABSTAIN

- Query "xyzabc123 nonsense" was returning 5 results with score 0.8
- Should return ABSTAIN (refuse to answer) when no relevant context found
- Threshold: < 0.15 = ABSTAIN

## Changes Made

### 1. Fixed `calculate_evidence_score()` in `reasoning_utils.py`

**Key Changes:**

- Made semantic relevance the PRIMARY scoring factor (60-80% weight)
- Source quality now acts as a secondary bonus (20-40% weight)
- Added comprehensive stop words list (English, Italian, Indonesian)
- Increased minimum keyword length from 3 to 4 characters
- Added entity type mismatch detection (e.g., KITAS query returning KBLI content)
- Fixed keyword matching to avoid false positives from generic words

**New Scoring Formula:**

```
- Semantic Relevance (0.0-0.6): Based on keyword match ratio
  - Match ratio >= 0.5: 0.6 points (strong)
  - Match ratio >= 0.3: 0.4 points (moderate)
  - Match ratio >= 0.15: 0.2 points (weak)
  - Match ratio < 0.15: 0.0 points (none)

- Source Quality Bonus (0.0-0.4): Based on top source score
  - Source score >= 0.7: 0.4 points
  - Source score >= 0.5: 0.3 points
  - Source score >= 0.3: 0.2 points
  - Source score < 0.3: 0.0-0.1 points

- Final Score:
  - If semantic_relevance == 0: min(source_quality * 0.2, 0.1)
  - If semantic_relevance < 0.3: min(semantic + source * 0.25, 0.35)
  - If semantic_relevance >= 0.3: semantic + source * 0.5
```

### 2. Updated Constants in `constants.py`

**EvidenceScoreConstants:**

- `ABSTAIN_THRESHOLD`: Changed from 0.10 to **0.15**
- Added `CONFIDENCE_LOW`: 0.15
- Added `CONFIDENCE_CAUTIOUS`: 0.6
- Added `CONFIDENCE_HIGH`: 0.6

### 3. Updated Response Schema in `schema.py`

**CoreResult model:**

- Added `abstain: bool = False` - True when system refused to answer
- Added `abstain_reason: str | None = None` - Reason for abstaining

### 4. Updated Response Builder in `orchestrator_response.py`

**build_core_result() method:**

- Now determines `abstain` status based on evidence_score < ABSTAIN_THRESHOLD
- Sets `abstain_reason` based on score:
  - score < 0.05: "no_relevant_context"
  - score < 0.15: "low_confidence"
  - otherwise: "insufficient_evidence"

### 5. Updated Router in `agentic_rag.py`

**AgenticQueryResponse model:**

- Added `abstain: bool = False`
- Added `abstain_reason: str | None = None`
- Added `evidence_score: float = 0.0`

**Response now includes:**

```json
{
    "answer": "...",
    "sources": [...],
    "abstain": true,
    "abstain_reason": "low_confidence",
    "evidence_score": 0.08
}
```

### 6. Updated ABSTAIN Messages in `reasoning.py`

**New localized messages:**

- `"abstain"`: Short message - "Mi dispiace, non ho trovato informazioni rilevanti per questa domanda."
- `"abstain_detailed"`: Long message with alternative topics
- Critical domain queries use detailed ABSTAIN messages
- All ABSTAIN responses now return with `abstain: true` flag

## Test Coverage

Created comprehensive test suite in `test_evidence_scoring_abstain.py`:

### Tests Added (15 total):

1. `test_kitas_query_with_kbli_results_low_score` - Verifies mismatched topics score < 0.15
2. `test_nonsense_query_zero_score` - Verifies nonsense queries score < 0.15
3. `test_relevant_visa_query_high_score` - Verifies relevant queries score > 0.6
4. `test_partially_relevant_query_medium_score` - Tests cautious range scoring
5. `test_empty_context_zero_score` - Empty context returns 0.0
6. `test_keyword_match_ratio_scoring` - Keyword matching affects score
7. `test_entity_type_mismatch_detection` - Entity mismatches are penalized
8. `test_abstain_threshold_value` - Threshold is 0.15
9. `test_score_below_threshold_should_abstain` - Scores < 0.15 trigger ABSTAIN
10. `test_score_above_threshold_should_not_abstain` - Scores >= 0.15 don't trigger ABSTAIN
11. `test_confidence_level_definitions` - Constants are correct
12. `test_confidence_categories` - Score ranges map to correct categories
13. `test_high_quality_source_boost` - Good sources boost score
14. `test_low_quality_source_penalty` - Poor sources penalize score
15. `test_multiple_sources_bonus` - Multiple sources add small bonus

## Score Interpretation

| Score Range | Category  | Behavior                                               |
| ----------- | --------- | ------------------------------------------------------ |
| < 0.15      | ABSTAIN   | System refuses to answer, returns abstain message      |
| 0.15 - 0.6  | CAUTIOUS  | Low confidence, uses Tier 1 fallback with transparency |
| > 0.6       | CONFIDENT | Proceed with answer based on retrieved context         |

## Examples

### Before Fix:

```
Query: "KITAS requirements"
Results: KBLI business codes
Score: 0.8 (WRONG - should be low)
Response: Generated answer based on wrong context
```

### After Fix:

```
Query: "KITAS requirements"
Results: KBLI business codes
Score: 0.08 (CORRECT - low due to entity mismatch)
Response: {
    "answer": "Mi dispiace, non ho trovato informazioni rilevanti per questa domanda.",
    "abstain": true,
    "abstain_reason": "low_confidence",
    "evidence_score": 0.08
}
```

## Files Modified

1. `backend/services/rag/agentic/reasoning_utils.py` - Fixed `calculate_evidence_score()`
2. `backend/app/core/constants.py` - Updated ABSTAIN_THRESHOLD
3. `backend/services/rag/agentic/schema.py` - Added abstain fields to CoreResult
4. `backend/services/rag/agentic/orchestrator_response.py` - Set abstain in response
5. `backend/app/routers/agentic_rag.py` - Added abstain fields to API response
6. `backend/services/rag/agentic/reasoning.py` - Updated ABSTAIN messages

## Files Added

1. `backend/tests/services/rag/test_evidence_scoring_abstain.py` - Comprehensive test suite

## Verification

All tests pass:

```bash
pytest backend/tests/services/rag/test_evidence_scoring_abstain.py -v
# 15 passed

pytest backend/tests/services/rag/test_confidence_scoring.py -v
# 21 passed, 2 skipped
```
