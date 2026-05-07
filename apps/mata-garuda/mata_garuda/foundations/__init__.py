"""Domain Mesh foundations layer (Phase 0).

Source spec: docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md §9
Source plan: docs/superpowers/plans/2026-05-08-domain-mesh-phase0-foundations.md

8 modules backed by R1-R7 SOTA research (2026-05-08):
- pasal_id_client (R2)        — 40k Indonesian regulations
- gov_apis_health (R2)        — gov portal status tracker
- bali_calendar (R6)          — Saka/Pawukon ceremonies
- gdelt_client (R6)           — Indonesia news raw signal
- opensanctions_id (R7)       — Indonesia sanctions/PEP
- ner_extractor (R7)          — bahasa NER (cahya BERT)
- arxiv_sanity_scorer (R5)    — personal relevance SVM
- openllmetry_init (R1)       — observability bootstrap
"""
from mata_garuda.foundations.arxiv_sanity_scorer import (
    ArxivSanityScorer,
    LabeledPaper,
)
from mata_garuda.foundations.bali_calendar import (
    BalineseDate,
    days_until_next_galungan,
    get_balinese_date,
    is_galungan,
    is_kuningan,
)
from mata_garuda.foundations.gdelt_client import GdeltArticle, GdeltClient
from mata_garuda.foundations.gov_apis_health import (
    HealthReport,
    PortalHealth,
    load_inventory,
    probe_inventory,
    probe_portal,
)
from mata_garuda.foundations.ner_extractor import NamedEntity, NERExtractor
from mata_garuda.foundations.openllmetry_init import (
    init_openllmetry,
    is_openllmetry_enabled,
)
from mata_garuda.foundations.opensanctions_id import (
    OpenSanctionsClient,
    SanctionEntity,
)
from mata_garuda.foundations.pasal_id_client import (
    LawSearchResult,
    LawStatus,
    PasalIdClient,
)

__all__ = [
    "ArxivSanityScorer",
    "BalineseDate",
    "GdeltArticle",
    "GdeltClient",
    "HealthReport",
    "LabeledPaper",
    "LawSearchResult",
    "LawStatus",
    "NERExtractor",
    "NamedEntity",
    "OpenSanctionsClient",
    "PasalIdClient",
    "PortalHealth",
    "SanctionEntity",
    "days_until_next_galungan",
    "get_balinese_date",
    "init_openllmetry",
    "is_galungan",
    "is_kuningan",
    "is_openllmetry_enabled",
    "load_inventory",
    "probe_inventory",
    "probe_portal",
]
