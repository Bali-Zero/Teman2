"""Local-only conftest: adds tools/ to sys.path so the standalone test modules can
`import nb2_query` / `import nb2_citation_audit` without the repo needing a package
install. This test suite is intentionally standalone — run via
`pytest research/visa/doctrine-factory/tools/tests -q`. It is NOT wired into the backend
pytest suite (apps/backend-rag/pytest.ini scopes testpaths to backend/tests only), matching
the precedent in research/operations/salvage-livekit-20260628/test_*.py: research tooling
tests are colocated and standalone, never joined to the main CI path.
"""
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
