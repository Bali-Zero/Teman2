"""
Lead Assignment Agent - LangGraph Workflow
Automatically assigns new leads to team members and sends Telegram notifications

Author: Claude Sonnet 4.5
Date: 2026-01-18

Flow:
1. Entity Resolution - Check for duplicates (email/phone matching)
2. Lead Assignment - Auto-assign based on specialty + load balancing
3. Telegram Notification - Send notification with inline keyboard buttons
"""

import logging
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    import asyncpg
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class LeadAssignmentState(TypedDict):
    """State for Lead Assignment workflow"""

    # Input
    client_id: int
    client_data: dict  # {email, phone, full_name, practice_type_code}

    # Entity Resolution
    is_duplicate: bool
    matched_client_id: int | None

    # Lead Selection
    assigned_lead: str | None  # team_member.email
    assigned_lead_name: str | None
    assignment_reason: str

    # Notification
    telegram_chat_id: int | None
    notification_sent: bool

    # Output
    success: bool
    errors: list[str]


async def check_duplicates(
    state: LeadAssignmentState, db_pool: "asyncpg.Pool",
) -> LeadAssignmentState:
    """
    Step 1: Entity resolution - check for duplicate clients

    Matches on:
    - Email (exact match, case-insensitive)
    - Phone (normalized match, removes spaces/dashes)
    - Telegram chat_id (via messaging_users.client_id)
    - WhatsApp number (via messaging_users.client_id)
    """
    from backend.services.crm.client_identity_resolver import ClientIdentityResolver

    client_data = state["client_data"]
    client_id = state["client_id"]
    resolver = ClientIdentityResolver(db_pool)

    async with db_pool.acquire() as conn:
        # 1. Check email exact match (case-insensitive)
        if email := client_data.get("email"):
            existing = await conn.fetchrow(
                "SELECT id, assigned_to FROM clients WHERE LOWER(email) = LOWER($1) AND id != $2",
                email,
                client_id,
            )
            if existing:
                state["is_duplicate"] = True
                state["matched_client_id"] = existing["id"]
                state["assigned_lead"] = existing["assigned_to"]
                logger.info(
                    f"🔍 Duplicate detected: client_id={client_id} matches existing client_id={existing['id']} (email)",
                )
                return state

        # 2. Check phone exact match (normalized - remove spaces, dashes, + prefix)
        if phone := client_data.get("phone"):
            phone_clean = phone.replace(" ", "").replace("-", "").lstrip("+")
            existing = await conn.fetchrow(
                """
                SELECT id, assigned_to FROM clients
                WHERE REPLACE(REPLACE(REPLACE(phone, ' ', ''), '-', ''), '+', '') = $1
                AND id != $2
                """,
                phone_clean,
                client_id,
            )
            if existing:
                state["is_duplicate"] = True
                state["matched_client_id"] = existing["id"]
                state["assigned_lead"] = existing["assigned_to"]
                logger.info(
                    f"🔍 Duplicate detected: client_id={client_id} matches existing client_id={existing['id']} (phone)",
                )
                return state

        # 3. Check Telegram cross-channel (if source is telegram)
        if telegram_chat_id := client_data.get("telegram_chat_id"):
            existing_client_id = await resolver.find_client_by_telegram(telegram_chat_id)
            if existing_client_id and existing_client_id != client_id:
                existing = await conn.fetchrow(
                    "SELECT id, assigned_to FROM clients WHERE id = $1",
                    existing_client_id,
                )
                if existing:
                    state["is_duplicate"] = True
                    state["matched_client_id"] = existing["id"]
                    state["assigned_lead"] = existing["assigned_to"]
                    logger.info(
                        f"🔍 Duplicate detected: client_id={client_id} matches existing client_id={existing['id']} (telegram)",
                    )
                    return state

        # 4. Check WhatsApp cross-channel (if source is whatsapp)
        if whatsapp := client_data.get("whatsapp"):
            existing_client_id = await resolver.find_client_by_whatsapp(whatsapp)
            if existing_client_id and existing_client_id != client_id:
                existing = await conn.fetchrow(
                    "SELECT id, assigned_to FROM clients WHERE id = $1",
                    existing_client_id,
                )
                if existing:
                    state["is_duplicate"] = True
                    state["matched_client_id"] = existing["id"]
                    state["assigned_lead"] = existing["assigned_to"]
                    logger.info(
                        f"🔍 Duplicate detected: client_id={client_id} matches existing client_id={existing['id']} (whatsapp)",
                    )
                    return state

    state["is_duplicate"] = False
    state["matched_client_id"] = None
    logger.info(f"✅ No duplicates found for client_id={client_id}")
    return state


# Roles eligible for lead assignment (excludes admin, client, support roles)
ASSIGNABLE_ROLES = {
    "Supervisor",
    "Team Leader",
    "Executive Consultant",
    "Junior Consultant",
    "Specialist Advisor",
    "Advisory",
    "Tax Lead",
    "Tax Care",
    "Tax Manager",
}

# Map practice types to departments for specialty routing
PRACTICE_DEPARTMENT_MAP: dict[str, str] = {
    "kitas": "setup",
    "kitap": "setup",
    "pt_pma": "setup",
    "investor_visa": "setup",
    "work_permit": "setup",
    "company_setup": "setup",
    "visa": "setup",
    "immigration": "setup",
    "tax": "tax",
    "tax_reporting": "tax",
    "tax_registration": "tax",
    "npwp": "tax",
}


async def assign_lead(state: LeadAssignmentState, db_pool: "asyncpg.Pool") -> LeadAssignmentState:
    """
    Step 2: Auto-assign lead to team member

    Strategy:
    1. If duplicate → use existing assignment
    2. Otherwise → department-based matching + load balancing
       - Map practice_type_code to department (setup/tax)
       - Find team members in matching department with least active practices
       - Fallback: any assignable team member with least workload
    """

    if state["is_duplicate"]:
        # Use existing assignment from matched client
        if state["assigned_lead"]:
            state["assignment_reason"] = (
                f"Duplicate client - using existing assignment from client #{state['matched_client_id']}"
            )
            logger.info(f"🔗 Using existing assignment: {state['assigned_lead']}")
            return state

    practice_type_code = state["client_data"].get("practice_type_code", "general")
    target_department = PRACTICE_DEPARTMENT_MAP.get(practice_type_code)

    # Build role filter as SQL-safe tuple
    role_placeholders = ", ".join(f"${i + 1}" for i in range(len(ASSIGNABLE_ROLES)))
    role_list = list(ASSIGNABLE_ROLES)

    async with db_pool.acquire() as conn:
        lead = None

        # Strategy 1: Department matching + load balancing
        if target_department:
            lead = await conn.fetchrow(
                f"""
                SELECT tm.email, tm.full_name, tm.department,
                       COUNT(p.id) as active_practices
                FROM team_members tm
                LEFT JOIN practices p ON p.assigned_to = tm.email
                    AND p.status IN ('inquiry', 'waiting_documents', 'sending_invoice', 'on_process')
                WHERE tm.active = true
                  AND tm.role IN ({role_placeholders})
                  AND LOWER(tm.department) = LOWER(${len(role_list) + 1})
                GROUP BY tm.email, tm.full_name, tm.department
                ORDER BY COUNT(p.id) ASC, RANDOM()
                LIMIT 1
                """,
                *role_list,
                target_department,
            )

        if lead:
            state["assigned_lead"] = lead["email"]
            state["assigned_lead_name"] = lead["full_name"]
            state["assignment_reason"] = (
                f"Department: {lead['department']} (practice: {practice_type_code}), "
                f"Current workload: {lead['active_practices']} practices"
            )

            await conn.execute(
                "UPDATE clients SET assigned_to = $1, updated_at = NOW() WHERE id = $2",
                lead["email"],
                state["client_id"],
            )
            logger.info(
                f"✅ Assigned client #{state['client_id']} to {lead['email']} "
                f"(dept={lead['department']}, workload={lead['active_practices']})",
            )
        else:
            # Fallback: any assignable team member with least workload
            lead = await conn.fetchrow(
                f"""
                SELECT tm.email, tm.full_name, tm.department,
                       COUNT(p.id) as active_practices
                FROM team_members tm
                LEFT JOIN practices p ON p.assigned_to = tm.email
                    AND p.status IN ('inquiry', 'waiting_documents', 'sending_invoice', 'on_process')
                WHERE tm.active = true
                  AND tm.role IN ({role_placeholders})
                GROUP BY tm.email, tm.full_name, tm.department
                ORDER BY COUNT(p.id) ASC, RANDOM()
                LIMIT 1
                """,
                *role_list,
            )
            if lead:
                state["assigned_lead"] = lead["email"]
                state["assigned_lead_name"] = lead["full_name"]
                state["assignment_reason"] = (
                    f"Round-robin (no dept match for {practice_type_code}), "
                    f"Dept: {lead['department']}, Workload: {lead['active_practices']}"
                )
                await conn.execute(
                    "UPDATE clients SET assigned_to = $1, updated_at = NOW() WHERE id = $2",
                    lead["email"],
                    state["client_id"],
                )
                logger.info(
                    f"✅ Assigned (fallback) client #{state['client_id']} to {lead['email']} "
                    f"(dept={lead['department']})",
                )
            else:
                state["errors"].append("No active team members available for assignment")
                logger.warning(
                    f"❌ No team members available to assign client #{state['client_id']}",
                )

    return state


async def send_telegram_notification(
    state: LeadAssignmentState, db_pool: "asyncpg.Pool", telegram_service,
) -> LeadAssignmentState:
    """
    Step 3: Send Telegram notification to assigned lead

    Includes:
    - Client details (name, email, phone, practice type)
    - Assignment reason
    - Inline keyboard with action buttons
    """

    if not state["assigned_lead"]:
        state["errors"].append("No lead assigned - cannot send notification")
        logger.warning(f"⚠️ Cannot notify: no lead assigned for client #{state['client_id']}")
        return state

    # Get Telegram chat_id for this team member
    async with db_pool.acquire() as conn:
        # Query: team_members.email → user_profiles.email → messaging_users.telegram_chat_id
        row = await conn.fetchrow(
            """
            SELECT mu.telegram_chat_id, tm.full_name
            FROM team_members tm
            LEFT JOIN messaging_users mu ON mu.user_id = (
                SELECT id FROM user_profiles WHERE email = tm.email LIMIT 1
            )
            WHERE tm.email = $1
              AND mu.channel = 'telegram'
              AND mu.active = true
            """,
            state["assigned_lead"],
        )

        if not row or not row["telegram_chat_id"]:
            state["errors"].append(f"No Telegram chat_id for {state['assigned_lead']}")
            logger.warning(
                f"⚠️ Cannot notify {state['assigned_lead']}: no Telegram chat_id found. "
                "Team member needs to link Telegram account.",
            )
            state["notification_sent"] = False
            return state

        state["telegram_chat_id"] = row["telegram_chat_id"]

    # Build notification message
    client_data = state["client_data"]
    practice_type_display = (
        client_data.get("practice_type_code", "General inquiry").replace("_", " ").title()
    )

    message = f"""
🆕 *Nuovo Lead Assegnato*

👤 *Cliente:* {client_data.get("full_name", "Unknown")}
📧 *Email:* {client_data.get("email", "N/A")}
📞 *Phone:* {client_data.get("phone", "N/A")}
🎯 *Pratica:* {practice_type_display}

📊 *Assegnazione:* {state["assignment_reason"]}
    """.strip()

    # Inline keyboard with action buttons
    crm_url = f"https://crm.balizero.com/clients/{state['client_id']}"
    inline_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Accetta",
                    "callback_data": f"accept_lead_{state['client_id']}",
                },
                {
                    "text": "➡️ Riassegna",
                    "callback_data": f"reassign_lead_{state['client_id']}",
                },
            ],
            [{"text": "👁️ Vedi Dettagli CRM", "url": crm_url}],
        ],
    }

    try:
        await telegram_service.send_message(
            chat_id=state["telegram_chat_id"],
            text=message,
            parse_mode="Markdown",
            reply_markup=inline_keyboard,
        )
        state["notification_sent"] = True
        logger.info(
            f"📨 Telegram notification sent to {state['assigned_lead']} (chat_id: {state['telegram_chat_id']})",
        )
    except Exception as e:
        state["errors"].append(f"Telegram notification failed: {str(e)}")
        state["notification_sent"] = False
        logger.error(
            f"❌ Failed to send Telegram notification to {state['assigned_lead']}: {e}",
            exc_info=True,
        )

    return state


def create_lead_assignment_workflow(db_pool: "asyncpg.Pool", telegram_service: Any) -> StateGraph:
    """
    Create LangGraph workflow for lead assignment

    Args:
        db_pool: AsyncPG connection pool
        telegram_service: TelegramBotService instance

    Returns:
        Compiled LangGraph StateGraph
    """
    workflow = StateGraph(LeadAssignmentState)

    # Dependency injection wrappers
    async def check_dup_wrapper(state) -> Any:
        return await check_duplicates(state, db_pool)

    async def assign_wrapper(state) -> Any:
        return await assign_lead(state, db_pool)

    async def notify_wrapper(state) -> Any:
        return await send_telegram_notification(state, db_pool, telegram_service)

    # Add nodes
    workflow.add_node("check_duplicates", check_dup_wrapper)
    workflow.add_node("assign_lead", assign_wrapper)
    workflow.add_node("notify_telegram", notify_wrapper)

    # Define flow
    workflow.set_entry_point("check_duplicates")
    workflow.add_edge("check_duplicates", "assign_lead")
    workflow.add_edge("assign_lead", "notify_telegram")
    workflow.add_edge("notify_telegram", END)

    return workflow.compile()


async def trigger_lead_assignment(
    client_id: int,
    client_data: dict,
    db_pool: "asyncpg.Pool",
    telegram_service,
) -> dict:
    """
    Trigger lead assignment workflow for a new client

    Args:
        client_id: ID of newly created client
        client_data: {email, phone, full_name, practice_type_code}
        db_pool: AsyncPG connection pool
        telegram_service: TelegramBotService instance

    Returns:
        Final state dict with success status
    """
    workflow = create_lead_assignment_workflow(db_pool, telegram_service)

    initial_state: LeadAssignmentState = {
        "client_id": client_id,
        "client_data": client_data,
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": None,
        "assigned_lead_name": None,
        "assignment_reason": "",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    try:
        final_state = await workflow.ainvoke(initial_state)

        # Update success based on errors
        final_state["success"] = len(final_state.get("errors", [])) == 0

        logger.info(
            f"🎯 Lead assignment completed for client #{client_id}: "
            f"assigned_to={final_state.get('assigned_lead')}, "
            f"notified={final_state.get('notification_sent')}",
        )

        return final_state

    except Exception as e:
        logger.error(
            f"❌ Lead assignment workflow failed for client #{client_id}: {e}", exc_info=True,
        )
        return {
            "client_id": client_id,
            "success": False,
            "errors": [str(e)],
            "assigned_lead": None,
            "notification_sent": False,
        }
