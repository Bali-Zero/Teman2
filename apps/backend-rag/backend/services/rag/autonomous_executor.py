"""
Autonomous Task Executor with Human-in-the-Loop.

POC for executing multi-step workflows with safety checks.
Critical steps pause for human approval via Telegram before proceeding.

Feature flag: ENABLE_AUTONOMOUS_EXECUTION (disabled by default)

Author: Windsurf
Created: 2026-02-09
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of an execution plan or individual step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepSafety(str, Enum):
    """Safety classification for execution steps."""

    SAFE = "safe"  # Can execute without approval
    CRITICAL = "critical"  # Requires human approval
    IRREVERSIBLE = "irreversible"  # Requires approval + confirmation


class ExecutionStep(TypedDict):
    """A single step in an execution plan."""

    step_id: str
    action: str
    description: str
    safety_level: str  # StepSafety value
    status: str  # ExecutionStatus value
    started_at: str | None
    completed_at: str | None
    error: str | None
    rollback_action: str | None


class ExecutionPlan(TypedDict):
    """A complete execution plan with steps and approval tracking."""

    plan_id: str
    user_query: str
    user_email: str
    task_type: str
    steps: list[ExecutionStep]
    current_step: int
    overall_status: str  # ExecutionStatus value
    created_at: str
    completed_at: str | None
    human_approvals: list[dict[str, Any]]


# Task type definitions with their step templates
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


def _make_step(template: dict[str, str], step_index: int) -> ExecutionStep:
    """Create an ExecutionStep from a template."""
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
    )


class AutonomousExecutor:
    """
    Executes multi-step workflows with human-in-the-loop for critical steps.

    Safe steps execute automatically. Critical/irreversible steps pause
    and request human approval via Telegram before proceeding.
    On failure, completed steps are rolled back in reverse order.
    """

    def __init__(
        self,
        db_pool: Any | None = None,
        telegram_service: Any | None = None,
        crm_service: Any | None = None,
    ):
        self.db_pool = db_pool
        self.telegram_service = telegram_service
        self.crm_service = crm_service
        # In-memory storage (POC) - production would use PostgreSQL
        self.plans: dict[str, ExecutionPlan] = {}
        # Approval tracking: {plan_id}_{step_id} -> bool
        self._approvals: dict[str, bool | None] = {}

    def classify_task(self, query: str) -> str:
        """
        Classify user query into a known task type.

        Args:
            query: Natural language task request

        Returns:
            Task type string matching TASK_TEMPLATES keys, or "general_task"
        """
        query_lower = query.lower()

        if "npwp" in query_lower:
            return "npwp_registration"
        elif any(kw in query_lower for kw in ("kitas", "work permit", "stay permit")):
            return "kitas_application"
        elif any(kw in query_lower for kw in ("pt pma", "incorporate", "company setup")):
            return "pt_pma_incorporation"
        return "general_task"

    def generate_steps(self, task_type: str) -> list[ExecutionStep]:
        """
        Generate execution steps for a task type.

        Args:
            task_type: One of the TASK_TEMPLATES keys

        Returns:
            List of ExecutionStep dicts, empty if task_type unknown
        """
        templates = TASK_TEMPLATES.get(task_type, [])
        return [_make_step(t, i) for i, t in enumerate(templates)]

    async def create_plan(self, query: str, user_email: str) -> ExecutionPlan:
        """
        Generate an execution plan from a user query.

        Args:
            query: Natural language task description
            user_email: Email of the requesting user

        Returns:
            ExecutionPlan with steps, status, and metadata

        Raises:
            ValueError: If task type is unknown or has no steps
        """
        task_type = self.classify_task(query)
        steps = self.generate_steps(task_type)

        if not steps:
            raise ValueError(
                f"Unknown task type '{task_type}' for query: {query}. "
                "Supported: npwp_registration, kitas_application, pt_pma_incorporation"
            )

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        plan = ExecutionPlan(
            plan_id=plan_id,
            user_query=query,
            user_email=user_email,
            task_type=task_type,
            steps=steps,
            current_step=0,
            overall_status=ExecutionStatus.PENDING,
            created_at=now,
            completed_at=None,
            human_approvals=[],
        )

        self.plans[plan_id] = plan
        logger.info(
            f"Created execution plan {plan_id}: {task_type} with {len(steps)} steps "
            f"for {user_email}"
        )
        return plan

    async def execute_plan(self, plan_id: str) -> ExecutionPlan:
        """
        Execute a plan step-by-step, pausing at critical steps for approval.

        Args:
            plan_id: ID of the plan to execute

        Returns:
            Updated ExecutionPlan with final status

        Raises:
            KeyError: If plan_id not found
        """
        plan = self.plans.get(plan_id)
        if not plan:
            raise KeyError(f"Plan {plan_id} not found")

        plan["overall_status"] = ExecutionStatus.IN_PROGRESS
        logger.info(f"Starting execution of plan {plan_id}")

        for i, step in enumerate(plan["steps"]):
            plan["current_step"] = i

            # Check if step requires approval
            if step["safety_level"] in (StepSafety.CRITICAL, StepSafety.IRREVERSIBLE):
                plan["overall_status"] = ExecutionStatus.WAITING_APPROVAL
                await self._request_approval(plan, step)

                approved = await self._wait_for_approval(plan_id, step["step_id"])
                if not approved:
                    step["status"] = ExecutionStatus.FAILED
                    step["error"] = "Human rejected this step"
                    plan["overall_status"] = ExecutionStatus.FAILED
                    logger.warning(
                        f"Plan {plan_id} step {step['step_id']} rejected by human"
                    )
                    return plan

                plan["overall_status"] = ExecutionStatus.IN_PROGRESS

            # Execute the step
            try:
                step["status"] = ExecutionStatus.IN_PROGRESS
                step["started_at"] = datetime.utcnow().isoformat()

                await self._execute_step(step, plan["user_email"])

                step["status"] = ExecutionStatus.COMPLETED
                step["completed_at"] = datetime.utcnow().isoformat()
                logger.info(f"Plan {plan_id} step {step['step_id']} completed")

            except Exception as e:
                step["status"] = ExecutionStatus.FAILED
                step["error"] = str(e)
                logger.error(
                    f"Plan {plan_id} step {step['step_id']} failed: {e}"
                )

                # Rollback completed steps in reverse
                await self._rollback_plan(plan, until_step=i - 1)
                plan["overall_status"] = ExecutionStatus.ROLLED_BACK
                return plan

        plan["overall_status"] = ExecutionStatus.COMPLETED
        plan["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"Plan {plan_id} completed successfully")
        return plan

    async def _execute_step(self, step: ExecutionStep, user_email: str) -> None:
        """
        Execute a single step action.

        In POC, most actions are simulated. Production would call real services.

        Args:
            step: The step to execute
            user_email: User email for CRM lookups
        """
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
            logger.info(f"CRITICAL action executed (POC simulation): {action} for {user_email}")

        elif action in ("track_npwp_status", "track_kitas_status", "obtain_nib"):
            logger.info(f"Tracking/finalizing: {action}")

        else:
            logger.warning(f"Unknown action: {action}, skipping")

    async def _request_approval(
        self, plan: ExecutionPlan, step: ExecutionStep
    ) -> None:
        """
        Send Telegram notification requesting human approval for a critical step.

        Args:
            plan: The execution plan
            step: The step requiring approval
        """
        approval_key = f"{plan['plan_id']}_{step['step_id']}"
        # Only set to pending if no approval has been recorded yet
        if approval_key not in self._approvals:
            self._approvals[approval_key] = None  # Pending

        message = (
            f"🚨 **Approval Required**\n\n"
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
                            {
                                "text": "✅ Approve",
                                "callback_data": f"approve_{approval_key}",
                            },
                            {
                                "text": "❌ Reject",
                                "callback_data": f"reject_{approval_key}",
                            },
                        ]
                    ],
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram approval request: {e}")

        logger.info(
            f"Approval requested for plan {plan['plan_id']} step {step['step_id']}"
        )

    async def _wait_for_approval(
        self, plan_id: str, step_id: str, timeout: int = 3600
    ) -> bool:
        """
        Wait for human approval of a critical step.

        In POC: polls in-memory approval dict.
        Production: would use Telegram webhook callback.

        Args:
            plan_id: Plan ID
            step_id: Step ID
            timeout: Max seconds to wait (default 1 hour)

        Returns:
            True if approved, False if rejected or timed out
        """
        approval_key = f"{plan_id}_{step_id}"
        elapsed = 0
        poll_interval = 1

        while elapsed < timeout:
            approval = self._approvals.get(approval_key)
            if approval is not None:
                if approval:
                    plan = self.plans.get(plan_id)
                    if plan:
                        plan["human_approvals"].append(
                            {
                                "step_id": step_id,
                                "approved": True,
                                "approved_at": datetime.utcnow().isoformat(),
                            }
                        )
                return approval

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning(f"Approval timed out for {approval_key}")
        return False

    def record_approval(self, plan_id: str, step_id: str, approved: bool) -> None:
        """
        Record a human approval/rejection decision.

        Called by the API endpoint when Telegram callback is received.

        Args:
            plan_id: Plan ID
            step_id: Step ID
            approved: True if approved, False if rejected
        """
        approval_key = f"{plan_id}_{step_id}"
        self._approvals[approval_key] = approved
        logger.info(
            f"Approval recorded for {approval_key}: {'approved' if approved else 'rejected'}"
        )

    async def _rollback_plan(self, plan: ExecutionPlan, until_step: int) -> None:
        """
        Rollback completed steps in reverse order.

        Args:
            plan: The execution plan
            until_step: Roll back from this step index down to 0
        """
        for i in range(until_step, -1, -1):
            step = plan["steps"][i]
            if step["status"] == ExecutionStatus.COMPLETED and step.get("rollback_action"):
                logger.info(
                    f"Rolling back step {step['step_id']}: {step['rollback_action']}"
                )
                step["status"] = ExecutionStatus.ROLLED_BACK
                # In production: execute actual rollback action

        logger.info(f"Rollback completed for plan {plan['plan_id']}")

    def get_plan_status(self, plan_id: str) -> ExecutionPlan | None:
        """Get current plan status by ID."""
        return self.plans.get(plan_id)

    def list_plans(self, user_email: str | None = None) -> list[ExecutionPlan]:
        """
        List all plans, optionally filtered by user email.

        Args:
            user_email: If provided, only return plans for this user

        Returns:
            List of ExecutionPlan dicts
        """
        plans = list(self.plans.values())
        if user_email:
            plans = [p for p in plans if p["user_email"] == user_email]
        return plans
