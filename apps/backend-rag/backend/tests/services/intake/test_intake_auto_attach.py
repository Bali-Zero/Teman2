"""LEVA 2 — auto-attach double-concordant: concordance-gate + killswitch tests.

The load-bearing safety logic is ``evaluate_concordance`` — the gate that decides
whether the system may commit a document WITHOUT a human. It must let through ONLY
the genuinely-unambiguous case (one strong identifier AND a sender phone agreeing
on the SAME single client) and refuse everything else. Per the cicatrix #3
antidote, this guard ships with BOTH guilt (it fires on the concordant case) and
innocence (it does NOT fire on every near-miss: phone-only, shared phone,
disagreeing signals, unresolved client, non-AUTO_ATTACH).

The phone resolution (``routing._match_sender_phone``) is patched here so the gate
logic is tested deterministically without depending on the live ``clients``
schema. The real CRM-commit path (``plan_commit`` / ``execute_commit``) is covered
by ``test_intake_writer.py`` against a schema-complete DB; this file owns the gate.
"""

from __future__ import annotations

import pytest

from backend.services.intake import auto_attach


class _StubConn:
    """Minimal stand-in; evaluate_concordance only passes it to the patched matcher."""


def _patch_phone(monkeypatch, matches):
    async def _fake_match(_conn, _phone):
        return list(matches)

    monkeypatch.setattr(auto_attach, "_match_sender_phone", _fake_match)


# --------------------------------------------------------------------------- #
# GUILT — the one case auto-attach exists to handle
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_guilt_strong_id_and_phone_agree_is_concordant(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "X"}])
    v = await auto_attach.evaluate_concordance(
        _StubConn(), decision="AUTO_ATTACH", client_id=42, sender_phone="0812..."
    )
    assert v["concordant"] is True
    assert v["phone_client_id"] == 42
    assert v["phone_match_count"] == 1


# --------------------------------------------------------------------------- #
# INNOCENCE — every neighbour that must STAY in human review
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_innocence_phone_disagrees_with_strong_id(monkeypatch):
    """strong-id→client 42 but phone→client 99 → NOT concordant (the key safety)."""
    _patch_phone(monkeypatch, [{"id": 99, "full_name": "Other"}])
    v = await auto_attach.evaluate_concordance(
        _StubConn(), decision="AUTO_ATTACH", client_id=42, sender_phone="0812..."
    )
    assert v["concordant"] is False
    assert v["phone_client_id"] == 99
    assert "DISAGREE" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_shared_phone_is_ambiguous(monkeypatch):
    """sender phone shared by >1 client (spouse/agent) → NOT concordant."""
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "A"}, {"id": 43, "full_name": "B"}])
    v = await auto_attach.evaluate_concordance(
        _StubConn(), decision="AUTO_ATTACH", client_id=42, sender_phone="0812..."
    )
    assert v["concordant"] is False
    assert v["phone_match_count"] == 2
    assert "shared" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_phone_unknown_strong_id_only(monkeypatch):
    """strong-id resolves but sender phone matches nobody → NOT concordant.

    Single-signal (strong-id only) must keep going to a human — auto-attach
    requires the SECOND concordant signal."""
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_concordance(
        _StubConn(), decision="AUTO_ATTACH", client_id=42, sender_phone="0812..."
    )
    assert v["concordant"] is False
    assert v["phone_match_count"] == 0


@pytest.mark.asyncio
async def test_innocence_not_auto_attach_decision(monkeypatch):
    """LINK_CANDIDATE / AMBIGUOUS / NO_MATCH never auto-attach (no phone lookup)."""
    called = {"n": 0}

    async def _spy(_c, _p):
        called["n"] += 1
        return [{"id": 42}]

    monkeypatch.setattr(auto_attach, "_match_sender_phone", _spy)
    for dec in ("LINK_CANDIDATE", "AMBIGUOUS", "NO_MATCH", None):
        v = await auto_attach.evaluate_concordance(
            _StubConn(), decision=dec, client_id=42, sender_phone="0812..."
        )
        assert v["concordant"] is False
    # Short-circuits BEFORE the phone lookup — no wasted query for non-AUTO_ATTACH.
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_innocence_auto_attach_without_resolved_client(monkeypatch):
    """AUTO_ATTACH but routing.client_id is None → NOT concordant (no target)."""
    _patch_phone(monkeypatch, [{"id": 42}])
    v = await auto_attach.evaluate_concordance(
        _StubConn(), decision="AUTO_ATTACH", client_id=None, sender_phone="0812..."
    )
    assert v["concordant"] is False
    assert "unresolved" in v["reason"]


# --------------------------------------------------------------------------- #
# kill-switch — default OFF, AND independent of the writer flag
# --------------------------------------------------------------------------- #
def test_auto_attach_disabled_by_default(monkeypatch):
    monkeypatch.delenv("INTAKE_AUTO_ATTACH_ENABLED", raising=False)
    assert auto_attach.auto_attach_enabled() is False


def test_auto_attach_enabled_when_truthy(monkeypatch):
    for val in ("1", "true", "yes", "on", "ON"):
        monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", val)
        assert auto_attach.auto_attach_enabled() is True


def test_auto_attach_disabled_when_falsy(monkeypatch):
    for val in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", val)
        assert auto_attach.auto_attach_enabled() is False


# --------------------------------------------------------------------------- #
# try_auto_attach short-circuits — both flags must be ON before any DB touch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_try_auto_attach_noop_when_killswitch_off(monkeypatch):
    monkeypatch.delenv("INTAKE_AUTO_ATTACH_ENABLED", raising=False)
    proposal = {"id": 1, "routing": {"client_id": 42}, "entity_resolution": {"decision": "AUTO_ATTACH"}}
    out = await auto_attach.try_auto_attach(proposal, pool=None, sender_phone="0812")
    assert out["committed"] is False
    assert out["skipped"] == "killswitch_off"


@pytest.mark.asyncio
async def test_try_auto_attach_noop_when_writer_off(monkeypatch):
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)
    proposal = {"id": 1, "routing": {"client_id": 42}, "entity_resolution": {"decision": "AUTO_ATTACH"}}
    out = await auto_attach.try_auto_attach(proposal, pool=None, sender_phone="0812")
    assert out["committed"] is False
    assert out["skipped"] == "writer_off"
