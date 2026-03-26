"""
Workflow Chain Executors.

Each module registers its chains via @register_chain decorator.
Import this package at startup to ensure all chains are registered.
"""

from backend.services.workflow.chains import intel  # noqa: F401

__all__ = ["intel"]
