"""F5: the signed envelope's protected header environment must equal the
payload's own declared environment before a CompiledRulePack is produced —
a TEST-signed header wrapping a PRODUCTION payload (or vice versa) is a
tamper/misconfiguration signal, not a legitimate pack.

Note: ProtectedHeader carries no jurisdiction/domain field comparable to
RulePackPayload's own `jurisdiction`/`decision_domain` (it has `domain`, a
fixed literal `"balizero.visa-rulepack.v1"` protocol tag, not a
jurisdiction) — so only `environment` equality is checked here.
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.compiler import compile_rule_pack
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import single_rule_envelope

_WHEN = {"op": "gt", "fact": "immigration.overstay_days", "value": 60}
_REQUIRED = ["immigration.overstay_days"]


def test_mismatched_header_and_payload_environment_rejected() -> None:
    envelope = single_rule_envelope(
        when=_WHEN,
        required_facts=_REQUIRED,
        environment="TEST",
        protected_environment="STAGING",
    )
    pack = RulePack(**envelope)
    with pytest.raises(RulePackCompilationError, match="environment"):
        compile_rule_pack(pack, fact_registry=FactRegistry())


def test_matching_header_and_payload_environment_compiles() -> None:
    envelope = single_rule_envelope(
        when=_WHEN,
        required_facts=_REQUIRED,
        environment="PRODUCTION",
        protected_environment="PRODUCTION",
    )
    pack = RulePack(**envelope)
    compiled = compile_rule_pack(pack, fact_registry=FactRegistry())
    assert compiled.environment == "PRODUCTION"
