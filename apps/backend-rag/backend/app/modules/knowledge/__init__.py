"""
NUZANTARA PRIME - Knowledge Module
RAG, Search, and Vector Database Interface
"""

from app.modules.knowledge.router import router
from app.modules.knowledge.service import KnowledgeService

__all__ = ["KnowledgeService", "router"]
