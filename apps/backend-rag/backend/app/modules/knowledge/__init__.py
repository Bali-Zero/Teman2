"""
NUZANTARA PRIME - Knowledge Module
RAG, Search, and Vector Database Interface
"""

from backend.app.modules.knowledge.router import router
from backend.app.modules.knowledge.service import KnowledgeService

__all__ = ["KnowledgeService", "router"]
