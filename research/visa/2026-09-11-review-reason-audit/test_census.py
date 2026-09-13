from __future__ import annotations

import ast
import inspect
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.gold_coverage_eval import _verified_compiled_pack
from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR, _offline_identity_provider, _parse_utc, select_highest_repository_pack,
)
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.api_models import VisaOracleEvaluateRequest
from backend.services.visa_engine.crypto import FactsFingerprintKey
from backend.services.visa_engine.decision_seal import seal_decision
from backend.services.visa_engine.pricing_adapter import UnavailablePricingCatalog

ROOT = Path('/tmp/visaoracle-audit-20260911')


def test_fresh_census() -> None:
    inputs = json.loads((ROOT / 'inputs.json').read_text())
    _, signed = select_highest_repository_pack(PACKS_DIR)
    copy = inputs['review_copy']
    backend_codes = set(evaluate_path._DISCLOSED_REVIEW_REASON_CODES.values())
    # Discover literal Reason(code=...) emissions from the actual adapter AST.
    for node in ast.walk(ast.parse(inspect.getsource(evaluate_path))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Reason':
            for keyword in node.keywords:
                if keyword.arg == 'code' and isinstance(keyword.value, ast.Constant):
                    backend_codes.add(keyword.value.value)
    pack_codes = {r['effect']['reason_code'] for r in signed['payload']['rules']
                  if (r['stage'] == 'HUMAN_REVIEW' or r['on_unknown'] == 'HUMAN_REVIEW')
                  and 'reason_code' in r['effect']}
    codes = sorted(pack_codes | backend_codes)
    result: dict[str, Any] = {
        'pack': {k: signed['payload'][k] for k in ('sequence', 'version', 'rule_pack_id')},
        'taxonomy': {'pack': sorted(pack_codes), 'backend': sorted(backend_codes),
                     'mapped': sorted(set(codes) & copy.keys()),
                     'unmapped': sorted(set(codes) - copy.keys()),
                     'stale_map_keys': sorted(copy.keys() - set(codes))},
        'clocks': {},
    }
    for clock, now in [('signed_at', _parse_utc(signed['protected']['signed_at'])),
                       ('current', datetime.now(UTC))]:
        _, compiled = _verified_compiled_pack(now)
        rows = []
        for row in inputs['rows']:
            request = VisaOracleEvaluateRequest.model_validate(row['request'])
            facts = request.applicant_facts()
            raw = evaluator.evaluate(facts, compiled, effective_at=now, observed_at=now,
                                     identity_provider=_offline_identity_provider)
            baseline = evaluate_path.apply_public_policy_adapters(raw, facts, compiled, disclosed_review_flags=())
            decision = evaluate_path.apply_public_policy_adapters(raw, facts, compiled,
                                          disclosed_review_flags=request.effective_review_flags())
            decision = seal_decision(decision, key=FactsFingerprintKey(
                kid='offline-copy-audit-non-secret', secret=b'offline-copy-audit-non-secret-key-20260911',
                environment=compiled.environment, valid_from=now, valid_to=None, revoked_at=None))
            envelope = {
                'mode': 'ENGINE', 'decision': decision.model_dump(mode='json'),
                'sources': evaluate_path._build_sources_dto(decision, compiled, request_trace='synthetic-copy-audit'),
                'display': evaluate_path._build_display(decision, compiled, request_trace='synthetic-copy-audit',
                                                        pricing_catalog=UnavailablePricingCatalog()),
            }
            rows.append({'label': row['label'], 'flags': [f.value for f in request.effective_review_flags()],
                         'baseline_state': baseline.state.value, 'state': decision.state.value,
                         'review_codes': [r.code for r in decision.review_reasons],
                         'missing_facts': [f.value for f in decision.missing_facts],
                         'envelope': envelope})
        sample = [r for r in rows if not r['label'].startswith('edge/')]
        result['clocks'][clock] = {'as_of': now.isoformat(),
            'baseline_census': dict(Counter(r['baseline_state'] for r in sample)),
            'public_census': dict(Counter(r['state'] for r in sample)),
            'review_frequency': dict(Counter(c for r in sample for c in r['review_codes'])), 'rows': rows}
    (ROOT / 'census.json').write_text(json.dumps(result, indent=2) + '\n')
    assert len(inputs['rows']) == 72
