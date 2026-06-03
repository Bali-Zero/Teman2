import os
import subprocess

import pytest

LIVE = os.environ.get("WA_CORPUS_LIVE") == "1"


@pytest.mark.skipif(not LIVE, reason="set WA_CORPUS_LIVE=1 to run live NLM/Drive test")
def test_pilot_end_to_end():
    nb = os.environ["WA_CORPUS_TEST_NB"]  # a throwaway NB id
    r = subprocess.run(
        [
            "apps/backend-rag/.venv/bin/python",
            "-m",
            "scripts.wa_corpus.pilot",
            "--team",
            "+628133946856",
            "--counterpart",
            "+33614653019",
            "--nb",
            nb,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "."},
        timeout=600,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "citations:" in r.stdout
