---
description: Zantara Agent Fleet Verification Protocol
---

# Zantara Live Verification Protocol

This workflow deploys the "Agent Fleet" (simulated by `zantara_fleet_check.py`) to verify Zantara's core systems across three vectors:

1.  **Knowledge Base (Alpha)**: Verifies Deep RAG retrieval (KITAS, PMA).
2.  **Tools (Beta)**: Verifies backend tool usage (Pricing, Calculator).
3.  **Communication (Gamma)**: Verifies identity and interaction fluidity.

## Prerequisites

- Backend environment variables must be configured (especially `GOOGLE_API_KEY`).
- Virtualenv must be active.

## Steps

### 1. Ensure Backend is Running

The verification script interacts with the live API.
Make sure the backend is running on `http://localhost:8080`.

```bash
# In a separate terminal:
docker compose up backend
# OR
cd apps/backend-rag && ./start_backend.sh
```

### 2. Engage the Fleet

Run the fleet verification script.

// turbo

```bash
python apps/evaluator/zantara_fleet_check.py
```

### 3. Analyze Report

- If **SUCCESS**: The system is field-ready.
- If **FAILURE**: Check `zantara_fleet_check.py` logs for specific agent failures.

### 3. Fix & Retry

If failures are detected, fix the underlying service in `backend/services/` and re-run step 1.
