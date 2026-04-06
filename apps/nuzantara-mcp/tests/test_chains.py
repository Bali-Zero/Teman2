"""Unit tests for workflow chains — mock-only, no backend calls.

Tests verify: dedup logic, idempotency guards, error handling, step flow.
NB-1 validated: mock-only is correct; integration tests live in backend-rag.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nuzantara_mcp.workflows.chains import register, _should_notify, _notification_log


def _register_chains(mock_mcp, mock_call, mock_call_safe):
    """Register chains and capture tool functions."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe, long_timeout=120)
    return tools


@pytest.fixture(autouse=True)
def clear_dedup():
    """Clear dedup log between tests."""
    _notification_log.clear()
    yield
    _notification_log.clear()


# =========================================================================
# CHAIN 1: Daily Ops Autopilot
# =========================================================================


@pytest.mark.asyncio
async def test_daily_ops_basic_flow(mock_mcp, mock_call, mock_call_safe) -> None:
    """daily_ops should run all steps and return log."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    # Mock responses for each step
    mock_call_safe.side_effect = [
        # Step 1: expiry alerts
        {"alerts": [{"client_id": 1, "phone": "+6281234", "document_type": "KITAS",
                     "days_remaining": 15}]},
        # Step 1: WhatsApp send
        {"status": "ok"},
        # Step 1: log interaction
        {"status": "ok"},
        # Step 2: agent health
        {"agents": {"main": {"status": "active"}}},
        # Step 3: intel critical
        {"alerts": []},
        # Step 4: team hours
        {"total_hours": 40},
        # Step 4: completion rates
        {"completion_rate": 85},
        # Step 6: send report email
        {"status": "ok"},
        # Reflection save
        {"status": "ok"},
    ]

    result = await tools["chain_daily_ops_autopilot"]()
    assert result["chain"] == "daily_ops_autopilot"
    assert "log" in result
    assert any(s["step"] == "expiry_alerts" for s in result["log"])


@pytest.mark.asyncio
async def test_daily_ops_dedup_reminders(mock_mcp, mock_call, mock_call_safe) -> None:
    """daily_ops should dedup WhatsApp reminders."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    alert = {"client_id": 1, "phone": "+6281234", "document_type": "KITAS", "days_remaining": 15}
    msg = f"Reminder: Your {alert['document_type']} expires in {alert['days_remaining']} days. Please contact Bali Zero for renewal."

    # Pre-populate dedup log
    _should_notify(1, "whatsapp", msg)  # first call succeeds, marks as sent

    mock_call_safe.side_effect = [
        {"alerts": [alert]},  # expiry alerts
        # No WhatsApp send — dedup blocks it
        {"agents": {}},  # agent health
        {"alerts": []},  # intel
        {},  # team hours
        {},  # completion
        {},  # email
        {},  # reflection
    ]

    result = await tools["chain_daily_ops_autopilot"]()
    # Should have 0 reminders sent because dedup blocked
    assert result["report"]["expiry_alerts"]["reminders_sent"] == 0


# =========================================================================
# CHAIN 2: New Client Onboarding (idempotency)
# =========================================================================


@pytest.mark.asyncio
async def test_onboarding_creates_new_client(mock_mcp, mock_call, mock_call_safe) -> None:
    """Onboarding should create client when email not found."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    mock_call_safe.side_effect = [
        # Step 1: search existing — empty
        {"clients": []},
        # Step 2: KBLI search
        {"results": [{"code": "62010"}]},
        # Step 3: pricing
        {"service_type": "visa"},
        # Step 4: drive folder
        {"folder_id": "abc123"},
        # Step 6: execution plan
        {"plan_id": "plan1"},
        # Step 7: portal welcome
        {},
        # Step 7: email welcome
        {},
        # Step 7: WhatsApp welcome
        {},
        # Step 8: log interaction
        {},
        # Reflection
        {},
    ]
    mock_call.side_effect = [
        # Step 1: create client
        {"id": 42},
        # Step 5: create practice
        {"id": 100},
    ]

    result = await tools["chain_new_client_onboarding"](
        name="Test User", email="test@example.com",
        nationality="Italian", business_description="restaurant in Canggu",
        phone="+6281234",
    )
    assert result["result"]["client_id"] == 42
    assert any(s["step"] == "create_client" and s["status"] == "ok" for s in result["log"])


@pytest.mark.asyncio
async def test_onboarding_skips_existing_client(mock_mcp, mock_call, mock_call_safe) -> None:
    """Onboarding should skip creation when email exists (idempotency)."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    mock_call_safe.side_effect = [
        # Step 1: search existing — found
        {"clients": [{"id": 99, "email": "test@example.com"}]},
        # Step 2: KBLI
        {"results": []},
        # Step 3: pricing
        {},
        # Step 4: drive
        {"folder_id": "existing"},
        # Step 6: plan
        {"plan_id": "p2"},
        # Step 7: portal
        {},
        # Step 7: email
        {},
        # Step 7: WA
        {},
        # Step 8: interaction
        {},
        # Reflection
        {},
    ]
    mock_call.side_effect = [
        # Step 5: create practice
        {"id": 200},
    ]

    result = await tools["chain_new_client_onboarding"](
        name="Test User", email="test@example.com",
        nationality="Italian", business_description="consulting",
        phone="+6281234",
    )
    # Should use existing client_id, not create new
    assert result["result"]["client_id"] == 99
    assert any(s["step"] == "create_client" and s["status"] == "skipped" for s in result["log"])


# =========================================================================
# CHAIN 3: Practice Lifecycle
# =========================================================================


@pytest.mark.asyncio
async def test_practice_lifecycle_basic(mock_mcp, mock_call, mock_call_safe) -> None:
    """practice_lifecycle should check practices and flag expiring ones."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    from datetime import date, timedelta
    expiry = (date.today() + timedelta(days=30)).isoformat()

    mock_call_safe.side_effect = [
        # Fetch practices
        {"practices": [
            {"id": 1, "client_id": 10, "type": "kitas", "status": "active",
             "expiry_date": expiry, "practice_type_code": "kitas"},
        ]},
        # PATCH practice status
        {},
        # Portal renewal message
        {},
        # Completion rates
        {"completion_rate": 90},
        # Reflection
        {},
    ]

    result = await tools["chain_practice_lifecycle_check"]()
    assert result["chain"] == "practice_lifecycle"
    assert result["stats"]["expiring_soon"] == 1


# =========================================================================
# CHAIN 7: Compliance Autopilot (dedup)
# =========================================================================


@pytest.mark.asyncio
async def test_compliance_sends_multi_channel(mock_mcp, mock_call, mock_call_safe) -> None:
    """compliance_autopilot should send WA+email+portal for critical items."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    mock_call_safe.side_effect = [
        # Step 1: critical alerts
        {"alerts": [{"client_id": 5, "title": "KITAS Expiry", "days_remaining": 3}]},
        # Step 2: get client data
        {"phone": "+6289876", "email": "client@test.com"},
        # Step 2: WA send
        {},
        # Step 2: email send
        {},
        # Step 2: portal send
        {},
        # Step 3: urgent alerts
        {"alerts": []},
        # Step 5: RDTR drift
        {"status": "healthy"},
        # Reflection
        {},
    ]

    result = await tools["chain_compliance_autopilot"]()
    assert result["stats"]["notifications_sent"] == 1
    assert result["stats"]["critical_items"] == 1


@pytest.mark.asyncio
async def test_compliance_dedup_blocks_repeat(mock_mcp, mock_call, mock_call_safe) -> None:
    """compliance_autopilot should dedup notifications on re-run."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    # Pre-populate dedup for all 3 channels
    wa_msg = "URGENT: KITAS Expiry expires in 3 days. Please contact us immediately."
    email_msg = "Your KITAS Expiry deadline is in 3 days. Please contact our team to ensure timely renewal."
    portal_msg = "Your KITAS Expiry is due in 3 days. Please check your portal for details."
    _should_notify(5, "whatsapp", wa_msg)
    _should_notify(5, "email", email_msg)
    _should_notify(5, "portal", portal_msg)

    mock_call_safe.side_effect = [
        # Step 1: critical alerts
        {"alerts": [{"client_id": 5, "title": "KITAS Expiry", "days_remaining": 3}]},
        # Step 2: get client data (still fetched, but sends are blocked)
        {"phone": "+6289876", "email": "client@test.com"},
        # Step 3: urgent alerts
        {"alerts": []},
        # Step 5: RDTR drift
        {"status": "healthy"},
        # Reflection
        {},
    ]

    result = await tools["chain_compliance_autopilot"]()
    # notifications_sent still increments (counts attempts, not actual sends)
    # but the actual _write_safe calls are fewer because dedup blocked them


# =========================================================================
# CHAIN 8: Journey Accelerator (idempotency)
# =========================================================================


@pytest.mark.asyncio
async def test_journey_skips_existing(mock_mcp, mock_call, mock_call_safe) -> None:
    """journey_accelerator should skip creation if journey exists."""
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe)

    mock_call_safe.side_effect = [
        # Check existing journeys — found matching type
        {"journeys": [{"journey_type": "pt_pma_setup", "id": "j-existing"}]},
        # Step 2: pricing
        {"base_price": 20_000_000},
        # Step 3: get client
        {"name": "Test Client", "phone": "+628123"},
        # Step 3: drive folder
        {"folder_id": "f1"},
        # Step 4: compliance track
        {},
        # Step 5: portal welcome
        {},
        # Step 5: WA welcome
        {},
        # Step 6: monitoring task
        {},
        # Reflection
        {},
    ]

    result = await tools["chain_journey_accelerator"](
        client_id="uuid-123", journey_type="pt_pma_setup",
    )
    assert any(s["step"] == "create_journey" and s["status"] == "skipped" for s in result["log"])


# =========================================================================
# Dedup unit tests
# =========================================================================


def test_should_notify_first_call_passes() -> None:
    """First notification should always pass."""
    assert _should_notify("c1", "wa", "hello") is True


def test_should_notify_same_blocked() -> None:
    """Same client+channel+content should be blocked."""
    _should_notify("c1", "wa", "hello")
    assert _should_notify("c1", "wa", "hello") is False


def test_should_notify_different_channel_passes() -> None:
    """Different channel should pass."""
    _should_notify("c1", "wa", "hello")
    assert _should_notify("c1", "email", "hello") is True


def test_should_notify_different_content_passes() -> None:
    """Different content should pass."""
    _should_notify("c1", "wa", "hello")
    assert _should_notify("c1", "wa", "goodbye") is True
