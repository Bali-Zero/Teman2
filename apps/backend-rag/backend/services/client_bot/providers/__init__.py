"""ClientBrainProvider implementations and the shared provider contract.

``base.py`` is the only module here owned by lane B1b (engine + provider
router). Concrete providers (``gemini.py``, ``codex_broker.py``,
``future_metered.py``) belong to other lanes (the existing Gemini spine,
B2's codex broker leg) and are intentionally absent — ``provider_router.py``
never imports a concrete provider module; it is constructed with an
injected ``Mapping[str, ClientBrainProvider]`` (F1.5 routing rule 1:
"Adapters call ClientBotEngine; they never import Gemini, Codex, or
provider environment variables" — the router itself does not import them
either, for the same reason).
"""

from __future__ import annotations
