# Phase 7: Autonomous Execution POC - Implementation Brief

**Assigned to:** Available AI Agent
**Priority:** LOW (experimental POC)
**Estimated Effort:** 3-4 hours
**Dependencies:** Phase 4 (Feedback), Phase 6 (Multi-Agent)
**⚠️ WARNING:** This is experimental - requires human approval before real execution

---

## Objective

Create a **Proof of Concept** for autonomous task execution where the agent can execute workflows (e.g., "Create NPWP for client") with human-in-the-loop for critical steps.

---

## Scope Limitations (POC)

**What This POC CAN Do:**

- ✅ Generate task execution plan
- ✅ Track task status (pending → in_progress → completed)
- ✅ Request human approval for critical steps
- ✅ Execute safe actions (send notifications, create CRM records)
- ✅ Rollback on failure

**What This POC CANNOT Do:**

- ❌ Submit government forms automatically (requires human)
- ❌ Make payments (requires human)
- ❌ Sign legal documents (requires human)
- ❌ Any irreversible action without approval

---

## Architecture

```
User: "Create NPWP for client@example.com"
     ↓
Autonomous Agent (generates execution plan)
     ↓
  ┌─────────────────────────────────────┐
  │ Execution Plan                      │
  │ 1. Verify client data (SAFE)       │
  │ 2. Check NPWP eligibility (SAFE)   │
  │ 3. Prepare documents (SAFE)         │
  │ 4. Submit to DJP (🚨 CRITICAL)     │
  │ 5. Track status (SAFE)              │
  └─────────────────────────────────────┘
       ↓
  Auto-execute steps 1-3 ✅
       ↓
  ⏸️  PAUSE at step 4 (human approval required)
       ↓
  Send Telegram notification to agent
       ↓
  [Approve] ← Human clicks
       ↓
  Resume execution (steps 4-5) ✅
       ↓
  Final status update
```

---

## Implementation

### File 1: `backend/services/rag/autonomous_executor.py` (~350 lines)

```python
"""
Autonomous Task Executor with Human-in-the-Loop.

POC for executing multi-step workflows with safety checks.
"""

from enum import Enum
from typing import TypedDict, Literal
from datetime import datetime
import asyncio

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class StepSafety(str, Enum):
    SAFE = "safe"  # Can execute without approval
    CRITICAL = "critical"  # Requires human approval
    IRREVERSIBLE = "irreversible"  # Requires approval + confirmation

class ExecutionStep(TypedDict):
    step_id: str
    action: str
    description: str
    safety_level: StepSafety
    status: ExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    rollback_action: str | None  # How to undo this step

class ExecutionPlan(TypedDict):
    plan_id: str
    user_query: str
    user_email: str
    steps: list[ExecutionStep]
    current_step: int
    overall_status: ExecutionStatus
    created_at: datetime
    completed_at: datetime | None
    human_approvals: list[dict]

class AutonomousExecutor:
    def __init__(self, db_pool, telegram_service, crm_service):
        self.db_pool = db_pool
        self.telegram_service = telegram_service
        self.crm_service = crm_service
        self.plans: dict[str, ExecutionPlan] = {}  # In-memory storage (POC)

    async def create_plan(self, query: str, user_email: str) -> ExecutionPlan:
        """
        Generate execution plan from user query.

        Example:
            Query: "Create NPWP for client@example.com"
            → 5-step plan with safety levels
        """
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Parse query to determine task type
        task_type = self._classify_task(query)

        # Generate steps based on task type
        steps = self._generate_steps(task_type, user_email)

        plan = ExecutionPlan(
            plan_id=plan_id,
            user_query=query,
            user_email=user_email,
            steps=steps,
            current_step=0,
            overall_status=ExecutionStatus.PENDING,
            created_at=datetime.now(),
            completed_at=None,
            human_approvals=[]
        )

        self.plans[plan_id] = plan
        return plan

    def _classify_task(self, query: str) -> str:
        """Classify query into task type."""
        query_lower = query.lower()

        if "npwp" in query_lower:
            return "npwp_registration"
        elif "kitas" in query_lower or "work permit" in query_lower:
            return "kitas_application"
        elif "pt pma" in query_lower:
            return "pt_pma_incorporation"
        else:
            return "general_task"

    def _generate_steps(self, task_type: str, user_email: str) -> list[ExecutionStep]:
        """Generate execution steps for task type."""

        if task_type == "npwp_registration":
            return [
                ExecutionStep(
                    step_id="verify_client",
                    action="verify_client_data",
                    description=f"Verify client data in CRM for {user_email}",
                    safety_level=StepSafety.SAFE,
                    status=ExecutionStatus.PENDING,
                    started_at=None,
                    completed_at=None,
                    error=None,
                    rollback_action=None
                ),
                ExecutionStep(
                    step_id="check_eligibility",
                    action="check_npwp_eligibility",
                    description="Check if client is eligible for NPWP",
                    safety_level=StepSafety.SAFE,
                    status=ExecutionStatus.PENDING,
                    started_at=None,
                    completed_at=None,
                    error=None,
                    rollback_action=None
                ),
                ExecutionStep(
                    step_id="prepare_docs",
                    action="prepare_npwp_documents",
                    description="Generate document checklist",
                    safety_level=StepSafety.SAFE,
                    status=ExecutionStatus.PENDING,
                    started_at=None,
                    completed_at=None,
                    error=None,
                    rollback_action=None
                ),
                ExecutionStep(
                    step_id="submit_djp",
                    action="submit_to_djp",
                    description="Submit NPWP application to DJP online",
                    safety_level=StepSafety.CRITICAL,  # ← Requires approval
                    status=ExecutionStatus.PENDING,
                    started_at=None,
                    completed_at=None,
                    error=None,
                    rollback_action="cancel_djp_submission"
                ),
                ExecutionStep(
                    step_id="track_status",
                    action="track_npwp_status",
                    description="Monitor application status",
                    safety_level=StepSafety.SAFE,
                    status=ExecutionStatus.PENDING,
                    started_at=None,
                    completed_at=None,
                    error=None,
                    rollback_action=None
                )
            ]

        # Add more task types...
        return []

    async def execute_plan(self, plan_id: str) -> ExecutionPlan:
        """
        Execute plan step-by-step.
        Pauses at CRITICAL steps for human approval.
        """
        plan = self.plans[plan_id]
        plan["overall_status"] = ExecutionStatus.IN_PROGRESS

        for i, step in enumerate(plan["steps"]):
            plan["current_step"] = i

            # Check safety level
            if step["safety_level"] in [StepSafety.CRITICAL, StepSafety.IRREVERSIBLE]:
                # Pause and request approval
                plan["overall_status"] = ExecutionStatus.WAITING_APPROVAL
                await self._request_approval(plan, step)

                # Wait for approval (polling or webhook)
                approval_granted = await self._wait_for_approval(plan_id, step["step_id"])

                if not approval_granted:
                    plan["overall_status"] = ExecutionStatus.FAILED
                    step["error"] = "Human rejected step"
                    return plan

            # Execute step
            try:
                step["status"] = ExecutionStatus.IN_PROGRESS
                step["started_at"] = datetime.now()

                await self._execute_step(step, plan["user_email"])

                step["status"] = ExecutionStatus.COMPLETED
                step["completed_at"] = datetime.now()

            except Exception as e:
                step["status"] = ExecutionStatus.FAILED
                step["error"] = str(e)

                # Rollback previous steps
                await self._rollback_plan(plan, until_step=i-1)
                plan["overall_status"] = ExecutionStatus.ROLLED_BACK
                return plan

        plan["overall_status"] = ExecutionStatus.COMPLETED
        plan["completed_at"] = datetime.now()
        return plan

    async def _execute_step(self, step: ExecutionStep, user_email: str):
        """Execute a single step."""
        action = step["action"]

        if action == "verify_client_data":
            # Safe: just read CRM
            clients, _ = await self.crm_service.search_clients(user_email, limit=1)
            if not clients:
                raise ValueError(f"Client {user_email} not found in CRM")

        elif action == "check_npwp_eligibility":
            # Safe: business logic check
            # Check if client has KTP, is eligible age, etc.
            await asyncio.sleep(1)  # Simulate check

        elif action == "prepare_npwp_documents":
            # Safe: generate checklist
            await asyncio.sleep(1)  # Simulate generation

        elif action == "submit_to_djp":
            # CRITICAL: This would actually submit to government
            # In POC, just log the action
            print(f"🚨 CRITICAL: Would submit NPWP for {user_email} to DJP")
            await asyncio.sleep(2)  # Simulate submission

        elif action == "track_npwp_status":
            # Safe: polling status
            await asyncio.sleep(1)

        # Add more actions...

    async def _request_approval(self, plan: ExecutionPlan, step: ExecutionStep):
        """Send Telegram notification requesting approval."""
        message = f"""
        🚨 **Approval Required**

        **Task:** {plan['user_query']}
        **Step:** {step['description']}
        **Safety:** {step['safety_level']}

        **Action:** {step['action']}

        Do you approve this step?
        """

        # Send to assigned agent via Telegram
        await self.telegram_service.send_message(
            user_email=plan['user_email'],
            message=message,
            inline_keyboard=[
                [
                    {"text": "✅ Approve", "callback_data": f"approve_{plan['plan_id']}_{step['step_id']}"},
                    {"text": "❌ Reject", "callback_data": f"reject_{plan['plan_id']}_{step['step_id']}"}
                ]
            ]
        )

    async def _wait_for_approval(self, plan_id: str, step_id: str, timeout: int = 3600) -> bool:
        """Wait for human approval (polling)."""
        # In production: use webhook from Telegram callback
        # For POC: simulate approval after 5 seconds
        await asyncio.sleep(5)
        return True  # Auto-approve for POC

    async def _rollback_plan(self, plan: ExecutionPlan, until_step: int):
        """Rollback completed steps in reverse order."""
        for i in range(until_step, -1, -1):
            step = plan["steps"][i]
            if step["status"] == ExecutionStatus.COMPLETED and step["rollback_action"]:
                print(f"🔄 Rolling back step {step['step_id']}: {step['rollback_action']}")
                # Execute rollback action
                await asyncio.sleep(1)

    def get_plan_status(self, plan_id: str) -> ExecutionPlan | None:
        """Get current plan status."""
        return self.plans.get(plan_id)
```

---

### File 2: API Endpoints

**File:** `backend/app/routers/autonomous_execution.py` (~150 lines)

```python
from fastapi import APIRouter, Depends
from backend.services.rag.autonomous_executor import AutonomousExecutor, ExecutionPlan

router = APIRouter(prefix="/api/v1/autonomous", tags=["Autonomous Execution"])

@router.post("/create-plan")
async def create_execution_plan(
    query: str,
    user_email: str,
    executor: AutonomousExecutor = Depends(get_executor)
) -> ExecutionPlan:
    """Generate execution plan from user query."""
    plan = await executor.create_plan(query, user_email)
    return plan

@router.post("/execute/{plan_id}")
async def execute_plan(
    plan_id: str,
    executor: AutonomousExecutor = Depends(get_executor)
) -> ExecutionPlan:
    """Execute plan (will pause at critical steps)."""
    result = await executor.execute_plan(plan_id)
    return result

@router.get("/status/{plan_id}")
async def get_plan_status(
    plan_id: str,
    executor: AutonomousExecutor = Depends(get_executor)
) -> ExecutionPlan:
    """Get current execution status."""
    plan = executor.get_plan_status(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan

@router.post("/approve/{plan_id}/{step_id}")
async def approve_step(
    plan_id: str,
    step_id: str,
    executor: AutonomousExecutor = Depends(get_executor)
):
    """Approve a critical step (called from Telegram webhook)."""
    # Store approval in plan
    plan = executor.get_plan_status(plan_id)
    plan["human_approvals"].append({
        "step_id": step_id,
        "approved": True,
        "approved_at": datetime.now()
    })
    return {"status": "approved"}
```

---

### File 3: Tests

**File:** `backend/tests/services/rag/test_autonomous_executor.py` (~200 lines)

```python
import pytest
from backend.services.rag.autonomous_executor import AutonomousExecutor, ExecutionStatus

class TestPlanGeneration:
    async def test_generate_npwp_plan(self):
        """Generate 5-step NPWP plan."""
        plan = await executor.create_plan("Create NPWP for test@example.com", "test@example.com")

        assert len(plan["steps"]) == 5
        assert plan["steps"][0]["action"] == "verify_client_data"
        assert plan["steps"][3]["safety_level"] == "critical"  # Submit to DJP

class TestStepExecution:
    async def test_execute_safe_step(self):
        """Safe steps execute without approval."""
        # Test verify_client_data step
        pass

    async def test_pause_at_critical_step(self):
        """Critical steps pause for approval."""
        # Test that plan status becomes WAITING_APPROVAL
        pass

class TestRollback:
    async def test_rollback_on_failure(self):
        """Failed steps trigger rollback."""
        # Inject failure at step 3
        # Verify steps 0-2 are rolled back
        pass
```

---

## Success Criteria

✅ Generate execution plans for common tasks (NPWP, KITAS)
✅ Execute safe steps automatically
✅ Pause at critical steps for human approval
✅ Telegram notification sent for approval requests
✅ Rollback mechanism works on failure
✅ All tests passing (target: 10+ tests)

---

## Files to Create

| File                                                     | Purpose                    | Lines |
| -------------------------------------------------------- | -------------------------- | ----- |
| `backend/services/rag/autonomous_executor.py`            | Executor + plan generation | ~350  |
| `backend/app/routers/autonomous_execution.py`            | API endpoints              | ~150  |
| `backend/tests/services/rag/test_autonomous_executor.py` | Tests                      | ~200  |

**Total:** ~700 lines

---

## Safety Notes

⚠️ **CRITICAL:** This POC is for demonstration only!

- **Never auto-execute irreversible actions** (payments, submissions)
- **Always require approval** for government interactions
- **Log all executions** for audit trail
- **Test rollback thoroughly** before production
- **Disable by default** - require explicit feature flag `ENABLE_AUTONOMOUS_EXECUTION=true`

---

## Future Enhancements (Not in POC)

- **Persistent storage:** Save plans to PostgreSQL
- **Webhook integration:** Real Telegram approval callbacks
- **Advanced rollback:** Compensation transactions
- **Multi-tenant:** Isolated execution per team
- **Audit log:** Complete execution history

---

**Ready to implement?** Start with plan generation, then add safe step execution, then critical step approval logic.
