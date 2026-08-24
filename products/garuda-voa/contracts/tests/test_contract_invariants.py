"""The contract freeze, made re-runnable.

The round-1 adversarial review established a set of properties by hand. A property
established by hand once is a property that decays, and seven build lanes plus a second
product on another machine are about to be written against these files — so every
invariant that mattered enough to check is pinned here instead of living in a report.

Two of these tests exist because the review found the property BROKEN, not because it was
fine: the late-payment remediation path (`test_both_late_payment_outcomes_are_expressible`)
and the privacy headers (`test_every_public_response_carries_the_privacy_headers`). Do not
relax either one to make a diff pass — the first is money a customer really paid, and the
second is the difference between a checkout URL that caches and one that does not.

Deliberately mechanical: everything here parses the YAML (which expands the anchors) or
imports the Python enum. A regex over the source would agree with a file that does not mean
what it says.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

CONTRACTS = Path(__file__).resolve().parents[1]
PUBLIC_FLAG = "GARUDA_PUBLIC_ENABLED"
PRIVACY_HEADERS = ("Cache-Control", "Referrer-Policy", "X-Robots-Tag")
HTTP_VERBS = ("get", "post", "put", "patch", "delete")


def _load(name: str) -> dict:
    path = CONTRACTS / name
    assert path.is_file(), f"{path} is missing — the contract lost a file"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def openapi() -> dict:
    return _load("openapi.yaml")


@pytest.fixture(scope="module")
def errors() -> dict:
    return _load("errors.yaml")


@pytest.fixture(scope="module")
def events() -> dict:
    return _load("events.yaml")


def _operations(openapi: dict):
    for route, item in openapi["paths"].items():
        for verb, op in item.items():
            if verb in HTTP_VERBS:
                yield route, verb, op


def _collect(node, key: str, out: set) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, list):
                out.update(v)
            else:
                _collect(v, key, out)
    elif isinstance(node, list):
        for item in node:
            _collect(item, key, out)


def test_every_public_response_carries_the_privacy_headers(openapi: dict) -> None:
    """Round 1 found these on 3 operations out of 8.

    The eligibility surface had them and the checkout surface did not, which left
    `OrderCheckout.checkout_url`, order and practice state, and document metadata with no
    contractual no-store / no-referrer / no-index guarantee. Uniform coverage is asserted
    rather than a curated subset, so a new operation cannot be added without inheriting it.
    """
    missing = [
        f"{op['operationId']} {status}"
        for _route, _verb, op in _operations(openapi)
        if op.get("x-feature-flag") == PUBLIC_FLAG
        for status, response in op["responses"].items()
        if not all(h in (response.get("headers") or {}) for h in PRIVACY_HEADERS)
    ]
    assert not missing, f"public responses without the full privacy header set: {missing}"


def test_error_codes_and_catalogue_match_exactly(openapi: dict, errors: dict) -> None:
    """Both directions. A used-but-undeclared code is an error a client cannot parse; a
    declared-but-dead one is a promise nothing keeps. Round 1 found two dead webhook codes
    mid-review."""
    catalogue = {
        branch["properties"]["code"]["const"]
        for branch in errors["$defs"]["ErrorResponse"]["oneOf"]
    }
    used: set[str] = set()
    _collect(openapi, "x-error-codes", used)
    assert used - catalogue == set(), f"used but undeclared: {sorted(used - catalogue)}"
    assert catalogue - used == set(), f"declared but dead: {sorted(catalogue - used)}"


def test_every_ref_resolves(openapi: dict, errors: dict, events: dict) -> None:
    """Includes the cross-file refs into errors.yaml and reason-codes.yaml.

    The `os.path.basename` is load-bearing: refs are written `./errors.yaml#/...`, and a
    checker that keys on the raw string reports every one of them unresolved. That false
    alarm happened once already; suspect the probe before the world.
    """
    docs = {
        p.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in CONTRACTS.glob("*.yaml")
    }

    def resolves(doc: dict, fragment: str) -> bool:
        cursor = doc
        for raw in (p for p in fragment.split("/") if p and p != "#"):
            part = raw.replace("~1", "/").replace("~0", "~")
            if not isinstance(cursor, dict) or part not in cursor:
                return False
            cursor = cursor[part]
        return True

    broken: list[str] = []
    seen = 0

    def walk(node, origin: str) -> None:
        nonlocal seen
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str):
                    seen += 1
                    filename, _, fragment = value.partition("#")
                    target = docs.get(os.path.basename(filename)) if filename else docs[origin]
                    if target is None or not resolves(target, fragment):
                        broken.append(f"{origin}: {value}")
                else:
                    walk(value, origin)
        elif isinstance(node, list):
            for item in node:
                walk(item, origin)

    for name, doc in docs.items():
        walk(doc, name)

    assert seen > 100, f"only {seen} refs walked — the walker stopped finding them"
    assert not broken, f"unresolved refs: {broken}"


def test_the_price_is_one_field_and_never_a_computation(openapi: dict) -> None:
    """The mandate's own seed text carried a formula (PNBP + 3jt) that quoted roughly 4.4x
    the catalogue price. The contract must not be able to express a split at all: one
    integer, no components, no fee line, no tax line."""
    schemas = openapi["components"]["schemas"]
    checkout = schemas["OrderCheckout"]["properties"]
    assert "price_idr" in checkout, "OrderCheckout lost its price field"
    assert checkout["price_idr"]["type"] == "integer"
    assert checkout["price_idr"]["minimum"] >= 1

    banned = ("fee", "pnbp", "subtotal", "discount", "surcharge", "breakdown", "component")
    offenders = [
        f"{name}.{prop}"
        for name, schema in schemas.items()
        if isinstance(schema, dict)
        for prop in (schema.get("properties") or {})
        if any(word in prop.lower() for word in banned)
    ]
    assert not offenders, f"price-splitting vocabulary reached a schema: {offenders}"


def test_both_late_payment_outcomes_are_expressible(openapi: dict, events: dict) -> None:
    """DECISIONS.md Q2: staff take exactly one of two paths — honour the order, or refund in
    full. Never neither.

    Round 1 found `payment.late_paid_after_terminal` missing entirely, so money arriving
    after we had told a customer "expired" had no wire-representable resolution at all. A
    contract that can express neither outcome makes "neither" the default.
    """
    defs = events["$defs"]
    assert "PaymentLatePaidAfterTerminal" in defs, "the OP-F05 event is gone again"
    assert "LateOrderResolved" in defs, "the resolution event is gone again"

    ids = defs["TransitionId"]["enum"]
    assert "OP-F04" in ids and "OP-F05" in ids, (
        "the forbidden-input recovery ids left the enum — both late-paid events become "
        "uninhabitable the moment they do (DECISIONS.md Q10)"
    )

    op = next(
        o for _r, _v, o in _operations(openapi) if o.get("operationId") == "resolveLateOrder"
    )
    body = op["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    outcomes = openapi["components"]["schemas"][body]["properties"]["resolution"]["enum"]
    assert sorted(outcomes) == ["honoured", "refunded_in_full"], (
        f"the two permitted outcomes changed to {outcomes} — Q2 forbids a third, and "
        "forbids removing either"
    )


def test_the_anonymous_check_carries_no_pii(openapi: dict) -> None:
    """Architecture D1: the public eligibility route and the identified order are separate
    data domains. Migration 261's header argues that the ABSENCE of PII is itself the safety
    property that lets the route be public — so a new field here is not a small change."""
    request = openapi["components"]["schemas"]["EligibilityCheckRequest"]
    fields = set(request["properties"])
    forbidden = {
        "name",
        "full_name",
        "email",
        "phone",
        "passport_number",
        "passport_no",
        "address",
    }
    assert not fields & forbidden, (
        f"PII reached the unauthenticated eligibility request: {sorted(fields & forbidden)}"
    )
    assert request.get("additionalProperties") is False, (
        "the anonymous request stopped being a closed object — anything can be posted into it"
    )


def test_every_mutating_operation_requires_an_idempotency_key(openapi: dict) -> None:
    offenders = []
    for _route, verb, op in _operations(openapi):
        if verb == "get":
            continue
        params = op.get("parameters") or []
        refs = [p.get("$ref", "") for p in params if isinstance(p, dict)]
        if not any(r.endswith("/IdempotencyKey") for r in refs):
            offenders.append(op["operationId"])
    assert not offenders, f"mutating operations without Idempotency-Key: {offenders}"


def test_every_inbound_date_states_its_civil_day(openapi: dict) -> None:
    """The engine already carries this scar: the backend runs on Fly.io in UTC, and reading a
    Bali civil day as a UTC day moves the ACCEPT/DECLINE cutoff and the published deadline by
    a full day for the first eight hours of every Bali day. `civil_clock.py::garuda_today`
    cured it inside the engine; a `format: date` with nothing said about which day it means
    lets it back in through the wire."""
    offenders = []
    for name, schema in openapi["components"]["schemas"].items():
        if not isinstance(schema, dict):
            continue
        for prop, spec in (schema.get("properties") or {}).items():
            if not isinstance(spec, dict) or spec.get("format") != "date":
                continue
            stated = spec.get("x-civil-timezone") or ""
            if "Asia/Makassar" not in (stated + spec.get("description", "")):
                offenders.append(f"{name}.{prop}")
    assert not offenders, f"date fields that never say which civil day they mean: {offenders}"


def test_the_prose_decisions_are_machine_readable(openapi: dict) -> None:
    """Q1 and Q9 were decided in prose, and prose binds nobody.

    The money/date re-derivation found that an implementer could ship any magic-link TTL and
    stay contract-valid, and that `G-FRESHNESS-FAIL-CLOSED` — a declared guardrail — had no
    numbers to fail closed on. A guardrail whose threshold does not exist is not a guardrail;
    it is a sentence. These assertions are what turn the sentences into a contract.
    """
    link = openapi["x-magic-link"]
    assert link["ttl_minutes"] == 15, "Q1's magic-link lifetime moved without a decision"
    assert link["single_use"] is True

    fresh = openapi["x-truth-freshness-max-age-days"]
    assert fresh == {
        "nationality_eligibility": 90,
        "rule_constants": 180,
        "price_catalogue": 90,
    }, f"Q9's freshness windows changed to {fresh} — revisable, but not silently"

    codes: set = set()
    _collect(openapi, "x-error-codes", codes)
    assert "TRUTH_SHEET_STALE" in codes, (
        "the windows exist but nothing declines on them — the guardrail is prose again"
    )
