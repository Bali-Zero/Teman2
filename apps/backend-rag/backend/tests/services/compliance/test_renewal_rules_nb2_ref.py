"""Ensure RenewalRule carries an NB-2 citation field (decision #9)."""
from __future__ import annotations

import dataclasses
import inspect

from backend.services.compliance.renewal_rules import RenewalRule


def test_renewal_rule_has_nb2_ref_field() -> None:
    fields = {f.name for f in dataclasses.fields(RenewalRule)}
    assert "nb2_ref" in fields


def test_nb2_ref_defaults_to_none_for_non_visa_rules() -> None:
    # Smoke: a minimal instance (args depend on actual RenewalRule shape)
    # Adapt kwargs based on existing RenewalRule signature.
    sig = inspect.signature(RenewalRule)
    kwargs: dict = {}
    for name, param in sig.parameters.items():
        if name == "nb2_ref":
            continue
        if param.default is inspect.Parameter.empty:
            # Provide sensible defaults by annotation
            annotation = param.annotation
            if annotation in (str, "str"):
                kwargs[name] = "x"
            elif annotation in (int, "int"):
                kwargs[name] = 0
            elif annotation in (float, "float"):
                kwargs[name] = 0.0
            elif annotation in (bool, "bool"):
                kwargs[name] = False
            else:
                kwargs[name] = None
    rule = RenewalRule(**kwargs)
    assert getattr(rule, "nb2_ref", ...) is None
