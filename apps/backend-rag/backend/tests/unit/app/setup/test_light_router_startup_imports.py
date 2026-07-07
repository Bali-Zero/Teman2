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

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
