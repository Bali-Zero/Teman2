"""Visa Oracle v2 rule engine — the only recommendation authority (spec §0.1).

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` and ``docs/plans/2026-07-17-visa-oracle-v2/00-product-
design.md``. Qdrant and LLMs may explain a persisted decision; they never
determine eligibility, candidates, rank, or price (spec §0 binding decision
#2). This package is greenfield and unused by any live surface until the
strangler adapters land in PR6 — it does not touch ``match_tree.py``,
``visa_oracle_service.py``, or any router.

PR1 delivers: typed contracts (``models.py``), the condition AST
(``ast.py``), the fact catalog (``fact_registry.py``), static RulePack
validation (``compiler.py``), JSON Schema export (``schema_export.py``), and
the error taxonomy (``errors.py``). Signing/verification (``bundle.py``),
the evaluator (``evaluator.py``, ``trace.py``), pricing/catalog/clock,
persistence (``repository.py``), and the v1 strangler adapters
(``compat.py``, ``service.py``) are later PRs — see each module's docstring
for exactly what it defers and why.
"""

from __future__ import annotations
