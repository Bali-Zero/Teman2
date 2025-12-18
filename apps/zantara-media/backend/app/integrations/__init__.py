"""
ZANTARA MEDIA - Integration Clients
Connects to NUZANTARA ecosystem and INTEL SCRAPING system
"""

from app.integrations.nuzantara_client import NuzantaraClient
from app.integrations.intel_client import IntelClient

__all__ = ["NuzantaraClient", "IntelClient"]
