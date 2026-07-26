import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_light_router_registration_does_not_eager_import_portal_document_pipeline() -> None:
    backend_root = Path(__file__).resolve().parents[5]
    script = textwrap.dedent(
        """
        import sys

        from fastapi import FastAPI

        from backend.app.setup.router_registration import include_light_routers

        app = FastAPI()
        include_light_routers(app)

        unexpected = [
            name
            for name in (
                "backend.services.portal.portal_service",
                "backend.services.portal.document_processing",
                "backend.services.multimodal.pdf_vision_service",
            )
            if name in sys.modules
        ]
        if unexpected:
            raise SystemExit(f"unexpected eager imports: {unexpected}")
        """
    )
    env = {**os.environ, "PYTHONPATH": "."}

    # The timeout is a FAILURE CEILING, not a performance assertion. What this
    # test checks is the exit code — whether `include_light_routers` eager-imports
    # the portal pipeline — and a subprocess that is merely slow tells us nothing
    # about that. The old 20s budget spawns a fresh interpreter that imports
    # FastAPI plus every light router: ~5s on an idle machine, but this repo's
    # pre-push runs the whole suite and several sessions push concurrently
    # (measured at load-average 50+ with 27 pre-push scripts running), and there
    # it blew straight past 20s and hard-blocked a push whose diff was one line
    # of JSON. Raising the ceiling weakens nothing — the assertion is unchanged
    # and a real eager import still fails in milliseconds.
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
