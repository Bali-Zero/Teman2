"""Falsifiable tests for the P2 confine-PII router (privacy_preflight).

CRITICO-2 / Pezzo 2 — MVL Step B+C. Enforces Symbiosis Law 2 (no client PII
to cloud LLMs) as a multi-strato, default-DENY gate in front of every cloud
dispatch.

ALL PII in this file is SYNTHETIC. No real client data ever appears here
(Law 2: test only with fake/synthetic PII). The 16-digit "KTP", the "+62"
phone and the "Budi Santoso" name are invented.

Run:  cd scripts && ../apps/backend-rag/.venv/bin/python -m pytest test_privacy_preflight.py -q
"""

from __future__ import annotations

import json


from _redact_pii import DynamicNameLoadError, Redactor, load_config
from privacy_preflight import (
    CLOUD_SAFE_TASK_TYPES,
    Decision,
    Route,
    privacy_preflight,
)

# --- synthetic PII fixtures (invented, never real) -------------------------
SYNTH_KTP = "3171234567890123"  # 16 digits, fake KTP/NIK
SYNTH_NPWP_DOTTED = "09.876.543.2-109.000"  # fake NPWP new-format dotted
SYNTH_PHONE_62 = "+6281234567890"  # fake +62 phone
SYNTH_PASSPORT = "AB1234567"  # fake passport
SYNTH_NAME = "Budi Santoso"  # fake CRM client name
PAD = " lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod " * 3


class _CleanRedactor:
    """A redactor that finds no PII (returns text unchanged)."""

    def redact(self, text: str) -> str:
        return text


class _ModifyingRedactor:
    """A redactor that detects a synthetic name and tokenises it."""

    def redact(self, text: str) -> str:
        return text.replace("budi santoso", "[CRM-NAME-REDACTED]").replace(
            SYNTH_NAME, "[CRM-NAME-REDACTED]"
        )


class _RaisingRedactor:
    """A redactor that fails-closed (simulates PG-down on cloud-egress)."""

    def redact(self, text: str) -> str:
        raise DynamicNameLoadError("PG expected but unreachable — fail-CLOSED")


def _real_redactor_with_names(names: list[str]) -> Redactor:
    """Real Redactor with synthetic CRM names injected (no PG needed)."""
    return Redactor(
        config=load_config(),
        runtime_names={
            "__DYNAMIC_CRM_CLIENT_NAMES__": names,
            "__DYNAMIC_CRM_COMPANY_NAMES__": [],
        },
    )


# === STRATO B — deterministic regex backstop (acceptance #1) ===============


def test_synthetic_ktp_routes_local():
    d = privacy_preflight(
        f"Refactor this module. {SYNTH_KTP} {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"
    assert "KTP" in (d.blocked_reason or "")


def test_npwp_dotted_routes_local():
    d = privacy_preflight(
        f"Analyse {SYNTH_NPWP_DOTTED} {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_phone_62_routes_local():
    d = privacy_preflight(
        f"Contact {SYNTH_PHONE_62} {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_passport_routes_local():
    d = privacy_preflight(
        f"Passport {SYNTH_PASSPORT} for the visa case {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


# === STRATO B — panel-hardened false-negatives (DeepSeek §3 / Codex §4) ====


def test_ktp_with_spaces_routes_local():
    d = privacy_preflight(
        f"id is 3171 2345 6789 0123 here {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_npwp_plain_15_digits_routes_local():
    d = privacy_preflight(
        f"the number 123456789012345 must stay local {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_phone_62_with_separators_routes_local():
    d = privacy_preflight(
        f"reach +62 812-3456-7890 now {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_passport_lowercase_routes_local():
    d = privacy_preflight(
        f"doc ab1234567 attached {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_whatsapp_jid_routes_local():
    d = privacy_preflight(
        f"sender 6281234567890@s.whatsapp.net pinged {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_passport_with_space_routes_local():
    # DeepSeek round-2 bypass: separator between LETTER and digit.
    d = privacy_preflight(
        f"doc A 1234567 attached for review {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "regex_backstop"


def test_spreadsheet_separator_ids_route_local():
    # M5 24-agent review: a real Law-2 leak — IDs/phones pasted from a
    # spreadsheet with comma / underscore / slash / NBSP / zero-width separators
    # were NOT normalized ([ .-] only) so \b\d{16}\b never matched → CLOUD.
    # Each of these synthetic IDs must now route LOCAL (raw AND with a built
    # redactor; here a CLEAN redactor proves the structured backstop alone gates
    # it). KTP=16 digits, NPWP=15 digits, phone=08+10.
    seps = [",", "_", "/", " ", "​", " ", "﻿"]
    for sep in seps:
        ktp = sep.join(["3171", "2345", "6789", "0123"])  # 16 digits
        npwp = sep.join(["123", "456", "789", "012", "345"])  # 15 digits
        phone = sep.join(["0812", "3456", "7890"])  # 08 + 10 digits
        for sample in (ktp, npwp, phone):
            d = privacy_preflight(
                f"pasted value {sample} from the sheet {PAD}",
                task_type="SYNTHETIC_TEST",
                redactor=_CleanRedactor(),
            )
            assert d.route is Route.LOCAL, (repr(sep), sample)
            assert d.layer == "regex_backstop", (repr(sep), sample)


def test_numeric_prose_not_overcollapsed_to_false_local():
    # the broad separator class must NOT merge alphabetic prose between numbers
    # into a false ID (would needlessly route legit tasks LOCAL).
    d = privacy_preflight(
        f"we processed 4 batches and 8 jobs across 12 nodes with 90 workers {PAD}",
        task_type="ARCHITECTURE_META",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.CLOUD


# === STRATO B+ — PII-context backstop (panel F1: bare-name leak) ============


def test_bare_crm_name_with_client_context_routes_local():
    # The council's exact bypass class: a CRM name with PG out of scope. Even
    # with a CLEAN (degraded) redactor, the "client" context word forces LOCAL.
    d = privacy_preflight(
        f"please analyse the account of our client {SYNTH_NAME} {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),  # degraded: finds nothing
    )
    assert d.route is Route.LOCAL
    assert d.layer == "context_backstop"


def test_honorific_name_routes_local():
    d = privacy_preflight(
        f"fix the case for Pak Budi today {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "context_backstop"


def test_id_context_word_routes_local():
    d = privacy_preflight(
        f"the customer sent their NPWP for review {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "context_backstop"


def test_saudara_honorific_routes_local():
    # DeepSeek round-2: "Saudara <name>" is common in ID client comms.
    d = privacy_preflight(
        f"draft a reply to Saudara Budi about the schedule {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "context_backstop"


def test_context_free_clean_prompt_still_cloud():
    # A genuinely PII-free architecture prompt (no ID, no context word) → CLOUD.
    d = privacy_preflight(
        f"refactor the retry loop to use exponential backoff {PAD}",
        task_type="ARCHITECTURE_META",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.CLOUD


def test_context_word_at_prompt_start_routes_local():
    # Codex round-2 / W73: a context word at the START of the prompt (no leading
    # space) must still match (word-boundary, not space-hack).
    d = privacy_preflight(
        f"SKCK Budi Santoso needs processing {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "context_backstop"


def test_honorific_with_punctuation_routes_local():
    # Codex round-2: "Pak, Budi" (comma after the honorific) must match.
    d = privacy_preflight(
        f"Pak, Budi Santoso called about the case {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "context_backstop"


def test_context_words_no_false_positive_inside_words():
    # word-boundary must NOT match "pak" in "package" nor "ms" in "500 ms"
    # (ms was deliberately dropped as a bare token to avoid the perf-unit FP).
    for clean in (
        "update the npm package and rerun the build pipeline",
        "the p99 latency dropped to 500 ms after the patch",
    ):
        d = privacy_preflight(
            f"{clean} {PAD}", task_type="ARCHITECTURE_META", redactor=_CleanRedactor()
        )
        assert d.route is Route.CLOUD, clean


# === STRATO A — whitelist-positiva / default-DENY ==========================


def test_clean_whitelisted_prompt_routes_cloud():
    d = privacy_preflight(
        f"Compare Kafka vs SQS for the event bus. {PAD}",
        task_type="ARCHITECTURE_META",
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.CLOUD
    assert d.layer == "clean"
    assert d.blocked_reason is None


def test_non_whitelisted_task_routes_local():
    d = privacy_preflight(
        f"Deploy with these credentials {PAD}",
        task_type="DEPLOY_SECRET",  # not in whitelist
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "whitelist"


def test_undeclared_clean_content_routes_cloud():
    # run_dispatch path: task_type=None → skip whitelist, gate on content only.
    d = privacy_preflight(
        f"Summarise the architecture of the dispatch layer. {PAD}",
        task_type=None,
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.CLOUD


def test_undeclared_strict_default_deny_routes_local():
    d = privacy_preflight(
        f"Summarise something. {PAD}",
        task_type=None,
        strict_default_deny=True,
        redactor=_CleanRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "whitelist"


def test_whitelist_membership_is_positive():
    # whitelist must be POSITIVE (named cloud-safe types), not a PII blacklist.
    assert "ARCHITECTURE_META" in CLOUD_SAFE_TASK_TYPES
    assert "SYNTHETIC_TEST" in CLOUD_SAFE_TASK_TYPES
    assert "CRM_CLIENT" not in CLOUD_SAFE_TASK_TYPES


# === STRATO C — redactor fail-closed (acceptance #2 + #3) ==================


def test_redactor_db_down_strict_fail_closed():
    # acceptance #2: a redactor that REFUSES (raises) on the cloud-egress
    # (strict) path → fail-CLOSED, NEVER returns the un-redacted prompt.
    d = privacy_preflight(
        f"Some clean-looking task {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_RaisingRedactor(),
        require_redactor=True,
    )
    assert d.route is Route.LOCAL
    assert d.layer == "redactor"
    reason = (d.blocked_reason or "").lower()
    assert "refused" in reason or "fail" in reason


def test_redactor_build_failure_strict_fail_closed():
    # acceptance #2 (literal DB-down-at-load): the redactor cannot even be
    # BUILT (Redactor.load_default raises DynamicNameLoadError when PG is
    # expected-but-down) → fail-CLOSED on the strict cloud-egress path.
    def _factory(_strict):
        raise DynamicNameLoadError("PG expected but down at load")

    d = privacy_preflight(
        f"Some clean-looking task {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor_factory=_factory,
        require_redactor=True,
    )
    assert d.route is Route.LOCAL
    assert d.layer == "redactor"
    assert "failclosed" in (d.blocked_reason or "").lower()


def test_redactor_build_failure_degraded_falls_through_to_regex():
    # degraded (non-strict) MVL posture: redactor build fails (PG out of scope)
    # but a CLEAN prompt with no regex-PII still reaches CLOUD — regex remained
    # the hard gate, the redactor gap is logged not fatal.
    def _factory(_strict):
        raise DynamicNameLoadError("PG out of scope at load")

    d = privacy_preflight(
        f"Explain the event-bus durability trade-offs {PAD}",
        task_type="ARCHITECTURE_META",
        redactor_factory=_factory,
        require_redactor=False,
    )
    assert d.route is Route.CLOUD


def test_redactor_db_down_non_strict_still_local_on_raise():
    # Even in degraded (non-strict) mode, a redactor that RAISES is a strong
    # PII signal → LOCAL. (Only redactor *build* failure degrades silently.)
    d = privacy_preflight(
        f"Some clean-looking task {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_RaisingRedactor(),
        require_redactor=False,
    )
    assert d.route is Route.LOCAL


def test_redactor_modifies_prompt_routes_local():
    # Codex §7.2.1: if the redactor CHANGES the text, PII was present →
    # cloud-vietato.
    d = privacy_preflight(
        f"Fix the bug for {SYNTH_NAME} {PAD}",
        task_type="SYNTHETIC_TEST",
        redactor=_ModifyingRedactor(),
    )
    assert d.route is Route.LOCAL
    assert d.layer == "redactor"
    assert d.blocked_reason == "redactor_found_pii"


def test_crm_name_lowercase_ignorecase_end_to_end():
    # acceptance #3: a CRM name that arrives LOWERCASE (typical WhatsApp) must
    # still be caught by the real Redactor (FASE-2 IGNORECASE fix), end-to-end
    # through the preflight → LOCAL.
    real = _real_redactor_with_names([SYNTH_NAME])
    prompt = f"please review the case for budi santoso and update notes {PAD}"
    d = privacy_preflight(prompt, task_type="SYNTHETIC_TEST", redactor=real)
    assert d.route is Route.LOCAL
    assert d.layer == "redactor"


def test_real_redactor_clean_prompt_routes_cloud():
    # Integration with the real Redactor (no PG, static-only): a genuinely
    # PII-free long prompt → CLOUD.
    real = _real_redactor_with_names([])
    prompt = (
        "Explain the trade-offs of consumer-group durability versus "
        "listen-notify for an event bus, with no client data involved. " + PAD
    )
    d = privacy_preflight(prompt, task_type="ARCHITECTURE_META", redactor=real)
    assert d.route is Route.CLOUD


# === fail-closed default posture ==========================================


def test_empty_prompt_routes_local():
    d = privacy_preflight("   ", task_type="SYNTHETIC_TEST", redactor=_CleanRedactor())
    assert d.route is Route.LOCAL


def test_internal_exception_fails_closed_local(monkeypatch):
    # ANY unexpected internal error must fail-closed to LOCAL, never leak.
    import privacy_preflight as pp

    def _boom(_prompt):
        raise RuntimeError("synthetic internal failure")

    monkeypatch.setattr(pp, "_structured_backstop", _boom)
    d = privacy_preflight(
        f"clean task {PAD}", task_type="SYNTHETIC_TEST", redactor=_CleanRedactor()
    )
    assert d.route is Route.LOCAL
    assert d.layer == "exception"


def test_default_route_is_local_on_ambiguity():
    # Decision dataclass default sanity + is_cloud helper.
    assert Decision(Route.LOCAL, "x").is_cloud is False
    assert Decision(Route.CLOUD, "clean").is_cloud is True


# === audit safety (Law 2: never log the raw prompt) ========================


def test_audit_writes_hash_not_raw_prompt(tmp_path):
    audit = tmp_path / "audit.jsonl"
    secret_prompt = f"client KTP {SYNTH_KTP} name {SYNTH_NAME} {PAD}"
    privacy_preflight(
        secret_prompt,
        task_type="SYNTHETIC_TEST",
        redactor=_CleanRedactor(),
        audit_path=audit,
    )
    raw = audit.read_text()
    # the raw PII must NOT appear in the audit log
    assert SYNTH_KTP not in raw
    assert SYNTH_NAME not in raw
    entry = json.loads(raw.strip().splitlines()[-1])
    assert "prompt_sha256_16" in entry
    assert entry["prompt_len"] == len(secret_prompt)


def test_audit_normalizes_untrusted_task_type(tmp_path):
    # panel F4: a caller could smuggle a name into task_type. The audit must
    # NOT echo a non-standard task_type verbatim.
    audit = tmp_path / "audit.jsonl"
    privacy_preflight(
        f"some task {PAD}",
        task_type="CLIENT_BUDI_SANTOSO",  # untrusted, name-shaped
        redactor=_CleanRedactor(),
        audit_path=audit,
    )
    raw = audit.read_text()
    assert "BUDI_SANTOSO" not in raw
    entry = json.loads(raw.strip().splitlines()[-1])
    assert entry["task_type"] == "<non-standard>"
    # the blocked reason must not interpolate the raw task_type either
    assert "BUDI" not in (entry["blocked_reason"] or "")
    assert entry["route"] == "local"
