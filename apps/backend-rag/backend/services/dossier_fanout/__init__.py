"""Dossier Fanout — distribute ResearchDossier across 10 consumer types.

Reference: docs/war-room-2.0-design.md §16 (Dossier ammortizzato — 10 consumatori).

Sprint 14 wires the 5 priority consumers (design §16.1 rows 1-5):
    1. Zantara chatbot RAG        (Qdrant upsert)
    2. CRM compliance alerting    (SQL join)
    3. NotebookLM feeders         (CLI upload)
    4. KG Curiosity Loop          (gap close)
    5. War Room Director          (event notifier)

Future sprints (Parte II §20 Sprint scheduling) add:
    6. Newsletter · 7. Guardian V5 · 8. Team search · 9. Intel pubblica
    + 4 cognitive layer consumers (Connector/Anomaly/Strategos/Oracle)

Design principle: each consumer is a black box exposing ``consume(dossier) ->
ConsumeResult``. The dispatcher routes strictly by ``dossier.domains`` and
``ConsumerType`` — so adding/removing a consumer never touches dispatcher
logic.
"""

from backend.services.dossier_fanout.base import (
    ConsumeResult,
    DossierConsumer,
    FanoutSkipReason,
)
from backend.services.dossier_fanout.consumers import (
    CRMAlertingConsumer,
    CuriosityConsumer,
    NLMFeederConsumer,
    WarRoomDirectorConsumer,
    ZantaraRAGConsumer,
)
from backend.services.dossier_fanout.dispatcher import (
    DomainFanoutDispatcher,
    FanoutResult,
)
from backend.services.dossier_fanout.subscriber import (
    IntelEventSubscriber,
)

__all__ = [
    "CRMAlertingConsumer",
    "ConsumeResult",
    "CuriosityConsumer",
    "DomainFanoutDispatcher",
    "DossierConsumer",
    "FanoutResult",
    "FanoutSkipReason",
    "IntelEventSubscriber",
    "NLMFeederConsumer",
    "WarRoomDirectorConsumer",
    "ZantaraRAGConsumer",
]
