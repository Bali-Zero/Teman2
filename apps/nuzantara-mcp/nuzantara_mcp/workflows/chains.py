"""
Deterministic Workflow Chains - 8 autopilot workflows.

Each chain is a sequence of tool calls with IF/THEN/ELSE branching.
NO LLM decisions — pure deterministic logic.

NLM Grounding: Chains can optionally query NotebookLM for operational
context (historical patterns, business intelligence). This enriches
reports with data-driven insights instead of raw numbers only.
"""

import asyncio
import logging
import os
import subprocess
import json as _json_mod
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("nuzantara-mcp.chains")

# --- NLM Grounding Configuration ---
_NLM_CLI = "nlm"
_NB_OPS_ID = os.environ.get("NB_OPS_ID", "")
_NB_INTEL_ID = os.environ.get("NB_INTEL_ID", "")
_NB_TELEMETRY_ID = os.environ.get("NB_TELEMETRY_ID", "")


async def _nlm_grounding(notebook_id: str, question: str, timeout: int = 60) -> str:
    """Query NLM for operational grounding — non-blocking, best-effort.

    Returns the answer string, or empty string on any failure.
    Used by chains to enrich reports with historical context.
    """
    if not notebook_id:
        return ""
    try:
        cmd = [_NLM_CLI, "query", "notebook", notebook_id, question, "--timeout", str(timeout)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 15)
        if proc.returncode != 0:
            logger.debug("NLM grounding query failed: %s", stderr.decode().strip()[:200])
            return ""
        data = _json_mod.loads(stdout.decode().strip())
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]
        return data.get("answer", "")
    except asyncio.TimeoutError:
        logger.debug("NLM grounding timed out for: %s", question[:60])
        return ""
    except Exception:
        logger.debug("NLM grounding unavailable", exc_info=True)
        return ""


async def _reflect_and_save(
    _call_safe: Callable,
    chain_name: str,
    summary: str,
    outcome: str,
    log: list,
) -> None:
    """
    Post-chain reflection: save an episodic memory of what just happened.
    Called at the end of every chain to build the LAM's long-term memory.
    """
    try:
        errors = [s.get("detail") for s in log if s.get("status") == "error"]
        content = (
            f"Chain '{chain_name}' completed. {summary}. "
            f"Steps: {len(log)}. Errors: {errors if errors else 'none'}."
        )
        await _call_safe(
            "/api/memory/lam/episodes",
            method="POST",
            json={
                "content": content,
                "agent": "chains",
                "tags": [chain_name, "chain_reflection"],
                "outcome": outcome,
                "metadata": {"chain": chain_name, "steps": len(log), "errors": errors},
            },
        )
        logger.debug(f"Reflection saved for chain '{chain_name}'")
    except Exception as e:
        logger.warning(f"Reflection save failed for '{chain_name}': {e}")


def register(mcp, _call: Callable, _call_safe: Callable, long_timeout: int):
    # =========================================================================
    # CHAIN 1: Daily Ops Autopilot
    # =========================================================================

    @mcp.tool()
    async def chain_daily_ops_autopilot(
        send_report_to: str = "zero@balizero.com",
    ) -> dict:
        """
        AUTOPILOT: Run the full daily operations workflow.

        Deterministic chain that runs every morning:
        1. Check expiry alerts → send WhatsApp reminders for <30 days
        2. Check autonomous agent health → restart stale agents
        3. Check critical intel alerts → auto-compose articles for high-impact items
        4. Gather team hours and completion rates
        5. Compile and email daily report

        Args:
            send_report_to: Email address for the daily report

        Returns:
            Full execution log: each step's result, actions taken, errors encountered.
        """
        log: list[dict[str, Any]] = []
        report: dict[str, Any] = {"date": datetime.now(timezone.utc).isoformat()}

        # Step 1: Expiry alerts
        try:
            alerts = await _call_safe("/api/crm/expiry-alerts", params={"days_ahead": 90})
            # alerts may be a list directly or a dict with "alerts"/"data" key
            alerts_list = alerts if isinstance(alerts, list) else (alerts.get("alerts") or alerts.get("data") or [])
            urgent = [a for a in alerts_list if isinstance(a, dict) and a.get("days_remaining", 999) < 30]
            reminders_sent = 0
            for alert in urgent[:10]:  # Cap at 10 reminders per run
                phone = alert.get("client_phone") or alert.get("phone")
                client_id = alert.get("client_id")
                if phone:
                    msg = f"Reminder: Your {alert.get('document_type', 'document')} expires in {alert.get('days_remaining')} days. Please contact Bali Zero for renewal."
                    await _call_safe("/api/whatsapp/send", method="POST", json={"phone": phone, "message": msg})
                    reminders_sent += 1
                if client_id:
                    await _call_safe("/api/crm/interactions", method="POST", json={
                        "client_id": client_id, "type": "system",
                        "summary": f"Auto-sent expiry reminder ({alert.get('days_remaining')}d remaining)",
                        "channel": "whatsapp",
                    })
            report["expiry_alerts"] = {"total": len(alerts_list), "urgent": len(urgent), "reminders_sent": reminders_sent}
            log.append({"step": "expiry_alerts", "status": "ok", "reminders_sent": reminders_sent})
        except Exception as e:
            log.append({"step": "expiry_alerts", "status": "error", "detail": str(e)})

        # Step 2: Agent health check
        try:
            agents = await _call_safe("/api/autonomous-agents/status")
            stale_agents = []
            # agents may be a list or a dict with "agents"/"data" key
            agents_dict = agents if isinstance(agents, dict) else {}
            agents_map = agents_dict.get("agents") or agents_dict.get("data") or {}
            if isinstance(agents_map, dict):
                for name, info in agents_map.items():
                    if isinstance(info, dict) and info.get("status") == "error":
                        stale_agents.append(name)
            elif isinstance(agents_map, list):
                for item in agents_map:
                    if isinstance(item, dict) and item.get("status") == "error":
                        stale_agents.append(item.get("name", "unknown"))
            report["agents"] = {"total": len(agents_map), "stale": stale_agents}
            log.append({"step": "agent_health", "status": "ok", "stale_agents": stale_agents})
        except Exception as e:
            log.append({"step": "agent_health", "status": "error", "detail": str(e)})

        # Step 3: Critical intel alerts
        try:
            intel = await _call_safe("/api/intel/critical")
            critical_items = intel.get("alerts") or intel.get("data") or []
            articles_composed = 0
            for item in critical_items[:3]:  # Max 3 auto-articles per day
                if isinstance(item, dict) and item.get("severity") == "high":
                    await _call_safe("/api/article-composer/compose", method="POST", json={
                        "topic": item.get("title", "Regulatory Update"),
                        "style": "alert",
                        "target_length": "short",
                    })
                    articles_composed += 1
            report["intel"] = {"critical_alerts": len(critical_items), "articles_composed": articles_composed}
            log.append({"step": "intel_alerts", "status": "ok", "articles_composed": articles_composed})
        except Exception as e:
            log.append({"step": "intel_alerts", "status": "error", "detail": str(e)})

        # Step 4: Team and completion metrics
        try:
            hours_data = await _call_safe("/api/team/activity/weekly")
            completion_data = await _call_safe("/api/analytics/completion-rates", params={"period": "7d"})
            report["team_hours"] = hours_data
            report["completion_rates"] = completion_data
            log.append({"step": "metrics", "status": "ok"})
        except Exception as e:
            log.append({"step": "metrics", "status": "error", "detail": str(e)})

        # Step 5: NLM grounding — enrich report with operational context
        nlm_context = ""
        try:
            urgent_count = report.get("expiry_alerts", {}).get("urgent", 0)
            if _NB_OPS_ID and urgent_count > 0:
                nlm_context = await _nlm_grounding(
                    _NB_OPS_ID,
                    f"There are {urgent_count} urgent expiry alerts today. "
                    "Are there recurring patterns? Which client segments are most affected?",
                )
            if nlm_context:
                report["nlm_ops_context"] = nlm_context
                log.append({"step": "nlm_grounding", "status": "ok", "answer_len": len(nlm_context)})
            else:
                log.append({"step": "nlm_grounding", "status": "skipped", "detail": "no NB_OPS_ID or no urgent alerts"})
        except Exception as e:
            log.append({"step": "nlm_grounding", "status": "error", "detail": str(e)})

        # Step 6: Send daily report email
        try:
            summary_lines = [
                f"Daily Ops Report — {report['date'][:10]}",
                "",
                f"Expiry Alerts: {report.get('expiry_alerts', {}).get('urgent', 'N/A')} urgent, {report.get('expiry_alerts', {}).get('reminders_sent', 0)} reminders sent",
                f"Agent Health: {report.get('agents', {}).get('stale', [])} stale",
                f"Intel: {report.get('intel', {}).get('critical_alerts', 0)} critical, {report.get('intel', {}).get('articles_composed', 0)} articles auto-composed",
            ]
            if nlm_context:
                summary_lines.extend(["", "## Operational Insights (NLM)", nlm_context])
            await _call_safe("/api/zoho/emails", method="POST", json={
                "to": send_report_to,
                "subject": f"[Nuzantara] Daily Ops Report {report['date'][:10]}",
                "body": "\n".join(summary_lines),
            })
            log.append({"step": "send_report", "status": "ok"})
        except Exception as e:
            log.append({"step": "send_report", "status": "error", "detail": str(e)})

        result = {"chain": "daily_ops_autopilot", "report": report, "log": log}
        await _reflect_and_save(_call_safe, "daily_ops_autopilot",
            f"Reminders={report.get('expiry_alerts',{}).get('reminders_sent',0)}, "
            f"Articles={report.get('intel',{}).get('articles_composed',0)}",
            "success" if not any(s.get("status") == "error" for s in log) else "partial",
            log)
        return result

    # =========================================================================
    # CHAIN 2: New Client Onboarding
    # =========================================================================

    @mcp.tool()
    async def chain_new_client_onboarding(
        name: str,
        email: str,
        nationality: str,
        business_description: str,
        phone: Optional[str] = None,
    ) -> dict:
        """
        AUTOPILOT: Complete new client onboarding in one shot.

        Deterministic chain:
        1. Create client in CRM
        2. Search matching KBLI codes for their business
        3. Determine recommended visa type based on nationality + business
        4. Create Google Drive folder structure
        5. Create initial practice
        6. Generate execution plan
        7. Send welcome message via portal + email + WhatsApp
        8. Log all interactions

        Args:
            name: Client's full legal name
            email: Client's email
            nationality: Client's nationality (e.g. "Italian", "Australian")
            business_description: What their business does (for KBLI matching)
            phone: WhatsApp number with country code

        Returns:
            Onboarding result: client_id, kbli_matches, visa_recommendation, practice_id, plan_id.
        """
        log: list[dict] = []
        result: dict[str, Any] = {}

        # Step 1: Create client
        try:
            client = await _call("/api/crm/clients", method="POST", json={
                "name": name, "email": email, "nationality": nationality,
                "phone": phone or "", "notes": f"Business: {business_description}",
            })
            client_id = client.get("id") or client.get("client_id")
            result["client_id"] = client_id
            log.append({"step": "create_client", "status": "ok", "client_id": client_id})
        except Exception as e:
            return {"chain": "new_client_onboarding", "error": f"Failed to create client: {e}", "log": log}

        # Step 2: KBLI search
        try:
            kbli = await _call_safe("/api/v1/kbli-notebook/search", params={"query": business_description, "limit": 5})
            result["kbli_matches"] = kbli.get("results") or kbli.get("data") or []
            log.append({"step": "kbli_search", "status": "ok", "matches": len(result["kbli_matches"])})
        except Exception as e:
            log.append({"step": "kbli_search", "status": "error", "detail": str(e)})

        # Step 2b: Zone check reale (Prime Nexus integration)
        _BALI_VILLAGES = {
            "canggu": (-8.648, 115.132), "seminyak": (-8.692, 115.168),
            "ubud": (-8.519, 115.263), "kuta": (-8.719, 115.167),
            "sanur": (-8.700, 115.261), "jimbaran": (-8.783, 115.172),
            "nusa dua": (-8.800, 115.231), "legian": (-8.706, 115.162),
            "petitenget": (-8.668, 115.157), "umalas": (-8.661, 115.148),
            "berawa": (-8.645, 115.131), "pererenan": (-8.632, 115.117),
            "denpasar": (-8.670, 115.212), "bukit": (-8.818, 115.108),
            "uluwatu": (-8.829, 115.085), "batu belig": (-8.659, 115.145),
        }
        try:
            lat: float | None = None
            lng: float | None = None
            desc_lower = business_description.lower()
            # Pattern: "at lat X lng Y"
            import re as _re
            coord_match = _re.search(r"at\s+lat\s+([-\d.]+)\s+lng\s+([-\d.]+)", desc_lower)
            if coord_match:
                lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
            else:
                # Ricerca villaggio noto nella descrizione
                for village, (vlat, vlng) in _BALI_VILLAGES.items():
                    if village in desc_lower:
                        lat, lng = vlat, vlng
                        break
            if lat is not None and lng is not None and result.get("kbli_matches"):
                top_kbli = result["kbli_matches"][0].get("code", "") if result["kbli_matches"] else ""
                zone_res = await _call_safe("/api/prime/v2/analyze", method="POST",
                                           json={"lat": lat, "lng": lng, "kbli_code": top_kbli, "is_pma": True})
                zone_code = zone_res.get("zone_code") or zone_res.get("zone", {}).get("code", "unknown")
                verdict = zone_res.get("verdict") or zone_res.get("zone", {}).get("verdict", "UNKNOWN")
                result["zone_analysis"] = {"zone_code": zone_code, "verdict": verdict, "lat": lat, "lng": lng}
                log.append({"step": "zone_check", "status": "ok",
                           "zone_code": zone_code, "verdict": verdict})
            else:
                log.append({"step": "zone_check", "status": "skipped",
                           "detail": "No coordinates or village found in description"})
        except Exception as e:
            log.append({"step": "zone_check", "status": "skipped", "detail": str(e)})

        # Step 3: Determine visa (intelligent pricing-based recommendation)
        visa_type = "kitas_investor"  # default fallback
        nat_lower = nationality.lower()

        # Indonesian citizens don't need visa
        if nat_lower in ("indonesian", "indonesia", "wni"):
            visa_type = "none"
        else:
            # Use PricingTool to intelligently determine visa type based on business description
            try:
                pricing_query = f"visa recommendation for {nationality} national doing: {business_description}"
                pricing_result = await _call_safe(
                    "/api/agents/pricing/calculate",
                    method="POST",
                    json={"service_type": "visa", "query": pricing_query}
                )

                # Parse pricing result to extract recommended visa type
                # The pricing service will return relevant visa options
                if isinstance(pricing_result, dict) and not pricing_result.get("error"):
                    # Priority order based on business context
                    if "retirement" in business_description.lower() or "retire" in business_description.lower():
                        visa_type = "kitas_retirement"
                    elif "student" in business_description.lower() or "study" in business_description.lower():
                        visa_type = "kitas_student"
                    elif "work" in business_description.lower() or "employee" in business_description.lower():
                        visa_type = "kitas_work"
                    elif "business" in business_description.lower() or "company" in business_description.lower() or "investor" in business_description.lower():
                        visa_type = "kitas_investor"
                    # else: keep default kitas_investor

                    log.append({"step": "visa_determination", "status": "ok", "visa": visa_type, "pricing_consulted": True})
                else:
                    # Fallback to simple keyword matching if pricing fails
                    if "student" in business_description.lower():
                        visa_type = "kitas_student"
                    elif "retire" in business_description.lower():
                        visa_type = "kitas_retirement"
                    elif "work" in business_description.lower() or "employee" in business_description.lower():
                        visa_type = "kitas_work"
                    log.append({"step": "visa_determination", "status": "ok", "visa": visa_type, "pricing_consulted": False, "fallback": True})
            except Exception as e:
                # Fallback to keyword matching on error
                if "student" in business_description.lower():
                    visa_type = "kitas_student"
                elif "retire" in business_description.lower():
                    visa_type = "kitas_retirement"
                elif "work" in business_description.lower() or "employee" in business_description.lower():
                    visa_type = "kitas_work"
                log.append({"step": "visa_determination", "status": "error", "detail": str(e), "visa": visa_type, "fallback": True})

        result["recommended_visa"] = visa_type

        # Step 4: Create Drive folder
        try:
            folder = await _call_safe(f"/api/crm/drive-folders/{client_id}", method="POST")
            result["drive_folder"] = folder.get("folder_id") or folder.get("id")
            log.append({"step": "drive_folder", "status": "ok"})
        except Exception as e:
            log.append({"step": "drive_folder", "status": "error", "detail": str(e)})

        # Step 5: Create practice
        if visa_type != "none":
            try:
                practice = await _call("/api/crm/practices", method="POST", json={
                    "client_id": client_id, "type": visa_type,
                    "notes": f"Auto-created during onboarding. KBLI: {[m.get('code') for m in result.get('kbli_matches', [])[:3]]}",
                })
                result["practice_id"] = practice.get("id") or practice.get("practice_id")
                log.append({"step": "create_practice", "status": "ok"})
            except Exception as e:
                log.append({"step": "create_practice", "status": "error", "detail": str(e)})

        # Step 6: Generate execution plan
        try:
            plan = await _call_safe("/api/v1/autonomous-execution/plans", method="POST", json={
                "query": f"Setup {visa_type} for {nationality} client doing {business_description}",
                "client_id": client_id,
            })
            result["plan_id"] = plan.get("plan_id") or plan.get("id")
            log.append({"step": "execution_plan", "status": "ok"})
        except Exception as e:
            log.append({"step": "execution_plan", "status": "error", "detail": str(e)})

        # Step 7: Send welcome messages
        welcome_msg = f"Welcome to Bali Zero, {name}! Your onboarding is complete. Check your portal for next steps."
        try:
            await _call_safe("/api/portal/messages", method="POST", json={
                "client_id": client_id, "subject": "Welcome to Bali Zero!", "body": welcome_msg,
            })
            log.append({"step": "portal_message", "status": "ok"})
        except Exception as e:
            log.append({"step": "portal_message", "status": "error", "detail": str(e)})

        try:
            await _call_safe("/api/zoho/emails", method="POST", json={
                "to": email, "subject": "Welcome to Bali Zero!", "body": welcome_msg,
            })
            log.append({"step": "welcome_email", "status": "ok"})
        except Exception as e:
            log.append({"step": "welcome_email", "status": "error", "detail": str(e)})

        if phone:
            try:
                await _call_safe("/api/whatsapp/send", method="POST", json={"phone": phone, "message": welcome_msg})
                log.append({"step": "whatsapp", "status": "ok"})
            except Exception as e:
                log.append({"step": "whatsapp", "status": "error", "detail": str(e)})

        # Step 8: Log interaction
        try:
            await _call_safe("/api/crm/interactions", method="POST", json={
                "client_id": client_id, "type": "system",
                "summary": "Automated onboarding completed", "channel": "internal",
            })
        except Exception:
            pass

        res = {"chain": "new_client_onboarding", "result": result, "log": log}
        await _reflect_and_save(_call_safe, "new_client_onboarding",
            f"Client={name}, email={email}, visa={result.get('recommended_visa','?')}",
            "success" if not any(s.get("status") == "error" for s in log) else "partial",
            log)
        return res

    # =========================================================================
    # CHAIN 3: Practice Lifecycle Manager
    # =========================================================================

    @mcp.tool()
    async def chain_practice_lifecycle_check() -> dict:
        """
        AUTOPILOT: Check all active practices and take action.

        Deterministic chain that runs every 6 hours:
        1. List all active practices
        2. For visa practices expiring within 90 days → create renewal, notify client
        3. For practices waiting documents >7 days → send reminder
        4. For submitted practices >14 days → escalate
        5. Check overall completion rates → alert if below 80%

        Returns:
            Actions taken: renewals created, reminders sent, escalations flagged.
        """
        log: list[dict] = []
        stats = {
            "renewals_created": 0,
            "reminders_sent": 0,
            "escalations": 0,
            "expiring_soon": 0,       # practices with expiry_date within 90 days
            "blocked": 0,             # practices past expected_completion_date and still open
        }

        try:
            # Fetching all practices (limit 500) to ensure we check completed/active ones that need renewal
            practices_resp = await _call_safe("/api/crm/practices", params={"limit": 500})
            practices = practices_resp.get("practices") or practices_resp.get("data") or []
        except Exception as e:
            return {"chain": "practice_lifecycle", "error": str(e)}

        from datetime import date as _date
        today = _date.today()

        for p in practices:
            if not isinstance(p, dict):
                continue
            p_id = p.get("id") or p.get("practice_id")
            client_id = p.get("client_id")
            p_type = p.get("practice_type_code") or p.get("type", "")
            status = p.get("status", "")
            days_in_status = p.get("days_in_current_status", 0)

            # Calculate days_to_expiry from expiry_date field (DB backfilled)
            days_to_expiry = None
            expiry_raw = p.get("expiry_date")
            if expiry_raw:
                try:
                    if isinstance(expiry_raw, str):
                        from datetime import datetime as _dt
                        expiry_d = _dt.strptime(expiry_raw[:10], "%Y-%m-%d").date()
                    else:
                        expiry_d = expiry_raw
                    days_to_expiry = (expiry_d - today).days
                except Exception:
                    pass

            # Calculate days past expected_completion_date (DB backfilled via backfill_practice_dates.py)
            days_past_expected = None
            expected_raw = p.get("expected_completion_date")
            if expected_raw and status not in ("completed", "archived", "cancelled"):
                try:
                    if isinstance(expected_raw, str):
                        from datetime import datetime as _dt
                        expected_d = _dt.strptime(expected_raw[:10], "%Y-%m-%d").date()
                    else:
                        expected_d = expected_raw
                    overdue = (today - expected_d).days
                    if overdue > 0:
                        days_past_expected = overdue
                except Exception:
                    pass

            # Calculate days_in_status from updated_at if not provided
            if not days_in_status:
                updated_raw = p.get("updated_at")
                if updated_raw:
                    try:
                        from datetime import datetime as _dt
                        updated_d = _dt.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
                        days_in_status = (today - updated_d.date()).days
                    except Exception:
                        days_in_status = 0

            # Rule 1: Practice expiring within 90 days
            if days_to_expiry is not None and days_to_expiry < 90:
                stats["expiring_soon"] += 1
                try:
                    await _call_safe(f"/api/crm/practices/{p_id}", method="PATCH", json={
                        "status": "renewal_needed", "notes": f"Auto-flagged: {days_to_expiry} days to expiry",
                    })
                    if client_id:
                        await _call_safe("/api/portal/messages", method="POST", json={
                            "client_id": client_id,
                            "subject": "Visa Renewal Notice",
                            "body": f"Your {p_type} expires in {days_to_expiry} days. Please prepare documents for renewal.",
                        })
                    stats["renewals_created"] += 1
                except Exception:
                    pass

            # Rule 1b: Practice blocked — past expected_completion_date and still open
            if days_past_expected is not None:
                stats["blocked"] += 1
                log.append({
                    "step": "blocked_practice",
                    "status": "warning",
                    "practice_id": p_id,
                    "type": p_type,
                    "days_overdue": days_past_expected,
                    "current_status": status,
                })

            # Rule 2: Waiting documents > 7 days
            elif status == "waiting_documents" and days_in_status > 7:
                phone = p.get("client_phone")
                if phone:
                    try:
                        await _call_safe("/api/whatsapp/send", method="POST", json={
                            "phone": phone,
                            "message": f"Hi! We're still waiting for documents for your {p_type} practice. Could you please send them at your earliest convenience?",
                        })
                        stats["reminders_sent"] += 1
                    except Exception:
                        pass

            # Rule 3: Submitted > 14 days — escalate via email to team lead
            elif status == "submitted" and days_in_status > 14:
                stats["escalations"] += 1
                team_lead = p.get("assigned_to")
                if team_lead:
                    try:
                        await _call_safe("/api/zoho/emails", method="POST", json={
                            "to": team_lead,
                            "subject": f"[ESCALATION] Practice #{p_id} submitted {days_in_status} days ago — no update",
                            "body": (
                                f"Practice <strong>#{p_id}</strong> ({p_type}) has been in "
                                f"<em>submitted</em> status for <strong>{days_in_status} days</strong> "
                                f"with no status change.<br><br>"
                                f"Please check with the relevant authority and update the CRM:<br>"
                                f"<a href=\"https://kita.balizero.com/process/{p_id}\">Open practice #{p_id}</a>"
                            ),
                        })
                    except Exception:
                        pass

        # Check completion rates
        try:
            rates = await _call_safe("/api/analytics/completion-rates", params={"period": "30d"})
            monthly_rate = rates.get("completion_rate") or rates.get("overall", 100)
            if isinstance(monthly_rate, (int, float)) and monthly_rate < 80:
                stats["completion_alert"] = f"Warning: {monthly_rate}% completion rate (below 80%)"
        except Exception:
            pass

        log.append({"step": "lifecycle_check", "status": "ok", "practices_checked": len(practices)})
        res = {"chain": "practice_lifecycle", "stats": stats, "log": log}
        await _reflect_and_save(_call_safe, "practice_lifecycle",
            (
                f"Checked={len(practices)}, expiring_soon={stats.get('expiring_soon', 0)}, "
                f"blocked={stats.get('blocked', 0)}, renewals={stats.get('renewals_created', 0)}, "
                f"reminders={stats.get('reminders_sent', 0)}, escalations={stats.get('escalations', 0)}"
            ),
            "success", log)
        return res

    # =========================================================================
    # CHAIN 4: Intel Pipeline Autopilot
    # =========================================================================

    @mcp.tool()
    async def chain_intel_pipeline(
        sources: Optional[list[str]] = None,
    ) -> dict:
        """
        AUTOPILOT: Run the full intelligence pipeline.

        Deterministic chain:
        1. Submit scraper jobs for regulatory sources
        2. Wait for processing
        3. Review staging items using RAG assessment
        4. Auto-approve high-confidence items
        5. Auto-compose articles for high-impact regulatory changes
        6. Report metrics

        Args:
            sources: Custom source list (default: standard Indonesian gov sources)

        Returns:
            Pipeline results: items scraped, assessed, approved, published.
        """
        if sources is None:
            sources = ["kemenkumham", "pajak.go.id", "oss.go.id"]

        log: list[dict] = []
        stats: dict[str, Any] = {"items_reviewed": 0, "auto_approved": 0, "flagged": 0, "archived": 0}

        # Step 1: Submit scraper job
        try:
            job = await _call_safe("/api/intel/scraper/submit", method="POST", json={"sources": sources})
            log.append({"step": "submit_scraper", "status": "ok", "job": job})
        except Exception as e:
            log.append({"step": "submit_scraper", "status": "error", "detail": str(e)})

        # Step 2: Wait for processing (10 seconds for MCP, actual scraping is async in backend)
        await asyncio.sleep(10)

        # Step 3: Review staging items
        try:
            staging = await _call_safe("/api/intel/staging/pending", params={"limit": 20})
            items = staging.get("items") or staging.get("data") or []
            stats["items_reviewed"] = len(items)

            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("id") or item.get("item_id")
                title = item.get("title", "Unknown")

                # Step 4: Assess relevance via lightweight Gemini call (NOT full RAG)
                # Previous: called /api/agentic-rag/query costing ~$0.02/article (35K tok prompt)
                # Now: direct Gemini API call with ~500 token prompt ($0.0001/article)
                try:
                    import os as _os
                    _gemini_key = _os.environ.get("GOOGLE_API_KEY") or _os.environ.get("GOOGLEAISTUDIO_API_KEY", "")
                    if _gemini_key:
                        import urllib.request as _ur, json as _json2
                        _prompt = (
                            f"Is this news article significant for foreign investors or expats in Bali, Indonesia?\n"
                            f"Title: {title}\n\n"
                            f"Reply ONLY with a JSON object: {{\"significant\": true/false, \"confidence\": 0.0-1.0, \"reason\": \"one sentence\"}}"
                        )
                        _req = _ur.Request(
                            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={_gemini_key}",
                            data=_json2.dumps({"contents": [{"parts": [{"text": _prompt}]}]}).encode(),
                            headers={"Content-Type": "application/json"},
                        )
                        _resp = _ur.urlopen(_req, timeout=15)
                        _data = _json2.loads(_resp.read())
                        _text = _data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        # Parse JSON from response
                        _text_clean = _text.strip().strip("`").strip()
                        if _text_clean.startswith("json"):
                            _text_clean = _text_clean[4:].strip()
                        _result = _json2.loads(_text_clean)
                        confidence = float(_result.get("confidence", 0))
                        is_significant = _result.get("significant", False)
                    else:
                        # Fallback to RAG if no Gemini key (shouldn't happen)
                        assessment = await _call_safe("/api/agentic-rag/query", method="POST", json={
                            "query": f"Is this regulation change significant for foreign investors in Bali? Title: {title}",
                            "user_id": "autopilot",
                        }, timeout=long_timeout)
                        confidence = assessment.get("confidence", 0)
                        answer = str(assessment.get("answer", "")).lower()
                        is_significant = confidence > 0.6 and ("significant" in answer or "important" in answer or "yes" in answer)

                    if is_significant and confidence > 0.6:
                        # Auto-approve and compose article
                        await _call_safe(f"/api/intel/staging/approve/{item_id}", method="POST")
                        await _call_safe("/api/article-composer/compose", method="POST", json={
                            "topic": title, "style": "alert", "target_length": "short",
                        })
                        stats["auto_approved"] += 1
                    elif confidence > 0.4:
                        stats["flagged"] += 1  # Leave for manual review
                    else:
                        stats["archived"] += 1
                except Exception:
                    stats["flagged"] += 1  # If assessment fails, flag for manual review

            log.append({"step": "review_staging", "status": "ok"})
        except Exception as e:
            log.append({"step": "review_staging", "status": "error", "detail": str(e)})

        # Step 5: Get metrics
        try:
            metrics = await _call_safe("/api/intel/metrics")
            stats["pipeline_metrics"] = metrics
        except Exception:
            pass

        res = {"chain": "intel_pipeline", "stats": stats, "log": log}
        await _reflect_and_save(_call_safe, "intel_pipeline",
            f"Scraped={stats.get('scraped',0)}, approved={stats.get('approved',0)}, published={stats.get('published',0)}",
            "success" if not any(s.get("status") == "error" for s in log) else "partial",
            log)
        return res

    # =========================================================================
    # CHAIN 5: Weekly Report Generator
    # =========================================================================

    @mcp.tool()
    async def chain_weekly_report(
        send_to: str = "zero@balizero.com",
    ) -> dict:
        """
        AUTOPILOT: Generate and send the weekly operations report.

        Gathers data from all systems and compiles a comprehensive report:
        1. CRM stats (clients, practices, completions)
        2. Revenue analytics
        3. Team productivity and burnout indicators
        4. Intelligence trends
        5. RAG system performance
        6. Sends compiled report via email

        Args:
            send_to: Email address for the report

        Returns:
            Complete weekly report data.
        """
        report: dict[str, Any] = {"week_of": datetime.now(timezone.utc).isoformat()[:10]}

        # Gather all data in parallel-ish (sequential for safety)
        sections = {
            "client_stats": ("/api/crm/clients/stats", {}),
            "completion_rates": ("/api/analytics/completion-rates", {"period": "7d"}),
            "revenue": ("/api/analytics/revenue", {"period": "7d"}),
            "response_times": ("/api/analytics/response-times", {"period": "7d"}),
            "sla_compliance": ("/api/analytics/sla-compliance", {"period": "7d"}),
            "query_analytics": ("/api/query-analytics/volume", {"period": "7d"}),
            "team_productivity": ("/api/team-analytics/productivity", {"period": "7d"}),
            "burnout": ("/api/team-analytics/burnout", {}),
            "intel_trends": ("/api/intel/trends", {"period": "7d"}),
            "agents_status": ("/api/autonomous-agents/status", {}),
        }

        for key, (endpoint, params) in sections.items():
            try:
                data = await _call_safe(endpoint, params=params if params else None)
                report[key] = data
            except Exception as e:
                report[key] = {"error": str(e)}

        # Compile summary
        summary_lines = [
            f"# Nuzantara Weekly Report — {report['week_of']}",
            "",
            "## Key Metrics",
        ]

        # Extract key numbers safely
        cs = report.get("client_stats", {})
        cr = report.get("completion_rates", {})
        rev = report.get("revenue", {})

        summary_lines.extend([
            f"- Total Clients: {cs.get('total', 'N/A')}",
            f"- Active Practices: {cs.get('active_practices', 'N/A')}",
            f"- Completion Rate: {cr.get('completion_rate', cr.get('overall', 'N/A'))}%",
            f"- Weekly Revenue: {rev.get('total', rev.get('weekly_total', 'N/A'))}",
            "",
            "## Alerts",
        ])

        burnout = report.get("burnout", {})
        if isinstance(burnout, dict) and burnout.get("at_risk"):
            summary_lines.append(f"⚠ Burnout risk detected: {burnout['at_risk']}")

        intel = report.get("intel_trends", {})
        if isinstance(intel, dict) and intel.get("high_activity_areas"):
            summary_lines.append(f"📋 High regulatory activity: {intel['high_activity_areas']}")

        # NLM grounding — business intelligence context
        nlm_intel = ""
        if _NB_INTEL_ID:
            nlm_intel = await _nlm_grounding(
                _NB_INTEL_ID,
                "Summarize this week's business performance: revenue trends, "
                "top performing services, client acquisition rate, and any anomalies "
                "compared to previous weeks.",
            )
        if nlm_intel:
            summary_lines.extend(["", "## Business Intelligence (NLM)", nlm_intel])
            report["nlm_intel_context"] = nlm_intel

        # Send email
        try:
            await _call_safe("/api/zoho/emails", method="POST", json={
                "to": send_to,
                "subject": f"[Nuzantara] Weekly Report — {report['week_of']}",
                "body": "\n".join(summary_lines),
            })
        except Exception:
            pass

        log: list[dict] = [{"step": "gather_data", "status": "ok"}, {"step": "nlm_grounding", "status": "ok" if nlm_intel else "skipped"}]
        res = {"chain": "weekly_report", "report": report, "log": log}
        await _reflect_and_save(_call_safe, "weekly_report",
            f"Week={report.get('week_of','?')}, sent to {send_to}, nlm={'yes' if nlm_intel else 'no'}",
            "success", log)
        return res

    # =========================================================================
    # CHAIN 6: Client Health Monitor
    # =========================================================================

    @mcp.tool()
    async def chain_client_health_monitor() -> dict:
        """
        AUTOPILOT: Monitor client health and take proactive action.

        Deterministic chain:
        1. Run client value predictor to score all clients
        2. For high-risk clients (inactive >30 days) → send re-engagement message
        3. For clients with stalled practices → send portal update request
        4. For VIP clients with upcoming birthdays → queue birthday greeting
        5. For recently completed practices → send satisfaction survey

        Returns:
            Actions taken: re-engagements, reminders, greetings, surveys sent.
        """
        log: list[dict] = []
        stats = {"re_engagements": 0, "stalled_reminders": 0, "birthday_greetings": 0, "surveys_sent": 0}

        # Step 1: Run predictor
        try:
            prediction = await _call_safe("/api/autonomous-agents/client-value-predictor/run", method="POST")
            log.append({"step": "predictor", "status": "ok", "result": prediction})
        except Exception as e:
            log.append({"step": "predictor", "status": "error", "detail": str(e)})

        # Step 2: Get all clients and check health
        try:
            clients_resp = await _call_safe("/api/crm/clients", params={"status": "active", "limit": 200})
            clients = clients_resp.get("clients") or clients_resp.get("data") or []

            for client in clients:
                if not isinstance(client, dict):
                    continue
                phone = client.get("phone")
                email = client.get("email")
                name = client.get("name", "")
                days_inactive = client.get("days_since_last_interaction", 0)
                risk_score = client.get("risk_score", 0)
                ltv = client.get("ltv_score", 50)

                # Rule: High-risk, inactive >30 days
                if (risk_score > 70 or days_inactive > 30) and phone:
                    try:
                        await _call_safe("/api/whatsapp/send", method="POST", json={
                            "phone": phone,
                            "message": f"Hi {name.split()[0] if name else 'there'}! It's been a while since we last connected. Is there anything we can help you with? — Bali Zero Team",
                        })
                        stats["re_engagements"] += 1
                    except Exception:
                        pass

                # Rule: VIP with upcoming birthday (if data available)
                if ltv > 80 and client.get("birthday_within_7_days") and email:
                    try:
                        await _call_safe("/api/zoho/emails", method="POST", json={
                            "to": email,
                            "subject": f"Happy Birthday, {name.split()[0] if name else ''}! 🎂",
                            "body": f"Dear {name},\n\nWishing you a wonderful birthday! As a valued client of Bali Zero, we appreciate your trust in us.\n\nBest regards,\nThe Bali Zero Team",
                        })
                        stats["birthday_greetings"] += 1
                    except Exception:
                        pass

            log.append({"step": "client_health_check", "status": "ok", "clients_checked": len(clients)})
        except Exception as e:
            log.append({"step": "client_health_check", "status": "error", "detail": str(e)})

        # Step 3: Check stalled practices
        try:
            stalled = await _call_safe("/api/crm/practices", params={"status": "stalled", "limit": 50})
            stalled_list = stalled.get("practices") or stalled.get("data") or []
            for p in stalled_list:
                if not isinstance(p, dict):
                    continue
                c_id = p.get("client_id")
                if c_id:
                    await _call_safe("/api/portal/messages", method="POST", json={
                        "client_id": c_id,
                        "subject": "Update on your practice",
                        "body": f"Your {p.get('type', 'practice')} seems to need attention. Please check your portal or contact us for assistance.",
                    })
                    stats["stalled_reminders"] += 1
            log.append({"step": "stalled_practices", "status": "ok", "stalled_count": len(stalled_list)})
        except Exception as e:
            log.append({"step": "stalled_practices", "status": "error", "detail": str(e)})

        # Step 4: NLM grounding — churn pattern analysis
        try:
            if _NB_OPS_ID and stats["re_engagements"] > 0:
                nlm_churn = await _nlm_grounding(
                    _NB_OPS_ID,
                    f"We sent {stats['re_engagements']} re-engagement messages today. "
                    "What patterns exist for client churn? Which segments have highest "
                    "churn risk and what retention strategies have worked?",
                )
                if nlm_churn:
                    stats["nlm_churn_insights"] = nlm_churn
                    log.append({"step": "nlm_churn_analysis", "status": "ok"})
        except Exception as e:
            log.append({"step": "nlm_churn_analysis", "status": "error", "detail": str(e)})

        res = {"chain": "client_health_monitor", "stats": stats, "log": log}
        await _reflect_and_save(_call_safe, "client_health_monitor",
            f"Re-engagements={stats.get('re_engagements',0)}, stalled_reminders={stats.get('stalled_reminders',0)}",
            "success" if not any(s.get("status") == "error" for s in log) else "partial",
            log)
        return res

    # =========================================================================
    # CHAIN 7: Compliance Autopilot
    # =========================================================================

    @mcp.tool()
    async def chain_compliance_autopilot(
        notify_critical: bool = True,
        auto_create_practices: bool = False,
    ) -> dict:
        """
        AUTOPILOT: Scan all compliance deadlines and take proactive action.

        Deterministic chain:
        1. Fetch all compliance alerts (CRITICAL + URGENT)
        2. For CRITICAL (<7 days): send WhatsApp + email + portal message
        3. For URGENT (<30 days): send portal reminder
        4. Optionally auto-create renewal practices for expiring items
        5. Generate summary report

        Args:
            notify_critical: Send multi-channel notifications for critical items
            auto_create_practices: Auto-create renewal practices for visa/license expiry

        Returns:
            Chain result with stats and action log.
        """
        log: list[dict] = []
        stats = {
            "critical_items": 0,
            "urgent_items": 0,
            "notifications_sent": 0,
            "practices_created": 0,
        }
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Step 1: Fetch critical alerts
        critical = await _call_safe(
            "/api/agents/compliance/alerts",
            params={"severity": "CRITICAL"},
        )
        critical_list = critical.get("alerts") or critical.get("data") or []
        stats["critical_items"] = len(critical_list)
        log.append({"step": "fetch_critical", "status": "ok", "count": len(critical_list)})

        # Step 2: Notify critical items (multi-channel)
        if notify_critical:
            for item in critical_list:
                if not isinstance(item, dict):
                    continue
                c_id = item.get("client_id")
                title = item.get("title", "Compliance deadline")
                days = item.get("days_remaining", "?")

                if c_id:
                    # WhatsApp (need phone from client data)
                    client_data = await _call_safe(f"/api/crm/clients/{c_id}")
                    phone = client_data.get("phone") if isinstance(client_data, dict) else None
                    if phone:
                        await _call_safe("/api/whatsapp/send", method="POST", json={
                            "phone": phone,
                            "message": f"⚠️ URGENT: {title} expires in {days} days. Please contact us immediately.",
                        })
                    # Email
                    client_email = client_data.get("email") if isinstance(client_data, dict) else None
                    if client_email:
                        await _call_safe("/api/zoho/emails", method="POST", json={
                            "to": client_email,
                            "subject": f"URGENT: {title} - Action Required",
                            "body": f"Your {title} deadline is in {days} days. Please contact our team to ensure timely renewal.",
                        })
                    # Portal
                    await _call_safe("/api/portal/messages", method="POST", json={
                        "client_id": c_id,
                        "subject": f"Action Required: {title}",
                        "body": f"Your {title} is due in {days} days. Please check your portal for details.",
                    })
                    stats["notifications_sent"] += 1
            log.append({"step": "notify_critical", "status": "ok", "sent": stats["notifications_sent"]})

        # Step 3: Fetch urgent alerts
        urgent = await _call_safe(
            "/api/agents/compliance/alerts",
            params={"severity": "URGENT"},
        )
        urgent_list = urgent.get("alerts") or urgent.get("data") or []
        stats["urgent_items"] = len(urgent_list)

        for item in urgent_list:
            if not isinstance(item, dict):
                continue
            c_id = item.get("client_id")
            title = item.get("title", "Upcoming deadline")
            days = item.get("days_remaining", "?")
            if c_id:
                await _call_safe("/api/portal/messages", method="POST", json={
                    "client_id": c_id,
                    "subject": f"Reminder: {title}",
                    "body": f"Friendly reminder: {title} is due in {days} days.",
                })
        log.append({"step": "notify_urgent", "status": "ok", "count": len(urgent_list)})

        # Step 4: Auto-create renewal practices
        if auto_create_practices:
            for item in critical_list:
                if not isinstance(item, dict):
                    continue
                comp_type = item.get("compliance_type", "")
                c_id = item.get("client_id")
                if comp_type in ("visa_expiry", "license_renewal") and c_id:
                    result = await _call_safe("/api/crm/practices", method="POST", json={
                        "client_id": c_id,
                        "type": f"renewal_{comp_type}",
                        "notes": f"Auto-created by compliance autopilot on {now_str}",
                    })
                    if not result.get("error"):
                        stats["practices_created"] += 1
            log.append({"step": "auto_practices", "status": "ok", "created": stats["practices_created"]})

        # Step 5: RDTR Zone Drift reale (Prime Nexus)
        stats.setdefault("zone_drifts", 0)
        try:
            geo_clients = await _call_safe("/api/crm/clients", params={"has_geo": "true", "limit": 20})
            clients_list = geo_clients.get("clients") or geo_clients.get("data") or []
            checked = 0
            for client in clients_list:
                if checked >= 5:
                    break
                stored_zone = client.get("rdtr_zone_code")
                if not stored_zone:
                    continue
                geo_point = client.get("geo_point") or {}
                lat = geo_point.get("lat") if isinstance(geo_point, dict) else None
                lng = geo_point.get("lng") if isinstance(geo_point, dict) else None
                if lat is None:
                    lat = client.get("geo_point_lat")
                if lng is None:
                    lng = client.get("geo_point_lng")
                if lat is None or lng is None:
                    continue
                try:
                    resolve_res = await _call_safe("/api/prime/v2/resolve", method="POST",
                                                  json={"lat": lat, "lng": lng})
                    current_zone = resolve_res.get("zone_code") or resolve_res.get("zone", {}).get("code")
                    checked += 1
                    if current_zone and current_zone != stored_zone:
                        stats["zone_drifts"] += 1
                        log.append({
                            "step": "rdtr_drift_check",
                            "status": "drift_detected",
                            "client_id": client.get("id"),
                            "stored_zone": stored_zone,
                            "current_zone": current_zone,
                        })
                except Exception:
                    pass  # skip silenzioso per singolo cliente
            log.append({"step": "rdtr_drift_check", "status": "ok",
                       "clients_checked": checked, "drifts_found": stats["zone_drifts"]})
        except Exception as e:
            log.append({"step": "rdtr_drift_check", "status": "skipped", "detail": str(e)})

        res = {"chain": "compliance_autopilot", "stats": stats, "log": log}
        await _reflect_and_save(_call_safe, "compliance_autopilot",
            f"Critical={stats.get('critical_compliance_items',0)}, notifications={stats.get('notifications_sent',0)}, practices={stats.get('practices_created',0)}",
            "success" if not any(s.get("status") == "error" for s in log) else "partial",
            log)
        return res

    # =========================================================================
    # CHAIN 8: Full Client Journey Accelerator
    # =========================================================================

    @mcp.tool()
    async def chain_journey_accelerator(
        client_id: str,
        journey_type: str = "pt_pma_setup",
    ) -> dict:
        """
        AUTOPILOT: Spin up a full client journey with all supporting assets.

        Deterministic chain:
        1. Create journey from template (pt_pma_setup / kitas_application / property_purchase)
        2. Calculate pricing for the service
        3. Create Google Drive folder for the client
        4. Track compliance deadlines based on journey type
        5. Send welcome message via portal + WhatsApp
        6. Submit orchestration task to generals for ongoing monitoring

        Args:
            client_id: UUID of the client
            journey_type: Journey template: pt_pma_setup, kitas_application, property_purchase

        Returns:
            Chain result with journey_id, pricing, folder, compliance items.
        """
        log: list[dict] = []
        result_data: dict = {}

        # Step 1: Create journey
        journey = await _call_safe(
            "/api/agents/journey/create",
            method="POST",
            json={"journey_type": journey_type, "client_id": client_id},
            timeout=long_timeout,
        )
        journey_id = journey.get("journey_id") or journey.get("id")
        result_data["journey"] = journey
        log.append({"step": "create_journey", "status": "ok" if journey_id else "error", "journey_id": journey_id})

        # Step 2: Calculate pricing
        service_map = {
            "pt_pma_setup": "pt_pma",
            "kitas_application": "kitas",
            "property_purchase": "property_due_diligence",
        }
        pricing = await _call_safe(
            "/api/agents/pricing/calculate",
            method="POST",
            json={"service_type": service_map.get(journey_type, journey_type)},
        )
        result_data["pricing"] = pricing
        log.append({"step": "calculate_pricing", "status": "ok" if not pricing.get("error") else "error"})

        # Step 3: Create Drive folder
        client = await _call_safe(f"/api/crm/clients/{client_id}")
        client_name = client.get("name") or client.get("full_name") or "Client"
        folder = await _call_safe(
            f"/api/crm/drive-folders/{client_id}",
            method="POST",
        )
        result_data["drive_folder"] = folder
        log.append({"step": "create_drive_folder", "status": "ok" if not folder.get("error") else "error"})

        # Step 4: Track compliance deadlines
        deadline_map = {
            "pt_pma_setup": ("license_renewal", "NIB Registration Deadline", 90),
            "kitas_application": ("visa_expiry", "KITAS Application Deadline", 60),
            "property_purchase": ("regulatory_change", "Property Due Diligence Deadline", 45),
        }
        if journey_type in deadline_map:
            comp_type, title, days_out = deadline_map[journey_type]
            from datetime import timedelta
            deadline = (datetime.now(timezone.utc) + timedelta(days=days_out)).strftime("%Y-%m-%d")
            compliance = await _call_safe(
                "/api/agents/compliance/track",
                method="POST",
                json={
                    "client_id": client_id,
                    "compliance_type": comp_type,
                    "title": title,
                    "description": f"Auto-tracked by journey accelerator for {journey_type}",
                    "deadline": deadline,
                },
            )
            result_data["compliance"] = compliance
            log.append({"step": "track_compliance", "status": "ok" if not compliance.get("error") else "error"})

        # Step 5: Welcome messages
        welcome = f"Welcome! Your {journey_type.replace('_', ' ')} journey has been created. Track progress in your portal."
        await _call_safe("/api/portal/messages", method="POST", json={
            "client_id": client_id,
            "subject": f"Journey Started: {journey_type.replace('_', ' ').title()}",
            "body": welcome,
        })
        client_phone = client.get("phone") if isinstance(client, dict) else None
        if client_phone:
            await _call_safe("/api/whatsapp/send", method="POST", json={
                "phone": client_phone,
                "message": welcome,
            })
        log.append({"step": "welcome_messages", "status": "ok"})

        # Step 6: Submit monitoring task to generals
        task = await _call_safe(
            "/api/generals/tasks",
            method="POST",
            json={
                "task_type": "orchestration",
                "title": f"Monitor {journey_type} for {client_name}",
                "description": f"Track journey {journey_id} progress, send reminders if stalled >7 days.",
                "payload": {"journey_id": journey_id, "client_id": client_id},
                "priority": 7,
            },
        )
        result_data["monitoring_task"] = task
        log.append({"step": "submit_monitoring", "status": "ok" if not task.get("error") else "error"})

        res = {
            "chain": "journey_accelerator",
            "journey_id": journey_id,
            "data": result_data,
            "log": log,
        }
        await _reflect_and_save(_call_safe, "journey_accelerator",
            f"Client={client_name}, journey_type={journey_type}, journey_id={journey_id}",
            "success" if not any(s.get("status") == "error" for s in log) else "partial",
            log)
        return res
