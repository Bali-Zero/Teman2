"""Thin wire-up for scripts/ci/test_trusted_extraction_layout.py.

scripts/ci/*.py is never globbed by any pytest run in this repo (verified:
scripts-tests-sweep.yml collects only `scripts/tests/`, and every workflow that
runs a scripts/ci/*.py test names that exact file, never a directory pattern) —
so the corpus-in-the-flat-layout probe next to the files it protects would
otherwise never execute anywhere except by hand. Re-exporting its
unittest.TestCase here puts it on the nightly `scripts/tests/` sweep
(scripts-tests-sweep.yml, report-only) and the local pre-push habit of running
`pytest scripts/tests/`.

CONSUMER, HONESTLY STATED: this is NOT a per-PR gate. scripts-tests-sweep.yml is
`schedule:`-only and `continue-on-error: true` by design (cicatrix superscar #2
staging plan — see that workflow's own header). Wiring THIS specific probe into
a required per-PR check (mirroring how test_classifier_extraction_closure.py was
armed in immune-enforcement.yml) is the follow-up PR's job, not this one's.

Same basename as its scripts/ci/ counterpart is deliberate, not an oversight —
pytest never collects both in one run (scripts/ci/ is not swept, see above), so
the "import file mismatch" collision that basename would otherwise risk does not
arise in any wiring this repo actually runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CI_DIR = REPO / "scripts" / "ci"
sys.path.insert(0, str(CI_DIR))

from test_trusted_extraction_layout import (  # noqa: E402
    TrustedExtractionLayoutTests as TrustedExtractionLayoutTests,
)
