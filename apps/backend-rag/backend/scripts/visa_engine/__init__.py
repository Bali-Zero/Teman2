"""Offline authoring/signing CLIs for the Visa Oracle v2 rule engine.

Spec §1's module-layout snippet (``research/visa/2026-07-17-visa-oracle-v2-
round2-codex-engine-concretization.md``) prescribes this package's location
and its first two members: ``compile_pack.py`` (validate + statically
compile a RulePack payload source) and ``sign_pack.py`` (the offline Ed25519
signing ceremony). Neither runs inside the FastAPI process — both are
operator-invoked tooling, run from a terminal via ``python -m``.
"""

from __future__ import annotations
