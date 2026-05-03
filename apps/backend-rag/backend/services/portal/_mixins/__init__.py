"""
Portal service mixins (internal).

Each mixin groups a cohesive slice of PortalService methods (messaging,
billing, dashboard, documents, ...). They are composed into the public
PortalService class in portal_service.py.

Mixins are considered an implementation detail — import PortalService
from backend.services.portal instead.
"""
