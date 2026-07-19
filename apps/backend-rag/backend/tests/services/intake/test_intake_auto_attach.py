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
    """Minimal stand-in for the direct-phone gate's own DB lookups.

    ``evaluate_concordance`` (strict gate) never queries through it. The
    direct-phone gate now runs two reads: an anti-funnel volume ``fetchrow`` and a
    client-name ``fetchval``. Defaults are the benign case (low volume + a client
    name); tests override per case.
    """

    def __init__(self, *, funnel=None, client_name="Maria Garcia"):
        # benign default: 1 doc / 1 doctype (not a funnel)
        self._funnel = funnel if funnel is not None else {"docs": 1, "distinct_types": 1}
        self._client_name = client_name

    async def fetchrow(self, _query, *_args):
        return self._funnel

    async def fetchval(self, _query, *_args):
        return self._client_name


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


def test_direct_phone_auto_attach_disabled_by_default(monkeypatch):
    monkeypatch.delenv("INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED", raising=False)
    assert auto_attach.direct_phone_auto_attach_enabled() is False


def test_direct_phone_auto_attach_enabled_when_truthy(monkeypatch):
    for val in ("1", "true", "yes", "on", "ON"):
        monkeypatch.setenv("INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED", val)
        assert auto_attach.direct_phone_auto_attach_enabled() is True


# --------------------------------------------------------------------------- #
# direct WA phone-only gate — opt-in post-routing catalog, not FASE-4 auto attach
# --------------------------------------------------------------------------- #
_DIRECT_SOURCE_CONTEXT = {
    "transport": "wa-mirror",
    "chat_type": "direct",
    "routing_identity_policy": "sender_phone_enabled",
}


@pytest.mark.asyncio
async def test_guilt_direct_phone_link_candidate_is_concordant(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Maria Garcia"}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match (no strong identifier, no fuzzy name >= 0.40)"},
        extracted_name="MARIA GARCIA LOPEZ",  # OCR subject name agrees with client
    )
    assert v["concordant"] is True
    assert v["phone_client_id"] == 42
    assert v["phone_match_count"] == 1


@pytest.mark.asyncio
async def test_internal_filter_direct_phone_internal_number_abstains(monkeypatch):
    monkeypatch.setenv("BZ_INTERNAL_PHONE_NUMBERS", "+628213454720")

    async def _fail_if_called(_conn, _phone):
        raise AssertionError("internal phone should not reach CRM phone lookup")

    monkeypatch.setattr(auto_attach, "_match_sender_phone", _fail_if_called)
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="+628213454720",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name="MARIA GARCIA",
    )
    assert v["concordant"] is False
    assert v["phone_client_id"] is None
    assert v["phone_match_count"] == 0
    assert "internal-number" in v["reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("sender_phone", ["08213454720", "628213454720"])
async def test_internal_filter_direct_phone_internal_number_alt_formats_abstain(
    monkeypatch, sender_phone
):
    monkeypatch.setenv("BZ_INTERNAL_PHONE_NUMBERS", "+62 821-345-4720")

    async def _fail_if_called(_conn, _phone):
        raise AssertionError("internal phone should not reach CRM phone lookup")

    monkeypatch.setattr(auto_attach, "_match_sender_phone", _fail_if_called)
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone=sender_phone,
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name="MARIA GARCIA",
    )
    assert v["concordant"] is False
    assert "internal-number" in v["reason"]


@pytest.mark.asyncio
async def test_internal_filter_direct_phone_non_internal_number_unchanged(monkeypatch):
    monkeypatch.setenv("BZ_INTERNAL_PHONE_NUMBERS", "+628213454720")
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Maria Garcia"}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="+628299900001",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name="MARIA GARCIA",
    )
    assert v["concordant"] is True
    assert v["phone_client_id"] == 42
    assert v["phone_match_count"] == 1


@pytest.mark.asyncio
async def test_internal_filter_direct_phone_empty_blocklist_unchanged(monkeypatch):
    monkeypatch.delenv("BZ_INTERNAL_PHONE_NUMBERS", raising=False)
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Maria Garcia"}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="+628213454720",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name="MARIA GARCIA",
    )
    assert v["concordant"] is True
    assert v["phone_client_id"] == 42
    assert v["phone_match_count"] == 1


@pytest.mark.asyncio
async def test_innocence_direct_phone_name_mismatch_abstains(monkeypatch):
    """The lived incident: phone resolves a client but the document's OCR subject
    name is a DIFFERENT person (operator forwarded a client's doc) → abstain."""
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Ari Firda"}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Ari Firda"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="birth_certificate",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name="JUAN CARLOS FERNANDEZ",  # the Spanish client, not Ari
    )
    assert v["concordant"] is False
    assert "name not concordant" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_no_extractable_name_abstains(monkeypatch):
    """doc with no subject name (ktp/bank_statement) cannot be verified → abstain."""
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Maria Garcia"}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="bank_statement",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name=None,  # nothing to verify the subject
    )
    assert v["concordant"] is False
    assert "no extractable subject name" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_funnel_abstains(monkeypatch):
    """high-volume funnel phone (one number forwarding for many clients) → abstain
    even though it resolves to one client_id and the name agrees."""
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Maria Garcia"}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(funnel={"docs": 51, "distinct_types": 8}, client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match"},
        extracted_name="MARIA GARCIA",
    )
    assert v["concordant"] is False
    assert "funnel/transit" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_rejects_group_context(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 42}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="0812...",
        source_context={
            "chat_type": "group",
            "routing_identity_policy": "group_participant_phone_suppressed",
        },
        reason={"reason": "sender phone match (legacy row)"},
    )
    assert v["concordant"] is False
    assert "direct-chat" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_rejects_unknown_doc_type(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 42}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="unknown",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match (no strong identifier, no fuzzy name >= 0.40)"},
    )
    assert v["concordant"] is False
    assert "no Kita category" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_rejects_subject_mismatch(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 42}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={
            "reason": "sender phone matched a FORWARDER, not the OCR subject",
            "sender_subject_mismatch": True,
        },
    )
    assert v["concordant"] is False
    assert "forwarder" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_rejects_shared_phone(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 42}, {"id": 99}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match (no strong identifier, no fuzzy name >= 0.40)"},
    )
    assert v["concordant"] is False
    assert v["phone_match_count"] == 2
    assert "shared" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_direct_phone_rejects_phone_disagreement(monkeypatch):
    _patch_phone(monkeypatch, [{"id": 99}])
    v = await auto_attach.evaluate_direct_phone_concordance(
        _StubConn(),
        decision="LINK_CANDIDATE",
        client_id=42,
        doc_type="passport",
        sender_phone="0812...",
        source_context=_DIRECT_SOURCE_CONTEXT,
        reason={"reason": "sender phone match (no strong identifier, no fuzzy name >= 0.40)"},
    )
    assert v["concordant"] is False
    assert v["phone_client_id"] == 99
    assert "DISAGREE" in v["reason"]


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


@pytest.mark.asyncio
async def test_try_direct_phone_auto_attach_noop_when_killswitch_off(monkeypatch):
    monkeypatch.delenv("INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED", raising=False)
    proposal = {
        "id": 1,
        "routing": {"client_id": 42, "doc_type": "passport"},
        "entity_resolution": {"decision": "LINK_CANDIDATE"},
    }
    out = await auto_attach.try_direct_phone_auto_attach(
        proposal,
        pool=None,
        sender_phone="0812",
        source_context=_DIRECT_SOURCE_CONTEXT,
    )
    assert out["committed"] is False
    assert out["skipped"] == "direct_phone_killswitch_off"


@pytest.mark.asyncio
async def test_try_direct_phone_auto_attach_noop_when_writer_off(monkeypatch):
    monkeypatch.setenv("INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED", "1")
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)
    proposal = {
        "id": 1,
        "routing": {"client_id": 42, "doc_type": "passport"},
        "entity_resolution": {"decision": "LINK_CANDIDATE"},
    }
    out = await auto_attach.try_direct_phone_auto_attach(
        proposal,
        pool=None,
        sender_phone="0812",
        source_context=_DIRECT_SOURCE_CONTEXT,
    )
    assert out["committed"] is False
    assert out["skipped"] == "writer_off"


# --------------------------------------------------------------------------- #
# _extracted_subject_name — FASE-3 stores fields as {"value": X, "confidence": ..}
# (extract.py); the raw scalar shape comes from HITL overrides. Both must yield
# the bare name — str() on the dict would tokenize {"value","confidence"} noise
# into every LEVA-3 name comparison (fixed 2026-07-19; this pins it).
# --------------------------------------------------------------------------- #
def test_extracted_subject_name_unwraps_fase3_value_dict():
    so = {
        "extract": {
            "fields": {"name": {"value": "MARIA ROSSI", "confidence": 0.9, "source_page": 1}}
        }
    }
    assert auto_attach._extracted_subject_name(so) == "MARIA ROSSI"


def test_extracted_subject_name_accepts_flat_scalar_and_missing():
    assert (
        auto_attach._extracted_subject_name({"extract": {"fields": {"name": "MARIA ROSSI"}}})
        == "MARIA ROSSI"
    )
    assert auto_attach._extracted_subject_name({"extract": {"fields": {}}}) is None
    assert auto_attach._extracted_subject_name({}) is None
    assert auto_attach._extracted_subject_name({"extract": {"fields": {"name": {"value": ""}}}}) is None
    assert (
        auto_attach._extracted_subject_name({"extract": {"fields": {"name": {"value": None}}}})
        is None
    )


# --------------------------------------------------------------------------- #
# _fresh_vs_locked_divergence — round-3 F3: an EXPLICIT fresh client_id=None is
# a real fresh value (unresolved target) and must diverge from a locked client;
# only a payload with NO fresh resolution at all skips the check.
# --------------------------------------------------------------------------- #
def test_divergence_explicit_none_client_diverges():
    reason = auto_attach._fresh_vs_locked_divergence(
        {"routing": {"client_id": None}, "entity_resolution": {"decision": "AUTO_ATTACH"}},
        "AUTO_ATTACH",
        42,
    )
    assert reason is not None and "diverges" in reason


def test_divergence_id_only_caller_skips():
    assert auto_attach._fresh_vs_locked_divergence({"id": 7}, "AUTO_ATTACH", 42) is None


def test_divergence_matching_payload_passes():
    assert (
        auto_attach._fresh_vs_locked_divergence(
            {"routing": {"client_id": 42}, "entity_resolution": {"decision": "AUTO_ATTACH"}},
            "AUTO_ATTACH",
            42,
        )
        is None
    )


@pytest.mark.asyncio
async def test_lock_busy_timeout_is_benign_skip(monkeypatch):
    """Round-5 F9: a bounded advisory-lock wait that expires must surface as a
    BENIGN skip (proposal untouched), never as an exception that burns worker
    retry attempts toward poison-pill."""

    async def _boom(proposal, pool, *, sender_phone):
        raise TimeoutError("lock wait exceeded")

    monkeypatch.setattr(auto_attach, "_try_auto_attach_inner", _boom)
    out = await auto_attach.try_auto_attach({"id": 9}, None, sender_phone="0812")
    assert out == {"committed": False, "skipped": "strong_id_lock_busy", "proposal_id": 9}

    async def _boom3(proposal, pool):
        raise TimeoutError("lock wait exceeded")

    monkeypatch.setattr(auto_attach, "_try_nameid_auto_attach_inner", _boom3)
    out3 = await auto_attach.try_nameid_auto_attach({"id": 11}, None)
    assert out3 == {"committed": False, "skipped": "strong_id_lock_busy", "proposal_id": 11}


def test_strong_id_lock_key_converges_across_formatting():
    """Round-4 F2 guilt: the gate locks the NORMALIZED value while a writer may
    hold the FORMATTED variant — both must project to the SAME lock key, or the
    advisory serialization silently misses (different hash, no contention)."""
    from backend.services.intake.client_enricher import strong_id_lock_value

    assert strong_id_lock_value("kitas", "2C-123.456/AB") == strong_id_lock_value(
        "kitas", "2C123456AB"
    )
    assert strong_id_lock_value("passport", "x 123-456") == strong_id_lock_value(
        "passport", "X123456"
    )
    assert strong_id_lock_value("npwp", "01.234.567.8-901.234") == strong_id_lock_value(
        "npwp", "012345678901234"
    )


def test_matched_value_validity_mirrors_matcher():
    # npwp: exactly 15/16 ASCII digits, already canonical
    assert auto_attach._matched_value_is_valid("npwp", "0" * 15)
    assert auto_attach._matched_value_is_valid("npwp", "1" * 16)
    assert not auto_attach._matched_value_is_valid("npwp", "9" * 14)  # F4 guilt
    assert not auto_attach._matched_value_is_valid("npwp", "0" * 17)
    assert not auto_attach._matched_value_is_valid("npwp", "01.234.567.8-901.234")
    # passport/kitas: must already BE the normalized projection
    assert auto_attach._matched_value_is_valid("passport_number", "X123456")
    assert not auto_attach._matched_value_is_valid("passport_number", "x 123-456")
    assert not auto_attach._matched_value_is_valid("kitas_number", "")


# --------------------------------------------------------------------------- #
# LEVA 3 — name-id concordance for NO-PHONE sources (Drive/Dropbox bulk).
# Second signal = OCR-extracted subject name vs CRM client name; a present,
# resolving sender phone is LEVA 2 territory and must NEVER be overruled here.
# --------------------------------------------------------------------------- #
def test_nameid_auto_attach_disabled_by_default(monkeypatch):
    monkeypatch.delenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", raising=False)
    assert auto_attach.nameid_auto_attach_enabled() is False


def test_nameid_auto_attach_enabled_when_truthy(monkeypatch):
    for val in ("1", "true", "yes", "on", "ON"):
        monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", val)
        assert auto_attach.nameid_auto_attach_enabled() is True


def test_nameid_auto_attach_disabled_when_falsy(monkeypatch):
    for val in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", val)
        assert auto_attach.nameid_auto_attach_enabled() is False


@pytest.mark.asyncio
async def test_guilt_nameid_no_phone_strong_id_and_name_agree(monkeypatch):
    """Drive doc: NO sender phone, strong-id→1 client, doc subject name matches
    the client name (order-insensitive) → concordant. The one case LEVA 3 exists for."""
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="AUTO_ATTACH",
        client_id=42,
        sender_phone=None,
        extracted_name="GARCIA MARIA",
    )
    assert v["concordant"] is True


@pytest.mark.asyncio
async def test_innocence_nameid_resolving_phone_defers_to_leva2(monkeypatch):
    """A sender phone that resolves to ANY client — even the SAME one, agreeing —
    keeps this gate shut: phone concordance (LEVA 2) owns every present-phone
    verdict (agree/disagree/shared) and name evidence never overrules it."""
    _patch_phone(monkeypatch, [{"id": 42, "full_name": "Maria Garcia"}])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="AUTO_ATTACH",
        client_id=42,
        sender_phone="0812...",
        extracted_name="GARCIA MARIA",
    )
    assert v["concordant"] is False
    assert "phone" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_nameid_name_mismatch_abstains(monkeypatch):
    """strong-id→client 42 but the document's subject is someone else → review."""
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="AUTO_ATTACH",
        client_id=42,
        sender_phone=None,
        extracted_name="JOHN SMITH",
    )
    assert v["concordant"] is False
    assert "name not concordant" in v["reason"]


@pytest.mark.asyncio
async def test_innocence_nameid_no_extractable_name_abstains(monkeypatch):
    """ktp/bank_statement carry no extractable subject name → unverifiable → review."""
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="AUTO_ATTACH",
        client_id=42,
        sender_phone=None,
        extracted_name=None,
    )
    assert v["concordant"] is False


@pytest.mark.asyncio
async def test_innocence_nameid_client_without_name_abstains(monkeypatch):
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name=None),
        decision="AUTO_ATTACH",
        client_id=42,
        sender_phone=None,
        extracted_name="GARCIA MARIA",
    )
    assert v["concordant"] is False


@pytest.mark.asyncio
async def test_innocence_nameid_not_auto_attach_decision(monkeypatch):
    """LINK_CANDIDATE/NO_MATCH never enter LEVA 3 — strong identifier is signal #1."""
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="LINK_CANDIDATE",
        client_id=42,
        sender_phone=None,
        extracted_name="GARCIA MARIA",
    )
    assert v["concordant"] is False


@pytest.mark.asyncio
async def test_innocence_nameid_unresolved_client_abstains(monkeypatch):
    _patch_phone(monkeypatch, [])
    v = await auto_attach.evaluate_nameid_concordance(
        _StubConn(client_name="Maria Garcia"),
        decision="AUTO_ATTACH",
        client_id=None,
        sender_phone=None,
        extracted_name="GARCIA MARIA",
    )
    assert v["concordant"] is False


@pytest.mark.asyncio
async def test_try_nameid_auto_attach_noop_when_killswitch_off(monkeypatch):
    monkeypatch.delenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", raising=False)
    proposal = {"id": 1, "routing": {"client_id": 42}, "entity_resolution": {"decision": "AUTO_ATTACH"}}
    out = await auto_attach.try_nameid_auto_attach(proposal, pool=None)
    assert out["committed"] is False
    assert out["skipped"] == "nameid_killswitch_off"


@pytest.mark.asyncio
async def test_try_nameid_auto_attach_noop_when_writer_off(monkeypatch):
    monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", "1")
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)
    proposal = {"id": 1, "routing": {"client_id": 42}, "entity_resolution": {"decision": "AUTO_ATTACH"}}
    out = await auto_attach.try_nameid_auto_attach(proposal, pool=None)
    assert out["committed"] is False
    assert out["skipped"] == "writer_off"
