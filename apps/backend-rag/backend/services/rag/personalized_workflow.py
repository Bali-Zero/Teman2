"""
Personalized Workflow Service

Provides logic to filter and personalize base workflows using CRM data and user memory.
Enables "Smart Step Skipping" and urgency-aware timeline management.

Author: Gemini 3 Pro (Track 3 Specialist)
Date: 2026-02-09
"""

import logging
from datetime import date, datetime, timezone
from typing import Any

from backend.services.crm.enhanced_crm_service import EnhancedCRMService
from backend.services.memory.orchestrator import MemoryOrchestrator

logger = logging.getLogger(__name__)


async def personalize_workflow(
    user_email: str,
    base_workflow: dict[str, Any],
    crm_service: EnhancedCRMService,
    memory_orchestrator: MemoryOrchestrator,
) -> dict[str, Any]:
    """
    Personalizes a base workflow for a specific user.

    Args:
        user_email: User's email address
        base_workflow: The template workflow to personalize
        crm_service: Initialized CRM service
        memory_orchestrator: Initialized Memory orchestrator

    Returns:
        Personalized workflow dictionary
    """
    try:
        # 1. Retrieve User Data from CRM
        # Note: We search by email since client_id might not be known by the caller
        clients, _ = await crm_service.search_clients(user_email, limit=1)
        user_data = clients[0] if clients else {}

        # 2. Retrieve Memory Context
        memory_context = await memory_orchestrator.get_user_context(user_email)
        profile_facts = memory_context.profile_facts or []

        # 3. Identify Completed Steps from Practices
        completed_steps = set()
        if user_data.get("id"):
            client_id = user_data["id"]
            client_full = await crm_service.get_client(client_id, include_practices=True)
            if client_full and "practices" in client_full:
                for practice in client_full["practices"]:
                    if practice["status"] == "completed":
                        completed_steps.add(practice["practice_type_id"])  # Or use practice code

        # 4. Apply Personalization Logic
        personalized_steps = []
        for step in base_workflow.get("steps", []):
            step_id = step.get("step_id")

            # Rule: Skip NPWP registration if user already has it
            if step_id == "npwp_registration":
                has_npwp = user_data.get("custom_fields", {}).get("has_npwp")
                if not has_npwp:
                    # Check memory facts as fallback
                    has_npwp = any("has npwp" in fact.lower() for fact in profile_facts)

                if has_npwp:
                    logger.info(f"⏭️ Skipping step '{step_id}' for {user_email} (Already has NPWP)")
                    continue

            # Rule: Auto-complete 'submit_passport' if passport_number is present
            if step_id == "submit_passport" and user_data.get("passport_number"):
                step["status"] = "completed"
                step["completed_at"] = datetime.now(tz=timezone.utc).isoformat()

            # Rule: Check Retirement Eligibility (Step: retirement_check)
            if step_id == "retirement_check" and user_data.get("date_of_birth"):
                dob = user_data["date_of_birth"]
                if isinstance(dob, str):
                    dob = date.fromisoformat(dob)

                age = (datetime.now(tz=timezone.utc).date() - dob).days // 365
                if age < 55:
                    logger.warning(
                        f"⚠️ User {user_email} is under 55 ({age}), retirement workflow may be invalid",
                    )
                    step["blocked_reason"] = "Age requirement (55+) not met"
                    step["status"] = "blocked"

            # Rule: High Urgency Flag
            is_urgent = any("urgent" in fact.lower() for fact in profile_facts)
            if is_urgent:
                step["priority"] = "urgent"
                # Compress duration by 20%
                original_duration = step.get("estimated_duration_days", 0)
                step["estimated_duration_days"] = max(1, int(original_duration * 0.8))

            personalized_steps.append(step)

        # 5. Build Final Workflow Object
        personalized_workflow = base_workflow.copy()
        personalized_workflow["steps"] = personalized_steps
        personalized_workflow["is_personalized"] = True
        personalized_workflow["personalized_at"] = datetime.now(tz=timezone.utc).isoformat()

        logger.info(f"✅ Workflow '{base_workflow.get('name')}' personalized for {user_email}")
        return personalized_workflow

    except Exception as e:
        logger.error(f"❌ Failed to personalize workflow for {user_email}: {e}")
        # Return base workflow as safe fallback
        return base_workflow
