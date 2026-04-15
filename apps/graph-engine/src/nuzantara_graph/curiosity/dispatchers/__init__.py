"""Tier dispatchers for Curiosity Loop research.

# Organo: graph-engine/curiosity/dispatchers → produce ResearchEvidence → consuma da orchestrator

Three tiers:
  Tier 1 (Simple): Ollama qwen3.5:9b local generation + template follow-ups
  Tier 2 (Medium): HyDE-style query expansion + web search
  Tier 3 (Complex): Deep research dispatch (background, async)
"""
from nuzantara_graph.curiosity.dispatchers.simple import SimpleDispatcher
from nuzantara_graph.curiosity.dispatchers.medium import MediumDispatcher
from nuzantara_graph.curiosity.dispatchers.complex import ComplexDispatcher

__all__ = ["SimpleDispatcher", "MediumDispatcher", "ComplexDispatcher"]
