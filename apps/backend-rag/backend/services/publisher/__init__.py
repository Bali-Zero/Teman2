"""Publisher — pluggable multi-platform publishing (Instagram, X, LinkedIn, Blog).

Reference: docs/war-room-2.0-design.md §9, M12.

Design contract:
    Publisher (ABC)
        async validate(draft) -> ValidationResult
        async publish(draft) -> PublishResult
        async delete(external_id) -> bool        # best-effort rollback
        property platform_name -> Platform

Concrete implementations:
    - IGPublisher: Meta Graph API v20 carousel (Sprint 7)
    - XPublisher:  X API v2 thread chained (Sprint 7)
    - LinkedInPublisher: REST API v2 posts (Sprint 8)
    - BlogPublisher: MDX + git commit (Sprint 8)
    - BlogBatchPublisher: N articles / single commit + daily cap (Sprint 19)
"""

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublisherError,
    PublishResult,
    SlidePayload,
    ValidationResult,
)
from backend.services.publisher.blog_batch_publisher import (
    HARD_DAILY_CAP,
    SOFT_DAILY_TARGET_MAX,
    SOFT_DAILY_TARGET_MIN,
    BatchResult,
    BlogBatchPublisher,
)
from backend.services.publisher.blog_publisher import BlogPublisher
from backend.services.publisher.ig_publisher import IGPublisher
from backend.services.publisher.linkedin_publisher import LinkedInPublisher
from backend.services.publisher.mdx_template import (
    MdxExtras,
    build_slug,
    calculate_reading_time_min,
    filename_for,
    render_full_mdx,
)
from backend.services.publisher.orchestrator import (
    KILL_SWITCH_ERROR,
    KILL_SWITCH_SETTING_KEY,
    PublisherOrchestrator,
    PublisherOrchestratorResult,
    build_db_kill_switch_check,
)
from backend.services.publisher.x_publisher import XPublisher

__all__ = [
    "BatchResult",
    "BlogBatchPublisher",
    "BlogPublisher",
    "DraftPayload",
    "HARD_DAILY_CAP",
    "IGPublisher",
    "KILL_SWITCH_ERROR",
    "KILL_SWITCH_SETTING_KEY",
    "LinkedInPublisher",
    "MdxExtras",
    "PublishResult",
    "Publisher",
    "PublisherError",
    "PublisherOrchestrator",
    "PublisherOrchestratorResult",
    "SOFT_DAILY_TARGET_MAX",
    "SOFT_DAILY_TARGET_MIN",
    "SlidePayload",
    "ValidationResult",
    "XPublisher",
    "build_db_kill_switch_check",
    "build_slug",
    "calculate_reading_time_min",
    "filename_for",
    "render_full_mdx",
]
