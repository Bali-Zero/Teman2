"""Tests for the local OpenClaw WhatsApp bridge runtime script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_bridge_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "openclaw_whatsapp_bridge.py"
    spec = importlib.util.spec_from_file_location("openclaw_whatsapp_bridge_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge_module()


def test_build_prompt_includes_kb_tool_contract_and_autonomy() -> None:
    history = [{"role": "user", "text": f"message {idx}"} for idx in range(10)]
    body = bridge.BridgeRequest(
        agent="wa",
        model="openai/gpt-5.5",
        thinking="high",
        persona="zantara_whatsapp_v1",
        autonomy_mode="supervised_autonomous",
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.test",
        text="I want to open a cafe in Canggu. Which KBLI?",
        context={
            "detected_language": "en",
            "is_first_message": False,
            "client_profile": {"segment": "founder"},
            "conversation_history": history,
        },
    )

    prompt = json.loads(bridge._build_prompt(body))

    assert prompt["persona"] == "zantara_whatsapp_v1"
    assert prompt["autonomy_mode"] == "supervised_autonomous"
    assert prompt["incoming_text"] == "I want to open a cafe in Canggu. Which KBLI?"
    assert prompt["client_profile"] == {"segment": "founder"}
    assert len(prompt["recent_history"]) == 8
    assert prompt["recent_history"][0]["text"] == "message 2"
    assert any("KBLI" in rule for rule in prompt["knowledge_tool_contract"])
    assert any("nuzantara-mcp.search_kbli" in rule for rule in prompt["knowledge_tool_contract"])
    assert any("Nuzantara MCP tools" in rule for rule in prompt["knowledge_tool_contract"])
    assert any("do not invent" in rule for rule in prompt["reply_rules"])
    assert any("self-triggered loop" in step for step in prompt["operating_loop"])
    assert any("Do not expose internal tools" in rule for rule in prompt["reply_rules"])


def test_build_prompt_marks_pricing_intent_as_mandatory_tool_call() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.price",
        text="Give me the exact total price for investor KITAS and guarantee the timeline.",
    )

    prompt = json.loads(bridge._build_prompt(body))

    assert any("Pricing/quote/timeline intent detected" in rule for rule in prompt["tool_mandates"])
    assert any("nuzantara-mcp.search_service_pricing" in rule for rule in prompt["tool_mandates"])
    assert any("mandatory" in rule for rule in prompt["knowledge_tool_contract"])


def test_build_prompt_marks_kbli_followup_from_recent_context() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.followup",
        text="And can that work with a PT PMA, or do I need a different setup?",
        context={
            "conversation_history": [
                {
                    "role": "user",
                    "text": "I want to open a small cafe in Canggu. Which KBLI?",
                }
            ]
        },
    )

    prompt = json.loads(bridge._build_prompt(body))

    assert any("KBLI/company-setup intent detected" in rule for rule in prompt["tool_mandates"])
    assert any("nuzantara-mcp.search_kbli" in rule for rule in prompt["tool_mandates"])


def test_build_prompt_includes_villa_55193_to_55203_mapping_rule() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.villa",
        text="ma per ville Airbnb e' 55193 o 55203?",
        context={"detected_language": "it"},
    )

    prompt = json.loads(bridge._build_prompt(body))
    contract = "\n".join(prompt["knowledge_tool_contract"])

    assert "55193" in contract
    assert "55203" in contract
    assert "KBLI 2020/PP28" in contract
    assert "KBLI 2025" in contract
    assert "55901" in contract
    assert "55400" in contract
    assert "AC/ventilation" in contract


def test_bridge_guard_corrects_bad_villa_55193_reply() -> None:
    guarded = bridge._guard_villa_kbli_reply(
        "ma per ville Airbnb e' 55193 o 55203?",
        "55193 - Aktivitas Vila: usa questo codice per Airbnb.",
        "it",
    )

    assert "55203" in guarded
    assert "55193" in guarded
    assert "KBLI 2020/PP28" in guarded
    assert "usa questo codice" not in guarded


def test_bridge_guard_keeps_grounded_villa_mapping_reply() -> None:
    reply = (
        "55193 era il codice KBLI 2020/PP28 sorgente; nel mapping KBLI 2025 "
        "mappa a 55203 - AKTIVITAS VILA."
    )

    assert bridge._guard_villa_kbli_reply("Differenza 55193 vs 55203", reply, "it") == reply


def test_property_zoning_guard_allows_villa_leasehold_duration() -> None:
    # Regression (villa-zoning-guard 2026-06-08): a lease-DURATION question
    # must NOT be clobbered by the Airbnb/zoning canned answer. The bare
    # "lease" trigger matches "leasehold"; the escape clause (oss+bkpm) is
    # unreachable for a correct duration reply, so pre-fix this returned the
    # canned zoning text instead of the real answer.
    correct = (
        "A typical villa leasehold in Bali is often around 25 to 30 years, "
        "sometimes with an option to extend."
    )
    assert (
        bridge._guard_property_zoning_reply(
            "How long is a typical villa leasehold in Bali?", correct, "en"
        )
        == correct
    )


def test_property_zoning_guard_allows_villa_lease_duration_reworded() -> None:
    correct = "A villa lease in Bali usually runs 25 years with renewal options."
    assert (
        bridge._guard_property_zoning_reply(
            "What is the usual duration of a villa lease in Bali?", correct, "en"
        )
        == correct
    )


def test_property_zoning_guard_still_fires_on_airbnb_operation() -> None:
    # The guard must STILL clobber a genuine Airbnb-in-residential-zone
    # operation question whose reply lacks the OSS/BKPM grounding.
    ungrounded = "Sure, just rent your villa on Airbnb, no special permits needed."
    guarded = bridge._guard_property_zoning_reply(
        "Can I run my villa as an Airbnb in a residential zone?", ungrounded, "en"
    )
    assert guarded != ungrounded  # was replaced by the canned zoning answer
def test_b211_guard_allows_correct_definitional_answer() -> None:
    reply = (
        "A B211/B211A is a short-stay visit/business visa: it gives no residency and "
        "no work rights. A KITAS is a limited-stay residency permit, and its work "
        "variant grants employment. B211 is old wording; the current short-stay "
        "business route is usually C2 Business, which the team confirms for your case."
    )

    assert (
        bridge._guard_legacy_b211_reply(
            "What's the difference between a B211A visa and a KITAS?", reply, "en"
        )
        == reply
    )


def test_b211_guard_still_clobbers_unsafe_current_claim() -> None:
    unsafe = (
        "Yes, the B211 is the right visa for you. Apply for it and you can run your "
        "business meetings in Bali with no problem."
    )

    guarded = bridge._guard_legacy_b211_reply(
        "Can I use a B211 to do business in Bali?", unsafe, "en"
    )

    assert guarded != unsafe
    assert "C2 Business" in guarded


def test_run_script_uses_installed_bridge_app_dir() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    script = (repo_root / "scripts" / "run_openclaw_whatsapp_bridge.sh").read_text(
        encoding="utf-8"
    )

    assert '--app-dir "$HOME/.openclaw/bin"' in script
    assert ".worktrees/backend-rag-openclaw-whatsapp-meta" not in script


def test_session_key_strips_phone_punctuation_and_scopes_message() -> None:
    assert bridge._session_key("wa", "+62 812-345") == "agent:wa:whatsapp-meta-62812345"
    assert (
        bridge._session_key("wa", "+62 812-345", "wamid.test:123")
        == "agent:wa:whatsapp-meta-62812345-wamid-test-123"
    )
    assert bridge._session_key("wa", "no digits") == "agent:wa:whatsapp-meta-unknown"


@pytest.mark.asyncio
async def test_run_openclaw_passes_runtime_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            payload = {"result": {"finalAssistantVisibleText": "Ready from Zantara."}}
            return json.dumps(payload).encode(), b""

    async def fake_create_subprocess_exec(*args: str, **kwargs: Any) -> FakeProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(bridge.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setenv("OPENCLAW_WHATSAPP_TIMEOUT_SECONDS", "30")

    reply = await bridge._run_openclaw(
        "wa",
        '{"incoming_text":"hi"}',
        "628123",
        "wamid.test",
        "openai/gpt-5.5",
        "high",
    )

    args = captured["args"]
    assert reply == "Ready from Zantara."
    assert args[:4] == ("openclaw", "agent", "--agent", "wa")
    assert "--channel" in args
    assert args[args.index("--channel") + 1] == "whatsapp"
    assert "--to" in args
    assert args[args.index("--to") + 1] == "+628123"
    assert "--session-key" in args
    assert args[args.index("--session-key") + 1] == "agent:wa:whatsapp-meta-628123-wamid-test"
    assert "--model" in args
    assert args[args.index("--model") + 1] == "openai/gpt-5.5"
    assert "--thinking" in args
    assert args[args.index("--thinking") + 1] == "high"
    assert "--deliver" not in args


def test_army_owner_allowlist_deny_all_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Panel fix (Gemini): unset env = true closed-by-default = deny-all,
    # NOT hardcoded-open-to-one. The army feature is disabled until opt-in.
    monkeypatch.delenv("WA_ARMY_OWNERS", raising=False)
    assert bridge._army_owner_allowlist() == frozenset()
    monkeypatch.setenv("WA_ARMY_OWNERS", "   ")
    assert bridge._army_owner_allowlist() == frozenset()


def test_army_owner_allowlist_parses_and_normalizes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", " +62 822-6459-9868 , 6281234567890 , ")
    allow = bridge._army_owner_allowlist()
    assert allow == frozenset({"6282264599868", "6281234567890"})


def test_army_owner_allowlist_drops_non_digit_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    # Panel fix (Codex): an env value that normalizes to "" must NOT become a
    # member, or a malformed sender phone normalizing to "" would match it.
    monkeypatch.setenv("WA_ARMY_OWNERS", "abc, 6282264599868, ---")
    allow = bridge._army_owner_allowlist()
    assert allow == frozenset({"6282264599868"})
    assert "" not in allow


def test_is_army_owner_normalizes_punctuation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282264599868")
    assert bridge._is_army_owner("+62 822-6459-9868") is True
    assert bridge._is_army_owner("6282264599868") is True
    assert bridge._is_army_owner("+62 812-000-0000") is False
    assert bridge._is_army_owner(None) is False
    assert bridge._is_army_owner("") is False


def test_is_army_owner_rejects_malformed_phone_against_empty_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Panel fix (Codex): even if the allowlist were somehow empty, a phone
    # that normalizes to "" must never match. Belt-and-suspenders on both sides.
    monkeypatch.delenv("WA_ARMY_OWNERS", raising=False)
    assert bridge._is_army_owner("no-digits-here") is False
    assert bridge._is_army_owner("---") is False


@pytest.mark.asyncio
async def test_army_command_owner_can_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282264599868")
    captured: dict[str, Any] = {}

    async def fake_runner(*args: str) -> tuple[int, str, str]:
        captured["args"] = args
        return (0, "LAUNCHED sess-1 /tmp/log", "")

    monkeypatch.setattr(bridge, "_run_army_launcher", fake_runner)

    reply = await bridge._handle_army_command("/lancia S1", "+62 822-6459-9868")

    assert captured["args"] == ("launch", "S1")
    assert reply is not None
    assert "LANCIATA" in reply


@pytest.mark.asyncio
async def test_army_command_non_owner_falls_through_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282264599868")
    called = False

    async def fake_runner(*args: str) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return (0, "should-not-run", "")

    monkeypatch.setattr(bridge, "_run_army_launcher", fake_runner)

    # Non-owner sends every army command shape — all must return None and
    # NEVER touch the launcher (no claude --dangerously-skip-permissions).
    for text in ("/lancia S1", "/armate", "armate-status", "/ferma S1"):
        assert await bridge._handle_army_command(text, "+62 812-000-0000") is None
    assert called is False


@pytest.mark.asyncio
async def test_army_command_deny_all_blocks_even_owner_number_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With WA_ARMY_OWNERS unset, the allowlist is empty → NOBODY can launch,
    # not even the default owner number. Deny-all is the safe failure mode.
    monkeypatch.delenv("WA_ARMY_OWNERS", raising=False)
    called = False

    async def fake_runner(*args: str) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return (0, "should-not-run", "")

    monkeypatch.setattr(bridge, "_run_army_launcher", fake_runner)

    assert await bridge._handle_army_command("/lancia S1", "+62 822-6459-9868") is None
    assert called is False


@pytest.mark.asyncio
async def test_army_command_non_command_returns_none_for_everyone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282264599868")
    # Even the owner: a normal message is not a command → None (LLM handles it).
    assert await bridge._handle_army_command("ciao come stai?", "+62 822-6459-9868") is None
    assert await bridge._handle_army_command("", "+62 822-6459-9868") is None


@pytest.mark.asyncio
async def test_run_openclaw_uses_env_model_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            payload = {"result": {"payloads": [{"text": "Env defaults ok."}]}}
            return json.dumps(payload).encode(), b""

    async def fake_create_subprocess_exec(*args: str, **kwargs: Any) -> FakeProcess:
        captured["args"] = args
        return FakeProcess()

    monkeypatch.setattr(bridge.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setenv("OPENCLAW_WHATSAPP_MODEL", "openai/gpt-5.5")
    monkeypatch.setenv("OPENCLAW_WHATSAPP_THINKING", "high")

    reply = await bridge._run_openclaw("wa", "{}", "+628123", "wamid.env", None, None)

    args = captured["args"]
    assert reply == "Env defaults ok."
    assert args[args.index("--model") + 1] == "openai/gpt-5.5"
    assert args[args.index("--thinking") + 1] == "high"
