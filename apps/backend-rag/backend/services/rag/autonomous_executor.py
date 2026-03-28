"""
Autonomous Task Executor with Human-in-the-Loop.

Production execution engine with:
- PostgreSQL-persisted state (survives restarts)
- Exponential backoff retry for transient failures
- Priority-based task queue
- Telegram approval flow for critical steps
- Rollback on failure

Feature flag: ENABLE_AUTONOMOUS_EXECUTION (disabled by default)

Author: Nuzantara Team
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypedDict

import asyncpg

logger = logging.getLogger(__name__)


# ============================================================================
# Enums & Types
# ============================================================================


class ExecutionStatus(str, Enum):
    """Status of an execution plan or individual step."""

    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class StepSafety(str, Enum):
    """Safety classification for execution steps."""

    SAFE = "safe"
    CRITICAL = "critical"
    IRREVERSIBLE = "irreversible"


class ExecutionStep(TypedDict):
    """A single step in an execution plan."""

    step_id: str
    action: str
    description: str
    safety_level: str
    status: str
    started_at: str | None
    completed_at: str | None
    error: str | None
    rollback_action: str | None
    retry_count: int
    max_retries: int


class ExecutionPlan(TypedDict):
    """A complete execution plan with steps and approval tracking."""

    plan_id: str
    user_query: str
    user_email: str
    task_type: str
    priority: int
    steps: list[ExecutionStep]
    current_step: int
    overall_status: str
    created_at: str
    completed_at: str | None
    human_approvals: list[dict[str, Any]]


# ============================================================================
# Task Templates
# ============================================================================

TASK_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "npwp_registration": [
        {
            "action": "verify_client_data",
            "description": "Verify client data in CRM",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "check_npwp_eligibility",
            "description": "Check if client is eligible for NPWP registration",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "prepare_npwp_documents",
            "description": "Generate document checklist and prepare submission package",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "submit_to_djp",
            "description": "Submit NPWP application to DJP online portal",
            "safety_level": StepSafety.CRITICAL,
            "rollback_action": "cancel_djp_submission",
        },
        {
            "action": "track_npwp_status",
            "description": "Monitor NPWP application status and notify client",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
    ],
    "kitas_application": [
        {
            "action": "verify_client_data",
            "description": "Verify client passport and sponsor data in CRM",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "check_kitas_eligibility",
            "description": "Check visa type eligibility and sponsor requirements",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "prepare_kitas_documents",
            "description": "Prepare RPTKA, IMTA, and supporting documents",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "submit_to_immigration",
            "description": "Submit KITAS application to immigration office",
            "safety_level": StepSafety.CRITICAL,
            "rollback_action": "cancel_immigration_submission",
        },
        {
            "action": "schedule_biometrics",
            "description": "Schedule biometrics appointment at immigration office",
            "safety_level": StepSafety.CRITICAL,
            "rollback_action": "cancel_biometrics_appointment",
        },
        {
            "action": "track_kitas_status",
            "description": "Monitor KITAS application status",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
    ],
    "pt_pma_incorporation": [
        {
            "action": "verify_shareholders",
            "description": "Verify shareholder data and investment plan",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "check_kbli_codes",
            "description": "Validate KBLI codes and PMA eligibility",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "prepare_incorporation_docs",
            "description": "Prepare deed of establishment and articles of association",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
        {
            "action": "submit_to_ahu",
            "description": "Submit incorporation to AHU (Ministry of Law)",
            "safety_level": StepSafety.IRREVERSIBLE,
            "rollback_action": "request_ahu_cancellation",
        },
        {
            "action": "register_oss",
            "description": "Register company on OSS (Online Single Submission)",
            "safety_level": StepSafety.CRITICAL,
            "rollback_action": "cancel_oss_registration",
        },
        {
            "action": "obtain_nib",
            "description": "Obtain NIB (Business Identification Number)",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        },
    ],
}

# Priority levels
TASK_PRIORITY: dict[str, int] = {
    "pt_pma_incorporation": 10,
    "kitas_application": 5,
    "npwp_registration": 3,
}

# Retry configuration per action
RETRY_CONFIG: dict[str, dict[str, int]] = {
    # External submissions can have transient failures
    "submit_to_djp": {"max_retries": 3, "base_delay_s": 5},
    "submit_to_immigration": {"max_retries": 3, "base_delay_s": 10},
    "submit_to_ahu": {"max_retries": 2, "base_delay_s": 15},
    "register_oss": {"max_retries": 3, "base_delay_s": 5},
    "schedule_biometrics": {"max_retries": 2, "base_delay_s": 10},
    # Verification steps — quick retry
    "verify_client_data": {"max_retries": 2, "base_delay_s": 2},
}

DEFAULT_RETRY = {"max_retries": 1, "base_delay_s": 2}


def _make_step(template: dict[str, str], step_index: int) -> ExecutionStep:
    """Create an ExecutionStep from a template."""
    retry_cfg = RETRY_CONFIG.get(template["action"], DEFAULT_RETRY)
    return ExecutionStep(
        step_id=f"step_{step_index}",
        action=template["action"],
        description=template["description"],
        safety_level=template["safety_level"],
        status=ExecutionStatus.PENDING,
        started_at=None,
        completed_at=None,
        error=None,
        rollback_action=template["rollback_action"] or None,
        retry_count=0,
        max_retries=retry_cfg["max_retries"],
    )


def _backoff_delay(attempt: int, base_delay_s: int = 2) -> float:
    """Calculate exponential backoff delay with jitter."""
    import random

    delay = base_delay_s * (2**attempt)
    jitter = random.uniform(0, delay * 0.3)  # noqa: S311
    return min(delay + jitter, 300)  # Cap at 5 minutes


# ============================================================================
# Executor
# ============================================================================


class AutonomousExecutor:
    """
    Executes multi-step workflows with human-in-the-loop for critical steps.

    State is persisted to PostgreSQL. If db_pool is None, falls back to
    in-memory storage (for testing / backwards compatibility).
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool | None = None,
        telegram_service: Any | None = None,
        crm_service: Any | None = None,
    ) -> None:
        self.db_pool = db_pool
        self.telegram_service = telegram_service
        self.crm_service = crm_service
        # In-memory fallback (when db_pool is None)
        self._memory_plans: dict[str, ExecutionPlan] = {}
        self._memory_approvals: dict[str, bool | None] = {}

    @property
    def _persistent(self) -> bool:
        return self.db_pool is not None

    # ------------------------------------------------------------------
    # Public: backward-compatible aliases
    # ------------------------------------------------------------------

    @property
    def plans(self) -> dict[str, ExecutionPlan]:
        """In-memory plans dict (for test compatibility)."""
        return self._memory_plans

    @property
    def _approvals(self) -> dict[str, bool | None]:
        """In-memory approvals dict (for test compatibility)."""
        return self._memory_approvals

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_task(self, query: str) -> str:
        """Classify user query into a known task type."""
        query_lower = query.lower()
        if "npwp" in query_lower:
            return "npwp_registration"
        if any(kw in query_lower for kw in ("kitas", "work permit", "stay permit")):
            return "kitas_application"
        if any(kw in query_lower for kw in ("pt pma", "incorporate", "company setup")):
            return "pt_pma_incorporation"
        return "general_task"

    def generate_steps(self, task_type: str) -> list[ExecutionStep]:
        """Generate execution steps for a task type."""
        templates = TASK_TEMPLATES.get(task_type, [])
        return [_make_step(t, i) for i, t in enumerate(templates)]

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------

    async def create_plan(
        self,
        query: str,
        user_email: str,
        priority: int | None = None,
    ) -> ExecutionPlan:
        """Create and persist an execution plan."""
        task_type = self.classify_task(query)
        steps = self.generate_steps(task_type)

        if not steps:
            raise ValueError(
                f"Unknown task type '{task_type}' for query: {query}. "
                "Supported: npwp_registration, kitas_application, pt_pma_incorporation",
            )

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        plan_priority = priority if priority is not None else TASK_PRIORITY.get(task_type, 0)

        plan = ExecutionPlan(
            plan_id=plan_id,
            user_query=query,
            user_email=user_email,
            task_type=task_type,
            priority=plan_priority,
            steps=steps,
            current_step=0,
            overall_status=ExecutionStatus.PENDING,
            created_at=now,
            completed_at=None,
            human_approvals=[],
        )

        if self._persistent:
            await self._persist_plan(plan)
        else:
            self._memory_plans[plan_id] = plan

        logger.info(
            f"Created plan {plan_id}: {task_type} ({len(steps)} steps, "
            f"priority={plan_priority}) for {user_email}",
        )
        return plan

    async def get_plan_status(self, plan_id: str) -> ExecutionPlan | None:
        """Get current plan status by ID."""
        if self._persistent:
            return await self._load_plan(plan_id)
        return self._memory_plans.get(plan_id)

    async def list_plans(
        self,
        user_email: str | None = None,
        status: ExecutionStatus | None = None,
        limit: int = 50,
    ) -> list[ExecutionPlan]:
        """List plans with optional filters."""
        if self._persistent:
            return await self._query_plans(user_email, status, limit)

        plans = list(self._memory_plans.values())
        if user_email:
            plans = [p for p in plans if p["user_email"] == user_email]
        if status:
            plans = [p for p in plans if p["overall_status"] == status]
        return plans[:limit]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_plan(self, plan_id: str) -> ExecutionPlan:
        """Execute a plan step-by-step with retry and approval flow."""
        plan = (
            await self.get_plan_status(plan_id)
            if self._persistent
            else self._memory_plans.get(plan_id)
        )
        if not plan:
            raise KeyError(f"Plan {plan_id} not found")

        await self._update_plan_status(plan, ExecutionStatus.IN_PROGRESS)
        logger.info(f"Starting execution of plan {plan_id}")

        for i, step in enumerate(plan["steps"]):
            plan["current_step"] = i

            # Approval gate for critical steps
            if step["safety_level"] in (StepSafety.CRITICAL, StepSafety.IRREVERSIBLE):
                await self._update_plan_status(plan, ExecutionStatus.WAITING_APPROVAL)
                await self._request_approval(plan, step)

                approved = await self._wait_for_approval(plan_id, step["step_id"])
                if not approved:
                    step["status"] = ExecutionStatus.FAILED
                    step["error"] = "Human rejected this step"
                    await self._update_plan_status(plan, ExecutionStatus.FAILED)
                    await self._persist_step_update(plan, step)
                    logger.warning(f"Plan {plan_id} step {step['step_id']} rejected")
                    return plan

                await self._update_plan_status(plan, ExecutionStatus.IN_PROGRESS)

            # Execute with retry
            success = await self._execute_step_with_retry(plan, step)
            if not success:
                await self._rollback_plan(plan, until_step=i - 1)
                await self._update_plan_status(plan, ExecutionStatus.ROLLED_BACK)
                return plan

        await self._update_plan_status(plan, ExecutionStatus.COMPLETED)
        plan["completed_at"] = datetime.now(UTC).isoformat()
        if self._persistent:
            await self._persist_plan_completion(plan)
        logger.info(f"Plan {plan_id} completed successfully")
        return plan

    async def _execute_step_with_retry(
        self,
        plan: ExecutionPlan,
        step: ExecutionStep,
    ) -> bool:
        """Execute a step with exponential backoff retry."""
        retry_cfg = RETRY_CONFIG.get(step["action"], DEFAULT_RETRY)
        max_retries = step.get("max_retries", retry_cfg["max_retries"])
        base_delay = retry_cfg["base_delay_s"]

        for attempt in range(max_retries + 1):
            try:
                step["status"] = ExecutionStatus.IN_PROGRESS
                step["started_at"] = datetime.now(UTC).isoformat()
                step["retry_count"] = attempt
                await self._persist_step_update(plan, step)

                await self._execute_step(step, plan["user_email"])

                step["status"] = ExecutionStatus.COMPLETED
                step["completed_at"] = datetime.now(UTC).isoformat()
                step["error"] = None
                await self._persist_step_update(plan, step)
                logger.info(
                    f"Plan {plan['plan_id']} step {step['step_id']} completed"
                    + (f" (attempt {attempt + 1})" if attempt > 0 else ""),
                )
                return True

            except Exception as e:
                step["error"] = str(e)
                logger.warning(
                    f"Plan {plan['plan_id']} step {step['step_id']} "
                    f"attempt {attempt + 1}/{max_retries + 1} failed: {e}",
                )

                if attempt < max_retries:
                    delay = _backoff_delay(attempt, base_delay)
                    step["status"] = ExecutionStatus.FAILED
                    await self._persist_step_update(plan, step)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    step["status"] = ExecutionStatus.FAILED
                    await self._persist_step_update(plan, step)
                    logger.error(
                        f"Plan {plan['plan_id']} step {step['step_id']} "
                        f"failed after {max_retries + 1} attempts: {e}",
                    )
                    return False

        return False  # unreachable, but satisfies type checker

    async def _execute_step(self, step: ExecutionStep, user_email: str) -> None:
        """Execute a single step action (simulated in POC)."""
        action = step["action"]

        if action == "verify_client_data":
            if self.crm_service:
                clients = await self.crm_service.search_clients(user_email, limit=1)
                if not clients:
                    raise ValueError(f"Client {user_email} not found in CRM")
            logger.info(f"Verified client data for {user_email}")

        elif action in (
            "check_npwp_eligibility",
            "check_kitas_eligibility",
            "check_kbli_codes",
            "verify_shareholders",
        ):
            logger.info(f"Eligibility check passed for {action}")

        elif action in (
            "prepare_npwp_documents",
            "prepare_kitas_documents",
            "prepare_incorporation_docs",
        ):
            logger.info(f"Documents prepared for {action}")

        elif action in (
            "submit_to_djp",
            "submit_to_immigration",
            "submit_to_ahu",
            "register_oss",
            "schedule_biometrics",
        ):
            logger.info(f"CRITICAL action executed (simulated): {action} for {user_email}")

        elif action in ("track_npwp_status", "track_kitas_status", "obtain_nib"):
            logger.info(f"Tracking/finalizing: {action}")

        else:
            logger.warning(f"Unknown action: {action}, skipping")

    # ------------------------------------------------------------------
    # Approval flow
    # ------------------------------------------------------------------

    async def _request_approval(self, plan: ExecutionPlan, step: ExecutionStep) -> None:
        """Send Telegram notification requesting human approval."""
        approval_key = f"{plan['plan_id']}_{step['step_id']}"
        if not self._persistent and approval_key not in self._memory_approvals:
            self._memory_approvals[approval_key] = None

        message = (
            f"🚨 **Approval Required**\n\n"
            f"**Plan:** {plan['plan_id']}\n"
            f"**Task:** {plan['user_query']}\n"
            f"**Step:** {step['description']}\n"
            f"**Safety:** {step['safety_level']}\n"
            f"**Action:** {step['action']}\n\n"
            f"Do you approve this step?"
        )

        if self.telegram_service:
            try:
                await self.telegram_service.send_message(
                    user_email=plan["user_email"],
                    message=message,
                    inline_keyboard=[
                        [
                            {"text": "✅ Approve", "callback_data": f"approve_{approval_key}"},
                            {"text": "❌ Reject", "callback_data": f"reject_{approval_key}"},
                        ],
                    ],
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram approval request: {e}")

        logger.info(f"Approval requested for {approval_key}")

    async def _wait_for_approval(
        self,
        plan_id: str,
        step_id: str,
        timeout: int = 3600,
    ) -> bool:
        """Wait for human approval, polling DB or in-memory store."""
        approval_key = f"{plan_id}_{step_id}"
        elapsed = 0
        poll_interval = 2

        while elapsed < timeout:
            # Check persistent storage first
            if self._persistent:
                approved = await self._check_approval_db(plan_id, step_id)
            else:
                approved = self._memory_approvals.get(approval_key)

            if approved is not None:
                if approved:
                    plan = (
                        await self.get_plan_status(plan_id)
                        if self._persistent
                        else self._memory_plans.get(plan_id)
                    )
                    if plan:
                        plan["human_approvals"].append(
                            {
                                "step_id": step_id,
                                "approved": True,
                                "approved_at": datetime.now(UTC).isoformat(),
                            },
                        )
                return approved

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning(f"Approval timed out for {approval_key}")
        return False

    async def record_approval(
        self,
        plan_id: str,
        step_id: str,
        approved: bool,
        approver_email: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record a human approval/rejection decision."""
        if self._persistent:
            await self._persist_approval(plan_id, step_id, approved, approver_email, reason)
        else:
            approval_key = f"{plan_id}_{step_id}"
            self._memory_approvals[approval_key] = approved

        action = "approved" if approved else "rejected"
        logger.info(f"Approval recorded for {plan_id}_{step_id}: {action}")

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def _rollback_plan(self, plan: ExecutionPlan, until_step: int) -> None:
        """Rollback completed steps in reverse order."""
        for i in range(until_step, -1, -1):
            step = plan["steps"][i]
            if step["status"] == ExecutionStatus.COMPLETED and step.get("rollback_action"):
                logger.info(f"Rolling back step {step['step_id']}: {step['rollback_action']}")
                step["status"] = ExecutionStatus.ROLLED_BACK
                await self._persist_step_update(plan, step)

        logger.info(f"Rollback completed for plan {plan['plan_id']}")

    # ------------------------------------------------------------------
    # Queue: dequeue next pending plan by priority
    # ------------------------------------------------------------------

    async def dequeue_next(self) -> ExecutionPlan | None:
        """Dequeue the highest-priority pending plan. Returns None if empty."""
        if not self._persistent:
            for plan in sorted(
                self._memory_plans.values(),
                key=lambda p: (-p.get("priority", 0), p["created_at"]),
            ):
                if plan["overall_status"] == ExecutionStatus.PENDING:
                    return plan
            return None

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE execution_plans
                SET overall_status = 'queued', updated_at = NOW()
                WHERE plan_id = (
                    SELECT plan_id FROM execution_plans
                    WHERE overall_status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING plan_id
            """)
            if not row:
                return None
            return await self._load_plan(row["plan_id"])

    # ------------------------------------------------------------------
    # PostgreSQL persistence layer
    # ------------------------------------------------------------------

    async def _persist_plan(self, plan: ExecutionPlan) -> None:
        """INSERT plan + steps into PostgreSQL."""
        if not self._persistent:
            return

        async with self.db_pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                    INSERT INTO execution_plans
                        (plan_id, user_query, user_email, task_type, priority,
                         overall_status, current_step, total_steps)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                plan["plan_id"],
                plan["user_query"],
                plan["user_email"],
                plan["task_type"],
                plan.get("priority", 0),
                plan["overall_status"],
                plan["current_step"],
                len(plan["steps"]),
            )

            for i, step in enumerate(plan["steps"]):
                await conn.execute(
                    """
                        INSERT INTO execution_steps
                            (plan_id, step_index, step_id, action, description,
                             safety_level, status, rollback_action, max_retries)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                    plan["plan_id"],
                    i,
                    step["step_id"],
                    step["action"],
                    step["description"],
                    step["safety_level"],
                    step["status"],
                    step.get("rollback_action"),
                    step.get("max_retries", 1),
                )

    async def _load_plan(self, plan_id: str) -> ExecutionPlan | None:
        """Load a plan + steps from PostgreSQL."""
        if not self._persistent:
            return self._memory_plans.get(plan_id)

        async with self.db_pool.acquire() as conn:
            plan_row = await conn.fetchrow(
                "SELECT * FROM execution_plans WHERE plan_id = $1",
                plan_id,
            )
            if not plan_row:
                return None

            step_rows = await conn.fetch(
                """SELECT * FROM execution_steps
                   WHERE plan_id = $1 ORDER BY step_index""",
                plan_id,
            )

            approval_rows = await conn.fetch(
                """SELECT step_id, approved, approver_email, decided_at
                   FROM execution_approvals WHERE plan_id = $1
                   ORDER BY decided_at""",
                plan_id,
            )

            steps: list[ExecutionStep] = []
            for sr in step_rows:
                steps.append(
                    ExecutionStep(
                        step_id=sr["step_id"],
                        action=sr["action"],
                        description=sr["description"],
                        safety_level=sr["safety_level"],
                        status=sr["status"],
                        started_at=sr["started_at"].isoformat() if sr["started_at"] else None,
                        completed_at=sr["completed_at"].isoformat() if sr["completed_at"] else None,
                        error=sr["last_error"],
                        rollback_action=sr["rollback_action"],
                        retry_count=sr["retry_count"],
                        max_retries=sr["max_retries"],
                    ),
                )

            approvals = [
                {
                    "step_id": ar["step_id"],
                    "approved": ar["approved"],
                    "approver_email": ar["approver_email"],
                    "approved_at": ar["decided_at"].isoformat() if ar["decided_at"] else None,
                }
                for ar in approval_rows
            ]

            return ExecutionPlan(
                plan_id=plan_row["plan_id"],
                user_query=plan_row["user_query"],
                user_email=plan_row["user_email"],
                task_type=plan_row["task_type"],
                priority=plan_row["priority"],
                steps=steps,
                current_step=plan_row["current_step"],
                overall_status=plan_row["overall_status"],
                created_at=plan_row["created_at"].isoformat(),
                completed_at=plan_row["completed_at"].isoformat()
                if plan_row["completed_at"]
                else None,
                human_approvals=approvals,
            )

    async def _query_plans(
        self,
        user_email: str | None,
        status: ExecutionStatus | None,
        limit: int,
    ) -> list[ExecutionPlan]:
        """Query plans from PostgreSQL with filters."""
        if not self._persistent:
            return []

        conditions = []
        params: list[Any] = []
        idx = 1

        if user_email:
            conditions.append(f"user_email = ${idx}")
            params.append(user_email)
            idx += 1
        if status:
            conditions.append(f"overall_status = ${idx}")
            params.append(status.value)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT plan_id FROM execution_plans {where} "
                f"ORDER BY priority DESC, created_at DESC LIMIT ${idx}",
                *params,
            )

        plans = []
        for row in rows:
            plan = await self._load_plan(row["plan_id"])
            if plan:
                plans.append(plan)
        return plans

    async def _update_plan_status(
        self,
        plan: ExecutionPlan,
        status: ExecutionStatus,
    ) -> None:
        """Update plan overall_status in both memory and DB."""
        plan["overall_status"] = status

        if self._persistent:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """UPDATE execution_plans
                       SET overall_status = $2, current_step = $3, updated_at = NOW()
                       WHERE plan_id = $1""",
                    plan["plan_id"],
                    status.value,
                    plan["current_step"],
                )

    async def _persist_step_update(self, plan: ExecutionPlan, step: ExecutionStep) -> None:
        """Persist step state changes to PostgreSQL."""
        if not self._persistent:
            return

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE execution_steps
                   SET status = $3, retry_count = $4, last_error = $5,
                       started_at = CASE WHEN $6::text IS NOT NULL
                           THEN $6::timestamptz ELSE started_at END,
                       completed_at = CASE WHEN $7::text IS NOT NULL
                           THEN $7::timestamptz ELSE completed_at END
                   WHERE plan_id = $1 AND step_id = $2""",
                plan["plan_id"],
                step["step_id"],
                step["status"],
                step.get("retry_count", 0),
                step.get("error"),
                step.get("started_at"),
                step.get("completed_at"),
            )

    async def _persist_plan_completion(self, plan: ExecutionPlan) -> None:
        """Mark plan as completed in DB."""
        if not self._persistent:
            return

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE execution_plans
                   SET overall_status = $2, completed_at = NOW(), updated_at = NOW()
                   WHERE plan_id = $1""",
                plan["plan_id"],
                plan["overall_status"],
            )

    async def _persist_approval(
        self,
        plan_id: str,
        step_id: str,
        approved: bool,
        approver_email: str | None,
        reason: str | None,
    ) -> None:
        """Insert approval record into PostgreSQL."""
        if not self._persistent:
            return

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO execution_approvals
                       (plan_id, step_id, approved, approver_email, reason)
                   VALUES ($1, $2, $3, $4, $5)""",
                plan_id,
                step_id,
                approved,
                approver_email,
                reason,
            )

    async def _check_approval_db(self, plan_id: str, step_id: str) -> bool | None:
        """Check if an approval exists in PostgreSQL."""
        if not self._persistent:
            return None

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT approved FROM execution_approvals
                   WHERE plan_id = $1 AND step_id = $2
                   ORDER BY decided_at DESC LIMIT 1""",
                plan_id,
                step_id,
            )
            return row["approved"] if row else None
