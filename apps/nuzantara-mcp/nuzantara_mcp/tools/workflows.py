"""Workflow Tools - 8 tools for autonomous execution and agent management."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def create_execution_plan(
        query: str,
        client_id: Optional[str] = None,
    ) -> dict:
        """
        Create a deterministic execution plan for a business task.

        The system identifies the task type (NPWP registration, KITAS application,
        PT PMA incorporation, etc.) and creates a step-by-step plan with
        safety levels (SAFE, CRITICAL, IRREVERSIBLE).

        Args:
            query: Natural language description of the task
            client_id: Optional client UUID to associate the plan with

        Returns:
            Plan with plan_id, task_type, steps (each with action, description, safety_level).
        """
        payload: dict = {"query": query}
        if client_id:
            payload["client_id"] = client_id
        return await _call(
            "/api/v1/autonomous-execution/plans",
            method="POST",
            json=payload,
        )

    @mcp.tool()
    async def execute_plan(plan_id: str) -> dict:
        """
        Execute a plan step by step.

        SAFE steps execute automatically. CRITICAL steps pause for approval.
        IRREVERSIBLE steps require double confirmation.

        Args:
            plan_id: UUID of the execution plan

        Returns:
            Execution status: completed steps, current step, pending approvals.
        """
        return await _call(
            f"/api/v1/autonomous-execution/plans/{plan_id}/execute",
            method="POST",
        )

    @mcp.tool()
    async def get_plan_status(plan_id: str) -> dict:
        """
        Get the current status of an execution plan.

        Args:
            plan_id: UUID of the execution plan

        Returns:
            Plan details: all steps with their statuses, approvals, results, errors.
        """
        return await _call(
            f"/api/v1/autonomous-execution/plans/{plan_id}"
        )

    @mcp.tool()
    async def approve_step(
        plan_id: str,
        step_id: str,
        approved: bool = True,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Approve or reject a CRITICAL/IRREVERSIBLE step in an execution plan.

        Args:
            plan_id: UUID of the plan
            step_id: UUID of the step awaiting approval
            approved: True to approve, False to reject
            notes: Optional notes for the approval/rejection

        Returns:
            Updated step status. If approved, execution continues automatically.
        """
        payload: dict = {"approved": approved}
        if notes:
            payload["notes"] = notes
        return await _call(
            f"/api/v1/autonomous-execution/plans/{plan_id}/steps/{step_id}/approve",
            method="POST",
            json=payload,
        )

    @mcp.tool()
    async def list_plans(
        status: Optional[str] = None, limit: int = 20
    ) -> dict:
        """
        List all execution plans.

        Args:
            status: Filter by status (pending, in_progress, completed, failed, waiting_approval)
            limit: Max results

        Returns:
            List of plans with summary, status, progress percentage.
        """
        params: dict = {"limit": limit}
        if status:
            params["status"] = status
        return await _call(
            "/api/v1/autonomous-execution/plans", params=params
        )

    @mcp.tool()
    async def run_conversation_trainer() -> dict:
        """
        Trigger the Conversation Quality Trainer agent.

        Analyzes recent high-rated conversations, extracts patterns,
        generates improved prompts, and creates a PR with improvements.

        Returns:
            Execution ID, patterns found, improvements generated.
        """
        return await _call(
            "/api/autonomous-agents/conversation-trainer/run",
            method="POST",
        )

    @mcp.tool()
    async def run_client_predictor() -> dict:
        """
        Trigger the Client Value Predictor & Nurturer agent.

        Scores all clients by LTV, identifies VIP and high-risk clients,
        sends personalized nurturing messages via WhatsApp.

        Returns:
            VIP nurtured count, high-risk contacted, total messages sent.
        """
        return await _call(
            "/api/autonomous-agents/client-value-predictor/run",
            method="POST",
        )

    @mcp.tool()
    async def get_agents_status() -> dict:
        """
        Get the status of all autonomous agents.

        Returns:
            Per-agent status: last_run, next_run, success_rate, total_runs, latest_result.
            Agents: conversation_trainer, client_value_predictor, knowledge_graph_builder.
        """
        return await _call("/api/autonomous-agents/status")
