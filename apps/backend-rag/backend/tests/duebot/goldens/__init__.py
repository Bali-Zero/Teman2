"""Client-bot golden conversation fixtures (lane B6b).

Deferred out of B6a on purpose — see
``backend/tests/duebot/__init__.py``'s docstring — until B1 froze
``CanonicalMessage``/``BrainCandidate``/``GateVerdict``/``FinalDecision``
(``backend.channels.models`` / ``backend.services.client_bot.contracts`` /
``backend.services.client_bot.policy.types``). Each fixture here indexes
into the shared defect-class catalogue B6a built
(``backend.tests.duebot.defect_catalogue``) by ``defect_class_id`` — this
package is DATA ENTRY against that catalogue, not a second list.

There is no ``ClientBotEngine`` / ``FinalPolicyGate.evaluate()``
implementation yet (both explicitly out of scope for the B1a contract-
freeze unit — see ``contracts.py``/``policy/types.py`` module docstrings).
So these fixtures do not (yet) execute against live code; each one is a
GOLD STANDARD triple — (inbound ``CanonicalMessage``, the frozen
``GroundingBundle`` a provider would see, the ``BrainCandidate`` a
provider returned) paired with the ``FinalDecision`` a correct
``FinalPolicyGate`` MUST produce for it — that a future engine/gate test
suite asserts against. ``test_client_goldens.py`` verifies today what is
verifiable without that engine: every instance actually constructs against
the frozen pydantic contracts (catches a fixture that would fail
validation before any engine ever sees it), and that the catalogue is
covered.

Public surface:

- ``builders`` — deterministic constructors for every frozen contract type
  (``det_uuid``/``det_sha256`` derive stable ids from a ``case_id`` string,
  so fixtures are reviewable and diff-stable — never ``uuid.uuid4()``).
- ``fixtures`` — ``CLIENT_GOLDENS: tuple[ClientGoldenFixture, ...]``, the
  19 golden fixtures covering all 17 ``client.*`` defect classes (2 of the
  17 carry 2 fixtures each, for their named ``variants``).
"""

from __future__ import annotations
