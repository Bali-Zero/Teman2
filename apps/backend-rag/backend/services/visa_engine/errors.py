"""Error hierarchy for the Visa Engine v2.

Every exception raised anywhere in ``backend.services.visa_engine`` derives
from :class:`VisaEngineError`, so callers can catch the whole family with a
single ``except VisaEngineError`` while still discriminating on the precise
failure mode when they need to (e.g. compilation failure vs. signature
failure vs. missing persistence).

Pure module: no I/O, no third-party imports.
"""

from __future__ import annotations


class VisaEngineError(Exception):
    """Base class for every error raised by the visa engine."""


class RulePackUnavailableError(VisaEngineError):
    """No active, loadable RulePack could be found for the requested scope.

    Raised by the repository/service layers (PR2+) when a query for the
    active bundle for an environment/effective-at window returns nothing.
    """


class RulePackVerificationError(VisaEngineError):
    """A RulePack envelope failed signature or trust-store verification.

    Raised by ``bundle.py`` (PR2+) — never by PR1's ``compiler.py``, which
    only ever receives an already schema-validated ``RulePack`` model.
    """


class RulePackCompilationError(VisaEngineError):
    """A schema-valid ``RulePack`` failed a compiler invariant.

    Examples: AST depth/node-count limits exceeded, too many rules/products,
    a condition references an unregistered fact path, or a ``RANKING`` stage
    rule references a non-commercial (legal) fact.
    """


class FactValidationError(VisaEngineError):
    """Applicant facts could not be validated or resolved.

    Raised by :class:`~backend.services.visa_engine.fact_registry.FactRegistry`
    when asked for the :class:`FactSpec` of an unregistered fact path.
    """


class PersistenceRequiredError(VisaEngineError):
    """An operation required durable persistence that was unavailable.

    Raised by the repository/service layers (PR2+) — e.g. a decision could
    not be saved, so no ``decision_id``/``public_id`` can be minted.
    """
