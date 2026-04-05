"""
Conftest for backend/tests/unit/app/setup/ tests.

Mocks optional dependencies not installed in the test venv
so service_initializer tests can import analytics modules.
"""

import sys
from unittest.mock import MagicMock

# aiosmtplib is not installed in the test venv
# (weekly_email_reporter imports it at module level)
if "aiosmtplib" not in sys.modules:
    sys.modules["aiosmtplib"] = MagicMock()
