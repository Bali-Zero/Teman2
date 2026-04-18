"""Handler package. Importing the package self-registers each handler
via register_job() at module-import time.

Scope: only the two legacy jobs with backend-side entry points.
Consiglio v1 and KG Curiosity Loop v1 live outside backend/ (Air-side
cron / apps/evaluator); their migration to the runner is a follow-up PR.
"""
from backend.jobs.handlers import (  # noqa: F401
    auto_practice_creator,
    conversation_cleanup,
)
