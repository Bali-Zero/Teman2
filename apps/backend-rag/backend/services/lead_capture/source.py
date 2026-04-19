"""LeadSource enum — the 6 homepage apps that can emit a lead intent.

Kept in a dedicated module so pydantic models, repository, routers,
and the matcher cron all import from one place and stay in sync.
"""

from __future__ import annotations

from enum import Enum


class LeadSource(str, Enum):
    VISA_CLOCK = "visa_clock"
    VISA_MATCH = "visa_match"
    KBLI_DECODER = "kbli_decoder"
    KBLI_BUILDER = "kbli_builder"
    TAX_GAP = "tax_gap"
    ZONING_CHECK = "zoning_check"

    @property
    def human_name(self) -> str:
        """Human-friendly name for the WhatsApp deeplink template."""
        return {
            LeadSource.VISA_CLOCK: "Visa Clock",
            LeadSource.VISA_MATCH: "Visa Match",
            LeadSource.KBLI_DECODER: "KBLI Decoder",
            LeadSource.KBLI_BUILDER: "KBLI Builder",
            LeadSource.TAX_GAP: "Tax Gap",
            LeadSource.ZONING_CHECK: "Zoning Check",
        }[self]

    @property
    def result_url_path(self) -> str:
        """The public result URL path for a given source (without host)."""
        return {
            LeadSource.VISA_CLOCK: "/visa/clock",
            LeadSource.VISA_MATCH: "/visa/match",
            LeadSource.KBLI_DECODER: "/kbli/decoder",
            LeadSource.KBLI_BUILDER: "/kbli/builder",
            LeadSource.TAX_GAP: "/tax/gap",
            LeadSource.ZONING_CHECK: "/zoning",
        }[self]
