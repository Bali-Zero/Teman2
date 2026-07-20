"""Typed error taxonomy for the Visa Oracle v2 rule engine.

Base hierarchy is spec §1 ``errors.py`` verbatim (five classes). One class is
added beyond the spec's literal enumeration, documented below — every other
class in this file is exactly what the spec's module-layout snippet lists.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1.
"""

from __future__ import annotations


class VisaEngineError(Exception):
    """Base class for every error raised by ``backend.services.visa_engine``."""


class RulePackUnavailableError(VisaEngineError):
    """No active RulePack could be resolved for the requested environment/time.

    PR2+ concern (repository/bundle territory) — declared here now so the
    full taxonomy compiles and is importable from PR1 onward.
    """


class RulePackVerificationError(VisaEngineError):
    """A RulePack envelope failed signature/trust-store verification.

    PR2 concern (``bundle.py``) — declared here now for the same reason.
    """


class RulePackCompilationError(VisaEngineError):
    """Raised only when compilation cannot even attempt to produce a report
    (e.g. the fact registry itself is malformed). Ordinary per-rule/per-pack
    defects are *not* raised — they are collected into a
    ``compiler.CompilationReport`` instead, so a caller can see every problem
    in one pass rather than fixing them one Pydantic-exception at a time.
    """


class FactValidationError(VisaEngineError):
    """A fact path is not known to the ``FactRegistry``, or a value does not
    conform to its ``FactSpec`` (spec §1 ``fact_registry.py``).
    """


class PersistenceRequiredError(VisaEngineError):
    """An operation needed the repository layer, which does not exist yet in
    PR1 (``repository.py`` is PR4 scope). Declared now so callers can import
    the full taxonomy without knowing which PR introduced each class.
    """


class ConditionStructureError(VisaEngineError):
    """A condition AST violates a structural limit (depth/node count) or is
    otherwise mal-shaped independent of any fact registry or rule pack.

    Not present in spec §1's literal five-class ``errors.py`` snippet. Added
    because ``ast.py`` is a standalone, directly-testable module (spec's own
    test layout, §7, lists ``test_condition_ast.py`` as its own file) and
    needs an exception type that does not depend on ``compiler.py`` or
    ``fact_registry.py`` importing it back. ``compiler.py`` catches this
    exception per-rule and folds it into a non-raising ``CompilationReport``
    entry rather than letting it propagate — see that module's docstring.
    """


class PlaceholderIdentityNotAllowedError(VisaEngineError):
    """Raised by ``evaluator._placeholder_identity_provider`` when asked to
    fabricate a ``Decision``'s ``decision_id``/``public_id``/
    ``facts_fingerprint`` for a rule pack whose ``environment`` is not
    ``TEST`` (PR5 gate round 1, 2026-07-19 — fail-closed guard on the
    non-secret placeholder identity provider). Not present in spec §1's
    literal five-class ``errors.py`` snippet, added for the same reason
    ``ConditionStructureError`` was: a standalone, directly-testable failure
    mode that did not exist until ``evaluator.py`` needed a real identity
    provider contract. A caller running against a STAGING/PRODUCTION pack
    must inject a real crypto-backed ``evaluator.IdentityProvider`` instead
    of relying on the default.
    """
