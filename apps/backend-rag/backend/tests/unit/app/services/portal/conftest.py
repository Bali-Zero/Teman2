"""Per-test reset of PortalService's upload rate-limit state.

``PortalService._upload_rate_limits`` is a CLASS attribute, so every instance in a pytest
process shares it. Both ``test_portal_service.py`` and ``test_documents_mixin.py`` upload as
``client_id=1``; when ``--dist loadfile`` puts both files on one xdist worker the shared
window fills (10 uploads / 15 min) and the later test fails with "Rate limit exceeded".
Which worker gets which file depends on the worker count, so the failure appeared only
when the suite ran on two workers. Clearing the dict before each test removes the order
dependence without touching any assertion.
"""

import pytest

from backend.services.portal.portal_service import PortalService


@pytest.fixture(autouse=True)
def _reset_portal_upload_rate_limits():
    PortalService._upload_rate_limits.clear()
    yield
    PortalService._upload_rate_limits.clear()
