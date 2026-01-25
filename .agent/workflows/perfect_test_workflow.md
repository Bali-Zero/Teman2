---
description: Zantara Triad Verification Protocol - A rigorous, multi-role testing workflow.
---

# Zantara Triad Verification Protocol

This workflow implements a "Triad" approach to system verification, splitting the agent's focus into three distinct roles to ensure comprehensive coverage.

## 1. The Watcher (Observer)

**Goal:** Capture the raw truth of system behavior (logs, metrics, errors) without bias.

1.  **Target Live Logs**:
    - If local: `docker compose logs -f backend-rag` or `tail -f apps/backend-rag/data/zantara_rag.log`
    - If cloud: `fly logs -a nuzantara-rag`
2.  **Filter Strategy**:
    - Grep for: `Evidence Score`, `ERROR`, `CRITICAL`, `Thinking Process`
    - Record _latency_ between request and first token (TTFT).

## 2. The Provocateur (Tester)

**Goal:** Stress-test the system via User simulation (Browser) and Infrastructure probes (Scripts).

1.  **Frontend Simulation (Browser Tool)**:
    - **Tone Check**: "Ciao!" (Expect: Natural response, no robot greeting).
    - **Stress Test**: "Analizza i file di migrazione e spiegami la logica del Knowledge Graph." (Expect: Long streaming response).
    - **Scroll Check**: Verify view stays at bottom during generation.
2.  **Infrastructure Probe (Script)**:
    - Run `python -m backend.tests.manual.test_drive_upload` (or equivalent) to verify Service Account permissions.

## 3. The Architect (Planner)

**Goal:** Synthesize findings into actionable fixes.

1.  **Correlate**: Match Frontend behavior (video/screenshot) with Backend logs (timestamped).
2.  **Decide**:
    - If Tone is rigid -> Adjust `prompt_builder.py`.
    - If Upload fails -> Check IAM/Scopes.
    - If Scroll lags -> Tuning `virtualizer` config.
3.  **Report**: Update `qa_compliance_report.md`.

## Execution Command

```bash
# To run this workflow, the agent will:
# 1. Start log monitoring in background.
# 2. Launch Browser Subagent for UI tests.
# 3. Analyze captured data.
```
