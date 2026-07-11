"""
Portal Services
- InviteService: Client invitation and onboarding
- PortalService: Client portal data access
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .invite_service import InviteService
    from .portal_service import PortalService

__all__ = ["InviteService", "PortalService"]


def __getattr__(name: str) -> Any:
    if name == "InviteService":
        from .invite_service import InviteService

        return InviteService
    if name == "PortalService":
        from .portal_service import PortalService

        return PortalService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
